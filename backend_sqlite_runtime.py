"""Small SQLite runtime proofs for the backend schema."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from backend_sqlite_schema import (
    SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
    SCHEMA_IDENTITY,
    SCHEMA_VERSION,
    sqlite_physical_schema_sql_definitions,
    sqlite_physical_schema_table_names,
)


def _apply_physical_schema(connection: sqlite3.Connection) -> None:
    """Apply the static physical schema definitions to an existing connection."""

    for sql_definition in sqlite_physical_schema_sql_definitions():
        connection.execute(sql_definition)


def create_in_memory_connection() -> sqlite3.Connection:
    """Create an in-memory connection and apply the static schema."""

    connection = sqlite3.connect(":memory:")
    try:
        _apply_physical_schema(connection)
    except Exception:
        connection.close()
        raise
    return connection


def create_file_backed_connection(db_path: Path) -> sqlite3.Connection:
    """Create or open one explicit file-backed database path."""

    db_path = _require_file_backed_db_path(db_path)
    existed_before_open = db_path.exists()
    connection = sqlite3.connect(db_path)
    try:
        if existed_before_open:
            _require_existing_database_is_current(connection)
        else:
            _apply_physical_schema(connection)
            record_in_memory_schema_version(connection)
            if not sqlite_runtime_schema_version_matches(connection):
                raise RuntimeError("backend sqlite schema version check failed")
            connection.commit()
    except Exception:
        connection.close()
        raise
    return connection


def _require_file_backed_db_path(db_path: Path) -> Path:
    """Return a narrow explicit database path or fail closed."""

    if not isinstance(db_path, Path):
        raise TypeError("backend sqlite database path must be a pathlib.Path")
    if db_path.suffix != ".db":
        raise ValueError("backend sqlite database path must use a .db suffix")
    if db_path.is_symlink():
        raise ValueError("backend sqlite database path must not be a symlink")
    if db_path.exists() and db_path.is_dir():
        raise ValueError("backend sqlite database path must not be a directory")
    if not db_path.parent.exists():
        raise ValueError("backend sqlite database parent directory must exist")
    if not db_path.parent.is_dir():
        raise ValueError("backend sqlite database parent must be a directory")
    if db_path.parent.is_symlink():
        raise ValueError("backend sqlite database parent must not be a symlink")
    return db_path


def _require_existing_database_is_current(connection: sqlite3.Connection) -> None:
    """Fail closed unless an existing database is already a current schema."""

    expected_tables = set(sqlite_physical_schema_table_names())
    actual_tables = set(sqlite_runtime_table_names(connection))
    if actual_tables != expected_tables:
        raise RuntimeError("existing backend sqlite database schema is not recognized")
    if not sqlite_runtime_schema_version_matches(connection):
        raise RuntimeError(
            "existing backend sqlite database schema version is not current"
        )


def sqlite_runtime_table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    """Return user table names from an existing connection."""

    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return tuple(row[0] for row in rows)


def _require_known_table_name(table_name: str) -> str:
    """Return a known physical schema table name or fail closed."""

    if table_name not in sqlite_physical_schema_table_names():
        raise ValueError(f"unknown backend sqlite schema table: {table_name}")
    return table_name


def sqlite_runtime_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> tuple[str, ...]:
    """Return column names for one table in an existing connection."""

    table_name = _require_known_table_name(table_name)
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return tuple(row[1] for row in rows)


def sqlite_runtime_table_primary_keys(
    connection: sqlite3.Connection,
    table_name: str,
) -> tuple[str, ...]:
    """Return primary-key column names for one table in an existing connection."""

    table_name = _require_known_table_name(table_name)
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return tuple(row[1] for row in rows if row[5] > 0)


def record_in_memory_schema_version(
    connection: sqlite3.Connection,
    source_commit: str | None = None,
) -> None:
    """Record the current schema version in an existing in-memory connection."""

    connection.execute(
        """
INSERT INTO schema_versions (
  schema_version,
  schema_identity,
  applied_at,
  source_commit,
  migration_state,
  notes
) VALUES (?, ?, NULL, ?, ?, NULL)
ON CONFLICT(schema_version) DO UPDATE SET
  schema_identity = excluded.schema_identity,
  source_commit = excluded.source_commit,
  migration_state = excluded.migration_state
""".strip(),
        (
            SCHEMA_VERSION,
            SCHEMA_IDENTITY,
            source_commit,
            SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
        ),
    )


def sqlite_runtime_schema_version(connection: sqlite3.Connection) -> str | None:
    """Return the acknowledged backend schema version, if exactly one exists."""

    try:
        rows = connection.execute(
            """
SELECT schema_version
FROM schema_versions
WHERE
  schema_identity = ?
  AND migration_state = ?
ORDER BY schema_version
""".strip(),
            (SCHEMA_IDENTITY, SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    if len(rows) != 1:
        return None
    return rows[0][0]


def sqlite_runtime_schema_version_matches(connection: sqlite3.Connection) -> bool:
    """Return True when the in-memory schema version matches the static schema."""

    return sqlite_runtime_schema_version(connection) == SCHEMA_VERSION
