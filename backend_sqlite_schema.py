"""Inert SQLite schema-definition contract for backend physical tables.

This module defines table metadata and SQL DDL text as constants only. It does
not import sqlite3, open database connections, execute SQL, persist data, read
or write runtime files, ingest, extract, index, embed, call providers, start
services, invoke MCPs, or touch app behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend_data_contract import (
    REQUIRED_SQLITE_TABLE_CONCEPTS,
    SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    required_sqlite_table_concept_fields,
    sqlite_table_concept,
    validate_sqlite_table_concept_definition,
)


@dataclass(frozen=True)
class ColumnDefinition:
    """Static column metadata for one inert table definition."""

    name: str
    storage_type: str
    conceptual_field: str
    required: bool = True
    purpose: str = ""


@dataclass(frozen=True)
class TableDefinition:
    """Static table metadata plus inert SQL definition text."""

    table_name: str
    related_schema_contract_surface: str
    columns: tuple[ColumnDefinition, ...]
    create_table_sql: str
    retrieval_structure_fields: frozenset[str]
    forbidden_implementation_behavior: tuple[str, ...] = (
        SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR
    )
    can_directly_imply_accepted_truth: bool = False

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    @property
    def conceptual_fields(self) -> frozenset[str]:
        return frozenset(column.conceptual_field for column in self.columns)


SCHEMA_VERSION = "backend-sqlite-schema-definition-v1"

RETRIEVAL_STRUCTURE_FIELDS = frozenset(
    {
        "document_id",
        "parent_record_id",
        "section_path",
        "page_ref",
        "summary_level",
        "summary_text_ref",
        "provenance_ref_id",
        "relationship_id",
        "freshness_label",
        "confidence_label",
        "authority_label",
        "sensitivity_label",
        "review_status_label",
        "promotion_id",
    }
)

SEMANTIC_RECORDS_COLUMNS = (
    ColumnDefinition("record_id", "TEXT", "record_id"),
    ColumnDefinition("entity_family", "TEXT", "entity_family"),
    ColumnDefinition("knowledge_layer", "TEXT", "knowledge_layer"),
    ColumnDefinition("contract_state", "TEXT", "contract_state"),
    ColumnDefinition("validator_decision", "TEXT", "validator_decision"),
    ColumnDefinition("synthesis_not_truth", "INTEGER", "synthesis_not_truth"),
    ColumnDefinition(
        "accepted_knowledge_derived",
        "INTEGER",
        "accepted_knowledge_derived",
        purpose="Derived from labels, receipt, and operator promotion only.",
    ),
    ColumnDefinition("provenance_refs", "TEXT", "provenance_refs"),
    ColumnDefinition("freshness_refs", "TEXT", "freshness_refs"),
    ColumnDefinition("confidence_label", "TEXT", "confidence_label"),
    ColumnDefinition("sensitivity_label", "TEXT", "sensitivity_label"),
    ColumnDefinition("authority_label", "TEXT", "authority_label"),
    ColumnDefinition("review_status_label", "TEXT", "review_status_label"),
    ColumnDefinition("document_id", "TEXT", "document_hierarchy", required=False),
    ColumnDefinition("parent_record_id", "TEXT", "document_hierarchy", required=False),
    ColumnDefinition("section_path", "TEXT", "section_page_reference", required=False),
    ColumnDefinition("page_ref", "TEXT", "section_page_reference", required=False),
    ColumnDefinition("summary_level", "TEXT", "multilevel_summary", required=False),
    ColumnDefinition("summary_text_ref", "TEXT", "multilevel_summary", required=False),
)

SEMANTIC_LABELS_COLUMNS = (
    ColumnDefinition("label_id", "TEXT", "label_id"),
    ColumnDefinition("target_record_id", "TEXT", "target_record_id"),
    ColumnDefinition("label_name", "TEXT", "label_name"),
    ColumnDefinition("label_value", "TEXT", "label_value"),
    ColumnDefinition("label_basis", "TEXT", "label_basis"),
    ColumnDefinition("review_status", "TEXT", "review_status"),
    ColumnDefinition("source_label_ref", "TEXT", "provenance_refs", required=False),
)

SEMANTIC_RELATIONSHIPS_COLUMNS = (
    ColumnDefinition("relationship_id", "TEXT", "relationship_id"),
    ColumnDefinition("from_record_id", "TEXT", "from_record_id"),
    ColumnDefinition("to_record_id", "TEXT", "to_record_id"),
    ColumnDefinition("relationship_kind", "TEXT", "relationship_kind"),
    ColumnDefinition("relationship_state", "TEXT", "relationship_state"),
    ColumnDefinition("provenance_refs", "TEXT", "provenance_refs"),
    ColumnDefinition("freshness_refs", "TEXT", "freshness_refs"),
    ColumnDefinition("authority_label", "TEXT", "authority_label"),
    ColumnDefinition("sensitivity_label", "TEXT", "sensitivity_label"),
    ColumnDefinition("relationship_scope", "TEXT", "relationship_edges", required=False),
)

PROVENANCE_REFS_COLUMNS = (
    ColumnDefinition("provenance_ref_id", "TEXT", "provenance_ref_id"),
    ColumnDefinition("target_record_id", "TEXT", "target_record_id"),
    ColumnDefinition("source_basis", "TEXT", "source_basis"),
    ColumnDefinition("source_set_ref", "TEXT", "source_set_ref"),
    ColumnDefinition("manifest_ref", "TEXT", "manifest_ref"),
    ColumnDefinition("bridge_ref", "TEXT", "bridge_ref"),
    ColumnDefinition("packet_ref", "TEXT", "packet_ref"),
    ColumnDefinition("receipt_ref", "TEXT", "receipt_ref"),
    ColumnDefinition("document_id", "TEXT", "document_hierarchy", required=False),
    ColumnDefinition("section_path", "TEXT", "section_page_reference", required=False),
    ColumnDefinition("page_ref", "TEXT", "section_page_reference", required=False),
)

VALIDATION_RECEIPTS_COLUMNS = (
    ColumnDefinition("receipt_id", "TEXT", "receipt_id"),
    ColumnDefinition("validated_target", "TEXT", "validated_target"),
    ColumnDefinition("validator_name", "TEXT", "validator_name"),
    ColumnDefinition("validation_result", "TEXT", "validation_result"),
    ColumnDefinition("failure_reasons", "TEXT", "failure_reasons"),
    ColumnDefinition("checked_at", "TEXT", "checked_at"),
    ColumnDefinition("source_basis", "TEXT", "source_basis"),
    ColumnDefinition("authority_boundary", "TEXT", "authority_label", required=False),
)

OPERATOR_PROMOTIONS_COLUMNS = (
    ColumnDefinition("promotion_id", "TEXT", "promotion_id"),
    ColumnDefinition("target_record_id", "TEXT", "target_record_id"),
    ColumnDefinition("operator_decision", "TEXT", "operator_decision"),
    ColumnDefinition("receipt_ref", "TEXT", "receipt_ref"),
    ColumnDefinition("promotion_scope", "TEXT", "promotion_scope"),
    ColumnDefinition("promoted_by_operator", "INTEGER", "promoted_by_operator"),
    ColumnDefinition("complete_label_set", "TEXT", "complete_label_set"),
    ColumnDefinition("authority_boundary", "TEXT", "authority_label", required=False),
)

CONTEXT_FILTER_RECEIPTS_COLUMNS = (
    ColumnDefinition(
        "context_filter_receipt_id",
        "TEXT",
        "context_filter_receipt_id",
    ),
    ColumnDefinition("context_package_ref", "TEXT", "context_package_ref"),
    ColumnDefinition("filter_scope", "TEXT", "filter_scope"),
    ColumnDefinition("checked_inputs", "TEXT", "checked_inputs"),
    ColumnDefinition("withheld_surfaces", "TEXT", "withheld_surfaces"),
    ColumnDefinition("filter_outcome", "TEXT", "filter_outcome"),
    ColumnDefinition("finding_summary", "TEXT", "finding_summary"),
    ColumnDefinition("review_route", "TEXT", "review_route"),
    ColumnDefinition("authority_boundary", "TEXT", "authority_label", required=False),
)

SCHEMA_VERSIONS_COLUMNS = (
    ColumnDefinition(
        "schema_version",
        "TEXT",
        "schema_version",
        purpose="Matches the static SCHEMA_VERSION identity.",
    ),
    ColumnDefinition(
        "schema_identity",
        "TEXT",
        "schema_identity",
        purpose="Stable namespace for the backend SQLite schema surface.",
    ),
    ColumnDefinition(
        "applied_at",
        "TEXT",
        "applied_at",
        required=False,
        purpose="Reserved for future runtime version checks.",
    ),
    ColumnDefinition(
        "source_commit",
        "TEXT",
        "source_commit",
        required=False,
        purpose="Reserved for future provenance of the applied schema source.",
    ),
    ColumnDefinition(
        "migration_state",
        "TEXT",
        "migration_state",
        purpose="Static policy state only; no migration runner is authorized.",
    ),
    ColumnDefinition(
        "notes",
        "TEXT",
        "notes",
        required=False,
        purpose="Reserved for future schema-control notes.",
    ),
)

SQLITE_SCHEMA_TABLES = (
    TableDefinition(
        table_name="semantic_records",
        related_schema_contract_surface="semantic_record",
        columns=SEMANTIC_RECORDS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in SEMANTIC_RECORDS_COLUMNS),
        create_table_sql="""
CREATE TABLE semantic_records (
  record_id TEXT PRIMARY KEY,
  entity_family TEXT NOT NULL,
  knowledge_layer TEXT NOT NULL,
  contract_state TEXT NOT NULL,
  validator_decision TEXT NOT NULL,
  synthesis_not_truth INTEGER NOT NULL,
  accepted_knowledge_derived INTEGER NOT NULL,
  provenance_refs TEXT NOT NULL,
  freshness_refs TEXT NOT NULL,
  confidence_label TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  authority_label TEXT NOT NULL,
  review_status_label TEXT NOT NULL,
  document_id TEXT,
  parent_record_id TEXT,
  section_path TEXT,
  page_ref TEXT,
  summary_level TEXT,
  summary_text_ref TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="semantic_labels",
        related_schema_contract_surface="semantic_label",
        columns=SEMANTIC_LABELS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in SEMANTIC_LABELS_COLUMNS),
        create_table_sql="""
CREATE TABLE semantic_labels (
  label_id TEXT PRIMARY KEY,
  target_record_id TEXT NOT NULL,
  label_name TEXT NOT NULL,
  label_value TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  review_status TEXT NOT NULL,
  source_label_ref TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="semantic_relationships",
        related_schema_contract_surface="semantic_relationship",
        columns=SEMANTIC_RELATIONSHIPS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in SEMANTIC_RELATIONSHIPS_COLUMNS),
        create_table_sql="""
CREATE TABLE semantic_relationships (
  relationship_id TEXT PRIMARY KEY,
  from_record_id TEXT NOT NULL,
  to_record_id TEXT NOT NULL,
  relationship_kind TEXT NOT NULL,
  relationship_state TEXT NOT NULL,
  provenance_refs TEXT NOT NULL,
  freshness_refs TEXT NOT NULL,
  authority_label TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  relationship_scope TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="provenance_refs",
        related_schema_contract_surface="provenance_ref",
        columns=PROVENANCE_REFS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in PROVENANCE_REFS_COLUMNS),
        create_table_sql="""
CREATE TABLE provenance_refs (
  provenance_ref_id TEXT PRIMARY KEY,
  target_record_id TEXT NOT NULL,
  source_basis TEXT NOT NULL,
  source_set_ref TEXT NOT NULL,
  manifest_ref TEXT NOT NULL,
  bridge_ref TEXT NOT NULL,
  packet_ref TEXT NOT NULL,
  receipt_ref TEXT NOT NULL,
  document_id TEXT,
  section_path TEXT,
  page_ref TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="validation_receipts",
        related_schema_contract_surface="validation_receipt",
        columns=VALIDATION_RECEIPTS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in VALIDATION_RECEIPTS_COLUMNS),
        create_table_sql="""
CREATE TABLE validation_receipts (
  receipt_id TEXT PRIMARY KEY,
  validated_target TEXT NOT NULL,
  validator_name TEXT NOT NULL,
  validation_result TEXT NOT NULL,
  failure_reasons TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  source_basis TEXT NOT NULL,
  authority_boundary TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="operator_promotions",
        related_schema_contract_surface="operator_promotion",
        columns=OPERATOR_PROMOTIONS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in OPERATOR_PROMOTIONS_COLUMNS),
        create_table_sql="""
CREATE TABLE operator_promotions (
  promotion_id TEXT PRIMARY KEY,
  target_record_id TEXT NOT NULL,
  operator_decision TEXT NOT NULL,
  receipt_ref TEXT NOT NULL,
  promotion_scope TEXT NOT NULL,
  promoted_by_operator INTEGER NOT NULL,
  complete_label_set TEXT NOT NULL,
  authority_boundary TEXT
);
""".strip(),
    ),
    TableDefinition(
        table_name="context_filter_receipts",
        related_schema_contract_surface="context_filter_receipt",
        columns=CONTEXT_FILTER_RECEIPTS_COLUMNS,
        retrieval_structure_fields=RETRIEVAL_STRUCTURE_FIELDS
        & frozenset(column.name for column in CONTEXT_FILTER_RECEIPTS_COLUMNS),
        create_table_sql="""
CREATE TABLE context_filter_receipts (
  context_filter_receipt_id TEXT PRIMARY KEY,
  context_package_ref TEXT NOT NULL,
  filter_scope TEXT NOT NULL,
  checked_inputs TEXT NOT NULL,
  withheld_surfaces TEXT NOT NULL,
  filter_outcome TEXT NOT NULL,
  finding_summary TEXT NOT NULL,
  review_route TEXT NOT NULL,
  authority_boundary TEXT
);
""".strip(),
    ),
)

SQLITE_SCHEMA_CONTROL_TABLES = (
    TableDefinition(
        table_name="schema_versions",
        related_schema_contract_surface="schema_control_metadata",
        columns=SCHEMA_VERSIONS_COLUMNS,
        retrieval_structure_fields=frozenset(),
        forbidden_implementation_behavior=(
            SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
            "no migration runner",
            "no file-backed database",
            "no persistence",
            "no runtime migration behavior",
        ),
        create_table_sql="""
CREATE TABLE schema_versions (
  schema_version TEXT PRIMARY KEY,
  schema_identity TEXT NOT NULL,
  applied_at TEXT,
  source_commit TEXT,
  migration_state TEXT NOT NULL,
  notes TEXT
);
""".strip(),
    ),
)

SQLITE_SCHEMA_TABLES_BY_NAME = {
    table.table_name: table for table in SQLITE_SCHEMA_TABLES
}
SQLITE_SCHEMA_CONTROL_TABLES_BY_NAME = {
    table.table_name: table for table in SQLITE_SCHEMA_CONTROL_TABLES
}
SQLITE_SCHEMA_TABLE_NAMES = tuple(table.table_name for table in SQLITE_SCHEMA_TABLES)
SQLITE_SCHEMA_CONTROL_TABLE_NAMES = tuple(
    table.table_name for table in SQLITE_SCHEMA_CONTROL_TABLES
)
SQLITE_PHYSICAL_SCHEMA_TABLES = SQLITE_SCHEMA_TABLES + SQLITE_SCHEMA_CONTROL_TABLES
SQLITE_PHYSICAL_SCHEMA_TABLES_BY_NAME = {
    table.table_name: table for table in SQLITE_PHYSICAL_SCHEMA_TABLES
}
SQLITE_PHYSICAL_SCHEMA_TABLE_NAMES = tuple(
    table.table_name for table in SQLITE_PHYSICAL_SCHEMA_TABLES
)
SQLITE_CREATE_TABLE_SQL = tuple(table.create_table_sql for table in SQLITE_SCHEMA_TABLES)
SQLITE_PHYSICAL_CREATE_TABLE_SQL = tuple(
    table.create_table_sql for table in SQLITE_PHYSICAL_SCHEMA_TABLES
)

INERT_SCHEMA_BOUNDARIES = (
    "no sqlite3 import",
    "no database connections",
    "no SQL execution",
    "no migrations",
    "no persistence",
    "no database files",
    "no runtime file I/O",
    "no API routes",
    "no ingestion",
    "no extraction",
    "no indexing",
    "no embeddings",
    "no retrieval runtime",
    "no PageIndex dependency",
    "no fixtures",
    "no provider/model calls",
    "no Hermes",
    "no MCPs",
    "no sync",
    "no private-root inspection",
    "no app behavior",
)


def sqlite_schema_table_names() -> tuple[str, ...]:
    """Return stable table names in contract order."""

    return SQLITE_SCHEMA_TABLE_NAMES


def sqlite_schema_tables() -> tuple[TableDefinition, ...]:
    """Return immutable inert table definitions."""

    return SQLITE_SCHEMA_TABLES


def sqlite_schema_table(table_name: str) -> TableDefinition | None:
    """Return a table definition by exact stable table name."""

    return SQLITE_SCHEMA_TABLES_BY_NAME.get(table_name)


def sqlite_schema_sql_definitions() -> tuple[str, ...]:
    """Return inert SQL DDL strings without applying or executing them."""

    return SQLITE_CREATE_TABLE_SQL


def sqlite_schema_control_table_names() -> tuple[str, ...]:
    """Return static schema-control metadata table names."""

    return SQLITE_SCHEMA_CONTROL_TABLE_NAMES


def sqlite_schema_control_tables() -> tuple[TableDefinition, ...]:
    """Return immutable schema-control table definitions."""

    return SQLITE_SCHEMA_CONTROL_TABLES


def sqlite_schema_control_table(table_name: str) -> TableDefinition | None:
    """Return a schema-control table by exact stable table name."""

    return SQLITE_SCHEMA_CONTROL_TABLES_BY_NAME.get(table_name)


def sqlite_physical_schema_table_names() -> tuple[str, ...]:
    """Return every physical table name in creation order."""

    return SQLITE_PHYSICAL_SCHEMA_TABLE_NAMES


def sqlite_physical_schema_tables() -> tuple[TableDefinition, ...]:
    """Return semantic and schema-control physical table definitions."""

    return SQLITE_PHYSICAL_SCHEMA_TABLES


def sqlite_physical_schema_table(table_name: str) -> TableDefinition | None:
    """Return any physical schema table by exact stable table name."""

    return SQLITE_PHYSICAL_SCHEMA_TABLES_BY_NAME.get(table_name)


def sqlite_physical_schema_sql_definitions() -> tuple[str, ...]:
    """Return inert SQL DDL strings for all physical schema tables."""

    return SQLITE_PHYSICAL_CREATE_TABLE_SQL


def validate_sqlite_schema_table(table: TableDefinition) -> bool:
    """Check one inert table definition against the backend contract."""

    concept = sqlite_table_concept(table.table_name)
    if concept is None:
        return False
    if table.related_schema_contract_surface != concept.related_schema_contract_surface:
        return False
    result = validate_sqlite_table_concept_definition(
        table.table_name,
        table.conceptual_fields,
        forbidden_implementation_behavior=table.forbidden_implementation_behavior,
    )
    return result.ok and not table.can_directly_imply_accepted_truth


def sqlite_schema_matches_backend_contract() -> bool:
    """Return True when every inert table definition matches the source contract."""

    if SQLITE_SCHEMA_TABLE_NAMES != REQUIRED_SQLITE_TABLE_CONCEPTS:
        return False
    return all(validate_sqlite_schema_table(table) for table in SQLITE_SCHEMA_TABLES)


def table_retrieval_structure_fields(table_name: str) -> frozenset[str]:
    """Return structure fields preserved for future retrieval flexibility."""

    table = sqlite_schema_table(table_name)
    if table is None:
        return frozenset()
    return table.retrieval_structure_fields


def required_contract_fields_for_table(table_name: str) -> frozenset[str]:
    """Return source-contract conceptual fields for a known table concept."""

    return required_sqlite_table_concept_fields(table_name)
