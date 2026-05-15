# Repo B Runtime Intake v0

## Source
- Path: `/home/openclaw_external/openclaw-runtime`
- Remote: `https://github.com/WinshipWheatley/openclaw-runtime.git`
- Branch: `master`
- Commit: `839e445fc64f181234042b410ecd7b41bb2fe149`
- Canonical status: `non_canonical_until_promoted`
- Import status: `metadata_scanned_only`

## Counts
- Files scanned: 146
- Python files: 89
- Shell scripts: 13
- Markdown docs: 30
- Startup scripts found: 10
- Invoked scripts referenced: 26
- Agent surfaces found: 136
- Legacy runtime risks: 10
- Direct execution risk findings: 157
- Module candidates: 134
- Client product candidates: 6
- Finance/invoice candidates: 51
- Music/album candidates: 17
- Security/HITL candidates: 9
- No-go/skipped metadata rows: 2

## Startup Scripts
- `builder_watcher.sh` refs=2 nohup=True background=True
- `loop_control.sh` refs=2 nohup=False background=True
- `loop_dashboard_watchdog.sh` refs=3 nohup=True background=True
- `loop_supervisor.sh` refs=10 nohup=True background=True
- `polish_loop/start_orchestrator.sh` refs=3 nohup=True background=True
- `retry_send_demo_dashboard.sh` refs=1 nohup=False background=True
- `start_album_brain.sh` refs=1 nohup=False background=False
- `start_chief.sh` refs=21 nohup=True background=True
- `start_chief_logged.sh` refs=9 nohup=True background=True
- `start_openclaw_brains.sh` refs=4 nohup=False background=True

## Top Runtime Risks
- `.claude/commands/cassandra.md` telegram_direct (high): Telegram-related source reference detected
- `.claude/commands/cassandra.md` approval_bypass_reference (high): approval bypass reference detected
- `CLAUDE.md` nohup_background (high): nohup/background runtime invocation detected
- `CLAUDE.md` telegram_direct (high): Telegram-related source reference detected
- `CLAUDE.md` env_token_reference (high): token/env reference detected
- `CLAUDE.md` dotenv_reference (high): .env reference detected
- `CLAUDE.md` google_access_reference (high): Google access reference detected
- `CURRENT_STATE.md` nohup_background (high): nohup/background runtime invocation detected
- `CURRENT_STATE.md` telegram_direct (high): Telegram-related source reference detected
- `CURRENT_STATE.md` env_token_reference (high): token/env reference detected
- `CURRENT_STATE.md` google_access_reference (high): Google access reference detected
- `KNOWN_GAPS.md` nohup_background (high): nohup/background runtime invocation detected

## Top Burden-Reduction Candidates
- `.claude/commands/cassandra.md` role=context_pack_component_candidate burden=reduces_finance_burden status=docs_only
- `CLAUDE.md` role=context_pack_component_candidate burden=reduces_finance_burden status=docs_only
- `CURRENT_STATE.md` role=reusable_module_candidate burden=reduces_finance_burden status=docs_only
- `KNOWN_GAPS.md` role=reusable_module_candidate burden=reduces_finance_burden status=docs_only
- `NEXT_ACTIONS.md` role=reusable_module_candidate burden=reduces_finance_burden status=docs_only
- `RUNBOOK.md` role=reusable_module_candidate burden=reduces_finance_burden status=docs_only
- `autonomy_mode.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `autonomy_qualification.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `budget_tracker.py` role=personal_only_candidate burden=reduces_finance_burden status=candidate_to_port
- `builder_watcher.sh` role=runtime_service_candidate burden=reduces_finance_burden status=legacy_runtime_risk
- `capability_registry.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `cassandra_brain.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `cassandra_capability.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `cassandra_outreach.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `chief_analytics_brain.py` role=reusable_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `chief_approval_bridge.py` role=security_guardrail_candidate burden=reduces_finance_burden status=candidate_to_wrap
- `chief_approval_policy.py` role=security_guardrail_candidate burden=reduces_finance_burden status=candidate_to_wrap
- `chief_billing_brain.py` role=personal_only_candidate burden=reduces_finance_burden status=candidate_to_port
- `chief_brainstorm_brain.py` role=reusable_module_candidate burden=reduces_finance_burden status=module_registry_candidate
- `chief_calendar_brain.py` role=core_module_candidate burden=reduces_finance_burden status=module_registry_candidate

## Recommended Next Lanes
- Niles Music Runtime Candidate Review v0: Classify useful helpers into metadata-only planning modules before any DAW or file-changing behavior.
- Client Template Candidate Review v0: Map candidate files to Project Capsule/module registry without generating client repos yet.
- Guardian HITL Security Reconciliation v0: Keep sensitive surfaces metadata-only and evaluate whether they map to Operator Action gates or remain blocked.
- Agent Runtime Reconciliation v0: Compare mapped runtime surfaces against Agent Presence and recovery policy; do not start services.
- Finance Invoice Helper Reconciliation v0: Inspect candidates under Guardian boundaries and decide whether a metadata-only finance helper lane should port safe logic.
- Legacy Runtime Startup Boundary Review v0: Convert any still-useful startup behavior into fixed recovery actions with receipts, or keep blocked.

## Decision Packet
- At a glance: Legacy runtime listeners, workers, startup scripts, approval/HITL helpers, Cassandra/Chief/Niles/Guardian surfaces, finance/music/client-product candidates, and legacy docs.
- Highest burden-reduction targets:
  - Finance/invoice helpers for business ops relief.
  - Music/album helpers for Niles support.
  - Cassandra/Chief runtime surfaces for agent recovery clarity.
  - Approval/HITL/security code for guarded Operator Action reuse.
- Do not touch yet:
  - Secrets, env files, credential-like files, private/client/legal/tax roots, and startup scripts that launch background processes.
  - Any Repo B runtime service until wrapped in fixed recovery policy with receipts.

## Authority Boundary
- `repo_b_canonical`: `false`.
- `repo_b_execution_allowed`: `false`.
- `repo_b_imported_as_truth`: `false`.
- `script_execution_allowed`: `false`.
- `service_start_allowed`: `false`.
- `secret_access_allowed`: `false`.
- `file_move_allowed`: `false`.
- `file_delete_allowed`: `false`.
- `client_deployment_allowed`: `false`.
- `module_promotion_allowed`: `false`.
- `operator_decision_required`: `true`.
