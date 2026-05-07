"""Deterministic knowledge-packet read models over backend SQLite repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend_sqlite_repository import (
    AgentContextProfile,
    ContextExportReceipt,
    read_active_agent_context_profile_by_role_and_task,
    read_record_labels,
    read_record_ids_for_exact_label_seed,
    read_record_ids_for_exact_operator_promotion_seed,
    read_record_ids_for_exact_provenance_ref_seed,
    read_record_ids_for_exact_validation_seed,
    read_record_operator_promotions,
    read_record_provenance_refs,
    read_record_relationships,
    read_record_validation_receipts,
    read_semantic_record,
    write_context_export_receipt,
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
class AgentContextRequest:
    """Explicit request for bounded context from a specific agent/actor."""

    tenant_id: str
    requesting_actor: str
    agent_role: str
    task_class: str
    seed_strategy: str
    seed_params: dict[str, Any]
    max_records: int = 20
    max_depth: int = 2


@dataclass(frozen=True)
class ContextOmission:
    """Explicit record of omitted/denied context without leaking private content."""

    record_id: str
    reason: str
    sensitivity_level: str = "unknown"


@dataclass(frozen=True)
class AgentContextExportDecision:
    """Result of an agent context access policy evaluation."""

    allowed: bool
    reason: str
    profile_id: str | None = None
    max_records: int = 0
    max_depth: int = 0
    sensitivity_ceiling: str = "unknown"


@dataclass(frozen=True)
class AgentContextExportPacket:
    """Bounded, deterministic, and policy-checked context packet for an agent."""

    tenant_id: str
    agent_role: str
    task_class: str
    context_profile_id: str
    export_receipt_id: str
    selections: tuple[ContextSelection, ...]
    omissions: tuple[ContextOmission, ...]
    packet_kind: str = "agent_context_export"
    truth_status: str = "not_accepted_truth"
    synthesized: bool = False


@dataclass(frozen=True)
class ExactLabelCandidateSeedSelection:
    """Bounded candidate seeds from one exact semantic label."""

    label_name: str
    label_value: str
    record_ids: tuple[str, ...]
    max_records: int
    records_returned: int
    seed_kind: str = "exact_semantic_label_seed"
    selection_strategy: str = "exact_label_match"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
    includes_fuzzy_match: bool = False
    includes_model_calls: bool = False
    ordered_by_record_id: bool = True


@dataclass(frozen=True)
class ExactProvenanceCandidateSeedSelection:
    """Bounded candidate seeds from one exact provenance ref ID."""

    provenance_ref_id: str
    record_ids: tuple[str, ...]
    max_records: int
    records_returned: int
    seed_kind: str = "exact_provenance_ref_seed"
    selection_strategy: str = "exact_provenance_ref_id_match"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
    includes_fuzzy_match: bool = False
    includes_model_calls: bool = False
    ordered_by_record_id: bool = True


@dataclass(frozen=True)
class ExactValidationCandidateSeedSelection:
    """Bounded candidate seeds from one exact validation result."""

    validator_name: str
    validation_result: str
    record_ids: tuple[str, ...]
    max_records: int
    records_returned: int
    seed_kind: str = "exact_validation_seed"
    selection_strategy: str = "exact_validator_result_match"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
    includes_fuzzy_match: bool = False
    includes_model_calls: bool = False
    ordered_by_record_id: bool = True


@dataclass(frozen=True)
class ExactOperatorPromotionCandidateSeedSelection:
    """Bounded candidate seeds from one exact operator-promotion boundary."""

    promotion_scope: str
    promoted_by_operator: int
    record_ids: tuple[str, ...]
    max_records: int
    records_returned: int
    seed_kind: str = "exact_operator_promotion_seed"
    selection_strategy: str = "exact_promotion_scope_and_flag_match"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
    includes_fuzzy_match: bool = False
    includes_model_calls: bool = False
    ordered_by_record_id: bool = True


@dataclass(frozen=True)
class TraversedRecordContext:
    """One record reached by bounded relationship traversal."""

    record_id: str
    depth: int
    packet: RecordKnowledgePacket
    via_relationship_id: str | None = None
    previous_record_id: str | None = None
    relationship_direction: str | None = None
    via_relationship_state: str | None = None
    via_relationship_provenance_refs: str | None = None


@dataclass(frozen=True)
class RelationshipTraversal:
    """Bounded deterministic walk over stored relationship rows."""

    root_record_id: str
    records: tuple[TraversedRecordContext, ...]
    max_depth: int
    max_records: int
    completed: bool
    truncated: bool
    truncation_reason: str | None
    records_returned: int
    max_depth_reached: int
    missing_related_record_ids: tuple[str, ...]
    skipped_relationship_ids: tuple[str, ...]
    integrity_findings: tuple[str, ...]
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


@dataclass(frozen=True)
class MultiSeedContextPacket:
    """Pure context packet assembled from explicit seed record IDs."""

    seed_record_ids: tuple[str, ...]
    records: tuple[TraversedRecordContext, ...]
    traversals: tuple[RelationshipTraversal, ...]
    synthesis_ready_records: tuple[SynthesisReadyReadModel, ...]
    max_seed_records: int
    max_depth: int
    max_records: int
    completed: bool
    truncated: bool
    truncation_reason: str | None
    records_returned: int
    max_depth_reached: int
    missing_seed_record_ids: tuple[str, ...]
    duplicate_seed_record_ids: tuple[str, ...]
    skipped_record_ids: tuple[str, ...]
    missing_related_record_ids: tuple[str, ...]
    skipped_relationship_ids: tuple[str, ...]
    integrity_findings: tuple[str, ...]
    context_kind: str = "multi_seed_context_packet"
    seed_ordering: str = "input_order"
    bounded: bool = True
    truth_status: str = "not_accepted_truth"
    synthesis_status: str = "not_synthesized"
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


def select_exact_label_candidate_seeds(
    connection: Any,
    label_name: str,
    label_value: str,
    *,
    max_records: int = 8,
) -> ExactLabelCandidateSeedSelection:
    """Select bounded candidate seed record IDs by exact label only."""

    record_ids = read_record_ids_for_exact_label_seed(
        connection,
        label_name,
        label_value,
        max_records=max_records,
    )
    return ExactLabelCandidateSeedSelection(
        label_name=label_name,
        label_value=label_value,
        record_ids=record_ids,
        max_records=max_records,
        records_returned=len(record_ids),
    )


def select_exact_provenance_candidate_seeds(
    connection: Any,
    provenance_ref_id: str,
    *,
    max_records: int = 8,
) -> ExactProvenanceCandidateSeedSelection:
    """Select bounded candidate seed record IDs by exact provenance ref ID."""

    record_ids = read_record_ids_for_exact_provenance_ref_seed(
        connection,
        provenance_ref_id,
        max_records=max_records,
    )
    return ExactProvenanceCandidateSeedSelection(
        provenance_ref_id=provenance_ref_id,
        record_ids=record_ids,
        max_records=max_records,
        records_returned=len(record_ids),
    )


def select_exact_validation_candidate_seeds(
    connection: Any,
    validator_name: str,
    validation_result: str,
    *,
    max_records: int = 8,
) -> ExactValidationCandidateSeedSelection:
    """Select bounded candidate seed record IDs by exact validation result."""

    record_ids = read_record_ids_for_exact_validation_seed(
        connection,
        validator_name,
        validation_result,
        max_records=max_records,
    )
    return ExactValidationCandidateSeedSelection(
        validator_name=validator_name,
        validation_result=validation_result,
        record_ids=record_ids,
        max_records=max_records,
        records_returned=len(record_ids),
    )


def select_exact_operator_promotion_candidate_seeds(
    connection: Any,
    promotion_scope: str,
    promoted_by_operator: int,
    *,
    max_records: int = 8,
) -> ExactOperatorPromotionCandidateSeedSelection:
    """Select bounded candidate seed IDs by exact operator-promotion boundary."""

    record_ids = read_record_ids_for_exact_operator_promotion_seed(
        connection,
        promotion_scope,
        promoted_by_operator,
        max_records=max_records,
    )
    return ExactOperatorPromotionCandidateSeedSelection(
        promotion_scope=promotion_scope,
        promoted_by_operator=promoted_by_operator,
        record_ids=record_ids,
        max_records=max_records,
        records_returned=len(record_ids),
    )


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
    truncation_reasons: list[str] = []
    missing_related_record_ids: list[str] = []
    skipped_relationship_ids: list[str] = []
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
            for relationship in current.packet.relationships:
                related_record_id = _related_record_id(
                    relationship,
                    current.record_id,
                )
                if related_record_id is None or related_record_id in visited:
                    continue
                _append_unique(truncation_reasons, "max_depth")
                _append_unique(
                    skipped_relationship_ids,
                    relationship["relationship_id"],
                )
            continue

        for relationship in current.packet.relationships:
            related_record_id = _related_record_id(relationship, current.record_id)
            if related_record_id is None or related_record_id in visited:
                continue
            if len(records) + len(queued) >= max_records:
                _append_unique(truncation_reasons, "max_records")
                _append_unique(
                    skipped_relationship_ids,
                    relationship["relationship_id"],
                )
                continue
            related_packet = assemble_record_knowledge_packet(
                connection,
                related_record_id,
            )
            if related_packet is None:
                _append_unique(missing_related_record_ids, related_record_id)
                _append_unique(
                    skipped_relationship_ids,
                    relationship["relationship_id"],
                )
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
                    via_relationship_state=relationship["relationship_state"],
                    via_relationship_provenance_refs=relationship["provenance_refs"],
                )
            )

    truncated = bool(truncation_reasons)
    integrity_findings = tuple(
        f"missing_related_record:{record_id}"
        for record_id in missing_related_record_ids
    )

    return RelationshipTraversal(
        root_record_id=root_record_id,
        records=tuple(records),
        max_depth=max_depth,
        max_records=max_records,
        completed=not truncated and not integrity_findings,
        truncated=truncated,
        truncation_reason=_combined_reason(truncation_reasons) if truncated else None,
        records_returned=len(records),
        max_depth_reached=max((record.depth for record in records), default=0),
        missing_related_record_ids=tuple(missing_related_record_ids),
        skipped_relationship_ids=tuple(skipped_relationship_ids),
        integrity_findings=integrity_findings,
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


def assemble_multi_seed_context(
    connection: Any,
    seed_record_ids: tuple[str, ...] | list[str],
    *,
    max_seed_records: int = 8,
    max_depth: int = 1,
    max_records: int = 16,
) -> MultiSeedContextPacket:
    """Assemble bounded context from explicit seed IDs in input order."""

    _require_traversal_bounds(max_depth=max_depth, max_records=max_records)
    _require_positive_int(max_seed_records, "max_seed_records")
    (
        normalized_seed_ids,
        duplicate_seed_record_ids,
        skipped_seed_record_ids,
    ) = _normalize_seed_record_ids(
        seed_record_ids,
        max_seed_records=max_seed_records,
    )
    traversals: list[RelationshipTraversal] = []
    records: list[TraversedRecordContext] = []
    included_record_ids: set[str] = set()
    missing_seed_record_ids: list[str] = []
    skipped_record_ids: list[str] = []
    missing_related_record_ids: list[str] = []
    skipped_relationship_ids: list[str] = []
    integrity_findings: list[str] = []
    truncation_reasons: list[str] = []
    if skipped_seed_record_ids:
        _append_unique(truncation_reasons, "max_seed_records")
        _extend_unique(skipped_record_ids, skipped_seed_record_ids)

    for seed_record_id in normalized_seed_ids:
        if len(records) >= max_records:
            _append_unique(truncation_reasons, "max_records")
            _append_unique(skipped_record_ids, seed_record_id)
            continue

        traversal = traverse_record_relationships(
            connection,
            seed_record_id,
            max_depth=max_depth,
            max_records=max_records - len(records),
        )
        if traversal is None:
            _append_unique(missing_seed_record_ids, seed_record_id)
            _append_unique(
                integrity_findings,
                f"missing_seed_record:{seed_record_id}",
            )
            continue

        traversals.append(traversal)
        if traversal.truncated and traversal.truncation_reason is not None:
            for reason in traversal.truncation_reason.split("_and_"):
                _append_unique(truncation_reasons, reason)
        _extend_unique(missing_related_record_ids, traversal.missing_related_record_ids)
        _extend_unique(skipped_relationship_ids, traversal.skipped_relationship_ids)
        _extend_unique(integrity_findings, traversal.integrity_findings)

        for record in traversal.records:
            if record.record_id in included_record_ids:
                _append_unique(skipped_record_ids, record.record_id)
                continue
            if len(records) >= max_records:
                _append_unique(truncation_reasons, "max_records")
                _append_unique(skipped_record_ids, record.record_id)
                continue
            records.append(record)
            included_record_ids.add(record.record_id)

    truncated = bool(truncation_reasons)
    return MultiSeedContextPacket(
        seed_record_ids=normalized_seed_ids,
        records=tuple(records),
        traversals=tuple(traversals),
        synthesis_ready_records=tuple(
            synthesis_ready_read_model(record.packet)
            for record in records
        ),
        max_seed_records=max_seed_records,
        max_depth=max_depth,
        max_records=max_records,
        completed=not truncated and not integrity_findings,
        truncated=truncated,
        truncation_reason=_combined_reason(truncation_reasons) if truncated else None,
        records_returned=len(records),
        max_depth_reached=max((record.depth for record in records), default=0),
        missing_seed_record_ids=tuple(missing_seed_record_ids),
        duplicate_seed_record_ids=duplicate_seed_record_ids,
        skipped_record_ids=tuple(skipped_record_ids),
        missing_related_record_ids=tuple(missing_related_record_ids),
        skipped_relationship_ids=tuple(skipped_relationship_ids),
        integrity_findings=tuple(integrity_findings),
    )


def assemble_context_from_exact_label_seed(
    connection: Any,
    label_name: str,
    label_value: str,
    *,
    seed_max_records: int = 8,
    max_depth: int = 1,
    max_records: int = 16,
) -> MultiSeedContextPacket:
    """Assemble context from one exact label seed selection."""

    selection = select_exact_label_candidate_seeds(
        connection,
        label_name,
        label_value,
        max_records=seed_max_records,
    )
    return assemble_multi_seed_context(
        connection,
        selection.record_ids,
        max_seed_records=seed_max_records,
        max_depth=max_depth,
        max_records=max_records,
    )


def assemble_context_from_exact_provenance_seed(
    connection: Any,
    provenance_ref_id: str,
    *,
    seed_max_records: int = 8,
    max_depth: int = 1,
    max_records: int = 16,
) -> MultiSeedContextPacket:
    """Assemble context from one exact provenance-ref seed selection."""

    selection = select_exact_provenance_candidate_seeds(
        connection,
        provenance_ref_id,
        max_records=seed_max_records,
    )
    return assemble_multi_seed_context(
        connection,
        selection.record_ids,
        max_seed_records=seed_max_records,
        max_depth=max_depth,
        max_records=max_records,
    )


def assemble_context_from_exact_validation_seed(
    connection: Any,
    validator_name: str,
    validation_result: str,
    *,
    seed_max_records: int = 8,
    max_depth: int = 1,
    max_records: int = 16,
) -> MultiSeedContextPacket:
    """Assemble context from one exact validation seed selection."""

    selection = select_exact_validation_candidate_seeds(
        connection,
        validator_name,
        validation_result,
        max_records=seed_max_records,
    )
    return assemble_multi_seed_context(
        connection,
        selection.record_ids,
        max_seed_records=seed_max_records,
        max_depth=max_depth,
        max_records=max_records,
    )


def assemble_context_from_exact_operator_promotion_seed(
    connection: Any,
    promotion_scope: str,
    promoted_by_operator: int,
    *,
    seed_max_records: int = 8,
    max_depth: int = 1,
    max_records: int = 16,
) -> MultiSeedContextPacket:
    """Assemble context from one exact operator-promotion seed selection."""

    selection = select_exact_operator_promotion_candidate_seeds(
        connection,
        promotion_scope,
        promoted_by_operator,
        max_records=seed_max_records,
    )
    return assemble_multi_seed_context(
        connection,
        selection.record_ids,
        max_seed_records=seed_max_records,
        max_depth=max_depth,
        max_records=max_records,
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


def exact_label_candidate_seed_selection_as_dict(
    selection: ExactLabelCandidateSeedSelection,
) -> dict[str, Any]:
    """Return a deterministic plain-Python candidate-seed representation."""

    return asdict(selection)


def exact_provenance_candidate_seed_selection_as_dict(
    selection: ExactProvenanceCandidateSeedSelection,
) -> dict[str, Any]:
    """Return a deterministic plain-Python candidate-seed representation."""

    return asdict(selection)


def exact_validation_candidate_seed_selection_as_dict(
    selection: ExactValidationCandidateSeedSelection,
) -> dict[str, Any]:
    """Return a deterministic plain-Python candidate-seed representation."""

    return asdict(selection)


def exact_operator_promotion_candidate_seed_selection_as_dict(
    selection: ExactOperatorPromotionCandidateSeedSelection,
) -> dict[str, Any]:
    """Return a deterministic plain-Python candidate-seed representation."""

    return asdict(selection)


def traversal_as_dict(traversal: RelationshipTraversal) -> dict[str, Any]:
    """Return a deterministic plain-Python traversal representation."""

    return asdict(traversal)


def traversal_context_packet_as_dict(
    context_packet: TraversalBackedContextPacket,
) -> dict[str, Any]:
    """Return a deterministic plain-Python traversal-context representation."""

    return asdict(context_packet)


def multi_seed_context_packet_as_dict(
    context_packet: MultiSeedContextPacket,
) -> dict[str, Any]:
    """Return a deterministic plain-Python multi-seed context representation."""

    return asdict(context_packet)


def agent_context_export_as_dict(packet: AgentContextExportPacket) -> dict[str, Any]:
    """Return a deterministic plain-Python representation for agent context export."""

    return asdict(packet)


def agent_context_request_as_dict(request: AgentContextRequest) -> dict[str, Any]:
    """Return a deterministic plain-Python representation for agent context request."""

    return asdict(request)


def agent_context_export_decision_as_dict(
    decision: AgentContextExportDecision,
) -> dict[str, Any]:
    """Return a deterministic plain-Python representation for agent export decision."""

    return asdict(decision)


def context_omission_as_dict(omission: ContextOmission) -> dict[str, Any]:
    """Return a deterministic plain-Python representation for context omission."""

    return asdict(omission)


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


def _require_positive_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")


def _normalize_seed_record_ids(
    seed_record_ids: tuple[str, ...] | list[str],
    *,
    max_seed_records: int,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if not isinstance(seed_record_ids, (tuple, list)):
        raise ValueError("seed_record_ids must be a tuple or list of record IDs")
    normalized: list[str] = []
    duplicate_seed_record_ids: list[str] = []
    skipped_seed_record_ids: list[str] = []
    for seed_record_id in seed_record_ids:
        if not isinstance(seed_record_id, str) or not seed_record_id:
            raise ValueError("seed record IDs must be non-empty strings")
        if seed_record_id in normalized:
            _append_unique(duplicate_seed_record_ids, seed_record_id)
            continue
        if len(normalized) >= max_seed_records:
            _append_unique(skipped_seed_record_ids, seed_record_id)
            continue
        normalized.append(seed_record_id)
    return (
        tuple(normalized),
        tuple(duplicate_seed_record_ids),
        tuple(skipped_seed_record_ids),
    )


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


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _extend_unique(items: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        _append_unique(items, value)


def _combined_reason(reasons: list[str]) -> str:
    return "_and_".join(reasons)


def evaluate_agent_context_access(
    connection: Any,
    request: AgentContextRequest,
) -> AgentContextExportDecision:
    """Evaluate if an agent context request is allowed by active profiles."""

    profile_row = read_active_agent_context_profile_by_role_and_task(
        connection,
        request.tenant_id,
        request.agent_role,
        request.task_class,
    )

    if profile_row is None:
        return AgentContextExportDecision(
            allowed=False,
            reason="no_active_profile_found",
        )

    # In this phase, we just check if the profile exists and is active.
    # Future hardening can add more granular capability/sensitivity checks.

    return AgentContextExportDecision(
        allowed=True,
        reason="active_profile_match",
        profile_id=profile_row["context_profile_id"],
        max_records=min(request.max_records, profile_row["max_records"]),
        max_depth=min(request.max_depth, profile_row["max_depth"]),
        sensitivity_ceiling=profile_row["sensitivity_ceiling"],
    )


def assemble_agent_context_export(
    connection: Any,
    request: AgentContextRequest,
    export_receipt_id: str,
    *,
    created_at: str,
) -> AgentContextExportPacket:
    """Assemble a policy-checked context export packet for an agent."""

    decision = evaluate_agent_context_access(connection, request)

    if not decision.allowed:
        # Write failure receipt
        write_context_export_receipt(
            connection,
            {
                "context_export_receipt_id": export_receipt_id,
                "tenant_id": request.tenant_id,
                "context_profile_id": "none",
                "requesting_actor": request.requesting_actor,
                "agent_role": request.agent_role,
                "task_class": request.task_class,
                "seed_strategy": request.seed_strategy,
                "records_returned": 0,
                "records_omitted": 0,
                "denied_reason": decision.reason,
                "export_status": "denied",
                "created_at": created_at,
            },
        )
        return AgentContextExportPacket(
            tenant_id=request.tenant_id,
            agent_role=request.agent_role,
            task_class=request.task_class,
            context_profile_id="none",
            export_receipt_id=export_receipt_id,
            selections=(),
            omissions=(),
        )

    # For now, we only support direct record_id seeding in this helper
    # Future versions will support multi-seed strategies.
    selections = []
    omissions = []

    if request.seed_strategy == "direct_record_id":
        record_id = request.seed_params.get("record_id")
        if record_id:
            # Check sensitivity ceiling if applicable
            # (Stub for now: everything is allowed if profile matches)
            packet = assemble_record_knowledge_packet(connection, record_id)
            selections.append(
                ContextSelection(
                    record_id=record_id,
                    packet=packet,
                    selection_strategy="direct_record_id",
                )
            )

    # Write success receipt
    write_context_export_receipt(
        connection,
        {
            "context_export_receipt_id": export_receipt_id,
            "tenant_id": request.tenant_id,
            "context_profile_id": decision.profile_id or "unknown",
            "requesting_actor": request.requesting_actor,
            "agent_role": request.agent_role,
            "task_class": request.task_class,
            "seed_strategy": request.seed_strategy,
            "records_returned": len(selections),
            "records_omitted": len(omissions),
            "denied_reason": "none",
            "export_status": "allowed",
            "created_at": created_at,
        },
    )

    return AgentContextExportPacket(
        tenant_id=request.tenant_id,
        agent_role=request.agent_role,
        task_class=request.task_class,
        context_profile_id=decision.profile_id or "unknown",
        export_receipt_id=export_receipt_id,
        selections=tuple(selections),
        omissions=tuple(omissions),
    )
