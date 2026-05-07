import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_sqlite_repository as repository
import backend_sqlite_runtime as runtime
from backend_sqlite_repository import (
    FileInventoryRow,
    OperatorPromotion,
    ProvenanceRef,
    SemanticLabel,
    SemanticRecord,
    SemanticRelationship,
    SourceDiscoveryEvent,
    SourceExclusion,
    SourceRegistryEntry,
    StorageOperationReceipt,
    ValidationReceipt,
    read_file_inventory_row,
    read_file_inventory_row_by_source_relative_path,
    read_file_inventory_rows_by_source_id,
    read_operator_promotion,
    read_provenance_ref,
    read_record_labels,
    read_record_operator_promotions,
    read_record_provenance_refs,
    read_record_relationships,
    read_record_validation_receipts,
    read_record_ids_for_exact_label_seed,
    read_record_ids_for_exact_operator_promotion_seed,
    read_record_ids_for_exact_provenance_ref_seed,
    read_record_ids_for_exact_validation_seed,
    read_semantic_label,
    read_semantic_record,
    read_semantic_relationship,
    read_source_discovery_event,
    read_source_exclusion,
    read_source_exclusions,
    read_source_registry_entries_by_device_identity,
    read_source_registry_entry,
    read_pending_source_discovery_events,
    read_storage_operation_receipt,
    read_storage_operation_receipts_by_inventory_id,
    read_validation_receipt,
    record_has_explicit_operator_promotion,
    semantic_record_column_names,
    table_column_names,
    write_file_inventory_row,
    write_operator_promotion,
    write_provenance_ref,
    write_semantic_label,
    write_semantic_record,
    write_semantic_relationship,
    write_source_discovery_event,
    write_source_exclusion,
    write_source_registry_entry,
    write_storage_operation_receipt,
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


def sample_source_registry_entry(source_id: str = "source-1") -> SourceRegistryEntry:
    return SourceRegistryEntry(
        source_id=source_id,
        device_identity="device-camera-001",
        last_known_mount_path="/Volumes/CAMERA_CARD",
        source_mode="inventory_only",
        operator_classification="camera",
        approval_receipt_ref="approval-1",
        freshness_timestamp="2026-05-06T00:00:00Z",
    )


def sample_source_discovery_event(
    discovery_id: str = "discovery-1",
) -> SourceDiscoveryEvent:
    return SourceDiscoveryEvent(
        discovery_id=discovery_id,
        device_identity="device-camera-001",
        detected_path="/Volumes/CAMERA_CARD",
        detected_at="2026-05-06T00:00:00Z",
        status="pending_approval",
    )


def sample_source_exclusion(exclusion_id: str = "exclusion-1") -> SourceExclusion:
    return SourceExclusion(
        exclusion_id=exclusion_id,
        source_id="source-1",
        pattern_type="folder",
        path_pattern="PRIVATE/",
        exclusion_level="private",
        reason="operator excluded private folder",
    )


def sample_file_inventory_row(inventory_id: str = "inventory-1") -> FileInventoryRow:
    return FileInventoryRow(
        inventory_id=inventory_id,
        source_id="source-1",
        relative_path="DCIM/100OPEN/clip001.mov",
        file_size=4096,
        mtime="2026-05-06T00:00:00Z",
        hash_heuristic="size-mtime",
        inventory_status="inventoried",
        last_seen_timestamp="2026-05-06T00:00:00Z",
        source_confidence="operator-approved-source",
    )


def sample_storage_operation_receipt(
    operation_id: str = "operation-1",
) -> StorageOperationReceipt:
    return StorageOperationReceipt(
        operation_id=operation_id,
        operation_type="backup_plan",
        source_inventory_id="inventory-1",
        target_path="/operator/provided/target",
        safety_tier="read_only",
        checksum_verification=0,
        operator_approval_ref="approval-1",
        execution_status="dry_run",
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
        "source_registry",
        "source_discovery_queue",
        "source_exclusions",
        "file_inventory",
        "storage_operation_receipts",
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


def test_storage_registry_inventory_exclusions_and_receipts_round_trip():
    connection = create_in_memory_connection()
    try:
        source = sample_source_registry_entry()
        discovery = sample_source_discovery_event()
        exclusion = sample_source_exclusion()
        inventory = sample_file_inventory_row()
        receipt = sample_storage_operation_receipt()

        write_source_registry_entry(connection, source)
        write_source_discovery_event(connection, discovery)
        write_source_exclusion(connection, exclusion)
        write_file_inventory_row(connection, inventory)
        write_storage_operation_receipt(connection, receipt)

        assert read_source_registry_entry(connection, "source-1") == source.__dict__
        assert read_source_discovery_event(connection, "discovery-1") == discovery.__dict__
        assert read_source_exclusion(connection, "exclusion-1") == exclusion.__dict__
        assert read_file_inventory_row(connection, "inventory-1") == inventory.__dict__
        assert read_storage_operation_receipt(connection, "operation-1") == (
            receipt.__dict__
        )
    finally:
        connection.close()


def test_storage_query_helpers_are_deterministic_and_source_scoped():
    connection = create_in_memory_connection()
    try:
        write_source_registry_entry(connection, sample_source_registry_entry("source-b"))
        write_source_registry_entry(connection, sample_source_registry_entry("source-a"))
        for discovery_id, detected_at, status in (
            ("discovery-c", "2026-05-06T00:02:00Z", "pending_approval"),
            ("discovery-a", "2026-05-06T00:01:00Z", "pending_approval"),
            ("discovery-b", "2026-05-06T00:01:00Z", "approved"),
        ):
            write_source_discovery_event(
                connection,
                {
                    **sample_source_discovery_event(discovery_id).__dict__,
                    "detected_at": detected_at,
                    "status": status,
                },
            )
        write_source_exclusion(
            connection,
            {**sample_source_exclusion("exclusion-b").__dict__, "source_id": "source-a"},
        )
        write_source_exclusion(
            connection,
            {**sample_source_exclusion("exclusion-a").__dict__, "source_id": "source-a"},
        )
        write_file_inventory_row(
            connection,
            {
                **sample_file_inventory_row("inventory-b").__dict__,
                "source_id": "source-a",
                "relative_path": "z-last.wav",
            },
        )
        write_file_inventory_row(
            connection,
            {
                **sample_file_inventory_row("inventory-a").__dict__,
                "source_id": "source-a",
                "relative_path": "a-first.wav",
            },
        )
        write_storage_operation_receipt(
            connection,
            {
                **sample_storage_operation_receipt("operation-b").__dict__,
                "source_inventory_id": "inventory-a",
            },
        )
        write_storage_operation_receipt(
            connection,
            {
                **sample_storage_operation_receipt("operation-a").__dict__,
                "source_inventory_id": "inventory-a",
            },
        )

        assert [
            row["source_id"]
            for row in read_source_registry_entries_by_device_identity(
                connection,
                "device-camera-001",
            )
        ] == ["source-a", "source-b"]
        assert [
            row["discovery_id"] for row in read_pending_source_discovery_events(connection)
        ] == ["discovery-a", "discovery-c"]
        assert [
            row["exclusion_id"] for row in read_source_exclusions(connection, "source-a")
        ] == ["exclusion-a", "exclusion-b"]
        assert [
            row["inventory_id"]
            for row in read_file_inventory_rows_by_source_id(connection, "source-a")
        ] == ["inventory-a", "inventory-b"]
        assert read_file_inventory_row_by_source_relative_path(
            connection,
            "source-a",
            "a-first.wav",
        )["inventory_id"] == "inventory-a"
        assert [
            row["operation_id"]
            for row in read_storage_operation_receipts_by_inventory_id(
                connection,
                "inventory-a",
            )
        ] == ["operation-a", "operation-b"]
    finally:
        connection.close()


def test_file_inventory_identity_is_source_id_plus_relative_path_not_mount_path():
    connection = create_in_memory_connection()
    try:
        write_source_registry_entry(
            connection,
            {
                **sample_source_registry_entry("source-1").__dict__,
                "last_known_mount_path": "/Volumes/CAMERA_CARD",
            },
        )
        write_source_registry_entry(
            connection,
            {
                **sample_source_registry_entry("source-2").__dict__,
                "last_known_mount_path": "/mnt/e",
            },
        )
        write_file_inventory_row(connection, sample_file_inventory_row("inventory-1"))
        write_file_inventory_row(
            connection,
            {
                **sample_file_inventory_row("inventory-2").__dict__,
                "source_id": "source-2",
            },
        )

        assert read_file_inventory_row_by_source_relative_path(
            connection,
            "source-1",
            "DCIM/100OPEN/clip001.mov",
        )["inventory_id"] == "inventory-1"
        assert read_file_inventory_row_by_source_relative_path(
            connection,
            "source-2",
            "DCIM/100OPEN/clip001.mov",
        )["inventory_id"] == "inventory-2"
    finally:
        connection.close()


def test_storage_repository_writes_fail_closed_for_unknown_references():
    connection = create_in_memory_connection()
    try:
        with pytest.raises(ValueError):
            write_source_exclusion(connection, sample_source_exclusion())
        with pytest.raises(ValueError):
            write_file_inventory_row(connection, sample_file_inventory_row())

        write_source_registry_entry(connection, sample_source_registry_entry())
        with pytest.raises(ValueError):
            write_storage_operation_receipt(connection, sample_storage_operation_receipt())
    finally:
        connection.close()


def test_storage_repository_rejects_absolute_paths_and_bool_numeric_values():
    connection = create_in_memory_connection()
    try:
        write_source_registry_entry(connection, sample_source_registry_entry())
        for relative_path in (
            "/absolute/path.mov",
            "../outside.mov",
            "folder/../outside.mov",
            "C:\\absolute\\path.mov",
        ):
            with pytest.raises(ValueError):
                write_file_inventory_row(
                    connection,
                    {
                        **sample_file_inventory_row(f"inventory-{relative_path}").__dict__,
                        "relative_path": relative_path,
                    },
                )
        with pytest.raises(ValueError):
            write_file_inventory_row(
                connection,
                {**sample_file_inventory_row("bool-size").__dict__, "file_size": True},
            )

        write_file_inventory_row(connection, sample_file_inventory_row())
        with pytest.raises(ValueError):
            write_storage_operation_receipt(
                connection,
                {
                    **sample_storage_operation_receipt().__dict__,
                    "checksum_verification": True,
                },
            )
    finally:
        connection.close()


def test_exact_label_seed_selection_is_bounded_deterministic_and_non_promoting():
    connection = create_in_memory_connection()
    try:
        for record_id in ("record-c", "record-a", "record-b"):
            write_semantic_record(connection, sample_semantic_record(record_id))
        write_semantic_label(
            connection,
            {**sample_semantic_label("label-c").__dict__, "target_record_id": "record-c"},
        )
        write_semantic_label(
            connection,
            {**sample_semantic_label("label-a").__dict__, "target_record_id": "record-a"},
        )
        write_semantic_label(
            connection,
            {**sample_semantic_label("label-b").__dict__, "target_record_id": "record-b"},
        )
        write_semantic_label(
            connection,
            {
                **sample_semantic_label("label-other").__dict__,
                "target_record_id": "record-a",
                "label_value": "other-confidence",
            },
        )

        assert read_record_ids_for_exact_label_seed(
            connection,
            "confidence",
            "test-confidence",
            max_records=2,
        ) == ("record-a", "record-b")
        assert read_record_ids_for_exact_label_seed(
            connection,
            "confidence",
            "other-confidence",
            max_records=8,
        ) == ("record-a",)
        assert read_semantic_record(connection, "record-a")[
            "accepted_knowledge_derived"
        ] == 0
    finally:
        connection.close()


def test_exact_label_seed_selection_fails_closed_for_invalid_inputs():
    connection = create_in_memory_connection()
    try:
        with pytest.raises(ValueError):
            read_record_ids_for_exact_label_seed(
                connection,
                "",
                "test-confidence",
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_label_seed(
                connection,
                "confidence",
                "",
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_label_seed(
                connection,
                "confidence",
                "test-confidence",
                max_records=0,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_label_seed(
                connection,
                "confidence",
                "test-confidence",
                max_records=True,
            )
    finally:
        connection.close()


def test_exact_provenance_seed_selection_is_bounded_deterministic_and_non_promoting():
    connection = create_in_memory_connection()
    try:
        for record_id in ("record-c", "record-a", "record-b"):
            write_semantic_record(connection, sample_semantic_record(record_id))
        write_provenance_ref(
            connection,
            {**sample_provenance_ref("prov-c").__dict__, "target_record_id": "record-c"},
        )
        write_provenance_ref(
            connection,
            {**sample_provenance_ref("prov-a").__dict__, "target_record_id": "record-a"},
        )

        assert read_record_ids_for_exact_provenance_ref_seed(
            connection,
            "prov-a",
            max_records=8,
        ) == ("record-a",)
        assert read_record_ids_for_exact_provenance_ref_seed(
            connection,
            "missing-prov",
            max_records=8,
        ) == ()
        assert read_semantic_record(connection, "record-a")[
            "accepted_knowledge_derived"
        ] == 0
    finally:
        connection.close()


def test_exact_validation_seed_selection_is_bounded_deterministic_and_deduped():
    connection = create_in_memory_connection()
    try:
        for record_id in ("record-c", "record-a", "record-b"):
            write_semantic_record(connection, sample_semantic_record(record_id))
        write_validation_receipt(
            connection,
            {
                **sample_validation_receipt("receipt-c").__dict__,
                "validated_target": "record-c",
            },
        )
        write_validation_receipt(
            connection,
            {
                **sample_validation_receipt("receipt-a1").__dict__,
                "validated_target": "record-a",
            },
        )
        write_validation_receipt(
            connection,
            {
                **sample_validation_receipt("receipt-a2").__dict__,
                "validated_target": "record-a",
            },
        )
        write_validation_receipt(
            connection,
            {
                **sample_validation_receipt("receipt-other").__dict__,
                "validated_target": "record-b",
                "validation_result": "failed",
            },
        )

        assert read_record_ids_for_exact_validation_seed(
            connection,
            "static-test",
            "passed",
            max_records=2,
        ) == ("record-a", "record-c")
        assert read_record_ids_for_exact_validation_seed(
            connection,
            "static-test",
            "failed",
            max_records=8,
        ) == ("record-b",)
    finally:
        connection.close()


def test_exact_operator_promotion_seed_selection_is_bounded_and_deduped():
    connection = create_in_memory_connection()
    try:
        for record_id in ("record-c", "record-a", "record-b"):
            write_semantic_record(connection, sample_semantic_record(record_id))
        write_operator_promotion(
            connection,
            {
                **sample_operator_promotion("promotion-c").__dict__,
                "target_record_id": "record-c",
            },
        )
        write_operator_promotion(
            connection,
            {
                **sample_operator_promotion("promotion-a1").__dict__,
                "target_record_id": "record-a",
            },
        )
        write_operator_promotion(
            connection,
            {
                **sample_operator_promotion("promotion-a2").__dict__,
                "target_record_id": "record-a",
            },
        )
        write_operator_promotion(
            connection,
            {
                **sample_operator_promotion("promotion-b").__dict__,
                "target_record_id": "record-b",
                "promoted_by_operator": 0,
            },
        )

        assert read_record_ids_for_exact_operator_promotion_seed(
            connection,
            "test scope",
            1,
            max_records=2,
        ) == ("record-a", "record-c")
        assert read_record_ids_for_exact_operator_promotion_seed(
            connection,
            "test scope",
            0,
            max_records=8,
        ) == ("record-b",)
        assert read_semantic_record(connection, "record-a")[
            "accepted_knowledge_derived"
        ] == 0
    finally:
        connection.close()


def test_new_exact_seed_selection_helpers_fail_closed_for_invalid_inputs():
    connection = create_in_memory_connection()
    try:
        with pytest.raises(ValueError):
            read_record_ids_for_exact_provenance_ref_seed(connection, "")
        with pytest.raises(ValueError):
            read_record_ids_for_exact_provenance_ref_seed(
                connection,
                "prov-1",
                max_records=True,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_validation_seed(
                connection,
                "",
                "passed",
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_validation_seed(
                connection,
                "static-test",
                "",
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_validation_seed(
                connection,
                "static-test",
                "passed",
                max_records=0,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_validation_seed(
                connection,
                "static-test",
                "passed",
                max_records=True,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_operator_promotion_seed(
                connection,
                "",
                1,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_operator_promotion_seed(
                connection,
                "test scope",
                True,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_operator_promotion_seed(
                connection,
                "test scope",
                2,
            )
        with pytest.raises(ValueError):
            read_record_ids_for_exact_operator_promotion_seed(
                connection,
                "test scope",
                1,
                max_records=True,
            )
    finally:
        connection.close()


def test_semantic_record_truth_boundary_flags_must_be_binary_ints():
    connection = create_in_memory_connection()
    try:
        for field_name in ("synthesis_not_truth", "accepted_knowledge_derived"):
            for bad_value in ("1", True):
                payload = {
                    **sample_semantic_record(f"bad-{field_name}-{bad_value}").__dict__,
                    field_name: bad_value,
                }

                with pytest.raises(ValueError):
                    write_semantic_record(connection, payload)
    finally:
        connection.close()


def test_operator_promotion_flag_must_be_binary_int_not_bool():
    connection = create_in_memory_connection()
    try:
        write_semantic_record(connection, sample_semantic_record("record-1"))
        with pytest.raises(ValueError):
            write_operator_promotion(
                connection,
                {**sample_operator_promotion().__dict__, "promoted_by_operator": True},
            )
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
