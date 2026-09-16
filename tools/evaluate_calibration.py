"""Run labelled or full-transcript evaluation with the pinned local model."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from asr.calibration import (
    CALIBRATION_MODEL_ID,
    CALIBRATION_MODEL_REVISION,
    CALIBRATION_POLICY_VERSION,
    calibrate_document,
    render_calibration_json,
)
from asr.calibration_mlx import MlxVlmCorrector
from asr.models import Segment, Token, TranscriptionDocument


class _TargetOnlyCorrector:
    def __init__(self, delegate: MlxVlmCorrector, skip: int) -> None:
        self.delegate = delegate
        self.skip = skip

    def generate(
        self,
        context: list[str],
        target: str,
        retry_error: str | None = None,
    ) -> str:
        if self.skip:
            self.skip -= 1
            return '{"proposals":[]}'
        return self.delegate.generate(context, target, retry_error)


class _ProgressCorrector:
    def __init__(self, delegate: MlxVlmCorrector, every: int = 25) -> None:
        self.delegate = delegate
        self.every = every
        self.count = 0
        self.retry_error_distribution: Counter[str] = Counter()

    def generate(
        self,
        context: list[str],
        target: str,
        retry_error: str | None = None,
    ) -> str:
        self.count += 1
        if retry_error is not None:
            self.retry_error_distribution["response_structure_error"] += 1
        if self.count == 1 or self.count % self.every == 0:
            print(f"model request {self.count}", flush=True)
        return self.delegate.generate(context, target, retry_error)


def _document_for_case(case: dict[str, Any]) -> TranscriptionDocument:
    segments = [
        Segment(
            id=f"context-{index}",
            text=text,
            start_time=float(index - 1),
            end_time=float(index),
            language="en",
        )
        for index, text in enumerate(case["context"], start=1)
    ]
    start = float(len(segments))
    segments.append(
        Segment(
            id="target",
            text=case["target"],
            start_time=start,
            end_time=start + 1.0,
            language="en",
        )
    )
    return TranscriptionDocument(
        source_path=case["id"],
        provider_name="labelled-fixture",
        segments=segments,
    )


def _proposal_key(proposal: dict[str, Any]) -> tuple[Any, ...]:
    return (
        proposal["start"],
        proposal["end"],
        proposal["source"],
        proposal["replacement"],
    )


def evaluate_labelled(fixture_path: Path, output_dir: Path) -> int:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    model = MlxVlmCorrector()
    case_results: list[dict[str, Any]] = []
    correct_applied = 0
    total_applied = 0
    recalled_cases = 0
    clean_modified = 0
    retry_exhausted = 0
    structure_changes = 0

    for index, case in enumerate(fixture["cases"], start=1):
        document = _document_for_case(case)
        original_count = len(document.segments)
        target_segment = document.segments[-1]
        original_times = (target_segment.start_time, target_segment.end_time)
        corrector = _TargetOnlyCorrector(model, skip=len(case["context"]))
        calibrated, result = calibrate_document(document, corrector=corrector)
        target_result = next(
            (
                item
                for item in result.corrected_units
                if item["segment_id"] == "target"
            ),
            None,
        )
        applied = [] if target_result is None else target_result["applied"]
        acceptable = {_proposal_key(item) for item in case["acceptable"]}
        matched = sum(_proposal_key(item) in acceptable for item in applied)
        total_applied += len(applied)
        correct_applied += matched
        if case["label"] == "correctable" and matched:
            recalled_cases += 1
        if case["label"] == "clean" and applied:
            clean_modified += 1
        retry_exhausted += sum(
            item["code"] == "invalid_response" for item in result.unit_errors
        )
        final_target = calibrated.segments[-1]
        if (
            len(calibrated.segments) != original_count
            or (final_target.start_time, final_target.end_time) != original_times
        ):
            structure_changes += 1
        case_results.append(
            {
                "id": case["id"],
                "label": case["label"],
                "category": case["category"],
                "status": result.status,
                "original_text": case["target"],
                "calibrated_text": final_target.text,
                "applied": applied,
                "matched_acceptable_count": matched,
                "rejected_proposals": result.rejected_proposals,
                "unit_errors": result.unit_errors,
            }
        )
        print(f"[{index}/{len(fixture['cases'])}] {case['id']}", flush=True)

    correctable_count = sum(
        case["label"] == "correctable" for case in fixture["cases"]
    )
    clean_count = sum(case["label"] == "clean" for case in fixture["cases"])
    precision = correct_applied / total_applied if total_applied else 0.0
    recall = recalled_cases / correctable_count
    false_modification_rate = clean_modified / clean_count
    thresholds = {
        "applied_proposal_precision": precision >= 0.95,
        "correctable_error_recall": recall >= 0.70,
        "clean_false_modification_rate": false_modification_rate <= 0.02,
        "structure_or_timestamp_changes": structure_changes == 0,
        "retry_exhausted_units": retry_exhausted == 0,
    }
    metrics = {
        "schema_version": 1,
        "model": CALIBRATION_MODEL_ID,
        "model_revision": CALIBRATION_MODEL_REVISION,
        "policy_version": CALIBRATION_POLICY_VERSION,
        "fixture": str(fixture_path),
        "case_count": len(fixture["cases"]),
        "correctable_count": correctable_count,
        "clean_count": clean_count,
        "correct_applied_proposals": correct_applied,
        "total_applied_proposals": total_applied,
        "applied_proposal_precision": precision,
        "recalled_correctable_cases": recalled_cases,
        "correctable_error_recall": recall,
        "clean_modified_cases": clean_modified,
        "clean_false_modification_rate": false_modification_rate,
        "structure_or_timestamp_changes": structure_changes,
        "retry_exhausted_units": retry_exhausted,
        "thresholds": thresholds,
        "passed": all(thresholds.values()),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "labelled.metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "labelled.results.json").write_text(
        json.dumps(
            {"metrics": metrics, "cases": case_results},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["passed"] else 1


def _document_from_json(payload: dict[str, Any]) -> TranscriptionDocument:
    segments = []
    for segment in payload["segments"]:
        tokens = [Token(**token) for token in segment.get("tokens", [])]
        segments.append(
            Segment(
                id=segment["id"],
                text=segment["text"],
                start_time=segment["start_time"],
                end_time=segment["end_time"],
                language=segment.get("language"),
                tokens=tokens,
                speaker=segment.get("speaker"),
            )
        )
    return TranscriptionDocument(
        source_path=payload["source_path"],
        provider_name=payload["provider_name"],
        source_media=payload.get("source_media"),
        detected_language=payload.get("detected_language"),
        segments=segments,
    )


def evaluate_full(transcript_path: Path, output_dir: Path) -> int:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    document = _document_from_json(payload)
    corrector = _ProgressCorrector(MlxVlmCorrector())
    _, result = calibrate_document(document, corrector=corrector)
    scores = Counter(
        str(proposal["score"])
        for unit in result.corrected_units
        for proposal in unit["applied"]
    )
    rejection_codes = Counter(
        item["code"] for item in result.rejected_proposals
    )
    error_codes = Counter(item["code"] for item in result.unit_errors)
    metrics = {
        "schema_version": 1,
        "model": CALIBRATION_MODEL_ID,
        "model_revision": CALIBRATION_MODEL_REVISION,
        "policy_version": CALIBRATION_POLICY_VERSION,
        "source": str(transcript_path),
        "segment_count": len(document.segments),
        "model_request_count": corrector.count,
        "retry_count": sum(corrector.retry_error_distribution.values()),
        "retry_distribution": dict(
            sorted(corrector.retry_error_distribution.items())
        ),
        "corrected_unit_count": len(result.corrected_units),
        "applied_proposal_count": sum(
            len(unit["applied"]) for unit in result.corrected_units
        ),
        "applied_score_distribution": dict(sorted(scores.items())),
        "rejected_proposal_count": len(result.rejected_proposals),
        "rejection_code_distribution": dict(sorted(rejection_codes.items())),
        "unit_error_count": len(result.unit_errors),
        "unit_error_code_distribution": dict(sorted(error_codes.items())),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "full.calibration.json").write_text(
        render_calibration_json(result), encoding="utf-8"
    )
    (output_dir / "full.metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if result.status == "success" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    labelled = subparsers.add_parser("labelled")
    labelled.add_argument("fixture", type=Path)
    labelled.add_argument("output_dir", type=Path)
    full = subparsers.add_parser("full")
    full.add_argument("transcript", type=Path)
    full.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.command == "labelled":
        return evaluate_labelled(args.fixture, args.output_dir)
    return evaluate_full(args.transcript, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
