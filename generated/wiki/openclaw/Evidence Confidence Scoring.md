# Evidence Confidence Scoring

Status: EVIDENCE_CONFIDENCE_SCORING_READY

paid truth requires payment evidence; sent truth requires explicit sent/manual-send evidence.

## Classes
- proven_receipt: 0.95
- proven_artifact_hash: 0.9
- operator_reported: 0.75
- generated_summary: 0.55
- inferred: 0.4
- stale: 0.2
- rejected: 0.0
- test_only: 0.1
- unknown: 0.0

Generated summaries cannot override receipts. Test-only facts stay out of primary UI truth.
