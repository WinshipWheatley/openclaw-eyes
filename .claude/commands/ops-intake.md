# Ops Intake Skill

Process, test, or debug an ops intake message for the OpenClaw/Chief system.

## What this Skill does

Given an ops intake message (or a request to inspect/debug the ops intake system), this Skill:
1. Runs the message through `chief_ops_brain.py`
2. Reports what got classified and written where
3. Shows the exact vault files written to
4. Flags any items that need follow-up

## How to invoke

**Test a message directly:**
```bash
cd /home/openclaw && source ~/chief_env/bin/activate && python chief_ops_brain.py "Ops update: <items>"
```

**Check what was written:**
- Ops email items: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Email Log.md`
- Calendar items: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Calendar Notes.md`
- Action items: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Actions.md`
- General notes: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Notes.md`
- Payment follow-ups: `/mnt/c/OpenClawShared/openclaw-vault/System/Ops Payment Follow-ups.md`
- Master log: `/mnt/c/OpenClaw/logs/ops_intake_log.md`
- Deferred queue: `/mnt/c/OpenClaw/logs/ops_intake_deferred.json`

## Recognized prefix markers

Any message starting with one of these triggers ops intake:
- `Ops update:`
- `Operational update:`
- `Brain dump:`
- `Admin update:`

## Classification priority

`payment` > `email` > `action` > `calendar` > `note`

Payment signals win over email to correctly route deposit/outstanding items.

## Focus-hat behavior

If an album session is active when the message arrives, items are deferred to
`ops_intake_deferred.json` and surfaced after the session ends (cancel or finalize).

## File I/O

All file writes go through `chief_file_io.py`:
- `append_md_entry(path, ts, text)` — writes to category destination
- `append_md_tagged(path, ts, tag, text)` — writes to master log with `[cls]` tag
- `load_json` / `save_json` — deferred queue state

## What NOT to touch without full testing

- `_PAYMENT_SIGNALS` — order and membership affects Capital Hilton-style routing
- `_META_PATTERNS` — filter for instruction lines that should not become ops items
- `_parse_items()` — indent-based grouping for sub-items (e.g. drafted emails list)
- Deferred summary delivery path in `chief_listener.py` (cancel + album-end hooks)

## Entry point in router

`chief_router.py` → `ops_intake_intent()` → fires before cancel/correction/brainstorm checks.
Stale non-album active sessions are reset before routing ops intake.
