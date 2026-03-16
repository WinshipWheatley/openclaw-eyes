import re
from chief_session_manager import (
    load_session,
    save_session,
    set_workflow,
    set_workflow_state,
    append_history,
    mark_cancelled,
    reset_session,
)
from chief_billing_brain import handle as billing_handle, get_questions as billing_questions
from chief_album_brain import handle as album_handle


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
        set_workflow("billing", billing_mode)
        set_workflow_state({
            "active": True,
            "mode": billing_mode,
            "step": 0,
            "answers": {},
            "last_field": None,
            "last_prompt": None,
        })
        questions = billing_questions(billing_mode)
        first_q = questions[0][1] if questions else "Ready."
        return {
            "intent": "billing_start",
            "mode": billing_mode,
            "reply": first_q,
        }

    if session.get("status") == "active" and session.get("active_workflow") == "album":
        replies = album_handle(text)
        return {
            "intent": "album_continue",
            "replies": replies,
        }

    if album_intent(text):
        set_workflow("album", None)
        set_workflow_state({
            "active": True,
            "phase": "song_name",
            "step": 0,
            "answers": {},
            "version_count": 0,
            "current_version_index": 0,
            "session_started_at": None,
            "test_mode": False,
        })
        return {
            "intent": "album_start",
            "reply": (
                "Album review mode started. First settle the version. "
                "Then we do lane-by-lane diagnosis. "
                "For each lane, start with one of: done, needs work, needs review, "
                "needs re-record, not applicable, or unclear. "
                "You can also use normal phrases like review first, redo, solid, "
                "n/a, skip, or not sure. "
                "The CSV row writes after the full song review is complete.\n\n"
                "What song are we assessing?"
            ),
        }

    return {
        "intent": "generic",
        "reply": "Routed to Chief.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(route_message("I need to send an invoice"), indent=2))
