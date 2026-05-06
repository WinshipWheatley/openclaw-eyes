"""Small table-specific repository helpers for backend SQLite semantic records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend_sqlite_schema import sqlite_schema_table


SEMANTIC_RECORDS_TABLE_NAME = "semantic_records"


@dataclass(frozen=True)
class SemanticRecord:
    """Plain semantic_records row data.

    The first repository slice can write and read records, but it does not
    promote synthesis into accepted knowledge. Accepted-knowledge derivation
    remains a separate operator-promotion lane.
    """

    record_id: str
    entity_family: str
    knowledge_layer: str
    contract_state: str
    validator_decision: str
    synthesis_not_truth: int
    accepted_knowledge_derived: int
    provenance_refs: str
    freshness_refs: str
    confidence_label: str
    sensitivity_label: str
    authority_label: str
    review_status_label: str
    document_id: str | None = None
    parent_record_id: str | None = None
    section_path: str | None = None
    page_ref: str | None = None
    summary_level: str | None = None
    summary_text_ref: str | None = None


def semantic_record_column_names() -> tuple[str, ...]:
    """Return the stable semantic_records column order from schema metadata."""

    table = sqlite_schema_table(SEMANTIC_RECORDS_TABLE_NAME)
    if table is None:
        raise RuntimeError("semantic_records schema table is not defined")
    return table.column_names


def write_semantic_record(connection: Any, record: SemanticRecord | Mapping[str, Any]) -> None:
    """Insert one semantic_records row through an existing caller-owned connection."""

    payload = _semantic_record_payload(record)
    placeholders = ", ".join("?" for _ in semantic_record_column_names())
    columns = ", ".join(semantic_record_column_names())
    connection.execute(
        f"INSERT INTO semantic_records ({columns}) VALUES ({placeholders})",
        tuple(payload[column] for column in semantic_record_column_names()),
    )


def read_semantic_record(connection: Any, record_id: str) -> dict[str, Any] | None:
    """Read one semantic_records row by explicit record_id."""

    if not isinstance(record_id, str) or not record_id:
        raise ValueError("semantic record_id must be a non-empty string")

    columns = ", ".join(semantic_record_column_names())
    row = connection.execute(
        f"SELECT {columns} FROM semantic_records WHERE record_id = ?",
        (record_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(semantic_record_column_names(), row))


def _semantic_record_payload(record: SemanticRecord | Mapping[str, Any]) -> dict[str, Any]:
    """Return a schema-shaped payload or fail closed before SQL execution."""

    payload = asdict(record) if isinstance(record, SemanticRecord) else dict(record)
    expected_columns = set(semantic_record_column_names())
    actual_columns = set(payload)
    if actual_columns != expected_columns:
        missing = sorted(expected_columns - actual_columns)
        extra = sorted(actual_columns - expected_columns)
        raise ValueError(
            "semantic record payload must exactly match schema columns; "
            f"missing={missing}; extra={extra}"
        )
    _require_non_empty_string(payload["record_id"], "record_id")
    _require_binary_int(payload["synthesis_not_truth"], "synthesis_not_truth")
    _require_binary_int(
        payload["accepted_knowledge_derived"],
        "accepted_knowledge_derived",
    )
    if payload["accepted_knowledge_derived"] != 0:
        raise ValueError(
            "semantic_records repository writes cannot derive accepted knowledge"
        )
    for column in semantic_record_column_names():
        value = payload[column]
        if value is None:
            continue
        if not isinstance(value, (str, int)):
            raise ValueError(f"semantic record column {column} has unsupported value")
    return payload


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"semantic record {field_name} must be a non-empty string")


def _require_binary_int(value: Any, field_name: str) -> None:
    if value not in {0, 1} or not isinstance(value, int):
        raise ValueError(f"semantic record {field_name} must be 0 or 1")
