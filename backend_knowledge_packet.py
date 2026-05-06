"""Deterministic knowledge-packet read models over backend SQLite repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend_sqlite_repository import (
    read_record_labels,
    read_record_operator_promotions,
    read_record_provenance_refs,
    read_record_relationships,
    read_record_validation_receipts,
    read_semantic_record,
)


@dataclass(frozen=True)
class RecordKnowledgePacket:
    """Evidence/read-model material for one explicit semantic record."""

    record_id: str
    record: dict[str, Any]
    labels: tuple[dict[str, Any], ...]
    provenance_refs: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    validation_receipts: tuple[dict[str, Any], ...]
    operator_promotions: tuple[dict[str, Any], ...]
    packet_kind: str = "evidence_read_model"
    truth_status: str = "not_accepted_truth"


@dataclass(frozen=True)
class ContextSelection:
    """Bounded deterministic context selected by explicit record_id."""

    record_id: str
    packet: RecordKnowledgePacket
    selection_kind: str = "explicit_record_context"
    selection_strategy: str = "direct_record_id"
    bounded: bool = True
    includes_fuzzy_search: bool = False
    includes_vector_search: bool = False
    includes_model_calls: bool = False


@dataclass(frozen=True)
class SynthesisReadyReadModel:
    """Pure data prepared for later synthesis, without synthesizing truth."""

    record_id: str
    record: dict[str, Any]
    labels: tuple[dict[str, Any], ...]
    evidence_refs: tuple[dict[str, Any], ...]
    direct_relationships: tuple[dict[str, Any], ...]
    validation_receipts: tuple[dict[str, Any], ...]
    operator_promotions: tuple[dict[str, Any], ...]
    read_model_kind: str = "synthesis_ready_read_model"
    synthesis_status: str = "not_synthesized"
    accepted_truth_status: str = "not_accepted_truth"
    promotion_boundary: str = "operator_promotion_required"


def assemble_record_knowledge_packet(
    connection: Any,
    record_id: str,
) -> RecordKnowledgePacket | None:
    """Assemble deterministic evidence material for one explicit record_id."""

    record = read_semantic_record(connection, record_id)
    if record is None:
        return None
    return RecordKnowledgePacket(
        record_id=record_id,
        record=record,
        labels=read_record_labels(connection, record_id),
        provenance_refs=read_record_provenance_refs(connection, record_id),
        relationships=read_record_relationships(connection, record_id),
        validation_receipts=read_record_validation_receipts(connection, record_id),
        operator_promotions=read_record_operator_promotions(connection, record_id),
    )


def select_context_for_record(
    connection: Any,
    record_id: str,
) -> ContextSelection | None:
    """Select bounded deterministic context by explicit record_id only."""

    packet = assemble_record_knowledge_packet(connection, record_id)
    if packet is None:
        return None
    return ContextSelection(record_id=record_id, packet=packet)


def synthesis_ready_read_model(
    packet: RecordKnowledgePacket,
) -> SynthesisReadyReadModel:
    """Return a pure read model; no synthesis, model call, or promotion occurs."""

    return SynthesisReadyReadModel(
        record_id=packet.record_id,
        record=packet.record,
        labels=packet.labels,
        evidence_refs=packet.provenance_refs,
        direct_relationships=packet.relationships,
        validation_receipts=packet.validation_receipts,
        operator_promotions=packet.operator_promotions,
    )


def packet_has_explicit_operator_promotion(packet: RecordKnowledgePacket) -> bool:
    """Return True only for an explicit positive operator promotion row."""

    return any(
        promotion["promoted_by_operator"] == 1
        for promotion in packet.operator_promotions
    )


def packet_as_dict(packet: RecordKnowledgePacket) -> dict[str, Any]:
    """Return a deterministic plain-Python representation."""

    return asdict(packet)


def context_selection_as_dict(selection: ContextSelection) -> dict[str, Any]:
    """Return a deterministic plain-Python context-selection representation."""

    return asdict(selection)


def synthesis_ready_read_model_as_dict(
    read_model: SynthesisReadyReadModel,
) -> dict[str, Any]:
    """Return a deterministic plain-Python read-model representation."""

    return asdict(read_model)
