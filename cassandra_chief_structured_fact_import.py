"""Cassandra/Chief structured fact import v0.

Imports only operator-approved structured Cassandra/Chief memory categories into
Repo A SQLite as parsed evidence, not truth. Raw logs, old HITL state,
agent-presence snapshots, album progress, spreadsheet cells, bank data, and
message/correspondence bodies are outside this lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_invoice_packet import CAPITAL_HILTON_PACKET_ID
from cassandra_chief_memory_authority import (
    DEFAULT_EXPORT_ROOT,
    seed_cassandra_chief_memory_dry_run_catalog,
    stable_json,
)
from finance_invoice_evidence_packet import init_finance_invoice_evidence_packet_schema


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "cassandra_chief_structured_fact_import_v0"
JSON_EXPORT_NAME = "cassandra_chief_structured_fact_import.json"
OPERATOR_EXPORT_NAME = "cassandra_chief_structured_fact_import_OPERATOR.md"
APPROVAL_EXPORT_NAME = "cassandra_chief_memory_import_approval.json"

APPROVED_CATEGORIES = (
    "contacts/nicknames",
    "company/contact relationships",
    "email permission posture",
    "invoice facts",
    "receivable/payment tracking",
)

SOURCE_IDS = {
    "contacts/nicknames": "memsrc_contacts_nicknames",
    "company/contact relationships": "memsrc_company_contact_relationships",
    "email permission posture": "memsrc_email_permission_posture",
    "invoice facts": "memsrc_invoice_facts",
    "receivable/payment tracking": "memsrc_receivable_payment_tracking",
}

NO_AUTHORITY_FLAGS = {
    "raw_logs_imported": False,
    "old_hitl_imported": False,
    "agent_presence_imported": False,
    "album_progress_imported": False,
    "raw_messages_imported": False,
    "correspondence_bodies_imported": False,
    "calendar_bodies_imported": False,
    "spreadsheet_cells_read": False,
    "bank_data_imported": False,
    "repo_b_runtime_data_imported": False,
    "runtime_authority_changed": False,
    "send_authority_granted": False,
    "gmail_send_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "no_send_authority": True,
    "no_runtime_authority": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_label(value: object, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    cleaned = "".join(char if char.isalnum() or char in ("_", "-", ".") else "_" for char in text)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:80] or fallback


def _hash_value(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _sha256_text(text)


def _path_hash(path_ref: str) -> str:
    return _sha256_text(path_ref)


def _read_approval(path: str | Path | None) -> dict[str, Any]:
    approval_path = _repo_path(path or DEFAULT_EXPORT_ROOT / APPROVAL_EXPORT_NAME)
    if not approval_path.is_file():
        raise FileNotFoundError(f"memory import approval receipt missing: {approval_path}")
    payload = _load_json(approval_path)
    if payload.get("safe_to_import_structured_facts") is not True:
        raise ValueError("memory import approval receipt does not mark structured fact import safe")
    if payload.get("data_imported") is not False:
        raise ValueError("memory import approval receipt must have data_imported=false")
    if payload.get("runtime_authority_changed") is not False:
        raise ValueError("memory import approval receipt must have runtime_authority_changed=false")
    approved = {item.get("display_name") for item in payload.get("approved_categories", [])}
    required = {
        "contacts and nicknames",
        "company/contact relationships",
        "allowed email recipients / email permission posture",
        "invoice facts",
        "receivable/payment tracking",
    }
    if not required <= approved:
        raise ValueError("memory import approval receipt is missing approved structured categories")
    return payload


def _common_columns(
    *,
    source_id: str,
    source_ref: str,
    source_type: str,
    sensitivity_level: str,
    recommended_fate: str = "import_structured_facts_to_sqlite",
    now: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_path": source_ref,
        "source_ref": source_ref,
        "source_type": source_type,
        "source_hash": None,
        "source_hash_kind": None,
        "source_path_hash": _path_hash(source_ref),
        "sensitivity_level": sensitivity_level,
        "trust_status": "needs_operator_confirmation",
        "evidence_status": "parsed_evidence_not_truth",
        "owner_scope": "operator_local",
        "tenant_id": None,
        "no_send_authority": 1,
        "no_runtime_authority": 1,
        "approval_required": 1,
        "recommended_fate": recommended_fate,
        "created_at": now,
        "updated_at": now,
    }


def _contact_records(contact_path: Path, *, now: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not contact_path.is_file():
        return [], [], [], []
    data = _load_json(contact_path)
    if not isinstance(data, Mapping):
        return [], [], [], []
    source_ref = "repo://contact_nicknames.json"
    entities: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    channels: list[dict[str, Any]] = []
    permissions: list[dict[str, Any]] = []
    common = _common_columns(
        source_id=SOURCE_IDS["contacts/nicknames"],
        source_ref=source_ref,
        source_type="contact_nicknames_json",
        sensitivity_level="sensitive_metadata",
        now=now,
    )
    email_common = _common_columns(
        source_id=SOURCE_IDS["email permission posture"],
        source_ref=source_ref,
        source_type="contact_nicknames_json",
        sensitivity_level="sensitive_metadata",
        now=now,
    )
    for nickname, payload in sorted(data.items(), key=lambda item: str(item[0])):
        if str(nickname).startswith("_") or not isinstance(payload, Mapping):
            continue
        nickname_label = _safe_label(nickname, fallback="contact")
        entity_id = _row_id("ccmem_ent", source_ref, nickname_label)
        entities.append(
            {
                "entity_id": entity_id,
                "entity_kind": "contact_candidate",
                "display_label_redacted": f"contact_nickname:{nickname_label}",
                "entity_status": "needs_operator_confirmation",
                **common,
            }
        )
        aliases.append(
            {
                "alias_id": _row_id("ccmem_alias", entity_id, "nickname", nickname_label),
                "entity_id": entity_id,
                "alias_kind": "nickname",
                "alias_display": f"nickname:{nickname_label}",
                "alias_value_hash": _hash_value(nickname),
                **common,
            }
        )
        if payload.get("name"):
            aliases.append(
                {
                    "alias_id": _row_id("ccmem_alias", entity_id, "name", _hash_value(payload.get("name"))),
                    "entity_id": entity_id,
                    "alias_kind": "name_hash",
                    "alias_display": "name_hash_present",
                    "alias_value_hash": _hash_value(payload.get("name")),
                    **common,
                }
            )
        for item in payload.get("aliases") or []:
            if item:
                aliases.append(
                    {
                        "alias_id": _row_id("ccmem_alias", entity_id, "alias", _hash_value(item)),
                        "entity_id": entity_id,
                        "alias_kind": "alias_hash",
                        "alias_display": "alias_hash_present",
                        "alias_value_hash": _hash_value(item),
                        **common,
                    }
                )
        for key, channel_kind in (
            ("pinned_email", "email"),
            ("pinned_phone", "phone"),
            ("pinned_whatsapp", "whatsapp"),
            ("telegram_chat_id", "telegram_chat_id"),
        ):
            value_hash = _hash_value(payload.get(key))
            if not value_hash:
                continue
            channels.append(
                {
                    "channel_id": _row_id("ccmem_channel", entity_id, channel_kind, value_hash),
                    "entity_ref": entity_id,
                    "channel_kind": channel_kind,
                    "channel_display_redacted": f"{channel_kind}_hash_present",
                    "channel_value_hash": value_hash,
                    "channel_verified": 0,
                    **common,
                }
            )
            if channel_kind == "email":
                permissions.append(
                    {
                        "permission_id": _row_id("ccmem_emailperm", entity_id, value_hash),
                        "entity_ref": entity_id,
                        "permission_kind": "email_candidate_hash",
                        "draft_allowed": 0,
                        "send_allowed": 0,
                        "guardian_required": 1,
                        "approval_link_ref": None,
                        **email_common,
                    }
                )
    return entities, aliases, channels, permissions


def _dict_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _finance_contact_records(conn: sqlite3.Connection, *, now: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not _table_exists(conn, "capital_hilton_contact_candidates"):
        return [], [], [], []
    rows = _dict_rows(
        conn,
        """
SELECT contact_candidate_id, organization, contact_name, role, email, allowed_use,
       confidence, source_basis
FROM capital_hilton_contact_candidates
WHERE packet_id = ?
ORDER BY contact_candidate_id
""".strip(),
        (CAPITAL_HILTON_PACKET_ID,),
    )
    source_ref = "sqlite://capital_hilton_contact_candidates"
    contact_common = _common_columns(
        source_id=SOURCE_IDS["contacts/nicknames"],
        source_ref=source_ref,
        source_type="governed_finance_contact_candidate",
        sensitivity_level="sensitive_metadata",
        now=now,
    )
    relation_common = _common_columns(
        source_id=SOURCE_IDS["company/contact relationships"],
        source_ref=source_ref,
        source_type="governed_finance_contact_candidate",
        sensitivity_level="sensitive_metadata",
        now=now,
    )
    email_common = _common_columns(
        source_id=SOURCE_IDS["email permission posture"],
        source_ref=source_ref,
        source_type="governed_finance_contact_candidate",
        sensitivity_level="sensitive_metadata",
        now=now,
    )
    entities: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    permissions: list[dict[str, Any]] = []
    for row in rows:
        contact_hash = _hash_value(row.get("contact_name") or row.get("contact_candidate_id")) or "sha256:unknown"
        org_hash = _hash_value(row.get("organization") or "organization") or "sha256:organization"
        contact_entity = _row_id("ccmem_ent", source_ref, "contact", contact_hash)
        org_entity = _row_id("ccmem_ent", source_ref, "org", org_hash)
        entities.extend(
            [
                {
                    "entity_id": contact_entity,
                    "entity_kind": "business_contact_candidate",
                    "display_label_redacted": f"business_contact:{contact_hash[:18]}",
                    "entity_status": "needs_operator_confirmation",
                    **contact_common,
                },
                {
                    "entity_id": org_entity,
                    "entity_kind": "organization_candidate",
                    "display_label_redacted": f"organization:{_safe_label(row.get('organization'), fallback='business')}",
                    "entity_status": "needs_operator_confirmation",
                    **contact_common,
                },
            ]
        )
        aliases.append(
            {
                "alias_id": _row_id("ccmem_alias", contact_entity, "contact_name", contact_hash),
                "entity_id": contact_entity,
                "alias_kind": "contact_name_hash",
                "alias_display": "contact_name_hash_present",
                "alias_value_hash": contact_hash,
                **contact_common,
            }
        )
        relationships.append(
            {
                "relationship_id": _row_id("ccmem_rel", contact_entity, org_entity, row.get("role")),
                "from_entity_ref": contact_entity,
                "to_entity_ref": org_entity,
                "relationship_kind": _safe_label(row.get("role"), fallback="business_contact"),
                "relationship_status": "needs_operator_confirmation",
                **relation_common,
            }
        )
        email_hash = _hash_value(row.get("email"))
        if email_hash:
            permissions.append(
                {
                    "permission_id": _row_id("ccmem_emailperm", contact_entity, email_hash, row.get("allowed_use")),
                    "entity_ref": contact_entity,
                    "permission_kind": _safe_label(row.get("allowed_use"), fallback="email_candidate"),
                    "draft_allowed": 0,
                    "send_allowed": 0,
                    "guardian_required": 1,
                    "approval_link_ref": None,
                    **email_common,
                }
            )
    return entities, aliases, relationships, permissions


def _finance_invoice_records(conn: sqlite3.Connection, *, now: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    common = _common_columns(
        source_id=SOURCE_IDS["invoice facts"],
        source_ref="sqlite://finance_invoice_packet_facts",
        source_type="governed_finance_invoice_packet",
        sensitivity_level="finance_sensitive_metadata",
        now=now,
    )
    if _table_exists(conn, "capital_hilton_invoice_fact_updates"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_update_id, field_name, value_text, source_kind, source_ref,
       confidence, truth_status
FROM capital_hilton_invoice_fact_updates
WHERE packet_id = ?
ORDER BY field_name, fact_update_id
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            field = _safe_label(row.get("field_name"), fallback="invoice_fact")
            records.append(
                {
                    "finance_link_id": _row_id("ccmem_fin", "capital_hilton_fact", row.get("fact_update_id")),
                    "finance_link_kind": f"invoice_fact:{field}",
                    "finance_surface": "capital_hilton_invoice_fact_updates",
                    "finance_record_ref": f"{field}:{_hash_value(row.get('value_text'))}",
                    "fact_authority_status": "parsed_evidence_not_truth_needs_operator_confirmation",
                    **common,
                }
            )
    if _table_exists(conn, "finance_invoice_packet_facts"):
        for row in _dict_rows(
            conn,
            """
SELECT fact_id, label, value_text, fact_kind, source_ref, confidence, truth_status
FROM finance_invoice_packet_facts
WHERE packet_id = ?
ORDER BY label, fact_id
""".strip(),
            (CAPITAL_HILTON_PACKET_ID,),
        ):
            label = _safe_label(row.get("label"), fallback="invoice_fact")
            records.append(
                {
                    "finance_link_id": _row_id("ccmem_fin", "finance_packet_fact", row.get("fact_id")),
                    "finance_link_kind": f"invoice_packet_fact:{label}",
                    "finance_surface": "finance_invoice_packet_facts",
                    "finance_record_ref": f"{label}:{_hash_value(row.get('value_text'))}",
                    "fact_authority_status": "parsed_evidence_not_truth_needs_operator_confirmation",
                    **common,
                }
            )
    return records


def _finance_state_receivable_records(finance_state_path: Path, *, now: str) -> list[dict[str, Any]]:
    if not finance_state_path.is_file():
        return []
    data = _load_json(finance_state_path)
    if not isinstance(data, Mapping):
        return []
    accounts = data.get("accounts")
    if not isinstance(accounts, Mapping):
        return []
    common = _common_columns(
        source_id=SOURCE_IDS["receivable/payment tracking"],
        source_ref="repo://finance_state.json",
        source_type="finance_state_json_account_metadata",
        sensitivity_level="finance_sensitive_metadata",
        now=now,
    )
    records = []
    for account_id, account in sorted(accounts.items(), key=lambda item: str(item[0])):
        if not isinstance(account, Mapping):
            continue
        account_hash = _hash_value(account_id) or "sha256:unknown"
        present_fields = [
            key
            for key in ("status", "workflow_summary", "payment_summary", "invoice_summary", "next_actions")
            if account.get(key)
        ]
        records.append(
            {
                "finance_link_id": _row_id("ccmem_fin", "finance_state", account_hash),
                "finance_link_kind": "receivable_payment_tracking_metadata",
                "finance_surface": "finance_state_json",
                "finance_record_ref": f"finance_state_account:{account_hash};fields={','.join(present_fields)}",
                "fact_authority_status": "parsed_evidence_not_truth_needs_operator_confirmation",
                **common,
            }
        )
    return records


def _sqlite_receivable_records(conn: sqlite3.Connection, *, now: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "finance_invoice_packets"):
        return []
    common = _common_columns(
        source_id=SOURCE_IDS["receivable/payment tracking"],
        source_ref="sqlite://finance_invoice_packets",
        source_type="governed_finance_packet_metadata",
        sensitivity_level="finance_sensitive_metadata",
        now=now,
    )
    records = []
    for row in _dict_rows(
        conn,
        """
SELECT packet_id, title, subject_entity, workflow_kind, status, next_safe_move
FROM finance_invoice_packets
ORDER BY packet_id
""".strip(),
    ):
        records.append(
            {
                "finance_link_id": _row_id("ccmem_fin", "finance_packet_status", row.get("packet_id")),
                "finance_link_kind": f"receivable_packet_status:{_safe_label(row.get('workflow_kind'), fallback='finance')}",
                "finance_surface": "finance_invoice_packets",
                "finance_record_ref": f"packet:{_hash_value(row.get('packet_id'))};status:{_safe_label(row.get('status'), fallback='unknown')}",
                "fact_authority_status": "parsed_evidence_not_truth_needs_operator_confirmation",
                **common,
            }
        )
    return records


def collect_structured_fact_records(
    *,
    db_path: str | Path | None = None,
    contact_nicknames_path: str | Path = "contact_nicknames.json",
    finance_state_path: str | Path = "finance_state.json",
    generated_at: str | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now()
    finance_db = init_finance_invoice_evidence_packet_schema(db_path or DEFAULT_DB_PATH)
    contact_path = _repo_path(contact_nicknames_path)
    finance_path = _repo_path(finance_state_path)
    contact_entities, contact_aliases, contact_channels, contact_permissions = _contact_records(
        contact_path,
        now=now,
    )
    conn = sqlite3.connect(finance_db)
    try:
        finance_contact_entities, finance_contact_aliases, relationships, finance_permissions = _finance_contact_records(
            conn,
            now=now,
        )
        invoice_links = _finance_invoice_records(conn, now=now)
        sqlite_receivables = _sqlite_receivable_records(conn, now=now)
    finally:
        conn.close()
    finance_state_receivables = _finance_state_receivable_records(finance_path, now=now)

    entities = contact_entities + finance_contact_entities
    aliases = contact_aliases + finance_contact_aliases
    channels = contact_channels
    permissions = contact_permissions + finance_permissions
    finance_links = invoice_links + finance_state_receivables + sqlite_receivables
    records_by_category = {
        "contacts/nicknames": len(entities) + len(aliases) + len(channels),
        "company/contact relationships": len(relationships),
        "email permission posture": len(permissions),
        "invoice facts": len(invoice_links),
        "receivable/payment tracking": len(finance_state_receivables) + len(sqlite_receivables),
    }
    skipped = [
        {
            "category": category,
            "reason": "No safe approved structured records were available from the bounded source candidates.",
        }
        for category, count in records_by_category.items()
        if count == 0
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "db_path": finance_db,
        "contact_nicknames_present": contact_path.is_file(),
        "finance_state_present": finance_path.is_file(),
        "entities": entities,
        "aliases": aliases,
        "channels": channels,
        "relationships": relationships,
        "permissions": permissions,
        "finance_links": finance_links,
        "records_by_category": records_by_category,
        "categories_importable": [category for category, count in records_by_category.items() if count > 0],
        "categories_skipped": skipped,
        **NO_AUTHORITY_FLAGS,
    }


def _insert_many(conn: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    keys = list(rows[0].keys())
    placeholders = ", ".join(":" + key for key in keys)
    columns = ", ".join(keys)
    assignments = ", ".join(f"{key}=excluded.{key}" for key in keys if not key.endswith("_id"))
    conn.executemany(
        f"""
INSERT INTO {table_name} ({columns})
VALUES ({placeholders})
ON CONFLICT({keys[0]}) DO UPDATE SET {assignments}
""".strip(),
        rows,
    )
    return len(rows)


def apply_structured_fact_import(
    *,
    db_path: str | Path | None = None,
    contact_nicknames_path: str | Path = "contact_nicknames.json",
    finance_state_path: str | Path = "finance_state.json",
    approval_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    _read_approval(approval_path)
    records = collect_structured_fact_records(
        db_path=db_path,
        contact_nicknames_path=contact_nicknames_path,
        finance_state_path=finance_state_path,
        generated_at=generated_at,
    )
    seed_cassandra_chief_memory_dry_run_catalog(
        db_path=records["db_path"],
        generated_at=records["generated_at"],
    )
    conn = sqlite3.connect(records["db_path"])
    try:
        inserted = {
            "cassandra_chief_memory_entities": _insert_many(conn, "cassandra_chief_memory_entities", records["entities"]),
            "cassandra_chief_memory_entity_aliases": _insert_many(conn, "cassandra_chief_memory_entity_aliases", records["aliases"]),
            "cassandra_chief_memory_contact_channels": _insert_many(conn, "cassandra_chief_memory_contact_channels", records["channels"]),
            "cassandra_chief_memory_entity_relationships": _insert_many(conn, "cassandra_chief_memory_entity_relationships", records["relationships"]),
            "cassandra_chief_memory_email_permissions": _insert_many(conn, "cassandra_chief_memory_email_permissions", records["permissions"]),
            "cassandra_chief_memory_finance_source_links": _insert_many(conn, "cassandra_chief_memory_finance_source_links", records["finance_links"]),
        }
        conn.commit()
    finally:
        conn.close()

    payload = build_structured_fact_import_read_model(
        records=records,
        inserted=inserted,
    )
    export_structured_fact_import_read_model(payload, export_root=export_root)
    return payload


def build_structured_fact_import_read_model(
    *,
    records: dict[str, Any],
    inserted: dict[str, int] | None = None,
) -> dict[str, Any]:
    inserted = inserted or {}
    records_imported_count = sum(inserted.values()) if inserted else sum(records["records_by_category"].values())
    categories_imported = [
        {
            "category": category,
            "records_imported": count,
            "evidence_status": "parsed_evidence_not_truth",
            "trust_status": "needs_operator_confirmation",
            "no_send_authority": True,
            "no_runtime_authority": True,
        }
        for category, count in records["records_by_category"].items()
        if count > 0
    ]
    safe_record_samples = []
    for table_name, row_list_name in (
        ("cassandra_chief_memory_entities", "entities"),
        ("cassandra_chief_memory_entity_aliases", "aliases"),
        ("cassandra_chief_memory_contact_channels", "channels"),
        ("cassandra_chief_memory_entity_relationships", "relationships"),
        ("cassandra_chief_memory_email_permissions", "permissions"),
        ("cassandra_chief_memory_finance_source_links", "finance_links"),
    ):
        for row in records[row_list_name][:5]:
            safe_record_samples.append(
                {
                    "table_name": table_name,
                    "record_id": next(iter(row.values())),
                    "source_id": row["source_id"],
                    "source_type": row["source_type"],
                    "evidence_status": row["evidence_status"],
                    "trust_status": row["trust_status"],
                    "no_send_authority": bool(row["no_send_authority"]),
                    "no_runtime_authority": bool(row["no_runtime_authority"]),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": records["generated_at"],
        "db_path": records["db_path"],
        "data_imported": True,
        "import_mode": "approved_structured_facts_only",
        "records_imported_count": records_imported_count,
        "records_needing_operator_confirmation": records_imported_count,
        "categories_imported": categories_imported,
        "categories_skipped": records["categories_skipped"],
        "inserted_tables": inserted,
        "approved_categories_only": list(APPROVED_CATEGORIES),
        "raw_logs_imported": False,
        "old_hitl_imported": False,
        "agent_presence_imported": False,
        "album_progress_imported": False,
        "raw_messages_imported": False,
        "correspondence_bodies_imported": False,
        "calendar_bodies_imported": False,
        "spreadsheet_cells_read": False,
        "bank_data_imported": False,
        "repo_b_runtime_data_imported": False,
        "runtime_authority_changed": False,
        "send_authority_granted": False,
        "source_access": {
            "contact_nicknames_json": "approved_structured_json_read" if records["contact_nicknames_present"] else "missing_skipped",
            "finance_state_json": "approved_structured_json_read" if records["finance_state_present"] else "missing_skipped",
            "finance_sqlite_surfaces": "approved_governed_sqlite_rows_only",
            "spreadsheet_cells": "not_read",
            "old_hitl_json_jsonl": "not_read",
            "agent_presence_snapshots": "not_read",
        },
        "safe_record_samples": safe_record_samples[:20],
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        "next_safe_lane": "Cassandra/Clara SQLite Fact Packet Refresh v0",
        **NO_AUTHORITY_FLAGS,
    }


def format_structured_fact_import_read_model(payload: dict[str, Any]) -> str:
    lines = [
        "# Cassandra/Chief Structured Fact Import v0",
        "",
        "Plain-English status:",
        "- Imported only the operator-approved structured categories.",
        "- Imported rows are parsed evidence, not truth.",
        "- Every imported row needs operator confirmation before use.",
        "- No send or runtime authority was granted.",
        "",
        "## Categories Imported",
    ]
    if not payload["categories_imported"]:
        lines.append("- None.")
    else:
        for item in payload["categories_imported"]:
            lines.append(
                f"- {item['category']}: {item['records_imported']} rows; "
                "parsed_evidence_not_truth; needs_operator_confirmation."
            )
    lines.append("")
    lines.append("## Categories Skipped")
    if not payload["categories_skipped"]:
        lines.append("- None.")
    else:
        for item in payload["categories_skipped"]:
            lines.append(f"- {item['category']}: {item['reason']}")
    lines.extend(
        [
            "",
            "## Boundaries Proven",
            f"- Raw logs imported: `{str(payload['raw_logs_imported']).lower()}`",
            f"- Old HITL imported: `{str(payload['old_hitl_imported']).lower()}`",
            f"- Agent presence imported: `{str(payload['agent_presence_imported']).lower()}`",
            f"- Spreadsheet cells read: `{str(payload['spreadsheet_cells_read']).lower()}`",
            f"- Send authority granted: `{str(payload['send_authority_granted']).lower()}`",
            f"- Runtime authority changed: `{str(payload['runtime_authority_changed']).lower()}`",
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_lane']}.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_structured_fact_import_read_model(
    payload: dict[str, Any],
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_structured_fact_import_read_model(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "records_imported_count": payload["records_imported_count"],
        "categories_imported": [item["category"] for item in payload["categories_imported"]],
        **NO_AUTHORITY_FLAGS,
    }


def dry_run_structured_fact_import(
    *,
    db_path: str | Path | None = None,
    contact_nicknames_path: str | Path = "contact_nicknames.json",
    finance_state_path: str | Path = "finance_state.json",
    approval_path: str | Path | None = None,
) -> dict[str, Any]:
    _read_approval(approval_path)
    records = collect_structured_fact_records(
        db_path=db_path,
        contact_nicknames_path=contact_nicknames_path,
        finance_state_path=finance_state_path,
    )
    counts = Counter()
    counts.update(records["records_by_category"])
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "dry_run",
        "would_import_records_count": sum(counts.values()),
        "would_import_categories": [category for category, count in records["records_by_category"].items() if count > 0],
        "categories_skipped": records["categories_skipped"],
        "data_imported": False,
        "runtime_authority_changed": False,
        **NO_AUTHORITY_FLAGS,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import approved Cassandra/Chief structured facts.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inspect approved structured source counts without writing SQLite rows.")
    mode.add_argument("--apply-approved", action="store_true", help="Apply the approved structured fact import and export read-models.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--contact-nicknames", default="contact_nicknames.json")
    parser.add_argument("--finance-state", default="finance_state.json")
    parser.add_argument("--approval", default=None)
    parser.add_argument("--export-root", default="generated/read_models")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(
            stable_json(
                dry_run_structured_fact_import(
                    db_path=args.db_path,
                    contact_nicknames_path=args.contact_nicknames,
                    finance_state_path=args.finance_state,
                    approval_path=args.approval,
                )
            ),
            end="",
        )
        return 0
    payload = apply_structured_fact_import(
        db_path=args.db_path,
        contact_nicknames_path=args.contact_nicknames,
        finance_state_path=args.finance_state,
        approval_path=args.approval,
        export_root=args.export_root,
    )
    print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
