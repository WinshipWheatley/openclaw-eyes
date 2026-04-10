# Mac Local AI Watch — Setup & Authority

## Start here

You are operating inside the Mac Local AI Watch workspace.
This workspace is an AI-facing reflection layer, not the canonical repo.
Canonical docs and source-of-truth materials live in `/home/openclaw/docs/` and the real repo/runtime surfaces.
Treat drafts here as candidate artifacts unless explicitly promoted.
Do not infer canonical truth from local draft presence alone.
Prefer confirmed canonical docs and runtime-derived evidence over local workspace artifacts.

Use `drafts/` for candidate AI-written artifacts in this workspace.
Use `archive/` for stale or superseded drafts you want to keep.
Do not create a truth-sounding `outputs/` bucket here.

## What is authoritative

| Root | Path | Authority |
|------|------|-----------|
| Runtime / code root (`Core System`) | `openclaw@DESKTOP-HP:/home/openclaw` | **Source of truth** — live runtime and all code edits |
| Runtime data / log / state root (`Runtime State`) | `\\DESKTOP-HP\C:\OpenClaw` | Runtime logs, state, legal |
| Shared business / vault root (`Shared Vault`) | `\\DESKTOP-HP\C:\OpenClawShared` | Obsidian vault, business data |

## What is mirrored (review-only)

This folder (`~/OpenClaw_Watch` on the Mac) contains **copies** of PC-generated files.
They are read-only snapshots pushed by `sync_to_mac.sh` running on the PC.

Files mirrored:
- **Live Watch.md** — single-glance heartbeat (timestamp + loop state)
- **Right now.md** — current loop status overview
- **Builder Right now.md** — builder runner status
- **Planner Right now.md** — planner/task queue status
- **Deep Dive Report.md** — manual investigation findings
- **What happened.md** — recent activity log

**Do not edit these files on the Mac.** Changes will be overwritten on next sync.

## Canonical writing flow

- Write canonical doctrine/spec/handoff docs into `/home/openclaw/docs/`.
- Use `/home/openclaw/docs/_ai/AI_WORKING_CONTEXT.md` as the single high-signal AI briefing file.
- Use `/home/openclaw/docs/_ai/BUILD_INTENT.md` to describe what is being built before asking for plans or docs.
- For Feynman-style planning work: read `AI_WORKING_CONTEXT.md` first, `BUILD_INTENT.md` second, then recommend an operating/settings profile before doing work.
- Keep draft artifacts in `drafts/` until they are explicitly promoted into `/home/openclaw/docs/`.
- Prefer archive over delete for stale drafts.

## How to open the Mac-local AI watch window

1. On the Mac, open VS Code normally (not Remote-SSH).
2. File → Open Workspace from File...
3. Navigate to `~/OpenClaw_Watch/Mac Local AI Watch.code-workspace`
4. This opens a local-only window showing the mirrored review files.

Or from terminal:
```bash
code ~/OpenClaw_Watch/Mac\ Local\ AI\ Watch.code-workspace
```

## How files stay fresh

On the PC (WSL), run the sync script:
```bash
# One-shot
/home/openclaw/mac_eyes/Launchers/sync_to_mac.sh

# Continuous (matches dashboard_gen.py 30s interval)
/home/openclaw/mac_eyes/Launchers/sync_to_mac.sh --watch
```

The pipeline: `dashboard_gen.py` writes to `mac_eyes/Winship/` every 30s → `sync_to_mac.sh` pushes those files to `~/OpenClaw_Watch/` on the Mac every 30s.

## Mac-side manual verification

Run this **on the Mac** to confirm freshness:
```bash
stat -f '%m %N' ~/OpenClaw_Watch/Live\ Watch.md
```
Or check the timestamp printed inside `Live Watch.md` — if it's more than 2 minutes old, either `dashboard_gen.py` or `sync_to_mac.sh` is stopped on the PC.

## Rollback

To fully remove this setup:

**On PC (WSL):**
```bash
rm /home/openclaw/mac_eyes/Launchers/sync_to_mac.sh
rm /home/openclaw/mac_eyes/Winship/Mac\ Local\ AI\ Watch.code-workspace
rm "/home/openclaw/mac_eyes/Winship/Mac Local AI Watch — READ ME.md"
rm "/home/openclaw/mac_eyes/Winship/Live Watch.md"
```

**On Mac:**
```bash
rm -rf ~/OpenClaw_Watch
```

In `dashboard_gen.py`, remove the `gen_live_watch()` function and the `Live Watch.md` line from `_winship_outputs()`.
