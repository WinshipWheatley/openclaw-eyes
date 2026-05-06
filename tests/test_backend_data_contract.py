import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_data_contract import (
    ContractDecision,
    ContractLabel,
    ContractState,
    KnowledgeLayer,
    REQUIRED_WRITE_BACK_CAPTURE_LABELS,
    SemanticRecordProposal,
    classify_record_state,
    classify_semantic_record,
    is_accepted_knowledge,
    is_implementation_forbidden,
    missing_write_back_capture_labels,
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


def test_synthesis_is_not_confirmed_truth_by_default():
    synthesis = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.INFERRED,
    )

    assert classify_semantic_record(synthesis) is ContractDecision.ALLOWED
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