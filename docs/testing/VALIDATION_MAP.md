# Validation Map

This map provides a deterministic lookup for selecting the correct tests and harnesses based on the files or systems modified. Use this as a mandatory pre-completion checklist.

## 1. Core Logic & Routing

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `chief_llm.py` | `tests/test_chief_llm_router.py` | — |
| `chief_router.py` | `test_cassandra_routing.py` (root) | — |
| `chief_approval_brain.py` | `tests/test_chief_approval_brain.py` | `guardian_schema_harness.py` |
| `agent_task_proposals.py` | `tests/test_agent_task_proposals.py` | — |
| `chief_session_manager.py` | `tests/test_chief_session_manager.py` | — |

## 2. Cassandra Briefings

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `cassandra_briefing_brain.py` | `tests/test_cassandra_briefing_brain.py` | `morning_brief_harness.py` |
| `chief_ops_reporter.py` | `tests/test_cassandra_briefing_context.py` | `morning_brief_harness.py` |
| `cassandra_mode.py` | `tests/test_cassandra_morning_policy.py` | — |

## 3. Outreach & Identity

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `cassandra_identity.py` | `tests/test_cassandra_identity.py` | — |
| `cassandra_outreach.py` | `tests/test_cassandra_outreach.py` | — |
| `inbox_parser.py` | `tests/test_inbox_parser.py` | — |
| `chief_guardian_sender.py` | `tests/test_chief_acceptance_gate.py` | — |

## 4. Subsystem Components

| Area / File | Primary Test(s) | Notes |
| :--- | :--- | :--- |
| `cassandra_voice.py` | `tests/test_cassandra_voice.py` | Requires `chief_env` virtualenv |
| `dashboard_gen.py` | `tests/test_agent_task_proposals.py` | Verifies advisory lane rendering |
| `finance_state.py` | `tests/test_cassandra_payment_verify.py` | — |

## 5. Static Policy / Contract Coverage

| Area / File | Primary Test(s) | Notes |
| :--- | :--- | :--- |
| `docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md`, `.mcp.json` | `tests/test_mcp_progressive_discovery_profiles.py` | Verifies hardened default MCP roots and withheld surfaces |
| Expert evidence chain static contracts | `tests/test_expert_evidence_chain_static_contract.py` | Verifies hash preservation, no-execution metadata, and fail-closed protected markers |
| `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md`, `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`, runtime/model backlog context | `tests/test_runtime_service_model_backlog_static_contract.py` | Verifies service freeze, no silent external fallback, and blocked Claude/provider paths |
| `service_inventory_audit.py`, `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md` | `tests/test_service_inventory_audit.py` | Verifies read-only service inventory parsing without live service inspection or mutation |
| `scripts/install_openclaw_stack.sh` | `tests/test_install_openclaw_stack_safety.py` | Verifies dry-run defaults, explicit apply/enable/start gates, and no broad user-service enablement |
| `scripts/start_all.sh`, `start_chief.sh`, `start_openclaw_brains.sh` | `tests/test_legacy_launch_script_safety.py` | Verifies Slice 4 dry-run/refusal-only defaults, fail-closed flags, and no preserved live launch path |
| `scripts/install_hermes_gateway_service.sh`, `systemd/user/hermes-gateway.service.in` | `tests/test_hermes_gateway_installer_safety.py` | Verifies Hermes gateway dry-run/apply/restart gates and no authority expansion beyond the sidecar gateway template |
| `chief_llm.py` model routing and external packet policy | `tests/test_chief_llm_router.py` | Verifies local routing, mocked provider behavior, and external packet guardrails |

## 6. Global Readiness (Full Suite)

If multiple core boundaries are touched (e.g., refactoring `chief_env` or `cassandra_mode`), run the full suite:

```bash
PYTHONPATH=. pytest tests/
```
