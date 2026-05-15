# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`

Mirror counts:
- canonical_expected=50
- observed=48
- missing_expected=2
- extra=0
- hash_mismatch=0
- matched_hash=48

Recommended fix:
- kind: `request_mac_sync`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-15T15:25:46+00:00`
- Mac completion: `synced` at `2026-05-15T15:15:45+00:00`
- PC import: `skipped_unchanged` at `2026-05-15T15:19:51+00:00`
- Windows task log present: `true`

Stale files:
- `sync_health.json`
- `sync_health_OPERATOR.md`

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
