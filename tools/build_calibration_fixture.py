"""Build the versioned 100-case calibration quality fixture."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from asr.calibration import split_correction_units

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/e2e/outputs/Metal Gear Solid Delta.json"
OUTPUT = ROOT / "tests/evaluation/calibration/policy-1/labelled.json"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _units(payload: dict[str, Any]) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    for segment in payload["segments"]:
        text = segment["text"]
        for index, (start, end) in enumerate(split_correction_units(text), start=1):
            unit_text = text[start:end]
            if re.search(r"[A-Za-z]", unit_text):
                units.append(
                    {
                        "id": f"{segment['id']}:unit-{index}",
                        "text": unit_text,
                    }
                )
    return units


def _case(
    *,
    unit: dict[str, str],
    context: list[str],
    category: str,
    target: str,
    source: str,
    replacement: str,
    start: int,
) -> dict[str, Any]:
    return {
        "id": f"{unit['id']}:{category}",
        "source_unit_id": unit["id"],
        "label": "correctable",
        "category": category,
        "context": context,
        "target": target,
        "acceptable": [
            {
                "start": start,
                "end": start + len(source),
                "source": source,
                "replacement": replacement,
            }
        ],
    }


def _transform_word(
    text: str,
    matcher: Callable[[str], bool],
    transform: Callable[[str], str],
) -> tuple[str, str, str, int] | None:
    for match in WORD_RE.finditer(text):
        original = match.group()
        if not matcher(original):
            continue
        corrupted = transform(original)
        if corrupted == original:
            continue
        target = text[: match.start()] + corrupted + text[match.end() :]
        return target, corrupted, original, match.start()
    return None


def _previous_context(
    units: list[dict[str, str]],
    index: int,
) -> list[str]:
    return [item["text"] for item in units[max(0, index - 3) : index]]


def _build_error_cases(units: list[dict[str, str]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    used: set[str] = set()

    def add_cases(
        category: str,
        count: int,
        transformer: Callable[[str], tuple[str, str, str, int] | None],
    ) -> None:
        for index, unit in enumerate(units):
            if len([case for case in cases if case["category"] == category]) >= count:
                return
            if (
                unit["id"] in used
                or not 25 <= len(unit["text"]) <= 140
                or unit["text"].rstrip()[-1] not in ".?!\"'”’"
            ):
                continue
            transformed = transformer(unit["text"])
            if transformed is None:
                continue
            target, source, replacement, start = transformed
            context = _previous_context(units, index)
            cases.append(
                _case(
                    unit=unit,
                    context=context,
                    category=category,
                    target=target,
                    source=source,
                    replacement=replacement,
                    start=start,
                )
            )
            used.add(unit["id"])
        raise RuntimeError(f"not enough {category} candidates")

    add_cases(
        "spelling",
        25,
        lambda text: _transform_word(
            text,
            lambda word: len(word) >= 8 and "'" not in word,
            lambda word: word[: max(2, len(word) // 2)]
            + word[max(2, len(word) // 2) + 1 :],
        ),
    )

    homophones = {
        "to": "two",
        "two": "too",
        "one": "won",
        "no": "know",
        "know": "no",
        "their": "there",
        "there": "their",
        "your": "you're",
        "you're": "your",
        "its": "it's",
        "it's": "its",
    }
    add_cases(
        "homophone",
        15,
        lambda text: _transform_word(
            text,
            lambda word: word.lower() in homophones,
            lambda word: homophones[word.lower()].capitalize()
            if word[0].isupper()
            else homophones[word.lower()],
        ),
    )

    wrong_words = {
        "mission": "missing",
        "world": "word",
        "ground": "round",
        "power": "flower",
        "launch": "lunch",
        "airspace": "air place",
        "nuclear": "new clear",
        "military": "mystery",
        "hospital": "hostile",
        "government": "governor",
        "satellite": "Saturday",
        "aircraft": "air draft",
        "weapon": "weather",
        "soldier": "shoulder",
    }
    add_cases(
        "wrong_word_or_phrase",
        5,
        lambda text: _transform_word(
            text,
            lambda word: word.lower() in wrong_words,
            lambda word: wrong_words[word.lower()].capitalize()
            if word[0].isupper()
            else wrong_words[word.lower()],
        ),
    )

    names = {
        "Snake": "Snape",
        "Sokolov": "Sokoloff",
        "Volgin": "Vulcan",
        "Khrushchev": "Khruschev",
        "Shagohod": "Shagohad",
        "Voyevoda": "Voevoda",
        "KGB": "KBG",
        "CIA": "CIE",
        "Adam": "Atom",
        "Eva": "Ava",
        "Fox": "Fawkes",
    }
    proper_count = 0
    for index, unit in enumerate(units):
        if proper_count == 5:
            break
        if not 15 <= len(unit["text"]) <= 140:
            continue
        context = _previous_context(units, index)
        context_text = " ".join(context)
        supported_names = {
            name
            for name in names
            if re.search(rf"\b{re.escape(name)}\b", unit["text"])
            and re.search(rf"\b{re.escape(name)}\b", context_text)
        }
        if not supported_names:
            continue
        transformed = _transform_word(
            unit["text"],
            lambda word: word in supported_names,
            lambda word: names[word],
        )
        if transformed is None:
            continue
        target, source, replacement, start = transformed
        cases.append(
            _case(
                unit=unit,
                context=context,
                category="proper_name",
                target=target,
                source=source,
                replacement=replacement,
                start=start,
            )
        )
        proper_count += 1
    if proper_count != 5:
        raise RuntimeError(f"not enough proper_name candidates: {proper_count}")
    return cases


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    units = _units(payload)
    correctable = _build_error_cases(units)
    used = {case["source_unit_id"] for case in correctable}
    clean: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        text = unit["text"]
        if (
            unit["id"] in used
            or not 25 <= len(text) <= 140
            or not text[0].isupper()
            or text[-1] not in ".?!\"'”’"
            or re.search(r"\b(\w+)\s+\1\b", text, flags=re.IGNORECASE)
        ):
            continue
        clean.append(
            {
                "id": f"{unit['id']}:clean",
                "source_unit_id": unit["id"],
                "label": "clean",
                "category": "clean",
                "context": _previous_context(units, index),
                "target": text,
                "acceptable": [],
            }
        )
        if len(clean) == 50:
            break
    if len(correctable) != 50 or len(clean) != 50:
        raise RuntimeError(
            f"expected 50 correctable and 50 clean, got "
            f"{len(correctable)} and {len(clean)}"
        )
    fixture = {
        "schema_version": 1,
        "source": str(SOURCE.relative_to(ROOT)),
        "description": (
            "Real ASR correction units; correctable cases contain deterministic "
            "ASR-like corruptions with verified source text as the answer."
        ),
        "cases": correctable + clean,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(fixture['cases'])} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
