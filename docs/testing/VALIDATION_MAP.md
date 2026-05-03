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
| `openclaw-gateway.service`, `openclaw-drift-control-scan.timer`, `openclaw-drift-control-scan.service` owner classification | `tests/test_service_owner_classification_static_contract.py` | Verifies frozen-pending owner records, absent repo templates, and no silent installer/launcher claims |
| Drift-control scheduler-owner static classification | `tests/test_drift_control_scheduler_static_contract.py` | Verifies no canonical scheduler owner is selected, cron/timer paths remain frozen pending, and no templates or launch/install claims are added |
| `scripts/install_openclaw_stack.sh` | `tests/test_install_openclaw_stack_safety.py` | Verifies dry-run defaults, explicit apply/enable/start gates, and no broad user-service enablement |
| `scripts/start_all.sh`, `start_chief.sh`, `start_openclaw_brains.sh` | `tests/test_legacy_launch_script_safety.py` | Verifies Slice 4 dry-run/refusal-only defaults, fail-closed flags, and no preserved live launch path |
| Legacy ownership/disposition static contract | `tests/test_legacy_ownership_disposition_static_contract.py` | Verifies every Slice 8 legacy launch/process surface has a definitive static disposition without live service/runtime inspection |
| `scripts/install_hermes_gateway_service.sh`, `systemd/user/hermes-gateway.service.in` | `tests/test_hermes_gateway_installer_safety.py` | Verifies Hermes gateway dry-run/apply/restart gates and no authority expansion beyond the sidecar gateway template |
| `hermes_advisory_packet.py`, `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`, `docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md` | `tests/test_hermes_advisory_packet_contract.py` | Verifies Hermes packet-in/proposal-out advisory contract, withheld surfaces, non-canonical memo shape, and no live runtime/provider/service/private-state dependency |
| `chief_llm.py` model routing and external packet policy | `tests/test_chief_llm_router.py` | Verifies local routing, mocked provider behavior, and external packet guardrails |
| `docs/planning/launch_ladder/*.md`, `docs/planning/launch_ladder/fixtures/mission_control/*.json`, `docs/planning/launch_ladder/knowledge_substrate/*.md`, `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`, `mac_eyes/Launchers/sync_operator_harness_to_mac.sh`, `mac_eyes/Launchers/refresh_operator_harness_ingest.sh`, `launch_ladder_contract_check.py` | `tests/test_launch_ladder_static_contract.py` | Verifies Launch Ladder stages, route compression, compact buttons, Launch Packet minimum fields, Action Authorization / Approval Receipt lifecycle and scope rules, UI State Claim evidence/freshness rules, Product Taste / Operator Experience Eval Spine, golden/malformed taste examples, Mac desktop Mission Control read-only fixture contract and JSON fixture boundaries, first-screen composition zones/fixtures/app-naming boundary/local-ahead-not-synced rule, Mac desktop taste/atmosphere spec, separate sound/haptics quiet feedback addendum, no audio-assets/haptics/notification/sound-settings implementation boundary, SQLite-backed Compiled Knowledge Substrate planning package and synthetic-only no-ingestion/no-external-model-sensitive-data boundaries, profile-to-packet handoff boundaries, parallel bundle requirements, view modes, evidence/freshness fields, generated `MANIFEST.md` upload authority, 23+MANIFEST=24 source-set rule, Source-Set Ladder and adjacent `CHAT_STAY_UP_TO_DATE.md` bridge behavior, Workspace Launch Profile record shape/example fixtures/navigation-only boundaries, current source-set posture, Apple-platform build-order clarification, prototype `.claude` bridge non-authority/retirement notes, non-authority boundaries, Atlas horizon/zoom levels, and active app-planning source-set freshness warnings |

## 6. Global Readiness (Full Suite)

If multiple core boundaries are touched (e.g., refactoring `chief_env` or `cassandra_mode`), run the full suite:

```bash
PYTHONPATH=. pytest tests/
```
