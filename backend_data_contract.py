"""Pure semantic vocabulary for the first backend/data-contract slice.

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


REQUIRED_WRITE_BACK_CAPTURE_LABELS = frozenset(
    {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.CONFIDENCE,
        ContractLabel.SENSITIVITY,
        ContractLabel.AUTHORITY,
        ContractLabel.REVIEW_STATUS,
    }
)

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
        "api",
        "mcp",
        "model",
        "provider",
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
    }
)


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

_STATE_ALIASES = {_normalize_phrase(state.value): state for state in ContractState}
_LABEL_ALIASES = {_normalize_phrase(label.value): label for label in ContractLabel}
_FORBIDDEN_CONCEPT_ALIASES = {
    _normalize_phrase(concept) for concept in IMPLEMENTATION_FORBIDDEN_CONCEPTS
}


def normalize_layer(layer: KnowledgeLayer | str) -> KnowledgeLayer | None:
    if isinstance(layer, KnowledgeLayer):
        return layer
    return _LAYER_ALIASES.get(_normalize_phrase(layer))


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
        layer is KnowledgeLayer.WRITE_BACK_CAPTURE
        and state is ContractState.CONFIRMED_WITH_RECEIPT
        and record.promoted_by_operator
        and not missing_write_back_capture_labels(record.labels)
        and classify_semantic_record(record) is ContractDecision.ALLOWED
    )


__all__ = [
    "ALLOWED_STATES_BY_LAYER",
    "ContractDecision",
    "ContractLabel",
    "ContractState",
    "EXCLUDED_STYLE_STATES",
    "IMPLEMENTATION_FORBIDDEN_CONCEPTS",
    "KnowledgeLayer",
    "REQUIRED_WRITE_BACK_CAPTURE_LABELS",
    "SemanticRecordProposal",
    "UNKNOWN_STYLE_STATES",
    "classify_record_state",
    "classify_semantic_record",
    "is_accepted_knowledge",
    "is_implementation_forbidden",
    "missing_write_back_capture_labels",
    "normalize_label",
    "normalize_layer",
    "normalize_state",
    "normalized_labels",
]