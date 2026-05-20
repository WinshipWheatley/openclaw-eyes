Bridge Manual Mount Recovery Packet v0

State:
- Status: `blocked_manual_mount_required`
- Owner: `Chief / Mirror Trust`
- Check Engine should remain on until bridge proof is current.

Why Bridge Sync Is Blocked:
- Bridge sync cannot complete because /Volumes/openclaw_e is missing on Mac.
- The Mac sync agent cannot see the Windows E:\openclaw shuttle, so full PC-Mac read-model proof cannot complete.

Exact Manual Mount Needed:
- Windows source: `E:\openclaw`
- WSL source: `/mnt/e/openclaw`
- Mac mount: `/Volumes/openclaw_e`

What Winship Should Verify After Mounting:
- `ls -la /Volumes/openclaw_e` -> /Volumes/openclaw_e lists the Windows E:\openclaw share.
- `ls -la /Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json` -> The bounded sync request marker is visible from the Mac mount.

Existing Safe Sync Kick After Mount:
- `launchctl kickstart -k gui/$(id -u)/com.openclaw.read-model-sync`
- This is future-gated and manual; the packet does not run it.

PC Proof Now:
- canonical_expected=202
- observed=192
- missing_expected=10
- hash_mismatch=0

Expected Success Proof:
- /Volumes/openclaw_e exists on Mac.
- Mac sync agent no longer reports share_missing.
- read_model_sync_completed.json updates.
- mac_generated_read_models_manifest.json updates.
- Mac local mirror receives Chief posture + Chief diagnostic package files.
- PC import/sync health eventually reaches missing_expected=0, hash_mismatch=0.
- PC canonical and observed counts agree, likely 198/198 or the current expected count at time of run.

Partial Success Means:
- `mac_local_mirror_updates_pc_proof_stale`: The Mac local mirror receives files, but PC sync_health still has stale observed counts.
- `mount_exists_completion_marker_missing`: /Volumes/openclaw_e exists, but read_model_sync_completed.json does not update.
- `completion_marker_updates_pc_import_pending`: Mac completion marker updates, but PC import has not refreshed sync_health yet.
- `expected_count_changed_while_pending`: Repo A gained more generated read-models while the bridge was waiting.

Failure States:
- `mount_still_missing`: /Volumes/openclaw_e still does not exist after manual mount attempt.
- `mounted_under_wrong_name`: The share exists under a different /Volumes path, so scripts still cannot see /Volumes/openclaw_e.
- `smb_or_share_unavailable`: The Mac cannot see the Windows share.
- `manual_credentials_needed`: The Mac prompts Winship for credentials.
- `agent_still_reports_share_missing`: The LaunchAgent still reports share_missing after the mount appears present.
- `expected_marker_missing_from_shuttle`: The mount exists, but read_model_sync_required.json is not visible in the shuttle path.
- `pc_proof_remains_stale_after_mac_completion`: Mac completion updates, but PC import/sync_health still does not agree.

What Mission Control Should Show:
- Bridge sync is blocked because /Volumes/openclaw_e is not mounted on Mac.
- Winship must mount Windows E:\openclaw as /Volumes/openclaw_e, then verify the shuttle marker and kick the existing Mac sync service.
- Do not show Mirror Current while this packet is still blocked.

What Would Make Check Engine Quiet:
- /Volumes/openclaw_e is present on Mac.
- The sync request marker is visible through the Mac mount.
- The existing Mac sync LaunchAgent completes without share_missing.
- read_model_sync_completed.json and mac_generated_read_models_manifest.json update.
- PC sync_health reaches missing_expected=0 and hash_mismatch=0 for the current expected set.
- Bridge Trust / Sync Truth returns trusted_current or equivalent current proof.

What Must Not Be Done:
- delete anything
- perform deletes
- remount /Volumes/openclaw_e automatically
- handle or store credentials
- create auto-remount authority
- run Mac commands from PC
- write OpenClaw artifacts to C:
- manual-copy generated read-model files as the primary fix
- mutate Mission Control app code
- repair backend services from this packet
- activate agents or call models
- open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows
- inspect raw private logs, raw trace contents, broad temp listings, or raw file bodies

Boundary:
- Manual recovery packet only; no remount, delete, repair, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.
- The only safe service action described is the existing Mac LaunchAgent kick after Winship has manually verified the mount.
- No OpenClaw artifacts are written to C:.
