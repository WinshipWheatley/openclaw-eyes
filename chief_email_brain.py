"""
chief_email_brain.py

Drafts and sends emails to clients via Gmail (App Password) or SMTP.
Every send requires explicit YES/NO approval in Telegram.
Draft mode works without credentials — sends require env vars.

Required env vars (one set):
  Gmail:        GMAIL_USER, GMAIL_APP_PASSWORD
  Generic SMTP: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

Client emails already in billing_records.csv.
Additional addresses stored in /mnt/c/OpenClawShared/business/contacts.json

Triggered by:
  - "send email" / "email to [name]" / "draft email" / "follow up email"
  - "email log" / "sent emails" / "email history"
Intent: email_draft / email_send in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/email_log.json  (source of truth)
  - openclaw-vault/Business/Email Log.md            (Obsidian)
"""

import csv
import json
import os
import re
import smtplib
import ssl
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from chief_llm import ollama_call, ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR  = Path("/mnt/c/OpenClawShared/business")
EMAIL_JSON    = BUSINESS_DIR / "email_log.json"
CONTACTS_JSON = BUSINESS_DIR / "contacts.json"
EMAIL_MD      = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/Email Log.md")
BILLING_CSV   = Path("/home/openclaw/OpenClaw/exports/billing_records.csv")
TRACKER_CSV   = Path("/mnt/c/OpenClaw/billing/tracker/invoice_tracker.csv")

# ── Credential check ───────────────────────────────────────────────────────────

def _smtp_config() -> dict | None:
    """Return SMTP config dict if credentials are present, else None."""
    if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        return {
            "host":     "smtp.gmail.com",
            "port":     465,
            "user":     os.environ["GMAIL_USER"],
            "password": os.environ["GMAIL_APP_PASSWORD"],
            "ssl":      True,
        }
    if all(os.environ.get(v) for v in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")):
        return {
            "host":     os.environ["SMTP_HOST"],
            "port":     int(os.environ["SMTP_PORT"]),
            "user":     os.environ["SMTP_USER"],
            "password": os.environ["SMTP_PASSWORD"],
            "ssl":      os.environ.get("SMTP_SSL", "true").lower() == "true",
        }
    return None


def _email_ready() -> bool:
    return _smtp_config() is not None


# ── Contact / email lookup ─────────────────────────────────────────────────────

def _load_contacts() -> dict:
    if CONTACTS_JSON.exists():
        try:
            return json.loads(CONTACTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"contacts": []}


def _lookup_email(name: str) -> str | None:
    """Search contacts.json, billing CSV, then invoice tracker for an email address."""
    name_lower = name.lower()

    # contacts.json first
    data = _load_contacts()
    for c in data.get("contacts", []):
        if name_lower in c.get("name", "").lower() and c.get("email"):
            return c["email"]

    # billing CSV fallback
    if BILLING_CSV.exists():
        try:
            with BILLING_CSV.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if name_lower in row.get("client_name", "").lower():
                        email = row.get("client_email", "").strip()
                        if email and "@" in email:
                            return email
        except Exception:
            pass

    # invoice tracker fallback
    if TRACKER_CSV.exists():
        try:
            with TRACKER_CSV.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if name_lower in row.get("client_name", "").lower():
                        email = row.get("client_email", "").strip()
                        if email and "@" in email:
                            return email
        except Exception:
            pass

    return None


def _save_contact_email(name: str, email: str) -> None:
    data     = _load_contacts()
    contacts = data.setdefault("contacts", [])
    for c in contacts:
        if c.get("name", "").lower() == name.lower():
            c["email"] = email
            CONTACTS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return
    contacts.append({"name": name, "email": email})
    CONTACTS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Email log storage ──────────────────────────────────────────────────────────

def _load_email_log() -> dict:
    if EMAIL_JSON.exists():
        try:
            return json.loads(EMAIL_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"messages": []}


def _save_email_log(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    EMAIL_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_email_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    data  = _load_email_log()
    count = sum(1 for m in data.get("messages", []) if m["id"].startswith(f"EMAIL-{today}"))
    return f"EMAIL-{today}-{count + 1:03d}"


def _log_email(to_name: str, to_email: str, subject: str, body: str,
               status: str, from_email: str = "") -> dict:
    entry = {
        "id":         _new_email_id(),
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "to_name":    to_name,
        "to_email":   to_email,
        "from_email": from_email,
        "subject":    subject,
        "body":       body,
        "status":     status,   # drafted | sent | failed | dry_run
    }
    data = _load_email_log()
    data.setdefault("messages", []).append(entry)
    _save_email_log(data)
    _write_email_md(data)
    return entry


# ── LLM: parse request and draft email ────────────────────────────────────────

_PARSE_PROMPT = """\
Extract email request details from this message.

Message: {text}

Return a JSON object with:
  to_name   — recipient name (string)
  to_email  — email address if explicitly mentioned, or null
  topic     — what the email should be about (string)
  context   — relevant context: invoice numbers, amounts, deadlines, etc.
  email_type — one of: invoice_followup | payment_received | introduction |
               general | contract | legal

Return only valid JSON, no markdown."""

_DRAFT_PROMPT = """\
You are drafting a professional email on behalf of Winship Wheatley IV
(artist name: Winship Live, label: Deep Pocket Records).

Recipient: {to_name}
Topic: {topic}
Context: {context}
Email type: {email_type}

Write a complete email with:
- Subject line (start with "Subject: ")
- Blank line
- Email body (professional but warm, 3-5 short paragraphs max)
- Sign-off: "Best,\nWinship\nDeep Pocket Records"

Plain text only. No markdown. Keep it concise."""


def _parse_email_request(text: str) -> dict:
    # Try LLM first
    prompt = _PARSE_PROMPT.format(text=text)
    parsed = ollama_json(prompt, timeout=20)
    if isinstance(parsed, dict) and parsed.get("topic"):
        return {
            "to_name":    (parsed.get("to_name") or "").strip() or None,
            "to_email":   (parsed.get("to_email") or "").strip() or None,
            "topic":      (parsed.get("topic") or text).strip(),
            "context":    (parsed.get("context") or "").strip(),
            "email_type": parsed.get("email_type", "general"),
        }

    # Regex fallback
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    to_email    = email_match.group(0) if email_match else None

    name_match = re.search(
        r"(?:email|send email to|draft email to|email to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        text, re.IGNORECASE,
    )
    to_name = name_match.group(1).strip() if name_match else None

    topic_match = re.search(r"(?:about|re:|regarding)\s+(.+)", text, re.IGNORECASE)
    topic = topic_match.group(1).strip() if topic_match else text

    inv_match = re.search(r"INV-\d+", text, re.IGNORECASE)
    context   = inv_match.group(0) if inv_match else ""

    # Detect email type
    t = text.lower()
    if any(k in t for k in ("follow up", "overdue", "payment due", "unpaid")):
        email_type = "invoice_followup"
    elif any(k in t for k in ("payment received", "receipt", "paid")):
        email_type = "payment_received"
    elif any(k in t for k in ("contract", "agreement", "terms")):
        email_type = "contract"
    elif any(k in t for k in ("invoice", "bill")):
        email_type = "invoice_followup"
    else:
        email_type = "general"

    return {
        "to_name":    to_name,
        "to_email":   to_email,
        "topic":      topic,
        "context":    context,
        "email_type": email_type,
    }


def _split_subject_body(raw: str) -> tuple[str, str]:
    """Split LLM output into (subject, body). Falls back gracefully."""
    lines = raw.strip().splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body_start = i + 1
            break

    # Skip blank line after subject
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()

    if not subject:
        subject = f"Message from Deep Pocket Records"
    if not body:
        body = raw.strip()

    return subject, body


def _draft_email(to_name: str, topic: str, context: str, email_type: str) -> tuple[str, str]:
    """Returns (subject, body)."""
    prompt = _DRAFT_PROMPT.format(
        to_name=to_name or "Valued Client",
        topic=topic,
        context=context or "none",
        email_type=email_type,
    )
    raw = ollama_call(prompt, timeout=30, lane="strong").strip()

    if not raw:
        # Fallback draft
        subject = f"Following up — Deep Pocket Records"
        body    = (
            f"Hi {to_name or 'there'},\n\n"
            f"I'm reaching out regarding {topic}.\n\n"
            f"Please let me know if you have any questions.\n\n"
            f"Best,\nWinship\nDeep Pocket Records"
        )
        return subject, body

    return _split_subject_body(raw)


# ── SMTP sender ────────────────────────────────────────────────────────────────

def _send_via_smtp(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Send an email. Returns (success, detail). Only called after approval."""
    config = _smtp_config()
    if not config:
        return False, "SMTP not configured"
    try:
        from_addr = config["user"]
        msg       = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = from_addr
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))

        if config["ssl"]:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(config["host"], config["port"], context=ctx) as server:
                server.login(config["user"], config["password"])
                server.sendmail(from_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(config["host"], config["port"]) as server:
                server.starttls()
                server.login(config["user"], config["password"])
                server.sendmail(from_addr, [to_email], msg.as_string())

        return True, from_addr
    except Exception as e:
        return False, str(e)


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_email_md(data: dict | None = None) -> None:
    if data is None:
        data = _load_email_log()
    messages = data.get("messages", [])
    today    = date.today().strftime("%Y-%m-%d")

    recent = sorted(messages, key=lambda m: m.get("date", ""), reverse=True)[:20]
    rows   = []
    for m in recent:
        rows.append(
            f"| {m['date']} | {m.get('to_name','?')} "
            f"| {m.get('subject','')[:50]} | {m.get('status','?')} |"
        )

    table = (
        "| Date | Recipient | Subject | Status |\n"
        "|---|---|---|---|\n"
        + ("\n".join(rows) if rows else "| — | — | — | (no emails yet) |")
    )

    sent    = sum(1 for m in messages if m.get("status") == "sent")
    drafted = sum(1 for m in messages if m.get("status") == "drafted")

    content = (
        "---\n"
        "type: email-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Email Log\n\n"
        "_Managed by `chief_email_brain.py` — do not edit manually._\n\n"
        f"**Sent:** {sent}  |  **Drafted:** {drafted}  |  **Total:** {len(messages)}\n\n"
        "## Recent Emails\n\n"
        + table + "\n\n"
        "## How to Send\n\n"
        "- `email [name] about [topic]`\n"
        "- `send follow up email to [name]`\n"
        "- Requires `GMAIL_USER` + `GMAIL_APP_PASSWORD` in `.chief.env`\n"
    )
    EMAIL_MD.parent.mkdir(parents=True, exist_ok=True)
    EMAIL_MD.write_text(content, encoding="utf-8")


# ── Pending draft state ────────────────────────────────────────────────────────

_PENDING_DRAFT: dict | None = None


def get_pending_draft() -> dict | None:
    return _PENDING_DRAFT


def clear_pending_draft() -> None:
    global _PENDING_DRAFT
    _PENDING_DRAFT = None


def confirm_send(approved: bool) -> list[str]:
    """Called by router when user replies YES/NO to a draft."""
    global _PENDING_DRAFT
    draft = _PENDING_DRAFT
    if not draft:
        return ["No pending email draft to confirm."]

    clear_pending_draft()

    if not approved:
        _log_email(draft["to_name"], draft["to_email"],
                   draft["subject"], draft["body"], "drafted")
        return ["Email cancelled. Draft saved to log."]

    if not _email_ready():
        _log_email(draft["to_name"], draft["to_email"],
                   draft["subject"], draft["body"], "dry_run")
        return [
            f"⚠️ DRY RUN — email credentials not configured.\n"
            f"Would have sent to {draft['to_name']} <{draft['to_email']}>:\n\n"
            f"Subject: {draft['subject']}\n\n"
            f"{draft['body']}\n\n"
            "Add GMAIL_USER + GMAIL_APP_PASSWORD to .chief.env to enable sending."
        ]

    success, detail = _send_via_smtp(draft["to_email"], draft["subject"], draft["body"])
    if success:
        _log_email(draft["to_name"], draft["to_email"],
                   draft["subject"], draft["body"], "sent", detail)
        return [
            f"✅ Email sent to {draft['to_name']} <{draft['to_email']}>\n"
            f"Subject: {draft['subject']}"
        ]
    else:
        _log_email(draft["to_name"], draft["to_email"],
                   draft["subject"], draft["body"], "failed")
        return [f"❌ Email failed: {detail}"]


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    global _PENDING_DRAFT
    t = text.lower().strip()

    # ── Email history ──────────────────────────────────────────────────────────
    if any(k in t for k in ("email log", "sent emails", "email history", "outbox")):
        data  = _load_email_log()
        msgs  = data.get("messages", [])
        _write_email_md(data)
        if not msgs:
            return ["No emails logged yet.\n\nTo draft: 'email [name] about [topic]'"]
        recent = sorted(msgs, key=lambda m: m.get("date", ""), reverse=True)[:10]
        lines  = [f"📧 Email Log — last {len(recent)} messages\n"]
        for m in recent:
            lines.append(
                f"• {m['date']}  →  {m.get('to_name','?')}  [{m.get('status','?')}]\n"
                f"  {m.get('subject','')}"
            )
        return ["\n".join(lines)]

    # ── Draft an email ─────────────────────────────────────────────────────────
    parsed   = _parse_email_request(text)
    to_name  = parsed["to_name"] or "Unknown"
    to_email = parsed["to_email"]

    # Look up email from contacts/billing CSV if not provided inline
    if not to_email and parsed["to_name"]:
        to_email = _lookup_email(parsed["to_name"])

    if not to_email:
        return [
            f"I need an email address for {to_name}.\n"
            f"Try: 'email {to_name} someone@example.com about [topic]'\n"
            f"Or their email may already be in billing records if they're a client."
        ]

    # Save email to contacts if given inline
    if parsed["to_name"] and parsed["to_email"]:
        _save_contact_email(parsed["to_name"], parsed["to_email"])

    subject, body = _draft_email(
        to_name, parsed["topic"], parsed["context"], parsed["email_type"]
    )

    _PENDING_DRAFT = {
        "to_name":  to_name,
        "to_email": to_email,
        "subject":  subject,
        "body":     body,
    }

    preview_body = body[:300] + "..." if len(body) > 300 else body

    from chief_notify import send as _notify_send
    _notify_send(
        f"📧 Draft email to {to_name} <{to_email}>\n\n"
        f"Subject: {subject}\n\n"
        f"{preview_body}\n\n"
        f"Approval request sent to Guardian. Tap Approve to send."
    )

    from chief_approval_brain import request_approval
    approved = request_approval(
        action=f"send email to {to_name}: {subject}",
        requester="chief_email_brain",
    )
    return confirm_send(approved)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "email log"
    print(f"Running email brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nEmail Log MD: {EMAIL_MD}")
    print(f"Email JSON:   {EMAIL_JSON}")
