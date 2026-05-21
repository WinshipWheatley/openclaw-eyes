# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Lifecycle state: `actionable_sync_failure`
Operator action required: `true`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=214
- observed=212
- missing_expected=2
- extra=0
- hash_mismatch=2
- matched_hash=210

Recommended fix:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- lifecycle state: `actionable_sync_failure`
- operator action required: `true`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `synced` at `2026-05-21T00:29:46+00:00`
- Mac completion: `synced` at `2026-05-21T00:29:46+00:00`
- PC import: `success` at `2026-05-21T00:29:48+00:00`
- Windows task log present: `true`

Stale files:
- `mission_control_design_memory_inventory.json`
- `mission_control_design_memory_inventory_OPERATOR.md`
- `system_health_lights_taxonomy.json`
- `system_health_lights_taxonomy_OPERATOR.md`

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
