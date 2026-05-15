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
