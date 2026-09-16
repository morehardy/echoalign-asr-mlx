"""Lazy MLX-VLM adapter for the pinned local calibration model."""

from __future__ import annotations

import gc
import json
import re
from typing import Any

from asr.calibration import (
    CALIBRATION_MODEL_ID,
    CALIBRATION_MODEL_REVISION,
    CALIBRATION_POLICY_VERSION,
    CalibrationGenerationError,
    CalibrationModelError,
)
from asr.observability.observer import Observer
from asr.observability.timing import observe_step

_MAX_OUTPUT_TOKENS = 256
_ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposals"],
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "start",
                    "end",
                    "source",
                    "replacement",
                    "score",
                ],
                "properties": {
                    "start": {"type": "integer", "minimum": 0},
                    "end": {"type": "integer", "minimum": 1},
                    "source": {"type": "string"},
                    "replacement": {"type": "string"},
                    "score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
            },
        }
    },
}

_SYSTEM_PROMPT = """\
You calibrate English ASR subtitles. Review only the TARGET sentence, using
CONTEXT as read-only evidence.

Allowed changes: demonstrable spelling, homophone/near-homophone, wrong English
word or short phrase, and context-supported proper-name ASR errors.
Forbidden changes: grammar/style polishing, punctuation or capitalization
cleanup, filler/repetition removal, paraphrase, summary, translation, and
factual rewriting.

Most TARGET sentences are already correct. Return no proposal unless the error
is an ASR-like acoustic mistake. A score-4/5 replacement MUST satisfy at least
one evidence rule:
1. source and replacement are a close spelling or sound match; or
2. replacement is a name/term repeated verbatim in CONTEXT.
If neither rule holds, the score is at most 3 and the proposal must be omitted.
Never replace a fluent word with a merely related word from CONTEXT. Dialogue
fragments and informal speech are valid; do not make them more grammatical.
Never add a missing grammar word, change tense/agreement/inflection, or remove
repetition. Change the smallest mistaken source span and preserve every correct
neighboring word. A multi-word homophone must be one proposal covering the
whole phrase, not separate guesses for its words.

Return JSON only:
{"proposals":[{"start":0,"end":1,"source":"x","replacement":"y","score":5}]}
or {"proposals":[]}.
Do not use Markdown fences.

Offsets are zero-based Unicode code-point offsets into TARGET; end is exclusive.
source must exactly equal TARGET[start:end]. Replacements may change character
or word count but must not split, merge, delete, or paraphrase the sentence.
Use the supplied ENGLISH TOKEN SPANS to copy the exact start and exclusive end.
For one-word corrections, copy that token's complete span. For a short phrase,
use the first token's start and the last token's end.
If source equals one token's text, start and end MUST come from that same token
entry; never borrow an adjacent token's offset. The span list is authoritative.
Before returning, verify for every proposal that TARGET[start:end] is exactly
identical to source. If you cannot verify the range, omit that proposal.
Score each proposal independently:
1 speculative; 2 possible; 3 ambiguous; 4 strong/nearly unique; 5 effectively
certain. Use 4 or 5 only with strong contextual evidence.

Examples:
- TARGET "We have two catch the train." with token span
  {"start":8,"end":11,"text":"two"} returns
  {"proposals":[{"start":8,"end":11,"source":"two","replacement":"to","score":5}]}.
- TARGET "Yeah, what kind of chance?" returns {"proposals":[]}; "Yeah" is not
  an ASR error and must not become "Yes".
- TARGET "Must be part of the top brass's inquiry." returns {"proposals":[]};
  a dialogue fragment is not a grammar error.
- TARGET "my flower over the military" corrects the sound-alike token
  "flower" to "power"; it must not guess a related word such as "force".
- If CONTEXT says "Colonel Volgin" and TARGET says "Colonel Vulcan", replace
  exactly "Vulcan" with the repeated name "Volgin".
- TARGET "miniature new clear shells" uses one phrase proposal replacing
  "new clear" with "nuclear"; do not rewrite "new" and "clear" separately.
- TARGET "Fox is going two die" replaces exactly "two" with "to"; never add
  "to" after "going", because adding a grammar word is forbidden.
Policy version: """ + CALIBRATION_POLICY_VERSION


def _build_user_prompt(
    context: list[str],
    target: str,
    retry_error: str | None,
) -> str:
    context_lines = "\n".join(
        f"{index}. {text}" for index, text in enumerate(context, start=1)
    )
    if not context_lines:
        context_lines = "(none)"
    retry = ""
    if retry_error:
        retry = (
            "\nYour previous response had this schema error: "
            f"{retry_error}. Return only the required JSON object."
        )
    token_spans = [
        {
            "start": match.start(),
            "end": match.end(),
            "text": match.group(),
        }
        for match in _ENGLISH_TOKEN_RE.finditer(target)
    ]
    return (
        f"CONTEXT (read-only):\n{context_lines}\n\n"
        f"TARGET:\n{target}\n\n"
        "ENGLISH TOKEN SPANS:\n"
        f"{json.dumps(token_spans, ensure_ascii=False, separators=(',', ':'))}\n"
        f"TARGET LENGTH: {len(target)}\n\n"
        "FINAL CHECK: propose only the mistaken token/phrase itself. Do not "
        "edit a correct neighbor, add a grammar word, change inflection, or "
        "copy a merely related context word. If uncertain, return "
        f'{{"proposals":[]}}.{retry}'
    )


class MlxVlmCorrector:
    """Load once on first eligible target and generate strict proposal JSON."""

    def __init__(self) -> None:
        self._model: Any = None
        self._processor: Any = None
        self._generate: Any = None
        self._apply_chat_template: Any = None
        self._build_schema_processor: Any = None
        self._load_error: CalibrationModelError | None = None
        self._observer: Observer | None = None
        self._run_id = "run-unknown"
        self._file_id: str | None = None
        self._source_path: str | None = None

    def bind_observer(
        self,
        *,
        observer: Observer,
        run_id: str,
        file_id: str,
        source_path: str,
    ) -> None:
        self._observer = observer
        self._run_id = run_id
        self._file_id = file_id
        self._source_path = source_path

    def clear_observer(self) -> None:
        self._observer = None
        self._file_id = None
        self._source_path = None

    def _ensure_loaded(self) -> None:
        if self._load_error is not None:
            raise self._load_error
        if self._model is not None:
            return
        try:
            with observe_step(
                self._observer,
                run_id=self._run_id,
                file_id=self._file_id,
                source_path=self._source_path,
                step="calibration_model_load",
            ):
                from mlx_vlm import apply_chat_template, generate, load
                from mlx_vlm.structured import build_json_schema_logits_processor

                model, processor = load(
                    CALIBRATION_MODEL_ID,
                    revision=CALIBRATION_MODEL_REVISION,
                )
        except Exception as exc:
            error = CalibrationModelError(
                f"unable to load calibration model: {exc}"
            )
            self._load_error = error
            raise error from exc
        self._model = model
        self._processor = processor
        self._generate = generate
        self._apply_chat_template = apply_chat_template
        self._build_schema_processor = build_json_schema_logits_processor

    def generate(
        self,
        context: list[str],
        target: str,
        retry_error: str | None = None,
    ) -> str:
        self._ensure_loaded()
        schema_processor: Any = None
        try:
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_prompt(context, target, retry_error),
                },
            ]
            prompt = self._apply_chat_template(
                self._processor,
                self._model.config,
                messages,
                enable_thinking=False,
            )
            tokenizer = getattr(self._processor, "tokenizer", self._processor)
            schema_processor = self._build_schema_processor(
                tokenizer,
                _RESPONSE_SCHEMA,
            )
            output = self._generate(
                self._model,
                self._processor,
                prompt=prompt,
                max_tokens=_MAX_OUTPUT_TOKENS,
                temperature=0,
                enable_thinking=False,
                logits_processors=[schema_processor],
                verbose=False,
            )
            return str(output.text)
        except Exception as exc:
            raise CalibrationGenerationError(
                f"calibration generation failed: {exc}"
            ) from exc
        finally:
            cleanup_error: Exception | None = None
            reset_schema_processor: Any = None
            if schema_processor is not None:
                try:
                    reset_schema_processor = getattr(schema_processor, "reset", None)
                    if callable(reset_schema_processor):
                        reset_schema_processor()
                except Exception as exc:
                    cleanup_error = exc
            schema_processor = None
            reset_schema_processor = None
            gc.collect()
            if cleanup_error is not None:
                raise CalibrationGenerationError(
                    f"calibration schema cleanup failed: {cleanup_error}"
                ) from cleanup_error
