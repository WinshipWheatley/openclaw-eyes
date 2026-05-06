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
        "sqlite",
        "sql ddl",
        "migration",
        "migrations",
        "persistence",
        "api",
        "api route",
        "api routes",
        "mcp",
        "model",
        "provider",
        "provider/model",
        "ingestion",
        "runtime",
        "runtime service",
        "service",
        "frontend",
        "app",
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


def schema_surface_names() -> tuple[str, ...]:
    return REQUIRED_SCHEMA_CONTRACT_SURFACES


def schema_contract_surfaces() -> tuple[SchemaContractSurface, ...]:
    return SCHEMA_CONTRACT_SURFACES


def schema_contract_surface(surface_name: str) -> SchemaContractSurface | None:
    normalized_name = normalize_schema_surface_name(surface_name)
    if normalized_name is None:
        return None
    return _SCHEMA_SURFACES_BY_NAME[normalized_name]


def is_schema_surface_known(surface_name: str) -> bool:
    return schema_contract_surface(surface_name) is not None


def required_schema_surface_fields(surface_name: str) -> frozenset[str]:
    surface = schema_contract_surface(surface_name)
    if surface is None:
        return frozenset()
    return surface.required_conceptual_fields


def _normalize_schema_field_name(field_name: object) -> str:
    return _normalize_phrase(field_name).replace(" ", "_")


def _format_schema_fields(field_names: Iterable[str]) -> str:
    return ", ".join(sorted(field_names))


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
    if forbidden_text and not is_implementation_forbidden(forbidden_text):
        reasons.append(
            f"schema surface {surface.name} missing forbidden implementation boundary"
        )

    if reasons:
        return ContractValidationResult(ContractDecision.UNKNOWN, tuple(reasons))
    return ContractValidationResult(ContractDecision.ALLOWED)


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
    "REQUIRED_WRITE_BACK_CAPTURE_LABELS",
    "SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR",
    "SCHEMA_CONTRACT_SURFACES",
    "SENSITIVE_OR_PRIVATE_STATES",
    "SchemaContractSurface",
    "SemanticRecordProposal",
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
    "missing_required_labels",
    "missing_write_back_capture_labels",
    "normalize_entity_family",
    "normalize_label",
    "normalize_layer",
    "normalize_schema_surface_name",
    "normalize_state",
    "normalized_labels",
    "required_labels_for_layer",
    "required_schema_surface_fields",
    "schema_contract_surface",
    "schema_contract_surfaces",
    "schema_surface_names",
    "validate_entity_family_record",
    "validate_field_bundle",
    "validate_schema_surface_definition",
]
