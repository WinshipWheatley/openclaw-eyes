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
from chief_billing_brain import handle as billing_handle, get_questions as billing_questions
from chief_album_brain import (
    handle as album_handle,
    handle_arc as album_arc_handle,
    handle_quick_update as album_quick_update,
    _match_song_title,
    _ALBUM_SONGS,
)


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
