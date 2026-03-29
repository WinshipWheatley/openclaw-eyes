"""
chief_approval_bridge.py

Multi-choice approval bridge for Chief workflows.

Chief calls send_choice() to push a numbered prompt to Telegram.
User replies with 1 / 2 / 3 / approve / deny.
Router reads the response and writes the decision.

Commands:
  1 / 2 / 3  — select option by number
  approve    — select option 1 (or signal yes on binary request)
  deny       — reject / cancel
  status     — show current pending request

This is separate from chief_approval_brain.py (which gates Claude Code
destructive actions via blocking YES/NO polls). This bridge is for
non-blocking multi-step Chief workflow choices.

How to use from another brain:
    from chief_approval_bridge import send_choice, last_answer, clear_resolved
    send_choice("Which format for the invoice?", ["PDF", "Google Doc", "Both"])
    # User replies "2" → last_answer() returns {"answer": "2", "chosen": "Google Doc"}

State: /mnt/c/OpenClawShared/album/choice_pending.json
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

_CHOICE_TIMEOUT_MINUTES = 30

PENDING_FILE = Path("/mnt/c/OpenClawShared/album/choice_pending.json")


# ── State ─────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if PENDING_FILE.exists():
        try:
            return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _clear() -> None:
    _save({})


# ── Public API ────────────────────────────────────────────────────────────────

def _is_choice_expired(data: dict) -> bool:
    """Return True if a pending choice is older than _CHOICE_TIMEOUT_MINUTES."""
    requested_at = data.get("requested_at", "")
    if not requested_at:
        return False
    try:
        age_s = (datetime.now() - datetime.fromisoformat(requested_at)).total_seconds()
        return age_s > _CHOICE_TIMEOUT_MINUTES * 60
    except Exception:
        return False


def has_pending_choice() -> bool:
    """True if there is an unanswered, non-expired choice request."""
    return pending_choice() is not None


def pending_choice() -> dict | None:
    """Return the current pending choice dict, or None if none/expired."""
    data = _load()
    if data.get("status") != "pending":
        return None
    if _is_choice_expired(data):
        data.update({"status": "expired", "answer": "timeout", "chosen": None,
                     "resolved_at": datetime.now().isoformat()})
        _save(data)
        return None
    return data


def send_choice(prompt: str, options: list[str], requester: str = "Chief") -> str:
    """
    Push a numbered choice prompt to Telegram. Non-blocking.
    Returns request_id. Result is read later via last_answer().
    """
    from chief_notify import send as notify_send

    request_id = str(uuid.uuid4())[:8].upper()
    data = {
        "id":           request_id,
        "prompt":       prompt,
        "options":      options,
        "requester":    requester,
        "requested_at": datetime.now().isoformat(),
        "status":       "pending",
        "answer":       None,
        "chosen":       None,
    }
    _save(data)

    lines = [f"❓ *{prompt}*\n"]
    for i, opt in enumerate(options, 1):
        lines.append(f"  {i}. {opt}")
    lines.append("\nReply `1`/`2`/`3`, `approve`, or `deny`.")
    # Build inline keyboard: one row per option, callback_data = "1"/"2"/"3"
    keyboard = {
        "inline_keyboard": [
            [{"text": f"{i}. {opt}", "callback_data": str(i)}]
            for i, opt in enumerate(options, 1)
        ]
    }
    notify_send("\n".join(lines), reply_markup=keyboard)

    return request_id


def last_answer() -> dict | None:
    """Return the most recently resolved choice (id, answer, chosen), or None."""
    data = _load()
    return data if data.get("status") == "resolved" else None


def clear_resolved() -> None:
    """Remove a resolved choice so it isn't re-read."""
    data = _load()
    if data.get("status") == "resolved":
        _clear()


# ── Handler (called by router) ────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    t = text.strip().lower()
    data = _load()

    # Status — always available regardless of pending state
    if t in ("status", "approval status", "choice status") or \
            "approval status" in t or "choice status" in t:
        if not data:
            return ["No pending approval request."]
        status  = data.get("status", "?")
        prompt  = data.get("prompt", "?")
        opts    = data.get("options", [])
        req_id  = data.get("id", "?")
        lines   = [f"[{req_id}] {prompt}", f"Status: {status}"]
        for i, o in enumerate(opts, 1):
            lines.append(f"  {i}. {o}")
        if status == "resolved":
            lines.append(f"Answered: {data.get('answer')} → {data.get('chosen')}")
        return ["\n".join(lines)]

    if not data or data.get("status") != "pending":
        return ["No pending choice request."]

    options = data.get("options", [])
    n_opts  = len(options)

    # Select by number
    if t in ("1", "2", "3") or (t.isdigit() and 1 <= int(t) <= n_opts):
        idx = int(t) - 1
        if idx >= n_opts:
            return [f"Only {n_opts} option(s). Reply 1–{n_opts}."]
        chosen = options[idx]
        data.update({"status": "resolved", "answer": t, "chosen": chosen,
                     "resolved_at": datetime.now().isoformat()})
        _save(data)
        return [f"✅ Selected: {chosen}"]

    # approve = option 1
    if t == "approve":
        chosen = options[0] if options else "approved"
        data.update({"status": "resolved", "answer": "approve", "chosen": chosen,
                     "resolved_at": datetime.now().isoformat()})
        _save(data)
        return [f"✅ Approved: {chosen}"]

    # deny = cancel
    if t == "deny":
        data.update({"status": "resolved", "answer": "deny", "chosen": None,
                     "resolved_at": datetime.now().isoformat()})
        _save(data)
        return [f"❌ Denied: {data.get('prompt', '')}"]

    return [f"Reply 1–{n_opts}, `approve`, or `deny`."]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print("\n".join(handle(" ".join(sys.argv[1:]))))
    else:
        # Demo: send a test choice
        rid = send_choice(
            "Test choice from CLI",
            ["Option A", "Option B", "Option C"],
            requester="CLI test",
        )
        print(f"Choice sent, id={rid}")
