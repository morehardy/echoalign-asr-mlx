# Development Guide

This document collects contributor and maintainer workflows for
`echoalign-asr-mlx`. The user-facing README stays focused on installing and
running `easr`.

## Project Shape

- package name: `echoalign-asr-mlx`
- public CLI command: `easr`
- source package: `src/asr`
- test suite: `tests`
- Python target: `>=3.14,<3.15`
- environment manager: `uv`
- CI workflow: `.github/workflows/ci.yml`
- PyPI publish workflow: `.github/workflows/publish-pypi.yml`

Use `easr` in user-facing documentation. Some older planning notes may mention
`asr`, but the current public entry point is `easr`.

## Local Setup

Install system media dependencies:

```bash
brew install ffmpeg
```

Create/update the project environment with the MLX runtime extra:

```bash
uv sync --extra mlx
```

Verify the CLI:

```bash
uv run --python 3.14 --extra mlx easr --help
uv run --python 3.14 --extra mlx easr --version
```

## Test Commands

Run the full unit test suite:

```bash
PYTHONPATH=src uv run --python 3.14 python -m unittest discover -s tests -p 'test_*.py'
```

Run a focused test module:

```bash
PYTHONPATH=src uv run --python 3.14 python -m unittest tests.test_authority
```

Dry-check CLI parsing/help without the MLX extra:

```bash
uv run --python 3.14 easr --help
```

Run a local transcription smoke test against your own media:

```bash
uv run --python 3.14 --extra mlx easr /path/to/demo.mp4 --verbose --output-dir tmp/easr-smoke
```

## Local Calibration Evaluation

For the audio/reference benchmark, start with
[the v1 evaluation contract](evaluation/text-calibration-benchmark-v1.md) and
`tests/evaluation/calibration/reference-v1/README.md`. It uses fixed FLEURS
recordings with publisher-validated references, separates an internal development
and holdout partition, and scores saved ASR JSON without giving the reference
text to the models. The commands below retain the older synthetic-error fixture
for regression comparisons; that fixture is not independent audio ground truth.

Real calibration-model evaluation runs locally on Apple Silicon and is not part
of the Ubuntu GitHub workflow. Install the expanded MLX extra first:

```bash
uv sync --extra mlx
```

Rebuild the deterministic 100-case fixture only when intentionally reviewing
the labelled baseline:

```bash
PYTHONPATH=src uv run --python 3.14 --extra mlx \
  python tools/build_calibration_fixture.py
```

Run the labelled quality gate:

```bash
PYTHONPATH=src uv run --python 3.14 --extra mlx \
  python tools/evaluate_calibration.py labelled \
  tests/evaluation/calibration/policy-1/labelled.json \
  tests/evaluation/calibration/policy-1/qwen3.5-4b-4bit
```

Run the full saved-ASR observation without retranscribing the 88-minute audio:

```bash
PYTHONPATH=src uv run --python 3.14 --extra mlx \
  python tools/evaluate_calibration.py full \
  "tests/e2e/outputs/Metal Gear Solid Delta.json" \
  tests/evaluation/calibration/policy-1/qwen3.5-4b-4bit
```

For the short end-to-end check, make a temporary audio slice and run the public
CLI:

```bash
ffmpeg -y -i "tests/e2e/out1/Metal Gear Solid Delta.mp3" \
  -t 30 -c:a pcm_s16le /tmp/easr-calibration-smoke.wav
uv run --python 3.14 --extra mlx easr /tmp/easr-calibration-smoke.wav \
  --calibrate --verbose \
  --output-dir tests/evaluation/calibration/policy-1/qwen3.5-4b-4bit/short-e2e
```

Commit the labelled fixture, compact results, aggregate metrics, and short E2E
outputs. Do not commit model weights/cache, prompt bodies, raw model responses,
retry response bodies, or hidden reasoning. A model revision or policy change
gets a new sibling baseline directory rather than overwriting the prior one.

## Build Distributions

Build source and wheel artifacts:

```bash
uv build
```

The package version is derived from Git tags through `hatch-vcs`. A clean
release build from tag `v0.2.1` produces `0.2.1` distributions.

Install a local wheel in a target environment:

```bash
python3.14 -m pip install dist/echoalign_asr_mlx-<version>-py3-none-any.whl
```

For full transcription runtime from a source checkout, install with the MLX
extra:

```bash
python3.14 -m pip install ".[mlx]"
```

After publishing to an index such as PyPI, end users can install with:

```bash
python3.14 -m pip install "echoalign-asr-mlx[mlx]"
```

## Release to PyPI

This repository includes a publish workflow at:

```text
.github/workflows/publish-pypi.yml
```

Release flow:

1. Configure a Trusted Publisher in PyPI for this project:
   - project: `echoalign-asr-mlx`
   - owner/repo: the GitHub repository
   - workflow: `publish-pypi.yml`
   - environment: `pypi`
2. Merge release-ready code to `main`.
3. Create and publish a GitHub Release tagged `vX.Y.Z`, for example `v0.2.1`.
4. GitHub Actions runs tests, builds distributions with the tag-derived version,
   checks them with Twine, and publishes to PyPI.

The workflow also supports manual `workflow_dispatch`, but manual publishing
must run from a release tag such as `v0.2.1`.

## Developer Notes

- The provider boundary is intentionally hidden from the public CLI.
- Keep output layout stable across provider changes.
- Keep JSON exports rich enough to preserve fine-grained token alignment.
- Do not expose ASR and aligner model selection as separate public options
  unless the CLI contract is intentionally redesigned.
- `--verbose` writes metrics JSON and is the primary local optimization aid.
