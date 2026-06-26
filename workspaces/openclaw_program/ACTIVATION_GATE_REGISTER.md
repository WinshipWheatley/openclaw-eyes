# Activation Gate Register

Schema: `activation_gate_register_v0`
Generated: `2026-06-26T00:00:00-04:00`

This register is descriptive only. It does not enable features, edit production config, inspect secrets, touch systemd, run canaries, or perform live external actions.

## Policy

- `classification_rule`: `Do not mark a capability enabled or safe to enable unless evidence proves it.`
- `descriptive_only`: `true`
- `features_enabled_by_this_register`: `false`
- `live_env_raw_values_stored`: `false`
- `live_env_reconciliation_enabled`: `false`
- `live_env_reconciliation_read_only`: `true`
- `live_env_secrets_printed_or_stored`: `false`
- `live_env_whitelist_only`: `true`
- `live_external_actions_run`: `false`
- `production_databases_touched`: `false`
- `production_env_files_inspected`: `false`
- `production_flags_changed`: `false`
- `systemctl_invoked`: `false`
- `systemd_inspected_or_modified`: `false`
- `systemd_modified`: `false`
- `systemd_user_unit_files_inspected_read_only`: `false`

## Summary

- Total capabilities registered: `19`
- Verified enabled/live: none recorded
- Activation allowed now: none recorded
- Ready for canary queue: `frontdoor_model_profile`
- Blocked: `legal_sealed_ingestion`, `polish_loop_factory_mode`, `polish_loop_local_builder_bridge`, `runtime_module_activation_gate`
- Intentionally off: `agent_package_preview_contract`, `cassandra_telegram_delivery`, `external_model_openrouter_path`, `gated_email_send_rail`, `lm_consult_spine`, `polish_loop_file_ledger_bridge`, `polish_loop_task_package_v1`
- Conflicting live state: none recorded
- Unknown production state: `active_machinery_classification`, `agent_package_preview_contract`, `cassandra_telegram_delivery`, `cassandra_telegram_dryrun_inbox`, `computer_use_worker_gateway`, `continuity_capsule`, `draft_only_email_adapter`, `external_model_openrouter_path`, `frontdoor_model_profile`, `gated_email_send_rail`, `interpreter_lm`, `legal_sealed_ingestion`, `lm_consult_spine`, `niles_album_evidence_intake_boundary`, `polish_loop_factory_mode`, `polish_loop_local_builder_bridge`, `runtime_module_activation_gate`

| Capability | Stage | Live production state | Current state | Activation allowed now | Next required step |
| --- | --- | --- | --- | --- | --- |
| Active Machinery classification orchestrator (`active_machinery_classification`) | `dry_run` | `not_applicable` | classification orchestrator exists with dry-run/mock classification and no autonomous worker dispatch | no | record a synthetic-to-canary plan before any Gemini worker dispatch |
| Agent package preview contract (`agent_package_preview_contract`) | `intentionally_off` | `not_applicable` | metadata-only preview contract exists; all dispatch/external authority toggles are false | no | use as review artifact only; do not grant package send authority |
| Cassandra / Telegram delivery (`cassandra_telegram_delivery`) | `intentionally_off` | `not_applicable` | code default dry-run/off; production toggle and authorized user were not inspected | no | keep disabled unless Opus defines an operator-watched internal-only canary |
| Cassandra Telegram dry-run inbox (`cassandra_telegram_dryrun_inbox`) | `dry_run` | `not_applicable` | dry-run inbox is local-only and denies Telegram live connection, credentials, send, email, browser, and ledger posting | no | keep as a synthetic proof source; do not connect to Telegram |
| Computer Use Worker Gateway (`computer_use_worker_gateway`) | `proposed` | `not_applicable` | proposed only; no production flag or built gateway was verified in this branch | no | write a design/proposal before implementation; do not grant desktop/browser authority |
| Continuity Capsule (`continuity_capsule`) | `unknown` | `not_applicable` | code default off; activation audit reported maestro-listener continuity flag ON, but this generator did not inspect systemd or production env | no | Opus should verify current runtime env without exposing secrets and record whether it remains approved live |
| Draft-only email adapter (`draft_only_email_adapter`) | `synthetic` | `not_applicable` | adapter exists as deterministic local artifact generator; live draft and send authority are false; production wiring unknown | no | wire only a synthetic/operator-review draft lane with receipts; do not create live Gmail/Mail drafts |
| External model / OpenRouter path (`external_model_openrouter_path`) | `intentionally_off` | `not_applicable` | code requires explicit cloud flag, configured model/key, and safety eligibility; secret values and production env were not inspected | no | keep unwired for live use until cloud policy, privacy routing, and audit/canary evidence are recorded |
| Front-door model profile (`frontdoor_model_profile`) | `canary` | `not_applicable` | code default off; production state unknown; prior audit says canary remained blocked by load/integrated-state review | no | run a contained front-door canary only after load is acceptable and Opus approves the envelope |
| Gated email send rail (`gated_email_send_rail`) | `intentionally_off` | `not_applicable` | send rail exists as a deterministic fail-closed receipt surface; live provider/network authority is false | no | do not activate; use draft-only review rail instead |
| Interpreter-LM (`interpreter_lm`) | `disabled` | `not_applicable` | code default off; production state unknown because production env files/services were not inspected | no | integrated-state audit and bounded canary plan before any live activation |
| Legal Sealed ingestion (`legal_sealed_ingestion`) | `blocked` | `not_applicable` | local legal policies and console bridge are synthetic/local-only; real sealed/private ingestion remains blocked | no | complete legal authorization and sealed-ingestion design before any implementation or test with real material |
| Advisory LM consult spine (`lm_consult_spine`) | `intentionally_off` | `not_applicable` | advisory-only consult spine is built; provider credentials/config and production env were not inspected | no | keep advisory-only and record any provider probe evidence separately without exposing credentials |
| Niles album evidence intake boundary (`niles_album_evidence_intake_boundary`) | `synthetic` | `not_applicable` | metadata-only boundary exists; raw audio, DAW contents, broad drive scans, automation, and mutation are blocked | no | if needed, run only synthetic metadata tests or operator-supplied metadata review |
| Polish Loop factory mode (`polish_loop_factory_mode`) | `blocked` | `not_applicable` | factory remains NOT_READY; no live loop was run or enabled | no | repair blockers #2 and #3, re-audit all 10 switch criteria, then separately approve activation |
| Polish Loop file-loop ledger reconciliation bridge (`polish_loop_file_ledger_bridge`) | `intentionally_off` | `not_applicable` | bridge is built as a default-off candidate to reconcile legacy file-loop results with the SQLite Control Plane ledger | no | Opus review of task-003 implementation, then a separate synthetic/canary authorization task if the factory remains otherwise eligible |
| Polish Loop local builder bridge (`polish_loop_local_builder_bridge`) | `blocked` | `not_applicable` | candidate built on isolated polish-loop-closure branch; current base branch does not contain the flag; production not enabled | no | Opus review/integration of closure branch, then blockers #2 and #3 and all 10 switch criteria |
| Polish Loop deterministic task package v1 (`polish_loop_task_package_v1`) | `intentionally_off` | `not_applicable` | deterministic task-package materialization is built as a default-off candidate for Polish Loop blocker #3 | no | Opus review of blocker #3 implementation, then a separate synthetic/canary authorization task if factory switch criteria otherwise pass |
| Runtime / Module Activation Gate v0 (`runtime_module_activation_gate`) | `blocked` | `not_applicable` | v0 gate always blocks runtime/module activation and claims no runtime health | no | satisfy and record all gate prerequisites before runtime/module activation |

## Capabilities

### Active Machinery classification orchestrator (`active_machinery_classification`)

- Flag/config: `dry_run mode; Gemini worker dispatch operator-gated`
- Default state: `dry_run`
- Current state if verifiable: classification orchestrator exists with dry-run/mock classification and no autonomous worker dispatch
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `dry_run`
- Canary status: `synthetic_ready`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: built as synthetic classification; live worker dispatch remains gated
- Enabled by: future operator-approved Gemini verification dispatch
- Disabled by: dry-run mode and operator gate
- Rollback: leave worker dispatch disabled; keep mock classification only
- Next required step: record a synthetic-to-canary plan before any Gemini worker dispatch
- Source files: `active_machinery_classification_orchestrator.py`
- Tests: `tests/test_active_machinery_classification_orchestrator.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`
- Evidence refs: `active_machinery_classification_orchestrator.py`, `tests/test_active_machinery_classification_orchestrator.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Agent package preview contract (`agent_package_preview_contract`)

- Flag/config: `contract toggles: runtime/model/agent/tool/package send authority false`
- Default state: `intentionally disabled`
- Current state if verifiable: metadata-only preview contract exists; all dispatch/external authority toggles are false
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `synthetic_ready; no dispatch canary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: preview is intentionally not an activation or dispatch mechanism
- Enabled by: future explicit operator approval for any dispatch-capable successor
- Disabled by: contract authority flags false
- Rollback: keep metadata-only contract; reject any package preview that becomes dispatch
- Next required step: use as review artifact only; do not grant package send authority
- Source files: `agent_package_preview_contract.py`
- Tests: `tests/test_agent_package_preview_contract.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`
- Evidence refs: `agent_package_preview_contract.py`, `tests/test_agent_package_preview_contract.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Cassandra / Telegram delivery (`cassandra_telegram_delivery`)

- Flag/config: `CASSANDRA_TELEGRAM_DELIVERY_ENABLED`, `/mnt/c/OpenClaw/logs/cassandra_telegram_delivery_enabled.flag`, `TELEGRAM_AUTHORIZED_USER_ID`
- Default state: `dry_run/off`
- Current state if verifiable: code default dry-run/off; production toggle and authorized user were not inspected
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live; dry-run tests only`
- Risk level: `high`
- Owner: `Cassandra lane / Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: live Telegram is an external action surface and remains intentionally off
- Enabled by: explicit operator approval plus documented toggle for authorized internal Telegram only
- Disabled by: default toggle false and dry-run receipt path
- Rollback: unset CASSANDRA_TELEGRAM_DELIVERY_ENABLED and remove the enabled flag file
- Next required step: keep disabled unless Opus defines an operator-watched internal-only canary
- Source files: `cassandra_telegram_delivery.py`
- Tests: `tests/test_cassandra_telegram_delivery.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`
- Evidence refs: `cassandra_telegram_delivery.py:TOGGLE_ENV_VAR`, `cassandra_telegram_delivery.py:TelegramDeliveryReceipt`, `tests/test_cassandra_telegram_delivery.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Cassandra Telegram dry-run inbox (`cassandra_telegram_dryrun_inbox`)

- Flag/config: `local JSON dry-run inbox paths; no live Telegram credential flag`
- Default state: `dry_run`
- Current state if verifiable: dry-run inbox is local-only and denies Telegram live connection, credentials, send, email, browser, and ledger posting
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `dry_run`
- Canary status: `synthetic_only`
- Risk level: `medium`
- Owner: `Cassandra lane / Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: live Telegram delivery remains disabled even though dry-run inbox can process local fixtures
- Enabled by: local synthetic fixture processing only
- Disabled by: authority boundary blocks live Telegram and external actions
- Rollback: delete local dry-run fixture binding; no live Telegram state exists to roll back
- Next required step: keep as a synthetic proof source; do not connect to Telegram
- Source files: `cassandra_telegram_dryrun_inbox.py`
- Tests: `tests/test_cassandra_telegram_dryrun_inbox.py`
- Audits: none recorded
- Evidence refs: `cassandra_telegram_dryrun_inbox.py:AUTHORITY_BOUNDARY`, `tests/test_cassandra_telegram_dryrun_inbox.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Computer Use Worker Gateway (`computer_use_worker_gateway`)

- Flag/config: `unknown`
- Default state: `not_built/proposed`
- Current state if verifiable: proposed only; no production flag or built gateway was verified in this branch
- Production state: `not_applicable_proposed_only`
- Live production state: `not_applicable`
- Gate stage: `proposed`
- Canary status: `not_applicable`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not implemented in this evidence pass; proposed only
- Enabled by: future design, audit, canary, and explicit operator approval
- Disabled by: no implementation or activation flag verified
- Rollback: do not create worker bindings until an approved design names rollback and receipts
- Next required step: write a design/proposal before implementation; do not grant desktop/browser authority
- Source files: none recorded
- Tests: none recorded
- Audits: `user task scope: required proposed capability`
- Evidence refs: `required by activation gate register task`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Continuity Capsule (`continuity_capsule`)

- Flag/config: `OPENCLAW_CONTINUITY_CAPSULE`, `OPENCLAW_PACKET_SOURCE`
- Default state: `off`
- Current state if verifiable: code default off; activation audit reported maestro-listener continuity flag ON, but this generator did not inspect systemd or production env
- Production state: `unknown_not_reverified; audit_reported_maestro_listener_continuity_on`
- Live production state: `not_applicable`
- Gate stage: `unknown`
- Canary status: `audit_reported_running_flag_on; not_reverified_by_this_task`
- Risk level: `low`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: current production state was not reverified here; code default is off
- Enabled by: operator-controlled runtime environment
- Disabled by: OPENCLAW_CONTINUITY_CAPSULE default 0
- Rollback: unset OPENCLAW_CONTINUITY_CAPSULE or set it to 0 and restart only through approved service-management procedure
- Next required step: Opus should verify current runtime env without exposing secrets and record whether it remains approved live
- Source files: `maestro_listener.py`, `maestro_context_packet.py`
- Tests: `tests/test_continuity_stamp.py`, `tests/test_packet_sqlite_flip.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`, `/home/openclaw/workspaces/openclaw_program/OPUS_REENTRY_FINAL_REPORT.md`
- Evidence refs: `maestro_listener.py:_continuity_enabled`, `tests/test_continuity_stamp.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Draft-only email adapter (`draft_only_email_adapter`)

- Flag/config: `no_live_send_flag; draft adapter is deterministic/no-send`, `unknown_live_wiring_flag`
- Default state: `unwired/no-send`
- Current state if verifiable: adapter exists as deterministic local artifact generator; live draft and send authority are false; production wiring unknown
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `synthetic`
- Canary status: `synthetic_ready; no live email canary`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: built local draft artifact path is not live-wired; live email and provider actions remain prohibited
- Enabled by: future explicit draft-only router binding plus operator approval; never send authority
- Disabled by: no router binding and authority_boundary live send/draft fields false
- Rollback: remove the router binding and keep generated local artifacts only
- Next required step: wire only a synthetic/operator-review draft lane with receipts; do not create live Gmail/Mail drafts
- Source files: `gated_email_draft_adapter.py`
- Tests: `tests/test_gated_email_draft_adapter.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`
- Evidence refs: `gated_email_draft_adapter.py:AUTHORITY_BOUNDARY`, `tests/test_gated_email_draft_adapter.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### External model / OpenRouter path (`external_model_openrouter_path`)

- Flag/config: `OPENCLAW_FREEFORM_CLOUD`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENCLAW_EXTERNAL_MODEL`, `OPENCLAW_CASSANDRA_EXTERNAL_MODEL`, `CASSANDRA_EXTERNAL_MODEL`
- Default state: `fail_closed/no_external_call`
- Current state if verifiable: code requires explicit cloud flag, configured model/key, and safety eligibility; secret values and production env were not inspected
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: external model calls can cross privacy boundaries and require explicit policy approval
- Enabled by: explicit operator approval, safe classification, cloud flag, and provider configuration
- Disabled by: no explicit OPENCLAW_FREEFORM_CLOUD enablement in this task; fail-closed if key/model missing
- Rollback: unset OPENCLAW_FREEFORM_CLOUD and OpenRouter model/provider variables; remove provider credentials through approved secret process
- Next required step: keep unwired for live use until cloud policy, privacy routing, and audit/canary evidence are recorded
- Source files: `protected_generate.py`, `chief_llm.py`, `openclaw_lm_consult_spine.py`
- Tests: `tests/test_chief_llm_router.py`
- Audits: `docs/operations/OPENROUTER_KEY_STORAGE.md`, `docs/planning/OPENCLAW_LANE_A_OPENROUTER_SCOUT_BACKLOG.md`
- Evidence refs: `protected_generate.py:OPENCLAW_FREEFORM_CLOUD`, `chief_llm.py:OPENROUTER_API_KEY`, `chief_llm.py:_external_model_configured`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Front-door model profile (`frontdoor_model_profile`)

- Flag/config: `OPENCLAW_FRONTDOOR_MODEL_PROFILE`, `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`, `OPENCLAW_FRONTDOOR_NUM_PREDICT`, `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`, `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`
- Default state: `off`
- Current state if verifiable: code default off; production state unknown; prior audit says canary remained blocked by load/integrated-state review
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `canary`
- Canary status: `queued_for_contained_canary; not_run_due_to_load_and_audit_gap`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: built but canary evidence is incomplete; not production-safe to enable from this register
- Enabled by: OPENCLAW_FRONTDOOR_MODEL_PROFILE plus operator-approved canary envelope
- Disabled by: OPENCLAW_FRONTDOOR_MODEL_PROFILE default 0
- Rollback: unset OPENCLAW_FRONTDOOR_MODEL_PROFILE; protected_generate falls back to deterministic/non-profile path
- Next required step: run a contained front-door canary only after load is acceptable and Opus approves the envelope
- Source files: `protected_generate.py`, `chief_llm.py`
- Tests: `tests/test_frontdoor_model_profile.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/FRONT-DOOR-LOCAL-MODEL-PROFILE-SPEC.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_FRONTDOOR_MODEL_INTEGRATION_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md`
- Evidence refs: `protected_generate.py:_frontdoor_model_profile_flag_enabled`, `chief_llm.py:select_frontdoor_model`, `tests/test_frontdoor_model_profile.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Gated email send rail (`gated_email_send_rail`)

- Flag/config: `approval receipt inputs only; no live provider flag`
- Default state: `blocked/no-send`
- Current state if verifiable: send rail exists as a deterministic fail-closed receipt surface; live provider/network authority is false
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run; live send prohibited`
- Risk level: `critical`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: email sending is an external action and remains outside this task
- Enabled by: not enabled by this register; any future send path requires separate approval and legal/comms policy
- Disabled by: AUTHORITY_BOUNDARY live send/provider fields false
- Rollback: keep provider send calls absent; remove any caller binding that attempts live send
- Next required step: do not activate; use draft-only review rail instead
- Source files: `gated_email_send_adapter.py`
- Tests: `tests/test_gated_email_send_adapter.py`
- Audits: none recorded
- Evidence refs: `gated_email_send_adapter.py:AUTHORITY_BOUNDARY`, `tests/test_gated_email_send_adapter.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Interpreter-LM (`interpreter_lm`)

- Flag/config: `OPENCLAW_INTERPRETER_LM`
- Default state: `off`
- Current state if verifiable: code default off; production state unknown because production env files/services were not inspected
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `disabled`
- Canary status: `not_run`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: built flag remains default-off; no live activation evidence is recorded in this register
- Enabled by: explicit operator approval after audit and canary evidence
- Disabled by: OPENCLAW_INTERPRETER_LM default 0
- Rollback: unset OPENCLAW_INTERPRETER_LM or set it to 0; deterministic fallback remains available
- Next required step: integrated-state audit and bounded canary plan before any live activation
- Source files: `interpreter_lm.py`, `maestro_listener.py`
- Tests: `tests/test_continuity_stamp.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_REENTRY_FINAL_REPORT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md`
- Evidence refs: `interpreter_lm.py:_interpreter_enabled`, `tests/test_continuity_stamp.py:interpreter flag test coverage`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Legal Sealed ingestion (`legal_sealed_ingestion`)

- Flag/config: `OPENCLAW_LEGAL_PRIVATE_ROOT`, `legal-console synthetic_only bridge`
- Default state: `blocked/no_real_matter_ingestion`
- Current state if verifiable: local legal policies and console bridge are synthetic/local-only; real sealed/private ingestion remains blocked
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `blocked; no real matter canary`
- Risk level: `critical`
- Owner: `Legal lane / Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: legal evidence and sealed/private matter ingestion are explicitly not ready
- Enabled by: future explicit legal authorization, sealed-data protocol, audit, and operator approval
- Disabled by: synthetic-only bridge and path guard constraints
- Rollback: keep legal private roots inaccessible; revert any bridge that can touch real sealed material
- Next required step: complete legal authorization and sealed-ingestion design before any implementation or test with real material
- Source files: `legal/local_capability_policy.py`, `legal/path_guard.py`, `apps/legal-console-spike/src-tauri/src/run.rs`
- Tests: `tests/test_alternative_methods.py`, `tests/test_support_packet.py`, `tests/test_legal_mock_discovery_demo.py`, `tests/test_legal_synthetic_stress_pack.py`
- Audits: `docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_REAL_MATTER_LOCAL_ONLY_VALIDATION_PROTOCOL.md`, `docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_REAL_MATTER_MAC_BRIDGE_VALIDATION_PROTOCOL.md`, `docs/planning/openclaw_legal/law_program/LEGAL_VAULT_PATH_CONTRACT.md`
- Evidence refs: `legal/local_capability_policy.py`, `legal/path_guard.py`, `apps/legal-console-spike/src-tauri/src/run.rs:synthetic_only`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Advisory LM consult spine (`lm_consult_spine`)

- Flag/config: `OPENCLAW_ENABLE_LM_CONSULTS`, `OPENCLAW_LM_PROVIDER`, `OPENCLAW_GEMINI_MODEL`, `OPENCLAW_GEMINI_FORM_MODEL`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`
- Default state: `provider_config_required/off`
- Current state if verifiable: advisory-only consult spine is built; provider credentials/config and production env were not inspected
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_by_this_task`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: external/provider-backed consults require explicit approval and credential-safe verification
- Enabled by: explicit operator approval and approved provider configuration; advisory-only
- Disabled by: provider config required and no runtime mutation authority
- Rollback: unset OPENCLAW_ENABLE_LM_CONSULTS and provider/model variables
- Next required step: keep advisory-only and record any provider probe evidence separately without exposing credentials
- Source files: `openclaw_lm_consult_spine.py`
- Tests: none recorded
- Audits: none recorded
- Evidence refs: `openclaw_lm_consult_spine.py:GENERIC_ENABLE_ENV`, `openclaw_lm_consult_spine.py:AUTHORITY_FALSE`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Niles album evidence intake boundary (`niles_album_evidence_intake_boundary`)

- Flag/config: `metadata-only intake contract; no live private-root flag`
- Default state: `synthetic/metadata-only`
- Current state if verifiable: metadata-only boundary exists; raw audio, DAW contents, broad drive scans, automation, and mutation are blocked
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `synthetic`
- Canary status: `synthetic_ready; no real album evidence ingest`
- Risk level: `medium`
- Owner: `Niles lane / Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: real album/private evidence ingestion is not activated; only metadata boundary exists
- Enabled by: operator-supplied metadata only under approved intake boundary
- Disabled by: blocked raw/private evidence types and no broad scan authority
- Rollback: reject metadata packets and keep raw/private evidence inaccessible
- Next required step: if needed, run only synthetic metadata tests or operator-supplied metadata review
- Source files: `niles_album_evidence_intake_boundary.py`
- Tests: `tests/test_niles_album_evidence_intake_boundary.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md`
- Evidence refs: `niles_album_evidence_intake_boundary.py:NO_AUTHORITY_FLAGS`, `tests/test_niles_album_evidence_intake_boundary.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Polish Loop factory mode (`polish_loop_factory_mode`)

- Flag/config: `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`, `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`, `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`, `OPENCLAW_POLISH_MAX_PARALLEL_LANES`, `OPENCLAW_POLISH_LANE_WORKER_CMD`, `OPENCLAW_TEST_MODE`, `OPENCLAW_SEND_HOLD`
- Default state: `not_ready/off`
- Current state if verifiable: factory remains NOT_READY; no live loop was run or enabled
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `blocked; no live loop`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: Blocker #1 candidate is not enough; factory mode remains NOT_READY
- Enabled by: only after blockers #2 and #3 and all 10 switch criteria pass re-audit
- Disabled by: audit NOT_READY verdict and live-loop prohibition
- Rollback: do not start orchestrator loop; keep production queues/ledgers untouched
- Next required step: repair blockers #2 and #3, re-audit all 10 switch criteria, then separately approve activation
- Source files: `polish_loop/orchestrator.py`, `polish_loop/lane_launcher.py`, `polish_loop/control_plane.py`, `builder_watcher.sh`
- Tests: `tests/test_polish_loop_self_scaling.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md`
- Evidence refs: `/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md:10-point switch criteria`, `polish_loop/orchestrator.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Polish Loop file-loop ledger reconciliation bridge (`polish_loop_file_ledger_bridge`)

- Flag/config: `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`
- Default state: `default-off`
- Current state if verifiable: bridge is built as a default-off candidate to reconcile legacy file-loop results with the SQLite Control Plane ledger
- Production state: `not_enabled_by_this_task; production activation prohibited`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `synthetic_only; canary required before runtime activation`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: changes runtime reconciliation behavior and Polish Loop remains NOT_READY; canary and Opus/operator approval are required
- Enabled by: explicit OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE only after Opus review, synthetic tests, canary, rollback proof, and operator-approved runtime scope
- Disabled by: default-off flag; production live loop remains prohibited
- Rollback: unset OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE or set it to 0; revert the bridge branch if synthetic receipts regress
- Next required step: Opus review of task-003 implementation, then a separate synthetic/canary authorization task if the factory remains otherwise eligible
- Source files: `polish_loop/orchestrator.py`, `polish_loop/control_plane.py`
- Tests: `tests/test_polish_loop_file_ledger_reconciliation.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_IMPL_RESULT.md`
- Evidence refs: `polish_loop/orchestrator.py:reconcile_file_loop_result_with_ledger`, `tests/test_polish_loop_file_ledger_reconciliation.py`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Polish Loop local builder bridge (`polish_loop_local_builder_bridge`)

- Flag/config: `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`
- Default state: `candidate default-off; not present in this base branch`
- Current state if verifiable: candidate built on isolated polish-loop-closure branch; current base branch does not contain the flag; production not enabled
- Production state: `not_enabled_by_this_task; production_state_unknown_not_read`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `synthetic_only_on_isolated_branch; no live loop`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: blocker #1 candidate exists but factory remains NOT_READY and this base branch lacks the bridge flag
- Enabled by: explicit OPENCLAW_POLISH_LOOP_LOCAL_BUILDER after Opus integration review, remaining blockers, and switch criteria
- Disabled by: flag absent/off; live loop prohibited
- Rollback: leave the flag unset; revert/disable bridge branch before any live dispatch if receipts regress
- Next required step: Opus review/integration of closure branch, then blockers #2 and #3 and all 10 switch criteria
- Source files: `polish_loop/orchestrator.py`, `polish_loop/worker_runtime.py`, `polish_loop/control_plane.py`
- Tests: `tests/test_polish_loop_closure_bridge.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md`
- Evidence refs: `polish_loop/worker_runtime.py:run_local_builder_worker`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Polish Loop deterministic task package v1 (`polish_loop_task_package_v1`)

- Flag/config: `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`
- Default state: `default-off`
- Current state if verifiable: deterministic task-package materialization is built as a default-off candidate for Polish Loop blocker #3
- Production state: `not_enabled_by_this_task; production activation prohibited`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `synthetic_only; canary required before runtime activation`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: changes builder input materialization and Polish Loop remains NOT_READY; canary and Opus/operator approval are required
- Enabled by: explicit OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1 only after Opus review, synthetic tests, canary, rollback proof, and operator-approved runtime scope
- Disabled by: default-off flag; legacy task.md/directive materialization remains unchanged when unset
- Rollback: unset OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1 or set it to 0; legacy task.md/directive materialization remains available
- Next required step: Opus review of blocker #3 implementation, then a separate synthetic/canary authorization task if factory switch criteria otherwise pass
- Source files: `polish_loop/worker_runtime.py`, `polish_loop/orchestrator.py`
- Tests: `tests/test_polish_loop_task_package_materialization.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_3_AUDIT_RESULT.md`
- Evidence refs: `polish_loop/worker_runtime.py:build_task_package_markdown`, `polish_loop/orchestrator.py:write_phase_c_fix_directive`, `tests/test_polish_loop_task_package_materialization.py`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_3_AUDIT_RESULT.md`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Runtime / Module Activation Gate v0 (`runtime_module_activation_gate`)

- Flag/config: `scripted gate report; no enable flag`
- Default state: `blocked`
- Current state if verifiable: v0 gate always blocks runtime/module activation and claims no runtime health
- Production state: `unknown_not_read_from_env_files_or_services`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `not_applicable; readiness contract only`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: the gate is intentionally a blocker, not an activator
- Enabled by: future explicit prerequisites: approval, rollback, manifest, boundary, receipt, dry-run proof
- Disabled by: blocked_v0_contract
- Rollback: keep using the v0 blocked report until a new audited gate version exists
- Next required step: satisfy and record all gate prerequisites before runtime/module activation
- Source files: `scripts/check_runtime_activation_gate.py`
- Tests: `tests/test_runtime_activation_gate.py`
- Audits: none recorded
- Evidence refs: `scripts/check_runtime_activation_gate.py:build_activation_gate_report`, `tests/test_runtime_activation_gate.py`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

## Flag Detection

- `CASSANDRA_EXTERNAL_MODEL`: `found` in `chief_llm.py`, `tests/test_chief_llm_router.py`
- `CASSANDRA_TELEGRAM_DELIVERY_ENABLED`: `found` in `cassandra_telegram_delivery.py`
- `GEMINI_API_KEY`: `found` in `openclaw_lm_consult_spine.py`
- `GOOGLE_API_KEY`: `found` in `openclaw_lm_consult_spine.py`
- `GOOGLE_GENERATIVE_AI_API_KEY`: `found` in `openclaw_lm_consult_spine.py`
- `OPENCLAW_CASSANDRA_EXTERNAL_MODEL`: `found` in `chief_llm.py`, `tests/test_chief_llm_router.py`
- `OPENCLAW_CONTINUITY_CAPSULE`: `found` in `maestro_context_packet.py`, `maestro_listener.py`
- `OPENCLAW_ENABLE_LM_CONSULTS`: `found` in `openclaw_lm_consult_spine.py`
- `OPENCLAW_EXTERNAL_MODEL`: `found` in `chief_llm.py`, `tests/test_chief_llm_router.py`
- `OPENCLAW_FREEFORM_CLOUD`: `found` in `protected_generate.py`
- `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`: `found` in `chief_llm.py`, `tests/test_frontdoor_model_profile.py`
- `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`: `found` in `chief_llm.py`, `tests/test_frontdoor_model_profile.py`
- `OPENCLAW_FRONTDOOR_MODEL_PROFILE`: `found` in `protected_generate.py`, `tests/test_frontdoor_model_profile.py`
- `OPENCLAW_FRONTDOOR_NUM_PREDICT`: `found` in `protected_generate.py`, `tests/test_frontdoor_model_profile.py`
- `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`: `found` in `protected_generate.py`, `tests/test_frontdoor_model_profile.py`
- `OPENCLAW_GEMINI_FORM_MODEL`: `found` in `openclaw_lm_consult_spine.py`
- `OPENCLAW_GEMINI_MODEL`: `found` in `openclaw_lm_consult_spine.py`
- `OPENCLAW_INTERPRETER_LM`: `found` in `interpreter_lm.py`, `maestro_context_packet.py`, `tests/test_continuity_stamp.py`
- `OPENCLAW_LEGAL_PRIVATE_ROOT`: `not_found_in_scanned_repo_paths` in none recorded
- `OPENCLAW_LM_PROVIDER`: `found` in `openclaw_lm_consult_spine.py`
- `OPENCLAW_PACKET_SOURCE`: `found` in `maestro_context_packet.py`, `tests/test_packet_sqlite_flip.py`
- `OPENCLAW_POLISH_LANE_WORKER_CMD`: `found` in `polish_loop/lane_launcher.py`
- `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`: `found` in `polish_loop/orchestrator.py`
- `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`: `found` in `polish_loop/orchestrator.py`
- `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`: `found` in `polish_loop/orchestrator.py`, `polish_loop/worker_runtime.py`, `tests/test_polish_loop_task_package_materialization.py`
- `OPENCLAW_POLISH_MAX_PARALLEL_LANES`: `found` in `polish_loop/lane_launcher.py`
- `OPENCLAW_SEND_HOLD`: `found` in `polish_loop/lane_launcher.py`, `polish_loop/orchestrator.py`, `tests/test_polish_loop_self_scaling.py`
- `OPENCLAW_TEST_MODE`: `found` in `polish_loop/lane_launcher.py`, `polish_loop/orchestrator.py`, `protected_generate.py`, `tests/test_continuity_stamp.py`, `tests/test_polish_loop_self_scaling.py`
- `OPENROUTER_API_KEY`: `found` in `chief_llm.py`, `tests/test_chief_llm_router.py`
- `OPENROUTER_MODEL`: `found` in `chief_llm.py`, `tests/test_chief_llm_router.py`
- `TELEGRAM_AUTHORIZED_USER_ID`: `found` in `cassandra_telegram_delivery.py`, `maestro_listener.py`

## Live Environment Reconciliation

- Enabled for this generation: `no`
- Whitelisted names: `OPENCLAW_INTERPRETER_LM`, `OPENCLAW_FRONTDOOR_MODEL_PROFILE`, `OPENCLAW_CONTINUITY_CAPSULE`, `OPENCLAW_PACKET_SOURCE`, `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`, `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`, `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`, `OPENCLAW_FREEFORM_CLOUD`, `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`, `OPENCLAW_FRONTDOOR_NUM_PREDICT`, `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`, `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`, `OPENROUTER_MODEL`, `OPENCLAW_EXTERNAL_MODEL`, `OPENCLAW_CASSANDRA_EXTERNAL_MODEL`, `CASSANDRA_EXTERNAL_MODEL`, `OPENROUTER_API_KEY`
- Packet source runtime context: `not_applicable`

Sources inspected:
- none recorded

Sources not inspected:
- `live_env_reconciliation` `all_live_sources`: not requested for this deterministic generation

## Evidence Gaps

- Missing repository evidence files referenced by register: none recorded
- Production env/service state: `not inspected by this task`
- Feature activation performed by this task: `no`
