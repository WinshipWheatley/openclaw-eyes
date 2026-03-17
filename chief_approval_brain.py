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

def request_approval(action: str, requester: str = "OpenClaw") -> bool:
    """
    Send a Telegram approval request and block until YES/NO or timeout.

    Returns True if approved, False if denied or timed out.
    Logs every decision to the vault Approval Log.
    """
    approval_id = str(uuid.uuid4())[:8].upper()
    requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = time.time()

    pending = {
        "id":           approval_id,
        "action":       action,
        "requester":    requester,
        "requested_at": requested_at,
        "status":       "pending",
        "decision":     None,
    }
    _save_pending(pending)

    _send(
        f"{action}\n"
        f"1. Yes\n"
        f"2. No"
    )

    # Poll for decision
    while time.time() - start < TIMEOUT:
        time.sleep(POLL_INTERVAL)
        data = _load_pending()
        if data.get("id") == approval_id and data.get("status") == "decided":
            decision = data.get("decision", "NO").upper()
            elapsed = time.time() - start
            _clear_pending()
            approved = decision == "YES"
            _append_log(action, requester, "APPROVED" if approved else "DENIED",
                        requested_at, elapsed)
            _send(f"✅ Approved." if approved else f"❌ Denied.")
            return approved

    # Timeout
    elapsed = time.time() - start
    _clear_pending()
    _append_log(action, requester, "TIMED OUT", requested_at, elapsed)
    _send(f"⏱ Approval timed out — denied by default.")
    return False


def record_decision(decision: str) -> str:
    """
    Called by the listener when the user replies to a pending approval.
    Accepts YES/NO or 1/2 (1=Yes, 2=No).
    Returns a brief reply string to send back to the user.
    """
    data = _load_pending()
    if not data or data.get("status") != "pending":
        return "No pending approval request found."

    d = decision.strip().upper()
    # Accept numbered shorthand
    if d == "1":
        d = "YES"
    elif d == "2":
        d = "NO"

    if d not in ("YES", "NO"):
        return "Reply 1 (Yes) or 2 (No)."

    data["status"]   = "decided"
    data["decision"] = d
    _save_pending(data)

    if d == "YES":
        return "✅ Approved."
    else:
        return "❌ Denied."


def has_pending_approval() -> bool:
    """True if there is a pending (unanswered) approval request."""
    data = _load_pending()
    return bool(data) and data.get("status") == "pending"


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chief_approval_brain.py \"action description\"")
        sys.exit(1)

    action_desc = " ".join(sys.argv[1:])
    requester   = "Claude Code"

    approved = request_approval(action_desc, requester)
    sys.exit(0 if approved else 1)
