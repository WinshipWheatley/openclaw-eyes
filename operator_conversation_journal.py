"""Operator conversation journal V0.

This module builds a lightweight Mission Control history grouped by target
world/thread. It stores short operator-display summaries and proof refs, not raw
request bodies or backend proof dumps. It never runs live providers or mutates
business truth.
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
from typing import Any, Mapping

import workflow_package_request_consumer as consumer


ROOT = Path(__file__).resolve().parent
DEFAULT_REQUEST_DIR = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_PACKAGE_QUEUE_SQLITE_PATH = Path("generated/system_knowledge/workflow_package_queue.sqlite")
DEFAULT_FINANCE_THREAD_INDEX_PATH = Path("generated/read_models/finance_thread_index.json")
DEFAULT_BUSINESS_DEVELOPMENT_PROPOSAL_PATH = Path("generated/read_models/capital_hilton_business_development_proposal.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/operator_conversation_journal.sqlite")

SCHEMA_VERSION = "operator_conversation_journal_v0"
READ_MODEL_ID = "operator_conversation_journal"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPERATOR_CONVERSATION_JOURNAL_READY"

AUTHORITY_BOUNDARY = {
    "telegram_live_connection_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid": False,
    "sent": False,
}


@dataclass(frozen=True)
class PublishResult:
    status: str
    read_model_path: str
    bridge_path: str
    sqlite_path: str
    entry_count: int
    grouped_thread_counts: dict[str, int]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object) -> str:
    text = "\u241f".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _request_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("request_id") or payload.get("source_request_id") or "").strip()


def _response_request_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("source_request_id") or payload.get("request_ref") or payload.get("request_id") or "").strip()


def index_request_files(request_dir: Path = DEFAULT_REQUEST_DIR) -> dict[str, dict[str, Any]]:
    request_dir = _rooted(request_dir)
    index: dict[str, dict[str, Any]] = {}
    if not request_dir.exists():
        return index
    for path in sorted(request_dir.glob("*.json")):
        payload = _read_json(path)
        if not payload:
            continue
        request_id = _request_id(payload)
        if not request_id:
            continue
        index[request_id] = {
            "path": path.as_posix(),
            "payload": payload,
        }
    return index


def _nested_consumer(response: Mapping[str, Any]) -> Mapping[str, Any]:
    detail = response.get("detail_disclosure")
    if isinstance(detail, Mapping):
        consumer_detail = detail.get("workflow_package_request_consumer")
        if isinstance(consumer_detail, Mapping):
            return consumer_detail
    return {}


def _nested_package(response: Mapping[str, Any]) -> Mapping[str, Any]:
    detail = response.get("detail_disclosure")
    if isinstance(detail, Mapping):
        package = detail.get("package")
        if isinstance(package, Mapping):
            return package
    return {}


def _operator_display(response: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = response.get("operator_display")
    if isinstance(direct, Mapping) and direct:
        return direct
    nested = _nested_consumer(response).get("operator_display")
    if isinstance(nested, Mapping) and nested:
        return nested
    package_display = _nested_package(response).get("operator_display")
    if isinstance(package_display, Mapping) and package_display:
        return package_display
    return {}


def _visible_card_summary(response: Mapping[str, Any]) -> tuple[str, str]:
    cards = response.get("visible_cards")
    if isinstance(cards, list) and cards:
        first = cards[0]
        if isinstance(first, Mapping):
            headline = str(first.get("title") or "").strip()
            bullets = first.get("bullets")
            summary = ""
            if isinstance(bullets, list):
                for bullet in bullets:
                    text = str(bullet or "").strip()
                    if text and not text.startswith(("Package:", "Workflow:", "Client:", "Authority:")):
                        summary = text
                        break
            return headline, summary
    return "", ""


def _field(response: Mapping[str, Any], nested: Mapping[str, Any], key: str, default: str = "") -> str:
    value = response.get(key)
    if value in (None, ""):
        value = nested.get(key)
    return str(value if value is not None else default)


def _target_lane(response: Mapping[str, Any], request_payload: Mapping[str, Any], nested: Mapping[str, Any]) -> tuple[str, str]:
    target_world = _field(response, nested, "target_world_ref")
    target_thread = _field(response, nested, "target_thread_ref")
    if target_world and target_thread:
        return target_world, target_thread
    workflow_ref = _field(response, nested, "workflow_ref")
    return consumer.target_lane_for_workflow(workflow_ref)


def _current_lane(response: Mapping[str, Any], request_payload: Mapping[str, Any], nested: Mapping[str, Any]) -> tuple[str, str]:
    current_world = _field(response, nested, "current_world_ref")
    current_thread = _field(response, nested, "current_thread_ref")
    if current_world and current_thread:
        return current_world, current_thread
    raw_world = str(request_payload.get("world_ref") or request_payload.get("world") or nested.get("source_world_ref") or "")
    raw_thread = str(request_payload.get("thread_ref") or nested.get("source_thread_ref") or "")
    return consumer.normalize_world_ref(raw_world), consumer.normalize_thread_ref(raw_thread)


def _source_text_ref(request_payload: Mapping[str, Any], nested: Mapping[str, Any]) -> str:
    value = request_payload.get("source_text_ref") or nested.get("source_text_ref")
    if value:
        return str(value)
    protected_hash = str(request_payload.get("protected_text_hash") or "")
    return "protected_text_hash:" + protected_hash if protected_hash else ""


def _proof_refs(
    *,
    request_ref: str,
    response_ref: str,
    source_text_ref: str,
    nested: Mapping[str, Any],
    package: Mapping[str, Any],
) -> list[dict[str, str]]:
    refs = [
        {"proof_type": "request_ref", "path": request_ref},
        {"proof_type": "response_ref", "path": response_ref},
    ]
    if source_text_ref:
        refs.append({"proof_type": "source_text_ref", "ref": source_text_ref})
    package_id = str(nested.get("package_id") or package.get("package_id") or "")
    if package_id:
        refs.append({"proof_type": "workflow_package", "ref": package_id})
    sqlite_path = str(nested.get("sqlite_path") or "")
    if sqlite_path:
        refs.append({"proof_type": "sqlite_path", "path": sqlite_path})
    return refs


def build_journal_entry(
    *,
    response_path: Path,
    response: Mapping[str, Any],
    request_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if str(response.get("response_kind") or "") != "WORKFLOW_PACKAGE_REQUEST_RESPONSE":
        return None
    request_id = _response_request_id(response)
    request_record = request_index.get(request_id, {})
    request_payload = request_record.get("payload") if isinstance(request_record.get("payload"), Mapping) else {}
    request_ref = str(request_record.get("path") or "")
    nested = _nested_consumer(response)
    package = _nested_package(response)
    display = _operator_display(response)
    fallback_headline, fallback_summary = _visible_card_summary(response)
    current_world, current_thread = _current_lane(response, request_payload, nested)
    target_world, target_thread = _target_lane(response, request_payload, nested)
    cross_lane = current_world != target_world or current_thread != target_thread
    routing_note = _field(response, nested, "routing_note")
    if cross_lane and not routing_note:
        routing_note = consumer.routing_note_for_lane(target_world, target_thread)
    source_text_ref = _source_text_ref(request_payload, nested)
    timestamp = str(response.get("generated_at") or response.get("created_at") or nested.get("created_at") or "")
    if not timestamp:
        timestamp = datetime.fromtimestamp(response_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    headline = str(display.get("headline") or response.get("headline") or fallback_headline or "Workflow package response")
    short_summary = str(
        display.get("plain_summary")
        or response.get("one_line_answer")
        or response.get("what_happened")
        or fallback_summary
        or response.get("primary_status")
        or "Package response recorded."
    )
    speaker_ref = str(display.get("speaker_ref") or response.get("speaker_ref") or nested.get("speaker_ref") or "openclaw")
    voice_mode = str(display.get("voice_mode") or response.get("voice_mode") or nested.get("voice_mode") or "status")
    package_status = str(response.get("package_status") or nested.get("package_status") or package.get("status") or "")
    action_status = str(response.get("primary_status") or nested.get("primary_status") or package_status)
    response_ref = response_path.as_posix()
    return {
        "journal_entry_id": "operator_conversation_journal:" + _short_hash(request_id, response_ref, timestamp),
        "timestamp": timestamp,
        "source_surface": str(request_payload.get("source_surface") or package.get("source_surface") or "mission_control"),
        "current_world_ref": current_world,
        "current_thread_ref": current_thread,
        "target_world_ref": target_world,
        "target_thread_ref": target_thread,
        "cross_lane_routed": cross_lane,
        "routing_note": routing_note,
        "speaker_ref": speaker_ref,
        "voice_mode": voice_mode,
        "headline": headline,
        "short_summary": short_summary,
        "package_status": package_status,
        "action_status": action_status,
        "proof_refs": _proof_refs(
            request_ref=request_ref,
            response_ref=response_ref,
            source_text_ref=source_text_ref,
            nested=nested,
            package=package,
        ),
        "request_ref": request_ref,
        "response_ref": response_ref,
        "source_text_ref": source_text_ref,
        "raw_request_body_stored": False,
        "show_machine_details_by_default": False,
    }


def _load_supporting_statuses(
    *,
    finance_thread_index_path: Path,
    business_development_proposal_path: Path,
) -> dict[str, Any]:
    finance = _read_json(_rooted(finance_thread_index_path)) or {}
    proposal = _read_json(_rooted(business_development_proposal_path)) or {}
    return {
        "finance_thread_index": {
            "path": str(finance_thread_index_path),
            "status": str(finance.get("status") or ""),
            "threads": [
                {
                    "world_ref": thread.get("world_ref"),
                    "thread_ref": thread.get("thread_ref"),
                    "display_name": thread.get("display_name"),
                }
                for thread in finance.get("threads", [])
                if isinstance(thread, Mapping)
            ],
        },
        "capital_hilton_business_development_proposal": {
            "path": str(business_development_proposal_path),
            "proposal_status": str(proposal.get("proposal_status") or ""),
            "proposal_accepted": bool(proposal.get("proposal_accepted") is True),
            "finance_handoff_allowed": bool(proposal.get("finance_handoff_allowed") is True),
        },
    }


def build_journal(
    *,
    request_dir: Path = DEFAULT_REQUEST_DIR,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    package_queue_sqlite_path: Path = DEFAULT_PACKAGE_QUEUE_SQLITE_PATH,
    finance_thread_index_path: Path = DEFAULT_FINANCE_THREAD_INDEX_PATH,
    business_development_proposal_path: Path = DEFAULT_BUSINESS_DEVELOPMENT_PROPOSAL_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    response_dir = _rooted(response_dir)
    request_index = index_request_files(request_dir)
    entries: list[dict[str, Any]] = []
    if response_dir.exists():
        for path in sorted(response_dir.glob("*.json")):
            payload = _read_json(path)
            if not payload:
                continue
            entry = build_journal_entry(response_path=path, response=payload, request_index=request_index)
            if entry is not None:
                entries.append(entry)
    entries.sort(key=lambda item: (item["timestamp"], item["response_ref"]))
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = f"{entry['target_world_ref']}/{entry['target_thread_ref']}"
        group = grouped.setdefault(
            key,
            {
                "world_ref": entry["target_world_ref"],
                "thread_ref": entry["target_thread_ref"],
                "entry_count": 0,
                "latest_timestamp": "",
                "latest_headline": "",
            },
        )
        group["entry_count"] += 1
        group["latest_timestamp"] = entry["timestamp"]
        group["latest_headline"] = entry["headline"]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": READY_STATUS,
        "purpose": "Compact operator-visible Mission Control request/response history grouped by target world/thread.",
        "source_inputs": {
            "request_dir": str(request_dir),
            "response_dir": str(response_dir),
            "workflow_package_queue_sqlite": str(package_queue_sqlite_path),
        },
        "supporting_read_models": _load_supporting_statuses(
            finance_thread_index_path=finance_thread_index_path,
            business_development_proposal_path=business_development_proposal_path,
        ),
        "entry_count": len(entries),
        "grouped_thread_counts": dict(sorted((key, value["entry_count"]) for key, value in grouped.items())),
        "threads": [grouped[key] for key in sorted(grouped)],
        "entries": entries,
        "privacy": {
            "raw_request_bodies_stored": False,
            "raw_long_prompt_dumps_stored": False,
            "source_text_refs_or_hashes_only": True,
            "proof_links_collapsed_by_default": True,
            "operator_display_summaries_only": True,
        },
        "rules": {
            "finance_st_annes_history_includes_work_log_events": True,
            "business_development_capital_hilton_includes_proposal_followup": True,
            "finance_capital_hilton_includes_invoice_operator_assist": True,
            "proof_details_are_refs": True,
            "no_business_action_occurs": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "no_raw_request_body_fields": all("source_text" not in entry and "operator_message" not in entry for entry in entries),
            "show_machine_details_default_false": all(entry["show_machine_details_by_default"] is False for entry in entries),
            "st_annes_group_present": "finance/st_annes" in grouped,
            "capital_hilton_finance_group_present": "finance/capital_hilton" in grouped,
            "capital_hilton_business_development_group_present": "business_development/capital_hilton" in grouped,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
        },
    }


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS operator_conversation_journal_entries (
  journal_entry_id TEXT PRIMARY KEY,
  timestamp TEXT NOT NULL,
  source_surface TEXT NOT NULL,
  current_world_ref TEXT NOT NULL,
  current_thread_ref TEXT NOT NULL,
  target_world_ref TEXT NOT NULL,
  target_thread_ref TEXT NOT NULL,
  speaker_ref TEXT NOT NULL,
  voice_mode TEXT NOT NULL,
  headline TEXT NOT NULL,
  short_summary TEXT NOT NULL,
  package_status TEXT NOT NULL,
  action_status TEXT NOT NULL,
  proof_refs_json TEXT NOT NULL,
  request_ref TEXT NOT NULL,
  response_ref TEXT NOT NULL,
  show_machine_details_by_default INTEGER NOT NULL CHECK(show_machine_details_by_default IN (0, 1))
);
""".strip() + "\n"


def export_sqlite(journal: Mapping[str, Any], *, sqlite_path: Path = DEFAULT_SQLITE_PATH) -> Path:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(sqlite_schema_sql())
        conn.execute("DELETE FROM operator_conversation_journal_entries")
        for entry in journal.get("entries", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO operator_conversation_journal_entries (
                  journal_entry_id, timestamp, source_surface, current_world_ref, current_thread_ref,
                  target_world_ref, target_thread_ref, speaker_ref, voice_mode, headline, short_summary,
                  package_status, action_status, proof_refs_json, request_ref, response_ref,
                  show_machine_details_by_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["journal_entry_id"],
                    entry["timestamp"],
                    entry["source_surface"],
                    entry["current_world_ref"],
                    entry["current_thread_ref"],
                    entry["target_world_ref"],
                    entry["target_thread_ref"],
                    entry["speaker_ref"],
                    entry["voice_mode"],
                    entry["headline"],
                    entry["short_summary"],
                    entry["package_status"],
                    entry["action_status"],
                    stable_json(entry["proof_refs"]),
                    entry["request_ref"],
                    entry["response_ref"],
                    int(bool(entry["show_machine_details_by_default"])),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return sqlite_path


def publish_journal(
    *,
    request_dir: Path = DEFAULT_REQUEST_DIR,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    package_queue_sqlite_path: Path = DEFAULT_PACKAGE_QUEUE_SQLITE_PATH,
    finance_thread_index_path: Path = DEFAULT_FINANCE_THREAD_INDEX_PATH,
    business_development_proposal_path: Path = DEFAULT_BUSINESS_DEVELOPMENT_PROPOSAL_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> PublishResult:
    journal = build_journal(
        request_dir=request_dir,
        response_dir=response_dir,
        package_queue_sqlite_path=package_queue_sqlite_path,
        finance_thread_index_path=finance_thread_index_path,
        business_development_proposal_path=business_development_proposal_path,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / JSON_EXPORT_NAME
    local_path.write_text(stable_json(journal), encoding="utf-8")
    sqlite_output = export_sqlite(journal, sqlite_path=sqlite_path)
    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(local_path, bridge)
        bridge_path = bridge.as_posix()
    return PublishResult(
        status=str(journal["status"]),
        read_model_path=local_path.as_posix(),
        bridge_path=bridge_path,
        sqlite_path=sqlite_output.as_posix(),
        entry_count=int(journal["entry_count"]),
        grouped_thread_counts=dict(journal["grouped_thread_counts"]),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish the operator conversation journal.")
    parser.add_argument("--request-dir", default=str(DEFAULT_REQUEST_DIR))
    parser.add_argument("--response-dir", default=str(DEFAULT_RESPONSE_DIR))
    parser.add_argument("--package-queue-sqlite-path", default=str(DEFAULT_PACKAGE_QUEUE_SQLITE_PATH))
    parser.add_argument("--finance-thread-index-path", default=str(DEFAULT_FINANCE_THREAD_INDEX_PATH))
    parser.add_argument("--business-development-proposal-path", default=str(DEFAULT_BUSINESS_DEVELOPMENT_PROPOSAL_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = publish_journal(
        request_dir=Path(args.request_dir),
        response_dir=Path(args.response_dir),
        package_queue_sqlite_path=Path(args.package_queue_sqlite_path),
        finance_thread_index_path=Path(args.finance_thread_index_path),
        business_development_proposal_path=Path(args.business_development_proposal_path),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    payload = {
        "status": result.status,
        "read_model_path": result.read_model_path,
        "bridge_path": result.bridge_path,
        "sqlite_path": result.sqlite_path,
        "entry_count": result.entry_count,
        "grouped_thread_counts": result.grouped_thread_counts,
    }
    print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
