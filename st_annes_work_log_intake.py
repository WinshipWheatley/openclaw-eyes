"""St. Anne's work-log intake V0.

This module records non-live work-log intake into staging only. It uses the
workflow package queue for package metadata, and it never touches Excel, exports
PDFs, sends email, mutates ledgers, marks paid, or connects Telegram live.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import workflow_package_queue


ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT_PATH = Path("generated/read_models/st_annes_monthly_work_log_contract.json")
DEFAULT_PACKAGE_QUEUE_CONTRACT_PATH = Path("generated/read_models/workflow_package_queue_contract.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/st_annes_monthly_work_log.sqlite")

SCHEMA_VERSION = "st_annes_work_log_events_v0"
READ_MODEL_ID = "st_annes_work_log_events"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "ST_ANNES_WORK_LOG_INTAKE_V0_READY"

CLIENT_REF = "st_annes"
WORKFLOW_REF = "st_annes_work_log_event"
DEFAULT_RATE = 125

AUTHORITY_BOUNDARY = {
    "telegram_live_connection_allowed": False,
    "telegram_send_allowed": False,
    "workbook_write_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "paid": False,
    "sent": False,
}

MONTH_LOOKUP = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
MONTH_LOOKUP.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})


@dataclass(frozen=True)
class IntakeResult:
    status: str
    event: dict[str, Any] | None
    package: dict[str, Any]
    blocked_reason: str


@dataclass(frozen=True)
class ExportResult:
    read_model_path: str
    sqlite_path: str
    event_count: int
    blocked_count: int
    status: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_rooted(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_hash(*parts: object) -> str:
    return _sha256_text("\u241f".join(str(part) for part in parts))[:16]


def _date_from_iso(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _current_date(current_date: str | None = None, generated_at: str | None = None) -> date:
    if current_date:
        return date.fromisoformat(current_date)
    if generated_at:
        return _date_from_iso(generated_at)
    return datetime.now(timezone.utc).date()


def validate_preconditions(
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    package_queue_contract_path: Path = DEFAULT_PACKAGE_QUEUE_CONTRACT_PATH,
) -> None:
    contract = _read_json(contract_path)
    package_queue = _read_json(package_queue_contract_path)
    if contract.get("status") != "ST_ANNES_MONTHLY_WORK_LOG_CONTRACT_READY":
        raise ValueError("ST_ANNES_MONTHLY_WORK_LOG_CONTRACT_READY precondition not met")
    if package_queue.get("status") != "WORKFLOW_PACKAGE_QUEUE_V0_READY":
        raise ValueError("WORKFLOW_PACKAGE_QUEUE_V0_READY precondition not met")


def _explicit_other_client(text: str) -> str | None:
    lower = text.lower()
    if "capital hilton" in lower:
        return "capital_hilton"
    if "live arts" in lower:
        return "live_arts_md"
    return None


def _mentions_st_annes(text: str) -> bool:
    lower = text.lower()
    return "st. anne" in lower or "st anne" in lower or "anne's" in lower or "annes" in lower


def _implies_today(text: str) -> bool:
    lower = text.lower()
    return "today" in lower or "i'm at" in lower or "i am at" in lower or "mark that i'm" in lower


def infer_service_date(text: str, *, current: date) -> tuple[str | None, str | None]:
    lower = text.lower()
    for month_name, month_number in MONTH_LOOKUP.items():
        match = re.search(rf"\b{re.escape(month_name)}\s+(\d{{1,2}})(?:,\s*(\d{{4}}))?\b", lower)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else current.year
            return date(year, month_number, day).isoformat(), "explicit_month_day"
    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lower)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))).isoformat(), "explicit_iso_date"
    if _implies_today(text):
        return current.isoformat(), "implied_today"
    return None, "date_required"


def infer_service_label(text: str) -> str:
    lower = text.lower()
    if "adult forum" in lower:
        return "Adult Forum"
    if "funeral" in lower:
        return "Funeral"
    if "wedding" in lower:
        return "Wedding"
    if "church service" in lower:
        return "Church Service"
    if "church" in lower or "running sound" in lower or "sound" in lower:
        return "Church sound"
    return "Church sound"


def _description_for_label(label: str, text: str) -> str:
    lower = text.lower()
    if label == "Funeral" and "av tech" in lower:
        return "Funeral AV tech event"
    if label == "Adult Forum":
        return "Adult Forum sound support"
    if label == "Wedding":
        return "Wedding sound support"
    if label == "Church Service":
        return "Church Service sound support"
    return "Church sound support"


def _invoice_period(service_date: str) -> str:
    return service_date[:7]


def _event_id(*, service_date: str, service_label: str, protected_text_hash: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", service_label.lower()).strip("_")
    return f"st_annes_work_log:{service_date}:{slug}:{_short_hash(protected_text_hash)}"


def _blocked_result(
    *,
    source_text: str,
    source_surface: str,
    generated_at: str,
    reason: str,
    package: dict[str, Any] | None = None,
) -> IntakeResult:
    package = package or workflow_package_queue.create_package(
        source_text,
        source_surface=source_surface,
        created_at=generated_at,
    )
    return IntakeResult(status="BLOCKED", event=None, package=package, blocked_reason=reason)


def intake_work_log_event(
    source_text: str,
    *,
    source_surface: str = "mission_control",
    current_date: str | None = None,
    generated_at: str | None = None,
    operator_confirmed: bool = False,
) -> IntakeResult:
    generated_at = generated_at or utc_now()
    package = workflow_package_queue.create_package(
        source_text,
        source_surface=source_surface,
        created_at=generated_at,
    )
    if package["workflow_ref"] != WORKFLOW_REF:
        return _blocked_result(
            source_text=source_text,
            source_surface=source_surface,
            generated_at=generated_at,
            reason=f"workflow_ref_not_work_log_event:{package['workflow_ref']}",
            package=package,
        )
    other_client = _explicit_other_client(source_text)
    if other_client is not None:
        return _blocked_result(
            source_text=source_text,
            source_surface=source_surface,
            generated_at=generated_at,
            reason=f"unsupported_client:{other_client}",
            package=package,
        )
    if not (_mentions_st_annes(source_text) or "church" in source_text.lower() or "running sound" in source_text.lower()):
        return _blocked_result(
            source_text=source_text,
            source_surface=source_surface,
            generated_at=generated_at,
            reason="client_ref_required",
            package=package,
        )

    service_date, date_basis = infer_service_date(source_text, current=_current_date(current_date, generated_at))
    if service_date is None:
        return _blocked_result(
            source_text=source_text,
            source_surface=source_surface,
            generated_at=generated_at,
            reason="service_date_required",
            package=package,
        )
    service_label = infer_service_label(source_text)
    protected_hash = package["protected_text_hash"]
    event = {
        "event_id": _event_id(service_date=service_date, service_label=service_label, protected_text_hash=protected_hash),
        "package_id": package["package_id"],
        "workflow_ref": WORKFLOW_REF,
        "client_ref": CLIENT_REF,
        "service_date": service_date,
        "service_time": "",
        "service_label": service_label,
        "description": _description_for_label(service_label, source_text),
        "default_rate": DEFAULT_RATE,
        "amount": DEFAULT_RATE,
        "source": source_surface,
        "operator_confirmed": operator_confirmed,
        "pii_privacy_status": package["pii_status"],
        "included_in_invoice_period": _invoice_period(service_date),
        "invoice_ref": "",
        "date_inference_basis": date_basis,
        "staging_status": "OPERATOR_REVIEW_REQUIRED",
        "invoice_inclusion_status": "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": generated_at,
        "updated_at": generated_at,
    }
    return IntakeResult(status="STAGED", event=event, package=package, blocked_reason="")


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS st_annes_work_log_events (
  event_id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  client_ref TEXT NOT NULL,
  service_date TEXT NOT NULL,
  service_time TEXT NOT NULL,
  service_label TEXT NOT NULL,
  description TEXT NOT NULL,
  default_rate INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  source TEXT NOT NULL,
  operator_confirmed INTEGER NOT NULL CHECK(operator_confirmed IN (0, 1)),
  pii_privacy_status TEXT NOT NULL,
  included_in_invoice_period TEXT NOT NULL,
  invoice_ref TEXT NOT NULL,
  date_inference_basis TEXT NOT NULL,
  staging_status TEXT NOT NULL,
  invoice_inclusion_status TEXT NOT NULL,
  authority_boundary_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS st_annes_work_log_intake_results (
  intake_ref TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  blocked_reason TEXT NOT NULL,
  protected_text_hash TEXT NOT NULL,
  source_surface TEXT NOT NULL,
  created_at TEXT NOT NULL,
  event_id TEXT NOT NULL
);
""".strip() + "\n"


def init_sqlite(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(sqlite_schema_sql())
        conn.commit()
    finally:
        conn.close()


def record_intake_result(result: IntakeResult, sqlite_path: Path = DEFAULT_SQLITE_PATH) -> None:
    sqlite_path = _rooted(sqlite_path)
    init_sqlite(sqlite_path)
    package = result.package
    event = result.event
    conn = sqlite3.connect(sqlite_path)
    try:
        if event is not None:
            conn.execute(
                """
                INSERT OR REPLACE INTO st_annes_work_log_events (
                  event_id, package_id, workflow_ref, client_ref, service_date, service_time,
                  service_label, description, default_rate, amount, source, operator_confirmed,
                  pii_privacy_status, included_in_invoice_period, invoice_ref, date_inference_basis,
                  staging_status, invoice_inclusion_status, authority_boundary_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["package_id"],
                    event["workflow_ref"],
                    event["client_ref"],
                    event["service_date"],
                    event["service_time"],
                    event["service_label"],
                    event["description"],
                    event["default_rate"],
                    event["amount"],
                    event["source"],
                    int(bool(event["operator_confirmed"])),
                    event["pii_privacy_status"],
                    event["included_in_invoice_period"],
                    event["invoice_ref"],
                    event["date_inference_basis"],
                    event["staging_status"],
                    event["invoice_inclusion_status"],
                    stable_json(event["authority_boundary"]),
                    event["created_at"],
                    event["updated_at"],
                ),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO st_annes_work_log_intake_results (
              intake_ref, package_id, workflow_ref, status, blocked_reason, protected_text_hash,
              source_surface, created_at, event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "st_annes_work_log_intake:" + _short_hash(package["package_id"], result.status, result.blocked_reason),
                package["package_id"],
                package["workflow_ref"],
                result.status,
                result.blocked_reason,
                package["protected_text_hash"],
                package["source_surface"],
                package["created_at"],
                event["event_id"] if event is not None else "",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def read_staged_events(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> list[dict[str, Any]]:
    sqlite_path = _rooted(sqlite_path)
    if not sqlite_path.exists():
        return []
    init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT * FROM st_annes_work_log_events
            ORDER BY service_date, event_id
            """
        ).fetchall()
    finally:
        conn.close()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        event["operator_confirmed"] = bool(event["operator_confirmed"])
        event["authority_boundary"] = json.loads(event.pop("authority_boundary_json"))
        events.append(event)
    return events


def build_read_model(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    events = read_staged_events(sqlite_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": READY_STATUS,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "event_count": len(events),
        "staged_events": events,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_contract": str(DEFAULT_CONTRACT_PATH),
        "source_package_queue_contract": str(DEFAULT_PACKAGE_QUEUE_CONTRACT_PATH),
        "sqlite_path": str(sqlite_path),
        "rules": {
            "telegram_live_connected": False,
            "excel_mutation_allowed": False,
            "pdf_export_allowed": False,
            "email_send_allowed": False,
            "ledger_mutation_allowed": False,
            "paid_marking_allowed": False,
            "operator_confirmation_required_before_invoice_inclusion": True,
        },
        "machine_proof": {
            "package_backed": True,
            "events_are_staging_only": True,
            "operator_confirmed_defaults_false": all(event["operator_confirmed"] is False for event in events),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }


def export_read_model(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> Path:
    read_model = build_read_model(sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    output_path = export_root / JSON_EXPORT_NAME
    output_path.write_text(stable_json(read_model), encoding="utf-8")
    return output_path


def intake_and_record(
    source_text: str,
    *,
    source_surface: str = "mission_control",
    current_date: str | None = None,
    generated_at: str | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    operator_confirmed: bool = False,
) -> IntakeResult:
    validate_preconditions()
    result = intake_work_log_event(
        source_text,
        source_surface=source_surface,
        current_date=current_date,
        generated_at=generated_at,
        operator_confirmed=operator_confirmed,
    )
    record_intake_result(result, sqlite_path=sqlite_path)
    export_read_model(sqlite_path=sqlite_path, export_root=export_root, generated_at=generated_at)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage a non-live St. Anne's work-log event.")
    parser.add_argument("source_text", nargs="?", default="Mark that I'm at church running sound.")
    parser.add_argument("--source-surface", default="mission_control")
    parser.add_argument("--current-date")
    parser.add_argument("--generated-at")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = intake_and_record(
        args.source_text,
        source_surface=args.source_surface,
        current_date=args.current_date,
        generated_at=args.generated_at,
        sqlite_path=Path(args.sqlite_path),
        export_root=Path(args.export_root),
    )
    payload = {
        "status": result.status,
        "event_id": result.event["event_id"] if result.event else "",
        "blocked_reason": result.blocked_reason,
        "workflow_ref": result.package["workflow_ref"],
        "package_id": result.package["package_id"],
        "read_model_path": str(_rooted(Path(args.export_root)) / JSON_EXPORT_NAME),
        "sqlite_path": str(_rooted(Path(args.sqlite_path))),
    }
    print(stable_json(result.event if args.format == "json" and result.event else payload), end="")
    return 0 if result.event is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
