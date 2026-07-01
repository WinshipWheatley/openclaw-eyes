"""
chief_approval_brain.py

Gatekeeper for all destructive, publishing, and irreversible actions.
Any brain or OpenClaw session calls request_approval() before proceeding.

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

Usage as CLI:
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

import chief_env

DEFAULT_PENDING_FILE = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
PENDING_FILE    = DEFAULT_PENDING_FILE
VAULT_LOG       = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md")
_SLOT_LOCK_FILE = Path.home() / ".chief_approval.lock"  # local ext4 — reliable flock
POLL_INTERVAL   = 2     # seconds between checks
TIMEOUT         = 86400  # 24 hours — remote approvals should survive a real day
_CHIEF_ENV_FILE = Path("/home/openclaw/.chief.env")
_USAGE = (
    "Usage:\n"
    "  python3 /home/openclaw/chief_approval_brain.py \"action description\"\n"
    "  python3 /home/openclaw/chief_approval_brain.py --resend-pending\n"
    "  python3 /home/openclaw/chief_approval_brain.py --help\n"
)


def _human_timeout(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" + ("s" if hours != 1 else "")
    if seconds % 60 == 0:
        mins = seconds // 60
        return f"{mins} minute" + ("s" if mins != 1 else "")
    return f"{seconds} seconds"


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


def _truncate_approval_text(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _build_approval_context_block(approval_context: dict | None) -> str:
    if not approval_context:
        return ""

    lines: list[str] = []
    action_label = _truncate_approval_text(approval_context.get("action_label", ""), 80)
    if action_label:
        lines.append(f"Action: {action_label}")

    mode = _truncate_approval_text(approval_context.get("mode", ""), 80)
    if mode:
        lines.append(f"Mode: {mode}")

    to_value = _truncate_approval_text(approval_context.get("to", ""), 120)
    if to_value:
        lines.append(f"To: {to_value}")

    cc_value = _truncate_approval_text(approval_context.get("cc", ""), 120)
    if cc_value:
        lines.append(f"CC: {cc_value}")

    subject = _truncate_approval_text(approval_context.get("subject", ""), 120)
    if subject:
        lines.append(f"Subject: {subject}")

    thread_synopsis = _truncate_approval_text(approval_context.get("thread_synopsis", ""), 160)
    if thread_synopsis:
        lines.extend(["", "Thread synopsis:", thread_synopsis])

    send_synopsis = _truncate_approval_text(approval_context.get("proposed_send", ""), 160)
    if send_synopsis:
        lines.extend(["", "Proposed send:", send_synopsis])

    draft_preview = _truncate_approval_text(approval_context.get("draft_preview", ""), 220)
    if draft_preview:
        lines.extend(["", "Draft preview:", draft_preview])

    if not lines:
        return ""
    return "\n".join(lines)


def _send_via_guardian(message: str, keyboard: dict | None = None) -> bool:
    chief_env.load_env()
    try:
        from chief_guardian_sender import send_approval
        send_approval(message, reply_markup=keyboard)
        return True
    except (ImportError, Exception) as e:
        if keyboard is not None:
            print(
                f"[approval] Guardian button send failed ({e!r}); "
                "refusing Chief bot fallback for button-bearing approval.",
                flush=True,
            )
            return False
        print(f"[approval] Guardian send failed ({e!r}), falling back to Chief bot.", flush=True)
        _send_chief(message)
        return True


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


def _dual_write_chief_approval_request(pending: dict) -> None:
    """Best-effort observational SQLite mirror; legacy JSON remains authority."""
    try:
        from guardian_hitl_dual_write_compatibility import (
            mirror_chief_approval_request_fail_open,
        )

        mirror_chief_approval_request_fail_open(pending, ttl_seconds=TIMEOUT)
    except Exception:
        # This adapter must never affect the active Chief approval path.
        pass


def _dual_write_chief_approval_decision(pending: dict, decision: str) -> None:
    """Best-effort observational decision receipt; legacy JSON remains authority."""
    try:
        from guardian_hitl_dual_write_compatibility import (
            mirror_chief_approval_decision_fail_open,
        )

        mirror_chief_approval_decision_fail_open(pending, decision, ttl_seconds=TIMEOUT)
    except Exception:
        # This adapter must never affect the active Chief approval path.
        pass


def _load_active_pending() -> dict:
    """
    Return the active pending approval record, or {} if there is no active
    approval. Stale pending records older than TIMEOUT are cleared first.
    """
    data = _load_pending()
    if not data or data.get("status") != "pending":
        return {}
    try:
        requested_at = data.get("requested_at", "")
        if requested_at:
            age = (
                datetime.now()
                - datetime.strptime(requested_at, "%Y-%m-%d %H:%M:%S")
            ).total_seconds()
            if age > TIMEOUT:
                _clear_pending()
                return {}
    except Exception:
        # Deterministic fallback: if the record cannot be validated, treat it as
        # active rather than silently discarding a potentially fresh approval.
        pass
    return data


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
    """Verify the action hash.

    Legacy compatibility is allowed only when hashing is fully disabled and the
    pending record has no hash. Any partial state (secret configured but hash
    missing, or stored hash present but secret unavailable) fails closed.
    """
    expected = _compute_hash(action, approval_id, requested_at)
    if not expected and not stored_hash:
        return True  # Hashing intentionally disabled.
    if not expected:
        return False  # Cannot verify a stored hash without the secret.
    if not stored_hash:
        return False  # Secret is configured, so the pending hash is required.
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
    chief_env.load_env()
    subprocess.run(
        ["python3", str(Path.home() / "chief_sender.py"), message],
        check=False,
    )


def resend_pending_request() -> bool:
    """
    Re-send the current pending approval request to Telegram.
    Returns True when a pending request was found and resend was attempted.
    """
    data = _load_pending()
    if data.get("status") != "pending":
        return False

    action = str(data.get("action", ""))
    approval_id = str(data.get("id", ""))
    requested_at = str(data.get("requested_at", ""))
    options = int(data.get("options", 2) or 2)
    action_hash = str(data.get("hash", ""))
    approval_context = data.get("approval_context")
    if not action_hash and approval_id and requested_at:
        action_hash = _compute_hash(action, approval_id, requested_at)

    return _send_via_guardian(
        _prepend_eli5(
            _build_l2_message(action, approval_id, action_hash, options, approval_context=approval_context),
            action, approval_context,
            requester=str(data.get("requester", "")), is_irreversible=_is_hard_t2(action),
        ),
        keyboard=_build_l2_keyboard(approval_id, options, allow_delay=False),
    )


def send_no_pending_confirmation() -> None:
    """Push a positive confirmation when no approval is currently pending."""
    _send_via_guardian("✅ No pending approval requests.")


# ── Approval message builder ───────────────────────────────────────────────────

def _guardian_eli5_enabled(env: dict | None = None) -> bool:
    """Concise ELI5 on the initial approval block. Default ON (operator asked for
    'all of Guardian's messages' to hit the light LM); disable with OPENCLAW_GUARDIAN_ELI5=0."""
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_GUARDIAN_ELI5", "1")).strip().lower() not in ("0", "false", "no", "off", "")


def _build_eli5_packet(action: str, approval_context: dict | None, *,
                       requester: str, is_irreversible: bool) -> dict:
    """Map a deterministic approval into the small fact packet guardian_eli5 expects."""
    ctx = approval_context or {}
    return {
        "action": ctx.get("action_label") or action,
        "summary": ctx.get("proposed_send") or ctx.get("subject") or "",
        "risk": "This cannot be undone." if is_irreversible else "This is recoverable.",
        "requester": requester or "An agent",
    }


def _prepend_eli5(message: str, action: str, approval_context: dict | None, *,
                  requester: str, is_irreversible: bool,
                  env: dict | None = None, eli5_fn=None) -> str:
    """Prepend a concise plain-English ELI5 lead to the deterministic approval block.
    Flag-gated (default on) and FAIL-CLOSED: any problem returns the message unchanged so
    the approval always sends. The 'Why now?' button stays the deeper (detailed) ELI5.
    The lead only rephrases — Approve/Deny logic remains fully deterministic."""
    if not _guardian_eli5_enabled(env):
        return message
    try:
        if eli5_fn is None:
            from guardian_eli5 import eli5_explain as eli5_fn  # type: ignore
        packet = _build_eli5_packet(action, approval_context, requester=requester,
                                    is_irreversible=is_irreversible)
        lead = str(eli5_fn(packet, depth="concise") or "").strip()
    except Exception:
        return message
    if not lead:
        return message
    return f"{lead}\n\n———\n{message}"


def _build_l2_message(action: str, approval_id: str, action_hash: str,
                      options: int, approval_context: dict | None = None) -> str:
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

    context_block = _build_approval_context_block(approval_context)
    if context_block:
        action_block = f"{context_block}{hash_line}{risk_line}"
    else:
        action_block = f"Action: {action}{hash_line}{risk_line}"

    return (
        f"APPROVAL REQUIRED\n\n"
        f"ID: {approval_id}\n"
        f"{action_block}\n"
        f"Expires: {_human_timeout(TIMEOUT)}"
        f"{choice_line}"
    )


def _build_l1_prompt(action: str) -> str:
    return f"\n  Action: {action}\n  Proceed? [y/N]: "


def _test_mode_fail_closed_default_path() -> bool:
    return (
        os.environ.get("OPENCLAW_TEST_MODE") == "1"
        and Path(PENDING_FILE).resolve(strict=False) == DEFAULT_PENDING_FILE.resolve(strict=False)
    )


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
    approval_context: dict | None = None,
) -> bool:
    """
    Request approval for an action, using the appropriate tier:

      Tier 0 — Proceed immediately (no gate).
      Tier 1 — Local terminal y/N prompt; escalates to Tier 2 if no TTY.
    Tier 2 — Remote phone approval via Guardian bot; blocks until response
            or timeout (auto-deny).

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
        "approval_context": approval_context or {},
    }

    if _test_mode_fail_closed_default_path():
        elapsed = time.time() - start
        _append_log(action, requester, "DENIED - TEST MODE", requested_at, elapsed, tier=tier)
        return False

    # Snapshot active album session so listener can resume after gate closes.
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _repo_root = str(_Path(__file__).resolve().parent)
        if _repo_root in _sys.path:
            _sys.path.remove(_repo_root)
        _sys.path.insert(0, _repo_root)
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

    if not _send_via_guardian(
        _prepend_eli5(
            _build_l2_message(action, approval_id, action_hash, options, approval_context=approval_context),
            action, approval_context, requester=requester, is_irreversible=_is_hard_t2(action),
        ),
        keyboard=_build_l2_keyboard(approval_id, options),
    ):
        elapsed = time.time() - start
        _clear_pending()
        _append_log(action, requester, "DENIED - GUARDIAN SEND FAILED", requested_at, elapsed, tier=tier)
        return False

    _dual_write_chief_approval_request(pending)

    # Operator assist escalation for blocked terminals or agents (e.g. Claude Code)
    try:
        from chief_assist import escalate_to_operator
        rc = approval_id[:4]
        assist_msg = escalate_to_operator(
            diagnosis=f"Approval Gate Locked: Pending authorization for '{_truncate_approval_text(action, 60)}'",
            reason="Irreversible action requires human judgment. TTY unavailable; escalated to phone/Telegram.",
            primary_cmd=f"python3 /home/openclaw/chief_router.py \"{rc} 1\"",
            context_cmd=f"cat {PENDING_FILE}"
        )
        print(f"\n{assist_msg}\n", flush=True)
    except Exception:
        pass

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
            if not _verify_hash(action, approval_id, requested_at, stored_hash):
                print(f"[approval] DENIED: hash mismatch on approval {approval_id}. "
                      "Pending file may have been tampered with.", flush=True)
                _dual_write_chief_approval_decision(data, "NO")
                _append_log(action, requester, "DENIED - HASH MISMATCH",
                            requested_at, elapsed, tier=tier)
                _clear_pending()
                send_no_pending_confirmation()
                return False

            _dual_write_chief_approval_decision(data, decision)
            _append_log(action, requester, "APPROVED" if approved else "DENIED",
                        requested_at, elapsed, tier=tier)
            _clear_pending()
            send_no_pending_confirmation()
            return approved

        elif data.get("id") == approval_id and data.get("status") == "delayed":
            # Operator tapped [Delay 5m] — reset the timeout window and re-send with buttons.
            # The listener sets status="delayed"; we detect it here, reset start, and re-send.
            # HMAC and ID binding remain intact — the pending record is unchanged except status.
            print(f"[approval] DELAYED: approval {approval_id} deferred by operator.", flush=True)
            start = time.time()
            data["status"] = "pending"
            _save_pending(data)
            if not _send_via_guardian(
                _prepend_eli5(
                    _build_l2_message(action, approval_id, action_hash, options, approval_context=approval_context),
                    action, approval_context, requester=requester, is_irreversible=_is_hard_t2(action),
                ),
                keyboard=_build_l2_keyboard(approval_id, options, allow_delay=False),
            ):
                elapsed = time.time() - start
                _clear_pending()
                _append_log(action, requester, "DENIED - GUARDIAN SEND FAILED", requested_at, elapsed, tier=tier)
                return False

    # Timeout
    elapsed = time.time() - start
    _dual_write_chief_approval_decision(pending, "TIMEOUT")
    _clear_pending()
    _append_log(action, requester, "TIMED OUT", requested_at, elapsed, tier=tier)
    _send_via_guardian("Approval timed out — denied by default.")
    send_no_pending_confirmation()
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
    _dual_write_chief_approval_decision(data, d)

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
    return bool(_load_active_pending())


def get_pending_id() -> str:
    """
    Return the ID of the currently active (status=pending) approval, or
    empty string if no approval is pending or the record is stale.
    """
    data = _load_active_pending()
    return data.get("id", "")


def get_pending_info() -> tuple[str, int]:
    """
    Return (approval_id, options) for the currently active pending approval.
    Returns ('', 2) if no approval is pending or the record is stale.

    Used by listeners that need both ID binding and option-aware hint text
    without two separate _load_pending() calls.
    """
    data = _load_active_pending()
    if data:
        return data.get("id", ""), data.get("options", 2)
    return "", 2


# ── CLI entry point ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) == 1 and argv[0] == "--resend-pending":
        ok = resend_pending_request()
        if ok:
            print("Pending approval re-sent.")
            return 0
        send_no_pending_confirmation()
        print("No pending approval to resend.")
        return 0

    if len(argv) == 1 and argv[0] in {"--help", "-h", "help"}:
        print(_USAGE.rstrip())
        return 0

    if not argv:
        print(_USAGE.rstrip())
        return 1

    if argv[0].startswith("-"):
        print(_USAGE.rstrip())
        return 2

    action_desc = " ".join(argv)
    requester = os.environ.get("OPENCLAW_APPROVAL_REQUESTER", "OpenClaw CLI")

    approved = request_approval(action_desc, requester)
    return 0 if approved else 1


if __name__ == "__main__":
    sys.exit(main())
