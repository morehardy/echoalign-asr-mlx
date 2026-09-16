"""Score saved sentence-level ASR JSON against frozen references, without models."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path


NORMALIZATION_VERSION = "english-lexical-v1"


def words(text: str) -> list[str]:
    """Ignore case/punctuation; retain internal apostrophes, repeats and word forms."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "ʼ": "'"}))
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text, flags=re.UNICODE)


def word_errors(reference: list[str], hypothesis: list[str]) -> dict:
    # Minimum word edit distance; deterministic ties prefer substitution, deletion,
    # then insertion. Counts, not sentence averages, are used for corpus WER.
    previous = [(j, 0, 0, j) for j in range(len(hypothesis) + 1)]
    for i, expected in enumerate(reference, 1):
        current = [(i, 0, i, 0)]
        for j, actual in enumerate(hypothesis, 1):
            if expected == actual:
                current.append(previous[j - 1])
                continue
            d, s, deletion, insertion = previous[j - 1]
            substitute = (d + 1, s + 1, deletion, insertion)
            d, s, deletion, insertion = previous[j]
            delete = (d + 1, s, deletion + 1, insertion)
            d, s, deletion, insertion = current[j - 1]
            insert = (d + 1, s, deletion, insertion + 1)
            current.append(min([substitute, delete, insert], key=lambda item: item[0]))
        previous = current
    distance, substitutions, deletions, insertions = previous[-1]
    return {"errors": distance, "substitutions": substitutions,
            "deletions": deletions, "insertions": insertions,
            "reference_words": len(reference),
            "wer": distance / len(reference) if reference else None}


def read_document(path: Path) -> dict:
    document = json.loads(path.read_text())
    if document.get("granularity", "sentence") != "sentence":
        raise ValueError(f"Use sentence-granularity JSON: {path}")
    if not isinstance(document.get("segments"), list):
        raise ValueError(f"Missing canonical segments: {path}")
    if any(not isinstance(segment.get("text"), str) for segment in document["segments"]):
        raise ValueError(f"Invalid segment text: {path}")
    return document


def document_text(document: dict) -> str:
    return " ".join(segment["text"] for segment in document["segments"])


def needs_normalization_review(text: str) -> bool:
    return bool(re.search(r"\d|\b[A-Z]{2,}\b|\b(?:[A-Za-z]\.){2,}", text))


def check_pair(baseline: dict, candidate: dict) -> None:
    if baseline.get("source_path") != candidate.get("source_path"):
        raise ValueError("Candidate must be derived from the same saved ASR document")
    if len(baseline["segments"]) != len(candidate["segments"]):
        raise ValueError("Calibration changed the number of subtitle segments")
    for before, after in zip(baseline["segments"], candidate["segments"]):
        for key in ["id", "start_time", "end_time", "tokens"]:
            if before.get(key) != after.get(key):
                raise ValueError(f"Calibration changed segment {key}")
        if before["text"] != after["text"] and after.get("original_text") != before["text"]:
            raise ValueError("Changed segment does not retain the saved ASR original_text")
        if "original_text" in after and after["original_text"] != before["text"]:
            raise ValueError("Candidate original_text differs from the baseline")


def total_score(cases: list[dict], key: str) -> dict:
    totals = {name: sum(case[key][name] for case in cases)
              for name in ["errors", "substitutions", "deletions", "insertions", "reference_words"]}
    totals["wer"] = totals["errors"] / totals["reference_words"]
    return totals


def score(manifest_path: Path, baseline_dir: Path, candidate_dir: Path | None, partition: str) -> dict:
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest["normalization_version"] != NORMALIZATION_VERSION:
        raise ValueError("Unsupported normalization policy; do not silently change scoring")
    samples = [sample for sample in manifest["samples"] if sample["partition"] == partition]
    if not samples:
        raise ValueError("No reference samples in the selected partition")
    if len({sample["id"] for sample in samples}) != len(samples):
        raise ValueError("Duplicate sample IDs in manifest")
    cases = []
    for sample in samples:
        reference_path = manifest_path.parent / sample["reference_path"]
        raw_reference = reference_path.read_bytes()
        if hashlib.sha256(raw_reference).hexdigest() != sample["reference_sha256"]:
            raise ValueError(f"Reference checksum mismatch: {sample['id']}")
        reference_text = raw_reference.decode().rstrip("\n")
        if reference_text != sample["reference_text"]:
            raise ValueError("Reference file differs from frozen manifest")
        reference = words(reference_text)
        if not reference:
            raise ValueError("Empty reference is not allowed in this speech pilot")
        baseline_path = baseline_dir / f"{sample['id']}.json"
        baseline = read_document(baseline_path)
        if Path(baseline["source_path"]).stem != sample["id"]:
            raise ValueError("ASR document source does not match the reference recording")
        if any("original_text" in segment for segment in baseline["segments"]):
            raise ValueError("Baseline already contains calibrated text")
        baseline_text = document_text(baseline)
        case = {"id": sample["id"], "reference": reference_text,
                "baseline_text": baseline_text,
                "normalization_review_required": needs_normalization_review(baseline_text),
                "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                "baseline": word_errors(reference, words(baseline_text))}
        if candidate_dir is not None:
            candidate_path = candidate_dir / f"{sample['id']}.json"
            candidate = read_document(candidate_path)
            check_pair(baseline, candidate)
            candidate_text = document_text(candidate)
            candidate_score = word_errors(reference, words(candidate_text))
            error_reduction = case["baseline"]["errors"] - candidate_score["errors"]
            case.update({"candidate_text": candidate_text,
                         "normalization_review_required": needs_normalization_review(baseline_text) or needs_normalization_review(candidate_text),
                         "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                         "candidate": candidate_score, "error_reduction": error_reduction,
                         "lexically_changed": words(baseline_text) != words(candidate_text),
                         "outcome": "improved" if error_reduction > 0 else "regressed" if error_reduction < 0 else "tied"})
        cases.append(case)
    report = {
        "schema_version": 1, "benchmark_version": manifest["benchmark_version"],
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "normalization_version": NORMALIZATION_VERSION, "partition": partition,
        "sample_count": len(cases), "baseline": total_score(cases, "baseline"),
        "normalization_review_clips": sum(case["normalization_review_required"] for case in cases),
        "interpretation": "Descriptive lexical pilot only; no semantic-correction precision or release pass/fail is inferred",
        "cases": cases,
    }
    if candidate_dir is not None:
        candidate_total = total_score(cases, "candidate")
        clean = [case for case in cases if case["baseline"]["errors"] == 0]
        damaged = sum(case["candidate"]["errors"] > 0 for case in clean)
        reduction = report["baseline"]["errors"] - candidate_total["errors"]
        report.update({
            "candidate": candidate_total, "net_word_error_reduction": reduction,
            "wer_reduction_percentage_points": 100 * reduction / report["baseline"]["reference_words"],
            "improved_clips": sum(case["outcome"] == "improved" for case in cases),
            "regressed_clips": sum(case["outcome"] == "regressed" for case in cases),
            "tied_clips": sum(case["outcome"] == "tied" for case in cases),
            "changed_but_tied_clips": sum(case["outcome"] == "tied" and case["lexically_changed"] for case in cases),
            "baseline_clean_clips": len(clean), "clean_clips_damaged": damaged,
            "clean_clip_damage_rate": damaged / len(clean) if clean else None,
        })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("baseline_dir", type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--partition", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(args.manifest, args.baseline_dir, args.candidate_dir, args.partition)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
