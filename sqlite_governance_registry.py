"""SQLite Governance Registry V0.

Classifies OpenClaw SQLite databases by truth ownership and consolidation
posture. This is a metadata-only registry: it does not consolidate, migrate,
delete, or mutate existing databases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
DEFAULT_OPENCLAW_ROOT = Path(".openclaw")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/SQLite Governance Registry.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/sqlite_governance_registry.sqlite")
DEFAULT_AGENTIC_CHAIN_READ_MODEL = Path("generated/read_models/agentic_chain_inspector.json")
DEFAULT_AGENTIC_CHAIN_SQLITE = Path("generated/system_knowledge/agentic_chain_inspector.sqlite")
DEFAULT_PACKAGE_EVENT_INDEX_READ_MODEL = Path("generated/read_models/package_event_index.json")

SCHEMA_VERSION = "sqlite_governance_registry_v0"
READ_MODEL_ID = "sqlite_governance_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
REGISTRY_STATUS = "SQLITE_GOVERNANCE_REGISTRY_READY"
REGISTRY_NOT_READY_STATUS = "SQLITE_GOVERNANCE_REGISTRY_NOT_READY"

REQUIRED_PRECONDITIONS = {
    "agentic_chain_inspector": "AGENTIC_CHAIN_INSPECTOR_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
}

CLASSIFICATIONS = (
    "canonical_workflow_state",
    "generated_evidence",
    "generated_status",
    "test_harness",
    "legacy_archive",
    "protected_business_ledger",
    "unknown_needs_review",
)

CONSOLIDATION_RISKS = ("low", "medium", "high", "forbidden")

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "database_delete_allowed": False,
    "database_move_allowed": False,
    "sqlite_consolidation_allowed": False,
    "sent": False,
    "paid": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _safe_load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


def _sqlite_uri(path: Path) -> str:
    return "file:" + quote(path.resolve().as_posix(), safe="/:") + "?mode=ro"


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sqlite_metadata(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    stat = path.stat()
    tables: list[str] = []
    row_counts: dict[str, int | str] = {}
    open_status = "ok"
    error = ""
    try:
        conn = sqlite3.connect(_sqlite_uri(path), uri=True)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            tables = [str(row[0]) for row in rows]
            for table in tables:
                try:
                    row_counts[table] = int(
                        conn.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").fetchone()[0]
                    )
                except sqlite3.DatabaseError as exc:
                    row_counts[table] = f"unavailable:{exc.__class__.__name__}"
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        open_status = "error"
        error = f"{exc.__class__.__name__}: {exc}"
    return {
        "path": path.resolve().as_posix(),
        "tables": tables,
        "row_counts": row_counts,
        "last_modified": _iso_from_timestamp(stat.st_mtime),
        "open_status": open_status,
        "error": error,
        "source": "direct_scan",
    }


def _discover_sqlite_paths(roots: Iterable[Path]) -> list[Path]:
    patterns = ("*.sqlite", "*.sqlite3", "*.db")
    paths: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = _rooted(root)
        if not resolved.exists():
            continue
        for pattern in patterns:
            for path in sorted(resolved.rglob(pattern)):
                if not path.is_file():
                    continue
                key = path.resolve().as_posix()
                if key not in seen:
                    seen.add(key)
                    paths.append(path)
    return paths


def _purpose_from_path(path: str, tables: Iterable[str], fallback: str = "") -> str:
    text = path.lower()
    table_text = " ".join(tables).lower()
    if fallback:
        return fallback
    if "ledger" in text:
        return "business ledger or ledger-shaped fixture"
    if "workflow_package_queue" in text or "packages" in table_text:
        return "workflow package queue and gate registry"
    if "operator_conversation_journal" in text:
        return "operator conversation journal"
    if "operator_action" in text:
        return "operator action event journal"
    if "package_event_index" in text:
        return "package event index evidence"
    if "agentic_chain_inspector" in text:
        return "agentic chain inspector inventory evidence"
    if "sqlite_governance_registry" in text:
        return "SQLite governance registry generated evidence"
    if _is_openclaw_test_path(text):
        return "test harness or pytest fixture database"
    if "token_vault" in text:
        return "privacy token vault"
    if "invoice" in text:
        return "invoice status or invoice review evidence"
    if any(term in text for term in ("sentinel", "health", "service", "status", "supervision")):
        return "system health, sentinel, or service status"
    if "memory" in text:
        return "agent memory store"
    return "local OpenClaw SQLite state"


def _is_openclaw_test_path(path_text: str) -> bool:
    return (
        "/.openclaw/test_harness/" in path_text
        or "/.openclaw/tmp/" in path_text
        or "/test_harness/" in path_text
    )


def _load_agentic_chain_json_inventory(path: Path) -> list[dict[str, Any]]:
    payload = _safe_load_json(path)
    inventory = payload.get("sqlite_inventory")
    if not isinstance(inventory, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in inventory:
        if isinstance(item, Mapping) and item.get("path"):
            rows.append({**dict(item), "source": "agentic_chain_inspector_json"})
    return rows


def _load_agentic_chain_sqlite_inventory(path: Path) -> list[dict[str, Any]]:
    path = _rooted(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(_sqlite_uri(path), uri=True)
        conn.row_factory = sqlite3.Row
        try:
            records = conn.execute(
                """
                SELECT path, purpose, tables_json, row_counts_json, last_modified,
                       canonical_noncanonical_guess, consolidation_risk, open_status, error
                FROM database_inventory
                ORDER BY path
                """
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return []
    for row in records:
        try:
            tables = json.loads(row["tables_json"])
        except json.JSONDecodeError:
            tables = []
        try:
            row_counts = json.loads(row["row_counts_json"])
        except json.JSONDecodeError:
            row_counts = {}
        rows.append(
            {
                "path": str(row["path"]),
                "purpose": str(row["purpose"]),
                "tables": tables if isinstance(tables, list) else [],
                "row_counts": row_counts if isinstance(row_counts, dict) else {},
                "last_modified": str(row["last_modified"]),
                "canonical_noncanonical_guess": str(row["canonical_noncanonical_guess"]),
                "consolidation_risk": str(row["consolidation_risk"]),
                "open_status": str(row["open_status"]),
                "error": str(row["error"]),
                "source": "agentic_chain_inspector_sqlite",
            }
        )
    return rows


def _merged_inventory(
    *,
    sqlite_roots: Iterable[Path],
    agentic_chain_read_model_path: Path,
    agentic_chain_sqlite_path: Path,
    extra_sqlite_paths: Iterable[Path] = (),
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    def add(item: Mapping[str, Any]) -> None:
        path_value = str(item.get("path") or "")
        if not path_value:
            return
        path = Path(path_value)
        key = (_rooted(path) if not path.is_absolute() else path).resolve().as_posix()
        existing = merged.get(key, {})
        sources = list(existing.get("source_refs") or [])
        source = str(item.get("source") or "unknown")
        if source not in sources:
            sources.append(source)
        merged[key] = {**existing, **dict(item), "path": key, "source_refs": sources}

    for item in _load_agentic_chain_json_inventory(agentic_chain_read_model_path):
        add(item)
    for item in _load_agentic_chain_sqlite_inventory(agentic_chain_sqlite_path):
        add(item)
    for path in [*_discover_sqlite_paths(sqlite_roots), *list(extra_sqlite_paths)]:
        if _rooted(path).exists():
            add(_sqlite_metadata(path))

    return [merged[key] for key in sorted(merged)]


def _risk_from_source(value: str, classification: str, path: str) -> str:
    text = f"{value} {path}".lower()
    if classification == "protected_business_ledger" or "never_mix" in text or "token_vault" in text:
        return "forbidden"
    if classification == "legacy_archive":
        return "low"
    if "low" in text:
        return "low"
    if "high" in text or "package" in text or "gate" in text:
        return "high"
    if "medium" in text:
        return "medium"
    return "medium"


def _owner_lane(path: str, purpose: str, classification: str) -> str:
    text = f"{path} {purpose}".lower()
    if classification == "protected_business_ledger":
        return "business_ops"
    if "token_vault" in text or "privacy" in text:
        return "privacy"
    if "workflow_package_queue" in text:
        return "workflow_package_queue"
    if "operator_conversation_journal" in text:
        return "operator_conversation"
    if "operator_action" in text:
        return "operator_action_events"
    if "package_event_index" in text:
        return "package_event_index"
    if "agentic_chain_inspector" in text:
        return "agentic_chain_inspector"
    if "sqlite_governance_registry" in text:
        return "sqlite_governance"
    if "invoice" in text or "st_annes" in text or "capital_hilton" in text:
        return "invoice_operations"
    if any(term in text for term in ("sentinel", "health", "service", "supervision")):
        return "system_health"
    if any(term in text for term in ("lm_child", "delegated_package", "shadow_lm", "lm_shadow")):
        return "lm_child_gate"
    if classification == "test_harness":
        return "test_harness"
    if classification == "legacy_archive":
        return "legacy_archive"
    return "unknown_review"


def classify_database(item: Mapping[str, Any]) -> dict[str, Any]:
    path = str(item.get("path") or "")
    tables = [str(table) for table in item.get("tables") or []]
    source_guess = str(item.get("canonical_noncanonical_guess") or "")
    source_risk = str(item.get("consolidation_risk") or "")
    purpose = _purpose_from_path(path, tables, str(item.get("purpose") or ""))
    text = f"{path} {purpose} {source_guess}".lower()
    notes: list[str] = []

    if "ledger" in text:
        classification = "protected_business_ledger"
        notes.append("Ledger-shaped databases are protected and never eligible for consolidation.")
    elif "business_ops/backups/" in text or "/backups/" in text or ".bak" in text:
        classification = "legacy_archive"
        notes.append("Backup or archive path; keep as historical evidence unless an operator reviews it.")
    elif _is_openclaw_test_path(text) or source_guess in {
        "noncanonical_test_or_tmp_artifact",
        "test_harness_state_keep_isolated",
    }:
        classification = "test_harness"
        notes.append("Test or temporary fixture state cannot be canonical truth.")
    elif source_guess in {
        "canonical_candidate_for_package_queue",
        "canonical_candidate_for_operator_conversation_history",
        "privacy_vault_canonical_isolated",
    }:
        classification = "canonical_workflow_state"
        notes.append("Canonical status comes from the agentic chain inspector inventory.")
    elif "generated/system_knowledge" in text and any(
        term in text for term in ("sentinel", "service", "supervision", "health", "status")
    ) and "invoice" not in text:
        classification = "generated_status"
        notes.append("Generated status database; evidence only unless another contract names it canonical.")
    elif "generated/system_knowledge" in text:
        classification = "generated_evidence"
        notes.append("Generated system knowledge; treat as evidence/read-model state, not canonical truth.")
    else:
        classification = "unknown_needs_review"
        notes.append("No explicit canonical owner found; defaulting to manual review.")

    risk = _risk_from_source(source_risk, classification, path)
    owner_lane = _owner_lane(path, purpose, classification)
    canonical_truth_allowed = (
        classification == "canonical_workflow_state"
        or (classification == "protected_business_ledger" and "/.openclaw/business_ops/ledger.sqlite" in text)
    )
    consolidation_candidate = classification in {"generated_evidence", "generated_status", "legacy_archive"} and risk != "forbidden"
    if source_guess:
        notes.append(f"Inspector guess: {source_guess}.")
    if source_risk:
        notes.append(f"Inspector consolidation signal: {source_risk}.")
    if item.get("open_status") == "error":
        notes.append(f"Metadata read error: {item.get('error') or 'unknown error'}.")

    if risk not in CONSOLIDATION_RISKS:
        risk = "medium"
    if classification not in CLASSIFICATIONS:
        classification = "unknown_needs_review"

    db_ref = "sqlite_db:sha256:" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return {
        "db_ref": db_ref,
        "path": path,
        "classification": classification,
        "owner_lane": owner_lane,
        "purpose": purpose,
        "tables": tables,
        "row_counts": dict(item.get("row_counts") or {}),
        "last_modified": str(item.get("last_modified") or ""),
        "canonical_truth_allowed": bool(canonical_truth_allowed),
        "writable_by_automation": False,
        "safe_to_delete": False,
        "consolidation_candidate": bool(consolidation_candidate),
        "consolidation_risk": risk,
        "notes": notes,
    }


def _precondition_statuses(
    *,
    agentic_chain_read_model_path: Path,
    package_event_index_read_model_path: Path,
) -> list[dict[str, Any]]:
    paths = {
        "agentic_chain_inspector": agentic_chain_read_model_path,
        "package_event_index": package_event_index_read_model_path,
    }
    statuses: list[dict[str, Any]] = []
    for key, required in REQUIRED_PRECONDITIONS.items():
        path = paths[key]
        payload = _safe_load_json(path)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        statuses.append(
            {
                "precondition_ref": key,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "path": _rooted(path).as_posix(),
            }
        )
    return statuses


def build_read_model(
    *,
    sqlite_roots: Iterable[Path] = (DEFAULT_SYSTEM_KNOWLEDGE_ROOT, DEFAULT_OPENCLAW_ROOT),
    agentic_chain_read_model_path: Path = DEFAULT_AGENTIC_CHAIN_READ_MODEL,
    agentic_chain_sqlite_path: Path = DEFAULT_AGENTIC_CHAIN_SQLITE,
    package_event_index_read_model_path: Path = DEFAULT_PACKAGE_EVENT_INDEX_READ_MODEL,
    extra_sqlite_paths: Iterable[Path] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_statuses(
        agentic_chain_read_model_path=agentic_chain_read_model_path,
        package_event_index_read_model_path=package_event_index_read_model_path,
    )
    raw_inventory = _merged_inventory(
        sqlite_roots=sqlite_roots,
        agentic_chain_read_model_path=agentic_chain_read_model_path,
        agentic_chain_sqlite_path=agentic_chain_sqlite_path,
        extra_sqlite_paths=extra_sqlite_paths,
    )
    databases = [classify_database(item) for item in raw_inventory]
    classification_counts = dict(Counter(item["classification"] for item in databases))
    owner_counts = dict(Counter(item["owner_lane"] for item in databases))
    protected_ledger_entries = [item for item in databases if item["classification"] == "protected_business_ledger"]
    consolidation_candidates = [item for item in databases if item["consolidation_candidate"]]
    unknown_review_entries = [item for item in databases if item["classification"] == "unknown_needs_review"]
    preconditions_ready = all(item["ready"] for item in preconditions)
    status = REGISTRY_STATUS if preconditions_ready else REGISTRY_NOT_READY_STATUS

    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Classifies OpenClaw SQLite databases by truth ownership, write posture, and consolidation risk.",
        "mode": "classification_only_no_consolidation",
        "preconditions": preconditions,
        "sqlite_roots_scanned": [_rooted(path).as_posix() for path in sqlite_roots if _rooted(path).exists()],
        "source_inventory_refs": [
            _rooted(agentic_chain_read_model_path).as_posix(),
            _rooted(agentic_chain_sqlite_path).as_posix(),
            _rooted(package_event_index_read_model_path).as_posix(),
        ],
        "database_count": len(databases),
        "classification_counts": classification_counts,
        "owner_lane_counts": owner_counts,
        "protected_ledger_count": len(protected_ledger_entries),
        "consolidation_candidate_count": len(consolidation_candidates),
        "unknown_review_count": len(unknown_review_entries),
        "classifications": list(CLASSIFICATIONS),
        "database_field_contract": [
            "db_ref",
            "path",
            "classification",
            "owner_lane",
            "purpose",
            "tables",
            "row_counts",
            "last_modified",
            "canonical_truth_allowed",
            "writable_by_automation",
            "safe_to_delete",
            "consolidation_candidate",
            "consolidation_risk",
            "notes",
        ],
        "databases": databases,
        "summary_refs": {
            "protected_ledger_entries": [item["db_ref"] for item in protected_ledger_entries],
            "consolidation_candidates": [item["db_ref"] for item in consolidation_candidates],
            "unknown_review_entries": [item["db_ref"] for item in unknown_review_entries],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "classification_only": True,
            "preconditions_ready": preconditions_ready,
            "sqlite_consolidation_performed": False,
            "database_move_performed": False,
            "database_delete_performed": False,
            "database_migration_performed": False,
            "ledger_mutation_performed": False,
            "workflow_db_mutation_performed": False,
            "business_state_mutation_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def registry_sqlite_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS database_governance (
  db_ref TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  classification TEXT NOT NULL,
  owner_lane TEXT NOT NULL,
  purpose TEXT NOT NULL,
  tables_json TEXT NOT NULL,
  row_counts_json TEXT NOT NULL,
  last_modified TEXT NOT NULL,
  canonical_truth_allowed INTEGER NOT NULL,
  writable_by_automation INTEGER NOT NULL,
  safe_to_delete INTEGER NOT NULL,
  consolidation_candidate INTEGER NOT NULL,
  consolidation_risk TEXT NOT NULL,
  notes_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classification_counts (
  classification TEXT PRIMARY KEY,
  count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS registry_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
""".strip() + "\n"


def write_registry_sqlite(sqlite_path: Path, read_model: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(registry_sqlite_schema())
        conn.execute("DELETE FROM database_governance")
        conn.execute("DELETE FROM classification_counts")
        conn.execute("DELETE FROM registry_metadata")
        for item in read_model["databases"]:
            conn.execute(
                """
                INSERT INTO database_governance (
                  db_ref, path, classification, owner_lane, purpose, tables_json,
                  row_counts_json, last_modified, canonical_truth_allowed,
                  writable_by_automation, safe_to_delete, consolidation_candidate,
                  consolidation_risk, notes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["db_ref"],
                    item["path"],
                    item["classification"],
                    item["owner_lane"],
                    item["purpose"],
                    stable_json(item["tables"]),
                    stable_json(item["row_counts"]),
                    item["last_modified"],
                    int(bool(item["canonical_truth_allowed"])),
                    int(bool(item["writable_by_automation"])),
                    int(bool(item["safe_to_delete"])),
                    int(bool(item["consolidation_candidate"])),
                    item["consolidation_risk"],
                    stable_json(item["notes"]),
                ),
            )
        for classification, count in sorted(read_model["classification_counts"].items()):
            conn.execute(
                "INSERT INTO classification_counts (classification, count) VALUES (?, ?)",
                (classification, int(count)),
            )
        metadata = {
            "status": str(read_model["status"]),
            "generated_at": str(read_model["generated_at"]),
            "database_count": str(read_model["database_count"]),
            "protected_ledger_count": str(read_model["protected_ledger_count"]),
            "consolidation_candidate_count": str(read_model["consolidation_candidate_count"]),
            "unknown_review_count": str(read_model["unknown_review_count"]),
        }
        for key, value in metadata.items():
            conn.execute("INSERT INTO registry_metadata (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def build_wiki(read_model: Mapping[str, Any], sqlite_path: Path) -> str:
    lines = [
        "# SQLite Governance Registry",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This registry classifies OpenClaw SQLite databases by truth ownership. It does not consolidate, migrate, delete, or grant write authority.",
        "",
        f"Registry SQLite: `{_rooted(sqlite_path).as_posix()}`",
        f"Databases classified: `{read_model['database_count']}`",
        f"Protected ledger entries: `{read_model['protected_ledger_count']}`",
        f"Consolidation candidates: `{read_model['consolidation_candidate_count']}`",
        f"Unknown review count: `{read_model['unknown_review_count']}`",
        "",
        "## Classification Counts",
        "",
    ]
    for classification in CLASSIFICATIONS:
        lines.append(f"- `{classification}`: {read_model['classification_counts'].get(classification, 0)}")
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- Business ledgers are `protected_business_ledger` and `consolidation_risk=forbidden`.",
            "- Test harness databases are never canonical truth.",
            "- Generated status and proof databases remain evidence unless explicitly named canonical.",
            "- Unknown databases are non-writable and require review.",
            "- `safe_to_delete` is false for every database.",
        ]
    )
    protected = [
        item
        for item in read_model["databases"]
        if item["classification"] == "protected_business_ledger"
    ][:10]
    if protected:
        lines.extend(["", "## Protected Ledger Samples", ""])
        for item in protected:
            lines.append(f"- `{item['path']}` ({item['consolidation_risk']})")
    unknown = [
        item
        for item in read_model["databases"]
        if item["classification"] == "unknown_needs_review"
    ][:10]
    if unknown:
        lines.extend(["", "## Unknown Review Samples", ""])
        for item in unknown:
            lines.append(f"- `{item['path']}`")
    return "\n".join(lines) + "\n"


def _write_json_and_wiki(
    *,
    read_model: Mapping[str, Any],
    export_root: Path,
    bridge_export_root: Path | None,
    wiki_path: Path,
    sqlite_path: Path,
) -> tuple[str, str, str]:
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / JSON_EXPORT_NAME
    local_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model, sqlite_path), encoding="utf-8")
    return local_path.as_posix(), bridge_path, wiki_path.as_posix()


def export_sqlite_governance_registry(
    *,
    sqlite_roots: Iterable[Path] = (DEFAULT_SYSTEM_KNOWLEDGE_ROOT, DEFAULT_OPENCLAW_ROOT),
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    registry_sqlite_path: Path = DEFAULT_SQLITE_PATH,
    agentic_chain_read_model_path: Path = DEFAULT_AGENTIC_CHAIN_READ_MODEL,
    agentic_chain_sqlite_path: Path = DEFAULT_AGENTIC_CHAIN_SQLITE,
    package_event_index_read_model_path: Path = DEFAULT_PACKAGE_EVENT_INDEX_READ_MODEL,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    registry_sqlite_path = _rooted(registry_sqlite_path)

    first = build_read_model(
        sqlite_roots=sqlite_roots,
        agentic_chain_read_model_path=agentic_chain_read_model_path,
        agentic_chain_sqlite_path=agentic_chain_sqlite_path,
        package_event_index_read_model_path=package_event_index_read_model_path,
        generated_at=generated_at,
    )
    write_registry_sqlite(registry_sqlite_path, first)

    final = build_read_model(
        sqlite_roots=sqlite_roots,
        agentic_chain_read_model_path=agentic_chain_read_model_path,
        agentic_chain_sqlite_path=agentic_chain_sqlite_path,
        package_event_index_read_model_path=package_event_index_read_model_path,
        extra_sqlite_paths=(registry_sqlite_path,),
        generated_at=generated_at,
    )
    write_registry_sqlite(registry_sqlite_path, final)
    local_path, bridge_path, rendered_wiki_path = _write_json_and_wiki(
        read_model=final,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
        sqlite_path=registry_sqlite_path,
    )
    return {
        "status": str(final["status"]),
        "read_model_path": local_path,
        "bridge_read_model_path": bridge_path,
        "wiki_path": rendered_wiki_path,
        "sqlite_path": registry_sqlite_path.as_posix(),
        "database_count": str(final["database_count"]),
        "protected_ledger_count": str(final["protected_ledger_count"]),
        "consolidation_candidate_count": str(final["consolidation_candidate_count"]),
        "unknown_review_count": str(final["unknown_review_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export SQLite Governance Registry V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--registry-sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--agentic-chain-read-model-path", default=str(DEFAULT_AGENTIC_CHAIN_READ_MODEL))
    parser.add_argument("--agentic-chain-sqlite-path", default=str(DEFAULT_AGENTIC_CHAIN_SQLITE))
    parser.add_argument("--package-event-index-read-model-path", default=str(DEFAULT_PACKAGE_EVENT_INDEX_READ_MODEL))
    parser.add_argument("--sqlite-root", action="append", dest="sqlite_roots")
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    sqlite_roots = tuple(Path(item) for item in args.sqlite_roots) if args.sqlite_roots else (
        DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
        DEFAULT_OPENCLAW_ROOT,
    )
    result = export_sqlite_governance_registry(
        sqlite_roots=sqlite_roots,
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        registry_sqlite_path=Path(args.registry_sqlite_path),
        agentic_chain_read_model_path=Path(args.agentic_chain_read_model_path),
        agentic_chain_sqlite_path=Path(args.agentic_chain_sqlite_path),
        package_event_index_read_model_path=Path(args.package_event_index_read_model_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == REGISTRY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
