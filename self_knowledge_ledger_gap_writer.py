"""Gated ledger writer for self-knowledge crawler gaps.

Extends the read-only crumb-crawler seed (`self_knowledge_crawler.py`) with a
write path that folds discovered filesystem gaps (files present on disk but
absent from the ledger's known-path inventory tables) into the ONE knowledge
ledger as known-unknown rows.

Safety model, following the house pattern in `scripts/fold_satellite_to_ledger.py`
and `scripts/populate_real_ledger.py`:

  (default)   DRY RUN  — return the would-write plan; the ledger is never opened
                          for writing and no backup is taken.
  confirm=True  WRITE  — back up the ledger file first (timestamped sibling
                          copy, verified non-empty), then write gap rows.
                          Idempotent: replaces only rows previously written by
                          this same fold_source (root), leaving every other
                          row/source in the table untouched — same idempotency
                          rule as fold_satellite_to_ledger.py.

Target table: `knowledge_sysknow_known_unknown`. This table already exists in
the live business-ops ledger (folded there via the same fold-satellite
pattern: unknown_id/subject/unknown_status/reason/next_safe_check plus the
`_fold_source`/`_fold_at` provenance columns) and is exactly the "what the
system knows it does NOT know" home described by
Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md. No new table is invented; this
module only ensures the table exists (CREATE TABLE IF NOT EXISTS with a
matching schema) so tests and fresh ledgers work without it pre-seeded.
"""

from __future__ import annotations

import shutil
import sqlite3
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from self_knowledge_crawler import diff_filesystem_against_ledger

GAP_TABLE = "knowledge_sysknow_known_unknown"
GAP_COLUMNS = (
    "unknown_id",
    "subject",
    "unknown_status",
    "reason",
    "next_safe_check",
    "_fold_source",
    "_fold_at",
)
GRAPH_NODE_TABLE = "knowledge_system_nodes"
GRAPH_EDGE_TABLE = "knowledge_system_edges"
GRAPH_NODE_COLUMNS = (
    "node_id",
    "kind",
    "owner_scope",
    "health_status",
    "activation_state",
    "last_seen_at",
    "last_verified_at",
    "payload_json",
    "_fold_source",
    "_fold_at",
)
GRAPH_EDGE_COLUMNS = (
    "source_node_id",
    "target_node_id",
    "relation",
    "owner_scope",
    "_fold_source",
    "_fold_at",
)
ACTIVATION_TABLE = "feedback_activation_records"
ACTIVATION_COLUMNS = (
    "activation_ref",
    "activation_state",
    "root",
    "scheduled_runtime_installed_by_this_call",
    "ledger_path",
    "ledger_write_confirmed",
    "inventory_graph_write_confirmed",
    "last_verified_at",
    "payload_json",
    "_fold_source",
    "_fold_at",
)


def _utc_now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def backup_ledger(ledger_path: str | Path) -> Path:
    """Copy the ledger file to a timestamped sibling path and verify the copy.

    Raises RuntimeError if the resulting backup does not exist or is empty —
    callers must treat that as fail-closed (do NOT proceed to write).
    """
    src = Path(ledger_path)
    backup_path = src.parent / f"{src.name}.bak-{_utc_now_stamp()}"
    shutil.copy2(src, backup_path)
    if not backup_path.exists() or backup_path.stat().st_size <= 0:
        raise RuntimeError(f"ledger backup verification failed: {backup_path}")
    return backup_path


def _fold_source_for(root: Path) -> str:
    return f"self_knowledge_crawler:{root.resolve()}"


def build_gap_write_plan(
    root: str | Path,
    ledger_path: str | Path,
    *,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Return the diff result plus the rows that WOULD be written, unexecuted."""
    root_path = Path(root).resolve()
    diff = diff_filesystem_against_ledger(root_path, ledger_path, max_files=max_files)
    fold_source = _fold_source_for(root_path)
    fold_at = _utc_now_iso()
    rows: list[dict[str, str]] = []
    for gap in diff["unknown_files"]:
        subject = gap["relative_path"]
        rows.append(
            {
                "unknown_id": f"self_knowledge_gap::{subject}",
                "subject": subject,
                "unknown_status": "unconfirmed_gap",
                "reason": (
                    "found on disk by self_knowledge_crawler; absent from the ledger's "
                    "known-path inventory tables"
                ),
                "next_safe_check": (
                    "operator/self-knowledge review: classify and either add to "
                    "file_inventory or record an explicit exclusion"
                ),
                "_fold_source": fold_source,
                "_fold_at": fold_at,
            }
        )
    return {
        "table": GAP_TABLE,
        "fold_source": fold_source,
        "diff_status": diff["status"],
        "counts": diff["counts"],
        "rows": rows,
    }


def write_gaps_to_ledger(
    root: str | Path,
    ledger_path: str | Path,
    *,
    confirm: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    """Dry-run by default; only writes (after a verified backup) with confirm=True."""
    plan = build_gap_write_plan(root, ledger_path, max_files=max_files)

    if not confirm:
        return {"status": "dry_run", "plan": plan}

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"status": "ledger_unavailable", "plan": plan}

    try:
        backup_path = backup_ledger(ledger)
    except (OSError, RuntimeError) as exc:
        return {"status": "backup_verification_failed", "reason": str(exc), "plan": plan}

    fold_source = plan["fold_source"]
    with sqlite3.connect(ledger) as conn:
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{GAP_TABLE}" ('
            "unknown_id TEXT, subject TEXT, unknown_status TEXT, reason TEXT, "
            "next_safe_check TEXT, _fold_source TEXT, _fold_at TEXT)"
        )
        # Idempotent: clear only this fold_source's prior rows, matching the
        # fold_satellite_to_ledger.py convention, before re-inserting.
        conn.execute(
            f'DELETE FROM "{GAP_TABLE}" WHERE "_fold_source" = ?', (fold_source,)
        )
        cols = ", ".join(GAP_COLUMNS)
        placeholders = ", ".join("?" for _ in GAP_COLUMNS)
        for row in plan["rows"]:
            conn.execute(
                f'INSERT INTO "{GAP_TABLE}" ({cols}) VALUES ({placeholders})',
                tuple(row[c] for c in GAP_COLUMNS),
            )
        conn.commit()

    return {
        "status": "written",
        "backup_path": str(backup_path),
        "written_count": len(plan["rows"]),
        "table": GAP_TABLE,
        "fold_source": fold_source,
    }


def _graph_fold_source(graph: Mapping[str, Any]) -> str:
    return f"self_knowledge_inventory_graph:{graph.get('owner_scope') or 'unknown'}"


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_activation_record_write_plan(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    activation_ref = str(payload.get("activation_ref") or "self_knowledge_scheduled_crawl:unknown")
    fold_source = f"self_knowledge_activation:{activation_ref}"
    fold_at = _utc_now_iso()
    row = {
        "activation_ref": activation_ref,
        "activation_state": str(payload.get("activation_state") or "unknown"),
        "root": str(payload.get("root") or ""),
        "scheduled_runtime_installed_by_this_call": 1
        if payload.get("scheduled_runtime_installed_by_this_call")
        else 0,
        "ledger_path": payload.get("ledger_path"),
        "ledger_write_confirmed": 1 if payload.get("ledger_write_confirmed") else 0,
        "inventory_graph_write_confirmed": 1
        if payload.get("inventory_graph_write_confirmed")
        else 0,
        "last_verified_at": payload.get("last_verified_at"),
        "payload_json": _stable_json(payload),
        "_fold_source": fold_source,
        "_fold_at": fold_at,
    }
    return {
        "table": ACTIVATION_TABLE,
        "fold_source": fold_source,
        "row": row,
    }


def _ensure_activation_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{ACTIVATION_TABLE}" ('
        "activation_ref TEXT PRIMARY KEY, activation_state TEXT NOT NULL, root TEXT, "
        "scheduled_runtime_installed_by_this_call INTEGER NOT NULL, ledger_path TEXT, "
        "ledger_write_confirmed INTEGER NOT NULL, inventory_graph_write_confirmed INTEGER NOT NULL, "
        "last_verified_at TEXT, payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
    )


def write_activation_record_to_ledger(
    record: Mapping[str, Any],
    ledger_path: str | Path,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    """Fold one scheduled self-knowledge activation record into an injectable ledger."""

    plan = build_activation_record_write_plan(record)
    if not confirm:
        return {"status": "dry_run", "plan": plan}

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"status": "ledger_unavailable", "plan": plan}

    try:
        backup_path = backup_ledger(ledger)
    except (OSError, RuntimeError) as exc:
        return {"status": "backup_verification_failed", "reason": str(exc), "plan": plan}

    with sqlite3.connect(ledger) as conn:
        _ensure_activation_table(conn)
        cols = ", ".join(ACTIVATION_COLUMNS)
        placeholders = ", ".join("?" for _ in ACTIVATION_COLUMNS)
        updates = ", ".join(
            f"{column}=excluded.{column}"
            for column in ACTIVATION_COLUMNS
            if column != "activation_ref"
        )
        row = plan["row"]
        conn.execute(
            f'INSERT INTO "{ACTIVATION_TABLE}" ({cols}) VALUES ({placeholders}) '
            f"ON CONFLICT(activation_ref) DO UPDATE SET {updates}",
            tuple(row.get(column) for column in ACTIVATION_COLUMNS),
        )
        conn.commit()

    return {
        "status": "written",
        "backup_path": str(backup_path),
        "table": ACTIVATION_TABLE,
        "activation_ref": plan["row"]["activation_ref"],
        "fold_source": plan["fold_source"],
    }


def build_inventory_graph_write_plan(graph: Mapping[str, Any]) -> dict[str, Any]:
    fold_source = _graph_fold_source(graph)
    fold_at = _utc_now_iso()
    owner_scope = str(graph.get("owner_scope") or "pc")
    node_rows: list[dict[str, Any]] = []
    for node_id, node in dict(graph.get("nodes") or {}).items():
        if not isinstance(node, Mapping):
            continue
        payload = dict(node)
        payload.setdefault("id", str(node_id))
        payload.setdefault("kind", str(node.get("kind") or "unknown"))
        node_rows.append(
            {
                "node_id": str(node_id),
                "kind": str(payload.get("kind") or "unknown"),
                "owner_scope": str(payload.get("owner_scope") or owner_scope),
                "health_status": payload.get("health_status"),
                "activation_state": payload.get("activation_state"),
                "last_seen_at": payload.get("last_seen_at"),
                "last_verified_at": payload.get("last_verified_at"),
                "payload_json": _stable_json(payload),
                "_fold_source": fold_source,
                "_fold_at": fold_at,
            }
        )

    edge_rows: list[dict[str, Any]] = []
    for edge in graph.get("edges") or ():
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        relation = str(edge.get("relation") or "")
        if not source or not target or not relation:
            continue
        edge_rows.append(
            {
                "source_node_id": source,
                "target_node_id": target,
                "relation": relation,
                "owner_scope": str(edge.get("owner_scope") or owner_scope),
                "_fold_source": fold_source,
                "_fold_at": fold_at,
            }
        )
    return {
        "node_table": GRAPH_NODE_TABLE,
        "edge_table": GRAPH_EDGE_TABLE,
        "fold_source": fold_source,
        "node_rows": node_rows,
        "edge_rows": edge_rows,
    }


def _ensure_graph_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{GRAPH_NODE_TABLE}" ('
        "node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_scope TEXT NOT NULL, "
        "health_status TEXT, activation_state TEXT, last_seen_at TEXT, last_verified_at TEXT, "
        "payload_json TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL)"
    )
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{GRAPH_EDGE_TABLE}" ('
        "source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation TEXT NOT NULL, "
        "owner_scope TEXT NOT NULL, _fold_source TEXT NOT NULL, _fold_at TEXT NOT NULL, "
        "UNIQUE(source_node_id, target_node_id, relation, _fold_source))"
    )


def write_inventory_graph_to_ledger(
    graph: Mapping[str, Any],
    ledger_path: str | Path,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    """Fold self-knowledge graph nodes/edges into an injectable SQLite ledger."""

    plan = build_inventory_graph_write_plan(graph)
    if not confirm:
        return {"status": "dry_run", "plan": plan}

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"status": "ledger_unavailable", "plan": plan}

    try:
        backup_path = backup_ledger(ledger)
    except (OSError, RuntimeError) as exc:
        return {"status": "backup_verification_failed", "reason": str(exc), "plan": plan}

    with sqlite3.connect(ledger) as conn:
        _ensure_graph_tables(conn)
        conn.execute(f'DELETE FROM "{GRAPH_EDGE_TABLE}" WHERE "_fold_source" = ?', (plan["fold_source"],))
        conn.execute(f'DELETE FROM "{GRAPH_NODE_TABLE}" WHERE "_fold_source" = ?', (plan["fold_source"],))

        node_cols = ", ".join(GRAPH_NODE_COLUMNS)
        node_placeholders = ", ".join("?" for _ in GRAPH_NODE_COLUMNS)
        for row in plan["node_rows"]:
            conn.execute(
                f'INSERT INTO "{GRAPH_NODE_TABLE}" ({node_cols}) VALUES ({node_placeholders})',
                tuple(row.get(column) for column in GRAPH_NODE_COLUMNS),
            )

        edge_cols = ", ".join(GRAPH_EDGE_COLUMNS)
        edge_placeholders = ", ".join("?" for _ in GRAPH_EDGE_COLUMNS)
        for row in plan["edge_rows"]:
            conn.execute(
                f'INSERT INTO "{GRAPH_EDGE_TABLE}" ({edge_cols}) VALUES ({edge_placeholders})',
                tuple(row.get(column) for column in GRAPH_EDGE_COLUMNS),
            )
        conn.commit()

    return {
        "status": "written",
        "backup_path": str(backup_path),
        "node_count": len(plan["node_rows"]),
        "edge_count": len(plan["edge_rows"]),
        "node_table": GRAPH_NODE_TABLE,
        "edge_table": GRAPH_EDGE_TABLE,
        "fold_source": plan["fold_source"],
    }


def _read_inventory_graph_from_ledger(
    ledger_path: str | Path,
    *,
    owner_scope: str | None = None,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    with sqlite3.connect(ledger_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        if GRAPH_NODE_TABLE not in tables or GRAPH_EDGE_TABLE not in tables:
            return {"schema_version": "self_knowledge_inventory_graph_v1", "owner_scope": owner_scope or "pc", "nodes": nodes, "edges": edges}
        node_sql = f'SELECT * FROM "{GRAPH_NODE_TABLE}"'
        node_args: tuple[Any, ...] = ()
        if owner_scope is not None:
            node_sql += " WHERE owner_scope = ?"
            node_args = (owner_scope,)
        for row in conn.execute(node_sql, node_args):
            payload = json.loads(row["payload_json"])
            payload.setdefault("id", row["node_id"])
            payload.setdefault("kind", row["kind"])
            nodes[row["node_id"]] = payload

        edge_sql = f'SELECT * FROM "{GRAPH_EDGE_TABLE}"'
        edge_args: tuple[Any, ...] = ()
        if owner_scope is not None:
            edge_sql += " WHERE owner_scope = ?"
            edge_args = (owner_scope,)
        for row in conn.execute(edge_sql, edge_args):
            edges.append(
                {
                    "source": row["source_node_id"],
                    "target": row["target_node_id"],
                    "relation": row["relation"],
                }
            )
    return {
        "schema_version": "self_knowledge_inventory_graph_v1",
        "owner_scope": owner_scope or "pc",
        "nodes": nodes,
        "edges": edges,
    }


def query_inventory_graph_from_ledger(
    ledger_path: str | Path,
    *,
    resolution: str,
    owner_scope: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    from self_knowledge_system_enumerators import query_system_inventory

    graph = _read_inventory_graph_from_ledger(ledger_path, owner_scope=owner_scope)
    return query_system_inventory(graph, resolution=resolution, owner_scope=owner_scope, node_id=node_id)


__all__ = [
    "GAP_TABLE",
    "GAP_COLUMNS",
    "GRAPH_EDGE_TABLE",
    "GRAPH_NODE_TABLE",
    "ACTIVATION_TABLE",
    "backup_ledger",
    "build_activation_record_write_plan",
    "build_gap_write_plan",
    "build_inventory_graph_write_plan",
    "query_inventory_graph_from_ledger",
    "write_activation_record_to_ledger",
    "write_gaps_to_ledger",
    "write_inventory_graph_to_ledger",
]
