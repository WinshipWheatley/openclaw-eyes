# Stress-Fixes Promotion Result

## Status

`codex/stress-fixes` has been promoted to `main`.

Verified refs:

- `codex/stress-fixes`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- `origin/codex/stress-fixes`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- `main`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- `origin/main`: `814259044ad3dbe6c482757da2df45e4e98f82a3`

The prior local `main` ref was preserved before alignment:

- `backup/local-main-before-stress-promotion-20260701`: `6da749228ec13cf30e02b756a7cefa8a5c5d7c30`

## Green Gate Evidence

Required gate command:

```bash
OPENCLAW_TRUSTED_TEST_REF=origin/codex/morning-test-deflake bash scripts/green_gate.sh codex/stress-fixes
```

Trusted test ref:

- `origin/codex/morning-test-deflake`: `847783ebdc2a7ec9673cfc3236812ca4749b1b1c`

Passing full clean-room gate logs:

- `/tmp/openclaw-green-gate-runs/greengate-1782874960-1905847/pytest.log`
  - `9401 passed, 14 skipped, 3 subtests passed in 1460.20s (0:24:20)`
- `/tmp/openclaw-green-gate-runs/greengate-1782876601-1931934/pytest.log`
  - `9401 passed, 14 skipped, 3 subtests passed in 1410.94s (0:23:30)`

## Promotion Method

The remote release branch was advanced so `origin/main` equals `origin/codex/stress-fixes` at `81425904`.

Local `main` was later aligned to `origin/main` after preserving the old local `main` ref.

## Cleanup

Deleted redundant local branch:

- `codex/packet-health-audit-20260630`

Before deletion, `git cherry -v codex/stress-fixes codex/packet-health-audit-20260630` showed all seven commits as patch-equivalent (`-`) to `codex/stress-fixes`, so the branch was semantically redundant even though it was not an ancestor ref.

## Notes

The final promotion commit is test-only:

- `81425904 test: align tests with new implementation`

Touched files:

- `tests/test_agent_handoff_registry.py`
- `tests/test_chief_llm_router.py`
- `tests/test_frontdoor_resource_probe.py`
- `tests/test_maestro_cassandra_responder.py`
- `tests/test_niles_track_registry.py`

Runtime behavior was already in `codex/stress-fixes`; this promotion advanced `main` to match already-live integration code.
