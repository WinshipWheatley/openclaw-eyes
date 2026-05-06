import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_knowledge_packet import (
    assemble_record_knowledge_packet,
    context_selection_as_dict,
    packet_as_dict,
    packet_has_explicit_operator_promotion,
    select_context_for_record,
    synthesis_ready_read_model,
    synthesis_ready_read_model_as_dict,
)
from backend_sqlite_repository import (
    OperatorPromotion,
    ProvenanceRef,
    SemanticLabel,
    SemanticRecord,
    SemanticRelationship,
    ValidationReceipt,
    write_operator_promotion,
    write_provenance_ref,
    write_semantic_label,
    write_semantic_record,
    write_semantic_relationship,
    write_validation_receipt,
)
from backend_sqlite_runtime import create_in_memory_connection


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = REPO_ROOT / "backend_knowledge_packet.py"


def module_ast() -> ast.Module:
    return ast.parse(PACKET_PATH.read_text(encoding="utf-8"))


def called_function_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def sample_semantic_record(record_id: str = "record-1") -> SemanticRecord:
    return SemanticRecord(
        record_id=record_id,
        entity_family="system artifact",
        knowledge_layer="synthesis layer",
        contract_state="draft",
        validator_decision="allowed",
        synthesis_not_truth=1,
        accepted_knowledge_derived=0,
        provenance_refs="planning-bridge:sample",
        freshness_refs="static-test",
        confidence_label="test-confidence",
        sensitivity_label="local-test-only",
        authority_label="repository-proof",
        review_status_label="needs review",
        document_id="doc-1",
        parent_record_id=None,
        section_path="1. sample",
        page_ref=None,
        summary_level="record",
        summary_text_ref="summary-ref-1",
    )


def populate_packet_fixture(connection):
    write_semantic_record(connection, sample_semantic_record("record-1"))
    write_semantic_record(connection, sample_semantic_record("record-2"))
    write_semantic_label(
        connection,
        SemanticLabel(
            label_id="label-1",
            target_record_id="record-1",
            label_name="confidence",
            label_value="test-confidence",
            label_basis="static test",
            review_status="needs review",
            source_label_ref=None,
        ),
    )
    write_provenance_ref(
        connection,
        ProvenanceRef(
            provenance_ref_id="prov-1",
            target_record_id="record-1",
            source_basis="test source",
            source_set_ref="source-set-1",
            manifest_ref="manifest-1",
            bridge_ref="bridge-1",
            packet_ref="packet-1",
            receipt_ref="receipt-1",
            document_id="doc-1",
            section_path="1. sample",
            page_ref=None,
        ),
    )
    write_semantic_relationship(
        connection,
        SemanticRelationship(
            relationship_id="rel-1",
            from_record_id="record-1",
            to_record_id="record-2",
            relationship_kind="supports",
            relationship_state="draft",
            provenance_refs="prov-1",
            freshness_refs="static-test",
            authority_label="repository-proof",
            sensitivity_label="local-test-only",
            relationship_scope="direct",
        ),
    )
    write_validation_receipt(
        connection,
        ValidationReceipt(
            receipt_id="receipt-1",
            validated_target="record-1",
            validator_name="static-test",
            validation_result="passed",
            failure_reasons="",
            checked_at="2026-05-06T00:00:00Z",
            source_basis="pytest",
            authority_boundary="repository-proof",
        ),
    )
    write_operator_promotion(
        connection,
        OperatorPromotion(
            promotion_id="promotion-1",
            target_record_id="record-1",
            operator_decision="accepted for review",
            receipt_ref="receipt-1",
            promotion_scope="test scope",
            promoted_by_operator=1,
            complete_label_set="confidence,sensitivity,authority,review",
            authority_boundary="operator explicit",
        ),
    )


def test_knowledge_packet_assembles_direct_record_evidence_material():
    connection = create_in_memory_connection()
    try:
        populate_packet_fixture(connection)

        packet = assemble_record_knowledge_packet(connection, "record-1")

        assert packet is not None
        assert packet.packet_kind == "evidence_read_model"
        assert packet.truth_status == "not_accepted_truth"
        assert packet.record["record_id"] == "record-1"
        assert [label["label_id"] for label in packet.labels] == ["label-1"]
        assert [ref["provenance_ref_id"] for ref in packet.provenance_refs] == [
            "prov-1"
        ]
        assert [rel["relationship_id"] for rel in packet.relationships] == ["rel-1"]
        assert [receipt["receipt_id"] for receipt in packet.validation_receipts] == [
            "receipt-1"
        ]
        assert [promotion["promotion_id"] for promotion in packet.operator_promotions] == [
            "promotion-1"
        ]
    finally:
        connection.close()


def test_missing_record_packet_and_context_selection_return_none():
    connection = create_in_memory_connection()
    try:
        assert assemble_record_knowledge_packet(connection, "missing-record") is None
        assert select_context_for_record(connection, "missing-record") is None
    finally:
        connection.close()


def test_context_selection_is_explicit_record_id_only_and_bounded():
    connection = create_in_memory_connection()
    try:
        populate_packet_fixture(connection)

        selection = select_context_for_record(connection, "record-1")

        assert selection is not None
        assert selection.record_id == "record-1"
        assert selection.selection_kind == "explicit_record_context"
        assert selection.selection_strategy == "direct_record_id"
        assert selection.bounded is True
        assert selection.includes_fuzzy_search is False
        assert selection.includes_vector_search is False
        assert selection.includes_model_calls is False
        assert selection.packet.record["record_id"] == "record-1"
    finally:
        connection.close()


def test_synthesis_ready_read_model_is_pure_data_not_synthesized_truth():
    connection = create_in_memory_connection()
    try:
        populate_packet_fixture(connection)
        packet = assemble_record_knowledge_packet(connection, "record-1")
        assert packet is not None

        read_model = synthesis_ready_read_model(packet)

        assert read_model.read_model_kind == "synthesis_ready_read_model"
        assert read_model.synthesis_status == "not_synthesized"
        assert read_model.accepted_truth_status == "not_accepted_truth"
        assert read_model.promotion_boundary == "operator_promotion_required"
        assert read_model.record["accepted_knowledge_derived"] == 0
        assert read_model.evidence_refs == packet.provenance_refs
        assert read_model.direct_relationships == packet.relationships
    finally:
        connection.close()


def test_packet_and_read_model_as_dict_are_deterministic_plain_python_data():
    connection = create_in_memory_connection()
    try:
        populate_packet_fixture(connection)
        packet = assemble_record_knowledge_packet(connection, "record-1")
        assert packet is not None
        selection = select_context_for_record(connection, "record-1")
        assert selection is not None
        read_model = synthesis_ready_read_model(packet)

        assert packet_as_dict(packet)["record_id"] == "record-1"
        assert context_selection_as_dict(selection)["selection_strategy"] == (
            "direct_record_id"
        )
        assert synthesis_ready_read_model_as_dict(read_model)["synthesis_status"] == (
            "not_synthesized"
        )
    finally:
        connection.close()


def test_operator_promotion_boundary_is_explicit_not_automatic_truth():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        packet_without_promotion = assemble_record_knowledge_packet(connection, "record-1")
        assert packet_without_promotion is not None
        assert packet_has_explicit_operator_promotion(packet_without_promotion) is False

        write_operator_promotion(
            connection,
            OperatorPromotion(
                promotion_id="promotion-1",
                target_record_id="record-1",
                operator_decision="accepted for review",
                receipt_ref="receipt-1",
                promotion_scope="test scope",
                promoted_by_operator=1,
                complete_label_set="confidence,sensitivity,authority,review",
                authority_boundary="operator explicit",
            ),
        )
        packet_with_promotion = assemble_record_knowledge_packet(connection, "record-1")
        assert packet_with_promotion is not None
        assert packet_has_explicit_operator_promotion(packet_with_promotion) is True
        assert packet_with_promotion.record["accepted_knowledge_derived"] == 0
    finally:
        connection.close()


def test_knowledge_packet_module_does_not_create_connections_or_forbidden_surfaces():
    source = PACKET_PATH.read_text(encoding="utf-8").lower()
    tree = module_ast()

    assert {
        "connect",
        "open",
        "read_text",
        "write_text",
        "executescript",
        "commit",
        "rollback",
    }.isdisjoint(called_function_names(tree))
    assert "sqlite3" not in source
    assert re.search(r"\bmigration(?!_state)\b", source) is None
    assert re.search(r"\bmigrate\b", source) is None
    assert re.search(r"\bingest(?:ion)?\b", source) is None
    assert re.search(r"\bextract(?:ion)?\b", source) is None
    assert re.search(r"\bindex(?:ing)?\b", source) is None
    assert re.search(r"\bfts\b", source) is None
    assert re.search(r"\bembedding(?:s)?\b", source) is None
    assert re.search(r"\bvector(?:s)?\b", source) is None
    assert re.search(r"\brag\b", source) is None
    assert re.search(r"\bpageindex\b", source) is None
    assert re.search(r"\bprovider\b", source) is None
    assert re.search(r"\bhermes\b", source) is None
    assert re.search(r"\bmcp\b", source) is None
    assert re.search(r"\bsync\b", source) is None
    assert re.search(r"\bapi\b", source) is None
    assert re.search(r"\bfrontend\b", source) is None
    assert re.search(r"\bapp\b", source) is None
