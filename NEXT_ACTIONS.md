# NEXT_ACTIONS.md
_Generated: 2026-03-17 | Prioritized by impact on current work. Based on real repo state._

Labels: `[album]` `[billing]` `[ops]` `[infra]` `[cleanup]`

---

## Priority 1 — Unblock Current Work

### 1. Resolve stuck Blue Weather session `[album]`
**What:** `chief_session.json` is stuck in `active_workflow=album, phase=follow_up, song=Blue Weather, turn=0`
**Action:** Send "album status" via Telegram to confirm state. Then either continue the session or send "cancel album" to clear it.
**Why first:** Every Telegram message may be silently consumed by the stale session until this is resolved.
**Risk:** Cancelling loses no data — Blue Weather was turn 0 (no answers recorded in this interrupted session).

### 2. Run album sessions for the 9 missing songs `[album]`
**What:** 9 of 12 songs have no CSV row. Batch planner is operating on 3 songs only.
**Action:** Run `album` session for each missing song. At minimum, seed basic fields (completion %, version locked, status).
**Songs missing (from `_ALBUM_SONGS` vs CSV):** Everything except "1 In A Million", "The Future", "Blue Weather"
**Why second:** Batch planner, mix briefs, and arc analysis are all blind to 75% of the album.

---

## Priority 2 — Stability / Visibility

### 3. Fix worker stdout logging `[ops]`
**What:** All worker `.out` files are 0 bytes. No visibility into errors.
**Action:** Add `flush=True` to key `print()` calls in `chief_listener.py`, `chief_worker.py`, `chief_memory_worker.py`. Or switch to `logging` module with file handler.
**Why:** When something breaks, there's nothing to look at. `billing_brain.out` being non-empty proves the mechanism works when output is actually written.

### 4. Confirm `chief_watcher_brain.py` is actually running `[ops]`
**What:** Watcher monitors billing overdue + album blockers on 15-min cadence. No systemd unit confirmed.
**Action:** Run `ps aux | grep chief_watcher` to check. If not running: `nohup python /home/openclaw/chief_watcher_brain.py > /mnt/c/OpenClaw/logs/watcher.out 2>&1 &`
**Optional:** Write a systemd unit for reliable restarts.

### 5. Add CLI smoke tests to pre-deploy checklist `[ops]`
**What:** No test suite. Changes are verified only via live Telegram testing.
**Action:** Document the minimal CLI smoke test commands in RUNBOOK.md (already started). Run before every stack restart.
**Key tests:**
```bash
python chief_album_batch.py "what should I do next"
python chief_nli.py "where are we at"
python chief_approval_brain.py "test query"
echo "1 in a million" | python chief_router.py  # if CLI mode exists
```

---

## Priority 3 — Album Completion

### 6. Run mix briefs for the 3 populated songs `[album]`
**What:** `chief_album_mixer.py` generates mix session briefs from CSV + Fundo prompts. Output goes to `vault/Album/Mix Briefs/*.md`.
**Action:** Send "mix brief" or "mix brief for Blue Weather" via Telegram.
**Why:** Mix briefs are immediately useful for actual studio sessions. 3 songs have enough data now.

### 7. Populate `DEEPPOCKET.md` with actual label data `[album]`
**What:** Roster, Releases, Publishing sections are blank stubs. Several brains reference this as label context.
**Action:** Fill in: DPR roster (Winship, Fundo), current release slate, publishing/PRO info.
**Effort:** 20 minutes. High leverage for brains that use it as context.

---

## Priority 4 — Integrations

### 8. Activate Google Calendar via broker `[infra]`
**What:** Calendar brain in dry-run mode. Google Access Broker scaffold is in place but inert — no credentials exist.
**Blocker:** External Google Cloud setup required first (cannot be done by Claude Code):
  1. Create GCP project → enable Google Calendar API
  2. Create OAuth 2.0 Client ID (Desktop app) → download credentials.json
  3. `mkdir -p /home/openclaw/.google-secrets && chmod 700 /home/openclaw/.google-secrets`
  4. Place file at `/home/openclaw/.google-secrets/credentials.json && chmod 600 ...`
  5. `source ~/chief_env/bin/activate && python3 /home/openclaw/google_access_broker.py --auth`
  6. `chmod 600 /home/openclaw/.google-secrets/token.json`
**After external setup:** Return to Claude Code for Phase 3 — live executor wiring, _fetch_events refactor, end-to-end test, capability state flip, legacy auth retirement. Do not attempt Phase 3 without credentials in place.
**Why now:** Broker scaffold, policy, and capability registry are all ready. Only the credential step is missing.

### 9. Deploy deeppocketrecords.com holding page `[infra]`
**What:** Domain registered March 15. No site deployed. Website QA brain has nothing to crawl.
**Action:** Deploy a minimal holding/teaser page (Fundo focus). Then run "website qa" to confirm QA pipeline works.
**Dependencies:** Hosting decision (Netlify/Vercel/Squarespace/etc.) not yet made.

---

## Priority 5 — Cleanup

### 10. Delete or archive `chief_album_brain_legacy.py` `[cleanup]`
**What:** Legacy file tracked in `.gitignore`. Not imported anywhere. Dead code.
**Action:** Run approval gate, then delete: `python3 chief_approval_brain.py "delete chief_album_brain_legacy.py"`. If approved: `rm /home/openclaw/chief_album_brain_legacy.py`
**Risk:** Low — confirmed no callers.
