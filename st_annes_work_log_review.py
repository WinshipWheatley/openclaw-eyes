"""St. Anne's work-log operator review V0.

This module reviews staged St. Anne's work-log events. It can confirm, discard,
or apply a narrow safe edit to an event already captured by
``st_annes_work_log_intake``. It never touches Excel, creates invoices, exports
PDFs, sends email, mutates ledgers, marks paid, connects Telegram live, or
submits anything.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import st_annes_work_log_intake as intake


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_SQLITE_PATH = intake.DEFAULT_SQLITE_PATH

SCHEMA_VERSION = "st_annes_work_log_review_v0"
READ_MODEL_ID = "st_annes_work_log_review_surface"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "ST_ANNES_WORK_LOG_REVIEW_V0_READY"

CONFIRM_ACTION = "confirm_st_annes_work_log_event"
DISCARD_ACTION = "discard_st_annes_work_log_event"
EDIT_ACTION = "edit_st_annes_work_log_event"
EXPORT_ACTION = "export_surface"
REVIEW_ACTIONS = (CONFIRM_ACTION, DISCARD_ACTION, EDIT_ACTION)

CONFIRMED_STATUS = "OPERATOR_CONFIRMED"
DISCARDED_STATUS = "DISCARDED_BY_OPERATOR"
PENDING_STATUS = "OPERATOR_REVIEW_REQUIRED"
READY_FOR_ROLLUP = "READY_FOR_MONTHLY_ROLLUP"
DISCARDED_FROM_INVOICE = "DISCARDED_NOT_FOR_INVOICE"
NOT_INCLUDED_PENDING = "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED"

AUTHORITY_BOUNDARY = {
    **intake.AUTHORITY_BOUNDARY,
    "excel_mutation_allowed": False,
    "invoice_creation_allowed": False,
    "finance_invoice_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "telegram_live_connection_allowed": False,
    "telegram_send_allowed": False,
}

EDITABLE_FIELDS = ("service_date", "service_time", "service_label", "description")


@dataclass(frozen=True)
class ReviewResult:
    status: str
    action: str
    event_id: str
    event: dict[str, Any] | None
    blocked_reason: str
    receipt: dict[str, Any]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _short_hash(*parts: object) -> str:
    return intake._short_hash(*parts)


def review_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS st_annes_work_log_review_actions (
  review_ref TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  action TEXT NOT NULL,
  review_status TEXT NOT NULL,
  blocked_reason TEXT NOT NULL,
  changed_fields_json TEXT NOT NULL,
  previous_event_json TEXT NOT NULL,
  resulting_event_json TEXT NOT NULL,
  authority_boundary_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
""".strip() + "\n"


def init_sqlite(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> None:
    sqlite_path = _rooted(sqlite_path)
    intake.init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(review_schema_sql())
        conn.commit()
    finally:
        conn.close()


def _event_from_row(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    event = dict(row)
    event["operator_confirmed"] = bool(event["operator_confirmed"])
    boundary = event.pop("authority_boundary_json", None)
    if isinstance(boundary, str):
        event["authority_boundary"] = json.loads(boundary)
    else:
        event["authority_boundary"] = dict(intake.AUTHORITY_BOUNDARY)
    return event


def _read_event(conn: sqlite3.Connection, event_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM st_annes_work_log_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    return _event_from_row(row)


def _validate_edits(edits: Mapping[str, Any]) -> tuple[dict[str, str], tuple[str, ...]]:
    clean: dict[str, str] = {}
    blockers: list[str] = []
    for key, value in edits.items():
        if value in (None, ""):
            continue
        if key not in EDITABLE_FIELDS:
            blockers.append(f"unsupported_edit_field:{key}")
            continue
        text = str(value).strip()
        if key == "service_date" and not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
            blockers.append("invalid_service_date")
            continue
        if key == "service_time" and text and not re.fullmatch(r"\d{1,2}:\d{2}(?:\s?[APMapm]{2})?", text):
            blockers.append("invalid_service_time")
            continue
        clean[key] = text
    if not clean and not blockers:
        blockers.append("no_safe_edit_fields_provided")
    return clean, tuple(dict.fromkeys(blockers))


def _write_review_receipt(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    action: str,
    review_status: str,
    blocked_reason: str,
    changed_fields: Mapping[str, Any],
    previous_event: Mapping[str, Any] | None,
    resulting_event: Mapping[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "ST_ANNES_WORK_LOG_REVIEW_ACTION_RECEIPT",
        "review_ref": "st_annes_work_log_review:" + _short_hash(event_id, action, created_at, blocked_reason),
        "event_id": event_id,
        "action": action,
        "review_status": review_status,
        "blocked_reason": blocked_reason,
        "changed_fields": dict(changed_fields),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": created_at,
        "machine_proof": {
            "excel_mutation_performed": False,
            "workbook_mutation_performed": False,
            "invoice_created": False,
            "pdf_export_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "telegram_live_connected": False,
            "telegram_message_sent": False,
            "original_evidence_deleted": False,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO st_annes_work_log_review_actions (
          review_ref, event_id, action, review_status, blocked_reason, changed_fields_json,
          previous_event_json, resulting_event_json, authority_boundary_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt["review_ref"],
            event_id,
            action,
            review_status,
            blocked_reason,
            stable_json(dict(changed_fields)),
            stable_json(dict(previous_event or {})),
            stable_json(dict(resulting_event or {})),
            stable_json(AUTHORITY_BOUNDARY),
            created_at,
        ),
    )
    return receipt


def review_event(
    event_id: str,
    action: str,
    *,
    edits: Mapping[str, Any] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> ReviewResult:
    generated_at = generated_at or utc_now()
    sqlite_path = _rooted(sqlite_path)
    init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        previous = _read_event(conn, event_id)
        if previous is None:
            receipt = _write_review_receipt(
                conn,
                event_id=event_id,
                action=action,
                review_status="BLOCKED",
                blocked_reason="unknown_event",
                changed_fields={},
                previous_event=None,
                resulting_event=None,
                created_at=generated_at,
            )
            conn.commit()
            return ReviewResult("BLOCKED", action, event_id, None, "unknown_event", receipt)

        if action not in REVIEW_ACTIONS:
            receipt = _write_review_receipt(
                conn,
                event_id=event_id,
                action=action,
                review_status="BLOCKED",
                blocked_reason="unsupported_review_action",
                changed_fields={},
                previous_event=previous,
                resulting_event=previous,
                created_at=generated_at,
            )
            conn.commit()
            return ReviewResult("BLOCKED", action, event_id, previous, "unsupported_review_action", receipt)

        changed: dict[str, Any]
        if action == CONFIRM_ACTION:
            changed = {
                "operator_confirmed": True,
                "staging_status": CONFIRMED_STATUS,
                "invoice_inclusion_status": READY_FOR_ROLLUP,
            }
            conn.execute(
                """
                UPDATE st_annes_work_log_events
                SET operator_confirmed = 1,
                    staging_status = ?,
                    invoice_inclusion_status = ?,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (CONFIRMED_STATUS, READY_FOR_ROLLUP, generated_at, event_id),
            )
        elif action == DISCARD_ACTION:
            changed = {
                "operator_confirmed": False,
                "staging_status": DISCARDED_STATUS,
                "invoice_inclusion_status": DISCARDED_FROM_INVOICE,
            }
            conn.execute(
                """
                UPDATE st_annes_work_log_events
                SET operator_confirmed = 0,
                    staging_status = ?,
                    invoice_inclusion_status = ?,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (DISCARDED_STATUS, DISCARDED_FROM_INVOICE, generated_at, event_id),
            )
        else:
            clean_edits, blockers = _validate_edits(edits or {})
            if blockers:
                receipt = _write_review_receipt(
                    conn,
                    event_id=event_id,
                    action=action,
                    review_status="BLOCKED",
                    blocked_reason=";".join(blockers),
                    changed_fields={},
                    previous_event=previous,
                    resulting_event=previous,
                    created_at=generated_at,
                )
                conn.commit()
                return ReviewResult("BLOCKED", action, event_id, previous, ";".join(blockers), receipt)
            changed = dict(clean_edits)
            changed.update(
                {
                    "operator_confirmed": False,
                    "staging_status": PENDING_STATUS,
                    "invoice_inclusion_status": NOT_INCLUDED_PENDING,
                }
            )
            assignments = []
            params: list[Any] = []
            for field, value in clean_edits.items():
                assignments.append(f"{field} = ?")
                params.append(value)
            if "service_date" in clean_edits:
                assignments.append("included_in_invoice_period = ?")
                params.append(str(clean_edits["service_date"])[:7])
            assignments.extend(
                [
                    "operator_confirmed = 0",
                    "staging_status = ?",
                    "invoice_inclusion_status = ?",
                    "updated_at = ?",
                ]
            )
            params.extend([PENDING_STATUS, NOT_INCLUDED_PENDING, generated_at, event_id])
            conn.execute(
                f"UPDATE st_annes_work_log_events SET {', '.join(assignments)} WHERE event_id = ?",
                tuple(params),
            )

        resulting = _read_event(conn, event_id)
        receipt = _write_review_receipt(
            conn,
            event_id=event_id,
            action=action,
            review_status="RECORDED",
            blocked_reason="",
            changed_fields=changed,
            previous_event=previous,
            resulting_event=resulting,
            created_at=generated_at,
        )
        conn.commit()
        return ReviewResult("RECORDED", action, event_id, resulting, "", receipt)
    finally:
        conn.close()


def _review_actions_for_event(event: Mapping[str, Any]) -> tuple[str, ...]:
    if event.get("staging_status") == DISCARDED_STATUS:
        return ()
    return REVIEW_ACTIONS


def build_review_surface(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    events = intake.read_staged_events(sqlite_path)
    pending = [event for event in events if event.get("invoice_inclusion_status") == NOT_INCLUDED_PENDING]
    ready = [event for event in events if event.get("invoice_inclusion_status") == READY_FOR_ROLLUP]
    discarded = [event for event in events if event.get("staging_status") == DISCARDED_STATUS]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": READY_STATUS,
        "client_ref": intake.CLIENT_REF,
        "workflow_ref": intake.WORKFLOW_REF,
        "sqlite_path": str(sqlite_path),
        "review_actions": list(REVIEW_ACTIONS),
        "event_counts": {
            "total": len(events),
            "pending_operator_review": len(pending),
            "ready_for_monthly_rollup": len(ready),
            "discarded_by_operator": len(discarded),
        },
        "events": [
            {
                "event_id": event["event_id"],
                "service_date": event["service_date"],
                "service_label": event["service_label"],
                "description": event["description"],
                "amount": event["amount"],
                "operator_confirmed": event["operator_confirmed"],
                "staging_status": event["staging_status"],
                "invoice_inclusion_status": event["invoice_inclusion_status"],
                "allowed_review_actions": list(_review_actions_for_event(event)),
                "invoice_ref": event["invoice_ref"],
            }
            for event in events
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": {
            "confirm_sets_operator_confirmed": True,
            "confirm_sets_invoice_inclusion_status": READY_FOR_ROLLUP,
            "discard_preserves_original_evidence": True,
            "edit_resets_confirmation": True,
            "excel_mutation_allowed": False,
            "invoice_creation_allowed": False,
            "pdf_export_allowed": False,
            "email_send_allowed": False,
            "ledger_mutation_allowed": False,
            "paid_marking_allowed": False,
        },
        "machine_proof": {
            "review_surface_ready": True,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
            "excel_mutation_performed": False,
            "workbook_mutation_performed": False,
            "invoice_created": False,
            "pdf_export_performed": False,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "telegram_live_connected": False,
        },
    }


def publish_read_models(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    events_path = intake.export_read_model(sqlite_path=sqlite_path, export_root=export_root, generated_at=generated_at)
    review_path = export_root / JSON_EXPORT_NAME
    review_path.write_text(stable_json(build_review_surface(sqlite_path=sqlite_path, generated_at=generated_at)), encoding="utf-8")
    bridge_events_path = ""
    bridge_review_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_events = bridge_export_root / intake.JSON_EXPORT_NAME
        bridge_review = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(events_path, bridge_events)
        shutil.copy2(review_path, bridge_review)
        bridge_events_path = bridge_events.as_posix()
        bridge_review_path = bridge_review.as_posix()
    return {
        "events_read_model_path": events_path.as_posix(),
        "review_surface_path": review_path.as_posix(),
        "bridge_events_read_model_path": bridge_events_path,
        "bridge_review_surface_path": bridge_review_path,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review staged St. Anne's work-log events.")
    parser.add_argument("action", choices=(EXPORT_ACTION, *REVIEW_ACTIONS))
    parser.add_argument("--event-id", default="")
    parser.add_argument("--service-date")
    parser.add_argument("--service-time")
    parser.add_argument("--service-label")
    parser.add_argument("--description")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    sqlite_path = Path(args.sqlite_path)
    result_payload: dict[str, Any] = {}
    if args.action != EXPORT_ACTION:
        if not args.event_id:
            raise SystemExit("--event-id is required for review actions")
        result = review_event(
            args.event_id,
            args.action,
            edits={
                "service_date": args.service_date,
                "service_time": args.service_time,
                "service_label": args.service_label,
                "description": args.description,
            },
            sqlite_path=sqlite_path,
            generated_at=args.generated_at,
        )
        result_payload = {
            "review_status": result.status,
            "action": result.action,
            "event_id": result.event_id,
            "blocked_reason": result.blocked_reason,
            "receipt": result.receipt,
        }
    paths = publish_read_models(
        sqlite_path=sqlite_path,
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    payload = {
        "status": READY_STATUS,
        "action": args.action,
        **result_payload,
        **paths,
    }
    print(stable_json(payload if args.format == "json" else payload), end="")
    return 0 if result_payload.get("review_status", "RECORDED") != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
