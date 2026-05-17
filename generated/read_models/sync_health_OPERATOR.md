# OpenClaw Sync Health

Trust status: `trusted`
Mirror status: `ok`
Display status: `current`
Next expected actor: `none`

Mirror counts:
- canonical_expected=92
- observed=92
- missing_expected=0
- extra=0
- hash_mismatch=0
- matched_hash=92

Recommended fix:
- kind: `none`
- display status: `current`
- next expected actor: `none`
- next: No sync repair is needed.
- app can request bounded Mac sync marker: `false`

Proof:
- Mac heartbeat: `idle` at `2026-05-17T01:30:34+00:00`
- Mac completion: `synced` at `2026-05-17T01:20:33+00:00`
- PC import: `skipped_unchanged` at `2026-05-17T01:24:51+00:00`
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
