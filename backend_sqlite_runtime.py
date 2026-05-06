"""Small in-memory runtime proof for the backend SQLite schema."""

from __future__ import annotations

import sqlite3

from backend_sqlite_schema import (
    sqlite_schema_sql_definitions,
    sqlite_schema_table_names,
)


def create_in_memory_connection() -> sqlite3.Connection:
    """Create an in-memory connection and apply the static schema."""

    connection = sqlite3.connect(":memory:")
    try:
        for sql_definition in sqlite_schema_sql_definitions():
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
    """Return a known static schema table name or fail closed."""

    if table_name not in sqlite_schema_table_names():
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
