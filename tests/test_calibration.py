import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from asr.calibration import (
    CALIBRATION_MODEL_ID,
    CALIBRATION_MODEL_REVISION,
    CalibrationGenerationError,
    CalibrationModelError,
    calibrate_document,
    render_calibration_json,
    split_correction_units,
)
from asr.calibration_mlx import MlxVlmCorrector
from asr.models import Segment, Token, TranscriptionDocument


class CorrectionUnitSplittingTest(unittest.TestCase):
    def test_preserves_offsets_while_handling_abbreviations_decimals_quotes_and_fragments(
        self,
    ) -> None:
        text = 'Dr. Fox paid 3.14 in the U.S. "Is that right?" Yes! trailing fragment'

        ranges = split_correction_units(text)

        self.assertEqual(
            [text[start:end] for start, end in ranges],
            [
                'Dr. Fox paid 3.14 in the U.S. "Is that right?"',
                "Yes!",
                "trailing fragment",
            ],
        )
        self.assertEqual(ranges, [(0, 46), (47, 51), (52, 69)])


class _FakeCorrector:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[tuple[list[str], str, str | None]] = []

    def generate(
        self,
        context: list[str],
        target: str,
        retry_error: str | None = None,
    ) -> str:
        self.calls.append((context, target, retry_error))
        return next(self.responses)


class CalibrationServiceTest(unittest.TestCase):
    def test_applies_variable_length_correction_and_rolls_it_into_cross_segment_context(
        self,
    ) -> None:
        original_token = Token(
            text="two", start_time=0.3, end_time=0.6, unit="word", language="en"
        )
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text="I want two go. 你好。",
                    start_time=0.0,
                    end_time=1.0,
                    language="en",
                    tokens=[original_token],
                ),
                Segment(
                    id="seg-2",
                    text="I said two go.",
                    start_time=1.0,
                    end_time=2.0,
                    language="en",
                    tokens=[],
                ),
            ],
        )
        corrector = _FakeCorrector(
            [
                '{"proposals":[{"start":7,"end":10,"source":"two",'
                '"replacement":"to","score":5}]}',
                '{"proposals":[{"start":7,"end":10,"source":"two",'
                '"replacement":"to","score":3}]}',
            ]
        )

        calibrated, result = calibrate_document(document, corrector=corrector)

        self.assertEqual(calibrated.segments[0].text, "I want to go. 你好。")
        self.assertEqual(calibrated.segments[0].original_text, "I want two go. 你好。")
        self.assertEqual(calibrated.segments[1].text, "I said two go.")
        self.assertIsNone(calibrated.segments[1].original_text)
        self.assertIs(calibrated.segments[0].tokens[0], original_token)
        self.assertEqual(
            corrector.calls,
            [
                ([], "I want two go.", None),
                (["I want to go.", "你好。"], "I said two go.", None),
            ],
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.corrected_units), 1)
        self.assertEqual(result.corrected_units[0]["unit_id"], "seg-1:unit-1")
        self.assertEqual(result.rejected_proposals, [])
        self.assertEqual(result.unit_errors, [])
        self.assertEqual(
            result.metrics.to_dict(),
            {
                "eligible_unit_count": 2,
                "model_request_count": 2,
                "retry_count": 0,
                "low_confidence_discard_count": 1,
                "applied_proposal_count": 1,
                "corrected_unit_count": 1,
                "rejected_proposal_count": 0,
                "unit_error_count": 0,
            },
        )

    def test_retries_invalid_json_three_times_then_continues_after_partial_unit(
        self,
    ) -> None:
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text="First sentence. Second sentence.",
                    start_time=0.0,
                    end_time=2.0,
                    language="en",
                )
            ],
        )
        corrector = _FakeCorrector(
            ["not json", "[]", '{"proposals":"bad"}', '{"proposals":[{}]}']
            + ['{"proposals":[]}']
        )

        calibrated, result = calibrate_document(document, corrector=corrector)

        self.assertEqual(calibrated.segments[0].text, document.segments[0].text)
        self.assertEqual(result.status, "partial")
        self.assertEqual(
            result.unit_errors,
            [
                {
                    "unit_id": "seg-1:unit-1",
                    "attempts": 4,
                    "code": "invalid_response",
                }
            ],
        )
        self.assertEqual(len(corrector.calls), 5)
        self.assertIsNone(corrector.calls[0][2])
        self.assertTrue(all(call[2] for call in corrector.calls[1:4]))
        self.assertEqual(
            corrector.calls[4],
            (["First sentence."], "Second sentence.", None),
        )
        self.assertEqual(result.metrics.model_request_count, 5)
        self.assertEqual(result.metrics.retry_count, 3)
        self.assertEqual(result.metrics.unit_error_count, 1)

    def test_rejects_overlap_group_but_applies_deduplicated_nonoverlapping_proposal(
        self,
    ) -> None:
        target = "I want two go and sea it."
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text=target,
                    start_time=0.0,
                    end_time=1.0,
                    language="en",
                )
            ],
        )
        sea_to_see = {
            "start": 18,
            "end": 21,
            "source": "sea",
            "replacement": "see",
            "score": 5,
        }
        corrector = _FakeCorrector(
            [
                json.dumps(
                    {
                        "proposals": [
                            {
                                "start": 7,
                                "end": 10,
                                "source": "two",
                                "replacement": "to",
                                "score": 5,
                            },
                            {
                                "start": 7,
                                "end": 13,
                                "source": "two go",
                                "replacement": "to go",
                                "score": 4,
                            },
                            sea_to_see,
                            sea_to_see,
                            {
                                "start": 0,
                                "end": 1,
                                "source": "I",
                                "replacement": "eye",
                                "score": 3,
                            },
                        ]
                    }
                )
            ]
        )

        calibrated, result = calibrate_document(document, corrector=corrector)

        self.assertEqual(calibrated.segments[0].text, "I want two go and see it.")
        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.corrected_units[0]["applied"],
            [sea_to_see],
        )
        self.assertEqual(
            [item["code"] for item in result.rejected_proposals],
            ["overlapping_ranges", "overlapping_ranges"],
        )

    def test_model_initialization_failure_preserves_document_and_renders_failed_audit(
        self,
    ) -> None:
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text="Keep this text.",
                    start_time=0.0,
                    end_time=1.0,
                    language="en",
                )
            ],
        )

        class FailingCorrector:
            def generate(
                self,
                context: list[str],
                target: str,
                retry_error: str | None = None,
            ) -> str:
                raise CalibrationModelError("model unavailable")

        calibrated, result = calibrate_document(
            document, corrector=FailingCorrector()
        )
        payload = json.loads(render_calibration_json(result))

        self.assertIs(calibrated, document)
        self.assertEqual(calibrated.segments[0].text, "Keep this text.")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["error"], "model unavailable")
        self.assertNotIn("raw_response", payload)

    def test_deterministic_rejections_use_stable_codes_without_retry(self) -> None:
        target = "Fix word 你好."
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text=target,
                    start_time=0.0,
                    end_time=1.0,
                    language="en",
                )
            ],
        )
        corrector = _FakeCorrector(
            [
                json.dumps(
                    {
                        "proposals": [
                            {
                                "start": 0,
                                "end": 1,
                                "source": "",
                                "replacement": "x",
                                "score": 5,
                            },
                            {
                                "start": 4,
                                "end": 8,
                                "source": "word",
                                "replacement": "",
                                "score": 5,
                            },
                            {
                                "start": -1,
                                "end": 3,
                                "source": "Fix",
                                "replacement": "Fit",
                                "score": 5,
                            },
                            {
                                "start": 0,
                                "end": 3,
                                "source": "Foo",
                                "replacement": "Fix",
                                "score": 5,
                            },
                            {
                                "start": 0,
                                "end": 3,
                                "source": "Fix",
                                "replacement": "Fix",
                                "score": 5,
                            },
                            {
                                "start": 9,
                                "end": 11,
                                "source": "你好",
                                "replacement": "hello",
                                "score": 5,
                            },
                            {
                                "start": 4,
                                "end": 8,
                                "source": "word",
                                "replacement": "wo\nrd",
                                "score": 5,
                            },
                            {
                                "start": 4,
                                "end": 8,
                                "source": "word",
                                "replacement": "word. Next",
                                "score": 5,
                            },
                        ]
                    }
                )
            ]
        )

        calibrated, result = calibrate_document(document, corrector=corrector)

        self.assertEqual(calibrated.segments[0].text, target)
        self.assertEqual(len(corrector.calls), 1)
        self.assertEqual(result.status, "success")
        self.assertEqual(
            [item["code"] for item in result.rejected_proposals],
            [
                "empty_source",
                "empty_replacement",
                "invalid_range",
                "source_mismatch",
                "no_change",
                "no_english_source",
                "newline_replacement",
                "structure_changed",
            ],
        )

    def test_applies_multiple_original_offsets_from_right_to_left(self) -> None:
        document = TranscriptionDocument(
            source_path="demo.mp4",
            provider_name="fake",
            segments=[
                Segment(
                    id="seg-1",
                    text="I want two go and sea it.",
                    start_time=0.0,
                    end_time=1.0,
                    language="en",
                )
            ],
        )
        corrector = _FakeCorrector(
            [
                json.dumps(
                    {
                        "proposals": [
                            {
                                "start": 7,
                                "end": 10,
                                "source": "two",
                                "replacement": "to",
                                "score": 5,
                            },
                            {
                                "start": 18,
                                "end": 21,
                                "source": "sea",
                                "replacement": "see",
                                "score": 5,
                            },
                        ]
                    }
                )
            ]
        )

        calibrated, result = calibrate_document(document, corrector=corrector)

        self.assertEqual(calibrated.segments[0].text, "I want to go and see it.")
        self.assertEqual(len(result.corrected_units[0]["applied"]), 2)


class MlxVlmCorrectorTest(unittest.TestCase):
    def test_loads_pinned_model_once_and_uses_deterministic_text_generation(
        self,
    ) -> None:
        calls: dict[str, list[object]] = {
            "load": [],
            "template": [],
            "generate": [],
            "schema": [],
        }
        model = SimpleNamespace(config=SimpleNamespace(model_type="qwen3_5"))
        processor = object()
        fake_module = types.ModuleType("mlx_vlm")
        fake_structured = types.ModuleType("mlx_vlm.structured")
        schema_resets: list[bool] = []

        def fake_load(model_id: str, **kwargs: object) -> tuple[object, object]:
            calls["load"].append((model_id, kwargs))
            return model, processor

        def fake_template(*args: object, **kwargs: object) -> str:
            calls["template"].append((args, kwargs))
            return "formatted prompt"

        def fake_generate(*args: object, **kwargs: object) -> object:
            calls["generate"].append((args, kwargs))
            return SimpleNamespace(text='{"proposals":[]}')

        def fake_schema(tokenizer: object, schema: object) -> object:
            calls["schema"].append((tokenizer, schema))
            return SimpleNamespace(reset=lambda: schema_resets.append(True))

        fake_module.load = fake_load  # type: ignore[attr-defined]
        fake_module.apply_chat_template = fake_template  # type: ignore[attr-defined]
        fake_module.generate = fake_generate  # type: ignore[attr-defined]
        fake_structured.build_json_schema_logits_processor = fake_schema  # type: ignore[attr-defined]

        corrector = MlxVlmCorrector()
        self.assertEqual(calls["load"], [])

        with patch.dict(
            sys.modules,
            {
                "mlx_vlm": fake_module,
                "mlx_vlm.structured": fake_structured,
            },
        ):
            first = corrector.generate([], "Clean sentence.")
            second = corrector.generate(["Clean sentence."], "Another sentence.")

        self.assertEqual(first, '{"proposals":[]}')
        self.assertEqual(second, '{"proposals":[]}')
        self.assertEqual(
            calls["load"],
            [
                (
                    CALIBRATION_MODEL_ID,
                    {"revision": CALIBRATION_MODEL_REVISION},
                )
            ],
        )
        for _, kwargs in calls["generate"]:
            self.assertEqual(kwargs["prompt"], "formatted prompt")
            self.assertEqual(kwargs["temperature"], 0)
            self.assertEqual(kwargs["max_tokens"], 256)
            self.assertIs(kwargs["enable_thinking"], False)
            self.assertIs(kwargs["verbose"], False)
            self.assertEqual(len(kwargs["logits_processors"]), 1)
        self.assertEqual(schema_resets, [True, True])

    def test_reports_schema_processor_setup_as_generation_failure(self) -> None:
        corrector = MlxVlmCorrector()
        corrector._model = SimpleNamespace(config=object())
        corrector._processor = object()
        corrector._apply_chat_template = lambda *args, **kwargs: "prompt"

        def fail_schema(*args: object, **kwargs: object) -> object:
            raise RuntimeError("schema unavailable")

        corrector._build_schema_processor = fail_schema

        with self.assertRaisesRegex(
            CalibrationGenerationError,
            "schema unavailable",
        ):
            corrector.generate([], "Clean sentence.")


if __name__ == "__main__":
    unittest.main()
