import re
import time as _time
import hashlib as _hashlib
import fcntl
from pathlib import Path as _Path

# -- Route logger -----------------------------------------------------------
_ROUTE_LOG = _Path("/mnt/c/OpenClaw/logs/route_log.csv")
_llm_fallback_fired = False

def _rotate_route_log() -> None:
    """Archive route_log.csv when it exceeds 10000 lines."""
    try:
        if not _ROUTE_LOG.exists():
            return
        with open(_ROUTE_LOG, "r") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                line_count = sum(1 for _ in f)
                if line_count > 10000:
                    archive = _ROUTE_LOG.with_suffix(
                        f".{_time.strftime('%Y%m%d_%H%M%S')}.csv"
                    )
                    _ROUTE_LOG.rename(archive)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        print(f"[route_log] rotation error: {e}", flush=True)


def _log_route(msg_hash: str, intent: str, llm_fallback: bool) -> None:
    """Append one row to route_log.csv. Fails open, never raises."""
    try:
        if llm_fallback:
            method = "llm_local"
        elif intent == "generic":
            method = "fallback_generic"
        else:
            method = "pattern"
        needs_header = not _ROUTE_LOG.exists() or _ROUTE_LOG.stat().st_size == 0
        with open(_ROUTE_LOG, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                if needs_header:
                    f.write("timestamp,message_hash,intent,route_method,llm_fallback_used\n")
                ts = _time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{ts},{msg_hash},{intent},{method},{llm_fallback}\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        _rotate_route_log()
    except Exception as e:
        print(f"[route_log] write error: {e}", flush=True)

from adaptive_model_call import adaptive_ollama_text
from email_intent import (
    EmailIntent,
    classify_email_intent,
    email_intent_requires_draft,
    is_outbound_email_history_request,
)

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)


from chief_llm import ollama_json
from chief_session_manager import (
    load_session,
    set_workflow,
    set_workflow_state,
    get_workflow_state,
    append_history,
    mark_cancelled,
    reset_session,
)
from chief_approval_brain import (
    has_pending_approval,
    record_decision,
    get_pending_info,
    parse_reply_code,
)
from chief_nonapproval_responder import nonapproval_response_for_text
from chief_reporter_brain import handle as reporter_handle
from chief_scout_brain import handle as scout_handle
from chief_integration_brain import handle as integration_handle
from chief_reflection_brain import handle as reflection_handle
from chief_cpa_brain import handle as cpa_handle
from chief_musiclaw_brain import handle as musiclaw_handle
from chief_publishing_brain import handle as publishing_handle
from chief_phone_brain import handle as phone_handle
from chief_sms_brain import (
    handle as sms_handle,
    get_pending_draft as sms_pending_draft,
    confirm_send as sms_confirm_send,
)
from chief_email_brain import handle as email_handle
from chief_calendar_brain import handle as calendar_handle
from chief_queue_brain import handle as queue_handle
from chief_trinity_brain import handle as trinity_handle
from chief_backup_brain import handle as backup_handle
from chief_financial_brain import handle as financial_handle
from chief_tax_sorter import handle as tax_sorter_handle
from fin_fortress_auditor import handle as fin_fortress_handle
from chief_analytics_brain import handle as analytics_handle
from chief_goals_brain import handle as goals_handle
from chief_momentum_brain import handle as momentum_handle
from chief_fundo_session import handle as fundo_session_handle
from chief_fundo_identity import handle as fundo_identity_handle
from chief_fundo_release import handle as fundo_release_handle
from chief_website_creative import handle as website_creative_handle
from chief_website_coordinator import handle as website_coordinator_handle
from chief_website_qa import handle as website_qa_handle
from chief_billing_brain import (
    handle as billing_handle,
    get_questions as billing_questions,
    BILLING_SURFACE,
)
from clarify_session_contract import stamp_clarify_session
from chief_content_brain import handle as content_handle
from chief_brand_brain import handle as brand_handle
from chief_marketing_brain import (
    handle as marketing_handle,
    _is_draft_request as _marketing_is_draft,
    _is_log_update as _marketing_is_log_update,
)
from chief_album_mixer import handle as album_mixer_handle
from chief_scheduler_brain import handle as scheduler_handle, _load as _sched_load
from chief_brainstorm_brain import handle as brainstorm_handle
from chief_brainstorm_router import handle as brainstorm_router_handle
from chief_brainstorm_watcher import handle as brainstorm_watch_handle
from chief_focus_shield import handle as focus_shield_handle
from chief_approval_bridge import (
    has_pending_choice,
    handle as bridge_handle,
)
from chief_nli import detect_nli_query, handle as nli_handle
from chief_ops_brain import is_ops_intake, handle as ops_handle, save_deferred as ops_save_deferred
from cassandra_brain import cassandra_intent, handle as cassandra_handle, get_cassandra_summary
from chief_morning_inspector import handle_morning_inspection, handle_morning_followup
from chief_album_batch import handle as batch_handle, batch_intent
from chief_album_brain import (
    handle as album_handle,
    handle_arc as album_arc_handle,
    handle_quick_update as album_quick_update,
    handle_status as album_status_handle,
    _ALBUM_SONGS,
)


def morning_inspection_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(t.startswith(cmd) for cmd in (
        "morning raw", "morning cache", "morning stale", 
        "morning blockers", "morning actions", "morning sources"
    ))

def morning_followup_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "morning brief", "what were the blockers", "what are the top priorities",
        "what did the morning brief", "what did chief use", "what was stale",
        "what was the directive", "remind me what cassandra said this morning",
        "morning report", "about the morning", "what was in the morning",
        "this morning's brief", "this mornings brief"
    ])

def scheduler_intent(text: str) -> bool:
    t = text.lower().strip()
    # Always intercept explicit start / status commands
    if any(k in t for k in ("schedule ", "timer ", "start block", "work block",
                             "timer status", "scheduler status", "block status")):
        return True
    # Always intercept explicit stop phrases
    if any(k in t for k in ("stop for now", "stop session", "done for now", "end session")):
        return True
    # Sticky: intercept session responses whenever scheduler is active (not idle)
    state = _sched_load()
    if state.get("status", "idle") != "idle":
        if t in ("continue", "stop") or t.startswith(("break", "switch", "take break")):
            return True
    return False


def looks_like_inspection(text: str) -> bool:
    t = text.lower()
    keywords = [
        "inspect",
        "inspection",
        "snapshot",
        "architecture",
        "system status",
        "what's running",
        "what is running",
        "ports",
        "processes",
        "check the system",
        "look at the system",
        "look at the setup",
    ]
    return any(k in t for k in keywords)


def looks_like_cancel(text: str) -> bool:
    t = text.lower().strip()
    phrases = [
        "cancel",
        "stop",
        "never mind",
        "nevermind",
        "start over",
        "reset",
        "quit",
        "exit",
    ]
    return any(p == t or p in t for p in phrases)


def looks_like_correction(text: str) -> bool:
    t = text.lower().strip()
    phrases = [
        "that was wrong",
        "hold up",
        "wait",
        "correction",
        "change that",
        "go back",
        "undo that",
        "the last thing was wrong",
    ]
    return any(p in t for p in phrases)


def billing_mode_from_text(text: str) -> str | None:
    t = text.lower().strip()

    if any(k in t for k in [
        "i need to send an invoice",
        "send an invoice",
        "make an invoice",
        "create invoice",
        "draft invoice",
        "bill this client",
        "i need to make an invoice",
        "invoice",
    ]):
        return "INVOICE"

    if any(k in t for k in [
        "payment received",
        "mark payment received",
        "payment came in",
        "got paid",
        "deposit received",
        "balance received",
        "update payment",
        "payment",
    ]):
        return "PAYMENT"

    if any(k in t for k in [
        "follow up",
        "follow-up",
        "remind this client",
        "check in with client",
        "nudge the client",
        "followup",
    ]):
        return "FOLLOWUP"

    if any(k in t for k in [
        "receipt",
        "issue receipt",
        "send receipt",
    ]):
        return "RECEIPT"

    return None


_QUICK_UPDATE_SIGNALS = [
    "is done", "are done", "is locked", "are locked", "is finished",
    "are finished", "finished tracking", "just finished", "just tracked",
    "i tracked", "tracking done", "done tracking", "just locked",
    "is complete", "are complete", "is ready", "is mixed", "is mastered",
]


def looks_like_quick_update(text: str) -> bool:
    """True when the message mentions a known song AND a completion signal,
    with no active album session in progress."""
    t = text.lower()
    has_signal = any(s in t for s in _QUICK_UPDATE_SIGNALS)
    has_song = any(song.lower() in t for song in _ALBUM_SONGS)
    return has_signal and has_song


def scout_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "scout report", "what's new in ai", "whats new in ai",
        "tech digest", "research report", "new tools", "ai tools",
        "new in ai", "what's new in tech", "whats new in tech",
        "music tech", "new platforms",
    ])


def reporter_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "system report", "daily report", "what ran today", "status report",
        "worker report", "watcher report", "what happened today",
        "how is the system",
    ])


def marketing_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "marketing", "content idea", "content ideas", "what should i post",
        "what can i post", "what can i make", "post about", "reel",
        "tiktok", "instagram", "youtube", "social media",
        "i have", "what to post", "log that", "i posted", "mark as posted",
        "mark it as", "draft a caption", "draft a hook", "write a caption",
        "write a hook", "write me a", "marketing idea",
    ])


def email_intent(text: str) -> bool:
    owned = classify_email_intent(text)
    return (
        owned in {EmailIntent.DRAFT_SEND, EmailIntent.OUTREACH}
        or (owned is EmailIntent.REPLY and email_intent_requires_draft(text))
        or is_outbound_email_history_request(text)
    )


def sms_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "send sms", "send a text", "text ", "sms to", "draft sms",
        "draft a text", "draft a message", "sms log", "sent texts",
        "text history", "message log",
    ])


def phone_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "log call", "log a call", "just got off a call", "had a call with",
        "got off the phone", "just spoke with", "just talked to",
        "call script", "talking points", "what should i say to",
        "how should i approach", "script for calling",
        "call log", "call history", "recent calls", "show calls",
    ])


def cpa_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "what did i make", "income this month", "income summary",
        "what do i owe", "quarterly tax", "estimated tax", "tax estimate",
        "what can i deduct", "deductions", "write off", "write-off",
        "log expense", "add expense", "i spent", "i paid for",
        "quarterly", "cpa", "tax owed",
    ])


def musiclaw_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "music law", "legal question", "my rights", "ten fingers",
        "log rhythm", "log rhythm records", "renae", "what are my options",
        "co-write", "co write", "publishing rights", "master rights",
        "work for hire", "music contract", "add case note",
        "sync license", "copyright", "royalty dispute",
    ])


def publishing_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "publishing status", "catalog status", "what songs are registered",
        "publishing", "register ", "sync opportunities", "sync-ready",
        "sync ready", "update publishing", "publishing catalog",
        "song rights", "pro registration", "ascap", "bmi",
    ])


def content_calendar_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "content calendar", "content schedule", "what's due for posting",
        "whats due for posting", "content status", "posting schedule",
        "what needs to go up", "mark posted", "schedule post",
    ])


def brand_guide_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "brand guide", "style guide", "brand rules",
        "is this on brand", "on brand check", "brand check",
        "dpr brand", "fundo brand guide",
    ])


def financial_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "financial report", "p&l", "profit and loss",
        "outstanding invoices", "who owes me", "unpaid invoices",
        "payment history", "revenue this month", "quarterly projection",
        "tax projection", "financial summary", "income report",
        "how's business", "hows business",
    ])


def tax_sorter_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "sort taxes", "tax sort", "classify transactions", "business deductions",
        "deduction review", "tax categories", "smart tax", "tax sorter",
        "sort my taxes", "classify deductions",
    ])


def fin_fortress_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "financial fortress", "fortress audit", "gear audit", "music gear",
        "gear deduction", "studio gear", "flag gear", "gear expenses",
        "equipment deduction", "gear report",
    ])


def analytics_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "analytics", "weekly metrics", "metrics report", "show analytics",
        "business report",
    ])


def goals_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "goals", "goal check", "how am i doing", "goal progress",
        "update goal", "set goal", "milestone goal", "check in",
        "goal tracker",
    ])


def momentum_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "momentum", "am i on track", "activity check", "how active am i",
        "artist mode", "admin mode", "am i in artist", "am i in admin",
        "momentum report",
    ])


def backup_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "backup status", "check backup", "git status",
        "backup now", "push backup", "do backup", "backup push",
        "is the repo current", "repo status",
    ])


def trinity_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "trinity check", "system audit", "brain audit", "trinity status",
        "trinity report", "check trinities", "what's missing",
        "queue gaps", "propose gaps",
    ])


def queue_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "queue request", "add to queue", "remember to", "when you're at the computer",
        "feature request", "add a feature", "queue status", "what's queued",
        "whats queued", "show queue", "pending queue", "done queue",
    ]) or re.search(r"\badd feature\b", t) is not None


def calendar_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "what's my week", "whats my week", "what's today", "whats today",
        "what's coming up", "whats coming up", "calendar", "schedule",
        "what do i have", "what's on my", "my week", "this week",
        "upcoming events", "what's happening",
    ])


def mix_brief_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "mix brief", "mix session", "mix status", "mix ready",
        "what's mix ready", "whats mix ready",
    ]) or bool(re.search(r"^mix\s+(for\s+)?\w", t))


def fundo_release_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "fundo release", "release fundo", "release checklist",
        "fundo ready", "fundo releases", "release status",
    ])


def fundo_session_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "fundo session", "work on fundo", "new fundo track",
        "fundo track", "build fundo",
    ]) or (t == "approve") or t.startswith("revise ") or any(
        k in t for k in ("element done", "next element", "fundo note", "fundo status", "fundo progress")
    )


def fundo_identity_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "fundo brief", "fundo identity", "fundo brand", "fundo visual",
        "who is fundo", "what is fundo", "fundo song", "track brief",
        "fundo arc",
    ])


def website_qa_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "website qa", "qa report", "check the site", "site audit",
        "qa the site", "qa fundo", "run qa", "site check",
    ])


def website_coordinator_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "site status", "what does the site need", "website update",
        "site roadmap", "brand rules", "brand guide", "what needs to be built",
        "website status", "update the site",
    ])


def website_creative_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "headline", "website copy", "write bio", "bio for the site",
        "song description", "track description", "fundo mystery",
        "mystery text", "logo idea", "canva brief", "canva direction",
        "write copy", "homepage copy", "about page copy",
    ])


def reflection_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "reflection report", "monthly report", "what's working", "whats working",
        "usage report", "system reflection", "how are things going",
        "assess the system", "how is the system doing",
    ])


def integration_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "integration proposal", "integration proposals", "what can we add",
        "what can i add", "proposals", "propose", "approve prop-", "reject prop-",
        "approve PROP-", "reject PROP-",
    ]) or bool(__import__("re").search(r"(approve|reject)\s+prop-", t))


def brainstorm_capture_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in (
        "brainstorm", "capture idea", "capture", "new idea", "idea:",
    ))


def brainstorm_watch_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in (
        "brainstorm status", "brainstorm watch", "brainstorm check",
        "watching ideas", "idea list",
    ))


def brainstorm_queue_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in (
        "brainstorm queue", "brainstorm backlog", "show ideas",
        "route idea", "brainstorm done",
    )) or bool(re.search(r"route\s+bs-\d+|done\s+bs-\d+|bs-\d+\s+done", t))


def album_arc_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "album arc", "arc mode", "album story", "track order",
        "lyric arc", "album analysis", "song order",
    ])


def artifact_transform_intent(text: str) -> bool:
    """True for meta-level document transformation or inventory requests."""
    t = text.lower().strip()
    return any(k in t for k in [
        "rewrite this", "transform this", "turn this into",
        "summarize this artifact", "make this readable",
        "use the snapshot", "use the latest snapshot",
        "inspection snapshot", "clean inventory",
        "normalized inventory", "inventory from"
    ])


_CLASSIFY_PROMPT = """\
You are a music producer's assistant routing messages to the correct workflow.
Classify the message below into exactly one of these intent labels:
  invoice   — user wants to create or send an invoice to a client
  payment   — user is recording a payment received from a client
  followup  — user wants to set a follow-up reminder for a client
  receipt   — user wants to issue a receipt to a client
  album     — user wants to work on a song, mix, vocal, or album session
  cpa       — income, expenses, money made, tax, financial summary, how much earned
  calendar  — schedule, what's coming up, upcoming events, what do I have today/this week
  analytics — analytics, business report, how is the business doing, metrics
  goals     — goals check, how am I doing on my goals, goal progress
  none      — does not match any of the above

Rules:
- Return only the single lowercase label, nothing else.
- When unsure, return "none".

Message: {text}
Intent:"""

_PREFILL_PROMPT = """\
Extract billing field values from this message. Only extract values that are explicitly stated.
Return a JSON object with any of these fields you find: {fields}

Rules:
- Only include fields that have a clear, explicit value. DO NOT guess or infer.
- Amounts: return numeric string only, no currency symbols (e.g. "500", "1500.00").
- Dates: use YYYY-MM-DD if possible; otherwise keep as-is.
- Omit any field that is missing or ambiguous.
- Return only valid JSON, no markdown, no extra text.

Message: {text}
JSON:"""

_MODE_FIELDS = {
    "INVOICE": "client_name, client_email, project_or_event, service_date, amount_total, deposit_amount, due_date, payment_method, notes",
    "PAYMENT": "invoice_number, payment_amount, payment_date, notes",
    "FOLLOWUP": "client_name, invoice_number, next_follow_up_date, notes",
    "RECEIPT": "client_name, invoice_number, amount_received, payment_date, notes",
}


def _cassandra_context_for_chief() -> str:
    """Format Cassandra's state as a context string for injection into LLM prompts.

    NOTE: chief_router has no central LLM context assembly — each brain manages its
    own prompts. This helper is ready for brain-level injection in a follow-up pass.
    Call it from any brain's system prompt builder when Cassandra state is relevant.
    """
    try:
        s = get_cassandra_summary()
        parts = []
        if s["project_mood"] != "neutral":
            parts.append(f"Project mood: {s['project_mood']}")
        if s["human_cues"]:
            parts.append("Recent signals: " + ", ".join(s["human_cues"]))
        if s["focus_mode"]:
            parts.append("Focus mode: ACTIVE")
        if s["social_mode"]:
            parts.append("Social mode: ACTIVE")
        if s["recurring_concerns"]:
            parts.append("Recurring concerns: " + "; ".join(s["recurring_concerns"]))
        return "\n".join(parts) if parts else ""
    except Exception as e:
        print(f"[chief_router] cassandra context error: {e}", flush=True)
        return ""


def _llm_classify_intent(text: str) -> str | None:
    """LLM fallback classifier. Returns intent label or None if unclear/error."""
    global _llm_fallback_fired
    _llm_fallback_fired = True
    try:
        prompt = _CLASSIFY_PROMPT.format(text=text)
        result = _local_model_call(prompt, timeout=10).lower().strip()
        valid = {"invoice", "payment", "followup", "receipt", "album",
                 "cpa", "calendar", "analytics", "goals"}
        return result if result in valid else None
    except Exception as e:
        print(f"[chief_router] LLM classify error: {e}", flush=True)
        return None


def _prefill_summary(prefilled: dict) -> str:
    """Convert pre-filled fields into a natural one-line confirmation string."""
    p = prefilled
    parts = []
    if "client_name" in p:
        parts.append(p["client_name"])
    if "project_or_event" in p:
        parts.append(f"for {p['project_or_event']}")
    if "service_date" in p:
        parts.append(f"on {p['service_date']}")
    if "amount_total" in p:
        parts.append(f"${p['amount_total']}")
    if "deposit_amount" in p:
        parts.append(f"deposit ${p['deposit_amount']}")
    if "invoice_number" in p:
        parts.append(f"invoice {p['invoice_number']}")
    if "payment_amount" in p:
        parts.append(f"${p['payment_amount']} paid")
    if "payment_date" in p:
        parts.append(f"on {p['payment_date']}")
    if "amount_received" in p:
        parts.append(f"${p['amount_received']} received")
    if "next_follow_up_date" in p:
        parts.append(f"follow up {p['next_follow_up_date']}")
    return ", ".join(parts)


def _llm_prefill_billing(text: str, mode: str) -> dict:
    """Extract pre-fillable billing fields from the trigger message. Returns {} on failure."""
    fields = _MODE_FIELDS.get(mode, "")
    if not fields:
        return {}
    prompt = _PREFILL_PROMPT.format(fields=fields, text=text)
    data = ollama_json(prompt, timeout=15)
    # Allowlist: only keep known fields for this mode
    allowed = {f.strip() for f in fields.split(",")}
    return {k: v for k, v in data.items() if k in allowed and isinstance(v, str) and v.strip()}


def ops_intake_intent(text: str) -> bool:
    """True for messages with an explicit ops/admin intake prefix marker."""
    return is_ops_intake(text)


def album_intent(text: str) -> bool:
    t = text.lower().strip()
    keywords = [
        "album",
        "song",
        "mix",
        "version",
        "vocal",
        "readiness",
        "track",
        "candidate",
        "ship it",
        "main version",
    ]
    return any(k in t for k in keywords)


def help_intent(text: str) -> bool:
    t = text.lower().strip()
    return t in (
        "help", "commands", "what can you do", "what can i do",
        "what do you do", "capabilities", "options",
    )


_HELP_TEXT = """\
Chief — what I can handle:

Album: album session, arc, mix brief, batch planner, quick update
Billing: invoice, payment, receipt, follow-up
Finance: income summary, expenses, quarterly tax, deductions
Calendar: what's on my schedule, upcoming events
Email: draft email (send requires Guardian approval)
Ops: ops update, pending actions, ops status
Brainstorm: brainstorm, idea queue, watch ideas
Goals: goals check, momentum check, analytics
Publishing: publishing status, catalog, rights
Marketing: content calendar, brand guide, content draft
Music law: music law question, rights, co-write
Reports: system report, scout report, reflection
Fundo: fundo session, fundo release, fundo identity
Stack: restart stack, restart chief
Cassandra: cassandra [anything] — switches to executive assistant
"""


def stack_restart_intent(text: str) -> bool:
    """True when user wants to restart the Chief/Cassandra stack."""
    t = text.lower().strip()
    return any(t == phrase or t.startswith(phrase) for phrase in (
        "restart stack", "restart chief", "restart the stack", "reload stack",
        "restart openclaw", "reboot stack",
    ))


def _hitl_command(text: str) -> tuple[str, str] | None:
    """Return (decision, token) if text is a /hitl_approve or /hitl_deny command.

    decision is 'Y' (approve) or 'N' (deny).
    Returns None if the text does not match.
    """
    t = text.strip()
    t_lower = t.lower()
    if t_lower.startswith("/hitl_approve "):
        return "Y", t[len("/hitl_approve "):].strip()
    if t_lower.startswith("/hitl_deny "):
        return "N", t[len("/hitl_deny "):].strip()
    return None


def _looks_like_approval_reply(text: str) -> bool:
    """True for CODE DECISION-shaped approval replies."""
    return bool(re.match(r"^[A-Z0-9]{4}\s+(?:1|2|3|YES|NO|APPROVE|DENY)\b", text.strip(), re.I))


def _operator_refusal_reply(text: str) -> str | None:
    """Task 141 refusal-first tap. Fail-open: guard errors never block routing."""
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent="chief", surface="chief_router")
    except Exception:
        return None


# Task 143 (CLASS #4): bare-status doctrine. A bare "status?" gets a short, current,
# Chief-scoped answer (services health + builds/approvals pending) built deterministically
# from live read-models -- no model call, distinct from _chief_fallback_reply's LLM path and
# from chief_nli's album-session-scoped status matcher.
_BARE_STATUS_PHRASES = frozenset(
    {
        "status",
        "status update",
        "status check",
        "status please",
        "quick status",
        "whats the status",
        "what is the status",
        "give me a status",
        "give me a status update",
    }
)
_CHIEF_STATUS_FRESHNESS_SLA_DAYS = 3


def _is_bare_status_query(text: str) -> bool:
    stripped = str(text or "").strip().rstrip("?!.").strip()
    normalized = stripped.lower().replace("'", "")
    normalized = " ".join(normalized.split())
    return normalized in _BARE_STATUS_PHRASES


def _read_json_read_model(root: _Path, filename: str) -> tuple[dict, _Path]:
    path = root / filename
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, path
    return (payload if isinstance(payload, dict) else {}), path


def _read_model_stale_days(payload: dict) -> int | None:
    from read_model_freshness_audit import _parse_date, _timestamp_from_payload, _today

    if not payload:
        return None
    parsed = _parse_date(_timestamp_from_payload(payload))
    if parsed is None:
        return None
    return (_today() - parsed).days


def build_chief_bare_status_answer() -> str:
    root = _Path("generated/read_models")
    presence_payload, _ = _read_json_read_model(root, "agent_presence.json")
    rail_payload, _ = _read_json_read_model(root, "chief_status_rail.json")
    board_payload, _ = _read_json_read_model(root, "work_board.json")

    lines: list[str] = []
    freshness_excluded_sources: list[str] = []

    def _usable(payload: dict, source: str) -> bool:
        if not payload:
            return False
        days = _read_model_stale_days(payload)
        if days is None or days > _CHIEF_STATUS_FRESHNESS_SLA_DAYS:
            freshness_excluded_sources.append(source)
            return False
        return True

    if _usable(presence_payload, "agent_presence.json"):
        online = presence_payload.get("online_count")
        total = presence_payload.get("agent_count")
        lines.append(f"Services: {online}/{total} agents online.")

    if _usable(rail_payload, "chief_status_rail.json"):
        rail_status = str(rail_payload.get("chief_current_status") or "").strip()
        if rail_status:
            lines.append(f"Rail: {rail_status}.")

    if _usable(board_payload, "work_board.json"):
        pending_approval = board_payload.get("pending_approval_count")
        needs_review = board_payload.get("needs_review_count")
        lines.append(f"Builds: {pending_approval} pending approval, {needs_review} need review.")

    if not lines:
        lines.append(
            "I don't have current status data to report -- the usual read models are missing, stale, or unverifiable."
        )
    if freshness_excluded_sources:
        # ── Task 174 (per Task 164 human-alias doctrine): the operator-visible
        # note shows a COUNT, never raw internal source filenames — identical
        # to the maestro_cassandra_responder bare-status note. Exact source
        # names remain in the read models themselves; only the operator
        # surface is aliased.
        _excluded_count = len(freshness_excluded_sources)
        lines.append(
            f"({_excluded_count} stale source{'s' if _excluded_count != 1 else ''} excluded)"
        )
    return "\n".join(lines)


def _route_message_inner(text: str, *, first_touch_receipt=None) -> dict:
    # Task 151: typed contract adapter at Chief's real router.  This runs
    # before append_history/session mutation.  Strict authority tokens are
    # labeled PASS_THROUGH and continue to the existing ID-bound parser;
    # semantic voting can never authorize them.
    _contract_context = None
    _preserve_contract = None
    try:
        from first_touch_decision import valid_pass_through_marker

        _refusal_evaluated = valid_pass_through_marker(
            first_touch_receipt,
            text=text,
            agent="chief",
        )
    except Exception:
        _refusal_evaluated = False
    try:
        from typed_contract_decision import (
            ContractContext,
            DecisionAction,
            HandoffResult,
            active_session_from_mapping,
            decide_contract,
            preserve_session_on_error,
            semantic_vote_enabled_for_adapter,
        )
        _preserve_contract = preserve_session_on_error

        _contract_session = load_session()
        _contract_active = active_session_from_mapping(_contract_session)
        if _contract_active and str(_contract_session.get("active_workflow") or "") == "billing":
            # Task 142 owns billing-session TTL/surface expiry.  The typed
            # layer must not preserve a stale session before billing_handle
            # gets the chance to expire and clear it.
            try:
                from clarify_session_contract import (
                    clarify_session_expired as _clarify_session_expired,
                    clarify_session_scope_ok as _clarify_session_scope_ok,
                )

                _billing_session = _contract_session.get("workflow_state")
                _contract_active = bool(
                    isinstance(_billing_session, dict)
                    and not _clarify_session_expired(_billing_session)
                    and _clarify_session_scope_ok(_billing_session, surface=BILLING_SURFACE)
                )
            except Exception:
                # Eligibility uncertainty cannot turn a possibly stale lease
                # into an active one.  Fall through to the established owner.
                _contract_active = False
        try:
            _authority_pending = bool(has_pending_approval() or has_pending_choice())
        except Exception:
            _authority_pending = False
        _contract_context = ContractContext(
            agent="chief",
            surface="chief_router",
            active_session=_contract_active,
            session_kind=str(_contract_session.get("active_workflow") or ""),
            session_field=str(_contract_session.get("last_field") or ""),
            authority_pending=_authority_pending,
            session_snapshot=dict(_contract_session),
        )

        def _stage_handoff(raw_text: str, _context: ContractContext) -> HandoffResult:
            from workflow_package_queue import (
                DEFAULT_SQLITE_PATH,
                classify_workflow_route,
                render_cassandra_nudge_handoff_reply,
                render_live_arts_handoff_reply,
                stage_cassandra_receivables_nudge_handoff,
                stage_live_arts_invoice_handoff,
            )

            workflow_ref = classify_workflow_route(raw_text).workflow_ref
            if workflow_ref == "cassandra_receivables_nudge_handoff":
                staged = stage_cassandra_receivables_nudge_handoff(
                    raw_text, source_surface="chief_router", sqlite_path=DEFAULT_SQLITE_PATH
                )
                _reply = render_cassandra_nudge_handoff_reply(staged)
            elif workflow_ref == "live_arts_md_invoice_workflow":
                staged = stage_live_arts_invoice_handoff(
                    raw_text, source_surface="chief_router", sqlite_path=DEFAULT_SQLITE_PATH
                )
                _reply = render_live_arts_handoff_reply(staged)
            else:
                raise ValueError("canonical workflow-route owner returned no staged route")
            return HandoffResult(
                reply=_reply,
                receipt_pointer=str(staged["receipt"]["receipt_ref"]),
                package_id=str(staged["package"]["package_id"]),
            )

        def _session_answer(raw_text: str) -> bool:
            if str(_contract_session.get("active_workflow") or "") != "billing":
                return False
            try:
                from chief_billing_brain import get_questions, looks_like_correction

                if looks_like_correction(raw_text):
                    return True
                questions = get_questions(str(_billing_session.get("mode") or ""))
                step = int(_billing_session.get("step") or 0)
                field = str(questions[step][0]) if 0 <= step < len(questions) else ""
                candidate = str(raw_text or "").strip()
                if field in {"amount_total", "deposit_amount", "payment_amount", "amount_received"}:
                    return bool(re.search(r"(?:\$\s*)?\d+(?:[,.]\d{1,2})?", candidate))
                if field in {"service_date", "due_date", "payment_date", "next_follow_up_date"}:
                    return bool(
                        re.search(r"\b\d{1,4}[-/]\d{1,2}(?:[-/]\d{1,4})?\b", candidate)
                        or re.search(
                            r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                            r"january|february|march|april|may|june|july|august|september|october|november|december)\b",
                            candidate,
                            re.IGNORECASE,
                        )
                    )
                if field == "client_email":
                    return bool(re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", candidate))
                if field == "notes":
                    return candidate.lower() in {"none", "no", "no notes", "nothing", "n/a"}
                return False
            except Exception:
                return False

        _contract_decision = decide_contract(
            text,
            context=_contract_context,
            status_renderer=build_chief_bare_status_answer,
            handoff_stager=_stage_handoff,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter(
                "chief", default=True
            ),
            session_answer_predicate=_session_answer,
            first_touch_receipt=first_touch_receipt,
        )
        _refusal_evaluated = True
    except Exception as exc:
        print(
            f"[typed_contract][chief] {type(exc).__name__}; "
            f"active_session={bool(_contract_context and _contract_context.active_session)}",
            flush=True,
        )
        if _contract_context is not None and _contract_context.active_session and _preserve_contract is not None:
            _contract_decision = _preserve_contract(
                text,
                context=_contract_context,
                error_type=type(exc).__name__,
            )
        else:
            _contract_decision = None

    if _contract_decision is not None and not _contract_decision.handled:
        try:
            from vote_timeout_clarification import warm_clarification_for_vote_timeout

            _timeout_reply = warm_clarification_for_vote_timeout(
                text,
                _contract_decision,
            )
        except Exception:
            _timeout_reply = None
        if _timeout_reply is not None:
            return {
                "intent": "typed_contract_vote_timeout_clarification",
                "reply": _timeout_reply,
                "send_performed": False,
                "ledger_touched": False,
                "workflow_package_staged": False,
                "contract_decision": _contract_decision.receipt.to_dict(),
                "contract_matches": [
                    label.value for label in _contract_decision.matches
                ],
            }

    if _contract_decision is not None and _contract_decision.handled:
        _intent_by_label = {
            "refusal": "operator_refusal_guard",
            "status": "chief_bare_status_readback",
            "identity": "identity_persona_core",
            "low_coherence": "gibberish_low_coherence",
            "route_instruction": "live_arts_invoice_handoff",
            "money_read": "money_status",
            "guardian_gate_narration": "guardian_gate_narration",
            "unresolved": "typed_contract_session_preserved",
        }
        return {
            "intent": _intent_by_label.get(_contract_decision.label.value, _contract_decision.label.value),
            "reply": str(_contract_decision.reply or ""),
            "send_performed": False,
            "ledger_touched": False,
            "workflow_package_staged": _contract_decision.action is DecisionAction.STAGE_HANDOFF,
            "contract_decision": _contract_decision.receipt.to_dict(),
            "contract_matches": [label.value for label in _contract_decision.matches],
        }

    # ── Refusal-first guard (task 141) — the pipeline's FIRST tap, before the
    # approval gate, client intake, clarify sessions, NLI, or any model call.
    # Destructive/money-movement/gate-bypass asks get an instant plain-English
    # refusal naming the gate; everything else continues untouched.
    _refusal = None if _refusal_evaluated else _operator_refusal_reply(text)
    if _refusal is not None:
        return {
            "intent": "operator_refusal_guard",
            "reply": _refusal,
            "send_performed": False,
            "ledger_touched": False,
        }

    # ── Identity persona core (task 142 hook, task 145 wiring) — SECOND tap,
    # before the approval gate or any model call. Task 142 built
    # is_identity_question/identity_persona_reply and wired them into
    # maestro_cassandra_responder.answer_frontdoor_chat -- Chief's PROBE path,
    # not his REAL Telegram surface (chief_router.route_message). Without
    # this tap, "who are you and what do you do for me?" fell through to
    # _chief_fallback_reply's model call (classify_nonapproval_prompt's
    # "capability" intent doesn't match literal "who are you" phrasing
    # either, so the existing canned-string bank was never reachable for
    # this exact ask). Deterministic and packet-free -- no cross-domain
    # bleed is possible.
    try:
        from protected_generate import identity_persona_reply, is_identity_question

        if is_identity_question(text):
            return {"intent": "identity_persona_core", "reply": identity_persona_reply("chief")}
    except Exception:
        pass

    t_lower = text.strip().lower()
    t_upper = text.strip().upper()

    # ── Bare-status short-circuit (task 143) — SECOND tap, before the approval gate,
    # session machinery, or _chief_fallback_reply's model call. Distinct from chief_nli's
    # album-session-scoped status matcher (which needs an active workflow session to be
    # meaningful) and from _chief_fallback_reply's LLM fallback (pass-1: bare "status?" got
    # "no specific operational response" because looks_like_inspection/scheduler_intent both
    # require multi-word phrases a bare "status?" lacks).
    if _is_bare_status_query(text):
        return {"intent": "chief_bare_status_readback", "reply": build_chief_bare_status_answer()}

    # ── Approval gate — HIGHEST PRIORITY. Claude Code approvals interrupt everything.
    # Requires CODE DECISION format (e.g. "A3F2 1") — same model as Guardian.
    # Also intercepts bare 1/2/3/YES/NO to return a format rejection rather than
    # falling through to unrelated routing. Both paths enforce the same reply-code model.
    _approval_reply_like = _looks_like_approval_reply(text)
    if has_pending_approval():
        _t = text.strip()
        _is_approval_attempt = (
            _approval_reply_like                            # CODE DECISION (with optional copied label)
            or bool(re.match(r'^[A-Z0-9]{4}\s', _t, re.I)) # CODE plus any decision text
            or _t.upper() in ("1", "2", "3", "YES", "NO")  # bare reply → format error
        )
        if _is_approval_attempt:
            _pending_id, _options = get_pending_info()
            decision, error = parse_reply_code(_t, _pending_id, options=_options)
            if decision:
                reply = record_decision(decision, expected_id=_pending_id)
            else:
                reply = error
            return {"intent": "approval_response", "reply": reply}

    if _approval_reply_like:
        return {
            "intent": "approval_response",
            "reply": "Expired or unknown approval code. No approval was applied. Request a fresh approval.",
        }

    if not has_pending_approval():
        safe_response = nonapproval_response_for_text(text, surface="chief")
        if safe_response is not None:
            return safe_response.as_route_result()

    # ── Approval bridge — Chief workflow multi-choice (1/2/3/approve/deny/status) ──
    # Note: approval brain (Claude Code permissions) is checked ABOVE this and
    # takes absolute priority. The bridge (Chief multi-choice prompts) is checked
    # here. During an active approval gate, has_pending_approval() fires first so
    # bridge never runs concurrently with an active approval request.
    _BRIDGE_TOKENS = ("1", "2", "3", "approve", "deny")
    if has_pending_choice() and (t_lower in _BRIDGE_TOKENS or
                                  t_lower in ("status", "approval status", "choice status")):
        replies = bridge_handle(text)
        return {"intent": "choice_response", "replies": replies}

    # ── SMS draft confirmation ─────────────────────────────────────────────────
    if sms_pending_draft() and t_upper in ("YES", "NO"):
        replies = sms_confirm_send(t_upper == "YES")
        return {"intent": "sms_send", "replies": replies}

    # ── Scheduler — before cancel so "continue"/"stop" work during active blocks ─
    if scheduler_intent(text):
        replies = scheduler_handle(text)
        return {"intent": "scheduler", "replies": replies}

    if artifact_transform_intent(text):
        return {
            "intent": "artifact_transform",
            "replies": _chief_fallback_reply(text),
        }

    # ── Batch planner — before NLI so "what should I do next on the album" hits here ─
    if batch_intent(text):
        replies = batch_handle(text)
        return {"intent": "batch_query", "replies": replies}

    # ── NLI layer — natural status/trust language ──────────────────────────────
    # Catches conversational status queries ("where are we at", "did you save that")
    # before the session machinery runs. Additive only — falls through if no match.
    if detect_nli_query(text):
        replies = nli_handle(text)
        if replies:
            return {"intent": "nli_status", "replies": replies}

    session = load_session()
    append_history("user", text)

    # ── Cassandra — relational assistant; explicit prefix or conversational query ─
    # Owns: orientation, priorities, context, relational continuity.
    # Does NOT handle: billing, album, approvals, operational execution.
    if cassandra_intent(text):
        return {"intent": "cassandra", "replies": cassandra_handle(text, session)}

    if help_intent(text):
        return {"intent": "generic", "reply": _HELP_TEXT}

    # ── Ops intake — top-level; escapes correction and active-session routing ─
    # Recognized by explicit prefix: "Ops update:", "Brain dump:", etc.
    # During album focus: defers silently; delivers summary after session closes.
    if ops_intake_intent(text):
        album_active = (session.get("status") == "active"
                        and session.get("active_workflow") == "album")
        if album_active:
            ops_save_deferred(text)
            return {"intent": "ops_intake", "replies": [
                "Captured. Album focus is on — I'll surface this after your session."
            ]}
        # Clear any stale non-album active session so subsequent messages are
        # not intercepted by a lingering billing or other workflow state.
        if session.get("status") == "active":
            reset_session()
        return {"intent": "ops_intake", "replies": ops_handle(text)}

    if looks_like_cancel(text):
        mark_cancelled()
        return {
            "intent": "cancel",
            "reply": "Current workflow cancelled.",
        }

    if looks_like_correction(text):
        return {
            "intent": "correction",
            "reply": "Correction noted. We need correction handling wired into the active workflow next.",
        }

    if looks_like_inspection(text):
        return {
            "intent": "inspection",
            "reply": None,
        }

    if morning_inspection_intent(text):
        replies = handle_morning_inspection(text)
        return {"intent": "morning_inspection", "replies": replies}

    if morning_followup_intent(text):
        replies = handle_morning_followup(text)
        return {"intent": "morning_followup", "replies": replies}

    # ── Explicit brainstorm commands escape any lingering active session ─────────
    # Must run before billing/album active session checks so "brainstorm" is
    # never swallowed by a stale billing FOLLOWUP or album workflow.
    _t = text.lower().strip()
    if any(_t.startswith(k) or _t == k for k in (
        "brainstorm", "capture idea", "capture", "new idea", "idea:",
    )):
        reset_session()
        if brainstorm_watch_intent(text):
            replies = brainstorm_watch_handle(text)
            return {"intent": "brainstorm_watch", "replies": replies}
        if brainstorm_queue_intent(text):
            replies = brainstorm_router_handle(text)
            return {"intent": "brainstorm_queue", "replies": replies}
        replies = brainstorm_handle(text)
        return {"intent": "brainstorm_capture", "replies": replies}

    # ── Billing clarify-session resume — task 142 ordering contract ──────────
    # refusal check (the 141 tap at the very top of _route_message_inner) →
    # session-relevance check (inside billing_handle: TTL, surface scope,
    # unrelated-input pass-through) → session resume. The live 12h stuck
    # session ate a delete bait; now billing_handle returns [] whenever the
    # session declines to capture (expired / unrelated / desynced inner state),
    # and routing continues as if no session existed.
    if session.get("status") == "active" and session.get("active_workflow") == "billing":
        replies = billing_handle(text)
        if replies:
            return {
                "intent": "billing_continue",
                "replies": replies,
            }
        # Session refused capture and (if stale) already reset itself —
        # fall through to normal routing for this message.

    # ── Explicit intents checked before billing keyword match ─────────────────
    # These must run before billing_mode_from_text to prevent collisions
    # (e.g. "log call...invoice" triggering billing instead of phone_log)

    if email_intent(text):
        replies = email_handle(text)
        return {"intent": "email_draft", "replies": replies}

    if sms_intent(text):
        replies = sms_handle(text)
        return {"intent": "sms_draft", "replies": replies}

    if phone_intent(text):
        replies = phone_handle(text)
        return {"intent": "phone_log", "replies": replies}

    if cpa_intent(text):
        replies = cpa_handle(text)
        return {"intent": "cpa_query", "replies": replies}

    if musiclaw_intent(text):
        replies = musiclaw_handle(text)
        return {"intent": "musiclaw_query", "replies": replies}

    if publishing_intent(text):
        replies = publishing_handle(text)
        return {"intent": "publishing_query", "replies": replies}

    if content_calendar_intent(text):
        replies = content_handle(text)
        return {"intent": "content_calendar", "replies": replies}

    if brand_guide_intent(text):
        replies = brand_handle(text)
        return {"intent": "brand_guide", "replies": replies}

    if fin_fortress_intent(text):
        replies = fin_fortress_handle(text)
        return {"intent": "fin_fortress", "replies": replies}

    if tax_sorter_intent(text):
        replies = tax_sorter_handle(text)
        return {"intent": "tax_sort", "replies": replies}

    if financial_intent(text):
        replies = financial_handle(text)
        return {"intent": "financial_report", "replies": replies}

    if analytics_intent(text):
        replies = analytics_handle(text)
        return {"intent": "analytics_report", "replies": replies}

    if goals_intent(text):
        replies = goals_handle(text)
        return {"intent": "goals_check", "replies": replies}

    if momentum_intent(text):
        replies = momentum_handle(text)
        return {"intent": "momentum_check", "replies": replies}

    if backup_intent(text):
        replies = backup_handle(text)
        return {"intent": "backup_status", "replies": replies}

    if brainstorm_watch_intent(text):
        replies = brainstorm_watch_handle(text)
        return {"intent": "brainstorm_watch", "replies": replies}

    if brainstorm_queue_intent(text):
        replies = brainstorm_router_handle(text)
        return {"intent": "brainstorm_queue", "replies": replies}

    if brainstorm_capture_intent(text):
        replies = brainstorm_handle(text)
        return {"intent": "brainstorm_capture", "replies": replies}

    if trinity_intent(text):
        replies = trinity_handle(text)
        return {"intent": "trinity_check", "replies": replies}

    if any(k in t_lower for k in ("focus status", "focus shield", "focus held",
                                   "held items", "whats held", "what's held",
                                   "surface now", "end of day")):
        replies = focus_shield_handle(text)
        return {"intent": "focus_status", "replies": replies}

    if queue_intent(text):
        replies = queue_handle(text)
        return {"intent": "queue_request", "replies": replies}

    if calendar_intent(text):
        replies = calendar_handle(text)
        return {"intent": "calendar_query", "replies": replies}

    if mix_brief_intent(text):
        replies = album_mixer_handle(text)
        return {"intent": "mix_brief", "replies": replies}

    if fundo_release_intent(text):
        replies = fundo_release_handle(text)
        return {"intent": "fundo_release", "replies": replies}

    if fundo_session_intent(text):
        replies = fundo_session_handle(text)
        return {"intent": "fundo_session", "replies": replies}

    if fundo_identity_intent(text):
        replies = fundo_identity_handle(text)
        return {"intent": "fundo_identity", "replies": replies}

    if website_qa_intent(text):
        replies = website_qa_handle(text)
        return {"intent": "website_qa", "replies": replies}

    if website_coordinator_intent(text):
        replies = website_coordinator_handle(text)
        return {"intent": "website_coordinator", "replies": replies}

    if website_creative_intent(text):
        replies = website_creative_handle(text)
        return {"intent": "website_creative", "replies": replies}

    billing_mode = billing_mode_from_text(text)
    if billing_mode:
        prefilled = _llm_prefill_billing(text, billing_mode)
        questions = billing_questions(billing_mode)
        # Advance step past any pre-filled fields
        first_step = 0
        while first_step < len(questions) and questions[first_step][0] in prefilled:
            first_step += 1
        set_workflow("billing", billing_mode)
        # Task 142: stamp the clarify session (TTL lease + surface scope).
        set_workflow_state(stamp_clarify_session({
            "active": True,
            "mode": billing_mode,
            "step": first_step,
            "answers": prefilled,
            "last_field": None,
            "last_prompt": None,
        }, surface=BILLING_SURFACE))
        if first_step < len(questions):
            first_q = questions[first_step][1]
            if prefilled:
                first_q = f"Got it — {_prefill_summary(prefilled)}. {first_q}"
        else:
            first_q = "All fields captured. Type 'confirm' to save."
        return {
            "intent": "billing_start",
            "mode": billing_mode,
            "reply": first_q,
        }

    # ── Brainstorm active session (second turn: waiting for idea text) ───────────
    if (session.get("status") == "active"
            and session.get("active_workflow") == "brainstorm"
            and get_workflow_state().get("active", False)):
        replies = brainstorm_handle(text)
        return {"intent": "brainstorm_capture", "replies": replies}

    if session.get("status") == "active" and session.get("active_workflow") == "album_arc":
        replies = album_arc_handle(text)
        return {"intent": "album_arc_continue", "replies": replies}

    if album_arc_intent(text):
        set_workflow("album_arc", None)
        set_workflow_state({"active": True, "arc_active": True, "phase": "arc"})
        return {
            "intent": "album_arc_start",
            "reply": "Running album arc analysis across all songs...",
        }

    # ── Album status — always available regardless of session state ──────────
    if t_lower in ("album status", "session status") or \
            re.match(r"^album\s+status\b", t_lower):
        replies = album_status_handle()
        return {"intent": "album_status", "replies": replies}

    if (session.get("status") == "active"
            and session.get("active_workflow") == "album"
            and get_workflow_state().get("active", False)):
        replies = album_handle(text)
        return {
            "intent": "album_continue",
            "replies": replies,
        }

    if session.get("status") != "active" and looks_like_quick_update(text):
        replies = album_quick_update(text)
        return {
            "intent": "quick_song_update",
            "replies": replies,
        }

    if marketing_intent(text):
        replies = marketing_handle(text)
        if _marketing_is_log_update(text):
            sub = "content_log_update"
        elif _marketing_is_draft(text):
            sub = "content_draft"
        else:
            sub = "marketing_ideas"
        return {"intent": sub, "replies": replies}

    if reflection_intent(text):
        replies = reflection_handle(text)
        return {"intent": "reflection_report", "replies": replies}

    if reporter_intent(text):
        replies = reporter_handle(text)
        return {"intent": "system_report", "replies": replies}

    if scout_intent(text):
        replies = scout_handle(text)
        return {"intent": "scout_report", "replies": replies}

    if integration_intent(text):
        replies = integration_handle(text)
        return {"intent": "integration_proposals", "replies": replies}

    if album_intent(text):
        # Always start completely fresh regardless of any lingering session state
        reset_session()
        set_workflow("album", None)
        set_workflow_state({
            "active": True,
            "phase": "song_name",
            "song_title": "",
            "topics_covered": [],
            "notes": {},
            "structured": {},
            "dynamic_columns": [],
            "history": [],
            "turn": 0,
            "arc_active": False,
            "last_topic_asked": None,
            "last_topic_stack": [],
        })
        return {
            "intent": "album_start",
            "reply": "What song are we working on?",
        }

    hitl_cmd = _hitl_command(text)
    if hitl_cmd is not None:
        decision, token = hitl_cmd
        try:
            from hitl_notification_service import handle_callback as _hitl_cb
            result = _hitl_cb(token, approved_by="telegram_command")
            if result["ok"]:
                label = "Approved" if result["decision"] == "Y" else "Denied"
                reply = f"HITL {result['action_id']}: {label}."
            else:
                reply = f"HITL callback failed: {result.get('error', 'unknown')}."
        except Exception as _e:
            reply = f"HITL command error: {_e}"
        return {"intent": "hitl_decision", "replies": [reply]}

    if stack_restart_intent(text):
        import subprocess, threading
        def _do_restart():
            import time; time.sleep(3)
            subprocess.Popen(
                ["bash", "/home/openclaw/start_chief.sh"],
                stdout=open("/mnt/c/OpenClaw/logs/restart.out", "w"),
                stderr=subprocess.STDOUT,
            )
        threading.Thread(target=_do_restart, daemon=True).start()
        return {"intent": "stack_restart", "replies": [
            "Restarting the stack now. Back in a few seconds."
        ]}

    # LLM fallback: try to classify when keyword matching found nothing
    llm_intent = _llm_classify_intent(text)
    if llm_intent in ("invoice", "payment", "followup", "receipt"):
        billing_mode = llm_intent.upper()
        prefilled = _llm_prefill_billing(text, billing_mode)
        questions = billing_questions(billing_mode)
        first_step = 0
        while first_step < len(questions) and questions[first_step][0] in prefilled:
            first_step += 1
        set_workflow("billing", billing_mode)
        # Task 142: stamp the clarify session (TTL lease + surface scope).
        set_workflow_state(stamp_clarify_session({
            "active": True,
            "mode": billing_mode,
            "step": first_step,
            "answers": prefilled,
            "last_field": None,
            "last_prompt": None,
        }, surface=BILLING_SURFACE))
        if first_step < len(questions):
            first_q = questions[first_step][1]
            if prefilled:
                first_q = f"Got it — {_prefill_summary(prefilled)}. {first_q}"
        else:
            first_q = "All fields captured. Type 'confirm' to save."
        return {
            "intent": "billing_start",
            "mode": billing_mode,
            "reply": first_q,
        }

    if llm_intent == "album":
        reset_session()
        set_workflow("album", None)
        set_workflow_state({
            "active": True,
            "phase": "song_name",
            "song_title": "",
            "topics_covered": [],
            "notes": {},
            "structured": {},
            "dynamic_columns": [],
            "history": [],
            "turn": 0,
            "arc_active": False,
            "last_topic_asked": None,
            "last_topic_stack": [],
        })
        return {
            "intent": "album_start",
            "reply": "What song are we working on?",
        }

    if llm_intent == "cpa":
        replies = cpa_handle(text)
        return {"intent": "cpa_query", "replies": replies}

    if llm_intent == "calendar":
        replies = calendar_handle(text)
        return {"intent": "calendar_query", "replies": replies}

    if llm_intent == "analytics":
        replies = analytics_handle(text)
        return {"intent": "analytics_report", "replies": replies}

    if llm_intent == "goals":
        replies = goals_handle(text)
        return {"intent": "goals_check", "replies": replies}

    return {
        "intent": "generic",
        "replies": _chief_fallback_reply(text),
    }


_CHIEF_SYSTEM_PROMPT = """\
You are Chief, the lead AI operations coordinator for OpenClaw Studios.
OpenClaw is an independent music label and production house owned by H. Winship Wheatley IV.

Your character: direct, operational, efficient, and slightly technical.
You handle the heavy lifting: billing, album session management, approvals, and complex analysis.
You are the primary link between the operator and the system's execution layers.

Response discipline:
- Lead with the answer or action.
- Be concise. No flowery language or preamble.
- If the user asks for something outside your operational domains (billing, album, execution),
  acknowledge it briefly but don't over-promise.
- Maintain a professional, results-oriented partnership with Winship.
"""

def _chief_fallback_reply(text: str) -> list[str]:
    """Last-resort conversational fallback for Chief."""
    from adaptive_model_call import adaptive_ollama_text
    from chief_output_utils import tts_clean
    from cassandra_brain import build_context_snapshot

    context = build_context_snapshot()
    prompt = (
        f"{_CHIEF_SYSTEM_PROMPT}\n\n"
        f"Current system context:\n{context}\n\n"
        f"User: {text}\n"
        f"Chief:"
    )

    try:
        # Interactive lane — the operator is waiting on Telegram. Model choice belongs to
        # the adaptive selector (fit-walled): a hardcoded qwen3.6:latest (27G) here
        # swap-killed the box mid-round on 2026-07-09.
        reply = _local_model_call(prompt, timeout=120, task_class="chief_user_reply")
        if not reply:
            return ["I processed that, but I have no specific operational response. Anything else?"]
        return [tts_clean(reply)]
    except Exception as e:
        print(f"[chief_router] fallback reply error: {e}", flush=True)
        return ["Routed to Chief (Error)."]


def route_message(text: str, *, first_touch_receipt=None) -> dict:
    """Public entry point. Delegates to inner router, then logs the decision."""
    global _llm_fallback_fired
    _llm_fallback_fired = False
    _h = _hashlib.sha256(text.encode()).hexdigest()[:8]
    try:
        result = _route_message_inner(text, first_touch_receipt=first_touch_receipt)
    except Exception as e:
        print(f"[chief_router] _route_message_inner error: {e}", flush=True)
        result = {"intent": "error", "reply": "Chief hit a snag routing that. Try again."}
    intent = result.get("intent", "unknown")
    try:
        from vote_timeout_clarification import is_outside_session_vote_failure

        _vote_timeout = is_outside_session_vote_failure(
            result.get("contract_decision")
        )
    except Exception:
        _vote_timeout = False
    if not _vote_timeout:
        _log_route(_h, intent, _llm_fallback_fired)
    return _guard_route_result(result, source_request=text)


def _guard_route_result(result: dict, *, source_request: str = "") -> dict:
    """Task 144 (CLASS #5): guard every reply/replies field before it leaves the router --
    covers all of _route_message_inner's branches (album/billing/CPA/analytics/goals/generic
    fallback) from one wrap point. Fail-open: import/guard errors leave the result
    untouched."""
    try:
        from operator_surface_guard import guard_operator_reply
    except Exception:
        safe = "Chief couldn't safely render that answer just now. Nothing was sent or changed."
        result = dict(result)
        if isinstance(result.get("reply"), str):
            result["reply"] = safe
        if isinstance(result.get("replies"), list):
            result["replies"] = [
                safe if isinstance(item, str) else item for item in result["replies"]
            ]
        return result
    if isinstance(result.get("reply"), str):
        result = {
            **result,
            "reply": guard_operator_reply(
                result["reply"],
                agent_role="CHIEF",
                source_request=source_request,
            ),
        }
    if isinstance(result.get("replies"), list):
        result = {
            **result,
            "replies": [
                guard_operator_reply(
                    r,
                    agent_role="CHIEF",
                    source_request=source_request,
                )
                if isinstance(r, str)
                else r
                for r in result["replies"]
            ],
        }
    contract_receipt = result.get("contract_decision")
    if isinstance(contract_receipt, dict):
        try:
            from vote_timeout_clarification import enforce_vote_timeout_output

            if isinstance(result.get("reply"), str):
                result = {
                    **result,
                    "reply": enforce_vote_timeout_output(
                        source_request,
                        result["reply"],
                        contract_receipt,
                    ),
                }
            if isinstance(result.get("replies"), list):
                result = {
                    **result,
                    "replies": [
                        enforce_vote_timeout_output(
                            source_request,
                            item,
                            contract_receipt,
                        )
                        if isinstance(item, str)
                        else item
                        for item in result["replies"]
                    ],
                }
        except Exception:
            pass
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(route_message("I need to send an invoice"), indent=2))
