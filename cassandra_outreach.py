
from __future__ import annotations

"""
cassandra_outreach.py

Draft-first pilot outreach flow for Cassandra inner-circle intro emails.

Usage:
    python3 /home/openclaw/cassandra_outreach.py --dry-run
    python3 /home/openclaw/cassandra_outreach.py
"""

def poll_gmail_unread_count() -> dict:
    """Poll Gmail for unread inbox count via broker."""
    from google_access_broker import call as broker_call
    return broker_call("cassandra", "google.gmail.unread_count", {})

def poll_gmail_recent_metadata(max_results: int = 10) -> dict:
    """Poll Gmail for recent inbox metadata via broker."""
    from google_access_broker import call as broker_call
    return broker_call("cassandra", "google.gmail.read.metadata", {"max_results": max_results})

def create_gmail_draft(email_addr: str, subject: str, body: str, review_inbox: str, review_status: str, review_detail: str) -> dict:
    """Abstraction for Gmail draft creation for correspondence. Returns a dict with keys:
    - ok: bool
    - result: broker result dict (if ok)
    - error: error string (if not ok)
    - review_status: passed through
    - review_detail: passed through
    """
    try:
        from google_access_broker import call as broker_call
        result = broker_call("cassandra", "google.gmail.draft.create", {
            "to":      email_addr,
            "cc":      review_inbox,
            "subject": subject,
            "body":    body,
        })
        return {"ok": True, "result": result, "review_status": review_status, "review_detail": review_detail}
    except Exception as e:
        return {"ok": False, "error": str(e), "review_status": review_status, "review_detail": review_detail}

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from cassandra_email_config import get_review_inbox
from chief_file_io import load_json, save_json
from finance_state import get_finance_status_answer

# ── Broker call import for test patching ──
try:
    from google_access_broker import call as broker_call
except ImportError:
    broker_call = None

_NICKNAMES_PATH = Path("/home/openclaw/contact_nicknames.json")
_OUTREACH_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_outreach.jsonl")
_PILOT_INTRO_TEMPLATE = Path("/home/openclaw/cassandra_inner_circle_pilot_intro.md")

_CORRESPONDENCE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl")

_SS_DRAFT             = "draft"
_SS_QUEUED            = "queued"
_SS_AWAITING_APPROVAL = "awaiting_approval"
_SS_SEND_ATTEMPTED    = "send_attempted"
_SS_SENT_CONFIRMED    = "sent_confirmed"

_EMAIL_THREAD_ANALYSIS_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_email_thread_analysis.jsonl")
_EMAIL_THREAD_STATE = Path("/mnt/c/OpenClaw/logs/cassandra_email_thread_state.json")
_EMAIL_THREAD_FOLLOWUP_DAYS = 4

_RECIPIENT_ORDER = ("draper", "dad", "mom")

_RECIPIENT_BLURBS = {
    "dad": "Financial questions are welcome too — invoices, payments, and anything in that lane.",
    "draper": "Work-related stuff is fair game too — projects, scheduling, and anything operational.",
    "mom": "Anything you're curious about is welcome — this is mostly a warm hello and a real-world test.",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_nicknames() -> dict:
    try:
        data = json.loads(_NICKNAMES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(key).lower(): value
        for key, value in data.items()
        if not str(key).startswith("_")
    }


def _resolve_contact_label(nickname: str) -> str:
    nicknames = _load_nicknames()
    value = nicknames.get(nickname.lower(), nickname)
    if isinstance(value, dict):
        for key in ("name", "display_name", "contact_name", "email"):
            resolved = str(value.get(key, "")).strip()
            if resolved:
                return resolved
        return nickname.title()
    resolved = str(value).strip()
    return resolved or nickname.title()


def _resolve_contact_email(nickname: str) -> tuple[str, str]:
    """
    Resolve nickname -> (email, display_name).

    contact_nicknames.json is the source of nickname mapping.
    Resolution order for the pilot path:
      1. inline email
      2. live Google Contacts lookup
      3. pinned_email fallback
    """
    nicknames = _load_nicknames()
    value = nicknames.get(nickname.lower(), nickname)

    pinned_email = ""
    if isinstance(value, dict):
        email = str(value.get("email", "")).strip()
        pinned_email = str(value.get("pinned_email", "")).strip()
        display_name = (
            str(value.get("display_name") or value.get("name") or value.get("contact_name") or nickname.title()).strip()
            or nickname.title()
        )
        if email:
            return email, display_name
        contact_label = display_name
    else:
        display_name = str(value).strip() or nickname.title()
        contact_label = str(value).strip() or nickname.title()

    from google_access_broker import call as broker_call

    result = broker_call("cassandra", "google.contacts.read", {"query": contact_label})
    if result.get("ok"):
        for contact in result.get("data") or []:
            email = str(contact.get("email", "")).strip()
            if email:
                display_name = str(contact.get("display_name", "")).strip() or contact_label
                return email, display_name
    else:
        raise RuntimeError(f"No contact email found for {nickname}.")

    if pinned_email:
        return pinned_email, display_name

    raise RuntimeError(f"Contact found for {nickname} but no email address is available.")


def _subject_for(display_name: str) -> str:
    return f"Hey {display_name} — an intro from Cassandra"


def _body_for(nickname: str, display_name: str) -> str:
    blurb = _RECIPIENT_BLURBS[nickname]
    template = _PILOT_INTRO_TEMPLATE.read_text(encoding="utf-8")
    return template.format(display_name=display_name, blurb=blurb).strip()


def _log_attempt(
    recipient: str,
    subject: str,
    status: str,
    detail: str = "",
    *,
    metadata: dict | None = None,
) -> None:
    entry = {
        "ts": _now(),
        "recipient": recipient,
        "subject": subject,
        "status": status,
    }
    if detail:
        entry["detail"] = detail
    if metadata:
        for key, value in metadata.items():
            if value not in (None, "", []):
                entry[key] = value

    try:
        _OUTREACH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _OUTREACH_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception as exc:
        print(f"[cassandra_outreach] log write failed: {exc}")


def _notify_winship(text: str) -> None:
    from cassandra_sender import send_message

    send_message(text)


def _safe_notify_winship(text: str) -> str:
    try:
        _notify_winship(text)
        return ""
    except Exception as exc:
        print(f"[cassandra_outreach] telegram notify failed: {exc}")
        return str(exc)


def build_outreach_messages() -> list[dict]:
    messages = []
    for nickname in _RECIPIENT_ORDER:
        display_name = _resolve_contact_label(nickname)
        subject = _subject_for(display_name)
        body = _body_for(nickname, display_name)
        messages.append(
            {
                "nickname": nickname,
                "display_name": display_name,
                "subject": subject,
                "body": body,
            }
        )
    return messages


def run_outreach(*, dry_run: bool = False, mode: str = "draft") -> list[dict]:
    """
    Build and optionally draft the outreach email set.

    mode:
        "draft" -- create brokered Gmail drafts for review (default)

    Returns a per-recipient result list for both dry runs and real execution.
    """
    if mode != "draft":
        raise RuntimeError("Cassandra outreach pilot is draft-only. No direct send path is enabled.")

    results: list[dict] = []
    from google_access_broker import call as broker_call
    review_inbox = get_review_inbox()

    for message in build_outreach_messages():
        nickname = message["nickname"]
        subject = message["subject"]

        if dry_run:
            email = ""
            status = "dry_run"
            detail = "not sent"
            metadata = {}
        else:
            try:
                email, resolved_name = _resolve_contact_email(nickname)
                message["email"] = email
                if resolved_name and resolved_name != message["display_name"]:
                    message["display_name"] = resolved_name
                    message["subject"] = _subject_for(resolved_name)
                    message["body"] = _body_for(nickname, resolved_name)
                    subject = message["subject"]
                capability = "google.gmail.draft.create"
                params = {
                    "to": email,
                    "cc": review_inbox,
                    "subject": message["subject"],
                    "body": message["body"],
                }
                result = broker_call("cassandra", capability, params)
                if result.get("ok"):
                    result_data = result.get("data") or {}
                    draft_id = result_data.get("draft_id", "")
                    status = "draft"
                    detail = f"drafted for {email}; cc {review_inbox}"
                    if draft_id:
                        detail += f"; draft_id={draft_id}"
                    metadata = {
                        "recipient_email": email,
                        "mailbox_identity": "primary",
                        "draft_id": result_data.get("draft_id", ""),
                        "message_id": result_data.get("message_id", ""),
                        "thread_id": result_data.get("thread_id", ""),
                        "route": "outreach_email",
                    }
                    notify_error = _safe_notify_winship(
                        f"Cassandra outreach {status} for {message['display_name']} at {email}. "
                        f"Subject: {message['subject']}"
                    )
                    if notify_error:
                        detail = f"{detail}; telegram notify failed: {notify_error}"
                else:
                    status = "send_failed"
                    detail = str(result.get("error", "unknown error"))
                    metadata = {
                        "recipient_email": email,
                        "mailbox_identity": "primary",
                        "route": "outreach_email",
                    }
                    _safe_notify_winship(
                        f"Cassandra outreach to {message['display_name']} was not sent. "
                        f"Reason: {detail}"
                    )
            except Exception as exc:
                status = "send_failed"
                detail = str(exc)
                email = ""
                metadata = {"route": "outreach_email", "mailbox_identity": "primary"}
                _safe_notify_winship(
                    f"Cassandra outreach to {message['display_name']} was not sent. "
                    f"Reason: {detail}"
                )

        if not dry_run:
            _log_attempt(nickname, subject, status, detail, metadata=metadata)

        result_row = dict(message)
        if email:
            result_row["email"] = email
        result_row["status"] = status
        result_row["detail"] = detail
        results.append(result_row)

    return results


def render_results(results: list[dict]) -> str:
    blocks = []
    for result in results:
        to_line = result.get("email") or f"(lookup via contacts for {result['display_name']})"
        blocks.append(
            "\n".join(
                [
                    f"TO: {to_line}",
                    f"NICKNAME: {result['nickname']}",
                    f"SUBJECT: {result['subject']}",
                    "BODY:",
                    result["body"],
                    f"STATUS: {result['status']}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Cassandra pilot intro email drafts.")
    parser.add_argument("--dry-run", action="store_true", help="Show the pilot intro email drafts without creating them.")
    args = parser.parse_args(argv)

    results = run_outreach(dry_run=args.dry_run)
    print(render_results(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── Shared outbound-email helpers (moved from cassandra_brain.py, Cut 4) ─────


def _load_jsonl_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
    except Exception as exc:
        print(f"[cassandra] jsonl read failed for {path}: {exc}", flush=True)
    return records


def _normalize_email_subject(subject: str) -> str:
    value = str(subject or "").strip()
    while True:
        lowered = value.lower()
        if lowered.startswith(("re:", "fw:", "fwd:")):
            value = value.split(":", 1)[1].strip()
            continue
        return value


def _extract_subject_from_detail(detail: str) -> str:
    match = re.search(r"subject=([^;]+)", str(detail or ""))
    return match.group(1).strip() if match else ""


def _extract_email_from_detail(detail: str) -> str:
    match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", str(detail or ""))
    return match.group(1).strip().lower() if match else ""


def _load_outbound_email_records() -> list[dict]:
    records: list[dict] = []
    for path, source in ((_CORRESPONDENCE_LOG, "correspondence"), (_OUTREACH_LOG, "outreach")):
        for entry in _load_jsonl_records(path):
            state = str(entry.get("state", entry.get("status", ""))).strip().lower()
            if state not in {
                _SS_DRAFT,
                _SS_QUEUED,
                _SS_AWAITING_APPROVAL,
                _SS_SEND_ATTEMPTED,
                _SS_SENT_CONFIRMED,
            }:
                continue
            subject = str(entry.get("subject") or _extract_subject_from_detail(entry.get("detail", ""))).strip()
            recipient_email = str(entry.get("recipient_email") or _extract_email_from_detail(entry.get("detail", ""))).strip().lower()
            records.append({
                "source": source,
                "ts": str(entry.get("ts", "")),
                "state": state,
                "recipient": str(entry.get("recipient", "")),
                "recipient_email": recipient_email,
                "subject": subject,
                "subject_norm": _normalize_email_subject(subject).lower(),
                "thread_id": str(entry.get("thread_id", "")),
                "message_id": str(entry.get("message_id", "")),
                "draft_id": str(entry.get("draft_id", "")),
                "mailbox_identity": str(entry.get("mailbox_identity", "primary") or "primary"),
                "route": str(entry.get("route", "")),
            })
    records.sort(key=lambda row: row.get("ts", ""), reverse=True)
    return records


def _match_outbound_email_record(message: dict, sender_email: str) -> dict | None:
    subject_norm = _normalize_email_subject(message.get("subject", "")).lower()
    thread_id = str(message.get("thread_id", "")).strip()
    for record in _load_outbound_email_records():
        if thread_id and record.get("thread_id") and record["thread_id"] == thread_id:
            return {**record, "matched_via": "thread_id"}
    for record in _load_outbound_email_records():
        if not record.get("recipient_email"):
            continue
        if record["recipient_email"] != str(sender_email or "").strip().lower():
            continue
        if record.get("subject_norm") == subject_norm:
            return {**record, "matched_via": "subject+recipient"}
    return None


# ── Email-thread evidence helpers (moved from cassandra_brain.py, Cut 5) ─────


def _bridge_preview(text: str, limit: int = 140) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _parse_event_datetime(raw: object, fallback: datetime | None = None) -> datetime:
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw))
        except Exception:
            pass

    raw_text = str(raw or "").strip()
    if raw_text.isdigit():
        try:
            ts = int(raw_text)
            if ts > 10_000_000_000:
                return datetime.fromtimestamp(ts / 1000.0)
            return datetime.fromtimestamp(ts)
        except Exception:
            pass

    if raw_text:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(raw_text)
            if dt.tzinfo is not None:
                return dt.astimezone().replace(tzinfo=None)
            return dt.replace(tzinfo=None)
        except Exception:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw_text[:19], fmt)
            except Exception:
                continue

    return fallback or datetime.now()


_EMAIL_THREAD_STOPWORDS = {
    "a", "an", "and", "are", "be", "did", "do", "does", "for", "from", "get",
    "had", "has", "have", "how", "i", "if", "in", "is", "it", "me", "my",
    "of", "on", "or", "our", "that", "the", "their", "there", "this", "to",
    "was", "we", "what", "when", "where", "who", "will", "with", "yet", "you",
    "your",
}

_EMAIL_THREAD_REQUEST_PREFIXES = (
    "can you",
    "could you",
    "would you",
    "will you",
    "did ",
    "do ",
    "does ",
    "how ",
    "what ",
    "when ",
    "where ",
    "who ",
    "why ",
    "is ",
    "are ",
    "should ",
    "let me know",
    "tell me",
    "check whether",
    "check if",
)


def _significant_terms(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9']+", str(text or "").lower())
    return {
        token
        for token in tokens
        if len(token) > 2 and token not in _EMAIL_THREAD_STOPWORDS
    }


def _question_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _extract_question_candidates(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def _push(candidate: str) -> None:
        value = candidate.strip(" -\t")
        if not value or not any(ch.isalpha() for ch in value):
            return
        key = _question_key(value)
        if not key or key in seen:
            return
        seen.add(key)
        candidates.append(value)

    for sentence in re.split(r"(?<=[?])\s+", cleaned):
        sentence = sentence.strip()
        if "?" not in sentence:
            continue
        for piece in re.findall(r"[^?]{3,240}\?", sentence):
            _push(piece)

    if candidates:
        return candidates[:5]

    for sentence in re.split(r"(?<=[.!])\s+|\n+", cleaned):
        sentence = sentence.strip(" -\t")
        lowered = sentence.lower()
        if any(lowered.startswith(prefix) for prefix in _EMAIL_THREAD_REQUEST_PREFIXES):
            _push(sentence.rstrip(".!"))

    return candidates[:5]


def _fetch_email_thread_messages(message: dict) -> tuple[list[dict], str]:
    try:
        call_fn = broker_call if broker_call is not None else __import__("google_access_broker").call
        result = call_fn(
            "cassandra",
            "google.gmail.read.body",
            {
                "thread_id": str(message.get("thread_id", "")),
                "message_id": str(message.get("message_id", "")),
                "max_messages": 8,
            },
        )
    except Exception as exc:
        print(f"[cassandra] gmail thread body fetch failed: {exc}", flush=True)
        result = {"ok": False, "data": None, "error": str(exc)}

    if result.get("ok") and isinstance(result.get("data"), dict):
        messages = list((result["data"] or {}).get("messages", []) or [])
        if messages:
            return messages, "gmail.read.body"

    fallback = dict(message)
    fallback.setdefault("body_text", "")
    fallback.setdefault("internal_date", "")
    return [fallback], "gmail.read.metadata"


def _message_evidence_rows(thread_messages: list[dict], sender_email: str) -> list[dict]:
    rows: list[dict] = []
    target_email = str(sender_email or "").strip().lower()
    for message in sorted(thread_messages, key=lambda row: _parse_event_datetime(row.get("internal_date") or row.get("date_raw"))):
        rows.append({
            "message_id": str(message.get("message_id", "")),
            "from_name": str(message.get("from_name", "")),
            "from_email": str(message.get("from_email", "")).strip().lower(),
            "direction": "inbound" if str(message.get("from_email", "")).strip().lower() == target_email else "outbound_or_other",
            "date_raw": str(message.get("date_raw", "")),
            "body_preview": _bridge_preview(message.get("body_text") or message.get("snippet", ""), limit=220),
        })
    return rows


def _bundle_answered_in_thread(bundle: dict, thread_messages: list[dict], sender_email: str) -> bool:
    target_email = str(sender_email or "").strip().lower()
    question_terms = _significant_terms(bundle.get("question", ""))
    asked_after = _parse_event_datetime(bundle.get("last_asked_at"))
    if not question_terms:
        return False

    for message in thread_messages:
        from_email = str(message.get("from_email", "")).strip().lower()
        if from_email == target_email:
            continue
        message_dt = _parse_event_datetime(message.get("internal_date") or message.get("date_raw"))
        if message_dt <= asked_after:
            continue
        message_text = " ".join(
            part for part in (
                message.get("subject", ""),
                message.get("body_text", ""),
                message.get("snippet", ""),
            )
            if isinstance(part, str) and part.strip()
        )
        overlap = question_terms & _significant_terms(message_text)
        if len(overlap) >= min(2, len(question_terms)):
            return True
    return False


def _load_email_thread_states() -> dict:
    try:
        return load_json(_EMAIL_THREAD_STATE, {})
    except Exception:
        return {}


def _save_email_thread_states(state: dict) -> None:
    try:
        save_json(_EMAIL_THREAD_STATE, state)
    except Exception as exc:
        print(f"[cassandra] email thread state save failed: {exc}", flush=True)


def _build_thread_followup_suggestion(contact_name: str, unresolved_bundles: list[dict]) -> str:
    if not unresolved_bundles:
        return ""
    first = unresolved_bundles[0]
    if first.get("status") == "needs_winship_review":
        return (
            f"If you follow up with {contact_name}, keep it short: "
            "\"I have the question and I\u2019m checking with Winship before I answer.\""
        )
    if first.get("status") == "needs_capability":
        return (
            f"If you follow up with {contact_name}, acknowledge the question and avoid bluffing "
            "until the missing capability is built."
        )
    return (
        f"If you follow up with {contact_name}, answer the open question directly and keep it to one clean reply."
    )


def _build_parked_thread_suggestions(unresolved_bundles: list[dict], predictions: list[dict]) -> list[str]:
    suggestions: list[str] = []
    lane_blocked = [bundle for bundle in unresolved_bundles if bundle.get("status") == "needs_winship_review"]
    capability_blocked = [bundle for bundle in unresolved_bundles if bundle.get("status") == "needs_capability"]
    if lane_blocked:
        suggestions.append("Decide what Cassandra is cleared to say before reopening the thread.")
    if capability_blocked:
        capabilities = ", ".join(sorted({gap["capability"] for bundle in capability_blocked for gap in bundle.get("capability_gaps", [])}))
        if capabilities:
            suggestions.append(f"Use the queued capability work before answering again: {capabilities}.")
    if predictions:
        suggestions.append(f"If you reply manually, pre-empt the likely next ask: {predictions[0]['question']}")
    if not suggestions:
        suggestions.append("Reply manually only if the relationship context now warrants reopening the thread.")
    return suggestions[:3]


def _advance_email_thread_cadence(
    *,
    thread_id: str,
    contact_name: str,
    unresolved_bundles: list[dict],
    predictions: list[dict],
    now: datetime | None = None,
) -> dict:
    now_dt = now or datetime.now()
    states = _load_email_thread_states()
    current = dict(states.get(thread_id, {}))

    if not unresolved_bundles:
        states[thread_id] = {
            "status": "resolved",
            "last_evaluated_at": now_dt.isoformat(timespec="seconds"),
        }
        _save_email_thread_states(states)
        return {
            "status": "resolved",
            "user_update": "This thread no longer has an open email question bundle.",
            "suggested_followup": "",
            "next_followup_at": "",
            "parked_suggestions": [],
        }

    latest_asked_at = max(_parse_event_datetime(bundle.get("last_asked_at"), now_dt) for bundle in unresolved_bundles)
    latest_asked_iso = latest_asked_at.isoformat(timespec="seconds")
    previous_last_asked = str(current.get("last_asked_at", ""))
    followup_attempts = int(current.get("followup_attempts", 0) or 0)

    if previous_last_asked != latest_asked_iso:
        followup_attempts = 0
        current = {}

    next_followup_at = _parse_event_datetime(
        current.get("next_followup_at"),
        latest_asked_at + timedelta(days=_EMAIL_THREAD_FOLLOWUP_DAYS),
    )

    status = "waiting"
    suggested_followup = ""
    parked_suggestions: list[str] = []
    if followup_attempts >= 1 and now_dt >= next_followup_at:
        status = "parked"
        parked_suggestions = _build_parked_thread_suggestions(unresolved_bundles, predictions)
        user_update = (
            "I parked this thread after one bounded follow-up window. "
            + " ".join(parked_suggestions)
        )
    elif now_dt >= next_followup_at:
        status = "followup_due"
        followup_attempts = 1
        suggested_followup = _build_thread_followup_suggestion(contact_name, unresolved_bundles)
        next_followup_at = now_dt + timedelta(days=_EMAIL_THREAD_FOLLOWUP_DAYS)
        user_update = (
            f"This has been unresolved since {latest_asked_at.strftime('%Y-%m-%d')}. "
            f"One short follow-up is reasonable now. {suggested_followup}"
        )
    else:
        user_update = (
            f"I'll leave this thread alone for now and revisit after "
            f"{next_followup_at.strftime('%Y-%m-%d')} if it still needs an answer."
        )

    states[thread_id] = {
        "status": status,
        "last_asked_at": latest_asked_iso,
        "last_evaluated_at": now_dt.isoformat(timespec="seconds"),
        "followup_attempts": followup_attempts,
        "next_followup_at": next_followup_at.isoformat(timespec="seconds"),
        "suggested_followup": suggested_followup,
        "parked_suggestions": parked_suggestions,
    }
    _save_email_thread_states(states)
    return {
        "status": status,
        "user_update": user_update,
        "suggested_followup": suggested_followup,
        "next_followup_at": next_followup_at.isoformat(timespec="seconds"),
        "parked_suggestions": parked_suggestions,
    }


def _log_email_thread_analysis(entry: dict) -> None:
    try:
        _EMAIL_THREAD_ANALYSIS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _EMAIL_THREAD_ANALYSIS_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception as exc:
        print(f"[cassandra] email thread analysis log write failed: {exc}", flush=True)


def _is_reply_like_email_message(message: dict) -> bool:
    subject = str(message.get("subject", "")).strip().lower()
    return bool(
        subject.startswith("re:")
        or str(message.get("in_reply_to", "")).strip()
        or str(message.get("references", "")).strip()
    )


def _build_email_bridge_review_text(message: dict) -> str:
    parts = []
    subject = str(message.get("subject", "")).strip()
    preview = _bridge_preview(message.get("snippet", ""), limit=240)
    if subject:
        parts.append(subject)
    if preview:
        parts.append(preview)
    return "\n".join(parts)


# ── Reply-bridge orchestration helpers (moved from cassandra_brain.py, Cut 6) ─


_EMAIL_REPLY_BRIDGE_PATTERNS = (
    "check inner circle email replies",
    "check inner-circle email replies",
    "show inner circle email replies",
    "show inner-circle email replies",
    "list inner circle email replies",
    "list inner-circle email replies",
    "any inner circle email replies",
    "any inner-circle email replies",
    "check pinned email replies",
    "show pinned email replies",
    "list pinned email replies",
    "check email replies from",
    "show email replies from",
    "list email replies from",
    "any email replies from",
)


def _detect_inner_circle_email_reply_intent(text: str) -> bool:
    t = text.lower()
    return any(pattern in t for pattern in _EMAIL_REPLY_BRIDGE_PATTERNS)


_EMAIL_BRIDGE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_email_bridge.jsonl")


def _email_bridge_message_seen(message_id: str) -> bool:
    if not message_id or not _EMAIL_BRIDGE_LOG.exists():
        return False
    try:
        for line in _EMAIL_BRIDGE_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("message_id") == message_id:
                return True
    except Exception:
        return False
    return False


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
    if dedupe and _email_bridge_message_seen(message_id):
        return
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message_id": message_id,
        "thread_id": thread_id,
        "nickname": nickname,
        "contact_name": contact_name,
        "sender_email": sender_email,
        "subject": _bridge_preview(subject, limit=120),
        "preview": _bridge_preview(preview, limit=160),
        "lane": lane,
        "status": status,
        "unread": bool(unread),
        "route": "inner_circle_email_reply",
    }
    try:
        _EMAIL_BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _EMAIL_BRIDGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        print(f"[cassandra] email bridge log write failed: {exc}", flush=True)


def _predict_likely_next_questions(question_bundles: list[dict]) -> list[dict]:
    predictions: list[dict] = []
    for bundle in question_bundles:
        lowered = bundle.get("question", "").lower()
        if not any(keyword in lowered for keyword in ("payment", "deposit", "invoice")):
            continue
        finance_reply = get_finance_status_answer(bundle["question"])
        if not finance_reply or "Next:" not in finance_reply:
            continue
        next_step = finance_reply.split("Next:", 1)[1].strip()
        if not next_step:
            continue
        predictions.append({
            "question": "What needs to happen next?",
            "because": next_step,
            "bundle_id": bundle.get("bundle_id", ""),
        })
        break
    return predictions
