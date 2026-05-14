# OpenClaw Full-Suite Failure Baseline v0

Generated: `2026-05-14T00:12:06-04:00`
Baseline run timestamp: `2026-05-14T00:05:36-04:00`
Git HEAD: `fb7ddb475032f8c5d0472e2a6401624f961a5c68`

This is an operator-readable baseline for the current full-suite failure landscape. It is classification-only. No fixes were attempted.

Detailed artifacts:

- `generated/full_suite_failure_baselines/full_suite_failure_baseline_v0_2026_05_14.md`
- `generated/full_suite_failure_baselines/full_suite_failure_baseline_v0_2026_05_14.json`

## Commands

Normal full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q
```

Result: collection stopped with exit code `2`.

Collection blocker:

- `tests/test_cassandra_voice.py` imports `numpy`.
- `numpy` is not installed in this environment.
- `numpy` was not installed for this lane.

Voice-ignored full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q --ignore=tests/test_cassandra_voice.py --tb=short --junitxml=/tmp/openclaw_full_suite_ignore_voice.xml
```

Result: `83 failed, 2623 passed, 1 skipped in 422.64s`.

This differs from the earlier observed `82 failed, 2624 passed, 1 skipped`. Treat `83 failed, 2623 passed, 1 skipped` as the current baseline for this workspace state.

Scoped substrate regression check:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_context_selection.py \
  tests/test_evidence_kettle.py \
  tests/test_corpus_atlas.py \
  tests/test_tool_inventory.py \
  tests/test_tool_inventory_read_model.py \
  tests/test_tool_intake.py \
  tests/test_tool_intake_read_model.py \
  -q
```

Result: `62 passed in 31.77s`.

## Top Failure Buckets

| Bucket | Count | Classification |
| --- | ---: | --- |
| `test_double_signature_drift` | 39 | Test doubles patch older Cassandra/runtime call signatures while current runtime passes keyword metadata such as `metadata` or `ops_packet`. |
| `cli_subprocess_import_path_failures` | 11 | Subprocess CLI tests launch scripts without the repo import path, producing `business_ops_ledger` import failures and empty JSON output. |
| `orientation_payment_status_context_contract_drift` | 11 | Cassandra/payment/orientation tests expect older status-route output, Gmail/payment behavior, or older orientation snapshot sections. |
| `identity_contact_fixture_drift` | 7 | Identity/contact matching tests return `None` against current fixtures/state. |
| `environment_external_fixture_or_dependency` | 3 | Missing local external fixture/package: `/mnt/c/OpenClaw/logs/expense_log.json` and `reportlab`. |

## Suspected Substrate Regressions

No suspected regressions were found in the recent SQLite/corpus/evidence/tool/context substrate lanes.

Evidence:

- The scoped substrate regression command passed with `62 passed`.
- The voice-ignored full suite did not report failures in:
  - `tests/test_context_selection.py`
  - `tests/test_evidence_kettle.py`
  - `tests/test_corpus_atlas.py`
  - `tests/test_tool_inventory.py`
  - `tests/test_tool_inventory_read_model.py`
  - `tests/test_tool_intake.py`
  - `tests/test_tool_intake_read_model.py`

Current suspected failure sources are older Cassandra connector/route tests, environment dependencies, subprocess CLI invocation contracts, static docs/output contracts, and fixture/state drift.

## Recommended Cleanup Lanes

1. Test-double signature cleanup: update Cassandra and inner-circle test stubs to accept the current `metadata` and `ops_packet` keyword shape, without changing production behavior.
2. CLI subprocess import-path cleanup: make legacy query scripts executable from subprocess tests without requiring implicit `PYTHONPATH`, or update tests to invoke them through the repo-supported path convention.
3. Cassandra payment/orientation contract review: decide whether current orientation-first responses are canonical or whether older payment/status routes should be restored.
4. Environment fixture lane: decide whether `tests/test_cassandra_connectors.py` should remain live-environment-gated, use fixture files, or be marked as optional in environments without `/mnt/c/OpenClaw/logs/expense_log.json` and `reportlab`.
5. Static docs/output contract refresh: review artifact checkpoint, evidence map, service freeze, dashboard headroom, and orientation snapshot tests against current generated surfaces.
6. Identity/contact fixture cleanup: refresh inner-circle and outreach fixtures or isolate them from accumulated local state.

## Boundaries

- No tests were fixed.
- `numpy` was not installed.
- Production code was not changed.
- Cassandra voice was not changed.
- Artifact expectations were not changed.
- Runtime, agents, Docker, Ollama, tools, and network behavior were not activated.
- Untracked `polish_loop/tasks/chief-cassandra-failure-*.md` files were left untouched.
