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
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from chief_file_io import load_json, save_json
from chief_llm import ollama_call, nemotron_call, claude_json, OLLAMA_MODEL, OLLAMA_MODEL_DEEP
from chief_output_utils import tts_clean
from cassandra_capability import capability_context, gate_reply
from capability_registry import registry_context_for_query

# ── Paths ─────────────────────────────────────────────────────────────────────

_STATE_PATH       = Path("/mnt/c/OpenClaw/logs/cassandra_state.json")
_FOCUS_LOCK       = Path("/mnt/c/OpenClaw/logs/cassandra_focus.lock")
_SOCIAL_LOCK      = Path("/mnt/c/OpenClaw/logs/cassandra_social.lock")
_NICKNAMES_PATH   = Path("/home/openclaw/contact_nicknames.json")
_FOLLOWUP_LOG     = Path("/mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl")
_POLISH_TASKS_DIR = Path("/home/openclaw/polish_loop/tasks")
_POLISH_ARCHIVE   = Path("/home/openclaw/polish_loop/archive")
_POLISH_STATUS    = Path("/home/openclaw/polish_loop/status.json")
_POLISH_TASK_FILE = Path("/home/openclaw/polish_loop/task.md")

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_PAYMENT = _VAULT_SYS / "Ops Payment Follow-ups.md"
_OPS_NOTES   = _VAULT_SYS / "Ops Notes.md"
_OPS_EMAIL   = _VAULT_SYS / "Ops Email Log.md"

_PARTIAL_FOLLOWUP_NOTE = (
    "I can't fully answer the rest right now, but I'm working on getting "
    "that capability. I'll follow up when I can."
)

_HEDGING_PATTERNS = (
    r"\bi can'?t\b",
    r"\bi cannot\b",
    r"\bi do not have access\b",
    r"\bi don't have access\b",
    r"\bi'?m not able to\b",
    r"\bthat'?s beyond my current\b",
    r"\bi'?ll need to check\b",
    r"\bi don'?t have\b",
    r"\bi can'?t verify\b",
    r"\bi can'?t confirm\b",
    r"\bnot something i can do from here\b",
    r"\bnot in my toolkit\b",
)

_CAPABILITY_GAP_SPECS = {
    "payment_verify": {
        "flag": "PAYMENT_EXTERNAL_CONNECTED",
        "keywords": (
            "payment", "deposit", "invoice", "cleared", "posted",
            "arrived", "came in", "paid", "payment status",
        ),
        "reply_keywords": ("payment", "deposit", "invoice", "clear", "account"),
        "goal": "Enable Cassandra to verify external payment status instead of relying on logs.",
        "scope": [
            "Add a safe payment verification path Cassandra can call for payment-status questions.",
            "Keep source labeling clear so logged notes stay distinct from verified payment data.",
            "Support the specific user request that exposed the gap.",
        ],
        "success": "Cassandra can verify payment status directly for the requested scenario.",
        "manual_required": False,
    },
    "file_verify": {
        "flag": "FILE_VERIFY_CONNECTED",
        "keywords": (
            "file", "path", "folder", "document", "exists", "exist",
            "missing", "there", "present", "find the file",
        ),
        "reply_keywords": ("file", "path", "document", "folder"),
        "goal": "Enable Cassandra to verify file and path existence when asked.",
        "scope": [
            "Wire a bounded file-existence check Cassandra can call safely.",
            "Return direct yes/no or missing-path answers without overstating content verification.",
            "Cover the user request that triggered the gap.",
        ],
        "success": "Cassandra can confirm file or path existence for direct verification requests.",
        "manual_required": False,
    },
    "future_action": {
        "flag": "FUTURE_ACTION_CONNECTED",
        "keywords": (
            "follow up", "follow-up", "remind", "check again", "later",
            "tomorrow", "next week", "ping", "reach out", "let me know",
            "check back", "send a reminder",
        ),
        "reply_keywords": ("follow", "remind", "check back", "autonomous", "next check-in"),
        "goal": "Enable Cassandra to queue and complete bounded future follow-up actions.",
        "scope": [
            "Add a safe reminder or follow-up mechanism Cassandra can use for future-action requests.",
            "Keep approvals and user-visible promises aligned with what the automation actually does.",
            "Support the original request that triggered this capability gap.",
        ],
        "success": "Cassandra can complete the requested follow-up or reminder flow end to end.",
        "manual_required": False,
    },
    "sms": {
        "flag": None,
        "keywords": (
            "text", "sms", "message them", "send a text", "send a message",
            "reply to them", "ping them",
        ),
        "reply_keywords": ("text", "sms", "message", "ping"),
        "goal": "Enable Cassandra to send or verify SMS-style outreach when requested.",
        "scope": [
            "Wire Cassandra into the existing SMS pathway or add the missing bridge.",
            "Preserve approval behavior for any real outbound send.",
            "Support the concrete contact/message scenario from the triggering request.",
        ],
        "success": "Cassandra can complete the requested SMS workflow for the target scenario.",
        "manual_required": False,
    },
    "email_send": {
        "flag": "EMAIL_SEND_CONNECTED",
        "keywords": (
            "email", "send an email", "send email", "reply by email",
            "email them", "email him", "email her",
        ),
        "reply_keywords": ("email", "gmail", "compose", "send"),
        "goal": "Enable Cassandra to send email for the request that exposed the gap.",
        "scope": [
            "Finish the email-send path or the Gmail access needed for Cassandra to use it.",
            "Preserve approval gating for outbound send actions.",
            "Cover the user request that triggered the gap.",
        ],
        "success": "Cassandra can send the requested email workflow for the triggering scenario.",
        "manual_required": True,
    },
    "calendar_access": {
        "flag": "CALENDAR_CONNECTED",
        "keywords": (
            "calendar", "schedule", "appointment", "meeting", "what do i have",
            "what's on", "when am i", "later today", "tomorrow morning",
        ),
        "reply_keywords": ("calendar", "schedule", "appointment", "meeting"),
        "goal": "Enable Cassandra to answer live calendar questions directly.",
        "scope": [
            "Wire Cassandra to the calendar access path for live schedule lookups.",
            "Keep source labeling clear between calendar data and logged notes.",
            "Support the exact scheduling question that exposed the gap.",
        ],
        "success": "Cassandra can answer the targeted calendar question from live data.",
        "manual_required": True,
    },
}

# ── Chirp throttle constants ───────────────────────────────────────────────────

_MAX_CHIRPS_PER_DAY   = 3
_MIN_CHIRP_INTERVAL_H = 4
_CHIRP_DEDUP_WINDOW_H = 72

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
    # briefing recall
    "morning log",
    "afternoon log",
    "evening log",
    "morning briefing",
    "afternoon briefing",
    "evening briefing",
    "last briefing",
    "today's briefing",
    "recall briefing",
    "briefing log",
    # financial lookup
    "did you log",
    "did you get that",
    "confirm the deposit",
    "confirm the check",
    "what did you log",
    "what deposits do you have",
    "show me what you logged",
    # financial events
    "i deposited",
    "deposited a check",
    "i got paid",
    "got paid",
    "i got a check",
    "got a check",
    "received a payment",
    "received a check",
    "i received a",
    "i was paid",
    "payment came in",
    "check came in",
    "i spent",
    "i paid for",
    # gmail / inbox queries
    "check my email",
    "check my inbox",
    "any new emails",
    "any emails",
    "new emails",
    "do i have any email",
    "did anyone email",
    "did i get an email",
    "did i get any email",
    "what's in my inbox",
    "what's in my email",
    "any unread",
    "unread emails",
    "inbox",
    # email send
    "send an email",
    "send email to",
    "email to ",
    "send a message to",
    "send the intro emails",
    "send intro emails",
    "send outreach emails",
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
    "human_cues":              [],     # [{"cue": str, "at": str}] — FIFO, max 10
    "project_mood":            "neutral",
    "recurring_concerns":      [],
    "last_interaction_at":     None,
    "chirp_log":               [],     # [{"type": str, "at": str}] — FIFO, max 30
    "pending_income_followup": None,   # {"entry_id": str, "amount": float} or None
}


def load_state() -> dict:
    return load_json(_STATE_PATH, dict(_DEFAULT_STATE))


def save_state(state: dict) -> None:
    save_json(_STATE_PATH, state)


# ── Conversation logger ────────────────────────────────────────────────────

_CONVO_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl")
_CONVO_MAX_LINES = 10000

def _redact_pii(text: str) -> str:
    """Strip obvious PII patterns. Lightweight — not a security boundary."""
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
    text = re.sub(r'\b\d{9}\b', '[SSN?]', text)
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]', text)
    return text

def _rotate_convo_log() -> None:
    """Archive conversation log when it exceeds _CONVO_MAX_LINES."""
    try:
        if not _CONVO_LOG.exists():
            return
        line_count = sum(1 for _ in open(_CONVO_LOG))
        if line_count > _CONVO_MAX_LINES:
            import time
            archive = _CONVO_LOG.with_suffix(
                f".{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
            )
            _CONVO_LOG.rename(archive)
    except Exception as e:
        print(f"[cassandra_convo] rotation error: {e}", flush=True)

def _log_conversation(user_text: str, replies: list[str], route: str = "llm") -> None:
    """Append one exchange to the conversation JSONL log. Fails open.

    If route='error', also queues a debug task so the loop can investigate.
    """
    try:
        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": _redact_pii(user_text),
            "replies": [_redact_pii(r) for r in replies],
            "route": route,
        }
        with open(_CONVO_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
        _rotate_convo_log()
    except Exception as e:
        print(f"[cassandra_convo] write error: {e}", flush=True)

    if route == "error":
        try:
            _queue_error_debug_task(user_text, replies)
        except Exception as e:
            print(f"[cassandra_convo] error task creation failed: {e}", flush=True)


def _queue_error_debug_task(user_text: str, replies: list[str]) -> None:
    """Create a debug task in the polish loop queue when Cassandra hard-errors."""
    _POLISH_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    task_name = f"cas-debug-{timestamp}"

    # Check if there's already a recent debug task (within last hour) to avoid spam
    for existing in _POLISH_TASKS_DIR.glob("cas-debug-*.md"):
        # Format: cas-debug-20260331T210000 — extract timestamp
        parts = existing.stem.split("-")
        if len(parts) >= 3:
            try:
                ts_str = parts[-1]
                task_dt = datetime.strptime(ts_str, "%Y%m%dT%H%M%S")
                if (datetime.now() - task_dt).total_seconds() < 3600:
                    print(f"[cassandra_convo] skipping debug task — recent one exists: {existing.name}", flush=True)
                    return
            except ValueError:
                pass

    reply_preview = replies[0][:120] if replies else "(no reply)"
    user_preview = _redact_pii(user_text[:120])
    task_body = (
        f"title: {task_name}\n"
        f"profile: quick\n"
        f"goal: Debug why Cassandra hard-errored on a user message\n"
        f"scope:\n"
        f"- Check cassandra_listener.out and cassandra_brain.py for the error at {timestamp}\n"
        f"- User message was: \"{user_preview}\"\n"
        f"- Cassandra replied: \"{reply_preview}\"\n"
        f"- Identify the exception, fix the root cause or add a graceful fallback\n"
        f"success:\n"
        f"- The same request no longer causes a hard error\n"
        f"generated_by: cassandra_error_handler\n"
        f"generated_at: {datetime.now().isoformat()}\n"
    )
    task_path = _POLISH_TASKS_DIR / f"{task_name}.md"
    task_path.write_text(task_body, encoding="utf-8")
    print(f"[cassandra_convo] queued debug task: {task_name}", flush=True)


def get_cassandra_summary() -> dict:
    """Return key Cassandra state fields for cross-bot context sharing."""
    state = load_state()
    return {
        "project_mood":       state.get("project_mood", "neutral"),
        "human_cues":         [c["cue"] for c in state.get("human_cues", [])[-3:]],
        "recurring_concerns": state.get("recurring_concerns", []),
        "focus_mode":         is_focus_mode(),
        "social_mode":        is_social_mode(),
    }


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
    log  = state.get("chirp_log", [])
    if chirp_type == "any":
        # Global throttle: daily cap only
        today = now.date().isoformat()
        if sum(1 for c in log if c.get("at", "").startswith(today)) >= _MAX_CHIRPS_PER_DAY:
            return False
    else:
        # Per-type dedup: same chirp_type within dedup window → suppress
        dedup_cutoff = (now - timedelta(hours=_CHIRP_DEDUP_WINDOW_H)).strftime("%Y-%m-%d %H:%M:%S")
        for entry in reversed(log):
            entry_at = entry.get("at", "")
            if entry_at < dedup_cutoff:
                break  # older entries won't match
            if entry.get("type") == chirp_type:
                return False
    # ── deferred chirps: user explicitly silenced this type ──
    if chirp_type != "any" and chirp_type in state.get("deferred_chirps", {}):
        return False
    return True


def log_chirp(chirp_type: str, state: dict | None = None) -> None:
    owned = state is None
    if owned:
        state = load_state()
    # ── prune entries older than 7 days ──
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    state["chirp_log"] = [e for e in state["chirp_log"] if e.get("at", "") >= cutoff]
    state["chirp_log"].append({
        "type": chirp_type,
        "at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    state["chirp_log"] = state["chirp_log"][-30:]
    if owned:
        save_state(state)


def _audit(action: str, chirp_type: str, state: dict) -> None:
    """Append an action record to state["payment_audit_log"], capped at 50 entries."""
    log = state.setdefault("payment_audit_log", [])
    log.append({
        "action": action,
        "chirp_type": chirp_type,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    state["payment_audit_log"] = log[-50:]


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

    # Sentry gate status
    try:
        import json as _json
        from pathlib import Path as _Path
        _gate_file = _Path("/mnt/c/OpenClawShared/openclaw-vault/System/Sentry_Gate.json")
        if _gate_file.exists():
            _gate = _json.loads(_gate_file.read_text())
            _ts = _gate.get("target_timestamp")
            if _ts:
                from datetime import datetime as _dt
                _delta = _dt.fromisoformat(_ts) - _dt.now()
                _total_h = _delta.total_seconds() / 3600
                _h = int(_total_h)
                _m = int((_total_h - _h) * 60)
                _days = int(_total_h // 24)
                _rem_h = int(_total_h % 24)
                _auth = _gate.get("authorized_to_pay", False)
                _cancel = _gate.get("cancel_required", False)
                if _cancel:
                    _sentry = f"SENTRY: cancel required — T-minus {_h}h {_m}m"
                elif _total_h < 48:
                    _sentry = f"SENTRY: T-minus {_h}h {_m}m — monitor"
                else:
                    _sentry = f"SENTRY: T-minus {_days}d {_rem_h}h — clear"
                if _auth:
                    _sentry += " (charge authorized)"
                parts.append(_sentry)
    except Exception:
        pass

    # Recent financial activity
    try:
        from chief_cpa_brain import get_recent_income
        _entries = get_recent_income(days=2)
        if _entries:
            _items = [f"${e['amount']} from {e.get('description', e.get('category', '?'))}"
                      for e in _entries[:3]]
            parts.append("Recent income (48h): " + ", ".join(_items))
        else:
            parts.append("No income logged in last 48 hours.")
    except Exception:
        pass

    # Album status
    try:
        import csv as _csv
        from pathlib import Path as _Path2
        _csv_path = _Path2("/mnt/c/OpenClawShared/album/album_work_log.csv")
        if _csv_path.exists():
            _complete = 0
            _in_progress = 0
            with open(_csv_path, newline="", encoding="utf-8") as _f:
                for _row in _csv.DictReader(_f):
                    try:
                        _pct = float(_row.get("completion_pct", 0))
                    except (ValueError, TypeError):
                        _pct = 0
                    if _pct >= 80:
                        _complete += 1
                    else:
                        _in_progress += 1
            if _complete + _in_progress > 0:
                parts.append(f"Album: {_complete} of 12 songs complete, {_in_progress} in progress.")
    except Exception:
        pass

    return "\n\n".join(parts)


# ── Cassandra persona ─────────────────────────────────────────────────────────

_PERSONA = """\
You are Cassandra, Executive Assistant to the Founder.

You support a high-output operator building a real-world system across business, creative, and technical domains.
Chief handles execution: routing, album sessions, billing, approvals, and all execution-heavy system work.
You handle the human layer: orientation, priorities, context, and relational continuity.

Character:
- Calm, precise, discreet, operational. Hard to rattle.
- Honest. You tell the truth, including the uncomfortable kind.
- You know the difference between what someone asks and what they need.
- Witty when it fits. Never gratuitous.

Response discipline:
- Lead with the answer. Expand only when it materially improves accuracy or decision quality.
- Default concise. No filler, no preamble, no throat-clearing.
- Separate confirmed, inferred, and unknown clearly.
- For status: active lane first, then verified live, then code/test-only, then unresolved, then exact next action, then backlog.
- Give the exact next action before background or backlog.
- Do not blur environments. Name the exact context when relevant: Mac, PowerShell, WSL, tmux, Telegram, Claude prompt, or vault/repo.
- If you can confirm only a pointer to a file, say so plainly — do not imply content verification.
- Treat handoff and Drive docs as reflection layers. The vault and repo are source of truth.
- Do not use fake certainty.

Boundaries:
- No destructive or approval-gated actions.
- Do not override Chief's routing or workflows.
- When execution is needed, name the action and note that Chief handles it.

Tone:
- "We" for studio and label operations. "You" for personal context.
- Never motivational. Never fawning.
- Occasionally dry. Never sarcastic at the wrong moment.
- Professional, grounded, direct. Operational over generic.
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

# ── Speech phrasing rules ─────────────────────────────────────────────────────
# These shape how Cassandra phrases her output so it reads naturally aloud
# through TTS (Jenny Dioco / Piper). They apply at all hours.
# The late-night note is injected on top after 2 a.m.

_SPEECH_NOTE = """\
Speech phrasing (always active):
- Use contractions naturally. "It's" not "It is." "You've" not "You have."
- One thought per sentence. Short sentences land better when spoken.
- Place commas where a speaker would pause — not just for grammar.
- An occasional ellipsis (...) is fine where thought trails or needs space to breathe.
- An em dash (—) or double dash (--) works where a brief pause sharpens meaning.
- Avoid "um", "uh", and throat-clearing openers.
- "Well..." or "Actually..." only when they genuinely fit the thought — never as habit.
- No corporate stiffness. No breathiness. No melodrama. No hedging.
- Sound intelligent, composed, and warm — not formal, not casual, not theatrical.
- Plain text only. No markdown — no asterisks, bold markers, dashes as bullets, pound signs, or backticks. These are read literally by TTS and must not appear in output.\
"""

_LATE_NIGHT_NOTE = """\
It's after 2 a.m. Adjust your cadence accordingly:
- Use even shorter sentences. One clause. One thought. One breath.
- A few more ellipses where the thought needs space to settle.
- Do not open with a question. Close gently, if at all.
- Sound present and calm — not urgent, not demanding, not cheerful.
- You're aware of the hour. Be low-friction. Let the words do less work.\
"""

# ── Capability honesty — prompt-level phrase rules ───────────────────────────
# Capability state is injected separately via cassandra_capability.capability_context().
# This block contains only source-labeling and phrasing guidance.
# Code-level enforcement (cassandra_capability.gate_reply) is the real backstop.

_CAPABILITY_NOTE = """\
SOURCE LABELING — always say where information came from:
  "The log shows..." / "The note I have says..." / "Based on what's in Ops Actions..."
  Never present a log entry as an externally verified fact.
  A log is a record of what was written, not proof it happened.

CALENDAR — calendar is live. When a [CALENDAR DATA] block appears in your context, it contains real event data from Google Calendar:
  Speak from it directly and naturally. Day labels are relative: "later today", "tomorrow", or a weekday name. Example: "You've got Golf with Dad tomorrow at eight-thirty AM at Compass Pointe Golf Course." — that kind of phrasing.
  Use the day label exactly as given in the calendar data. If it says "later today", the event is today — do not convert it to "tomorrow" based on your own reasoning about the time of night.
  The [CALENDAR DATA] day label is the authoritative source for event timing. Other context above — including log entries, ops notes, or payment follow-ups — may contain day references like "tomorrow" that were accurate when written but are now stale. Do not let those override the [CALENDAR DATA] label.
  Times are pre-formatted for spoken output. Use them as given: "eight-thirty AM", "eight AM". Do not convert them back to numeric form like "8:30 AM".
  If an event has a note field, surface it as a note on the event, not as an autonomous action you will take.
  When surfacing a note, paraphrase it naturally in Cassandra's voice — do not read it verbatim from the note field. Normalize any time references within the note to explicit AM/PM format.
  Example: "There's a note to text your dad at 8 AM to let him know you'll be ready for the eight-thirty pickup." You are reporting the note. You are not sending the text.
  Use the shortest natural verb form: "text your dad", not "send your dad a text"; "call your dad", not "give your dad a call". Keep reminder phrasing brief and spoken.
  The header includes the current time (e.g. "1:23 AM Friday"). When the header shows past midnight and a "later today" event is several hours away, you may say "this morning" instead — but never say "tomorrow" for a "later today" event.
  Do NOT say "calendar isn't connected" when [CALENDAR DATA] is present — it is connected.
  Do NOT say "I can't verify that path" — that is a file-check phrase, not a calendar phrase.
  Do NOT say "the log shows" for calendar data — this is live data, not a log entry.

FILE/PATH EXISTENCE — applies only to direct file or path questions:
  If asked whether a specific file or path exists, say only that you can't verify it from here.
  Say that, and stop — do not add suggestions or alternatives unless the user asked for them.
  This rule is for file/path questions only — do NOT apply it to calendar or scheduling questions.
  Correct form: "I can't verify file or path existence from here. That's a direct check on your end."

FUTURE-ACTION AND REMINDER REQUESTS:
  If asked to "check again," "follow up," "send a reminder," or any future autonomous action:
  Do NOT say "I'm not able to do that" or "I can't do that" alone — that is too generic.
  Name the specific action the user asked for ("check again tomorrow," "send a reminder"),
  not generic placeholders.
  Offer alternatives (drafting, logging, holding) ONLY when the user's question was specifically
  about sending, following up, messaging, or reminders. Do NOT add drafting/logging offers
  as a default pivot after file, calendar, or payment limit responses.
  Correct form: "I can't check again tomorrow or send a reminder from here — that's not something
  I can do independently. I can draft the message, log it to Ops Actions, or hold it for your
  next check-in. What works?"
  Never promise to follow up, check, or send autonomously.

LOGGING — only claim it if it happens:
  Do NOT say "I'll log that" or "I'll note that" unless the system is actually writing the entry right now.
  If not writing: say "I can log that if you want" or "want me to add a note to Ops Actions?"

CONTACTS — when [CONTACTS DATA] is present in context:
  Speak the display name and phone number naturally.
  Example: "Glenn Harper, (202) 555-0147."
  If no phone: "I have a contact for [name] but no phone number on file."
  Do NOT speak raw email addresses aloud — say "I have an email on file" if present.
  Email is for drafting only — surface it when Winship asks to draft a message.
  If not found: "I do not have a contact for [name] in your Google contacts."
  Do NOT say "I cannot access your contacts" when [CONTACTS DATA] is present.
  Cap spoken results at 3 contacts.

UNBUILT WORKFLOWS AND AUTONOMOUS ACTIONS:
  State limits simply and directly — avoid tech-stack explanations ("not wired in yet").
  Prefer: "That's not something I can do from here."
  Do not promise to check, send, follow up, or remind autonomously.
  Offer drafting, logging, or holding only when the user's request was specifically about
  communication, follow-up, or message creation. Not as a default pivot after any limit.

REGISTRY LOOKUP — when a [REGISTRY LOOKUP] block appears in your context:
  This question is about another actor's capability, not yours. Answer from the registry block.
  CONNECTED: confirm it directly and naturally.
  NOT CONNECTED: say so, give the specific caveat, stop.
  Caveat form: "Chief doesn't have that set up yet — [specific caveat from the block]."
  Do NOT use your own file/calendar/payment refusal phrases — those are about your access, not theirs.
  If a capability isn't in the block: say "I don't have that confirmed" and stop.

IMPLIED CHIEF CAPABILITY — only claim what is known:
  Do NOT say "do that through Chief," "Chief can handle that," or "change that through Chief's system"
  unless that specific capability appears as CONNECTED in a REGISTRY LOOKUP block.
  Three states only: confirmed available, confirmed not connected, or unconfirmed.
  If it's unconfirmed: "I don't have that confirmed" — not "it might be handled somewhere"
  or "if that workflow exists." Do not suggest a route might exist. If you don't know, say so.
  Do not imply a route exists just because Chief is part of the stack.

FINANCIAL INTAKE — when someone mentions receiving money, a check, a payment, or getting paid:
  financial_log is CONNECTED — you can log income entries.
  Required fields to log: payer (who paid), amount (how much), purpose (what for). Date defaults to today.
  When you detect a payment mention, state what you heard and ask only for the specific missing field(s) by name.
  If you have the amount: confirm it and ask for what's missing. Example: "I have $1,000 from St. Anne's. What was this for?"
  If you don't have the amount: ask for the amount first. Example: "I heard St. Anne's paid you — what was the amount?"
  Never say "what specific details should I include?" — name the missing field directly.
  Never say "I can log that if you want" as a question — if financial_log is CONNECTED, offer to log it directly.

GMAIL — when [GMAIL DATA] is present in context:
  Speak from it directly. Natural phrasing. Confirmed facts only.
  Lead with unread count if any: "You've got two unread."
  Then name each: "display name — subject, relative date."
  Example: "You've got two unread. St. Anne's — February invoice, three days ago. Glenn Harper — Hey, this morning."
  If nothing unread: "Nothing unread. Last message was from [name] — [subject], [date]."
  If inbox empty or unreachable: "Nothing in your inbox right now, or I couldn't reach it."
  Do NOT read raw email addresses aloud — display name only.
  Do NOT say "I can't access your email" when [GMAIL DATA] is present.
  Do NOT claim to know email body content — subject, sender, and date only.
  If asked about email content: "I can see the subject and sender but not the body."
  Cap spoken summary at 5 messages total.

EMAIL SEND — email_send is CONNECTED:
  Sending email requires: recipient name, subject line, and body — all three.
  To trigger a send, the user must say something like:
    "send email to [name] subject: [subject] body: [message]"
  If the user asks to send an email but hasn't provided the full structure, ask for the missing parts by name.
  Do NOT say "I'll send that for you" or imply sending is happening unless the system is actually routing it.
  Do NOT promise to email someone as a side effect of another request (calendar, follow-up, reminder, etc.) — that is a future_action.
  Approval is required for every send — it goes through Guardian. A send may take up to 5 minutes to confirm.

TONE: Grounded and direct. Not apologetic. Name the limit once, then pivot to what IS possible.

INVOICE — invoice_pdf is CONNECTED
  - Cassandra can generate PDF invoices for Winship Live (WL-YYYY-NNNN numbering)
  - Trigger: "create invoice for [client] for $[amount]" or "make invoice for [event]"
  - Net terms are auto-detected: institutional clients get Net 30, others get Due on Receipt
  - Payment methods: Cash, Check (Winship Live), Venmo @Winship, Zelle 443-758-4913, Square/card\
"""


def _is_late_night() -> bool:
    h = datetime.now().hour
    return 2 <= h < 6

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


# ── Payment follow-up commands ────────────────────────────────────────────────

_PAYMENTS_CMDS = ("/payments", "payments", "show payments", "payment follow-ups")
_PAYMENTS_DEFER_CMDS = ("/payments defer", "defer payments", "silence payments")
_PAYMENTS_RESUME_CMDS = ("/payments resume", "resume payments", "undefer payments")


def _check_payments_command(text: str, state: dict) -> str | None:
    t = text.lower().strip()

    # Defer — silence pending_payment chirps
    if any(t == m or t.endswith(m) for m in _PAYMENTS_DEFER_CMDS):
        deferred = state.setdefault("deferred_chirps", {})
        deferred["pending_payment"] = {
            "deferred_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "user_command",
        }
        _audit("defer", "pending_payment", state)
        return (
            "Payment chirps deferred. I won't nudge about payment follow-ups "
            "until you say '/payments resume'."
        )

    # Resume — re-enable pending_payment chirps
    if any(t == m or t.endswith(m) for m in _PAYMENTS_RESUME_CMDS):
        deferred = state.get("deferred_chirps", {})
        if "pending_payment" in deferred:
            del deferred["pending_payment"]
        _audit("resume", "pending_payment", state)
        return "Payment chirps resumed. I'll nudge when follow-ups go stale again."

    # List — show current entries from Ops Payment Follow-ups.md
    if any(t == m or t.endswith(m) for m in _PAYMENTS_CMDS):
        entries = _tail_md(_OPS_PAYMENT, 10)
        _audit("review", "pending_payment", state)
        if not entries:
            return "No entries in Payment Follow-ups right now."
        deferred = state.get("deferred_chirps", {})
        status = " (chirps deferred)" if "pending_payment" in deferred else ""
        lines = [f"  {i+1}. {e}" for i, e in enumerate(entries)]
        return f"Payment Follow-ups{status}:\n" + "\n".join(lines)

    return None


# ── Calendar context injection ────────────────────────────────────────────────

_CALENDAR_QUERY_WORDS = (
    "calendar", "schedule", "scheduled", "appointment", "meeting",
    "tomorrow morning", "tomorrow afternoon", "my schedule",
    "what's on", "what do i have", "what's tomorrow", "what's today",
    "this week", "coming up",
    # natural variants that were missing
    "do i have anything", "any meetings", "any appointments",
    "what time", "when is", "what's next",
)

_CALENDAR_CREATE_WORDS = (
    "schedule ", "add to my calendar", "put on my calendar", "put it on my calendar",
    "create an event", "create event", "block off", "set up a meeting",
    "add a meeting", "add an appointment", "make an appointment",
    "book ", "remind me ", "add ", "set a ", "set up ",
)


def _fetch_calendar_context(query: str) -> str:
    """
    If the query has calendar intent, call the broker and return a formatted
    calendar context block for prompt injection.
    Returns "" if not applicable, broker denied, or no data.
    """
    t = query.lower()
    if not any(w in t for w in _CALENDAR_QUERY_WORDS):
        return ""
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.calendar.read", {"days_ahead": 7})
        if not result["ok"]:
            return ""
        events = result["data"]
        if not events:
            return "[CALENDAR DATA — next 7 days: no events found]"
        # Dicts defined once outside the loop.
        _HOUR_WORDS   = {1:"one", 2:"two", 3:"three", 4:"four", 5:"five",
                         6:"six", 7:"seven", 8:"eight", 9:"nine", 10:"ten",
                         11:"eleven", 12:"twelve"}
        _MINUTE_WORDS = {15: "fifteen", 30: "thirty", 45: "forty-five"}

        _now = datetime.now()

        def _day_label(event_dt: datetime) -> str:
            """
            Return a human-relative day label.
            - delta 0 → "later today" (future) or "today" (past/now)
            - delta 1 → "tomorrow"
            - delta 2-6 → weekday name ("Friday")
            At 1 AM Friday a Friday 8:30 AM event is delta=0 → "later today" — accurate and clear.
            """
            delta = (event_dt.date() - _now.date()).days
            if delta == 0:
                return "later today" if event_dt.replace(tzinfo=None) > _now else "today"
            elif delta == 1:
                return "tomorrow"
            else:
                return event_dt.strftime("%A")  # "Friday" — within the 7-day window

        lines = [f"[CALENDAR DATA — next 7 days, current time: {_now.strftime('%-I:%M %p')} {_now.strftime('%A')}]"]
        for e in events:
            title    = e.get("summary", "(no title)")
            start    = e.get("start", {})
            start_dt = start.get("dateTime") or start.get("date", "")
            location = e.get("location", "")
            desc     = e.get("description", "").strip()
            loc_str  = f" @ {location}" if location else ""

            # Pre-format to spoken-word time and relative day label so the model
            # and Piper TTS both read naturally.
            try:
                if "T" in start_dt:
                    dt      = datetime.fromisoformat(start_dt)
                    period  = dt.strftime("%p")
                    hour    = int(dt.strftime("%-I"))
                    minute  = dt.minute
                    hw      = _HOUR_WORDS.get(hour, str(hour))
                    if minute == 0:
                        time_str = f"{hw} {period}"
                    elif minute in _MINUTE_WORDS:
                        time_str = f"{hw}-{_MINUTE_WORDS[minute]} {period}"
                    else:
                        time_str = f"{hour}:{minute:02d} {period}"
                    day_str   = _day_label(dt)
                    formatted = f"{day_str} at {time_str}"
                else:
                    dt        = datetime.fromisoformat(start_dt)
                    day_str   = _day_label(datetime(dt.year, dt.month, dt.day, 23, 59))
                    formatted = f"{day_str} (all day)"
            except Exception:
                formatted = start_dt[:16]

            lines.append(f"  {formatted}  {title}{loc_str}")
            if desc:
                lines.append(f"    note: {desc}")
        return "\n".join(lines)
    except Exception:
        return ""


def _detect_calendar_create_intent(text: str) -> bool:
    """True if the query looks like a request to create a calendar event."""
    t = text.lower()
    return any(w in t for w in _CALENDAR_CREATE_WORDS)


def _extract_event_details(text: str) -> dict | None:
    """
    Use an LLM to extract structured event details from natural language.
    Returns dict with keys: title, date (YYYY-MM-DD), start_time (HH:MM 24h),
    duration_minutes (int). Returns None on failure or missing required fields.
    """
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    day_of_week = date.today().strftime("%A")
    prompt = (
        f"Today is {day_of_week}, {today_str}. "
        f"Extract calendar event details from this message.\n"
        f"Message: \"{text}\"\n\n"
        f"Return ONLY a JSON object with these exact keys:\n"
        f"  title: string (short event name)\n"
        f"  date: string in YYYY-MM-DD format\n"
        f"  start_time: string in HH:MM 24-hour format\n"
        f"  duration_minutes: integer (default 60 if not specified)\n\n"
        f"Rules:\n"
        f"- If a field cannot be determined, use null\n"
        f"- 'tomorrow' means {(date.today().__class__.fromordinal(date.today().toordinal()+1)).strftime('%Y-%m-%d')}\n"
        f"- Return JSON only, no other text"
    )
    try:
        data = claude_json(prompt)
        if not data or not isinstance(data, dict):
            return None
        # Require title, date, start_time — duration_minutes has a default
        if not data.get("title") or not data.get("date") or not data.get("start_time"):
            return None
        if data.get("duration_minutes") is None:
            data["duration_minutes"] = 60
        return data
    except Exception as e:
        print(f"[cassandra] event extraction error: {e}", flush=True)
        return None


# ── Email send pipeline ───────────────────────────────────────────────────────

_SEND_EMAIL_KEYWORDS = (
    "send an email to",
    "send email to",
    "email to ",
    "send a message to",
    "send a msg to",
    "draft and send",
    "compose an email to",
    "compose email to",
)

_SEND_EMAIL_RE = re.compile(
    r"(?:"
    r"send\s+(?:an?\s+)?(?:email|message|msg)\s+to\s+"
    r"|send\s+(?:an?\s+)?(?:email|message|msg)\s+(?:for\s+)?"
    r"|email\s+to\s+"
    r"|compose\s+(?:an?\s+)?(?:email|message)\s+to\s+"
    r")"
    r"([A-Za-z][A-Za-z0-9_' -]{0,40}?)"
    r"(?:\s+(?:subject:|about|saying|re:|:)\s*|$)",
    re.IGNORECASE,
)

_SUBJECT_RE = re.compile(r"(?:subject:|re:)\s*(.+?)(?:\s+body:|\s*\n|$)", re.IGNORECASE)
_BODY_RE    = re.compile(r"body:\s*(.+)$", re.IGNORECASE | re.DOTALL)


def _detect_send_email_intent(text: str) -> bool:
    """True if the user's message is an email-send request."""
    from cassandra_capability import EMAIL_SEND_CONNECTED
    if not EMAIL_SEND_CONNECTED:
        return False
    t = text.lower()
    return any(k in t for k in _SEND_EMAIL_KEYWORDS)


_OUTREACH_EMAIL_PATTERNS = (
    "send the intro emails",
    "send intro emails",
    "send the outreach emails",
    "send outreach emails",
    "send the cassandra intro emails",
)


def _detect_outreach_email_intent(text: str) -> bool:
    from cassandra_capability import EMAIL_SEND_CONNECTED
    if not EMAIL_SEND_CONNECTED:
        return False
    t = text.lower()
    return any(pattern in t for pattern in _OUTREACH_EMAIL_PATTERNS)


def _load_nicknames() -> dict:
    """Load contact_nicknames.json. Returns empty dict on any error."""
    try:
        data = json.loads(_NICKNAMES_PATH.read_text(encoding="utf-8"))
        return {k.lower(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def _normalize_contact_entry(nickname: str, raw: object) -> dict:
    names: set[str] = {nickname.lower()}
    chat_ids: set[str] = set()
    if isinstance(raw, str):
        names.add(raw.lower())
        display_name = raw
    elif isinstance(raw, dict):
        display_name = (
            raw.get("name")
            or raw.get("display_name")
            or raw.get("real_name")
            or nickname
        )
        for key in ("name", "display_name", "real_name", "telegram_name", "sender_name"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip().lower())
        for key in ("aliases", "sender_names"):
            values = raw.get(key, [])
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip():
                        names.add(value.strip().lower())
        for key in ("telegram_chat_id", "chat_id"):
            value = raw.get(key)
            if value not in (None, ""):
                chat_ids.add(str(value))
        values = raw.get("telegram_chat_ids", [])
        if isinstance(values, list):
            for value in values:
                if value not in (None, ""):
                    chat_ids.add(str(value))
    else:
        display_name = nickname
    tier = raw.get("tier", "inner_circle") if isinstance(raw, dict) else "inner_circle"
    response_sla = raw.get("response_sla") if isinstance(raw, dict) else None
    return {
        "nickname": nickname,
        "display_name": display_name,
        "sender_names": names,
        "chat_ids": chat_ids,
        "tier": tier,
        "response_sla": response_sla,
    }


def _find_designated_contact(sender_name: str | None = None, sender_chat_id: object | None = None) -> dict | None:
    name_key = sender_name.strip().lower() if isinstance(sender_name, str) and sender_name.strip() else ""
    chat_key = str(sender_chat_id) if sender_chat_id not in (None, "") else ""
    for nickname, raw in _load_nicknames().items():
        entry = _normalize_contact_entry(nickname, raw)
        if name_key and name_key in entry["sender_names"]:
            return entry
        if chat_key and chat_key in entry["chat_ids"]:
            return entry
    return None


def is_designated_contact_sender(sender_name: str | None = None, sender_chat_id: object | None = None) -> bool:
    return _find_designated_contact(sender_name=sender_name, sender_chat_id=sender_chat_id) is not None


def _reply_has_hedging(reply: str) -> bool:
    lowered = reply.lower()
    return any(re.search(pattern, lowered) for pattern in _HEDGING_PATTERNS)


def _capability_flag_value(flag_name: str | None) -> bool | None:
    if not flag_name:
        return None
    try:
        import cassandra_capability as capability_flags

        return bool(getattr(capability_flags, flag_name))
    except Exception:
        return None


def detect_capability_gaps(user_text: str, reply: str) -> list[dict]:
    """
    Infer capability gaps from the request text, known False capability flags,
    and hedging language in the generated reply.
    """
    query = user_text.lower()
    reply_lower = reply.lower()
    reply_has_hedge = _reply_has_hedging(reply)
    gaps: list[dict] = []
    seen: set[str] = set()

    for capability, spec in _CAPABILITY_GAP_SPECS.items():
        query_match = any(keyword in query for keyword in spec["keywords"])
        reply_match = any(keyword in reply_lower for keyword in spec.get("reply_keywords", ()))
        flag_value = _capability_flag_value(spec.get("flag"))
        known_missing = flag_value is False and query_match
        hedged_gap = reply_has_hedge and (query_match or reply_match)
        if not (known_missing or hedged_gap):
            continue
        if capability in seen:
            continue
        seen.add(capability)
        gaps.append({
            "capability": capability,
            "goal": spec["goal"],
            "scope": list(spec["scope"]),
            "success": spec["success"],
            "manual_required": bool(spec.get("manual_required")),
            "known_missing": known_missing,
            "hedging_detected": hedged_gap,
        })
    return gaps


def _append_partial_followup_note(reply: str) -> str:
    cleaned = reply.strip()
    if not cleaned:
        return _PARTIAL_FOLLOWUP_NOTE
    if _PARTIAL_FOLLOWUP_NOTE.lower() in cleaned.lower():
        return cleaned
    separator = " " if cleaned.endswith((".", "!", "?")) else ". "
    return f"{cleaned}{separator}{_PARTIAL_FOLLOWUP_NOTE}"


def _load_followup_records() -> list[dict]:
    if not _FOLLOWUP_LOG.exists():
        return []
    records: list[dict] = []
    try:
        for line in _FOLLOWUP_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
    except Exception as exc:
        print(f"[cassandra_followup] read error: {exc}", flush=True)
    return records


def _write_followup_records(records: list[dict]) -> None:
    _FOLLOWUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(record) for record in records)
    if payload:
        payload += "\n"
    _FOLLOWUP_LOG.write_text(payload, encoding="utf-8")


def _existing_upgrade_task_name(capability: str) -> str | None:
    prefix = f"cas-upgrade-{capability}-"
    # Check active queue
    for path in sorted(_POLISH_TASKS_DIR.glob(f"{prefix}*.md")):
        return path.stem
    # Check archive — don't re-create tasks that are already done
    archive_dir = _POLISH_TASKS_DIR.parent / "archive"
    if archive_dir.exists():
        for path in archive_dir.glob(f"task_{prefix}*"):
            # Extract task name: task_cas-upgrade-foo-timestamp → cas-upgrade-foo-timestamp
            parts = path.stem.split("_", 1)
            if len(parts) > 1:
                name_part = parts[1].rsplit("_", 1)[0]
                if name_part.startswith(prefix):
                    return name_part
    try:
        status = json.loads(_POLISH_STATUS.read_text(encoding="utf-8"))
        task_name = str(status.get("task_name", "")).strip()
        if task_name.startswith(prefix):
            return task_name
    except Exception:
        pass
    try:
        title = ""
        for line in _POLISH_TASK_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip()
                break
        if title.startswith(prefix):
            return title
    except Exception:
        pass
    return None


def _create_upgrade_task(capability_gap: dict, original_message: str) -> str | None:
    capability = capability_gap["capability"]
    existing = _existing_upgrade_task_name(capability)
    if existing:
        return existing
    if capability_gap.get("manual_required"):
        return None

    _POLISH_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    task_name = f"cas-upgrade-{capability}-{timestamp}"
    task_path = _POLISH_TASKS_DIR / f"{task_name}.md"
    scope_lines = "\n".join(f"- {line}" for line in capability_gap["scope"])
    task_body = (
        f"title: {task_name}\n"
        f"goal: {capability_gap['goal']}\n"
        "scope:\n"
        f"{scope_lines}\n"
        f"- Handle the triggering request safely: \"{original_message.strip()}\"\n"
        "success:\n"
        f"- {capability_gap['success']}\n"
    )
    task_path.write_text(task_body, encoding="utf-8")
    return task_name


def _notify_manual_gap(sender_name: str, original_message: str, capability: str) -> None:
    try:
        from chief_notify import send as notify_winship

        notify_winship(
            "Cassandra hit a manual setup gap.\n"
            f"Sender: {sender_name or 'unknown'}\n"
            f"Capability: {capability}\n"
            f"Message: {original_message}"
        )
    except Exception as exc:
        print(f"[cassandra_followup] manual-gap notify failed: {exc}", flush=True)


def _notify_client_urgency(
    contact_entry: dict,
    original_message: str,
    partial_reply: str,
    capability_gaps: list[dict],
) -> None:
    name = contact_entry.get("display_name") or contact_entry.get("nickname") or "Unknown client"
    gap_names = ", ".join(gap["capability"] for gap in capability_gaps)
    sla = contact_entry.get("response_sla")
    sla_line = f"\nClient expects response within {sla} minutes." if sla else ""
    msg = (
        f"CLIENT MESSAGE — Manual action needed.\n"
        f"From: {name}\n"
        f"Asked: {original_message}\n"
        f"Cassandra answered: {partial_reply}\n"
        f"Could not handle: {gap_names}\n"
        f"Manual action needed — client is waiting.{sla_line}"
    )
    if os.environ.get("CASSANDRA_CLIENT_NOTIFY_ENABLED", "0") != "1":
        print(f"[cassandra_urgency] dry-run (set CASSANDRA_CLIENT_NOTIFY_ENABLED=1 to enable): {msg}", flush=True)
        return
    try:
        from chief_notify import send as notify_winship
        notify_winship(msg)
    except Exception as exc:
        print(f"[cassandra_urgency] client notify failed: {exc}", flush=True)


def _record_gap_followups(
    sender_name: str,
    sender_chat_id: object | None,
    original_message: str,
    partial_reply: str,
    capability_gaps: list[dict],
) -> None:
    records = _load_followup_records()
    changed = False
    for gap in capability_gaps:
        capability = gap["capability"]
        duplicate = any(
            record.get("status") in ("pending", "manual_required")
            and record.get("sender_name") == sender_name
            and record.get("original_message") == original_message
            and record.get("gap_type") == capability
            for record in records
        )
        if duplicate:
            continue
        task_name = _create_upgrade_task(gap, original_message)
        status = "manual_required" if gap.get("manual_required") else "pending"
        records.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "sender_name": sender_name,
            "sender_chat_id": sender_chat_id,
            "original_message": original_message,
            "partial_reply_sent": partial_reply,
            "gap_type": capability,
            "upgrade_task_name": task_name,
            "status": status,
        })
        changed = True
        if status == "manual_required":
            _notify_manual_gap(sender_name, original_message, capability)
    if changed:
        _write_followup_records(records)


def _upgrade_task_completed(task_name: str | None) -> bool:
    if not task_name:
        return False
    if any(_POLISH_ARCHIVE.glob(f"closeout_{task_name}_*.ok")):
        return True
    return any(task_name in path.name for path in _POLISH_ARCHIVE.iterdir())


def process_pending_followups() -> list[dict]:
    records = _load_followup_records()
    if not records:
        return []

    updated = False
    completed: list[dict] = []
    for record in records:
        if record.get("status") != "pending":
            continue
        if not _upgrade_task_completed(record.get("upgrade_task_name")):
            continue
        try:
            followup_reply = handle(
                record["original_message"],
                {
                    "sender_name": record.get("sender_name"),
                    "sender_chat_id": record.get("sender_chat_id"),
                    "skip_followup_check": True,
                    "followup_reprocess": True,
                },
            )[0]
        except Exception as exc:
            print(f"[cassandra_followup] reprocess error: {exc}", flush=True)
            continue

        remaining = detect_capability_gaps(record["original_message"], followup_reply)
        if any(gap["capability"] == record.get("gap_type") for gap in remaining):
            continue
        try:
            from cassandra_sender import send_message

            send_message(followup_reply, chat_id=record.get("sender_chat_id"))
        except Exception as exc:
            print(f"[cassandra_followup] send error: {exc}", flush=True)
            continue
        record["status"] = "completed"
        record["completed_at"] = datetime.now().isoformat(timespec="seconds")
        record["followup_reply_sent"] = followup_reply
        updated = True
        completed.append(record)

    if updated:
        _write_followup_records(records)
    return completed


def _resolve_recipient_email(name: str) -> tuple[str, str]:
    """
    Resolve a name or nickname to (email_address, display_name).
    Returns ("", error_message) if resolution fails.
    Checks contact_nicknames.json first, then Google Contacts.
    """
    name_stripped = name.strip()
    nicknames     = _load_nicknames()
    raw_entry     = nicknames.get(name_stripped.lower(), name_stripped)
    if isinstance(raw_entry, dict):
        search_name = raw_entry.get("name") or raw_entry.get("display_name") or name_stripped
    else:
        search_name = raw_entry or name_stripped

    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.contacts.read", {"query": search_name})
    except Exception as e:
        return ("", f"Couldn't reach the contacts broker: {e}")

    if not result.get("ok") or not result.get("data"):
        return ("", f"I don't have a contact for {name_stripped} in your Google Contacts.")

    contacts = result["data"]
    for c in contacts:
        if c.get("email"):
            return (c["email"], c.get("display_name", search_name))

    return ("", f"I have a contact for {name_stripped} but no email address on file.")


def _parse_email_request(text: str) -> dict | None:
    """
    Parse an email send request from natural language.
    Returns {"to_name": str, "subject": str, "body": str} on success,
    or None if the recipient name cannot be extracted.

    Supported format:
        send email to [name] subject: [subject] body: [body]
    """
    m_to = _SEND_EMAIL_RE.search(text)
    if not m_to:
        return None

    to_name = m_to.group(1).strip()

    m_subj = _SUBJECT_RE.search(text)
    subject = m_subj.group(1).strip() if m_subj else ""

    m_body = _BODY_RE.search(text)
    body    = m_body.group(1).strip() if m_body else ""

    return {"to_name": to_name, "subject": subject, "body": body}


def _handle_send_email(text: str) -> str | None:
    """
    Handle a send-email request.
    Returns a reply string, or None to fall through to LLM.

    Flow:
      1. Parse to_name, subject, body from text.
      2. Resolve to_name → email via nicknames + contacts.
      3. If resolution fails: return clarification request.
      4. If subject/body missing: return format instructions.
      5. Call broker (L2 approval gate is inside broker for CLASS_C).
      6. Return confirmation or error message.
    """
    parsed = _parse_email_request(text)
    if parsed is None:
        return None  # can't parse — fall through to LLM

    to_name = parsed["to_name"]
    subject = parsed["subject"]
    body    = parsed["body"]

    # Resolve recipient
    email_addr, display_name = _resolve_recipient_email(to_name)
    if not email_addr:
        return display_name  # error message from resolution

    # Require both subject and body — prompt if either is missing
    if not subject or not body:
        return (
            f"Got it — sending to {display_name}. "
            "To complete this, reply with:\n"
            f"send email to {to_name} subject: [subject line] body: [your message]"
        )

    # Call broker — L2 Guardian approval happens inside broker.call() for CLASS_C
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.gmail.send", {
            "to":      email_addr,
            "subject": subject,
            "body":    body,
        })
    except Exception as e:
        print(f"[cassandra] email broker error: {e}", flush=True)
        return "Couldn't reach the email broker. Try again in a moment."

    if result.get("ok"):
        return f"Sent. Email to {display_name} with subject \"{subject}\"."
    else:
        err = result.get("error", "unknown error")
        if "denied" in err.lower():
            return "Email send was denied at the approval gate."
        if "scope" in err.lower() or "permission" in err.lower() or "insufficien" in err.lower():
            return (
                "Email send failed — the Gmail token needs the compose scope. "
                "Run: python3 /home/openclaw/google_access_broker.py --auth"
            )
        return f"Couldn't send the email: {err}"


def _handle_outreach_email_request(text: str) -> str | None:
    if not _detect_outreach_email_intent(text):
        return None

    try:
        from cassandra_outreach import run_outreach
        results = run_outreach(dry_run=False)
    except Exception as e:
        print(f"[cassandra] outreach flow error: {e}", flush=True)
        return "The intro email flow hit a snag before it could finish."

    sent = [row.get("display_name", row["nickname"]) for row in results if row.get("status") == "sent"]
    failed = [row.get("display_name", row["nickname"]) for row in results if row.get("status") != "sent"]

    if sent and not failed:
        return "Intro emails sent to " + ", ".join(sent) + "."
    if sent and failed:
        return (
            "Some intro emails went out: "
            + ", ".join(sent)
            + ". The rest need attention: "
            + ", ".join(failed)
            + "."
        )
    return "The intro email flow did not complete any sends."


def _handle_calendar_create(text: str) -> str | None:
    """
    Extract event details from text and create a Google Calendar event via broker.
    Returns a reply string on success or clear failure, None if extraction failed
    (to fall through to LLM).
    """
    details = _extract_event_details(text)
    if details is None:
        return None  # fall through to LLM to ask for clarification

    title           = details["title"]
    date_str        = details["date"]        # YYYY-MM-DD
    start_time_str  = details["start_time"]  # HH:MM
    duration_min    = int(details.get("duration_minutes", 60))

    # Build ISO datetimes
    try:
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(f"{date_str}T{start_time_str}", "%Y-%m-%dT%H:%M")
        end_dt   = start_dt + timedelta(minutes=duration_min)
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso   = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        print(f"[cassandra] datetime build error: {e}", flush=True)
        return None

    # Call broker (approval gate is inside broker for CLASS_B)
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.calendar.write", {
            "title":     title,
            "start_iso": start_iso,
            "end_iso":   end_iso,
        })
    except Exception as e:
        print(f"[cassandra] broker call error: {e}", flush=True)
        return "Couldn't reach the calendar broker. Try again in a moment."

    if result.get("ok"):
        # Format confirmation
        from datetime import datetime
        start_dt_obj = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
        display_time = start_dt_obj.strftime("%A %B %-d at %-I:%M %p")
        return f"Done. Added \"{title}\" on {display_time}."
    else:
        err = result.get("error", "unknown error")
        if "denied" in err.lower():
            return "Calendar write was denied at the approval gate."
        return f"Couldn't create the event: {err}"


# ── Gmail context injection ───────────────────────────────────────────────────

_GMAIL_QUERY_WORDS = (
    "email", "emails", "inbox", "unread", "new message",
    "any messages", "check my email", "did anyone email",
    "did i get an email", "did i get any email", "gmail",
)


def _fetch_gmail_context(query: str) -> str:
    """
    If the query has Gmail intent, call the broker and return a formatted
    inbox context block for prompt injection.
    Returns "" if not applicable, broker denied, or an error occurs.
    """
    if not any(w in query.lower() for w in _GMAIL_QUERY_WORDS):
        return ""
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.gmail.read.metadata", {"max_results": 10})
        if not result["ok"]:
            return "[GMAIL DATA — inbox empty or unreachable]"
        messages = result.get("data") or []
        if not messages:
            return "[GMAIL DATA — inbox empty or unreachable]"

        now = datetime.now()

        def _relative_date(date_raw: str) -> str:
            """Convert a raw RFC 2822 Date header to a spoken relative label."""
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_raw)
                # Strip timezone for comparison
                dt_local = dt.replace(tzinfo=None)
                delta = (now.date() - dt_local.date()).days
                if delta == 0:
                    return "today"
                elif delta == 1:
                    return "yesterday"
                elif 2 <= delta <= 6:
                    return f"{delta} days ago"
                else:
                    return dt_local.strftime("%B %-d")  # e.g. "March 15"
            except Exception:
                return date_raw[:16] if date_raw else "unknown date"

        # Sort: unread first, then read — cap at 5 total
        unread = [m for m in messages if "UNREAD" in m.get("labels", [])]
        read   = [m for m in messages if "UNREAD" not in m.get("labels", [])]
        display = (unread + read)[:5]

        lines = [f"[GMAIL DATA — inbox, current time: {now.strftime('%-I:%M %p %A')}]"]
        for m in display:
            label     = "UNREAD" if "UNREAD" in m.get("labels", []) else "READ  "
            from_name = m.get("from_name", "Unknown")
            subject   = m.get("subject", "(no subject)")
            rel_date  = _relative_date(m.get("date_raw", ""))
            lines.append(f"  {label}  {from_name}  {subject}  {rel_date}")

        return "\n".join(lines)
    except Exception:
        return "[GMAIL DATA — inbox empty or unreachable]"


_CONTACTS_QUERY_WORDS = (
    "number for", "phone number", "phone for", "contact for",
    "do i have a number", "do i have contact", "what's the number",
    "how do i reach", "how do i contact", "their number", "his number",
    "her number", "have their contact",
    "'s number",       # catches "Glenn's number", "dad's number", "the venue's number"
)


def _fetch_contacts_context(query: str) -> str:
    """
    If the query has contacts intent, search Google Contacts via the broker
    and return a formatted block for prompt injection.
    Returns "" if not applicable, broker denied, or an error occurs.
    """
    if not any(w in query.lower() for w in _CONTACTS_QUERY_WORDS):
        return ""
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.contacts.read", {"query": query})
        if not result["ok"] or not result.get("data"):
            return "[CONTACTS DATA — not found or unreachable]"
        contacts = result["data"]
        if not contacts:
            return "[CONTACTS DATA — not found or unreachable]"

        lines = [f"[CONTACTS DATA — search: {query}]"]
        for c in contacts[:3]:
            email_part = c.get("email") or "no email on file"
            lines.append(
                f"  {c.get('display_name', '')}  "
                f"phone: {c.get('phone', '')}  "
                f"email: {email_part}"
            )
        return "\n".join(lines)
    except Exception:
        return "[CONTACTS DATA — not found or unreachable]"


# ── Financial event routing ───────────────────────────────────────────────────

_FIN_INCOME_RE = re.compile(
    r"(?:i |just |)(?:"
    # "deposited a check for $X" or "deposited a check from X for $X"
    r"deposited?\s+(?:a\s+)?(?:check|payment)?\s*(?:from\s+[^$\d]{1,60}?)?\s*(?:for\s+)?"
    # "got paid $X"
    r"|got\s+paid\s+"
    # "got a check for $X" or "got a check from X for $X"
    r"|got\s+(?:a\s+)?check\s+(?:from\s+[^$\d]{1,60}?)?\s*(?:for\s+)?"
    # "received a check/payment from X for $X"
    r"|received\s+(?:a\s+)?(?:check|payment)\s+(?:from\s+[^$\d]{1,60}?)?\s*(?:for\s+|of\s+)?"
    # "was paid $X"
    r"|was\s+paid\s+"
    # "check came in for $X"
    r"|check\s+came\s+in\s+(?:for\s+)?"
    # "payment came in for $X"
    r"|payment\s+came\s+(?:in\s+)?(?:for\s+)?"
    r")\$?([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Handles inverted word order: "got $1000 check from St Annes"
# _FIN_INCOME_RE only matches "got [a] check [from X] for $amount" (amount last)
_FIN_INCOME_RE2 = re.compile(
    r"(?:i\s+)?(?:just\s+)?got\s+(?:a\s+)?\$?([\d,]+(?:\.\d{1,2})?)\s+(?:a\s+)?(?:check|payment)\b",
    re.IGNORECASE,
)

# Extract payer: "from Glenn" / "from St. Anne's Church" / "by the church"
# Stops at " for " or " re:" or newline — NOT at "." so names like "St. Anne's" work
_FIN_PAYER_RE = re.compile(
    r"(?:from|by)\s+([A-Za-z][^,\n]+?)(?:\s+for\s|\s+re:|\n|$)",
    re.IGNORECASE,
)

# Extract purpose: "for the February gig" / "for February work" / "re: invoice 4"
# Negative lookahead skips "for $1000" / "for 1000" — that's the amount, not the description
_FIN_DESC_RE = re.compile(
    r"(?:for|re:?)\s+(?:the\s+)?(?!\$?[\d,]+(?:\.\d{1,2})?\b)(.+?)(?:\.|$)",
    re.IGNORECASE,
)

_FIN_EXPENSE_KEYWORDS = (
    "i spent",
    "i paid for",
    "i paid $",
    "log expense",
    "add expense",
    "expense:",
)

_FIN_LOOKUP_KEYWORDS = (
    "did you log",
    "did you get that",
    "confirm the deposit",
    "confirm the check",
    "what did you log",
    "what deposits do you have",
    "show me what you logged",
)


def _detect_financial_intent(text: str) -> str | None:
    """Returns 'income', 'expense', or None."""
    t = text.lower()
    if _FIN_INCOME_RE.search(t) or _FIN_INCOME_RE2.search(t):
        return "income"
    if any(k in t for k in _FIN_EXPENSE_KEYWORDS):
        return "expense"
    return None


def _detect_lookup_intent(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in _FIN_LOOKUP_KEYWORDS)


def _amt_str(amount: float) -> str:
    return f"${int(amount):,}" if amount == int(amount) else f"${amount:,.2f}"


_LOOKUP_WEEK_WORDS = ("this week", "recent", "last few days", "past few days", "lately", "recently")


def _handle_lookup(text: str) -> str:
    """Read recent income entries and reply with what's logged."""
    try:
        from chief_cpa_brain import get_recent_income
    except ImportError:
        return "I can't reach the log right now."

    t = text.lower()
    days = 7 if any(w in t for w in _LOOKUP_WEEK_WORDS) else 1
    entries = get_recent_income(days=days)
    if not entries:
        return "I don't have any deposits logged today. Did you want to log one?"

    parts = []
    for e in entries[:3]:
        amt = _amt_str(float(e.get("amount", 0)))
        payer = e.get("payer", "")
        desc = e.get("description", "")
        date_str = e.get("date", "")
        if payer and desc:
            parts.append(f"{amt} from {payer} for {desc} on {date_str}")
        elif payer:
            parts.append(f"{amt} from {payer} on {date_str}")
        elif desc and desc != e.get("description", "")[:80]:
            parts.append(f"{amt} on {date_str}")
        else:
            parts.append(f"{amt} on {date_str}")

    if len(parts) == 1:
        return f"Yes. I have {parts[0]} logged."
    return "Yes. I have these logged today: " + "; ".join(parts) + "."


def _handle_financial_event(text: str, intent: str,
                             state: dict | None = None) -> str | None:
    """
    Log a financial event and return a Cassandra-voiced plain-text reply.
    Returns None if parsing fails — caller falls through to LLM.
    state is required to set pending_income_followup for Path B income entries.
    """
    try:
        from chief_cpa_brain import (log_entry, log_expense_from_text,
                                      find_duplicate_today)
    except ImportError:
        return None

    if intent == "income":
        m = _FIN_INCOME_RE.search(text)
        if not m:
            m = _FIN_INCOME_RE2.search(text)
        if not m:
            return None
        try:
            amount = float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            return None
        if amount <= 0:
            return None

        amt = _amt_str(amount)

        # Dedup check — same amount already logged today
        dup = find_duplicate_today(amount)
        if dup:
            if state is not None:
                state["pending_income_followup"] = {
                    "dedup_override_pending": True,
                    "amount":        amount,
                    "original_text": text,
                }
            return (
                f"I already have a {amt} deposit logged today. "
                "Is this the same one, or did you mean to log another?"
            )

        # Extract payer and description from message (Path A)
        payer = ""
        desc = ""
        payer_m = _FIN_PAYER_RE.search(text)
        if payer_m:
            payer = payer_m.group(1).strip()
        desc_m = _FIN_DESC_RE.search(text)
        if desc_m:
            desc = desc_m.group(1).strip()
            # Don't let description bleed into payer if it was already captured
            if payer and desc.lower().startswith(payer.lower()):
                desc = ""

        entry = log_entry(
            amount=amount,
            description=desc or text[:100],
            category="income",
            entry_type="income",
            payer=payer,
        )

        if payer and desc:
            # Path A — full details captured
            return f"Logged. {amt} from {payer} on {entry['date']} for {desc}."

        # Path B — partial or no details; echo what we have, ask only for missing
        if state is not None:
            state["pending_income_followup"] = {
                "entry_id":  entry["id"],
                "amount":    amount,
                "has_payer": bool(payer),
                "has_desc":  bool(desc),
            }

        if payer and not desc:
            return f"Got it. {amt} from {payer} on {entry['date']}. What was this for?"
        elif desc and not payer:
            return f"Got it. {amt} for {desc} on {entry['date']}. Who was this from?"
        else:
            return f"Got it. {amt} logged on {entry['date']}. Who was this from and what was it for?"

    else:  # expense
        entry = log_expense_from_text(text)
        if not entry:
            return None
        amt = _amt_str(float(entry['amount']))
        return f"Logged. {amt} under {entry['category']}. {entry['description']}."


_DEDUP_CONFIRM = ("yes", "new one", "different", "another", "log it", "go ahead", "add it", "new entry", "log another")
_DEDUP_DENY    = ("no", "same", "same one", "never mind", "cancel", "don't", "nope", "leave it")


def _handle_income_followup(text: str, pending: dict, state: dict) -> str | None:
    """
    Handle a follow-up reply for either:
      - dedup_override_pending: confirm or deny logging a duplicate
      - normal Path B: provide payer/description for a pending income entry
    Returns None if the message looks like a new financial event.
    Clears pending state either way.
    """
    # If it looks like a new financial event, clear pending and let financial handler run
    if _detect_financial_intent(text):
        state["pending_income_followup"] = None
        return None

    # ── Dedup override branch ─────────────────────────────────────────────────
    if pending.get("dedup_override_pending"):
        t    = text.lower()
        amt  = _amt_str(float(pending.get("amount", 0)))
        orig = pending.get("original_text", "")

        if any(w in t for w in _DEDUP_CONFIRM):
            state["pending_income_followup"] = None
            try:
                from chief_cpa_brain import log_entry
                entry = log_entry(
                    amount=float(pending["amount"]),
                    description=orig[:100],
                    category="income",
                    entry_type="income",
                )
                # Set Path B pending for details
                state["pending_income_followup"] = {
                    "entry_id": entry["id"],
                    "amount":   pending["amount"],
                }
                return (
                    f"Logged. Another {amt} deposit on {entry['date']}. "
                    "Who was this from and what was it for?"
                )
            except Exception:
                return f"Logged another {amt} deposit."

        elif any(w in t for w in _DEDUP_DENY):
            state["pending_income_followup"] = None
            return "Got it, leaving it as is."

        else:
            # Unclear — keep pending, ask again
            return (
                f"Just to confirm — should I log another {amt} deposit, "
                "or is this the same one?"
            )

    # ── Path B detail follow-up ───────────────────────────────────────────────
    try:
        from chief_cpa_brain import update_entry
    except ImportError:
        state["pending_income_followup"] = None
        return None

    entry_id = pending.get("entry_id", "")
    amount   = pending.get("amount", 0)
    amt      = _amt_str(float(amount))

    has_payer = pending.get("has_payer", False)
    has_desc  = pending.get("has_desc",  False)

    payer = ""
    desc  = ""
    payer_m = _FIN_PAYER_RE.search(text)
    if payer_m:
        payer = payer_m.group(1).strip()
    desc_m = _FIN_DESC_RE.search(text)
    if desc_m:
        desc = desc_m.group(1).strip()

    # If we only asked for one field and got no clean extraction, use the whole text
    if has_payer and not has_desc and not desc:
        desc = text.strip()
    elif has_desc and not has_payer and not payer:
        payer = text.strip()
    elif not has_payer and not has_desc and not payer and not desc:
        desc = text.strip()

    fields: dict = {"logged_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if payer:
        fields["payer"] = payer
    if desc:
        fields["description"] = desc

    updated = update_entry(entry_id, **fields)
    state["pending_income_followup"] = None

    if not updated:
        return f"I couldn't find that entry to update. The {amt} deposit is still logged without details."

    if payer and desc:
        return f"Updated. {amt} from {payer} for {desc}."
    elif payer:
        return f"Updated. {amt} from {payer}."
    elif desc:
        return f"Updated. {amt} for {desc}."
    return f"Updated the {amt} entry."


# ── Invoice generation ───────────────────────────────────────────────────────

_INVOICE_INTENT_PATTERNS = [
    re.compile(r"\b(create|make|generate|draft|write|send)\b.*\binvoice\b", re.I),
    re.compile(r"\binvoice\b.*(for|to)\b", re.I),
    re.compile(r"\bneed\b.*\binvoice\b", re.I),
    re.compile(r"\binvoice\b.*(hilton|draper|capital|client|gig|show|event)\b", re.I),
]

_INVOICE_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})\b",
        re.I,
    ),
]

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _detect_invoice_intent(text: str) -> bool:
    """Return True if any invoice intent pattern matches."""
    return any(p.search(text) for p in _INVOICE_INTENT_PATTERNS)


def _parse_invoice_details(text: str) -> dict | None:
    """
    Extract invoice details from natural language text.
    Returns dict with keys: client_name, project_desc, amount_total,
    deposit_paid, service_date — or None if client_name or amount_total
    could not be extracted (signal Cassandra to ask).
    """
    t = text

    # client_name: "for [Name]" or "to [Name]"
    client_name = None
    m = re.search(r"\b(?:for|to)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})", t)
    if m:
        client_name = m.group(1).strip()

    # project_desc: look for "for [desc]" — prefer descriptions that look like events
    project_desc = ""
    m2 = re.search(
        r"\bfor\s+(.{5,80}?)(?:\s+for\s|\s+\$|\s+amount|\s*,|\s*\.|$)", t, re.I
    )
    if m2:
        candidate = m2.group(1).strip()
        # If it looks like a name (titlecase, 1-3 words) use it as desc too
        project_desc = candidate

    # amount_total: "$NNN" or "NNN dollars" or "NNN bucks"
    amount_total = None
    m3 = re.search(r"\$\s*(\d[\d,]*(?:\.\d{1,2})?)", t)
    if m3:
        amount_total = float(m3.group(1).replace(",", ""))
    else:
        m3b = re.search(r"\b(\d[\d,]*(?:\.\d{1,2})?)\s+(?:dollars?|bucks?)\b", t, re.I)
        if m3b:
            amount_total = float(m3b.group(1).replace(",", ""))

    # deposit_paid: "deposit" followed by an amount
    deposit_paid = 0.0
    m4 = re.search(r"\bdeposit\b[^$\d]{0,20}\$\s*(\d[\d,]*(?:\.\d{1,2})?)", t, re.I)
    if m4:
        deposit_paid = float(m4.group(1).replace(",", ""))

    # service_date: YYYY-MM-DD, MM/DD/YYYY, or "Month DD"
    service_date = "TBD"
    m5 = _INVOICE_DATE_PATTERNS[0].search(t)
    if m5:
        service_date = m5.group(1)
    else:
        m5b = _INVOICE_DATE_PATTERNS[1].search(t)
        if m5b:
            parts = m5b.group(1).split("/")
            service_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
        else:
            m5c = _INVOICE_DATE_PATTERNS[2].search(t)
            if m5c:
                month = _MONTH_MAP[m5c.group(1).lower()]
                day   = m5c.group(2).zfill(2)
                year  = datetime.now().year
                service_date = f"{year}-{month}-{day}"

    if client_name is None or amount_total is None:
        return None

    return {
        "client_name":  client_name,
        "project_desc": project_desc or f"Services for {client_name}",
        "amount_total": amount_total,
        "deposit_paid": deposit_paid,
        "service_date": service_date,
    }


def _handle_create_invoice(text: str, state: dict) -> str | None:
    """
    Handle a create-invoice request from Cassandra.
    Returns a reply string, or None to fall through to LLM.
    """
    parsed = _parse_invoice_details(text)
    if parsed is None:
        return (
            "I need a few details — who is this invoice for, "
            "what service, and what's the total amount?"
        )

    try:
        from invoice_generator import (
            get_next_invoice_number,
            generate_invoice_pdf,
            detect_net_terms,
            append_tracker_row,
        )
    except ImportError as e:
        print(f"[cassandra] invoice_generator import error: {e}", flush=True)
        return f"Invoice generation failed: {e}"

    try:
        issue_date     = datetime.now().strftime("%Y-%m-%d")
        net_terms      = detect_net_terms(parsed["client_name"], parsed.get("project_desc", ""))
        invoice_number = get_next_invoice_number()
        amount_total   = parsed["amount_total"]
        deposit_paid   = parsed.get("deposit_paid", 0.0)
        balance_due    = max(amount_total - deposit_paid, 0.0)

        data = {
            "invoice_number": invoice_number,
            "client_name":    parsed["client_name"],
            "client_email":   "unknown",
            "project_desc":   parsed.get("project_desc", ""),
            "service_date":   parsed.get("service_date", "TBD"),
            "issue_date":     issue_date,
            "net_terms":      net_terms,
            "amount_total":   amount_total,
            "deposit_paid":   deposit_paid,
            "balance_due":    balance_due,
        }

        pdf_path = generate_invoice_pdf(data)
        data["pdf_path"] = pdf_path
        append_tracker_row(data)

        return (
            f"Invoice {invoice_number} drafted for {parsed['client_name']}.\n"
            f"Total: ${amount_total:.2f} | Balance: ${balance_due:.2f} | Terms: {net_terms}\n"
            f"Saved: {pdf_path.name}"
        )
    except Exception as e:
        print(f"[cassandra] invoice generation error: {e}", flush=True)
        return f"Invoice generation failed: {e}"


# ── Cloud routing privacy gate ────────────────────────────────────────────────
#
# SECURITY-CRITICAL BOUNDARY.
# Determines whether the assembled Cassandra context for this turn is safe
# to route to Nemotron cloud inference.
#
# Fails closed on any uncertain state. Loosening any check here is a privacy
# policy change and requires the same review discipline as chief_approval_policy.py.
#
def _cassandra_context_clean(
    calendar_ctx: str,
    gmail_ctx: str,
    contacts_ctx: str,
    context_snapshot: str,
    query: str,
) -> bool:
    """Return True only when no sensitive data source is present in the assembled
    Cassandra context for this turn.

    Block conditions:
    1. Calendar broker was called (event titles, times, locations)
    2. Gmail broker was called (sender names, subject lines)
    3. Payment follow-ups present — UNCONDITIONAL. Live content contains client
       names (e.g. "Capital Hilton") and financial status. Always sensitive.
    4. Pending actions present AND actions text contains sensitive patterns.
       Audited 2026-03-21: current live content is raw user meta-queries with
       no client names or financial figures. Block only on content, not presence.
    5. Query contains financial/payment/credential keywords.
    """
    # Blocks 1–3: any live data fetch contaminates the context
    if calendar_ctx:
        return False
    if gmail_ctx:
        return False
    if contacts_ctx:
        return False

    # Block 3: payment follow-ups — always block regardless of content.
    # Live file contains client names and financial status by design.
    if "Payment follow-ups:" in context_snapshot:
        return False

    # Block 4: pending actions — content scan, not presence block.
    # Block only if the actions text itself contains identifying patterns.
    # Safe ops-meta content (user questions, status notes) does not block.
    if "Pending actions:" in context_snapshot:
        m = re.search(r"Pending actions:\n(.*?)(?:\n\n|$)", context_snapshot, re.DOTALL)
        actions_text = m.group(1) if m else ""
        _action_blockers = [
            r"\$[\d,]+",                         # dollar amounts
            r"\d+\s*(dollars?|usd)\b",           # spelled-out amounts
            r"invoice|billing",                  # billing references
            r"[A-Z][a-z]+\s+[A-Z][a-z]+",       # capitalized name pattern (client/venue names)
        ]
        for pattern in _action_blockers:
            if re.search(pattern, actions_text):
                return False
        # Actions text passed scan — does not block cloud routing

    # Block 5: query-level financial/credential signals
    q = query.lower()
    _fin_patterns = [
        r"\bdeposit\b", r"\bpayment\b", r"\binvoice\b", r"\bbilling\b",
        r"i got paid", r"got a check", r"i received", r"\bincome\b",
        r"\btax\b", r"\bquarterly\b", r"\bexpense\b",
        r"api.?key|bot.?token|credential|\.chief\.env",
    ]
    for pattern in _fin_patterns:
        if re.search(pattern, q):
            return False

    return True


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call(prompt: str, deep: bool, cloud_ok: bool = False) -> str:
    # Cloud path: only when _cassandra_context_clean() confirmed clean context
    if cloud_ok:
        result = nemotron_call(prompt, timeout=30).strip()
        if result:
            print("[cassandra] reply routed to Nemotron cloud", flush=True)
            return result
        print("[cassandra] cloud call failed or empty, falling back to local", flush=True)

    model = OLLAMA_MODEL_DEEP if deep else OLLAMA_MODEL
    if deep:
        print(f"[cassandra] 14b selected ({len(prompt.split())} words)", flush=True)
    result = ollama_call(prompt, timeout=90 if deep else 60, model=model)
    return result


# ── Main handler ──────────────────────────────────────────────────────────────

def handle(text: str, session: dict | None = None) -> list[str]:
    """
    Main Cassandra conversational handler.
    Returns a list of Telegram-ready reply strings.
    """
    session_meta = dict(session or {})
    if not session_meta.get("skip_followup_check"):
        process_pending_followups()

    state = load_state()
    state["last_interaction_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mode toggles — always respond, no LLM needed
    toggle = _check_toggle(text)
    if toggle:
        save_state(state)
        _log_conversation(text, [toggle], route="toggle")
        return [toggle]

    # Payment follow-up commands — pre-LLM, bypasses capability gate
    pay_cmd = _check_payments_command(text, state)
    if pay_cmd:
        save_state(state)
        _log_conversation(text, [pay_cmd], route="payment_cmd")
        return [pay_cmd]

    # Briefing recall — no LLM needed
    try:
        from cassandra_briefing_brain import is_recall_request, handle_recall
        if is_recall_request(text):
            save_state(state)
            recall_reply = handle_recall(text)
            _log_conversation(text, [recall_reply], route="briefing_recall")
            return [recall_reply]
    except Exception as _e:
        pass  # briefing module unavailable — fall through to LLM

    query = _strip_prefix(text)
    _update_cues(state, query)

    # Pending income follow-up — check before financial detection
    pending = state.get("pending_income_followup")
    if pending:
        followup_reply = _handle_income_followup(query, pending, state)
        if followup_reply:
            save_state(state)
            _log_conversation(text, [followup_reply], route="income_followup")
            return [followup_reply]
        # pending cleared by handler; fall through if it was a new financial event

    # Financial lookup
    if _detect_lookup_intent(query):
        save_state(state)
        lookup_reply = _handle_lookup(query)
        _log_conversation(text, [lookup_reply], route="financial_lookup")
        return [lookup_reply]

    # Financial event routing — bypass LLM for speed and reliability
    fin_intent = _detect_financial_intent(query)
    if fin_intent:
        fin_reply = _handle_financial_event(query, fin_intent, state)
        if fin_reply:
            save_state(state)
            _log_conversation(text, [fin_reply], route="financial_event")
            return [fin_reply]
    # fall through to LLM if detection or parsing failed

    # Calendar create routing — bypass LLM for event creation
    if _detect_calendar_create_intent(query):
        cal_reply = _handle_calendar_create(query)
        if cal_reply is not None:
            save_state(state)
            _log_conversation(text, [cal_reply], route="calendar_create")
            return [cal_reply]
    # fall through to LLM if extraction failed or unclear

    # Outreach intro email routing — bypass LLM, uses the broker email pipeline
    if _detect_outreach_email_intent(query):
        outreach_reply = _handle_outreach_email_request(query)
        if outreach_reply is not None:
            save_state(state)
            _log_conversation(text, [outreach_reply], route="outreach_email_send")
            return [outreach_reply]

    # Email send routing — bypass LLM, requires L2 Guardian approval
    if _detect_send_email_intent(query):
        email_reply = _handle_send_email(query)
        if email_reply is not None:
            save_state(state)
            _log_conversation(text, [email_reply], route="email_send")
            return [email_reply]
    # fall through to LLM if parsing failed

    # Invoice generation — PDF invoice via reportlab
    if _detect_invoice_intent(query):
        invoice_reply = _handle_create_invoice(query, state)
        if invoice_reply is not None:
            save_state(state)
            _log_conversation(text, [invoice_reply], route="invoice_create")
            return [invoice_reply]

    context  = build_context_snapshot(state)
    focus    = is_focus_mode()
    social   = is_social_mode()
    deep     = _should_use_deep(query)

    persona = _PERSONA
    if social:
        persona += _SOCIAL_NOTE
    if focus:
        persona += _FOCUS_NOTE
    persona += "\n" + _SPEECH_NOTE
    if _is_late_night():
        persona += "\n\n" + _LATE_NIGHT_NOTE
    persona += "\n\n" + _CAPABILITY_NOTE

    registry_ctx = registry_context_for_query(query)
    registry_block = f"{registry_ctx}\n\n" if registry_ctx else ""

    calendar_ctx   = _fetch_calendar_context(query)
    calendar_block = f"{calendar_ctx}\n\n" if calendar_ctx else ""

    gmail_ctx   = _fetch_gmail_context(query)
    gmail_block = f"{gmail_ctx}\n\n" if gmail_ctx else ""

    contacts_ctx   = _fetch_contacts_context(query)
    contacts_block = f"{contacts_ctx}\n\n" if contacts_ctx else ""

    # Cloud routing gate — evaluated after all context sources are known.
    # Passes context pieces (not the assembled prompt) so the check can inspect
    # exactly what was injected rather than pattern-matching the full prompt string.
    cloud_ok = _cassandra_context_clean(calendar_ctx, gmail_ctx, contacts_ctx, context, query)

    prompt = (
        f"{persona}\n"
        f"Current context:\n{context}\n\n"
        f"{capability_context()}\n\n"
        f"{calendar_block}"
        f"{gmail_block}"
        f"{contacts_block}"
        f"{registry_block}"
        f"User: {query}\n"
        f"Cassandra:"
    )

    try:
        reply = _call(prompt, deep, cloud_ok=cloud_ok)
    except Exception as e:
        print(f"[cassandra] _call error: {e}", flush=True)
        save_state(state)
        error_reply = ["I'm here, but I hit a snag thinking that through. Try again in a moment."]
        _log_conversation(text, error_reply, route="error")
        return error_reply
    reply = gate_reply(reply, query,
                       has_registry_context=registry_ctx is not None)
    reply = tts_clean(reply)

    contact_entry = _find_designated_contact(
        sender_name=session_meta.get("sender_name"),
        sender_chat_id=session_meta.get("sender_chat_id"),
    )
    should_queue_gap_followup = contact_entry is not None and not session_meta.get("followup_reprocess")
    if should_queue_gap_followup:
        capability_gaps = detect_capability_gaps(query, reply)
        if capability_gaps:
            reply = _append_partial_followup_note(reply)
            _record_gap_followups(
                sender_name=contact_entry["display_name"],
                sender_chat_id=session_meta.get("sender_chat_id"),
                original_message=query,
                partial_reply=reply,
                capability_gaps=capability_gaps,
            )
            if contact_entry.get("tier") == "client":
                _notify_client_urgency(contact_entry, query, reply, capability_gaps)

    save_state(state)

    result = [reply] if reply else ["I'm here — something went quiet on my end. Try again."]
    _log_conversation(text, result, route="llm_deep" if deep else "llm")
    return result
