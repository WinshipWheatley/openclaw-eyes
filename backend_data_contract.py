"""Pure semantic contract spine for backend/data-contract slices.

This module defines contract labels and guards only. It contains no CLI, DB,
SQLite, API, MCP, provider/model, ingestion, indexing, embedding, source-set,
runtime, service, frontend, app, or fixture behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Iterable


class ContractDecision(str, Enum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    EXCLUDED = "excluded"
    IMPLEMENTATION_FORBIDDEN = "implementation-forbidden"


class KnowledgeLayer(str, Enum):
    RAW = "raw layer"
    COMPILED_WIKI = "compiled/wiki layer"
    RELATIONSHIP = "relationship layer"
    SYNTHESIS = "synthesis layer"
    WRITE_BACK_CAPTURE = "write-back/capture layer"


class EntityFamily(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    CLIENT = "client"
    JOB = "job"
    INVOICE = "invoice"
    PAYMENT = "payment"
    PROJECT = "project"
    MUSIC_WORK = "music work"
    LEGAL_MATTER = "legal matter"
    TAX_MATTER = "tax matter"
    SOURCE_MATERIAL = "source material"
    COMPILED_PAGE = "compiled page"
    RELATIONSHIP = "relationship"
    SYNTHESIS = "synthesis"
    FOLLOW_UP_ACTION = "follow-up action"
    APPROVAL = "approval"
    BLOCKER = "blocker"
    SYSTEM_ARTIFACT = "system artifact"


class ContractLabel(str, Enum):
    PROVENANCE = "provenance"
    FRESHNESS = "freshness"
    CONFIDENCE = "confidence"
    SENSITIVITY = "sensitivity"
    AUTHORITY = "authority"
    REVIEW_STATUS = "review status"


class ContractState(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    STALE = "stale"
    SENSITIVE_LOCAL_ONLY = "sensitive/local-only"
    EVIDENCE_AVAILABLE = "evidence available"
    APPROVAL_PROMOTION_AVAILABLE = "approval/promotion available"
    CONTRADICTION_PRESENT = "contradiction present"
    PACKET_PREPARED = "packet prepared"
    CONTEXT_FILTER_BLOCKED = "context-filter blocked"
    NEEDS_REVIEW = "needs review"
    DRAFT = "draft"
    CONFIRMED_AS_INTERPRETATION = "confirmed-as-interpretation"
    CONFIRMED_WITH_RECEIPT = "confirmed with receipt"
    REJECTED = "rejected"
    HISTORICAL = "historical"
    SENSITIVE = "sensitive"
    QUARANTINED = "quarantined"
    PRIVATE_ROOT_EXCLUDED = "private-root-excluded"
    LOCAL_ONLY = "local-only"
    OWNER_REVIEW_REQUIRED = "owner-review-required"


@dataclass(frozen=True)
class SemanticRecordProposal:
    layer: KnowledgeLayer | str
    state: ContractState | str
    labels: frozenset[ContractLabel | str] = field(default_factory=frozenset)
    proposed_use: str = ""
    promoted_by_operator: bool = False


@dataclass(frozen=True)
class ContractValidationResult:
    decision: ContractDecision
    reasons: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.decision is ContractDecision.ALLOWED and not self.reasons


@dataclass(frozen=True)
class SchemaContractSurface:
    name: str
    purpose: str
    required_conceptual_fields: frozenset[str]
    forbidden_implementation_behavior: tuple[str, ...]
    knowledge_layers: frozenset[KnowledgeLayer] = field(default_factory=frozenset)
    entity_families: frozenset[EntityFamily] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SQLiteTableConcept:
    name: str
    purpose: str
    required_conceptual_fields: frozenset[str]
    related_schema_contract_surface: str
    forbidden_implementation_behavior: tuple[str, ...]
    knowledge_layers: frozenset[KnowledgeLayer] = field(default_factory=frozenset)
    can_directly_imply_accepted_truth: bool = False


REQUIRED_CONTRACT_LABELS = frozenset(
    {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.CONFIDENCE,
        ContractLabel.SENSITIVITY,
        ContractLabel.AUTHORITY,
        ContractLabel.REVIEW_STATUS,
    }
)
REQUIRED_WRITE_BACK_CAPTURE_LABELS = REQUIRED_CONTRACT_LABELS

REQUIRED_LABEL_BUNDLES_BY_LAYER = {
    KnowledgeLayer.RAW: REQUIRED_CONTRACT_LABELS,
    KnowledgeLayer.COMPILED_WIKI: REQUIRED_CONTRACT_LABELS,
    KnowledgeLayer.RELATIONSHIP: REQUIRED_CONTRACT_LABELS,
    KnowledgeLayer.SYNTHESIS: REQUIRED_CONTRACT_LABELS,
    KnowledgeLayer.WRITE_BACK_CAPTURE: REQUIRED_CONTRACT_LABELS,
}

UNKNOWN_STYLE_STATES = frozenset(
    {
        ContractState.UNKNOWN,
        ContractState.NEEDS_REVIEW,
        ContractState.QUARANTINED,
    }
)

EXCLUDED_STYLE_STATES = frozenset(
    {
        ContractState.EXCLUDED,
        ContractState.BLOCKED,
        ContractState.CONTEXT_FILTER_BLOCKED,
        ContractState.PRIVATE_ROOT_EXCLUDED,
        ContractState.LOCAL_ONLY,
        ContractState.OWNER_REVIEW_REQUIRED,
    }
)

SENSITIVE_OR_PRIVATE_STATES = frozenset(
    {
        ContractState.SENSITIVE,
        ContractState.SENSITIVE_LOCAL_ONLY,
        ContractState.PRIVATE_ROOT_EXCLUDED,
        ContractState.LOCAL_ONLY,
        ContractState.OWNER_REVIEW_REQUIRED,
    }
)

ALLOWED_STATES_BY_LAYER = {
    KnowledgeLayer.RAW: frozenset(
        {
            ContractState.CONFIRMED,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.EVIDENCE_AVAILABLE,
        }
    ),
    KnowledgeLayer.COMPILED_WIKI: frozenset(
        {
            ContractState.CONFIRMED_AS_INTERPRETATION,
            ContractState.DRAFT,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.SENSITIVE_LOCAL_ONLY,
            ContractState.NEEDS_REVIEW,
        }
    ),
    KnowledgeLayer.RELATIONSHIP: frozenset(
        {
            ContractState.CONFIRMED,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.CONTRADICTION_PRESENT,
            ContractState.NEEDS_REVIEW,
        }
    ),
    KnowledgeLayer.SYNTHESIS: frozenset(
        {
            ContractState.DRAFT,
            ContractState.INFERRED,
            ContractState.CONFIRMED_AS_INTERPRETATION,
            ContractState.CONTRADICTION_PRESENT,
            ContractState.STALE,
            ContractState.SENSITIVE_LOCAL_ONLY,
            ContractState.BLOCKED,
            ContractState.NEEDS_REVIEW,
        }
    ),
    KnowledgeLayer.WRITE_BACK_CAPTURE: frozenset(
        {
            ContractState.CONFIRMED_WITH_RECEIPT,
            ContractState.REJECTED,
            ContractState.HISTORICAL,
            ContractState.SENSITIVE,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.NEEDS_REVIEW,
        }
    ),
}

IMPLEMENTATION_FORBIDDEN_CONCEPTS = frozenset(
    {
        "cli",
        "command line",
        "db",
        "database",
        "database connection",
        "file i/o",
        "sqlite",
        "sqlite3",
        "sql ddl",
        "migration",
        "migrations",
        "persistence",
        "api",
        "api route",
        "api routes",
        "mcp",
        "mcps",
        "model",
        "provider",
        "provider/model",
        "ingestion",
        "runtime",
        "runtime service",
        "service",
        "frontend",
        "frontend/app behavior",
        "app",
        "app behavior",
        "schema",
        "embedding",
        "embeddings",
        "indexing",
        "index",
        "source set generation",
        "source-set generation",
        "hermes",
        "sync",
        "fixture",
        "fixtures",
        "extraction",
        "loader",
        "extractor",
        "chunking",
        "chunk",
        "automated sending",
        "auto send",
        "auto-send",
        "collection action",
        "external sending",
        "harassment",
        "private data",
        "private data inspection",
        "private root",
        "private root inspection",
    }
)

REQUIRED_SCHEMA_CONTRACT_SURFACES = (
    "semantic_record",
    "semantic_label",
    "semantic_relationship",
    "provenance_ref",
    "validation_receipt",
    "operator_promotion",
    "context_filter_receipt",
    "source_registry",
    "source_discovery_queue",
    "source_exclusion",
    "file_inventory",
    "storage_operation_receipt",
    "openclaw_node",
    "node_source_link",
    "source_authorization_scope",
    "runtime_component",
    "component_capability",
    "node_heartbeat",
    "component_heartbeat",
    "component_health_snapshot",
    "performance_session",
    "setlist",
    "setlist_item",
    "song_cue",
    "section_cue",
    "performance_action_receipt",
    "manual_override_event",
    "highlight_marker",
    "actor_profile",
    "agent_context_profile",
    "context_export_receipt",
)

REQUIRED_SQLITE_TABLE_CONCEPTS = (
    "semantic_records",
    "semantic_labels",
    "semantic_relationships",
    "provenance_refs",
    "validation_receipts",
    "operator_promotions",
    "context_filter_receipts",
    "source_registry",
    "source_discovery_queue",
    "source_exclusions",
    "file_inventory",
    "storage_operation_receipts",
    "openclaw_nodes",
    "node_source_links",
    "source_authorization_scopes",
    "runtime_components",
    "component_capabilities",
    "node_heartbeats",
    "component_heartbeats",
    "component_health_snapshots",
    "performance_sessions",
    "setlists",
    "setlist_items",
    "song_cues",
    "section_cues",
    "performance_action_receipts",
    "manual_override_events",
    "highlight_markers",
    "actor_profiles",
    "agent_context_profiles",
    "context_export_receipts",
)

SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR = (
    "SQLite implementation",
    "SQL DDL",
    "migration",
    "persistence",
    "API route",
    "ingestion",
    "indexing",
    "embedding",
    "runtime service",
    "fixture",
    "provider/model call",
    "Hermes",
    "MCP",
    "private-root inspection",
    "file I/O",
    "database connection",
)

SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR = (
    "SQLite implementation",
    "SQLite runtime",
    "sqlite3",
    "SQL DDL execution",
    "migration",
    "persistence",
    "database connection",
    "DB connections",
    "file I/O",
    "API route",
    "ingestion",
    "extraction",
    "indexing",
    "embedding",
    "fixture",
    "runtime service",
    "frontend/app behavior",
    "provider/model call",
    "Hermes",
    "MCP",
    "sync",
    "source-set generation",
    "private-root inspection",
    "app behavior",
)

STORAGE_INTELLIGENCE_ALLOWED_SOURCE_MODES = (
    "ignore",
    "guided_review",
    "inventory_only",
    "metadata_safe",
    "content_allowed",
    "private_vault",
)

STORAGE_INTELLIGENCE_OPERATOR_CLASSIFICATIONS = (
    "camera",
    "field_recorder",
    "archive",
    "music_projects",
    "video_projects",
    "backup",
    "legal_private",
    "client_delivery",
    "system_noise",
    "ignore",
    "unknown",
)

STORAGE_INTELLIGENCE_DISCOVERY_STATUSES = (
    "pending_approval",
    "approved",
    "ignored",
)

STORAGE_INTELLIGENCE_INVENTORY_STATUSES = (
    "discovered",
    "inventoried",
    "metadata_extracted",
    "content_extracted",
    "stale",
    "missing",
    "error",
)

STORAGE_INTELLIGENCE_SAFETY_TIERS = (
    "read_only",
    "reversible_copy",
    "move_after_verified_copy",
    "destructive_or_reformat",
)

STORAGE_INTELLIGENCE_EXECUTION_STATUSES = (
    "dry_run",
    "planned",
    "approved",
    "executed",
    "verified",
    "blocked",
    "failed",
)

ENVIRONMENT_INTELLIGENCE_NODE_ROLES = (
    "primary",
    "worker",
    "observer",
    "mobile",
    "source_only",
    "firm_workstation",
)

ENVIRONMENT_INTELLIGENCE_TRUST_STATUSES = (
    "unknown",
    "pending_approval",
    "approved",
    "revoked",
    "stale",
)

ENVIRONMENT_INTELLIGENCE_NODE_SOURCE_LINK_STATUSES = (
    "pending",
    "active",
    "revoked",
    "stale",
)

ENVIRONMENT_INTELLIGENCE_AUTHORIZATION_SCOPE_STATUSES = (
    "active",
    "expired",
    "revoked",
)

ENVIRONMENT_INTELLIGENCE_AUTHORIZED_ENTITY_FAMILIES = (
    "personal_project",
    "music_project",
    "video_project",
    "legal_matter",
    "client_delivery",
    "archive",
    "system",
)

RUNTIME_PRESENCE_COMPONENT_STATUSES = (
    "pending_approval",
    "approved",
    "active",
    "inactive",
    "revoked",
    "stale",
    "degraded",
    "unknown",
)

RUNTIME_PRESENCE_COMPONENT_ROLES = (
    "primary",
    "worker",
    "storage_runner",
    "hermes_sidecar",
    "web_capture_runner",
    "mobile_bridge",
    "control_surface_runner",
    "environment_runner",
    "discovery_runner",
    "unknown",
)

RUNTIME_PRESENCE_CAPABILITY_STATUSES = (
    "pending",
    "approved",
    "revoked",
    "stale",
)

RUNTIME_PRESENCE_HEALTH_STATUSES = (
    "healthy",
    "degraded",
    "stale",
    "critical",
    "unknown",
)

PERFORMANCE_SESSION_TYPES = (
    "live_show",
    "rehearsal",
    "studio_tracking",
    "livestream",
    "podcast",
    "soundcheck",
    "unknown",
)

PERFORMANCE_SESSION_STATUSES = (
    "planned",
    "ready",
    "active",
    "paused",
    "completed",
    "cancelled",
    "archived",
)

PERFORMANCE_SETLIST_ITEM_TYPES = (
    "song",
    "talk",
    "interlude",
    "break",
    "improvisation",
    "unknown",
)

PERFORMANCE_SONG_CUE_TYPES = (
    "song_start",
    "song_end",
    "intro",
    "verse",
    "chorus",
    "bridge",
    "solo",
    "outro",
    "talk",
    "vamp",
    "unknown",
)

PERFORMANCE_ACTION_STATUSES = (
    "dry_run",
    "planned",
    "approved",
    "blocked",
    "logged",
    "executed_later",
    "failed",
)

PERFORMANCE_ACTION_TIERS = (
    "read_only",
    "visual_safe",
    "audio_safe",
    "show_control",
    "requires_confirmation",
    "blocked_high_risk",
)

PERFORMANCE_OVERRIDE_TYPES = (
    "manual_override",
    "panic_safe_baseline",
    "cue_hold",
    "cue_skip",
    "cue_relock",
    "talk_mode",
    "vamp_mode",
)

PERFORMANCE_MARKER_SOURCES = (
    "operator",
    "footswitch",
    "control_surface",
    "system_suggestion",
    "imported",
)

AGENT_CONTEXT_EXPORT_AGENT_ROLES = (
    "primary_agent",
    "advisory_agent",
    "safety_agent",
    "legal_operator",
    "operator_harness",
    "future_agent",
    "unknown",
)

AGENT_CONTEXT_EXPORT_TASK_CLASSES = (
    "user_reply",
    "evidence_scan",
    "safety_review",
    "legal_review",
    "storage_planning",
    "runtime_status",
    "performance_planning",
    "handoff_generation",
    "future_task",
    "unknown",
)

AGENT_CONTEXT_EXPORT_CAPABILITY_SCOPES = (
    "personal",
    "firm",
    "legal",
    "music",
    "system",
    "unknown",
)

AGENT_CONTEXT_EXPORT_STATUSES = (
    "dry_run",
    "allowed",
    "denied",
    "omitted",
    "failed",
)

ACTOR_PROFILE_ACTOR_CLASSES = (
    "canonical",
    "advisory_sidecar",
    "build_worker",
    "cloud_sidecar",
    "local_sidecar",
    "human_operator",
    "future_actor",
    "unknown",
)

ACTOR_PROFILE_SENSITIVITY_CEILINGS = (
    "public",
    "non_sensitive",
    "sanitized",
    "sensitive_local",
    "private_strict",
    "tenant_strict",
    "unknown",
)

ACTOR_PROFILE_STATUSES = (
    "active",
    "inactive",
    "revoked",
    "pending",
    "archived",
)

_ALL_KNOWLEDGE_LAYERS = frozenset(KnowledgeLayer)
_ALL_ENTITY_FAMILIES = frozenset(EntityFamily)

SCHEMA_CONTRACT_SURFACES = (
    SchemaContractSurface(
        name="semantic_record",
        purpose=(
            "No-runtime semantic record envelope for future normalized semantic core "
            "storage planning."
        ),
        required_conceptual_fields=frozenset(
            {
                "record_id",
                "entity_family",
                "knowledge_layer",
                "contract_state",
                "provenance_refs",
                "freshness_refs",
                "confidence_label",
                "sensitivity_label",
                "authority_label",
                "review_status_label",
                "validator_decision",
                "synthesis_not_truth",
                "accepted_knowledge_derived",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
        entity_families=_ALL_ENTITY_FAMILIES,
    ),
    SchemaContractSurface(
        name="semantic_label",
        purpose="Explicit label boundary for provenance/freshness/confidence/sensitivity/authority/review status.",
        required_conceptual_fields=frozenset(
            {
                "label_id",
                "target_record_id",
                "label_name",
                "label_value",
                "label_basis",
                "review_status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
    ),
    SchemaContractSurface(
        name="semantic_relationship",
        purpose="Directional semantic link surface that preserves relationship meaning without making it truth.",
        required_conceptual_fields=frozenset(
            {
                "relationship_id",
                "from_record_id",
                "to_record_id",
                "relationship_kind",
                "relationship_state",
                "provenance_refs",
                "freshness_refs",
                "authority_label",
                "sensitivity_label",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=frozenset(
            {
                KnowledgeLayer.RELATIONSHIP,
                KnowledgeLayer.SYNTHESIS,
                KnowledgeLayer.WRITE_BACK_CAPTURE,
            }
        ),
    ),
    SchemaContractSurface(
        name="provenance_ref",
        purpose="Source-basis reference surface for approved context, manifests, bridges, packets, and receipts.",
        required_conceptual_fields=frozenset(
            {
                "provenance_ref_id",
                "target_record_id",
                "source_basis",
                "source_set_ref",
                "manifest_ref",
                "bridge_ref",
                "packet_ref",
                "receipt_ref",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
    ),
    SchemaContractSurface(
        name="validation_receipt",
        purpose="Static validation evidence surface; receipts do not create runtime, provider, or approval authority.",
        required_conceptual_fields=frozenset(
            {
                "receipt_id",
                "validated_target",
                "validator_name",
                "validation_result",
                "failure_reasons",
                "checked_at",
                "source_basis",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="operator_promotion",
        purpose="Scope-bound operator write-back/capture decision surface for accepted knowledge derivation.",
        required_conceptual_fields=frozenset(
            {
                "promotion_id",
                "target_record_id",
                "operator_decision",
                "receipt_ref",
                "promotion_scope",
                "promoted_by_operator",
                "complete_label_set",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=frozenset({KnowledgeLayer.WRITE_BACK_CAPTURE}),
    ),
    SchemaContractSurface(
        name="context_filter_receipt",
        purpose="Context package pass/warn/block/needs-review receipt surface before execution influence.",
        required_conceptual_fields=frozenset(
            {
                "context_filter_receipt_id",
                "context_package_ref",
                "filter_scope",
                "checked_inputs",
                "withheld_surfaces",
                "filter_outcome",
                "finding_summary",
                "review_route",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="source_registry",
        purpose=(
            "Approved source/device/server registry surface; discovery alone does "
            "not authorize source access."
        ),
        required_conceptual_fields=frozenset(
            {
                "source_id",
                "device_identity",
                "last_known_mount_path",
                "source_mode",
                "operator_classification",
                "approval_receipt_ref",
                "freshness_timestamp",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="source_discovery_queue",
        purpose=(
            "Discovered-but-not-approved source event surface; pending discovery "
            "does not imply source approval."
        ),
        required_conceptual_fields=frozenset(
            {
                "discovery_id",
                "device_identity",
                "detected_path",
                "detected_at",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="source_exclusion",
        purpose="Explicit source, folder, file, type, or sensitivity exclusion boundary.",
        required_conceptual_fields=frozenset(
            {
                "exclusion_id",
                "source_id",
                "pattern_type",
                "path_pattern",
                "exclusion_level",
                "reason",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="file_inventory",
        purpose=(
            "Approved-source file metadata inventory surface before content "
            "extraction; source_id plus relative_path is the durable identity."
        ),
        required_conceptual_fields=frozenset(
            {
                "inventory_id",
                "source_id",
                "relative_path",
                "file_size",
                "mtime",
                "hash_heuristic",
                "inventory_status",
                "last_seen_timestamp",
                "source_confidence",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="storage_operation_receipt",
        purpose=(
            "Evidence receipt surface for future dry-run and storage operations; "
            "receipt rows do not imply execution unless execution_status says so."
        ),
        required_conceptual_fields=frozenset(
            {
                "operation_id",
                "operation_type",
                "source_inventory_id",
                "target_path",
                "safety_tier",
                "checksum_verification",
                "operator_approval_ref",
                "execution_status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="openclaw_node",
        purpose=(
            "Approved OpenClaw-aware endpoint identity surface; node approval "
            "does not authorize source, content, network, or remote execution access."
        ),
        required_conceptual_fields=frozenset(
            {
                "node_id",
                "node_identity",
                "node_fingerprint",
                "trust_status",
                "identity_verified_at",
                "node_role",
                "tenant_id",
                "agent_version",
                "status",
                "operator_approval_ref",
                "first_seen",
                "last_seen",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="node_source_link",
        purpose=(
            "Explicit tenant-scoped link between an approved node and approved "
            "source; the link does not authorize content access."
        ),
        required_conceptual_fields=frozenset(
            {
                "link_id",
                "node_id",
                "source_id",
                "tenant_id",
                "status",
                "linked_at",
                "last_seen",
                "operator_approval_ref",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="source_authorization_scope",
        purpose=(
            "Explicit tenant-scoped source authorization for sensitive, legal, "
            "private, and matter workflows before any source/content handling."
        ),
        required_conceptual_fields=frozenset(
            {
                "scope_id",
                "source_id",
                "tenant_id",
                "authorized_entity_family",
                "authorized_entity_id",
                "operator_approval_ref",
                "expiration_timestamp",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="runtime_component",
        purpose=(
            "Tenant-scoped runtime component registration surface; component "
            "presence does not authorize source access or action execution."
        ),
        required_conceptual_fields=frozenset(
            {
                "component_id",
                "node_id",
                "tenant_id",
                "component_name",
                "component_instance_id",
                "component_role",
                "component_version",
                "status",
                "approval_receipt_ref",
                "registered_at",
                "last_seen",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="component_capability",
        purpose=(
            "Static component capability declaration surface; capabilities are "
            "metadata/authorization signals, not live execution."
        ),
        required_conceptual_fields=frozenset(
            {
                "capability_id",
                "component_id",
                "tenant_id",
                "capability_name",
                "capability_scope",
                "status",
                "approval_receipt_ref",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="node_heartbeat",
        purpose=(
            "Stored node heartbeat state surface; heartbeat records are data only "
            "and do not implement live heartbeat senders or receivers."
        ),
        required_conceptual_fields=frozenset(
            {
                "heartbeat_id",
                "node_id",
                "tenant_id",
                "reported_at",
                "heartbeat_ttl_seconds",
                "health_status",
                "status_message",
                "last_known_state",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="component_heartbeat",
        purpose=(
            "Stored component heartbeat state surface; component heartbeat records "
            "are data only and do not implement live polling."
        ),
        required_conceptual_fields=frozenset(
            {
                "heartbeat_id",
                "component_id",
                "node_id",
                "tenant_id",
                "reported_at",
                "heartbeat_ttl_seconds",
                "health_status",
                "status_message",
                "last_known_state",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="component_health_snapshot",
        purpose=(
            "Last-known component health/vitals surface as caller-provided plain "
            "data, without process scanning or runtime integration."
        ),
        required_conceptual_fields=frozenset(
            {
                "snapshot_id",
                "component_id",
                "node_id",
                "tenant_id",
                "captured_at",
                "health_status",
                "degraded_reason",
                "capabilities_reported",
                "version_reported",
                "last_known_state",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="performance_session",
        purpose="Inert show map boundary representing a bounded live performance or studio session.",
        required_conceptual_fields=frozenset(
            {
                "performance_session_id",
                "tenant_id",
                "session_name",
                "session_type",
                "planned_start",
                "actual_start",
                "actual_end",
                "status",
                "operator_approval_ref",
                "source_context_ref",
                "runtime_context_ref",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="setlist",
        purpose="Inert planned roadmap for a performance session.",
        required_conceptual_fields=frozenset(
            {
                "setlist_id",
                "tenant_id",
                "performance_session_id",
                "setlist_name",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="setlist_item",
        purpose="Inert ordered item in a performance setlist.",
        required_conceptual_fields=frozenset(
            {
                "setlist_item_id",
                "tenant_id",
                "setlist_id",
                "item_order",
                "item_type",
                "title",
                "semantic_record_id",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="song_cue",
        purpose="Inert planned song-level marker.",
        required_conceptual_fields=frozenset(
            {
                "song_cue_id",
                "tenant_id",
                "setlist_item_id",
                "cue_name",
                "cue_type",
                "cue_order",
                "expected_tempo",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="section_cue",
        purpose="Inert explicit section-level map marker.",
        required_conceptual_fields=frozenset(
            {
                "section_cue_id",
                "tenant_id",
                "song_cue_id",
                "section_name",
                "section_type",
                "section_order",
                "expected_duration",
                "safe_baseline_scene_ref",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="performance_action_receipt",
        purpose="Inert receipt or log for performance actions; execution is status-explicit.",
        required_conceptual_fields=frozenset(
            {
                "performance_action_receipt_id",
                "tenant_id",
                "performance_session_id",
                "action_type",
                "action_target",
                "action_tier",
                "requested_by",
                "approved_by",
                "status",
                "receipt_payload",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="manual_override_event",
        purpose="Inert explicit record of operator intervention overriding show control.",
        required_conceptual_fields=frozenset(
            {
                "manual_override_event_id",
                "tenant_id",
                "performance_session_id",
                "override_type",
                "override_reason",
                "affected_target",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="highlight_marker",
        purpose="Inert timestamped moment for later review or editing.",
        required_conceptual_fields=frozenset(
            {
                "highlight_marker_id",
                "tenant_id",
                "performance_session_id",
                "setlist_item_id",
                "marker_time",
                "marker_label",
                "marker_source",
                "notes",
                "status",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="actor_profile",
        purpose=(
            "Inert actor identity and trust profile surface upstream of context "
            "export; presence, profile trust, and export access do not grant action."
        ),
        required_conceptual_fields=frozenset(
            {
                "actor_profile_id",
                "tenant_id",
                "actor_role",
                "actor_class",
                "trust_tier",
                "sensitivity_ceiling",
                "capability_scope",
                "runtime_component_id",
                "model_policy_ref",
                "provider_policy_ref",
                "write_canonical_memory",
                "runtime_execution_authority",
                "requires_receipt",
                "allowed_export_formats",
                "status",
                "approval_receipt_ref",
                "created_at",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="agent_context_profile",
        purpose="Inert definition of approved context access profiles for agent/lane roles.",
        required_conceptual_fields=frozenset(
            {
                "context_profile_id",
                "tenant_id",
                "agent_role",
                "task_class",
                "capability_scope",
                "allowed_entity_family",
                "allowed_source_mode",
                "max_records",
                "max_depth",
                "sensitivity_ceiling",
                "model_policy_ref",
                "provider_policy_ref",
                "status",
                "approval_receipt_ref",
                "created_at",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
    SchemaContractSurface(
        name="context_export_receipt",
        purpose="Inert log for deterministic context export attempts/results.",
        required_conceptual_fields=frozenset(
            {
                "context_export_receipt_id",
                "tenant_id",
                "context_profile_id",
                "requesting_actor",
                "agent_role",
                "task_class",
                "seed_strategy",
                "records_returned",
                "records_omitted",
                "denied_reason",
                "export_status",
                "created_at",
            }
        ),
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    ),
)

SQLITE_TABLE_CONCEPTS = (
    SQLiteTableConcept(
        name="semantic_records",
        purpose=(
            "No-runtime table concept for the central semantic record envelope; "
            "it preserves layer, family, state, labels, and accepted-knowledge "
            "derivation inputs without creating storage."
        ),
        required_conceptual_fields=frozenset(
            {
                "record_id",
                "entity_family",
                "knowledge_layer",
                "contract_state",
                "validator_decision",
                "synthesis_not_truth",
                "accepted_knowledge_derived",
                "provenance_refs",
                "freshness_refs",
                "confidence_label",
                "sensitivity_label",
                "authority_label",
                "review_status_label",
            }
        ),
        related_schema_contract_surface="semantic_record",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
    ),
    SQLiteTableConcept(
        name="semantic_labels",
        purpose=(
            "No-runtime table concept for explicit provenance, freshness, "
            "confidence, sensitivity, authority, and review-status labels."
        ),
        required_conceptual_fields=frozenset(
            {
                "label_id",
                "target_record_id",
                "label_name",
                "label_value",
                "label_basis",
                "review_status",
            }
        ),
        related_schema_contract_surface="semantic_label",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
    ),
    SQLiteTableConcept(
        name="semantic_relationships",
        purpose=(
            "No-runtime table concept for directional semantic, responsibility, "
            "contradiction, provenance, freshness, authority, and sensitivity links."
        ),
        required_conceptual_fields=frozenset(
            {
                "relationship_id",
                "from_record_id",
                "to_record_id",
                "relationship_kind",
                "relationship_state",
                "provenance_refs",
                "freshness_refs",
                "authority_label",
                "sensitivity_label",
            }
        ),
        related_schema_contract_surface="semantic_relationship",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=frozenset(
            {
                KnowledgeLayer.RELATIONSHIP,
                KnowledgeLayer.SYNTHESIS,
                KnowledgeLayer.WRITE_BACK_CAPTURE,
            }
        ),
    ),
    SQLiteTableConcept(
        name="provenance_refs",
        purpose=(
            "No-runtime table concept for source-basis, source-set, manifest, "
            "bridge, packet, and receipt references without authority laundering."
        ),
        required_conceptual_fields=frozenset(
            {
                "provenance_ref_id",
                "target_record_id",
                "source_basis",
                "source_set_ref",
                "manifest_ref",
                "bridge_ref",
                "packet_ref",
                "receipt_ref",
            }
        ),
        related_schema_contract_surface="provenance_ref",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=_ALL_KNOWLEDGE_LAYERS,
    ),
    SQLiteTableConcept(
        name="validation_receipts",
        purpose=(
            "No-runtime table concept for static validation evidence; it does not "
            "grant implementation, runtime, approval, or truth authority."
        ),
        required_conceptual_fields=frozenset(
            {
                "receipt_id",
                "validated_target",
                "validator_name",
                "validation_result",
                "failure_reasons",
                "checked_at",
                "source_basis",
            }
        ),
        related_schema_contract_surface="validation_receipt",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="operator_promotions",
        purpose=(
            "No-runtime table concept for scope-bound operator write-back/capture "
            "decisions that can support accepted-knowledge derivation."
        ),
        required_conceptual_fields=frozenset(
            {
                "promotion_id",
                "target_record_id",
                "operator_decision",
                "receipt_ref",
                "promotion_scope",
                "promoted_by_operator",
                "complete_label_set",
            }
        ),
        related_schema_contract_surface="operator_promotion",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        knowledge_layers=frozenset({KnowledgeLayer.WRITE_BACK_CAPTURE}),
    ),
    SQLiteTableConcept(
        name="context_filter_receipts",
        purpose=(
            "No-runtime table concept for pass, warn, block, or needs-review "
            "context-filter outcomes before execution influence."
        ),
        required_conceptual_fields=frozenset(
            {
                "context_filter_receipt_id",
                "context_package_ref",
                "filter_scope",
                "checked_inputs",
                "withheld_surfaces",
                "filter_outcome",
                "finding_summary",
                "review_route",
            }
        ),
        related_schema_contract_surface="context_filter_receipt",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="source_registry",
        purpose=(
            "Static table concept for approved source/device/server registry rows; "
            "source modes bound future behavior and discovery does not imply approval."
        ),
        required_conceptual_fields=frozenset(
            {
                "source_id",
                "device_identity",
                "last_known_mount_path",
                "source_mode",
                "operator_classification",
                "approval_receipt_ref",
                "freshness_timestamp",
            }
        ),
        related_schema_contract_surface="source_registry",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="source_discovery_queue",
        purpose=(
            "Static table concept for discovered source events that remain pending "
            "until explicit approval, ignore, or other operator decision."
        ),
        required_conceptual_fields=frozenset(
            {
                "discovery_id",
                "device_identity",
                "detected_path",
                "detected_at",
                "status",
            }
        ),
        related_schema_contract_surface="source_discovery_queue",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="source_exclusions",
        purpose=(
            "Static table concept for first-class private, source, folder, file, "
            "type, and sensitivity exclusions."
        ),
        required_conceptual_fields=frozenset(
            {
                "exclusion_id",
                "source_id",
                "pattern_type",
                "path_pattern",
                "exclusion_level",
                "reason",
            }
        ),
        related_schema_contract_surface="source_exclusion",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="file_inventory",
        purpose=(
            "Static table concept for approved-source metadata inventory before "
            "content extraction; identity is source_id plus relative_path, not "
            "absolute path."
        ),
        required_conceptual_fields=frozenset(
            {
                "inventory_id",
                "source_id",
                "relative_path",
                "file_size",
                "mtime",
                "hash_heuristic",
                "inventory_status",
                "last_seen_timestamp",
                "source_confidence",
            }
        ),
        related_schema_contract_surface="file_inventory",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="storage_operation_receipts",
        purpose=(
            "Static table concept for storage-operation and dry-run receipts; "
            "safety tier and execution status preserve approval boundaries."
        ),
        required_conceptual_fields=frozenset(
            {
                "operation_id",
                "operation_type",
                "source_inventory_id",
                "target_path",
                "safety_tier",
                "checksum_verification",
                "operator_approval_ref",
                "execution_status",
            }
        ),
        related_schema_contract_surface="storage_operation_receipt",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="openclaw_nodes",
        purpose=(
            "Static table concept for OpenClaw-aware node identity, tenant, trust, "
            "and operator approval state without network communication authority."
        ),
        required_conceptual_fields=frozenset(
            {
                "node_id",
                "node_identity",
                "node_fingerprint",
                "trust_status",
                "identity_verified_at",
                "node_role",
                "tenant_id",
                "agent_version",
                "status",
                "operator_approval_ref",
                "first_seen",
                "last_seen",
            }
        ),
        related_schema_contract_surface="openclaw_node",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="node_source_links",
        purpose=(
            "Static table concept for explicit tenant-scoped node/source links; "
            "node approval and source approval remain separate."
        ),
        required_conceptual_fields=frozenset(
            {
                "link_id",
                "node_id",
                "source_id",
                "tenant_id",
                "status",
                "linked_at",
                "last_seen",
                "operator_approval_ref",
            }
        ),
        related_schema_contract_surface="node_source_link",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="source_authorization_scopes",
        purpose=(
            "Static table concept for scoped source authorization; tenant and "
            "authorized entity are required before sensitive/legal/private handling."
        ),
        required_conceptual_fields=frozenset(
            {
                "scope_id",
                "source_id",
                "tenant_id",
                "authorized_entity_family",
                "authorized_entity_id",
                "operator_approval_ref",
                "expiration_timestamp",
                "status",
            }
        ),
        related_schema_contract_surface="source_authorization_scope",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="runtime_components",
        purpose=(
            "Static table concept for tenant-scoped runtime component presence; "
            "presence is not trust, source access, or action permission."
        ),
        required_conceptual_fields=frozenset(
            {
                "component_id",
                "node_id",
                "tenant_id",
                "component_name",
                "component_instance_id",
                "component_role",
                "component_version",
                "status",
                "approval_receipt_ref",
                "registered_at",
                "last_seen",
            }
        ),
        related_schema_contract_surface="runtime_component",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="component_capabilities",
        purpose=(
            "Static table concept for bounded component capability declarations; "
            "capabilities do not execute behavior."
        ),
        required_conceptual_fields=frozenset(
            {
                "capability_id",
                "component_id",
                "tenant_id",
                "capability_name",
                "capability_scope",
                "status",
                "approval_receipt_ref",
            }
        ),
        related_schema_contract_surface="component_capability",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="node_heartbeats",
        purpose=(
            "Static table concept for recorded node heartbeat data; no live "
            "network, process, or service-manager behavior is authorized."
        ),
        required_conceptual_fields=frozenset(
            {
                "heartbeat_id",
                "node_id",
                "tenant_id",
                "reported_at",
                "heartbeat_ttl_seconds",
                "health_status",
                "status_message",
                "last_known_state",
            }
        ),
        related_schema_contract_surface="node_heartbeat",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="component_heartbeats",
        purpose=(
            "Static table concept for recorded component heartbeat data; no live "
            "polling, sockets, or runtime supervisor is authorized."
        ),
        required_conceptual_fields=frozenset(
            {
                "heartbeat_id",
                "component_id",
                "node_id",
                "tenant_id",
                "reported_at",
                "heartbeat_ttl_seconds",
                "health_status",
                "status_message",
                "last_known_state",
            }
        ),
        related_schema_contract_surface="component_heartbeat",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="component_health_snapshots",
        purpose=(
            "Static table concept for caller-provided component health/vitals "
            "snapshots without process scanning or adapter integration."
        ),
        required_conceptual_fields=frozenset(
            {
                "snapshot_id",
                "component_id",
                "node_id",
                "tenant_id",
                "captured_at",
                "health_status",
                "degraded_reason",
                "capabilities_reported",
                "version_reported",
                "last_known_state",
            }
        ),
        related_schema_contract_surface="component_health_snapshot",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="performance_sessions",
        purpose="Physical representation of a bounded live performance or studio session.",
        required_conceptual_fields=frozenset(
            {
                "performance_session_id",
                "tenant_id",
                "session_name",
                "session_type",
                "planned_start",
                "actual_start",
                "actual_end",
                "status",
                "operator_approval_ref",
                "source_context_ref",
                "runtime_context_ref",
            }
        ),
        related_schema_contract_surface="performance_session",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="setlists",
        purpose="Physical representation of an inert planned roadmap for a session.",
        required_conceptual_fields=frozenset(
            {
                "setlist_id",
                "tenant_id",
                "performance_session_id",
                "setlist_name",
                "status",
            }
        ),
        related_schema_contract_surface="setlist",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="setlist_items",
        purpose="Physical representation of an inert ordered item in a setlist.",
        required_conceptual_fields=frozenset(
            {
                "setlist_item_id",
                "tenant_id",
                "setlist_id",
                "item_order",
                "item_type",
                "title",
                "semantic_record_id",
                "status",
            }
        ),
        related_schema_contract_surface="setlist_item",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="song_cues",
        purpose="Physical representation of an inert planned song-level marker.",
        required_conceptual_fields=frozenset(
            {
                "song_cue_id",
                "tenant_id",
                "setlist_item_id",
                "cue_name",
                "cue_type",
                "cue_order",
                "expected_tempo",
                "status",
            }
        ),
        related_schema_contract_surface="song_cue",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="section_cues",
        purpose="Physical representation of an inert explicit section-level map marker.",
        required_conceptual_fields=frozenset(
            {
                "section_cue_id",
                "tenant_id",
                "song_cue_id",
                "section_name",
                "section_type",
                "section_order",
                "expected_duration",
                "safe_baseline_scene_ref",
                "status",
            }
        ),
        related_schema_contract_surface="section_cue",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="performance_action_receipts",
        purpose="Physical representation of a receipt or log for performance actions.",
        required_conceptual_fields=frozenset(
            {
                "performance_action_receipt_id",
                "tenant_id",
                "performance_session_id",
                "action_type",
                "action_target",
                "action_tier",
                "requested_by",
                "approved_by",
                "status",
                "receipt_payload",
            }
        ),
        related_schema_contract_surface="performance_action_receipt",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="manual_override_events",
        purpose="Physical representation of an explicit operator intervention.",
        required_conceptual_fields=frozenset(
            {
                "manual_override_event_id",
                "tenant_id",
                "performance_session_id",
                "override_type",
                "override_reason",
                "affected_target",
                "status",
            }
        ),
        related_schema_contract_surface="manual_override_event",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="highlight_markers",
        purpose="Physical representation of a timestamped moment for later review.",
        required_conceptual_fields=frozenset(
            {
                "highlight_marker_id",
                "tenant_id",
                "performance_session_id",
                "setlist_item_id",
                "marker_time",
                "marker_label",
                "marker_source",
                "notes",
                "status",
            }
        ),
        related_schema_contract_surface="highlight_marker",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="actor_profiles",
        purpose=(
            "Physical representation of actor identity, class, trust tier, "
            "capability scope, and receipt requirements before context export."
        ),
        required_conceptual_fields=frozenset(
            {
                "actor_profile_id",
                "tenant_id",
                "actor_role",
                "actor_class",
                "trust_tier",
                "sensitivity_ceiling",
                "capability_scope",
                "runtime_component_id",
                "model_policy_ref",
                "provider_policy_ref",
                "write_canonical_memory",
                "runtime_execution_authority",
                "requires_receipt",
                "allowed_export_formats",
                "status",
                "approval_receipt_ref",
                "created_at",
            }
        ),
        related_schema_contract_surface="actor_profile",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="agent_context_profiles",
        purpose="Physical representation of approved context access profiles.",
        required_conceptual_fields=frozenset(
            {
                "context_profile_id",
                "tenant_id",
                "agent_role",
                "task_class",
                "capability_scope",
                "allowed_entity_family",
                "allowed_source_mode",
                "max_records",
                "max_depth",
                "sensitivity_ceiling",
                "model_policy_ref",
                "provider_policy_ref",
                "status",
                "approval_receipt_ref",
                "created_at",
            }
        ),
        related_schema_contract_surface="agent_context_profile",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
    SQLiteTableConcept(
        name="context_export_receipts",
        purpose="Physical representation of context export attempt logs.",
        required_conceptual_fields=frozenset(
            {
                "context_export_receipt_id",
                "tenant_id",
                "context_profile_id",
                "requesting_actor",
                "agent_role",
                "task_class",
                "seed_strategy",
                "records_returned",
                "records_omitted",
                "denied_reason",
                "export_status",
                "created_at",
            }
        ),
        related_schema_contract_surface="context_export_receipt",
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    ),
)

EXCLUDED_ENTITY_FAMILY_NAMES = frozenset(
    {
        "secret",
        "credential",
        "provider prompt",
        "provider output",
        "runtime log",
        "runtime state",
        "private data",
        "private root",
        "private source content",
        "bank account",
        "legal private content",
        "tax private content",
    }
)

GENERAL_ENTITY_STATES = frozenset(
    {
        ContractState.CONFIRMED,
        ContractState.INFERRED,
        ContractState.EXCLUDED,
        ContractState.UNKNOWN,
        ContractState.STALE,
        ContractState.SENSITIVE_LOCAL_ONLY,
        ContractState.NEEDS_REVIEW,
    }
)
ACCOUNTABILITY_ENTITY_STATES = frozenset(
    {
        ContractState.CONFIRMED,
        ContractState.INFERRED,
        ContractState.EXCLUDED,
        ContractState.UNKNOWN,
        ContractState.BLOCKED,
        ContractState.STALE,
        ContractState.EVIDENCE_AVAILABLE,
        ContractState.CONTRADICTION_PRESENT,
        ContractState.NEEDS_REVIEW,
    }
)

ALLOWED_LAYERS_BY_ENTITY_FAMILY = {
    EntityFamily.PERSON: frozenset(KnowledgeLayer),
    EntityFamily.ORGANIZATION: frozenset(KnowledgeLayer),
    EntityFamily.CLIENT: frozenset(KnowledgeLayer),
    EntityFamily.JOB: frozenset(KnowledgeLayer),
    EntityFamily.INVOICE: frozenset(
        {
            KnowledgeLayer.RAW,
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.PAYMENT: frozenset(
        {
            KnowledgeLayer.RAW,
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.PROJECT: frozenset(KnowledgeLayer),
    EntityFamily.MUSIC_WORK: frozenset(KnowledgeLayer),
    EntityFamily.LEGAL_MATTER: frozenset(KnowledgeLayer),
    EntityFamily.TAX_MATTER: frozenset(KnowledgeLayer),
    EntityFamily.SOURCE_MATERIAL: frozenset(
        {
            KnowledgeLayer.RAW,
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
        }
    ),
    EntityFamily.COMPILED_PAGE: frozenset(
        {
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.SYNTHESIS,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.RELATIONSHIP: frozenset(
        {
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.SYNTHESIS,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.SYNTHESIS: frozenset(
        {
            KnowledgeLayer.SYNTHESIS,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.FOLLOW_UP_ACTION: frozenset(
        {
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.SYNTHESIS,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.APPROVAL: frozenset(
        {
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    ),
    EntityFamily.BLOCKER: frozenset(KnowledgeLayer),
    EntityFamily.SYSTEM_ARTIFACT: frozenset(KnowledgeLayer),
}

ALLOWED_STATES_BY_ENTITY_FAMILY = {
    EntityFamily.PERSON: GENERAL_ENTITY_STATES,
    EntityFamily.ORGANIZATION: GENERAL_ENTITY_STATES,
    EntityFamily.CLIENT: GENERAL_ENTITY_STATES,
    EntityFamily.JOB: ACCOUNTABILITY_ENTITY_STATES,
    EntityFamily.INVOICE: ACCOUNTABILITY_ENTITY_STATES,
    EntityFamily.PAYMENT: ACCOUNTABILITY_ENTITY_STATES,
    EntityFamily.PROJECT: GENERAL_ENTITY_STATES,
    EntityFamily.MUSIC_WORK: GENERAL_ENTITY_STATES
    | {ContractState.DRAFT, ContractState.CONFIRMED_AS_INTERPRETATION},
    EntityFamily.LEGAL_MATTER: GENERAL_ENTITY_STATES,
    EntityFamily.TAX_MATTER: GENERAL_ENTITY_STATES,
    EntityFamily.SOURCE_MATERIAL: frozenset(
        {
            ContractState.CONFIRMED,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.EVIDENCE_AVAILABLE,
        }
    ),
    EntityFamily.COMPILED_PAGE: frozenset(
        {
            ContractState.CONFIRMED_AS_INTERPRETATION,
            ContractState.DRAFT,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.SENSITIVE_LOCAL_ONLY,
            ContractState.NEEDS_REVIEW,
        }
    ),
    EntityFamily.RELATIONSHIP: frozenset(
        {
            ContractState.CONFIRMED,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.CONTRADICTION_PRESENT,
            ContractState.NEEDS_REVIEW,
        }
    ),
    EntityFamily.SYNTHESIS: frozenset(
        {
            ContractState.DRAFT,
            ContractState.INFERRED,
            ContractState.CONFIRMED_AS_INTERPRETATION,
            ContractState.CONTRADICTION_PRESENT,
            ContractState.STALE,
            ContractState.SENSITIVE_LOCAL_ONLY,
            ContractState.BLOCKED,
            ContractState.NEEDS_REVIEW,
            ContractState.CONFIRMED_WITH_RECEIPT,
        }
    ),
    EntityFamily.FOLLOW_UP_ACTION: frozenset(
        {
            ContractState.DRAFT,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.PACKET_PREPARED,
            ContractState.APPROVAL_PROMOTION_AVAILABLE,
            ContractState.NEEDS_REVIEW,
            ContractState.CONFIRMED_WITH_RECEIPT,
        }
    ),
    EntityFamily.APPROVAL: frozenset(
        {
            ContractState.CONFIRMED_WITH_RECEIPT,
            ContractState.APPROVAL_PROMOTION_AVAILABLE,
            ContractState.REJECTED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.NEEDS_REVIEW,
        }
    ),
    EntityFamily.BLOCKER: frozenset(
        {
            ContractState.BLOCKED,
            ContractState.NEEDS_REVIEW,
            ContractState.UNKNOWN,
            ContractState.EXCLUDED,
            ContractState.CONTRADICTION_PRESENT,
            ContractState.STALE,
        }
    ),
    EntityFamily.SYSTEM_ARTIFACT: frozenset(
        {
            ContractState.CONFIRMED,
            ContractState.INFERRED,
            ContractState.EXCLUDED,
            ContractState.UNKNOWN,
            ContractState.BLOCKED,
            ContractState.STALE,
            ContractState.EVIDENCE_AVAILABLE,
            ContractState.CONTEXT_FILTER_BLOCKED,
            ContractState.NEEDS_REVIEW,
            ContractState.CONFIRMED_WITH_RECEIPT,
        }
    ),
}


def _normalize_phrase(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    lowered = str(value).strip().lower().replace("_", " ").replace("-", " ")
    flattened = re.sub(r"[^a-z0-9/]+", " ", lowered)
    return re.sub(r"\s+", " ", flattened).strip()


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    return f" {normalized_phrase} " in f" {normalized_text} "


_LAYER_ALIASES = {
    _normalize_phrase(layer.value): layer for layer in KnowledgeLayer
} | {
    "raw": KnowledgeLayer.RAW,
    "compiled/wiki": KnowledgeLayer.COMPILED_WIKI,
    "compiled wiki": KnowledgeLayer.COMPILED_WIKI,
    "relationship": KnowledgeLayer.RELATIONSHIP,
    "synthesis": KnowledgeLayer.SYNTHESIS,
    "write back/capture": KnowledgeLayer.WRITE_BACK_CAPTURE,
    "write back capture": KnowledgeLayer.WRITE_BACK_CAPTURE,
}

_ENTITY_FAMILY_ALIASES = {
    _normalize_phrase(family.value): family for family in EntityFamily
} | {
    "music": EntityFamily.MUSIC_WORK,
    "song": EntityFamily.MUSIC_WORK,
    "legal": EntityFamily.LEGAL_MATTER,
    "tax": EntityFamily.TAX_MATTER,
    "source": EntityFamily.SOURCE_MATERIAL,
    "compiled/wiki page": EntityFamily.COMPILED_PAGE,
    "compiled wiki page": EntityFamily.COMPILED_PAGE,
    "follow up": EntityFamily.FOLLOW_UP_ACTION,
    "followup": EntityFamily.FOLLOW_UP_ACTION,
    "follow up action": EntityFamily.FOLLOW_UP_ACTION,
    "system": EntityFamily.SYSTEM_ARTIFACT,
}

_EXCLUDED_ENTITY_FAMILY_ALIASES = {
    _normalize_phrase(family) for family in EXCLUDED_ENTITY_FAMILY_NAMES
}

_STATE_ALIASES = {_normalize_phrase(state.value): state for state in ContractState}
_LABEL_ALIASES = {_normalize_phrase(label.value): label for label in ContractLabel}
_FORBIDDEN_CONCEPT_ALIASES = {
    _normalize_phrase(concept) for concept in IMPLEMENTATION_FORBIDDEN_CONCEPTS
}
_SCHEMA_SURFACES_BY_NAME = {
    surface.name: surface for surface in SCHEMA_CONTRACT_SURFACES
}
_SCHEMA_SURFACE_ALIASES = {
    _normalize_phrase(surface.name): surface.name for surface in SCHEMA_CONTRACT_SURFACES
} | {
    "semantic record": "semantic_record",
    "semantic records": "semantic_record",
    "record label": "semantic_label",
    "record labels": "semantic_label",
    "semantic label": "semantic_label",
    "semantic labels": "semantic_label",
    "semantic relationship": "semantic_relationship",
    "semantic relationships": "semantic_relationship",
    "provenance ref": "provenance_ref",
    "provenance refs": "provenance_ref",
    "provenance reference": "provenance_ref",
    "provenance references": "provenance_ref",
    "validation receipt": "validation_receipt",
    "validation receipts": "validation_receipt",
    "operator promotion": "operator_promotion",
    "operator promotions": "operator_promotion",
    "context filter receipt": "context_filter_receipt",
    "context filter receipts": "context_filter_receipt",
    "source registry": "source_registry",
    "source discovery": "source_discovery_queue",
    "source discovery queue": "source_discovery_queue",
    "source exclusion": "source_exclusion",
    "source exclusions": "source_exclusion",
    "file inventory": "file_inventory",
    "storage operation receipt": "storage_operation_receipt",
    "storage operation receipts": "storage_operation_receipt",
    "openclaw node": "openclaw_node",
    "openclaw nodes": "openclaw_node",
    "node source link": "node_source_link",
    "node source links": "node_source_link",
    "source authorization scope": "source_authorization_scope",
    "source authorization scopes": "source_authorization_scope",
    "runtime component": "runtime_component",
    "runtime components": "runtime_component",
    "component capability": "component_capability",
    "component capabilities": "component_capability",
    "node heartbeat": "node_heartbeat",
    "node heartbeats": "node_heartbeat",
    "component heartbeat": "component_heartbeat",
    "component heartbeats": "component_heartbeat",
    "component health snapshot": "component_health_snapshot",
    "component health snapshots": "component_health_snapshot",
    "performance session": "performance_session",
    "performance sessions": "performance_session",
    "setlist": "setlist",
    "setlists": "setlist",
    "setlist item": "setlist_item",
    "setlist items": "setlist_item",
    "song cue": "song_cue",
    "song cues": "song_cue",
    "section cue": "section_cue",
    "section cues": "section_cue",
    "performance action receipt": "performance_action_receipt",
    "performance action receipts": "performance_action_receipt",
    "manual override event": "manual_override_event",
    "manual override events": "manual_override_event",
    "highlight marker": "highlight_marker",
    "highlight markers": "highlight_marker",
    "agent context profile": "agent_context_profile",
    "agent context profiles": "agent_context_profile",
    "context export receipt": "context_export_receipt",
    "context export receipts": "context_export_receipt",
}
_SQLITE_TABLE_CONCEPTS_BY_NAME = {
    concept.name: concept for concept in SQLITE_TABLE_CONCEPTS
}
_SQLITE_TABLE_CONCEPT_ALIASES = {
    _normalize_phrase(concept.name): concept.name for concept in SQLITE_TABLE_CONCEPTS
} | {
    "semantic record": "semantic_records",
    "semantic records": "semantic_records",
    "semantic table": "semantic_records",
    "semantic label": "semantic_labels",
    "semantic labels": "semantic_labels",
    "record label": "semantic_labels",
    "record labels": "semantic_labels",
    "semantic relationship": "semantic_relationships",
    "semantic relationships": "semantic_relationships",
    "provenance ref": "provenance_refs",
    "provenance refs": "provenance_refs",
    "provenance reference": "provenance_refs",
    "provenance references": "provenance_refs",
    "validation receipt": "validation_receipts",
    "validation receipts": "validation_receipts",
    "operator promotion": "operator_promotions",
    "operator promotions": "operator_promotions",
    "context filter receipt": "context_filter_receipts",
    "context filter receipts": "context_filter_receipts",
    "source registry": "source_registry",
    "source discovery": "source_discovery_queue",
    "source discovery queue": "source_discovery_queue",
    "source exclusion": "source_exclusions",
    "source exclusions": "source_exclusions",
    "file inventory": "file_inventory",
    "storage operation receipt": "storage_operation_receipts",
    "storage operation receipts": "storage_operation_receipts",
    "openclaw node": "openclaw_nodes",
    "openclaw nodes": "openclaw_nodes",
    "node source link": "node_source_links",
    "node source links": "node_source_links",
    "source authorization scope": "source_authorization_scopes",
    "source authorization scopes": "source_authorization_scopes",
    "runtime component": "runtime_components",
    "runtime components": "runtime_components",
    "component capability": "component_capabilities",
    "component capabilities": "component_capabilities",
    "node heartbeat": "node_heartbeats",
    "node heartbeats": "node_heartbeats",
    "component heartbeat": "component_heartbeats",
    "component heartbeats": "component_heartbeats",
    "component health snapshot": "component_health_snapshots",
    "component health snapshots": "component_health_snapshots",
    "performance session": "performance_sessions",
    "performance sessions": "performance_sessions",
    "setlist": "setlists",
    "setlists": "setlists",
    "setlist item": "setlist_items",
    "setlist items": "setlist_items",
    "song cue": "song_cues",
    "song cues": "song_cues",
    "section cue": "section_cues",
    "section cues": "section_cues",
    "performance action receipt": "performance_action_receipts",
    "performance action receipts": "performance_action_receipts",
    "manual override event": "manual_override_events",
    "manual override events": "manual_override_events",
    "highlight marker": "highlight_markers",
    "highlight markers": "highlight_markers",
    "agent context profile": "agent_context_profiles",
    "agent context profiles": "agent_context_profiles",
    "context export receipt": "context_export_receipts",
    "context export receipts": "context_export_receipts",
}


def normalize_layer(layer: KnowledgeLayer | str) -> KnowledgeLayer | None:
    if isinstance(layer, KnowledgeLayer):
        return layer
    return _LAYER_ALIASES.get(_normalize_phrase(layer))


def normalize_entity_family(family: EntityFamily | str) -> EntityFamily | None:
    if isinstance(family, EntityFamily):
        return family
    return _ENTITY_FAMILY_ALIASES.get(_normalize_phrase(family))


def normalize_schema_surface_name(surface_name: str) -> str | None:
    return _SCHEMA_SURFACE_ALIASES.get(_normalize_phrase(surface_name))


def normalize_sqlite_table_concept_name(table_name: str) -> str | None:
    return _SQLITE_TABLE_CONCEPT_ALIASES.get(_normalize_phrase(table_name))


def schema_surface_names() -> tuple[str, ...]:
    return REQUIRED_SCHEMA_CONTRACT_SURFACES


def sqlite_table_concept_names() -> tuple[str, ...]:
    return REQUIRED_SQLITE_TABLE_CONCEPTS


def schema_contract_surfaces() -> tuple[SchemaContractSurface, ...]:
    return SCHEMA_CONTRACT_SURFACES


def sqlite_table_concepts() -> tuple[SQLiteTableConcept, ...]:
    return SQLITE_TABLE_CONCEPTS


def schema_contract_surface(surface_name: str) -> SchemaContractSurface | None:
    normalized_name = normalize_schema_surface_name(surface_name)
    if normalized_name is None:
        return None
    return _SCHEMA_SURFACES_BY_NAME[normalized_name]


def sqlite_table_concept(table_name: str) -> SQLiteTableConcept | None:
    normalized_name = normalize_sqlite_table_concept_name(table_name)
    if normalized_name is None:
        return None
    return _SQLITE_TABLE_CONCEPTS_BY_NAME[normalized_name]


def is_schema_surface_known(surface_name: str) -> bool:
    return schema_contract_surface(surface_name) is not None


def is_sqlite_table_concept_known(table_name: str) -> bool:
    return sqlite_table_concept(table_name) is not None


def required_schema_surface_fields(surface_name: str) -> frozenset[str]:
    surface = schema_contract_surface(surface_name)
    if surface is None:
        return frozenset()
    return surface.required_conceptual_fields


def required_sqlite_table_concept_fields(table_name: str) -> frozenset[str]:
    concept = sqlite_table_concept(table_name)
    if concept is None:
        return frozenset()
    return concept.required_conceptual_fields


def _normalize_schema_field_name(field_name: object) -> str:
    return _normalize_phrase(field_name).replace(" ", "_")


def _format_schema_fields(field_names: Iterable[str]) -> str:
    return ", ".join(sorted(field_names))


def _format_schema_boundaries(boundaries: Iterable[str]) -> str:
    return ", ".join(sorted(boundaries))


def validate_schema_surface_definition(
    surface_name: str,
    conceptual_fields: Iterable[str],
    *,
    forbidden_implementation_behavior: Iterable[str] = (),
) -> ContractValidationResult:
    surface = schema_contract_surface(surface_name)
    if surface is None:
        return ContractValidationResult(
            ContractDecision.UNKNOWN,
            (f"unknown schema surface: {surface_name}",),
        )

    supplied_fields = frozenset(
        _normalize_schema_field_name(field) for field in conceptual_fields
    )
    missing_fields = surface.required_conceptual_fields - supplied_fields
    reasons: list[str] = []

    if missing_fields:
        reasons.append(
            f"schema surface {surface.name} missing conceptual fields: "
            f"{_format_schema_fields(missing_fields)}"
        )

    forbidden_text = " ".join(forbidden_implementation_behavior)
    supplied_forbidden_boundaries = frozenset(
        _normalize_phrase(boundary) for boundary in forbidden_implementation_behavior
    )
    missing_forbidden_boundaries = tuple(
        boundary
        for boundary in surface.forbidden_implementation_behavior
        if _normalize_phrase(boundary) not in supplied_forbidden_boundaries
    )
    if missing_forbidden_boundaries:
        reasons.append(
            f"schema surface {surface.name} missing forbidden implementation behavior: "
            f"{_format_schema_boundaries(missing_forbidden_boundaries)}"
        )
    elif not is_implementation_forbidden(forbidden_text):
        reasons.append(
            f"schema surface {surface.name} missing forbidden implementation boundary"
        )

    if reasons:
        return ContractValidationResult(ContractDecision.UNKNOWN, tuple(reasons))
    return ContractValidationResult(ContractDecision.ALLOWED)


def validate_sqlite_table_concept_definition(
    table_name: str,
    conceptual_fields: Iterable[str],
    *,
    forbidden_implementation_behavior: Iterable[str] = (),
) -> ContractValidationResult:
    concept = sqlite_table_concept(table_name)
    if concept is None:
        return ContractValidationResult(
            ContractDecision.UNKNOWN,
            (f"unknown SQLite table concept: {table_name}",),
        )

    supplied_fields = frozenset(
        _normalize_schema_field_name(field) for field in conceptual_fields
    )
    missing_fields = concept.required_conceptual_fields - supplied_fields
    reasons: list[str] = []

    if missing_fields:
        reasons.append(
            f"SQLite table concept {concept.name} missing conceptual fields: "
            f"{_format_schema_fields(missing_fields)}"
        )

    forbidden_text = " ".join(forbidden_implementation_behavior)
    supplied_forbidden_boundaries = frozenset(
        _normalize_phrase(boundary) for boundary in forbidden_implementation_behavior
    )
    missing_forbidden_boundaries = tuple(
        boundary
        for boundary in concept.forbidden_implementation_behavior
        if _normalize_phrase(boundary) not in supplied_forbidden_boundaries
    )
    if missing_forbidden_boundaries:
        reasons.append(
            f"SQLite table concept {concept.name} missing forbidden implementation behavior: "
            f"{_format_schema_boundaries(missing_forbidden_boundaries)}"
        )
    elif not is_implementation_forbidden(forbidden_text):
        reasons.append(
            f"SQLite table concept {concept.name} missing forbidden implementation boundary"
        )

    if concept.can_directly_imply_accepted_truth:
        reasons.append(
            f"SQLite table concept {concept.name} cannot directly imply accepted truth"
        )

    if reasons:
        return ContractValidationResult(ContractDecision.UNKNOWN, tuple(reasons))
    return ContractValidationResult(ContractDecision.ALLOWED)


def table_concept_can_directly_imply_accepted_truth(table_name: str) -> bool:
    concept = sqlite_table_concept(table_name)
    return bool(concept and concept.can_directly_imply_accepted_truth)


def semantic_records_table_preserves_synthesis_not_truth() -> bool:
    concept = sqlite_table_concept("semantic_records")
    if concept is None:
        return False
    return (
        KnowledgeLayer.SYNTHESIS in concept.knowledge_layers
        and "synthesis_not_truth" in concept.required_conceptual_fields
        and "accepted_knowledge_derived" in concept.required_conceptual_fields
        and not concept.can_directly_imply_accepted_truth
    )


def sqlite_table_concepts_keep_receipts_and_promotion_separate() -> bool:
    required_separate = {
        "operator_promotions",
        "validation_receipts",
        "provenance_refs",
        "context_filter_receipts",
    }
    found = {concept.name for concept in SQLITE_TABLE_CONCEPTS}
    return required_separate <= found and len(required_separate) == len(
        {
            sqlite_table_concept(name).related_schema_contract_surface
            for name in required_separate
            if sqlite_table_concept(name) is not None
        }
    )


def entity_family_decision(family: EntityFamily | str) -> ContractDecision:
    if normalize_entity_family(family) is not None:
        return ContractDecision.ALLOWED
    if _normalize_phrase(family) in _EXCLUDED_ENTITY_FAMILY_ALIASES:
        return ContractDecision.EXCLUDED
    return ContractDecision.UNKNOWN


def is_entity_family_known(family: EntityFamily | str) -> bool:
    return entity_family_decision(family) is ContractDecision.ALLOWED


def is_entity_family_excluded(family: EntityFamily | str) -> bool:
    return entity_family_decision(family) is ContractDecision.EXCLUDED


def normalize_state(state: ContractState | str) -> ContractState | None:
    if isinstance(state, ContractState):
        return state
    return _STATE_ALIASES.get(_normalize_phrase(state))


def normalize_label(label: ContractLabel | str) -> ContractLabel | None:
    if isinstance(label, ContractLabel):
        return label
    return _LABEL_ALIASES.get(_normalize_phrase(label))


def normalized_labels(labels: Iterable[ContractLabel | str]) -> frozenset[ContractLabel]:
    return frozenset(
        normalized_label
        for label in labels
        if (normalized_label := normalize_label(label)) is not None
    )


def _format_labels(labels: Iterable[ContractLabel]) -> str:
    return ", ".join(sorted(label.value for label in labels))


def _format_layers(layers: Iterable[KnowledgeLayer]) -> str:
    return ", ".join(sorted(layer.value for layer in layers))


def required_labels_for_layer(layer: KnowledgeLayer | str) -> frozenset[ContractLabel]:
    normalized_layer = normalize_layer(layer)
    if normalized_layer is None:
        return frozenset()
    return REQUIRED_LABEL_BUNDLES_BY_LAYER[normalized_layer]


def missing_required_labels(
    layer: KnowledgeLayer | str,
    labels: Iterable[ContractLabel | str],
) -> frozenset[ContractLabel]:
    return required_labels_for_layer(layer) - normalized_labels(labels)


def allowed_layers_for_entity_family(
    family: EntityFamily | str,
) -> frozenset[KnowledgeLayer]:
    normalized_family = normalize_entity_family(family)
    if normalized_family is None:
        return frozenset()
    return ALLOWED_LAYERS_BY_ENTITY_FAMILY[normalized_family]


def allowed_states_for_entity_family(
    family: EntityFamily | str,
) -> frozenset[ContractState]:
    normalized_family = normalize_entity_family(family)
    if normalized_family is None:
        return frozenset()
    return ALLOWED_STATES_BY_ENTITY_FAMILY[normalized_family]


def is_implementation_forbidden(proposed_use: str | None) -> bool:
    if not proposed_use:
        return False
    normalized_use = _normalize_phrase(proposed_use)
    return any(
        _contains_phrase(normalized_use, forbidden_concept)
        for forbidden_concept in _FORBIDDEN_CONCEPT_ALIASES
    )


def missing_write_back_capture_labels(
    labels: Iterable[ContractLabel | str],
) -> frozenset[ContractLabel]:
    return REQUIRED_WRITE_BACK_CAPTURE_LABELS - normalized_labels(labels)


def validate_field_bundle(record: SemanticRecordProposal) -> ContractValidationResult:
    if is_implementation_forbidden(record.proposed_use):
        return ContractValidationResult(
            ContractDecision.IMPLEMENTATION_FORBIDDEN,
            ("implementation-forbidden proposed use cannot be accepted",),
        )

    layer = normalize_layer(record.layer)
    state = normalize_state(record.state)
    labels = normalized_labels(record.labels)
    reasons: list[str] = []

    if layer is None:
        reasons.append(f"unknown knowledge layer: {record.layer}")
    if state is None:
        reasons.append(f"unknown contract state: {record.state}")

    if layer is not None:
        missing_labels = REQUIRED_LABEL_BUNDLES_BY_LAYER[layer] - labels
        if missing_labels:
            reasons.append(
                f"missing required labels for {layer.value}: {_format_labels(missing_labels)}"
            )

    if layer is not None and state is not None:
        if state in UNKNOWN_STYLE_STATES:
            reasons.append("unknown-style state cannot be treated as confirmed")
        if state in EXCLUDED_STYLE_STATES:
            reasons.append("excluded-style state cannot be treated as confirmed")
        if state not in ALLOWED_STATES_BY_LAYER[layer]:
            reasons.append(f"state {state.value} is not allowed for {layer.value}")
        if layer is KnowledgeLayer.SYNTHESIS and state is ContractState.CONFIRMED:
            reasons.append("synthesis layer is not confirmed truth by default")
        if (
            layer is KnowledgeLayer.WRITE_BACK_CAPTURE
            and state is ContractState.CONFIRMED_WITH_RECEIPT
            and not record.promoted_by_operator
        ):
            reasons.append(
                "write-back/capture confirmed receipt requires operator promotion"
            )
        if record.promoted_by_operator and state in SENSITIVE_OR_PRIVATE_STATES:
            missing_promotion_labels = {
                ContractLabel.SENSITIVITY,
                ContractLabel.AUTHORITY,
            } - labels
            if missing_promotion_labels:
                reasons.append(
                    "private/sensitive promotion requires labels: "
                    f"{_format_labels(missing_promotion_labels)}"
                )

    if reasons:
        if state in EXCLUDED_STYLE_STATES:
            decision = ContractDecision.EXCLUDED
        else:
            decision = ContractDecision.UNKNOWN
        return ContractValidationResult(decision, tuple(reasons))

    return ContractValidationResult(ContractDecision.ALLOWED)


def validate_entity_family_record(
    family: EntityFamily | str,
    layer: KnowledgeLayer | str,
    state: ContractState | str,
    *,
    labels: Iterable[ContractLabel | str] = (),
    proposed_use: str = "",
    promoted_by_operator: bool = False,
) -> ContractValidationResult:
    if is_implementation_forbidden(proposed_use):
        return ContractValidationResult(
            ContractDecision.IMPLEMENTATION_FORBIDDEN,
            ("implementation-forbidden proposed use cannot be accepted",),
        )

    field_result = validate_field_bundle(
        SemanticRecordProposal(
            layer=layer,
            state=state,
            labels=frozenset(labels),
            proposed_use=proposed_use,
            promoted_by_operator=promoted_by_operator,
        )
    )
    normalized_family = normalize_entity_family(family)
    layer_value = normalize_layer(layer)
    state_value = normalize_state(state)
    family_decision = entity_family_decision(family)
    reasons: list[str] = list(field_result.reasons)

    if family_decision is ContractDecision.EXCLUDED:
        reasons.insert(0, f"excluded entity family cannot be accepted: {family}")
    elif family_decision is ContractDecision.UNKNOWN:
        reasons.insert(0, f"unknown entity family: {family}")

    if normalized_family is not None:
        allowed_layers = ALLOWED_LAYERS_BY_ENTITY_FAMILY[normalized_family]
        allowed_states = ALLOWED_STATES_BY_ENTITY_FAMILY[normalized_family]
        if layer_value is not None and layer_value not in allowed_layers:
            reasons.append(
                f"family {normalized_family.value} is not allowed in {layer_value.value}; "
                f"allowed layers: {_format_layers(allowed_layers)}"
            )
        if state_value is not None and state_value not in allowed_states:
            reasons.append(
                f"state {state_value.value} is not allowed for {normalized_family.value}"
            )

    if reasons:
        if field_result.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN:
            decision = ContractDecision.IMPLEMENTATION_FORBIDDEN
        elif (
            family_decision is ContractDecision.EXCLUDED
            or state_value in EXCLUDED_STYLE_STATES
        ):
            decision = ContractDecision.EXCLUDED
        else:
            decision = ContractDecision.UNKNOWN
        return ContractValidationResult(decision, tuple(reasons))

    return ContractValidationResult(ContractDecision.ALLOWED)


def classify_semantic_record(record: SemanticRecordProposal) -> ContractDecision:
    if is_implementation_forbidden(record.proposed_use):
        return ContractDecision.IMPLEMENTATION_FORBIDDEN

    layer = normalize_layer(record.layer)
    state = normalize_state(record.state)
    if layer is None or state is None:
        return ContractDecision.UNKNOWN
    if state in EXCLUDED_STYLE_STATES:
        return ContractDecision.EXCLUDED
    if state in UNKNOWN_STYLE_STATES:
        return ContractDecision.UNKNOWN
    if state not in ALLOWED_STATES_BY_LAYER[layer]:
        return ContractDecision.UNKNOWN
    if layer is KnowledgeLayer.WRITE_BACK_CAPTURE and missing_write_back_capture_labels(
        record.labels
    ):
        return ContractDecision.UNKNOWN
    if (
        layer is KnowledgeLayer.WRITE_BACK_CAPTURE
        and state is ContractState.CONFIRMED_WITH_RECEIPT
        and not record.promoted_by_operator
    ):
        return ContractDecision.UNKNOWN
    return ContractDecision.ALLOWED


def classify_record_state(
    layer: KnowledgeLayer | str,
    state: ContractState | str,
    *,
    labels: Iterable[ContractLabel | str] = (),
    proposed_use: str = "",
    promoted_by_operator: bool = False,
) -> ContractDecision:
    return classify_semantic_record(
        SemanticRecordProposal(
            layer=layer,
            state=state,
            labels=frozenset(labels),
            proposed_use=proposed_use,
            promoted_by_operator=promoted_by_operator,
        )
    )


def is_accepted_knowledge(record: SemanticRecordProposal) -> bool:
    layer = normalize_layer(record.layer)
    state = normalize_state(record.state)
    if layer is KnowledgeLayer.SYNTHESIS:
        return False
    return (
        validate_field_bundle(record).ok
        and layer is KnowledgeLayer.WRITE_BACK_CAPTURE
        and state is ContractState.CONFIRMED_WITH_RECEIPT
        and record.promoted_by_operator
    )


def is_entity_record_accepted_knowledge(
    family: EntityFamily | str,
    layer: KnowledgeLayer | str,
    state: ContractState | str,
    *,
    labels: Iterable[ContractLabel | str] = (),
    proposed_use: str = "",
    promoted_by_operator: bool = False,
) -> bool:
    layer_value = normalize_layer(layer)
    state_value = normalize_state(state)
    if layer_value is KnowledgeLayer.SYNTHESIS:
        return False
    return (
        validate_entity_family_record(
            family,
            layer,
            state,
            labels=labels,
            proposed_use=proposed_use,
            promoted_by_operator=promoted_by_operator,
        ).ok
        and layer_value is KnowledgeLayer.WRITE_BACK_CAPTURE
        and state_value is ContractState.CONFIRMED_WITH_RECEIPT
        and promoted_by_operator
    )


__all__ = [
    "ALLOWED_LAYERS_BY_ENTITY_FAMILY",
    "ALLOWED_STATES_BY_LAYER",
    "ALLOWED_STATES_BY_ENTITY_FAMILY",
    "ACTOR_PROFILE_ACTOR_CLASSES",
    "ACTOR_PROFILE_SENSITIVITY_CEILINGS",
    "ACTOR_PROFILE_STATUSES",
    "ContractDecision",
    "ContractLabel",
    "ContractState",
    "ContractValidationResult",
    "EntityFamily",
    "EXCLUDED_ENTITY_FAMILY_NAMES",
    "EXCLUDED_STYLE_STATES",
    "IMPLEMENTATION_FORBIDDEN_CONCEPTS",
    "KnowledgeLayer",
    "REQUIRED_CONTRACT_LABELS",
    "REQUIRED_LABEL_BUNDLES_BY_LAYER",
    "REQUIRED_SCHEMA_CONTRACT_SURFACES",
    "REQUIRED_SQLITE_TABLE_CONCEPTS",
    "REQUIRED_WRITE_BACK_CAPTURE_LABELS",
    "RUNTIME_PRESENCE_CAPABILITY_STATUSES",
    "RUNTIME_PRESENCE_COMPONENT_ROLES",
    "RUNTIME_PRESENCE_COMPONENT_STATUSES",
    "RUNTIME_PRESENCE_HEALTH_STATUSES",
    "SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR",
    "SCHEMA_CONTRACT_SURFACES",
    "SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR",
    "SQLITE_TABLE_CONCEPTS",
    "SENSITIVE_OR_PRIVATE_STATES",
    "SchemaContractSurface",
    "SemanticRecordProposal",
    "SQLiteTableConcept",
    "UNKNOWN_STYLE_STATES",
    "allowed_layers_for_entity_family",
    "allowed_states_for_entity_family",
    "classify_record_state",
    "classify_semantic_record",
    "entity_family_decision",
    "is_accepted_knowledge",
    "is_entity_family_excluded",
    "is_entity_family_known",
    "is_entity_record_accepted_knowledge",
    "is_implementation_forbidden",
    "is_schema_surface_known",
    "is_sqlite_table_concept_known",
    "missing_required_labels",
    "missing_write_back_capture_labels",
    "normalize_entity_family",
    "normalize_label",
    "normalize_layer",
    "normalize_schema_surface_name",
    "normalize_sqlite_table_concept_name",
    "normalize_state",
    "normalized_labels",
    "required_labels_for_layer",
    "required_schema_surface_fields",
    "required_sqlite_table_concept_fields",
    "schema_contract_surface",
    "schema_contract_surfaces",
    "schema_surface_names",
    "semantic_records_table_preserves_synthesis_not_truth",
    "sqlite_table_concept",
    "sqlite_table_concept_names",
    "sqlite_table_concepts",
    "sqlite_table_concepts_keep_receipts_and_promotion_separate",
    "table_concept_can_directly_imply_accepted_truth",
    "validate_entity_family_record",
    "validate_field_bundle",
    "validate_schema_surface_definition",
    "validate_sqlite_table_concept_definition",
]
