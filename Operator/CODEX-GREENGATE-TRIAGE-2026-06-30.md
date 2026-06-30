# Green-Gate Triage - 2026-06-30

## Gate Confirmation

Command run:

```bash
OPENCLAW_TRUSTED_TEST_REF=origin/codex/morning-test-deflake bash scripts/green_gate.sh codex/stress-fixes
```

The gate did use the required trusted-test ref, not the stale default. The clean-room checkout tested commit `8b79e402` and restored tests from `origin/codex/morning-test-deflake` at `4f7c876b`.

Result:

```text
316 failed, 9079 passed, 14 skipped, 2 errors, 3 subtests passed in 1567.94s (0:26:07)
```

Full pytest log:

```text
/tmp/openclaw-green-gate-runs/greengate-1782847399-1596044/pytest.log
```

Extracted failing/error nodes:

```text
/tmp/openclaw-green-gate-runs/greengate-1782847399-1596044/failure-summary.tsv
```

Note: local `codex/stress-fixes` is currently at `7e8e1490`, so the next green-gate run must re-baseline the current branch tip after fixes. `main` was not touched.

## Bucket Counts

Total failing/error nodes triaged: 318.

| Bucket | Count | Headline |
| --- | ---: | --- |
| A. Built but not committed | 2 | Confirmed missing ignored source module: `self_knowledge.py`, causing two `test_no_response_watchdog.py` import failures. |
| B. Clean-room fixtures/state/DBs/projections absent | 233 | Dominant bucket. Failures are concentrated in truth/ledger/read-model/proof/SQLite fixture surfaces that live state supplies but a clean checkout does not. |
| C. Real breakage, stale contracts, or policy/model drift | 83 | Includes old model-retiering expectations, activation-state assertions, sqlite runtime behavior, global run-mode behavior, and current policy text mismatches. |

## Bucket A Scope

Confirmed A is small, not a mass-add situation:

- `tests/test_no_response_watchdog.py` has two `ModuleNotFoundError: No module named 'self_knowledge'` failures.
- `self_knowledge.py` exists in the live checkout but is ignored by `.gitignore` and absent from committed clean-room state.

There is a much larger ignored Python surface in the live checkout, but this gate log does not show it as the main failure cause. Do not mass commit ignored files.

Dirty tracked source candidates observed in the live tree:

- `google_access_broker.py`
- `polish_loop/control_plane.py`
- `polish_loop_backlog_ingest.py`
- `systemd/user/hermes-gateway.service.in`

Those map to at most a small number of specific failures and should be handled only with targeted tests, not by broad staging.

## Bucket B Shape

Largest clusters:

- `tests/test_truth_reconciliation_gateway.py`: 23
- `tests/test_external_lm_shadow_adapter.py`: 13
- `tests/test_external_lm_safe_package_compiler.py`: 12
- `tests/test_lm_readiness_dashboard.py`: 7
- `tests/test_truth_substrate_status.py`: 7
- `tests/test_answer_harness.py`: 6
- `tests/test_external_shadow_provider_config.py`: 6
- `tests/test_ingestion_guard.py`: 6
- `tests/test_packet_sqlite_flip.py`: 6
- `tests/test_tool_intake_read_model.py`: 6
- `tests/test_truth_ingest_readiness_report.py`: 6

Representative symptoms:

- `Database not found` / `Database missing`
- `no such table`
- `Missing tables`
- `KeyError` from generated read-model or registry projections
- `JSONDecodeError` from missing or empty generated fixture output
- expected seeded counts are zero in clean-room state

This bucket should be fixed by making tests create bounded fixtures from committed source, or by adding narrowly scoped committed fixture inputs where appropriate. It should not be fixed by committing live state DBs or generated read-model outputs.

## Bucket C Shape

Largest clusters:

- `tests/test_chief_llm_router.py`: 18 old model expectations such as `gemma4:*` versus current qwen/magistral retiering.
- `tests/test_activation_gate_register.py`: 14 activation disposition mismatches.
- `tests/test_backend_sqlite_runtime.py`: 9 sqlite runtime contract failures.
- `tests/test_live_lm_activation_requirements.py`: 5 live-LM readiness/activation contract failures.
- `tests/test_frontdoor_resource_probe.py`: 4 routing/selection expectation drift failures.

Representative symptoms:

- expected old model names after local-model retiering
- expected `canary` or `intentionally_off` while current registry says `operator_approved_live`
- sqlite helpers not failing closed or not reopening as tests expect
- changed policy text, route, or staging behavior

## Recommendation

Proceed with targeted fixes only:

1. Add `self_knowledge.py` explicitly if inspection confirms it is source-only and contains no secrets.
2. Fix Bucket B by moving tests away from session-generated state and toward deterministic committed fixtures or in-test fixture builders.
3. Fix Bucket C by updating stale trusted-test expectations where the live branch behavior is intentional, and repairing real runtime-contract regressions where it is not.

Do not promote `main` until the full clean-room green-gate passes with the deflake trusted-test ref.
