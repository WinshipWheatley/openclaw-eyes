import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_sqlite_repository as repository
import backend_sqlite_runtime as runtime
from backend_sqlite_repository import (
    OperatorPromotion,
    ProvenanceRef,
    SemanticLabel,
    SemanticRecord,
    SemanticRelationship,
    ValidationReceipt,
    read_operator_promotion,
    read_provenance_ref,
    read_record_labels,
    read_record_operator_promotions,
    read_record_provenance_refs,
    read_record_relationships,
    read_record_validation_receipts,
    read_semantic_label,
    read_semantic_record,
    read_semantic_relationship,
    read_validation_receipt,
    record_has_explicit_operator_promotion,
    semantic_record_column_names,
    table_column_names,
    write_operator_promotion,
    write_provenance_ref,
    write_semantic_label,
    write_semantic_record,
    write_semantic_relationship,
    write_validation_receipt,
)
from backend_sqlite_runtime import create_file_backed_connection, create_in_memory_connection
from backend_sqlite_schema import sqlite_schema_table


REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = REPO_ROOT / "backend_sqlite_repository.py"


def module_ast() -> ast.Module:
    return ast.parse(REPOSITORY_PATH.read_text(encoding="utf-8"))


def imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


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


def sample_semantic_label(label_id: str = "label-1") -> SemanticLabel:
    return SemanticLabel(
        label_id=label_id,
        target_record_id="record-1",
        label_name="confidence",
        label_value="test-confidence",
        label_basis="static test",
        review_status="needs review",
        source_label_ref=None,
    )


def sample_provenance_ref(provenance_ref_id: str = "prov-1") -> ProvenanceRef:
    return ProvenanceRef(
        provenance_ref_id=provenance_ref_id,
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
    )


def sample_semantic_relationship(
    relationship_id: str = "rel-1",
) -> SemanticRelationship:
    return SemanticRelationship(
        relationship_id=relationship_id,
        from_record_id="record-1",
        to_record_id="record-2",
        relationship_kind="supports",
        relationship_state="draft",
        provenance_refs="prov-1",
        freshness_refs="static-test",
        authority_label="repository-proof",
        sensitivity_label="local-test-only",
        relationship_scope="direct",
    )


def sample_validation_receipt(receipt_id: str = "receipt-1") -> ValidationReceipt:
    return ValidationReceipt(
        receipt_id=receipt_id,
        validated_target="record-1",
        validator_name="static-test",
        validation_result="passed",
        failure_reasons="",
        checked_at="2026-05-06T00:00:00Z",
        source_basis="pytest",
        authority_boundary="repository-proof",
    )


def sample_operator_promotion(promotion_id: str = "promotion-1") -> OperatorPromotion:
    return OperatorPromotion(
        promotion_id=promotion_id,
        target_record_id="record-1",
        operator_decision="accepted for review",
        receipt_ref="receipt-1",
        promotion_scope="test scope",
        promoted_by_operator=1,
        complete_label_set="confidence,sensitivity,authority,review",
        authority_boundary="operator explicit",
    )


def test_repository_module_does_not_import_sqlite3_or_create_connections():
    tree = module_ast()
    source = REPOSITORY_PATH.read_text(encoding="utf-8").lower()

    assert "sqlite3" not in imported_module_names(tree)
    assert {"connect", "open", "read_text", "write_text"}.isdisjoint(
        called_function_names(tree)
    )
    assert "create_in_memory_connection" not in source
    assert "create_file_backed_connection" not in source


def test_semantic_record_column_names_match_schema_contract():
    table = sqlite_schema_table("semantic_records")

    assert table is not None
    assert semantic_record_column_names() == table.column_names
    assert SemanticRecord.__dataclass_fields__.keys() == set(table.column_names)


def test_repository_table_column_names_match_schema_contracts():
    expected_tables = {
        "semantic_records",
        "semantic_labels",
        "semantic_relationships",
        "provenance_refs",
        "validation_receipts",
        "operator_promotions",
    }

    for table_name in expected_tables:
        table = sqlite_schema_table(table_name)
        assert table is not None
        assert table_column_names(table_name) == table.column_names

    with pytest.raises(ValueError):
        table_column_names("context_filter_receipts")


def test_semantic_record_can_be_inserted_and_read_back_in_memory():
    connection = create_in_memory_connection()
    try:
        record = sample_semantic_record()

        write_semantic_record(connection, record)

        assert read_semantic_record(connection, record.record_id) == {
            "record_id": "record-1",
            "entity_family": "system artifact",
            "knowledge_layer": "synthesis layer",
            "contract_state": "draft",
            "validator_decision": "allowed",
            "synthesis_not_truth": 1,
            "accepted_knowledge_derived": 0,
            "provenance_refs": "planning-bridge:sample",
            "freshness_refs": "static-test",
            "confidence_label": "test-confidence",
            "sensitivity_label": "local-test-only",
            "authority_label": "repository-proof",
            "review_status_label": "needs review",
            "document_id": "doc-1",
            "parent_record_id": None,
            "section_path": "1. sample",
            "page_ref": None,
            "summary_level": "record",
            "summary_text_ref": "summary-ref-1",
        }
    finally:
        connection.close()


def test_semantic_record_can_be_inserted_and_read_back_file_backed(tmp_path):
    connection = create_file_backed_connection(tmp_path / "repository.db")
    try:
        record = sample_semantic_record("file-backed-record")

        write_semantic_record(connection, record)
        connection.commit()

        assert read_semantic_record(connection, "file-backed-record")["record_id"] == (
            "file-backed-record"
        )
    finally:
        connection.close()


def test_label_provenance_relationship_receipt_and_promotion_round_trip():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        write_semantic_record(connection, sample_semantic_record("record-2"))

        label = sample_semantic_label()
        provenance_ref = sample_provenance_ref()
        relationship = sample_semantic_relationship()
        receipt = sample_validation_receipt()
        promotion = sample_operator_promotion()

        write_semantic_label(connection, label)
        write_provenance_ref(connection, provenance_ref)
        write_semantic_relationship(connection, relationship)
        write_validation_receipt(connection, receipt)
        write_operator_promotion(connection, promotion)

        assert read_semantic_label(connection, "label-1") == label.__dict__
        assert read_provenance_ref(connection, "prov-1") == provenance_ref.__dict__
        assert read_semantic_relationship(connection, "rel-1") == relationship.__dict__
        assert read_validation_receipt(connection, "receipt-1") == receipt.__dict__
        assert read_operator_promotion(connection, "promotion-1") == promotion.__dict__
    finally:
        connection.close()


def test_record_query_helpers_return_stable_ordered_rows():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        write_semantic_record(connection, sample_semantic_record("record-2"))
        write_semantic_label(connection, sample_semantic_label("label-b"))
        write_semantic_label(connection, sample_semantic_label("label-a"))
        write_provenance_ref(connection, sample_provenance_ref("prov-b"))
        write_provenance_ref(connection, sample_provenance_ref("prov-a"))
        write_semantic_relationship(connection, sample_semantic_relationship("rel-b"))
        write_semantic_relationship(connection, sample_semantic_relationship("rel-a"))
        write_validation_receipt(connection, sample_validation_receipt("receipt-b"))
        write_validation_receipt(connection, sample_validation_receipt("receipt-a"))
        write_operator_promotion(connection, sample_operator_promotion("promotion-b"))
        write_operator_promotion(connection, sample_operator_promotion("promotion-a"))

        assert [row["label_id"] for row in read_record_labels(connection, "record-1")] == [
            "label-a",
            "label-b",
        ]
        assert [
            row["provenance_ref_id"]
            for row in read_record_provenance_refs(connection, "record-1")
        ] == ["prov-a", "prov-b"]
        assert [
            row["relationship_id"]
            for row in read_record_relationships(connection, "record-1")
        ] == ["rel-a", "rel-b"]
        assert [
            row["receipt_id"]
            for row in read_record_validation_receipts(connection, "record-1")
        ] == ["receipt-a", "receipt-b"]
        assert [
            row["promotion_id"]
            for row in read_record_operator_promotions(connection, "record-1")
        ] == ["promotion-a", "promotion-b"]
    finally:
        connection.close()


def test_missing_related_rows_return_empty_deterministic_tuples():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))

        assert read_record_labels(connection, "record-1") == ()
        assert read_record_provenance_refs(connection, "record-1") == ()
        assert read_record_relationships(connection, "record-1") == ()
        assert read_record_validation_receipts(connection, "record-1") == ()
        assert read_record_operator_promotions(connection, "record-1") == ()
    finally:
        connection.close()


def test_related_writes_fail_closed_for_unknown_semantic_record_references():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))

        with pytest.raises(ValueError):
            write_semantic_label(
                connection,
                {**sample_semantic_label().__dict__, "target_record_id": "missing"},
            )
        with pytest.raises(ValueError):
            write_provenance_ref(
                connection,
                {**sample_provenance_ref().__dict__, "target_record_id": "missing"},
            )
        with pytest.raises(ValueError):
            write_validation_receipt(
                connection,
                {**sample_validation_receipt().__dict__, "validated_target": "missing"},
            )
        with pytest.raises(ValueError):
            write_operator_promotion(
                connection,
                {**sample_operator_promotion().__dict__, "target_record_id": "missing"},
            )
        with pytest.raises(ValueError):
            write_semantic_relationship(connection, sample_semantic_relationship())
    finally:
        connection.close()


def test_related_duplicate_primary_keys_fail_closed():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        write_semantic_record(connection, sample_semantic_record("record-2"))

        write_semantic_label(connection, sample_semantic_label())
        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_semantic_label(connection, sample_semantic_label())

        write_provenance_ref(connection, sample_provenance_ref())
        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_provenance_ref(connection, sample_provenance_ref())

        write_semantic_relationship(connection, sample_semantic_relationship())
        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_semantic_relationship(connection, sample_semantic_relationship())

        write_validation_receipt(connection, sample_validation_receipt())
        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_validation_receipt(connection, sample_validation_receipt())

        write_operator_promotion(connection, sample_operator_promotion())
        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_operator_promotion(connection, sample_operator_promotion())
    finally:
        connection.close()


def test_missing_semantic_record_returns_none():
    connection = create_in_memory_connection()
    try:
        assert read_semantic_record(connection, "missing-record") is None
    finally:
        connection.close()


def test_empty_record_id_fails_closed_before_read():
    connection = create_in_memory_connection()
    try:
        with pytest.raises(ValueError):
            read_semantic_record(connection, "")
    finally:
        connection.close()


def test_duplicate_record_id_fails_closed():
    connection = create_in_memory_connection()
    try:
        record = sample_semantic_record()
        write_semantic_record(connection, record)

        with pytest.raises(runtime.sqlite3.IntegrityError):
            write_semantic_record(connection, record)
    finally:
        connection.close()


def test_payload_must_match_semantic_records_schema_exactly():
    connection = create_in_memory_connection()
    try:
        payload = sample_semantic_record().__dict__
        missing_payload = dict(payload)
        missing_payload.pop("freshness_refs")
        extra_payload = dict(payload)
        extra_payload["runtime_path"] = "/tmp/nope"

        with pytest.raises(ValueError):
            write_semantic_record(connection, missing_payload)
        with pytest.raises(ValueError):
            write_semantic_record(connection, extra_payload)
    finally:
        connection.close()


def test_semantic_record_write_does_not_magically_promote_accepted_knowledge():
    connection = create_in_memory_connection()
    try:
        record = sample_semantic_record()
        promoted_payload = {
            **record.__dict__,
            "accepted_knowledge_derived": 1,
        }

        with pytest.raises(ValueError):
            write_semantic_record(connection, promoted_payload)

        write_semantic_record(connection, record)
        stored = read_semantic_record(connection, record.record_id)

        assert stored is not None
        assert stored["synthesis_not_truth"] == 1
        assert stored["accepted_knowledge_derived"] == 0
    finally:
        connection.close()


def test_operator_promotion_is_explicit_and_does_not_rewrite_record_truth_flags():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        assert record_has_explicit_operator_promotion(connection, "record-1") is False

        write_operator_promotion(connection, sample_operator_promotion())
        stored_record = read_semantic_record(connection, "record-1")

        assert record_has_explicit_operator_promotion(connection, "record-1") is True
        assert stored_record is not None
        assert stored_record["accepted_knowledge_derived"] == 0
    finally:
        connection.close()


def test_semantic_record_truth_boundary_flags_must_be_binary_ints():
    connection = create_in_memory_connection()
    try:
        for field_name in ("synthesis_not_truth", "accepted_knowledge_derived"):
            payload = {
                **sample_semantic_record(f"bad-{field_name}").__dict__,
                field_name: "1",
            }

            with pytest.raises(ValueError):
                write_semantic_record(connection, payload)
    finally:
        connection.close()


def test_repository_uses_caller_supplied_connection_only():
    class RecordingConnection:
        def __init__(self):
            self.calls = []

        def execute(self, sql, parameters=()):
            self.calls.append((sql, parameters))
            return self

        def fetchone(self):
            return None

    connection = RecordingConnection()

    assert read_semantic_record(connection, "known-missing") is None

    assert len(connection.calls) == 1
    assert "WHERE record_id = ?" in connection.calls[0][0]
    assert connection.calls[0][1] == ("known-missing",)


def test_repository_avoids_forbidden_surfaces():
    source = REPOSITORY_PATH.read_text(encoding="utf-8").lower()
    tree = module_ast()

    assert "sqlite3" not in source
    assert {
        "connect",
        "open",
        "read_text",
        "write_text",
        "executescript",
        "commit",
        "rollback",
    }.isdisjoint(called_function_names(tree))
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
    assert re.search(r"\bmodel\b", source) is None
    assert re.search(r"\bhermes\b", source) is None
    assert re.search(r"\bmcp\b", source) is None
    assert re.search(r"\bsync\b", source) is None
    assert re.search(r"\bapi\b", source) is None
    assert re.search(r"\bfrontend\b", source) is None
    assert re.search(r"\bapp\b", source) is None
