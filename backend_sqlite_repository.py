"""Table-specific repository helpers for backend SQLite semantic data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend_sqlite_schema import sqlite_schema_table


SEMANTIC_RECORDS_TABLE_NAME = "semantic_records"
SEMANTIC_LABELS_TABLE_NAME = "semantic_labels"
SEMANTIC_RELATIONSHIPS_TABLE_NAME = "semantic_relationships"
PROVENANCE_REFS_TABLE_NAME = "provenance_refs"
VALIDATION_RECEIPTS_TABLE_NAME = "validation_receipts"
OPERATOR_PROMOTIONS_TABLE_NAME = "operator_promotions"

REPOSITORY_TABLE_PRIMARY_KEYS = {
    SEMANTIC_RECORDS_TABLE_NAME: "record_id",
    SEMANTIC_LABELS_TABLE_NAME: "label_id",
    SEMANTIC_RELATIONSHIPS_TABLE_NAME: "relationship_id",
    PROVENANCE_REFS_TABLE_NAME: "provenance_ref_id",
    VALIDATION_RECEIPTS_TABLE_NAME: "receipt_id",
    OPERATOR_PROMOTIONS_TABLE_NAME: "promotion_id",
}


@dataclass(frozen=True)
class SemanticRecord:
    """Plain semantic_records row data."""

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


@dataclass(frozen=True)
class SemanticLabel:
    """Plain semantic_labels row data."""

    label_id: str
    target_record_id: str
    label_name: str
    label_value: str
    label_basis: str
    review_status: str
    source_label_ref: str | None = None


@dataclass(frozen=True)
class SemanticRelationship:
    """Plain semantic_relationships row data."""

    relationship_id: str
    from_record_id: str
    to_record_id: str
    relationship_kind: str
    relationship_state: str
    provenance_refs: str
    freshness_refs: str
    authority_label: str
    sensitivity_label: str
    relationship_scope: str | None = None


@dataclass(frozen=True)
class ProvenanceRef:
    """Plain provenance_refs row data."""

    provenance_ref_id: str
    target_record_id: str
    source_basis: str
    source_set_ref: str
    manifest_ref: str
    bridge_ref: str
    packet_ref: str
    receipt_ref: str
    document_id: str | None = None
    section_path: str | None = None
    page_ref: str | None = None


@dataclass(frozen=True)
class ValidationReceipt:
    """Plain validation_receipts row data."""

    receipt_id: str
    validated_target: str
    validator_name: str
    validation_result: str
    failure_reasons: str
    checked_at: str
    source_basis: str
    authority_boundary: str | None = None


@dataclass(frozen=True)
class OperatorPromotion:
    """Plain operator_promotions row data.

    This stores an explicit operator decision. It does not derive accepted
    knowledge or update semantic_records by itself.
    """

    promotion_id: str
    target_record_id: str
    operator_decision: str
    receipt_ref: str
    promotion_scope: str
    promoted_by_operator: int
    complete_label_set: str
    authority_boundary: str | None = None


def semantic_record_column_names() -> tuple[str, ...]:
    """Return the stable semantic_records column order from schema metadata."""

    return table_column_names(SEMANTIC_RECORDS_TABLE_NAME)


def table_column_names(table_name: str) -> tuple[str, ...]:
    """Return the stable column order for a repository-managed table."""

    table_name = _require_repository_table_name(table_name)
    table = sqlite_schema_table(table_name)
    if table is None:
        raise RuntimeError(f"{table_name} schema table is not defined")
    return table.column_names


def write_semantic_record(
    connection: Any,
    record: SemanticRecord | Mapping[str, Any],
) -> None:
    """Insert one semantic_records row through an existing caller-owned connection."""

    payload = _table_payload(SEMANTIC_RECORDS_TABLE_NAME, record)
    _require_binary_int(payload["synthesis_not_truth"], "synthesis_not_truth")
    _require_binary_int(
        payload["accepted_knowledge_derived"],
        "accepted_knowledge_derived",
    )
    if payload["accepted_knowledge_derived"] != 0:
        raise ValueError(
            "semantic_records repository writes cannot derive accepted knowledge"
        )
    _insert_row(connection, SEMANTIC_RECORDS_TABLE_NAME, payload)


def read_semantic_record(connection: Any, record_id: str) -> dict[str, Any] | None:
    """Read one semantic_records row by explicit record_id."""

    return _read_row_by_primary_key(connection, SEMANTIC_RECORDS_TABLE_NAME, record_id)


def write_semantic_label(
    connection: Any,
    label: SemanticLabel | Mapping[str, Any],
) -> None:
    """Insert one semantic_labels row for an existing semantic record."""

    payload = _table_payload(SEMANTIC_LABELS_TABLE_NAME, label)
    _require_existing_semantic_record(connection, payload["target_record_id"])
    _insert_row(connection, SEMANTIC_LABELS_TABLE_NAME, payload)


def read_semantic_label(connection: Any, label_id: str) -> dict[str, Any] | None:
    """Read one semantic_labels row by explicit label_id."""

    return _read_row_by_primary_key(connection, SEMANTIC_LABELS_TABLE_NAME, label_id)


def read_record_labels(connection: Any, record_id: str) -> tuple[dict[str, Any], ...]:
    """Read labels for one semantic record in deterministic label_id order."""

    _require_non_empty_string(record_id, "record_id")
    return _read_rows_where(
        connection,
        SEMANTIC_LABELS_TABLE_NAME,
        "target_record_id",
        record_id,
        order_by="label_id",
    )


def write_provenance_ref(
    connection: Any,
    provenance_ref: ProvenanceRef | Mapping[str, Any],
) -> None:
    """Insert one provenance_refs row for an existing semantic record."""

    payload = _table_payload(PROVENANCE_REFS_TABLE_NAME, provenance_ref)
    _require_existing_semantic_record(connection, payload["target_record_id"])
    _insert_row(connection, PROVENANCE_REFS_TABLE_NAME, payload)


def read_provenance_ref(
    connection: Any,
    provenance_ref_id: str,
) -> dict[str, Any] | None:
    """Read one provenance_refs row by explicit provenance_ref_id."""

    return _read_row_by_primary_key(
        connection,
        PROVENANCE_REFS_TABLE_NAME,
        provenance_ref_id,
    )


def read_record_provenance_refs(
    connection: Any,
    record_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read provenance refs for one semantic record in deterministic order."""

    _require_non_empty_string(record_id, "record_id")
    return _read_rows_where(
        connection,
        PROVENANCE_REFS_TABLE_NAME,
        "target_record_id",
        record_id,
        order_by="provenance_ref_id",
    )


def write_semantic_relationship(
    connection: Any,
    relationship: SemanticRelationship | Mapping[str, Any],
) -> None:
    """Insert one semantic_relationships row between existing semantic records."""

    payload = _table_payload(SEMANTIC_RELATIONSHIPS_TABLE_NAME, relationship)
    _require_existing_semantic_record(connection, payload["from_record_id"])
    _require_existing_semantic_record(connection, payload["to_record_id"])
    _insert_row(connection, SEMANTIC_RELATIONSHIPS_TABLE_NAME, payload)


def read_semantic_relationship(
    connection: Any,
    relationship_id: str,
) -> dict[str, Any] | None:
    """Read one semantic_relationships row by explicit relationship_id."""

    return _read_row_by_primary_key(
        connection,
        SEMANTIC_RELATIONSHIPS_TABLE_NAME,
        relationship_id,
    )


def read_record_relationships(
    connection: Any,
    record_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read direct relationships touching one record in deterministic order."""

    _require_non_empty_string(record_id, "record_id")
    columns = ", ".join(table_column_names(SEMANTIC_RELATIONSHIPS_TABLE_NAME))
    rows = connection.execute(
        f"""
SELECT {columns}
FROM semantic_relationships
WHERE from_record_id = ? OR to_record_id = ?
ORDER BY relationship_id
""".strip(),
        (record_id, record_id),
    ).fetchall()
    return tuple(
        dict(zip(table_column_names(SEMANTIC_RELATIONSHIPS_TABLE_NAME), row))
        for row in rows
    )


def write_validation_receipt(
    connection: Any,
    receipt: ValidationReceipt | Mapping[str, Any],
) -> None:
    """Insert one validation_receipts row for an existing semantic record."""

    payload = _table_payload(VALIDATION_RECEIPTS_TABLE_NAME, receipt)
    _require_existing_semantic_record(connection, payload["validated_target"])
    _insert_row(connection, VALIDATION_RECEIPTS_TABLE_NAME, payload)


def read_validation_receipt(
    connection: Any,
    receipt_id: str,
) -> dict[str, Any] | None:
    """Read one validation_receipts row by explicit receipt_id."""

    return _read_row_by_primary_key(
        connection,
        VALIDATION_RECEIPTS_TABLE_NAME,
        receipt_id,
    )


def read_record_validation_receipts(
    connection: Any,
    record_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read validation receipts for one semantic record in deterministic order."""

    _require_non_empty_string(record_id, "record_id")
    return _read_rows_where(
        connection,
        VALIDATION_RECEIPTS_TABLE_NAME,
        "validated_target",
        record_id,
        order_by="receipt_id",
    )


def write_operator_promotion(
    connection: Any,
    promotion: OperatorPromotion | Mapping[str, Any],
) -> None:
    """Insert one explicit operator_promotions row for an existing semantic record."""

    payload = _table_payload(OPERATOR_PROMOTIONS_TABLE_NAME, promotion)
    _require_existing_semantic_record(connection, payload["target_record_id"])
    _require_binary_int(payload["promoted_by_operator"], "promoted_by_operator")
    _insert_row(connection, OPERATOR_PROMOTIONS_TABLE_NAME, payload)


def read_operator_promotion(
    connection: Any,
    promotion_id: str,
) -> dict[str, Any] | None:
    """Read one operator_promotions row by explicit promotion_id."""

    return _read_row_by_primary_key(
        connection,
        OPERATOR_PROMOTIONS_TABLE_NAME,
        promotion_id,
    )


def read_record_operator_promotions(
    connection: Any,
    record_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read operator promotions for one semantic record in deterministic order."""

    _require_non_empty_string(record_id, "record_id")
    return _read_rows_where(
        connection,
        OPERATOR_PROMOTIONS_TABLE_NAME,
        "target_record_id",
        record_id,
        order_by="promotion_id",
    )


def record_has_explicit_operator_promotion(connection: Any, record_id: str) -> bool:
    """Return True only when an explicit positive operator promotion exists."""

    return any(
        promotion["promoted_by_operator"] == 1
        for promotion in read_record_operator_promotions(connection, record_id)
    )


def _insert_row(connection: Any, table_name: str, payload: Mapping[str, Any]) -> None:
    table_name = _require_repository_table_name(table_name)
    columns = table_column_names(table_name)
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    connection.execute(
        f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})",
        tuple(payload[column] for column in columns),
    )


def _read_row_by_primary_key(
    connection: Any,
    table_name: str,
    primary_key_value: str,
) -> dict[str, Any] | None:
    table_name = _require_repository_table_name(table_name)
    primary_key_column = REPOSITORY_TABLE_PRIMARY_KEYS[table_name]
    _require_non_empty_string(primary_key_value, primary_key_column)
    columns = ", ".join(table_column_names(table_name))
    row = connection.execute(
        f"SELECT {columns} FROM {table_name} WHERE {primary_key_column} = ?",
        (primary_key_value,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(table_column_names(table_name), row))


def _read_rows_where(
    connection: Any,
    table_name: str,
    where_column: str,
    where_value: str,
    *,
    order_by: str,
) -> tuple[dict[str, Any], ...]:
    table_name = _require_repository_table_name(table_name)
    columns = table_column_names(table_name)
    if where_column not in columns:
        raise ValueError(f"unknown repository where column: {where_column}")
    if order_by not in columns:
        raise ValueError(f"unknown repository order column: {order_by}")
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM {table_name}
WHERE {where_column} = ?
ORDER BY {order_by}
""".strip(),
        (where_value,),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def _table_payload(
    table_name: str,
    row_data: Any,
) -> dict[str, Any]:
    table_name = _require_repository_table_name(table_name)
    payload = asdict(row_data) if hasattr(row_data, "__dataclass_fields__") else dict(row_data)
    columns = table_column_names(table_name)
    expected_columns = set(columns)
    actual_columns = set(payload)
    if actual_columns != expected_columns:
        missing = sorted(expected_columns - actual_columns)
        extra = sorted(actual_columns - expected_columns)
        raise ValueError(
            f"{table_name} payload must exactly match schema columns; "
            f"missing={missing}; extra={extra}"
        )

    primary_key_column = REPOSITORY_TABLE_PRIMARY_KEYS[table_name]
    _require_non_empty_string(payload[primary_key_column], primary_key_column)
    _validate_payload_values(table_name, payload)
    return payload


def _validate_payload_values(table_name: str, payload: Mapping[str, Any]) -> None:
    table = sqlite_schema_table(table_name)
    if table is None:
        raise RuntimeError(f"{table_name} schema table is not defined")
    for column in table.columns:
        value = payload[column.name]
        if value is None:
            if column.required:
                raise ValueError(f"{table_name}.{column.name} must not be None")
            continue
        if column.storage_type == "INTEGER":
            if not isinstance(value, int):
                raise ValueError(f"{table_name}.{column.name} must be an integer")
            continue
        if column.storage_type == "TEXT":
            if not isinstance(value, str):
                raise ValueError(f"{table_name}.{column.name} must be text")
            continue
        raise ValueError(f"{table_name}.{column.name} has unsupported storage type")


def _require_existing_semantic_record(connection: Any, record_id: str) -> None:
    _require_non_empty_string(record_id, "record_id")
    if read_semantic_record(connection, record_id) is None:
        raise ValueError(f"unknown semantic record reference: {record_id}")


def _require_repository_table_name(table_name: str) -> str:
    if table_name not in REPOSITORY_TABLE_PRIMARY_KEYS:
        raise ValueError(f"unknown backend sqlite repository table: {table_name}")
    return table_name


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_binary_int(value: Any, field_name: str) -> None:
    if value not in {0, 1} or not isinstance(value, int):
        raise ValueError(f"{field_name} must be 0 or 1")
