import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend_sqlite_runtime as runtime
from backend_sqlite_runtime import (
    create_file_backed_connection,
    create_in_memory_connection,
    record_in_memory_schema_version,
    sqlite_runtime_schema_version,
    sqlite_runtime_schema_version_matches,
    sqlite_runtime_table_columns,
    sqlite_runtime_table_names,
    sqlite_runtime_table_primary_keys,
)
from backend_sqlite_schema import (
    SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
    SCHEMA_IDENTITY,
    SCHEMA_VERSION,
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
    "source_registry": "source_id",
    "source_discovery_queue": "discovery_id",
    "source_exclusions": "exclusion_id",
    "file_inventory": "inventory_id",
    "storage_operation_receipts": "operation_id",
    "openclaw_nodes": "node_id",
    "node_source_links": "link_id",
    "source_authorization_scopes": "scope_id",
    "runtime_components": "component_id",
    "component_capabilities": "capability_id",
    "node_heartbeats": "heartbeat_id",
    "component_heartbeats": "heartbeat_id",
    "component_health_snapshots": "snapshot_id",
    "performance_sessions": "performance_session_id",
    "setlists": "setlist_id",
    "setlist_items": "setlist_item_id",
    "song_cues": "song_cue_id",
    "section_cues": "section_cue_id",
    "performance_action_receipts": "performance_action_receipt_id",
    "manual_override_events": "manual_override_event_id",
    "highlight_markers": "highlight_marker_id",
    "actor_profiles": "actor_profile_id",
    "agent_context_profiles": "context_profile_id",
    "context_export_receipts": "context_export_receipt_id",
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


def test_runtime_module_exposes_memory_and_explicit_file_backed_creation():
    tree = module_ast(RUNTIME_PATH)
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert 'sqlite3.connect(":memory:")' in source
    assert "create_file_backed_connection(db_path: Path)" in source
    assert "sqlite3.connect" in ast.unparse(tree)
    assert "connect" in called_function_names(tree)
    assert {"open", "read_text", "write_text"}.isdisjoint(called_function_names(tree))
    assert "pathlib" in imported_module_names(tree)


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


def allowed_sqlite_files_for(db_path: Path) -> set[Path]:
    return {
        db_path,
        db_path.with_name(f"{db_path.name}-journal"),
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    }


def assert_only_expected_sqlite_files(tmp_path: Path, db_path: Path) -> None:
    actual_files = {path for path in tmp_path.iterdir() if path.is_file()}
    assert db_path in actual_files
    assert actual_files <= allowed_sqlite_files_for(db_path)


def test_create_file_backed_connection_creates_db_only_under_tmp_path(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"

    connection = create_file_backed_connection(db_path)
    try:
        database_rows = connection.execute("PRAGMA database_list").fetchall()

        assert set(sqlite_runtime_table_names(connection)) == set(
            sqlite_physical_schema_table_names()
        )
        assert sqlite_runtime_schema_version(connection) == SCHEMA_VERSION
        assert sqlite_runtime_schema_version_matches(connection) is True
        assert database_rows == [(0, "main", str(db_path))]
    finally:
        connection.close()

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_create_file_backed_connection_rejects_directory_path(tmp_path):
    with pytest.raises(ValueError):
        create_file_backed_connection(tmp_path)

    assert tuple(tmp_path.iterdir()) == ()


def test_create_file_backed_connection_rejects_missing_parent_path(tmp_path):
    db_path = tmp_path / "missing" / "openclaw_runtime.db"

    with pytest.raises(ValueError):
        create_file_backed_connection(db_path)

    assert tuple(tmp_path.iterdir()) == ()


def test_create_file_backed_connection_rejects_non_path_argument():
    with pytest.raises(TypeError):
        create_file_backed_connection("openclaw_runtime.db")


def test_create_file_backed_connection_rejects_unsafe_suffix(tmp_path):
    for db_path in (
        tmp_path / "openclaw_runtime.sqlite",
        tmp_path / "openclaw_runtime",
    ):
        with pytest.raises(ValueError):
            create_file_backed_connection(db_path)

        assert not db_path.exists()


def test_create_file_backed_connection_rejects_symlink_path(tmp_path):
    real_db_path = tmp_path / "real.db"
    symlink_db_path = tmp_path / "linked.db"
    symlink_db_path.symlink_to(real_db_path)

    with pytest.raises(ValueError):
        create_file_backed_connection(symlink_db_path)

    assert set(tmp_path.iterdir()) == {symlink_db_path}


def test_create_file_backed_connection_rejects_symlink_parent(tmp_path):
    real_parent = tmp_path / "real_parent"
    linked_parent = tmp_path / "linked_parent"
    real_parent.mkdir()
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ValueError):
        create_file_backed_connection(linked_parent / "openclaw_runtime.db")

    assert set(tmp_path.iterdir()) == {real_parent, linked_parent}
    assert tuple(real_parent.iterdir()) == ()


def test_file_backed_database_has_all_physical_tables_and_schema_version(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"

    connection = create_file_backed_connection(db_path)
    try:
        assert set(sqlite_runtime_table_names(connection)) == set(
            sqlite_physical_schema_table_names()
        )
        assert sqlite_runtime_schema_version(connection) == SCHEMA_VERSION
        assert sqlite_runtime_schema_version_matches(connection) is True
    finally:
        connection.close()

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_reopening_same_valid_file_backed_database_succeeds(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"

    connection = create_file_backed_connection(db_path)
    connection.close()

    reopened = create_file_backed_connection(db_path)
    try:
        assert set(sqlite_runtime_table_names(reopened)) == set(
            sqlite_physical_schema_table_names()
        )
        assert sqlite_runtime_schema_version_matches(reopened) is True
    finally:
        reopened.close()

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_existing_empty_database_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    connection = runtime.sqlite3.connect(db_path)
    connection.close()

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_existing_wrong_shape_database_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    connection = runtime.sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE unrelated (id TEXT PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_existing_non_sqlite_database_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    db_path.write_bytes(b"not a sqlite database")

    with pytest.raises(runtime.sqlite3.DatabaseError):
        create_file_backed_connection(db_path)

    assert {db_path} <= set(tmp_path.iterdir())


def create_database_with_physical_schema_without_current_version(
    db_path: Path,
) -> None:
    connection = runtime.sqlite3.connect(db_path)
    try:
        for sql_definition in runtime.sqlite_physical_schema_sql_definitions():
            connection.execute(sql_definition)
        connection.commit()
    finally:
        connection.close()


def test_existing_database_with_missing_version_metadata_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    create_database_with_physical_schema_without_current_version(db_path)

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_existing_database_with_wrong_version_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    create_database_with_physical_schema_without_current_version(db_path)
    connection = runtime.sqlite3.connect(db_path)
    try:
        connection.execute(
            """
INSERT INTO schema_versions (
  schema_version,
  schema_identity,
  migration_state
) VALUES (?, ?, ?)
""".strip(),
            ("wrong-version", SCHEMA_IDENTITY, SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_existing_database_with_ambiguous_version_state_fails_closed(tmp_path):
    db_path = tmp_path / "openclaw_runtime.db"
    create_database_with_physical_schema_without_current_version(db_path)
    connection = runtime.sqlite3.connect(db_path)
    try:
        record_in_memory_schema_version(connection)
        connection.execute(
            """
INSERT INTO schema_versions (
  schema_version,
  schema_identity,
  migration_state
) VALUES (?, ?, ?)
""".strip(),
            (
                "other-current-version",
                SCHEMA_IDENTITY,
                SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert_only_expected_sqlite_files(tmp_path, db_path)


def test_create_file_backed_connection_closes_connection_on_schema_failure(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "openclaw_runtime.db"
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
        create_file_backed_connection(db_path)

    assert len(connections) == 1
    with pytest.raises(runtime.sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")

    assert set(tmp_path.iterdir()) <= allowed_sqlite_files_for(db_path)


def test_create_file_backed_connection_closes_connection_on_version_failure(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "openclaw_runtime.db"
    real_connect = runtime.sqlite3.connect
    connections = []

    def tracking_connect(database_name):
        connection = real_connect(database_name)
        connections.append(connection)
        return connection

    monkeypatch.setattr(runtime.sqlite3, "connect", tracking_connect)
    monkeypatch.setattr(
        runtime,
        "record_in_memory_schema_version",
        lambda connection: (_ for _ in ()).throw(RuntimeError("version failed")),
    )

    with pytest.raises(RuntimeError):
        create_file_backed_connection(db_path)

    assert len(connections) == 1
    with pytest.raises(runtime.sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")

    assert set(tmp_path.iterdir()) <= allowed_sqlite_files_for(db_path)


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


def schema_version_rows(connection):
    return connection.execute(
        """
SELECT
  schema_version,
  schema_identity,
  applied_at,
  source_commit,
  migration_state,
  notes
FROM schema_versions
ORDER BY schema_version
""".strip()
    ).fetchall()


def test_schema_version_table_is_empty_until_explicitly_recorded():
    connection = create_in_memory_connection()
    try:
        assert schema_version_rows(connection) == []
        assert sqlite_runtime_schema_version(connection) is None
        assert sqlite_runtime_schema_version_matches(connection) is False
    finally:
        connection.close()


def test_schema_version_match_fails_closed_when_metadata_table_is_missing():
    connection = runtime.sqlite3.connect(":memory:")
    try:
        assert sqlite_runtime_schema_version(connection) is None
        assert sqlite_runtime_schema_version_matches(connection) is False
    finally:
        connection.close()


def test_record_in_memory_schema_version_writes_current_schema_row():
    connection = create_in_memory_connection()
    try:
        record_in_memory_schema_version(connection, source_commit="4e7617d")

        assert schema_version_rows(connection) == [
            (
                SCHEMA_VERSION,
                SCHEMA_IDENTITY,
                None,
                "4e7617d",
                SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
                None,
            )
        ]
        assert sqlite_runtime_schema_version(connection) == SCHEMA_VERSION
        assert sqlite_runtime_schema_version_matches(connection) is True
    finally:
        connection.close()


def test_record_in_memory_schema_version_is_idempotent_for_current_schema():
    connection = create_in_memory_connection()
    try:
        record_in_memory_schema_version(connection, source_commit="older")
        record_in_memory_schema_version(connection, source_commit="newer")

        assert schema_version_rows(connection) == [
            (
                SCHEMA_VERSION,
                SCHEMA_IDENTITY,
                None,
                "newer",
                SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
                None,
            )
        ]
        assert sqlite_runtime_schema_version_matches(connection) is True
    finally:
        connection.close()


def test_schema_version_match_fails_closed_for_wrong_or_ambiguous_versions():
    connection = create_in_memory_connection()
    try:
        connection.execute(
            """
INSERT INTO schema_versions (
  schema_version,
  schema_identity,
  migration_state
) VALUES (?, ?, ?)
""".strip(),
            ("wrong-version", SCHEMA_IDENTITY, SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE),
        )
        assert sqlite_runtime_schema_version(connection) == "wrong-version"
        assert sqlite_runtime_schema_version_matches(connection) is False

        record_in_memory_schema_version(connection)
        assert sqlite_runtime_schema_version(connection) is None
        assert sqlite_runtime_schema_version_matches(connection) is False
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
        "rollback",
    }.isdisjoint(called_function_names(tree))
    assert "commit" in called_function_names(tree)
    assert "rollback" not in called_function_names(tree)
    assert "expanduser" not in source
    assert "environ" not in source
    assert "getenv" not in source
    assert "home()" not in source
    assert "glob" not in source
    assert "rglob" not in source
    assert "iterdir" not in source
    assert "mkdir" not in source
    assert re.search(r"\bmigration(?!_state)\b", source) is None
    assert re.search(r"\bmigrate\b", source) is None
    assert re.search(r"\balter\s+table\b", source) is None
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
