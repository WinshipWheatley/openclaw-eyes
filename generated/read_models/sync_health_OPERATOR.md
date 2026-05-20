# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `sync_requested_waiting_for_mac`
Lifecycle state: `sync_requested_waiting_for_mac`
Operator action required: `false`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=204
- observed=202
- missing_expected=2
- extra=0
- hash_mismatch=0
- matched_hash=202

Recommended fix:
- kind: `wait_for_mac_sync`
- display status: `sync_requested_waiting_for_mac`
- next expected actor: `mac_sync_agent`
- lifecycle state: `sync_requested_waiting_for_mac`
- operator action required: `false`
- next: Mac sync has already been requested; waiting for the normal Mac sync agent cycle.
- app can request bounded Mac sync marker: `false`

Proof:
- Mac heartbeat: `idle` at `2026-05-20T16:07:09+00:00`
- Mac completion: `synced` at `2026-05-20T16:02:08+00:00`
- PC import: `skipped_unchanged` at `2026-05-20T16:04:48+00:00`
- Windows task log present: `true`

Stale files:
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
