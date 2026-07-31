# Local Text Calibration Design

Date: `2026-07-31`

## Purpose

Add an optional local-language-model pass that reviews English ASR text one
sentence at a time, uses the previous three sentences as context, and applies
only high-confidence, deterministically validated corrections before subtitle
export.

The calibration pass is a backend-neutral postprocessor. It runs after the ASR
provider has completed transcription, forced alignment, window merging, timing
repair, and final segment construction. It runs before SRT, VTT, and JSON
rendering.

## Goals

- Correct demonstrable English ASR spelling, homophone, wrong-word,
  short-phrase, and context-supported proper-name errors.
- Preserve subtitle segment boundaries, correction-unit boundaries, ordering,
  and timestamps.
- Let replacement text become longer or shorter, including changes in word
  count such as `two -> to`.
- Give the model the previous three calibrated sentences as read-only context.
- Require every proposed replacement to identify an exact source range and
  assign itself a confidence score from 1 through 5.
- Automatically apply only scores 4 and 5 that pass deterministic validation.
- Keep low-confidence output out of all public artifacts.
- Produce a compact per-media calibration audit file.
- Preserve original token text and acoustic timing rather than inventing new
  token alignment.
- Run entirely locally on Apple Silicon with a pinned MLX model.
- Evaluate the pinned real model locally against labelled and full-transcript
  datasets before considering the feature complete.

## Non-Goals

- Do not perform grammar polishing, style rewriting, punctuation cleanup,
  capitalization cleanup, filler removal, summarisation, or factual rewriting.
- Do not translate text.
- Do not split, merge, delete, or paraphrase whole sentences.
- Do not run a second forced-alignment pass.
- Do not rewrite or synthesize token timestamps.
- Do not expose a general text-model provider selector.
- Do not support Ollama, llama.cpp, an HTTP model service, or a non-MLX runtime
  in the first version.
- Do not enable calibration by default.
- Do not run the real MLX model in the existing Ubuntu GitHub workflow.
- Do not parallelize correction units within a media file; rolling calibrated
  context makes processing sequential.
- Do not add target-text truncation or context-overflow behavior. The accepted
  input constraint is that the previous three sentences plus the target fit
  within the selected model context.

## Current Processing Boundary

The current public flow is:

```text
prepare media
-> optional VAD
-> provider transcription + alignment
-> window quality and merge
-> segment construction
-> render SRT / VTT / JSON
-> write outputs
```

The new flow is:

```text
prepare media
-> optional VAD
-> provider transcription + alignment
-> window quality and merge
-> segment construction
-> optional local text calibration
-> render SRT / VTT / JSON
-> write outputs + calibration JSON
```

`process_media_file()` remains an ASR-only function returning
`TranscriptionDocument`. The CLI invokes a separate backend-neutral
`calibrate_document()` operation immediately after it and before any exporter.
This preserves existing integrations and keeps text-model behavior out of
`QwenMlxProvider`.

Conceptually:

```python
document = process_media_file(...)

if calibrate:
    document, calibration_result = calibrate_document(
        document,
        corrector=corrector,
    )

render_outputs(document)
write_calibration_result(calibration_result)
```

## CLI and Installation Contract

Calibration is explicitly enabled:

```text
easr INPUT --calibrate
```

Without `--calibrate`, the command does not import, construct, load, or preflight
the calibration runtime. Existing CLI behavior and output schemas remain
unchanged.

`mlx-vlm` is added to the existing `mlx` optional dependency group:

```text
pip install "echoalign-asr-mlx[mlx]"
```

There is no separate calibration extra in the first version. Adding
`mlx-vlm` requires refreshing the lockfile and running the existing ASR, VAD,
provider, and exporter regressions under Python 3.14.

## Model Contract

The first calibration model is:

```text
model_id = mlx-community/Qwen3.5-4B-MLX-4bit
revision = 32f3e8ecf65426fc3306969496342d504bfa13f3
runtime = mlx-vlm
```

The revision is pinned so a repository update cannot silently change
calibration behavior. A model upgrade is an explicit code and baseline change.

The model is used in text-only mode. Vision input is never constructed.

The model repository is approximately 2.9GB on disk, uses 4-bit quantized MLX
weights, and is licensed under Apache-2.0:

- https://huggingface.co/mlx-community/Qwen3.5-4B-MLX-4bit

The standard Hugging Face cache is used. The pinned snapshot downloads
automatically on the first `--calibrate` run and is reused afterward. There is
no custom model path or fallback model in the first version.

### Model Lifetime

- Construct the corrector only when `--calibrate` is present.
- Load the model lazily when the first eligible correction unit is reached
  after ASR has completed for that file.
- Keep the loaded corrector resident across all remaining sentences and files
  in the CLI run.
- Keep the ASR and aligner models resident as they are today.
- Do not unload and reload the corrector per file.
- If the first model load fails, remember that failure for the run and do not
  repeat the load for every later file.

## Text Model

### Recognition Text and Calibrated Text

`Recognition Text` is the immutable ASR-provider text associated with original
tokens and timestamps.

`Calibrated Text` is the sentence-level text after accepted replacements. It
preserves subtitle structure and timing but may differ in character length or
word count.

### Correction Unit

A correction unit is exactly one sentence-like, continuous source range within
one final subtitle segment. Units are derived deterministically from Recognition
Text before the first model call.

The splitter must:

- preserve exact source offsets;
- use sentence-ending punctuation such as `.`, `?`, and `!` as primary
  boundaries;
- retain terminal punctuation and following closing quotes in the unit;
- avoid false boundaries for common abbreviations, initials, and decimal
  numbers such as `Dr.`, `U.S.`, and `3.14`;
- emit trailing text without terminal punctuation as a final unit;
- never ask the language model to choose unit boundaries; and
- produce stable chronological identifiers such as `seg-3:unit-2`.

A correction unit never crosses a subtitle-segment boundary. Correction context
may cross segment boundaries.

### English-Primary Eligibility

- A target unit is eligible when it contains at least one English word.
- A mixed-language unit is eligible.
- Only English words or English phrases may be changed.
- Non-English content may be supplied as read-only context.
- A wholly non-English unit is skipped without creating a result entry.

### Rolling Correction Context

For each target, the model receives:

```text
up to three immediately preceding correction units
+ the current target correction unit
```

Context never crosses a media-file boundary. At the beginning of a file, use the
available zero, one, or two preceding units.

Processing is chronological and sequential. When an earlier unit has Applied
Corrections, its Calibrated Text becomes context for later targets. Unchanged,
rejected, or failed units contribute their Recognition Text. Context units are
read-only, and every returned position is interpreted against the current
target's Recognition Text.

This rolling behavior is recorded in ADR 0002.

## Prompt Policy

The system prompt defines the calibration task narrowly.

Allowed:

- spelling mistakes;
- homophone or near-homophone recognition mistakes;
- contextually demonstrable wrong English words or short phrases; and
- proper-name errors supported by the supplied context.

Forbidden:

- grammar polishing;
- stylistic editing;
- punctuation changes;
- capitalization changes;
- filler or repetition removal;
- rewriting or paraphrasing;
- summarisation;
- translation; and
- factual correction not evidenced by the text context.

The prompt labels the preceding sentences as read-only context and the final
sentence as the only target. It defines the score rubric:

```text
1 = speculative, almost no contextual evidence
2 = possible, with several plausible interpretations
3 = plausible but materially ambiguous
4 = strong context supports a unique or nearly unique correction
5 = effectively certain from a fixed phrase, repeated context, or explicit name
```

Only scores 4 and 5 are eligible for validation and application.

The prompt has an explicit policy version. The calibration result records that
version together with the pinned model revision.

## Generation Policy

Use deterministic, compact generation:

```text
enable_thinking = false
temperature = 0
fixed small output-token budget
```

The model must output only JSON and no prose, Markdown fences, evidence text, or
reasoning content.

## Model Response

The complete accepted response shape is:

```json
{
  "proposals": [
    {
      "start": 12,
      "end": 15,
      "source": "two",
      "replacement": "to",
      "score": 5
    }
  ]
}
```

No proposed changes:

```json
{"proposals": []}
```

Field semantics:

- `start` is the zero-based Unicode-code-point start offset in the target
  Recognition Text.
- `end` is the exclusive Unicode-code-point end offset.
- `source` echoes the exact intended source slice.
- `replacement` is the local replacement and may be shorter or longer.
- `score` is an integer from 1 through 5.

The response intentionally omits `unit_id`, `has_error`, explanations,
evidence, manual-review arrays, and raw reasoning. One model request has exactly
one target, so those fields are unnecessary.

## Response Parsing and Retries

One target may make at most four model calls:

```text
initial attempt + at most three retries
```

Retry only response-structure failures:

- invalid JSON;
- missing or non-array `proposals`;
- missing required proposal fields;
- incorrect field types; or
- a score outside the integer range 1 through 5.

Each retry receives the same correction context plus a concise description of
the structure error. Raw invalid model output is not persisted.

Do not retry deterministic proposal-validation failures such as a source
mismatch, invalid position, or overlap. If all three retries are exhausted,
record a unit error, leave the target unchanged, and continue with later units.

## Confidence Gate

Apply the confidence gate before deterministic proposal validation:

- scores 1, 2, and 3 are discarded silently;
- scores 4 and 5 become validation candidates.

Discarded low-confidence output is not written to the calibration result and
does not influence later rolling context.

## Deterministic Proposal Validation

Each high-confidence candidate must pass:

1. `score` is the integer 4 or 5.
2. `0 <= start < end <= len(target_text)`.
3. `target_text[start:end] == source` using exact comparison.
4. `source` and `replacement` are both non-empty.
5. `source != replacement`.
6. `source` contains at least one English character.
7. `replacement` contains no newline.
8. Applying the proposal preserves exactly one correction unit and does not
   add, remove, split, or merge sentence boundaries.

Completely identical proposals are deduplicated.

For any other overlapping proposals:

- identify the complete overlap-connected conflict group;
- reject every proposal in that group with `overlapping_ranges`; and
- continue validating and applying non-overlapping proposals outside the group.

Stable rejection codes include:

```text
invalid_range
source_mismatch
empty_source
empty_replacement
no_change
no_english_source
newline_replacement
structure_changed
overlapping_ranges
```

Semantic scope is enforced by the prompt and model score. The deterministic
validator does not pretend it can distinguish proofreading from transcription
correction.

## Applying Corrections

All proposal positions refer to the original target text. Validate the complete
proposal set before mutation, then apply accepted replacements from the highest
`start` offset to the lowest. This prevents an earlier variable-length
replacement from shifting later source positions.

Correction units and their absolute segment offsets are derived from Recognition
Text and remain stable for the run. When multiple units in one segment change,
rebuild final segment text by applying all accepted absolute segment edits from
right to left.

Once a unit's valid replacements are applied, its Calibrated Text is immediately
available as rolling context for the next target.

## Canonical Data and Token Semantics

Extend `Segment` with optional original text:

```python
@dataclass(slots=True)
class Segment:
    id: str
    text: str
    start_time: float
    end_time: float
    language: str | None
    tokens: list[Token]
    speaker: str | None = None
    original_text: str | None = None
```

Semantics:

- `text` is final sentence-level display text.
- `original_text` is Recognition Text and is set only when at least one
  correction changed that segment.
- `tokens` retain original ASR text and timestamps.
- calibration never changes token text, count, unit, language, or timing.

Sentence-granularity SRT, VTT, and JSON views use `Segment.text`.

Token-granularity views continue to use the original tokens. This intentional
dual representation is recorded in ADR 0001.

### JSON Compatibility

- Serialize `original_text` only for segments that changed.
- Omit the key entirely for unmodified segments.
- When calibration is disabled, public JSON keeps the existing segment schema
  unchanged.
- Calibration status and detailed audit data live only in the separate
  calibration result, not in the main transcript JSON.

## Calibration Result

When `--calibrate` is present, always write:

```text
<media-name>.calibration.json
```

It is written beside the SRT, VTT, and transcript JSON, including when there are
no corrections or calibration fails.

The compact shape is:

```json
{
  "status": "success",
  "source_path": "demo.mp4",
  "model": "mlx-community/Qwen3.5-4B-MLX-4bit",
  "model_revision": "32f3e8ecf65426fc3306969496342d504bfa13f3",
  "policy_version": "1",
  "corrected_units": [
    {
      "unit_id": "seg-3:unit-2",
      "segment_id": "seg-3",
      "original_text": "I want two go.",
      "corrected_text": "I want to go.",
      "applied": [
        {
          "start": 7,
          "end": 10,
          "source": "two",
          "replacement": "to",
          "score": 5
        }
      ]
    }
  ],
  "rejected_proposals": [],
  "unit_errors": []
}
```

Rules:

- Do not include unchanged units.
- Do not include scores 1 through 3.
- Record each high-confidence validation failure with its `unit_id`, proposal,
  and stable rejection code.
- Record each retry-exhausted unit with its `unit_id`, four attempts, and stable
  error code.
- Add a top-level `error` when model initialization fails.
- Never persist raw model responses, retry responses, prompt bodies, or model
  reasoning.

Status meanings:

- `success`: the model initialized and every eligible unit completed, even if
  some high-confidence proposals were deterministically rejected.
- `partial`: at least one unit exhausted response retries; other valid
  corrections remain applied.
- `failed`: the calibration runtime or model could not initialize; the
  transcription remains uncalibrated.

## Failure and Exit-Code Semantics

### Model Initialization Failure

- Preserve and export the original ASR SRT, VTT, and JSON.
- Write a `failed` calibration result.
- Print a clear stderr error.
- Return CLI exit code 1.
- Do not fall back to another text model.
- Do not retry initialization for later batch files in the same run.

### Unit Failure

- Keep the failed unit's Recognition Text.
- Continue processing later units.
- Retain corrections already validated for other units.
- Write a `partial` calibration result.
- Return CLI exit code 1.

### Rejected Proposal

A rejected proposal is an expected safe outcome, not an operational failure:

- do not apply it;
- record it;
- continue processing; and
- keep status `success` and exit code 0 when there are no unit or initialization
  failures.

## Observability

Add calibration-level observability without emitting noisy default logs for
every sentence.

Recommended steps:

```text
calibration_model_load
calibrate_text
render_calibration_json
```

Verbose metrics should expose at least:

- eligible unit count;
- model request count;
- retry count;
- low-confidence discard count;
- applied proposal count;
- corrected unit count;
- rejected proposal count;
- unit error count;
- model-load duration; and
- calibration duration.

The compact default console output remains unchanged unless calibration fails.

## Automated Tests

Normal unit tests remain network-free and use fake correctors or fake generation
backends. They must cover:

- deterministic sentence splitting and exact offsets;
- abbreviation, decimal, quote, and trailing-fragment boundaries;
- same-media context crossing subtitle segments;
- rolling use of previously Calibrated Text;
- English-primary eligibility;
- minimal JSON parsing;
- initial attempt plus three retries;
- retry versus deterministic rejection boundaries;
- confidence score rubric and gate;
- exact source matching;
- variable-length replacement;
- stable right-to-left application;
- duplicate and overlap handling;
- structure preservation;
- original versus calibrated segment serialization;
- unchanged raw tokens and token-granularity output;
- calibration-result rendering;
- success, partial, and failed behavior;
- exit codes;
- lazy import and model loading; and
- CLI behavior with and without `--calibrate`.

The existing Ubuntu GitHub workflow continues to run the network-free suite.
It does not install or execute the real MLX model.

## Required Local Real-Model Evaluation

The feature is not complete until the pinned model is downloaded and evaluated
locally on Apple Silicon.

### Labelled Quality Gate

Create at least 100 labelled correction units from real ASR material:

- 50 units with verified correctable errors;
- 50 verified clean units.

The error set covers:

- spelling;
- homophone or near-homophone;
- wrong word or short phrase; and
- proper name.

An error may list multiple acceptable source-range and replacement answers.
Each unit retains its preceding three-sentence context.

Required thresholds:

```text
applied-proposal precision >= 95%
correctable-error recall >= 70%
clean-unit false-modification rate <= 2%
subtitle structure or timestamp changes = 0
retry-exhausted units = 0
```

### Full Real-ASR Observation

Run the corrector over every English correction unit in the existing
`tests/e2e/outputs/Metal Gear Solid Delta.json`, which currently contains 1,334
real ASR segments. This evaluation reads the saved transcript rather than
rerunning the approximately 88-minute audio, so it isolates correction-model
behavior.

Persist:

- the full compact calibration result;
- aggregate counts and score distributions;
- retry and rejection distributions; and
- a reviewable list of every applied correction.

The unlabelled full run is an observation artifact, not a quality pass/fail
oracle.

### Short End-to-End Check

Run a short audio slice through:

```text
media -> ASR -> alignment -> calibration -> all exporters
```

This verifies the CLI, lazy model download/load, corrected output, raw tokens,
calibration artifact, and exit semantics together.

### Versioned Evaluation Artifacts

Commit:

- labelled fixtures and accepted answers;
- pinned-model metrics;
- the compact full-transcript calibration result; and
- the short end-to-end result.

Do not commit:

- model caches or weights;
- raw prompts;
- raw model responses;
- retry response bodies; or
- hidden reasoning.

Store new baselines alongside old ones when the model revision or prompt policy
version changes.

## Documentation Updates

Implementation must update:

- `README.md` with `--calibrate`, first-download behavior, outputs, failure
  semantics, and token-granularity caveat;
- `docs/development.md` with the local real-model evaluation command and
  baseline update procedure;
- CLI help and compatibility parser tests; and
- installation notes for the expanded `mlx` extra.

## Acceptance Criteria

- Existing non-calibration behavior and tests remain unchanged.
- `--calibrate` is opt-in and loads only the pinned model revision.
- Model calls use the previous three rolling calibrated sentences and one
  Recognition Text target.
- Only strict JSON proposals are accepted.
- A target receives at most four generation attempts.
- Scores 1 through 3 leave no public trace.
- Scores 4 and 5 are applied only after all deterministic checks.
- Variable-length replacements preserve correction-unit, segment, and timestamp
  structure.
- Sentence-level outputs use calibrated text.
- Token-level text and timing remain original.
- Every requested run writes a calibration result, including empty and failed
  runs.
- Partial and failed calibration return exit code 1 while preserving outputs.
- The labelled real-model evaluation meets every agreed threshold.
- Full real-ASR and short end-to-end evaluation artifacts are committed.
