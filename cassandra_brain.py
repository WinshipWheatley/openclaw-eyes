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
import threading
import fcntl
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from chief_file_io import load_json, save_json
from chief_llm import (
    external_language_model_call,
    external_model_packet_policy,
    ollama_call,
    nemotron_call,
    resolve_local_model,
)
from chief_output_utils import tts_clean
from cassandra_mode import (
    is_focus_mode,
    is_social_mode,
    FOCUS_LOCK_PATH,
    SOCIAL_LOCK_PATH,
)
from cassandra_capability import capability_context, gate_reply
from cassandra_date_awareness import (
    answer_date_awareness_query,
    build_authoritative_date_context,
)
from cassandra_email_config import get_review_inbox
from finance_state import (
    build_finance_snapshot,
    detect_finance_status_intent,
    finance_entity_terms,
    format_finance_context,
    get_finance_payment_answer,
    get_finance_status_answer,
)
from capital_hilton_agency_status import (
    format_capital_hilton_agency_answer,
    format_capital_hilton_openclaw_status_answer,
)
from reynolds_gig_setup_status import (
    format_reynolds_gig_setup_answer,
    is_reynolds_gig_setup_query,
)
from capability_registry import get_actor, registry_context_for_query
from business_ops_packet import assemble_business_ops_packet, BusinessOpsPacket
from business_ops_intent import classify_business_ops_intent
from hitl_pending_store import propose_action as _hitl_propose
from cassandra_custom_tools import handle_operator_objective as _handle_operator_objective
from operator_universal_intake import (
    is_universal_operator_intake_candidate as _is_universal_operator_intake_candidate,
    try_process_surface_operator_intake as _try_universal_operator_intake,
)
from cassandra_guided_review import process_guided_review_message as _process_guided_review_message
from operator_context_switchboard import process_operator_context_switchboard_message as _process_operator_context_switchboard_message
from openclaw_system_knowledge_registry import (
    format_system_knowledge_answer as _format_system_knowledge_answer,
    is_system_knowledge_registry_query as _is_system_knowledge_registry_query,
    query_system_knowledge_registry as _query_system_knowledge_registry,
)
from cassandra_pii_hooks import (
    tokenize_prompt as _pii_tokenize,
    rehydrate_reply as _pii_rehydrate_reply,
    detokenize_for_dashboard,
)


# ── Broker call import for test patching ──
try:
    from google_access_broker import call as broker_call
except ImportError:
    broker_call = None

# ── Paths ─────────────────────────────────────────────────────────────────────

_STATE_PATH       = Path("/mnt/c/OpenClaw/logs/cassandra_state.json")
_FOLLOWUP_LOG     = Path("/mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl")
_POLISH_TASKS_DIR = Path("/home/openclaw/polish_loop/tasks")
_POLISH_ARCHIVE   = Path("/home/openclaw/polish_loop/archive")
_POLISH_STATUS    = Path("/home/openclaw/polish_loop/status.json")
_POLISH_TASK_FILE = Path("/home/openclaw/polish_loop/task.md")
_DEFAULT_CORRESPONDENCE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl")
_DEFAULT_OUTREACH_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_outreach.jsonl")
_CORRESPONDENCE_LOG = _DEFAULT_CORRESPONDENCE_LOG
_OUTREACH_LOG    = _DEFAULT_OUTREACH_LOG
_REALITY_NOTES    = Path("/home/openclaw/cassandra_reality_notes.json")
_INBOUND_EMAIL_REPLY_LOCK = Path.home() / ".cassandra_inbound_email_reply.lock"
_MODEL_ROUTE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_model_routes.jsonl")

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_PAYMENT = _VAULT_SYS / "Ops Payment Follow-ups.md"
_OPS_NOTES   = _VAULT_SYS / "Ops Notes.md"
_OPS_EMAIL   = _VAULT_SYS / "Ops Email Log.md"
_OPS_WORKSTREAMS = _VAULT_SYS / "Ops Workstreams.md"

# Canonical send-state strings (spec: SEND-STATE TRUTH POLICY)
_SS_DRAFT             = "draft"
_SS_QUEUED            = "queued"
_SS_AWAITING_APPROVAL = "awaiting_approval"
_SS_SEND_ATTEMPTED    = "send_attempted"
_SS_SENT_CONFIRMED    = "sent_confirmed"
_SS_SEND_FAILED       = "send_failed"
_SS_BLOCKED           = "blocked"
_SS_PARTIAL           = "partial"

_PARTIAL_FOLLOWUP_NOTE = (
    "I can't fully answer the rest right now, but I'm working on getting "
    "that capability. I'll follow up when I can."
)

_EMAIL_REVIEW_UNCERTAINTY_PREFIX = "I don't want to overstate what I can confirm."

_EMAIL_REVIEW_PAYMENT_ASSERTIONS = (
    r"\b(payment|deposit|invoice|transfer)\b.*\b(came through|cleared|arrived|landed|posted|was received|has been received)\b",
    r"\b(i|we)\s+(confirmed|verified)\b.*\b(payment|deposit|invoice|transfer)\b",
)

_EMAIL_REVIEW_CALENDAR_ASSERTIONS = (
    r"\b(on|in)\s+(your|the)\s+calendar\b",
    r"\b(you('?re| are)|we('?re| are)|it('?s| is))\s+(scheduled|booked|set)\b",
    r"\bcalendar\s+(is|looks)\s+clear\b",
)

_EMAIL_REVIEW_CAPABILITY_ASSERTIONS = {
    "email_send": (
        r"\b(send|sent|sending)\b.*\b(directly|from here|on my end)\b",
        r"\bi\s+can\s+(send|email|message)\b",
        r"\bi\s+will\s+(send|email|message)\b",
        r"\bi\s+(sent|have sent|just sent)\b.*\b(email|message|contract|invoice|note)\b",
    ),
}

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
        "flag": "PAYMENT_METADATA_CONNECTED",
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
        "suppress_when_flag": "EMAIL_DRAFT_CONNECTED",
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

# ── HITL integration point ───────────────────────────────────────────────────
#
# Cassandra calls _propose_external_action() before executing any action that
# reaches outside the read-only/logging boundary (email send, SMS, calendar
# writes, outreach, etc.).
#
# When HITL is disabled (default), this is a no-op — (True, None) is returned
# and the caller proceeds as before.  When HITL is enabled, a pending action
# record is created and (False, action_id) is returned.  The caller must NOT
# execute the action; instead, surface a message like:
#   "I've queued that for your approval. Action ID: <action_id>"
#
# Example:
#   ok, aid = _propose_external_action("email_send", {"to": addr, "body": text})
#   if not ok:
#       return [f"Queued for approval. Action ID: {aid}"]
#   # proceed with send

def _propose_external_action(
    action_type: str,
    payload: dict,
    ttl_seconds: int = 86400,
) -> tuple[bool, str | None]:
    """
    Wrap hitl_pending_store.propose_action for Cassandra.

    Returns (True, None) when HITL is off or already approved.
    Returns (False, action_id) when HITL is on and a pending record was created.
    """
    return _hitl_propose("cassandra", action_type, payload, ttl_seconds)


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

def set_focus_mode(active: bool) -> None:
    FOCUS_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if active:
        FOCUS_LOCK_PATH.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               encoding="utf-8")
    elif FOCUS_LOCK_PATH.exists():
        FOCUS_LOCK_PATH.unlink()


def set_social_mode(active: bool) -> None:
    SOCIAL_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if active:
        SOCIAL_LOCK_PATH.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                encoding="utf-8")
    elif SOCIAL_LOCK_PATH.exists():
        SOCIAL_LOCK_PATH.unlink()


# ── State management ──────────────────────────────────────────────────────────

_DEFAULT_STATE = {
    "human_cues":              [],     # [{"cue": str, "at": str}] — FIFO, max 10
    "project_mood":            "neutral",
    "recurring_concerns":      [],
    "last_interaction_at":     None,
    "chirp_log":               [],     # [{"type": str, "at": str}] — FIFO, max 30
    "pending_income_followup": None,   # {"entry_id": str, "amount": float} or None
    "session_fact_overrides":  {},     # {"entity_key": {"summary": str, "at": str, "source_text": str}}
    "last_finance_entity":     None,   # {"key": str, "at": str}
}


def load_state() -> dict:
    return load_json(_STATE_PATH, dict(_DEFAULT_STATE))


def save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _STATE_PATH.with_name(f"{_STATE_PATH.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, _STATE_PATH)


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

def _log_conversation(user_text: str, replies: list[str], route: str = "llm", metadata: dict | None = None) -> None:
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
        if metadata:
            entry.update(metadata)

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


def record_cassandra_packet_event(
    user_text: str,
    ops_packet: BusinessOpsPacket,
    route_hint: str | None = None,
    operator_visible_summary: str | None = None,
) -> str | None:
    """
    Safely records a Cassandra Business Ops Spine event and packet receipt.
    Fails open — never raises to caller.
    """
    try:
        from business_ops_ledger import append_event, append_packet_receipt

        # Safe prompt handling (hash only)
        # We do not store raw prompt text in the ledger for sensitive reasons.
        prompt_hash = hashlib.sha256(user_text.encode("utf-8")).hexdigest()

        # Link event to packet. In v0, we use the packet_id as the primary event identifier.
        event_id = ops_packet.packet_id

        append_event(
            event_id=event_id,
            event_type="cassandra_handle",
            actor="cassandra",
            prompt_hash=prompt_hash,
            operator_visible_summary=operator_visible_summary or f"Cassandra handling: {ops_packet.intent_name}",
        )

        # Redact the query in the packet dictionary before storage to ensure sensitive data
        # boundary is maintained in the SQLite receipts.
        p_dict = ops_packet.to_dict()
        p_dict["query"] = f"[REDACTED:{prompt_hash[:8]}]"

        append_packet_receipt(
            packet=p_dict,
            event_id=event_id,
        )

        return event_id
    except Exception as e:
        print(f"[cassandra_ledger] write failure: {e}", flush=True)
        return None


def _log_correspondence_state(
    recipient: str,
    state: str,
    detail: str = "",
    route: str = "",
    metadata: dict | None = None,
) -> None:
    """Append one send-state transition to the correspondence JSONL log. Fails open."""
    entry: dict = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": recipient,
        "state": state,
    }
    if detail:
        entry["detail"] = detail
    if route:
        entry["route"] = route
    if metadata:
        for key, value in metadata.items():
            if value not in (None, "", []):
                entry[key] = value
    try:
        _CORRESPONDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _CORRESPONDENCE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        print(f"[cassandra] correspondence log write failed: {exc}", flush=True)


def _detect_request_capability_gaps(user_text: str) -> list[dict]:
    query = user_text.lower()
    gaps: list[dict] = []
    for capability, spec in _CAPABILITY_GAP_SPECS.items():
        suppress_flag = spec.get("suppress_when_flag")
        if suppress_flag and _capability_flag_value(suppress_flag) is True:
            continue
        if not any(keyword in query for keyword in spec["keywords"]):
            continue
        flag_name = spec.get("flag")
        if not flag_name or _capability_flag_value(flag_name) is not False:
            continue
        gaps.append({
            "capability": capability,
            "goal": spec["goal"],
            "scope": list(spec["scope"]),
            "success": spec["success"],
            "manual_required": bool(spec.get("manual_required")),
            "known_missing": True,
            "hedging_detected": False,
        })
    return gaps


def _queue_inbound_email_gap_task(
    capability_gap: dict,
    *,
    question_text: str,
    contact_name: str,
    sender_email: str,
    subject: str,
    thread_id: str,
    message_ids: list[str],
) -> str | None:
    extra_scope = [
        f"Inbound email contact: {contact_name} <{sender_email}>",
        f"Inbound email subject: {subject or '(no subject)'}",
        f"Inbound email thread id: {thread_id}",
        f"Inbound message ids: {', '.join(mid for mid in message_ids if mid) or 'unknown'}",
        f"Grounded unanswered question: {question_text}",
        "Keep the task tied back to the email thread evidence so later review can confirm the original question is solved.",
    ]
    return _create_upgrade_task(
        capability_gap,
        question_text,
        extra_scope_lines=extra_scope,
        force_queue_manual=bool(capability_gap.get("manual_required")),
    )


# ── Thin wrappers for functions moved to cassandra_outreach (Cut 4 + Cut 5 + Cut 6) ──

def _sync_outreach_test_seams() -> None:
    """Keep brain-level monkeypatches visible to outreach-owned helper wrappers."""
    import cassandra_outreach as _cassandra_outreach

    _cassandra_outreach.broker_call = broker_call
    if _CORRESPONDENCE_LOG != _DEFAULT_CORRESPONDENCE_LOG:
        _cassandra_outreach._CORRESPONDENCE_LOG = _CORRESPONDENCE_LOG
    if _OUTREACH_LOG != _DEFAULT_OUTREACH_LOG:
        _cassandra_outreach._OUTREACH_LOG = _OUTREACH_LOG
    _cassandra_outreach._EMAIL_THREAD_ANALYSIS_LOG = globals().get(
        "_EMAIL_THREAD_ANALYSIS_LOG",
        _cassandra_outreach._EMAIL_THREAD_ANALYSIS_LOG,
    )
    _cassandra_outreach._EMAIL_THREAD_STATE = globals().get(
        "_EMAIL_THREAD_STATE",
        _cassandra_outreach._EMAIL_THREAD_STATE,
    )
    _cassandra_outreach._EMAIL_BRIDGE_LOG = globals().get(
        "_EMAIL_BRIDGE_LOG",
        _cassandra_outreach._EMAIL_BRIDGE_LOG,
    )
    _cassandra_outreach.get_finance_status_answer = globals().get(
        "get_finance_status_answer",
        _cassandra_outreach.get_finance_status_answer,
    )

def _load_jsonl_records(path: Path) -> list[dict]:
    _sync_outreach_test_seams()
    from cassandra_outreach import _load_jsonl_records as _impl
    return _impl(path)


def _load_outbound_email_records() -> list[dict]:
    _sync_outreach_test_seams()
    from cassandra_outreach import _load_outbound_email_records as _impl
    return _impl()


def _match_outbound_email_record(message: dict, sender_email: str) -> dict | None:
    _sync_outreach_test_seams()
    from cassandra_outreach import _match_outbound_email_record as _impl
    return _impl(message, sender_email)


def _bridge_preview(text: str, limit: int = 140) -> str:
    from cassandra_outreach import _bridge_preview as _impl
    return _impl(text, limit)


def _parse_event_datetime(raw: object, fallback: datetime | None = None) -> datetime:
    from cassandra_outreach import _parse_event_datetime as _impl
    return _impl(raw, fallback)


def _question_key(text: str) -> str:
    from cassandra_outreach import _question_key as _impl
    return _impl(text)


def _extract_question_candidates(text: str) -> list[str]:
    from cassandra_outreach import _extract_question_candidates as _impl
    return _impl(text)


def _fetch_email_thread_messages(message: dict) -> tuple[list[dict], str]:
    _sync_outreach_test_seams()
    from cassandra_outreach import _fetch_email_thread_messages as _impl
    return _impl(message)


def _message_evidence_rows(thread_messages: list[dict], sender_email: str) -> list[dict]:
    from cassandra_outreach import _message_evidence_rows as _impl
    return _impl(thread_messages, sender_email)


def _bundle_answered_in_thread(bundle: dict, thread_messages: list[dict], sender_email: str) -> bool:
    from cassandra_outreach import _bundle_answered_in_thread as _impl
    return _impl(bundle, thread_messages, sender_email)


def _advance_email_thread_cadence(
    *,
    thread_id: str,
    contact_name: str,
    unresolved_bundles: list[dict],
    predictions: list[dict],
    now: datetime | None = None,
) -> dict:
    _sync_outreach_test_seams()
    from cassandra_outreach import _advance_email_thread_cadence as _impl
    return _impl(
        thread_id=thread_id,
        contact_name=contact_name,
        unresolved_bundles=unresolved_bundles,
        predictions=predictions,
        now=now,
    )


def _log_email_thread_analysis(entry: dict) -> None:
    _sync_outreach_test_seams()
    from cassandra_outreach import _log_email_thread_analysis as _impl
    _impl(entry)


def _is_reply_like_email_message(message: dict) -> bool:
    from cassandra_outreach import _is_reply_like_email_message as _impl
    return _impl(message)


def _build_email_bridge_review_text(message: dict) -> str:
    from cassandra_outreach import _build_email_bridge_review_text as _impl
    return _impl(message)


def _detect_inner_circle_email_reply_intent(text: str) -> bool:
    _sync_outreach_test_seams()
    from cassandra_outreach import _detect_inner_circle_email_reply_intent as _impl
    return _impl(text)


def _log_email_bridge_event(
    *,
    message_id: str,
    thread_id: str,
    nickname: str,
    contact_name: str,
    sender_email: str,
    subject: str,
    preview: str,
    lane: str,
    status: str,
    unread: bool,
    dedupe: bool = True,
) -> None:
    _sync_outreach_test_seams()
    from cassandra_outreach import _log_email_bridge_event as _impl
    _impl(
        message_id=message_id,
        thread_id=thread_id,
        nickname=nickname,
        contact_name=contact_name,
        sender_email=sender_email,
        subject=subject,
        preview=preview,
        lane=lane,
        status=status,
        unread=unread,
        dedupe=dedupe,
    )


def _email_bridge_message_seen(message_id: str) -> bool:
    _sync_outreach_test_seams()
    from cassandra_outreach import _email_bridge_message_seen as _impl
    return _impl(message_id)


def _predict_likely_next_questions(question_bundles: list[dict]) -> list[dict]:
    _sync_outreach_test_seams()
    from cassandra_outreach import _predict_likely_next_questions as _impl
    return _impl(question_bundles)


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
    state["chirp_log"] = [e for e in state.setdefault("chirp_log", []) if e.get("at", "") >= cutoff]
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
    skip_prefixes = ("type:", "last_updated:", "updated:")
    return [l.strip() for l in lines
            if l.strip()
            and not l.startswith("#")
            and not l.startswith("---")
            and not any(l.strip().lower().startswith(prefix) for prefix in skip_prefixes)][-n:]


_HISTORICAL_LOG_TS_RE = re.compile(r"^\s*[-*]?\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$")


def _sanitize_historical_log_line(line: str) -> str | None:
    cleaned = line.strip()
    ts_match = _HISTORICAL_LOG_TS_RE.match(cleaned)
    if ts_match:
        cleaned = f"[{ts_match.group(1)}] {ts_match.group(2).strip()}"
    replacements = {
        " tomorrow ": " the next day ",
        " today ": " that day ",
        " yesterday ": " the previous day ",
        " tonight ": " that night ",
    }
    padded = f" {cleaned} "
    for old, new in replacements.items():
        padded = padded.replace(old, new)
    return " ".join(padded.strip().split())


def _tail_md_recent(path: Path, n: int = 6, *, max_age_days: int | None = None) -> list[str]:
    """Last n non-header markdown log lines, optionally filtered by age and with
    stale relative-day words normalized so raw history does not masquerade as live timing.

    Age filtering works at two levels:
    1. Per-line: lines with an inline ``[YYYY-MM-DD HH:MM:SS]`` timestamp are
       dropped when older than *max_age_days*.
    2. File-level fallback: when **no** line carried an inline timestamp the
       file's ``mtime`` is checked instead.  If the entire file is older than
       *max_age_days* every line is dropped — this prevents undated bullet
       lists (e.g. Ops Actions.md) from appearing stale in the context window.
    """
    raw_lines = _tail_md(path, n=500)
    kept: list[str] = []
    stale_relative_day_summaries: list[str] = []
    now = datetime.now()
    any_ts_matched = False
    for line in raw_lines:
        ts_match = _HISTORICAL_LOG_TS_RE.match(line)
        if ts_match and max_age_days is not None:
            any_ts_matched = True
            try:
                stamp = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                if (now - stamp).days > max_age_days:
                    lowered = line.lower()
                    if any(word in lowered for word in ("tomorrow", "today", "yesterday", "tonight")):
                        stale_relative_day_summaries.append(
                            f"[{ts_match.group(1)}] one-off historical event omitted; relative-day wording is stale."
                        )
                    continue
            except ValueError:
                pass
        cleaned = _sanitize_historical_log_line(line)
        if cleaned:
            kept.append(cleaned)

    # File-level fallback: if no line had an inline timestamp, gate on mtime.
    if kept and not any_ts_matched and max_age_days is not None:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if (now - mtime).days > max_age_days:
                return []
        except OSError:
            pass

    return [*stale_relative_day_summaries, *kept][-n:]


def _load_reality_notes() -> dict:
    data = load_json(_REALITY_NOTES, {})
    return data if isinstance(data, dict) else {}


def _find_reality_entry(query: str) -> tuple[str, dict] | None:
    q = (query or "").lower()
    notes = _load_reality_notes()
    for key, raw in notes.items():
        if not isinstance(raw, dict):
            continue
        aliases = [key]
        aliases.extend(a for a in raw.get("aliases", []) if isinstance(a, str))
        if any(alias.lower() in q for alias in aliases):
            return key, raw
    return None


def _reality_entity_terms(query: str) -> tuple[str, ...]:
    finance_terms = finance_entity_terms(query)
    found = _find_reality_entry(query)
    if found is None:
        return finance_terms
    key, entry = found
    aliases = [key]
    aliases.extend(a for a in entry.get("aliases", []) if isinstance(a, str))
    combined = list(finance_terms)
    combined.extend(a.lower() for a in aliases if isinstance(a, str) and a.strip())
    return tuple(dict.fromkeys(combined))


def _format_reality_context(query: str) -> str:
    found = _find_reality_entry(query)
    if found is None:
        return ""
    _, entry = found
    label = str(entry.get("label") or "Known reality")
    facts = [fact for fact in entry.get("facts", []) if isinstance(fact, str) and fact.strip()]
    if not facts:
        return ""
    lines = [f"[CANONICAL REALITY — {label}]"]
    summary = str(entry.get("status_summary") or "").strip()
    if summary:
        lines.append(f"Status summary: {summary}")
    lines.extend(f"  {fact}" for fact in facts)
    return "\n".join(lines)


def _session_fact_overrides(state: dict | None) -> dict:
    if not isinstance(state, dict):
        return {}
    overrides = state.get("session_fact_overrides")
    return overrides if isinstance(overrides, dict) else {}


def _remember_finance_entity(query: str, state: dict) -> None:
    from finance_state import find_finance_account

    found = find_finance_account(query)
    if found is None:
        return
    account_key, _ = found
    state["last_finance_entity"] = {
        "key": account_key,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _session_finance_entity(query: str, state: dict) -> tuple[str, dict] | None:
    from finance_state import find_finance_account, load_finance_state

    found = find_finance_account(query)
    if found is not None:
        return found

    last_entity = state.get("last_finance_entity")
    if not isinstance(last_entity, dict):
        return None
    account_key = str(last_entity.get("key") or "").strip()
    if not account_key:
        return None
    account = load_finance_state().get("accounts", {}).get(account_key)
    if not isinstance(account, dict):
        return None
    return account_key, account


def _extract_fact_correction_summary(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    normalized = " ".join(raw.split())
    patterns = (
        r"\bcurrent truth(?: is)?(?: only)?[:\s]+(.+?)(?:[.!?]|$)",
        r"\bcurrent status(?: is)?(?: only)?[:\s]+(.+?)(?:[.!?]|$)",
        r"\bthe truth is(?: only)?[:\s]+(.+?)(?:[.!?]|$)",
        r"\bonly[:\s]+(.+?)(?:[.!?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            summary = match.group(1).strip(" -,:;")
            if summary:
                return summary[0].upper() + summary[1:]

    sentences = [segment.strip(" -,:;") for segment in re.split(r"[.!?]+", normalized) if segment.strip()]
    for sentence in reversed(sentences):
        lowered = sentence.lower()
        if any(marker in lowered for marker in ("waiting for", "next step", "current truth", "only")):
            return sentence[0].upper() + sentence[1:]
    return ""


_FACT_CORRECTION_MARKERS = (
    "stale",
    "consumed",
    "outdated",
    "no longer true",
    "isn't true anymore",
    "is not true anymore",
    "not true anymore",
    "current truth",
    "current status",
    "superseded",
)


def _has_fact_correction_marker(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _FACT_CORRECTION_MARKERS) or (
        "anymore" in lowered and "not " in lowered
    )


def _store_session_fact_override(
    account_key: str,
    summary: str,
    source_text: str,
    state: dict,
) -> None:
    overrides = _session_fact_overrides(state)
    overrides[account_key] = {
        "summary": summary,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_text": str(source_text or "").strip(),
    }
    state["session_fact_overrides"] = overrides
    state["pending_session_fact_correction"] = None


def _format_session_fact_ack(label: str, summary: str) -> str:
    clean = " ".join(str(summary or "").split()).strip()
    suffix = "" if clean.endswith((".", "!", "?")) else "."
    return f"Got it — for {label}, the current truth now is: {clean}{suffix}"


def _looks_like_new_request_during_pending_correction(query: str) -> bool:
    lowered = " ".join(str(query or "").lower().split())
    if not lowered:
        return False
    if _extract_fact_correction_summary(query) or _has_fact_correction_marker(query):
        return False

    replacement_starters = (
        "actually ",
        "change it to ",
        "current truth ",
        "current truth is ",
        "it is ",
        "it's ",
        "its ",
        "make it ",
        "no, ",
        "now ",
        "set it to ",
        "they are ",
        "they're ",
        "update it ",
        "we are ",
        "we're ",
    )
    if lowered.startswith(replacement_starters):
        return False

    request_starters = (
        "are ",
        "can ",
        "could ",
        "did ",
        "do ",
        "does ",
        "how ",
        "is ",
        "list ",
        "show ",
        "should ",
        "summarize ",
        "tell me ",
        "what ",
        "when ",
        "where ",
        "which ",
        "who ",
        "why ",
        "would ",
    )
    if "?" in str(query or "") or lowered.startswith(request_starters):
        return True

    if any(term in lowered for term in ("agent", "agents", "telegram", "niles", "hermes", "guardian", "chief")):
        return True

    return False


def _handle_pending_session_fact_correction(query: str, state: dict) -> str | None:
    pending = state.get("pending_session_fact_correction")
    if not isinstance(pending, dict):
        return None

    account_key = str(pending.get("account_key") or "").strip()
    label = str(pending.get("label") or account_key).strip()
    if not account_key:
        state["pending_session_fact_correction"] = None
        return None

    lowered = str(query or "").lower()
    if lowered.strip() in {"cancel", "never mind", "nevermind", "stop"}:
        state["pending_session_fact_correction"] = None
        return f"Got it. I left the stored note for {label} unchanged."

    if _looks_like_new_request_during_pending_correction(query):
        state["pending_session_fact_correction"] = None
        return None

    summary = _extract_fact_correction_summary(query)
    if not summary and _has_fact_correction_marker(query):
        return f"Right, I have {label} marked as stale. What should I change it to?"
    if not summary:
        summary = " ".join(str(query or "").split()).strip(" -,:;")
    if not summary:
        return f"Right, I have {label} marked as stale. What should I change it to?"

    summary = summary[0].upper() + summary[1:]
    _store_session_fact_override(account_key, summary, query, state)
    return _format_session_fact_ack(label, summary)


def _detect_session_fact_correction(query: str, state: dict) -> str | None:
    found = _session_finance_entity(query, state)
    if found is None:
        return None
    account_key, account = found
    if not _has_fact_correction_marker(query):
        return None

    summary = _extract_fact_correction_summary(query)
    if not summary:
        label = str(account.get("label") or account_key).strip()
        state["pending_session_fact_correction"] = {
            "account_key": account_key,
            "label": label,
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_text": str(query or "").strip(),
        }
        return f"You're right — I may be looking at stale context for {label}. What should I change it to?"

    _store_session_fact_override(account_key, summary, query, state)
    label = str(account.get("label") or account_key).strip()
    return _format_session_fact_ack(label, summary)


def _get_session_fact_override(query: str, state: dict | None) -> tuple[str, dict] | None:
    from finance_state import find_finance_account

    overrides = _session_fact_overrides(state)
    if not overrides:
        return None
    found = find_finance_account(query)
    if found is None:
        return None
    account_key, account = found
    override = overrides.get(account_key)
    if not isinstance(override, dict):
        return None
    return str(account.get("label") or account_key).strip(), override


def _format_session_fact_override_context(query: str, state: dict | None) -> str:
    found = _get_session_fact_override(query, state)
    if found is None:
        return ""
    label, override = found
    summary = str(override.get("summary") or "").strip()
    if not summary:
        return ""
    return f"[SESSION CORRECTION — {label}]\nCurrent truth: {summary}"


def _build_reality_snapshot() -> str:
    """Compact always-on canonical reality summary for prompts and briefings."""
    notes = _load_reality_notes()
    lines: list[str] = []
    for key, raw in notes.items():
        if not isinstance(raw, dict):
            continue
        summary = str(raw.get("status_summary") or "").strip()
        if not summary:
            continue
        label = str(raw.get("label") or key).strip()
        if not label:
            continue
        lines.append(f"  {label}: {summary}")
    if not lines:
        return ""
    return "[CANONICAL REALITY SNAPSHOT]\n" + "\n".join(lines)


def _known_payment_status_reply(query: str) -> str | None:
    finance_reply = get_finance_payment_answer(query)
    if finance_reply is not None:
        return finance_reply
    found = _find_reality_entry(query)
    if found is None:
        return None
    _, entry = found
    reply = str(entry.get("payment_answer") or "").strip()
    return reply or None


def _time_label(now: datetime | None = None) -> str:
    h = (now or datetime.now()).hour
    if h < 6:   return "very early morning (before 6am)"
    if h < 9:   return "early morning"
    if h < 12:  return "morning"
    if h < 14:  return "midday"
    if h < 17:  return "afternoon"
    if h < 20:  return "early evening"
    if h < 23:  return "evening"
    return "late night"


def _build_temporal_anchor(now: datetime) -> str:
    local_now = now.astimezone()
    tz_label = local_now.tzname() or "local"
    yesterday = local_now.date() - timedelta(days=1)
    today = local_now.date()
    tomorrow = today + timedelta(days=1)
    return (
        f"Time: {_time_label(local_now)} ({local_now.strftime('%Y-%m-%d %H:%M')}, {tz_label})\n"
        "Relative date anchors: "
        f"yesterday is {yesterday.strftime('%Y-%m-%d')} ({yesterday.strftime('%A')}); "
        f"today is {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}); "
        f"tomorrow is {tomorrow.strftime('%Y-%m-%d')} ({tomorrow.strftime('%A')})"
    )


def _build_context_invariants() -> str:
    return (
        "Context invariants: interpret relative day words against the date anchors above. "
        "Use source priority in this order: live connector data, finance state, canonical reality, current-state ops files, then historical logs."
    )


def build_context_snapshot(state: dict | None = None) -> str:
    if state is None:
        state = load_state()
    parts = []
    now = datetime.now()

    parts.append(_build_temporal_anchor(now))
    parts.append(_build_context_invariants())

    finance_snapshot = build_finance_snapshot(limit=3)
    if finance_snapshot:
        parts.append(finance_snapshot)

    reality_snapshot = _build_reality_snapshot()
    if reality_snapshot:
        parts.append(reality_snapshot)

    workstreams = _tail_md(_OPS_WORKSTREAMS, 8)
    if workstreams:
        parts.append("Active workstreams:\n" + "\n".join(f"  {l}" for l in workstreams))

    cues = state.get("human_cues", [])[-3:]
    if cues:
        parts.append("Recent signals: " + ", ".join(c["cue"] for c in cues))

    if is_focus_mode():
        parts.append("Focus mode: ACTIVE")
    if is_social_mode():
        parts.append("Social mode: ACTIVE")

    actions = _tail_md_recent(_OPS_ACTIONS, 6, max_age_days=3)
    if actions:
        parts.append("Pending actions:\n" + "\n".join(f"  {l}" for l in actions))

    payments = _tail_md_recent(_OPS_PAYMENT, 4, max_age_days=7)
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
                if _total_h < 0:
                    _sentry = "SENTRY: target timestamp passed — review gate file"
                elif _cancel:
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
  Speak from it directly and naturally. Day labels are relative: "later today", "tomorrow", or a weekday name. Example: "You've got a call with Dane later today at two PM." — that kind of phrasing.
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

PAYMENT VERIFICATION:
  You have access to recent Gmail notifications and local income logs only.
  You do NOT have live bank or payment processor access.
  Never say a payment has "cleared the bank" or "arrived in the account."
  Always clarify that you are checking email receipts or logs.

FUTURE-ACTION AND REMINDER REQUESTS:
  If asked to "check again," "follow up," "send a reminder," or any future autonomous action:
  Do NOT say "I'm not able to do that" or "I can't do that" alone — that is too generic.
  Name the specific action the user asked for ("check again tomorrow," "send a reminder"),
  not generic placeholders.
  Direct reminder requests are live: you can queue and later surface a bounded reminder to Telegram.
  Do NOT present that as broad autonomous execution.
  You cannot autonomously re-check external systems, contact third parties, or perform broad future
  external follow-up from here.
  Offer alternatives (drafting, logging, holding) ONLY when the user's question was specifically
  about sending, following up, messaging, or reminders. Do NOT add drafting/logging offers
  as a default pivot after file, calendar, or payment limit responses.
  Correct form when the request fits the live reminder queue:
  "I can queue a reminder for tomorrow at 9. I can't re-check the external system, contact anyone,
  or handle a broader follow-up on my own from here."
  Never promise to follow up, check, message, or send autonomously beyond that bounded reminder queue.

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
  Do not promise to check, send, follow up, or contact people autonomously beyond the bounded
  reminder queue.
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
  Approval is required for every send — it goes through Guardian. A send may remain pending for up to 24 hours before timing out.

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


def _use_small_cassandra_reply_model(query: str) -> bool:
    t = query.lower()
    if any(k in t for k in _CASSANDRA_SYNTHESIS_KEYWORDS):
        return False
    if len(query.split()) > 18:
        return False
    complexity_markers = (
        "compare",
        "walk me through",
        "step by step",
        "why is",
        "how do",
        "what am i missing",
        "help me prioritize",
    )
    return not any(marker in t for marker in complexity_markers)


def _log_model_route(
    *,
    task_class: str,
    preferred_lane: str,
    chosen_lane: str,
    reason: str,
    escalation: bool,
    validation_outcome: str | None,
    model: str,
) -> None:
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task_class": task_class,
        "preferred_lane": preferred_lane,
        "chosen_lane": chosen_lane,
        "reason": reason,
        "escalation": escalation,
        "validation_outcome": validation_outcome,
        "model": model,
    }
    try:
        _MODEL_ROUTE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _MODEL_ROUTE_LOG.open("a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except Exception:
        pass


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
    "what do you show for work on",
)

_CALENDAR_CREATE_WORDS = (
    "schedule ", "add to my calendar", "put on my calendar", "put it on my calendar",
    "create an event", "create event", "block off", "set up a meeting",
    "add a meeting", "add an appointment", "make an appointment",
    "book ", "remind me ", "add ", "set a ", "set up ",
)


def _fetch_calendar_context(query: str, ops_packet: Any = None) -> str:
    """
    If the query has calendar intent, call the broker and return a formatted
    calendar context block for prompt injection.
    Returns "" if not applicable, broker denied, or no data.
    """
    # Use formal ops_packet if provided
    if ops_packet is not None:
        has_cal_cap = any(c.domain == "calendar" for c in ops_packet.permitted_capabilities)
        if not has_cal_cap:
            return ""

    t = query.lower().translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }))
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
    if any(w in t for w in _CALENDAR_CREATE_WORDS):
        return True
    # Cover natural phrasing like "put Doctor Appointment on my calendar",
    # which the exact substring list misses because words appear in between.
    return re.search(r"\bput\b.{0,120}\bon my calendar\b", t, re.DOTALL) is not None


def _detect_calendar_delete_intent(text: str) -> bool:
    """True if the query looks like a request to delete calendar events."""
    t = " ".join(text.lower().split())
    if "calendar" not in t:
        return False
    if "remove" not in t and "delete" not in t:
        return False
    return re.search(r"\b(remove|delete)\b.{0,140}\bfrom my calendar\b", t, re.DOTALL) is not None


def _extract_calendar_delete_details(text: str) -> dict | None:
    from datetime import date, timedelta

    normalized = " ".join(text.strip().split())
    direct_match = re.search(
        r"^\s*(?:cassandra,\s*)?(?:remove|delete)\s+(?:the\s+)?(?:(?P<count_word>one|two|\d+)\s+)?"
        r"(?P<title>.+?)\s+events?\s+(?P<day>tomorrow|today)\s+at\s+"
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)\s+from\s+my\s+calendar\.?\s*$",
        normalized,
        re.IGNORECASE,
    )
    if not direct_match:
        return None

    count_raw = (direct_match.group("count_word") or "1").lower()
    count_map = {"one": 1, "two": 2}
    max_matches = count_map.get(count_raw, None)
    if max_matches is None:
        try:
            max_matches = max(1, int(count_raw))
        except Exception:
            max_matches = 1

    hour = int(direct_match.group("hour"))
    minute = int(direct_match.group("minute") or "0")
    ampm = direct_match.group("ampm").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    event_date = date.today()
    if direct_match.group("day").lower() == "tomorrow":
        event_date = event_date + timedelta(days=1)

    return {
        "title": direct_match.group("title").strip(" ."),
        "date": event_date.strftime("%Y-%m-%d"),
        "start_time": f"{hour:02d}:{minute:02d}",
        "max_matches": max_matches,
    }


def _extract_event_details(text: str) -> dict | None:
    """
    Use an LLM to extract structured event details from natural language.
    Returns dict with keys: title, date (YYYY-MM-DD), start_time (HH:MM 24h),
    duration_minutes (int). Returns None on failure or missing required fields.
    """
    from datetime import date, datetime, timedelta

    normalized = " ".join(text.strip().split())
    direct_match = re.search(
        r"^\s*(?:cassandra,\s*)?put\s+(?P<title>.+?)\s+on\s+my\s+calendar\s+"
        r"(?P<day>tomorrow|today)\s+at\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
        r"(?P<ampm>am|pm)\s+for\s+(?P<duration>\d{1,3})\s+minutes?\.?\s*$",
        normalized,
        re.IGNORECASE,
    )
    if direct_match:
        title = direct_match.group("title").strip(" .")
        hour = int(direct_match.group("hour"))
        minute = int(direct_match.group("minute") or "0")
        ampm = direct_match.group("ampm").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        event_date = date.today()
        if direct_match.group("day").lower() == "tomorrow":
            event_date = event_date + timedelta(days=1)
        return {
            "title": title,
            "date": event_date.strftime("%Y-%m-%d"),
            "start_time": f"{hour:02d}:{minute:02d}",
            "duration_minutes": int(direct_match.group("duration")),
        }

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
        data = _call_hidden_extract_classify_json(prompt, validation_label="calendar_event_details")
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
    r"send\s+(?:an?\s+)?new\s+(?:email|message|msg)\s+to\s+"
    r"|send\s+(?:an?\s+)?(?:email|message|msg)\s+to\s+"
    r"|send\s+(?:an?\s+)?(?:email|message|msg)\s+(?:for\s+)?"
    r"|send\s+"
    r"|email\s+to\s+"
    r"|compose\s+(?:an?\s+)?(?:email|message)\s+to\s+"
    r")"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|[A-Za-z][A-Za-z0-9_.' -]{0,40}?)"
    r"(?:\s+(?:a\s+new\s+)?(?:email|message|msg)\b|\s+(?:subject:|about|saying|re:|:)\s*|$)",
    re.IGNORECASE,
)

_SUBJECT_RE = re.compile(r"(?:subject:|re:)\s*(.+?)(?:\s+body:|\s*\n|$)", re.IGNORECASE)
_BODY_RE    = re.compile(r"body:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_INFERRED_EMAIL_SUBJECT = "Quick note"

_NATURAL_EMAIL_PATTERNS = (
    re.compile(r"^\s*(?:can you|could you|please)?\s*email\s+(?P<to>.+?)\s+and\s+ask\s+if\s+(?P<body>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:please\s+)?send\s+(?P<to>.+?)\s+(?:a\s+)?note\s+about\s+(?P<body>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*tell\s+(?P<to>.+?)\s+by\s+email\s+that\s+(?P<body>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*i\s+need\s+(?P<to>.+?)\s+to\s+know\s+(?P<body>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:can you|could you|please)?\s*email\s+(?P<to>.+?)\s+and\s+say\s+(?P<body>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*send\s+(?P<to>.+?)\s+(?:a\s+)?quick\s+note\s+saying\s+(?P<body>.+?)\s*$", re.IGNORECASE),
)


def _detect_send_email_intent(text: str) -> bool:
    """True if the user's message is an email-send request."""
    from cassandra_capability import EMAIL_DRAFT_CONNECTED
    if not EMAIL_DRAFT_CONNECTED:
        return False
    t = text.lower()
    if any(k in t for k in _SEND_EMAIL_KEYWORDS):
        return True
    parsed = _parse_email_request(text)
    if parsed is None:
        return False
    to_name = str(parsed.get("to_name") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", to_name):
        return True
    resolved = resolve_outbound_contact(to_name)
    return resolved["status"] in {"exact", "fuzzy", "ambiguous"}


_OUTREACH_EMAIL_PATTERNS = (
    "send the intro emails",
    "send intro emails",
    "send the outreach emails",
    "send outreach emails",
    "send the cassandra intro emails",
)


def _detect_outreach_email_intent(text: str) -> bool:
    from cassandra_capability import EMAIL_DRAFT_CONNECTED
    if not EMAIL_DRAFT_CONNECTED:
        return False
    t = text.lower()
    return any(pattern in t for pattern in _OUTREACH_EMAIL_PATTERNS)


def _detect_file_verify_intent(text: str) -> bool:
    """Return True if the message is asking about file or path existence."""
    t = text.lower()
    # Require a file/path noun
    nouns = ("file", "path", "folder", "directory", "document")
    has_noun = any(n in t for n in nouns)
    # Or an explicit absolute path (starts with /)
    has_path = bool(re.search(r'(/[^\s,;:]+)', t))
    if not has_noun and not has_path:
        return False
    # Require an existence verb or question pattern
    verbs = ("exist", "exists", "there", "present", "missing",
             "find the", "check if", "check whether", "is there",
             "does it exist", "verify", "confirm")
    return any(v in t for v in verbs)


def _handle_file_verification_request(text: str) -> str | None:
    """Route file-existence queries to tools/file_verify. Returns reply or None."""
    if not _detect_file_verify_intent(text):
        return None
    try:
        import sys as _sys
        _tools_path = str(Path(__file__).resolve().parent / "tools")
        if _tools_path in _sys.path:
            _sys.path.remove(_tools_path)
        _sys.path.insert(0, _tools_path)
        from file_verify import answer_file_verification
        return answer_file_verification(text)
    except Exception as e:
        print(f"[cassandra] file_verify error: {e}", flush=True)
        return "I tried to check that path but hit a problem. You may need to verify it directly."


def _extract_markdown_section(md: str, header: str) -> str:
    lines = md.splitlines()
    section = []
    found = False
    header_level = 0
    for line in lines:
        clean_line = line.strip()
        match = re.match(r"^(#+)\s+", clean_line)
        if match:
            current_level = len(match.group(1))
            if not found:
                if header.lower() in clean_line.lower():
                    found = True
                    header_level = current_level
                    continue
            elif current_level <= header_level:
                break

        if found:
            section.append(line)

    return "\n".join(section).strip()


def _clean_ops_bullets(section: str) -> list[str]:
    bullets = []
    for raw_line in section.splitlines():
        item = raw_line.strip()
        if not item:
            continue
        if item.startswith(("-", "*")):
            item = item[1:].strip()
        if item:
            bullets.append(item)
    return bullets


def _rewrite_ops_confirmed_fact(item: str) -> list[str]:
    if item.startswith("Active Handoff:"):
        facts = ["Active handoff: current checkpoint for this work."]
        match = re.search(r"roadmap authority is\s+(.+?)\.?$", item, re.IGNORECASE)
        if match:
            facts.append(f"Canonical roadmap source: {match.group(1).rstrip('.')}.")
        return facts
    return [item]


def _build_cassandra_capability_packet() -> dict:
    """Return a compact, bounded capability map for Cassandra orientation prompts."""
    capabilities = {
        "read_only_scripts": [
            {
                "name": "orientation_snapshot",
                "command": "python scripts/orientation_snapshot.py",
                "purpose": "build/read the current orientation snapshot",
                "authority": "read_only",
            },
            {
                "name": "operator_status_check",
                "command": "python scripts/generate_operator_status.py --check",
                "purpose": "check generated operator status surfaces",
                "authority": "read_only",
            },
            {
                "name": "tool_inventory_query",
                "command": "python scripts/query_tool_inventory.py",
                "purpose": "inspect local tool inventory read-models",
                "authority": "read_only",
            },
            {
                "name": "tool_intake_query",
                "command": "python scripts/query_tool_intake.py",
                "purpose": "inspect tool intake candidates",
                "authority": "read_only",
            },
        ],
        "available_patterns": [
            "read local status/read-model files",
            "stage bounded requests for approval",
            "draft review material without sending",
            "ask follow-up questions when context is old or ambiguous",
        ],
        "hard_bounds": [
            "no external sends",
            "no deploy, push, merge, service restart, or destructive mutation",
            "no account or money movement",
            "no raw restricted values in model prompts",
        ],
    }

    reconciliation_path = Path("generated/read_models/cassandra_email_calendar_capability_reconciliation.json")
    try:
        if reconciliation_path.exists():
            data = json.loads(reconciliation_path.read_text(encoding="utf-8"))
            capabilities["connector_status"] = {
                "live_mail_read_enabled": bool(data.get("live_gmail_read_enabled")),
                "live_calendar_read_enabled": bool(data.get("live_calendar_read_enabled")),
                "mail_draft_creation_enabled": bool(data.get("gmail_draft_creation_enabled")),
                "mail_send_enabled": bool(data.get("email_send_enabled")),
                "calendar_mutation_enabled": bool(data.get("calendar_mutation_enabled")),
                "audit_only": bool(data.get("audit_only")),
            }
    except Exception:
        capabilities["connector_status"] = {"status": "unreadable"}

    return capabilities


def _build_ops_status_packet(query: str) -> dict:
    """Build Cassandra's deterministic orientation packet; this is context, not voice."""
    current_state_path = Path("Operator/GENERATED_CURRENT_STATE.md")
    next_actions_path = Path("Operator/GENERATED_NEXT_ACTIONS.md")

    if not current_state_path.exists() or not next_actions_path.exists():
        return {
            "packet_type": "cassandra_orientation_status_v1",
            "query": query,
            "status": "missing_surfaces",
            "missing": [
                str(current_state_path),
                str(next_actions_path),
            ],
            "safe_operator_reply": (
                "Orientation status surfaces are missing. "
                "Please run 'python scripts/generate_operator_status.py --check', "
                "then '--write' only if stale."
            ),
        }

    try:
        current_md = current_state_path.read_text(encoding="utf-8")
        next_md = next_actions_path.read_text(encoding="utf-8")

        lane = _extract_markdown_section(current_md, "Active Lane")
        next_move = _extract_markdown_section(next_md, "Next Safe Move")
        unsafe_beyond = _extract_markdown_section(next_md, "Unsafe Beyond")
        confirmed = _extract_markdown_section(current_md, "Confirmed System State")

        # Fallback to get_orientation_snapshot if extraction fails to find something
        # (This is a read-only fallback, does not write files)
        if not lane or not next_move:
            try:
                from scripts.orientation_snapshot import get_orientation_snapshot
                snapshot = get_orientation_snapshot()
                lane = lane or snapshot.get("active_lane")
                next_move = next_move or snapshot.get("next_safe_move")
            except Exception:
                pass

        confirmed_facts = []
        for fact in _clean_ops_bullets(confirmed):
            confirmed_facts.extend(_rewrite_ops_confirmed_fact(fact))

        return {
            "packet_type": "cassandra_orientation_status_v1",
            "query": query,
            "status": "ready",
            "current_documented_lane": lane or "Unknown",
            "raw_next_safe_move": next_move or "Unknown",
            "recommended_next_move": (
                "Review Orientation Snapshot v0 for five-second usefulness. "
                "After wording is approved, wire Cassandra's read-only where-are-we response "
                "to that verified snapshot."
                if next_move else "Unknown"
            ),
            "confirmed_facts": confirmed_facts,
            "not_yet_confirmed": [
                "Cassandra is not yet confirmed to be reading directly from Orientation Snapshot v0.",
                "No live runtime health is claimed.",
                "Some personal operations read-models may be old; if the operator says stale, ask what should change.",
                "No external model key or configured external model is assumed by this packet.",
            ],
            "unsafe_beyond": unsafe_beyond,
            "capabilities": _build_cassandra_capability_packet(),
            "voice_instructions": [
                "Answer as Cassandra, not as the packet.",
                "Do not expose internal jargon like deterministic surfaces.",
                "Choose one recommended next move, then mention alternatives only if helpful.",
                "Translate uncertainty into practical consequences.",
                "If the operator says something is stale, ask what they want changed.",
            ],
        }
    except Exception:
        return {
            "packet_type": "cassandra_orientation_status_v1",
            "query": query,
            "status": "read_error",
            "safe_operator_reply": (
                "Orientation status surfaces could not be read safely. "
                "Run the generated status check, then retry."
            ),
        }


def _format_ops_status_fallback(packet: dict) -> str:
    if packet.get("safe_operator_reply"):
        return str(packet["safe_operator_reply"])

    confirmed_facts = packet.get("confirmed_facts")
    reply = [
        "OpenClaw Orientation",
        "",
        "Current documented lane",
        str(packet.get("current_documented_lane") or "Unknown"),
        "",
        "Recommended next move",
        str(packet.get("recommended_next_move") or "Unknown"),
        "",
        "Confirmed",
    ]
    if isinstance(confirmed_facts, list) and confirmed_facts:
        reply.extend(f"- {fact}" for fact in confirmed_facts)
    else:
        reply.append("- None recorded")
    reply.extend([
        "",
        "Not yet confirmed",
        "- Cassandra is not yet confirmed to be reading directly from Orientation Snapshot v0.",
        "- No claim is being made about live runtime health.",
        "",
        "Status: Ready for snapshot wording review.",
    ])
    return "\n".join(reply)


def _build_ops_status_model_prompt(query: str, packet: dict) -> str:
    packet_json = json.dumps(packet, indent=2, sort_keys=True)
    return (
        "You are Cassandra, the operator-facing OpenClaw orientation voice.\n"
        "The JSON packet below is bounded context, not final copy.\n"
        "Use the packet to answer the operator in plain, practical language.\n"
        "Keep it concise. Pick one best next move. Do not claim live runtime health.\n"
        "Do not expose internal implementation phrases unless the operator asks for backend details.\n"
        "If any context sounds old or the operator says it is stale, ask what should change.\n"
        "Mention available script-backed capabilities only when they help the next move.\n\n"
        f"Operator question: {query}\n\n"
        f"ORIENTATION_PACKET_JSON:\n{packet_json}\n\n"
        "Cassandra:"
    )


def _answer_ops_status_inquiry(query: str, state: dict) -> tuple[str, dict]:
    packet = _build_ops_status_packet(query)
    if packet.get("status") != "ready":
        return _format_ops_status_fallback(packet), packet
    prompt = _build_ops_status_model_prompt(query, packet)
    safe_prompt, pii_ctx = _pii_tokenize(prompt)
    if safe_prompt is None:
        return _format_ops_status_fallback(packet), packet

    metadata = {
        "workload": "cassandra_user_reply",
        "cloud_ok": True,
        "data_classification": "sanitized_public",
        "cloud_allowed": "true",
    }
    reply = external_language_model_call(
        safe_prompt,
        metadata=metadata,
        timeout=20,
    ).strip()
    if reply:
        print("[cassandra] orientation reply routed to external language model", flush=True)
        reply = _pii_rehydrate_reply(reply, pii_ctx).strip()
    if not reply:
        print("[cassandra] orientation external model unavailable; using verified snapshot fallback", flush=True)
        reply = _format_ops_status_fallback(packet)
    return reply, packet


def _handle_ops_status_inquiry(query: str) -> str:
    """Backward-compatible deterministic fallback for status inquiries."""
    return _format_ops_status_fallback(_build_ops_status_packet(query))


def _detect_payment_verify_intent(text: str) -> bool:
    """Return True if the message is asking to verify an external payment status."""
    from cassandra_capability import PAYMENT_METADATA_CONNECTED
    if not PAYMENT_METADATA_CONNECTED:
        return False
    return _looks_like_payment_verify_query(text)


def _handle_payment_verification_request(text: str) -> str | None:
    """
    Route payment verification queries to Gmail metadata and logs.
    Returns a direct Cassandra reply or None to fall through to LLM.
    """
    if not _detect_payment_verify_intent(text):
        return None

    known_reply = _known_payment_status_reply(text)
    if known_reply is not None:
        return known_reply

    ctx = _fetch_payment_verify_context(text)
    if not ctx:
        return None

    if "[VERIFIED PAYMENT DATA — no recent Gmail notifications found]" in ctx:
        # Check logs before giving up
        try:
            from chief_cpa_brain import get_recent_income
            # Extract possible entity like "Hilton"
            m = re.search(r"(?:the\s+)?([A-Za-z0-9]{3,20})\s+payment", text, re.I)
            if not m:
                m = re.search(r"payment\s+from\s+([A-Za-z0-9]{3,20})", text, re.I)
            entity = m.group(1).lower() if m else None
            logs = get_recent_income(days=7)
            if entity:
                match = next((e for e in logs if entity in (e.get("payer") or "").lower()), None)
                if match:
                    return f"I don't see a Gmail notification for that, but I do have a {match.get('payer')} payment logged for ${match['amount']} on {match['date']}."
        except Exception:
            pass
        return "I checked your recent Gmail notifications but didn't see any matching that payment yet."

    if "Gmail unreachable" in ctx:
        return "I tried to check your Gmail for payment notifications but the service is unreachable right now."

    if "From:" in ctx:
        # Extract first match for a direct answer
        try:
            lines = ctx.splitlines()
            from_name = ""
            subject = ""
            for l in lines:
                if "From:" in l: from_name = l.split("From:")[1].strip()
                if "Subject:" in l: subject = l.split("Subject:")[1].strip()
                if from_name and subject: break
            if from_name and subject:
                return f"I've verified a matching notification in your Gmail: {subject} from {from_name}."
        except Exception:
            pass

    # Fall through to LLM for nuanced answers if we can't format a simple one
    return None


def _handle_finance_status_request(text: str, state: dict | None = None) -> str | None:
    if not detect_finance_status_intent(text):
        return None
    found_override = _get_session_fact_override(text, state or {})
    if found_override is not None:
        _, override = found_override
        summary = str(override.get("summary") or "").strip()
        if summary:
            return summary if summary.endswith((".", "!", "?")) else summary + "."
    reply = get_finance_status_answer(text)
    if reply is not None and isinstance(state, dict):
        _remember_finance_entity(text, state)
        return (
            "Stored finance read-model says (not live-confirmed): "
            f"{reply} If that's stale, tell me what to change."
        )
    return reply


def _should_route_finance_status_before_intake(text: str, gmail_decision: Any | None = None) -> bool:
    if not detect_finance_status_intent(text):
        return False
    t = (text or "").lower()
    status_markers = (
        "status",
        "where are we",
        "where do we stand",
        "what is current",
        "what's current",
        "current truth",
        "current state",
        "latest",
        "update",
    )
    live_verify_markers = (
        "come through",
        "did it land",
        "hit the account",
        "cleared",
        "posted",
        "verify",
        "confirm",
        "search",
        "find the",
        "see the",
    )
    if any(marker in t for marker in live_verify_markers):
        return False
    if any(marker in t for marker in status_markers):
        return True
    if getattr(gmail_decision, "category", "") == "payment_verify":
        return False
    return not _looks_like_payment_verify_query(text)


# ── Future-action enqueue pipeline ───────────────────────────────────────────

# Direct action phrases that unambiguously signal a reminder/queue request.
# "tomorrow" and "next week" alone are excluded — they appear in calendar and
# scheduling contexts. Co-occurrence with a verb phrase is required instead.
_FUTURE_ACTION_PHRASES = (
    "remind me",
    "remind us",
    "follow up",
    "follow-up",
    "check back",
    "check again",
    "send a reminder",
    "set a reminder",
)

# Action verbs that, when co-present with a parser-supported time reference,
# indicate future-action intent. Keep this list aligned with
# tools/future_action_queue._parse_due_at() so Cassandra does not imply support
# for relative dates the queue cannot actually schedule.
_FUTURE_ACTION_VERBS = ("remind", "follow up", "follow-up", "check back", "check again", "ping me")
_FUTURE_ACTION_TIME_WORDS = ("tomorrow", "next week", "next month")


def _detect_future_action_intent(text: str) -> bool:
    """True if the query is a reminder or future follow-up queue request.

    Matches direct action phrases (e.g. "remind me", "follow up") and also
    the combination of an actually supported time word + action verb. Does NOT
    match bare "tomorrow" or "next week" to avoid capturing calendar and
    scheduling queries.
    """
    t = text.lower()
    # Draft approval messages contain "follow up" in their body but are NOT reminder requests
    if any(phrase in t for phrase in ("draft is approved", "draft approved", "prepare the send authority", "send authority request")):
        return False
    if any(phrase in t for phrase in _FUTURE_ACTION_PHRASES):
        return True
    # Require both a time word and an action verb to match indirect patterns
    has_time = any(word in t for word in _FUTURE_ACTION_TIME_WORDS)
    has_verb = any(verb in t for verb in _FUTURE_ACTION_VERBS)
    return has_time and has_verb


def _detect_send_authority_prepared_status_echo(text: str) -> bool:
    """True for Cassandra's own send-authority-prepared operator status line."""
    normalized = " ".join(str(text or "").lower().split())
    return all(
        phrase in normalized
        for phrase in (
            "prepared the send authority request",
            "nothing has been sent",
            "approve the exact send request",
        )
    )


def _handle_send_authority_prepared_status_echo(text: str) -> str:
    match = re.search(r"send authority request for\s+([^\s,;]+@[^\s,;]+)", str(text or ""), re.IGNORECASE)
    recipient = match.group(1).rstrip(".") if match else "the recipient"
    return (
        f"The send-authority request for {recipient} is already prepared. "
        "Nothing has been sent. Next: review and approve the exact send request only if it matches what you want."
    )


def _handle_future_action_queue_request(text: str, sender_chat_id: object | None = None) -> str | None:
    """Enqueue a future-action reminder. Returns reply string or None if not a match."""
    if not _detect_future_action_intent(text):
        return None
    try:
        from cassandra_capability import FUTURE_ACTION_CONNECTED
    except Exception:
        FUTURE_ACTION_CONNECTED = False
    if not FUTURE_ACTION_CONNECTED:
        return (
            "I can't check back or send a reminder from here — "
            "future-action isn't connected yet. You may need to check back manually."
        )
    try:
        import sys as _sys
        _tools_path = str(Path(__file__).resolve().parent / "tools")
        if _tools_path in _sys.path:
            _sys.path.remove(_tools_path)
        _sys.path.insert(0, _tools_path)
        from future_action_queue import enqueue_request
        result = enqueue_request(text, chat_id=str(sender_chat_id or ""))
        return result["message"]
    except Exception as e:
        print(f"[cassandra] future_action_queue error: {e}", flush=True)
        return "I tried to queue that but hit a problem. You may want to check back manually."


import cassandra_identity as _cassandra_identity

_IDENTITY_DEFAULT_NICKNAMES_PATH = _cassandra_identity._NICKNAMES_PATH
_NICKNAMES_PATH = _IDENTITY_DEFAULT_NICKNAMES_PATH
_LAST_SYNCED_NICKNAMES_PATH = _IDENTITY_DEFAULT_NICKNAMES_PATH

_DEFAULT_DESIGNATED_CONTACTS = {
    "dad": {
        "name": "Henry Winship Wheatley III",
        "tier": "inner_circle",
        "aliases": ["Henry Wheatley", "Mr. Wheatley"],
    },
    "mom": {
        "name": "Susan Elizabeth Wheatley",
        "tier": "inner_circle",
        "aliases": ["Susan Wheatley", "Mrs. Wheatley"],
    },
    "draper": {
        "name": "Draper Carter",
        "tier": "inner_circle",
        "aliases": ["Draper"],
    },
    "sampleclient": {
        "name": "Sarah Johansen",
        "tier": "client",
        "aliases": ["Sarah"],
    },
}


def _sync_identity_nicknames_path() -> None:
    """Keep brain and identity nickname-path monkeypatches visible to each other."""
    global _NICKNAMES_PATH, _LAST_SYNCED_NICKNAMES_PATH

    brain_path = _NICKNAMES_PATH
    identity_path = _cassandra_identity._NICKNAMES_PATH
    identity_side_patch = (
        brain_path == _IDENTITY_DEFAULT_NICKNAMES_PATH
        and identity_path != brain_path
        and identity_path != _LAST_SYNCED_NICKNAMES_PATH
    )

    if identity_side_patch:
        _NICKNAMES_PATH = identity_path
    else:
        _cassandra_identity._NICKNAMES_PATH = brain_path

    _LAST_SYNCED_NICKNAMES_PATH = _cassandra_identity._NICKNAMES_PATH


def _load_nicknames() -> dict:
    _sync_identity_nicknames_path()
    return _cassandra_identity._load_nicknames()


def _normalize_contact_entry(nickname: str, raw: object) -> dict:
    _sync_identity_nicknames_path()
    return _cassandra_identity._normalize_contact_entry(nickname, raw)


def _contact_data_for_routing() -> dict:
    """Return contact data for routing without requiring a live nickname file."""
    data = _load_nicknames()
    return data if data else dict(_DEFAULT_DESIGNATED_CONTACTS)


def _find_designated_contact(sender_name: str | None = None, sender_chat_id: object | None = None) -> dict | None:
    name_key = sender_name.strip().lower() if isinstance(sender_name, str) and sender_name.strip() else ""
    chat_key = str(sender_chat_id) if sender_chat_id not in (None, "") else ""
    for nickname, raw in _contact_data_for_routing().items():
        entry = _normalize_contact_entry(nickname, raw)
        if name_key and name_key in entry["sender_names"]:
            return entry
        if chat_key and chat_key in entry["chat_ids"]:
            return entry
    return None


def find_contact_by_nickname(nickname: str) -> dict | None:
    norm_nickname = str(nickname or "").lower()
    data = _contact_data_for_routing()
    if norm_nickname in data:
        return _normalize_contact_entry(norm_nickname, data[norm_nickname])
    return None


def resolve_outbound_contact(name: str) -> dict:
    _sync_identity_nicknames_path()
    return _cassandra_identity.resolve_outbound_contact(name)


def is_designated_contact_sender(
    sender_name: str | None = None,
    sender_chat_id: object | None = None,
) -> bool:
    return _find_designated_contact(sender_name=sender_name, sender_chat_id=sender_chat_id) is not None


def is_pinned_on_channel(nickname: str, channel: str) -> bool:
    raw = _contact_data_for_routing().get(str(nickname or "").lower())
    if raw is None:
        return False
    entry = _normalize_contact_entry(str(nickname or "").lower(), raw)
    if channel == "telegram":
        return bool(entry["chat_ids"])
    if channel == "email":
        return entry["pinned_email"] is not None
    if channel in ("sms", "phone"):
        return entry["pinned_phone"] is not None
    if channel == "whatsapp":
        return entry["pinned_whatsapp"] is not None
    return False


def verify_sender_on_channel(
    sender_name: str | None,
    sender_id: str | None,
    channel: str,
) -> dict | None:
    _sync_identity_nicknames_path()
    return _cassandra_identity.verify_sender_on_channel(
        sender_name=sender_name,
        sender_id=sender_id,
        channel=channel,
    )


def pin_telegram_chat_id(nickname: str, chat_id: str | int) -> bool:
    """Updates contact_nicknames.json with a pinned telegram_chat_id for a nickname."""
    try:
        if not _NICKNAMES_PATH.exists():
            print(f"[cassandra_brain] pin error: {_NICKNAMES_PATH} not found", flush=True)
            return False

        data = json.loads(_NICKNAMES_PATH.read_text(encoding="utf-8"))
        norm_nickname = nickname.lower()
        if norm_nickname not in data:
            print(f"[cassandra_brain] pin error: nickname '{nickname}' not in contact_nicknames.json", flush=True)
            return False

        data[norm_nickname]["telegram_chat_id"] = str(chat_id)
        _NICKNAMES_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Log it to conversation log
        _log_conversation(
            f"ADMIN: Pin telegram_chat_id={chat_id} to nickname='{nickname}'",
            [f"Pinned {chat_id} to '{nickname}' successfully."],
            route="admin_pin"
        )
        return True
    except Exception as e:
        print(f"[cassandra_brain] pin error: {e}", flush=True)
        return False


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
        suppress_flag = spec.get("suppress_when_flag")
        if suppress_flag and _capability_flag_value(suppress_flag) is True:
            continue
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
    tmp_path = _FOLLOWUP_LOG.with_name(f"{_FOLLOWUP_LOG.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, _FOLLOWUP_LOG)


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


def _create_upgrade_task(
    capability_gap: dict,
    original_message: str,
    *,
    extra_scope_lines: list[str] | None = None,
    force_queue_manual: bool = False,
) -> str | None:
    capability = capability_gap["capability"]
    existing = _existing_upgrade_task_name(capability)
    if existing:
        return existing
    if capability_gap.get("manual_required") and not force_queue_manual:
        return None

    _POLISH_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    task_name = f"cas-upgrade-{capability}-{timestamp}"
    task_path = _POLISH_TASKS_DIR / f"{task_name}.md"
    safe_original = original_message.strip().replace("\n", " ").replace('"', "'")
    scope_items = list(capability_gap["scope"])
    if extra_scope_lines:
        scope_items.extend(extra_scope_lines)
    scope_lines = "\n".join(f"- {line}" for line in scope_items)
    task_body = (
        f"title: {task_name}\n"
        f"goal: {capability_gap['goal']}\n"
        "scope:\n"
        f"{scope_lines}\n"
        f"- Handle the triggering request safely: \"{safe_original}\"\n"
        "success:\n"
        f"- {capability_gap['success']}\n"
    )
    if capability_gap.get("manual_required") and force_queue_manual:
        task_body += "execution mode: human-supervised\n"
    task_path.write_text(task_body, encoding="utf-8")
    return task_name


def _registry_capability_connected(capability_name: str) -> bool | None:
    actor = get_actor("cassandra")
    if actor is None:
        return None
    for capability in actor.capabilities:
        if capability.name == capability_name:
            return bool(capability.connected)
    return None


def _detect_email_review_capability_gap(review_text: str) -> dict | None:
    lowered = review_text.lower()
    for capability_name, patterns in _EMAIL_REVIEW_CAPABILITY_ASSERTIONS.items():
        if _registry_capability_connected(capability_name) is not False:
            continue
        if not any(re.search(pattern, lowered) for pattern in patterns):
            continue
        gap = dict(_CAPABILITY_GAP_SPECS.get(capability_name, {}))
        if not gap:
            continue
        gap["capability"] = capability_name
        return gap
    return None


def _queue_email_review_gap_task(
    capability_gap: dict,
    *,
    original_message: str,
    recipient_name: str,
    recipient_email: str,
    draft_subject: str,
) -> str | None:
    extra_scope = [
        f"Email review recipient: {recipient_name} <{recipient_email}>",
        f"Blocked draft subject: {draft_subject}",
        "Keep the grounded email review path honest so Cassandra stops bluffing about this gap.",
    ]
    return _create_upgrade_task(
        capability_gap,
        original_message,
        extra_scope_lines=extra_scope,
        force_queue_manual=True,
    )


def _email_draft_has_payment_assertion(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _EMAIL_REVIEW_PAYMENT_ASSERTIONS)


def _email_draft_has_calendar_assertion(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _EMAIL_REVIEW_CALENDAR_ASSERTIONS)


def _payment_context_is_verified(payment_ctx: str) -> bool:
    return payment_ctx.startswith("[VERIFIED GMAIL NOTIFICATIONS")


def _calendar_context_is_verified(calendar_ctx: str) -> bool:
    return calendar_ctx.startswith("[CALENDAR DATA")


def _rewrite_payment_email_uncertainty(payment_ctx: str) -> str:
    if payment_ctx.startswith("[VERIFIED PAYMENT DATA — no recent Gmail notifications found]"):
        detail = "I checked the current payment notifications and I don't have confirmation that it came through yet."
    elif "Gmail unreachable" in payment_ctx or "error during Gmail fetch" in payment_ctx:
        detail = "I couldn't verify the current payment status because the live Gmail check is unavailable right now."
    else:
        detail = "I can't confirm the current payment status from the live record I have."
    return f"{_EMAIL_REVIEW_UNCERTAINTY_PREFIX} {detail}"


def _rewrite_calendar_email_uncertainty() -> str:
    return (
        f"{_EMAIL_REVIEW_UNCERTAINTY_PREFIX} "
        "I need a live calendar check before I state that schedule as settled."
    )


def _review_grounded_email_draft(
    *,
    recipient_name: str,
    recipient_email: str,
    original_message: str,
    draft_subject: str,
    draft_body: str,
) -> dict:
    review_text = "\n".join(
        part.strip()
        for part in (original_message, draft_subject, draft_body)
        if isinstance(part, str) and part.strip()
    )

    contact_entry = _find_designated_contact(sender_name=recipient_name)
    if contact_entry is not None and contact_entry.get("tier") == "inner_circle":
        verified_contact = verify_sender_on_channel(
            sender_name=recipient_name,
            sender_id=recipient_email,
            channel="email",
        )
        if verified_contact is None:
            return {
                "status": "blocked",
                "subject": draft_subject,
                "body": draft_body,
                "detail": "grounded review blocked — recipient email pin is not verified",
                "queued_task_name": None,
                "user_reply": (
                    "I didn't draft that because the recipient's pinned email address "
                    "isn't verified yet."
                ),
            }

        from cassandra_contact_policy import classify_topic

        lane = classify_topic(review_text, verified_contact["nickname"])
        if lane != "allowed":
            return {
                "status": "blocked",
                "subject": draft_subject,
                "body": draft_body,
                "detail": f"grounded review blocked — {verified_contact['nickname']} trust lane={lane}",
                "queued_task_name": None,
                "user_reply": (
                    "I didn't draft that because it crosses this contact's trust lane. "
                    "Winship should review that reply directly."
                ),
            }

    capability_gap = _detect_email_review_capability_gap(review_text)
    if capability_gap:
        task_name = _queue_email_review_gap_task(
            capability_gap,
            original_message=original_message or review_text,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            draft_subject=draft_subject,
        )
        task_note = f" I queued {task_name}." if task_name else ""
        return {
            "status": "blocked",
            "subject": draft_subject,
            "body": draft_body,
            "detail": f"grounded review blocked — capability gap {capability_gap['capability']}",
            "queued_task_name": task_name,
            "user_reply": (
                "I didn't draft that because it leans on a capability I can't back up yet."
                f"{task_note}"
            ),
        }

    if _email_draft_has_payment_assertion(draft_body):
        payment_ctx = _fetch_payment_verify_context(review_text)
        if not _payment_context_is_verified(payment_ctx):
            return {
                "status": "rewritten",
                "subject": draft_subject,
                "body": _rewrite_payment_email_uncertainty(payment_ctx),
                "detail": "grounded review rewrote payment certainty",
                "queued_task_name": None,
                "user_reply": "",
            }

    if _email_draft_has_calendar_assertion(draft_body):
        calendar_ctx = _fetch_calendar_context(review_text)
        if not _calendar_context_is_verified(calendar_ctx):
            return {
                "status": "rewritten",
                "subject": draft_subject,
                "body": _rewrite_calendar_email_uncertainty(),
                "detail": "grounded review rewrote calendar certainty",
                "queued_task_name": None,
                "user_reply": "",
            }

    return {
        "status": "allowed",
        "subject": draft_subject,
        "body": draft_body,
        "detail": "grounded review allowed",
        "queued_task_name": None,
        "user_reply": "",
    }


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
    sender_channel: str | None,
    sender_email: str | None,
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
            "sender_channel": sender_channel,
            "sender_email": sender_email.strip().lower() if isinstance(sender_email, str) and sender_email.strip() else None,
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


def _resolve_followup_email_target(record: dict) -> tuple[str, str] | None:
    sender_channel = str(record.get("sender_channel", "")).strip().lower()
    sender_name = str(record.get("sender_name", "")).strip() or "Unknown recipient"
    sender_email = str(record.get("sender_email", "")).strip().lower()

    if sender_channel != "email":
        return None

    verified_contact = None
    if sender_email:
        verified_contact = verify_sender_on_channel(
            sender_name=sender_name,
            sender_id=sender_email,
            channel="email",
        )
    if verified_contact is None:
        contact_entry = _find_designated_contact(sender_name=sender_name, sender_chat_id=None)
        if contact_entry is not None and contact_entry.get("pinned_email"):
            verified_contact = verify_sender_on_channel(
                sender_name=sender_name,
                sender_id=contact_entry["pinned_email"],
                channel="email",
            )
    if verified_contact is None:
        return None
    return verified_contact["pinned_email"], verified_contact["display_name"]


def _build_followup_email_subject(original_message: str) -> str:
    preview = _bridge_preview(original_message.strip().replace("\n", " "), limit=72)
    return f"Follow-up: {preview or 'your question'}"


def _create_followup_email_draft(record: dict, followup_reply: str) -> bool:
    target = _resolve_followup_email_target(record)
    if target is None:
        return False

    recipient_email, recipient_name = target
    subject = _build_followup_email_subject(str(record.get("original_message", "")))
    review = _review_grounded_email_draft(
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        original_message=str(record.get("original_message", "")),
        draft_subject=subject,
        draft_body=followup_reply,
    )
    if review["status"] == "blocked":
        _log_correspondence_state(
            recipient_name,
            _SS_BLOCKED,
            review["detail"],
            route="followup_email_draft",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        return False

    subject = review["subject"]
    body = review["body"]
    review_inbox = get_review_inbox()
    try:
        result = broker_call("cassandra", "google.gmail.draft.create", {
            "to": recipient_email,
            "cc": review_inbox,
            "subject": subject,
            "body": body,
        })
    except Exception as exc:
        _log_correspondence_state(
            recipient_name,
            _SS_SEND_FAILED,
            str(exc),
            route="followup_email_draft",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        print(f"[cassandra_followup] email draft broker error: {exc}", flush=True)
        return False

    if result.get("ok"):
        result_data = result.get("data") or {}
        detail = f"subject={subject}"
        if review["status"] == "rewritten":
            detail += f"; {review['detail']}"
        draft_id = str(result_data.get("draft_id", "")).strip()
        if draft_id:
            detail += f"; draft_id={draft_id}"
        _log_correspondence_state(
            recipient_name,
            _SS_DRAFT,
            detail,
            route="followup_email_draft",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
                "draft_id": draft_id,
                "message_id": result_data.get("message_id", ""),
                "thread_id": result_data.get("thread_id", ""),
            },
        )
        return True

    err = str(result.get("error", "unknown error"))
    state = _SS_BLOCKED if "denied" in err.lower() else _SS_SEND_FAILED
    detail = "denied at approval gate" if state == _SS_BLOCKED else err
    _log_correspondence_state(
        recipient_name,
        state,
        detail,
        route="followup_email_draft",
        metadata={
            "recipient_email": recipient_email,
            "subject": subject,
            "mailbox_identity": "primary",
        },
    )
    return False


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
            sent_ok = _create_followup_email_draft(record, followup_reply)
            if not sent_ok:
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
    direct_email = str(name or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", direct_email):
        return (direct_email, direct_email)

    resolved = resolve_outbound_contact(name)
    if resolved["status"] in {"exact", "fuzzy"}:
        return (resolved["email"], resolved["display_name"])
    if resolved["status"] == "ambiguous":
        choices = ", ".join(resolved["candidates"])
        return ("", f"I found multiple plausible contacts for {name}: {choices}. Tell me which one you mean before I draft it.")

    # Compatibility wrapper: delegate to cassandra_outreach._resolve_contact_email
    try:
        from cassandra_outreach import _resolve_contact_email
        email, display_name = _resolve_contact_email(name)
        return email, display_name
    except RuntimeError as e:
        # Match legacy error message shape
        return ("", str(e))
    except Exception as e:
        return ("", f"Couldn't reach the contacts broker: {e}")


def _parse_email_request(text: str) -> dict | None:
    """
    Parse an email send request from natural language.
    Returns {"to_name": str, "subject": str, "body": str} on success,
    or None if the recipient name cannot be extracted.

    Supported format:
        send email to [name] subject: [subject] body: [body]
    """
    for pattern in _NATURAL_EMAIL_PATTERNS:
        natural = pattern.search(text)
        if not natural:
            continue
        to_name = str(natural.group("to") or "").strip(" ,.")
        body = str(natural.group("body") or "").strip()
        if not to_name or not body:
            return None
        return {"to_name": to_name, "subject": _INFERRED_EMAIL_SUBJECT, "body": body}

    m_to = _SEND_EMAIL_RE.search(text)
    if not m_to:
        return None

    to_name = m_to.group(1).strip()

    m_subj = _SUBJECT_RE.search(text)
    subject = m_subj.group(1).strip() if m_subj else ""

    m_body = _BODY_RE.search(text)
    body    = m_body.group(1).strip() if m_body else ""

    if m_subj or m_body:
        return {"to_name": to_name, "subject": subject, "body": body}

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
      5. Create a brokered Gmail draft.
      6. Launch the approval-gated send in the background.
      7. Return honest draft confirmation or error message.
    """
    parsed = _parse_email_request(text)
    if parsed is None:
        return None  # can't parse — fall through to LLM

    to_name = parsed["to_name"]
    subject = parsed["subject"]
    body    = parsed["body"]

    # Resolve recipient
    resolution = resolve_outbound_contact(to_name)
    if resolution["status"] in {"exact", "fuzzy"}:
        email_addr = resolution["email"]
        display_name = resolution["display_name"]
    elif resolution["status"] == "ambiguous":
        choices = ", ".join(resolution["candidates"])
        return f"I found multiple plausible contacts for {to_name}: {choices}. Tell me which one you mean before I draft it."
    else:
        email_addr, display_name = _resolve_recipient_email(to_name)
        if not email_addr:
            return display_name  # error message from resolution

    # Require both subject and body — prompt if either is missing
    if not subject or not body:
        _log_correspondence_state(
            display_name,
            _SS_DRAFT,
            "awaiting subject/body from user",
            route="email_send",
            metadata={
                "recipient_email": email_addr,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        return (
            f"Got it — I can draft that for {display_name}. "
            "To complete this, reply with:\n"
            f"send email to {to_name} subject: [subject line] body: [your message]"
        )

    review = _review_grounded_email_draft(
        recipient_name=display_name,
        recipient_email=email_addr,
        original_message=text,
        draft_subject=subject,
        draft_body=body,
    )
    if review["status"] == "blocked":
        _log_correspondence_state(
            display_name,
            _SS_BLOCKED,
            review["detail"],
            route="email_review",
            metadata={
                "recipient_email": email_addr,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        return review["user_reply"]
    subject = review["subject"]
    body = review["body"]
    review_inbox = get_review_inbox()

    # Use outreach-owned transport abstraction
    from cassandra_outreach import create_gmail_draft
    draft_result = create_gmail_draft(email_addr, subject, body, review_inbox, review["status"], review.get("detail", ""))
    if not draft_result["ok"]:
        err_str = draft_result["error"]
        print(f"[cassandra] email draft broker error: {err_str}", flush=True)
        _log_correspondence_state(
            display_name,
            _SS_SEND_FAILED,
            err_str,
            route="email_send",
            metadata={
                "recipient_email": email_addr,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        return "The email draft system isn't reachable right now. No draft was created — try again in a moment."

    result = draft_result["result"]
    if result.get("ok"):
        result_data = result.get("data") or {}
        draft_id = result_data.get("draft_id", "")
        detail = f"subject={subject}"
        if review["status"] == "rewritten":
            detail += f"; {review['detail']}"
        if draft_id:
            detail += f"; draft_id={draft_id}"
        _log_correspondence_state(
            display_name,
            _SS_DRAFT,
            detail,
            route="email_send",
            metadata={
                "recipient_email": email_addr,
                "subject": subject,
                "mailbox_identity": "primary",
                "draft_id": draft_id,
                "message_id": result_data.get("message_id", ""),
                "thread_id": result_data.get("thread_id", ""),
            },
        )
        _start_email_send_after_draft(
            recipient_name=display_name,
            recipient_email=email_addr,
            subject=subject,
            body=body,
            review_inbox=review_inbox,
            draft_id=draft_id,
            draft_message_id=str(result_data.get("message_id", "")),
            draft_thread_id=str(result_data.get("thread_id", "")),
            approval_context=_build_send_approval_context(
                recipient_name=display_name,
                recipient_email=email_addr,
                subject=subject,
                body=body,
                review_inbox=review_inbox,
            ),
        )
        reply = (
            f"Drafted. Email to {display_name} with subject \"{subject}\" is ready in "
            f"{review_inbox} for review, with {review_inbox} on CC."
        )
        if resolution["status"] == "fuzzy":
            reply += f" I drafted this to {resolution['confirmation_name']}. If you meant someone else, tell me before approval."
        if review["status"] == "rewritten":
            reply += " I tightened the wording so it stays inside what I can confirm from the current record."
        return reply
    else:
        err = result.get("error", "unknown error")
        if "denied" in err.lower():
            _log_correspondence_state(
                display_name,
                _SS_BLOCKED,
                "denied at approval gate",
                route="email_send",
                metadata={
                    "recipient_email": email_addr,
                    "subject": subject,
                    "mailbox_identity": "primary",
                },
            )
            return "That draft needed approval, and it was denied. No draft was created."
        if "scope" in err.lower() or "permission" in err.lower() or "insufficien" in err.lower():
            _log_correspondence_state(
                display_name,
                _SS_SEND_FAILED,
                err,
                route="email_send",
                metadata={
                    "recipient_email": email_addr,
                    "subject": subject,
                    "mailbox_identity": "primary",
                },
            )
            return (
                "Email draft creation failed — the Gmail token needs the compose scope. "
                "Run: python3 /home/openclaw/google_access_broker.py --auth"
            )
        _log_correspondence_state(
            display_name,
            _SS_SEND_FAILED,
            err,
            route="email_send",
            metadata={
                "recipient_email": email_addr,
                "subject": subject,
                "mailbox_identity": "primary",
            },
        )
        return f"That email draft didn't go through. {err}"


def _start_email_send_after_draft(
    *,
    recipient_name: str,
    recipient_email: str,
    subject: str,
    body: str,
    review_inbox: str,
    draft_id: str = "",
    draft_message_id: str = "",
    draft_thread_id: str = "",
    reply_thread_id: str = "",
    reply_in_reply_to: str = "",
    reply_references: str = "",
    approval_context: dict | None = None,
) -> None:
    thread = threading.Thread(
        target=_run_email_send_after_draft,
        kwargs={
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "review_inbox": review_inbox,
            "draft_id": draft_id,
            "draft_message_id": draft_message_id,
            "draft_thread_id": draft_thread_id,
            "reply_thread_id": reply_thread_id,
            "reply_in_reply_to": reply_in_reply_to,
            "reply_references": reply_references,
            "approval_context": approval_context,
        },
        daemon=True,
        name="cassandra-email-send",
    )
    thread.start()


def _notify_post_draft_send_outcome(
    *,
    recipient_name: str,
    subject: str,
    review_inbox: str,
    state: str,
    detail: str,
) -> None:
    if state not in {_SS_BLOCKED, _SS_SEND_FAILED}:
        return
    if state == _SS_BLOCKED:
        message = (
            f"The draft to {recipient_name} with subject \"{subject}\" was created, "
            f"but the send step was denied at approval. The draft still exists in "
            f"{review_inbox} for review."
        )
    else:
        message = (
            f"The draft to {recipient_name} with subject \"{subject}\" was created, "
            f"but the send step failed: {detail}. The draft still exists in "
            f"{review_inbox} for review."
        )
    try:
        from cassandra_sender import send_message

        send_message(message)
    except Exception as exc:
        print(f"[cassandra] post-draft send notify failed: {exc}", flush=True)


def _truncate_approval_preview(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _deterministic_send_synopsis(*, mode: str, recipient_name: str, subject: str, body: str) -> str:
    body_preview = _truncate_approval_preview(body, 110)
    if mode == "reply in thread":
        return (
            f"Reply in-thread to {recipient_name}"
            + (f' about "{subject}"' if subject else "")
            + (f" saying {body_preview}" if body_preview else ".")
        )
    return (
        f"New outbound email to {recipient_name}"
        + (f' about "{subject}"' if subject else "")
        + (f" saying {body_preview}" if body_preview else ".")
    )


def _build_send_approval_context(
    *,
    recipient_name: str,
    recipient_email: str,
    subject: str,
    body: str,
    review_inbox: str,
    reply_thread_id: str = "",
    inbound_summary: str = "",
) -> dict:
    mode = "reply in thread" if reply_thread_id else "new email"
    thread_synopsis = (
        _truncate_approval_preview(inbound_summary, 160)
        if inbound_summary
        else f"New outbound email to {recipient_name}; no prior thread context required."
    )
    return {
        "action_label": "send email",
        "mode": mode,
        "to": f"{recipient_name} <{recipient_email}>",
        "cc": review_inbox,
        "subject": subject,
        "thread_synopsis": thread_synopsis,
        "proposed_send": _truncate_approval_preview(
            _deterministic_send_synopsis(
                mode=mode,
                recipient_name=recipient_name,
                subject=subject,
                body=body,
            ),
            160,
        ),
        "draft_preview": _truncate_approval_preview(body, 220),
    }


def _run_email_send_after_draft(
    *,
    recipient_name: str,
    recipient_email: str,
    subject: str,
    body: str,
    review_inbox: str,
    draft_id: str = "",
    draft_message_id: str = "",
    draft_thread_id: str = "",
    reply_thread_id: str = "",
    reply_in_reply_to: str = "",
    reply_references: str = "",
    approval_context: dict | None = None,
) -> None:
    _log_correspondence_state(
        recipient_name,
        _SS_AWAITING_APPROVAL,
        "awaiting Guardian approval for send",
        route="email_send",
        metadata={
            "recipient_email": recipient_email,
            "subject": subject,
            "mailbox_identity": "primary",
            "draft_id": draft_id,
            "draft_message_id": draft_message_id,
            "draft_thread_id": draft_thread_id,
            "reply_thread_id": reply_thread_id,
        },
    )

    try:
        result = broker_call(
            "cassandra",
            "google.gmail.send",
            {
                "to": recipient_email,
                "cc": review_inbox,
                "subject": subject,
                "body": body,
                "thread_id": reply_thread_id,
                "in_reply_to": reply_in_reply_to,
                "references": reply_references,
                "approval_context": approval_context or _build_send_approval_context(
                    recipient_name=recipient_name,
                    recipient_email=recipient_email,
                    subject=subject,
                    body=body,
                    review_inbox=review_inbox,
                    reply_thread_id=reply_thread_id,
                ),
            },
        )
    except Exception as exc:
        _log_correspondence_state(
            recipient_name,
            _SS_SEND_FAILED,
            str(exc),
            route="email_send",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
                "draft_id": draft_id,
                "draft_message_id": draft_message_id,
                "draft_thread_id": draft_thread_id,
                "reply_thread_id": reply_thread_id,
            },
        )
        print(f"[cassandra] email send broker error: {exc}", flush=True)
        return

    if result.get("ok"):
        result_data = result.get("data") or {}
        detail = f"subject={subject}"
        message_id = str(result_data.get("message_id", ""))
        thread_id = str(result_data.get("thread_id", ""))
        if message_id:
            detail += f"; message_id={message_id}"
        if thread_id:
            detail += f"; thread_id={thread_id}"
        _log_correspondence_state(
            recipient_name,
            _SS_SENT_CONFIRMED,
            detail,
            route="email_send",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
                "draft_id": draft_id,
                "draft_message_id": draft_message_id,
                "draft_thread_id": draft_thread_id,
                "reply_thread_id": reply_thread_id,
                "message_id": message_id,
                "thread_id": thread_id,
            },
        )
        return

    err = str(result.get("error", "unknown error"))
    state = _SS_BLOCKED if "denied" in err.lower() else _SS_SEND_FAILED
    detail = "denied at approval gate" if state == _SS_BLOCKED else err
    _log_correspondence_state(
        recipient_name,
        state,
        detail,
        route="email_send",
        metadata={
            "recipient_email": recipient_email,
            "subject": subject,
            "mailbox_identity": "primary",
            "draft_id": draft_id,
            "draft_message_id": draft_message_id,
            "draft_thread_id": draft_thread_id,
            "reply_thread_id": reply_thread_id,
        },
    )
    _notify_post_draft_send_outcome(
        recipient_name=recipient_name,
        subject=subject,
        review_inbox=review_inbox,
        state=state,
        detail=detail,
    )


def _handle_outreach_email_request(text: str) -> str | None:
    if not _detect_outreach_email_intent(text):
        return None

    try:
        from cassandra_outreach import run_outreach
        results = run_outreach(dry_run=False, mode="draft")
    except Exception as e:
        print(f"[cassandra] outreach flow error: {e}", flush=True)
        _log_correspondence_state("outreach_batch", _SS_SEND_FAILED, str(e), route="outreach_email_draft")
        return "The intro email draft flow hit a problem. No drafts were created — I'll need to try again."

    drafted = [row.get("display_name", row["nickname"]) for row in results if row.get("status") == "draft"]
    failed = [row.get("display_name", row["nickname"]) for row in results if row.get("status") != "draft"]

    for name in drafted:
        _log_correspondence_state(name, _SS_DRAFT, route="outreach_email_draft")
    for name in failed:
        _log_correspondence_state(name, _SS_SEND_FAILED, route="outreach_email_draft")

    if drafted and not failed:
        return "Intro email drafts prepared for " + ", ".join(drafted) + "."
    if drafted and failed:
        return (
            "Drafted for "
            + ", ".join(drafted)
            + ". The rest didn't go through: "
            + ", ".join(failed)
            + "."
        )
    _log_correspondence_state("outreach_batch", _SS_SEND_FAILED, "no successful drafts", route="outreach_email_draft")
    return "The intro email drafts didn't go through. No drafts were created."


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


def _handle_calendar_delete(text: str) -> str | None:
    """
    Extract delete details from text and delete matching Google Calendar events via broker.
    Returns a reply string on success or clear failure, None if extraction failed.
    """
    details = _extract_calendar_delete_details(text)
    if details is None:
        return None

    title = details["title"]
    start_iso = f"{details['date']}T{details['start_time']}:00"
    max_matches = int(details.get("max_matches", 1))

    try:
        result = broker_call(
            "cassandra",
            "google.calendar.delete",
            {
                "title": title,
                "start_iso": start_iso,
                "max_matches": max_matches,
            },
        )
    except Exception as e:
        print(f"[cassandra] broker call error: {e}", flush=True)
        return "Couldn't reach the calendar broker. Try again in a moment."

    if result.get("ok"):
        from datetime import datetime
        start_dt_obj = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
        display_time = start_dt_obj.strftime("%A %B %-d at %-I:%M %p")
        deleted_count = int(result.get("data", {}).get("deleted_count", 0))
        event_word = "event" if deleted_count == 1 else "events"
        return f'Done. Removed {deleted_count} "{title}" {event_word} on {display_time}.'

    err = result.get("error", "unknown error")
    if "denied" in err.lower():
        return "Calendar delete was denied at the approval gate."
    if "no matching events found" in err.lower():
        return f'I could not find any "{title}" events on the calendar at that time.'
    return f"Couldn't delete the event: {err}"


# ── Inner-circle email reply bridge ──────────────────────────────────────────

def _extract_inner_circle_contact_filter(text: str) -> str | None:
    lowered = text.lower()
    for nickname, raw in _load_nicknames().items():
        if str(nickname).startswith("_"):
            continue
        entry = _normalize_contact_entry(nickname, raw)
        for candidate in {entry["nickname"], entry["display_name"], *entry["sender_names"]}:
            if not candidate:
                continue
            if re.search(rf"\b{re.escape(str(candidate).lower())}\b", lowered):
                return entry["nickname"]
    return None


def _analyze_inner_circle_email_thread(message: dict, verified_contact: dict) -> dict:
    from cassandra_contact_policy import classify_topic

    thread_messages, evidence_source = _fetch_email_thread_messages(message)
    contact_email = str(message.get("from_email", "")).strip().lower()
    thread_id = str(message.get("thread_id", ""))
    sorted_messages = sorted(
        thread_messages,
        key=lambda row: _parse_event_datetime(row.get("internal_date") or row.get("date_raw")),
    )
    reply_round = sum(
        1
        for row in sorted_messages
        if str(row.get("from_email", "")).strip().lower() == contact_email and _is_reply_like_email_message(row)
    ) or 1

    linked_outbound = _match_outbound_email_record(message, contact_email)
    trigger_message_text = ""
    question_map: dict[str, dict] = {}
    for thread_message in sorted_messages:
        if str(thread_message.get("from_email", "")).strip().lower() != contact_email:
            continue
        if str(thread_message.get("message_id", "")) == str(message.get("message_id", "")):
            trigger_message_text = str(thread_message.get("body_text") or thread_message.get("snippet") or "").strip()
        extracted = _extract_question_candidates(
            thread_message.get("body_text") or thread_message.get("snippet", "")
        )
        for candidate in extracted:
            key = _question_key(candidate)
            bundle = question_map.setdefault(
                key,
                {
                    "question": candidate,
                    "message_ids": [],
                    "evidence": [],
                    "last_asked_at": "",
                },
            )
            asked_at = _parse_event_datetime(thread_message.get("internal_date") or thread_message.get("date_raw"))
            bundle["message_ids"].append(str(thread_message.get("message_id", "")))
            bundle["last_asked_at"] = max(
                filter(None, [bundle.get("last_asked_at"), asked_at.isoformat(timespec="seconds")])
            )
            bundle["evidence"].append({
                "message_id": str(thread_message.get("message_id", "")),
                "quote": _bridge_preview(thread_message.get("body_text") or thread_message.get("snippet", ""), limit=220),
                "asked_at": asked_at.isoformat(timespec="seconds"),
            })

    question_bundles: list[dict] = []
    for index, bundle in enumerate(question_map.values(), start=1):
        lane = classify_topic(bundle["question"], verified_contact["nickname"])
        answered_in_thread = _bundle_answered_in_thread(bundle, sorted_messages, contact_email)
        capability_gaps: list[dict] = []
        queued_tasks: list[str] = []
        if answered_in_thread:
            status = "answered_in_thread"
        elif lane != "allowed":
            status = "needs_winship_review"
        else:
            capability_gaps = _detect_request_capability_gaps(bundle["question"])
            if capability_gaps:
                status = "needs_capability"
                for gap in capability_gaps:
                    task_name = _queue_inbound_email_gap_task(
                        gap,
                        question_text=bundle["question"],
                        contact_name=verified_contact["display_name"],
                        sender_email=contact_email,
                        subject=str(message.get("subject", "")),
                        thread_id=thread_id,
                        message_ids=bundle["message_ids"],
                    )
                    if task_name:
                        queued_tasks.append(task_name)
            else:
                status = "answer_now"
        question_bundles.append({
            "bundle_id": f"{thread_id or 'thread'}-q{index}",
            "question": bundle["question"],
            "lane": lane,
            "status": status,
            "message_ids": bundle["message_ids"],
            "last_asked_at": bundle["last_asked_at"],
            "evidence": bundle["evidence"],
            "capability_gaps": capability_gaps,
            "queued_task_names": queued_tasks,
        })

    predictions = _predict_likely_next_questions(question_bundles)
    unresolved = [bundle for bundle in question_bundles if bundle["status"] != "answered_in_thread"]
    cadence = _advance_email_thread_cadence(
        thread_id=thread_id or f"message:{message.get('message_id', '')}",
        contact_name=verified_contact["display_name"],
        unresolved_bundles=unresolved,
        predictions=predictions,
    )

    analysis = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mailbox_identity": "primary",
        "thread_id": thread_id,
        "message_id": str(message.get("message_id", "")),
        "reply_round": reply_round,
        "promotion_gate": "evaluated_reply_rounds",
        "contact_identity": {
            "nickname": verified_contact["nickname"],
            "display_name": verified_contact["display_name"],
            "sender_email": contact_email,
        },
        "linked_outbound": linked_outbound or {},
        "thread_evidence": {
            "subject": str(message.get("subject", "")),
            "message_count": len(sorted_messages),
            "evidence_source": evidence_source,
        },
        "message_evidence": _message_evidence_rows(sorted_messages, contact_email),
        "trigger_message_text": trigger_message_text,
        "question_bundles": question_bundles,
        "likely_next_questions": predictions,
        "cadence": cadence,
    }
    _log_email_thread_analysis(analysis)
    return analysis


def _handle_inner_circle_email_reply_bridge(text: str) -> str | None:
    if not _detect_inner_circle_email_reply_intent(text):
        return None

    try:
        call_fn = broker_call if broker_call is not None else __import__("google_access_broker").call
        result = call_fn("cassandra", "google.gmail.read.metadata", {"max_results": 20})
    except Exception as exc:
        print(f"[cassandra] email reply bridge broker error: {exc}", flush=True)
        return "I couldn't reach the inbox metadata bridge right now."

    if not result.get("ok"):
        return "I couldn't reach the inbox metadata bridge right now."

    from cassandra_contact_policy import classify_topic

    contact_filter = _extract_inner_circle_contact_filter(text)
    admitted = []
    for message in result.get("data") or []:
        if not _is_reply_like_email_message(message):
            continue

        sender_email = str(message.get("from_email", "")).strip().lower()
        verified = verify_sender_on_channel(
            sender_name=message.get("from_name"),
            sender_id=sender_email,
            channel="email",
        )
        if verified is None or verified.get("tier") != "inner_circle":
            continue
        if contact_filter and verified["nickname"] != contact_filter:
            continue

        lane = classify_topic(_build_email_bridge_review_text(message), verified["nickname"])
        status = {
            "allowed": "admitted",
            "caution": "held",
            "escalate": "escalated",
        }.get(lane, "held")
        preview = _bridge_preview(message.get("snippet", ""), limit=160)
        analysis = _analyze_inner_circle_email_thread(message, verified)
        admitted.append({
            "nickname": verified["nickname"],
            "display_name": verified["display_name"],
            "subject": str(message.get("subject", "")).strip() or "(no subject)",
            "preview": preview,
            "lane": lane,
            "status": status,
            "unread": "UNREAD" in (message.get("labels") or []),
            "analysis": analysis,
        })
        _log_email_bridge_event(
            message_id=str(message.get("message_id", "")),
            thread_id=str(message.get("thread_id", "")),
            nickname=verified["nickname"],
            contact_name=verified["display_name"],
            sender_email=sender_email,
            subject=str(message.get("subject", "")),
            preview=preview,
            lane=lane,
            status=status,
            unread="UNREAD" in (message.get("labels") or []),
        )

    if not admitted:
        if contact_filter:
            return "I didn't find any pinned email replies from that inner-circle contact in the recent inbox window."
        return "I didn't find any pinned inner-circle email replies in the recent inbox window."

    admitted.sort(key=lambda item: (not item["unread"], item["display_name"].lower()))
    lines = [
        f"I found {len(admitted)} pinned inner-circle email {'reply' if len(admitted) == 1 else 'replies'} in the recent inbox window."
    ]
    for item in admitted[:3]:
        status_bits = [f"{item['lane']} lane"]
        if item["unread"]:
            status_bits.append("unread")
        lines.append(f"{item['display_name']} — {', '.join(status_bits)}.")
        lines.append(f"Subject: {item['subject']}")
        if item["preview"]:
            lines.append(f"Preview: {item['preview']}")
        analysis = item.get("analysis") or {}
        linked_outbound = analysis.get("linked_outbound") or {}
        if linked_outbound:
            lines.append(
                "Linked thread: "
                f"{linked_outbound.get('state', 'draft')} via {linked_outbound.get('matched_via', 'unknown')} "
                f"({linked_outbound.get('source', 'log')})."
            )
        bundles = list(analysis.get("question_bundles") or [])
        if not bundles:
            lines.append("I didn't find a clean question bundle in the grounded thread content.")
        else:
            for bundle in bundles[:2]:
                if bundle["status"] == "answered_in_thread":
                    prefix = "Answered in thread"
                elif bundle["status"] == "needs_capability":
                    prefix = "Capability gap"
                elif bundle["status"] == "needs_winship_review":
                    prefix = "Needs Winship review"
                else:
                    prefix = "Can answer now"
                lines.append(f"{prefix}: {bundle['question']}")
                if bundle["status"] == "needs_capability":
                    capabilities = ", ".join(
                        gap["capability"] for gap in bundle.get("capability_gaps", [])
                    )
                    task_names = ", ".join(bundle.get("queued_task_names", []))
                    if capabilities:
                        lines.append(f"Gap type: {capabilities}")
                    if task_names:
                        lines.append(f"Queued task: {task_names}")
            predictions = list(analysis.get("likely_next_questions") or [])
            if predictions:
                lines.append(f"Likely next ask: {predictions[0]['question']}")
                lines.append(f"Why: {predictions[0]['because']}")
        cadence = analysis.get("cadence") or {}
        if cadence.get("user_update"):
            lines.append(cadence["user_update"])
        if item["lane"] == "caution":
            lines.append("I held that for Winship review.")
        elif item["lane"] == "escalate":
            lines.append("That needs Winship authorization before any reply.")
        else:
            lines.append("That one is safe to route through the normal draft-review flow.")
    if len(admitted) > 3:
        lines.append(f"There are {len(admitted) - 3} more pinned replies in the same recent window.")
    return "\n".join(lines)


def _compose_inner_circle_email_reply_body(
    message: dict,
    verified_contact: dict,
    analysis: dict,
) -> str | None:
    linked_outbound = analysis.get("linked_outbound") or {}
    if not linked_outbound:
        return None

    bundles = list(analysis.get("question_bundles") or [])
    unresolved = [bundle for bundle in bundles if bundle.get("status") != "answered_in_thread"]
    if any(bundle.get("status") != "answer_now" for bundle in unresolved):
        return None

    inbound_text = _extract_inbound_reply_text(message, analysis)
    if not inbound_text:
        return None

    relay_reply = _compose_relay_email_reply_body(
        inbound_text=inbound_text,
        sender_display_name=str(verified_contact.get("display_name") or "").strip(),
        sender_nickname=str(verified_contact.get("nickname") or "").strip(),
    )
    if relay_reply:
        return relay_reply

    prompt = _build_open_ended_inner_circle_reply_prompt(
        inbound_text=inbound_text,
        sender_display_name=str(verified_contact.get("display_name") or "").strip(),
    )
    draft_body = _call(
        prompt,
        task_class="cassandra_outbound_draft",
        cloud_ok=False,
        allow_deep_escalation=False,
    ).strip()
    if not draft_body:
        return None
    lines = [line.strip() for line in draft_body.splitlines() if line.strip()]
    if not lines:
        return None
    return "\n".join(lines[:2])


def _build_open_ended_inner_circle_reply_prompt(*, inbound_text: str, sender_display_name: str) -> str:
    return (
        "Draft a short plain-text email reply from Cassandra.\n"
        "This is the open-ended reply path, not the deterministic relay path.\n"
        "Rules:\n"
        "- Use only the grounded inbound email content below.\n"
        "- Keep it to one or two sentences.\n"
        "- Sound natural, warm, and context-aware rather than canned.\n"
        "- Acknowledge the actual content of the note.\n"
        "- Preserve who is speaking, who any sentiment is about, and which channel is mentioned.\n"
        "- Only mention Telegram if the sender explicitly asked for Telegram.\n"
        "- Do not turn an email-originated note into a Telegram-originated note.\n"
        "- Do not invent facts, capabilities, commitments, or extra context.\n"
        "- No greeting, no sign-off, no subject line.\n\n"
        f"Sender: {sender_display_name}\n"
        f"Inbound email: {inbound_text}\n\n"
        "Reply:"
    )


def _clean_inbound_email_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""

    cleaned_lines = []
    signature_markers = (
        "--",
        "sent from my iphone",
        "sent from my ipad",
        "get outlook for ios",
        "unsubscribe",
    )
    for line in raw.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        if stripped.startswith(">"):
            break
        if re.match(r"^on .+wrote:$", lowered):
            break
        if lowered.startswith("from:"):
            break
        if lowered in signature_markers:
            break
        cleaned_lines.append(stripped)

    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_inbound_reply_text(message: dict, analysis: dict | None = None) -> str:
    analysis = analysis or {}
    text = _clean_inbound_email_text(analysis.get("trigger_message_text") or "")
    if text:
        return text
    text = _clean_inbound_email_text(message.get("body_text") or "")
    if text:
        return text
    text = _clean_inbound_email_text(message.get("snippet") or "")
    if text:
        return text
    return str(message.get("subject") or "").strip()


def _sender_matches_relay_target(sender_display_name: str, sender_nickname: str, relay_target: str) -> bool:
    target = relay_target.strip().lower()
    if not target:
        return False
    sender_name = sender_display_name.strip().lower()
    sender_nick = sender_nickname.strip().lower()
    sender_terms = {
        token
        for token in re.split(r"[^a-z0-9]+", sender_name)
        if token
    }
    if sender_nick:
        sender_terms.add(sender_nick)
    target_terms = {
        token
        for token in re.split(r"[^a-z0-9]+", target)
        if token
    }
    if not target_terms:
        return False
    return bool(sender_terms & target_terms)


def _extract_relay_directive(inbound_text: str) -> dict | None:
    cleaned = re.sub(r"\s+", " ", str(inbound_text or "")).strip()
    if not cleaned:
        return None

    relay_match = re.search(
        r"\b(?:(?P<lemma>please\s+tell|tell|let)\s+(?P<target_a>[A-Za-z][A-Za-z .'-]{1,40}?)\s+(?:know\b)?|pass\s+along(?:\s+to\s+(?P<target_b>[A-Za-z][A-Za-z .'-]{1,40}?))?)\s*(?P<payload>.*?)(?:[.!?]|$)",
        cleaned,
        re.IGNORECASE,
    )
    if not relay_match:
        return None

    target = str(relay_match.group("target_a") or relay_match.group("target_b") or "").strip()
    lemma = str(relay_match.group("lemma") or "pass along").strip().lower()
    payload = str(relay_match.group("payload") or "").strip(" ,")
    if not target:
        return None
    lowered = cleaned.lower()
    destination_channel = "telegram" if re.search(r"\bon\s+telegram\b|\bvia\s+telegram\b", lowered) else ""

    encouraging_about_progress = bool(
        re.search(r"\b(pumped|glad|proud)\b", lowered)
        and re.search(r"\b(?:your|ur|the)\s+progress\b", lowered)
    )
    sender_claim = bool(
        re.search(r"\bi(?:'m| am)\b.*\b(pumped|glad|proud)\b", lowered)
        or re.search(r"\bhow\s+(pumped|glad|proud)\s+i(?:'m| am)\b", lowered)
        or re.search(r"\bi(?:'m| am)\s+the\s+one\s+who\s+is\s+(pumped|glad|proud)\b", lowered)
        or re.search(rf"\b{re.escape(target.lower())}\b.*\bis\s+(pumped|glad|proud)\b", lowered)
        or re.search(r"\bhe\s+is\s+(pumped|glad|proud)\b", lowered)
    )

    if encouraging_about_progress and sender_claim:
        return {
            "kind": "progress_encouragement",
            "target": target,
            "destination_channel": destination_channel,
            "payload": payload,
            "verb": lemma,
        }

    return None


def _relay_meaning_phrase(inbound_text: str, relay: dict) -> str:
    lowered = re.sub(r"\s+", " ", str(inbound_text or "")).strip().lower()
    payload = str(relay.get("payload") or "").strip().lower()
    scope = f"{lowered} {payload}".strip()

    if re.search(r"\bglad\b.*\b(?:your|the)\s+progress\s+is\s+real\b", scope):
        return "he's glad my progress is real"
    if re.search(r"\bproud\b.*\b(?:of\s+)?(?:your|the)\s+progress\b", scope):
        return "he's proud of my progress"
    if re.search(r"\bpumped\b", scope) and re.search(r"\b(?:your|the)\s+progress\b", scope):
        return "he's pumped about my progress"
    return "he's glad my progress is real"


def _compose_relay_email_reply_body(
    *,
    inbound_text: str,
    sender_display_name: str,
    sender_nickname: str,
) -> str | None:
    relay = _extract_relay_directive(inbound_text)
    if relay is None:
        return None
    if relay.get("kind") != "progress_encouragement":
        return None

    target = relay["target"]
    destination_channel = relay.get("destination_channel") or ""
    if not destination_channel and _sender_matches_relay_target(sender_display_name, sender_nickname, target):
        destination_channel = "telegram"
    channel_clause = " on Telegram" if destination_channel == "telegram" else ""
    meaning_phrase = _relay_meaning_phrase(inbound_text, relay)
    verb = str(relay.get("verb") or "").lower()
    if verb.startswith("pass along"):
        action_phrase = f"I'll pass that along to {target}{channel_clause}"
    elif "tell" in verb:
        action_phrase = f"I'll tell {target}{channel_clause}"
    else:
        action_phrase = f"I'll let {target} know{channel_clause}"
    return (
        "Thanks for saying that — it means a lot. "
        f"{action_phrase} that {meaning_phrase}."
    )


def _build_inbound_reply_grounded_summary(
    *,
    inbound_text: str,
    sender_display_name: str,
    sender_nickname: str,
) -> str | None:
    relay = _extract_relay_directive(inbound_text)
    if relay is None:
        return None
    if relay.get("kind") != "progress_encouragement":
        return None

    target = relay["target"]
    destination_channel = relay.get("destination_channel") or ""
    if not destination_channel and _sender_matches_relay_target(sender_display_name, sender_nickname, target):
        destination_channel = "telegram"
    channel_clause = " on Telegram" if destination_channel == "telegram" else ""
    meaning_phrase = _relay_meaning_phrase(inbound_text, relay)
    return f"Grounded meaning: {target} said by email that {meaning_phrase}, and I should let {target} know{channel_clause}."


def _build_inbound_reply_operator_update(
    *,
    inbound_text: str,
    sender_display_name: str,
    sender_nickname: str,
) -> str | None:
    relay = _extract_relay_directive(inbound_text)
    if relay is None:
        return None
    if relay.get("kind") != "progress_encouragement":
        return None

    target = relay["target"]
    meaning_phrase = _relay_meaning_phrase(inbound_text, relay)
    return f"{target} says {meaning_phrase}."


def _try_acquire_inbound_email_reply_lock():
    try:
        handle = _INBOUND_EMAIL_REPLY_LOCK.open("w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except BlockingIOError:
        return None
    except Exception as exc:
        print(f"[cassandra] inbound email reply lock failed: {exc}", flush=True)
        return None


def _release_inbound_email_reply_lock(handle) -> None:
    if handle is None:
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def _create_inner_circle_email_reply_draft(
    *,
    message: dict,
    verified_contact: dict,
    analysis: dict,
    draft_body: str,
    ops_packet: BusinessOpsPacket | None = None,
) -> dict:
    # Check for email draft permission if ops_packet is provided
    if ops_packet:
        has_draft_cap = any(c.name == "email_draft" for c in ops_packet.permitted_capabilities)
        if not has_draft_cap:
            return {"ok": False, "error": "email_draft capability missing from ops_packet"}

    subject = str(message.get("subject", "")).strip() or "Follow-up"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    recipient_email = str(verified_contact.get("pinned_email") or message.get("from_email") or "").strip().lower()
    recipient_name = str(verified_contact.get("display_name") or recipient_email or "contact").strip()
    if not recipient_email:
        return {"ok": False, "error": "recipient email missing"}

    inbound_reply_text = _extract_inbound_reply_text(message, analysis)

    review = _review_grounded_email_draft(
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        original_message=inbound_reply_text,
        draft_subject=subject,
        draft_body=draft_body,
    )
    if review["status"] == "blocked":
        _log_correspondence_state(
            recipient_name,
            _SS_BLOCKED,
            review["detail"],
            route="inner_circle_email_reply",
            metadata={
                "recipient_email": recipient_email,
                "subject": subject,
                "mailbox_identity": "primary",
                "source_message_id": str(message.get("message_id", "")),
                "source_thread_id": str(message.get("thread_id", "")),
            },
        )
        return {"ok": False, "error": review["user_reply"] or review["detail"]}

    from cassandra_outreach import create_gmail_draft

    review_inbox = get_review_inbox()
    draft_result = create_gmail_draft(
        recipient_email,
        review["subject"],
        review["body"],
        review_inbox,
        review["status"],
        review.get("detail", ""),
        thread_id=str(message.get("thread_id", "")).strip(),
        in_reply_to=str(message.get("in_reply_to", "")).strip(),
        references=str(message.get("references", "")).strip(),
    )
    if not draft_result["ok"]:
        err = str(draft_result["error"])
        _log_correspondence_state(
            recipient_name,
            _SS_SEND_FAILED,
            err,
            route="inner_circle_email_reply",
            metadata={
                "recipient_email": recipient_email,
                "subject": review["subject"],
                "mailbox_identity": "primary",
                "source_message_id": str(message.get("message_id", "")),
                "source_thread_id": str(message.get("thread_id", "")),
            },
        )
        return {"ok": False, "error": err}

    result = draft_result["result"]
    if not result.get("ok"):
        err = str(result.get("error", "unknown error"))
        state = _SS_BLOCKED if "denied" in err.lower() else _SS_SEND_FAILED
        detail = "denied at approval gate" if state == _SS_BLOCKED else err
        _log_correspondence_state(
            recipient_name,
            state,
            detail,
            route="inner_circle_email_reply",
            metadata={
                "recipient_email": recipient_email,
                "subject": review["subject"],
                "mailbox_identity": "primary",
                "source_message_id": str(message.get("message_id", "")),
                "source_thread_id": str(message.get("thread_id", "")),
            },
        )
        return {"ok": False, "error": detail}

    result_data = result.get("data") or {}
    detail = f"subject={review['subject']}"
    draft_id = str(result_data.get("draft_id", "")).strip()
    if draft_id:
        detail += f"; draft_id={draft_id}"
    _log_correspondence_state(
        recipient_name,
        _SS_DRAFT,
        detail,
        route="inner_circle_email_reply",
        metadata={
            "recipient_email": recipient_email,
            "subject": review["subject"],
            "mailbox_identity": "primary",
            "draft_id": draft_id,
            "message_id": result_data.get("message_id", ""),
            "thread_id": result_data.get("thread_id", ""),
            "source_message_id": str(message.get("message_id", "")),
            "source_thread_id": str(message.get("thread_id", "")),
        },
    )
    _start_email_send_after_draft(
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        subject=review["subject"],
        body=review["body"],
        review_inbox=review_inbox,
        draft_id=draft_id,
        draft_message_id=str(result_data.get("message_id", "")),
        draft_thread_id=str(result_data.get("thread_id", "")),
        reply_thread_id=str(message.get("thread_id", "")).strip(),
        reply_in_reply_to=str(message.get("in_reply_to", "")).strip(),
        reply_references=str(message.get("references", "")).strip(),
        approval_context=_build_send_approval_context(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            subject=review["subject"],
            body=review["body"],
            review_inbox=review_inbox,
            reply_thread_id=str(message.get("thread_id", "")).strip(),
            inbound_summary=(
                f"Latest inbound email from {recipient_name}: "
                f"{_truncate_approval_preview(inbound_reply_text, 120)}"
            ),
        ),
    )
    return {
        "ok": True,
        "subject": review["subject"],
        "body": review["body"],
        "draft_id": draft_id,
        "thread_id": str(result_data.get("thread_id", "")),
    }


def process_inbound_email_replies() -> list[dict]:
    lock_handle = _try_acquire_inbound_email_reply_lock()
    if lock_handle is None:
        return []

    # Business Ops Spine integration (Background Monitored Conversation)
    ops_packet = assemble_business_ops_packet(
        query="monitored_email_conversation",
        actor_name="cassandra"
    )

    try:
        # Check for Gmail metadata read permission in the packet
        has_read_cap = any(c.name == "gmail_metadata" for c in ops_packet.permitted_capabilities)
        if not has_read_cap:
            print("[cassandra] inbound email reply poll denied: gmail_metadata capability missing from ops_packet", flush=True)
            _release_inbound_email_reply_lock(lock_handle)
            return []

        call_fn = broker_call if broker_call is not None else __import__("google_access_broker").call
        result = call_fn("cassandra", "google.gmail.read.metadata", {"max_results": 20})
    except Exception as exc:
        print(f"[cassandra] inbound email reply poll failed: {exc}", flush=True)
        _release_inbound_email_reply_lock(lock_handle)
        return []

    if not result.get("ok"):
        _release_inbound_email_reply_lock(lock_handle)
        return []

    from cassandra_contact_policy import classify_topic
    from cassandra_sender import send_message as send_telegram

    try:
        processed: list[dict] = []
        for message in result.get("data") or []:
            message_id = str(message.get("message_id", "")).strip()
            if not message_id or _email_bridge_message_seen(message_id):
                continue
            if not _is_reply_like_email_message(message):
                continue

            sender_email = str(message.get("from_email", "")).strip().lower()
            verified = verify_sender_on_channel(
                sender_name=message.get("from_name"),
                sender_id=sender_email,
                channel="email",
            )
            if verified is None or verified.get("tier") != "inner_circle":
                continue

            lane = classify_topic(_build_email_bridge_review_text(message), verified["nickname"])
            status = {
                "allowed": "admitted",
                "caution": "held",
                "escalate": "escalated",
            }.get(lane, "held")
            preview = _bridge_preview(message.get("snippet", ""), limit=220)
            analysis = _analyze_inner_circle_email_thread(message, verified)
            _log_email_bridge_event(
                message_id=message_id,
                thread_id=str(message.get("thread_id", "")),
                nickname=verified["nickname"],
                contact_name=verified["display_name"],
                sender_email=sender_email,
                subject=str(message.get("subject", "")),
                preview=preview,
                lane=lane,
                status=status,
                unread="UNREAD" in (message.get("labels") or []),
            )

            inbound_text = _extract_inbound_reply_text(message, analysis)
            operator_update = _build_inbound_reply_operator_update(
                inbound_text=inbound_text,
                sender_display_name=str(verified.get("display_name") or ""),
                sender_nickname=str(verified.get("nickname") or ""),
            )
            if operator_update:
                lines = [operator_update]
            else:
                lines = [
                    f"{verified['display_name']} replied by email.",
                    f"Subject: {str(message.get('subject', '')).strip() or '(no subject)'}",
                ]
                if preview:
                    lines.append(f"Message: {preview}")
            grounded_summary = _build_inbound_reply_grounded_summary(
                inbound_text=inbound_text,
                sender_display_name=str(verified.get("display_name") or ""),
                sender_nickname=str(verified.get("nickname") or ""),
            )
            if grounded_summary and not operator_update:
                lines.append(grounded_summary)

            linked_outbound = analysis.get("linked_outbound") or {}
            if lane != "allowed":
                lines.append("I held the reply for review before drafting anything.")
                send_telegram("\n".join(lines))
                processed.append({"message_id": message_id, "status": status, "drafted": False})
                continue

            if not linked_outbound:
                lines.append("I saw it, but I didn't auto-reply because it isn't linked to a Cassandra-started thread yet.")
                send_telegram("\n".join(lines))
                processed.append({"message_id": message_id, "status": "unlinked", "drafted": False})
                continue

            draft_body = _compose_inner_circle_email_reply_body(message, verified, analysis)
            if not draft_body:
                lines.append("I saw it, but I didn't auto-reply because the grounded reply path wasn't clear enough.")
                send_telegram("\n".join(lines))
                processed.append({"message_id": message_id, "status": "no_draft_path", "drafted": False})
                continue

            draft_result = _create_inner_circle_email_reply_draft(
                message=message,
                verified_contact=verified,
                analysis=analysis,
                draft_body=draft_body,
                ops_packet=ops_packet,
            )
            if draft_result.get("ok"):
                if operator_update:
                    lines.append("Guardian approval is on the way for the send step.")
                else:
                    lines.append("Guardian approval is on the way for the send step.")
                send_telegram("\n".join(lines))
                processed.append({"message_id": message_id, "status": "drafted", "drafted": True})
                continue

            lines.append(f"I saw it, but I couldn't draft the reply cleanly: {draft_result.get('error', 'unknown error')}")
            send_telegram("\n".join(lines))
            processed.append({"message_id": message_id, "status": "draft_failed", "drafted": False})

        return processed
    finally:
        _release_inbound_email_reply_lock(lock_handle)


# ── Gmail intent gate ─────────────────────────────────────────────────────────

class GmailIntentDecision:
    def __init__(self, allowed: bool, reason: str, category: str = "none", trigger: str | None = None):
        self.allowed = allowed
        self.reason = reason
        self.category = category
        self.trigger = trigger

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "category": self.category,
            "trigger": self.trigger,
        }


def decide_gmail_intent(query: str, *, scheduled_triage: bool = False) -> GmailIntentDecision:
    """
    Deterministic gate for Gmail API access.
    Default-deny unless explicit email or business objects are present.
    """
    if scheduled_triage:
        return GmailIntentDecision(True, "Scheduled email triage explicitly running.", "scheduled_triage")

    q = (query or "").lower().strip()

    # Explicit user denial
    if any(phrase in q for phrase in ("no gmail", "no email", "no tools", "without gmail", "without email")):
        return GmailIntentDecision(False, "User explicitly requested no Gmail/tools.", "none")

    # Explicit email terms: allowed
    email_terms = (
        "email", "gmail", "inbox", "message", "unread", "sender",
        "subject", "from", "reply", "draft", "thread", "attachment"
    )
    for term in email_terms:
        if term in q:
            return GmailIntentDecision(True, f"Explicit email term trigger: '{term}'", "email_search", term)

    # Materially specific business/payment terms: allowed
    business_terms = (
        "invoice", "payment", "paid", "unpaid", "receivable",
        "owes", "owed", "client follow-up", "balance", "overdue"
    )
    for term in business_terms:
        if term in q:
            return GmailIntentDecision(True, f"Material business term trigger: '{term}'", "payment_verify", term)

    # Do not allow generic verbs alone: check, verify, status, health, look, find, search.
    # These are already implicitly denied by falling through, but we could be explicit if needed.

    return GmailIntentDecision(False, "No explicit email or business intent detected; defaulting to deny.", "none")


# ── Gmail context injection ───────────────────────────────────────────────────

_GMAIL_QUERY_WORDS = (
    "email", "emails", "inbox", "unread", "new message",
    "any messages", "check my email", "did anyone email",
    "did i get an email", "did i get any email", "gmail",
)


def _fetch_gmail_context(query: str, decision: GmailIntentDecision | None = None, ops_packet: Any = None) -> str:
    """
    If the query has Gmail intent, call the broker and return a formatted
    inbox context block for prompt injection.
    Returns "" if not applicable, broker denied, or an error occurs.
    """
    # Use formal ops_packet if provided; fallback to gmail_decision
    if ops_packet is not None:
        has_email_cap = any(c.domain == "email" for c in ops_packet.permitted_capabilities)
        if not has_email_cap:
            return ""
    elif decision and not decision.allowed:
        return ""

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


def _fetch_contacts_context(query: str, ops_packet: Any = None) -> str:
    """
    If the query has contacts intent, search Google Contacts via the broker
    and return a formatted block for prompt injection.
    Returns "" if not applicable, broker denied, or an error occurs.
    """
    # Use formal ops_packet if provided
    if ops_packet is not None:
        has_contacts_cap = any(c.domain == "contacts" for c in ops_packet.permitted_capabilities)
        if not has_contacts_cap:
            return ""

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


# ── Payment verification context injection ───────────────────────────────────

_PAY_VERIFY_QUERY_WORDS = (
    "payment", "deposit", "invoice", "cleared", "posted",
    "arrived", "came in", "paid", "payment status", "come through",
    "hilton", "zelle", "venmo", "square", "check", "funds", "hit the account",
    "did it land", "did we get", "owes", "owed", "receivable", "balance", "overdue"
)

_PAY_VERIFY_VERBS = (
    "did", "verify", "check", "confirm", "has", "status", "any", "search",
    "see the", "find the", "land", "arrived", "come through", "owes", "owed"
)

_PAYMENT_VERIFY_RESCUE_MARKERS = (
    "can't verify deposit or payment status",
    "payment status isn't something i can check externally",
    "external payment data isn't accessible",
    "the payment follow-ups log",
    "follow-ups log shows what was recorded",
    "the account is the source of truth",
    "the account is the only way to confirm clearance",
    "file or path existence",
    "path existence isn't something i can confirm",
    "can't verify that path",
)


def _looks_like_payment_verify_query(text: str) -> bool:
    t = (text or "").lower()
    # Explicitly exclude general email checks from being treated as payment verification
    # even if "check" is present.
    if "email" in t and "check" in t:
        # If "payment", "paid", "invoice" etc are NOT present, it's likely just email.
        business_markers = ("payment", "paid", "invoice", "deposit", "hilton", "zelle", "venmo", "owes", "owed")
        if not any(bm in t for bm in business_markers):
            return False

    if not any(w in t for w in _PAY_VERIFY_QUERY_WORDS):
        return False
    return any(v in t for v in _PAY_VERIFY_VERBS)


def _needs_payment_verify_rescue(query: str, reply: str) -> bool:
    if not _looks_like_payment_verify_query(query):
        return False
    t = (reply or "").lower()
    return any(marker in t for marker in _PAYMENT_VERIFY_RESCUE_MARKERS)


def _rescue_payment_verify_reply(query: str, reply: str) -> str | None:
    if not _needs_payment_verify_rescue(query, reply):
        return None
    rescued = _handle_payment_verification_request(query)
    if rescued is not None:
        return rescued
    return "I can't confirm the current payment status from the live record I have."


def _fetch_payment_verify_context(query: str, decision: GmailIntentDecision | None = None, ops_packet: Any = None) -> str:
    """
    If the query has payment verification intent, search Gmail metadata for
    recent payment notifications (Zelle, Venmo, Hilton, etc.) and return
    a formatted block for prompt injection.
    """
    # Use formal ops_packet if provided
    if ops_packet is not None:
        has_pay_cap = any(c.domain == "payment" for c in ops_packet.permitted_capabilities)
        if not has_pay_cap:
            return ""
    elif decision and not decision.allowed:
        return ""

    q_low = query.lower()
    # Trust the decision gate category if it already identified payment_verify intent
    if not _looks_like_payment_verify_query(q_low) and not (decision and decision.category == "payment_verify"):
        return ""

    try:
        from google_access_broker import call as broker_call
        # Search last 20 inbox messages for payment signals
        result = broker_call("cassandra", "google.gmail.read.metadata", {"max_results": 20})
        if not result["ok"]:
            return "[VERIFIED PAYMENT DATA — Gmail unreachable]"

        messages = result.get("data") or []
        entity_terms = _reality_entity_terms(query)
        # Keywords for payment notifications (subjects/snippets)
        pay_signals = (
            "payment", "deposit", "received", "zelle", "venmo", "square",
            "paypal", "check", "hilton", "credit", "posted", "cleared",
            "arrived", "landed", "sent you"
        )

        matches = []
        for m in messages:
            subj = m.get("subject", "").lower()
            snip = m.get("snippet", "").lower()
            from_name = m.get("from_name", "").lower()
            haystack = " ".join(part for part in (subj, snip, from_name) if part)
            if entity_terms and not any(term in haystack for term in entity_terms):
                continue
            if any(s in subj or s in snip for s in pay_signals):
                matches.append(m)

        if not matches:
            return "[VERIFIED PAYMENT DATA — no recent Gmail notifications found]"

        lines = ["[VERIFIED GMAIL NOTIFICATIONS — recent payment-related emails]"]
        for m in matches[:5]:
            from_name = m.get("from_name", "Unknown")
            subject   = m.get("subject", "(no subject)")
            snippet   = m.get("snippet", "(no snippet)")
            # Clean snippet for voice-readability (no markdown, no dashes)
            snippet = snippet.replace("*", "").replace("-", " ").replace("#", "").strip()
            date_raw  = m.get("date_raw", "")
            lines.append(f"  From: {from_name}")
            lines.append(f"  Subject: {subject}")
            lines.append(f"  Snippet: {snippet}")
            lines.append(f"  Date: {date_raw[:16]}")
            lines.append("")

        return "\n".join(lines).strip()
    except Exception:
        return "[VERIFIED PAYMENT DATA — error during Gmail fetch]"


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
    finance_ctx: str,
    payment_verify_ctx: str,
    reality_ctx: str,
    context_snapshot: str,
    query: str,
) -> bool:
    """Return True only when no sensitive data source is present in the assembled
    Cassandra context for this turn.

    Block conditions:
    1. Calendar broker was called (event titles, times, locations)
    2. Gmail broker was called (sender names, subject lines)
    3. Payment verification Gmail metadata present (snippets, subjects)
    4. Payment follow-ups present — UNCONDITIONAL. Live content contains client
       names (e.g. "Capital Hilton") and financial status. Always sensitive.
    5. Pending actions present AND actions text contains sensitive patterns.
       Audited 2026-03-21: current live content is raw user meta-queries with
       no client names or financial figures. Block only on content, not presence.
    6. Query contains financial/payment/credential keywords.
    """
    # Blocks 1–3: any live data fetch contaminates the context
    if calendar_ctx:
        return False
    if gmail_ctx:
        return False
    if contacts_ctx:
        return False
    if finance_ctx:
        return False
    if payment_verify_ctx:
        return False
    if reality_ctx:
        return False

    # Block 4: payment follow-ups — always block regardless of content.
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

    policy = external_model_packet_policy(
        {"query": query, "context_snapshot": context_snapshot},
        metadata={"workload": "cassandra_user_reply"},
    )
    return bool(policy.get("external_model_safe"))


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call(
    prompt: str,
    *,
    task_class: str,
    cloud_ok: bool = False,
    allow_deep_escalation: bool = False,
    validation_outcome: str | None = None,
    external_model_metadata: dict | None = None,
) -> str:
    # Cloud path: only when _cassandra_context_clean() confirmed clean context
    if cloud_ok:
        policy_metadata = {"workload": task_class, "cloud_ok": True}
        if external_model_metadata:
            policy_metadata.update(external_model_metadata)
        policy = external_model_packet_policy(prompt, metadata=policy_metadata)
        if policy.get("external_model_safe"):
            result = external_language_model_call(
                prompt,
                metadata=policy_metadata,
                timeout=30,
            ).strip()
            if result:
                print("[cassandra] reply routed to external language model", flush=True)
                return result
            print("[cassandra] cloud call failed or empty, falling back to local", flush=True)
        else:
            print(
                f"[cassandra] central external-model policy blocked cloud routing: {policy.get('reason')}",
                flush=True,
            )

    model, lane = resolve_local_model(prompt, task_class=task_class)
    _log_model_route(
        task_class=task_class,
        preferred_lane=lane,
        chosen_lane=lane,
        reason=f"policy route via shared local router for {task_class}",
        escalation=False,
        validation_outcome=validation_outcome,
        model=model,
    )
    result = ollama_call(prompt, timeout=90 if lane == "deep" else 60, model=model)
    if result or not allow_deep_escalation:
        return result

    if task_class == "cassandra_user_reply_fast":
        strong_model, strong_lane = resolve_local_model(prompt, task_class="cassandra_user_reply")
        _log_model_route(
            task_class=task_class,
            preferred_lane=lane,
            chosen_lane=strong_lane,
            reason="explicit escalation from small conversational lane to gemma strong after empty response",
            escalation=True,
            validation_outcome="empty_response",
            model=strong_model,
        )
        print(f"[cassandra] escalating {task_class} from {lane} to {strong_lane}", flush=True)
        return ollama_call(prompt, timeout=60, model=strong_model)

    if task_class == "cassandra_user_reply":
        return result

    if lane != "strong":
        return result

    deep_model, deep_lane = resolve_local_model(prompt, lane="deep", task_class=task_class)
    _log_model_route(
        task_class=task_class,
        preferred_lane=lane,
        chosen_lane=deep_lane,
        reason="explicit escalation after strong-lane empty response",
        escalation=True,
        validation_outcome="empty_response",
        model=deep_model,
    )
    print(f"[cassandra] escalating {task_class} from {lane} to {deep_lane}", flush=True)
    result = ollama_call(prompt, timeout=90, model=deep_model)
    return result


def _call_hidden_extract_classify_json(prompt: str, *, validation_label: str) -> dict | None:
    model, lane = resolve_local_model(prompt, task_class="cassandra_extract_classify")
    _log_model_route(
        task_class="cassandra_extract_classify",
        preferred_lane=lane,
        chosen_lane=lane,
        reason=f"policy route via shared local router for {validation_label}",
        escalation=False,
        validation_outcome=None,
        model=model,
    )
    raw = ollama_call(prompt, timeout=20, model=model)
    if not raw:
        _log_model_route(
            task_class="cassandra_extract_classify",
            preferred_lane=lane,
            chosen_lane=lane,
            reason=f"local extract/classify empty for {validation_label}",
            escalation=False,
            validation_outcome="empty_response",
            model=model,
        )
        return None

    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)

    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            _log_model_route(
                task_class="cassandra_extract_classify",
                preferred_lane=lane,
                chosen_lane=lane,
                reason=f"local extract/classify parse failed for {validation_label}",
                escalation=False,
                validation_outcome="parse_failed",
                model=model,
            )
            return None
        try:
            parsed = json.loads(match.group(1))
        except Exception:
            _log_model_route(
                task_class="cassandra_extract_classify",
                preferred_lane=lane,
                chosen_lane=lane,
                reason=f"local extract/classify parse failed for {validation_label}",
                escalation=False,
                validation_outcome="parse_failed",
                model=model,
            )
            return None

    if not isinstance(parsed, dict):
        _log_model_route(
            task_class="cassandra_extract_classify",
            preferred_lane=lane,
            chosen_lane=lane,
            reason=f"local extract/classify returned non-dict for {validation_label}",
            escalation=False,
            validation_outcome="shape_invalid",
            model=model,
        )
        return None

    _log_model_route(
        task_class="cassandra_extract_classify",
        preferred_lane=lane,
        chosen_lane=lane,
        reason=f"local extract/classify succeeded for {validation_label}",
        escalation=False,
        validation_outcome="ok",
        model=model,
    )
    return parsed


# ── Main handler ──────────────────────────────────────────────────────────────

def handle(text: str, session: dict | None = None) -> list[str]:
    session_meta = dict(session or {})
    # --- Explicit Gmail inbox queries: force live Gmail read, bypass LLM and context blending ---
    inbox_list_patterns = [
        "any new emails", "list my 5 newest unread inbox emails with sender and subject only",
        "list my 5 newest unread emails", "show my 5 newest unread emails", "show unread inbox emails",
        "show unread emails", "list unread emails", "list unread inbox emails"
    ]
    query = _strip_prefix(text)
    t_query = query.lower().strip()

    # Deterministic Intent (Business Ops Spine Step 2)
    ops_intent = classify_business_ops_intent(query)
    system_knowledge_query = _is_system_knowledge_registry_query(query)
    reynolds_setup_query = is_reynolds_gig_setup_query(query)

    # Formalize the Context/Capability Packet (Business Ops Spine Step 3)
    ops_packet = assemble_business_ops_packet(
        query=query,
        actor_name="cassandra",
        intent=ops_intent
    )

    # Record the event and packet receipt in the SQLite Ledger (Business Ops Spine Step 7)
    # Skip ledger write for deterministic status/self-knowledge inquiries to preserve pure read-only behavior.
    if ops_intent.intent_name == "ops_status" or system_knowledge_query or reynolds_setup_query:
        event_id = None
    else:
        event_id = record_cassandra_packet_event(query, ops_packet)

    # Legacy gmail_decision for backward compatibility in this handler
    gmail_decision = decide_gmail_intent(query)

    # Always initialize state for logging and saving
    state = load_state()
    explicit_finance_status_query = detect_finance_status_intent(query) and any(
        marker in query.lower()
        for marker in (
            "status",
            "where are we",
            "where do we stand",
            "what is current",
            "what's current",
            "current truth",
            "current state",
            "latest",
            "update",
        )
    )
    operator_intake_candidate = (
        str(session_meta.get("source_user_label") or "operator") == "operator"
        and not explicit_finance_status_query
        and _is_universal_operator_intake_candidate(query)
    )

    date_awareness_reply = answer_date_awareness_query(query)
    if date_awareness_reply is not None:
        save_state(state)
        _log_conversation(text, [date_awareness_reply], route="date_awareness", metadata={"event_id": event_id})
        return [date_awareness_reply]

    if system_knowledge_query:
        answer_kwargs: dict[str, Any] = {}
        if session_meta.get("system_knowledge_repo_root"):
            answer_kwargs["repo_root"] = session_meta["system_knowledge_repo_root"]
        if session_meta.get("system_knowledge_ledger_path"):
            answer_kwargs["ledger_path"] = session_meta["system_knowledge_ledger_path"]
        if session_meta.get("system_knowledge_atlas_path"):
            answer_kwargs["atlas_path"] = session_meta["system_knowledge_atlas_path"]
        answer = _query_system_knowledge_registry(query, **answer_kwargs)
        reply = [_format_system_knowledge_answer(answer)]
        save_state(state)
        _log_conversation(
            text,
            reply,
            route="system_knowledge_registry_query",
            metadata={
                "event_id": event_id,
                "ops_packet": ops_packet.to_dict(),
                "answer_type": answer.get("answer_type"),
                "model_called": False,
                "external_calls_performed": False,
                "runtime_mutation_performed": False,
                "business_action_performed": False,
            },
        )
        return reply

    if not operator_intake_candidate:
        capital_hilton_agency_reply = format_capital_hilton_agency_answer(query)
        if capital_hilton_agency_reply is not None:
            reply = [capital_hilton_agency_reply]
            save_state(state)
            _log_conversation(
                text,
                reply,
                route="capital_hilton_agency_status",
                metadata={
                    "event_id": event_id,
                    "ops_packet": ops_packet.to_dict(),
                    "model_called": False,
                    "external_calls_performed": False,
                    "runtime_mutation_performed": False,
                    "money_or_ledger_mutation_performed": False,
                },
            )
            return reply

        capital_hilton_openclaw_status_reply = format_capital_hilton_openclaw_status_answer(query)
        if capital_hilton_openclaw_status_reply is not None:
            reply = [capital_hilton_openclaw_status_reply]
            save_state(state)
            _log_conversation(
                text,
                reply,
                route="capital_hilton_openclaw_status",
                metadata={
                    "event_id": event_id,
                    "ops_packet": ops_packet.to_dict(),
                    "model_called": False,
                    "external_calls_performed": False,
                    "runtime_mutation_performed": False,
                    "money_or_ledger_mutation_performed": False,
                },
            )
            return reply

    reynolds_gig_setup_reply = format_reynolds_gig_setup_answer(query)
    if reynolds_gig_setup_reply is not None:
        reply = [reynolds_gig_setup_reply]
        save_state(state)
        _log_conversation(
            text,
            reply,
            route="reynolds_gig_setup_status",
            metadata={
                "event_id": event_id,
                "ops_packet": ops_packet.to_dict(),
                "model_called": False,
                "external_calls_performed": False,
                "runtime_mutation_performed": False,
                "calendar_or_contact_mutation_performed": False,
                "invoice_send_performed": False,
                "money_or_ledger_mutation_performed": False,
            },
        )
        return reply

    objective_result = _handle_operator_objective(
        query,
        source_channel="telegram",
        source_message_ref=str(session_meta.get("source_message_id") or session_meta.get("message_id") or ""),
        lane_context={
            "target_world_ref": "operator_comms",
            "target_thread_ref": "cassandra",
            "source_channel": "telegram",
        },
    )
    if objective_result is not None:
        reply = [str(objective_result["operator_reply"])]
        save_state(state)
        _log_conversation(
            text,
            reply,
            route="cassandra_operator_objective",
            metadata={
                "event_id": event_id,
                "objective_id": objective_result["objective"]["objective_id"],
                "gmail_lookup_performed": False,
                "email_send_performed": False,
            },
        )
        return reply

    if _detect_send_authority_prepared_status_echo(query):
        reply = [_handle_send_authority_prepared_status_echo(query)]
        save_state(state)
        _log_conversation(
            text,
            reply,
            route="cassandra_operator_objective_status_echo",
            metadata={
                "event_id": event_id,
                "gmail_lookup_performed": False,
                "email_send_performed": False,
                "gmail_draft_created": False,
            },
        )
        return reply

    # Check for email capability in the packet
    has_email_cap = any(c.domain == "email" for c in ops_packet.permitted_capabilities)

    if has_email_cap and (t_query in (p.lower() for p in inbox_list_patterns) or (
        t_query.startswith("list my ") and "unread inbox" in t_query and "sender" in t_query and "subject" in t_query
    )):
        try:
            from cassandra_outreach import poll_gmail_unread_count, poll_gmail_recent_metadata
            # Use direct unread count for count queries
            if (
                "count" in t_query or
                "any new emails" in t_query or
                t_query.startswith("any new email") or
                t_query.startswith("show unread") or
                t_query.startswith("list unread")
            ):
                count_result = poll_gmail_unread_count()
                if not count_result["ok"]:
                    reply = ["[GMAIL] Inbox is empty or unreachable."]
                else:
                    reply = [f"You have {count_result['data']} unread inbox emails."]
            else:
                result = poll_gmail_recent_metadata(10)
                if not result["ok"]:
                    reply = ["[GMAIL] Inbox is empty or unreachable."]
                else:
                    messages = result.get("data") or []
                    unread = [m for m in messages if "UNREAD" in m.get("labels", [])]
                    lines = [f"{min(len(unread), 5)} newest unread inbox emails:"]
                    for m in unread[:5]:
                        from_name = m.get("from_name", "Unknown")
                        subject = m.get("subject", "(no subject)")
                        lines.append(f"- {from_name}: {subject}")
                    if len(unread) == 0:
                        lines.append("(No unread inbox emails)")
                    reply = ["\n".join(lines)]
            save_state(state)
            _log_conversation(text, reply, route="gmail_live", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return reply
        except Exception as e:
            reply = ["[GMAIL] Inbox is empty or unreachable."]
            save_state(state)
            _log_conversation(text, reply, route="gmail_live_error", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return reply
    if has_email_cap and _detect_inner_circle_email_reply_intent(query):
        bridge_reply = _handle_inner_circle_email_reply_bridge(query)
        if bridge_reply is not None:
            reply = [bridge_reply]
            save_state(state)
            _log_conversation(text, reply, route="email_reply_bridge", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return reply
    """
    Main Cassandra conversational handler.
    Returns a list of Telegram-ready reply strings.
    """
    if not session_meta.get("skip_followup_check"):
        process_pending_followups()

    state = load_state()
    state["last_interaction_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mode toggles — always respond, no LLM needed
    toggle = _check_toggle(text)
    if toggle:
        save_state(state)
        _log_conversation(text, [toggle], route="toggle", metadata={"event_id": event_id})
        return [toggle]

    # Payment follow-up commands — pre-LLM, bypasses capability gate
    pay_cmd = _check_payments_command(text, state)
    if pay_cmd:
        save_state(state)
        _log_conversation(text, [pay_cmd], route="payment_cmd", metadata={"event_id": event_id})
        return [pay_cmd]

    correction_reply = _handle_pending_session_fact_correction(text, state)
    if correction_reply is None:
        correction_reply = _detect_session_fact_correction(text, state)
    if correction_reply is not None:
        save_state(state)
        _log_conversation(text, [correction_reply], route="session_fact_correction", metadata={"event_id": event_id})
        return [correction_reply]

    # Briefing recall — no LLM needed
    try:
        from cassandra_briefing_brain import is_recall_request, handle_recall
        if is_recall_request(text):
            save_state(state)
            recall_reply = handle_recall(text)
            _log_conversation(text, [recall_reply], route="briefing_recall", metadata={"event_id": event_id})
            return [recall_reply]
    except Exception as _e:
        pass  # briefing module unavailable — fall through to LLM

    if not operator_intake_candidate and _should_route_finance_status_before_intake(query, gmail_decision):
        finance_reply = _handle_finance_status_request(query, state)
        if finance_reply is not None:
            save_state(state)
            _log_conversation(text, [finance_reply], route="finance_status", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [finance_reply]

    # Deterministic Status Inquiry (Business Ops Spine Step 5)
    # Priority: Must come before fuzzy intent matching for financial/future-action
    # to ensure "remind me what's current" routes to status, not a reminder.
    if ops_intent.intent_name == "ops_status":
        finance_reply = _handle_finance_status_request(query, state)
        if finance_reply is not None:
            save_state(state)
            _log_conversation(text, [finance_reply], route="finance_status", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [finance_reply]
        save_state(state)
        status_reply, status_packet = _answer_ops_status_inquiry(query, state)
        _log_conversation(
            text,
            [status_reply],
            route="ops_status",
            metadata={
                "event_id": event_id,
                "ops_packet": ops_packet.to_dict(),
                "orientation_packet_type": status_packet.get("packet_type"),
                "orientation_packet_status": status_packet.get("status"),
                "model_called": True,
            },
        )
        return [status_reply]

    query = _strip_prefix(text)
    if str(session_meta.get("source_user_label") or "operator") == "operator":
        guided_review_kwargs: dict[str, Any] = {}
        if session_meta.get("received_at_utc"):
            guided_review_kwargs["generated_at_utc"] = str(session_meta["received_at_utc"])
        if session_meta.get("guided_review_root"):
            guided_review_kwargs["review_root"] = session_meta["guided_review_root"]
        if session_meta.get("guided_review_read_model_root"):
            guided_review_kwargs["read_model_root"] = session_meta["guided_review_read_model_root"]
        if session_meta.get("guided_review_receipt_root"):
            guided_review_kwargs["receipt_root"] = session_meta["guided_review_receipt_root"]
        if session_meta.get("guided_review_promotion_review_path"):
            guided_review_kwargs["promotion_review_path"] = session_meta["guided_review_promotion_review_path"]
        if session_meta.get("chatgpt55_provider"):
            guided_review_kwargs["chatgpt55_provider"] = session_meta["chatgpt55_provider"]
        if session_meta.get("chatgpt55_env"):
            guided_review_kwargs["chatgpt55_env"] = session_meta["chatgpt55_env"]
        if session_meta.get("gemini_form_provider"):
            guided_review_kwargs["gemini_form_provider"] = session_meta["gemini_form_provider"]
        if session_meta.get("gemini_form_env"):
            guided_review_kwargs["gemini_form_env"] = session_meta["gemini_form_env"]
        switchboard_read_model_root = guided_review_kwargs.get("read_model_root") or session_meta.get("operator_intake_read_model_root")
        switchboard_review_root = guided_review_kwargs.get("review_root")
        if switchboard_review_root is None and (
            session_meta.get("operator_intake_read_model_root") or session_meta.get("operator_intake_receipt_root")
        ):
            switchboard_review_root = (
                Path(switchboard_read_model_root).parent / "guided_review"
                if switchboard_read_model_root
                else Path(session_meta["operator_intake_receipt_root"]).parent / "guided_review"
            )
        switchboard_kwargs: dict[str, Any] = {
            "review_root": switchboard_review_root,
            "read_model_root": switchboard_read_model_root,
            "receipt_root": session_meta.get("operator_context_switchboard_receipt_root"),
            "operator_intake_receipt_root": session_meta.get("operator_intake_receipt_root"),
        }
        if session_meta.get("received_at_utc"):
            switchboard_kwargs["received_at_utc"] = str(session_meta["received_at_utc"])
        if session_meta.get("operator_timezone"):
            switchboard_kwargs["operator_timezone"] = str(session_meta["operator_timezone"])
        switchboard_decision = _process_operator_context_switchboard_message(
            query,
            surface="telegram",
            source_agent="cassandra",
            operator="Winship",
            **switchboard_kwargs,
        )
        skip_guided_review = False
        skip_universal_intake = False
        email_send_request = gmail_decision.allowed and _detect_send_email_intent(query)
        if switchboard_decision is not None:
            switch_decision = str(switchboard_decision.get("decision") or "")
            if switch_decision in {"new_task_interrupt", "new_task_stage", "clarification_needed", "unsupported_but_logged"}:
                reply = [str(switchboard_decision.get("operator_visible_reply") or "I need one quick clarification before I route that.")]
                save_state(state)
                _log_conversation(
                    text,
                    reply,
                    route="operator_context_switchboard",
                    metadata={
                        "event_id": event_id,
                        "decision_id": switchboard_decision.get("decision_id", ""),
                        "decision": switch_decision,
                        "detected_intent": switchboard_decision.get("detected_intent", ""),
                        "detected_lane": switchboard_decision.get("detected_lane", ""),
                        "routed_to_agent": switchboard_decision.get("routed_to_agent", ""),
                        "routed_to_lane": switchboard_decision.get("routed_to_lane", ""),
                        "current_task_action": switchboard_decision.get("current_task_action", ""),
                        "receipt_refs": switchboard_decision.get("receipt_refs", []),
                        "watch_desk_refs": switchboard_decision.get("watch_desk_refs", []),
                        "safety_flags": switchboard_decision.get("safety_flags", {}),
                    },
                )
                return reply
            if switch_decision == "resume_task" and str(switchboard_decision.get("routed_to_lane") or "") != "guided_review_session":
                reply = [str(switchboard_decision.get("operator_visible_reply") or "Continuing that task.")]
                save_state(state)
                _log_conversation(
                    text,
                    reply,
                    route="operator_context_switchboard",
                    metadata={
                        "event_id": event_id,
                        "decision_id": switchboard_decision.get("decision_id", ""),
                        "decision": switch_decision,
                        "detected_intent": switchboard_decision.get("detected_intent", ""),
                        "detected_lane": switchboard_decision.get("detected_lane", ""),
                        "routed_to_agent": switchboard_decision.get("routed_to_agent", ""),
                        "routed_to_lane": switchboard_decision.get("routed_to_lane", ""),
                        "current_task_action": switchboard_decision.get("current_task_action", ""),
                        "receipt_refs": switchboard_decision.get("receipt_refs", []),
                        "watch_desk_refs": switchboard_decision.get("watch_desk_refs", []),
                        "safety_flags": switchboard_decision.get("safety_flags", {}),
                    },
                )
                return reply
            if switch_decision == "current_task_control" and switchboard_decision.get("operator_visible_reply"):
                reply = [str(switchboard_decision.get("operator_visible_reply"))]
                save_state(state)
                _log_conversation(
                    text,
                    reply,
                    route="operator_context_switchboard",
                    metadata={
                        "event_id": event_id,
                        "decision_id": switchboard_decision.get("decision_id", ""),
                        "decision": switch_decision,
                        "detected_intent": switchboard_decision.get("detected_intent", ""),
                        "detected_lane": switchboard_decision.get("detected_lane", ""),
                        "routed_to_agent": switchboard_decision.get("routed_to_agent", ""),
                        "routed_to_lane": switchboard_decision.get("routed_to_lane", ""),
                        "current_task_action": switchboard_decision.get("current_task_action", ""),
                        "receipt_refs": switchboard_decision.get("receipt_refs", []),
                        "watch_desk_refs": switchboard_decision.get("watch_desk_refs", []),
                        "safety_flags": switchboard_decision.get("safety_flags", {}),
                    },
                )
                return reply
            if switch_decision == "approval_passthrough":
                skip_guided_review = True
                skip_universal_intake = True
        if email_send_request:
            skip_universal_intake = True

        guided_review_response = None
        if not skip_guided_review:
            guided_review_response = _process_guided_review_message(
                query,
                surface="telegram",
                operator="Winship",
                **guided_review_kwargs,
            )
        if guided_review_response is not None:
            reply = [str(guided_review_response["reply_text"])]
            save_state(state)
            _log_conversation(
                text,
                reply,
                route="guided_review_session",
                metadata={
                    "event_id": event_id,
                    "review_session_id": guided_review_response.get("review_session_id", ""),
                    "current_question_id": guided_review_response.get("current_question_id", ""),
                    "status": guided_review_response.get("status", ""),
                    "progress": guided_review_response.get("progress", {}),
                    "artifact_refs": guided_review_response.get("artifact_refs", {}),
                    "receipt_refs": guided_review_response.get("receipt_refs", []),
                    "watch_desk_refs": guided_review_response.get("watch_desk_refs", []),
                    "authoritative": False,
                    "runtime_policy_changed": False,
                    "external_calls_performed": False,
                },
            )
            return reply

        intake_kwargs: dict[str, Any] = {}
        if session_meta.get("received_at_utc"):
            intake_kwargs["received_at_utc"] = str(session_meta["received_at_utc"])
        if session_meta.get("operator_timezone"):
            intake_kwargs["operator_timezone"] = str(session_meta["operator_timezone"])
        if session_meta.get("operator_intake_read_model_root"):
            intake_kwargs["read_model_root"] = session_meta["operator_intake_read_model_root"]
        if session_meta.get("operator_intake_receipt_root"):
            intake_kwargs["receipt_root"] = session_meta["operator_intake_receipt_root"]
        intake_response = None
        if not skip_universal_intake:
            intake_response = _try_universal_operator_intake(
                query,
                surface="telegram",
                operator="Winship",
                **intake_kwargs,
            )
        if intake_response is not None:
            reply = [str(intake_response["reply"])]
            save_state(state)
            _log_conversation(
                text,
                reply,
                route="universal_operator_intake",
                metadata={
                    "event_id": event_id,
                    "intake_id": intake_response["intake_id"],
                    "action_type": intake_response["action_type"],
                    "action_types": intake_response.get("action_types", []),
                    "risk_tier": intake_response["risk_tier"],
                    "inferred_owner_agent": intake_response.get("inferred_owner_agent", ""),
                    "inferred_owner_lane": intake_response.get("inferred_owner_lane", ""),
                    "routed_from_agent": intake_response.get("routed_from_agent", ""),
                    "routed_to_agent": intake_response.get("routed_to_agent", ""),
                    "execution_mode": intake_response.get("execution_mode", ""),
                    "route_confidence": intake_response.get("route_confidence", ""),
                    "approval_required": bool(intake_response.get("approval_required")),
                    "external_calls_performed": bool(intake_response.get("external_calls_performed")),
                    "receipt_refs": intake_response.get("receipt_refs", []),
                    "watch_desk_refs": intake_response.get("watch_desk_refs", []),
                },
            )
            return reply

    _update_cues(state, query)
    _remember_finance_entity(query, state)

    # ── Topic-sensitivity gate for inner-circle contacts ──────────────────────
    _sender_name = session_meta.get("sender_name")
    _sender_chat_id = session_meta.get("sender_chat_id")
    _contact_entry = None
    if _sender_name and _sender_chat_id not in (None, ""):
        _name_contact = _find_designated_contact(sender_name=_sender_name, sender_chat_id=None)
        if _name_contact is not None and _name_contact.get("tier") == "inner_circle":
            _verified_contact = verify_sender_on_channel(
                sender_name=_sender_name,
                sender_id=str(_sender_chat_id),
                channel="telegram",
            )
            if _verified_contact is None:
                _identity_reply = (
                    "I can't verify who this is. Winship will need to help me connect us."
                )
                log_chirp("unverified_sender", state)
                save_state(state)
                _log_conversation(text, [_identity_reply], route="identity_challenge", metadata={"event_id": event_id})
                return [_identity_reply]
            _contact_entry = _verified_contact
    if _contact_entry is None:
        _contact_entry = _find_designated_contact(
            sender_name=_sender_name, sender_chat_id=_sender_chat_id
        )
    if _contact_entry is not None:
        from cassandra_contact_policy import classify_topic as _classify_topic
        _lane = _classify_topic(query, _contact_entry["nickname"])
        if _lane == "caution":
            _hold_reply = (
                "I have context on that, but I'd like to verify with Winship "
                "before sharing. I'll follow up shortly."
            )
            try:
                from chief_notify import send as _notify_winship
                _notify_winship(
                    f"Cassandra topic hold \u2014 caution lane.\n"
                    f"From: {_contact_entry['display_name']} ({_contact_entry['nickname']})\n"
                    f"Asked: {query}\n"
                    f"Lane: caution \u2014 awaiting your confirmation."
                )
            except Exception as _e:
                print(f"[cassandra] topic-gate notify error: {_e}", flush=True)
            save_state(state)
            _log_conversation(text, [_hold_reply], route="topic_gate_hold", metadata={"event_id": event_id})
            return [_hold_reply]
        if _lane == "escalate":
            _escalate_reply = (
                "That's something I'd need Winship to authorize. "
                "I'll flag it for him."
            )
            try:
                from chief_notify import send as _notify_winship
                _notify_winship(
                    f"Cassandra topic ESCALATION.\n"
                    f"From: {_contact_entry['display_name']} ({_contact_entry['nickname']})\n"
                    f"Asked: {query}\n"
                    f"Lane: escalate \u2014 do not answer without your approval."
                )
            except Exception as _e:
                print(f"[cassandra] topic-gate notify error: {_e}", flush=True)
            save_state(state)
            _log_conversation(text, [_escalate_reply], route="topic_gate_escalate", metadata={"event_id": event_id})
            return [_escalate_reply]
        # _lane == "allowed" → fall through to normal dispatch
    # ── End topic-sensitivity gate ────────────────────────────────────────────

    # Pending income follow-up — check before financial detection
    pending = state.get("pending_income_followup")
    if pending:
        followup_reply = _handle_income_followup(query, pending, state)
        if followup_reply:
            save_state(state)
            _log_conversation(text, [followup_reply], route="income_followup", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [followup_reply]
        # pending cleared by handler; fall through if it was a new financial event

    # Financial lookup
    if _detect_lookup_intent(query):
        save_state(state)
        lookup_reply = _handle_lookup(query)
        _log_conversation(text, [lookup_reply], route="financial_lookup", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
        return [lookup_reply]

    # Financial event routing — bypass LLM for speed and reliability
    fin_intent = _detect_financial_intent(query)
    if fin_intent:
        fin_reply = _handle_financial_event(query, fin_intent, state)
        if fin_reply:
            save_state(state)
            _log_conversation(text, [fin_reply], route="financial_event", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [fin_reply]
    # fall through to LLM if detection or parsing failed

    # Future-action enqueue — bypass LLM, queues reminder for later dispatch.
    # Must come before calendar_create because "remind me " is in _CALENDAR_CREATE_WORDS.
    if _detect_future_action_intent(query):
        future_reply = _handle_future_action_queue_request(query, sender_chat_id=session_meta.get("sender_chat_id"))
        if future_reply is not None:
            save_state(state)
            _log_conversation(text, [future_reply], route="future_action", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [future_reply]
    # fall through to LLM if enqueue returned None

    # Calendar delete routing — bypass LLM for event deletion
    if _detect_calendar_delete_intent(query):
        cal_delete_reply = _handle_calendar_delete(query)
        if cal_delete_reply is not None:
            save_state(state)
            _log_conversation(text, [cal_delete_reply], route="calendar_delete", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [cal_delete_reply]
    # fall through to LLM if extraction failed or unclear

    # Calendar create routing — bypass LLM for event creation
    if _detect_calendar_create_intent(query):
        cal_reply = _handle_calendar_create(query)
        if cal_reply is not None:
            save_state(state)
            _log_conversation(text, [cal_reply], route="calendar_create", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [cal_reply]
    # fall through to LLM if extraction failed or unclear

    # Outreach intro email routing — bypass LLM, creates brokered Gmail drafts
    if gmail_decision.allowed and _detect_outreach_email_intent(query):
        outreach_reply = _handle_outreach_email_request(query)
        if outreach_reply is not None:
            save_state(state)
            _log_conversation(text, [outreach_reply], route="outreach_email_draft", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return [outreach_reply]

    # Email routing — bypass LLM, creates brokered review drafts instead of sending
    if gmail_decision.allowed and _detect_send_email_intent(query):
        email_reply = _handle_send_email(query)
        if email_reply is not None:
            save_state(state)
            _log_conversation(text, [email_reply], route="email_send", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return [email_reply]
    # fall through to LLM if parsing failed

    # Invoice generation — PDF invoice via reportlab
    if _detect_invoice_intent(query):
        invoice_reply = _handle_create_invoice(query, state)
        if invoice_reply is not None:
            save_state(state)
            _log_conversation(text, [invoice_reply], route="invoice_create", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [invoice_reply]

    # File verification — bypass LLM, direct filesystem check
    if _detect_file_verify_intent(query):
        file_reply = _handle_file_verification_request(query)
        if file_reply is not None:
            save_state(state)
            _log_conversation(text, [file_reply], route="file_verify", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [file_reply]

    if _get_session_fact_override(query, state) is not None:
        finance_reply = _handle_finance_status_request(query, state)
        if finance_reply is not None:
            save_state(state)
            _log_conversation(text, [finance_reply], route="finance_status", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [finance_reply]

    # Payment verification — bypass LLM, direct Gmail/log check
    if gmail_decision.allowed and gmail_decision.category == "payment_verify" and _detect_payment_verify_intent(query):
        pay_reply = _handle_payment_verification_request(query)
        if pay_reply is not None:
            save_state(state)
            _log_conversation(text, [pay_reply], route="payment_verify", metadata={
                "gmail_intent": gmail_decision.to_dict(),
                "ops_packet": ops_packet.to_dict(),
                "event_id": event_id,
                "gmail_polled": True
            })
            return [pay_reply]

    if not operator_intake_candidate and _should_route_finance_status_before_intake(query, gmail_decision):
        finance_reply = _handle_finance_status_request(query, state)
        if finance_reply is not None:
            save_state(state)
            _log_conversation(text, [finance_reply], route="finance_status", metadata={"event_id": event_id, "ops_packet": ops_packet.to_dict()})
            return [finance_reply]

    context  = build_context_snapshot(state)
    focus    = is_focus_mode()
    social   = is_social_mode()
    allow_deep_escalation = _should_use_deep(query)
    reply_task_class = (
        "cassandra_user_reply_fast"
        if _use_small_cassandra_reply_model(query)
        else "cassandra_user_reply"
    )

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

    calendar_ctx   = _fetch_calendar_context(query, ops_packet=ops_packet)
    calendar_block = f"{calendar_ctx}\n\n" if calendar_ctx else ""

    gmail_ctx   = _fetch_gmail_context(query, decision=gmail_decision, ops_packet=ops_packet)
    gmail_block = f"{gmail_ctx}\n\n" if gmail_ctx else ""

    contacts_ctx   = _fetch_contacts_context(query, ops_packet=ops_packet)
    contacts_block = f"{contacts_ctx}\n\n" if contacts_ctx else ""

    finance_ctx   = format_finance_context(query)
    finance_block = f"{finance_ctx}\n\n" if finance_ctx else ""

    payment_verify_ctx   = _fetch_payment_verify_context(query, decision=gmail_decision, ops_packet=ops_packet)
    payment_verify_block = f"{payment_verify_ctx}\n\n" if payment_verify_ctx else ""

    # Check if Gmail was actually polled (attempted)
    gmail_polled = bool(gmail_ctx or payment_verify_ctx)
    reality_ctx   = _format_reality_context(query)
    reality_block = f"{reality_ctx}\n\n" if reality_ctx else ""
    session_override_ctx = _format_session_fact_override_context(query, state)
    session_override_block = f"{session_override_ctx}\n\n" if session_override_ctx else ""

    # Cloud routing gate — evaluated after all context sources are known.
    # Passes context pieces (not the assembled prompt) so the check can inspect
    # exactly what was injected rather than pattern-matching the full prompt string.
    cloud_ok = _cassandra_context_clean(
        calendar_ctx, gmail_ctx, contacts_ctx, finance_ctx, payment_verify_ctx, reality_ctx, context, query
    )

    prompt = (
        f"{build_authoritative_date_context()}\n\n"
        f"{persona}\n"
        f"Current context:\n{context}\n\n"
        f"{capability_context()}\n\n"
        f"{calendar_block}"
        f"{gmail_block}"
        f"{contacts_block}"
        f"{finance_block}"
        f"{payment_verify_block}"
        f"{reality_block}"
        f"{session_override_block}"
        f"{registry_block}"
        f"User: {query}\n"
        f"Cassandra:"
    )

    # PII guard — tokenize sensitive content from the assembled prompt before
    # sending to any LLM (local or cloud).  Tokens are rehydrated after the
    # response so the reply can reference the original values if needed.
    # If all tokenization paths fail, block the send rather than leak plaintext.
    safe_prompt, _pii_ctx = _pii_tokenize(prompt)
    if safe_prompt is None:
        save_state(state)
        blocked_reply = ["I need to protect some sensitive context before replying. Please try again in a moment."]
        _log_conversation(text, blocked_reply, route="pii_block", metadata={
            "gmail_intent": gmail_decision.to_dict(),
            "ops_packet": ops_packet.to_dict(),
            "event_id": event_id,
            "gmail_polled": gmail_polled
        })
        return blocked_reply

    try:
        reply = _call(
            safe_prompt,
            task_class=reply_task_class,
            cloud_ok=cloud_ok,
            allow_deep_escalation=allow_deep_escalation,
        )
    except Exception as e:
        print(f"[cassandra] _call error: {e}", flush=True)
        save_state(state)
        error_reply = ["I'm here, but I hit a snag thinking that through. Try again in a moment."]
        _log_conversation(text, error_reply, route="error", metadata={
            "gmail_intent": gmail_decision.to_dict(),
            "ops_packet": ops_packet.to_dict(),
            "event_id": event_id,
            "gmail_polled": gmail_polled
        })
        return error_reply
    route_override = None
    reply = _pii_rehydrate_reply(reply, _pii_ctx)
    rescued_payment_reply = _rescue_payment_verify_reply(query, reply)
    if rescued_payment_reply is not None:
        reply = rescued_payment_reply
        route_override = "payment_verify_rescue"
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
                sender_channel=session_meta.get("sender_channel"),
                sender_email=session_meta.get("sender_email"),
                original_message=query,
                partial_reply=reply,
                capability_gaps=capability_gaps,
            )
            if contact_entry.get("tier") == "client":
                _notify_client_urgency(contact_entry, query, reply, capability_gaps)

    save_state(state)

    result = [reply] if reply else ["I'm here — something went quiet on my end. Try again."]
    _log_conversation(
        text,
        result,
        route=route_override or ("llm_deep" if allow_deep_escalation else "llm"),
        metadata={
            "gmail_intent": gmail_decision.to_dict(),
            "ops_packet": ops_packet.to_dict(),
            "event_id": event_id,
            "gmail_polled": gmail_polled,
            "model_path": "nemotron" if cloud_ok else "local",
            "reply_task_class": reply_task_class
        }
    )
    return result
