import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_sqlite_runtime as runtime
from backend_sqlite_runtime import (
    create_in_memory_connection,
    sqlite_runtime_table_columns,
    sqlite_runtime_table_names,
    sqlite_runtime_table_primary_keys,
)
from backend_sqlite_schema import (
    sqlite_physical_schema_table_names,
    sqlite_schema_control_table,
    sqlite_schema_table_names,
    sqlite_schema_tables,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = REPO_ROOT / "backend_sqlite_runtime.py"

EXPECTED_PRIMARY_KEYS = {
    "semantic_records": "record_id",
    "semantic_labels": "label_id",
    "semantic_relationships": "relationship_id",
    "provenance_refs": "provenance_ref_id",
    "validation_receipts": "receipt_id",
    "operator_promotions": "promotion_id",
    "context_filter_receipts": "context_filter_receipt_id",
}


def backend_sqlite_lane_paths() -> tuple[Path, ...]:
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "backend_sqlite_schema.py"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    allowed_names = (
        "backend_data_contract.py",
        "backend_sqlite_schema.py",
        "backend_sqlite_runtime.py",
        "tests/test_backend_data_contract.py",
        "tests/test_backend_sqlite_schema.py",
        "tests/test_backend_sqlite_runtime.py",
    )
    return tuple(REPO_ROOT / path for path in allowed_names)


def module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


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


def test_backend_sqlite_lane_confines_sqlite3_import_to_runtime_module():
    importers = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in backend_sqlite_lane_paths()
        if re.search(r"^\s*(import|from)\s+sqlite3\b", path.read_text(), re.MULTILINE)
    }

    assert importers == {"backend_sqlite_runtime.py"}


def test_runtime_module_exposes_only_in_memory_connection_creation():
    tree = module_ast(RUNTIME_PATH)
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert 'sqlite3.connect(":memory:")' in source
    assert "sqlite3.connect" in ast.unparse(tree)
    assert "connect" in called_function_names(tree)
    assert {"open", "read_text", "write_text"}.isdisjoint(called_function_names(tree))
    assert "Path" not in imported_module_names(tree)


def test_create_in_memory_connection_creates_no_database_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    connection = create_in_memory_connection()
    try:
        assert sqlite_runtime_table_names(connection)
    finally:
        connection.close()

    assert tuple(tmp_path.iterdir()) == ()


def test_create_in_memory_connection_uses_memory_database_only():
    connection = create_in_memory_connection()
    try:
        database_rows = connection.execute("PRAGMA database_list").fetchall()
    finally:
        connection.close()

    assert database_rows == [(0, "main", "")]


def test_create_in_memory_connection_closes_connection_on_schema_failure(monkeypatch):
    real_connect = runtime.sqlite3.connect
    connections = []

    def tracking_connect(database_name):
        connection = real_connect(database_name)
        connections.append(connection)
        return connection

    monkeypatch.setattr(runtime.sqlite3, "connect", tracking_connect)
    monkeypatch.setattr(
        runtime,
        "sqlite_physical_schema_sql_definitions",
        lambda: ("CREATE TABLE ok_table (id TEXT PRIMARY KEY);", "BROKEN SQL"),
    )

    with pytest.raises(Exception):
        create_in_memory_connection()

    assert len(connections) == 1
    with pytest.raises(runtime.sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")


def test_all_static_schema_tables_exist_in_runtime_connection():
    connection = create_in_memory_connection()
    try:
        runtime_tables = set(sqlite_runtime_table_names(connection))

        assert runtime_tables == set(sqlite_physical_schema_table_names())
        assert set(sqlite_schema_table_names()) < runtime_tables
        assert "schema_versions" in runtime_tables
    finally:
        connection.close()


def test_runtime_schema_versions_table_matches_static_schema_control_metadata():
    schema_versions = sqlite_schema_control_table("schema_versions")
    assert schema_versions is not None

    connection = create_in_memory_connection()
    try:
        assert sqlite_runtime_table_columns(connection, "schema_versions") == (
            schema_versions.column_names
        )
        assert sqlite_runtime_table_primary_keys(connection, "schema_versions") == (
            "schema_version",
        )
    finally:
        connection.close()


def test_runtime_columns_match_static_schema_definitions():
    connection = create_in_memory_connection()
    try:
        for table in sqlite_schema_tables():
            assert sqlite_runtime_table_columns(connection, table.table_name) == (
                table.column_names
            )
    finally:
        connection.close()


def test_runtime_primary_keys_match_static_schema_definitions():
    assert set(EXPECTED_PRIMARY_KEYS) == set(sqlite_schema_table_names())

    connection = create_in_memory_connection()
    try:
        for table in sqlite_schema_tables():
            assert sqlite_runtime_table_primary_keys(connection, table.table_name) == (
                EXPECTED_PRIMARY_KEYS[table.table_name],
            )
    finally:
        connection.close()


def test_table_inspection_helpers_fail_closed_for_unknown_table_names():
    connection = create_in_memory_connection()
    try:
        for unknown_table_name in (
            "runtime_logs",
            "semantic_records; DROP TABLE semantic_records",
        ):
            with pytest.raises(ValueError):
                sqlite_runtime_table_columns(connection, unknown_table_name)
            with pytest.raises(ValueError):
                sqlite_runtime_table_primary_keys(connection, unknown_table_name)

        assert "semantic_records" in sqlite_runtime_table_names(connection)
    finally:
        connection.close()


def test_runtime_module_avoids_forbidden_surfaces():
    source = RUNTIME_PATH.read_text(encoding="utf-8").lower()
    tree = module_ast(RUNTIME_PATH)

    assert {
        "open",
        "read_text",
        "write_text",
        "executescript",
        "commit",
        "rollback",
    }.isdisjoint(called_function_names(tree))
    assert ".db" not in source
    assert re.search(r"\bmigration\b", source) is None
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
