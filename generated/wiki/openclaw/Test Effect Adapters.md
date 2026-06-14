# Test Effect Adapters

Status: `OPENCLAW_TEST_EFFECT_ADAPTERS_READY`

Universal adapters for useful Test Mode effects without production contamination.

## Effects
- SQLite: dry-run receipt or marked test row in dedicated test DB.
- Email: dry-run receipt; live test requires a future safe transport and only `winshiplive@gmail.com`.
- Files/Logic: copy-before-mutate into `/tmp/openclaw-mission-control/test_workspaces/`.

## Production Boundary
All test artifacts carry `OPENCLAW_TEST_ONLY_DO_NOT_USE_AS_PROOF_V0` and are rejected for production claims.
