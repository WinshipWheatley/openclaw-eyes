"""Small in-memory runtime proof for the backend SQLite schema."""

from __future__ import annotations

import sqlite3

from backend_sqlite_schema import (
    SCHEMA_CONTROL_IN_MEMORY_CURRENT_STATE,
    SCHEMA_IDENTITY,
    SCHEMA_VERSION,
    sqlite_physical_schema_sql_definitions,
    sqlite_physical_schema_table_names,
)


def create_in_memory_connection() -> sqlite3.Connection:
    """Create an in-memory connection and apply the static schema."""

    connection = sqlite3.connect(":memory:")
    try:
        for sql_definition in sqlite_physical_schema_sql_definitions():
            connection.execute(sql_definition)
    except Exception:
        connection.close()
        raise
    return connection


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
