#!/usr/bin/env python3
"""One-off SMTP sender for the Inner Circle demo dashboard attachment."""

import os
import smtplib
import ssl
import sys
import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ATTACHMENT = Path("/home/openclaw/mac_eyes/inner_circle_command_center_mock.html")
TO_EMAIL = "WinshipLive@gmail.com"
SUBJECT = "Inner Circle Demo Dashboard (Mock)"
BODY = (
    "Winship,\n\n"
    "Attached is the mock Executive Command Center dashboard for the Inner Circle demo.\n"
    "Open the HTML file on your phone browser (or files app preview).\n\n"
    "- OpenClaw Runtime"
)


def smtp_config() -> dict | None:
    if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        return {
            "host": "smtp.gmail.com",
            "port": 465,
            "user": os.environ["GMAIL_USER"],
            "password": os.environ["GMAIL_APP_PASSWORD"],
            "ssl": True,
        }

    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")
    if all(os.environ.get(k) for k in required):
        return {
            "host": os.environ["SMTP_HOST"],
            "port": int(os.environ["SMTP_PORT"]),
            "user": os.environ["SMTP_USER"],
            "password": os.environ["SMTP_PASSWORD"],
            "ssl": os.environ.get("SMTP_SSL", "true").lower() == "true",
        }
    return None


def send_once() -> tuple[bool, str]:
    if not ATTACHMENT.exists():
        return False, f"Attachment missing: {ATTACHMENT}"

    cfg = smtp_config()

    msg = MIMEMultipart("mixed")
    if cfg:
        msg["From"] = cfg["user"]
    msg["To"] = TO_EMAIL
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(BODY, "plain", "utf-8"))

    part = MIMEApplication(ATTACHMENT.read_bytes(), Name=ATTACHMENT.name)
    part["Content-Disposition"] = f'attachment; filename="{ATTACHMENT.name}"'
    part["Content-Type"] = "text/html; charset=utf-8"
    msg.attach(part)

    if cfg:
        try:
            if cfg["ssl"]:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=context) as server:
                    server.login(cfg["user"], cfg["password"])
                    server.sendmail(cfg["user"], [TO_EMAIL], msg.as_string())
            else:
                with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                    server.starttls()
                    server.login(cfg["user"], cfg["password"])
                    server.sendmail(cfg["user"], [TO_EMAIL], msg.as_string())
            return True, "smtp handed off"
        except Exception as smtp_exc:
            smtp_error = str(smtp_exc)
    else:
        smtp_error = "SMTP credentials not configured"

    # Fallback: Gmail API send with OAuth token from existing broker credentials.
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = Path("/home/openclaw/.google-secrets/token.json")
        if not token_path.exists():
            return False, f"{smtp_error}; gmail api token missing"

        creds = Credentials.from_authorized_user_file(
            str(token_path),
            scopes=["https://www.googleapis.com/auth/gmail.compose"],
        )
        service = build("gmail", "v1", credentials=creds)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, "gmail api handed off"
    except Exception as api_exc:
        return False, f"{smtp_error}; gmail api fallback failed: {api_exc}"


if __name__ == "__main__":
    ok, detail = send_once()
    if ok:
        print("SUCCESS: Demo Dashboard sent to mobile.")
        sys.exit(0)
    print(f"SEND_FAILED: {detail}")
    sys.exit(1)
