"""Fetch a small, frozen FLEURS reference corpus; no ASR/LLM is involved."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "tests/evaluation/calibration/reference-v1"
DATASET = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
SEED = "echoalign-reference-v1"
PARTITIONS = ("dev", "heldout")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    # curl uses the platform TLS setup on macOS, matching the media tools already
    # required by this repository. Never disable certificate verification.
    result = subprocess.run(
        ["curl", "--location", "--fail", "--silent", "--show-error", "--retry", "3",
         "--retry-all-errors", "--retry-delay", "1", "--max-time", "60", url],
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"Public dataset download failed: {result.stderr.decode().strip()}")
    return result.stdout


def viewer_rows(split: str, offset: int, length: int = 100) -> dict:
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "en_us", "split": split,
         "offset": offset, "length": length}
    )
    return json.loads(fetch(f"https://datasets-server.huggingface.co/rows?{query}"))


def read_split(split: str, tsv_name: str) -> tuple[list[dict], dict]:
    source = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/data/en_us/{tsv_name}.tsv"
    raw = fetch(source)
    official = {row[1]: row for row in csv.reader(io.StringIO(raw.decode()), delimiter="\t")}
    first = viewer_rows(split, 0)
    if first.get("partial"):
        raise ValueError("The dataset viewer returned a partial corpus")
    pages = [first]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages.extend(pool.map(lambda offset: viewer_rows(split, offset),
                              range(100, first["num_rows_total"], 100)))
    rows = []
    for page in pages:
        for item in page["rows"]:
            row = item["row"]
            filename = Path(row["path"]).name
            expected = official[filename]
            if (str(row["id"]), row["raw_transcription"], row["transcription"], str(row["num_samples"])) != (
                expected[0], expected[2], expected[3], expected[5]
            ):
                raise ValueError(f"Viewer data differs from pinned TSV: {filename}")
            audio_url = row["audio"][0]["src"]
            if f"/--/{REVISION}/--/" not in audio_url:
                raise ValueError("Viewer revision changed; do not silently replace the reference corpus")
            rows.append({**row, "row_index": item["row_idx"], "filename": filename,
                         "download_url": audio_url})
    if len(rows) != len(official) or len({row["filename"] for row in rows}) != len(official):
        raise ValueError("Incomplete or duplicate dataset rows")
    return rows, {"url": source, "sha256": digest(raw), "recording_count": len(rows)}


def eligible(row: dict) -> bool:
    """Freeze an elementary lexical pilot, without output-dependent selection."""
    text = row["raw_transcription"]
    return (
        5 <= row["num_samples"] / 16000 <= 30
        and 10 <= len(text.split()) <= 70
        and not re.search(r"\d|\b[A-Z]{2,}\b|\b(?:[A-Za-z]\.){2,}", text)
    )


def select_rows(rows: list[dict], count: int) -> list[dict]:
    selected = []
    seen = set()
    ordered = sorted(rows, key=lambda row: digest(f"{SEED}:{row['id']}:{row['filename']}".encode()))
    for row in ordered:
        if row["id"] in seen or not eligible(row):
            continue
        selected.append(row)
        seen.add(row["id"])
        if len(selected) == count:
            return selected
    raise ValueError(f"Only {len(selected)} eligible unique sentences, requested {count}")


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def inspect_audio(path: Path, expected_samples: int) -> None:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels,duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    if (int(stream["sample_rate"]) != 16000 or stream["channels"] != 1
            or abs(float(stream["duration"]) - expected_samples / 16000) > 0.001):
        raise ValueError(f"Audio dimensions differ from official metadata: {path.name}")


def materialize(output: Path, partition: str, split: str, row: dict) -> dict:
    recording_id = Path(row["filename"]).stem
    sample_id = f"fleurs-en-{partition}-{row['id']}-{recording_id}"
    audio_relative = f"audio/{partition}/{sample_id}.wav"
    text_relative = f"references/{partition}/{sample_id}.txt"
    subtitle_relative = f"references/{partition}/{sample_id}.srt"
    audio_path = output / audio_relative
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    content = audio_path.read_bytes() if audio_path.exists() else fetch(row["download_url"])
    if not audio_path.exists():
        audio_path.write_bytes(content)
    inspect_audio(audio_path, row["num_samples"])
    duration = row["num_samples"] / 16000
    text = row["raw_transcription"]
    text_bytes = (text + "\n").encode()
    subtitle_bytes = f"1\n00:00:00,000 --> {timestamp(duration)}\n{text}\n\n".encode()
    (output / text_relative).parent.mkdir(parents=True, exist_ok=True)
    (output / text_relative).write_bytes(text_bytes)
    (output / subtitle_relative).write_bytes(subtitle_bytes)
    return {
        "id": sample_id, "partition": partition, "source_split": split,
        "sentence_id": row["id"], "recording_filename": row["filename"],
        "source_row_index": row["row_index"], "gender_label": row["gender"],
        "sample_rate": 16000, "num_samples": row["num_samples"],
        "duration_seconds": duration, "audio_path": audio_relative,
        "audio_sha256": digest(content), "reference_path": text_relative,
        "reference_sha256": digest(text_bytes), "subtitle_path": subtitle_relative,
        "subtitle_sha256": digest(subtitle_bytes),
        "reference_text": text, "publisher_normalized_text": row["transcription"],
        "reference_evidence": "publisher_human_validated",
        "local_listening_review": "pending",
        "subtitle_timing": "clip_boundary_only_not_alignment_ground_truth",
    }


def verify(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    seen_ids, seen_sentences, seen_texts = set(), set(), set()
    for sample in manifest["samples"]:
        normalized_text = " ".join(sample["reference_text"].casefold().split())
        if (sample["id"] in seen_ids or sample["sentence_id"] in seen_sentences
                or normalized_text in seen_texts):
            raise ValueError("Duplicate recording or sentence across the reference corpus")
        seen_ids.add(sample["id"])
        seen_sentences.add(sample["sentence_id"])
        seen_texts.add(normalized_text)
        for kind in ["audio", "reference", "subtitle"]:
            path = output / sample[f"{kind}_path"]
            if digest(path.read_bytes()) != sample[f"{kind}_sha256"]:
                raise ValueError(f"Changed {kind} file: {path}")
        if (output / sample["reference_path"]).read_text().rstrip("\n") != sample["reference_text"]:
            raise ValueError("Reference file differs from frozen manifest")
        inspect_audio(output / sample["audio_path"], sample["num_samples"])
    return manifest


def build(output: Path, count: int) -> None:
    if (output / "manifest.json").exists():
        raise ValueError("Manifest already exists; use verify or choose a new version directory")
    samples = []
    rows, source_metadata = read_split("validation", "dev")
    selected = select_rows(rows, 2 * count)
    for index, partition in enumerate(PARTITIONS):
        chosen = selected[index * count : (index + 1) * count]
        print(f"{partition}: selected {len(chosen)} unique sentences using the frozen sampling rule", flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            samples.extend(pool.map(lambda row: materialize(output, partition, "validation", row), chosen))
    manifest = {
        "schema_version": 1, "benchmark_version": "reference-v1",
        "dataset": DATASET, "config": "en_us", "dataset_revision": REVISION,
        "source": "https://huggingface.co/datasets/google/fleurs",
        "license": "CC-BY-4.0",
        "reference_evidence_source": "https://arxiv.org/pdf/2205.12446#page=2",
        "normalization_version": "english-lexical-v1", "selection_seed": SEED,
        "selection": "From official validation: SHA256(seed:sentence_id:filename), first eligible recording per sentence; first count for dev, next count for heldout; 5-30s; 10-70 whitespace words; exclude digits, uppercase acronyms and dotted initials",
        "samples_per_partition": count, "source_metadata": {"validation": source_metadata},
        "official_test_split": "not_used; heldout is an internal validation subset",
        "pretraining_contamination": "unknown",
        "scope": "English read-speech lexical pilot; not a release-quality gate or a test of cross-clip rolling context",
        "samples": sorted(samples, key=lambda sample: sample["id"]),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (output / ".gitignore").write_text("audio/\n")
    verify(output)
    print(f"Verified {len(samples)} recordings and references in {output}", flush=True)


def restore(output: Path) -> None:
    """Restore ignored audio without changing the frozen references or hashes."""
    manifest = json.loads((output / "manifest.json").read_text())
    for sample in manifest["samples"]:
        path = output / sample["audio_path"]
        if path.exists() and digest(path.read_bytes()) == sample["audio_sha256"]:
            continue
        page = viewer_rows(sample["source_split"], sample["source_row_index"], 1)
        row = page["rows"][0]["row"]
        url = row["audio"][0]["src"]
        if (Path(row["path"]).name != sample["recording_filename"]
                or row["raw_transcription"] != sample["reference_text"]
                or f"/--/{manifest['dataset_revision']}/--/" not in url):
            raise ValueError("Upstream viewer changed; restore from the pinned official archive instead")
        content = fetch(url)
        if digest(content) != sample["audio_sha256"]:
            raise ValueError("Downloaded audio differs from frozen checksum")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    verify(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify", "restore"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=24, help="Unique sentences per partition when building")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    if args.command == "build":
        build(args.output, args.count)
    elif args.command == "restore":
        restore(args.output)
    else:
        manifest = verify(args.output)
        print(f"Verified {len(manifest['samples'])} recordings, text files and subtitle files")


if __name__ == "__main__":
    main()
