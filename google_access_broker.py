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
from datetime import datetime
from pathlib import Path


# ── Secrets paths ─────────────────────────────────────────────────────────────

_SECRETS_DIR = Path("/home/openclaw/.google-secrets")
_CREDS_FILE  = _SECRETS_DIR / "credentials.json"
_TOKEN_FILE  = _SECRETS_DIR / "token.json"


# ── Audit log ─────────────────────────────────────────────────────────────────

_AUDIT_LOG = Path("/mnt/c/OpenClaw/logs/google_access_audit.jsonl")


# ── Active OAuth scope bundle ─────────────────────────────────────────────────
# Pass 1 only. Do NOT add Pass 2/3 scopes until prior pass is verified and audited.
# Pass 2 adds: gmail.readonly
# Pass 3 adds: gmail.compose
# Each scope expansion requires a deliberate code change here + re-run of --auth.

_ACTIVE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.metadata",
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

def _audit(agent: str, capability: str, params: dict,
           result_ok: bool, error: str = "") -> None:
    """Append one JSONL line to the Google access audit log."""
    entry = {
        "ts":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent":      agent,
        "capability": capability,
        "params":     {k: v for k, v in params.items() if k != "body_text"},
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

def _request_approval(action: str, tier: int) -> bool:
    """
    Hook into the OpenClaw approval gate for Class B and C capabilities.
    Class A reads do not go through this — they are auto-proceed.
    Returns True if approved, False if denied or timed out.
    """
    try:
        from chief_approval_brain import request_approval
        return request_approval(action, requester="google_broker", explicit_tier=tier)
    except ImportError:
        print("[google_broker] approval gate unavailable — defaulting to deny", flush=True)
        return False


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
    _CALENDAR_ALLOWLIST = [
        "primary",
        "4hra0c8ektf0l3jqirb7aim018@group.calendar.google.com",
    ]
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
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }

            raw_from = headers.get("From", "")
            if "<" in raw_from:
                from_name = raw_from[: raw_from.index("<")].strip().strip('"')
            else:
                from_name = raw_from.split("@")[0].strip()
            if not from_name:
                from_name = raw_from

            messages.append({
                "message_id": msg_id,
                "from_name":  from_name,
                "subject":    headers.get("Subject", "(no subject)"),
                "date_raw":   headers.get("Date", ""),
                "labels":     detail.get("labelIds", []),
                "snippet":    detail.get("snippet", ""),
            })

        return {"ok": True, "data": messages, "error": ""}
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

    approval_class = get_class(agent, capability)

    # 2. Approval gate (Class B and C only)
    #    Class A reads auto-proceed — gating would make reads unusable.
    if approval_class == "B":
        action = f"Google broker: {agent} → {capability}"
        if not _request_approval(action, tier=1):
            _audit(agent, capability, params, False, "denied at L1")
            return {"ok": False, "data": None, "error": "denied at L1 approval gate"}
    elif approval_class == "C":
        action = f"Google broker: {agent} → {capability}"
        if not _request_approval(action, tier=2):
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
    elif capability == "google.gmail.read.metadata":
        result = _exec_gmail_read_metadata(creds, params)
    elif capability == "google.contacts.read":
        result = _exec_contacts_read(creds, params)
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
