# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Lifecycle state: `actionable_sync_failure`
Operator action required: `true`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=261
- observed=218
- missing_expected=43
- extra=0
- hash_mismatch=4
- matched_hash=214

App-visible stable map:
- map_status: `map_current`
- map_generation_id: `map_b324cf6bbb0237e81aa6`
- bundle_hash: `sha256:d890341105f29001293f65836472d6a11bec38ce110cd55a3dc31612fb17ba66`
- app_visible: `true`
- receipt_matches_pc_bundle: `true`
- agent_dossier_cards: `12` at `agent_council.agent_dossier_cards`
- agent_dossier_cards_path_status: `accepted_canonical_nested_path`
- package_preview_summary: `true` count=`8`
- tool_adapter_receipt_summary: `true` count=`12`
- capital_hilton_summary: `true` missing_proof=`10` protected_proof=`true`
- capital_hilton_protected_proof_intake: `true` proof_items=`10` missing_proof=`10` protected_proof=`true` candidate_facts_proven=`false`
- capital_hilton_authority_flags_false: `true`
- security_audit_readiness: `true` ready_for_pass=`true` approval=`false` action_authority=`false`
- security_coverage_gaps: `5` parked_breadcrumbs=`15`
- security_pass: `true` completed=`true` read_only=`true` preview=`true` action_authority=`false`
- security_pass_worker_orphan_chief_hermes: worker=`true` orphaned=`true` chief_hermes=`true`
- post_security_governance_batch: `true` parked_capital=`true` security_delta=`true` attention_promotion=`true` chief_cross_off=`true`
- front-door operator action required: `false`
- next expected actor: `none`
- next: none

Raw read-model mirror detail:
- raw_mirror_status: `raw_mirror_stale_or_mismatched`
- raw_mirror_blocks_app_visible_map: `false`

Check Transmission display:
- lamp_state: `QUIET`
- headline: Stable map bundle current
- summary: Mission Control can trust the app-facing map bundle; raw read-model differences stay in proof/detail.

Raw read-model mirror proof/detail recommendation:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- lifecycle state: `actionable_sync_failure`
- operator action required: `true`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-23T05:39:08+00:00`
- Mac completion: `synced` at `2026-05-21T18:25:34+00:00`
- PC import: `skipped_unchanged` at `2026-05-21T18:29:48+00:00`
- Windows task log present: `true`

Stale files:
- `agent_identity_actor_router_contract.json`
- `agent_identity_actor_router_contract_OPERATOR.md`
- `agent_memory_scope_contract.json`
- `agent_memory_scope_contract_OPERATOR.md`
- `agent_package_preview_contract.json`
- `agent_package_preview_contract_OPERATOR.md`
- `agent_platform_alignment.json`
- `agent_platform_alignment_OPERATOR.md`
- `agent_terrain_awareness_readback_contract.json`
- `agent_terrain_awareness_readback_contract_OPERATOR.md`
- `capital_hilton_proof_metadata_packet.json`
- `capital_hilton_proof_metadata_packet_OPERATOR.md`
- `capital_hilton_protected_proof_intake.json`
- `capital_hilton_protected_proof_intake_OPERATOR.md`
- `chief_test_harness_cross_off_receipt_contract.json`
- `chief_test_harness_cross_off_receipt_contract_OPERATOR.md`
- `memory_candidate_receipt_contract.json`
- `memory_candidate_receipt_contract_OPERATOR.md`
- `model_selection_policy_contract.json`
- `model_selection_policy_contract_OPERATOR.md`
- `model_selection_receipt_contract.json`
- `model_selection_receipt_contract_OPERATOR.md`
- `openclaw_map_OPERATOR.md`
- `openclaw_map_manifest.json`
- `openclaw_map_snapshot.json`
- `operator_attention_promotion_contract.json`
- `operator_attention_promotion_contract_OPERATOR.md`
- `operator_map_bundle_contract.json`
- `operator_map_bundle_contract_OPERATOR.md`
- `operator_threshold_map_contract.json`
- `operator_threshold_map_contract_OPERATOR.md`
- `package_preview_receipt_contract.json`
- `package_preview_receipt_contract_OPERATOR.md`
- `parked_autonomous_capital_pipeline_experiment.json`
- `parked_autonomous_capital_pipeline_experiment_OPERATOR.md`
- `security_audit_readiness_packet.json`
- `security_audit_readiness_packet_OPERATOR.md`
- `security_delta_review_contract.json`
- `security_delta_review_contract_OPERATOR.md`
- `security_pass_contract.json`
- `security_pass_contract_OPERATOR.md`
- `system_health_lights_taxonomy.json`
- `system_health_lights_taxonomy_OPERATOR.md`
- `tool_adapter_receipt_contract.json`
- `tool_adapter_receipt_contract_OPERATOR.md`
- `tool_protocol_adapter_registry_contract.json`
- `tool_protocol_adapter_registry_contract_OPERATOR.md`

No-authority posture:
- `app_direct_execution_allowed`: `false`
- `arbitrary_command_allowed`: `false`
- `remote_control_allowed`: `false`
- `ssh_scp_rsync_allowed`: `false`
- `docker_ollama_allowed`: `false`
- `runtime_activation_allowed`: `false`
- `agent_activation_allowed`: `false`
- `file_delete_allowed`: `false`
- `file_move_allowed`: `false`

Boundary:
- Sync Health is a read-model and ledger snapshot only.
- It does not remote-control Mac or Windows, run arbitrary commands, modify Mission Control, or broaden sync authority.
