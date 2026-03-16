import re
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

    return {
        "intent": "generic",
        "reply": "Routed to Chief.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(route_message("I need to send an invoice"), indent=2))
