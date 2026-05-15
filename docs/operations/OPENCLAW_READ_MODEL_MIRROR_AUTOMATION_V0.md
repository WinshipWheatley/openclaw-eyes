# OpenClaw Read-Model Mirror Automation v0

Purpose: make the PC -> Mac generated read-model mirror loop repeatable without
manual manifest dragging or pasted one-off scripts.

This layer wraps the existing Read-Model Shuttle and Mac Mirror Atlas contract.
It does not change generated read-model contracts, Mission Control, runtime,
agents, Docker, Ollama, SSH, SCP, rsync, or launchd.

## Paths

- PC/WSL generated read-model source:
  `/home/openclaw/generated/read_models`
- Mac generated read-model mirror:
  `/Users/hwinshipwheatley/openclaw_generated_read_models`
- Shared drop:
  - Mac: `/Volumes/openclaw_e`
  - PC: `E:\openclaw`
  - WSL: `/mnt/e/openclaw`
- Returned Mac manifest:
  `/mnt/e/openclaw/mac_generated_read_models_manifest.json`

## Mac Command

Unified command from the active backend clone:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator
```

On Mac, this performs the Mac sync/drop step. On PC/WSL, this imports the
latest returned manifest from `/mnt/e/openclaw/mac_generated_read_models_manifest.json`
and reports mirror health. If the PC/WSL side runs before the Mac has dropped a
manifest, it reports the missing manifest path instead of attempting a sync.

The unified command reports explicit handoff states:

- `ok`: PC/WSL imported the latest manifest and the Mac mirror is current.
- `needs_mac_sync`: PC/WSL imported a manifest, but the Mac mirror is stale.
  This includes missing canonical backend generated read-model files or
  hash-mismatched files that differ from backend `generated/read_models`.
  PC/WSL writes a sync request marker for the Mac LaunchAgent.
- `needs_pc_import`: the Mac synced and dropped a manifest to the E-drive share.
  Run the same unified command on PC/WSL.
- `share_missing`: the Mac share `/Volumes/openclaw_e` is not mounted, so PC/WSL
  cannot see the returned manifest yet.
- `manifest_missing`: PC/WSL cannot find
  `/mnt/e/openclaw/mac_generated_read_models_manifest.json`.
- `review_needed`: PC/WSL sees extra Mac mirror files not in canonical backend
  `generated/read_models`.
- `error`: the command failed for a reason other than ordinary stale Mac mirror
  state.

When PC/WSL reports `needs_mac_sync`, it writes a safe marker at:

```text
/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json
```

The marker contains missing filenames, hash-mismatched filenames, the expected
responder (`mac_read_model_sync_agent`), a manual fallback command, and
no-authority flags only. It does not run anything on the Mac.

Primary behavior: the Mac LaunchAgent should notice the marker and refresh the
Mac generated-read-model mirror automatically. The manual Mac command is a
diagnostic fallback, not the normal first step. Use the local services doctor or
sync heartbeat when checking whether the background loop responded.

Run from the backend clone on the Mac:

```bash
cd ~/Developer/OpenClawBackend/openclaw
PYTHONDONTWRITEBYTECODE=1 python3 scripts/mac_sync_generated_read_models.py --pull --format operator
```

What it does:

- optionally runs `git pull origin main` when `--pull` is passed
- copies safe JSON, Markdown, and text generated read-model/operator files into
  `/Users/hwinshipwheatley/openclaw_generated_read_models`
- excludes manifests, SQLite databases, temp/private/no-go patterns, hidden
  files, and nested folders
- writes the local Mac manifest:
  `~/Desktop/openclaw_mac_manifests/mac_generated_read_models_manifest.json`
- if `/Volumes/openclaw_e` is mounted, copies that manifest to:
  `/Volumes/openclaw_e/mac_generated_read_models_manifest.json`
- if the share is mounted, writes:
  `/Volumes/openclaw_e/shuttle/from_mac/read_model_sync_latest.json`

If the share is not mounted, the local Mac mirror and desktop manifest still
update. Add `--require-share` to fail when the share is missing.

## PC Import Command

Run on PC/WSL:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_latest_mac_read_model_mirror.py --format operator
```

Default import source:

```text
/mnt/e/openclaw/mac_generated_read_models_manifest.json
```

The helper imports through the existing Mac Mirror Atlas path and prints:

- generated-read-model mirror summary
- mirror mismatch summary
- Mac roots summary
- critical file presence for:
  - `operator_actions.json`
  - `agent_lanes.json`
  - `project_capsules.json`
  - `report_bridge.json`
  - `context_selection.json`

The generated-read-model mirror report derives its full expected file set from
the canonical backend `generated/read_models` directory using the same safe
top-level JSON/Markdown/text selection rules as the shuttle. New generated
read-model exports become expected automatically after they exist in that
canonical backend directory.

If the PC import reports `needs_mac_sync`, first check the local service
doctor/heartbeat and let the Mac LaunchAgent respond to the request marker. If
manual fallback is needed, run on the Mac:

```bash
cd ~/Developer/OpenClawBackend/openclaw
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator
```

If the Mac sync reports `needs_pc_import`, run on PC/WSL:

```bash
cd /home/openclaw
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --format operator
```

## Boundary

- No background daemon or launchd item is installed in v0.
- No files are deleted, moved, or reorganized.
- No C-drive transfer path is used by default.
- No Mission Control source code is modified.
- No generated read-model contract is changed.
- No runtime, agent, tool, model, container, network, SSH, SCP, rsync, or truth
  promotion authority is created.

## Next Safe Move

Use the two commands above as the standard mirror loop. A later lane may create
a Mac LaunchAgent or button-driven request path, but that requires explicit
approval and separate tests.

## Local Services v0

`OPENCLAW_LOCAL_AUTOMATION_SERVICES_V0.md` now defines the safe background
service manager for this loop. The single status/doctor surface is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --doctor read_model_mirror --format operator
```

It installs or controls only the current machine's local half. It does not
control the other machine or add a remote-management path.
