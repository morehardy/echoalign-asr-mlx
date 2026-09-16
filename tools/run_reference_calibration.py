"""Run the existing calibrator on saved ASR JSON, without loading references."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from asr.calibration import (
    CALIBRATION_MODEL_ID,
    CALIBRATION_MODEL_REVISION,
    CALIBRATION_POLICY_VERSION,
    calibrate_document,
    render_calibration_json,
)
from asr.calibration_mlx import MlxVlmCorrector
from asr.exporters import render_json, render_srt, render_vtt
from asr.models import Segment, Token, TranscriptionDocument


def load_document(path: Path) -> TranscriptionDocument:
    payload = json.loads(path.read_text())
    if payload.get("granularity", "sentence") != "sentence":
        raise ValueError(f"Expected sentence-granularity ASR JSON: {path}")
    if any("original_text" in segment for segment in payload["segments"]):
        raise ValueError(f"Input already contains calibrated text: {path}")
    segments = [
        Segment(
            id=segment["id"], text=segment["text"],
            start_time=segment["start_time"], end_time=segment["end_time"],
            language=segment.get("language"), speaker=segment.get("speaker"),
            tokens=[Token(**token) for token in segment.get("tokens", [])],
            timing_source=segment.get("timing_source"),
        )
        for segment in payload["segments"]
    ]
    return TranscriptionDocument(
        source_path=payload["source_path"], provider_name=payload["provider_name"],
        segments=segments, source_media=payload.get("source_media"),
        detected_language=payload.get("detected_language"),
        status=payload.get("status", "ok"), warnings=payload.get("warnings", []),
    )


def run(baseline_dir: Path, output_dir: Path) -> int:
    if output_dir.resolve() == baseline_dir.resolve():
        raise ValueError("Calibrated output must not overwrite the ASR baseline")
    if output_dir.exists():
        raise ValueError("Choose a new output directory to preserve existing run evidence")
    inputs = sorted(path for path in baseline_dir.glob("*.json")
                    if not path.name.endswith((".metrics.json", ".calibration.json")))
    if not inputs:
        raise ValueError("No saved ASR JSON files found")
    output_dir.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    started = datetime.now(timezone.utc).isoformat()
    runtime = MlxVlmCorrector()
    cases = []
    counts = {}
    had_error = False
    for index, path in enumerate(inputs, 1):
        document = load_document(path)
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        start = time.perf_counter()
        calibrated, result = calibrate_document(document, corrector=runtime)
        seconds = time.perf_counter() - start
        for suffix, content in [
            (".json", render_json(calibrated)),
            (".srt", render_srt(calibrated)),
            (".vtt", render_vtt(calibrated)),
            (".calibration.json", render_calibration_json(result)),
        ]:
            (output_dir / f"{path.stem}{suffix}").write_text(content)
        if hashlib.sha256(path.read_bytes()).hexdigest() != original_hash:
            raise ValueError("ASR baseline changed during calibration")
        metrics = result.metrics.to_dict()
        for key, value in metrics.items():
            counts[key] = counts.get(key, 0) + value
        cases.append({"id": path.stem, "baseline_sha256": original_hash,
                      "status": result.status, "duration_seconds": seconds,
                      "metrics": metrics})
        had_error |= result.status != "success"
        print(f"[{index}/{len(inputs)}] {path.stem}: {result.status}, "
              f"{metrics['applied_proposal_count']} applied, "
              f"{metrics['rejected_proposal_count']} rejected, {seconds:.2f}s", flush=True)
    metadata = {
        "schema_version": 1, "started_at_utc": started,
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "partial_or_failed" if had_error else "success",
        "baseline_dir": str(baseline_dir), "reference_provided_to_model": False,
        "asr_rerun": False, "model": CALIBRATION_MODEL_ID,
        "model_revision": CALIBRATION_MODEL_REVISION,
        "policy_version": CALIBRATION_POLICY_VERSION,
        "project_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ["src/asr/calibration.py", "src/asr/calibration_mlx.py",
                                       "tools/run_reference_calibration.py"]},
        "python_version": platform.python_version(), "platform": platform.platform(),
        "packages": {name: version(name) for name in ["mlx", "mlx-vlm", "transformers"]},
        "metrics": counts, "cases": cases,
    }
    (output_dir / "run.metrics.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": metadata["status"], "metrics": counts}, indent=2))
    return 1 if had_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    return run(args.baseline_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
