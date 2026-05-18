# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=158
- observed=154
- missing_expected=4
- extra=0
- hash_mismatch=2
- matched_hash=152

Recommended fix:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-18T02:41:07+00:00`
- Mac completion: `synced` at `2026-05-18T00:55:58+00:00`
- PC import: `skipped_unchanged` at `2026-05-18T00:59:52+00:00`
- Windows task log present: `true`

Stale files:
- `niles_album_matrix_review.json`
- `niles_album_matrix_review_OPERATOR.md`
- `niles_album_metadata_intake_packet.json`
- `niles_album_metadata_intake_packet_OPERATOR.md`
- `niles_album_review_packet.json`
- `niles_album_review_packet_OPERATOR.md`

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
