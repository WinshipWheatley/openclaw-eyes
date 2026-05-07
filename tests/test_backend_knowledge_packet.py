import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_knowledge_packet import (
    assemble_multi_seed_context,
    assemble_record_knowledge_packet,
    context_selection_as_dict,
    exact_label_candidate_seed_selection_as_dict,
    multi_seed_context_packet_as_dict,
    packet_as_dict,
    packet_has_explicit_operator_promotion,
    select_context_for_record,
    select_exact_label_candidate_seeds,
    select_traversal_context_for_record,
    synthesis_ready_read_model,
    synthesis_ready_read_model_as_dict,
    traversal_as_dict,
    traversal_context_packet_as_dict,
    traverse_record_relationships,
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


def write_relationship(
    connection,
    relationship_id: str,
    from_record_id: str,
    to_record_id: str,
    *,
    relationship_state: str = "draft",
):
    write_semantic_relationship(
        connection,
        SemanticRelationship(
            relationship_id=relationship_id,
            from_record_id=from_record_id,
            to_record_id=to_record_id,
            relationship_kind="supports",
            relationship_state=relationship_state,
            provenance_refs=f"prov:{relationship_id}",
            freshness_refs="static-test",
            authority_label="repository-proof",
            sensitivity_label="local-test-only",
            relationship_scope="direct",
        ),
    )


def populate_traversal_fixture(connection):
    for record_id in ("record-1", "record-2", "record-3", "record-4"):
        write_semantic_record(connection, sample_semantic_record(record_id))
    write_relationship(connection, "rel-b", "record-1", "record-2")
    write_relationship(
        connection,
        "rel-a",
        "record-1",
        "record-3",
        relationship_state="reviewed",
    )
    write_relationship(connection, "rel-c", "record-3", "record-4")


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


def test_exact_label_candidate_seed_selection_is_bounded_plain_data():
    connection = create_in_memory_connection()
    try:
        for record_id in ("record-c", "record-a", "record-b"):
            write_semantic_record(connection, sample_semantic_record(record_id))
            write_semantic_label(
                connection,
                SemanticLabel(
                    label_id=f"label-{record_id}",
                    target_record_id=record_id,
                    label_name="confidence",
                    label_value="test-confidence",
                    label_basis="static test",
                    review_status="needs review",
                    source_label_ref=None,
                ),
            )

        selection = select_exact_label_candidate_seeds(
            connection,
            "confidence",
            "test-confidence",
            max_records=2,
        )
        selection_dict = exact_label_candidate_seed_selection_as_dict(selection)

        assert selection.seed_kind == "exact_semantic_label_seed"
        assert selection.selection_strategy == "exact_label_match"
        assert selection.record_ids == ("record-a", "record-b")
        assert selection.records_returned == 2
        assert selection.max_records == 2
        assert selection.truth_status == "not_accepted_truth"
        assert selection.includes_fuzzy_match is False
        assert selection.includes_model_calls is False
        assert selection.ordered_by_record_id is True
        assert selection_dict["record_ids"] == ("record-a", "record-b")
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


def test_relationship_traversal_is_bounded_deterministic_and_state_aware():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        traversal = traverse_record_relationships(
            connection,
            "record-1",
            max_depth=2,
            max_records=4,
        )

        assert traversal is not None
        assert traversal.traversal_kind == "bounded_relationship_walk"
        assert traversal.traversal_strategy == "breadth_first_by_relationship_id"
        assert traversal.truth_status == "not_accepted_truth"
        assert traversal.completed is True
        assert traversal.truncated is False
        assert traversal.truncation_reason is None
        assert traversal.records_returned == 4
        assert traversal.max_depth_reached == 2
        assert traversal.missing_related_record_ids == ()
        assert traversal.skipped_relationship_ids == ()
        assert traversal.integrity_findings == ()
        assert [record.record_id for record in traversal.records] == [
            "record-1",
            "record-3",
            "record-2",
            "record-4",
        ]
        assert [record.depth for record in traversal.records] == [0, 1, 1, 2]
        assert traversal.records[1].via_relationship_id == "rel-a"
        assert traversal.records[1].relationship_direction == "outbound"
        assert traversal.records[1].via_relationship_state == "reviewed"
        assert traversal.records[1].via_relationship_provenance_refs == "prov:rel-a"
        assert traversal.records[1].packet.relationships[0]["relationship_state"] == (
            "reviewed"
        )
        assert traversal.records[1].packet.relationships[0]["provenance_refs"] == (
            "prov:rel-a"
        )
    finally:
        connection.close()


def test_relationship_traversal_respects_depth_and_record_bounds():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        depth_limited = traverse_record_relationships(
            connection,
            "record-1",
            max_depth=1,
            max_records=8,
        )
        record_limited = traverse_record_relationships(
            connection,
            "record-1",
            max_depth=2,
            max_records=2,
        )

        assert depth_limited is not None
        assert [record.record_id for record in depth_limited.records] == [
            "record-1",
            "record-3",
            "record-2",
        ]
        assert depth_limited.completed is False
        assert depth_limited.truncated is True
        assert depth_limited.truncation_reason == "max_depth"
        assert depth_limited.records_returned == 3
        assert depth_limited.max_depth_reached == 1
        assert depth_limited.skipped_relationship_ids == ("rel-c",)
        assert record_limited is not None
        assert [record.record_id for record in record_limited.records] == [
            "record-1",
            "record-3",
        ]
        assert record_limited.completed is False
        assert record_limited.truncated is True
        assert record_limited.truncation_reason == "max_records"
        assert record_limited.records_returned == 2
        assert record_limited.max_depth_reached == 1
        assert record_limited.skipped_relationship_ids == ("rel-b", "rel-c")
    finally:
        connection.close()


def test_relationship_traversal_fails_closed_for_missing_or_invalid_inputs():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        assert traverse_record_relationships(connection, "missing-record") is None
        with pytest.raises(ValueError):
            traverse_record_relationships(connection, "record-1", max_depth=-1)
        with pytest.raises(ValueError):
            traverse_record_relationships(connection, "record-1", max_records=0)
        with pytest.raises(ValueError):
            traverse_record_relationships(connection, "record-1", max_depth=True)
        with pytest.raises(ValueError):
            traverse_record_relationships(connection, "record-1", max_records=True)
    finally:
        connection.close()


def test_relationship_traversal_reports_missing_related_records_deterministically():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        connection.execute(
            """
INSERT INTO semantic_relationships (
  relationship_id,
  from_record_id,
  to_record_id,
  relationship_kind,
  relationship_state,
  provenance_refs,
  freshness_refs,
  authority_label,
  sensitivity_label,
  relationship_scope
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                "rel-missing",
                "record-1",
                "missing-record",
                "supports",
                "draft",
                "prov:rel-missing",
                "static-test",
                "repository-proof",
                "local-test-only",
                "direct",
            ),
        )

        traversal = traverse_record_relationships(
            connection,
            "record-1",
            max_depth=1,
            max_records=8,
        )

        assert traversal is not None
        assert traversal.completed is False
        assert traversal.truncated is False
        assert traversal.truncation_reason is None
        assert traversal.records_returned == 1
        assert traversal.missing_related_record_ids == ("missing-record",)
        assert traversal.skipped_relationship_ids == ("rel-missing",)
        assert traversal.integrity_findings == (
            "missing_related_record:missing-record",
        )
    finally:
        connection.close()


def test_traversal_context_packet_is_pure_bounded_read_model_material():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        context_packet = select_traversal_context_for_record(
            connection,
            "record-1",
            max_depth=1,
            max_records=3,
        )

        assert context_packet is not None
        assert context_packet.context_kind == "traversal_backed_context_packet"
        assert context_packet.bounded is True
        assert context_packet.truth_status == "not_accepted_truth"
        assert context_packet.promotion_boundary == "operator_promotion_required"
        assert context_packet.traversal.records_returned == 3
        assert context_packet.traversal.truncated is True
        assert context_packet.traversal.truncation_reason == "max_depth"
        assert [model.record_id for model in context_packet.synthesis_ready_records] == [
            "record-1",
            "record-3",
            "record-2",
        ]
        assert {
            model.synthesis_status for model in context_packet.synthesis_ready_records
        } == {"not_synthesized"}
        assert {
            model.accepted_truth_status
            for model in context_packet.synthesis_ready_records
        } == {"not_accepted_truth"}
    finally:
        connection.close()


def test_multi_seed_context_preserves_input_seed_order_and_dedupes_overlap():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        context_packet = assemble_multi_seed_context(
            connection,
            ("record-3", "record-1", "record-3"),
            max_seed_records=8,
            max_depth=2,
            max_records=8,
        )

        assert context_packet.context_kind == "multi_seed_context_packet"
        assert context_packet.seed_ordering == "input_order"
        assert context_packet.seed_record_ids == ("record-3", "record-1")
        assert context_packet.duplicate_seed_record_ids == ("record-3",)
        assert [record.record_id for record in context_packet.records] == [
            "record-3",
            "record-1",
            "record-4",
            "record-2",
        ]
        assert context_packet.skipped_record_ids == (
            "record-1",
            "record-3",
            "record-2",
            "record-4",
        )
        assert context_packet.records_returned == 4
        assert context_packet.max_depth_reached == 2
        assert context_packet.completed is True
        assert context_packet.truncated is False
        assert context_packet.truncation_reason is None
    finally:
        connection.close()


def test_multi_seed_context_enforces_global_record_budget_across_seeds():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        context_packet = assemble_multi_seed_context(
            connection,
            ("record-1", "record-3"),
            max_seed_records=8,
            max_depth=2,
            max_records=3,
        )

        assert [record.record_id for record in context_packet.records] == [
            "record-1",
            "record-3",
            "record-2",
        ]
        assert context_packet.completed is False
        assert context_packet.truncated is True
        assert context_packet.truncation_reason == "max_records"
        assert context_packet.records_returned == 3
        assert context_packet.skipped_record_ids == ("record-3",)
        assert context_packet.skipped_relationship_ids == ("rel-c",)
    finally:
        connection.close()


def test_multi_seed_context_reports_missing_seed_and_missing_related_records():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        connection.execute(
            """
INSERT INTO semantic_relationships (
  relationship_id,
  from_record_id,
  to_record_id,
  relationship_kind,
  relationship_state,
  provenance_refs,
  freshness_refs,
  authority_label,
  sensitivity_label,
  relationship_scope
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                "rel-missing",
                "record-1",
                "missing-related",
                "supports",
                "draft",
                "prov:rel-missing",
                "static-test",
                "repository-proof",
                "local-test-only",
                "direct",
            ),
        )

        context_packet = assemble_multi_seed_context(
            connection,
            ("record-1", "missing-seed"),
            max_seed_records=8,
            max_depth=1,
            max_records=8,
        )

        assert context_packet.completed is False
        assert context_packet.truncated is False
        assert context_packet.missing_seed_record_ids == ("missing-seed",)
        assert context_packet.missing_related_record_ids == ("missing-related",)
        assert context_packet.skipped_relationship_ids == ("rel-missing",)
        assert context_packet.integrity_findings == (
            "missing_related_record:missing-related",
            "missing_seed_record:missing-seed",
        )
    finally:
        connection.close()


def test_multi_seed_context_fails_closed_for_invalid_bounds_and_seed_ids():
    connection = create_in_memory_connection()
    try:
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, "record-1")
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, ("",))
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, ("record-1",), max_seed_records=0)
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, ("record-1",), max_seed_records=True)
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, ("record-1",), max_depth=True)
        with pytest.raises(ValueError):
            assemble_multi_seed_context(connection, ("record-1",), max_records=True)
    finally:
        connection.close()


def test_multi_seed_context_handles_empty_and_max_seed_budget_deterministically():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        empty_packet = assemble_multi_seed_context(connection, ())
        seed_limited_packet = assemble_multi_seed_context(
            connection,
            ("record-1", "record-2", "record-3"),
            max_seed_records=2,
            max_depth=0,
            max_records=8,
        )

        assert empty_packet.completed is True
        assert empty_packet.records == ()
        assert empty_packet.records_returned == 0
        assert seed_limited_packet.seed_record_ids == ("record-1", "record-2")
        assert seed_limited_packet.truncated is True
        assert seed_limited_packet.truncation_reason == (
            "max_seed_records_and_max_depth"
        )
        assert seed_limited_packet.skipped_record_ids == ("record-3",)
    finally:
        connection.close()


def test_multi_seed_context_output_is_plain_data_not_synthesized_truth():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)

        context_packet = assemble_multi_seed_context(
            connection,
            ("record-1",),
            max_depth=1,
            max_records=3,
        )
        context_dict = multi_seed_context_packet_as_dict(context_packet)

        assert context_packet.truth_status == "not_accepted_truth"
        assert context_packet.synthesis_status == "not_synthesized"
        assert context_packet.promotion_boundary == "operator_promotion_required"
        assert {
            model.synthesis_status for model in context_packet.synthesis_ready_records
        } == {"not_synthesized"}
        assert {
            model.accepted_truth_status
            for model in context_packet.synthesis_ready_records
        } == {"not_accepted_truth"}
        assert context_dict["context_kind"] == "multi_seed_context_packet"
        assert context_dict["seed_ordering"] == "input_order"
        assert context_dict["records"][1]["via_relationship_id"] == "rel-a"
        assert context_dict["records"][1]["via_relationship_state"] == "reviewed"
    finally:
        connection.close()


def test_traversal_dict_conversions_are_deterministic_plain_python_data():
    connection = create_in_memory_connection()
    try:
        populate_traversal_fixture(connection)
        traversal = traverse_record_relationships(
            connection,
            "record-1",
            max_depth=2,
        )
        context_packet = select_traversal_context_for_record(
            connection,
            "record-1",
            max_depth=2,
        )
        assert traversal is not None
        assert context_packet is not None

        traversal_dict = traversal_as_dict(traversal)
        context_packet_dict = traversal_context_packet_as_dict(context_packet)

        assert traversal_dict["traversal_strategy"] == "breadth_first_by_relationship_id"
        assert traversal_dict["completed"] is True
        assert traversal_dict["records_returned"] == 4
        assert traversal_dict["records"][0]["record_id"] == "record-1"
        assert traversal_dict["records"][1]["via_relationship_state"] == "reviewed"
        assert context_packet_dict["context_kind"] == "traversal_backed_context_packet"
        assert context_packet_dict["synthesis_ready_records"][0]["record_id"] == (
            "record-1"
        )
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
