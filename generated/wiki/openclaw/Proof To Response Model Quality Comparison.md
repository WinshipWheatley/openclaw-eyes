# Proof To Response Model Quality Comparison

Status: `PROOF_RESPONSE_MODEL_QUALITY_COMPARISON_READY`

This comparison uses recorded local read models only. It does not invoke models, call APIs, browse, send prompts, send proof bundles, mutate business systems, or push.

## Summary

- `local_qwen_first_run`: score `5/15`, class `not_ready`
- `external_synthetic_manual_response`: score `14/15`, class `strong`
- `shadow_mock_baseline`: score `14/15`, class `strong`

## Recommendation

Recommended next test: `retry_local_with_schema_adapter`

- The local qwen run failed primarily because it did not return JSON, not because it made unsafe business claims.
- The schema adapter and aligned synthetic external sample show that verifier-compatible JSON can pass without loosening rules.
- The shadow baseline remains clean, so the next local test should target schema compliance before expanding external samples.

## Boundary

- Candidate text is not truth.
- The verifier remains the publication gate.
- Synthetic success is not real Finance truth.
- Private proof and business execution remain blocked.
