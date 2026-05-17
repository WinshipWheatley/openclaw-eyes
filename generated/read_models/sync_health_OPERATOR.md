# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=92
- observed=62
- missing_expected=30
- extra=0
- hash_mismatch=0
- matched_hash=62

Recommended fix:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-17T00:35:28+00:00`
- Mac completion: `synced` at `2026-05-16T05:28:43+00:00`
- PC import: `skipped_unchanged` at `2026-05-16T05:29:50+00:00`
- Windows task log present: `true`

Stale files:
- `OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json`
- `OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json`
- `agent_capability_migration_map.json`
- `approved_module_registry.json`
- `approved_module_registry_OPERATOR.md`
- `bundle_blueprint_planner.json`
- `bundle_blueprint_planner_OPERATOR.md`
- `cassandra_chief_memory_authority.json`
- `cassandra_chief_memory_authority_OPERATOR.md`
- `cassandra_chief_memory_dry_run.json`
- `cassandra_chief_memory_dry_run_OPERATOR.md`
- `cassandra_chief_memory_operator_review.md`
- `cassandra_chief_structured_import_plan.json`
- `cassandra_chief_structured_import_plan_OPERATOR.md`
- `cassandra_clara_fact_packet.json`
- `cassandra_clara_fact_packet_OPERATOR.md`
- `estate_topology.json`
- `estate_topology_OPERATOR.md`
- `governed_intake_spine.json`
- `governed_intake_spine_OPERATOR.md`
- `guardian_hitl_authority_reconciliation.json`
- `guardian_hitl_authority_reconciliation_OPERATOR.md`
- `guardian_hitl_cassandra_proposal_shadow.json`
- `guardian_hitl_cassandra_proposal_shadow_OPERATOR.md`
- `guardian_hitl_dual_write_compatibility.json`
- `guardian_hitl_dual_write_compatibility_OPERATOR.md`
- `guardian_hitl_shadow_adapter.json`
- `guardian_hitl_shadow_adapter_OPERATOR.md`
- `guardian_hitl_surface_disposition.json`
- `guardian_hitl_surface_disposition_OPERATOR.md`

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
