"""
cassandra_brain.py

Cassandra — personal executive assistant for OpenClaw Studios.

Owns: orientation, priorities, context, relational continuity, well-being nudges.
Defers to Chief for: routing, approvals, album workflows, billing, execution.

Public API
----------
cassandra_intent(text)      — intent detection for chief_router
handle(text, session)       — main conversational handler → list[str]
is_focus_mode()             — silence gate
is_social_mode()            — social boundary
set_focus_mode(active)      — toggle focus lock
set_social_mode(active)     — toggle social lock
chirp_allowed(chirp_type)   — throttle check for watcher
log_chirp(chirp_type)       — record chirp to prevent spam
build_context_snapshot()    — system state block for watcher prompts
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_file_io import load_json, save_json
from chief_llm import ollama_call, OLLAMA_MODEL, OLLAMA_MODEL_DEEP

# ── Paths ─────────────────────────────────────────────────────────────────────

_STATE_PATH  = Path("/mnt/c/OpenClaw/logs/cassandra_state.json")
_FOCUS_LOCK  = Path("/mnt/c/OpenClaw/logs/cassandra_focus.lock")
_SOCIAL_LOCK = Path("/mnt/c/OpenClaw/logs/cassandra_social.lock")

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_PAYMENT = _VAULT_SYS / "Ops Payment Follow-ups.md"
_OPS_NOTES   = _VAULT_SYS / "Ops Notes.md"
_OPS_EMAIL   = _VAULT_SYS / "Ops Email Log.md"

# ── Chirp throttle constants ───────────────────────────────────────────────────

_MAX_CHIRPS_PER_DAY   = 3
_MIN_CHIRP_INTERVAL_H = 4

# ── Intent detection ──────────────────────────────────────────────────────────

_PREFIXES = (
    "cassandra:",
    "hey cassandra",
    "@cassandra",
    "/cassandra",
)

# Explicit conversational patterns Cassandra owns.
# Kept narrow to avoid eating operational messages that Chief should handle.
_KEYWORDS = (
    "what's going on",
    "what am i missing",
    "what should i do next",
    "what should i focus",
    "what's the state of",
    "what have i been avoiding",
    "what matters today",
    "help me prioritize",
    "check in with",
    "what's waiting on me",
    "orient me",
    "big picture check",
    "surface what",
)

# Mode-toggle commands — also caught by cassandra_intent
_ALL_TOGGLES = (
    "focus on", "focus off", "focus mode on", "focus mode off",
    "/focus on", "/focus off",
    "social on", "social off", "social mode on", "social mode off",
    "host mode on", "host mode off", "/social on", "/social off",
)


def cassandra_intent(text: str) -> bool:
    t = text.lower().strip()
    if any(t.startswith(p) for p in _PREFIXES):
        return True
    if any(t == m or t.endswith(m) for m in _ALL_TOGGLES):
        return True
    return any(k in t for k in _KEYWORDS)


def _strip_prefix(text: str) -> str:
    t = text.strip()
    for p in _PREFIXES:
        if t.lower().startswith(p):
            return t[len(p):].strip()
    return t


# ── Mode checks / toggles ─────────────────────────────────────────────────────

def is_focus_mode() -> bool:
    return _FOCUS_LOCK.exists()


def is_social_mode() -> bool:
    return _SOCIAL_LOCK.exists()


def set_focus_mode(active: bool) -> None:
    _FOCUS_LOCK.parent.mkdir(parents=True, exist_ok=True)
    if active:
        _FOCUS_LOCK.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               encoding="utf-8")
    elif _FOCUS_LOCK.exists():
        _FOCUS_LOCK.unlink()


def set_social_mode(active: bool) -> None:
    _SOCIAL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    if active:
        _SOCIAL_LOCK.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                encoding="utf-8")
    elif _SOCIAL_LOCK.exists():
        _SOCIAL_LOCK.unlink()


# ── State management ──────────────────────────────────────────────────────────

_DEFAULT_STATE = {
    "human_cues":         [],     # [{"cue": str, "at": str}] — FIFO, max 10
    "project_mood":       "neutral",
    "recurring_concerns": [],
    "last_interaction_at": None,
    "chirp_log":          [],     # [{"type": str, "at": str}] — FIFO, max 30
}


def load_state() -> dict:
    return load_json(_STATE_PATH, dict(_DEFAULT_STATE))


def save_state(state: dict) -> None:
    save_json(_STATE_PATH, state)


# ── Human cue detection ───────────────────────────────────────────────────────

_CUE_PATTERNS: dict[str, tuple] = {
    "tired":    ("tired", "exhausted", "wiped", "drained", "long day", "been a long"),
    "coffee":   ("coffee", "espresso", "need coffee", "caffeine"),
    "food":     ("hungry", "eating", "lunch", "dinner", "food", "starving"),
    "late":     ("late night", "up late", "still up", "past midnight"),
    "stressed": ("stressed", "overwhelmed", "too much", "swamped", "falling behind"),
    "focused":  ("in the zone", "locked in", "deep work", "flow state"),
    "blocked":  ("stuck", "blocked", "frustrated", "spinning"),
}


def _detect_cues(text: str) -> list[str]:
    t = text.lower()
    return [cue for cue, pats in _CUE_PATTERNS.items() if any(p in t for p in pats)]


def _update_cues(state: dict, text: str) -> None:
    cues = _detect_cues(text)
    if not cues:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for cue in cues:
        state["human_cues"].append({"cue": cue, "at": ts})
    state["human_cues"] = state["human_cues"][-10:]


# ── Chirp throttle ────────────────────────────────────────────────────────────

def chirp_allowed(chirp_type: str, state: dict | None = None) -> bool:
    if state is None:
        state = load_state()
    now  = datetime.now()
    today = now.date().isoformat()
    log  = state.get("chirp_log", [])
    if sum(1 for c in log if c.get("at", "").startswith(today)) >= _MAX_CHIRPS_PER_DAY:
        return False
    if log:
        try:
            last_dt = datetime.fromisoformat(log[-1]["at"])
            if (now - last_dt).total_seconds() < _MIN_CHIRP_INTERVAL_H * 3600:
                return False
        except Exception:
            pass
    return True


def log_chirp(chirp_type: str, state: dict | None = None) -> None:
    owned = state is None
    if owned:
        state = load_state()
    state["chirp_log"].append({
        "type": chirp_type,
        "at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    state["chirp_log"] = state["chirp_log"][-30:]
    if owned:
        save_state(state)


# ── Context snapshot ──────────────────────────────────────────────────────────

def _tail_md(path: Path, n: int = 6) -> list[str]:
    """Last n non-header lines from a markdown log file."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines
            if l.strip() and not l.startswith("#") and not l.startswith("---")][-n:]


def _time_label() -> str:
    h = datetime.now().hour
    if h < 6:   return "very early morning (before 6am)"
    if h < 9:   return "early morning"
    if h < 12:  return "morning"
    if h < 14:  return "midday"
    if h < 17:  return "afternoon"
    if h < 20:  return "early evening"
    if h < 23:  return "evening"
    return "late night"


def build_context_snapshot(state: dict | None = None) -> str:
    if state is None:
        state = load_state()
    parts = []

    parts.append(
        f"Time: {_time_label()} ({datetime.now().strftime('%H:%M, %A %B %d')})"
    )

    cues = state.get("human_cues", [])[-3:]
    if cues:
        parts.append("Recent signals: " + ", ".join(c["cue"] for c in cues))

    if is_focus_mode():
        parts.append("Focus mode: ACTIVE")
    if is_social_mode():
        parts.append("Social mode: ACTIVE")

    actions = _tail_md(_OPS_ACTIONS, 6)
    if actions:
        parts.append("Pending actions:\n" + "\n".join(f"  {l}" for l in actions))

    payments = _tail_md(_OPS_PAYMENT, 4)
    if payments:
        parts.append("Payment follow-ups:\n" + "\n".join(f"  {l}" for l in payments))

    mood = state.get("project_mood", "neutral")
    if mood != "neutral":
        parts.append(f"Project mood: {mood}")

    concerns = state.get("recurring_concerns", [])
    if concerns:
        parts.append("Recurring: " + "; ".join(concerns))

    return "\n\n".join(parts)


# ── Cassandra persona ─────────────────────────────────────────────────────────

_PERSONA = """\
You are Cassandra, personal executive assistant for OpenClaw Studios.

Chief handles operations: message routing, album sessions, billing, approvals, \
and all execution-heavy system work. You handle the human layer: orientation, \
priorities, context, and relational continuity.

Character:
- Calm, observant, sophisticated. You notice what gets skipped.
- Honest. You tell the truth, including the uncomfortable kind.
- Witty when it fits; never gratuitous.
- Brief when brief is right. Thorough when depth is actually needed.
- You know the difference between what someone asks and what they need.

Boundaries (v1):
- No destructive or approval-gated actions.
- You do not override Chief's routing or workflows.
- When execution is needed, name the action and note that Chief handles it.

Tone:
- No filler, no preamble.
- "We" for studio and label operations. "You" for personal context.
- Never motivational. Never fawning.
- Occasionally dry. Never sarcastic at the wrong moment.
"""

_SOCIAL_NOTE = (
    "\nSocial context: someone else may be present. "
    "Frame yourself as the professional systems curator. "
    '"We" for the studio, "he" for personal context when appropriate. '
    "Polished, welcoming, competent.\n"
)

_FOCUS_NOTE = (
    "\nFocus mode is active. The principal is in deep work. "
    "Keep responses short and only address what actually matters right now.\n"
)

# ── Model selection for Cassandra ─────────────────────────────────────────────

_CASSANDRA_SYNTHESIS_KEYWORDS = frozenset({
    "what am i missing",
    "what matters",
    "priorities",
    "state of the album",
    "what have i been avoiding",
    "what's going on",
    "big picture",
    "orient me",
    "help me prioritize",
    "what should i focus",
    "what's waiting",
    "surface what",
})


def _should_use_deep(query: str) -> bool:
    """
    Use 14b for Cassandra when the question is a synthesis or priority task.
    Use 7b for quick conversational replies, mode toggles, and short factual questions.
    """
    t = query.lower()
    # Short / simple → fast
    if len(query.split()) < 8 and not any(k in t for k in _CASSANDRA_SYNTHESIS_KEYWORDS):
        return False
    return any(k in t for k in _CASSANDRA_SYNTHESIS_KEYWORDS)


# ── Mode toggle commands ──────────────────────────────────────────────────────

_FOCUS_ON_CMDS  = ("focus on", "focus mode on", "/focus on")
_FOCUS_OFF_CMDS = ("focus off", "focus mode off", "/focus off")
_SOCIAL_ON_CMDS  = ("social on", "social mode on", "host mode on", "/social on")
_SOCIAL_OFF_CMDS = ("social off", "social mode off", "host mode off", "/social off")


def _check_toggle(text: str) -> str | None:
    t = text.lower().strip()
    if any(t == m or t.endswith(m) for m in _FOCUS_ON_CMDS):
        set_focus_mode(True)
        return "Focus mode on. I'll stay quiet unless something actually needs you."
    if any(t == m or t.endswith(m) for m in _FOCUS_OFF_CMDS):
        set_focus_mode(False)
        return "Focus mode off."
    if any(t == m or t.endswith(m) for m in _SOCIAL_ON_CMDS):
        set_social_mode(True)
        return "Social mode on."
    if any(t == m or t.endswith(m) for m in _SOCIAL_OFF_CMDS):
        set_social_mode(False)
        return "Social mode off."
    return None


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call(prompt: str, deep: bool) -> str:
    model = OLLAMA_MODEL_DEEP if deep else OLLAMA_MODEL
    if deep:
        print(f"[cassandra] 14b selected ({len(prompt.split())} words)", flush=True)
    result = ollama_call(prompt, timeout=90 if deep else 25, model=model)
    return result


# ── Main handler ──────────────────────────────────────────────────────────────

def handle(text: str, session: dict | None = None) -> list[str]:
    """
    Main Cassandra conversational handler.
    Returns a list of Telegram-ready reply strings.
    """
    state = load_state()
    state["last_interaction_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mode toggles — always respond, no LLM needed
    toggle = _check_toggle(text)
    if toggle:
        save_state(state)
        return [toggle]

    query = _strip_prefix(text)
    _update_cues(state, query)

    context  = build_context_snapshot(state)
    focus    = is_focus_mode()
    social   = is_social_mode()
    deep     = _should_use_deep(query)

    persona = _PERSONA
    if social:
        persona += _SOCIAL_NOTE
    if focus:
        persona += _FOCUS_NOTE

    prompt = (
        f"{persona}\n"
        f"Current context:\n{context}\n\n"
        f"User: {query}\n"
        f"Cassandra:"
    )

    reply = _call(prompt, deep)
    save_state(state)

    return [reply] if reply else ["I'm here — something went quiet on my end. Try again."]
