def _exec_gmail_unread_count(creds, params: dict) -> dict:
    """
    Fetch the unread count for the INBOX label from Gmail API.
    """
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        label_resp = service.users().labels().get(userId="me", id="INBOX").execute()
        unread_count = label_resp.get("messagesUnread", 0)
        return {"ok": True, "data": unread_count, "error": ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}

"""
google_access_broker.py

Central Google API access broker for the OpenClaw system.

BOUNDARY RULE: This module is the ONLY permitted Google API entry point.
  - No brain module may call Google APIs directly.
  - Brains call this module; this module never imports or calls a brain.
  - All calls are policy-checked, approval-gated (Class B/C), and audit-logged.

Current state: inert scaffolding.
  No live API calls are made until credentials are configured and --auth is run.
  All capability executors return "not yet activated" until explicitly wired.

Secrets location (must be created manually before --auth):
    /home/openclaw/.google-secrets/credentials.json   — OAuth client secret
    /home/openclaw/.google-secrets/token.json         — refresh token (written by --auth)

Required filesystem permissions:
    chmod 700 /home/openclaw/.google-secrets/
    chmod 600 /home/openclaw/.google-secrets/credentials.json
    chmod 600 /home/openclaw/.google-secrets/token.json

One-time setup (run manually, never from the stack):
    python3 google_access_broker.py --auth

Public API:
    from google_access_broker import call
    result = call("cassandra", "google.calendar.read", {"days_ahead": 7})
    # Returns: {"ok": bool, "data": any, "error": str}
    # Returns {"ok": False, ...} if not configured, denied, or not yet wired.
"""

import json
import os
import sys
import importlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


# ── Secrets paths ─────────────────────────────────────────────────────────────

_SECRETS_DIR = Path("/home/openclaw/.google-secrets")
_CREDS_FILE  = _SECRETS_DIR / "credentials.json"
_TOKEN_FILE  = _SECRETS_DIR / "token.json"


# ── Audit log ─────────────────────────────────────────────────────────────────

_AUDIT_LOG = Path("/mnt/c/OpenClaw/logs/google_access_audit.jsonl")

_CALENDAR_ALLOWLIST = [
    "primary",
    "4hra0c8ektf0l3jqirb7aim018@group.calendar.google.com",
]

# Friendly source-calendar names so brains can show WHICH calendar an event is on
# when a read spans more than one (answers "can we see different calendars?").
_CALENDAR_NAMES = {
    "primary": "Schedule",
    "4hra0c8ektf0l3jqirb7aim018@group.calendar.google.com": "Availability",
}

_CALENDAR_TIMEZONE = ZoneInfo("America/New_York")


# ── Active OAuth scope bundle ─────────────────────────────────────────────────
# Pass 1 only. Do NOT add Pass 2/3 scopes until prior pass is verified and audited.
# Pass 2 adds: gmail.readonly
# Pass 3 adds: gmail.compose
# Each scope expansion requires a deliberate code change here + re-run of --auth.

_ACTIVE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",  # Pass 3: email send
]


# ── Credential helpers ────────────────────────────────────────────────────────

def _is_configured() -> bool:
    """True only if both secrets files exist. Does not validate contents."""
    return _CREDS_FILE.exists() and _TOKEN_FILE.exists()


def _load_credentials():
    """
    Load and refresh OAuth2 credentials from the secrets directory.
    Returns None if not configured or if refresh fails.
    """
    if not _is_configured():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _ACTIVE_SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            return creds
        return None  # Token exists but not refreshable — re-run --auth
    except Exception as e:
        print(f"[google_broker] credential load failed: {e}", flush=True)
        return None


# ── Audit logging ─────────────────────────────────────────────────────────────

_AUDIT_BODY_PARAM_KEYS = {"body", "body_text", "message_body"}
_AUDIT_APPROVAL_CONTEXT_KEEP_KEYS = {
    "request_id",
    "idempotency_key",
    "objective_id",
    "payload_hash",
    "body_hash",
    "authority_refs",
    "credential_lease_refs",
    "authority_envelope_ref",
    "authority_envelope_id",
    "credential_lease_ref",
    "credential_lease_id",
    "exact_send_gate",
}

_GMAIL_BROKER_RUNTIME_IMPORTS = (
    "googleapiclient.discovery",
    "google.oauth2.credentials",
    "google.auth.transport.requests",
)


def _redact_audit_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _redact_audit_value(v)
            for k, v in value.items()
            if str(k) not in _AUDIT_BODY_PARAM_KEYS
        }
    if isinstance(value, list):
        return [_redact_audit_value(item) for item in value]
    return value


def _redact_approval_context(value: Any) -> dict:
    if not isinstance(value, Mapping):
        return {"redacted": True}
    return {
        key: _redact_audit_value(value[key])
        for key in _AUDIT_APPROVAL_CONTEXT_KEEP_KEYS
        if key in value
    }


def _redact_audit_params(params: Mapping[str, Any]) -> dict:
    redacted = {}
    for key, value in params.items():
        key_str = str(key)
        if key_str in _AUDIT_BODY_PARAM_KEYS:
            continue
        if key_str == "approval_context":
            redacted[key_str] = _redact_approval_context(value)
            redacted["approval_context_redacted"] = True
            continue
        redacted[key_str] = _redact_audit_value(value)
    return redacted


def _audit(agent: str, capability: str, params: dict,
           result_ok: bool, error: str = "") -> None:
    """Append one JSONL line to the Google access audit log."""
    entry = {
        "ts":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent":      agent,
        "capability": capability,
        "params":     _redact_audit_params(params),
        "ok":         result_ok,
        "error":      error,
    }
    try:
        _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[google_broker] audit write failed: {e}", flush=True)


# ── Approval gate hook ────────────────────────────────────────────────────────

def _request_approval(action: str, tier: int, approval_context: dict | None = None) -> bool:
    """
    Hook into the OpenClaw approval gate for Class B and C capabilities.
    Class A reads do not go through this — they are auto-proceed.
    Returns True if approved, False if denied or timed out.
    """
    try:
        from chief_approval_brain import request_approval
        return request_approval(
            action,
            requester="google_broker",
            explicit_tier=tier,
            approval_context=approval_context,
        )
    except ImportError:
        print("[google_broker] approval gate unavailable — defaulting to deny", flush=True)
        return False


def _import_runtime_dependency(module_name: str):
    return importlib.import_module(module_name)


def check_gmail_broker_runtime_dependencies() -> dict:
    """Import Gmail broker runtime modules without loading credentials."""
    missing: list[dict[str, str]] = []
    for module_name in _GMAIL_BROKER_RUNTIME_IMPORTS:
        try:
            _import_runtime_dependency(module_name)
        except Exception as exc:
            missing.append(
                {
                    "module": module_name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return {
        "ok": not missing,
        "checked_modules": list(_GMAIL_BROKER_RUNTIME_IMPORTS),
        "missing": missing,
        "credentials_read": False,
        "google_api_called": False,
    }


# ── Gmail SELF-SEND TEST MODE ─────────────────────────────────────────────────
# Until the operator graduates them, agents may send real email ONLY to the operator's
# own inbox — the real Gmail send path, but physically impossible to reach anyone else.
# This breaks the chicken-and-egg: you can watch agents actually send and verify they do
# the right thing BEFORE trusting external sends. Graduate with OPENCLAW_GMAIL_SEND_SELF_TEST=0
# (external sends then require the existing Class C / exact-send approval gate).
_GMAIL_SELF_TEST_RECIPIENTS = frozenset({"winshiplive@gmail.com"})


def _gmail_self_test_enabled(env: Mapping[str, Any] | None = None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_GMAIL_SEND_SELF_TEST", "1")).strip().lower() not in (
        "0", "false", "no", "off", "")


def _gmail_recipient_list(params: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("to", "cc", "bcc"):
        raw = str(params.get(key, "") or "")
        for addr in raw.replace(";", ",").split(","):
            a = addr.strip().lower()
            if a:
                out.append(a)
    return out


def _gmail_send_recipients_allowed(params: Mapping[str, Any]) -> bool:
    """True only if EVERY recipient (to/cc/bcc) is an allowlisted self-test address."""
    recips = _gmail_recipient_list(params)
    if not recips:
        return False
    allow = {a.lower() for a in _GMAIL_SELF_TEST_RECIPIENTS}
    return all(a in allow for a in recips)


def _exact_send_gate_context_verified(
    agent: str,
    capability: str,
    params: Mapping[str, Any],
) -> bool:
    """True when Cassandra's exact-send gate already verified human approval."""
    if agent.lower() != "cassandra" or capability != "google.gmail.send":
        return False
    context = params.get("approval_context")
    if not isinstance(context, Mapping):
        return False
    request_id = str(params.get("exact_send_request_id") or context.get("request_id") or "")
    idempotency_key = str(params.get("idempotency_key") or context.get("idempotency_key") or "")
    return bool(
        context.get("exact_send_gate") is True
        and request_id
        and idempotency_key == request_id
        and context.get("payload_hash")
        and context.get("authority_refs")
        and context.get("credential_lease_refs")
    )


# ── Capability executors ──────────────────────────────────────────────────────
# Each executor receives live credentials and capability-specific params.
# Returns {"ok": bool, "data": any, "error": str}.
# Formatting and interpretation are the calling brain's responsibility.

def _exec_calendar_read(creds, params: dict) -> dict:
    """
    Fetch raw calendar events from Google Calendar API.

    Reads an explicit allowlist of calendar IDs, merges results, and
    returns them sorted by start time. Brains format the output.

    Allowlist (hardcoded, narrow):
      - "primary"       → Schedule (winshiplive@gmail.com)
      - Winship Availability → 4hra0c8ektf0l3jqirb7aim018@group.calendar.google.com
    """
    days_ahead = params.get("days_ahead", 7)
    try:
        from googleapiclient.discovery import build
        from datetime import timezone, timedelta
        service  = build("calendar", "v3", credentials=creds)
        now      = datetime.now(timezone.utc)
        time_max = (now + timedelta(days=days_ahead)).isoformat()
        time_min = now.isoformat()

        all_events = []
        for cal_id in _CALENDAR_ALLOWLIST:
            try:
                result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                ).execute()
                _cal_name = _CALENDAR_NAMES.get(cal_id, cal_id)
                for _ev in result.get("items", []):
                    _ev.setdefault("_calendar_name", _cal_name)
                    all_events.append(_ev)
            except Exception as cal_err:
                print(f"[google_broker] calendar {cal_id} skipped: {cal_err}", flush=True)

        # Sort merged list by start time (dateTime preferred, date fallback)
        def _sort_key(e):
            s = e.get("start", {})
            return s.get("dateTime") or s.get("date") or ""

        all_events.sort(key=_sort_key)
        return {"ok": True, "data": all_events, "error": ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_calendar_write(creds, params: dict) -> dict:
    """
    Create a calendar event via Google Calendar API.

    Required params:
        title      : str  — event summary/title
        start_iso  : str  — ISO 8601 datetime, e.g. "2026-03-24T14:00:00"
        end_iso    : str  — ISO 8601 datetime, e.g. "2026-03-24T15:00:00"

    Optional params:
        description : str  — event description (default "")
        calendar_id : str  — calendar to write to (default "primary")
    """
    title       = params.get("title", "").strip()
    start_iso   = params.get("start_iso", "").strip()
    end_iso     = params.get("end_iso", "").strip()
    description = params.get("description", "")
    calendar_id = params.get("calendar_id", "primary")

    if not title or not start_iso or not end_iso:
        return {"ok": False, "data": None, "error": "title, start_iso, and end_iso are required"}

    _TZ = "America/New_York"

    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        event_body: dict = {
            "summary": title,
            "start":   {"dateTime": start_iso, "timeZone": _TZ},
            "end":     {"dateTime": end_iso,   "timeZone": _TZ},
        }
        if description:
            event_body["description"] = description
        created = service.events().insert(
            calendarId=calendar_id, body=event_body
        ).execute()
        return {
            "ok":    True,
            "data":  {
                "event_id": created.get("id", ""),
                "link":     created.get("htmlLink", ""),
                "title":    created.get("summary", title),
            },
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_calendar_delete(creds, params: dict) -> dict:
    """
    Delete matching calendar events via Google Calendar API.

    Required params:
        title       : str  — exact event summary/title
        start_iso   : str  — local event start in YYYY-MM-DDTHH:MM:SS

    Optional params:
        max_matches : int  — maximum number of matching events to delete
    """
    title = str(params.get("title", "")).strip()
    start_iso = str(params.get("start_iso", "")).strip()
    max_matches = max(1, int(params.get("max_matches", 1)))

    if not title or not start_iso:
        return {"ok": False, "data": None, "error": "title and start_iso are required"}

    try:
        target_dt = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return {"ok": False, "data": None, "error": "start_iso must be YYYY-MM-DDTHH:MM:SS"}

    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds)
        start_of_day = target_dt.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=_CALENDAR_TIMEZONE,
        )
        time_min = start_of_day.isoformat()
        time_max = (start_of_day + timedelta(days=1)).isoformat()

        matches: list[dict] = []
        for cal_id in _CALENDAR_ALLOWLIST:
            try:
                result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=100,
                ).execute()
            except Exception as cal_err:
                print(f"[google_broker] calendar {cal_id} skipped during delete lookup: {cal_err}", flush=True)
                continue

            for item in result.get("items", []):
                start = item.get("start", {})
                event_start = start.get("dateTime") or ""
                if not event_start:
                    continue
                try:
                    event_dt = datetime.fromisoformat(event_start)
                except Exception:
                    continue
                if item.get("summary", "").strip() != title:
                    continue
                if (
                    event_dt.year,
                    event_dt.month,
                    event_dt.day,
                    event_dt.hour,
                    event_dt.minute,
                ) != (
                    target_dt.year,
                    target_dt.month,
                    target_dt.day,
                    target_dt.hour,
                    target_dt.minute,
                ):
                    continue
                matches.append(
                    {
                        "calendar_id": cal_id,
                        "event_id": item.get("id", ""),
                        "title": item.get("summary", title),
                        "start": event_start,
                    }
                )

        if not matches:
            return {"ok": False, "data": None, "error": "no matching events found"}

        matches = matches[:max_matches]
        for match in matches:
            service.events().delete(
                calendarId=match["calendar_id"],
                eventId=match["event_id"],
            ).execute()

        return {
            "ok": True,
            "data": {
                "deleted_count": len(matches),
                "events": matches,
            },
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _gmail_header_map(detail: dict) -> dict:
    return {
        h["name"]: h["value"]
        for h in detail.get("payload", {}).get("headers", [])
        if "name" in h and "value" in h
    }


def _gmail_sender_fields(headers: dict) -> tuple[str, str]:
    from email.utils import parseaddr

    raw_from = headers.get("From", "")
    from_name, from_email = parseaddr(raw_from)
    from_name = from_name.strip().strip('"')
    if not from_name and from_email:
        from_name = from_email.split("@")[0].strip()
    if not from_name:
        from_name = raw_from
    return from_name, from_email.strip().lower()


def _gmail_reply_to_email(headers: dict) -> str:
    from email.utils import parseaddr

    _, reply_to_email = parseaddr(headers.get("Reply-To", ""))
    return reply_to_email.strip().lower()


def _decode_gmail_body(data: str) -> str:
    if not data:
        return ""
    try:
        import base64

        padding = "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(data + padding)
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _gmail_payload_text(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""

    mime_type = str(payload.get("mimeType", "")).lower()
    body_data = str((payload.get("body") or {}).get("data", "") or "")

    if mime_type == "text/plain":
        return _decode_gmail_body(body_data)

    parts = payload.get("parts") or []
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            part_text = _gmail_payload_text(part)
            if part_text:
                texts.append(part_text)
    if texts:
        return "\n".join(chunk.strip() for chunk in texts if chunk.strip()).strip()

    if mime_type == "text/html":
        html = _decode_gmail_body(body_data)
        if html:
            import re

            text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    return _decode_gmail_body(body_data).strip()


def _exec_gmail_read_metadata(creds, params: dict) -> dict:
    """
    Fetch inbox message metadata from Gmail API.

    Returns up to max_results messages with From display name, Subject, Date,
    label IDs, and snippet. Does not access message bodies.
    """
    max_results = params.get("max_results", 10)
    # Optional Gmail search query (e.g. "subject:OC-LOOPBACK", "from:foo"). Additive:
    # with no query the behaviour is unchanged (10 most recent INBOX messages).
    query = str(params.get("query") or params.get("q") or "").strip()
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)

        _list_kwargs = {"userId": "me", "maxResults": max_results, "labelIds": ["INBOX"]}
        if query:
            _list_kwargs["q"] = query
        list_resp = service.users().messages().list(**_list_kwargs).execute()
        messages_raw = list_resp.get("messages", [])
        if not messages_raw:
            return {"ok": True, "data": [], "error": ""}

        messages = []
        for msg in messages_raw:
            msg_id = msg["id"]
            detail = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=[
                    "From",
                    "To",
                    "Reply-To",
                    "Subject",
                    "Date",
                    "In-Reply-To",
                    "References",
                ],
            ).execute()

            headers = _gmail_header_map(detail)
            from_name, from_email = _gmail_sender_fields(headers)
            reply_to_email = _gmail_reply_to_email(headers)

            messages.append({
                "message_id": msg_id,
                "thread_id":  detail.get("threadId", ""),
                "from_name":  from_name,
                "from_email": from_email.strip().lower(),
                "subject":    headers.get("Subject", "(no subject)"),
                "date_raw":   headers.get("Date", ""),
                "to_raw":     headers.get("To", ""),
                "reply_to_raw": headers.get("Reply-To", ""),
                "reply_to_email": reply_to_email.strip().lower(),
                "in_reply_to": headers.get("In-Reply-To", ""),
                "references": headers.get("References", ""),
                "labels":     detail.get("labelIds", []),
                "snippet":    detail.get("snippet", ""),
            })

        return {"ok": True, "data": messages, "error": ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_gmail_read_body(creds, params: dict) -> dict:
    """
    Fetch grounded Gmail thread content through the broker boundary.

    Supported params:
        thread_id    : str — Gmail thread id to inspect
        message_id   : str — specific message id if thread_id is unavailable
        max_messages : int — max messages to return from the tail of the thread
    """
    thread_id = str(params.get("thread_id", "")).strip()
    message_id = str(params.get("message_id", "")).strip()
    max_messages = int(params.get("max_messages", 6) or 6)
    max_messages = max(1, min(max_messages, 20))

    if not thread_id and not message_id:
        return {"ok": False, "data": None, "error": "thread_id or message_id is required"}

    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)
        raw_messages: list[dict]
        if thread_id:
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full",
            ).execute()
            raw_messages = list(thread.get("messages", []) or [])
        else:
            detail = service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()
            raw_messages = [detail]
            thread_id = str(detail.get("threadId", "")).strip()

        if not raw_messages:
            return {"ok": True, "data": {"thread_id": thread_id, "messages": []}, "error": ""}

        messages = []
        for detail in raw_messages[-max_messages:]:
            headers = _gmail_header_map(detail)
            from_name, from_email = _gmail_sender_fields(headers)
            body_text = _gmail_payload_text(detail.get("payload") or {})
            messages.append({
                "message_id": str(detail.get("id", "")),
                "thread_id": str(detail.get("threadId", thread_id)),
                "internal_date": str(detail.get("internalDate", "")),
                "from_name": from_name,
                "from_email": from_email,
                "subject": headers.get("Subject", "(no subject)"),
                "date_raw": headers.get("Date", ""),
                "to_raw": headers.get("To", ""),
                "reply_to_raw": headers.get("Reply-To", ""),
                "reply_to_email": _gmail_reply_to_email(headers),
                "in_reply_to": headers.get("In-Reply-To", ""),
                "references": headers.get("References", ""),
                "labels": detail.get("labelIds", []),
                "snippet": detail.get("snippet", ""),
                "body_text": body_text,
            })

        return {
            "ok": True,
            "data": {
                "thread_id": thread_id,
                "message_count": len(messages),
                "messages": messages,
            },
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_contacts_read(creds, params: dict) -> dict:
    """
    Search Google Contacts (People API) by name.

    Returns up to 5 results with display name, phone, and email.
    Does not access contact notes, addresses, or other fields.
    """
    query = params.get("query", "")
    try:
        from googleapiclient.discovery import build
        service = build("people", "v1", credentials=creds)
        result = service.people().searchContacts(
            query=query,
            readMask="names,phoneNumbers,emailAddresses",
            pageSize=5,
        ).execute()

        contacts = []
        for person in result.get("results", []):
            p = person.get("person", {})
            names  = p.get("names", [])
            phones = p.get("phoneNumbers", [])
            emails = p.get("emailAddresses", [])
            contacts.append({
                "display_name": names[0].get("displayName", "") if names else "",
                "phone":        phones[0].get("value", "") if phones else "",
                "email":        emails[0].get("value", "") if emails else "",
            })

        return {"ok": True, "data": contacts, "error": ""}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_gmail_send(creds, params: dict) -> dict:
    """
    Send an email via the Gmail API.

    Required params:
        to      : str — recipient email address (already resolved)
        subject : str — email subject line
        body    : str — plain-text email body

    Optional params:
        cc      : str — comma-separated CC recipients

    Requires gmail.compose scope in the active token.
    Every call to this executor is already L2 approval-gated by the broker dispatcher.
    """
    to      = params.get("to", "").strip()
    cc      = params.get("cc", "").strip()
    subject = params.get("subject", "").strip()
    body    = params.get("body", "").strip()
    thread_id = str(params.get("thread_id", "")).strip()
    in_reply_to = str(params.get("in_reply_to", "")).strip()
    references = str(params.get("references", "")).strip()

    if not to or not subject or not body:
        return {"ok": False, "data": None, "error": "to, subject, and body are all required"}

    try:
        import base64
        from email.mime.text import MIMEText
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)

        msg = MIMEText(body, "plain", "utf-8")
        msg["to"]      = to
        if cc:
            msg["cc"] = cc
        msg["subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        request_body = {"raw": raw}
        if thread_id:
            request_body["threadId"] = thread_id
        sent    = service.users().messages().send(
            userId="me", body=request_body
        ).execute()

        return {
            "ok":   True,
            "data": {
                "message_id": sent.get("id", ""),
                "thread_id":  sent.get("threadId", ""),
            },
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_gmail_draft_create(creds, params: dict) -> dict:
    """
    Create a Gmail draft via the Gmail API.

    Required params:
        to      : str — recipient email address (already resolved)
        subject : str — draft subject line
        body    : str — plain-text draft body

    Optional params:
        cc      : str — comma-separated CC recipients
    """
    to      = params.get("to", "").strip()
    cc      = params.get("cc", "").strip()
    subject = params.get("subject", "").strip()
    body    = params.get("body", "").strip()
    thread_id = str(params.get("thread_id", "")).strip()
    in_reply_to = str(params.get("in_reply_to", "")).strip()
    references = str(params.get("references", "")).strip()

    if not to or not subject or not body:
        return {"ok": False, "data": None, "error": "to, subject, and body are all required"}

    try:
        import base64
        from email.mime.text import MIMEText
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)

        msg = MIMEText(body, "plain", "utf-8")
        msg["to"] = to
        if cc:
            msg["cc"] = cc
        msg["subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        message_body = {"raw": raw}
        if thread_id:
            message_body["threadId"] = thread_id
        created = service.users().drafts().create(
            userId="me",
            body={"message": message_body},
        ).execute()

        message = created.get("message", {}) or {}
        return {
            "ok": True,
            "data": {
                "draft_id": created.get("id", ""),
                "message_id": message.get("id", ""),
                "thread_id": message.get("threadId", ""),
            },
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e)}


def _exec_not_implemented(capability: str) -> dict:
    return {
        "ok":    False,
        "data":  None,
        "error": f"{capability} not yet implemented in this phase",
    }


# ── Public entry point ────────────────────────────────────────────────────────

# ── Workflow Test Mode / SEND_HOLD gear-shift (Phase 1) ───────────────────────
# The broker is the LAST gate before the Google API call. It consults ONE policy
# (workflow_test_mode): PRODUCTION+SEND_HOLD => refuse; TEST mode => redirect the send to the
# operator's own inbox + flag it (the safe channel). Fail-safe: run-mode unknown => PRODUCTION;
# SEND_HOLD unreadable => treated as active (fail-closed).
from workflow_test_mode import (  # noqa: E402
    resolve_send_disposition,
    apply_test_mode_send,
    is_send_class_capability,
    PROCEED,
    BLOCK_SEND_HOLD,
    TEST_REDIRECT_FLAG,
)


def _broker_send_hold_active() -> bool:
    try:
        override = os.environ.get("OPENCLAW_SEND_HOLD_PATH")
        if override:
            return Path(override).is_file()
        from email_send_executor import DEFAULT_SEND_HOLD_PATH
        return Path(DEFAULT_SEND_HOLD_PATH).is_file()
    except Exception:
        return True  # fail-closed


def _resolve_broker_run_mode() -> tuple[str, str]:
    """Resolve run-mode from the TRUSTED backend state ONLY. Never from caller-supplied params —
    a send's authorization (approval-skip + redirect) must not be flippable by request input.
    Test mode is a deliberate operator/Chief activation (persisted run-mode state). Fail-safe:
    PRODUCTION on any error, so a real send is never mistaken for a test."""
    try:
        from global_run_mode_context import resolve_run_mode_context, DEFAULT_SQLITE_PATH, PRODUCTION
        ctx = resolve_run_mode_context(DEFAULT_SQLITE_PATH, {})  # empty request: no caller-influenced hint
        return str(ctx.get("run_mode") or PRODUCTION), str(ctx.get("test_run_id") or "")
    except Exception:
        return "production", ""


def _operator_test_inbox() -> str:
    try:
        from cassandra_email_config import get_review_inbox
        inbox = get_review_inbox()
        if inbox:
            return inbox
    except Exception:
        pass
    return sorted(_GMAIL_SELF_TEST_RECIPIENTS)[0]


def call(agent: str, capability: str, params: dict | None = None) -> dict:
    """
    Request Google API access on behalf of an agent.

    Parameters
    ----------
    agent      : str  — requesting agent, e.g. "cassandra"
    capability : str  — capability name, e.g. "google.calendar.read"
    params     : dict — capability-specific parameters (optional)

    Returns
    -------
    dict:
        "ok"    : bool — True if the call succeeded
        "data"  : any  — result payload; type depends on capability
        "error" : str  — error description if not ok
    """
    if params is None:
        params = {}

    # 1. Policy check
    try:
        from google_access_policy import allowed, get_class
    except ImportError:
        _audit(agent, capability, params, False, "policy module unavailable")
        return {"ok": False, "data": None, "error": "policy module unavailable"}

    if not allowed(agent, capability):
        msg = f"{agent} is not permitted to call {capability}"
        _audit(agent, capability, params, False, msg)
        return {"ok": False, "data": None, "error": msg}

    if capability.startswith("google.gmail."):
        readiness = check_gmail_broker_runtime_dependencies()
        if not readiness["ok"]:
            missing = ", ".join(item["module"] for item in readiness["missing"])
            msg = f"missing Gmail broker runtime dependencies: {missing}"
            _audit(agent, capability, params, False, msg)
            return {"ok": False, "data": readiness, "error": msg}

    approval_class = get_class(agent, capability)

    # 2. Approval gate (Class B and C only)
    #    Class A reads auto-proceed — gating would make reads unusable.
    exact_send_gate_verified = _exact_send_gate_context_verified(agent, capability, params)

    # Gmail SELF-SEND TEST MODE: in self-test mode google.gmail.send may ONLY reach the
    # operator's own inbox. A self-only send is safe and skips the heavy Class C / exact-send
    # gate; external recipients still pass through authority/credential checks before this
    # mode blocks execution.
    _gmail_self_test_send = False
    if capability == "google.gmail.send" and _gmail_self_test_enabled():
        _gmail_self_test_send = _gmail_send_recipients_allowed(params)

    # Workflow Test Mode: resolve run-mode from the TRUSTED backend state (not params) and compute
    # the send disposition ONCE. The approval-skip is derived from the SAME decision as the redirect,
    # so a test-mode send can never skip approval without also being redirected+flagged.
    _wtm_run_mode, _wtm_test_run_id = _resolve_broker_run_mode() if is_send_class_capability(capability) else ("production", "")
    _wtm_disposition = (
        resolve_send_disposition(
            run_mode=_wtm_run_mode, send_hold_active=_broker_send_hold_active(), is_send_class=True,
        )
        if is_send_class_capability(capability) else PROCEED
    )
    _wtm_test_send = _wtm_disposition == TEST_REDIRECT_FLAG

    if approval_class == "B":
        action = f"Google broker: {agent} → {capability}"
        if not _request_approval(action, tier=1, approval_context=params.get("approval_context")):
            _audit(agent, capability, params, False, "denied at L1")
            return {"ok": False, "data": None, "error": "denied at L1 approval gate"}
    elif approval_class == "C":
        action = f"Google broker: {agent} → {capability}"
        if not exact_send_gate_verified and not _gmail_self_test_send and not _wtm_test_send and not _request_approval(action, tier=2, approval_context=params.get("approval_context")):
            _audit(agent, capability, params, False, "denied at L2")
            return {"ok": False, "data": None, "error": "denied at L2 approval gate"}

    # 3. Credential check
    if not _is_configured():
        msg = (
            f"Google credentials not configured.\n"
            f"Steps:\n"
            f"  1. Obtain credentials.json from Google Cloud Console.\n"
            f"  2. Place at: {_CREDS_FILE}\n"
            f"  3. Run: chmod 700 {_SECRETS_DIR} && chmod 600 {_CREDS_FILE}\n"
            f"  4. Run: python3 google_access_broker.py --auth\n"
            f"  5. Run: chmod 600 {_TOKEN_FILE}"
        )
        _audit(agent, capability, params, False, "credentials not configured")
        return {"ok": False, "data": None, "error": msg}

    creds = _load_credentials()
    if creds is None:
        msg = "credentials present but could not be loaded — re-run --auth"
        _audit(agent, capability, params, False, msg)
        return {"ok": False, "data": None, "error": msg}

    # SEND_HOLD gear-shift at the last gate before the provider send (reuses the single decision).
    if is_send_class_capability(capability):
        if _wtm_disposition == BLOCK_SEND_HOLD:
            msg = "SEND_HOLD is active — broker refuses the send (kill-switch enforced at the broker)."
            _audit(agent, capability, params, False, msg)
            return {"ok": False, "data": {"send_hold_active": True}, "error": msg}
        if _wtm_disposition == TEST_REDIRECT_FLAG:
            _operator_inbox = _operator_test_inbox()
            params = apply_test_mode_send(
                params, operator_inbox=_operator_inbox, test_run_id=_wtm_test_run_id or "adhoc",
            )
            # PART B invariant: a test-mode send that skipped approval MUST have been redirected to
            # the operator's own inbox before it can proceed. If the redirect did not take, refuse.
            if str(params.get("to") or "") != _operator_inbox:
                msg = "test-mode send refused: redirect to operator inbox was not applied."
                _audit(agent, capability, params, False, msg)
                return {"ok": False, "data": None, "error": msg}
            _gmail_self_test_send = _gmail_send_recipients_allowed(params)
            _audit(agent, capability, params, True, f"workflow_test_mode_redirect_flag:{_wtm_test_run_id}")

    if capability == "google.gmail.send" and _gmail_self_test_enabled() and not _gmail_self_test_send:
        msg = ("gmail self-test mode: agents may only send to "
               + ", ".join(sorted(_GMAIL_SELF_TEST_RECIPIENTS))
               + " until graduated (set OPENCLAW_GMAIL_SEND_SELF_TEST=0)")
        _audit(agent, capability, params, False, msg)
        return {"ok": False, "data": None, "error": msg}

    # 4. Dispatch
    if capability == "google.calendar.read":
        result = _exec_calendar_read(creds, params)
    elif capability == "google.calendar.write":
        result = _exec_calendar_write(creds, params)
    elif capability == "google.calendar.delete":
        result = _exec_calendar_delete(creds, params)
    elif capability == "google.gmail.read.metadata":
        result = _exec_gmail_read_metadata(creds, params)
    elif capability == "google.gmail.read.body":
        result = _exec_gmail_read_body(creds, params)
    elif capability == "google.gmail.unread_count":
        result = _exec_gmail_unread_count(creds, params)
    elif capability == "google.contacts.read":
        result = _exec_contacts_read(creds, params)
    elif capability == "google.gmail.draft.create":
        result = _exec_gmail_draft_create(creds, params)
    elif capability == "google.gmail.send":
        result = _exec_gmail_send(creds, params)
    else:
        result = _exec_not_implemented(capability)

    _audit(agent, capability, params, result["ok"], result.get("error", ""))
    return result


# ── One-time auth flow ────────────────────────────────────────────────────────

def run_auth_flow() -> None:
    """
    Run the OAuth2 browser-based authorization flow and write token.json.
    Run once manually. Never call from the running stack.

    Prerequisites:
      - credentials.json already at /home/openclaw/.google-secrets/credentials.json
      - chmod 700 /home/openclaw/.google-secrets/
      - chmod 600 /home/openclaw/.google-secrets/credentials.json
    """
    if not _CREDS_FILE.exists():
        print(f"[google_broker] credentials.json not found at {_CREDS_FILE}")
        print("Download OAuth client credentials from Google Cloud Console.")
        print(f"Place at {_CREDS_FILE}, then: chmod 600 {_CREDS_FILE}")
        sys.exit(1)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_FILE), _ACTIVE_SCOPES)
        print("[google_broker] A URL will print below. Open it, pick your account, and on the", flush=True)
        print("[google_broker] permission screen make sure EVERY box is checked — especially", flush=True)
        print("[google_broker] Google Calendar — then click Continue/Allow.", flush=True)
        # prompt=consent forces the full granular consent screen every run (so Calendar is
        # always presented); roll to a free port so a lingering 8085 can't block a retry
        # (desktop OAuth clients accept http://localhost on any port).
        creds = None
        last_err = None
        for port in (8085, 8086, 8087, 8088, 8089):
            try:
                creds = flow.run_local_server(
                    port=port, open_browser=False,
                    prompt="consent", access_type="offline",
                )
                break
            except OSError as e:
                last_err = e
                print(f"[google_broker] port {port} busy ({e}); trying {port + 1}…", flush=True)
                continue
        if creds is None:
            print(f"[google_broker] could not bind a local callback port: {last_err}")
            sys.exit(1)
        granted = set(getattr(creds, "granted_scopes", None) or getattr(creds, "scopes", None) or [])
        if "https://www.googleapis.com/auth/calendar.events" not in granted:
            print("[google_broker] ⚠️ Calendar was NOT granted on the consent screen.", flush=True)
            print("[google_broker]    Re-run --setup and tick the Calendar permission.", flush=True)
        _SECRETS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        _TOKEN_FILE.chmod(0o600)
        print(f"[google_broker] token saved → {_TOKEN_FILE}", flush=True)
    except Exception as e:
        print(f"[google_broker] auth flow failed: {e}")
        sys.exit(1)


def _extract_auth_code(resp: str) -> str:
    """Pull the OAuth `code` out of a pasted redirect URL, or accept a bare code."""
    resp = resp.strip()
    if "code=" in resp:
        from urllib.parse import urlparse, parse_qs

        query = urlparse(resp).query if "://" in resp else resp.split("?", 1)[-1]
        codes = parse_qs(query).get("code")
        if codes:
            return codes[0]
    return resp


def run_auth_flow_manual() -> None:
    """OAuth that does NOT need the localhost callback to be reachable (robust on WSL2,
    where the Windows browser can't reach the server inside WSL). Prints the URL; the
    operator approves, copies the code from the redirected URL — even though the page
    says 'localhost refused to connect' — and pastes it back here."""
    if not _CREDS_FILE.exists():
        print(f"[google_broker] credentials.json not found at {_CREDS_FILE}")
        sys.exit(1)
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_FILE), _ACTIVE_SCOPES)
    flow.redirect_uri = "http://localhost:8085/"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\n1) Open this URL, pick your account, and APPROVE (keep the Calendar box checked):\n", flush=True)
    print(auth_url, flush=True)
    print("\n2) Your browser will land on a page that says 'localhost refused to connect'.", flush=True)
    print("   That is EXPECTED. Copy the FULL address-bar URL of that page (it contains", flush=True)
    print("   'code=...') and paste it below, then press Enter.\n", flush=True)
    resp = input("Paste the redirect URL (or just the code): ").strip()
    try:
        flow.fetch_token(code=_extract_auth_code(resp))
    except Exception as e:  # noqa: BLE001
        print(f"[google_broker] could not exchange that code: {e}")
        print("   (Codes are one-time + short-lived — re-run --setup and paste the fresh one.)")
        sys.exit(1)
    creds = flow.credentials
    granted = set(getattr(creds, "granted_scopes", None) or getattr(creds, "scopes", None) or [])
    if "https://www.googleapis.com/auth/calendar.events" not in granted:
        print("[google_broker] ⚠️ Calendar was NOT in the grant — re-run --setup and keep Calendar checked.", flush=True)
    _SECRETS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    _TOKEN_FILE.chmod(0o600)
    print(f"[google_broker] token saved → {_TOKEN_FILE}", flush=True)


def _calendar_selfcheck() -> "tuple[bool, object]":
    """Read-only probe: can we list calendars with the current credentials?
    Returns (ok, calendar_names) on success or (False, reason) on failure."""
    creds = _load_credentials()
    if creds is None:
        return False, "no usable credentials yet"
    try:
        from datetime import datetime, timezone
        from googleapiclient.discovery import build

        svc = build("calendar", "v3", credentials=creds)
        # The calendar.events scope grants EVENT access on 'primary' (it does NOT grant
        # calendarList.list — that needs a broader scope we deliberately don't request).
        now = datetime.now(timezone.utc).isoformat()
        events = svc.events().list(
            calendarId="primary", timeMin=now, maxResults=3,
            singleEvents=True, orderBy="startTime",
        ).execute()
        titles = [e.get("summary", "(untitled)") for e in events.get("items", [])]
        return True, titles or ["(calendar reachable — no upcoming events)"]
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def cmd_setup() -> None:
    """One-shot, foolproof Google Calendar setup: check first, authorize only if
    needed, then verify and confirm. Safe to run repeatedly."""
    print("=== OpenClaw Google Calendar setup ===", flush=True)
    if not _CREDS_FILE.exists():
        print(f"Missing OAuth client at {_CREDS_FILE} — that file already existed on this box,")
        print("so if you see this, restore it before continuing.")
        sys.exit(1)
    ok, detail = _calendar_selfcheck()
    if ok:
        print("✅ Calendar is ALREADY connected — nothing to do.", flush=True)
        print("   Calendars:", ", ".join(detail) if detail else "(none visible yet)", flush=True)
        return
    print("Calendar not authorized yet. Starting a one-time consent.", flush=True)
    print("A Google URL will print below — open it, approve (keep Calendar checked), then", flush=True)
    print("paste the redirect URL back here (works even on WSL where localhost won't connect).\n", flush=True)
    run_auth_flow_manual()
    print("", flush=True)
    ok, detail = _calendar_selfcheck()
    if ok:
        print("✅ Calendar connected! You're done.", flush=True)
        print("   Calendars:", ", ".join(detail) if detail else "(none visible yet)", flush=True)
    else:
        print("⚠️ Authorized, but the calendar check still failed:", detail, flush=True)
        print("   If the consent screen had a 'Calendar' checkbox you left unticked,", flush=True)
        print("   just run this again and tick everything.", flush=True)


def _ensure_google_libs() -> None:
    """If the Google client libs aren't importable (e.g. run under the system python),
    re-exec under the fleet venv that has them, so `python3 google_access_broker.py`
    just works no matter which interpreter the operator used."""
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
        return
    except ImportError:
        pass
    import os

    # Loop guard: venv pythons are usually symlinks to the SAME base binary, so we
    # compare invocation paths (abspath), not resolved symlinks — and never re-exec twice.
    if os.environ.get("_OPENCLAW_GBROKER_REEXEC") == "1":
        return  # already re-exec'd once; let the original ImportError surface
    for cand in ("/home/openclaw/chief_env/bin/python", "/home/openclaw/.openclaw/venv/bin/python"):
        if os.path.exists(cand) and os.path.abspath(cand) != os.path.abspath(sys.executable):
            print(f"[google_broker] re-running under {cand} (has the Google libraries)…", flush=True)
            os.environ["_OPENCLAW_GBROKER_REEXEC"] = "1"
            os.execv(cand, [cand, os.path.abspath(__file__), *sys.argv[1:]])
    # no suitable venv found — let the original ImportError surface downstream


if __name__ == "__main__":
    if any(a in sys.argv for a in ("--setup", "--check", "--auth", "--auth-manual")):
        _ensure_google_libs()
    if "--setup" in sys.argv:
        cmd_setup()
    elif "--check" in sys.argv:
        ok, detail = _calendar_selfcheck()
        print(("✅ calendar OK: " + ", ".join(detail)) if ok else f"❌ not connected: {detail}")
        sys.exit(0 if ok else 1)
    elif "--auth-manual" in sys.argv:
        run_auth_flow_manual()
    elif "--auth" in sys.argv:
        run_auth_flow()
    elif "--test-policy" in sys.argv:
        import subprocess
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "google_access_policy.py")],
            check=False,
        )
    else:
        print("Usage:")
        print("  python3 google_access_broker.py --setup         one-shot: check, authorize if needed, verify")
        print("  python3 google_access_broker.py --check         read-only: is calendar connected?")
        print("  python3 google_access_broker.py --auth          run OAuth2 flow only (local-server callback)")
        print("  python3 google_access_broker.py --auth-manual   OAuth2 paste-the-code flow (WSL-safe, no localhost callback)")
        print("  python3 google_access_broker.py --test-policy   run policy smoke test")
