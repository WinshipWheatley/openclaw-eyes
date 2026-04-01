#!/usr/bin/env python3
"""8AM CEO Briefing generator + sender (Deep-Flight autopilot)."""

from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")
QUEUE_DIR = Path("/home/openclaw/polish_loop/tasks")
PENDING_APPROVAL = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
BUDGET_STATE = Path("/home/openclaw/.budget_state.json")
REPORT_LOG = Path("/mnt/c/OpenClaw/logs/ceo_briefing.log")
LIFE_SYNC_FILE = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Life Sync.md")

TO_EMAIL = os.environ.get("CEO_BRIEF_EMAIL", "WinshipLive@gmail.com")
SUBJECT = "Morning Executive Summary"


def _load_env() -> None:
    env_file = Path("/home/openclaw/.chief.env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:]
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _log(msg: str) -> None:
    REPORT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def _night_window() -> tuple[datetime, datetime]:
    tz = ZoneInfo("America/New_York") if ZoneInfo else None
    now = datetime.now(tz) if tz else datetime.now()
    end = now
    start = now - timedelta(hours=12)
    return start, end


def _completed_overnight() -> tuple[int, list[str]]:
    start, end = _night_window()
    count = 0
    names: list[str] = []
    if not ARCHIVE_DIR.exists():
        return 0, []
    for p in sorted(ARCHIVE_DIR.glob("task_*.md")):
        ts = datetime.fromtimestamp(p.stat().st_mtime, tz=start.tzinfo)
        if start <= ts <= end:
            count += 1
            name = p.stem[len("task_"):].rsplit("_", 1)[0]
            names.append(name)
    return count, names[-5:]


def _gate_summary() -> str:
    if not PENDING_APPROVAL.exists():
        return "The Gate: no pending approval record found."
    try:
        data = json.loads(PENDING_APPROVAL.read_text())
    except Exception:
        return "The Gate: pending approval record unreadable."
    if data.get("status") == "pending":
        aid = data.get("id", "unknown")
        action = str(data.get("action", "")).strip()[:140]
        return f"The Gate: 1 approval waiting (id={aid}) — {action}"
    return "The Gate: no actions currently waiting for approval click."


def _health_summary() -> str:
    try:
        import budget_tracker
        status = budget_tracker.get_budget_status()
        spent = status.get("global_spent", 0)
        cap = status.get("global_cap", 0)
        zone = status.get("budget_zone", "unknown")
        stuck = status.get("stuck_loop", False)
        burst = "ON" if zone in ("orange", "red") or stuck else "NORMAL"
        return (
            f"Health: billing spend ${spent:.2f}/${cap:.2f}, zone={zone}; "
            f"Limit Bust protection={burst}."
        )
    except Exception:
        if BUDGET_STATE.exists():
            return "Health: budget tracker fallback active; detailed zone unavailable."
        return "Health: budget tracker unavailable."


def _life_sync_summary() -> str:
    weather = "Annapolis weather/surf report not connected; review local surf app before first break."
    tee = "Golf tee time reminder: confirm today's tee block in Ops schedule."

    if LIFE_SYNC_FILE.exists():
        try:
            text = LIFE_SYNC_FILE.read_text(errors="replace")
            low = text.lower()
            if "annapolis" in low and "surf" in low:
                weather = "Annapolis life-sync loaded from vault context."
            if "golf" in low and "tee" in low:
                tee = "Golf tee time found in vault life-sync notes."
        except Exception:
            pass
    return f"Life-Sync: {weather} {tee}"


def build_summary() -> str:
    count, recent = _completed_overnight()
    recent_text = ", ".join(recent) if recent else "none"
    queue_depth = len(list(QUEUE_DIR.glob("*.md"))) if QUEUE_DIR.exists() else 0

    lines = [
        "Morning Executive Summary",
        "",
        f"Progress: {count} tasks completed overnight. Recent: {recent_text}.",
        _gate_summary(),
        _health_summary(),
        _life_sync_summary(),
        f"Queue: {queue_depth} tasks ready for execution.",
    ]
    return "\n".join(lines)


def _smtp_config() -> dict | None:
    if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD"):
        return {
            "host": "smtp.gmail.com",
            "port": 465,
            "user": os.environ["GMAIL_USER"],
            "password": os.environ["GMAIL_APP_PASSWORD"],
            "ssl": True,
        }
    if all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")):
        return {
            "host": os.environ["SMTP_HOST"],
            "port": int(os.environ["SMTP_PORT"]),
            "user": os.environ["SMTP_USER"],
            "password": os.environ["SMTP_PASSWORD"],
            "ssl": os.environ.get("SMTP_SSL", "true").lower() == "true",
        }
    return None


def send_summary() -> tuple[bool, str]:
    body = build_summary()
    cfg = _smtp_config()

    msg = MIMEMultipart("alternative")
    if cfg:
        msg["From"] = cfg["user"]
    msg["To"] = TO_EMAIL
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(body, "plain", "utf-8"))

    smtp_error = "smtp unavailable"
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
            return True, "smtp"
        except Exception as exc:
            smtp_error = str(exc)

    # Gmail API fallback if compose scope exists.
    try:
        from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
        from googleapiclient.discovery import build  # type: ignore[import-not-found]
        token = Path("/home/openclaw/.google-secrets/token.json")
        if not token.exists():
            return False, f"{smtp_error}; gmail token missing"
        creds = Credentials.from_authorized_user_file(
            str(token),
            scopes=["https://www.googleapis.com/auth/gmail.compose"],
        )
        service = build("gmail", "v1", credentials=creds)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, "gmail_api"
    except Exception as exc:
        return False, f"{smtp_error}; gmail api fallback failed: {exc}"


if __name__ == "__main__":
    _load_env()
    ok, detail = send_summary()
    if ok:
        _log(f"CEO briefing sent via {detail}")
        print("CEO_BRIEFING_SENT")
    else:
        _log(f"CEO briefing failed: {detail}")
        print(f"CEO_BRIEFING_FAILED: {detail}")
        raise SystemExit(1)
