import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_data_contract import (
    ContractDecision,
    ContractLabel,
    ContractState,
    KnowledgeLayer,
    REQUIRED_LABEL_BUNDLES_BY_LAYER,
    REQUIRED_WRITE_BACK_CAPTURE_LABELS,
    SemanticRecordProposal,
    classify_record_state,
    classify_semantic_record,
    is_accepted_knowledge,
    is_implementation_forbidden,
    missing_required_labels,
    missing_write_back_capture_labels,
    required_labels_for_layer,
    validate_field_bundle,
)


FULL_LABELS = frozenset(
    {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.CONFIDENCE,
        ContractLabel.SENSITIVITY,
        ContractLabel.AUTHORITY,
        ContractLabel.REVIEW_STATUS,
    }
)


def test_core_vocabulary_preserves_knowledge_compiler_layers_and_labels():
    assert {layer.value for layer in KnowledgeLayer} == {
        "raw layer",
        "compiled/wiki layer",
        "relationship layer",
        "synthesis layer",
        "write-back/capture layer",
    }

    assert REQUIRED_WRITE_BACK_CAPTURE_LABELS == frozenset(
        {
            ContractLabel.PROVENANCE,
            ContractLabel.FRESHNESS,
            ContractLabel.CONFIDENCE,
            ContractLabel.SENSITIVITY,
            ContractLabel.AUTHORITY,
            ContractLabel.REVIEW_STATUS,
        }
    )
    assert REQUIRED_WRITE_BACK_CAPTURE_LABELS == FULL_LABELS

    assert {state.value for state in ContractState} >= {
        "confirmed",
        "inferred",
        "excluded",
        "unknown",
        "blocked",
        "stale",
        "confirmed-as-interpretation",
        "draft",
        "needs review",
    }


def test_each_layer_has_required_field_bundle_labels():
    assert set(REQUIRED_LABEL_BUNDLES_BY_LAYER) == set(KnowledgeLayer)

    for layer in KnowledgeLayer:
        assert required_labels_for_layer(layer) == FULL_LABELS
        assert REQUIRED_LABEL_BUNDLES_BY_LAYER[layer] == FULL_LABELS


def test_forbidden_implementation_concepts_are_not_authorized():
    forbidden_uses = (
        "build a CLI command",
        "create SQLite persistence",
        "define API endpoints",
        "invoke an MCP tool",
        "provider model call",
        "start an ingestion job",
        "run runtime services",
        "generate embeddings and indexing",
        "create frontend app code",
    )

    for proposed_use in forbidden_uses:
        assert is_implementation_forbidden(proposed_use) is True
        assert (
            classify_record_state(
                KnowledgeLayer.RAW,
                ContractState.CONFIRMED,
                proposed_use=proposed_use,
            )
            is ContractDecision.IMPLEMENTATION_FORBIDDEN
        )


def test_record_state_classifier_preserves_allowed_unknown_and_excluded_results():
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.CONFIRMED)
        is ContractDecision.ALLOWED
    )
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.UNKNOWN)
        is ContractDecision.UNKNOWN
    )
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.EXCLUDED)
        is ContractDecision.EXCLUDED
    )
    assert classify_record_state("new mystery layer", "confirmed") is ContractDecision.UNKNOWN


def test_write_back_capture_requires_contract_labels_before_allowed():
    partial_labels = {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.AUTHORITY,
    }
    assert missing_write_back_capture_labels(partial_labels) == frozenset(
        {
            ContractLabel.CONFIDENCE,
            ContractLabel.SENSITIVITY,
            ContractLabel.REVIEW_STATUS,
        }
    )

    assert (
        classify_record_state(
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=partial_labels,
            promoted_by_operator=True,
        )
        is ContractDecision.UNKNOWN
    )

    assert (
        classify_record_state(
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
            promoted_by_operator=True,
        )
        is ContractDecision.ALLOWED
    )


def test_valid_minimal_records_pass_field_bundle_validation():
    records = (
        SemanticRecordProposal(
            layer=KnowledgeLayer.RAW,
            state=ContractState.CONFIRMED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.COMPILED_WIKI,
            state=ContractState.CONFIRMED_AS_INTERPRETATION,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.RELATIONSHIP,
            state=ContractState.CONFIRMED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.SYNTHESIS,
            state=ContractState.INFERRED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
            state=ContractState.CONFIRMED_WITH_RECEIPT,
            labels=FULL_LABELS,
            promoted_by_operator=True,
        ),
    )

    for record in records:
        result = validate_field_bundle(record)
        assert result.ok is True
        assert result.reasons == ()


def test_missing_layer_labels_fail_with_useful_reasons():
    partial_labels = FULL_LABELS - {
        ContractLabel.CONFIDENCE,
        ContractLabel.REVIEW_STATUS,
    }
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.CONFIRMED,
        labels=partial_labels,
    )

    assert missing_required_labels(KnowledgeLayer.RAW, partial_labels) == frozenset(
        {ContractLabel.CONFIDENCE, ContractLabel.REVIEW_STATUS}
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "missing required labels for raw layer: confidence, review status",
    )


def test_synthesis_is_not_confirmed_truth_by_default():
    synthesis = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.INFERRED,
        labels=FULL_LABELS,
    )

    assert classify_semantic_record(synthesis) is ContractDecision.ALLOWED
    assert validate_field_bundle(synthesis).ok is True
    assert is_accepted_knowledge(synthesis) is False

    overstated_synthesis = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.CONFIRMED,
        labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
        promoted_by_operator=True,
    )
    assert classify_semantic_record(overstated_synthesis) is ContractDecision.UNKNOWN
    assert is_accepted_knowledge(overstated_synthesis) is False

    captured = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
        promoted_by_operator=True,
    )
    assert classify_semantic_record(captured) is ContractDecision.ALLOWED
    assert is_accepted_knowledge(captured) is True


def test_write_back_capture_needs_promotion_for_valid_record_and_acceptance():
    unpromoted = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
    )

    result = validate_field_bundle(unpromoted)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "write-back/capture confirmed receipt requires operator promotion",
    )
    assert is_accepted_knowledge(unpromoted) is False


def test_forbidden_implementation_concepts_fail_field_bundle_validation():
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        proposed_use="define API routes for a runtime service",
        promoted_by_operator=True,
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN
    assert result.reasons == (
        "implementation-forbidden proposed use cannot be accepted",
    )
    assert is_accepted_knowledge(record) is False


def test_unknown_and_excluded_states_cannot_confirm_accidentally():
    unknown = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.UNKNOWN,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )
    excluded = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.EXCLUDED,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )

    unknown_result = validate_field_bundle(unknown)
    assert unknown_result.ok is False
    assert unknown_result.decision is ContractDecision.UNKNOWN
    assert "unknown-style state cannot be treated as confirmed" in unknown_result.reasons

    excluded_result = validate_field_bundle(excluded)
    assert excluded_result.ok is False
    assert excluded_result.decision is ContractDecision.EXCLUDED
    assert "excluded-style state cannot be treated as confirmed" in excluded_result.reasons


def test_private_sensitive_promotion_requires_sensitivity_and_authority_labels():
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.COMPILED_WIKI,
        state=ContractState.SENSITIVE_LOCAL_ONLY,
        labels=FULL_LABELS - {ContractLabel.SENSITIVITY, ContractLabel.AUTHORITY},
        promoted_by_operator=True,
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert "private/sensitive promotion requires labels: authority, sensitivity" in result.reasons