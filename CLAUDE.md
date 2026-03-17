# OpenClaw — Claude Code Operating Rules

## Approval Gate (REQUIRED)

Before performing any of the following actions, you MUST call the approval brain and check the exit code. Do not proceed if exit code is 1.

```bash
python3 /home/openclaw/chief_approval_brain.py "plain English description of what you are about to do"
```

**Actions that require approval:**
- Deleting any file (`rm`, `unlink`, `Path.unlink()`, `shutil.rmtree`)
- Git force-push (`push --force`, `push -f`)
- Git branch deletion (`branch -D`, `push origin --delete`)
- Writing to any file outside `/home/openclaw/` that is not in `/mnt/c/OpenClawShared/openclaw-vault/`
- Posting or publishing to any external service
- Modifying saved billing records (CSV or JSONL) after they have been written
- Dropping or truncating any database or log file
- Any action you assess as irreversible

**Actions that do NOT require approval:**
- Reading files
- Writing new Python source files under `/home/openclaw/`
- Editing vault markdown files under `/mnt/c/OpenClawShared/openclaw-vault/`
- Running tests or smoke tests
- Git add, commit, push (non-force) to the repo
- Running `start_chief.sh`

## Working Directory

Primary: `/home/openclaw/`
Vault: `/mnt/c/OpenClawShared/openclaw-vault/`
Logs: `/mnt/c/OpenClaw/logs/`

## Python Environment

Always use the virtualenv: `source ~/chief_env/bin/activate`
Or run scripts directly with `python` (the venv python is on PATH when activated).

## Key Files

| File | Purpose |
|---|---|
| `chief_listener.py` | Telegram bot entry point |
| `chief_router.py` | Intent routing |
| `chief_session_manager.py` | Shared session state |
| `chief_llm.py` | Ollama LLM client |
| `chief_obsidian_sync.py` | Vault sync |
| `start_chief.sh` | Start the full stack |
| `DEEPPOCKET.md` | Label/artist reference |

## Stack Restart

```bash
bash /home/openclaw/start_chief.sh
```
