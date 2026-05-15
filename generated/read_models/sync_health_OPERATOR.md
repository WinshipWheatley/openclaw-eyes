# OpenClaw Sync Health

Trust status: `stale_needs_pc_import`
Mirror status: `needs_pc_import`
Display status: `waiting_for_pc_import`
Next expected actor: `pc_import_task`

Mirror counts:
- canonical_expected=52
- observed=52
- missing_expected=0
- extra=0
- hash_mismatch=0
- matched_hash=52

Recommended fix:
- kind: `wait_for_pc_import`
- display status: `waiting_for_pc_import`
- next expected actor: `pc_import_task`
- next: Mac sync appears complete. Waiting for PC import task.
- app can request bounded Mac sync marker: `false`

Proof:
- Mac heartbeat: `synced` at `2026-05-15T15:45:50+00:00`
- Mac completion: `synced` at `2026-05-15T15:45:50+00:00`
- PC import: `skipped_unchanged` at `2026-05-15T15:34:48+00:00`
- Windows task log present: `true`

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
