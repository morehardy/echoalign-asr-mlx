import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from asr.cli import main
from asr.exporters import render_json, render_srt
from asr.media import FfmpegMediaPreparer
from asr.models import Token, TranscriptionDocument
from asr.pipeline import process_media_file
from asr.output import validate_output_paths
from asr.providers.qwen_mlx import QwenMlxProvider, WindowRun
from asr.providers.windowing import AlignmentWindow
from asr.vad import build_speech_plan


class Backend:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, audio, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class IdentityPreparer:
    def prepare(self, source):
        return source


def make_provider(texts, alignments, duration=10.0):
    provider = QwenMlxProvider()
    provider._asr_model = Backend(texts)
    provider._aligner_model = Backend(alignments)
    provider._probe_duration_sec = lambda _: duration
    provider._resolve_silence_anchor = lambda *args: None
    provider._context_input_path = lambda *args: "probe.wav"
    return provider


def aligned(text, start, end):
    return SimpleNamespace(text=text, start_time=start, end_time=end)


class LanguageContractTest(unittest.TestCase):
    def test_chinese_backend_names_lists_and_codes_keep_character_alignment(self):
        text = "\u4f60\u597d\u4e16\u754c"
        for language in (["Chinese"], "Chinese", "zh", "zh-CN"):
            with self.subTest(language=language):
                provider = make_provider(
                    [SimpleNamespace(text=text, language=language)],
                    [[aligned(char, 1 + i * 0.2, 1.15 + i * 0.2)
                      for i, char in enumerate(text)]],
                )
                document = provider.transcribe(Path("probe.wav"))
                tokens = [token for segment in document.segments for token in segment.tokens]
                self.assertEqual([token.text for token in tokens], list(text))
                self.assertEqual([token.unit for token in tokens], ["char"] * 4)
                self.assertEqual(document.detected_language, "zh")
                self.assertEqual(provider._aligner_model.calls[0]["language"], "Chinese")
                self.assertAlmostEqual(tokens[0].start_time, 1.0)

    def test_english_list_and_code_use_aligner_language_name(self):
        for language in (["English"], "en", [None, "English", "English"]):
            with self.subTest(language=language):
                provider = make_provider(
                    [SimpleNamespace(text="Hello world.", language=language)],
                    [[aligned("Hello", 1.0, 1.3), aligned("world", 1.4, 1.7)]],
                )
                document = provider.transcribe(Path("probe.wav"))
                self.assertEqual(document.detected_language, "en")
                self.assertEqual(provider._aligner_model.calls[0]["language"], "English")
                self.assertEqual(document.segments[0].text, "Hello world.")

    def test_mixed_chinese_english_keeps_words_and_sentence_punctuation(self):
        text = "\u7528Python\u5199code\u3002"
        provider = make_provider(
            [SimpleNamespace(text=text, language=["Chinese"])],
            [[aligned(part, 1 + i * 0.3, 1.2 + i * 0.3)
              for i, part in enumerate(["\u7528", "Python", "\u5199", "code"])]],
        )
        document = provider.transcribe(Path("probe.wav"))
        tokens = [token for segment in document.segments for token in segment.tokens]
        self.assertEqual([token.text for token in tokens], ["\u7528", "Python", "\u5199", "code\u3002"])
        self.assertEqual([token.unit for token in tokens], ["char", "word", "char", "word"])
        self.assertEqual(document.segments[0].text, text)


class PartialTranscriptionTest(unittest.TestCase):
    def run_cli(self, provider, source):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("asr.cli.run_environment_preflight", return_value=(True, "")), \
             patch("asr.cli.create_default_provider", return_value=provider), \
             patch("asr.cli.FfmpegMediaPreparer", return_value=IdentityPreparer()), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(source), "--no-vad"])
        return code, stderr.getvalue()

    def test_aligner_exception_preserves_recognition_and_cli_reports_partial(self):
        provider = make_provider(
            [SimpleNamespace(text=text, language=["English"])
             for text in ["First.", "Important middle content.", "Last."]],
            [[aligned("First", 1.0, 1.4)], RuntimeError("alignment failed"),
             [aligned("Last", 16.0, 16.4)]],
            duration=340.0,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "probe.wav"
            source.touch()
            code, stderr = self.run_cli(provider, source)
            payload = json.loads((source.parent / "outputs/probe.json").read_text())
        self.assertEqual(code, 1)
        self.assertIn("partial", stderr)
        self.assertIn("alignment failed", stderr)
        self.assertEqual(payload["status"], "partial")
        self.assertEqual([segment["text"] for segment in payload["segments"]],
                         ["First.", "Important middle content.", "Last."])
        self.assertEqual(payload["segments"][1]["timing_source"], "estimated")

    def test_recognition_exception_still_exports_other_windows_and_reports_partial(self):
        provider = make_provider(
            [RuntimeError("recognition failed"), SimpleNamespace(text="Tail.", language=["English"])],
            [[aligned("Tail", 16.0, 16.4)]],
            duration=299.0,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "probe.wav"
            source.touch()
            code, stderr = self.run_cli(provider, source)
            payload = json.loads((source.parent / "outputs/probe.json").read_text())
        self.assertEqual(code, 1)
        self.assertIn("recognition failed", stderr)
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["segments"][0]["text"], "Tail.")

    def test_empty_recognition_does_not_call_aligner(self):
        provider = make_provider([SimpleNamespace(text="", language=[])], [])
        document = provider.transcribe(Path("probe.wav"))
        self.assertEqual(document.segments, [])
        self.assertEqual(provider._aligner_model.calls, [])


class WindowBoundaryRegressionTest(unittest.TestCase):
    def test_shared_audio_with_small_timing_drift_merges_boundary_word_once(self):
        provider = QwenMlxProvider()
        def token(text, start, end):
            return Token(text, start, end, "word", "en")

        left = [token(f"left{i}", i * 2.0, i * 2.0 + 0.3) for i in range(60)]
        left += [token("before", 140, 140.3), token("boundary", 149.8, 150.2), token("after", 155, 155.3)]
        right = [token("before", 140, 140.3), token("boundary", 149.9, 150.3), token("after", 155, 155.3)]
        right += [token(f"right{i}", 170 + i * 2.0, 170 + i * 2.0 + 0.3) for i in range(60)]
        runs = []
        for window, tokens in [(AlignmentWindow(0, 0, 150, 0, 165), left),
                               (AlignmentWindow(1, 150, 300, 135, 300), right)]:
            before, core, after = provider._split_window_tokens(tokens, window)
            runs.append(WindowRun(
                window=window, text=provider._join_tokens(tokens), tokens=tokens,
                core_tokens=core, left_overlap_tokens=before, right_overlap_tokens=after,
                core_text=provider._join_tokens(core), has_timing_anchor=True,
                timing_source_counts={"aligner": len(tokens)},
            ))
        provider._evaluate_window_qualities(runs)
        merged = provider._merge_window_runs(runs)
        self.assertTrue(all(run.quality.passed for run in runs))
        self.assertEqual([token.text for token in merged].count("boundary"), 1)
        self.assertEqual(len(merged), 123)


class FallbackExportRegressionTest(unittest.TestCase):
    def test_long_unaligned_transcript_has_readable_estimated_cues_and_token_fallback(self):
        text = " ".join(["example"] * 250)
        provider = make_provider([SimpleNamespace(text=text, language=["English"])], [[]], duration=149.0)
        document = provider.transcribe(Path("probe.wav"))
        self.assertGreater(len(document.segments), 20)
        self.assertEqual(" ".join(segment.text for segment in document.segments), text)
        self.assertGreater(document.segments[-1].end_time, 140.0)
        for segment in document.segments:
            self.assertEqual(segment.tokens, [])
            self.assertEqual(segment.timing_source, "estimated")
            self.assertLessEqual(len(segment.text), 64)
            self.assertLessEqual(segment.end_time - segment.start_time, 6.0 + 1e-6)
        payload = json.loads(render_json(document, granularity="token"))
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(len(payload["items"]), len(document.segments))
        self.assertTrue(all(item["unit"] == "segment" for item in payload["items"]))
        self.assertIn("example", render_srt(document, granularity="token"))


class OutputCollisionRegressionTest(unittest.TestCase):
    def assert_collision(self, directory, names, extra_args=()):
        root = Path(directory)
        for name in names:
            (root / name).touch()
        output = root / "outputs"
        output.mkdir()
        sentinel = output / "demo.srt"
        sentinel.write_text("existing subtitles")
        stderr = io.StringIO()
        with patch("asr.cli.run_environment_preflight", return_value=(True, "")) as preflight, \
             patch("asr.cli.create_default_provider") as factory, \
             patch("asr.cli.process_media_file") as process, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = main([str(root), "--no-vad", *extra_args])
        self.assertEqual(code, 1)
        self.assertIn("collision", stderr.getvalue().lower())
        for name in names:
            self.assertIn(name, stderr.getvalue())
        preflight.assert_not_called()
        factory.assert_not_called()
        process.assert_not_called()
        self.assertEqual(sentinel.read_text(), "existing subtitles")

    def test_different_extensions_cannot_overwrite_the_same_subtitles(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_collision(directory, ["demo.mp3", "demo.wav"])

    def test_metrics_sidecar_cannot_overwrite_another_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_collision(directory, ["demo.mp3", "demo.metrics.wav"], ["--verbose"])

    def test_case_only_output_names_are_collisions_on_macos(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_collision(directory, ["Demo.mp3", "demo.wav"])

    def test_symlinked_input_keeps_its_lexical_output_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            external = root / "external.wav"
            external.touch()
            link = media / "alias.wav"
            link.symlink_to(external)
            validate_output_paths([(link, media)], output_dir=None, suffixes=[".srt"])

    def test_files_from_different_roots_cannot_collide_in_shared_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for name in ("a", "b"):
                media = root / name
                media.mkdir()
                source = media / "demo.wav"
                source.touch()
                sources.append((source, media))
            with self.assertRaisesRegex(ValueError, "collision"):
                validate_output_paths(sources, output_dir=root / "outputs", suffixes=[".srt"])


class PreparedAudioLifecycleTest(unittest.TestCase):
    def test_cleanup_only_releases_the_requested_owned_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            source.write_bytes(b"original")
            preparer = FfmpegMediaPreparer()
            with patch("asr.media.subprocess.run"), patch("tempfile.tempdir", directory):
                first = preparer.prepare(source)
                second = preparer.prepare(source)
            try:
                preparer.cleanup(source)
                preparer.cleanup(first)
                preparer.cleanup(first)
                self.assertFalse(first.parent.exists())
                self.assertTrue(second.parent.exists())
                self.assertEqual(source.read_bytes(), b"original")
            finally:
                preparer.cleanup(second)

    def test_prepared_audio_is_removed_after_success_failure_silence_and_interrupt(self):
        for outcome in ("success", "failure", "silence", "interrupt"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "source.mp3"
                source.write_bytes(b"source")
                prepared_paths = []

                def convert(command, **kwargs):
                    target = Path(command[-1])
                    target.write_bytes(b"prepared audio")
                    prepared_paths.append(target)

                def transcribe(path):
                    self.assertTrue(path.exists())
                    if outcome == "failure":
                        raise RuntimeError("recognition failed")
                    if outcome == "interrupt":
                        raise KeyboardInterrupt()
                    return TranscriptionDocument(str(path), "fake", [])

                provider = SimpleNamespace(name="fake", transcribe=Mock(side_effect=transcribe))
                vad = SimpleNamespace(build_plan=lambda _: build_speech_plan(duration_sec=1, raw_spans=[]))
                preparer = FfmpegMediaPreparer()
                with patch("asr.media.subprocess.run", side_effect=convert), \
                     patch("tempfile.tempdir", directory):
                    try:
                        process_media_file(
                            source_path=source, provider=provider,
                            media_preparer=preparer,
                            vad_enabled=outcome == "silence", vad_preprocessor=vad,
                        )
                    except (RuntimeError, KeyboardInterrupt):
                        self.assertIn(outcome, ("failure", "interrupt"))
                self.assertEqual(len(prepared_paths), 1)
                self.assertFalse(prepared_paths[0].parent.exists())
                self.assertEqual(source.read_bytes(), b"source")
                if outcome == "silence":
                    provider.transcribe.assert_not_called()

    def test_failed_conversion_removes_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp3"
            source.touch()
            error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="invalid media")
            with patch("asr.media.subprocess.run", side_effect=error), patch("tempfile.tempdir", directory):
                with self.assertRaisesRegex(RuntimeError, "invalid media"):
                    FfmpegMediaPreparer().prepare(source)
            self.assertEqual(list(Path(directory).glob("asr-media-*")), [])
            self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
