"""
chief_approval_brain.py

Gatekeeper for all destructive, publishing, and irreversible actions.
Any brain or Claude Code session calls request_approval() before proceeding.

Usage as Python function:
    from chief_approval_brain import request_approval
    approved = request_approval("Delete Blue Weather.md", "Claude Code")
    if not approved:
        sys.exit("Action denied.")

Usage as CLI (for Claude Code shell calls):
    python3 /home/openclaw/chief_approval_brain.py "Delete Blue Weather.md"
    # exit code 0 = approved, exit code 1 = denied or timed out

Router intent: approval_response — triggered when incoming text is YES/NO
and a pending approval exists.
"""

import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

PENDING_FILE  = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
VAULT_LOG     = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md")
POLL_INTERVAL = 2    # seconds between checks
TIMEOUT       = 300  # 5 minutes


# ── Pending state ──────────────────────────────────────────────────────────────

def _load_pending() -> dict:
    if PENDING_FILE.exists():
        try:
            return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_pending(data: dict) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _clear_pending() -> None:
    _save_pending({})


# ── Approval log ───────────────────────────────────────────────────────────────

def _append_log(action: str, requester: str, decision: str,
                requested_at: str, elapsed: float) -> None:
    decided_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n## {requested_at}\n"
        f"- **Requester:** {requester}\n"
        f"- **Action:** {action}\n"
        f"- **Decision:** {decision}\n"
        f"- **Decided at:** {decided_at}\n"
        f"- **Elapsed:** {int(elapsed)}s\n"
    )
    if VAULT_LOG.exists():
        content = VAULT_LOG.read_text(encoding="utf-8")
        # Remove the placeholder line if it's the only content after frontmatter
        content = content.replace("\n_(no decisions recorded yet)_\n", "\n")
        VAULT_LOG.write_text(content + entry, encoding="utf-8")
    else:
        VAULT_LOG.write_text(entry, encoding="utf-8")


# ── Telegram sender ────────────────────────────────────────────────────────────

def _send(message: str) -> None:
    subprocess.run(
        ["python3", str(Path.home() / "chief_sender.py"), message],
        check=False,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def _build_prompt(action: str, options: int) -> str:
    """Render the approval prompt with the exact valid options for this request.

    options=2  →  1. Yes  /  2. No
    options=3  →  1. Yes  /  2. Yes for all  /  3. No
    """
    if options == 3:
        return f"{action}\n1. Yes\n2. Yes for all\n3. No"
    return f"{action}\n1. Yes\n2. No"


def request_approval(
    action: str,
    requester: str = "OpenClaw",
    allow_yes_for_all: bool = False,
) -> bool:
    """
    Send a Telegram approval request and block until the user responds or timeout.

    allow_yes_for_all=False  →  2-option prompt: 1. Yes / 2. No
    allow_yes_for_all=True   →  3-option prompt: 1. Yes / 2. Yes for all / 3. No

    Returns True if approved (Yes or Yes for all), False if denied or timed out.
    Logs every decision to the vault Approval Log.

    If an album session is active when this is called, saves an album
    snapshot so the listener can resume precisely after the gate closes.
    """
    approval_id = str(uuid.uuid4())[:8].upper()
    requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = time.time()

    options = 3 if allow_yes_for_all else 2
    pending = {
        "id":           approval_id,
        "action":       action,
        "requester":    requester,
        "requested_at": requested_at,
        "status":       "pending",
        "decision":     None,
        "options":      options,   # 2 or 3 — tells record_decision() what numbers are valid
    }

    # Snapshot the active album session so the listener can resume it cleanly.
    # The snapshot is read by the listener *before* _clear_pending() is called
    # by the poll loop below, so the race window is the poll interval (2s).
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _home = str(_Path.home())
        if _home not in _sys.path:
            _sys.path.insert(0, _home)
        from chief_session_manager import load_session as _load_sess
        _s = _load_sess()
        if _s.get("status") == "active" and _s.get("active_workflow") == "album":
            _wf = _s.get("workflow_state", {})
            pending["gating_workflow"] = "album"
            pending["album_snapshot"] = {
                "song_title":       _wf.get("song_title", ""),
                "last_topic_asked": _wf.get("last_topic_asked"),
                "phase":            _wf.get("phase", ""),
            }
    except Exception:
        pass

    _save_pending(pending)
    _send(_build_prompt(action, options))

    # Poll for decision
    while time.time() - start < TIMEOUT:
        time.sleep(POLL_INTERVAL)
        data = _load_pending()
        if data.get("id") == approval_id and data.get("status") == "decided":
            decision = data.get("decision", "NO").upper()
            elapsed = time.time() - start
            approved = decision == "YES"
            _append_log(action, requester, "APPROVED" if approved else "DENIED",
                        requested_at, elapsed)
            _clear_pending()
            # NOTE: do NOT call _send() here for the decision reply.
            # The listener already sent "✅ Approved." / "❌ Denied." from
            # record_decision()'s return value. Sending again is a duplicate.
            return approved

    # Timeout — user never responded; send notification since listener cannot.
    elapsed = time.time() - start
    _clear_pending()
    _append_log(action, requester, "TIMED OUT", requested_at, elapsed)
    _send("⏱ Approval timed out — denied by default.")
    return False


def record_decision(decision: str) -> str:
    """
    Called by the listener when the user replies to a pending approval.

    2-option (default):  1=Yes, 2=No
    3-option:            1=Yes, 2=Yes for all, 3=No

    The option count is read from the pending JSON so the mapping is always
    consistent with the prompt that was actually shown.
    Returns a brief reply string to send back to the user.
    """
    data = _load_pending()
    if not data or data.get("status") != "pending":
        return "No pending approval request found."

    options = data.get("options", 2)   # default to 2 for any legacy pending records
    raw = decision.strip().upper()

    if options == 3:
        # 3-option: 1. Yes  2. Yes for all  3. No
        if raw == "1" or raw == "YES":
            d = "YES"
        elif raw == "2" or raw == "YES_FOR_ALL":
            d = "YES_FOR_ALL"
        elif raw == "3" or raw == "NO":
            d = "NO"
        else:
            return "Reply 1 (Yes), 2 (Yes for all), or 3 (No)."
    else:
        # 2-option: 1. Yes  2. No
        if raw == "1" or raw == "YES":
            d = "YES"
        elif raw == "2" or raw == "NO":
            d = "NO"
        else:
            return "Reply 1 (Yes) or 2 (No)."

    data["status"]   = "decided"
    data["decision"] = d
    _save_pending(data)

    if d == "YES":
        return "✅ Approved."
    elif d == "YES_FOR_ALL":
        return "✅ Approved for all."
    else:
        return "❌ Denied."


def get_pending_album_snapshot() -> dict | None:
    """Return the album snapshot saved when this approval was requested, or None.

    Called by chief_listener AFTER recording the decision but BEFORE the
    polling loop clears the pending file. The snapshot is used to resume
    album flow precisely after the gate closes.

    Returns None if the approval was not gating an album session, or if
    the pending file has already been cleared.
    """
    data = _load_pending()
    # Works for both "pending" and "decided" states — listener reads this
    # before the CLI poll loop calls _clear_pending().
    if data.get("status") not in ("pending", "decided"):
        return None
    return data.get("album_snapshot")   # None if no snapshot was saved


def has_pending_approval() -> bool:
    """True if there is a fresh, pending (unanswered) approval request.
    Auto-clears stale pending records so they cannot interrupt unrelated
    sessions after the original requester has already timed out.
    """
    data = _load_pending()
    if not data or data.get("status") != "pending":
        return False
    # Auto-clear requests that are older than TIMEOUT — the requester has
    # already timed out and logged a denial, so this record is dead weight.
    try:
        requested_at = data.get("requested_at", "")
        if requested_at:
            age = (datetime.now()
                   - datetime.strptime(requested_at, "%Y-%m-%d %H:%M:%S")
                   ).total_seconds()
            if age > TIMEOUT:
                _clear_pending()
                return False
    except Exception:
        pass
    return True


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chief_approval_brain.py \"action description\"")
        sys.exit(1)

    action_desc = " ".join(sys.argv[1:])
    requester   = "Claude Code"

    approved = request_approval(action_desc, requester)
    sys.exit(0 if approved else 1)
