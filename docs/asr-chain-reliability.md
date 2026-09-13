# ASR Chain Reliability

The CLI processes files synchronously through discovery, output validation,
environment checks, WAV preparation, optional VAD, bounded ASR/alignment
windows, merging, cue construction, and SRT/VTT/JSON export.

## Changes

| Problem | Resolution | Regression coverage |
| --- | --- | --- |
| MLX language lists and language names bypass Chinese tokenization | Normalize list/name/code metadata to canonical codes; translate codes to aligner language names; tokenize mixed Chinese characters and English words without losing punctuation. | Chinese list/name/code variants, English lists, mixed-language alignment. |
| Alignment exceptions erase successful recognition and the CLI exits successfully | Retain recognition text on alignment failure. Carry partial status and warnings in the document; write available outputs and return exit code 1. | Public CLI tests with failed recognition and failed alignment windows. |
| Boundary checks compare different audio intervals | Select tokens from the actual intersection of adjacent context windows on both sides before quality evaluation. | Small timing drift at a boundary still merges the shared word once. |
| A whole unaligned window becomes one six-second cue | Split text into readable cues, estimate their timing within the owned window/display bounds, and mark the cues as estimated. Token views expose explicitly marked segment fallbacks. | Long unaligned text remains complete, spans the window, and is visible in token exports. |
| Different sources overwrite each other's outputs | Validate all requested output paths, including metrics sidecars, before model work or writes. Reject conflicts with their source and destination paths. | Same-stem extensions and metrics/transcript collisions preserve existing outputs. |
| Prepared WAV files leak after processing | The media preparer owns its temporary directories; the pipeline releases prepared audio in a finally block. Failed conversion also releases its directory. | Success, provider failure, silence, interruption, and conversion failure. |

## Output Semantics

- Existing successful documents retain their JSON shape. Partial documents add
  `status` and `warnings`.
- Recognized text survives alignment exceptions. If all recognition windows
  fail, processing still raises a file-level error.
- Estimated cue timing is explicitly separate from acoustic evidence. These
  segments have `timing_source: "estimated"` and no fabricated public tokens.
- Token-granularity `items` may contain a coarse fallback with `unit: "segment"`
  and `timing_source` when no token alignment exists for that segment.
- Short unaligned phrases keep short estimated display durations. Longer text
  is distributed across the available window and split into cues of at most
  six seconds, subject to the text's indivisible words.
- Batch output conflicts stop the whole command before writes. Ordinary
  per-file failures or partial results allow remaining files to continue.
- Prepared audio paths in JSON identify temporary preprocessing artifacts;
  those artifacts are removed before export. Original media is never cleaned up.

## Verification

```bash
PYTHONPATH=src uv run --python 3.14 python -m unittest tests.test_chain_regressions
PYTHONPATH=src uv run --frozen --python 3.14 python -m unittest discover -s tests -p 'test_*.py'
```

The regression tests use backend-shaped responses, including MLX's language
lists, without loading model weights. A local Apple Silicon smoke run can
additionally check actual MLX and ffmpeg integration using cached models.

Local validation on 2026-09-13 used Python 3.14.4 and cached `mlx-audio` 0.4.4
models with network downloads disabled:

- The locked base dependency environment passed all 182 unit tests, including
  16 new regression tests with additional subcases.
- A known English speech sample passed default VAD and alignment, reproduced
  the expected text exactly, and exported two cues and 17 word tokens with exit
  code 0.
- A 20-second Chinese singing excerpt exported six cues and 30 character
  tokens. Its remaining flat timings correctly produced a partial result.
- A 299.2-second Chinese singing sample with `--no-vad` exercised two windows
  and exported 82 cues and 379 character tokens. Its previously saved output
  had two cues and no tokens. Segment times were bounded and non-overlapping,
  and the aligner's remaining quality failures correctly produced exit code 1.
- The same song with default VAD only selected its first 5.2 seconds and
  returned no text. This is a remaining limitation for singing; the run was
  reported as partial. Use `--no-vad` for this input and review its timing.
- Temporary prepared audio directories were absent after the real-model runs.

These smoke checks validate integration and failure reporting, not a measured
improvement in model recognition or alignment accuracy on songs. The media and
local generated output files are not included in the repository.
