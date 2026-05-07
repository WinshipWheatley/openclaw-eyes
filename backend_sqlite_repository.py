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
SOURCE_REGISTRY_TABLE_NAME = "source_registry"
SOURCE_DISCOVERY_QUEUE_TABLE_NAME = "source_discovery_queue"
SOURCE_EXCLUSIONS_TABLE_NAME = "source_exclusions"
FILE_INVENTORY_TABLE_NAME = "file_inventory"
STORAGE_OPERATION_RECEIPTS_TABLE_NAME = "storage_operation_receipts"
OPENCLAW_NODES_TABLE_NAME = "openclaw_nodes"
NODE_SOURCE_LINKS_TABLE_NAME = "node_source_links"
SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME = "source_authorization_scopes"
RUNTIME_COMPONENTS_TABLE_NAME = "runtime_components"
COMPONENT_CAPABILITIES_TABLE_NAME = "component_capabilities"
NODE_HEARTBEATS_TABLE_NAME = "node_heartbeats"
COMPONENT_HEARTBEATS_TABLE_NAME = "component_heartbeats"
COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME = "component_health_snapshots"
PERFORMANCE_SESSIONS_TABLE_NAME = "performance_sessions"
SETLISTS_TABLE_NAME = "setlists"
SETLIST_ITEMS_TABLE_NAME = "setlist_items"
SONG_CUES_TABLE_NAME = "song_cues"
SECTION_CUES_TABLE_NAME = "section_cues"
PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME = "performance_action_receipts"
MANUAL_OVERRIDE_EVENTS_TABLE_NAME = "manual_override_events"
HIGHLIGHT_MARKERS_TABLE_NAME = "highlight_markers"

REPOSITORY_TABLE_PRIMARY_KEYS = {
    SEMANTIC_RECORDS_TABLE_NAME: "record_id",
    SEMANTIC_LABELS_TABLE_NAME: "label_id",
    SEMANTIC_RELATIONSHIPS_TABLE_NAME: "relationship_id",
    PROVENANCE_REFS_TABLE_NAME: "provenance_ref_id",
    VALIDATION_RECEIPTS_TABLE_NAME: "receipt_id",
    OPERATOR_PROMOTIONS_TABLE_NAME: "promotion_id",
    SOURCE_REGISTRY_TABLE_NAME: "source_id",
    SOURCE_DISCOVERY_QUEUE_TABLE_NAME: "discovery_id",
    SOURCE_EXCLUSIONS_TABLE_NAME: "exclusion_id",
    FILE_INVENTORY_TABLE_NAME: "inventory_id",
    STORAGE_OPERATION_RECEIPTS_TABLE_NAME: "operation_id",
    OPENCLAW_NODES_TABLE_NAME: "node_id",
    NODE_SOURCE_LINKS_TABLE_NAME: "link_id",
    SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME: "scope_id",
    RUNTIME_COMPONENTS_TABLE_NAME: "component_id",
    COMPONENT_CAPABILITIES_TABLE_NAME: "capability_id",
    NODE_HEARTBEATS_TABLE_NAME: "heartbeat_id",
    COMPONENT_HEARTBEATS_TABLE_NAME: "heartbeat_id",
    COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME: "snapshot_id",
    PERFORMANCE_SESSIONS_TABLE_NAME: "performance_session_id",
    SETLISTS_TABLE_NAME: "setlist_id",
    SETLIST_ITEMS_TABLE_NAME: "setlist_item_id",
    SONG_CUES_TABLE_NAME: "song_cue_id",
    SECTION_CUES_TABLE_NAME: "section_cue_id",
    PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME: "performance_action_receipt_id",
    MANUAL_OVERRIDE_EVENTS_TABLE_NAME: "manual_override_event_id",
    HIGHLIGHT_MARKERS_TABLE_NAME: "highlight_marker_id",
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


@dataclass(frozen=True)
class SourceRegistryEntry:
    """Approved source/device/server registry row.

    last_known_mount_path is an ephemeral location hint. File identity belongs
    to file_inventory.source_id plus file_inventory.relative_path.
    """

    source_id: str
    device_identity: str
    last_known_mount_path: str
    source_mode: str
    operator_classification: str
    approval_receipt_ref: str
    freshness_timestamp: str


@dataclass(frozen=True)
class SourceDiscoveryEvent:
    """Discovered source event that is not approved by discovery alone."""

    discovery_id: str
    device_identity: str
    detected_path: str
    detected_at: str
    status: str


@dataclass(frozen=True)
class SourceExclusion:
    """Explicit source/folder/file/type/sensitivity exclusion boundary."""

    exclusion_id: str
    source_id: str
    pattern_type: str
    path_pattern: str
    exclusion_level: str
    reason: str


@dataclass(frozen=True)
class FileInventoryRow:
    """Metadata inventory row for an approved source, before content access."""

    inventory_id: str
    source_id: str
    relative_path: str
    file_size: int
    mtime: str
    hash_heuristic: str
    inventory_status: str
    last_seen_timestamp: str
    source_confidence: str


@dataclass(frozen=True)
class StorageOperationReceipt:
    """Dry-run or future operation receipt row; execution is status-explicit."""

    operation_id: str
    operation_type: str
    source_inventory_id: str
    target_path: str
    safety_tier: str
    checksum_verification: int
    operator_approval_ref: str
    execution_status: str


@dataclass(frozen=True)
class OpenClawNode:
    """Approved OpenClaw-aware node row; no source/content access is implied."""

    node_id: str
    node_identity: str
    node_fingerprint: str
    trust_status: str
    identity_verified_at: str
    node_role: str
    tenant_id: str
    agent_version: str
    status: str
    operator_approval_ref: str
    first_seen: str
    last_seen: str


@dataclass(frozen=True)
class NodeSourceLink:
    """Tenant-scoped link between a node and an approved source."""

    link_id: str
    node_id: str
    source_id: str
    tenant_id: str
    status: str
    linked_at: str
    last_seen: str
    operator_approval_ref: str


@dataclass(frozen=True)
class SourceAuthorizationScope:
    """Explicit tenant/source/entity authorization scope."""

    scope_id: str
    source_id: str
    tenant_id: str
    authorized_entity_family: str
    authorized_entity_id: str
    operator_approval_ref: str
    expiration_timestamp: str
    status: str


@dataclass(frozen=True)
class RuntimeComponent:
    """Tenant-scoped runtime component row; presence is not permission."""

    component_id: str
    node_id: str
    tenant_id: str
    component_name: str
    component_instance_id: str
    component_role: str
    component_version: str
    status: str
    approval_receipt_ref: str
    registered_at: str
    last_seen: str


@dataclass(frozen=True)
class ComponentCapability:
    """Bounded component capability metadata; it does not execute behavior."""

    capability_id: str
    component_id: str
    tenant_id: str
    capability_name: str
    capability_scope: str
    status: str
    approval_receipt_ref: str


@dataclass(frozen=True)
class NodeHeartbeat:
    """Stored node heartbeat data; no live heartbeat behavior is implied."""

    heartbeat_id: str
    node_id: str
    tenant_id: str
    reported_at: str
    heartbeat_ttl_seconds: int
    health_status: str
    status_message: str
    last_known_state: str


@dataclass(frozen=True)
class ComponentHeartbeat:
    """Stored component heartbeat data; no polling behavior is implied."""

    heartbeat_id: str
    component_id: str
    node_id: str
    tenant_id: str
    reported_at: str
    heartbeat_ttl_seconds: int
    health_status: str
    status_message: str
    last_known_state: str


@dataclass(frozen=True)
class ComponentHealthSnapshot:
    """Caller-provided component health snapshot; no process scan is implied."""

    snapshot_id: str
    component_id: str
    node_id: str
    tenant_id: str
    captured_at: str
    health_status: str
    degraded_reason: str
    capabilities_reported: str
    version_reported: str
    last_known_state: str


@dataclass(frozen=True)
class PerformanceSession:
    """Bounded live show, performance, or studio-flow session."""

    performance_session_id: str
    tenant_id: str
    session_name: str
    session_type: str
    planned_start: str
    actual_start: str
    actual_end: str
    status: str
    operator_approval_ref: str
    source_context_ref: str
    runtime_context_ref: str
    created_at: str


@dataclass(frozen=True)
class Setlist:
    """Inert planned roadmap for a performance session."""

    setlist_id: str
    tenant_id: str
    performance_session_id: str
    setlist_name: str
    status: str
    created_at: str


@dataclass(frozen=True)
class SetlistItem:
    """Inert ordered item in a performance setlist."""

    setlist_item_id: str
    tenant_id: str
    setlist_id: str
    item_order: int
    item_type: str
    title: str
    semantic_record_id: str
    status: str


@dataclass(frozen=True)
class SongCue:
    """Inert planned song-level cue marker."""

    song_cue_id: str
    tenant_id: str
    setlist_item_id: str
    cue_name: str
    cue_type: str
    cue_order: int
    expected_tempo: str
    status: str


@dataclass(frozen=True)
class SectionCue:
    """Inert explicit section-level map marker."""

    section_cue_id: str
    tenant_id: str
    song_cue_id: str
    section_name: str
    section_type: str
    section_order: int
    expected_duration: int
    safe_baseline_scene_ref: str
    status: str


@dataclass(frozen=True)
class PerformanceActionReceipt:
    """Inert receipt or log for performance actions."""

    performance_action_receipt_id: str
    tenant_id: str
    performance_session_id: str
    action_type: str
    action_target: str
    action_tier: str
    requested_by: str
    approved_by: str
    status: str
    receipt_payload: str
    created_at: str


@dataclass(frozen=True)
class ManualOverrideEvent:
    """Inert explicit record of operator intervention overriding show control."""

    manual_override_event_id: str
    tenant_id: str
    performance_session_id: str
    override_type: str
    override_reason: str
    affected_target: str
    status: str
    created_at: str


@dataclass(frozen=True)
class HighlightMarker:
    """Inert timestamped moment for later review or editing."""

    highlight_marker_id: str
    tenant_id: str
    performance_session_id: str
    setlist_item_id: str
    marker_time: str
    marker_label: str
    marker_source: str
    notes: str
    status: str


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


def write_source_registry_entry(
    connection: Any,
    entry: SourceRegistryEntry | Mapping[str, Any],
) -> None:
    """Insert one approved source_registry row through a caller-owned connection."""

    payload = _table_payload(SOURCE_REGISTRY_TABLE_NAME, entry)
    _insert_row(connection, SOURCE_REGISTRY_TABLE_NAME, payload)


def read_source_registry_entry(
    connection: Any,
    source_id: str,
) -> dict[str, Any] | None:
    """Read one source_registry row by explicit source_id."""

    return _read_row_by_primary_key(connection, SOURCE_REGISTRY_TABLE_NAME, source_id)


def read_source_registry_entries_by_device_identity(
    connection: Any,
    device_identity: str,
) -> tuple[dict[str, Any], ...]:
    """Read approved source rows for one exact device identity in source_id order."""

    _require_non_empty_string(device_identity, "device_identity")
    return _read_rows_where(
        connection,
        SOURCE_REGISTRY_TABLE_NAME,
        "device_identity",
        device_identity,
        order_by="source_id",
    )


def write_source_discovery_event(
    connection: Any,
    event: SourceDiscoveryEvent | Mapping[str, Any],
) -> None:
    """Insert one discovered source event; this does not approve the source."""

    payload = _table_payload(SOURCE_DISCOVERY_QUEUE_TABLE_NAME, event)
    _insert_row(connection, SOURCE_DISCOVERY_QUEUE_TABLE_NAME, payload)


def read_source_discovery_event(
    connection: Any,
    discovery_id: str,
) -> dict[str, Any] | None:
    """Read one source_discovery_queue row by explicit discovery_id."""

    return _read_row_by_primary_key(
        connection,
        SOURCE_DISCOVERY_QUEUE_TABLE_NAME,
        discovery_id,
    )


def read_pending_source_discovery_events(
    connection: Any,
) -> tuple[dict[str, Any], ...]:
    """Read pending source discovery events in deterministic detected_at/id order."""

    columns = table_column_names(SOURCE_DISCOVERY_QUEUE_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM source_discovery_queue
WHERE status = ?
ORDER BY detected_at, discovery_id
""".strip(),
        ("pending_approval",),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_source_exclusion(
    connection: Any,
    exclusion: SourceExclusion | Mapping[str, Any],
) -> None:
    """Insert one explicit exclusion for an approved source."""

    payload = _table_payload(SOURCE_EXCLUSIONS_TABLE_NAME, exclusion)
    _require_existing_source_registry_entry(connection, payload["source_id"])
    _insert_row(connection, SOURCE_EXCLUSIONS_TABLE_NAME, payload)


def read_source_exclusion(
    connection: Any,
    exclusion_id: str,
) -> dict[str, Any] | None:
    """Read one source_exclusions row by explicit exclusion_id."""

    return _read_row_by_primary_key(connection, SOURCE_EXCLUSIONS_TABLE_NAME, exclusion_id)


def read_source_exclusions(
    connection: Any,
    source_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read exclusions for one source in deterministic exclusion_id order."""

    _require_existing_source_registry_entry(connection, source_id)
    return _read_rows_where(
        connection,
        SOURCE_EXCLUSIONS_TABLE_NAME,
        "source_id",
        source_id,
        order_by="exclusion_id",
    )


def write_file_inventory_row(
    connection: Any,
    row: FileInventoryRow | Mapping[str, Any],
) -> None:
    """Insert one metadata inventory row without touching real files."""

    payload = _table_payload(FILE_INVENTORY_TABLE_NAME, row)
    _require_existing_source_registry_entry(connection, payload["source_id"])
    _require_relative_inventory_path(payload["relative_path"])
    _require_non_negative_int(payload["file_size"], "file_size")
    _insert_row(connection, FILE_INVENTORY_TABLE_NAME, payload)


def read_file_inventory_row(
    connection: Any,
    inventory_id: str,
) -> dict[str, Any] | None:
    """Read one file_inventory row by explicit inventory_id."""

    return _read_row_by_primary_key(connection, FILE_INVENTORY_TABLE_NAME, inventory_id)


def read_file_inventory_rows_by_source_id(
    connection: Any,
    source_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read inventory rows for one source in deterministic relative_path order."""

    _require_existing_source_registry_entry(connection, source_id)
    return _read_rows_where(
        connection,
        FILE_INVENTORY_TABLE_NAME,
        "source_id",
        source_id,
        order_by="relative_path",
    )


def read_file_inventory_row_by_source_relative_path(
    connection: Any,
    source_id: str,
    relative_path: str,
) -> dict[str, Any] | None:
    """Read one inventory row by durable source_id plus relative_path identity."""

    _require_existing_source_registry_entry(connection, source_id)
    _require_relative_inventory_path(relative_path)
    columns = table_column_names(FILE_INVENTORY_TABLE_NAME)
    row = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM file_inventory
WHERE source_id = ? AND relative_path = ?
""".strip(),
        (source_id, relative_path),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def write_storage_operation_receipt(
    connection: Any,
    receipt: StorageOperationReceipt | Mapping[str, Any],
) -> None:
    """Insert one dry-run/future operation receipt without executing operations."""

    payload = _table_payload(STORAGE_OPERATION_RECEIPTS_TABLE_NAME, receipt)
    _require_existing_file_inventory_row(connection, payload["source_inventory_id"])
    _require_binary_int(payload["checksum_verification"], "checksum_verification")
    _insert_row(connection, STORAGE_OPERATION_RECEIPTS_TABLE_NAME, payload)


def read_storage_operation_receipt(
    connection: Any,
    operation_id: str,
) -> dict[str, Any] | None:
    """Read one storage_operation_receipts row by explicit operation_id."""

    return _read_row_by_primary_key(
        connection,
        STORAGE_OPERATION_RECEIPTS_TABLE_NAME,
        operation_id,
    )


def read_storage_operation_receipts_by_inventory_id(
    connection: Any,
    inventory_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read operation receipts for one inventory row in operation_id order."""

    _require_existing_file_inventory_row(connection, inventory_id)
    return _read_rows_where(
        connection,
        STORAGE_OPERATION_RECEIPTS_TABLE_NAME,
        "source_inventory_id",
        inventory_id,
        order_by="operation_id",
    )


def write_openclaw_node(
    connection: Any,
    node: OpenClawNode | Mapping[str, Any],
) -> None:
    """Insert one OpenClaw-aware node row without network communication."""

    payload = _table_payload(OPENCLAW_NODES_TABLE_NAME, node)
    _require_non_empty_string(payload["node_identity"], "node_identity")
    _require_non_empty_string(payload["node_fingerprint"], "node_fingerprint")
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _insert_row(connection, OPENCLAW_NODES_TABLE_NAME, payload)


def read_openclaw_node(connection: Any, node_id: str) -> dict[str, Any] | None:
    """Read one openclaw_nodes row by explicit node_id."""

    return _read_row_by_primary_key(connection, OPENCLAW_NODES_TABLE_NAME, node_id)


def read_openclaw_nodes_by_node_identity(
    connection: Any,
    node_identity: str,
) -> tuple[dict[str, Any], ...]:
    """Read nodes for one exact node identity in deterministic node_id order."""

    _require_non_empty_string(node_identity, "node_identity")
    return _read_rows_where(
        connection,
        OPENCLAW_NODES_TABLE_NAME,
        "node_identity",
        node_identity,
        order_by="node_id",
    )


def read_openclaw_nodes_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read nodes for one tenant in deterministic node_id order."""

    _require_non_empty_string(tenant_id, "tenant_id")
    return _read_rows_where(
        connection,
        OPENCLAW_NODES_TABLE_NAME,
        "tenant_id",
        tenant_id,
        order_by="node_id",
    )


def read_openclaw_nodes_by_trust_status(
    connection: Any,
    trust_status: str,
) -> tuple[dict[str, Any], ...]:
    """Read nodes by exact trust status in deterministic node_id order."""

    _require_non_empty_string(trust_status, "trust_status")
    return _read_rows_where(
        connection,
        OPENCLAW_NODES_TABLE_NAME,
        "trust_status",
        trust_status,
        order_by="node_id",
    )


def read_openclaw_nodes_by_status(
    connection: Any,
    status: str,
) -> tuple[dict[str, Any], ...]:
    """Read nodes by exact status in deterministic node_id order."""

    _require_non_empty_string(status, "status")
    return _read_rows_where(
        connection,
        OPENCLAW_NODES_TABLE_NAME,
        "status",
        status,
        order_by="node_id",
    )


def write_node_source_link(
    connection: Any,
    link: NodeSourceLink | Mapping[str, Any],
) -> None:
    """Insert one explicit node/source link; this does not authorize content."""

    payload = _table_payload(NODE_SOURCE_LINKS_TABLE_NAME, link)
    _require_existing_openclaw_node(connection, payload["node_id"])
    _require_existing_source_registry_entry(connection, payload["source_id"])
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    node_row = read_openclaw_node(connection, payload["node_id"])
    if node_row is not None and node_row["tenant_id"] != payload["tenant_id"]:
        raise ValueError("node_source_links.tenant_id must match openclaw_nodes.tenant_id")
    _insert_row(connection, NODE_SOURCE_LINKS_TABLE_NAME, payload)


def read_node_source_link(connection: Any, link_id: str) -> dict[str, Any] | None:
    """Read one node_source_links row by explicit link_id."""

    return _read_row_by_primary_key(connection, NODE_SOURCE_LINKS_TABLE_NAME, link_id)


def read_node_source_links_by_node_id(
    connection: Any,
    node_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read source links for one node in deterministic link_id order."""

    _require_existing_openclaw_node(connection, node_id)
    return _read_rows_where(
        connection,
        NODE_SOURCE_LINKS_TABLE_NAME,
        "node_id",
        node_id,
        order_by="link_id",
    )


def read_node_source_links_by_source_id(
    connection: Any,
    source_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read node links for one source in deterministic link_id order."""

    _require_existing_source_registry_entry(connection, source_id)
    return _read_rows_where(
        connection,
        NODE_SOURCE_LINKS_TABLE_NAME,
        "source_id",
        source_id,
        order_by="link_id",
    )


def read_node_source_links_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read node/source links for one tenant in deterministic link_id order."""

    _require_non_empty_string(tenant_id, "tenant_id")
    return _read_rows_where(
        connection,
        NODE_SOURCE_LINKS_TABLE_NAME,
        "tenant_id",
        tenant_id,
        order_by="link_id",
    )


def write_source_authorization_scope(
    connection: Any,
    scope: SourceAuthorizationScope | Mapping[str, Any],
) -> None:
    """Insert one explicit source authorization scope."""

    payload = _table_payload(SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME, scope)
    _require_existing_source_registry_entry(connection, payload["source_id"])
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_non_empty_string(
        payload["authorized_entity_family"],
        "authorized_entity_family",
    )
    _require_non_empty_string(payload["authorized_entity_id"], "authorized_entity_id")
    _insert_row(connection, SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME, payload)


def read_source_authorization_scope(
    connection: Any,
    scope_id: str,
) -> dict[str, Any] | None:
    """Read one source_authorization_scopes row by explicit scope_id."""

    return _read_row_by_primary_key(
        connection,
        SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME,
        scope_id,
    )


def read_source_authorization_scopes_by_source_id(
    connection: Any,
    source_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read authorization scopes for one source in deterministic scope_id order."""

    _require_existing_source_registry_entry(connection, source_id)
    return _read_rows_where(
        connection,
        SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME,
        "source_id",
        source_id,
        order_by="scope_id",
    )


def read_source_authorization_scopes_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read authorization scopes for one tenant in deterministic scope_id order."""

    _require_non_empty_string(tenant_id, "tenant_id")
    return _read_rows_where(
        connection,
        SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME,
        "tenant_id",
        tenant_id,
        order_by="scope_id",
    )


def read_active_source_authorization_scopes(
    connection: Any,
    source_id: str,
    tenant_id: str,
    authorized_entity_family: str,
    authorized_entity_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read active exact source authorization scopes for one tenant/entity."""

    _require_existing_source_registry_entry(connection, source_id)
    _require_non_empty_string(tenant_id, "tenant_id")
    _require_non_empty_string(authorized_entity_family, "authorized_entity_family")
    _require_non_empty_string(authorized_entity_id, "authorized_entity_id")
    columns = table_column_names(SOURCE_AUTHORIZATION_SCOPES_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM source_authorization_scopes
WHERE source_id = ?
  AND tenant_id = ?
  AND authorized_entity_family = ?
  AND authorized_entity_id = ?
  AND status = ?
ORDER BY scope_id
""".strip(),
        (
            source_id,
            tenant_id,
            authorized_entity_family,
            authorized_entity_id,
            "active",
        ),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_runtime_component(
    connection: Any,
    component: RuntimeComponent | Mapping[str, Any],
) -> None:
    """Insert one runtime component row without process or network checks."""

    payload = _table_payload(RUNTIME_COMPONENTS_TABLE_NAME, component)
    _require_existing_openclaw_node(connection, payload["node_id"])
    _require_tenant_matches_openclaw_node(
        connection,
        payload["node_id"],
        payload["tenant_id"],
    )
    _insert_row(connection, RUNTIME_COMPONENTS_TABLE_NAME, payload)


def read_runtime_component(
    connection: Any,
    component_id: str,
) -> dict[str, Any] | None:
    """Read one runtime_components row by explicit component_id."""

    return _read_row_by_primary_key(connection, RUNTIME_COMPONENTS_TABLE_NAME, component_id)


def read_runtime_components_by_node_id(
    connection: Any,
    node_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read components for one node in deterministic component_id order."""

    _require_existing_openclaw_node(connection, node_id)
    return _read_rows_where(
        connection,
        RUNTIME_COMPONENTS_TABLE_NAME,
        "node_id",
        node_id,
        order_by="component_id",
    )


def read_runtime_components_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read components for one tenant in deterministic component_id order."""

    _require_non_empty_string(tenant_id, "tenant_id")
    return _read_rows_where(
        connection,
        RUNTIME_COMPONENTS_TABLE_NAME,
        "tenant_id",
        tenant_id,
        order_by="component_id",
    )


def read_runtime_components_by_component_role(
    connection: Any,
    component_role: str,
) -> tuple[dict[str, Any], ...]:
    """Read components by exact role in deterministic component_id order."""

    _require_non_empty_string(component_role, "component_role")
    return _read_rows_where(
        connection,
        RUNTIME_COMPONENTS_TABLE_NAME,
        "component_role",
        component_role,
        order_by="component_id",
    )


def read_runtime_components_by_status(
    connection: Any,
    status: str,
) -> tuple[dict[str, Any], ...]:
    """Read components by exact status in deterministic component_id order."""

    _require_non_empty_string(status, "status")
    return _read_rows_where(
        connection,
        RUNTIME_COMPONENTS_TABLE_NAME,
        "status",
        status,
        order_by="component_id",
    )


def write_component_capability(
    connection: Any,
    capability: ComponentCapability | Mapping[str, Any],
) -> None:
    """Insert one component capability declaration without executing it."""

    payload = _table_payload(COMPONENT_CAPABILITIES_TABLE_NAME, capability)
    _require_existing_runtime_component(connection, payload["component_id"])
    _require_tenant_matches_runtime_component(
        connection,
        payload["component_id"],
        payload["tenant_id"],
    )
    _insert_row(connection, COMPONENT_CAPABILITIES_TABLE_NAME, payload)


def read_component_capability(
    connection: Any,
    capability_id: str,
) -> dict[str, Any] | None:
    """Read one component_capabilities row by explicit capability_id."""

    return _read_row_by_primary_key(
        connection,
        COMPONENT_CAPABILITIES_TABLE_NAME,
        capability_id,
    )


def read_component_capabilities_by_component_id(
    connection: Any,
    component_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read capability declarations for one component in capability_id order."""

    _require_existing_runtime_component(connection, component_id)
    return _read_rows_where(
        connection,
        COMPONENT_CAPABILITIES_TABLE_NAME,
        "component_id",
        component_id,
        order_by="capability_id",
    )


def read_approved_component_capabilities_by_component_id(
    connection: Any,
    component_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read approved capabilities for one component in deterministic order."""

    _require_existing_runtime_component(connection, component_id)
    columns = table_column_names(COMPONENT_CAPABILITIES_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM component_capabilities
WHERE component_id = ? AND status = ?
ORDER BY capability_id
""".strip(),
        (component_id, "approved"),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_node_heartbeat(
    connection: Any,
    heartbeat: NodeHeartbeat | Mapping[str, Any],
) -> None:
    """Insert one stored node heartbeat row without live polling."""

    payload = _table_payload(NODE_HEARTBEATS_TABLE_NAME, heartbeat)
    _require_existing_openclaw_node(connection, payload["node_id"])
    _require_tenant_matches_openclaw_node(
        connection,
        payload["node_id"],
        payload["tenant_id"],
    )
    _require_positive_int(payload["heartbeat_ttl_seconds"], "heartbeat_ttl_seconds")
    _insert_row(connection, NODE_HEARTBEATS_TABLE_NAME, payload)


def read_node_heartbeat(
    connection: Any,
    heartbeat_id: str,
) -> dict[str, Any] | None:
    """Read one node_heartbeats row by explicit heartbeat_id."""

    return _read_row_by_primary_key(connection, NODE_HEARTBEATS_TABLE_NAME, heartbeat_id)


def read_latest_node_heartbeat(
    connection: Any,
    node_id: str,
) -> dict[str, Any] | None:
    """Read latest stored heartbeat for one node by reported_at/id order."""

    _require_existing_openclaw_node(connection, node_id)
    columns = table_column_names(NODE_HEARTBEATS_TABLE_NAME)
    row = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM node_heartbeats
WHERE node_id = ?
ORDER BY reported_at DESC, heartbeat_id DESC
LIMIT 1
""".strip(),
        (node_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def read_stale_node_heartbeats(
    connection: Any,
    stale_before_reported_at: str,
) -> tuple[dict[str, Any], ...]:
    """Read stored stale node heartbeats using a caller-provided timestamp bound."""

    _require_non_empty_string(stale_before_reported_at, "stale_before_reported_at")
    columns = table_column_names(NODE_HEARTBEATS_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM node_heartbeats
WHERE reported_at < ?
ORDER BY reported_at, heartbeat_id
""".strip(),
        (stale_before_reported_at,),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_component_heartbeat(
    connection: Any,
    heartbeat: ComponentHeartbeat | Mapping[str, Any],
) -> None:
    """Insert one stored component heartbeat row without live polling."""

    payload = _table_payload(COMPONENT_HEARTBEATS_TABLE_NAME, heartbeat)
    _require_existing_runtime_component(connection, payload["component_id"])
    _require_existing_openclaw_node(connection, payload["node_id"])
    _require_component_belongs_to_node(
        connection,
        payload["component_id"],
        payload["node_id"],
    )
    _require_tenant_matches_runtime_component(
        connection,
        payload["component_id"],
        payload["tenant_id"],
    )
    _require_positive_int(payload["heartbeat_ttl_seconds"], "heartbeat_ttl_seconds")
    _insert_row(connection, COMPONENT_HEARTBEATS_TABLE_NAME, payload)


def read_component_heartbeat(
    connection: Any,
    heartbeat_id: str,
) -> dict[str, Any] | None:
    """Read one component_heartbeats row by explicit heartbeat_id."""

    return _read_row_by_primary_key(
        connection,
        COMPONENT_HEARTBEATS_TABLE_NAME,
        heartbeat_id,
    )


def read_latest_component_heartbeat(
    connection: Any,
    component_id: str,
) -> dict[str, Any] | None:
    """Read latest stored heartbeat for one component by reported_at/id order."""

    _require_existing_runtime_component(connection, component_id)
    columns = table_column_names(COMPONENT_HEARTBEATS_TABLE_NAME)
    row = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM component_heartbeats
WHERE component_id = ?
ORDER BY reported_at DESC, heartbeat_id DESC
LIMIT 1
""".strip(),
        (component_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def write_component_health_snapshot(
    connection: Any,
    snapshot: ComponentHealthSnapshot | Mapping[str, Any],
) -> None:
    """Insert one component health snapshot without process inspection."""

    payload = _table_payload(COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME, snapshot)
    _require_existing_runtime_component(connection, payload["component_id"])
    _require_existing_openclaw_node(connection, payload["node_id"])
    _require_component_belongs_to_node(
        connection,
        payload["component_id"],
        payload["node_id"],
    )
    _require_tenant_matches_runtime_component(
        connection,
        payload["component_id"],
        payload["tenant_id"],
    )
    _insert_row(connection, COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME, payload)


def read_component_health_snapshot(
    connection: Any,
    snapshot_id: str,
) -> dict[str, Any] | None:
    """Read one component_health_snapshots row by explicit snapshot_id."""

    return _read_row_by_primary_key(
        connection,
        COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME,
        snapshot_id,
    )


def read_latest_component_health_snapshot(
    connection: Any,
    component_id: str,
) -> dict[str, Any] | None:
    """Read latest component health snapshot by captured_at/id order."""

    _require_existing_runtime_component(connection, component_id)
    columns = table_column_names(COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME)
    row = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM component_health_snapshots
WHERE component_id = ?
ORDER BY captured_at DESC, snapshot_id DESC
LIMIT 1
""".strip(),
        (component_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def read_degraded_component_health_snapshots_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read degraded component snapshots for one tenant in deterministic order."""

    _require_non_empty_string(tenant_id, "tenant_id")
    columns = table_column_names(COMPONENT_HEALTH_SNAPSHOTS_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM component_health_snapshots
WHERE tenant_id = ? AND health_status = ?
ORDER BY captured_at, snapshot_id
""".strip(),
        (tenant_id, "degraded"),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_performance_session(
    connection: Any,
    session: PerformanceSession | Mapping[str, Any],
) -> None:
    """Insert one performance session record."""

    payload = _table_payload(PERFORMANCE_SESSIONS_TABLE_NAME, session)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _insert_row(connection, PERFORMANCE_SESSIONS_TABLE_NAME, payload)


def read_performance_session(
    connection: Any,
    performance_session_id: str,
) -> dict[str, Any] | None:
    """Read one performance session record by its primary key."""

    return _read_row_by_primary_key(
        connection,
        PERFORMANCE_SESSIONS_TABLE_NAME,
        performance_session_id,
    )


def read_performance_sessions_by_tenant_id(
    connection: Any,
    tenant_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read performance sessions for a tenant ordered by performance_session_id."""

    _require_non_empty_string(tenant_id, "tenant_id")
    return _read_rows_where(
        connection,
        PERFORMANCE_SESSIONS_TABLE_NAME,
        "tenant_id",
        tenant_id,
        order_by="performance_session_id",
    )


def read_performance_sessions_by_status(
    connection: Any,
    tenant_id: str,
    status: str,
) -> tuple[dict[str, Any], ...]:
    """Read performance sessions by status for a tenant."""

    _require_non_empty_string(tenant_id, "tenant_id")
    _require_non_empty_string(status, "status")
    columns = table_column_names(PERFORMANCE_SESSIONS_TABLE_NAME)
    rows = connection.execute(
        f"""
SELECT {", ".join(columns)}
FROM performance_sessions
WHERE tenant_id = ? AND status = ?
ORDER BY performance_session_id
""".strip(),
        (tenant_id, status),
    ).fetchall()
    return tuple(dict(zip(columns, row)) for row in rows)


def write_setlist(
    connection: Any,
    setlist: Setlist | Mapping[str, Any],
) -> None:
    """Insert one setlist record."""

    payload = _table_payload(SETLISTS_TABLE_NAME, setlist)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_performance_session(connection, payload["performance_session_id"])
    _insert_row(connection, SETLISTS_TABLE_NAME, payload)


def read_setlist(connection: Any, setlist_id: str) -> dict[str, Any] | None:
    """Read one setlist record by its primary key."""

    return _read_row_by_primary_key(connection, SETLISTS_TABLE_NAME, setlist_id)


def read_setlists_by_performance_session_id(
    connection: Any,
    performance_session_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read setlists for a performance session ordered by setlist_id."""

    _require_non_empty_string(performance_session_id, "performance_session_id")
    return _read_rows_where(
        connection,
        SETLISTS_TABLE_NAME,
        "performance_session_id",
        performance_session_id,
        order_by="setlist_id",
    )


def write_setlist_item(
    connection: Any,
    item: SetlistItem | Mapping[str, Any],
) -> None:
    """Insert one setlist item record."""

    payload = _table_payload(SETLIST_ITEMS_TABLE_NAME, item)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_setlist(connection, payload["setlist_id"])
    _require_non_negative_int(payload["item_order"], "item_order")
    _insert_row(connection, SETLIST_ITEMS_TABLE_NAME, payload)


def read_setlist_item(connection: Any, setlist_item_id: str) -> dict[str, Any] | None:
    """Read one setlist item record by its primary key."""

    return _read_row_by_primary_key(connection, SETLIST_ITEMS_TABLE_NAME, setlist_item_id)


def read_setlist_items_by_setlist_id(
    connection: Any,
    setlist_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read setlist items for a setlist ordered by item_order."""

    _require_non_empty_string(setlist_id, "setlist_id")
    return _read_rows_where(
        connection,
        SETLIST_ITEMS_TABLE_NAME,
        "setlist_id",
        setlist_id,
        order_by="item_order",
    )


def write_song_cue(
    connection: Any,
    cue: SongCue | Mapping[str, Any],
) -> None:
    """Insert one song cue record."""

    payload = _table_payload(SONG_CUES_TABLE_NAME, cue)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_setlist_item(connection, payload["setlist_item_id"])
    _require_non_negative_int(payload["cue_order"], "cue_order")
    _insert_row(connection, SONG_CUES_TABLE_NAME, payload)


def read_song_cue(connection: Any, song_cue_id: str) -> dict[str, Any] | None:
    """Read one song cue record by its primary key."""

    return _read_row_by_primary_key(connection, SONG_CUES_TABLE_NAME, song_cue_id)


def read_song_cues_by_setlist_item_id(
    connection: Any,
    setlist_item_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read song cues for a setlist item ordered by cue_order."""

    _require_non_empty_string(setlist_item_id, "setlist_item_id")
    return _read_rows_where(
        connection,
        SONG_CUES_TABLE_NAME,
        "setlist_item_id",
        setlist_item_id,
        order_by="cue_order",
    )


def write_section_cue(
    connection: Any,
    cue: SectionCue | Mapping[str, Any],
) -> None:
    """Insert one section cue record."""

    payload = _table_payload(SECTION_CUES_TABLE_NAME, cue)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_song_cue(connection, payload["song_cue_id"])
    _require_non_negative_int(payload["section_order"], "section_order")
    _require_non_negative_int(payload["expected_duration"], "expected_duration")
    _insert_row(connection, SECTION_CUES_TABLE_NAME, payload)


def read_section_cue(connection: Any, section_cue_id: str) -> dict[str, Any] | None:
    """Read one section cue record by its primary key."""

    return _read_row_by_primary_key(connection, SECTION_CUES_TABLE_NAME, section_cue_id)


def read_section_cues_by_song_cue_id(
    connection: Any,
    song_cue_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read section cues for a song cue ordered by section_order."""

    _require_non_empty_string(song_cue_id, "song_cue_id")
    return _read_rows_where(
        connection,
        SECTION_CUES_TABLE_NAME,
        "song_cue_id",
        song_cue_id,
        order_by="section_order",
    )


def write_performance_action_receipt(
    connection: Any,
    receipt: PerformanceActionReceipt | Mapping[str, Any],
) -> None:
    """Insert one performance action receipt."""

    payload = _table_payload(PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME, receipt)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_performance_session(connection, payload["performance_session_id"])
    _insert_row(connection, PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME, payload)


def read_performance_action_receipt(
    connection: Any,
    performance_action_receipt_id: str,
) -> dict[str, Any] | None:
    """Read one performance action receipt by its primary key."""

    return _read_row_by_primary_key(
        connection,
        PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME,
        performance_action_receipt_id,
    )


def read_performance_action_receipts_by_performance_session_id(
    connection: Any,
    performance_session_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read performance action receipts for a session ordered by created_at."""

    _require_non_empty_string(performance_session_id, "performance_session_id")
    return _read_rows_where(
        connection,
        PERFORMANCE_ACTION_RECEIPTS_TABLE_NAME,
        "performance_session_id",
        performance_session_id,
        order_by="created_at",
    )


def write_manual_override_event(
    connection: Any,
    event: ManualOverrideEvent | Mapping[str, Any],
) -> None:
    """Insert one manual override event."""

    payload = _table_payload(MANUAL_OVERRIDE_EVENTS_TABLE_NAME, event)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_performance_session(connection, payload["performance_session_id"])
    _insert_row(connection, MANUAL_OVERRIDE_EVENTS_TABLE_NAME, payload)


def read_manual_override_event(
    connection: Any,
    manual_override_event_id: str,
) -> dict[str, Any] | None:
    """Read one manual override event by its primary key."""

    return _read_row_by_primary_key(
        connection,
        MANUAL_OVERRIDE_EVENTS_TABLE_NAME,
        manual_override_event_id,
    )


def read_manual_override_events_by_performance_session_id(
    connection: Any,
    performance_session_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read manual override events for a session ordered by created_at."""

    _require_non_empty_string(performance_session_id, "performance_session_id")
    return _read_rows_where(
        connection,
        MANUAL_OVERRIDE_EVENTS_TABLE_NAME,
        "performance_session_id",
        performance_session_id,
        order_by="created_at",
    )


def write_highlight_marker(
    connection: Any,
    marker: HighlightMarker | Mapping[str, Any],
) -> None:
    """Insert one highlight marker record."""

    payload = _table_payload(HIGHLIGHT_MARKERS_TABLE_NAME, marker)
    _require_non_empty_string(payload["tenant_id"], "tenant_id")
    _require_existing_performance_session(connection, payload["performance_session_id"])
    _insert_row(connection, HIGHLIGHT_MARKERS_TABLE_NAME, payload)


def read_highlight_marker(
    connection: Any,
    highlight_marker_id: str,
) -> dict[str, Any] | None:
    """Read one highlight marker record by its primary key."""

    return _read_row_by_primary_key(
        connection,
        HIGHLIGHT_MARKERS_TABLE_NAME,
        highlight_marker_id,
    )


def read_highlight_markers_by_performance_session_id(
    connection: Any,
    performance_session_id: str,
) -> tuple[dict[str, Any], ...]:
    """Read highlight markers for a session ordered by marker_time."""

    _require_non_empty_string(performance_session_id, "performance_session_id")
    return _read_rows_where(
        connection,
        HIGHLIGHT_MARKERS_TABLE_NAME,
        "performance_session_id",
        performance_session_id,
        order_by="marker_time",
    )


def read_record_ids_for_exact_label_seed(
    connection: Any,
    label_name: str,
    label_value: str,
    *,
    max_records: int = 8,
) -> tuple[str, ...]:
    """Return bounded candidate record IDs for one exact semantic label."""

    _require_non_empty_string(label_name, "label_name")
    _require_non_empty_string(label_value, "label_value")
    _require_positive_int(max_records, "max_records")
    rows = connection.execute(
        """
SELECT labels.target_record_id
FROM semantic_labels AS labels
INNER JOIN semantic_records AS records
  ON records.record_id = labels.target_record_id
WHERE labels.label_name = ? AND labels.label_value = ?
GROUP BY labels.target_record_id
ORDER BY labels.target_record_id
LIMIT ?
""".strip(),
        (label_name, label_value, max_records),
    ).fetchall()
    return tuple(row[0] for row in rows)


def read_record_ids_for_exact_provenance_ref_seed(
    connection: Any,
    provenance_ref_id: str,
    *,
    max_records: int = 8,
) -> tuple[str, ...]:
    """Return bounded candidate record IDs for one exact provenance ref ID."""

    _require_non_empty_string(provenance_ref_id, "provenance_ref_id")
    _require_positive_int(max_records, "max_records")
    rows = connection.execute(
        """
SELECT refs.target_record_id
FROM provenance_refs AS refs
INNER JOIN semantic_records AS records
  ON records.record_id = refs.target_record_id
WHERE refs.provenance_ref_id = ?
GROUP BY refs.target_record_id
ORDER BY refs.target_record_id
LIMIT ?
""".strip(),
        (provenance_ref_id, max_records),
    ).fetchall()
    return tuple(row[0] for row in rows)


def read_record_ids_for_exact_validation_seed(
    connection: Any,
    validator_name: str,
    validation_result: str,
    *,
    max_records: int = 8,
) -> tuple[str, ...]:
    """Return bounded candidate record IDs for one exact validation result."""

    _require_non_empty_string(validator_name, "validator_name")
    _require_non_empty_string(validation_result, "validation_result")
    _require_positive_int(max_records, "max_records")
    rows = connection.execute(
        """
SELECT receipts.validated_target
FROM validation_receipts AS receipts
INNER JOIN semantic_records AS records
  ON records.record_id = receipts.validated_target
WHERE receipts.validator_name = ? AND receipts.validation_result = ?
GROUP BY receipts.validated_target
ORDER BY receipts.validated_target
LIMIT ?
""".strip(),
        (validator_name, validation_result, max_records),
    ).fetchall()
    return tuple(row[0] for row in rows)


def read_record_ids_for_exact_operator_promotion_seed(
    connection: Any,
    promotion_scope: str,
    promoted_by_operator: int,
    *,
    max_records: int = 8,
) -> tuple[str, ...]:
    """Return bounded candidate record IDs for one exact operator boundary."""

    _require_non_empty_string(promotion_scope, "promotion_scope")
    _require_binary_int(promoted_by_operator, "promoted_by_operator")
    _require_positive_int(max_records, "max_records")
    rows = connection.execute(
        """
SELECT promotions.target_record_id
FROM operator_promotions AS promotions
INNER JOIN semantic_records AS records
  ON records.record_id = promotions.target_record_id
WHERE promotions.promotion_scope = ? AND promotions.promoted_by_operator = ?
GROUP BY promotions.target_record_id
ORDER BY promotions.target_record_id
LIMIT ?
""".strip(),
        (promotion_scope, promoted_by_operator, max_records),
    ).fetchall()
    return tuple(row[0] for row in rows)


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


def _require_existing_source_registry_entry(connection: Any, source_id: str) -> None:
    _require_non_empty_string(source_id, "source_id")
    if read_source_registry_entry(connection, source_id) is None:
        raise ValueError(f"unknown source registry reference: {source_id}")


def _require_existing_file_inventory_row(connection: Any, inventory_id: str) -> None:
    _require_non_empty_string(inventory_id, "inventory_id")
    if read_file_inventory_row(connection, inventory_id) is None:
        raise ValueError(f"unknown file inventory reference: {inventory_id}")


def _require_existing_openclaw_node(connection: Any, node_id: str) -> None:
    _require_non_empty_string(node_id, "node_id")
    if read_openclaw_node(connection, node_id) is None:
        raise ValueError(f"unknown OpenClaw node reference: {node_id}")


def _require_existing_runtime_component(connection: Any, component_id: str) -> None:
    _require_non_empty_string(component_id, "component_id")
    if read_runtime_component(connection, component_id) is None:
        raise ValueError(f"unknown runtime component reference: {component_id}")


def _require_existing_performance_session(
    connection: Any,
    performance_session_id: str,
) -> None:
    _require_non_empty_string(performance_session_id, "performance_session_id")
    if read_performance_session(connection, performance_session_id) is None:
        raise ValueError(
            f"unknown performance session reference: {performance_session_id}"
        )


def _require_existing_setlist(connection: Any, setlist_id: str) -> None:
    _require_non_empty_string(setlist_id, "setlist_id")
    if read_setlist(connection, setlist_id) is None:
        raise ValueError(f"unknown setlist reference: {setlist_id}")


def _require_existing_setlist_item(connection: Any, setlist_item_id: str) -> None:
    _require_non_empty_string(setlist_item_id, "setlist_item_id")
    if read_setlist_item(connection, setlist_item_id) is None:
        raise ValueError(f"unknown setlist item reference: {setlist_item_id}")


def _require_existing_song_cue(connection: Any, song_cue_id: str) -> None:
    _require_non_empty_string(song_cue_id, "song_cue_id")
    if read_song_cue(connection, song_cue_id) is None:
        raise ValueError(f"unknown song cue reference: {song_cue_id}")


def _require_tenant_matches_openclaw_node(
    connection: Any,
    node_id: str,
    tenant_id: str,
) -> None:
    _require_non_empty_string(tenant_id, "tenant_id")
    node_row = read_openclaw_node(connection, node_id)
    if node_row is None:
        raise ValueError(f"unknown OpenClaw node reference: {node_id}")
    if node_row["tenant_id"] != tenant_id:
        raise ValueError("tenant_id must match openclaw_nodes.tenant_id")


def _require_tenant_matches_runtime_component(
    connection: Any,
    component_id: str,
    tenant_id: str,
) -> None:
    _require_non_empty_string(tenant_id, "tenant_id")
    component_row = read_runtime_component(connection, component_id)
    if component_row is None:
        raise ValueError(f"unknown runtime component reference: {component_id}")
    if component_row["tenant_id"] != tenant_id:
        raise ValueError("tenant_id must match runtime_components.tenant_id")


def _require_component_belongs_to_node(
    connection: Any,
    component_id: str,
    node_id: str,
) -> None:
    _require_non_empty_string(node_id, "node_id")
    component_row = read_runtime_component(connection, component_id)
    if component_row is None:
        raise ValueError(f"unknown runtime component reference: {component_id}")
    if component_row["node_id"] != node_id:
        raise ValueError("component node_id must match runtime_components.node_id")


def _require_repository_table_name(table_name: str) -> str:
    if table_name not in REPOSITORY_TABLE_PRIMARY_KEYS:
        raise ValueError(f"unknown backend sqlite repository table: {table_name}")
    return table_name


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_binary_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value not in {0, 1}:
        raise ValueError(f"{field_name} must be 0 or 1")


def _require_non_negative_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_positive_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_relative_inventory_path(value: Any) -> None:
    _require_non_empty_string(value, "relative_path")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("relative_path must be source-relative")
    if len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}:
        raise ValueError("relative_path must not be an absolute drive path")
