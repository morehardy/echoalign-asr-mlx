"""Translate backend language metadata into canonical codes and aligner names."""

from __future__ import annotations


_ALIGNER_NAMES = {
    "ar": "Arabic",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fi": "Finnish",
    "fil": "Filipino",
    "fr": "French",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "mk": "Macedonian",
    "ms": "Malay",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "yue": "Chinese",
    "zh": "Chinese",
}
_LANGUAGE_CODES = {name.lower(): code for code, name in _ALIGNER_NAMES.items()}
_LANGUAGE_CODES.update({"cantonese": "yue", "mandarin": "zh"})


def normalize_language(value: object) -> str | None:
    """Use the first detected language, including MLX's per-chunk list format."""
    if isinstance(value, (list, tuple)):
        return next((code for item in value if (code := normalize_language(item))), None)
    if not isinstance(value, str):
        return None
    language = value.strip().lower().replace("_", "-")
    if language in {"", "none", "unknown", "auto"}:
        return None
    if language in _LANGUAGE_CODES:
        return _LANGUAGE_CODES[language]
    code = language.split("-", 1)[0]
    return code if code in _ALIGNER_NAMES else language


def aligner_language(language: str | None) -> str | None:
    code = normalize_language(language)
    return _ALIGNER_NAMES.get(code, code) if code else None
