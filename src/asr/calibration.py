"""Context-aware, structure-preserving text calibration."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, List, Protocol, Sequence, Tuple

from asr.models import TranscriptionDocument

CALIBRATION_MODEL_ID = "mlx-community/Qwen3.5-4B-MLX-4bit"
CALIBRATION_MODEL_REVISION = "32f3e8ecf65426fc3306969496342d504bfa13f3"
CALIBRATION_POLICY_VERSION = "1"
_ENGLISH_RE = re.compile(r"[A-Za-z]")

_CLOSING_QUOTES = frozenset("\"'”’»)]}")
_COMMON_ABBREVIATIONS = frozenset(
    {
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
        "prof.",
        "sr.",
        "jr.",
        "st.",
        "vs.",
        "etc.",
        "e.g.",
        "i.e.",
        "u.s.",
        "u.k.",
    }
)


class TextCorrector(Protocol):
    def generate(
        self,
        context: list[str],
        target: str,
        retry_error: str | None = None,
    ) -> str: ...


class CalibrationModelError(RuntimeError):
    """The pinned calibration model could not be initialized."""


class CalibrationGenerationError(RuntimeError):
    """One model generation call failed after initialization."""


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    start: int
    end: int
    source: str
    replacement: str
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "replacement": self.replacement,
            "score": self.score,
        }


@dataclass(slots=True)
class CalibrationMetrics:
    eligible_unit_count: int = 0
    model_request_count: int = 0
    retry_count: int = 0
    low_confidence_discard_count: int = 0
    applied_proposal_count: int = 0
    corrected_unit_count: int = 0
    rejected_proposal_count: int = 0
    unit_error_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "eligible_unit_count": self.eligible_unit_count,
            "model_request_count": self.model_request_count,
            "retry_count": self.retry_count,
            "low_confidence_discard_count": (
                self.low_confidence_discard_count
            ),
            "applied_proposal_count": self.applied_proposal_count,
            "corrected_unit_count": self.corrected_unit_count,
            "rejected_proposal_count": self.rejected_proposal_count,
            "unit_error_count": self.unit_error_count,
        }


@dataclass(slots=True)
class CalibrationResult:
    status: str
    source_path: str
    model: str = CALIBRATION_MODEL_ID
    model_revision: str = CALIBRATION_MODEL_REVISION
    policy_version: str = CALIBRATION_POLICY_VERSION
    corrected_units: list[dict[str, Any]] = field(default_factory=list)
    rejected_proposals: list[dict[str, Any]] = field(default_factory=list)
    unit_errors: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    metrics: CalibrationMetrics = field(default_factory=CalibrationMetrics)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "source_path": self.source_path,
            "model": self.model,
            "model_revision": self.model_revision,
            "policy_version": self.policy_version,
            "corrected_units": self.corrected_units,
            "rejected_proposals": self.rejected_proposals,
            "unit_errors": self.unit_errors,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


class _ResponseStructureError(ValueError):
    pass


def _period_ends_sentence(text: str, index: int) -> bool:
    if index > 0 and index + 1 < len(text):
        if text[index - 1].isdigit() and text[index + 1].isdigit():
            return False

    token_start = index
    while token_start > 0 and not text[token_start - 1].isspace():
        token_start -= 1
    token = text[token_start : index + 1].lower().strip("\"'“‘([{")
    if token in _COMMON_ABBREVIATIONS:
        return False
    if re.fullmatch(r"(?:[a-z]\.){1,5}", token):
        return False
    return True


def split_correction_units(text: str) -> List[Tuple[int, int]]:
    """Return exact half-open sentence-like ranges within *text*."""

    ranges: List[Tuple[int, int]] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        is_boundary = char in "?!" or (
            char == "." and _period_ends_sentence(text, index)
        )
        if not is_boundary:
            index += 1
            continue

        end = index + 1
        while end < len(text) and text[end] in _CLOSING_QUOTES:
            end += 1
        unit_start = start
        while unit_start < end and text[unit_start].isspace():
            unit_start += 1
        if unit_start < end:
            ranges.append((unit_start, end))
        start = end
        index = end

    unit_start = start
    while unit_start < len(text) and text[unit_start].isspace():
        unit_start += 1
    unit_end = len(text)
    while unit_end > unit_start and text[unit_end - 1].isspace():
        unit_end -= 1
    if unit_start < unit_end:
        ranges.append((unit_start, unit_end))
    return ranges


def _parse_response(raw: str) -> list[CorrectionProposal]:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise _ResponseStructureError("response must be valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"proposals"}:
        raise _ResponseStructureError("response must contain only a proposals array")
    raw_proposals = payload["proposals"]
    if not isinstance(raw_proposals, list):
        raise _ResponseStructureError("proposals must be an array")

    proposals: list[CorrectionProposal] = []
    expected_fields = {"start", "end", "source", "replacement", "score"}
    for raw_proposal in raw_proposals:
        if not isinstance(raw_proposal, dict) or set(raw_proposal) != expected_fields:
            raise _ResponseStructureError(
                "each proposal requires start, end, source, replacement, and score"
            )
        start = raw_proposal["start"]
        end = raw_proposal["end"]
        source = raw_proposal["source"]
        replacement = raw_proposal["replacement"]
        score = raw_proposal["score"]
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not isinstance(source, str)
            or not isinstance(replacement, str)
            or isinstance(score, bool)
            or not isinstance(score, int)
            or not 1 <= score <= 5
        ):
            raise _ResponseStructureError("proposal fields have invalid types or score")
        proposals.append(
            CorrectionProposal(
                start=start,
                end=end,
                source=source,
                replacement=replacement,
                score=score,
            )
        )
    return proposals


def _has_terminal_boundary(text: str) -> bool:
    stripped = text.rstrip()
    while stripped and stripped[-1] in _CLOSING_QUOTES:
        stripped = stripped[:-1].rstrip()
    return bool(stripped and stripped[-1] in ".?!")


def _structure_is_preserved(original: str, proposal: CorrectionProposal) -> bool:
    candidate = (
        original[: proposal.start]
        + proposal.replacement
        + original[proposal.end :]
    )
    return (
        len(split_correction_units(candidate)) == 1
        and _has_terminal_boundary(candidate) == _has_terminal_boundary(original)
    )


def _has_non_english_lexical_content(text: str) -> bool:
    # Match the adapter's ASCII English spans, including when a model proposes
    # a wider phrase containing another script or a combining character.
    return any(
        not char.isascii() and unicodedata.category(char)[0] in "LMN"
        for char in text
    )


def _punctuation_is_preserved(source: str, replacement: str) -> bool:
    # Unchanged surrounding punctuation is allowed, e.g. Jhon's -> John's.
    # Require the actual edit to stay within a punctuation-free span. Comparing
    # punctuation counts alone would permit moving a comma to another word.
    start = 0
    while (
        start < min(len(source), len(replacement))
        and source[start] == replacement[start]
    ):
        start += 1
    source_end, replacement_end = len(source), len(replacement)
    while (
        source_end > start
        and replacement_end > start
        and source[source_end - 1] == replacement[replacement_end - 1]
    ):
        source_end -= 1
        replacement_end -= 1
    changed = source[start:source_end] + replacement[start:replacement_end]
    return not any(unicodedata.category(char)[0] in "PS" for char in changed)


def _base_rejection_code(
    target: str, proposal: CorrectionProposal
) -> str | None:
    if not proposal.source:
        return "empty_source"
    if not proposal.replacement:
        return "empty_replacement"
    if not (0 <= proposal.start < proposal.end <= len(target)):
        return "invalid_range"
    if target[proposal.start : proposal.end] != proposal.source:
        return "source_mismatch"
    if proposal.source == proposal.replacement:
        return "no_change"
    if not _ENGLISH_RE.search(proposal.source):
        return "no_english_source"
    if (
        _has_non_english_lexical_content(proposal.source)
        or _has_non_english_lexical_content(proposal.replacement)
    ):
        return "non_english_span"
    if "\n" in proposal.replacement or "\r" in proposal.replacement:
        return "newline_replacement"
    if not _structure_is_preserved(target, proposal):
        return "structure_changed"
    if not _punctuation_is_preserved(proposal.source, proposal.replacement):
        return "punctuation_changed"
    return None


def _overlap(left: CorrectionProposal, right: CorrectionProposal) -> bool:
    return left.start < right.end and right.start < left.end


def _validate_proposals(
    target: str,
    proposals: Sequence[CorrectionProposal],
) -> tuple[list[CorrectionProposal], list[tuple[CorrectionProposal, str]], int]:
    low_confidence_count = sum(proposal.score <= 3 for proposal in proposals)
    candidates = [proposal for proposal in proposals if proposal.score >= 4]
    unique: list[CorrectionProposal] = []
    seen: set[CorrectionProposal] = set()
    for proposal in candidates:
        if proposal not in seen:
            seen.add(proposal)
            unique.append(proposal)

    rejected: list[tuple[CorrectionProposal, str]] = []
    valid: list[CorrectionProposal] = []
    for proposal in unique:
        code = _base_rejection_code(target, proposal)
        if code is None:
            valid.append(proposal)
        else:
            rejected.append((proposal, code))

    overlapping: set[CorrectionProposal] = set()
    for index, proposal in enumerate(valid):
        for other in valid[index + 1 :]:
            if _overlap(proposal, other):
                overlapping.add(proposal)
                overlapping.add(other)
    if overlapping:
        valid = [proposal for proposal in valid if proposal not in overlapping]
        rejected.extend(
            (proposal, "overlapping_ranges")
            for proposal in unique
            if proposal in overlapping
        )
    return valid, rejected, low_confidence_count


def _apply_proposals(
    target: str, proposals: Sequence[CorrectionProposal]
) -> str:
    corrected = target
    for proposal in sorted(proposals, key=lambda item: item.start, reverse=True):
        corrected = (
            corrected[: proposal.start]
            + proposal.replacement
            + corrected[proposal.end :]
        )
    return corrected


def calibrate_document(
    document: TranscriptionDocument,
    *,
    corrector: TextCorrector,
) -> tuple[TranscriptionDocument, CalibrationResult]:
    """Calibrate eligible correction units in chronological order."""

    result = CalibrationResult(status="success", source_path=document.source_path)
    rolling_context: Deque[str] = deque(maxlen=3)
    segment_edits: dict[int, list[tuple[int, int, str]]] = {}

    for segment_index, segment in enumerate(document.segments):
        recognition_text = segment.text
        for unit_index, (start, end) in enumerate(
            split_correction_units(recognition_text), start=1
        ):
            target = recognition_text[start:end]
            unit_id = f"{segment.id}:unit-{unit_index}"
            if not _ENGLISH_RE.search(target):
                rolling_context.append(target)
                continue

            result.metrics.eligible_unit_count += 1
            proposals: list[CorrectionProposal] | None = None
            retry_error: str | None = None
            for attempt in range(1, 5):
                result.metrics.model_request_count += 1
                if attempt > 1:
                    result.metrics.retry_count += 1
                try:
                    raw = corrector.generate(
                        list(rolling_context),
                        target,
                        retry_error=retry_error,
                    )
                except CalibrationModelError as exc:
                    result.status = "failed"
                    result.error = str(exc)
                    return document, result
                except CalibrationGenerationError:
                    # A backend failure is not a response-schema error. Retry
                    # the same target without stale schema feedback or raw
                    # backend exception text in the model prompt.
                    retry_error = None
                    if attempt == 4:
                        result.status = "partial"
                        result.unit_errors.append(
                            {
                                "unit_id": unit_id,
                                "attempts": attempt,
                                "code": "generation_failed",
                            }
                        )
                        result.metrics.unit_error_count += 1
                    continue
                try:
                    proposals = _parse_response(raw)
                    break
                except _ResponseStructureError as exc:
                    retry_error = str(exc)
                    if attempt == 4:
                        result.status = "partial"
                        result.unit_errors.append(
                            {
                                "unit_id": unit_id,
                                "attempts": 4,
                                "code": "invalid_response",
                            }
                        )
                        result.metrics.unit_error_count += 1
            if proposals is None:
                rolling_context.append(target)
                continue

            accepted, rejected, low_confidence_count = _validate_proposals(
                target, proposals
            )
            result.metrics.low_confidence_discard_count += low_confidence_count
            result.metrics.applied_proposal_count += len(accepted)
            result.metrics.rejected_proposal_count += len(rejected)
            corrected = _apply_proposals(target, accepted)
            for proposal, code in rejected:
                result.rejected_proposals.append(
                    {
                        "unit_id": unit_id,
                        "proposal": proposal.to_dict(),
                        "code": code,
                    }
                )
            if corrected != target:
                result.metrics.corrected_unit_count += 1
                segment_edits.setdefault(segment_index, []).append(
                    (start, end, corrected)
                )
                result.corrected_units.append(
                    {
                        "unit_id": unit_id,
                        "segment_id": segment.id,
                        "original_text": target,
                        "corrected_text": corrected,
                        "applied": [
                            proposal.to_dict()
                            for proposal in sorted(
                                accepted, key=lambda item: item.start
                            )
                        ],
                    }
                )
            rolling_context.append(corrected)

    for segment_index, edits in segment_edits.items():
        segment = document.segments[segment_index]
        original_text = segment.text
        calibrated_text = original_text
        for start, end, replacement in sorted(
            edits, key=lambda item: item[0], reverse=True
        ):
            calibrated_text = (
                calibrated_text[:start] + replacement + calibrated_text[end:]
            )
        segment.original_text = original_text
        segment.text = calibrated_text
    return document, result


def render_calibration_json(result: CalibrationResult) -> str:
    """Render the compact calibration audit artifact."""

    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
