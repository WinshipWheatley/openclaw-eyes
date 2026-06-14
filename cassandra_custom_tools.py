"""Cassandra custom tool extension surface.

All future Cassandra tool/capability additions should be implemented here and
imported into cassandra_brain.py, rather than adding feature logic directly
inside cassandra_brain.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import cassandra_operator_objective_loop


def register_tools() -> dict[str, object]:
    """Return a registry for future custom Cassandra tools."""
    return {
        "operator_objective_loop": handle_operator_objective,
    }


def handle_operator_objective(
    text: str,
    *,
    source_channel: str = "telegram",
    source_message_ref: str = "",
    lane_context: Mapping[str, Any] | None = None,
    sqlite_path: str | Path = cassandra_operator_objective_loop.DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any] | None:
    """Create a gated Cassandra operator objective when the text matches.

    The objective loop is metadata-only. It does not execute Gmail lookups,
    create drafts, send, schedule, call Telegram, or invoke models.
    """
    result = cassandra_operator_objective_loop.route_cassandra_objective_message(
        text,
        source_channel=source_channel,
        source_message_ref=source_message_ref,
        lane_context=lane_context or {
            "target_world_ref": "operator_comms",
            "target_thread_ref": "cassandra",
        },
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    if result.get("recognized") is not True:
        return None
    return result
