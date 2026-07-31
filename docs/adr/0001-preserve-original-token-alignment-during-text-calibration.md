---
status: accepted
---

# Preserve original token alignment during text calibration

Text calibration changes sentence-level display text but does not rewrite token text or timing. A calibrated Subtitle Segment retains its Recognition Text alongside its Calibrated Text; sentence-level exports use the calibrated form, while token-granularity exports continue to expose the original aligned tokens. To preserve the existing JSON contract, `original_text` is serialized only for segments that were actually changed and is absent when calibration is disabled or no correction was applied. We chose this over estimating new token timings or running a second forced alignment so that generated timing is never presented as acoustic evidence.
