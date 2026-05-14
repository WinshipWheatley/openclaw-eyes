"""Bounded Evidence Kettle v0.1 seed ingestion for OpenClaw.

Evidence Kettle consumes Corpus Atlas eligibility labels and writes a small
``evidence_*`` namespace into the existing Business Ops ledger. It records
generated read-model snapshots, deterministic evidence items, and receipt
metadata summaries. It does not create truth rows, ingest arbitrary raw text,
or grant runtime authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import DEFAULT_ROOT, init_corpus_atlas_schema, stable_json


EVIDENCE_KETTLE_VERSION = "evidence_kettle_v0_1"
SAFE_SENSITIVITY_LABELS = {"public_project", "internal_project"}
GENERATED_SOURCE_ROLES = {
    "generated_read_model",
    "source_inventory",
    "artifact_registry",
    "evidence_freshness",
}
RECEIPT_SOURCE_ROLES = {"receipt", "test_result"}
CANONICAL_INGEST_SOURCE_ROLES = {"docs", "handoff", "ux_product_synthesis"}
BODY_STORED = 0
RUNTIME_AUTHORITY = 0
ACTIVATION_ALLOWED = 0


@dataclass(frozen=True)
class EvidenceIngestionResult:
    ingestion_run_id: str
    atlas_run_id: str
    db_path: str
    source_count: int
    evidence_item_count: int
    snapshot_count: int
    receipt_summary_count: int
    counts: dict[str, dict[str, int]]


@dataclass(frozen=True)
class EvidenceItemSpec:
    evidence_label: str
    evidence_category: str
    evidence_key: str
    evidence_value: Any
    summary: str
    world_id: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS evidence_ingestion_runs (
  ingestion_run_id TEXT PRIMARY KEY,
  atlas_run_id TEXT NOT NULL,
  evidence_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  evidence_item_count INTEGER NOT NULL DEFAULT 0,
  snapshot_count INTEGER NOT NULL DEFAULT 0,
  receipt_summary_count INTEGER NOT NULL DEFAULT 0,
  body_ingested INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_data_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  activation_allowed INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (atlas_run_id) REFERENCES corpus_atlas_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS evidence_sources (
  source_id TEXT PRIMARY KEY,
  ingestion_run_id TEXT NOT NULL,
  atlas_run_id TEXT NOT NULL,
  corpus_path_id TEXT,
  root_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_role TEXT NOT NULL,
  evidence_category TEXT NOT NULL,
  content_hash TEXT,
  snapshot_hash TEXT,
  hash_algorithm TEXT,
  freshness_label TEXT NOT NULL,
  canonicality TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  raw_content_eligibility TEXT NOT NULL,
  retrieval_eligibility TEXT NOT NULL,
  ingestion_eligibility TEXT NOT NULL,
  world_binding TEXT NOT NULL,
  size_bytes INTEGER,
  observed_at TEXT,
  created_at TEXT NOT NULL,
  body_ingested INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_data_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  source_pointer_json TEXT NOT NULL,
  FOREIGN KEY (ingestion_run_id) REFERENCES evidence_ingestion_runs(ingestion_run_id),
  FOREIGN KEY (corpus_path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(ingestion_run_id, corpus_path_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS evidence_items (
  evidence_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  corpus_path_id TEXT,
  root_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_type TEXT NOT NULL,
  content_hash TEXT,
  snapshot_hash TEXT,
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
  observed_at TEXT,
  created_at TEXT NOT NULL,
  ingestion_run_id TEXT NOT NULL,
  source_pointer_json TEXT NOT NULL,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (source_id) REFERENCES evidence_sources(source_id),
  FOREIGN KEY (corpus_path_id) REFERENCES corpus_paths(path_id),
  FOREIGN KEY (ingestion_run_id) REFERENCES evidence_ingestion_runs(ingestion_run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS evidence_item_labels (
  label_id TEXT PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  label_name TEXT NOT NULL,
  label_value TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (evidence_id) REFERENCES evidence_items(evidence_id),
  UNIQUE(evidence_id, label_name, label_value, label_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS evidence_world_bindings (
  binding_id TEXT PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  world_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  binding_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (evidence_id) REFERENCES evidence_items(evidence_id),
  UNIQUE(evidence_id, world_id, binding_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS evidence_source_links (
  link_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  linked_table TEXT NOT NULL,
  linked_id TEXT NOT NULL,
  link_role TEXT NOT NULL,
  link_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES evidence_sources(source_id),
  UNIQUE(source_id, linked_table, linked_id, link_role)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS read_model_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  ingestion_run_id TEXT NOT NULL,
  atlas_run_id TEXT NOT NULL,
  corpus_path_id TEXT,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_format TEXT NOT NULL,
  read_model_name TEXT NOT NULL,
  read_model_version TEXT,
  content_hash TEXT,
  snapshot_hash TEXT NOT NULL,
  hash_algorithm TEXT NOT NULL,
  snapshot_timestamp TEXT,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  body_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (source_id) REFERENCES evidence_sources(source_id),
  FOREIGN KEY (ingestion_run_id) REFERENCES evidence_ingestion_runs(ingestion_run_id),
  FOREIGN KEY (corpus_path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(ingestion_run_id, source_id, relative_path)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_evidence_sources_run ON evidence_sources(ingestion_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_sources_corpus_path ON evidence_sources(corpus_path_id)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_items_run ON evidence_items(ingestion_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_items_label ON evidence_items(ingestion_run_id, evidence_label)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_items_category ON evidence_items(ingestion_run_id, evidence_category)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_world_bindings_world ON evidence_world_bindings(world_id)",
        "CREATE INDEX IF NOT EXISTS idx_read_model_snapshots_run ON read_model_snapshots(ingestion_run_id)",
    )


def init_evidence_kettle_schema(db_path: str | Path | None = None) -> str:
    path = init_corpus_atlas_schema(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def evidence_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_evidence_kettle_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND (name LIKE 'evidence_%' OR name = 'read_model_snapshots')
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_atlas_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM corpus_atlas_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _latest_ingestion_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT ingestion_run_id
FROM evidence_ingestion_runs
ORDER BY completed_at DESC, started_at DESC, ingestion_run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _safe_source_where() -> str:
    safe = ",".join(f"'{label}'" for label in sorted(SAFE_SENSITIVITY_LABELS))
    generated_roles = ",".join(f"'{role}'" for role in sorted(GENERATED_SOURCE_ROLES))
    receipt_roles = ",".join(f"'{role}'" for role in sorted(RECEIPT_SOURCE_ROLES))
    canonical_roles = ",".join(f"'{role}'" for role in sorted(CANONICAL_INGEST_SOURCE_ROLES))
    return f"""
(
  ingestion_eligibility = 'generated_snapshot_only'
  AND retrieval_eligibility = 'generated_read_model_only'
  AND raw_content_eligibility = 'eligible'
  AND sensitivity_label IN ({safe})
  AND source_role IN ({generated_roles})
)
OR
(
  ingestion_eligibility = 'receipt_summary_only'
  AND retrieval_eligibility = 'receipt_metadata_only'
  AND sensitivity_label IN ({safe})
  AND raw_content_eligibility IN ('metadata_only','unknown','eligible')
  AND source_role IN ({receipt_roles})
)
OR
(
  ingestion_eligibility = 'ingest_allowed'
  AND retrieval_eligibility = 'retrievable'
  AND raw_content_eligibility = 'eligible'
  AND sensitivity_label IN ({safe})
  AND source_role IN ({canonical_roles})
)
""".strip()


def _source_rows(conn: sqlite3.Connection, atlas_run_id: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
SELECT
  path_id, run_id AS atlas_run_id, root_id, absolute_path, relative_path, path_name,
  path_type, tracked_status, git_head, size_bytes, mtime, ctime, content_hash,
  hash_algorithm, source_role, freshness_label, sensitivity_label,
  raw_content_eligibility, retrieval_eligibility, ingestion_eligibility,
  canonicality, world_binding, evidence_category, metadata_basis
FROM corpus_paths
WHERE run_id = ? AND ({_safe_source_where()})
ORDER BY
  CASE ingestion_eligibility
    WHEN 'generated_snapshot_only' THEN 0
    WHEN 'receipt_summary_only' THEN 1
    WHEN 'ingest_allowed' THEN 2
    ELSE 3
  END,
  relative_path
""".strip(),
        (atlas_run_id,),
    ).fetchall()
    return rows


def plan_evidence_ingestion(
    db_path: str | Path | None = None,
    *,
    atlas_run_id: str | None = None,
) -> dict[str, Any]:
    path = init_evidence_kettle_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_atlas_run_id = atlas_run_id or _latest_atlas_run_id(conn)
        if not resolved_atlas_run_id:
            return {"status": "no_atlas_runs", "source_count": 0, "counts": {}}
        rows = _source_rows(conn, resolved_atlas_run_id)
        included = Counter(row["ingestion_eligibility"] for row in rows)
        source_roles = Counter(row["source_role"] for row in rows)
        excluded_rows = conn.execute(
            """
SELECT ingestion_eligibility, COUNT(*) AS count
FROM corpus_paths
WHERE run_id = ?
  AND path_id NOT IN (
    SELECT path_id
    FROM corpus_paths
    WHERE run_id = ? AND (
""".strip()
            + _safe_source_where()
            + """
    )
  )
GROUP BY ingestion_eligibility
ORDER BY ingestion_eligibility
""",
            (resolved_atlas_run_id, resolved_atlas_run_id),
        ).fetchall()
        return {
            "status": "planned",
            "atlas_run_id": resolved_atlas_run_id,
            "source_count": len(rows),
            "counts": {
                "included_ingestion_eligibility": dict(sorted(included.items())),
                "included_source_role": dict(sorted(source_roles.items())),
                "excluded_ingestion_eligibility": {
                    row["ingestion_eligibility"]: row["count"] for row in excluded_rows
                },
            },
            "sample_sources": [
                {
                    "relative_path": row["relative_path"],
                    "ingestion_eligibility": row["ingestion_eligibility"],
                    "source_role": row["source_role"],
                    "sensitivity_label": row["sensitivity_label"],
                    "raw_content_eligibility": row["raw_content_eligibility"],
                }
                for row in rows[:20]
            ],
        }
    finally:
        conn.close()


def _source_type(row: sqlite3.Row) -> str:
    if row["ingestion_eligibility"] == "generated_snapshot_only":
        return "generated_read_model_snapshot"
    if row["ingestion_eligibility"] == "receipt_summary_only":
        return "verification_evidence_summary" if row["source_role"] == "test_result" else "receipt_summary"
    return "ingest_allowed_source"


def _resolve_source_path(root: Path, relative_path: str) -> Path:
    root_resolved = root.resolve()
    source = (root_resolved / relative_path).resolve()
    try:
        source.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"source path escapes atlas root: {relative_path}") from exc
    return source


def _read_model_name(relative_path: str) -> str:
    name = Path(relative_path).name
    for suffix in (".operator.txt", ".json", ".md", ".txt"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(relative_path).stem


def _file_format(relative_path: str) -> str:
    if relative_path.endswith(".json"):
        return "json"
    if relative_path.endswith(".md"):
        return "markdown"
    if relative_path.endswith(".txt"):
        return "operator_text"
    return "unknown"


def _json_value(value: Any) -> str:
    return stable_json(value)


def _item(
    label: str,
    category: str,
    key: str,
    value: Any,
    summary: str,
    *,
    world_id: str | None = None,
) -> EvidenceItemSpec:
    return EvidenceItemSpec(
        evidence_label=label,
        evidence_category=category,
        evidence_key=key,
        evidence_value=value,
        summary=summary,
        world_id=world_id,
    )


def _flag_item(key: str, value: Any, *, category: str = "runtime_gate") -> EvidenceItemSpec:
    return _item(
        "generated_read_model_fact",
        category,
        key,
        value,
        f"{key}={json.dumps(value, sort_keys=True)} from generated read-model.",
    )


def _unsupported_item(key: str, value: Any) -> EvidenceItemSpec:
    return _item(
        "unsupported_claim",
        "unsupported_capability",
        key,
        value,
        f"{key} is not supported by the generated read-model.",
    )


def _future_gate_item(key: str, value: Any) -> EvidenceItemSpec:
    return _item(
        "future_gated_capability",
        "runtime_gate",
        key,
        value,
        f"{value} is a missing prerequisite before future activation.",
    )


def _extract_json_items(relative_path: str, data: dict[str, Any]) -> list[EvidenceItemSpec]:
    name = Path(relative_path).name
    items: list[EvidenceItemSpec] = []

    if name == "helm_state.json":
        helm = data.get("helm_state") or {}
        if helm.get("state") is not None:
            items.append(
                _item(
                    "generated_read_model_fact",
                    "helm_state",
                    "helm_state",
                    helm.get("state"),
                    f"Helm state is {helm.get('state')}.",
                )
            )
        for key in ("runtime_authority", "activation_allowed", "backend_execution"):
            if key in data:
                items.append(_flag_item(key, data[key]))
        strategic_gravity = data.get("strategic_gravity") or {}
        if strategic_gravity.get("supported") is False:
            items.append(_unsupported_item("strategic_gravity_supported", False))
        agent_presence = data.get("agent_presence_model") or {}
        if agent_presence.get("supported") is False:
            items.append(_unsupported_item("agent_presence_supported", False))
        if agent_presence.get("live_agents_claimed") is not None:
            items.append(_flag_item("live_agents_claimed", agent_presence["live_agents_claimed"]))
        activation_gate = data.get("activation_gate") or {}
        if activation_gate.get("gate_state"):
            items.append(_flag_item("activation_gate_state", activation_gate["gate_state"]))
        for prerequisite in activation_gate.get("missing_prerequisites") or []:
            items.append(_future_gate_item(f"missing_prerequisite:{prerequisite}", prerequisite))
        if data.get("next_safe_move"):
            items.append(
                _item(
                    "generated_read_model_fact",
                    "operator_status",
                    "next_safe_move",
                    data["next_safe_move"],
                    "Generated helm state names the next safe move.",
                )
            )

    elif name == "runtime_activation_gate.json":
        if data.get("gate_state"):
            items.append(_flag_item("gate_state", data["gate_state"]))
        for key in ("runtime_authority", "activation_allowed", "module_activation_authority"):
            if key in data:
                items.append(_flag_item(key, data[key]))
        if "backend_execution" in data:
            items.append(_flag_item("backend_execution", data["backend_execution"]))
        for prerequisite in data.get("missing_prerequisites") or []:
            items.append(_future_gate_item(f"missing_prerequisite:{prerequisite}", prerequisite))
        if data.get("next_safe_move"):
            items.append(
                _item(
                    "generated_read_model_fact",
                    "operator_status",
                    "next_safe_move",
                    data["next_safe_move"],
                    "Runtime gate names the next safe move.",
                )
            )

    elif name == "world_domain_registry.json":
        if "world_count" in data:
            items.append(
                _item(
                    "generated_read_model_fact",
                    "world_registry",
                    "world_count",
                    data["world_count"],
                    f"World registry contains {data['world_count']} worlds.",
                )
            )
        for world in data.get("worlds") or []:
            world_id = world.get("world_id")
            if not world_id:
                continue
            items.append(
                _item(
                    "generated_read_model_fact",
                    "world_registry",
                    f"world_id:{world_id}",
                    world_id,
                    f"Registered world id {world_id}.",
                    world_id=world_id,
                )
            )
        for key in (
            "dynamic_world_state",
            "strategic_gravity_supported",
            "agent_presence_supported",
        ):
            if data.get(key) is False:
                items.append(_unsupported_item(key, False))
        for key in ("runtime_authority", "activation_allowed", "backend_execution"):
            if key in data:
                items.append(_flag_item(key, data[key]))

    elif name == "world_status.json":
        if "world_count" in data:
            items.append(
                _item(
                    "generated_read_model_fact",
                    "world_status",
                    "world_count",
                    data["world_count"],
                    f"World status contains {data['world_count']} worlds.",
                )
            )
        for world in data.get("worlds") or []:
            world_id = world.get("world_id")
            if not world_id:
                continue
            status = world.get("status") or world.get("state") or "registry_only"
            items.append(
                _item(
                    "generated_read_model_fact",
                    "world_status",
                    f"world_status:{world_id}",
                    status,
                    f"World {world_id} has generated status {status}.",
                    world_id=world_id,
                )
            )
        for key in (
            "dynamic_world_state",
            "strategic_gravity_supported",
            "agent_presence_supported",
        ):
            if data.get(key) is False:
                items.append(_unsupported_item(key, False))
        for key in ("runtime_authority", "activation_allowed", "backend_execution"):
            if key in data:
                items.append(_flag_item(key, data[key]))

    elif name == "artifact_registry.json":
        if "artifact_count" in data:
            items.append(
                _item(
                    "generated_read_model_fact",
                    "artifact_registry",
                    "artifact_count",
                    data["artifact_count"],
                    f"Artifact registry contains {data['artifact_count']} records.",
                )
            )
        for key in (
            "runtime_authority",
            "activation_allowed",
            "backend_execution_authorized",
            "body_ingested",
            "metadata_only",
        ):
            if key in data:
                category = "runtime_gate" if key != "metadata_only" else "artifact_registry"
                items.append(_flag_item(key, data[key], category=category))

    elif name == "source_inventory.json":
        summary = data.get("summary") or {}
        for key in (
            "records_total",
            "allowlisted_records",
            "blocked_no_go_examples",
            "blocked_records",
            "body_ingested",
            "metadata_only_records",
        ):
            if key in summary:
                items.append(
                    _item(
                        "generated_read_model_fact",
                        "source_inventory",
                        f"source_inventory:{key}",
                        summary[key],
                        f"Source inventory {key}={summary[key]}.",
                    )
                )
        scope = data.get("scope") or {}
        for key in (
            "runtime_activation",
            "agent_activation",
            "broker_connection",
            "customer_deployment",
            "hard_drive_scan",
            "sqlite_touched",
            "whole_repo_scan",
        ):
            if key in scope:
                label = "generated_read_model_fact" if scope[key] is False else "source_claim"
                items.append(
                    _item(
                        label,
                        "source_inventory",
                        f"source_inventory_scope:{key}",
                        scope[key],
                        f"Source inventory scope {key}={scope[key]}.",
                    )
                )

    elif name == "evidence_freshness.json":
        if "artifact_count" in data:
            items.append(
                _item(
                    "generated_read_model_fact",
                    "evidence_freshness",
                    "artifact_count",
                    data["artifact_count"],
                    f"Evidence freshness tracks {data['artifact_count']} artifacts.",
                )
            )
        freshness_counts = data.get("freshness_counts") or {}
        for key in ("current", "stale", "missing", "unknown"):
            if key in freshness_counts:
                items.append(
                    _item(
                        "generated_read_model_fact",
                        "evidence_freshness",
                        f"freshness_count:{key}",
                        freshness_counts[key],
                        f"Evidence freshness count {key}={freshness_counts[key]}.",
                    )
                )
        for key in (
            "generated_status_current",
            "read_model_exports_current",
            "runtime_authority",
            "activation_allowed",
            "backend_execution_authorized",
            "body_ingested",
        ):
            if key in data:
                category = "runtime_gate" if key in {"runtime_authority", "activation_allowed", "backend_execution_authorized"} else "evidence_freshness"
                items.append(_flag_item(key, data[key], category=category))

    return items


def _insert_source_link(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    linked_table: str,
    linked_id: str,
    link_role: str,
    link_basis: str,
    created_at: str,
) -> None:
    conn.execute(
        """
INSERT INTO evidence_source_links (
  link_id, source_id, linked_table, linked_id, link_role, link_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(source_id, linked_table, linked_id, link_role) DO UPDATE SET
  link_basis = excluded.link_basis
""".strip(),
        (
            _row_id("eslink", source_id, linked_table, linked_id, link_role),
            source_id,
            linked_table,
            linked_id,
            link_role,
            link_basis,
            created_at,
        ),
    )


def _insert_world_binding(
    conn: sqlite3.Connection,
    *,
    evidence_id: str,
    world_id: str,
    confidence: float,
    basis: str,
    created_at: str,
) -> None:
    conn.execute(
        """
INSERT INTO evidence_world_bindings (
  binding_id, evidence_id, world_id, confidence, binding_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(evidence_id, world_id, binding_basis) DO UPDATE SET
  confidence = excluded.confidence
""".strip(),
        (
            _row_id("eworld", evidence_id, world_id, basis),
            evidence_id,
            world_id,
            confidence,
            basis,
            created_at,
        ),
    )


def _insert_item_labels(
    conn: sqlite3.Connection,
    *,
    evidence_id: str,
    row: sqlite3.Row,
    item: EvidenceItemSpec,
    created_at: str,
) -> None:
    labels = {
        "evidence_label": item.evidence_label,
        "evidence_category": item.evidence_category,
        "freshness_label": row["freshness_label"],
        "canonicality": row["canonicality"],
        "sensitivity_label": row["sensitivity_label"],
        "retrieval_eligibility": row["retrieval_eligibility"],
        "ingestion_eligibility": row["ingestion_eligibility"],
    }
    for name, value in labels.items():
        conn.execute(
            """
INSERT INTO evidence_item_labels (
  label_id, evidence_id, label_name, label_value, label_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(evidence_id, label_name, label_value, label_basis) DO NOTHING
""".strip(),
            (
                _row_id("elabel", evidence_id, name, value, "evidence_kettle_v0_1"),
                evidence_id,
                name,
                value,
                "evidence_kettle_v0_1",
                created_at,
            ),
        )


def _insert_evidence_item(
    conn: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    source_id: str,
    source_type: str,
    snapshot_hash: str | None,
    item: EvidenceItemSpec,
    ingestion_run_id: str,
    created_at: str,
) -> str:
    value_json = _json_value(item.evidence_value)
    evidence_id = _row_id(
        "eitem",
        ingestion_run_id,
        source_id,
        item.evidence_label,
        item.evidence_category,
        item.evidence_key,
        value_json,
    )
    source_pointer = {
        "corpus_path_id": row["path_id"],
        "atlas_run_id": row["atlas_run_id"],
        "source_path": row["relative_path"],
        "body_stored": False,
        "truth_claimed": False,
    }
    conn.execute(
        """
INSERT INTO evidence_items (
  evidence_id, source_id, corpus_path_id, root_id, source_path, source_type,
  content_hash, snapshot_hash, evidence_label, evidence_category, evidence_key,
  evidence_value_json, summary, freshness_label, canonicality, sensitivity_label,
  retrieval_eligibility, ingestion_eligibility, world_binding, observed_at,
  created_at, ingestion_run_id, source_pointer_json, truth_claimed,
  runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
ON CONFLICT(evidence_id) DO UPDATE SET
  summary = excluded.summary,
  evidence_value_json = excluded.evidence_value_json,
  snapshot_hash = excluded.snapshot_hash
""".strip(),
        (
            evidence_id,
            source_id,
            row["path_id"],
            row["root_id"],
            row["relative_path"],
            source_type,
            row["content_hash"],
            snapshot_hash,
            item.evidence_label,
            item.evidence_category,
            item.evidence_key,
            value_json,
            item.summary,
            row["freshness_label"],
            row["canonicality"],
            row["sensitivity_label"],
            row["retrieval_eligibility"],
            row["ingestion_eligibility"],
            row["world_binding"],
            row["mtime"],
            created_at,
            ingestion_run_id,
            stable_json(source_pointer),
        ),
    )
    _insert_item_labels(conn, evidence_id=evidence_id, row=row, item=item, created_at=created_at)
    world_id = item.world_id or row["world_binding"]
    if world_id and world_id not in {"unknown", "no_world"}:
        _insert_world_binding(
            conn,
            evidence_id=evidence_id,
            world_id=world_id,
            confidence=0.95 if item.world_id else 0.75,
            basis="evidence_item_world_binding" if item.world_id else "corpus_path_world_binding",
            created_at=created_at,
        )
    return evidence_id


def _read_generated_snapshot(
    *,
    root: Path,
    row: sqlite3.Row,
    file_reader: Callable[[Path], bytes],
) -> tuple[bytes, str]:
    relative_path = row["relative_path"]
    if not (
        relative_path.startswith("generated/read_models/")
        or relative_path.startswith("Operator/GENERATED_")
    ):
        raise ValueError(f"generated snapshot path is not allowlisted: {relative_path}")
    source_path = _resolve_source_path(root, relative_path)
    data = file_reader(source_path)
    return data, _sha256_bytes(data)


def _insert_snapshot(
    conn: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    source_id: str,
    ingestion_run_id: str,
    snapshot_hash: str,
    read_model_version: str | None,
    metadata: dict[str, Any],
    created_at: str,
) -> str:
    relative_path = row["relative_path"]
    snapshot_id = _row_id("rmsnap", ingestion_run_id, source_id, relative_path)
    conn.execute(
        """
INSERT INTO read_model_snapshots (
  snapshot_id, source_id, ingestion_run_id, atlas_run_id, corpus_path_id, root_id,
  relative_path, file_name, file_format, read_model_name, read_model_version,
  content_hash, snapshot_hash, hash_algorithm, snapshot_timestamp, created_at,
  metadata_json, body_stored, runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
ON CONFLICT(ingestion_run_id, source_id, relative_path) DO UPDATE SET
  read_model_version = excluded.read_model_version,
  content_hash = excluded.content_hash,
  snapshot_hash = excluded.snapshot_hash,
  snapshot_timestamp = excluded.snapshot_timestamp,
  metadata_json = excluded.metadata_json
""".strip(),
        (
            snapshot_id,
            source_id,
            ingestion_run_id,
            row["atlas_run_id"],
            row["path_id"],
            row["root_id"],
            relative_path,
            Path(relative_path).name,
            _file_format(relative_path),
            _read_model_name(relative_path),
            read_model_version,
            row["content_hash"],
            snapshot_hash,
            "sha256",
            row["mtime"],
            created_at,
            stable_json(metadata),
        ),
    )
    _insert_source_link(
        conn,
        source_id=source_id,
        linked_table="read_model_snapshots",
        linked_id=snapshot_id,
        link_role="snapshot_record",
        link_basis="evidence_kettle_generated_snapshot",
        created_at=created_at,
    )
    return snapshot_id


def _generated_snapshot_items(
    *,
    root: Path,
    row: sqlite3.Row,
    file_reader: Callable[[Path], bytes],
) -> tuple[str, str | None, dict[str, Any], list[EvidenceItemSpec]]:
    data, snapshot_hash = _read_generated_snapshot(root=root, row=row, file_reader=file_reader)
    relative_path = row["relative_path"]
    metadata: dict[str, Any] = {
        "relative_path": relative_path,
        "file_format": _file_format(relative_path),
        "byte_count": len(data),
        "body_stored": False,
        "deterministic_extraction_only": True,
    }
    read_model_version: str | None = None
    items = [
        _item(
            "generated_read_model_fact",
            row["evidence_category"] if row["evidence_category"] != "unknown" else "operator_status",
            "snapshot_recorded",
            {
                "relative_path": relative_path,
                "snapshot_hash": snapshot_hash,
                "body_stored": False,
            },
            f"Generated snapshot recorded for {relative_path}; body not stored.",
        )
    ]

    if relative_path.endswith(".json"):
        parsed = json.loads(data.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError(f"read-model JSON root must be an object: {relative_path}")
        read_model_version = (
            parsed.get("read_model_version")
            or parsed.get("artifact_version")
            or parsed.get("inventory_version")
        )
        metadata.update(
            {
                "top_level_keys": sorted(parsed.keys()),
                "read_model_version": read_model_version,
            }
        )
        items.extend(_extract_json_items(relative_path, parsed))
    return snapshot_hash, read_model_version, metadata, items


def _receipt_summary_items(row: sqlite3.Row) -> list[EvidenceItemSpec]:
    label = "verification_evidence" if row["source_role"] == "test_result" else "receipt_summary"
    category = "test_result" if row["source_role"] == "test_result" else "receipt"
    value = {
        "relative_path": row["relative_path"],
        "source_role": row["source_role"],
        "size_bytes": row["size_bytes"],
        "mtime": row["mtime"],
        "content_hash": row["content_hash"],
        "body_ingested": False,
        "summary_only": True,
    }
    return [
        _item(
            label,
            category,
            "receipt_metadata_summary",
            value,
            f"Receipt metadata summary recorded for {row['relative_path']}; body not ingested.",
        )
    ]


def _canonical_source_items(row: sqlite3.Row) -> list[EvidenceItemSpec]:
    value = {
        "relative_path": row["relative_path"],
        "content_hash": row["content_hash"],
        "freshness_label": row["freshness_label"],
        "canonicality": row["canonicality"],
        "body_stored": False,
        "truth_promoted": False,
    }
    return [
        _item(
            "source_claim",
            "operator_status",
            "ingest_allowed_source_registered",
            value,
            f"Ingest-allowed canonical source registered for {row['relative_path']}; body not stored as truth.",
        )
    ]


def _insert_evidence_source(
    conn: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    source_id: str,
    source_type: str,
    snapshot_hash: str | None,
    ingestion_run_id: str,
    created_at: str,
) -> None:
    pointer = {
        "corpus_path_id": row["path_id"],
        "atlas_run_id": row["atlas_run_id"],
        "relative_path": row["relative_path"],
        "metadata_basis": row["metadata_basis"],
    }
    conn.execute(
        """
INSERT INTO evidence_sources (
  source_id, ingestion_run_id, atlas_run_id, corpus_path_id, root_id, source_path,
  absolute_path, source_type, source_role, evidence_category, content_hash,
  snapshot_hash, hash_algorithm, freshness_label, canonicality, sensitivity_label,
  raw_content_eligibility, retrieval_eligibility, ingestion_eligibility,
  world_binding, size_bytes, observed_at, created_at, body_ingested,
  raw_sensitive_data_stored, runtime_authority, source_pointer_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
ON CONFLICT(ingestion_run_id, corpus_path_id) DO UPDATE SET
  snapshot_hash = excluded.snapshot_hash,
  content_hash = excluded.content_hash,
  source_pointer_json = excluded.source_pointer_json
""".strip(),
        (
            source_id,
            ingestion_run_id,
            row["atlas_run_id"],
            row["path_id"],
            row["root_id"],
            row["relative_path"],
            row["absolute_path"],
            source_type,
            row["source_role"],
            row["evidence_category"],
            row["content_hash"],
            snapshot_hash,
            row["hash_algorithm"] or ("sha256" if row["content_hash"] or snapshot_hash else None),
            row["freshness_label"],
            row["canonicality"],
            row["sensitivity_label"],
            row["raw_content_eligibility"],
            row["retrieval_eligibility"],
            row["ingestion_eligibility"],
            row["world_binding"],
            row["size_bytes"],
            row["mtime"],
            created_at,
            stable_json(pointer),
        ),
    )
    _insert_source_link(
        conn,
        source_id=source_id,
        linked_table="corpus_paths",
        linked_id=row["path_id"],
        link_role="source_classification",
        link_basis="corpus_atlas_v0_6",
        created_at=created_at,
    )


def run_evidence_kettle(
    db_path: str | Path | None = None,
    *,
    root: str | Path = DEFAULT_ROOT,
    atlas_run_id: str | None = None,
    ingestion_run_id: str | None = None,
    file_reader: Callable[[Path], bytes] | None = None,
) -> EvidenceIngestionResult:
    path = init_evidence_kettle_schema(db_path)
    root_path = Path(root)
    reader = file_reader or (lambda source_path: source_path.read_bytes())
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        resolved_atlas_run_id = atlas_run_id or _latest_atlas_run_id(conn)
        if not resolved_atlas_run_id:
            raise RuntimeError("Corpus Atlas must run before Evidence Kettle ingestion")
        rows = _source_rows(conn, resolved_atlas_run_id)
        created_at = utc_now()
        run_id = ingestion_run_id or _row_id(
            "ekrun",
            EVIDENCE_KETTLE_VERSION,
            resolved_atlas_run_id,
            created_at,
        )
        source_basis = {
            "version": EVIDENCE_KETTLE_VERSION,
            "atlas_run_id": resolved_atlas_run_id,
            "included_ingestion_eligibility": [
                "generated_snapshot_only",
                "receipt_summary_only",
                "ingest_allowed",
            ],
            "excluded_ingestion_eligibility": [
                "needs_review",
                "no_go",
                "metadata_only",
                "not_for_ingestion",
            ],
            "body_ingested": False,
            "raw_sensitive_data_stored": False,
            "runtime_authority": False,
        }
        conn.execute(
            """
INSERT INTO evidence_ingestion_runs (
  ingestion_run_id, atlas_run_id, evidence_version, started_at, completed_at,
  source_count, evidence_item_count, snapshot_count, receipt_summary_count,
  body_ingested, raw_sensitive_data_stored, runtime_authority,
  activation_allowed, source_basis_json, notes
) VALUES (?, ?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?)
ON CONFLICT(ingestion_run_id) DO UPDATE SET
  atlas_run_id = excluded.atlas_run_id,
  evidence_version = excluded.evidence_version,
  started_at = excluded.started_at,
  source_basis_json = excluded.source_basis_json
""".strip(),
            (
                run_id,
                resolved_atlas_run_id,
                EVIDENCE_KETTLE_VERSION,
                created_at,
                stable_json(source_basis),
                "Generated read-model snapshots, receipt summaries, and explicitly ingest-allowed source metadata only.",
            ),
        )

        snapshot_count = 0
        receipt_summary_count = 0
        for row in rows:
            source_type = _source_type(row)
            source_id = _row_id("esrc", run_id, row["path_id"], source_type)
            snapshot_hash: str | None = None
            read_model_version: str | None = None
            metadata: dict[str, Any] | None = None
            if row["ingestion_eligibility"] == "generated_snapshot_only":
                snapshot_hash, read_model_version, metadata, items = _generated_snapshot_items(
                    root=root_path,
                    row=row,
                    file_reader=reader,
                )
            elif row["ingestion_eligibility"] == "receipt_summary_only":
                items = _receipt_summary_items(row)
                receipt_summary_count += 1
            else:
                items = _canonical_source_items(row)

            _insert_evidence_source(
                conn,
                row=row,
                source_id=source_id,
                source_type=source_type,
                snapshot_hash=snapshot_hash,
                ingestion_run_id=run_id,
                created_at=created_at,
            )
            if row["ingestion_eligibility"] == "generated_snapshot_only":
                assert snapshot_hash is not None
                assert metadata is not None
                snapshot_id = _insert_snapshot(
                    conn,
                    row=row,
                    source_id=source_id,
                    ingestion_run_id=run_id,
                    snapshot_hash=snapshot_hash,
                    read_model_version=read_model_version,
                    metadata=metadata,
                    created_at=created_at,
                )
                snapshot_count += 1
                _insert_source_link(
                    conn,
                    source_id=source_id,
                    linked_table="read_model_snapshots",
                    linked_id=snapshot_id,
                    link_role="generated_snapshot",
                    link_basis="generated_snapshot_only_ingestion",
                    created_at=created_at,
                )

            for item in items:
                _insert_evidence_item(
                    conn,
                    row=row,
                    source_id=source_id,
                    source_type=source_type,
                    snapshot_hash=snapshot_hash,
                    item=item,
                    ingestion_run_id=run_id,
                    created_at=created_at,
                )

        item_count = conn.execute(
            "SELECT COUNT(*) FROM evidence_items WHERE ingestion_run_id = ?",
            (run_id,),
        ).fetchone()[0]
        source_count = conn.execute(
            "SELECT COUNT(*) FROM evidence_sources WHERE ingestion_run_id = ?",
            (run_id,),
        ).fetchone()[0]
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM read_model_snapshots WHERE ingestion_run_id = ?",
            (run_id,),
        ).fetchone()[0]
        receipt_summary_count = conn.execute(
            """
SELECT COUNT(*)
FROM evidence_sources
WHERE ingestion_run_id = ?
  AND source_type IN ('receipt_summary','verification_evidence_summary')
""".strip(),
            (run_id,),
        ).fetchone()[0]
        completed_at = utc_now()
        conn.execute(
            """
UPDATE evidence_ingestion_runs
SET completed_at = ?,
    source_count = ?,
    evidence_item_count = ?,
    snapshot_count = ?,
    receipt_summary_count = ?,
    body_ingested = 0,
    raw_sensitive_data_stored = 0,
    runtime_authority = 0,
    activation_allowed = 0
WHERE ingestion_run_id = ?
""".strip(),
            (
                completed_at,
                source_count,
                item_count,
                snapshot_count,
                receipt_summary_count,
                run_id,
            ),
        )
        conn.commit()
        counts = _run_counts(conn, run_id)
        return EvidenceIngestionResult(
            ingestion_run_id=run_id,
            atlas_run_id=resolved_atlas_run_id,
            db_path=path,
            source_count=source_count,
            evidence_item_count=item_count,
            snapshot_count=snapshot_count,
            receipt_summary_count=receipt_summary_count,
            counts=counts,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _group_counts(
    conn: sqlite3.Connection,
    table_name: str,
    run_column: str,
    run_id: str,
    group_column: str,
) -> dict[str, int]:
    rows = conn.execute(
        f"""
SELECT {group_column} AS label, COUNT(*) AS count
FROM {table_name}
WHERE {run_column} = ?
GROUP BY {group_column}
ORDER BY count DESC, label
""".strip(),
        (run_id,),
    ).fetchall()
    return {row["label"]: row["count"] for row in rows}


def _run_counts(conn: sqlite3.Connection, ingestion_run_id: str) -> dict[str, dict[str, int]]:
    conn.row_factory = sqlite3.Row
    return {
        "source_type": _group_counts(
            conn,
            "evidence_sources",
            "ingestion_run_id",
            ingestion_run_id,
            "source_type",
        ),
        "source_ingestion_eligibility": _group_counts(
            conn,
            "evidence_sources",
            "ingestion_run_id",
            ingestion_run_id,
            "ingestion_eligibility",
        ),
        "evidence_label": _group_counts(
            conn,
            "evidence_items",
            "ingestion_run_id",
            ingestion_run_id,
            "evidence_label",
        ),
        "evidence_category": _group_counts(
            conn,
            "evidence_items",
            "ingestion_run_id",
            ingestion_run_id,
            "evidence_category",
        ),
        "world_binding": _group_counts(
            conn,
            "evidence_items",
            "ingestion_run_id",
            ingestion_run_id,
            "world_binding",
        ),
    }


def _sample_items(
    conn: sqlite3.Connection,
    ingestion_run_id: str,
    where_sql: str,
    params: Iterable[Any] = (),
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT
  evidence_id, source_path, source_type, evidence_label, evidence_category,
  evidence_key, evidence_value_json, summary, world_binding, freshness_label,
  canonicality, ingestion_eligibility
FROM evidence_items
WHERE ingestion_run_id = ? AND ({where_sql})
ORDER BY source_path, evidence_category, evidence_key
LIMIT ?
""".strip(),
        (ingestion_run_id, *tuple(params), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _snapshot_rows(conn: sqlite3.Connection, ingestion_run_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT
  snapshot_id, relative_path, file_format, read_model_name, read_model_version,
  content_hash, snapshot_hash, snapshot_timestamp, body_stored, runtime_authority
FROM read_model_snapshots
WHERE ingestion_run_id = ?
ORDER BY relative_path
LIMIT ?
""".strip(),
        (ingestion_run_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _source_rows_for_report(
    conn: sqlite3.Connection,
    ingestion_run_id: str,
    where_sql: str,
    params: Iterable[Any] = (),
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT
  source_id, source_path, source_type, source_role, evidence_category,
  freshness_label, canonicality, sensitivity_label, retrieval_eligibility,
  ingestion_eligibility, world_binding, content_hash, snapshot_hash
FROM evidence_sources
WHERE ingestion_run_id = ? AND ({where_sql})
ORDER BY source_path
LIMIT ?
""".strip(),
        (ingestion_run_id, *tuple(params), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def build_evidence_report(
    db_path: str | Path | None = None,
    *,
    ingestion_run_id: str | None = None,
) -> dict[str, Any]:
    path = init_evidence_kettle_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = ingestion_run_id or _latest_ingestion_run_id(conn)
        if not run_id:
            return {"status": "no_runs", "evidence_version": EVIDENCE_KETTLE_VERSION}
        run = dict(
            conn.execute(
                "SELECT * FROM evidence_ingestion_runs WHERE ingestion_run_id = ?",
                (run_id,),
            ).fetchone()
        )
        counts = _run_counts(conn, run_id)
        world_rows = conn.execute(
            """
SELECT world_id, COUNT(*) AS count
FROM evidence_world_bindings wb
JOIN evidence_items ei ON ei.evidence_id = wb.evidence_id
WHERE ei.ingestion_run_id = ?
GROUP BY world_id
ORDER BY count DESC, world_id
""".strip(),
            (run_id,),
        ).fetchall()
        counts["world_id"] = {row["world_id"]: row["count"] for row in world_rows}
        return {
            "status": "ok",
            "evidence_version": EVIDENCE_KETTLE_VERSION,
            "run": run,
            "counts": counts,
            "read_model_snapshots": _snapshot_rows(conn, run_id),
            "future_gated_capabilities": _sample_items(
                conn,
                run_id,
                "evidence_label = 'future_gated_capability'",
            ),
            "unsupported_capabilities": _sample_items(
                conn,
                run_id,
                "evidence_label = 'unsupported_claim'",
            ),
            "runtime_gate_evidence": _sample_items(
                conn,
                run_id,
                "evidence_category = 'runtime_gate'",
            ),
            "next_safe_move_evidence": _sample_items(
                conn,
                run_id,
                "evidence_key = 'next_safe_move'",
            ),
            "receipt_summary_evidence": _sample_items(
                conn,
                run_id,
                "evidence_label IN ('receipt_summary','verification_evidence')",
            ),
        }
    finally:
        conn.close()


def _count_line(label: str, counts: dict[str, int]) -> str:
    if not counts:
        return f"{label}: none"
    rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return f"{label}: {rendered}"


def _sample_lines(items: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    if not items:
        return ["- none"]
    lines = []
    for item in items[:limit]:
        lines.append(
            "- "
            + item["source_path"].replace("\n", "\\n")
            + f" :: {item['evidence_label']} / {item['evidence_category']} / {item['evidence_key']}"
        )
    return lines


def format_evidence_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Evidence Kettle v0.1\n\nNo evidence ingestion runs are recorded."
    run = report["run"]
    counts = report["counts"]
    lines = [
        "Evidence Kettle v0.1",
        "",
        f"Run: `{run['ingestion_run_id']}`",
        f"Atlas run: `{run['atlas_run_id']}`",
        f"Sources: {run['source_count']}",
        f"Evidence items: {run['evidence_item_count']}",
        f"Read-model snapshots: {run['snapshot_count']}",
        f"Receipt summaries: {run['receipt_summary_count']}",
        f"Body ingested: {bool(run['body_ingested'])}",
        f"Runtime authority: {bool(run['runtime_authority'])}",
        "",
        _count_line("Source types", counts["source_type"]),
        _count_line("Evidence labels", counts["evidence_label"]),
        _count_line("Evidence categories", counts["evidence_category"]),
        _count_line("World bindings", counts["world_id"]),
        "",
        "Read-model snapshots:",
    ]
    if report["read_model_snapshots"]:
        for snapshot in report["read_model_snapshots"][:8]:
            lines.append(
                "- "
                + snapshot["relative_path"].replace("\n", "\\n")
                + f" ({snapshot['file_format']}, {snapshot['read_model_version']})"
            )
    else:
        lines.append("- none")
    lines.extend(["", "Runtime gate evidence:", *_sample_lines(report["runtime_gate_evidence"])])
    lines.extend(["", "Future-gated capabilities:", *_sample_lines(report["future_gated_capabilities"])])
    lines.extend(["", "Receipt summaries:", *_sample_lines(report["receipt_summary_evidence"])])
    return "\n".join(lines)


def query_evidence_report_section(
    db_path: str | Path | None = None,
    *,
    ingestion_run_id: str | None = None,
    section: str = "summary",
    world: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    path = init_evidence_kettle_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = ingestion_run_id or _latest_ingestion_run_id(conn)
        if not run_id:
            return {"status": "no_runs", "section": section}
        if section == "summary":
            return build_evidence_report(db_path=path, ingestion_run_id=run_id)
        if section == "read-models":
            items = _snapshot_rows(conn, run_id)
        elif section == "future-gated":
            items = _sample_items(conn, run_id, "evidence_label = 'future_gated_capability'", limit=100)
        elif section == "unsupported":
            items = _sample_items(conn, run_id, "evidence_label = 'unsupported_claim'", limit=100)
        elif section == "runtime-gate":
            items = _sample_items(conn, run_id, "evidence_category = 'runtime_gate'", limit=100)
        elif section == "next-safe-move":
            items = _sample_items(conn, run_id, "evidence_key = 'next_safe_move'", limit=100)
        elif section == "receipts":
            items = _sample_items(
                conn,
                run_id,
                "evidence_label IN ('receipt_summary','verification_evidence')",
                limit=100,
            )
        elif section == "world":
            if not world:
                raise ValueError("--world is required for the world report")
            rows = conn.execute(
                """
SELECT
  ei.evidence_id, ei.source_path, ei.source_type, ei.evidence_label,
  ei.evidence_category, ei.evidence_key, ei.evidence_value_json, ei.summary,
  wb.world_id, ei.freshness_label, ei.canonicality, ei.ingestion_eligibility
FROM evidence_items ei
JOIN evidence_world_bindings wb ON wb.evidence_id = ei.evidence_id
WHERE ei.ingestion_run_id = ? AND wb.world_id = ?
ORDER BY ei.source_path, ei.evidence_category, ei.evidence_key
LIMIT 100
""".strip(),
                (run_id, world),
            ).fetchall()
            items = [dict(row) for row in rows]
        elif section == "category":
            if not category:
                raise ValueError("--category is required for the category report")
            items = _sample_items(
                conn,
                run_id,
                "evidence_category = ?",
                (category,),
                limit=100,
            )
        elif section == "sources":
            items = _source_rows_for_report(conn, run_id, "1 = 1", limit=100)
        else:
            raise ValueError(f"Unknown evidence report section: {section}")

        return {
            "status": "ok",
            "section": section,
            "ingestion_run_id": run_id,
            "items": items,
        }
    finally:
        conn.close()


__all__ = [
    "EVIDENCE_KETTLE_VERSION",
    "EvidenceIngestionResult",
    "build_evidence_report",
    "evidence_table_names",
    "format_evidence_report",
    "init_evidence_kettle_schema",
    "plan_evidence_ingestion",
    "query_evidence_report_section",
    "run_evidence_kettle",
    "stable_json",
]
