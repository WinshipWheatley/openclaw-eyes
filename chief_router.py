import re
from chief_llm import ollama_call, ollama_json
from chief_session_manager import (
    load_session,
    save_session,
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
)
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
    clear_pending_draft as sms_clear_draft,
)
from chief_email_brain import (
    handle as email_handle,
    get_pending_draft as email_pending_draft,
    confirm_send as email_confirm_send,
    clear_pending_draft as email_clear_draft,
)
from chief_calendar_brain import handle as calendar_handle
from chief_queue_brain import handle as queue_handle
from chief_trinity_brain import handle as trinity_handle
from chief_backup_brain import handle as backup_handle
from chief_financial_brain import handle as financial_handle
from chief_analytics_brain import handle as analytics_handle
from chief_goals_brain import handle as goals_handle
from chief_momentum_brain import handle as momentum_handle
from chief_fundo_session import handle as fundo_session_handle
from chief_fundo_identity import handle as fundo_identity_handle
from chief_fundo_release import handle as fundo_release_handle
from chief_website_creative import handle as website_creative_handle
from chief_website_coordinator import handle as website_coordinator_handle
from chief_website_qa import handle as website_qa_handle
from chief_billing_brain import handle as billing_handle, get_questions as billing_questions
from chief_content_brain import handle as content_handle
from chief_brand_brain import handle as brand_handle
from chief_marketing_brain import (
    handle as marketing_handle,
    _is_draft_request as _marketing_is_draft,
    _is_log_update as _marketing_is_log_update,
)
from chief_album_mixer import handle as album_mixer_handle
from chief_scheduler_brain import handle as scheduler_handle, _load as _sched_load
from chief_album_brain import (
    handle as album_handle,
    handle_arc as album_arc_handle,
    handle_quick_update as album_quick_update,
    _match_song_title,
    _ALBUM_SONGS,
)


def scheduler_intent(text: str) -> bool:
    t = text.lower().strip()
    # Explicit start / status commands
    if any(k in t for k in ("schedule ", "timer ", "start block", "work block",
                             "timer status", "scheduler status", "block status")):
        return True
    # Stop session — only intercept when scheduler is running/prompting
    if any(k in t for k in ("stop for now", "stop session", "done for now", "end session")):
        return True
    # Responses to end-of-block prompt — only when scheduler is in prompting state
    state = _sched_load()
    if state.get("status") == "prompting":
        if t in ("continue", "break", "take break", "take a break", "stop") or t.startswith("switch"):
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
    t = text.lower().strip()
    return any(k in t for k in [
        "send email", "email to", "draft email", "follow up email",
        "email ", "write an email", "send a follow up",
        "invoice email", "follow-up email", "email log",
        "sent emails", "email history", "outbox",
    ])


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


def album_arc_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in [
        "album arc", "arc mode", "album story", "track order",
        "lyric arc", "album analysis", "song order",
    ])


_CLASSIFY_PROMPT = """\
You are a music producer's assistant routing messages to the correct workflow.
Classify the message below into exactly one of these intent labels:
  invoice   — user wants to create or send an invoice to a client
  payment   — user is recording a payment received from a client
  followup  — user wants to set a follow-up reminder for a client
  receipt   — user wants to issue a receipt to a client
  album     — user wants to work on a song, mix, vocal, or album session
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


def _llm_classify_intent(text: str) -> str | None:
    """LLM fallback classifier. Returns intent label or None if unclear/error."""
    prompt = _CLASSIFY_PROMPT.format(text=text)
    result = ollama_call(prompt, timeout=10).lower().strip()
    valid = {"invoice", "payment", "followup", "receipt", "album"}
    return result if result in valid else None


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


def route_message(text: str) -> dict:
    # ── Approval gate — checked before ALL other routing ──────────────────────
    t_upper = text.strip().upper()
    if has_pending_approval() and t_upper in ("YES", "NO"):
        reply = record_decision(text)
        return {"intent": "approval_response", "reply": reply}

    # ── SMS draft confirmation ─────────────────────────────────────────────────
    if sms_pending_draft() and t_upper in ("YES", "NO"):
        replies = sms_confirm_send(t_upper == "YES")
        return {"intent": "sms_send", "replies": replies}

    # ── Email draft confirmation ───────────────────────────────────────────────
    if email_pending_draft() and t_upper in ("YES", "NO"):
        replies = email_confirm_send(t_upper == "YES")
        return {"intent": "email_send", "replies": replies}

    # ── Scheduler — before cancel so "continue"/"stop" work during active blocks ─
    if scheduler_intent(text):
        replies = scheduler_handle(text)
        return {"intent": "scheduler", "replies": replies}

    session = load_session()
    append_history("user", text)

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

    if session.get("status") == "active" and session.get("active_workflow") == "billing":
        replies = billing_handle(text)
        return {
            "intent": "billing_continue",
            "replies": replies,
        }

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

    if trinity_intent(text):
        replies = trinity_handle(text)
        return {"intent": "trinity_check", "replies": replies}

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
        set_workflow_state({
            "active": True,
            "mode": billing_mode,
            "step": first_step,
            "answers": prefilled,
            "last_field": None,
            "last_prompt": None,
        })
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
        set_workflow_state({
            "active": True,
            "mode": billing_mode,
            "step": first_step,
            "answers": prefilled,
            "last_field": None,
            "last_prompt": None,
        })
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

    return {
        "intent": "generic",
        "reply": "Routed to Chief.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(route_message("I need to send an invoice"), indent=2))
