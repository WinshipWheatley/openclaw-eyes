"""
chief_approval_brain.py

Gatekeeper for all destructive, publishing, and irreversible actions.
Any brain or Claude Code session calls request_approval() before proceeding.

Tier model:
  Tier 0 — No gate. Action proceeds immediately.
  Tier 1 — Local terminal confirmation (y/N). Escalates to Tier 2 if no TTY.
  Tier 2 — Remote phone approval via Guardian bot (out-of-band authorization).

Usage as Python function:
    from chief_approval_brain import request_approval
    approved = request_approval("Delete Blue Weather.md", "Claude Code")
    if not approved:
        sys.exit("Action denied.")

    # Override auto-classified tier:
    approved = request_approval("...", explicit_tier=2)

Usage as CLI (for Claude Code shell calls):
    python3 /home/openclaw/chief_approval_brain.py "plain English description"
    # exit code 0 = approved, exit code 1 = denied or timed out

Router intent: approval_response — triggered when incoming text is YES/NO
and a pending approval exists.
"""

import hashlib
import hmac as _hmac_mod
import json
import os
import subprocess
import sys
import fcntl
import time
import uuid
from datetime import datetime
from pathlib import Path

PENDING_FILE    = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
VAULT_LOG       = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md")
_SLOT_LOCK_FILE = Path.home() / ".chief_approval.lock"  # local ext4 — reliable flock
POLL_INTERVAL   = 2     # seconds between checks
TIMEOUT         = 300   # 5 minutes


# ── Lazy imports with fallback ─────────────────────────────────────────────────
# Guardian sender and policy are new modules. Import lazily so existing code
# continues to function even if a partial rollout or import error occurs.

def _get_policy_tier(action: str) -> int:
    try:
        from chief_approval_policy import classify
        return classify(action)
    except ImportError:
        return 2  # safe default


def _is_hard_t2(action: str) -> bool:
    """
    Return True if the action matches a T2 hard rule that cannot be overridden.
    Safe-defaults to True on import failure so the gate never silently opens.
    """
    try:
        from chief_approval_policy import is_hard_t2
        return is_hard_t2(action)
    except ImportError:
        return True  # safe default: treat as hard T2 if policy unavailable


def _build_l2_keyboard(approval_id: str, options: int, allow_delay: bool = True) -> dict:
    """
    Build an inline keyboard dict for the L2 approval message.
    Returns a plain dict ready for JSON serialisation into the Telegram API —
    no PTB dependency so it can be used from both brain and raw-requests sender.
    Callback data format: 'DECISION:APPROVAL_ID' — binds each tap to the specific
    approval ID, so stale button presses from a previous approval are rejected.

    allow_delay: when False, omits the [Delay] button. Used on re-sent messages
    to prevent cascade (tapping Delay on the re-sent message → another re-send → loop).
    One delay per approval cycle is the intended model.
    """
    rc = approval_id
    # Meta-row: [Delay] is omitted on re-sent messages to prevent cascade loops.
    _meta_row = (
        [
            {"text": "Delay 5m", "callback_data": f"DELAY:{rc}"},
            {"text": "Why now?", "callback_data": f"WHY:{rc}"},
        ]
        if allow_delay
        else [
            {"text": "Why now?", "callback_data": f"WHY:{rc}"},
        ]
    )
    if options == 3:
        return {
            "inline_keyboard": [
                [
                    {"text": "Approve", "callback_data": f"YES:{rc}"},
                    {"text": "Approve All", "callback_data": f"YES_FOR_ALL:{rc}"},
                ],
                [
                    {"text": "Deny", "callback_data": f"NO:{rc}"},
                ],
                _meta_row,
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"YES:{rc}"},
                {"text": "Deny", "callback_data": f"NO:{rc}"},
            ],
            _meta_row,
        ]
    }


def _send_via_guardian(message: str, keyboard: dict | None = None) -> None:
    try:
        from chief_guardian_sender import send_approval
        send_approval(message, reply_markup=keyboard)
    except (ImportError, Exception) as e:
        print(f"[approval] Guardian send failed ({e!r}), falling back to Chief bot.", flush=True)
        _send_chief(message)
        # Chief bot fallback does not support inline keyboards — the typed CODE DECISION
        # path on the Chief channel remains available as intentional fallback.


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


# ── Pending-slot advisory lock ─────────────────────────────────────────────────
# Uses fcntl.LOCK_EX on a local ext4 file to make the check-then-write
# critical section atomic across separate processes.  The lock is held only
# during that section (< 1 ms); it is released before Guardian sends or polling.

def _acquire_slot_lock():
    """
    Open _SLOT_LOCK_FILE and acquire an exclusive advisory flock.
    Returns the open file object (lock held) on success, or None on failure.
    Failure falls back to non-atomic behaviour with a logged warning — the
    single-process collision guard still applies in that case.
    """
    try:
        lf = _SLOT_LOCK_FILE.open("w")
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        return lf
    except Exception as e:
        print(
            f"[approval] WARNING: slot lock unavailable ({e!r}) — "
            "falling back to non-atomic pending check.",
            flush=True,
        )
        return None


def _release_slot_lock(lf) -> None:
    """Release the lock returned by _acquire_slot_lock()."""
    if lf is None:
        return
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        lf.close()
    except Exception:
        pass


# ── HMAC action hash ───────────────────────────────────────────────────────────

def _compute_hash(action: str, approval_id: str, requested_at: str) -> str:
    """
    Compute a short HMAC-SHA256 hash linking the action, id, and timestamp.
    Returns empty string if APPROVAL_HMAC_SECRET is not configured.
    The hash appears in both the Telegram message and pending JSON.
    Tampering with the action in the JSON would produce a hash mismatch.
    """
    secret = os.environ.get("APPROVAL_HMAC_SECRET", "").encode()
    if not secret:
        return ""
    msg = f"{action}|{approval_id}|{requested_at}".encode()
    return _hmac_mod.new(secret, msg, hashlib.sha256).hexdigest()[:12].upper()


def _verify_hash(action: str, approval_id: str, requested_at: str, stored_hash: str) -> bool:
    """Verify the action hash. Returns True if hash matches or if hashing is disabled."""
    if not stored_hash:
        return True  # Hashing not configured — pass through
    expected = _compute_hash(action, approval_id, requested_at)
    if not expected:
        return True  # Secret not set on this call — pass through
    return _hmac_mod.compare_digest(expected, stored_hash)


# ── Approval log ───────────────────────────────────────────────────────────────

def _append_log(action: str, requester: str, decision: str,
                requested_at: str, elapsed: float, tier: int = 2) -> None:
    decided_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tier_labels = {0: "L0-pass", 1: "L1-terminal", 2: "L2-phone"}
    entry = (
        f"\n## {requested_at}\n"
        f"- **Requester:** {requester}\n"
        f"- **Action:** {action}\n"
        f"- **Tier:** {tier_labels.get(tier, 'L2-phone')}\n"
        f"- **Decision:** {decision}\n"
        f"- **Decided at:** {decided_at}\n"
        f"- **Elapsed:** {int(elapsed)}s\n"
    )
    if VAULT_LOG.exists():
        content = VAULT_LOG.read_text(encoding="utf-8")
        content = content.replace("\n_(no decisions recorded yet)_\n", "\n")
        VAULT_LOG.write_text(content + entry, encoding="utf-8")
    else:
        VAULT_LOG.write_text(entry, encoding="utf-8")


# ── Telegram senders ───────────────────────────────────────────────────────────

def _send_chief(message: str) -> None:
    """Send via Chief bot (used for timeout/error notifications)."""
    subprocess.run(
        ["python3", str(Path.home() / "chief_sender.py"), message],
        check=False,
    )


# ── Approval message builder ───────────────────────────────────────────────────

def _build_l2_message(action: str, approval_id: str, action_hash: str,
                      options: int) -> str:
    """Build the structured L2 approval message sent to the Guardian bot."""
    hash_line = f"\nHash: {action_hash}" if action_hash else ""
    risk_line = "\nRisk: Irreversible" if _is_hard_t2(action) else "\nRisk: Recoverable"
    rc = approval_id[:4]  # 4-char reply code — user must prefix replies with this
    if options == 3:
        choice_line = (
            f"\n\nReply code: {rc}\n"
            f"{rc} 1 — Approve\n"
            f"{rc} 2 — Approve for all\n"
            f"{rc} 3 — Deny"
        )
    else:
        choice_line = (
            f"\n\nReply code: {rc}\n"
            f"{rc} 1 — Approve\n"
            f"{rc} 2 — Deny"
        )

    return (
        f"APPROVAL REQUIRED\n\n"
        f"ID: {approval_id}\n"
        f"Action: {action}{hash_line}{risk_line}\n"
        f"Expires: 5 min"
        f"{choice_line}"
    )


def _build_l1_prompt(action: str) -> str:
    return f"\n  Action: {action}\n  Proceed? [y/N]: "


# ── Level 1 — local terminal confirmation ─────────────────────────────────────

def _confirm_terminal(action: str) -> bool | None:
    """
    Prompt for local terminal confirmation.
    Returns True (confirmed), False (denied), or None (no TTY — escalate to L2).
    """
    if not sys.stdin.isatty():
        return None  # No TTY — caller should escalate to L2
    try:
        sys.stdout.write(f"\nL1 Confirm required:\n{_build_l1_prompt(action)}")
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        return answer in ("y", "yes")
    except (EOFError, OSError):
        return None  # Treat as no TTY — escalate


# ── Public API ─────────────────────────────────────────────────────────────────

def _build_prompt(action: str, options: int) -> str:
    """Legacy prompt builder — kept for backward compatibility with any callers
    that pass options directly. New code uses _build_l2_message."""
    if options == 3:
        return f"{action}\n1. Yes\n2. Yes for all\n3. No"
    return f"{action}\n1. Yes\n2. No"


def request_approval(
    action: str,
    requester: str = "OpenClaw",
    allow_yes_for_all: bool = False,
    explicit_tier: int | None = None,
) -> bool:
    """
    Request approval for an action, using the appropriate tier:

      Tier 0 — Proceed immediately (no gate).
      Tier 1 — Local terminal y/N prompt; escalates to Tier 2 if no TTY.
      Tier 2 — Remote phone approval via Guardian bot; blocks until response
                or 5-minute timeout (auto-deny).

    explicit_tier overrides auto-classification. Tier 2 hard rules in
    chief_approval_policy.py cannot be downgraded by explicit_tier.

    Returns True if approved, False if denied or timed out.
    Logs every Tier 1/2 decision to the vault Approval Log.
    """
    # Determine tier
    if explicit_tier is not None:
        tier = explicit_tier
        # T2 hard rules are structurally prior — explicit_tier cannot suppress them.
        # _is_hard_t2 checks only hardcoded T2 patterns, not the T2 default for unknowns,
        # so callers retain the ability to specify tier for unrecognized actions.
        if _is_hard_t2(action):
            tier = 2
    else:
        tier = _get_policy_tier(action)

    # ── Tier 0: no gate ────────────────────────────────────────────────────────
    if tier == 0:
        return True

    # ── Tier 1: local terminal confirmation ───────────────────────────────────
    if tier == 1:
        result = _confirm_terminal(action)
        if result is not None:
            # Got a real answer from the terminal
            start = time.time()
            elapsed = time.time() - start
            decision = "APPROVED" if result else "DENIED"
            _append_log(action, requester, decision,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), elapsed, tier=1)
            return result
        # No TTY — fall through to Tier 2
        print(f"[approval] No TTY detected — escalating L1 to L2 phone approval.", flush=True)
        tier = 2

    # ── Tier 2: remote phone approval ─────────────────────────────────────────
    # Build the approval payload before acquiring the slot lock so the
    # critical section (check → write) is as short as possible (< 1 ms).
    approval_id = str(uuid.uuid4())[:8].upper()
    requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start = time.time()
    options = 3 if allow_yes_for_all else 2

    action_hash = _compute_hash(action, approval_id, requested_at)

    pending = {
        "id":           approval_id,
        "action":       action,
        "requester":    requester,
        "requested_at": requested_at,
        "status":       "pending",
        "decision":     None,
        "options":      options,
        "tier":         tier,
        "hash":         action_hash,
    }

    # Snapshot active album session so listener can resume after gate closes.
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

    # Atomic slot claim: acquire exclusive advisory flock → check → write → release.
    # The lock closes the TOCTOU race between has_pending_approval() and
    # _save_pending() across separate processes.  All payload construction is done
    # above; only the check and the write happen inside the lock.
    # Slow operations (Guardian send, polling) run after the lock is released.
    _slot_lf = _acquire_slot_lock()
    _collision = has_pending_approval()
    if not _collision:
        _save_pending(pending)
    _release_slot_lock(_slot_lf)

    if _collision:
        _collision_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[approval] DENIED: L2 collision — another approval is already in flight. "
            f"action={action!r}",
            flush=True,
        )
        _append_log(action, requester, "DENIED - L2 COLLISION", _collision_at, 0.0, tier=tier)
        _send_via_guardian(
            f"[blocked] L2 request denied — another approval is already pending.\n"
            f"Action: {action}\nRetry after the current approval resolves."
        )
        return False

    _send_via_guardian(
        _build_l2_message(action, approval_id, action_hash, options),
        keyboard=_build_l2_keyboard(approval_id, options),
    )

    # Poll for decision
    while time.time() - start < TIMEOUT:
        time.sleep(POLL_INTERVAL)
        data = _load_pending()
        if data.get("id") == approval_id and data.get("status") == "decided":
            decision = data.get("decision", "NO").upper()
            elapsed = time.time() - start
            approved = decision in ("YES", "YES_FOR_ALL")

            # Hash verification — deny on mismatch (hardened 2026-03-21).
            # Inert when APPROVAL_HMAC_SECRET is not set: stored_hash is "" → falsy
            # → this block never executes. Mismatch means the pending file was
            # modified after the approval request was written.
            stored_hash = data.get("hash", "")
            if stored_hash and not _verify_hash(action, approval_id, requested_at, stored_hash):
                print(f"[approval] DENIED: hash mismatch on approval {approval_id}. "
                      "Pending file may have been tampered with.", flush=True)
                _append_log(action, requester, "DENIED - HASH MISMATCH",
                            requested_at, elapsed, tier=tier)
                _clear_pending()
                return False

            _append_log(action, requester, "APPROVED" if approved else "DENIED",
                        requested_at, elapsed, tier=tier)
            _clear_pending()
            return approved

        elif data.get("id") == approval_id and data.get("status") == "delayed":
            # Operator tapped [Delay 5m] — reset the timeout window and re-send with buttons.
            # The listener sets status="delayed"; we detect it here, reset start, and re-send.
            # HMAC and ID binding remain intact — the pending record is unchanged except status.
            print(f"[approval] DELAYED: approval {approval_id} deferred by operator.", flush=True)
            start = time.time()
            data["status"] = "pending"
            _save_pending(data)
            _send_via_guardian(
                _build_l2_message(action, approval_id, action_hash, options),
                keyboard=_build_l2_keyboard(approval_id, options, allow_delay=False),
            )

    # Timeout
    elapsed = time.time() - start
    _clear_pending()
    _append_log(action, requester, "TIMED OUT", requested_at, elapsed, tier=tier)
    _send_via_guardian("Approval timed out — denied by default.")
    return False


def record_decision(decision: str, expected_id: str = "") -> str:
    """
    Called by the listener (Chief or Guardian) when the user replies.

    2-option (default):  1=Approve / Yes,  2=Deny / No
    3-option:            1=Approve,  2=Approve for all,  3=Deny

    expected_id: when provided by the caller, the active pending approval ID is
    validated against it before applying the decision. A mismatch means the
    pending state changed after the caller's has_pending_approval() check —
    the reply is rejected and logged. Guardian passes the ID it read.
    Chief router omits this parameter (intentional usability redundancy path —
    no ID binding on that path).

    Returns a brief reply string to send back to the user.
    """
    data = _load_pending()
    if not data or data.get("status") != "pending":
        print(
            f"[approval] WARN: record_decision called with no active pending approval "
            f"— possible stale or duplicate reply. decision={decision!r}",
            flush=True,
        )
        return "No pending approval request found."

    # ID binding: reject if the pending ID changed since the caller's check.
    # Guards against the narrow race where a new approval started after the
    # caller read has_pending_approval() and before this call runs.
    if expected_id and data.get("id") != expected_id:
        print(
            f"[approval] DENIED: approval ID mismatch on resolution — "
            f"expected={expected_id!r} found={data.get('id')!r} decision={decision!r}",
            flush=True,
        )
        return "Approval ID mismatch — reply not applied."

    options = data.get("options", 2)
    raw = decision.strip().upper()

    if options == 3:
        if raw in ("1", "YES"):
            d = "YES"
        elif raw in ("2", "YES_FOR_ALL"):
            d = "YES_FOR_ALL"
        elif raw in ("3", "NO"):
            d = "NO"
        else:
            return "Reply 1 (Approve), 2 (Approve for all), or 3 (Deny)."
    else:
        if raw in ("1", "YES"):
            d = "YES"
        elif raw in ("2", "NO"):
            d = "NO"
        else:
            return "Reply 1 (Approve) or 2 (Deny)."

    data["status"]   = "decided"
    data["decision"] = d
    _save_pending(data)

    if d == "YES":
        return "Approved."
    elif d == "YES_FOR_ALL":
        return "Approved for all."
    else:
        return "Denied."


def parse_reply_code(text: str, pending_id: str, options: int = 2) -> tuple[str, str]:
    """
    Parse and validate a 'CODE DECISION' approval reply.

    Expected format: '<4-char code> <decision>'  e.g. 'A3F2 1', 'A3F2 YES'
    The code is the first 4 characters of the active pending approval ID.

    options: number of choices (2 or 3); used to build correct format hints only.

    Returns (decision, "") on success where decision is the bare token ('1', '2', etc.).
    Returns ("", error_msg) on failure:
      - Wrong format (no code prefix, or part[0] is not 4 chars): returns an
        options-aware hint, no log (could be a legitimate non-approval message).
      - Wrong code: returns rejection and logs the mismatch.
      - No pending_id: returns rejection.

    Callers pass the extracted decision to record_decision(); they do not need
    to validate the decision token themselves — record_decision() handles that.
    """
    reply_code = pending_id[:4].upper() if pending_id else ""
    parts = text.strip().split(None, 1)

    if len(parts) != 2 or len(parts[0]) != 4:
        if reply_code:
            if options == 3:
                hint = (f"{reply_code} 1 (approve), "
                        f"{reply_code} 2 (approve all), or "
                        f"{reply_code} 3 (deny)")
            else:
                hint = f"{reply_code} 1 (approve) or {reply_code} 2 (deny)"
        else:
            hint = "CODE 1"
        return "", f"Include reply code. Example: {hint}"

    code, decision = parts[0].upper(), parts[1].strip()

    if not reply_code:
        print("[approval] DENIED: parse_reply_code called with no active pending_id.", flush=True)
        return "", "No pending approval — reply not accepted."

    if code != reply_code:
        print(
            f"[approval] DENIED: reply code mismatch — "
            f"expected={reply_code!r} got={code!r}",
            flush=True,
        )
        return "", f"Wrong approval code. Expected {reply_code}."

    return decision, ""


def get_pending_album_snapshot() -> dict | None:
    """Return the album snapshot saved at approval request time, or None."""
    data = _load_pending()
    if data.get("status") not in ("pending", "decided"):
        return None
    return data.get("album_snapshot")


def has_pending_approval() -> bool:
    """True if there is a fresh, unanswered approval request."""
    data = _load_pending()
    if not data or data.get("status") != "pending":
        return False
    # Auto-clear stale pending records older than TIMEOUT
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


def get_pending_id() -> str:
    """
    Return the ID of the currently active (status=pending) approval, or
    empty string if no approval is pending or the record is stale.
    """
    data = _load_pending()
    return data.get("id", "") if data.get("status") == "pending" else ""


def get_pending_info() -> tuple[str, int]:
    """
    Return (approval_id, options) for the currently active pending approval.
    Returns ('', 2) if no approval is pending or the record is stale.

    Used by listeners that need both ID binding and option-aware hint text
    without two separate _load_pending() calls.
    """
    data = _load_pending()
    if data.get("status") == "pending":
        return data.get("id", ""), data.get("options", 2)
    return "", 2


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chief_approval_brain.py \"action description\"")
        sys.exit(1)

    action_desc = " ".join(sys.argv[1:])
    requester   = "Claude Code"

    approved = request_approval(action_desc, requester)
    sys.exit(0 if approved else 1)
