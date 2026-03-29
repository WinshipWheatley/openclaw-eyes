# CURRENT_STATE.md
_Generated: 2026-03-17 | Based on actual repo audit — not aspirational architecture._

---

## System Identity

**Owner:** H. Winship Wheatley IV
**Company:** Deep Pocket Records (parent: Winship Live)
**Domain:** deeppocketrecords.com (registered March 15, 2026)
**Primary artist projects:** DPR / Winship (12-song album), Fundo (Afrobeats, 15-song arc)

---

## Architecture

```
Telegram (user) ──► chief_listener.py ──► chief_router.py ──► [brain].handle(text)
                                               │
                         ┌─────────────────────┤
                         │ routing cascade:     │
                         │ 1. approval gate     │
                         │ 2. approval bridge   │
                         │ 3. SMS/email confirm  │
                         │ 4. scheduler         │
                         │ 5. batch planner     │
                         │ 6. NLI status layer  │
                         │ 7. session load      │
                         │ 8. cancel/correction │
                         │ 9. brainstorm escape │
                         │ 10. active session   │
                         │ 11. explicit intents │
                         │ 12. LLM classify     │
                         └──────────────────────┘

Background:
  chief_watcher_brain.py   (systemd/nohup, 15-min checks)
  chief_album_brain.py     (nohup, legacy polling mode)
  chief_billing_brain.py   (nohup, legacy polling mode)
```

---

## Entry Points

| File | Role | How started |
|---|---|---|
| `chief_listener.py` | Telegram bot, main message loop | `nohup python chief_listener.py` via `start_chief.sh` |
| `chief_worker.py` | Monitors chief_input.log, deduplicates | `nohup python chief_worker.py` via `start_chief.sh` |
| `chief_memory_worker.py` | Appends to decision_log.md | `nohup python chief_memory_worker.py` |
| `chief_state_worker.py` | Parses STATE\|item\|status entries to state.csv | `nohup python chief_state_worker.py` |
| `chief_reply_worker.py` | Sends "Chief received" confirmation | `nohup python chief_reply_worker.py` |
| `chief_album_brain.py` | Legacy polling mode for album queue | `nohup python chief_album_brain.py` (start_openclaw_brains.sh) |
| `chief_billing_brain.py` | Legacy billing polling | `nohup python chief_billing_brain.py` (start_openclaw_brains.sh) |
| `chief_watcher_brain.py` | Silent monitor (billing overdue, album blockers) | Systemd or manual nohup |

---

## LLM Layer (`chief_llm.py`)

| Function | Model | Used for |
|---|---|---|
| `claude_call()` | claude-sonnet-4-6 | Creative, business, synthesis, narrative |
| `claude_json()` | claude-sonnet-4-6 | Structured extraction |
| `ollama_call()` | qwen2.5-coder:7b @ localhost:11434 | Album notes, marketing drafts, quick classification |
| `ollama_json()` | qwen2.5-coder:7b | Quick structured extraction |

Both return empty string on failure. No retry logic.

---

## Session State

**File:** `/home/openclaw/OpenClaw/state/chief_session.json`
**Current state:** `active_workflow=album, status=active, phase=follow_up, song=Blue Weather, turn=0`
**Managed by:** `chief_session_manager.py` (file-locked JSON read/write)
**Workflows with multi-turn sessions:** album, billing, invoice, fundo, brainstorm, scheduler (external JSON)

---

## Brain Ecosystem — 40 implemented brains

### Fully active / production data present

| Brain | What it does | Key data file |
|---|---|---|
| `chief_album_brain.py` | Album session coach, 13-topic Q&A, CSV+MD write | `album_work_log.csv` (3 songs, partial) |
| `chief_album_io.py` | CSV/markdown I/O for album | `album_work_log.csv`, `vault/Album/Songs/*.md` |
| `chief_album_batch.py` | Cross-album batch planner (8 batch types) | reads `album_work_log.csv` |
| `chief_album_mixer.py` | Mix session briefs from CSV + Fundo prompts | `vault/Album/Mix Briefs/*.md` |
| `chief_billing_brain.py` | Multi-turn invoice/payment intake | `billing_records.csv`, `billing_records.jsonl` |
| `chief_invoice_brain.py` | Invoice generation | `billing_records.*`, `invoice_counter.txt` |
| `chief_financial_brain.py` | P&L, tax projection (2025 baseline embedded) | reads billing records |
| `chief_cpa_brain.py` | Tax/expense tracking (2025 actuals embedded) | `expense_log.json` |
| `chief_musiclaw_brain.py` | Music law Q&A — **Ten Fingers dispute active** | `musiclaw_log.json` (44 lines) |
| `chief_publishing_brain.py` | Catalog registry, 12-song DPR catalog | `publishing_registry.json` (4.6KB) |
| `chief_fundo_session.py` | Two-phase Fundo coaching (Suno + tool-aware) | `fundo_sessions.json` (4.7KB) |
| `chief_fundo_identity.py` | Fundo brand/arc briefs | `vault/Fundo/Fundo Identity.md` |
| `chief_fundo_release.py` | Release checklists, DistroKid fields | `fundo_releases.json` |
| `chief_marketing_brain.py` | Content ideas, copy drafts (Ollama) | `content_log.json` (278 lines) |
| `chief_content_brain.py` | Content calendar management | `content_log.json` |
| `chief_brand_brain.py` | DPR + Fundo brand rules | `vault/Marketing/Brand Guide.md` |
| `chief_email_brain.py` | Email draft + send (Gmail optional) | `email_log.json` |
| `chief_sms_brain.py` | SMS draft + send (Twilio optional) | `sms_log.json` |
| `chief_phone_brain.py` | Call logging + script generation | `call_log.json` |
| `chief_website_creative.py` | Headlines, bios, SVG logos, Canva briefs | `vault/Website/Creative Log.md` |
| `chief_website_coordinator.py` | Site project tracker | `website_state.json` |
| `chief_website_qa.py` | Crawl + audit deeppocketrecords.com | `vault/Website/QA Log.md` |
| `chief_scheduler_brain.py` | Pomodoro work blocks, break/stop/switch | `scheduler_state.json` |
| `chief_queue_brain.py` | Claude Code task queue (Telegram → queue) | `claude_queue.log` |
| `chief_analytics_brain.py` | Cross-domain metrics (billing + album + content) | `vault/System/Analytics Report.md` |
| `chief_goals_brain.py` | Goal milestone tracking | `goals.json` (46 lines) |
| `chief_momentum_brain.py` | Artist vs admin mode detection | `vault/System/Momentum Report.md` |
| `chief_calendar_brain.py` | Google Calendar (OAuth ready, dry-run if no creds) | `vault/Calendar/Weekly Log.md` |
| `chief_backup_brain.py` | Git status + auto-push (approval-gated) | `vault/System/Backup Status.md` |
| `chief_scout_brain.py` | Tech digest + tool discovery | `scout_findings.json` (171 lines) |
| `chief_reflection_brain.py` | System feedback loop (reads all logs) | `reflection_log.json` (336 lines) |
| `chief_integration_brain.py` | Feature/upgrade proposals from scout | `integration_proposals.json` (238 lines) |
| `chief_reporter_brain.py` | Daily digest from all worker logs | `vault/System/Daily Report.md` |
| `chief_validator_brain.py` | Reply length/safety gate | `vault/System/Validation Log.md` |
| `chief_watcher_brain.py` | Silent monitor (billing overdue, blockers) | `chief_watcher_state.json` |
| `chief_trinity_brain.py` | Architecture audit (domain completeness) | `vault/System/Trinity Audit.md` |
| `chief_approval_brain.py` | Blocking YES/NO gate for destructive actions | `approval_pending.json` |
| `chief_approval_bridge.py` | Non-blocking multi-choice prompt (1/2/3) | `choice_pending.json` |
| `chief_focus_shield.py` | Hold non-urgent items during work blocks | `focus_held.json` |
| `chief_nli.py` | Natural language status/trust queries | none (reads session) |
| `chief_brainstorm_brain.py` | Idea capture + Claude synthesis | `brainstorm_log.json` (69 lines) |
| `chief_brainstorm_router.py` | Routes by timing class → queue/backlog/etc | `brainstorm_log.json` |
| `chief_brainstorm_watcher.py` | Surfaces watching items by keyword | `brainstorm_log.json` |
| `chief_obsidian_sync.py` | CSV → vault YAML frontmatter sync | all vault/Album files |

---

## Storage Map

```
/home/openclaw/
  OpenClaw/
    state/chief_session.json     ← active session (file-locked)
    exports/
      billing_records.csv        ← billing history
      billing_records.jsonl      ← billing history (append-only)
      invoice_counter.txt        ← next invoice number
      inspection-*/              ← 9 codebase snapshots (Mar 14-15)
  chief_env/                     ← Python venv

/mnt/c/OpenClaw/logs/
  chief_input.log                ← 323 lines, all incoming messages
  claude_queue.log               ← pending Claude Code tasks
  chief_watcher_state.json       ← watcher run state
  listener.out / worker.out / *  ← all 0 bytes (workers not logging stdout)
  billing_brain.out              ← 6.2KB (only non-empty .out file)

/mnt/c/OpenClawShared/
  album/
    album_work_log.csv           ← 3 songs (1 in Million, The Future, Blue Weather)
    brainstorm_log.json          ← ~25 ideas
    content_log.json             ← marketing calendar
    goals.json                   ← 5 active goals
    scheduler_state.json         ← current block state
    reflection_log.json          ← 10 reflection runs
    scout_findings.json          ← tech digest cache
    integration_proposals.json   ← 238-line proposals list
    focus_held.json              ← items held by focus shield
    choice_pending.json          ← approval bridge state
  business/
    fundo_sessions.json          ← active Fundo sessions
    musiclaw_log.json            ← Ten Fingers dispute (44 lines, ACTIVE)
    publishing_registry.json     ← 12-song DPR catalog
    email_log.json / sms_log.json / call_log.json
    expense_log.json / contacts.json
    website_state.json
  openclaw-vault/                ← Obsidian vault (Windows, synced)
    Album/Songs/*.md             ← 12 song files (all exist, mostly empty)
    System/*.md                  ← Reports, logs, audit files
    Marketing/ Fundo/ Website/ Business/ Research/ Calendar/

```

---

## Environment Dependencies

| Variable | Required | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | chief_llm.py |
| `TELEGRAM_BOT_TOKEN` | Yes | chief_listener.py, chief_sender.py, chief_notify.py |
| `TELEGRAM_AUTHORIZED_USER_ID` | Yes | chief_listener.py, chief_notify.py |
| `TELEGRAM_CHAT_ID` | Yes | chief_sender.py |
| `GMAIL_USER` | Optional | chief_email_brain.py (drafts still work without) |
| `GMAIL_APP_PASSWORD` | Optional | chief_email_brain.py |
| `TWILIO_ACCOUNT_SID` | Optional | chief_sms_brain.py (drafts still work without) |
| `TWILIO_AUTH_TOKEN` | Optional | chief_sms_brain.py |
| `TWILIO_FROM_NUMBER` | Optional | chief_sms_brain.py |

Ollama must be running at `localhost:11434` with `qwen2.5-coder:7b` loaded.
