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
import sys
import importlib
import secrets
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
    "broker_capability_token_fingerprint",
}
_AUDIT_BROKER_CAPABILITY_TOKEN_PARAM = "broker_capability_token"

BROKER_CAPABILITY_TOKEN_SCHEMA = "GOOGLE_BROKER_CAPABILITY_TOKEN_V0"
_BROKER_CAPABILITY_TOKEN_REQUIRED = frozenset(
    {
        "google.calendar.write",
        "google.calendar.delete",
        "google.contacts.read",
        "google.gmail.read.body",
        "google.gmail.draft.create",
        "google.gmail.send",
    }
)
_BROKER_CAPABILITY_TOKEN_REGISTRY: dict[str, dict[str, Any]] = {}

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


def _redact_broker_capability_token(value: Any) -> dict:
    if not isinstance(value, Mapping):
        return {"redacted": True}
    return {
        "schema_version": value.get("schema_version"),
        "token_fingerprint": value.get("token_fingerprint"),
        "agent": value.get("agent"),
        "capability": value.get("capability"),
        "issuer": value.get("issuer"),
        "send_hold_checked": value.get("send_hold_checked"),
        "send_hold_active": value.get("send_hold_active"),
        "redacted": True,
    }


def _redact_audit_params(params: Mapping[str, Any]) -> dict:
    redacted = {}
    for key, value in params.items():
        key_str = str(key)
        if key_str in _AUDIT_BODY_PARAM_KEYS:
            continue
        if key_str == _AUDIT_BROKER_CAPABILITY_TOKEN_PARAM:
            redacted[key_str] = _redact_broker_capability_token(value)
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


def _stable_token_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _token_fingerprint(record: Mapping[str, Any]) -> str:
    import hashlib

    public_record = {
        key: record.get(key)
        for key in (
            "schema_version",
            "token_id",
            "agent",
            "capability",
            "issuer",
            "request_id",
            "idempotency_key",
            "payload_hash",
            "authority_refs",
            "credential_lease_refs",
            "send_hold_checked",
            "send_hold_active",
            "send_hold_ref",
        )
    }
    return "sha256:" + hashlib.sha256(_stable_token_json(public_record).encode("utf-8")).hexdigest()


def broker_capability_token_required(capability: str) -> bool:
    """Return whether the broker refuses this capability without a minted token."""

    return capability in _BROKER_CAPABILITY_TOKEN_REQUIRED


def mint_send_hold_gated_broker_capability_token(
    *,
    agent: str,
    capability: str,
    issuer: str,
    request_id: str = "",
    idempotency_key: str = "",
    payload_hash: str = "",
    authority_refs: list[str] | tuple[str, ...] = (),
    credential_lease_refs: list[str] | tuple[str, ...] = (),
    send_hold_checked: bool,
    send_hold_active: bool = False,
    send_hold_ref: str = "",
) -> dict[str, Any]:
    """Mint a one-use broker token after an executor-level SEND_HOLD check."""

    agent = str(agent or "").strip().lower()
    capability = str(capability or "").strip()
    issuer = str(issuer or "").strip()
    request_id = str(request_id or "").strip()
    idempotency_key = str(idempotency_key or "").strip()
    payload_hash = str(payload_hash or "").strip()
    if not agent or not capability or not issuer:
        raise ValueError("agent, capability, and issuer are required")
    if not broker_capability_token_required(capability):
        raise ValueError(f"capability does not require a broker capability token: {capability}")
    if not send_hold_checked:
        raise ValueError("SEND_HOLD check is required before minting broker capability token")
    if send_hold_active:
        raise ValueError("SEND_HOLD is active; broker capability token not minted")
    if capability == "google.gmail.send" and (not request_id or idempotency_key != request_id or not payload_hash):
        raise ValueError("gmail send token requires request_id, matching idempotency_key, and payload_hash")

    record = {
        "schema_version": BROKER_CAPABILITY_TOKEN_SCHEMA,
        "token_id": "google_broker_capability:" + secrets.token_urlsafe(24),
        "agent": agent,
        "capability": capability,
        "issuer": issuer,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "payload_hash": payload_hash,
        "authority_refs": [str(ref) for ref in authority_refs if str(ref).strip()],
        "credential_lease_refs": [str(ref) for ref in credential_lease_refs if str(ref).strip()],
        "send_hold_checked": True,
        "send_hold_active": False,
        "send_hold_ref": str(send_hold_ref or ""),
        "consumed": False,
        "issued_at": datetime.now().isoformat(timespec="seconds"),
    }
    record["token_fingerprint"] = _token_fingerprint(record)
    _BROKER_CAPABILITY_TOKEN_REGISTRY[record["token_id"]] = dict(record)
    return {
        "schema_version": BROKER_CAPABILITY_TOKEN_SCHEMA,
        "token_id": record["token_id"],
        "token_fingerprint": record["token_fingerprint"],
        "agent": agent,
        "capability": capability,
        "issuer": issuer,
        "send_hold_checked": True,
        "send_hold_active": False,
    }


def _broker_capability_token_verdict(agent: str, capability: str, params: Mapping[str, Any]) -> tuple[bool, str]:
    if not broker_capability_token_required(capability):
        return True, ""
    token = params.get(_AUDIT_BROKER_CAPABILITY_TOKEN_PARAM)
    if not isinstance(token, Mapping):
        return False, f"broker capability token required for {capability}"
    if token.get("schema_version") != BROKER_CAPABILITY_TOKEN_SCHEMA:
        return False, "broker capability token schema mismatch"
    token_id = str(token.get("token_id") or "")
    fingerprint = str(token.get("token_fingerprint") or "")
    record = _BROKER_CAPABILITY_TOKEN_REGISTRY.get(token_id)
    if not record:
        return False, "broker capability token not minted by this broker process"
    if record.get("consumed"):
        return False, "broker capability token already consumed"
    if fingerprint != record.get("token_fingerprint"):
        return False, "broker capability token fingerprint mismatch"
    if str(record.get("agent") or "") != agent.lower():
        return False, "broker capability token agent mismatch"
    if str(record.get("capability") or "") != capability:
        return False, "broker capability token capability mismatch"
    if record.get("send_hold_checked") is not True or record.get("send_hold_active") is True:
        return False, "broker capability token missing successful SEND_HOLD check"

    context = params.get("approval_context") if isinstance(params.get("approval_context"), Mapping) else {}
    expected_request_id = str(record.get("request_id") or "")
    if expected_request_id:
        observed_request_id = str(params.get("exact_send_request_id") or context.get("request_id") or "")
        observed_idempotency_key = str(params.get("idempotency_key") or context.get("idempotency_key") or "")
        if observed_request_id != expected_request_id or observed_idempotency_key != expected_request_id:
            return False, "broker capability token request/idempotency mismatch"
    expected_payload_hash = str(record.get("payload_hash") or "")
    if expected_payload_hash:
        observed_payload_hash = str(context.get("payload_hash") or params.get("payload_hash") or "")
        if observed_payload_hash != expected_payload_hash:
            return False, "broker capability token payload hash mismatch"
    expected_authority_refs = list(record.get("authority_refs") or [])
    expected_lease_refs = list(record.get("credential_lease_refs") or [])
    if expected_authority_refs and list(context.get("authority_refs") or []) != expected_authority_refs:
        return False, "broker capability token authority refs mismatch"
    if expected_lease_refs and list(context.get("credential_lease_refs") or []) != expected_lease_refs:
        return False, "broker capability token credential lease refs mismatch"

    record["consumed"] = True
    _BROKER_CAPABILITY_TOKEN_REGISTRY[token_id] = record
    return True, ""


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
                all_events.extend(result.get("items", []))
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
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)

        list_resp = service.users().messages().list(
            userId="me", maxResults=max_results, labelIds=["INBOX"]
        ).execute()
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

    token_ok, token_error = _broker_capability_token_verdict(agent, capability, params)
    if not token_ok:
        _audit(agent, capability, params, False, token_error)
        return {"ok": False, "data": None, "error": token_error}

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
    if approval_class == "B":
        action = f"Google broker: {agent} → {capability}"
        if not _request_approval(action, tier=1, approval_context=params.get("approval_context")):
            _audit(agent, capability, params, False, "denied at L1")
            return {"ok": False, "data": None, "error": "denied at L1 approval gate"}
    elif approval_class == "C":
        action = f"Google broker: {agent} → {capability}"
        if not exact_send_gate_verified and not _request_approval(action, tier=2, approval_context=params.get("approval_context")):
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
        print("[google_broker] Open this URL in your Windows browser to authorize:", flush=True)
        print("[google_broker] (waiting on http://localhost:8085/ for the redirect callback)", flush=True)
        creds = flow.run_local_server(port=8085, open_browser=False)
        _SECRETS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        _TOKEN_FILE.chmod(0o600)
        print(f"[google_broker] token saved → {_TOKEN_FILE}")
        print(f"[google_broker] chmod 600 applied")
    except Exception as e:
        print(f"[google_broker] auth flow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if "--auth" in sys.argv:
        run_auth_flow()
    elif "--test-policy" in sys.argv:
        import subprocess
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "google_access_policy.py")],
            check=False,
        )
    else:
        print("Usage:")
        print("  python3 google_access_broker.py --auth          run OAuth2 flow")
        print("  python3 google_access_broker.py --test-policy   run policy smoke test")
