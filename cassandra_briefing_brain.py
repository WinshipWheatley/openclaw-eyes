"""
cassandra_briefing_brain.py

Generates, archives, and manages delivery state for Cassandra's scheduled
daily briefings.  Used exclusively by cassandra_briefing_scheduler.py.

Slots
-----
  morning    08:00–09:30
  afternoon  13:00–14:30
  evening    20:00–21:30

Archive
-------
  /mnt/c/OpenClaw/logs/cassandra_briefings/YYYY-MM-DD_{slot}.json
  /mnt/c/OpenClaw/logs/cassandra_briefings/briefing_log.md   (append-only)

Each JSON record:
  {
    "slot":          "morning",
    "date":          "YYYY-MM-DD",
    "text":          "...",
    "generated_at":  "ISO datetime",
    "delivered":     false,
    "delivered_at":  null,
    "pending_reason": null | "focus_mode" | "album_session" | "approval_pending" | ...
  }

Protected-window checks (read-only, no imports from approval/session logic):
  1. Cassandra focus lock file
  2. Cassandra social lock file
  3. Chief session status (reads JSON directly)
  4. Scheduler running_work state (reads JSON directly)
  5. Pending approval (reads JSON directly)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from cassandra_brain import build_context_snapshot, is_focus_mode, is_social_mode
from chief_output_utils import tts_clean
from chief_llm import ollama_call, resolve_local_model
from chief_file_io import save_json, load_json, append_md_tagged

# ── Paths ─────────────────────────────────────────────────────────────────────

BRIEFING_DIR  = Path("/mnt/c/OpenClaw/logs/cassandra_briefings")
BRIEFING_LOG  = BRIEFING_DIR / "briefing_log.md"
_OPS_ACTIONS  = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Ops Actions.md")

# Read-only peeks at external state (no circular imports)
_SESSION_FILE     = Path("/home/openclaw/OpenClaw/state/chief_session.json")
_SCHEDULER_STATE  = Path("/mnt/c/OpenClawShared/album/scheduler_state.json")
_APPROVAL_PENDING = Path("/mnt/c/OpenClaw/logs/approval_pending.json")

# Treat very old pending approvals as stale so delayed/abandoned records
# do not keep Cassandra in a permanent protected window.
_APPROVAL_PENDING_MAX_AGE_SECONDS = 900
_APPROVAL_IGNORED_REQUESTERS = {
    "codex-test",
    "claude-test",
}

# ── Slot definitions ──────────────────────────────────────────────────────────

# {slot: (start_hour, end_hour_exclusive, briefing_directive)}
SLOTS = {
    "morning": (
        8, 10,
        "Generate the morning briefing. Use the MORNING BRIEFING CONTEXT above.\n"
        "Structure the output in this order — no section headers, flowing prose:\n"
        "1. Task milestone — call out the 400+ completed-task milestone if it is present in context.\n"
        "2. Financial status — what income is logged, what follow-ups are open.\n"
        "3. Music / album — where the album stands right now.\n"
        "4. Ocean City conditions — call the surf/golf/work directive by name.\n"
        "Close with a single decisive directive line: SURF MODE, GOLF WINDOW, or WORK MODE.\n"
        "If a data source shows unavailable, say so plainly in one clause and move on.\n"
        "3–5 sentences total. No filler. No motivational language. No markdown.",
    ),
    "afternoon": (
        13, 15,
        "Generate a brief afternoon check-in (3–4 sentences).\n"
        "Acknowledge the midday point.\n"
        "Highlight anything still unresolved from the morning if present.\n"
        "Name one priority for the afternoon.\n"
        "Be efficient. No filler.",
    ),
    "evening": (
        20, 22,
        "Generate a brief evening summary (3–4 sentences).\n"
        "Wind down the day — what's still open, what can wait until tomorrow.\n"
        "Keep the tone low-friction and calm.\n"
        "Close the briefing gently. Do not open new threads.",
    ),
}

# ── Protected-window detection ────────────────────────────────────────────────

def _read_json_safe(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _parse_requested_at(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for parser in (datetime.fromisoformat, lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S")):
        try:
            return parser(value)
        except Exception:
            continue
    return None


def _approval_pending_active() -> bool:
    approval = _read_json_safe(_APPROVAL_PENDING)
    if approval.get("status") != "pending":
        return False

    requester = str(approval.get("requester", "")).strip().lower()
    if requester in _APPROVAL_IGNORED_REQUESTERS:
        return False

    requested_at = _parse_requested_at(str(approval.get("requested_at", "")))
    if requested_at is not None:
        age = (datetime.now() - requested_at).total_seconds()
        if age > _APPROVAL_PENDING_MAX_AGE_SECONDS:
            return False

    return True


def protected_reason() -> str | None:
    """
    Return a short reason string if a protected window is active, else None.
    Reads state files directly — no imports from session/approval/router.
    """
    if is_focus_mode():
        return "focus_mode"
    if is_social_mode():
        return "social_mode"

    session = _read_json_safe(_SESSION_FILE)
    if session.get("status") == "active":
        workflow = session.get("active_workflow") or "workflow"
        return f"active_session:{workflow}"

    sched = _read_json_safe(_SCHEDULER_STATE)
    if sched.get("status") == "running_work":
        ends_at = sched.get("ends_at", "")
        try:
            if not ends_at or datetime.fromisoformat(ends_at) >= datetime.now():
                task = sched.get("task") or "work_block"
                return f"scheduler:{task}"
        except Exception:
            pass  # malformed ends_at — treat as idle

    if _approval_pending_active():
        return "approval_pending"

    return None


def is_protected_window() -> bool:
    return protected_reason() is not None


# ── Archive helpers ───────────────────────────────────────────────────────────

def _briefing_path(date: str, slot: str) -> Path:
    return BRIEFING_DIR / f"{date}_{slot}.json"


def load_briefing(date: str, slot: str) -> dict | None:
    p = _briefing_path(date, slot)
    if not p.exists():
        return None
    return load_json(p, None)


def save_briefing(slot: str, text: str, pending_reason: str | None) -> dict:
    """Write the generated briefing to the archive. Returns the entry dict."""
    now   = datetime.now()
    date  = now.date().isoformat()
    entry = {
        "slot":           slot,
        "date":           date,
        "text":           text,
        "generated_at":   now.isoformat(timespec="seconds"),
        "delivered":      False,
        "delivered_at":   None,
        "pending_reason": pending_reason,
    }
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    save_json(_briefing_path(date, slot), entry)

    # Append to markdown log
    tag  = f"{slot}/{'PENDING' if pending_reason else 'queued'}"
    append_md_tagged(BRIEFING_LOG, now.strftime("%Y-%m-%d %H:%M"), tag, text[:120] + "…")

    return entry


def mark_delivered(date: str, slot: str) -> None:
    p = _briefing_path(date, slot)
    entry = load_json(p, {})
    if not entry:
        return
    entry["delivered"]    = True
    entry["delivered_at"] = datetime.now().isoformat(timespec="seconds")
    entry["pending_reason"] = None
    save_json(p, entry)

    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_md_tagged(BRIEFING_LOG, ts, f"{slot}/delivered", "✓")


def refresh_briefing_text(date: str, slot: str, text: str, pending_reason: str | None = None) -> None:
    """Update archived briefing text before delayed delivery."""
    p = _briefing_path(date, slot)
    entry = load_json(p, {})
    if not entry:
        return
    entry["text"] = text
    entry["generated_at"] = datetime.now().isoformat(timespec="seconds")
    entry["pending_reason"] = pending_reason
    save_json(p, entry)


# ── Scheduling helpers ────────────────────────────────────────────────────────

def due_slots() -> list[str]:
    """
    Return slot names whose generation window is currently open
    and have not yet been generated today.
    """
    now   = datetime.now()
    today = now.date().isoformat()
    due   = []
    for slot, (start_h, end_h, _) in SLOTS.items():
        if start_h <= now.hour < end_h:
            if load_briefing(today, slot) is None:
                due.append(slot)
    return due


def pending_briefings() -> list[dict]:
    """Return today's archived briefings that have been generated but not delivered.
    Prior-day briefings are stale — they remain in the archive as undelivered
    historical records and are not re-delivered when a protected window clears.
    """
    result = []
    if not BRIEFING_DIR.exists():
        return result
    today = datetime.now().date().isoformat()
    for p in sorted(BRIEFING_DIR.glob("????-??-??_*.json")):
        entry = load_json(p, {})
        if entry and not entry.get("delivered") and entry.get("date") == today:
            result.append(entry)
    return result


# ── Action classification ─────────────────────────────────────────────────────

_DONE_RE = re.compile(
    r"\[done\]|\[completed\]|\[x\]|✓|~~.+~~|\(done\)",
    re.IGNORECASE,
)
_PRIORITY_RE = re.compile(
    r"\burgent\b|\basap\b|\bcritical\b|\bhigh.?priority\b|\btoday\b|\boverdue\b",
    re.IGNORECASE,
)


def classify_ops_actions(lines: list[str]) -> tuple[list[str], list[str]]:
    """
    Split action lines into (pending, completed).
    Lines matching _DONE_RE are completed; all others are pending.
    Pending list is sorted: priority items first.
    """
    pending: list[str] = []
    completed: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _DONE_RE.search(stripped):
            completed.append(stripped)
        else:
            pending.append(stripped)
    pending.sort(key=lambda l: (0 if _PRIORITY_RE.search(l) else 1))
    return pending, completed


def build_action_summary(n_actions: int = 12) -> str:
    """
    Read Ops Actions.md, classify into pending/completed, and return a
    structured summary string with counts and priority items first in Pending.
    Used to enrich the morning briefing context.
    """
    lines: list[str] = []
    if _OPS_ACTIONS.exists():
        raw = _OPS_ACTIONS.read_text(encoding="utf-8").splitlines()
        lines = [
            l.strip() for l in raw
            if l.strip() and not l.startswith("#") and not l.startswith("---")
        ][-n_actions:]

    pending, completed = classify_ops_actions(lines)

    parts: list[str] = []
    parts.append(f"Pending ({len(pending)}):")
    if pending:
        for item in pending:
            marker = "[PRIORITY] " if _PRIORITY_RE.search(item) else ""
            parts.append(f"  {marker}{item}")
    else:
        parts.append("  (none)")

    parts.append(f"Completed ({len(completed)}):")
    if completed:
        for item in completed:
            parts.append(f"  {item}")
    else:
        parts.append("  (none)")

    return "\n".join(parts)


# ── LLM generation ────────────────────────────────────────────────────────────

_PERSONA_BRIEF = """\
You are Cassandra, Executive Assistant to the Founder.
Character: calm, precise, discreet, honest. Hard to rattle.
No filler. No preamble. No motivational language.
Respond directly — your output IS the briefing, ready to send.

Response discipline:
- Lead with the answer. Expand only when it materially improves decision quality.
- Separate confirmed, inferred, and unknown clearly. Never use fake certainty.
- Status order: active lane first, verified live, code/test-only, unresolved, exact next action, backlog.
- Name the exact context when relevant: Mac, PowerShell, WSL, tmux, Telegram, Claude prompt, or vault/repo.
- Treat handoff and Drive docs as reflection layers. Finance state is source of truth for client, invoice, and payment workflow. Vault and repo are source of truth for the rest.

Capability honesty (always):
- Every claim must be labeled by source: "the log shows", "what's in Ops Actions", "based on the note" — never presented as externally verified fact.
- DO NOT SAY "your calendar shows", "the payment hasn't cleared", "the deposit is pending" as real-world fact.
- INSTEAD SAY "what's logged", "I can't confirm externally", "the follow-up is still open in the log".
- Never say a task was completed, sent, or synced unless the log entry explicitly confirms it.\
- When a FINANCE STATE block appears, treat it as higher priority than raw historical log lines for client, invoice, and payment facts.\
- When a CANONICAL REALITY block appears, treat it as higher priority than raw historical log lines. If a raw log conflicts with canonical reality, follow canonical reality.\
"""


def generate_briefing(slot: str) -> str:
    """
    Call the fast local LLM to generate a briefing for the given slot.
    Returns the briefing text (may be a fallback if LLM fails).
    Morning slot prepends the morning briefing context block (task/financial/music/surf).
    """
    _, _, directive = SLOTS[slot]
    context = build_context_snapshot()

    if slot == "morning":
        # Morning briefing context: task milestone, financial, music, surf/weather cue.
        try:
            from cassandra_briefing_morning_context import build_morning_briefing_context
            morning_context = build_morning_briefing_context()
        except Exception as _e:
            morning_context = f"[morning briefing context unavailable: {_e}]"

        # Classified action summary alongside the morning context block.
        action_summary = build_action_summary()
        context = (
            f"{morning_context}\n\n"
            f"Action summary:\n{action_summary}\n\n"
            f"{context}"
        )

    prompt = (
        f"{_PERSONA_BRIEF}\n\n"
        f"Current context:\n{context}\n\n"
        f"Task — {slot} briefing:\n{directive}\n\n"
        f"Cassandra:"
    )

    task_class = "cassandra_morning_brief" if slot == "morning" else "cassandra_user_reply"
    model, _lane = resolve_local_model(prompt, task_class=task_class)
    result = ollama_call(prompt, timeout=45, model=model)
    if result:
        return tts_clean(result.strip())

    # Minimal fallback if LLM is unreachable — for morning, include the morning context summary.
    ts = datetime.now().strftime("%H:%M")
    if slot == "morning":
        try:
            from cassandra_briefing_morning_context import (
                _task_milestone_snapshot,
                _financial_snapshot,
                _music_snapshot,
                _surf_cue_text,
            )
            fallback_body = " ".join([
                _task_milestone_snapshot(),
                _financial_snapshot().replace("\n", " "),
                _music_snapshot(),
                _surf_cue_text(),
            ])
            return tts_clean(f"[{ts} — morning briefing, LLM offline] {fallback_body}")
        except Exception:
            pass

    return (
        f"[{ts} — {slot} log unavailable. LLM did not respond. "
        "Check Ollama and retry.]"
    )


# ── Recall ────────────────────────────────────────────────────────────────────

_RECALL_PATTERNS = (
    "morning log", "afternoon log", "evening log",
    "morning briefing", "afternoon briefing", "evening briefing",
    "last briefing", "today's briefing", "briefing log",
    "recall briefing", "show briefing", "what was the briefing",
    "what was this morning", "what was this afternoon", "what was tonight",
)


def is_recall_request(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _RECALL_PATTERNS)


def handle_recall(text: str) -> str:
    """Return archived briefing text for a recall request, or a not-found message."""
    t     = today = datetime.now().date().isoformat()
    lower = text.lower()

    # Determine which slot was requested
    if "morning" in lower:
        slots_to_try = ["morning"]
    elif "afternoon" in lower:
        slots_to_try = ["afternoon"]
    elif "evening" in lower or "tonight" in lower or "night" in lower:
        slots_to_try = ["evening"]
    else:
        # "last briefing" — return most recent delivered one across all slots
        slots_to_try = list(SLOTS.keys())

    for slot in slots_to_try:
        entry = load_briefing(today, slot)
        if entry and entry.get("text"):
            delivered = "delivered" if entry.get("delivered") else "pending delivery"
            return (
                f"[{slot.title()} · {today} · {delivered}]\n\n"
                + entry["text"]
            )

    return f"No briefing archived for today ({today}). Check back after the scheduled window."
