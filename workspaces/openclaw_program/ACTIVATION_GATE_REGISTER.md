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

- Total capabilities registered: `39`
- Verified enabled/live: none recorded
- Activation allowed now: none recorded
- Ready for canary queue: `control_plane_heal_emission`, `frontdoor_model_profile`, `packet_source_sqlite_flip`
- Blocked: `claude_agent_hard_block`, `legal_sealed_ingestion`, `openai_adapter_stub`, `polish_loop_factory_mode`, `polish_loop_local_builder_bridge`, `runtime_module_activation_gate`
- Intentionally off: `action_runtime`, `agent_package_preview_contract`, `brain_dump_parser_cli`, `cassandra_morning_brief_test_mode`, `cassandra_telegram_delivery`, `external_model_openrouter_path`, `external_shadow_lm_config`, `gated_email_send_rail`, `git_task_guard`, `hitl_pipeline`, `interpreter_lm`, `lm_consult_spine`, `model_selection_policy_contract`, `nemotron_provider`, `polish_loop_file_ledger_bridge`, `polish_loop_size_router_v1`, `polish_loop_task_package_v1`, `walk_away_autonomy_mode`
- Conflicting live state: none recorded
- Unknown production state: `action_runtime`, `active_machinery_classification`, `agent_package_preview_contract`, `cassandra_telegram_delivery`, `cassandra_telegram_dryrun_inbox`, `computer_use_worker_gateway`, `continuity_capsule`, `draft_only_email_adapter`, `external_model_openrouter_path`, `gated_email_send_rail`, `legal_sealed_ingestion`, `lm_consult_spine`, `niles_album_evidence_intake_boundary`, `packet_source_sqlite_flip`, `polish_loop_factory_mode`, `polish_loop_local_builder_bridge`, `runtime_module_activation_gate`

| Capability | Stage | Live production state | Current state | Activation allowed now | Next required step |
| --- | --- | --- | --- | --- | --- |
| Action runtime (`action_runtime`) | `intentionally_off` | `not_applicable` | built but intentionally off; dispatch raises while the flag is off | no | prove synthetic executor canary and rollback before any live action runtime activation |
| Active Machinery classification orchestrator (`active_machinery_classification`) | `dry_run` | `not_applicable` | classification orchestrator exists with dry-run/mock classification and no autonomous worker dispatch | no | record a synthetic-to-canary plan before any Gemini worker dispatch |
| Agent package preview contract (`agent_package_preview_contract`) | `intentionally_off` | `not_applicable` | metadata-only preview contract exists; all dispatch/external authority toggles are false | no | use as review artifact only; do not grant package send authority |
| Authority gate + SEND_HOLD sentinel (`authority_gate_send_hold`) | `operator_approved_live` | `not_applicable` | enabled guardrail: default-deny authority gate and SEND_HOLD sentinel keep send surfaces denied; no new activation authority | no | keep SEND_HOLD in place; audit any future send-surface change before activation |
| Brain dump parser CLI (`brain_dump_parser_cli`) | `intentionally_off` | `not_applicable` | manual CLI can dry-run; non-dry-run can call local Ollama and write handoff files, so it remains intentionally off for unattended use | no | wait for deterministic size/risk routing before any queue-ready parser automation |
| Cassandra morning-brief test mode (`cassandra_morning_brief_test_mode`) | `intentionally_off` | `not_applicable` | test-mode branch exists for synthetic morning brief context; production morning path is separate | no | use only in synthetic tests unless Opus queues a separate briefing canary |
| Cassandra / Telegram delivery (`cassandra_telegram_delivery`) | `intentionally_off` | `not_applicable` | code default dry-run/off; production toggle and authorized user were not inspected | no | keep disabled unless Opus defines an operator-watched internal-only canary |
| Cassandra Telegram dry-run inbox (`cassandra_telegram_dryrun_inbox`) | `dry_run` | `not_applicable` | dry-run inbox is local-only and denies Telegram live connection, credentials, send, email, browser, and ledger posting | no | keep as a synthetic proof source; do not connect to Telegram |
| Claude agent hard-block (`claude_agent_hard_block`) | `blocked` | `not_applicable` | agent-side Claude calls are hard-blocked and should remain blocked | no | keep permanently blocked unless Opus writes a new human-only design |
| Computer Use Worker Gateway (`computer_use_worker_gateway`) | `proposed` | `not_applicable` | proposed only; no production flag or built gateway was verified in this branch | no | write a design/proposal before implementation; do not grant desktop/browser authority |
| Continuity Capsule (`continuity_capsule`) | `unknown` | `not_applicable` | code default off; activation audit reported maestro-listener continuity flag ON, but this generator did not inspect systemd or production env | no | Opus should verify current runtime env without exposing secrets and record whether it remains approved live |
| Control-plane heal emission (`control_plane_heal_emission`) | `canary` | `not_applicable` | built detector-to-ledger emission gate remains off pending supervised canary | no | queue a synthetic/supervised canary with temp ledger proof before activation |
| Draft-only email adapter (`draft_only_email_adapter`) | `synthetic` | `not_applicable` | adapter exists as deterministic local artifact generator; live draft and send authority are false; production wiring unknown | no | wire only a synthetic/operator-review draft lane with receipts; do not create live Gmail/Mail drafts |
| External model / OpenRouter path (`external_model_openrouter_path`) | `intentionally_off` | `not_applicable` | code requires explicit cloud flag, configured model/key, and safety eligibility; secret values and production env were not inspected | no | keep unwired for live use until cloud policy, privacy routing, and audit/canary evidence are recorded |
| External-model packet safety policy (`external_model_packet_policy`) | `operator_approved_live` | `not_applicable` | enabled guardrail: cloud eligibility policy fails closed and does not authorize external calls by itself | no | keep active and require policy/canary proof before any external egress activation |
| External shadow LM config (`external_shadow_lm_config`) | `intentionally_off` | `not_applicable` | shadow-only config records redacted credential presence but grants no provider call authority | no | keep shadow-only; any external call path requires high-risk provider activation approval |
| Front-door model profile (`frontdoor_model_profile`) | `canary` | `not_applicable` | code default off; activation sprint canary failed 3/3 by timeout; task-014 found a qwen3:8b contained recanary recipe but production remains off | no | Opus integrates task-019, then runs contained qwen3:8b recanary with OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST=qwen3:8b-q4_K_M, OPENCLAW_FRONTDOOR_NUM_CTX=1024, OPENCLAW_FRONTDOOR_NUM_GPU=999, and OPENCLAW_FRONTDOOR_KEEP_ALIVE set only inside the canary envelope |
| Gated email send rail (`gated_email_send_rail`) | `intentionally_off` | `not_applicable` | send rail exists as a deterministic fail-closed receipt surface; live provider/network authority is false | no | do not activate; use draft-only review rail instead |
| Polish Loop git task guard (`git_task_guard`) | `intentionally_off` | `not_applicable` | catalogued from audit as repo-mutation guard; current base may not contain the script | no | reconcile source presence and audit branch-mutation behavior before any use |
| Human-in-the-loop pending action pipeline (`hitl_pipeline`) | `intentionally_off` | `not_applicable` | built but intentionally off; pending action mutation is a high-risk action surface | no | define a synthetic-only pending-action canary before any live enablement |
| Interpreter-LM (`interpreter_lm`) | `intentionally_off` | `not_applicable` | code default off; activation sprint keeps Interpreter-LM queued for repair because processor wiring is blocked and front-door model-fit canary must pass first | no | unblock task-013 wiring repair, review task-014 model-fit recipe, then run contained Interpreter-LM/front-door canaries before any live activation |
| Legal Sealed ingestion (`legal_sealed_ingestion`) | `blocked` | `not_applicable` | local legal policies and console bridge are synthetic/local-only; real sealed/private ingestion remains blocked | no | complete legal authorization and sealed-ingestion design before any implementation or test with real material |
| LLM diagnostics logging (`llm_diagnostics_logging`) | `operator_approved_live` | `not_applicable` | already-on internal observability; no external action or activation authority | no | keep as internal read-only observability; do not expose secrets in logs |
| Advisory LM consult spine (`lm_consult_spine`) | `intentionally_off` | `not_applicable` | advisory-only consult spine is built; provider credentials/config and production env were not inspected | no | keep advisory-only and record any provider probe evidence separately without exposing credentials |
| Maestro brain live (`maestro_brain_live`) | `operator_approved_live` | `not_applicable` | already-on runtime lane per Opus decision; disabled under TEST_MODE and does not grant new activation authority | no | keep watching model-fit and timeout behavior; do not change this flag in this task |
| Model-selection policy contract (`model_selection_policy_contract`) | `intentionally_off` | `not_applicable` | metadata-only contract exists with no runtime/model/provider authority | no | keep as metadata; future runtime policy wiring needs a separate default-off task |
| Nemotron provider (`nemotron_provider`) | `intentionally_off` | `not_applicable` | external provider path exists but is intentionally off for live use without policy-safe caller and credentials | no | keep off until external egress policy and canary evidence are recorded |
| Niles album evidence intake boundary (`niles_album_evidence_intake_boundary`) | `synthetic` | `not_applicable` | metadata-only boundary exists; raw audio, DAW contents, broad drive scans, automation, and mutation are blocked | no | if needed, run only synthetic metadata tests or operator-supplied metadata review |
| Ollama model defaults (`ollama_model_defaults`) | `operator_approved_live` | `not_applicable` | already-on local model default lane; model-fit repair remains needed for strong/deep references | no | repair strong/deep lane model-fit references before expanding model routing |
| OpenAI adapter stub (`openai_adapter_stub`) | `blocked` | `not_applicable` | adapter exists only as a hard unavailable stub; no live OpenAI provider path is enabled | no | DEPRECATED_OR_REMOVE_LATER unless Opus queues a credential-safe OpenAI design |
| Packet-source SQLite flip (`packet_source_sqlite_flip`) | `canary` | `not_applicable` | standalone activation record for packet-source sqlite/hybrid flip; related continuity context is preserved separately | no | run a supervised hybrid packet content-diff canary before production flip |
| Polish Loop factory mode (`polish_loop_factory_mode`) | `blocked` | `not_applicable` | factory remains NOT_READY; no live loop was run or enabled | no | repair blockers #2 and #3, re-audit all 10 switch criteria, then separately approve activation |
| Polish Loop file-loop ledger reconciliation bridge (`polish_loop_file_ledger_bridge`) | `intentionally_off` | `not_applicable` | bridge is built as a default-off candidate to reconcile legacy file-loop results with the SQLite Control Plane ledger | no | Opus review of task-003 implementation, then a separate synthetic/canary authorization task if the factory remains otherwise eligible |
| Polish Loop local builder bridge (`polish_loop_local_builder_bridge`) | `blocked` | `not_applicable` | candidate built on isolated polish-loop-closure branch; current base branch does not contain the flag; production not enabled | no | Opus review/integration of closure branch, then blockers #2 and #3 and all 10 switch criteria |
| Polish Loop size/type/risk router v1 (`polish_loop_size_router_v1`) | `intentionally_off` | `not_applicable` | planned default-off size/type/risk router record from task-012; catalog-only here and no runtime wiring in this branch | no | Opus review/integration of task-012, then separate synthetic/canary authorization if Polish Loop switch criteria otherwise pass |
| Polish Loop deterministic task package v1 (`polish_loop_task_package_v1`) | `intentionally_off` | `not_applicable` | deterministic task-package materialization is built as a default-off candidate for Polish Loop blocker #3 | no | Opus review of blocker #3 implementation, then a separate synthetic/canary authorization task if factory switch criteria otherwise pass |
| protected_generate Ollama timeouts (`protected_generate_ollama_timeouts`) | `operator_approved_live` | `not_applicable` | already-on internal timeout knobs with safe defaults; they tune bounded local generation behavior only | no | keep defaults; record any future timeout tuning receipt |
| Runtime / Module Activation Gate v0 (`runtime_module_activation_gate`) | `blocked` | `not_applicable` | v0 gate always blocks runtime/module activation and claims no runtime health | no | satisfy and record all gate prerequisites before runtime/module activation |
| Walk-away autonomy mode (`walk_away_autonomy_mode`) | `intentionally_off` | `not_applicable` | built but intentionally off by default; enabling writes an autonomy mode state file | no | do not enable from the register; require an operator-approved autonomy receipt |

## Capabilities

### Action runtime (`action_runtime`)

- Flag/config: `OPENCLAW_ACTION_RUNTIME`
- Default state: `off`
- Current state if verifiable: built but intentionally off; dispatch raises while the flag is off
- Production state: `not_enabled_by_this_register; production action runtime remains off or unknown`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: high-risk action dispatch must remain off without canary and operator approval
- Enabled by: explicit operator approval immediately before a contained action-runtime canary
- Disabled by: OPENCLAW_ACTION_RUNTIME default 0
- Rollback: unset OPENCLAW_ACTION_RUNTIME or set it to 0; remove any caller binding added by a canary
- Next required step: prove synthetic executor canary and rollback before any live action runtime activation
- Source files: `action_runtime.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `action_runtime.py:_action_runtime_enabled`, `action_runtime.py:dispatch_action`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

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

### Authority gate + SEND_HOLD sentinel (`authority_gate_send_hold`)

- Flag/config: `authority_gate.decide`, `SEND_HOLD.md`
- Default state: `enabled_guardrail_default_deny`
- Current state if verifiable: enabled guardrail: default-deny authority gate and SEND_HOLD sentinel keep send surfaces denied; no new activation authority
- Production state: `enabled_verified_by_opus_decision_and_code_guardrail`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `enabled_guardrail_no_new_canary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off; active guardrail only and grants no send authority
- Enabled by: existing default-deny authority gate and SEND_HOLD sentinel
- Disabled by: removing SEND_HOLD or bypassing authority_gate would be a separate prohibited activation change
- Rollback: restore SEND_HOLD sentinel and route send surfaces through authority_gate default-deny decisions
- Next required step: keep SEND_HOLD in place; audit any future send-surface change before activation
- Source files: `authority_gate.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `authority_gate.py:decide`, `authority_gate.py:DEFAULT_SEND_HOLD_PATH`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Brain dump parser CLI (`brain_dump_parser_cli`)

- Flag/config: `brain_dump_parser.py --dry-run`
- Default state: `manual_cli/dry_run_available`
- Current state if verifiable: manual CLI can dry-run; non-dry-run can call local Ollama and write handoff files, so it remains intentionally off for unattended use
- Production state: `not_invoked_by_this_register`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `manual_dry_run_only`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: non-dry-run parser can call a local model and write handoff files; unattended activation is not approved
- Enabled by: manual operator invocation or future bounded parser task with synthetic fixtures
- Disabled by: not wired to unattended queue ingestion by this register
- Rollback: use --dry-run or do not invoke; remove any unattended caller binding
- Next required step: wait for deterministic size/risk routing before any queue-ready parser automation
- Source files: `brain_dump_parser.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `brain_dump_parser.py:--dry-run`, `brain_dump_parser.py:ollama invocation`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Cassandra morning-brief test mode (`cassandra_morning_brief_test_mode`)

- Flag/config: `CASSANDRA_MORNING_BRIEF_TEST_MODE`, `OPENCLAW_CASSANDRA_MORNING_BRIEF_TIMEOUT_SECONDS`, `OPENCLAW_CASSANDRA_MORNING_TEST_TIMEOUT_SECONDS`, `OPENCLAW_CASSANDRA_MORNING_BRIEF_ATTEMPTS`
- Default state: `test_mode_off`
- Current state if verifiable: test-mode branch exists for synthetic morning brief context; production morning path is separate
- Production state: `not_enabled_by_this_register; live briefing not touched`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `synthetic_test_mode_only`
- Risk level: `low`
- Owner: `Cassandra lane / Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: test mode should not be treated as production briefing activation
- Enabled by: test-only invocation in focused tests, not production services
- Disabled by: CASSANDRA_MORNING_BRIEF_TEST_MODE unset by default
- Rollback: unset CASSANDRA_MORNING_BRIEF_TEST_MODE and keep production briefing path unchanged
- Next required step: use only in synthetic tests unless Opus queues a separate briefing canary
- Source files: `cassandra_briefing_brain.py`, `chief_llm.py`
- Tests: `tests/test_cassandra_briefing_context.py`, `tests/test_chief_llm_router.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `cassandra_briefing_brain.py:_MORNING_TEST_MODE_ENV`, `chief_llm.py:_CASSANDRA_MORNING_TEST_TIMEOUT`
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

### Claude agent hard-block (`claude_agent_hard_block`)

- Flag/config: `chief_llm.claude_call`, `chief_llm.claude_json`
- Default state: `blocked_by_policy`
- Current state if verifiable: agent-side Claude calls are hard-blocked and should remain blocked
- Production state: `blocked_verified_by_code_policy`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `not_applicable_permanent_block`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: Claude CLI agent calls are intentionally unavailable to agents
- Enabled by: not enabled; human-only Claude CLI policy
- Disabled by: hard-coded policy block
- Rollback: restore the hard block if any future branch attempts to call Claude CLI from agents
- Next required step: keep permanently blocked unless Opus writes a new human-only design
- Source files: `chief_llm.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `chief_llm.py:claude_call`, `chief_llm.py:claude_json`
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

### Control-plane heal emission (`control_plane_heal_emission`)

- Flag/config: `OPENCLAW_CONTROL_PLANE_EMIT`
- Default state: `off`
- Current state if verifiable: built detector-to-ledger emission gate remains off pending supervised canary
- Production state: `not_enabled_by_this_register; production ledger not touched`
- Live production state: `not_applicable`
- Gate stage: `canary`
- Canary status: `queued_for_supervised_canary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: writes to control-plane ledger and needs canary evidence before live emission
- Enabled by: supervised canary after Opus approval, with rollback to dormant detector mode
- Disabled by: OPENCLAW_CONTROL_PLANE_EMIT default off
- Rollback: unset OPENCLAW_CONTROL_PLANE_EMIT; keep detector-only mode and do not admit live heal tasks
- Next required step: queue a synthetic/supervised canary with temp ledger proof before activation
- Source files: `polish_loop/pc4_heal_emitter.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `polish_loop/pc4_heal_emitter.py:_control_plane_emit_enabled`, `polish_loop/pc4_heal_emitter.py:emit_heal_task`
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

### External-model packet safety policy (`external_model_packet_policy`)

- Flag/config: `chief_llm.external_model_packet_policy`
- Default state: `enabled_guardrail_fail_closed`
- Current state if verifiable: enabled guardrail: cloud eligibility policy fails closed and does not authorize external calls by itself
- Production state: `enabled_verified_by_opus_decision_and_code_guardrail`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `enabled_guardrail_no_new_canary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off; active safety policy only and grants no external egress authority
- Enabled by: existing fail-closed packet policy
- Disabled by: external model paths remain disabled unless separate provider/egress gates pass
- Rollback: keep cloud eligibility policy fail-closed; revert any policy relaxation before provider canary
- Next required step: keep active and require policy/canary proof before any external egress activation
- Source files: `chief_llm.py`
- Tests: `tests/test_chief_llm_router.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `chief_llm.py:external_model_packet_policy`, `chief_llm.py:external_model_allowed`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### External shadow LM config (`external_shadow_lm_config`)

- Flag/config: `OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL`, `OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL`, `OPENCLAW_EXTERNAL_LM2_SHADOW_CREDENTIAL`
- Default state: `shadow_only/no_production_authority`
- Current state if verifiable: shadow-only config records redacted credential presence but grants no provider call authority
- Production state: `not_enabled_by_this_register; credential presence not inspected`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `shadow_only_no_live_canary`
- Risk level: `low`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: configuration is intentionally non-production and external egress remains off
- Enabled by: shadow-only provider policy records; no live provider calls
- Disabled by: AUTHORITY_BOUNDARY production/provider/network authority false
- Rollback: remove shadow credential references and keep production_allowed false
- Next required step: keep shadow-only; any external call path requires high-risk provider activation approval
- Source files: `external_shadow_provider_config.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `external_shadow_provider_config.py:AUTHORITY_BOUNDARY`, `external_shadow_provider_config.py:ExternalShadowProviderConfigRecord`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Front-door model profile (`frontdoor_model_profile`)

- Flag/config: `OPENCLAW_FRONTDOOR_MODEL_PROFILE`, `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`, `OPENCLAW_FRONTDOOR_NUM_PREDICT`, `OPENCLAW_FRONTDOOR_NUM_CTX`, `OPENCLAW_FRONTDOOR_NUM_GPU`, `OPENCLAW_FRONTDOOR_KEEP_ALIVE`, `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`, `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`
- Default state: `off`
- Current state if verifiable: code default off; activation sprint canary failed 3/3 by timeout; task-014 found a qwen3:8b contained recanary recipe but production remains off
- Production state: `not_enabled_by_this_task; production activation prohibited`
- Live production state: `not_applicable`
- Gate stage: `canary`
- Canary status: `queued_for_recanary; task-019 config remains default-off until Opus contained recanary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: QUEUED_FOR_CANARY: prior activation-sprint ladder canary failed 3/3 by timeout, but task-014 + Opus re-probe found a working qwen3:8b recanary recipe; a passing contained recanary is still required before any enablement
- Enabled by: OPENCLAW_FRONTDOOR_MODEL_PROFILE plus operator-approved canary envelope after repair/recanary evidence
- Disabled by: OPENCLAW_FRONTDOOR_MODEL_PROFILE default 0
- Rollback: unset OPENCLAW_FRONTDOOR_MODEL_PROFILE; protected_generate falls back to deterministic/non-profile path
- Next required step: Opus integrates task-019, then runs contained qwen3:8b recanary with OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST=qwen3:8b-q4_K_M, OPENCLAW_FRONTDOOR_NUM_CTX=1024, OPENCLAW_FRONTDOOR_NUM_GPU=999, and OPENCLAW_FRONTDOOR_KEEP_ALIVE set only inside the canary envelope
- Source files: `protected_generate.py`, `chief_llm.py`
- Tests: `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/FRONT-DOOR-LOCAL-MODEL-PROFILE-SPEC.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_FRONTDOOR_MODEL_INTEGRATION_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/04_frontdoor_canary_decision.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/frontdoor_ladder_canary_RESULT.json`, `/home/openclaw/workspaces/openclaw_program/CODEX_LOCAL_THROUGHPUT_MODELFIT_AUDIT_RESULT.md`
- Evidence refs: `protected_generate.py:_frontdoor_model_profile_flag_enabled`, `protected_generate.py:_frontdoor_ollama_options`, `protected_generate.py:_frontdoor_keep_alive`, `chief_llm.py:select_frontdoor_model`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/frontdoor_ladder_canary_RESULT.json`, `/home/openclaw/workspaces/openclaw_program/CODEX_LOCAL_THROUGHPUT_MODELFIT_AUDIT_RESULT.md`
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

### Polish Loop git task guard (`git_task_guard`)

- Flag/config: `polish_loop/git_task_guard.sh`
- Default state: `inert_unless_invoked`
- Current state if verifiable: catalogued from audit as repo-mutation guard; current base may not contain the script
- Production state: `not_invoked_by_this_register; live loop remains prohibited`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: repo mutation guard can create commits/branches if invoked and is not authorized here
- Enabled by: future approved Polish Loop task path only after branch mutation safeguards are audited
- Disabled by: not wired/invoked by this register; live loop prohibited
- Rollback: remove caller wiring and keep branch mutation guarded by human review
- Next required step: reconcile source presence and audit branch-mutation behavior before any use
- Source files: `polish_loop/git_task_guard.sh`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `polish_loop/git_task_guard.sh:audit reference`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Human-in-the-loop pending action pipeline (`hitl_pipeline`)

- Flag/config: `HITL_ENABLED`, `HITL_FLAG_PATH`
- Default state: `off`
- Current state if verifiable: built but intentionally off; pending action mutation is a high-risk action surface
- Production state: `not_enabled_by_this_register; live state requires redacted operator verification`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: external/action approval pipeline is high risk and lacks canary evidence
- Enabled by: explicit operator approval plus canary/rollback receipt for pending-action writes
- Disabled by: HITL_ENABLED default off and no approved flag-file activation
- Rollback: unset HITL_ENABLED and remove any HITL flag file created by an approved canary
- Next required step: define a synthetic-only pending-action canary before any live enablement
- Source files: `hitl_pending_store.py`, `hitl_pending_action.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `hitl_pending_store.py:is_hitl_enabled`, `hitl_pending_action.py:_hitl_enabled`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Interpreter-LM (`interpreter_lm`)

- Flag/config: `OPENCLAW_INTERPRETER_LM`
- Default state: `off`
- Current state if verifiable: code default off; activation sprint keeps Interpreter-LM queued for repair because processor wiring is blocked and front-door model-fit canary must pass first
- Production state: `not_enabled_by_this_task; production activation prohibited`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `queued_for_repair; task-013 blocked; front-door model-fit recanary required first`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: QUEUED_FOR_REPAIR: processor wiring is blocked and model-fit/canary evidence is incomplete
- Enabled by: explicit operator approval after processor wiring repair, front-door canary, audit, and rollback evidence
- Disabled by: OPENCLAW_INTERPRETER_LM default 0
- Rollback: unset OPENCLAW_INTERPRETER_LM or set it to 0; deterministic fallback remains available
- Next required step: unblock task-013 wiring repair, review task-014 model-fit recipe, then run contained Interpreter-LM/front-door canaries before any live activation
- Source files: `interpreter_lm.py`, `maestro_listener.py`
- Tests: `tests/test_continuity_stamp.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_REENTRY_FINAL_REPORT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/02_interpreter_lm_decision.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_LOCAL_THROUGHPUT_MODELFIT_AUDIT_RESULT.md`
- Evidence refs: `interpreter_lm.py:_interpreter_enabled`, `tests/test_continuity_stamp.py:interpreter flag test coverage`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/02_interpreter_lm_decision.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_LOCAL_THROUGHPUT_MODELFIT_AUDIT_RESULT.md`
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

### LLM diagnostics logging (`llm_diagnostics_logging`)

- Flag/config: `OPENCLAW_LLM_DIAGNOSTICS`
- Default state: `enabled_by_default`
- Current state if verifiable: already-on internal observability; no external action or activation authority
- Production state: `enabled_verified_by_code_default_and_opus_decision`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `not_applicable_internal_observability`
- Risk level: `low`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off by default; if disabled, operator should record why diagnostics were suppressed
- Enabled by: code default internal diagnostics logging
- Disabled by: set OPENCLAW_LLM_DIAGNOSTICS=0 through approved config if needed
- Rollback: set OPENCLAW_LLM_DIAGNOSTICS=0 to suppress diagnostic logging
- Next required step: keep as internal read-only observability; do not expose secrets in logs
- Source files: `chief_llm.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `chief_llm.py:_diagnostics_enabled`
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

### Maestro brain live (`maestro_brain_live`)

- Flag/config: `OPENCLAW_MAESTRO_BRAIN_LIVE`
- Default state: `enabled_by_default_outside_test_mode`
- Current state if verifiable: already-on runtime lane per Opus decision; disabled under TEST_MODE and does not grant new activation authority
- Production state: `enabled_verified_by_opus_decision; this catalog task did not inspect live services`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `already_live_watch_timeout_lane`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off per Opus decision; no new enablement is authorized by this register
- Enabled by: Opus GO on 2026-06-19 behind protected_generate
- Disabled by: set OPENCLAW_MAESTRO_BRAIN_LIVE=0 through approved service configuration change
- Rollback: set OPENCLAW_MAESTRO_BRAIN_LIVE=0 through approved runtime rollback; keep TEST_MODE disabling behavior
- Next required step: keep watching model-fit and timeout behavior; do not change this flag in this task
- Source files: `protected_generate.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `protected_generate.py:_maestro_brain_live_enabled`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Model-selection policy contract (`model_selection_policy_contract`)

- Flag/config: `NO_AUTHORITY_FLAGS`
- Default state: `metadata_only_all_authority_false`
- Current state if verifiable: metadata-only contract exists with no runtime/model/provider authority
- Production state: `not_applicable_metadata_only`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_applicable_metadata_only`
- Risk level: `low`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: contract is descriptive and intentionally grants no model-selection authority
- Enabled by: metadata generation only; no runtime activation authority
- Disabled by: NO_AUTHORITY_FLAGS false by design
- Rollback: remove any consumer that treats this metadata contract as activation authority
- Next required step: keep as metadata; future runtime policy wiring needs a separate default-off task
- Source files: `model_selection_policy_contract.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `model_selection_policy_contract.py:NO_AUTHORITY_FLAGS`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Nemotron provider (`nemotron_provider`)

- Flag/config: `NVIDIA_API_KEY`, `NEMOTRON_URL`, `NEMOTRON_MODEL`
- Default state: `provider_config_required/fail_closed`
- Current state if verifiable: external provider path exists but is intentionally off for live use without policy-safe caller and credentials
- Production state: `not_enabled_by_this_register; credential presence not inspected`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: external model egress is high risk and requires explicit approval immediately before activation
- Enabled by: explicit operator approval, policy-safe packet, credential-safe provider setup, canary, and rollback
- Disabled by: no approved external-provider activation; missing key fails closed
- Rollback: remove approved provider env/config and keep external calls fail-closed
- Next required step: keep off until external egress policy and canary evidence are recorded
- Source files: `chief_llm.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `chief_llm.py:nemotron_call`, `chief_llm.py:_nemotron_api_key`
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

### Ollama model defaults (`ollama_model_defaults`)

- Flag/config: `OPENCLAW_OLLAMA_MODEL`, `OPENCLAW_OLLAMA_MODEL_DEEP`
- Default state: `enabled_by_code_default_qwen3_8b`
- Current state if verifiable: already-on local model default lane; model-fit repair remains needed for strong/deep references
- Production state: `enabled_verified_by_code_default_and_opus_decision`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `already_local_default; model_fit_repair_pending`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off by code default; no new model activation is authorized here
- Enabled by: existing local-only code default
- Disabled by: set OPENCLAW_OLLAMA_MODEL through approved config change or disable callers
- Rollback: restore OPENCLAW_OLLAMA_MODEL=qwen3:8b-q4_K_M or unset env to return to code default
- Next required step: repair strong/deep lane model-fit references before expanding model routing
- Source files: `chief_llm.py`
- Tests: `tests/test_chief_llm_router.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `chief_llm.py:OLLAMA_MODEL`, `chief_llm.py:OLLAMA_MODEL_DEEP`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### OpenAI adapter stub (`openai_adapter_stub`)

- Flag/config: `OPENAI_API_KEY`, `OpenAIConsultAdapter`
- Default state: `stub_unavailable`
- Current state if verifiable: adapter exists only as a hard unavailable stub; no live OpenAI provider path is enabled
- Production state: `not_enabled_by_this_register; credential presence not inspected`
- Live production state: `not_applicable`
- Gate stage: `blocked`
- Canary status: `not_applicable_stub`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: provider adapter is a stub and external egress would be high risk
- Enabled by: future explicit provider design only; not this register
- Disabled by: adapter raises adapter_stub_not_live
- Rollback: keep the adapter unavailable or remove it if Opus chooses deprecation
- Next required step: DEPRECATED_OR_REMOVE_LATER unless Opus queues a credential-safe OpenAI design
- Source files: `openclaw_lm_consult_spine.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `openclaw_lm_consult_spine.py:OpenAIConsultAdapter`, `openclaw_lm_consult_spine.py:adapter_stub_not_live`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Packet-source SQLite flip (`packet_source_sqlite_flip`)

- Flag/config: `OPENCLAW_PACKET_SOURCE`
- Default state: `flat/default`
- Current state if verifiable: standalone activation record for packet-source sqlite/hybrid flip; related continuity context is preserved separately
- Production state: `unknown_or_related_live_context_only; this task did not inspect live services`
- Live production state: `not_applicable`
- Gate stage: `canary`
- Canary status: `queued_for_hybrid_canary`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: packet content changes need a canary and rollback receipt before activation
- Enabled by: operator-approved hybrid/sqlite packet-source canary with content-diff receipt
- Disabled by: flat default or unset OPENCLAW_PACKET_SOURCE
- Rollback: set OPENCLAW_PACKET_SOURCE=flat or unset it through approved service configuration
- Next required step: run a supervised hybrid packet content-diff canary before production flip
- Source files: `maestro_context_packet.py`, `activation_gate_register.py`
- Tests: `tests/test_activation_gate_register.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `maestro_context_packet.py:OPENCLAW_PACKET_SOURCE`, `activation_gate_register.py:continuity related runtime context`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### Polish Loop factory mode (`polish_loop_factory_mode`)

- Flag/config: `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`, `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`, `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`, `OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1`, `OPENCLAW_POLISH_MAX_PARALLEL_LANES`, `OPENCLAW_POLISH_LANE_WORKER_CMD`, `OPENCLAW_TEST_MODE`, `OPENCLAW_SEND_HOLD`
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
- Audits: `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_IMPL_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/01_polish_loop_synthetic_activation.md`
- Evidence refs: `polish_loop/orchestrator.py:reconcile_file_loop_result_with_ledger`, `tests/test_polish_loop_file_ledger_reconciliation.py`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/01_polish_loop_synthetic_activation.md`
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

### Polish Loop size/type/risk router v1 (`polish_loop_size_router_v1`)

- Flag/config: `OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1`
- Default state: `planned/default-off`
- Current state if verifiable: planned default-off size/type/risk router record from task-012; catalog-only here and no runtime wiring in this branch
- Production state: `not_enabled_by_this_task; production activation prohibited`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `planned_synthetic_only; queued_for_repair/integration; canary required before runtime activation`
- Risk level: `medium`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: INTENTIONALLY_OFF / QUEUED_FOR_REPAIR: planned admission-routing capability is not integrated or canaried in this catalog-only task
- Enabled by: explicit OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1 only after Opus integration review, synthetic tests, canary, rollback proof, and operator-approved runtime scope
- Disabled by: catalog-only default-off record; runtime branch not integrated here
- Rollback: leave OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1 unset or set it to 0; Control Plane keeps legacy source-based admission/dispatchability
- Next required step: Opus review/integration of task-012, then separate synthetic/canary authorization if Polish Loop switch criteria otherwise pass
- Source files: `activation_gate_register.py`, `polish_loop/task_routing.py`, `polish_loop/control_plane.py`
- Tests: `tests/test_activation_gate_register.py`, `tests/test_polish_loop_size_routing.py`, `tests/test_polish_loop_size_router_wire.py`
- Audits: `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LIVE_WIRING_AUDIT_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_SIZE_ROUTER_WIRE_RESULT.md`
- Evidence refs: `polish_loop/task_routing.py:classify_task_routing`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LIVE_WIRING_AUDIT_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_SIZE_ROUTER_WIRE_RESULT.md`
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
- Audits: `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_3_AUDIT_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/01_polish_loop_synthetic_activation.md`
- Evidence refs: `polish_loop/worker_runtime.py:build_task_package_markdown`, `polish_loop/orchestrator.py:write_phase_c_fix_directive`, `tests/test_polish_loop_task_package_materialization.py`, `/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_3_AUDIT_RESULT.md`, `/home/openclaw/workspaces/openclaw_program/activation_receipts/01_polish_loop_synthetic_activation.md`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

### protected_generate Ollama timeouts (`protected_generate_ollama_timeouts`)

- Flag/config: `OPENCLAW_PROTECTED_GENERATE_EXTERNAL_TIMEOUT`, `OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT`, `OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS`, `OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT`
- Default state: `enabled_by_safe_defaults`
- Current state if verifiable: already-on internal timeout knobs with safe defaults; they tune bounded local generation behavior only
- Production state: `enabled_verified_by_code_default_and_opus_decision`
- Live production state: `not_applicable`
- Gate stage: `operator_approved_live`
- Canary status: `not_applicable_internal_tuning`
- Risk level: `low`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: not off by code default; no new runtime enablement is performed by this register
- Enabled by: existing safe default timeout values
- Disabled by: override/remove timeout env through approved config change only
- Rollback: unset OPENCLAW_PROTECTED_GENERATE_* timeout env values to return to code defaults
- Next required step: keep defaults; record any future timeout tuning receipt
- Source files: `protected_generate.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `protected_generate.py:OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT`, `protected_generate.py:OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT`
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

### Walk-away autonomy mode (`walk_away_autonomy_mode`)

- Flag/config: `autonomy_mode.py state file`
- Default state: `off`
- Current state if verifiable: built but intentionally off by default; enabling writes an autonomy mode state file
- Production state: `not_enabled_by_this_register; state file was not inspected`
- Live production state: `not_applicable`
- Gate stage: `intentionally_off`
- Canary status: `not_run_live`
- Risk level: `high`
- Owner: `Opus`
- Activation allowed now: `no`
- Operator approval required: `yes`
- Reason if off: walk-away autonomy expands unattended authority and requires immediate operator approval
- Enabled by: explicit operator approval for a bounded autonomy window
- Disabled by: default off state and no approved state-file write
- Rollback: run the approved disable path or restore the default off state file
- Next required step: do not enable from the register; require an operator-approved autonomy receipt
- Source files: `autonomy_mode.py`
- Tests: none recorded
- Audits: `/home/openclaw/workspaces/openclaw_program/OPUS_ACTIVATION_DECISIONS.md`, `/home/openclaw/workspaces/openclaw_program/CODEX_ACTIVATION_GATE_GAPS_AUDIT_RESULT.md`
- Evidence refs: `autonomy_mode.py:_default_state`, `autonomy_mode.py:cmd_enable`
- Last verified at: `2026-06-26T00:00:00-04:00`

Live-state evidence:
- Status: `not_applicable`
- Confidence: `none`
- Notes: live environment reconciliation was not requested for this register generation

## Flag Detection

- `CASSANDRA_EXTERNAL_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_chief_llm_router.py`
- `CASSANDRA_MORNING_BRIEF_TEST_MODE`: `found` in `activation_gate_register.py`, `cassandra_briefing_brain.py`, `tests/test_activation_gate_register.py`
- `CASSANDRA_TELEGRAM_DELIVERY_ENABLED`: `found` in `activation_gate_register.py`, `cassandra_telegram_delivery.py`
- `GEMINI_API_KEY`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `GOOGLE_API_KEY`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `GOOGLE_GENERATIVE_AI_API_KEY`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `HITL_ENABLED`: `found` in `activation_gate_register.py`, `hitl_pending_action.py`, `hitl_pending_store.py`, `tests/test_activation_gate_register.py`
- `HITL_FLAG_PATH`: `found` in `activation_gate_register.py`, `hitl_pending_store.py`
- `NEMOTRON_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`
- `NEMOTRON_URL`: `found` in `activation_gate_register.py`, `chief_llm.py`
- `NO_AUTHORITY_FLAGS`: `found` in `activation_gate_register.py`, `agent_package_preview_contract.py`, `model_selection_policy_contract.py`, `niles_album_evidence_intake_boundary.py`
- `NVIDIA_API_KEY`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_activation_gate_register.py`
- `OPENAI_API_KEY`: `found` in `activation_gate_register.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_ACTION_RUNTIME`: `found` in `action_runtime.py`, `activation_gate_register.py`, `authority_gate.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_CASSANDRA_EXTERNAL_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_chief_llm_router.py`
- `OPENCLAW_CASSANDRA_MORNING_BRIEF_ATTEMPTS`: `found` in `activation_gate_register.py`, `chief_llm.py`
- `OPENCLAW_CASSANDRA_MORNING_BRIEF_TIMEOUT_SECONDS`: `found` in `activation_gate_register.py`, `cassandra_briefing_brain.py`, `chief_llm.py`
- `OPENCLAW_CASSANDRA_MORNING_TEST_TIMEOUT_SECONDS`: `found` in `activation_gate_register.py`, `chief_llm.py`
- `OPENCLAW_CONTINUITY_CAPSULE`: `found` in `activation_gate_register.py`, `maestro_context_packet.py`, `maestro_listener.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_CONTROL_PLANE_EMIT`: `found` in `activation_gate_register.py`, `polish_loop/pc4_heal_emitter.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_ENABLE_LM_CONSULTS`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL`: `found` in `activation_gate_register.py`, `external_shadow_provider_config.py`
- `OPENCLAW_EXTERNAL_LM2_SHADOW_CREDENTIAL`: `found` in `activation_gate_register.py`, `external_shadow_provider_config.py`
- `OPENCLAW_EXTERNAL_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_chief_llm_router.py`
- `OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL`: `found` in `activation_gate_register.py`, `external_shadow_provider_config.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_FREEFORM_CLOUD`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_FRONTDOOR_KEEP_ALIVE`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`: `found` in `activation_gate_register.py`, `chief_llm.py`, `protected_generate.py`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_MODEL_PROFILE`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_NUM_CTX`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_NUM_GPU`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_NUM_PREDICT`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_frontdoor_model_profile.py`, `tests/test_frontdoor_warmpin_offload.py`
- `OPENCLAW_GEMINI_FORM_MODEL`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `OPENCLAW_GEMINI_MODEL`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `OPENCLAW_INTERPRETER_LM`: `found` in `activation_gate_register.py`, `interpreter_lm.py`, `maestro_context_packet.py`, `tests/test_activation_gate_register.py`, `tests/test_continuity_stamp.py`
- `OPENCLAW_LEGAL_PRIVATE_ROOT`: `found` in `activation_gate_register.py`
- `OPENCLAW_LLM_DIAGNOSTICS`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_LM_PROVIDER`: `found` in `activation_gate_register.py`, `openclaw_lm_consult_spine.py`
- `OPENCLAW_MAESTRO_BRAIN_LIVE`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_OLLAMA_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_OLLAMA_MODEL_DEEP`: `found` in `activation_gate_register.py`, `chief_llm.py`
- `OPENCLAW_PACKET_SOURCE`: `found` in `activation_gate_register.py`, `maestro_context_packet.py`, `tests/test_activation_gate_register.py`, `tests/test_packet_sqlite_flip.py`
- `OPENCLAW_POLISH_LANE_WORKER_CMD`: `found` in `activation_gate_register.py`, `polish_loop/lane_launcher.py`
- `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`: `found` in `activation_gate_register.py`, `polish_loop/orchestrator.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`: `found` in `activation_gate_register.py`, `polish_loop/orchestrator.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1`: `found` in `activation_gate_register.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`: `found` in `activation_gate_register.py`, `polish_loop/orchestrator.py`, `polish_loop/worker_runtime.py`, `tests/test_activation_gate_register.py`, `tests/test_polish_loop_task_package_materialization.py`
- `OPENCLAW_POLISH_MAX_PARALLEL_LANES`: `found` in `activation_gate_register.py`, `polish_loop/lane_launcher.py`
- `OPENCLAW_PROTECTED_GENERATE_EXTERNAL_TIMEOUT`: `found` in `activation_gate_register.py`, `protected_generate.py`
- `OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS`: `found` in `activation_gate_register.py`, `protected_generate.py`
- `OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT`: `found` in `activation_gate_register.py`, `protected_generate.py`, `tests/test_activation_gate_register.py`
- `OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT`: `found` in `activation_gate_register.py`, `protected_generate.py`
- `OPENCLAW_SEND_HOLD`: `found` in `activation_gate_register.py`, `polish_loop/lane_launcher.py`, `polish_loop/orchestrator.py`, `polish_loop/pc4_heal_emitter.py`, `tests/test_polish_loop_self_scaling.py`
- `OPENCLAW_TEST_MODE`: `found` in `activation_gate_register.py`, `polish_loop/lane_launcher.py`, `polish_loop/orchestrator.py`, `polish_loop/pc4_heal_emitter.py`, `protected_generate.py`, `tests/test_continuity_stamp.py`, `tests/test_polish_loop_self_scaling.py`
- `OPENROUTER_API_KEY`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_activation_gate_register.py`, `tests/test_chief_llm_router.py`
- `OPENROUTER_MODEL`: `found` in `activation_gate_register.py`, `chief_llm.py`, `tests/test_activation_gate_register.py`, `tests/test_chief_llm_router.py`
- `TELEGRAM_AUTHORIZED_USER_ID`: `found` in `activation_gate_register.py`, `cassandra_telegram_delivery.py`, `maestro_listener.py`

## Live Environment Reconciliation

- Enabled for this generation: `no`
- Whitelisted names: `OPENCLAW_INTERPRETER_LM`, `OPENCLAW_FRONTDOOR_MODEL_PROFILE`, `OPENCLAW_CONTINUITY_CAPSULE`, `OPENCLAW_PACKET_SOURCE`, `OPENCLAW_POLISH_LOOP_LOCAL_BUILDER`, `OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE`, `OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1`, `OPENCLAW_POLISH_LOOP_SIZE_ROUTER_V1`, `OPENCLAW_FREEFORM_CLOUD`, `OPENCLAW_FRONTDOOR_REPLY_TIMEOUT`, `OPENCLAW_FRONTDOOR_NUM_PREDICT`, `OPENCLAW_FRONTDOOR_NUM_CTX`, `OPENCLAW_FRONTDOOR_NUM_GPU`, `OPENCLAW_FRONTDOOR_KEEP_ALIVE`, `OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`, `OPENCLAW_FRONTDOOR_MODEL_MAX_GB`, `OPENROUTER_MODEL`, `OPENCLAW_EXTERNAL_MODEL`, `OPENCLAW_CASSANDRA_EXTERNAL_MODEL`, `CASSANDRA_EXTERNAL_MODEL`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`, `OPENCLAW_MAESTRO_BRAIN_LIVE`, `OPENCLAW_LLM_DIAGNOSTICS`, `HITL_ENABLED`, `OPENCLAW_ACTION_RUNTIME`, `OPENCLAW_CONTROL_PLANE_EMIT`, `OPENCLAW_OLLAMA_MODEL`, `OPENCLAW_OLLAMA_MODEL_DEEP`, `OPENCLAW_PROTECTED_GENERATE_EXTERNAL_TIMEOUT`, `OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT`, `OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS`, `OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT`, `CASSANDRA_MORNING_BRIEF_TEST_MODE`, `OPENCLAW_CASSANDRA_MORNING_BRIEF_TIMEOUT_SECONDS`, `OPENCLAW_CASSANDRA_MORNING_TEST_TIMEOUT_SECONDS`, `OPENCLAW_CASSANDRA_MORNING_BRIEF_ATTEMPTS`, `OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL`, `OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL`, `OPENCLAW_EXTERNAL_LM2_SHADOW_CREDENTIAL`
- Packet source runtime context: `not_applicable`

Sources inspected:
- none recorded

Sources not inspected:
- `live_env_reconciliation` `all_live_sources`: not requested for this deterministic generation

## Evidence Gaps

- Missing repository evidence files referenced by register: `tests/test_polish_loop_size_router_wire.py`
- Production env/service state: `not inspected by this task`
- Feature activation performed by this task: `no`
