import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.prepare_reference_benchmark import eligible, select_rows
from tools.score_reference_benchmark import score, word_errors, words


class WordScoringTest(unittest.TestCase):
    def test_normalization_ignores_display_format_but_preserves_spoken_words(self):
        self.assertEqual(words('“Don’t” re-enter Number One\'!'), ["don't", "re", "enter", "number", "one"])
        self.assertNotEqual(words("we we can't go"), words("we cannot go"))
        self.assertNotEqual(words("two"), words("2"))

    def test_counts_substitution_deletion_insertion_and_empty_hypothesis(self):
        self.assertEqual(word_errors(words("we want to go home"), words("we need to go home now")), {
            "errors": 2, "substitutions": 1, "deletions": 0, "insertions": 1,
            "reference_words": 5, "wer": 0.4,
        })
        self.assertEqual(word_errors(words("we go go home"), words("we go home"))["deletions"], 1)
        self.assertEqual(word_errors(words("we go home"), [])["wer"], 1)
        self.assertIsNone(word_errors([], ["extra"])["wer"])

    def test_selection_is_order_independent_and_deduplicates_sentences(self):
        rows = [{"id": value, "filename": f"{value}-{recording}.wav", "num_samples": 160000,
                 "raw_transcription": "The speaker reads a complete sentence for this small evaluation sample."}
                for value in range(8) for recording in range(2)]
        first = select_rows(rows, 5)
        self.assertEqual(first, select_rows(list(reversed(rows)), 5))
        self.assertEqual(len({row["id"] for row in first}), 5)
        self.assertFalse(eligible({**rows[0], "raw_transcription": "There are 20 words in this sample and it contains numbers."}))


class ReferenceComparisonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "baseline"
        self.candidate = self.root / "candidate"
        self.baseline.mkdir()
        self.candidate.mkdir()
        self.samples = []

    def add_case(self, identifier, reference, original, corrected):
        raw_reference = (reference + "\n").encode()
        reference_path = self.root / f"{identifier}.txt"
        reference_path.write_bytes(raw_reference)
        self.samples.append({"id": identifier, "partition": "dev", "reference_text": reference,
                             "reference_path": reference_path.name,
                             "reference_sha256": hashlib.sha256(raw_reference).hexdigest()})
        segment = {"id": "seg-1", "start_time": 0.0, "end_time": 4.0, "text": original,
                   "tokens": [{"text": "original", "start_time": 0.0, "end_time": 1.0}]}
        baseline = {"source_path": f"/audio/{identifier}.wav", "segments": [segment]}
        candidate_segment = {**segment, "text": corrected}
        if corrected != original:
            candidate_segment["original_text"] = original
        candidate = {**baseline, "segments": [candidate_segment]}
        (self.baseline / f"{identifier}.json").write_text(json.dumps(baseline))
        (self.candidate / f"{identifier}.json").write_text(json.dumps(candidate))

    def evaluate(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps({"benchmark_version": "test", "normalization_version": "english-lexical-v1",
                                    "samples": self.samples}))
        return score(path, self.baseline, self.candidate, "dev")

    def test_reports_repairs_and_damage_separately_with_word_weighted_wer(self):
        self.add_case("repair", "we want to go", "we want two go", "we want to go")
        self.add_case("damage", "hello", "hello", "goodbye")
        report = self.evaluate()
        self.assertEqual(report["baseline"]["wer"], 1 / 5)
        self.assertEqual(report["candidate"]["wer"], 1 / 5)
        self.assertEqual(report["net_word_error_reduction"], 0)
        self.assertEqual(report["improved_clips"], 1)
        self.assertEqual(report["regressed_clips"], 1)
        self.assertEqual(report["clean_clip_damage_rate"], 1)

    def test_missing_prediction_cannot_silently_improve_the_score(self):
        self.add_case("missing", "correct text", "wrong text", "correct text")
        (self.candidate / "missing.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.evaluate()

    def test_reference_mutation_is_rejected(self):
        self.add_case("changed", "correct text", "wrong text", "correct text")
        (self.root / "changed.txt").write_text("wrong text\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.evaluate()

    def test_changed_timing_or_tokens_are_rejected(self):
        self.add_case("structural", "correct text", "wrong text", "correct text")
        path = self.candidate / "structural.json"
        document = json.loads(path.read_text())
        document["segments"][0]["tokens"] = []
        path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "tokens"):
            self.evaluate()

    def test_zero_clean_denominator_is_not_reported_as_zero_damage(self):
        self.add_case("none-clean", "we want two", "we want three", "we want 2")
        report = self.evaluate()
        self.assertIsNone(report["clean_clip_damage_rate"])
        self.assertEqual(report["normalization_review_clips"], 1)


if __name__ == "__main__":
    unittest.main()
