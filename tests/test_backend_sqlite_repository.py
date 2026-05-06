import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_sqlite_repository as repository
import backend_sqlite_runtime as runtime
from backend_sqlite_repository import (
    SemanticRecord,
    read_semantic_record,
    semantic_record_column_names,
    write_semantic_record,
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
