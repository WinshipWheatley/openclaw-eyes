"""Evidence-grounded Context Selection / Knowledge Packet v0.

This module compiles deterministic knowledge packets from the existing
OpenClaw SQLite/read-model substrate. It bridges Evidence Kettle rows,
generated read-model snapshots, generated tool posture read-models, and Corpus
Atlas exclusion metadata into a separate ``context_selection_*`` namespace.
It does not perform generic RAG, vector search, model calls, tool execution,
runtime activation, truth promotion, or raw private/no-go reads.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH
from evidence_kettle import init_evidence_kettle_schema, stable_json


CONTEXT_SELECTION_VERSION = "context_selection_knowledge_packet_v0"
DEFAULT_PACKET_ROOT = Path("generated/context_packets")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

ALLOWED_EVIDENCE_LABELS = {
    "generated_read_model_fact",
    "receipt_summary",
    "verification_evidence",
    "future_gated_capability",
    "unsupported_claim",
    "parsed_evidence",
}
CONDITIONAL_EVIDENCE_LABELS = {"source_claim", "operator_note"}
ALLOWED_RETRIEVAL = {"retrievable", "generated_read_model_only", "receipt_metadata_only"}
ALLOWED_INGESTION = {"generated_snapshot_only", "receipt_summary_only", "ingest_allowed"}
SAFE_SENSITIVITY = {"public_project", "internal_project"}
BLOCKED_RETRIEVAL = {
    "blocked_no_go",
    "blocked_sensitive",
    "blocked_unknown",
    "needs_operator_review",
}
BLOCKED_INGESTION = {"no_go", "needs_review", "not_for_ingestion"}
SENSITIVE_LABELS = {
    "private",
    "credential_boundary",
    "finance_boundary",
    "legal_tax_boundary",
    "runtime_log_boundary",
    "no_go",
    "sensitive_metadata_only",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "runtime_activation": False,
    "agent_activation": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "remote_access_allowed": False,
    "vector_search_used": False,
    "model_calls_used": False,
    "truth_claimed": False,
}

TASK_CATEGORY_HINTS = {
    "mission control": (
        "runtime_gate",
        "helm_state",
        "world_registry",
        "world_status",
        "artifact_registry",
        "source_inventory",
        "evidence_freshness",
        "operator_status",
        "unsupported_capability",
        "future_gated_capability",
        "generated_read_model_fact",
    ),
    "frontend prompt": (
        "runtime_gate",
        "helm_state",
        "world_registry",
        "world_status",
        "artifact_registry",
        "source_inventory",
        "evidence_freshness",
        "operator_status",
        "unsupported_capability",
        "future_gated_capability",
        "generated_read_model_fact",
    ),
    "client capsule": ("tool_posture",),
    "capsule candidates": ("tool_posture",),
}


@dataclass(frozen=True)
class ContextPacketResult:
    run_id: str
    packet_id: str
    db_path: str
    json_path: str
    operator_path: str
    selected_item_count: int
    excluded_item_count: int
    no_go_exclusion_count: int
    query: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _root() -> Path:
    return Path(__file__).resolve().parent


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(_root().resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return _root() / candidate


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS context_selection_runs (
  run_id TEXT PRIMARY KEY,
  selector_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  query_world TEXT,
  query_category TEXT,
  query_task TEXT,
  evidence_ingestion_run_id TEXT,
  source_basis_json TEXT NOT NULL,
  selected_item_count INTEGER NOT NULL DEFAULT 0,
  excluded_item_count INTEGER NOT NULL DEFAULT 0,
  no_go_exclusion_count INTEGER NOT NULL DEFAULT 0,
  packet_count INTEGER NOT NULL DEFAULT 0,
  generated_json_path TEXT,
  generated_operator_path TEXT,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  vector_search_used INTEGER NOT NULL DEFAULT 0,
  model_calls_used INTEGER NOT NULL DEFAULT 0,
  network_access_attempted INTEGER NOT NULL DEFAULT 0,
  tool_execution_attempted INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  FOREIGN KEY (evidence_ingestion_run_id) REFERENCES evidence_ingestion_runs(ingestion_run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packets (
  packet_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  packet_kind TEXT NOT NULL,
  selector_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  query_json TEXT NOT NULL,
  packet_json TEXT NOT NULL,
  selected_item_count INTEGER NOT NULL,
  excluded_item_count INTEGER NOT NULL,
  no_go_exclusion_count INTEGER NOT NULL,
  world_binding TEXT NOT NULL,
  evidence_categories_json TEXT NOT NULL,
  freshness_summary_json TEXT NOT NULL,
  canonicality_summary_json TEXT NOT NULL,
  sensitivity_summary_json TEXT NOT NULL,
  authority_posture_json TEXT NOT NULL,
  context_for_reasoning_only INTEGER NOT NULL DEFAULT 1,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES context_selection_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packet_items (
  packet_item_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  item_order INTEGER NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  item_kind TEXT NOT NULL,
  evidence_label TEXT NOT NULL,
  evidence_category TEXT NOT NULL,
  evidence_key TEXT NOT NULL,
  evidence_value_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  freshness_label TEXT NOT NULL,
  canonicality TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  retrieval_eligibility TEXT NOT NULL,
  ingestion_eligibility TEXT NOT NULL,
  world_binding TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (packet_id) REFERENCES context_packets(packet_id) ON DELETE CASCADE,
  UNIQUE(packet_id, source_table, source_id, evidence_key)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packet_sources (
  source_ref_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_type TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES context_packets(packet_id) ON DELETE CASCADE,
  UNIQUE(packet_id, source_table, source_id, source_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packet_world_bindings (
  binding_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  world_id TEXT NOT NULL,
  binding_basis TEXT NOT NULL,
  confidence REAL NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES context_packets(packet_id) ON DELETE CASCADE,
  UNIQUE(packet_id, world_id, binding_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packet_exclusions (
  exclusion_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  packet_id TEXT,
  source_table TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  exclusion_reason TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  retrieval_eligibility TEXT NOT NULL,
  ingestion_eligibility TEXT NOT NULL,
  no_go_boundary INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES context_selection_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (packet_id) REFERENCES context_packets(packet_id) ON DELETE CASCADE,
  UNIQUE(run_id, source_table, source_id, exclusion_reason)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packet_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  packet_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES context_selection_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (packet_id) REFERENCES context_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_context_runs_created ON context_selection_runs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_context_packets_run ON context_packets(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_items_packet ON context_packet_items(packet_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_items_category ON context_packet_items(evidence_category)",
        "CREATE INDEX IF NOT EXISTS idx_context_worlds_world ON context_packet_world_bindings(world_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_exclusions_run ON context_packet_exclusions(run_id)",
    )


def init_context_selection_schema(db_path: str | Path | None = None) -> str:
    path = init_evidence_kettle_schema(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def context_selection_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_context_selection_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'context_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_evidence_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT ingestion_run_id
FROM evidence_ingestion_runs
ORDER BY completed_at DESC, started_at DESC, ingestion_run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["ingestion_run_id"] if row else None


def _latest_atlas_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM corpus_atlas_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _latest_context_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM context_selection_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _latest_packet_id(conn: sqlite3.Connection, run_id: str | None = None) -> str | None:
    if run_id:
        row = conn.execute(
            """
SELECT packet_id
FROM context_packets
WHERE run_id = ?
ORDER BY created_at DESC, packet_id DESC
LIMIT 1
""".strip(),
            (run_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """
SELECT packet_id
FROM context_packets
ORDER BY created_at DESC, packet_id DESC
LIMIT 1
""".strip()
        ).fetchone()
    return row["packet_id"] if row else None


def _task_categories(task: str | None) -> tuple[str, ...]:
    if not task:
        return ()
    lowered = task.lower()
    categories: list[str] = []
    for needle, hints in TASK_CATEGORY_HINTS.items():
        if needle in lowered:
            for hint in hints:
                if hint not in categories:
                    categories.append(hint)
    return tuple(categories)


def _query_categories(category: str | None, task: str | None) -> tuple[str, ...]:
    categories: list[str] = []
    if category:
        categories.append(category)
    for hint in _task_categories(task):
        if hint not in categories:
            categories.append(hint)
    return tuple(categories)


def _category_predicate(categories: Iterable[str]) -> tuple[str, list[Any]]:
    category_values = tuple(categories)
    if not category_values:
        return "1 = 1", []

    clauses: list[str] = []
    params: list[Any] = []
    for category in category_values:
        if category == "future_gated_capability":
            clauses.append("ei.evidence_label = ?")
            params.append("future_gated_capability")
        elif category == "generated_read_model_fact":
            clauses.append("ei.evidence_label = ?")
            params.append("generated_read_model_fact")
        elif category == "unsupported_capability":
            clauses.append("ei.evidence_label = ?")
            params.append("unsupported_claim")
        elif category == "tool_posture":
            continue
        else:
            clauses.append("ei.evidence_category = ?")
            params.append(category)
    if not clauses:
        return "0 = 1", []
    return "(" + " OR ".join(clauses) + ")", params


def _eligible_evidence_predicate() -> str:
    allowed_labels = ",".join(f"'{label}'" for label in sorted(ALLOWED_EVIDENCE_LABELS))
    conditional_labels = ",".join(f"'{label}'" for label in sorted(CONDITIONAL_EVIDENCE_LABELS))
    allowed_retrieval = ",".join(f"'{label}'" for label in sorted(ALLOWED_RETRIEVAL))
    allowed_ingestion = ",".join(f"'{label}'" for label in sorted(ALLOWED_INGESTION))
    safe_sensitivity = ",".join(f"'{label}'" for label in sorted(SAFE_SENSITIVITY))
    return f"""
ei.runtime_authority = 0
AND ei.truth_claimed = 0
AND (
  ei.evidence_label IN ({allowed_labels})
  OR (ei.evidence_label IN ({conditional_labels}) AND ei.ingestion_eligibility = 'ingest_allowed')
)
AND ei.retrieval_eligibility IN ({allowed_retrieval})
AND ei.ingestion_eligibility IN ({allowed_ingestion})
AND ei.sensitivity_label IN ({safe_sensitivity})
""".strip()


def _safe_evidence_item(row: sqlite3.Row) -> dict[str, Any]:
    value = json.loads(row["evidence_value_json"])
    return {
        "item_id": row["evidence_id"],
        "source_table": "evidence_items",
        "source_id": row["evidence_id"],
        "source_path": row["source_path"],
        "source_type": row["source_type"],
        "item_kind": "selected_evidence",
        "evidence_label": row["evidence_label"],
        "evidence_category": row["evidence_category"],
        "evidence_key": row["evidence_key"],
        "evidence_value": value,
        "evidence_value_json": row["evidence_value_json"],
        "summary": row["summary"],
        "freshness_label": row["freshness_label"],
        "canonicality": row["canonicality"],
        "sensitivity_label": row["sensitivity_label"],
        "retrieval_eligibility": row["retrieval_eligibility"],
        "ingestion_eligibility": row["ingestion_eligibility"],
        "world_binding": row["world_binding"],
        "provenance": {
            "evidence_id": row["evidence_id"],
            "source_id": row["source_id"],
            "corpus_path_id": row["corpus_path_id"],
            "ingestion_run_id": row["ingestion_run_id"],
            "source_pointer": json.loads(row["source_pointer_json"]),
            "truth_claimed": False,
            "runtime_authority": False,
        },
    }


def _selected_evidence_rows(
    conn: sqlite3.Connection,
    *,
    ingestion_run_id: str | None,
    world: str | None,
    categories: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    if not ingestion_run_id:
        return []
    category_sql, category_params = _category_predicate(categories)
    world_sql = ""
    params: list[Any] = [ingestion_run_id]
    params.extend(category_params)
    if world:
        world_sql = """
AND (
  ei.world_binding IN (?, 'cross_world')
  OR EXISTS (
    SELECT 1
    FROM evidence_world_bindings wb
    WHERE wb.evidence_id = ei.evidence_id
      AND wb.world_id = ?
  )
)
""".strip()
        params.extend([world, world])
    rows = conn.execute(
        f"""
SELECT
  ei.evidence_id, ei.source_id, ei.corpus_path_id, ei.root_id, ei.source_path,
  ei.source_type, ei.evidence_label, ei.evidence_category, ei.evidence_key,
  ei.evidence_value_json, ei.summary, ei.freshness_label, ei.canonicality,
  ei.sensitivity_label, ei.retrieval_eligibility, ei.ingestion_eligibility,
  ei.world_binding, ei.ingestion_run_id, ei.source_pointer_json
FROM evidence_items ei
WHERE ei.ingestion_run_id = ?
  AND ({category_sql})
  AND ({_eligible_evidence_predicate()})
  {world_sql}
ORDER BY
  CASE ei.evidence_label
    WHEN 'future_gated_capability' THEN 0
    WHEN 'unsupported_claim' THEN 1
    WHEN 'generated_read_model_fact' THEN 2
    ELSE 3
  END,
  ei.evidence_category,
  ei.evidence_key,
  ei.source_path
LIMIT ?
""".strip(),
        (*params, limit),
    ).fetchall()
    return [_safe_evidence_item(row) for row in rows]


def _read_generated_json(read_model_root: Path, name: str) -> tuple[str, dict[str, Any]] | None:
    root = read_model_root.resolve()
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return path.as_posix(), data


def _read_model_item(
    *,
    source_path: str,
    read_model_name: str,
    key: str,
    value: Any,
    summary: str,
    label: str = "generated_read_model_fact",
    category: str = "tool_posture",
    world: str = "build",
) -> dict[str, Any]:
    value_json = stable_json(value)
    source_id = _row_id("readmodel", source_path, key)
    return {
        "item_id": _row_id("ctxrmitem", source_path, key, value_json),
        "source_table": "generated_read_model_export",
        "source_id": source_id,
        "source_path": _display_path(source_path),
        "source_type": read_model_name,
        "item_kind": "selected_generated_read_model_fact",
        "evidence_label": label,
        "evidence_category": category,
        "evidence_key": key,
        "evidence_value": value,
        "evidence_value_json": value_json,
        "summary": summary,
        "freshness_label": "generated_read_model_fact",
        "canonicality": "generated_current",
        "sensitivity_label": "internal_project",
        "retrieval_eligibility": "generated_read_model_only",
        "ingestion_eligibility": "generated_snapshot_only",
        "world_binding": world,
        "provenance": {
            "source_path": _display_path(source_path),
            "read_model_name": read_model_name,
            "read_model_export": True,
            "body_stored": False,
            "truth_claimed": False,
            "runtime_authority": False,
        },
    }


def _tool_posture_items(read_model_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    inventory = _read_generated_json(read_model_root, "tool_inventory.json")
    if inventory:
        source_path, data = inventory
        for key in ("observed_candidate_count", "detected_count", "not_detected_count"):
            if key in data:
                items.append(
                    _read_model_item(
                        source_path=source_path,
                        read_model_name="tool_inventory",
                        key=f"tool_inventory:{key}",
                        value=data[key],
                        summary=f"Tool inventory {key}={data[key]}.",
                    )
                )
        high_risk = [tool["tool_id"] for tool in data.get("high_risk_detected_tools") or []]
        local_llm = data.get("local_llm_findings") or {}
        sqlite_findings = data.get("sqlite_findings") or {}
        items.extend(
            [
                _read_model_item(
                    source_path=source_path,
                    read_model_name="tool_inventory",
                    key="tool_inventory:high_risk_detected_tools",
                    value=high_risk,
                    summary="Tool inventory lists high-risk detected tools as metadata only.",
                ),
                _read_model_item(
                    source_path=source_path,
                    read_model_name="tool_inventory",
                    key="tool_inventory:local_llm_findings",
                    value={
                        "detected_count": local_llm.get("detected_count", 0),
                        "tool_ids": [tool["tool_id"] for tool in local_llm.get("tools") or []],
                    },
                    summary="Tool inventory local LLM findings remain observed metadata only.",
                    label="unsupported_claim",
                ),
                _read_model_item(
                    source_path=source_path,
                    read_model_name="tool_inventory",
                    key="tool_inventory:sqlite_findings",
                    value={
                        "detected_count": sqlite_findings.get("detected_count", 0),
                        "tool_ids": [tool["tool_id"] for tool in sqlite_findings.get("tools") or []],
                    },
                    summary="Tool inventory SQLite findings are inspection metadata only.",
                ),
            ]
        )
        for key in (
            "tool_activation_allowed",
            "runtime_authority",
            "integration_authority",
            "model_execution_allowed",
            "container_execution_allowed",
            "remote_access_allowed",
            "network_authority",
        ):
            if key in data:
                items.append(
                    _read_model_item(
                        source_path=source_path,
                        read_model_name="tool_inventory",
                        key=f"tool_inventory:{key}",
                        value=data[key],
                        summary=f"Tool inventory no-authority flag {key}={data[key]}.",
                    )
                )

    intake = _read_generated_json(read_model_root, "tool_intake.json")
    if intake:
        source_path, data = intake
        for key in (
            "candidate_count",
            "inventory_linked_candidate_count",
            "installed_candidate_count",
        ):
            if key in data:
                items.append(
                    _read_model_item(
                        source_path=source_path,
                        read_model_name="tool_intake",
                        key=f"tool_intake:{key}",
                        value=data[key],
                        summary=f"Tool intake {key}={data[key]}.",
                    )
                )
        for list_key in (
            "installed_candidates",
            "high_fit_candidates",
            "high_risk_candidates",
            "sandbox_later_candidates",
            "client_capsule_candidates",
        ):
            tools = data.get(list_key) or []
            items.append(
                _read_model_item(
                    source_path=source_path,
                    read_model_name="tool_intake",
                    key=f"tool_intake:{list_key}",
                    value=[tool["tool_id"] for tool in tools],
                    summary=f"Tool intake exposes {list_key.replace('_', ' ')} as policy metadata.",
                    label="unsupported_claim" if list_key == "high_risk_candidates" else "generated_read_model_fact",
                )
            )
        for key in (
            "tool_install_allowed",
            "tool_execution_allowed",
            "integration_authority",
            "approval_authority",
            "runtime_authority",
            "network_authority",
            "model_execution_allowed",
            "container_execution_allowed",
            "remote_access_allowed",
        ):
            if key in data:
                items.append(
                    _read_model_item(
                        source_path=source_path,
                        read_model_name="tool_intake",
                        key=f"tool_intake:{key}",
                        value=data[key],
                        summary=f"Tool intake no-authority flag {key}={data[key]}.",
                    )
                )
    return items


def _exclusion_rows(
    conn: sqlite3.Connection,
    *,
    atlas_run_id: str | None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    if not atlas_run_id:
        return [], 0
    sensitive = ",".join(f"'{label}'" for label in sorted(SENSITIVE_LABELS))
    blocked_retrieval = ",".join(f"'{label}'" for label in sorted(BLOCKED_RETRIEVAL))
    blocked_ingestion = ",".join(f"'{label}'" for label in sorted(BLOCKED_INGESTION))
    base_sql = f"""
FROM corpus_paths
WHERE run_id = ?
  AND (
    sensitivity_label IN ({sensitive})
    OR retrieval_eligibility IN ({blocked_retrieval})
    OR ingestion_eligibility IN ({blocked_ingestion})
    OR raw_content_eligibility = 'no_go'
  )
""".strip()
    total = conn.execute(f"SELECT COUNT(*) {base_sql}", (atlas_run_id,)).fetchone()[0]
    rows = conn.execute(
        f"""
SELECT path_id, relative_path, sensitivity_label, retrieval_eligibility,
       ingestion_eligibility, raw_content_eligibility
{base_sql}
ORDER BY
  CASE raw_content_eligibility WHEN 'no_go' THEN 0 ELSE 1 END,
  relative_path
LIMIT ?
""".strip(),
        (atlas_run_id, limit),
    ).fetchall()
    exclusions = []
    for row in rows:
        no_go = (
            row["raw_content_eligibility"] == "no_go"
            or row["sensitivity_label"] in SENSITIVE_LABELS
            or row["retrieval_eligibility"] in BLOCKED_RETRIEVAL
            or row["ingestion_eligibility"] in BLOCKED_INGESTION
        )
        exclusions.append(
            {
                "source_table": "corpus_paths",
                "source_id": row["path_id"],
                "source_path": row["relative_path"],
                "exclusion_reason": "corpus_path_not_context_selectable",
                "sensitivity_label": row["sensitivity_label"],
                "retrieval_eligibility": row["retrieval_eligibility"],
                "ingestion_eligibility": row["ingestion_eligibility"],
                "no_go_boundary": bool(no_go),
            }
        )
    return exclusions, total


def _dedupe_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (item["source_table"], item["source_id"], item["evidence_key"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _summaries(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "evidence_label": dict(sorted(Counter(item["evidence_label"] for item in items).items())),
        "evidence_category": dict(sorted(Counter(item["evidence_category"] for item in items).items())),
        "freshness_label": dict(sorted(Counter(item["freshness_label"] for item in items).items())),
        "canonicality": dict(sorted(Counter(item["canonicality"] for item in items).items())),
        "sensitivity_label": dict(sorted(Counter(item["sensitivity_label"] for item in items).items())),
        "retrieval_eligibility": dict(
            sorted(Counter(item["retrieval_eligibility"] for item in items).items())
        ),
        "ingestion_eligibility": dict(
            sorted(Counter(item["ingestion_eligibility"] for item in items).items())
        ),
        "world_binding": dict(sorted(Counter(item["world_binding"] for item in items).items())),
    }


def _packet_json(
    *,
    run_id: str,
    packet_id: str,
    query: dict[str, Any],
    evidence_run_id: str | None,
    selected_items: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    no_go_exclusion_count: int,
    created_at: str,
) -> dict[str, Any]:
    summaries = _summaries(selected_items)
    world_bindings = sorted(
        {
            item["world_binding"]
            for item in selected_items
            if item["world_binding"] not in {"unknown", "no_world", ""}
        }
    )
    next_safe_moves = [
        {
            "source_path": item["source_path"],
            "summary": item["summary"],
            "value": item["evidence_value"],
        }
        for item in selected_items
        if item["evidence_key"].endswith("next_safe_move") or item["evidence_key"] == "next_safe_move"
    ]
    future_or_unsupported = [
        {
            "source_path": item["source_path"],
            "label": item["evidence_label"],
            "category": item["evidence_category"],
            "key": item["evidence_key"],
            "summary": item["summary"],
        }
        for item in selected_items
        if item["evidence_label"] in {"future_gated_capability", "unsupported_claim"}
    ]
    return {
        "packet_version": CONTEXT_SELECTION_VERSION,
        "packet_id": packet_id,
        "run_id": run_id,
        "packet_kind": "evidence_grounded_context_packet",
        "created_at": created_at,
        "query": query,
        "selector": {
            "selector_version": CONTEXT_SELECTION_VERSION,
            "selection_strategy": "deterministic_sql_and_generated_read_model_filters",
            "generic_rag": False,
            "vector_search_used": False,
            "model_calls_used": False,
        },
        "source_tables_used": [
            "evidence_items",
            "read_model_snapshots",
            "corpus_paths",
            "generated/read_models/tool_inventory.json",
            "generated/read_models/tool_intake.json",
        ],
        "evidence_ingestion_run_id": evidence_run_id,
        "selected_item_count": len(selected_items),
        "excluded_item_count": len(exclusions),
        "no_go_exclusion_count": no_go_exclusion_count,
        "context_for_reasoning_only": True,
        "truth_claimed": False,
        "authority_posture": dict(NO_AUTHORITY_FLAGS),
        "summaries": summaries,
        "world_bindings": world_bindings,
        "selected_items": [
            {
                key: value
                for key, value in item.items()
                if key not in {"evidence_value_json"}
            }
            for item in selected_items
        ],
        "next_safe_moves": next_safe_moves,
        "future_or_unsupported_facts": future_or_unsupported,
        "exclusions": {
            "policy": "No-go, blocked, sensitive, unknown, and needs-review paths are excluded from selected context.",
            "sample": exclusions[:25],
            "total_recorded": len(exclusions),
            "no_go_exclusion_count": no_go_exclusion_count,
        },
        "receipt": {
            "receipt_kind": "context_packet_compile_receipt",
            "runtime_authority": False,
            "truth_promoted": False,
            "raw_private_data_read": False,
            "raw_no_go_content_read": False,
            "network_access_attempted": False,
            "tool_execution_attempted": False,
            "model_calls_used": False,
            "vector_search_used": False,
        },
    }


def _operator_packet(packet: dict[str, Any]) -> str:
    summaries = packet["summaries"]
    items = packet["selected_items"]
    item_lines = []
    for item in items[:20]:
        item_lines.append(
            "- "
            + item["source_path"].replace("\n", "\\n")
            + f" :: {item['evidence_label']} / {item['evidence_category']} / {item['evidence_key']}"
        )
    if not item_lines:
        item_lines.append("- none")
    future_lines = []
    for item in packet["future_or_unsupported_facts"][:12]:
        future_lines.append(
            "- "
            + item["source_path"].replace("\n", "\\n")
            + f" :: {item['label']} / {item['key']}"
        )
    if not future_lines:
        future_lines.append("- none")
    next_safe = []
    for item in packet["next_safe_moves"][:6]:
        next_safe.append("- " + item["source_path"].replace("\n", "\\n") + f" :: {item['summary']}")
    if not next_safe:
        next_safe.append("- none")

    category_counts = ", ".join(
        f"{key}={value}" for key, value in summaries["evidence_category"].items()
    ) or "none"
    label_counts = ", ".join(
        f"{key}={value}" for key, value in summaries["evidence_label"].items()
    ) or "none"
    worlds = ", ".join(packet["world_bindings"]) or "none"
    lines = [
        "# Context Selection Knowledge Packet v0",
        "",
        "Evidence:",
        f"- Packet `{packet['packet_id']}` selected {packet['selected_item_count']} bounded evidence items.",
        f"- Query: `{stable_json(packet['query']).strip()}`.",
        f"- Evidence labels: {label_counts}.",
        f"- Evidence categories: {category_counts}.",
        f"- World bindings: {worlds}.",
        "",
        "Selected items:",
        *item_lines,
        "",
        "Future/unsupported facts:",
        *future_lines,
        "",
        "Next safe moves:",
        *next_safe,
        "",
        "Boundary:",
        "- This is selected evidence and bounded context, not truth promotion.",
        "- Unknown, needs-review, sensitive, blocked, and no-go material is excluded.",
        "- Receipt summaries remain metadata only; raw private/no-go bodies are not included.",
        "- No generic RAG, vector search, embeddings, model calls, tool execution, network calls, or runtime activation are used.",
        "",
        "Blocked:",
        f"- Excluded records recorded: {packet['excluded_item_count']}.",
        f"- No-go exclusion count: {packet['no_go_exclusion_count']}.",
        "- runtime_authority=false; model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false.",
        "",
        "Next safe move:",
        "- Use this packet as reasoning context only; any synthesis, write-back, promotion, runtime action, or tool use needs a separate scoped lane.",
    ]
    return "\n".join(lines) + "\n"


def _write_packet_artifacts(packet: dict[str, Any], output_root: str | Path) -> tuple[str, str]:
    root = _resolve_repo_path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "context_packet_latest.json"
    operator_path = root / "context_packet_latest.md"
    json_path.write_text(stable_json(packet), encoding="utf-8")
    operator_path.write_text(_operator_packet(packet), encoding="utf-8")
    return _display_path(json_path), _display_path(operator_path)


def _insert_packet_rows(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    packet_id: str,
    packet: dict[str, Any],
    selected_items: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    created_at: str,
) -> None:
    summaries = packet["summaries"]
    conn.execute("DELETE FROM context_selection_runs WHERE run_id = ?", (run_id,))
    conn.execute(
        """
INSERT INTO context_selection_runs (
  run_id, selector_version, created_at, completed_at, query_world, query_category,
  query_task, evidence_ingestion_run_id, source_basis_json, selected_item_count,
  excluded_item_count, no_go_exclusion_count, packet_count, generated_json_path,
  generated_operator_path, runtime_authority, vector_search_used, model_calls_used,
  network_access_attempted, tool_execution_attempted, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0, 0, 0, 0, 0, ?)
""".strip(),
        (
            run_id,
            CONTEXT_SELECTION_VERSION,
            created_at,
            created_at,
            packet["query"].get("world"),
            packet["query"].get("category"),
            packet["query"].get("task"),
            packet["evidence_ingestion_run_id"],
            stable_json(
                {
                    "source_tables_used": packet["source_tables_used"],
                    "generic_rag": False,
                    "vector_search": False,
                    "model_calls": False,
                    "runtime_activation": False,
                }
            ),
            len(selected_items),
            len(exclusions),
            packet["no_go_exclusion_count"],
            packet.get("generated_json_path"),
            packet.get("generated_operator_path"),
            "Deterministic evidence-grounded packet compile; context for reasoning only.",
        ),
    )
    conn.execute(
        """
INSERT INTO context_packets (
  packet_id, run_id, packet_kind, selector_version, created_at, query_json,
  packet_json, selected_item_count, excluded_item_count, no_go_exclusion_count,
  world_binding, evidence_categories_json, freshness_summary_json,
  canonicality_summary_json, sensitivity_summary_json, authority_posture_json,
  context_for_reasoning_only, truth_claimed, runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0)
""".strip(),
        (
            packet_id,
            run_id,
            packet["packet_kind"],
            CONTEXT_SELECTION_VERSION,
            created_at,
            stable_json(packet["query"]),
            stable_json(packet),
            len(selected_items),
            len(exclusions),
            packet["no_go_exclusion_count"],
            ",".join(packet["world_bindings"]) or "none",
            stable_json(summaries["evidence_category"]),
            stable_json(summaries["freshness_label"]),
            stable_json(summaries["canonicality"]),
            stable_json(summaries["sensitivity_label"]),
            stable_json(packet["authority_posture"]),
        ),
    )

    for index, item in enumerate(selected_items):
        conn.execute(
            """
INSERT INTO context_packet_items (
  packet_item_id, packet_id, item_order, source_table, source_id, source_path,
  item_kind, evidence_label, evidence_category, evidence_key,
  evidence_value_json, summary, freshness_label, canonicality,
  sensitivity_label, retrieval_eligibility, ingestion_eligibility,
  world_binding, provenance_json, truth_claimed, runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
ON CONFLICT(packet_id, source_table, source_id, evidence_key) DO UPDATE SET
  item_order = excluded.item_order,
  summary = excluded.summary,
  evidence_value_json = excluded.evidence_value_json,
  provenance_json = excluded.provenance_json
""".strip(),
            (
                _row_id("ctxitem", packet_id, item["source_table"], item["source_id"], item["evidence_key"]),
                packet_id,
                index,
                item["source_table"],
                item["source_id"],
                item["source_path"],
                item["item_kind"],
                item["evidence_label"],
                item["evidence_category"],
                item["evidence_key"],
                item["evidence_value_json"],
                item["summary"],
                item["freshness_label"],
                item["canonicality"],
                item["sensitivity_label"],
                item["retrieval_eligibility"],
                item["ingestion_eligibility"],
                item["world_binding"],
                stable_json(item["provenance"]),
            ),
        )
        conn.execute(
            """
INSERT INTO context_packet_sources (
  source_ref_id, packet_id, source_table, source_id, source_path,
  source_type, provenance_json
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(packet_id, source_table, source_id, source_path) DO UPDATE SET
  provenance_json = excluded.provenance_json
""".strip(),
            (
                _row_id("ctxsrc", packet_id, item["source_table"], item["source_id"], item["source_path"]),
                packet_id,
                item["source_table"],
                item["source_id"],
                item["source_path"],
                item["source_type"],
                stable_json(item["provenance"]),
            ),
        )
        if item["world_binding"] not in {"unknown", "no_world", ""}:
            conn.execute(
                """
INSERT INTO context_packet_world_bindings (
  binding_id, packet_id, world_id, binding_basis, confidence
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(packet_id, world_id, binding_basis) DO UPDATE SET
  confidence = excluded.confidence
""".strip(),
                (
                    _row_id("ctxworld", packet_id, item["world_binding"], "selected_item_world_binding"),
                    packet_id,
                    item["world_binding"],
                    "selected_item_world_binding",
                    0.9,
                ),
            )

    for exclusion in exclusions:
        conn.execute(
            """
INSERT INTO context_packet_exclusions (
  exclusion_id, run_id, packet_id, source_table, source_id, source_path,
  exclusion_reason, sensitivity_label, retrieval_eligibility,
  ingestion_eligibility, no_go_boundary
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id, source_table, source_id, exclusion_reason) DO UPDATE SET
  no_go_boundary = excluded.no_go_boundary
""".strip(),
            (
                _row_id("ctxexcl", run_id, exclusion["source_table"], exclusion["source_id"], exclusion["exclusion_reason"]),
                run_id,
                packet_id,
                exclusion["source_table"],
                exclusion["source_id"],
                exclusion["source_path"],
                exclusion["exclusion_reason"],
                exclusion["sensitivity_label"],
                exclusion["retrieval_eligibility"],
                exclusion["ingestion_eligibility"],
                1 if exclusion["no_go_boundary"] else 0,
            ),
        )

    receipt = {
        "run_id": run_id,
        "packet_id": packet_id,
        "selected_item_count": len(selected_items),
        "excluded_item_count": len(exclusions),
        "no_go_exclusion_count": packet["no_go_exclusion_count"],
        **packet["receipt"],
    }
    conn.execute(
        """
INSERT INTO context_packet_receipts (
  receipt_id, run_id, packet_id, receipt_kind, receipt_json, created_at,
  runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, 0)
""".strip(),
        (
            _row_id("ctxreceipt", run_id, packet_id, "compile"),
            run_id,
            packet_id,
            "context_packet_compile_receipt",
            stable_json(receipt),
            created_at,
        ),
    )


def compile_context_packet(
    db_path: str | Path | None = None,
    *,
    world: str | None = None,
    category: str | None = None,
    task: str | None = None,
    run_id: str | None = None,
    limit: int = 60,
    output_root: str | Path = DEFAULT_PACKET_ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> ContextPacketResult:
    if not (world or category or task):
        raise ValueError("at least one of world, category, or task is required")
    if limit <= 0:
        raise ValueError("limit must be positive")

    path = init_context_selection_schema(db_path)
    categories = _query_categories(category, task)
    created_at = utc_now()
    resolved_run_id = run_id or _row_id(
        "ctxrun",
        CONTEXT_SELECTION_VERSION,
        world or "",
        category or "",
        task or "",
        created_at,
    )
    packet_id = _row_id(
        "ctxpacket",
        CONTEXT_SELECTION_VERSION,
        resolved_run_id,
        world or "",
        category or "",
        task or "",
    )
    query = {
        "world": world,
        "category": category,
        "task": task,
        "task_category_hints": list(_task_categories(task)),
        "limit": limit,
    }

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        evidence_run_id = _latest_evidence_run_id(conn)
        atlas_run_id = _latest_atlas_run_id(conn)
        selected = _selected_evidence_rows(
            conn,
            ingestion_run_id=evidence_run_id,
            world=world,
            categories=categories,
            limit=limit,
        )
        if "tool_posture" in categories:
            selected.extend(_tool_posture_items(_resolve_repo_path(read_model_root)))
        selected = _dedupe_items(selected)[:limit]
        exclusions, no_go_total = _exclusion_rows(conn, atlas_run_id=atlas_run_id)
        packet = _packet_json(
            run_id=resolved_run_id,
            packet_id=packet_id,
            query=query,
            evidence_run_id=evidence_run_id,
            selected_items=selected,
            exclusions=exclusions,
            no_go_exclusion_count=no_go_total,
            created_at=created_at,
        )
        json_path, operator_path = _write_packet_artifacts(packet, output_root)
        packet["generated_json_path"] = json_path
        packet["generated_operator_path"] = operator_path
        json_path, operator_path = _write_packet_artifacts(packet, output_root)
        _insert_packet_rows(
            conn,
            run_id=resolved_run_id,
            packet_id=packet_id,
            packet=packet,
            selected_items=selected,
            exclusions=exclusions,
            created_at=created_at,
        )
        conn.commit()
        return ContextPacketResult(
            run_id=resolved_run_id,
            packet_id=packet_id,
            db_path=path,
            json_path=json_path,
            operator_path=operator_path,
            selected_item_count=len(selected),
            excluded_item_count=len(exclusions),
            no_go_exclusion_count=no_go_total,
            query=query,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_context_selection_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = init_context_selection_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_context_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "selector_version": CONTEXT_SELECTION_VERSION}
        run = dict(
            conn.execute(
                "SELECT * FROM context_selection_runs WHERE run_id = ?",
                (resolved_run_id,),
            ).fetchone()
        )
        packet_id = _latest_packet_id(conn, resolved_run_id)
        packet = None
        if packet_id:
            row = conn.execute(
                "SELECT packet_json FROM context_packets WHERE packet_id = ?",
                (packet_id,),
            ).fetchone()
            packet = json.loads(row["packet_json"]) if row else None
        counts = {}
        for field in ("evidence_label", "evidence_category", "world_binding"):
            rows = conn.execute(
                f"""
SELECT {field} AS label, COUNT(*) AS count
FROM context_packet_items
WHERE packet_id = ?
GROUP BY {field}
ORDER BY count DESC, label
""".strip(),
                (packet_id,),
            ).fetchall()
            counts[field] = {row["label"]: row["count"] for row in rows}
        return {
            "status": "ok",
            "selector_version": CONTEXT_SELECTION_VERSION,
            "run": run,
            "packet_id": packet_id,
            "counts": counts,
            "packet": packet,
        }
    finally:
        conn.close()


def query_context_selection_report_section(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    packet_id: str | None = None,
    section: str = "summary",
) -> dict[str, Any]:
    path = init_context_selection_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_context_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": section}
        resolved_packet_id = packet_id or _latest_packet_id(conn, resolved_run_id)
        if not resolved_packet_id:
            return {"status": "no_packets", "section": section, "run_id": resolved_run_id}
        if section == "summary":
            return build_context_selection_report(db_path=path, run_id=resolved_run_id)
        if section == "items":
            rows = conn.execute(
                """
SELECT item_order, source_table, source_path, evidence_label, evidence_category,
       evidence_key, summary, freshness_label, canonicality, sensitivity_label,
       retrieval_eligibility, ingestion_eligibility, world_binding
FROM context_packet_items
WHERE packet_id = ?
ORDER BY item_order
""".strip(),
                (resolved_packet_id,),
            ).fetchall()
            items = [dict(row) for row in rows]
        elif section == "sources":
            rows = conn.execute(
                """
SELECT source_table, source_id, source_path, source_type, provenance_json
FROM context_packet_sources
WHERE packet_id = ?
ORDER BY source_table, source_path
""".strip(),
                (resolved_packet_id,),
            ).fetchall()
            items = [dict(row) for row in rows]
        elif section == "exclusions":
            rows = conn.execute(
                """
SELECT source_table, source_path, exclusion_reason, sensitivity_label,
       retrieval_eligibility, ingestion_eligibility, no_go_boundary
FROM context_packet_exclusions
WHERE packet_id = ?
ORDER BY no_go_boundary DESC, source_path
LIMIT 200
""".strip(),
                (resolved_packet_id,),
            ).fetchall()
            items = [dict(row) for row in rows]
        elif section == "receipts":
            rows = conn.execute(
                """
SELECT receipt_id, receipt_kind, receipt_json, created_at, runtime_authority
FROM context_packet_receipts
WHERE packet_id = ?
ORDER BY created_at, receipt_id
""".strip(),
                (resolved_packet_id,),
            ).fetchall()
            items = [dict(row) for row in rows]
        else:
            raise ValueError(f"unknown context selection report section: {section}")
        return {
            "status": "ok",
            "section": section,
            "run_id": resolved_run_id,
            "packet_id": resolved_packet_id,
            "items": items,
        }
    finally:
        conn.close()


def format_context_selection_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Context Selection Knowledge Packet v0\n\nNo context selection runs are recorded."
    run = report["run"]
    counts = report["counts"]
    lines = [
        "Context Selection Knowledge Packet v0",
        "",
        f"Run: `{run['run_id']}`",
        f"Packet: `{report['packet_id']}`",
        f"Query world: `{run['query_world']}`",
        f"Query category: `{run['query_category']}`",
        f"Query task: `{run['query_task']}`",
        f"Selected items: {run['selected_item_count']}",
        f"Excluded records: {run['excluded_item_count']}",
        f"No-go exclusions: {run['no_go_exclusion_count']}",
        f"Runtime authority: {bool(run['runtime_authority'])}",
        "",
        "Counts:",
    ]
    for name, group in counts.items():
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(group.items())) or "none"
        lines.append(f"- {name}: {rendered}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Selected rows are bounded evidence/context, not truth.",
            "- No runtime activation, agent activation, model calls, vector search, network, Docker, Ollama, or tool execution.",
        ]
    )
    return "\n".join(lines)


def format_context_selection_section(payload: dict[str, Any]) -> str:
    if payload.get("status") == "no_runs":
        return "Context Selection Knowledge Packet v0\n\nNo context selection runs are recorded."
    if payload.get("section") == "summary":
        return format_context_selection_report(payload)
    lines = [
        f"Context Selection Knowledge Packet v0 - {payload['section']}",
        "",
        f"Run: `{payload.get('run_id')}`",
        f"Packet: `{payload.get('packet_id')}`",
        "",
        "Items:",
    ]
    items = payload.get("items") or []
    if not items:
        lines.append("- none")
        return "\n".join(lines)
    for item in items[:80]:
        if "evidence_key" in item:
            lines.append(
                "- "
                + item["source_path"].replace("\n", "\\n")
                + f" :: {item['evidence_label']} / {item['evidence_category']} / {item['evidence_key']}"
            )
        elif "exclusion_reason" in item:
            lines.append(
                "- "
                + item["source_path"].replace("\n", "\\n")
                + f" :: {item['exclusion_reason']} / no_go={bool(item['no_go_boundary'])}"
            )
        elif "receipt_kind" in item:
            lines.append(f"- {item['receipt_id']} :: {item['receipt_kind']}")
        else:
            lines.append("- " + item.get("source_path", "unknown").replace("\n", "\\n"))
    return "\n".join(lines)


__all__ = [
    "CONTEXT_SELECTION_VERSION",
    "ContextPacketResult",
    "build_context_selection_report",
    "compile_context_packet",
    "context_selection_table_names",
    "format_context_selection_report",
    "format_context_selection_section",
    "init_context_selection_schema",
    "query_context_selection_report_section",
    "stable_json",
]
