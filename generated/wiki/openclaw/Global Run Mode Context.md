# Global Run Mode Context

Status: `OPENCLAW_GLOBAL_RUN_MODE_CONTEXT_READY`

Run mode is a backend source of truth for production, dry-run test, and controlled live-test behavior.

## Contracts

- `RUN_MODE_CONTEXT_V0`
- `OPERATOR_RUN_MODE_SET_REQUEST_V0`
- `OPERATOR_RUN_MODE_STATE_V0`
- `RUN_MODE_TRANSITION_RECEIPT_V0`
- `TEST_ARTIFACT_PRODUCTION_REJECTION_V0`

## Rules

- Production is the default when no state exists.
- Test artifacts carry `OPENCLAW_TEST_ONLY_DO_NOT_USE_AS_PROOF_V0`.
- Production proof rejects test-only artifacts.
- Test-live requires verified test execution authority and an allowlisted recipient.
- Run mode does not grant protected business authority.
