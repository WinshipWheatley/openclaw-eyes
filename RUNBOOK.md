# RUNBOOK.md
_Generated: 2026-03-17 | Exact commands only. Based on real repo state._

---

## Operator Surface

- Copilot is the manual operator surface for interactive work inside VS Code.
- Do not use Copilot as the primary autonomous OpenClaw engine.
- For autonomous code tasks, use Claude Code or Codex with bounded prompts, explicit file scope, and diff-first review when possible.

### Codex Invocation Pattern

Use Codex from the repo root with a bounded prompt, explicit file scope, and diff-only closeout.

```bash
cd /home/openclaw && codex "You are working in /home/openclaw. Task: <task>. Edit only <exact file paths>. Do not touch polish_loop/orchestrator/approval logic unless the named files explicitly require it. Inspect first, make the smallest safe change, and show the exact diff only."
```

Read-only variant:

```bash
cd /home/openclaw && codex "Read only. Inspect <exact file paths>. Do not edit anything. Return findings briefly."
```

## Stack Start / Stop / Restart

### Service Management Freeze

Pass 3C Slice 1 freezes this section as historical command reference only. Do not remove these command blocks in this slice, but treat service authority, deprecated controls, and cleanup order as governed by [docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md](docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md). Existing start, stop, restart, install, and legacy polling commands are frozen/historical until cleanup slices replace, guard, or retire them.

### Unified Restart (Authoritative)
Starts or restarts the **Full OpenClaw Operating Environment**. This is the primary command to bring all systems online.
- **Includes**: Core systemd stack + Expected legacy polling brains.
```bash
bash /home/openclaw/scripts/start_all.sh
```

### Core Stack Only (systemd)
Restarts only the modern, systemd-managed services.
```bash
systemctl --user restart openclaw-stack.target
```

### Install boot-persistent user services
```bash
bash /home/openclaw/scripts/install_openclaw_stack.sh
```
Installs repo-owned systemd user units into `~/.config/systemd/user/`, enables `openclaw-stack.target`, and starts it.
If another machine does not already have lingering enabled, run once as root:
```bash
loginctl enable-linger <user>
```

### Start the main stack
```bash
source ~/chief_env/bin/activate
bash /home/openclaw/start_chief.sh
```
Starts: `chief_listener.py`, `chief_worker.py`, `chief_memory_worker.py`, `chief_state_worker.py`

### Start legacy polling brains (optional)
```bash
bash /home/openclaw/start_openclaw_brains.sh
```
Starts: `chief_album_brain.py` (polling), `chief_billing_brain.py` (polling)
Note: Main stack does NOT depend on these. They are legacy polling loops.

### Stop everything
```bash
pkill -f chief_listener.py
pkill -f chief_worker.py
pkill -f chief_memory_worker.py
pkill -f chief_state_worker.py
pkill -f chief_album_brain.py
pkill -f chief_billing_brain.py
```
Note: `pkill` exits with code 1 if no matching process — this is normal, not an error.

### Check what's running
```bash
ps aux | grep chief_ | grep -v grep
```

---

## Log Files

| File | What it shows |
|---|---|
| `/mnt/c/OpenClaw/logs/listener.out` | Telegram listener stdout (currently 0 bytes — known gap) |
| `/mnt/c/OpenClaw/logs/worker.out` | Worker stdout (currently 0 bytes) |
| `/mnt/c/OpenClaw/logs/chief_input.log` | All incoming Telegram messages (323 lines as of audit) |
| `/mnt/c/OpenClaw/logs/billing_brain.out` | Billing polling brain output (6.2KB — only active out file) |
| `/tmp/chief_album_brain.log` | Album brain polling stdout (if `start_openclaw_brains.sh` was used) |
| `/tmp/chief_billing_brain.log` | Billing brain polling stdout |

### Tail live input log
```bash
tail -f /mnt/c/OpenClaw/logs/chief_input.log
```

---

## Environment

### Activate virtualenv
```bash
source ~/chief_env/bin/activate
```

### Load env vars (for manual script runs)
```bash
source /home/openclaw/.chief.env
```

### Check env vars are set
```bash
echo $ANTHROPIC_API_KEY | cut -c1-8
echo $TELEGRAM_BOT_TOKEN | cut -c1-8
echo $TELEGRAM_AUTHORIZED_USER_ID
```

### Check Ollama is running
```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep name
```
Expected: `qwen2.5-coder:7b` in the list.

---

## Session State

### Read current session
```bash
cat /home/openclaw/OpenClaw/state/chief_session.json
```

### Reset a stuck session (manual)
```bash
echo '{"active_workflow": null, "status": "idle", "workflow_state": {}}' \
  > /home/openclaw/OpenClaw/state/chief_session.json
```
**Warning:** Only do this if session is stuck and you're not mid-workflow. Prefer sending "cancel" via Telegram.

### Check pending approval
```bash
cat /mnt/c/OpenClawShared/album/approval_pending.json 2>/dev/null || echo "No pending approval"
```

### Check pending bridge choice
```bash
cat /mnt/c/OpenClawShared/album/choice_pending.json 2>/dev/null || echo "No pending choice"
```

---

## Album Data

### View CSV (current data)
```bash
source ~/chief_env/bin/activate
python3 -c "
from chief_album_io import load_all_rows
for r in load_all_rows():
    print(r.get('song_title'), '|', r.get('completion_pct'), '|', r.get('status'))
"
```

### Run batch planner manually
```bash
source ~/chief_env/bin/activate && source /home/openclaw/.chief.env
python3 /home/openclaw/chief_album_batch.py "what should I do next"
python3 /home/openclaw/chief_album_batch.py "chill batch"
python3 /home/openclaw/chief_album_batch.py "overview"
```

### Sync vault markdown from CSV
```bash
source ~/chief_env/bin/activate && source /home/openclaw/.chief.env
python3 /home/openclaw/chief_obsidian_sync.py
```

---

## Smoke Tests (Run Before Stack Restart)

Run these before restarting after any code change:

```bash
source ~/chief_env/bin/activate && source /home/openclaw/.chief.env

# NLI layer
python3 -c "from chief_nli import detect_nli_query; print(detect_nli_query('where are we at'))"
# Expected: 'status'

# Batch planner
python3 /home/openclaw/chief_album_batch.py "best batch"

# Focus shield
python3 -c "from chief_focus_shield import is_focus_active; print('focus active:', is_focus_active())"

# Approval bridge
python3 -c "from chief_approval_bridge import has_pending_choice; print('pending choice:', has_pending_choice())"

# Router import (catches syntax errors)
python3 -c "import chief_router; print('router OK')"
python3 -c "import chief_listener; print('listener OK')"
```

---

## Codebase Snapshot (Inspection)

### Create a snapshot via Telegram
Send: `inspect` or `inspection`

### Create a snapshot from CLI
```bash
/home/openclaw/chief-inspect "manual snapshot reason"
```
Output appears in: `/home/openclaw/OpenClaw/exports/inspection-YYYYMMDD-HHMMSS/`

---

## Git Operations

### Check status
```bash
cd /home/openclaw && git status
```

### Commit tracked files
```bash
cd /home/openclaw
git add chief_router.py chief_listener.py chief_album_brain.py  # etc.
git commit -m "message"
```

### Push
```bash
cd /home/openclaw && git push
```

### What's tracked
See `/home/openclaw/.gitignore` — allowlist format (`!filename`). Only explicitly listed files are tracked.

---

## Approval Gate (Claude Code Actions)

Before any destructive action (delete, overwrite billing records, etc.):
```bash
source ~/chief_env/bin/activate && source /home/openclaw/.chief.env
python3 /home/openclaw/chief_approval_brain.py "plain English description of what you are about to do"
```
- Exit code 0 = approved, proceed
- Exit code 1 = denied, stop

---

## Failure Points

| Symptom | Likely cause | Check |
|---|---|------|
| No reply to Telegram messages | Listener not running | `ps aux \| grep chief_listener` |
| "Billing input captured" for every message | Active billing session open | Check `chief_session.json` workflow |
| Album session not progressing | Session stuck in unexpected phase | Read `chief_session.json`, send "cancel" |
| LLM calls failing silently | Ollama not running or key missing | `curl localhost:11434/api/tags`; check `$ANTHROPIC_API_KEY` |
| Batch planner returns no songs | CSV empty or songs not in `_ALBUM_SONGS` list | Run CSV check above |
| Focus shield blocking all brainstorm | Scheduler stuck in `running_work` | Check `scheduler_state.json`; send "stop" via Telegram |
| "Chief received" double-reply | `chief_reply_worker.py` + direct reply both firing | Known gap; suppress with intent-aware log writes |

---

## Watcher Brain (15-min monitor)

### Check if running
```bash
ps aux | grep chief_watcher | grep -v grep
```

### Start manually
```bash
source ~/chief_env/bin/activate && source /home/openclaw/.chief.env
nohup python /home/openclaw/chief_watcher_brain.py > /mnt/c/OpenClaw/logs/watcher.out 2>&1 &
```

### Check its last run state
```bash
cat /mnt/c/OpenClaw/logs/chief_watcher_state.json
```
