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
SCHEMA_IDENTITY = "backend_sqlite_schema"
SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE = "in_memory_current"

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

SOURCE_REGISTRY_COLUMNS = (
    ColumnDefinition("source_id", "TEXT", "source_id"),
    ColumnDefinition("device_identity", "TEXT", "device_identity"),
    ColumnDefinition(
        "last_known_mount_path",
        "TEXT",
        "last_known_mount_path",
        purpose="Ephemeral source location; not a durable file identity.",
    ),
    ColumnDefinition("source_mode", "TEXT", "source_mode"),
    ColumnDefinition("operator_classification", "TEXT", "operator_classification"),
    ColumnDefinition("approval_receipt_ref", "TEXT", "approval_receipt_ref"),
    ColumnDefinition("freshness_timestamp", "TEXT", "freshness_timestamp"),
)

SOURCE_DISCOVERY_QUEUE_COLUMNS = (
    ColumnDefinition("discovery_id", "TEXT", "discovery_id"),
    ColumnDefinition("device_identity", "TEXT", "device_identity"),
    ColumnDefinition("detected_path", "TEXT", "detected_path"),
    ColumnDefinition("detected_at", "TEXT", "detected_at"),
    ColumnDefinition("status", "TEXT", "status"),
)

SOURCE_EXCLUSIONS_COLUMNS = (
    ColumnDefinition("exclusion_id", "TEXT", "exclusion_id"),
    ColumnDefinition("source_id", "TEXT", "source_id"),
    ColumnDefinition("pattern_type", "TEXT", "pattern_type"),
    ColumnDefinition("path_pattern", "TEXT", "path_pattern"),
    ColumnDefinition("exclusion_level", "TEXT", "exclusion_level"),
    ColumnDefinition("reason", "TEXT", "reason"),
)

FILE_INVENTORY_COLUMNS = (
    ColumnDefinition("inventory_id", "TEXT", "inventory_id"),
    ColumnDefinition("source_id", "TEXT", "source_id"),
    ColumnDefinition(
        "relative_path",
        "TEXT",
        "relative_path",
        purpose="Durable source-local file identity; never an absolute mount path.",
    ),
    ColumnDefinition("file_size", "INTEGER", "file_size"),
    ColumnDefinition("mtime", "TEXT", "mtime"),
    ColumnDefinition("hash_heuristic", "TEXT", "hash_heuristic"),
    ColumnDefinition("inventory_status", "TEXT", "inventory_status"),
    ColumnDefinition("last_seen_timestamp", "TEXT", "last_seen_timestamp"),
    ColumnDefinition("source_confidence", "TEXT", "source_confidence"),
)

STORAGE_OPERATION_RECEIPTS_COLUMNS = (
    ColumnDefinition("operation_id", "TEXT", "operation_id"),
    ColumnDefinition("operation_type", "TEXT", "operation_type"),
    ColumnDefinition("source_inventory_id", "TEXT", "source_inventory_id"),
    ColumnDefinition("target_path", "TEXT", "target_path"),
    ColumnDefinition("safety_tier", "TEXT", "safety_tier"),
    ColumnDefinition("checksum_verification", "INTEGER", "checksum_verification"),
    ColumnDefinition("operator_approval_ref", "TEXT", "operator_approval_ref"),
    ColumnDefinition("execution_status", "TEXT", "execution_status"),
)

OPENCLAW_NODES_COLUMNS = (
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition(
        "node_identity",
        "TEXT",
        "node_identity",
        purpose="Stable node identity surface; not merely MAC, IP, or hostname.",
    ),
    ColumnDefinition(
        "node_fingerprint",
        "TEXT",
        "node_fingerprint",
        purpose="Reserved for future cryptographic/public-key identity material.",
    ),
    ColumnDefinition("trust_status", "TEXT", "trust_status"),
    ColumnDefinition("identity_verified_at", "TEXT", "identity_verified_at"),
    ColumnDefinition("node_role", "TEXT", "node_role"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("agent_version", "TEXT", "agent_version"),
    ColumnDefinition("status", "TEXT", "status"),
    ColumnDefinition("operator_approval_ref", "TEXT", "operator_approval_ref"),
    ColumnDefinition("first_seen", "TEXT", "first_seen"),
    ColumnDefinition("last_seen", "TEXT", "last_seen"),
)

NODE_SOURCE_LINKS_COLUMNS = (
    ColumnDefinition("link_id", "TEXT", "link_id"),
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition("source_id", "TEXT", "source_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("status", "TEXT", "status"),
    ColumnDefinition("linked_at", "TEXT", "linked_at"),
    ColumnDefinition("last_seen", "TEXT", "last_seen"),
    ColumnDefinition("operator_approval_ref", "TEXT", "operator_approval_ref"),
)

SOURCE_AUTHORIZATION_SCOPES_COLUMNS = (
    ColumnDefinition("scope_id", "TEXT", "scope_id"),
    ColumnDefinition("source_id", "TEXT", "source_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("authorized_entity_family", "TEXT", "authorized_entity_family"),
    ColumnDefinition("authorized_entity_id", "TEXT", "authorized_entity_id"),
    ColumnDefinition("operator_approval_ref", "TEXT", "operator_approval_ref"),
    ColumnDefinition("expiration_timestamp", "TEXT", "expiration_timestamp"),
    ColumnDefinition("status", "TEXT", "status"),
)

RUNTIME_COMPONENTS_COLUMNS = (
    ColumnDefinition("component_id", "TEXT", "component_id"),
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("component_name", "TEXT", "component_name"),
    ColumnDefinition("component_instance_id", "TEXT", "component_instance_id"),
    ColumnDefinition("component_role", "TEXT", "component_role"),
    ColumnDefinition("component_version", "TEXT", "component_version"),
    ColumnDefinition("status", "TEXT", "status"),
    ColumnDefinition(
        "approval_receipt_ref",
        "TEXT",
        "approval_receipt_ref",
        purpose="Component approval does not authorize source or action access.",
    ),
    ColumnDefinition("registered_at", "TEXT", "registered_at"),
    ColumnDefinition("last_seen", "TEXT", "last_seen"),
)

COMPONENT_CAPABILITIES_COLUMNS = (
    ColumnDefinition("capability_id", "TEXT", "capability_id"),
    ColumnDefinition("component_id", "TEXT", "component_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("capability_name", "TEXT", "capability_name"),
    ColumnDefinition("capability_scope", "TEXT", "capability_scope"),
    ColumnDefinition("status", "TEXT", "status"),
    ColumnDefinition(
        "approval_receipt_ref",
        "TEXT",
        "approval_receipt_ref",
        purpose="Capability metadata is not live execution permission.",
    ),
)

NODE_HEARTBEATS_COLUMNS = (
    ColumnDefinition("heartbeat_id", "TEXT", "heartbeat_id"),
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("reported_at", "TEXT", "reported_at"),
    ColumnDefinition("heartbeat_ttl_seconds", "INTEGER", "heartbeat_ttl_seconds"),
    ColumnDefinition("health_status", "TEXT", "health_status"),
    ColumnDefinition("status_message", "TEXT", "status_message"),
    ColumnDefinition("last_known_state", "TEXT", "last_known_state"),
)

COMPONENT_HEARTBEATS_COLUMNS = (
    ColumnDefinition("heartbeat_id", "TEXT", "heartbeat_id"),
    ColumnDefinition("component_id", "TEXT", "component_id"),
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("reported_at", "TEXT", "reported_at"),
    ColumnDefinition("heartbeat_ttl_seconds", "INTEGER", "heartbeat_ttl_seconds"),
    ColumnDefinition("health_status", "TEXT", "health_status"),
    ColumnDefinition("status_message", "TEXT", "status_message"),
    ColumnDefinition("last_known_state", "TEXT", "last_known_state"),
)

COMPONENT_HEALTH_SNAPSHOTS_COLUMNS = (
    ColumnDefinition("snapshot_id", "TEXT", "snapshot_id"),
    ColumnDefinition("component_id", "TEXT", "component_id"),
    ColumnDefinition("node_id", "TEXT", "node_id"),
    ColumnDefinition("tenant_id", "TEXT", "tenant_id"),
    ColumnDefinition("captured_at", "TEXT", "captured_at"),
    ColumnDefinition("health_status", "TEXT", "health_status"),
    ColumnDefinition("degraded_reason", "TEXT", "degraded_reason"),
    ColumnDefinition("capabilities_reported", "TEXT", "capabilities_reported"),
    ColumnDefinition("version_reported", "TEXT", "version_reported"),
    ColumnDefinition("last_known_state", "TEXT", "last_known_state"),
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
    TableDefinition(
        table_name="source_registry",
        related_schema_contract_surface="source_registry",
        columns=SOURCE_REGISTRY_COLUMNS,
        retrieval_structure_fields=frozenset(),
        create_table_sql="""
CREATE TABLE source_registry (
  source_id TEXT PRIMARY KEY,
  device_identity TEXT NOT NULL,
  last_known_mount_path TEXT NOT NULL,
  source_mode TEXT NOT NULL,
  operator_classification TEXT NOT NULL,
  approval_receipt_ref TEXT NOT NULL,
  freshness_timestamp TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="source_discovery_queue",
        related_schema_contract_surface="source_discovery_queue",
        columns=SOURCE_DISCOVERY_QUEUE_COLUMNS,
        retrieval_structure_fields=frozenset(),
        create_table_sql="""
CREATE TABLE source_discovery_queue (
  discovery_id TEXT PRIMARY KEY,
  device_identity TEXT NOT NULL,
  detected_path TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  status TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="source_exclusions",
        related_schema_contract_surface="source_exclusion",
        columns=SOURCE_EXCLUSIONS_COLUMNS,
        retrieval_structure_fields=frozenset(),
        create_table_sql="""
CREATE TABLE source_exclusions (
  exclusion_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  pattern_type TEXT NOT NULL,
  path_pattern TEXT NOT NULL,
  exclusion_level TEXT NOT NULL,
  reason TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="file_inventory",
        related_schema_contract_surface="file_inventory",
        columns=FILE_INVENTORY_COLUMNS,
        retrieval_structure_fields=frozenset({"source_id", "relative_path"}),
        create_table_sql="""
CREATE TABLE file_inventory (
  inventory_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  mtime TEXT NOT NULL,
  hash_heuristic TEXT NOT NULL,
  inventory_status TEXT NOT NULL,
  last_seen_timestamp TEXT NOT NULL,
  source_confidence TEXT NOT NULL,
  UNIQUE (source_id, relative_path)
);
""".strip(),
    ),
    TableDefinition(
        table_name="storage_operation_receipts",
        related_schema_contract_surface="storage_operation_receipt",
        columns=STORAGE_OPERATION_RECEIPTS_COLUMNS,
        retrieval_structure_fields=frozenset(),
        create_table_sql="""
CREATE TABLE storage_operation_receipts (
  operation_id TEXT PRIMARY KEY,
  operation_type TEXT NOT NULL,
  source_inventory_id TEXT NOT NULL,
  target_path TEXT NOT NULL,
  safety_tier TEXT NOT NULL,
  checksum_verification INTEGER NOT NULL,
  operator_approval_ref TEXT NOT NULL,
  execution_status TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="openclaw_nodes",
        related_schema_contract_surface="openclaw_node",
        columns=OPENCLAW_NODES_COLUMNS,
        retrieval_structure_fields=frozenset({"node_identity", "tenant_id"}),
        create_table_sql="""
CREATE TABLE openclaw_nodes (
  node_id TEXT PRIMARY KEY,
  node_identity TEXT NOT NULL,
  node_fingerprint TEXT NOT NULL,
  trust_status TEXT NOT NULL,
  identity_verified_at TEXT NOT NULL,
  node_role TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  agent_version TEXT NOT NULL,
  status TEXT NOT NULL,
  operator_approval_ref TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="node_source_links",
        related_schema_contract_surface="node_source_link",
        columns=NODE_SOURCE_LINKS_COLUMNS,
        retrieval_structure_fields=frozenset({"node_id", "source_id", "tenant_id"}),
        create_table_sql="""
CREATE TABLE node_source_links (
  link_id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  status TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  operator_approval_ref TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="source_authorization_scopes",
        related_schema_contract_surface="source_authorization_scope",
        columns=SOURCE_AUTHORIZATION_SCOPES_COLUMNS,
        retrieval_structure_fields=frozenset(
            {
                "source_id",
                "tenant_id",
                "authorized_entity_family",
                "authorized_entity_id",
            }
        ),
        create_table_sql="""
CREATE TABLE source_authorization_scopes (
  scope_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  authorized_entity_family TEXT NOT NULL,
  authorized_entity_id TEXT NOT NULL,
  operator_approval_ref TEXT NOT NULL,
  expiration_timestamp TEXT NOT NULL,
  status TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="runtime_components",
        related_schema_contract_surface="runtime_component",
        columns=RUNTIME_COMPONENTS_COLUMNS,
        retrieval_structure_fields=frozenset(
            {"node_id", "tenant_id", "component_role", "status"}
        ),
        create_table_sql="""
CREATE TABLE runtime_components (
  component_id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  component_name TEXT NOT NULL,
  component_instance_id TEXT NOT NULL,
  component_role TEXT NOT NULL,
  component_version TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_receipt_ref TEXT NOT NULL,
  registered_at TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="component_capabilities",
        related_schema_contract_surface="component_capability",
        columns=COMPONENT_CAPABILITIES_COLUMNS,
        retrieval_structure_fields=frozenset(
            {"component_id", "tenant_id", "capability_name", "status"}
        ),
        create_table_sql="""
CREATE TABLE component_capabilities (
  capability_id TEXT PRIMARY KEY,
  component_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  capability_name TEXT NOT NULL,
  capability_scope TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_receipt_ref TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="node_heartbeats",
        related_schema_contract_surface="node_heartbeat",
        columns=NODE_HEARTBEATS_COLUMNS,
        retrieval_structure_fields=frozenset(
            {"node_id", "tenant_id", "reported_at", "health_status"}
        ),
        create_table_sql="""
CREATE TABLE node_heartbeats (
  heartbeat_id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  reported_at TEXT NOT NULL,
  heartbeat_ttl_seconds INTEGER NOT NULL,
  health_status TEXT NOT NULL,
  status_message TEXT NOT NULL,
  last_known_state TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="component_heartbeats",
        related_schema_contract_surface="component_heartbeat",
        columns=COMPONENT_HEARTBEATS_COLUMNS,
        retrieval_structure_fields=frozenset(
            {"component_id", "node_id", "tenant_id", "reported_at", "health_status"}
        ),
        create_table_sql="""
CREATE TABLE component_heartbeats (
  heartbeat_id TEXT PRIMARY KEY,
  component_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  reported_at TEXT NOT NULL,
  heartbeat_ttl_seconds INTEGER NOT NULL,
  health_status TEXT NOT NULL,
  status_message TEXT NOT NULL,
  last_known_state TEXT NOT NULL
);
""".strip(),
    ),
    TableDefinition(
        table_name="component_health_snapshots",
        related_schema_contract_surface="component_health_snapshot",
        columns=COMPONENT_HEALTH_SNAPSHOTS_COLUMNS,
        retrieval_structure_fields=frozenset(
            {"component_id", "node_id", "tenant_id", "captured_at", "health_status"}
        ),
        create_table_sql="""
CREATE TABLE component_health_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  component_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  health_status TEXT NOT NULL,
  degraded_reason TEXT NOT NULL,
  capabilities_reported TEXT NOT NULL,
  version_reported TEXT NOT NULL,
  last_known_state TEXT NOT NULL
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
