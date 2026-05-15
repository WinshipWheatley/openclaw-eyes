# OpenClaw Agent Runtime Readiness v0

Status: implemented backend readiness/read-model lane.

This layer verifies whether OpenClaw agent lanes are registered, bounded, and ready for dry-run morning tests. It is a readiness harness, not live agent activation.

## Scope

- Records `agent_runtime_*` rows in `.openclaw/business_ops/ledger.sqlite`.
- Represents Chief, Cassandra, Guardian, Niles, Hermes, and Report Bridge.
- Checks the presence of Agent Lane Registry, Intent Router, Operator Intent Inbox, Operator Action Path, File Event Queue, Local Automation Services, Report Bridge, and the generated read-model mirror posture.
- Runs deterministic smoke tests by routing sample intents only.
- Exports `generated/read_models/agent_runtime_readiness.json` and `generated/read_models/agent_runtime_readiness_OPERATOR.md`.

## Commands

Check readiness:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_agent_runtime_readiness.py --format operator
```

Run the dry-run start sequence:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_agent_start_sequence.py --dry-run --format operator
```

Run deterministic smoke tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_agent_smoke_tests.py --format operator
```

Export read-models:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_agent_runtime_readiness_read_model.py --format operator
```

Query receipts:

```bash
python3 scripts/query_agent_runtime_readiness.py --report summary --format operator
python3 scripts/query_agent_runtime_readiness.py --report components --format operator
python3 scripts/query_agent_runtime_readiness.py --report blockers --format operator
python3 scripts/query_agent_runtime_readiness.py --report smoke-tests --format operator
python3 scripts/query_agent_runtime_readiness.py --report start-sequence --format operator
```

## Agents Represented

- `chief`: system orchestration and safe plan routing.
- `cassandra`: operator communications summaries and briefings.
- `guardian`: safety/security/no-go boundary review.
- `niles`: music/art and Logic-file metadata posture.
- `hermes`: advisory synthesis only.
- `report_bridge`: sanitized report-package posture.

## Start Sequence

The v0 start sequence is dry-run by design:

1. Ledger reachable.
2. Agent Lane Registry present.
3. Intent Router present.
4. Operator Intent Inbox present.
5. Operator Action Path present.
6. File Event Queue present.
7. Read-model mirror health checked.
8. Local Automation Services present.
9. Agent no-authority bounds checked.
10. Smoke-test candidates available.

No long-running agent loops are started.

## Smoke Tests

The smoke tests route sample intents and record receipts:

- Chief: Markdown/status planning.
- Cassandra: changed-summary framing.
- Guardian: safety review.
- Niles: new Logic-file request, metadata-only.
- Hermes: advisory synthesis.
- Report Bridge: package posture.

Passing smoke tests prove deterministic routing and receipts. They do not prove live agent execution, model access, external messaging, or runtime readiness for autonomous work.

## Authority Boundary

All v0 no-authority flags remain false:

- `live_agent_activation_allowed=false`
- `autonomous_loop_allowed=false`
- `telegram_api_allowed=false`
- `gmail_api_allowed=false`
- `model_call_allowed=false`
- `arbitrary_shell_allowed=false`
- `tool_execution_allowed=false`
- `approval_bypass_allowed=false`
- `no_go_raw_access_allowed=false`
- `client_deployment_allowed=false`

Any future live runtime lane must add an explicit gate, approval posture, receipts, rollback/stop behavior, and operator-visible status before activation.
