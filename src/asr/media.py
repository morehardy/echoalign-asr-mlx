"""Media normalization helpers."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Protocol


class MediaPreparer(Protocol):
    def prepare(self, source_path: Path) -> Path:
        """Prepare a source media file for transcription."""


class FfmpegMediaPreparer:
    """Normalize media into mono 16 kHz WAV for ASR backends."""

    def __init__(self, sample_rate: int = 16_000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._prepared_directories: dict[Path, tempfile.TemporaryDirectory] = {}

    def prepare(self, source_path: Path) -> Path:
        source = source_path.expanduser().resolve()
        directory = tempfile.TemporaryDirectory(prefix="asr-media-")
        target = Path(directory.name) / f"{source.stem}.wav"
        self._prepared_directories[target] = directory
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            str(self.channels),
            "-ar",
            str(self.sample_rate),
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
        try:
            try:
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError("ffmpeg is required but was not found on PATH.") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(exc.stderr.strip() or "ffmpeg failed to normalize media.") from exc
        except BaseException:
            self.cleanup(target)
            raise
        return target

    def cleanup(self, prepared_path: Path) -> None:
        """Release only a temporary directory owned by this preparer."""
        directory = self._prepared_directories.pop(prepared_path, None)
        if directory is not None:
            directory.cleanup()
