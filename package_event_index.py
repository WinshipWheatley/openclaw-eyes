"""Package Event Index V0.

Builds a non-destructive index over package queue records, Mission Control
request/response receipts, operator conversation journal entries, and selected
read models. It creates only package_event_index outputs and does not move,
delete, consolidate, or mutate existing databases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SQLITE_ROOT = Path("generated/system_knowledge")
DEFAULT_REQUEST_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Package Event Index.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/package_event_index.sqlite")

SCHEMA_VERSION = "package_event_index_v0"
READ_MODEL_ID = "package_event_index"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
INDEX_STATUS = "PACKAGE_EVENT_INDEX_READY"

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "coupa_submit_allowed": False,
    "ledger_posting_allowed": False,
    "portal_submit_allowed": False,
    "paid": False,
    "sent": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "sqlite_consolidation_allowed": False,
    "database_move_allowed": False,
    "database_delete_allowed": False,
}

KEY_READ_MODELS = (
    "operator_conversation_journal.json",
    "workflow_package_queue_contract.json",
    "client_work_closeout_2026_06_01.json",
    "capital_hilton_invoice_operator_run_status.json",
    "st_annes_invoice_status.json",
    "capital_hilton_business_development_proposal.json",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_ref(path_or_ref: object) -> str:
    value = str(path_or_ref or "").strip()
    if not value:
        return ""
    if value.startswith("/home/openclaw/"):
        return value.removeprefix("/home/openclaw/")
    return value


def _json_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _short_summary(value: object, *, max_chars: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 14].rstrip() + " [truncated]"


def _read_model_refs(read_model_root: Path) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for filename in KEY_READ_MODELS:
        path = read_model_root / filename
        refs[filename] = {
            "path": _json_ref(filename),
            "exists": path.exists(),
            "sha256": _sha256_file(path) if path.exists() else "",
        }
    return refs


def _sqlite_table_counts(sqlite_path: Path) -> dict[str, Any]:
    if not sqlite_path.exists():
        return {"exists": False, "tables": [], "table_counts": {}}
    conn = sqlite3.connect(sqlite_path)
    try:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int | str] = {}
        for table in tables:
            try:
                quoted = '"' + table.replace('"', '""') + '"'
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
            except sqlite3.DatabaseError:
                counts[table] = "unavailable"
        return {"exists": True, "tables": tables, "table_counts": counts}
    finally:
        conn.close()


def _load_package_rows(workflow_package_sqlite: Path) -> dict[str, dict[str, Any]]:
    if not workflow_package_sqlite.exists():
        return {}
    conn = sqlite3.connect(workflow_package_sqlite)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """
                SELECT package_id, workflow_ref, world, client_ref, source_surface,
                       source_text_ref, status, created_at
                FROM packages
                """
            ).fetchall()
        except sqlite3.DatabaseError:
            return {}
        return {str(row["package_id"]): dict(row) for row in rows}
    finally:
        conn.close()


def _package_id_from_proof_refs(proof_refs: object) -> str:
    if not isinstance(proof_refs, list):
        return ""
    for item in proof_refs:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("proof_type") or "") == "workflow_package":
            return str(item.get("ref") or "")
        ref = str(item.get("ref") or "")
        if ref.startswith("workflow_package:"):
            return ref
    return ""


def _flatten_proof_refs(proof_refs: object) -> list[str]:
    refs: list[str] = []
    if isinstance(proof_refs, Mapping):
        for value in proof_refs.values():
            if isinstance(value, str) and value:
                refs.append(value)
    elif isinstance(proof_refs, list):
        for item in proof_refs:
            if isinstance(item, Mapping):
                value = item.get("path") or item.get("ref")
                if value:
                    refs.append(str(value))
            elif item:
                refs.append(str(item))
    return list(dict.fromkeys(_safe_ref(ref) for ref in refs if ref))


def _file_exists(value: str) -> bool:
    if not value:
        return False
    return Path(value).exists() or (ROOT / value).exists()


def _request_response_summary(path: str, *, allowed_keys: tuple[str, ...]) -> dict[str, Any]:
    if not path or not _file_exists(path):
        return {"exists": False, "sha256": ""}
    resolved = Path(path) if Path(path).is_absolute() else ROOT / path
    payload = _load_json(resolved)
    summary = {key: _short_summary(payload.get(key)) for key in allowed_keys if key in payload}
    summary.update(
        {
            "exists": True,
            "sha256": _sha256_file(resolved),
            "path": _safe_ref(path),
        }
    )
    return summary


def _business_action_for_event(
    event: Mapping[str, Any],
    *,
    capital_status: Mapping[str, Any],
    closeout: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> tuple[bool, str, list[str]]:
    workflow_ref = str(event.get("workflow_ref") or "")
    refs: list[str] = []
    if workflow_ref == "capital_hilton_invoice_operator_assist" and capital_status:
        if capital_status.get("coupa_submitted") is True or capital_status.get("email_to_annette_sent") is True:
            refs.append(_json_ref("capital_hilton_invoice_operator_run_status.json"))
            return True, "operator_assisted_coupa_submission_and_email_recorded", refs
    if workflow_ref == "capital_hilton_proposal_followup":
        if proposal:
            refs.append(_json_ref("capital_hilton_business_development_proposal.json"))
        if closeout:
            refs.append(_json_ref("client_work_closeout_2026_06_01.json"))
        if refs:
            return True, "operator_assisted_proposal_send_recorded", refs
    return False, "", refs


def _linked_read_models_for_event(
    event: Mapping[str, Any],
    *,
    st_annes_status: Mapping[str, Any],
    capital_status: Mapping[str, Any],
    closeout: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> list[str]:
    workflow_ref = str(event.get("workflow_ref") or "")
    refs = [_json_ref("operator_conversation_journal.json"), _json_ref("workflow_package_queue_contract.json")]
    if workflow_ref.startswith("st_annes") and st_annes_status:
        refs.append(_json_ref("st_annes_invoice_status.json"))
    if workflow_ref == "capital_hilton_invoice_operator_assist" and capital_status:
        refs.append(_json_ref("capital_hilton_invoice_operator_run_status.json"))
    if workflow_ref == "capital_hilton_proposal_followup":
        if proposal:
            refs.append(_json_ref("capital_hilton_business_development_proposal.json"))
        if closeout:
            refs.append(_json_ref("client_work_closeout_2026_06_01.json"))
    return list(dict.fromkeys(refs))


def _authority_summary(
    event: Mapping[str, Any],
    *,
    business_action_performed: bool,
    business_action_kind: str,
) -> dict[str, Any]:
    return {
        "index_grants_authority": False,
        "email_send_allowed": False,
        "coupa_submit_allowed": False,
        "ledger_posting_allowed": False,
        "paid_truth": False,
        "ledger_excluded": True,
        "business_action_performed": business_action_performed,
        "business_action_source": "existing_operator_ingested_read_model" if business_action_performed else "none",
        "business_action_kind": business_action_kind,
        "does_not_create_new_business_truth": True,
        "package_status_source": "operator_conversation_journal",
    }


def _event_from_journal_entry(
    entry: Mapping[str, Any],
    *,
    package_rows: Mapping[str, Mapping[str, Any]],
    capital_status: Mapping[str, Any],
    st_annes_status: Mapping[str, Any],
    closeout: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    package_id = str(entry.get("package_id") or "") or _package_id_from_proof_refs(entry.get("proof_refs"))
    package_row = package_rows.get(package_id, {})
    workflow_ref = str(entry.get("workflow_ref") or package_row.get("workflow_ref") or "")
    business_action_performed, business_action_kind, business_refs = _business_action_for_event(
        {"workflow_ref": workflow_ref},
        capital_status=capital_status,
        closeout=closeout,
        proposal=proposal,
    )
    linked_read_models = _linked_read_models_for_event(
        {"workflow_ref": workflow_ref},
        st_annes_status=st_annes_status,
        capital_status=capital_status,
        closeout=closeout,
        proposal=proposal,
    )
    linked_read_models.extend(business_refs)
    proof_refs = _flatten_proof_refs(entry.get("proof_refs"))
    request_ref = _safe_ref(entry.get("request_ref") or "")
    response_ref = _safe_ref(entry.get("response_ref") or "")
    if request_ref and request_ref not in proof_refs:
        proof_refs.append(request_ref)
    if response_ref and response_ref not in proof_refs:
        proof_refs.append(response_ref)
    return {
        "event_id": "package_event:" + hashlib.sha256(
            stable_json(
                {
                    "journal_entry_id": entry.get("journal_entry_id"),
                    "package_id": package_id,
                    "request_ref": request_ref,
                    "response_ref": response_ref,
                }
            ).encode("utf-8")
        ).hexdigest()[:16],
        "package_id": package_id,
        "workflow_ref": workflow_ref,
        "request_ref": request_ref,
        "response_ref": response_ref,
        "journal_entry_id": str(entry.get("journal_entry_id") or ""),
        "target_world_ref": str(entry.get("target_world_ref") or package_row.get("world") or ""),
        "target_thread_ref": str(entry.get("target_thread_ref") or package_row.get("client_ref") or ""),
        "speaker_ref": str(entry.get("speaker_ref") or ""),
        "package_status": str(entry.get("package_status") or package_row.get("status") or ""),
        "action_status": str(entry.get("action_status") or entry.get("package_status") or package_row.get("status") or ""),
        "proof_refs": list(dict.fromkeys(proof_refs)),
        "created_at": str(entry.get("created_at") or package_row.get("created_at") or ""),
        "source_surface": str(entry.get("source_surface") or package_row.get("source_surface") or ""),
        "business_action_performed": business_action_performed,
        "business_action_kind": business_action_kind,
        "authority_summary": _authority_summary(
            entry,
            business_action_performed=business_action_performed,
            business_action_kind=business_action_kind,
        ),
        "linked_read_models": list(dict.fromkeys(linked_read_models)),
        "request_summary": _request_response_summary(
            request_ref,
            allowed_keys=("request_id", "request_type", "source_surface", "protected_text_hash", "created_at"),
        ),
        "response_summary": _request_response_summary(
            response_ref,
            allowed_keys=(
                "source_request_id",
                "workflow_ref",
                "package_status",
                "raw_internal_status",
                "response_kind",
                "speaker_ref",
                "created_at",
            ),
        ),
        "raw_request_body_stored": False,
    }


def _source_systems(
    *,
    read_model_root: Path,
    sqlite_root: Path,
    request_inbox: Path,
    response_dir: Path,
) -> dict[str, Any]:
    workflow_package_sqlite = sqlite_root / "workflow_package_queue.sqlite"
    operator_journal_sqlite = sqlite_root / "operator_conversation_journal.sqlite"
    return {
        "workflow_package_queue_sqlite": {
            "path": _safe_ref(workflow_package_sqlite),
            "included": True,
            "policy": "referenced_only_not_mutated",
            **_sqlite_table_counts(workflow_package_sqlite),
        },
        "operator_conversation_journal_sqlite": {
            "path": _safe_ref(operator_journal_sqlite),
            "included": operator_journal_sqlite.exists(),
            "policy": "referenced_only_not_mutated",
            **_sqlite_table_counts(operator_journal_sqlite),
        },
        "mission_control_requests": {
            "path": _safe_ref(request_inbox),
            "included": True,
            "policy": "metadata_and_hash_refs_only",
            "json_file_count": len(list(request_inbox.glob("*.json"))) if request_inbox.exists() else 0,
        },
        "mission_control_responses": {
            "path": _safe_ref(response_dir),
            "included": True,
            "policy": "metadata_and_hash_refs_only",
            "json_file_count": len(list(response_dir.glob("*.json"))) if response_dir.exists() else 0,
        },
        "key_read_models": _read_model_refs(read_model_root),
        "business_ledger": {
            "included": False,
            "policy": "excluded",
            "path": "",
            "reason": "Package event index does not read, consolidate, move, or mutate business ledger databases.",
        },
    }


def build_package_event_index(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_root: Path = DEFAULT_SQLITE_ROOT,
    request_inbox: Path = DEFAULT_REQUEST_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    read_model_root = _rooted(read_model_root)
    sqlite_root = _rooted(sqlite_root)
    generated_at = generated_at or utc_now()
    journal = _load_json(read_model_root / "operator_conversation_journal.json")
    entries = journal.get("entries") if isinstance(journal.get("entries"), list) else []
    package_rows = _load_package_rows(sqlite_root / "workflow_package_queue.sqlite")
    capital_status = _load_json(read_model_root / "capital_hilton_invoice_operator_run_status.json")
    st_annes_status = _load_json(read_model_root / "st_annes_invoice_status.json")
    closeout = _load_json(read_model_root / "client_work_closeout_2026_06_01.json")
    proposal = _load_json(read_model_root / "capital_hilton_business_development_proposal.json")

    events = [
        _event_from_journal_entry(
            entry,
            package_rows=package_rows,
            capital_status=capital_status,
            st_annes_status=st_annes_status,
            closeout=closeout,
            proposal=proposal,
        )
        for entry in entries
        if isinstance(entry, Mapping)
    ]
    events.sort(key=lambda event: (event.get("created_at") or "", event["event_id"]))
    workflow_refs = sorted({event["workflow_ref"] for event in events if event.get("workflow_ref")})
    source_systems = _source_systems(
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
        request_inbox=request_inbox,
        response_dir=response_dir,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": INDEX_STATUS,
        "purpose": "Unified non-destructive index over packages, Mission Control requests/responses, operator conversation journal entries, and selected read models.",
        "event_count": len(events),
        "workflow_refs_indexed": workflow_refs,
        "source_systems": source_systems,
        "events": events,
        "consolidation_risk_reduction": {
            "duplicate_package_concepts_reduced_by_index": True,
            "sqlite_consolidated": False,
            "existing_databases_moved": False,
            "existing_package_records_mutated": False,
            "ledger_excluded": True,
        },
        "privacy": {
            "raw_long_prompt_bodies_stored": False,
            "raw_request_bodies_stored": False,
            "stores_refs_hashes_summaries_only": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "non_destructive_index_only": True,
            "business_ledger_excluded": True,
            "sqlite_consolidated": False,
            "existing_databases_moved_or_deleted": False,
            "existing_package_records_mutated": False,
            "raw_prompt_bodies_excluded": True,
            "event_count": len(events),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "unsafe_true_grants_absent": True,
        },
    }
    payload["content_hash"] = _sha256_text(stable_json(payload))
    return payload


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS package_event_index (
  event_id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  request_ref TEXT NOT NULL,
  response_ref TEXT NOT NULL,
  journal_entry_id TEXT NOT NULL,
  target_world_ref TEXT NOT NULL,
  target_thread_ref TEXT NOT NULL,
  speaker_ref TEXT NOT NULL,
  package_status TEXT NOT NULL,
  action_status TEXT NOT NULL,
  proof_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_surface TEXT NOT NULL,
  business_action_performed INTEGER NOT NULL CHECK(business_action_performed IN (0, 1)),
  business_action_kind TEXT NOT NULL,
  authority_summary_json TEXT NOT NULL,
  linked_read_models_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS package_event_index_sources (
  source_key TEXT PRIMARY KEY,
  source_ref TEXT NOT NULL,
  included INTEGER NOT NULL CHECK(included IN (0, 1)),
  policy TEXT NOT NULL
);
""".strip() + "\n"


def record_sqlite_index(payload: Mapping[str, Any], sqlite_path: Path) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(sqlite_schema_sql())
        conn.execute("DELETE FROM package_event_index")
        conn.execute("DELETE FROM package_event_index_sources")
        for event in payload.get("events", []):
            if not isinstance(event, Mapping):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO package_event_index (
                  event_id, package_id, workflow_ref, request_ref, response_ref, journal_entry_id,
                  target_world_ref, target_thread_ref, speaker_ref, package_status, action_status,
                  proof_refs_json, created_at, source_surface, business_action_performed,
                  business_action_kind, authority_summary_json, linked_read_models_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event["event_id"]),
                    str(event.get("package_id") or ""),
                    str(event.get("workflow_ref") or ""),
                    str(event.get("request_ref") or ""),
                    str(event.get("response_ref") or ""),
                    str(event.get("journal_entry_id") or ""),
                    str(event.get("target_world_ref") or ""),
                    str(event.get("target_thread_ref") or ""),
                    str(event.get("speaker_ref") or ""),
                    str(event.get("package_status") or ""),
                    str(event.get("action_status") or ""),
                    stable_json(event.get("proof_refs") or []),
                    str(event.get("created_at") or ""),
                    str(event.get("source_surface") or ""),
                    int(bool(event.get("business_action_performed"))),
                    str(event.get("business_action_kind") or ""),
                    stable_json(event.get("authority_summary") or {}),
                    stable_json(event.get("linked_read_models") or []),
                ),
            )
        for key, source in payload.get("source_systems", {}).items():
            if not isinstance(source, Mapping):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO package_event_index_sources (
                  source_key, source_ref, included, policy
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    str(key),
                    str(source.get("path") or ""),
                    int(bool(source.get("included"))),
                    str(source.get("policy") or ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def build_wiki(payload: Mapping[str, Any], *, sqlite_path: Path, bridge_path: Path | None) -> str:
    lines = [
        "# Package Event Index",
        "",
        f"Status: `{INDEX_STATUS}`",
        "",
        "This is a non-destructive reference index across workflow packages, Mission Control requests/responses, operator conversation journal entries, and selected read models.",
        "",
        "## Outputs",
        "",
        f"- Read model: `generated/read_models/{JSON_EXPORT_NAME}`",
        f"- SQLite index: `{_safe_ref(sqlite_path)}`",
    ]
    if bridge_path:
        lines.append(f"- Bridge read model: `{_safe_ref(bridge_path)}`")
    lines.extend(
        [
            "",
            "## Scope",
            "",
            f"- Rows indexed: `{payload.get('event_count')}`",
            f"- Workflow refs: `{', '.join(payload.get('workflow_refs_indexed') or [])}`",
            "- Existing SQLite databases are referenced only. They are not consolidated, moved, deleted, or rewritten.",
            "- Business ledger databases are excluded.",
            "- Raw prompt and request bodies are not stored.",
            "- Email/Coupa/proposal events are only marked from already ingested operator-assisted read models.",
            "",
            "## Consolidation Risk",
            "",
            "The index reduces duplicate package concept risk by making one cross-reference surface without merging source databases.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_package_event_index(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_root: Path = DEFAULT_SQLITE_ROOT,
    request_inbox: Path = DEFAULT_REQUEST_INBOX,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_package_event_index(
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
        request_inbox=request_inbox,
        response_dir=response_dir,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_read_model_path: Path | None = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_read_model_path = bridge_export_root / JSON_EXPORT_NAME
        bridge_read_model_path.write_text(stable_json(payload), encoding="utf-8")

    resolved_sqlite_path = _rooted(sqlite_path)
    record_sqlite_index(payload, resolved_sqlite_path)

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(payload, sqlite_path=resolved_sqlite_path, bridge_path=bridge_read_model_path), encoding="utf-8")

    return {
        "status": INDEX_STATUS,
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path.as_posix() if bridge_read_model_path else "",
        "wiki_path": wiki_path.as_posix(),
        "sqlite_path": resolved_sqlite_path.as_posix(),
        "event_count": len(payload["events"]),
        "workflow_refs_indexed": payload["workflow_refs_indexed"],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export non-destructive Package Event Index V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--sqlite-root", default=str(DEFAULT_SQLITE_ROOT))
    parser.add_argument("--request-inbox", default=str(DEFAULT_REQUEST_INBOX))
    parser.add_argument("--response-dir", default=str(DEFAULT_RESPONSE_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_package_event_index(
        read_model_root=Path(args.read_model_root),
        sqlite_root=Path(args.sqlite_root),
        request_inbox=Path(args.request_inbox),
        response_dir=Path(args.response_dir),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
