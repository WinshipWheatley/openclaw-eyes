"""Status/dry-run inspection for Cassandra send-capable services.

This module only inspects safe metadata and emits no-send posture. It does not
send Telegram/Gmail/email/calendar messages, deliver briefings, trigger voice,
approve actions, or execute Repo B code.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cassandra_no_send_reload_guard import (
    STATUS_DRY_RUN_MODE,
    outbound_delivery_blocked,
)


SCHEMA_VERSION = "cassandra_send_status_dry_run_v0"
ROOT = Path(__file__).resolve().parent
FOLLOWUP_LOG_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl")
FUTURE_ACTION_DB_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_future_actions.db")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "cassandra_send_status_dry_run.json"
OPERATOR_EXPORT_NAME = "cassandra_send_status_dry_run_OPERATOR.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def write_json(path: str | Path, payload: Any) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_json(payload), encoding="utf-8")
    return display_path(target)


def write_text(path: str | Path, text: str) -> str:
    target = rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return display_path(target)


def display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def inspect_pending_followups(path: str | Path = FOLLOWUP_LOG_PATH) -> dict[str, Any]:
    """Count followup statuses without returning raw message text."""
    target = Path(path)
    status_counts: dict[str, int] = {}
    malformed_count = 0
    total_count = 0
    if not target.exists():
        return {
            "source_exists": False,
            "inspection": "metadata_status_counts_only",
            "total_count": 0,
            "status_counts": {},
            "pending_count": 0,
            "malformed_count": 0,
            "raw_message_text_returned": False,
            "delivery_blocked": True,
        }

    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        total_count += 1
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            malformed_count += 1
            continue
        status = str(payload.get("status") or "unknown").strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "source_exists": True,
        "inspection": "metadata_status_counts_only",
        "total_count": total_count,
        "status_counts": dict(sorted(status_counts.items())),
        "pending_count": status_counts.get("pending", 0),
        "malformed_count": malformed_count,
        "raw_message_text_returned": False,
        "delivery_blocked": True,
    }


def inspect_future_actions(
    db_path: str | Path = FUTURE_ACTION_DB_PATH,
    *,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Count future-action rows without returning request text or chat IDs."""
    target = Path(db_path)
    if not target.exists():
        return {
            "source_exists": False,
            "inspection": "metadata_counts_only",
            "pending_count": 0,
            "due_count": 0,
            "status_counts": {},
            "request_text_returned": False,
            "chat_ids_returned": False,
            "dispatch_blocked": True,
        }

    now_value = now_iso or datetime.now().isoformat(timespec="seconds")
    status_counts: dict[str, int] = {}
    due_count = 0
    with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM future_actions GROUP BY status").fetchall()
        status_counts = {str(row["status"]): int(row["count"]) for row in rows}
        due_row = conn.execute(
            "SELECT COUNT(*) AS count FROM future_actions WHERE status = 'pending' AND due_at <= ?",
            (now_value,),
        ).fetchone()
        due_count = int(due_row["count"]) if due_row else 0

    return {
        "source_exists": True,
        "inspection": "metadata_counts_only",
        "pending_count": status_counts.get("pending", 0),
        "due_count": due_count,
        "status_counts": dict(sorted(status_counts.items())),
        "request_text_returned": False,
        "chat_ids_returned": False,
        "dispatch_blocked": True,
    }


def inspect_briefing_scheduler() -> dict[str, Any]:
    """Inspect briefing schedule state without generating or delivering text."""
    try:
        from cassandra_briefing_brain import due_slots, pending_briefings
    except Exception as exc:
        return {
            "inspection": "failed_import",
            "error_type": exc.__class__.__name__,
            "due_slots": [],
            "pending_count": 0,
            "pending_slots": [],
            "generation_blocked": True,
            "delivery_blocked": True,
            "raw_briefing_text_returned": False,
        }

    due = list(due_slots())
    pending = pending_briefings()
    pending_slots = sorted({str(entry.get("slot") or "unknown") for entry in pending})
    return {
        "inspection": "schedule_metadata_only",
        "due_slots": due,
        "due_count": len(due),
        "pending_count": len(pending),
        "pending_slots": pending_slots,
        "generation_blocked": True,
        "delivery_blocked": True,
        "telegram_delivery_blocked": True,
        "voice_delivery_blocked": True,
        "raw_briefing_text_returned": False,
    }


def build_watcher_status(
    *,
    followup_path: str | Path = FOLLOWUP_LOG_PATH,
    future_action_db_path: str | Path = FUTURE_ACTION_DB_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "service": "cassandra-watcher.service",
        "generated_at": generated_at or utc_now(),
        "mode": STATUS_DRY_RUN_MODE,
        "advanced_beyond_startup_guard": True,
        "outbound_delivery_blocked": outbound_delivery_blocked(),
        "pending_followups": inspect_pending_followups(followup_path),
        "future_actions": inspect_future_actions(future_action_db_path),
        "email_gmail_polling": {
            "posture": "blocked_dry_run_only",
            "polled": False,
            "gmail_or_email_send_triggered": False,
        },
        "ambient_chirp": {
            "posture": "blocked_dry_run_only",
            "evaluated_message_text": False,
            "telegram_delivery_blocked": True,
            "voice_delivery_blocked": True,
        },
        "blocked_outbound_paths": [
            "pending_followup_email_draft",
            "pending_followup_telegram_fallback",
            "inbound_email_reply_poll",
            "future_action_telegram_reminder",
            "ambient_telegram_chirp",
            "ambient_voice_delivery",
        ],
        "real_telegram_send_triggered": False,
        "real_gmail_or_email_send_triggered": False,
        "real_voice_delivery_triggered": False,
    }


def build_briefing_scheduler_status(*, generated_at: str | None = None) -> dict[str, Any]:
    briefing = inspect_briefing_scheduler()
    return {
        "service": "cassandra-briefing-scheduler.service",
        "generated_at": generated_at or utc_now(),
        "mode": STATUS_DRY_RUN_MODE,
        "advanced_beyond_startup_guard": True,
        "outbound_delivery_blocked": outbound_delivery_blocked(),
        "briefing_schedule": briefing,
        "blocked_outbound_paths": [
            "briefing_generation_to_delivery",
            "pending_briefing_delivery",
            "telegram_briefing_delivery",
            "voice_briefing_delivery",
        ],
        "real_telegram_send_triggered": False,
        "real_briefing_delivery_triggered": False,
        "real_voice_delivery_triggered": False,
    }


def format_service_status_marker(service_name: str, status: dict[str, Any]) -> str:
    if service_name == "cassandra_watcher":
        followups = status.get("pending_followups") or {}
        future = status.get("future_actions") or {}
        return (
            "[cassandra_watcher] status-dry-run: "
            f"pending_followups={followups.get('pending_count', 0)} "
            f"future_actions_pending={future.get('pending_count', 0)} "
            f"future_actions_due={future.get('due_count', 0)} "
            "email_polling=blocked outbound=blocked"
        )

    briefing = status.get("briefing_schedule") or {}
    return (
        "[briefing_scheduler] status-dry-run: "
        f"due_slots={','.join(briefing.get('due_slots') or []) or 'none'} "
        f"pending_briefings={briefing.get('pending_count', 0)} "
        "telegram_delivery=blocked voice_delivery=blocked"
    )


def build_status_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "mode": STATUS_DRY_RUN_MODE,
        "runtime_authority_changed": False,
        "send_authority_added": False,
        "guard_removed": False,
        "real_telegram_send_triggered": False,
        "real_gmail_or_email_send_triggered": False,
        "real_briefing_delivery_triggered": False,
        "real_voice_delivery_triggered": False,
        "niles_used_for_cassandra_path": False,
        "identity_resolution": {
            "cassandra_bot_identity_expected": "cassandrastudio_bot",
            "token_values_exposed": False,
            "raw_chat_ids_exposed": False,
            "runtime_process_probe_required": True,
        },
        "services": {
            "watcher": build_watcher_status(generated_at=ts),
            "briefing_scheduler": build_briefing_scheduler_status(generated_at=ts),
        },
        "next_safe_move": "Cassandra send-capable dry-run receipt review",
    }


def render_operator_markdown(payload: dict[str, Any]) -> str:
    watcher = (payload.get("services") or {}).get("watcher") or {}
    followups = watcher.get("pending_followups") or {}
    future = watcher.get("future_actions") or {}
    scheduler = (payload.get("services") or {}).get("briefing_scheduler") or {}
    briefing = scheduler.get("briefing_schedule") or {}
    lines = [
        "# Cassandra Send-Capable Status Dry-Run",
        "",
        "This is a no-send status pass. Cassandra send-capable services can inspect their own posture, but outbound delivery remains blocked.",
        "",
        "## Current Proof",
        "- Runtime authority changed: no",
        "- Send authority added: no",
        "- Emergency guard removed: no",
        "- Telegram delivery triggered: no",
        "- Gmail/email delivery triggered: no",
        "- Briefing delivery triggered: no",
        "- Voice delivery triggered: no",
        "- Niles used for Cassandra path: no",
        "",
        "## Watcher",
        f"- Pending followups: {followups.get('pending_count', 0)} pending / {followups.get('total_count', 0)} total",
        f"- Future actions: {future.get('pending_count', 0)} pending, {future.get('due_count', 0)} due now",
        "- Email/Gmail polling: blocked in dry-run",
        "- Ambient Telegram/voice chirps: blocked in dry-run",
        "",
        "## Briefing Scheduler",
        f"- Due briefing slots: {', '.join(briefing.get('due_slots') or []) or 'none'}",
        f"- Pending briefings: {briefing.get('pending_count', 0)}",
        "- Telegram briefing delivery: blocked",
        "- Voice briefing delivery: blocked",
        "",
        "## Next Safe Move",
        payload.get("next_safe_move", "Review dry-run receipts before any send-capable resume."),
        "",
    ]
    return "\n".join(lines)


def export_read_models(format_name: str = "both") -> list[str]:
    payload = build_status_read_model()
    written: list[str] = []
    if format_name in {"json", "both"}:
        written.append(write_json(DEFAULT_EXPORT_ROOT / JSON_EXPORT_NAME, payload))
    if format_name in {"operator", "both"}:
        written.append(write_text(DEFAULT_EXPORT_ROOT / OPERATOR_EXPORT_NAME, render_operator_markdown(payload)))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Cassandra send-capable status dry-run read-model.")
    parser.add_argument("--format", choices=("json", "operator", "both"), default="both")
    args = parser.parse_args(argv)
    for path in export_read_models(args.format):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
