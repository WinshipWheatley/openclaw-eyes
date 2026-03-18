# Cassandra Skill

Cassandra is the personal executive assistant layer for OpenClaw Studios.
This skill is for testing, debugging, and extending Cassandra.

## Entry point
`/home/openclaw/cassandra_brain.py`

## Routing
Same Telegram bot as Chief. `cassandra_intent()` fires on:
- Explicit prefixes: `cassandra:`, `hey cassandra`, `@cassandra`, `/cassandra`
- Mode toggles: `focus on/off`, `social on/off`, `host mode on/off`
- Conversational keywords: "what's going on", "what am I missing",
  "help me prioritize", "orient me", "what matters today", etc.

Cassandra routing fires BEFORE ops intake and BEFORE cancel/correction checks
in `chief_router.py`.

## Model policy
- 7b (`qwen2.5-coder:7b`): quick conversational replies, mode toggles, short factual
- 14b (`qwen2.5-coder:14b`): synthesis, priorities, "what am I missing", big picture
- Decision: `_should_use_deep(query)` in cassandra_brain.py
- Uses explicit `model=` parameter on `ollama_call()` — bypasses auto-escalation

## State file
`/mnt/c/OpenClaw/logs/cassandra_state.json`
Tracks: human_cues, project_mood, recurring_concerns, chirp_log, last_interaction_at

## Mode locks (inspectable files)
Focus mode: `/mnt/c/OpenClaw/logs/cassandra_focus.lock`
  → exists = Cassandra quiet; watcher silenced
  → set: `touch /mnt/c/OpenClaw/logs/cassandra_focus.lock`
  → clear: `rm /mnt/c/OpenClaw/logs/cassandra_focus.lock`
  → via Telegram: "focus on" / "focus off"

Social mode: `/mnt/c/OpenClaw/logs/cassandra_social.lock`
  → exists = social/host mode active; chirps silenced, tone adjusted
  → via Telegram: "social on" / "social off"

## Watcher (cassandra_watcher.py)
- Polls every 30 minutes
- Chirp throttle: max 3/day, min 4h between chirps
- Chirp types: late_session, pending_payment, pending_action
- Silenced by: focus mode OR social mode
- Log: `/mnt/c/OpenClaw/logs/cassandra_watcher.out`

## What Cassandra owns
- Orientation, priorities, context, relational continuity
- Human-state awareness (cues: tired, stressed, blocked, focused)
- Ambient chirps for stale payments, stale actions, late sessions
- Mode management (focus, social)

## What Chief owns — Cassandra never touches
- Routing decisions (outside her intent detection)
- Album workflows, billing, approval gates
- Session state, session manager
- Operational execution (write-heavy system actions)

## Testing
```bash
source ~/chief_env/bin/activate
python3 -c "
from cassandra_brain import cassandra_intent, handle
print(cassandra_intent('hey cassandra what am I missing'))
print(handle('hey cassandra what am I missing'))
"
```
