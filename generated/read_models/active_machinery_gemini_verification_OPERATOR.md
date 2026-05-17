# Active Machinery Gemini Verification v0

Status:
- Gemini output treated as truth: `false`.
- Worker rows reconciled: `766`.
- Worker rows unreconciled: `0`.
- Verified high-risk rows: `17`.
- Likely active rows needing operator review: `76`.
- False-positive or safe artifact rows: `316`.
- Repo B reference-only rows: `1`.

## What This Means
Gemini hypotheses were joined back to the original safe shard metadata. High-risk claims were only promoted when the safe header excerpt or path metadata had matching deterministic signals. Nothing was bound to modules, nodes, or authority state.

## Verified High-Risk Active Machinery
Count: `17`
- `builder_watcher.sh` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, importer_exporter, path_daemon_listener_hint
- `cassandra_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api
- `cassandra_watcher.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, importer_exporter, mcp_tool_plugin_surface, path_daemon_listener_hint, send_external_api
- `chief_brainstorm_watcher.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, importer_exporter, path_daemon_listener_hint, state_mutator
- `chief_email_brain.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: approval_hitl, importer_exporter, path_send_api_hint, send_external_api
- `chief_guardian_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, path_daemon_listener_hint
- `chief_guardian_sender.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, path_send_api_hint, send_external_api
- `chief_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, scheduler_watchdog
- `chief_sender.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `chief_watcher_brain.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, shell_or_process
- `producer_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, importer_exporter, path_daemon_listener_hint, scheduler_watchdog, send_external_api
- `retry_send_demo_dashboard.sh` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: path_send_api_hint
- `scripts/run_producer_listener.sh` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, path_daemon_listener_hint
- `send_demo_dashboard.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `tests/test_cassandra_email_thread_analysis.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `tests/test_chief_listener_lifecycle.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api, state_mutator
- `tests/test_send_truth.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api

## Likely Active Machinery Needing Operator Review
Count: `76`
- `architecture_map_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: importer_exporter, mcp_tool_plugin_surface, send_external_api
- `capital_hilton_review_packet_approval.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, send_external_api, state_mutator
- `cassandra_briefing_scheduler.py` -> `scheduler_watchdog` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, scheduler_watchdog, send_external_api
- `chief_acceptance_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `chief_approval_brain.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, shell_or_process
- `chief_approval_bridge.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, send_external_api
- `chief_approval_policy.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint
- `chief_obsidian_sync.py` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, path_sync_bridge_hint, sync_bridge
- `chief_scheduler_brain.py` -> `scheduler_watchdog` / `hypothesis_needs_operator_review`; signals: importer_exporter, scheduler_watchdog, send_external_api, state_mutator
- `hitl_action_service.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint
- `hitl_flowchart_gen.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint
- `hitl_notification_service.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, send_external_api, state_mutator
- `hitl_pending_action.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, send_external_api
- `hitl_pending_store.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint
- `mac_eyes/Launchers/start_legal_planning_sync_window.sh` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: daemon_listener, path_sync_bridge_hint, state_mutator, sync_bridge
- `mac_eyes/Launchers/sync_legal_planning_to_mac.sh` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: daemon_listener, path_sync_bridge_hint, state_mutator, sync_bridge
- `mac_eyes/Launchers/sync_operator_harness_to_mac.sh` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: approval_hitl, daemon_listener, path_sync_bridge_hint, send_external_api, state_mutator
- `mac_eyes/Launchers/sync_to_mac.sh` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: daemon_listener, path_sync_bridge_hint, sync_bridge
- `mac_mirror_atlas.py` -> `importer_exporter` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, path_sync_bridge_hint, shell_or_process, state_mutator, sync_bridge
- `plugin_domain_registry.py` -> `mcp_tool_plugin_surface` / `likely_active_from_safe_header_needs_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface
- `scripts/build_tool_intake.py` -> `mcp_tool_plugin_surface` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, mcp_tool_plugin_surface, state_mutator
- `scripts/build_tool_inventory.py` -> `mcp_tool_plugin_surface` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, mcp_tool_plugin_surface, state_mutator
- `scripts/check_runtime_activation_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, state_mutator, sync_bridge
- `scripts/export_approved_module_registry_read_model.py` -> `importer_exporter` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, state_mutator, sync_bridge
- `scripts/export_bundle_blueprint_planner_read_model.py` -> `importer_exporter` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, sync_bridge
- ...51 more omitted from this operator view.

## False Positives / Safe Docs And Generated Files
Count: `316`
- `AGENTS.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: documentation, mcp_tool_plugin_surface
- `CURRENT_STATE.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, scheduler_watchdog, send_external_api
- `DEEPPOCKET.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: documentation, sync_bridge
- `KNOWN_GAPS.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: daemon_listener, documentation, send_external_api
- `NEXT_ACTIONS.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, send_external_api
- `OPENCLAW_RUNTIME.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, mcp_tool_plugin_surface, state_mutator, sync_bridge
- `OPERATOR_EXTENSION_MANIFESTO.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, mcp_tool_plugin_surface, sync_bridge
- `Operator/GENERATED_CURRENT_STATE.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, mcp_tool_plugin_surface, state_mutator, sync_bridge
- `Operator/GENERATED_NEXT_ACTIONS.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, state_mutator
- `RUNBOOK.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation
- `USER.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: documentation, mcp_tool_plugin_surface
- `apps/legal-console-spike/README.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, state_mutator
- `docs/INDEX.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, mcp_tool_plugin_surface, state_mutator
- `docs/README.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: documentation
- `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, importer_exporter, scheduler_watchdog
- `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, state_mutator, sync_bridge
- `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, state_mutator, sync_bridge
- `docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, state_mutator, sync_bridge
- `docs/operations/ACTIVE_MACHINERY_CLASSIFICATION_WORKER_PROMPT_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, importer_exporter, mcp_tool_plugin_surface
- `docs/operations/AGENT_CAPABILITY_MIGRATION_MAP_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, importer_exporter, scheduler_watchdog
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_MIGRATION_SPEC_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, send_external_api, state_mutator
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_SCHEMA_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, send_external_api, state_mutator
- `docs/operations/CASSANDRA_MACHINE_CONTRACT.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, send_external_api, state_mutator
- `docs/operations/CHIEF_MACHINE_CONTRACT.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, daemon_listener, documentation, send_external_api, sync_bridge
- `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md` -> `canonical_doctrine_docs` / `safe_doc_or_generated_false_positive`; signals: approval_hitl, documentation, importer_exporter, path_approval_hitl_hint, send_external_api
- ...291 more omitted from this operator view.

## Repo B Reference-Only Machinery
Count: `1`
- `.` -> `legacy_reference_only` / `reference_only_not_runtime_verified`

## Send/API Surfaces
Count: `7`
- `chief_email_brain.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: approval_hitl, importer_exporter, path_send_api_hint, send_external_api
- `chief_guardian_sender.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, path_send_api_hint, send_external_api
- `chief_sender.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `retry_send_demo_dashboard.sh` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: path_send_api_hint
- `send_demo_dashboard.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `tests/test_cassandra_email_thread_analysis.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api
- `tests/test_send_truth.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: importer_exporter, path_send_api_hint, send_external_api

## Sync/Bridge Surfaces
Count: `151`
- `active_machinery_classification_orchestrator.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `backend_knowledge_packet.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator, sync_bridge
- `bundle_blueprint_planner.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, sync_bridge
- `capital_hilton_review_packet_approval.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, send_external_api, state_mutator
- `cassandra_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api
- `chief_acceptance_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `chief_ceo_briefing.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, send_external_api, state_mutator, sync_bridge
- `chief_eod_harness.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, state_mutator, sync_bridge
- `chief_fundo_identity.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, sync_bridge
- `chief_fundo_session.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, mcp_tool_plugin_surface, sync_bridge
- `chief_guardian_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, path_daemon_listener_hint
- `chief_integration_brain.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator, sync_bridge
- `chief_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, scheduler_watchdog
- `chief_obsidian_sync.py` -> `sync_bridge` / `likely_active_from_safe_header_needs_review`; signals: importer_exporter, path_sync_bridge_hint, sync_bridge
- `chief_publishing_brain.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator, sync_bridge
- `context_selection.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, mcp_tool_plugin_surface, send_external_api, state_mutator, sync_bridge
- `corpus_atlas.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, shell_or_process, state_mutator, sync_bridge
- `estate_read_model.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `evidence_kettle.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator, sync_bridge
- `external_ai_context_packager.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `governed_intake_spine.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, send_external_api, state_mutator
- `guardian_schema_harness.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, send_external_api
- `launch_ladder_contract_check.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator, sync_bridge
- `local_automation_registry.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, mcp_tool_plugin_surface, send_external_api, state_mutator, sync_bridge
- `mac_eyes/Launchers/refresh_operator_harness_ingest.sh` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, send_external_api, state_mutator, sync_bridge
- ...126 more omitted from this operator view.

## Approval/HITL Surfaces
Count: `134`
- `agent_task_proposals.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator
- `architecture_map_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: importer_exporter, mcp_tool_plugin_surface, send_external_api
- `autonomy_mode.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, state_mutator
- `autonomy_qualification.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `backend_data_contract.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, state_mutator
- `backend_storage_intelligence.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `business_ops_ledger.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator
- `business_ops_packet.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface
- `capability_registry.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `capital_hilton_review_packet_approval.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint, send_external_api, state_mutator
- `cassandra_briefing_brain.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, scheduler_watchdog
- `cassandra_briefing_scheduler.py` -> `scheduler_watchdog` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, scheduler_watchdog, send_external_api
- `cassandra_listener.py` -> `daemon_listener` / `deterministically_verified_from_safe_header`; signals: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api
- `chief_acceptance_gate.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `chief_approval_brain.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, shell_or_process
- `chief_approval_bridge.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, send_external_api
- `chief_approval_policy.py` -> `approval_hitl` / `hypothesis_needs_operator_review`; signals: approval_hitl, importer_exporter, path_approval_hitl_hint
- `chief_brainstorm_brain.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, scheduler_watchdog
- `chief_ceo_briefing.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, send_external_api, state_mutator, sync_bridge
- `chief_chat.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, send_external_api, state_mutator
- `chief_email_brain.py` -> `send_external_api` / `deterministically_verified_from_safe_header`; signals: approval_hitl, importer_exporter, path_send_api_hint, send_external_api
- `chief_end_of_day_review.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, send_external_api, shell_or_process
- `chief_eod_harness.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, daemon_listener, importer_exporter, state_mutator, sync_bridge
- `chief_file_io.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator
- `chief_focus_reporter.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- ...109 more omitted from this operator view.

## Unknown / Needs Deeper Review
Count: `357`
- `active_machinery_classification_orchestrator.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, state_mutator, sync_bridge
- `agent_task_proposals.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator
- `apps/legal-console-spike/index.html` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/package-lock.json` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/package.json` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/src-tauri/Cargo.toml` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: mcp_tool_plugin_surface
- `apps/legal-console-spike/src-tauri/build.rs` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/src-tauri/capabilities/default.json` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/src-tauri/tauri.conf.json` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `apps/legal-console-spike/tsconfig.json` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`
- `autonomy_mode.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, state_mutator
- `autonomy_qualification.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `backend_data_contract.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface, state_mutator
- `backend_knowledge_packet.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator, sync_bridge
- `backend_sqlite_repository.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator
- `backend_sqlite_runtime.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, state_mutator
- `backend_sqlite_schema.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, mcp_tool_plugin_surface, state_mutator
- `backend_storage_intelligence.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `budget_tracker.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter
- `bundle_blueprint_planner.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, send_external_api, sync_bridge
- `business_ops_intent.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: importer_exporter, mcp_tool_plugin_surface, scheduler_watchdog, send_external_api
- `business_ops_ledger.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, state_mutator
- `business_ops_packet.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, mcp_tool_plugin_surface
- `capability_registry.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter
- `cassandra_briefing_brain.py` -> `unknown_operator_review` / `unknown_or_low_signal_needs_deeper_review`; signals: approval_hitl, importer_exporter, scheduler_watchdog
- ...332 more omitted from this operator view.

## Boundaries
- No code was executed.
- No Repo B code was run.
- No raw private/no-go content was read.
- Gemini output remains hypothesis input, not truth.
- No `openclaw_nodes` or `module_registry` binding was created.

## Next Safe Move
Operator reviews verified high-risk and likely active surfaces before any binding to modules, nodes, or authority state.
