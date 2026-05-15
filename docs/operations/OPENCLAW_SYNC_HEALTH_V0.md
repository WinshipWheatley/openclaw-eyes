# OpenClaw Sync Health v0

Sync Health v0 is a backend read-model surface for Mac/PC generated read-model mirror trust.

It answers whether the mirror is currently trusted, stale, mismatched, degraded, or needs operator review. It does not sync files itself, remote-control another machine, modify Mission Control, or broaden mirror authority.

## Inputs

- Canonical backend generated read-model files: `/home/openclaw/generated/read_models`
- Mac returned manifest: `/mnt/e/openclaw/mac_generated_read_models_manifest.json`
- Mac heartbeat/status marker: `/mnt/e/openclaw/shuttle/from_mac/read_model_sync_agent_status.json`
- Mac completion marker: `/mnt/e/openclaw/shuttle/from_mac/read_model_sync_completed.json`
- PC import agent state: `/home/openclaw/.openclaw/state/read_model_import_agent_state.json`
- PC import task log: `/home/openclaw/.openclaw/logs/windows_task_read_model_import.log`
- Windows-side task log from WSL: `/mnt/e/openclaw/windows_tasks/logs/OpenClawReadModelImport.log`

## Trust Status

- `trusted`: manifest matches backend generated read-models, and enough automation proof exists.
- `stale_needs_mac_sync`: missing expected files or hash-mismatched files indicate the Mac mirror is stale.
- `stale_needs_pc_import`: Mac completion or manifest hash indicates the PC import side has not caught up.
- `mismatch`: unexpected extra mirror files require review.
- `degraded`: mirror content matches, but heartbeat/log/state proof is incomplete.
- `unknown_review`: required state is missing or cannot be determined.

## Recommended Fix

- `none`: no sync repair needed.
- `request_mac_sync`: write/request the bounded Mac sync marker at `/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json`.
- `wait_for_pc_import`: wait for the Windows scheduled task or run the PC import agent one-shot.
- `inspect_automation`: inspect service/log proof.
- `manual_review`: review unexpected mirror state before trusting it.

`can_request_fix_from_app` is true only for the bounded Mac sync marker path. That is a request marker, not direct execution.

## Commands

```bash
python3 scripts/build_sync_health.py --format operator
python3 scripts/query_sync_health.py --report summary --format operator
python3 scripts/query_sync_health.py --report proof --format operator
python3 scripts/export_sync_health_read_model.py --format operator
```

Exports:

- `generated/read_models/sync_health.json`
- `generated/read_models/sync_health_OPERATOR.md`

## Boundary

- No Mission Control changes in this lane.
- No arbitrary command execution.
- No remote control of Mac or Windows.
- No SSH/SCP/rsync.
- No Docker/Ollama.
- No runtime, agent, or tool activation.
- No file moves, deletes, or C-drive writes.
