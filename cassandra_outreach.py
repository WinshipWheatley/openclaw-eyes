
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
from datetime import datetime
from pathlib import Path

from cassandra_email_config import get_review_inbox

_NICKNAMES_PATH = Path("/home/openclaw/contact_nicknames.json")
_OUTREACH_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_outreach.jsonl")
_PILOT_INTRO_TEMPLATE = Path("/home/openclaw/cassandra_inner_circle_pilot_intro.md")

_CORRESPONDENCE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl")

_SS_DRAFT             = "draft"
_SS_QUEUED            = "queued"
_SS_AWAITING_APPROVAL = "awaiting_approval"
_SS_SEND_ATTEMPTED    = "send_attempted"
_SS_SENT_CONFIRMED    = "sent_confirmed"
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
