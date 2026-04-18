"""
chief_sms_brain.py

Drafts and sends SMS messages to clients via Twilio.
Every send requires explicit approval from chief_approval_brain.

Draft mode works without Twilio credentials — sends require:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .chief.env

Client phone numbers stored in /mnt/c/OpenClawShared/business/contacts.json
or can be provided inline: "text +12025551234 about..."

Triggered by:
  - "send sms" / "text [name/number]" / "draft sms" / "draft a text"
  - "sms log" / "sent texts" / "text history"
Intent: sms_draft in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/sms_log.json   (source of truth)
  - /mnt/c/OpenClawShared/business/contacts.json  (phone book)
  - openclaw-vault/Business/SMS Log.md             (Obsidian)
"""

import json
import os
import re
from datetime import datetime, date
from pathlib import Path

from chief_llm import ollama_call, ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR  = Path("/mnt/c/OpenClawShared/business")
SMS_JSON      = BUSINESS_DIR / "sms_log.json"
CONTACTS_JSON = BUSINESS_DIR / "contacts.json"
SMS_MD        = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/SMS Log.md")

# ── Twilio credentials (runtime check) ────────────────────────────────────────

def _twilio_ready() -> bool:
    return all(os.environ.get(v) for v in (
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"
    ))


# ── Contacts ───────────────────────────────────────────────────────────────────

def _load_contacts() -> dict:
    if CONTACTS_JSON.exists():
        try:
            return json.loads(CONTACTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"contacts": []}


def _save_contacts(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    CONTACTS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _lookup_number(name: str) -> str | None:
    """Find a phone number by contact name (case-insensitive partial match)."""
    data = _load_contacts()
    name_lower = name.lower()
    for c in data.get("contacts", []):
        if name_lower in c.get("name", "").lower():
            return c.get("phone")
    return None


def _save_contact(name: str, phone: str) -> None:
    """Add or update a contact's phone number."""
    data = _load_contacts()
    contacts = data.setdefault("contacts", [])
    for c in contacts:
        if c.get("name", "").lower() == name.lower():
            c["phone"] = phone
            _save_contacts(data)
            return
    contacts.append({"name": name, "phone": phone})
    _save_contacts(data)


# ── SMS log storage ────────────────────────────────────────────────────────────

def _load_sms_log() -> dict:
    if SMS_JSON.exists():
        try:
            return json.loads(SMS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"messages": []}


def _save_sms_log(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    SMS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_sms_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    data  = _load_sms_log()
    count = sum(1 for m in data.get("messages", []) if m["id"].startswith(f"SMS-{today}"))
    return f"SMS-{today}-{count + 1:03d}"


def _log_message(to_name: str, to_number: str, body: str,
                 status: str, twilio_sid: str = "") -> dict:
    entry = {
        "id":          _new_sms_id(),
        "date":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "to_name":     to_name,
        "to_number":   to_number,
        "body":        body,
        "status":      status,          # drafted | sent | failed | dry_run
        "twilio_sid":  twilio_sid,
        "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M") if status == "sent" else None,
    }
    data = _load_sms_log()
    data.setdefault("messages", []).append(entry)
    _save_sms_log(data)
    _write_sms_md(data)
    return entry


# ── LLM: parse request and draft message ──────────────────────────────────────

_PARSE_PROMPT = """\
Extract SMS request details from this message.

Message: {text}

Return a JSON object with:
  to_name   — recipient name (string, or null if only a number was given)
  to_number — phone number in E.164 format if present (e.g. "+12025551234"), or null
  topic     — what the SMS should be about (string)
  context   — any extra context mentioned (invoice number, amount, deadline, etc.)

Return only valid JSON, no markdown."""

_DRAFT_PROMPT = """\
You are drafting a professional SMS on behalf of Winship Wheatley IV
(Winship Live / Deep Pocket Records).

Recipient: {to_name}
Topic: {topic}
Context: {context}

Rules:
- SMS must be under 160 characters
- Friendly but professional
- End with a clear next step or question if appropriate
- Plain text only — no markdown, no emojis unless natural

Draft the SMS message only, nothing else."""


def _parse_sms_request(text: str) -> dict:
    # Try LLM first
    prompt = _PARSE_PROMPT.format(text=text)
    parsed = ollama_json(prompt, timeout=20)
    if isinstance(parsed, dict) and parsed.get("topic"):
        return {
            "to_name":   (parsed.get("to_name") or "").strip() or None,
            "to_number": (parsed.get("to_number") or "").strip() or None,
            "topic":     (parsed.get("topic") or text).strip(),
            "context":   (parsed.get("context") or "").strip(),
        }

    # Regex fallback
    number_match = re.search(r"\+?1?\d{10,11}", text)
    to_number    = number_match.group(0) if number_match else None
    if to_number and not to_number.startswith("+"):
        to_number = "+1" + to_number.lstrip("1") if len(to_number) == 11 else "+1" + to_number

    # Extract name: "text/sms [Name]" pattern
    name_match = re.search(
        r"(?:text|sms|send sms to|draft sms to|send a text to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        text, re.IGNORECASE,
    )
    to_name = name_match.group(1).strip() if name_match else None

    # Topic: everything after "about" or "re:" or "regarding"
    topic_match = re.search(r"(?:about|re:|regarding)\s+(.+)", text, re.IGNORECASE)
    topic = topic_match.group(1).strip() if topic_match else text

    # Context: invoice numbers
    inv_match = re.search(r"INV-\d+", text, re.IGNORECASE)
    context = inv_match.group(0) if inv_match else ""

    return {
        "to_name":   to_name,
        "to_number": to_number,
        "topic":     topic,
        "context":   context,
    }


def _draft_sms(to_name: str, topic: str, context: str) -> str:
    prompt = _DRAFT_PROMPT.format(
        to_name=to_name or "the recipient",
        topic=topic,
        context=context or "none",
    )
    result = ollama_call(prompt, timeout=20, lane="strong").strip()
    if not result:
        return f"Hi, this is Winship from Deep Pocket Records. {topic}. Please reply or call me back. Thanks."
    # Hard cap at 160 chars
    if len(result) > 160:
        result = result[:157] + "..."
    return result


# ── Twilio sender ──────────────────────────────────────────────────────────────

def _send_via_twilio(to_number: str, body: str) -> tuple[bool, str]:
    """
    Send an SMS via Twilio. Returns (success, twilio_sid_or_error).
    Only called after explicit approval.
    """
    try:
        from twilio.rest import Client
        sid    = os.environ["TWILIO_ACCOUNT_SID"]
        token  = os.environ["TWILIO_AUTH_TOKEN"]
        from_  = os.environ["TWILIO_FROM_NUMBER"]
        client = Client(sid, token)
        msg    = client.messages.create(body=body, from_=from_, to=to_number)
        return True, msg.sid
    except Exception as e:
        return False, str(e)


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_sms_md(data: dict | None = None) -> None:
    if data is None:
        data = _load_sms_log()
    messages = data.get("messages", [])
    today    = date.today().strftime("%Y-%m-%d")

    recent = sorted(messages, key=lambda m: m.get("date", ""), reverse=True)[:20]
    rows = []
    for m in recent:
        body_preview = m.get("body", "")[:60]
        rows.append(
            f"| {m['date']} | {m.get('to_name','?')} "
            f"| {m.get('status','?')} | {body_preview} |"
        )

    table = (
        "| Date | Recipient | Status | Message Preview |\n"
        "|---|---|---|---|\n"
        + ("\n".join(rows) if rows else "| — | — | — | (no messages yet) |")
    )

    sent  = sum(1 for m in messages if m.get("status") == "sent")
    draft = sum(1 for m in messages if m.get("status") == "drafted")

    content = (
        "---\n"
        "type: sms-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# SMS Log\n\n"
        "_Managed by `chief_sms_brain.py` — do not edit manually._\n\n"
        f"**Sent:** {sent}  |  **Drafted:** {draft}  |  **Total:** {len(messages)}\n\n"
        "## Recent Messages\n\n"
        + table + "\n\n"
        "## How to Send\n\n"
        "- `text [name] about [topic]`\n"
        "- `draft sms to [name] re: [topic]`\n"
        "- Requires `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` in env\n"
    )
    SMS_MD.parent.mkdir(parents=True, exist_ok=True)
    SMS_MD.write_text(content, encoding="utf-8")


# ── Draft pending state ────────────────────────────────────────────────────────
# Stored in memory only — drafts not persisted between sessions.
# The user sees the draft, replies YES/NO, and the listener handles it.

_PENDING_DRAFT: dict | None = None


def get_pending_draft() -> dict | None:
    return _PENDING_DRAFT


def clear_pending_draft() -> None:
    global _PENDING_DRAFT
    _PENDING_DRAFT = None


def confirm_send(approved: bool) -> list[str]:
    """
    Called by the router when user replies YES/NO to a draft.
    Returns reply strings.
    """
    global _PENDING_DRAFT
    draft = _PENDING_DRAFT
    if not draft:
        return ["No pending SMS draft to confirm."]

    clear_pending_draft()

    if not approved:
        _log_message(draft["to_name"], draft["to_number"], draft["body"], "drafted")
        return ["SMS cancelled. Draft saved to log."]

    if not _twilio_ready():
        _log_message(draft["to_name"], draft["to_number"], draft["body"], "dry_run")
        return [
            f"⚠️ DRY RUN — Twilio not configured.\n"
            f"Would have sent to {draft['to_name']} ({draft['to_number']}):\n\n"
            f"{draft['body']}\n\n"
            "Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER to .chief.env to enable sending."
        ]

    success, sid_or_err = _send_via_twilio(draft["to_number"], draft["body"])
    if success:
        _log_message(draft["to_name"], draft["to_number"], draft["body"], "sent", sid_or_err)
        return [f"✅ SMS sent to {draft['to_name']} ({draft['to_number']})\nSID: {sid_or_err}"]
    else:
        _log_message(draft["to_name"], draft["to_number"], draft["body"], "failed")
        return [f"❌ SMS failed: {sid_or_err}"]


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    global _PENDING_DRAFT
    t = text.lower().strip()

    # ── SMS history ────────────────────────────────────────────────────────────
    if any(k in t for k in ("sms log", "sent texts", "text history", "message log")):
        data = _load_sms_log()
        msgs = data.get("messages", [])
        _write_sms_md(data)
        if not msgs:
            return ["No SMS messages logged yet.\n\nTo draft: 'text [name] about [topic]'"]
        recent = sorted(msgs, key=lambda m: m.get("date",""), reverse=True)[:10]
        lines  = [f"📱 SMS Log — last {len(recent)} messages\n"]
        for m in recent:
            lines.append(
                f"• {m['date']}  →  {m.get('to_name','?')}  [{m.get('status','?')}]\n"
                f"  {m.get('body','')[:80]}"
            )
        return ["\n".join(lines)]

    # ── Draft an SMS ───────────────────────────────────────────────────────────
    parsed = _parse_sms_request(text)
    to_name   = parsed["to_name"] or "Unknown"
    to_number = parsed["to_number"]

    # Try looking up number from contacts if not provided inline
    if not to_number and parsed["to_name"]:
        to_number = _lookup_number(parsed["to_name"])

    if not to_number:
        return [
            f"I need a phone number for {to_name}.\n"
            f"Try: 'text {to_name} +12025551234 about [topic]'\n"
            f"Or save their number: 'save contact {to_name} +12025551234'"
        ]

    # Save contact if number was given inline
    if parsed["to_name"] and parsed["to_number"]:
        _save_contact(parsed["to_name"], parsed["to_number"])

    body = _draft_sms(to_name, parsed["topic"], parsed["context"])

    # Store draft in pending state
    _PENDING_DRAFT = {
        "to_name":   to_name,
        "to_number": to_number,
        "body":      body,
    }

    twilio_status = "✅ Twilio configured" if _twilio_ready() else "⚠️ Twilio not configured — dry run only"
    return [
        f"📱 Draft SMS to {to_name} ({to_number})\n\n"
        f"{body}\n\n"
        f"({len(body)} chars)  {twilio_status}\n\n"
        f"Reply YES to send, NO to cancel."
    ]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "sms log"
    print(f"Running SMS brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nSMS Log MD: {SMS_MD}")
    print(f"SMS JSON:   {SMS_JSON}")
