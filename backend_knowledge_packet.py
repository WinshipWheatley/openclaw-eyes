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
class TraversedRecordContext:
    """One record reached by bounded relationship traversal."""

    record_id: str
    depth: int
    packet: RecordKnowledgePacket
    via_relationship_id: str | None = None
    previous_record_id: str | None = None
    relationship_direction: str | None = None


@dataclass(frozen=True)
class RelationshipTraversal:
    """Bounded deterministic walk over stored relationship rows."""

    root_record_id: str
    records: tuple[TraversedRecordContext, ...]
    max_depth: int
    max_records: int
    traversal_kind: str = "bounded_relationship_walk"
    traversal_strategy: str = "breadth_first_by_relationship_id"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"


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


@dataclass(frozen=True)
class TraversalBackedContextPacket:
    """Pure context packet assembled from a bounded relationship traversal."""

    root_record_id: str
    traversal: RelationshipTraversal
    synthesis_ready_records: tuple[SynthesisReadyReadModel, ...]
    context_kind: str = "traversal_backed_context_packet"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
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


def traverse_record_relationships(
    connection: Any,
    root_record_id: str,
    *,
    max_depth: int = 1,
    max_records: int = 8,
) -> RelationshipTraversal | None:
    """Walk relationship-linked records from one explicit root, within bounds."""

    _require_traversal_bounds(max_depth=max_depth, max_records=max_records)
    root_packet = assemble_record_knowledge_packet(connection, root_record_id)
    if root_packet is None:
        return None

    visited = {root_record_id}
    queued = [
        TraversedRecordContext(
            record_id=root_record_id,
            depth=0,
            packet=root_packet,
        )
    ]
    records: list[TraversedRecordContext] = []

    while queued and len(records) < max_records:
        current = queued.pop(0)
        records.append(current)
        if current.depth >= max_depth:
            continue

        for relationship in current.packet.relationships:
            related_record_id = _related_record_id(relationship, current.record_id)
            if related_record_id is None or related_record_id in visited:
                continue
            related_packet = assemble_record_knowledge_packet(
                connection,
                related_record_id,
            )
            if related_packet is None:
                continue
            visited.add(related_record_id)
            queued.append(
                TraversedRecordContext(
                    record_id=related_record_id,
                    depth=current.depth + 1,
                    packet=related_packet,
                    via_relationship_id=relationship["relationship_id"],
                    previous_record_id=current.record_id,
                    relationship_direction=_relationship_direction(
                        relationship,
                        current.record_id,
                    ),
                )
            )
            if len(records) + len(queued) >= max_records:
                break

    return RelationshipTraversal(
        root_record_id=root_record_id,
        records=tuple(records),
        max_depth=max_depth,
        max_records=max_records,
    )


def select_traversal_context_for_record(
    connection: Any,
    record_id: str,
    *,
    max_depth: int = 1,
    max_records: int = 8,
) -> TraversalBackedContextPacket | None:
    """Select a bounded relationship context packet by explicit record_id."""

    traversal = traverse_record_relationships(
        connection,
        record_id,
        max_depth=max_depth,
        max_records=max_records,
    )
    if traversal is None:
        return None
    return TraversalBackedContextPacket(
        root_record_id=record_id,
        traversal=traversal,
        synthesis_ready_records=tuple(
            synthesis_ready_read_model(record.packet)
            for record in traversal.records
        ),
    )


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


def traversal_as_dict(traversal: RelationshipTraversal) -> dict[str, Any]:
    """Return a deterministic plain-Python traversal representation."""

    return asdict(traversal)


def traversal_context_packet_as_dict(
    context_packet: TraversalBackedContextPacket,
) -> dict[str, Any]:
    """Return a deterministic plain-Python traversal-context representation."""

    return asdict(context_packet)


def synthesis_ready_read_model_as_dict(
    read_model: SynthesisReadyReadModel,
) -> dict[str, Any]:
    """Return a deterministic plain-Python read-model representation."""

    return asdict(read_model)


def _require_traversal_bounds(*, max_depth: int, max_records: int) -> None:
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    if type(max_records) is not int or max_records < 1:
        raise ValueError("max_records must be a positive integer")


def _related_record_id(
    relationship: dict[str, Any],
    current_record_id: str,
) -> str | None:
    if relationship["from_record_id"] == current_record_id:
        return relationship["to_record_id"]
    if relationship["to_record_id"] == current_record_id:
        return relationship["from_record_id"]
    return None


def _relationship_direction(
    relationship: dict[str, Any],
    current_record_id: str,
) -> str:
    if relationship["from_record_id"] == current_record_id:
        return "outbound"
    return "inbound"
