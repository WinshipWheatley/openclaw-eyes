"""St. Anne's work-log smoke/test hygiene.

This module keeps Mission Control smoke events from becoming billable invoice
truth. It preserves the original intake/review evidence, updates only local
SQLite/read-model state, and never touches Excel, PDFs, email, ledgers, or live
providers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import st_annes_work_log_intake as intake
import st_annes_work_log_review as review


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = intake.DEFAULT_SQLITE_PATH
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_REQUEST_DIR = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")

SCHEMA_VERSION = "st_annes_work_log_hygiene_v0"
READ_MODEL_ID = "st_annes_work_log_hygiene"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "ST_ANNES_WORK_LOG_SMOKE_HYGIENE_READY"

SMOKE_OR_TEST_STATUS = review.SMOKE_OR_TEST_STATUS
NOT_INCLUDED_SMOKE = review.NOT_INCLUDED_SMOKE
BUSINESS_CONFIRMED_STATUS = "BUSINESS_CONFIRMED_READY_FOR_ROLLUP"
PENDING_STATUS = intake.PENDING_BILLING_TRUTH_STATUS

KNOWN_SMOKE_SOURCE_TEXTS = (
    "Mark that I'm at church running sound.",
    "Mark that I’m at church running sound.",
)
KNOWN_GENERATED_TEST_TIMESTAMPS = {
    "2026-06-01T23:30:00+00:00",
}

AUTHORITY_BOUNDARY = {
    "telegram_live_connection_allowed": False,
    "telegram_send_allowed": False,
    "workbook_write_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "excel_mutation_allowed": False,
    "pdf_export_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "sent": False,
    "paid": False,
}


@dataclass(frozen=True)
class HygieneResult:
    status: str
    smoke_event_ids: tuple[str, ...]
    excluded_event_ids: tuple[str, ...]
    preserved_event_ids: tuple[str, ...]
    read_model_path: str
    bridge_path: str
    sqlite_path: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _short_hash(*parts: object) -> str:
    joined = "\u241f".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


KNOWN_SMOKE_PROTECTED_HASHES = {_source_hash(text) for text in KNOWN_SMOKE_SOURCE_TEXTS}


def _load_json_text(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _rows_by_event(conn: sqlite3.Connection, table: str) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone() is None:
        return rows
    for row in conn.execute(f"SELECT * FROM {table}"):
        item = dict(row)
        event_id = str(item.get("event_id") or "")
        if event_id:
            rows.setdefault(event_id, []).append(item)
    return rows


def hygiene_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS st_annes_work_log_hygiene_actions (
  hygiene_ref TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  hygiene_status TEXT NOT NULL,
  detected_reason TEXT NOT NULL,
  previous_event_json TEXT NOT NULL,
  resulting_event_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  authority_boundary_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
""".strip() + "\n"


def init_sqlite(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> None:
    sqlite_path = _rooted(sqlite_path)
    intake.init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(hygiene_schema_sql())
        conn.commit()
    finally:
        conn.close()


def _evidence_file_ref(path: Path, data: Mapping[str, Any], reason: str) -> dict[str, str]:
    return {
        "evidence_type": "mission_control_json",
        "path": path.as_posix(),
        "request_id": str(data.get("request_id") or data.get("source_request_id") or ""),
        "response_kind": str(data.get("response_kind") or data.get("receipt_type") or ""),
        "reason": reason,
    }


def _scan_json_evidence_files(
    *,
    event: Mapping[str, Any],
    intake_rows: Iterable[Mapping[str, Any]],
    request_dir: Path,
    response_dir: Path,
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    event_id = str(event.get("event_id") or "")
    package_id = str(event.get("package_id") or "")

    for directory in (request_dir, response_dir):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            matched_event_id = bool(event_id and event_id in text)
            matched_package_id = bool(package_id and package_id in text)
            if not (matched_event_id or matched_package_id):
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            lower_name = path.name.lower()
            reason = "matched_event_or_package_evidence"
            if "smoke" in lower_name or "test" in lower_name:
                reason = "matched_smoke_or_test_filename"
            refs.append(_evidence_file_ref(path, data if isinstance(data, Mapping) else {}, reason))
    return refs


def _business_confirmation_found(
    *,
    event: Mapping[str, Any],
    evidence_refs: Iterable[Mapping[str, Any]],
) -> bool:
    if event.get("operator_business_confirmed") is True:
        return True
    for ref in evidence_refs:
        if ref.get("operator_business_confirmed") is True:
            return True
    return False


def _classify_event(
    *,
    event: Mapping[str, Any],
    intake_rows: Iterable[Mapping[str, Any]],
    review_rows: Iterable[Mapping[str, Any]],
    evidence_refs: Iterable[Mapping[str, Any]],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    protected_hashes = {str(row.get("protected_text_hash") or "") for row in intake_rows}
    if protected_hashes & KNOWN_SMOKE_PROTECTED_HASHES:
        reasons.append("protected_text_hash_matches_known_smoke_instruction")
    if str(event.get("created_at") or "") in KNOWN_GENERATED_TEST_TIMESTAMPS:
        reasons.append("created_at_matches_validation_fixture_timestamp")
    for ref in evidence_refs:
        path = str(ref.get("path") or "").lower()
        request_id = str(ref.get("request_id") or "").lower()
        if "smoke" in path or "smoke" in request_id or "test" in path or "test" in request_id:
            reasons.append("mission_control_evidence_contains_smoke_or_test")
            break
    for row in review_rows:
        review_ref = str(row.get("review_ref") or "").lower()
        if "smoke" in review_ref or "test" in review_ref:
            reasons.append("review_receipt_contains_smoke_or_test")
            break
    return bool(reasons), sorted(set(reasons))


def _event_from_row(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    event = dict(row)
    event["operator_confirmed"] = bool(event.get("operator_confirmed", 0))
    event["operator_business_confirmed"] = bool(event.get("operator_business_confirmed", 0))
    event["hygiene_notes"] = _load_json_text(event.pop("hygiene_notes_json", "[]"), [])
    event["hygiene_evidence_refs"] = _load_json_text(event.pop("hygiene_evidence_refs_json", "[]"), [])
    event["authority_boundary"] = _load_json_text(event.pop("authority_boundary_json", "{}"), dict(intake.AUTHORITY_BOUNDARY))
    return event


def apply_smoke_hygiene(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    request_dir: Path = DEFAULT_REQUEST_DIR,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    generated_at: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    generated_at = generated_at or utc_now()
    sqlite_path = _rooted(sqlite_path)
    init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    smoke_event_ids: list[str] = []
    excluded_event_ids: list[str] = []
    preserved_event_ids: list[str] = []
    try:
        intake_rows_by_event = _rows_by_event(conn, "st_annes_work_log_intake_results")
        review_rows_by_event = _rows_by_event(conn, "st_annes_work_log_review_actions")
        event_rows = conn.execute("SELECT * FROM st_annes_work_log_events ORDER BY service_date, event_id").fetchall()
        for row in event_rows:
            event = _event_from_row(row)
            event_id = str(event["event_id"])
            intake_rows = intake_rows_by_event.get(event_id, [])
            review_rows = review_rows_by_event.get(event_id, [])
            evidence_refs = _scan_json_evidence_files(
                event=event,
                intake_rows=intake_rows,
                request_dir=request_dir,
                response_dir=response_dir,
            )
            evidence_refs.extend(
                {
                    "evidence_type": "sqlite_intake_result",
                    "path": str(sqlite_path),
                    "intake_ref": str(item.get("intake_ref") or ""),
                    "protected_text_hash": str(item.get("protected_text_hash") or ""),
                    "reason": "intake_result_preserved",
                }
                for item in intake_rows
            )
            evidence_refs.extend(
                {
                    "evidence_type": "sqlite_review_action",
                    "path": str(sqlite_path),
                    "review_ref": str(item.get("review_ref") or ""),
                    "review_status": str(item.get("review_status") or ""),
                    "action": str(item.get("action") or ""),
                    "reason": "review_action_preserved",
                }
                for item in review_rows
            )
            is_smoke, reasons = _classify_event(
                event=event,
                intake_rows=intake_rows,
                review_rows=review_rows,
                evidence_refs=evidence_refs,
            )
            has_business_confirmation = _business_confirmation_found(event=event, evidence_refs=evidence_refs)
            previous_event = dict(event)

            if is_smoke and not has_business_confirmation:
                smoke_event_ids.append(event_id)
                notes = list(event.get("hygiene_notes") or [])
                notes.extend(reason for reason in reasons if reason not in notes)
                if "separate_operator_business_confirmed_receipt_missing" not in notes:
                    notes.append("separate_operator_business_confirmed_receipt_missing")
                conn.execute(
                    """
                    UPDATE st_annes_work_log_events
                    SET operator_confirmed = 0,
                        operator_business_confirmed = 0,
                        staging_status = ?,
                        invoice_inclusion_status = ?,
                        billing_truth_status = ?,
                        hygiene_notes_json = ?,
                        hygiene_evidence_refs_json = ?,
                        updated_at = ?
                    WHERE event_id = ?
                    """,
                    (
                        SMOKE_OR_TEST_STATUS,
                        NOT_INCLUDED_SMOKE,
                        SMOKE_OR_TEST_STATUS,
                        stable_json(notes),
                        stable_json(evidence_refs),
                        generated_at,
                        event_id,
                    ),
                )
                resulting = _event_from_row(
                    conn.execute("SELECT * FROM st_annes_work_log_events WHERE event_id = ?", (event_id,)).fetchone()
                )
                excluded_event_ids.append(event_id)
                hygiene_status = "SMOKE_OR_TEST_EVENT_EXCLUDED"
            else:
                if event.get("invoice_inclusion_status") == review.READY_FOR_ROLLUP and has_business_confirmation:
                    conn.execute(
                        """
                        UPDATE st_annes_work_log_events
                        SET billing_truth_status = ?,
                            operator_business_confirmed = 1,
                            updated_at = ?
                        WHERE event_id = ?
                        """,
                        (BUSINESS_CONFIRMED_STATUS, generated_at, event_id),
                    )
                    resulting = _event_from_row(
                        conn.execute("SELECT * FROM st_annes_work_log_events WHERE event_id = ?", (event_id,)).fetchone()
                    )
                    hygiene_status = "BUSINESS_CONFIRMED_EVENT_PRESERVED"
                else:
                    resulting = previous_event
                    hygiene_status = "EVENT_PRESERVED"
                preserved_event_ids.append(event_id)

            conn.execute(
                """
                INSERT OR REPLACE INTO st_annes_work_log_hygiene_actions (
                  hygiene_ref, event_id, hygiene_status, detected_reason, previous_event_json,
                  resulting_event_json, evidence_refs_json, authority_boundary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "st_annes_work_log_hygiene:" + _short_hash(event_id, hygiene_status, generated_at),
                    event_id,
                    hygiene_status,
                    ";".join(reasons),
                    stable_json(previous_event),
                    stable_json(resulting),
                    stable_json(evidence_refs),
                    stable_json(AUTHORITY_BOUNDARY),
                    generated_at,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return smoke_event_ids, excluded_event_ids, preserved_event_ids


def _read_hygiene_actions(sqlite_path: Path) -> list[dict[str, Any]]:
    sqlite_path = _rooted(sqlite_path)
    init_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM st_annes_work_log_hygiene_actions ORDER BY created_at, event_id").fetchall()
    finally:
        conn.close()
    actions: list[dict[str, Any]] = []
    for row in rows:
        action = dict(row)
        action["previous_event"] = _load_json_text(action.pop("previous_event_json", "{}"), {})
        action["resulting_event"] = _load_json_text(action.pop("resulting_event_json", "{}"), {})
        action["evidence_refs"] = _load_json_text(action.pop("evidence_refs_json", "[]"), [])
        action["authority_boundary"] = _load_json_text(action.pop("authority_boundary_json", "{}"), dict(AUTHORITY_BOUNDARY))
        actions.append(action)
    return actions


def build_read_model(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    events = intake.read_staged_events(sqlite_path)
    actions = _read_hygiene_actions(sqlite_path)
    smoke_events = [event for event in events if event.get("billing_truth_status") == SMOKE_OR_TEST_STATUS]
    ready_events = [event for event in events if event.get("invoice_inclusion_status") == review.READY_FOR_ROLLUP]
    business_confirmed_ready = [
        event
        for event in ready_events
        if event.get("operator_business_confirmed") is True
        or event.get("billing_truth_status") in {BUSINESS_CONFIRMED_STATUS, review.CONFIRMED_BILLING_TRUTH_STATUS}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": READY_STATUS,
        "client_ref": intake.CLIENT_REF,
        "workflow_ref": intake.WORKFLOW_REF,
        "sqlite_path": str(sqlite_path),
        "smoke_test_events_found": len(smoke_events),
        "events_excluded_from_invoice_rollup": [event["event_id"] for event in smoke_events],
        "business_confirmed_ready_event_ids": [event["event_id"] for event in business_confirmed_ready],
        "events": [
            {
                "event_id": event["event_id"],
                "service_date": event["service_date"],
                "service_label": event["service_label"],
                "source": event["source"],
                "operator_confirmed": event["operator_confirmed"],
                "operator_business_confirmed": event.get("operator_business_confirmed", False),
                "billing_truth_status": event.get("billing_truth_status", PENDING_STATUS),
                "invoice_inclusion_status": event["invoice_inclusion_status"],
                "staging_status": event["staging_status"],
                "evidence_preserved": bool(event.get("hygiene_evidence_refs")),
                "hygiene_notes": event.get("hygiene_notes", []),
            }
            for event in events
        ],
        "hygiene_actions": [
            {
                "hygiene_ref": action["hygiene_ref"],
                "event_id": action["event_id"],
                "hygiene_status": action["hygiene_status"],
                "detected_reason": action["detected_reason"],
                "evidence_ref_count": len(action["evidence_refs"]),
                "created_at": action["created_at"],
            }
            for action in actions
        ],
        "rules": {
            "smoke_or_test_events_preserve_evidence": True,
            "smoke_or_test_events_operator_confirmed_false": True,
            "smoke_or_test_events_invoice_inclusion_status": NOT_INCLUDED_SMOKE,
            "separate_business_confirmation_required_for_billable_truth": True,
            "real_events_preserved_without_smoke_evidence": True,
            "excel_mutation_allowed": False,
            "pdf_export_allowed": False,
            "email_send_allowed": False,
            "ledger_mutation_allowed": False,
            "paid_marking_allowed": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "evidence_preserved": all(bool(event.get("hygiene_evidence_refs")) for event in smoke_events),
            "smoke_events_operator_confirmed_false": all(event["operator_confirmed"] is False for event in smoke_events),
            "smoke_events_excluded_from_rollup": all(
                event["invoice_inclusion_status"] == NOT_INCLUDED_SMOKE for event in smoke_events
            ),
            "ready_for_rollup_not_smoke": all(
                event.get("billing_truth_status") != SMOKE_OR_TEST_STATUS for event in ready_events
            ),
            "excel_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "email_send_performed": False,
            "telegram_live_connected": False,
            "telegram_message_sent": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
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
    hygiene_path = export_root / JSON_EXPORT_NAME
    hygiene_path.write_text(stable_json(build_read_model(sqlite_path=sqlite_path, generated_at=generated_at)), encoding="utf-8")
    events_path = intake.export_read_model(sqlite_path=sqlite_path, export_root=export_root, generated_at=generated_at)
    review_path = _rooted(export_root) / review.JSON_EXPORT_NAME
    review_path.write_text(review.stable_json(review.build_review_surface(sqlite_path=sqlite_path, generated_at=generated_at)), encoding="utf-8")

    bridge_hygiene_path = ""
    bridge_events_path = ""
    bridge_review_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_hygiene = bridge_export_root / JSON_EXPORT_NAME
        bridge_events = bridge_export_root / intake.JSON_EXPORT_NAME
        bridge_review = bridge_export_root / review.JSON_EXPORT_NAME
        shutil.copy2(hygiene_path, bridge_hygiene)
        shutil.copy2(events_path, bridge_events)
        shutil.copy2(review_path, bridge_review)
        bridge_hygiene_path = bridge_hygiene.as_posix()
        bridge_events_path = bridge_events.as_posix()
        bridge_review_path = bridge_review.as_posix()
    return {
        "hygiene_read_model_path": hygiene_path.as_posix(),
        "events_read_model_path": events_path.as_posix(),
        "review_surface_path": review_path.as_posix(),
        "bridge_hygiene_read_model_path": bridge_hygiene_path,
        "bridge_events_read_model_path": bridge_events_path,
        "bridge_review_surface_path": bridge_review_path,
    }


def run_hygiene(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    request_dir: Path = DEFAULT_REQUEST_DIR,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> HygieneResult:
    generated_at = generated_at or utc_now()
    smoke, excluded, preserved = apply_smoke_hygiene(
        sqlite_path=sqlite_path,
        request_dir=request_dir,
        response_dir=response_dir,
        generated_at=generated_at,
    )
    paths = publish_read_models(
        sqlite_path=sqlite_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
    )
    return HygieneResult(
        status=READY_STATUS,
        smoke_event_ids=tuple(smoke),
        excluded_event_ids=tuple(excluded),
        preserved_event_ids=tuple(preserved),
        read_model_path=paths["hygiene_read_model_path"],
        bridge_path=paths["bridge_hygiene_read_model_path"],
        sqlite_path=str(_rooted(sqlite_path)),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit St. Anne's work-log smoke/test events.")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--request-dir", default=str(DEFAULT_REQUEST_DIR))
    parser.add_argument("--response-dir", default=str(DEFAULT_RESPONSE_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_hygiene(
        sqlite_path=Path(args.sqlite_path),
        request_dir=Path(args.request_dir),
        response_dir=Path(args.response_dir),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    payload = {
        "status": result.status,
        "smoke_event_ids": list(result.smoke_event_ids),
        "excluded_event_ids": list(result.excluded_event_ids),
        "preserved_event_ids": list(result.preserved_event_ids),
        "read_model_path": result.read_model_path,
        "bridge_path": result.bridge_path,
        "sqlite_path": result.sqlite_path,
    }
    print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
