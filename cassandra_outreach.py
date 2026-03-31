"""
cassandra_outreach.py

One-time outreach flow for Cassandra intro emails.

Usage:
    python3 /home/openclaw/cassandra_outreach.py --dry-run
    python3 /home/openclaw/cassandra_outreach.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


_NICKNAMES_PATH = Path("/home/openclaw/contact_nicknames.json")
_OUTREACH_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_outreach.jsonl")

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
    If it stores an inline email, use it directly. Otherwise resolve through the
    existing Google Contacts broker by the mapped contact label.
    """
    nicknames = _load_nicknames()
    value = nicknames.get(nickname.lower(), nickname)

    if isinstance(value, dict):
        email = str(value.get("email", "")).strip()
        display_name = (
            str(value.get("display_name") or value.get("name") or value.get("contact_name") or nickname.title()).strip()
            or nickname.title()
        )
        if email:
            return email, display_name
        contact_label = display_name
    else:
        contact_label = str(value).strip() or nickname.title()

    from google_access_broker import call as broker_call

    result = broker_call("cassandra", "google.contacts.read", {"query": contact_label})
    if not result.get("ok") or not result.get("data"):
        raise RuntimeError(f"No contact email found for {nickname}.")

    for contact in result["data"]:
        email = str(contact.get("email", "")).strip()
        if email:
            display_name = str(contact.get("display_name", "")).strip() or contact_label
            return email, display_name

    raise RuntimeError(f"Contact found for {nickname} but no email address is available.")


def _subject_for(display_name: str) -> str:
    return f"Hey {display_name} — an intro from Cassandra"


def _body_for(nickname: str, display_name: str) -> str:
    blurb = _RECIPIENT_BLURBS[nickname]
    return (
        f"Hey {display_name},\n\n"
        "I’m Cassandra — Winship’s AI assistant.\n\n"
        "He’s using me in the real world now to help keep the system useful, grounded, and worth improving. "
        "This note is a quick intro and a live test.\n\n"
        f"{blurb}\n\n"
        "If anything feels confusing, useful, off, or worth improving, just reply with your questions, comments, or concerns.\n\n"
        "Thanks,\n"
        "Cassandra"
    )


def _log_attempt(recipient: str, subject: str, status: str, detail: str = "") -> None:
    entry = {
        "ts": _now(),
        "recipient": recipient,
        "subject": subject,
        "status": status,
    }
    if detail:
        entry["detail"] = detail

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


def run_outreach(*, dry_run: bool = False) -> list[dict]:
    """
    Build and optionally send the outreach email set.

    Returns a per-recipient result list for both dry runs and real sends.
    """
    results: list[dict] = []
    from google_access_broker import call as broker_call

    for message in build_outreach_messages():
        nickname = message["nickname"]
        subject = message["subject"]

        if dry_run:
            email = ""
            status = "dry_run"
            detail = "not sent"
        else:
            try:
                email, resolved_name = _resolve_contact_email(nickname)
                message["email"] = email
                if resolved_name and resolved_name != message["display_name"]:
                    message["display_name"] = resolved_name
                    message["subject"] = _subject_for(resolved_name)
                    message["body"] = _body_for(nickname, resolved_name)
                    subject = message["subject"]
                result = broker_call(
                    "cassandra",
                    "google.gmail.send",
                    {
                        "to": email,
                        "subject": message["subject"],
                        "body": message["body"],
                    },
                )
                if result.get("ok"):
                    status = "sent"
                    detail = f"sent to {email}"
                    notify_error = _safe_notify_winship(
                        f"Cassandra outreach sent to {message['display_name']} at {email}. "
                        f"Subject: {message['subject']}"
                    )
                    if notify_error:
                        detail = f"{detail}; telegram notify failed: {notify_error}"
                else:
                    status = "send_failed"
                    detail = str(result.get("error", "unknown error"))
                    _safe_notify_winship(
                        f"Cassandra outreach to {message['display_name']} was not sent. "
                        f"Reason: {detail}"
                    )
            except Exception as exc:
                status = "send_failed"
                detail = str(exc)
                email = ""
                _safe_notify_winship(
                    f"Cassandra outreach to {message['display_name']} was not sent. "
                    f"Reason: {detail}"
                )

        if not dry_run:
            _log_attempt(nickname, subject, status, detail)

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
    parser = argparse.ArgumentParser(description="Send Cassandra intro outreach emails.")
    parser.add_argument("--dry-run", action="store_true", help="Show the outreach emails without sending them.")
    args = parser.parse_args(argv)

    results = run_outreach(dry_run=args.dry_run)
    print(render_results(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
