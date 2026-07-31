# EchoAlign ASR

This context describes the language used for producing and textually calibrating timestamped transcription output.

## Language

**Text Calibration（文本校准）**:
The context-aware correction of demonstrable transcription mistakes through local replacements, including spelling, homophone, wrong-word, short-phrase, and context-supported proper-name errors. It excludes grammar or style polishing, punctuation or casing changes, filler removal, paraphrasing, summarisation, and factual rewriting.
_Avoid_: Editing, proofreading, rewriting

**English-primary Calibration（英文优先校准）**:
Text Calibration in which only English words or phrases may be changed. Non-English text may appear as read-only context, mixed-language Correction Units remain eligible, and wholly non-English units are skipped.
_Avoid_: English-only transcription, multilingual rewriting

**Subtitle Segment（字幕片段）**:
The canonical timestamped span emitted by transcription and consumed by exporters. It may contain one or more grammatical sentences.
_Avoid_: Sentence, line

**Recognition Text（识别原文）**:
The immutable text emitted by the ASR provider whose token content and timestamps remain the acoustic-alignment evidence.
_Avoid_: Calibrated Text, display text

**Calibrated Text（校准文本）**:
The sentence-level text derived from Recognition Text by applying validated corrections while preserving subtitle structure and timestamps. It is used for sentence-level exports and may intentionally differ from the original token text.
_Avoid_: Recognition Text, rewritten transcript

**Correction Unit（校准单元）**:
A single sentence represented by a continuous character range deterministically derived from one Subtitle Segment, normally bounded by sentence-ending punctuation. A trailing fragment is still one unit; model output never determines unit boundaries.
_Avoid_: Subtitle Segment, line, sentence

**Correction Context（校准上下文）**:
The ordered input supplied for one calibration judgment: up to three immediately preceding Correction Units from the same media transcription followed by one target Correction Unit. Context may cross Subtitle Segment boundaries but never media boundaries; preceding units use Calibrated Text produced earlier in the same run when available and remain read-only, while Correction Proposals may target only the final unit's Recognition Text.
_Avoid_: Batch, prompt

**Correction Proposal（校准建议）**:
A model-authored replacement targeting an exact character range within one Correction Unit. It identifies the expected source text, replacement text, and a Calibration Confidence Score without directly changing subtitle text; source and replacement lengths may differ.
_Avoid_: Correction, fix

**Calibration Confidence Score（校准置信分）**:
An integer from 1 through 5 expressing the model's confidence that a Correction Proposal is both necessary and correct: 1 is speculative, 3 remains materially ambiguous, and 5 is effectively certain. Scores 4 and 5 are high-confidence; lower scores are discarded.
_Avoid_: Quality score, probability

**Applied Correction（已应用校准）**:
A Correction Proposal that passes the confidence gate and deterministic validation, and whose replacement is written into the canonical subtitle text.
_Avoid_: Suggestion, model output

**Rejected Proposal（被拒建议）**:
A high-confidence Correction Proposal that fails deterministic validation. It is recorded with its rejection reason but never changes canonical subtitle text.
_Avoid_: Low-confidence output, unit error

**Calibration Structure Invariant（校准结构约束）**:
The requirement that calibration preserve Correction Unit and Subtitle Segment boundaries, ordering, and timestamps without splitting, merging, deleting, or paraphrasing whole sentences. A local replacement may change character count, word length, or word count.
_Avoid_: Equal-length replacement, sentence-length constraint

**Calibration Run（校准运行）**:
The attempt to calibrate every eligible Correction Unit in one media transcription. A run may succeed completely, remain partial when individual units fail, or fail while preserving the uncalibrated transcription when the calibration model is unavailable.
_Avoid_: ASR run, model request

**Calibration Result（校准结果）**:
The per-media audit artifact produced whenever calibration is requested, including when no text changes or calibration fails. It identifies the Calibration Run status and the text that was changed, rejected, or left unprocessed because of unit-level errors.
_Avoid_: Transcript JSON, model response
