"""Corpus-linked Markdown Knowledge Atlas v0 for OpenClaw.

This module adds a document-role overlay on top of existing Corpus Atlas rows.
It does not scan filesystems, read Markdown bodies, move files, activate tools,
or promote prose into truth.
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
from corpus_atlas import init_corpus_atlas_schema, stable_json


MARKDOWN_ATLAS_VERSION = "markdown_knowledge_atlas_v0"

DOCUMENT_ROLES = {
    "canonical_doctrine",
    "current_system_map",
    "active_handoff",
    "generated_status",
    "implementation_spec",
    "operation_doc",
    "test_baseline",
    "product_vision",
    "ux_taste",
    "planning_note",
    "legacy_doc",
    "unknown_review",
}

FRESHNESS_STATUS = {
    "current",
    "stale_possible",
    "superseded",
    "unknown_review",
}

REORG_STATUS = {
    "keep_current",
    "archive_candidate",
    "scratch",
    "unknown_review",
}

SENSITIVITY_STATUS = {
    "normal_internal",
    "sensitive_metadata_only",
    "no_go",
    "unknown_review",
}

RETRIEVAL_POLICY = {
    "agent_retrievable",
    "metadata_only",
    "blocked_no_go",
    "needs_operator_review",
    "generated_surface_only",
}

CLASSIFICATION_AXES = (
    "document_role",
    "freshness_status",
    "reorg_status",
    "sensitivity_status",
    "retrieval_policy",
)

CANONICAL_DOCTRINE_PATHS = {
    "AGENTS.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "OPENCLAW_RUNTIME.md",
    "USER.md",
}

KNOWN_STALE_PATHS = {
    "CURRENT_STATE.md",
    "NEXT_ACTIONS.md",
    "docs/operations/OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "truth_promotion_allowed": False,
}


@dataclass(frozen=True)
class MarkdownAtlasResult:
    run_id: str
    db_path: str
    document_count: int
    source_corpus_runs: tuple[str, ...]
    counts: dict[str, dict[str, int]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS markdown_atlas_runs (
  run_id TEXT PRIMARY KEY,
  atlas_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  source_corpus_runs_json TEXT NOT NULL,
  source_root_count INTEGER NOT NULL DEFAULT 0,
  document_count INTEGER NOT NULL DEFAULT 0,
  body_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_documents (
  markdown_document_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  corpus_path_id TEXT NOT NULL,
  corpus_run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  root_kind TEXT NOT NULL,
  host_kind TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  project_id TEXT,
  client_id TEXT,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  mirror_of_root_id TEXT,
  lineage_source TEXT,
  relative_path TEXT NOT NULL,
  filename TEXT NOT NULL,
  document_role TEXT NOT NULL,
  freshness_status TEXT NOT NULL,
  reorg_status TEXT NOT NULL,
  sensitivity_status TEXT NOT NULL,
  retrieval_policy TEXT NOT NULL,
  world_binding TEXT NOT NULL,
  module_topic TEXT NOT NULL,
  source_basis TEXT NOT NULL,
  classification_rule TEXT NOT NULL,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  observed_at TEXT,
  body_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES markdown_atlas_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (corpus_path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(run_id, corpus_path_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_document_classifications (
  classification_id TEXT PRIMARY KEY,
  markdown_document_id TEXT NOT NULL,
  axis TEXT NOT NULL,
  value TEXT NOT NULL,
  confidence REAL NOT NULL,
  basis TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (markdown_document_id) REFERENCES markdown_documents(markdown_document_id) ON DELETE CASCADE,
  UNIQUE(markdown_document_id, axis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_document_links (
  link_id TEXT PRIMARY KEY,
  markdown_document_id TEXT NOT NULL,
  link_kind TEXT NOT NULL,
  target_id TEXT,
  target_path TEXT,
  basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (markdown_document_id) REFERENCES markdown_documents(markdown_document_id) ON DELETE CASCADE,
  UNIQUE(markdown_document_id, link_kind, target_id, target_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_document_reorg_candidates (
  candidate_id TEXT PRIMARY KEY,
  markdown_document_id TEXT NOT NULL,
  reorg_status TEXT NOT NULL,
  suggested_bucket TEXT NOT NULL,
  reason TEXT NOT NULL,
  confidence REAL NOT NULL,
  advisory_only INTEGER NOT NULL DEFAULT 1,
  moved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (markdown_document_id) REFERENCES markdown_documents(markdown_document_id) ON DELETE CASCADE,
  UNIQUE(markdown_document_id, suggested_bucket)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_document_supersession (
  relation_id TEXT PRIMARY KEY,
  markdown_document_id TEXT NOT NULL,
  relation_kind TEXT NOT NULL,
  superseded_by_path TEXT,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (markdown_document_id) REFERENCES markdown_documents(markdown_document_id) ON DELETE CASCADE,
  UNIQUE(markdown_document_id, relation_kind, superseded_by_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_document_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  report TEXT NOT NULL,
  created_at TEXT NOT NULL,
  result_count INTEGER NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  body_read INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES markdown_atlas_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_markdown_documents_run ON markdown_documents(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_documents_role ON markdown_documents(document_role)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_documents_freshness ON markdown_documents(freshness_status)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_documents_retrieval ON markdown_documents(retrieval_policy)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_documents_root ON markdown_documents(root_id)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_classifications_axis ON markdown_document_classifications(axis, value)",
    )


def init_markdown_knowledge_atlas_schema(db_path: str | Path | None = None) -> str:
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


def markdown_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_markdown_knowledge_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'markdown_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_corpus_runs_by_root(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    roots = conn.execute(
        """
SELECT root_id
FROM corpus_roots
ORDER BY root_id
""".strip()
    ).fetchall()
    rows: list[sqlite3.Row] = []
    for root in roots:
        row = conn.execute(
            """
SELECT run_id, root_id, completed_at, started_at
FROM corpus_atlas_runs
WHERE root_id = ?
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip(),
            (root["root_id"],),
        ).fetchone()
        if row is not None:
            rows.append(row)
    return rows


def _source_digest(corpus_run_ids: Iterable[str]) -> str:
    payload = stable_json(
        {
            "version": MARKDOWN_ATLAS_VERSION,
            "corpus_run_ids": sorted(corpus_run_ids),
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _is_markdown_path(relative_path: str) -> bool:
    return relative_path.lower().endswith(".md")


def _path_parts(relative_path: str) -> set[str]:
    return {part.lower() for part in Path(relative_path).parts}


def _module_topic_for(relative_path: str) -> str:
    lower = relative_path.lower()
    topics = (
        ("operator_action", "operator_action"),
        ("context_selection", "context_selection"),
        ("project_capsule", "project_capsule"),
        ("report_bridge", "report_bridge"),
        ("tool_inventory", "tool_inventory"),
        ("tool_intake", "tool_intake"),
        ("corpus_atlas", "corpus_atlas"),
        ("markdown_knowledge_atlas", "markdown_knowledge_atlas"),
        ("evidence_kettle", "evidence_kettle"),
        ("mac_mirror", "mac_mirror_atlas"),
        ("read_model_shuttle", "read_model_shuttle"),
        ("mission_control", "mission_control"),
        ("runtime", "runtime_gate"),
        ("activation", "runtime_gate"),
        ("truth", "truth_registry"),
        ("receipt", "receipt_spine"),
        ("module_registry", "module_registry"),
        ("legacy_repo", "legacy_repo_intake"),
        ("full_suite", "testing"),
        ("failure_baseline", "testing"),
        ("baseline", "testing"),
        ("doc_governance", "doc_governance"),
        ("doc_lifecycle", "doc_governance"),
    )
    for needle, topic in topics:
        if needle in lower:
            return topic
    if "legal" in lower:
        return "legal_product_planning"
    if "music" in lower or "producer" in lower:
        return "music_art"
    if "business" in lower:
        return "business_development"
    return "openclaw"


def _sensitivity_status(row: sqlite3.Row) -> tuple[str, str]:
    sensitivity = row["sensitivity_label"]
    retrieval = row["retrieval_eligibility"]
    raw = row["raw_content_eligibility"]
    if raw == "no_go" or retrieval in {"blocked_no_go", "blocked_sensitive"}:
        return "no_go", "corpus path is no-go or blocked-sensitive"
    if sensitivity in {"credential_boundary", "finance_boundary", "legal_tax_boundary", "private", "no_go"}:
        return "no_go", f"corpus sensitivity is {sensitivity}"
    if sensitivity in {"metadata_only", "runtime_log_boundary"} or raw == "metadata_only":
        return "sensitive_metadata_only", "corpus metadata-only boundary"
    if sensitivity in {"public_project", "internal_project"}:
        return "normal_internal", "corpus sensitivity is project-safe"
    return "unknown_review", "corpus sensitivity requires review"


def _retrieval_policy(row: sqlite3.Row, sensitivity_status: str) -> tuple[str, str]:
    retrieval = row["retrieval_eligibility"]
    source_role = row["source_role"]
    if sensitivity_status == "no_go" or retrieval in {"blocked_no_go", "blocked_sensitive"}:
        return "blocked_no_go", "blocked by corpus no-go/sensitive retrieval gate"
    if source_role == "generated_read_model" or retrieval == "generated_read_model_only":
        return "generated_surface_only", "generated read-model Markdown is retrievable only as a generated surface"
    if retrieval == "retrievable" and sensitivity_status == "normal_internal":
        return "agent_retrievable", "corpus marks this Markdown retrievable"
    if retrieval in {"metadata_only", "receipt_metadata_only"} or sensitivity_status == "sensitive_metadata_only":
        return "metadata_only", "metadata-only document boundary"
    return "needs_operator_review", "corpus retrieval requires operator review or is unknown"


def _document_role(relative_path: str, row: sqlite3.Row) -> tuple[str, str, float]:
    filename = Path(relative_path).name
    upper_name = filename.upper()
    lower = relative_path.lower()
    parts = _path_parts(relative_path)
    source_role = row["source_role"]

    if row["raw_content_eligibility"] == "no_go" or row["sensitivity_label"] in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "no_go",
    }:
        return "unknown_review", "no-go/sensitive Markdown role is not inferred from raw content", 0.95
    if source_role == "generated_read_model" or lower.startswith("generated/read_models/") or lower.startswith("operator/generated_"):
        return "generated_status", "generated read-model/status Markdown path", 0.9
    if relative_path in CANONICAL_DOCTRINE_PATHS or lower.startswith("docs/doctrine/"):
        return "canonical_doctrine", "canonical doctrine/runtime path", 0.95
    if "current_system_map" in lower:
        return "current_system_map", "current system map filename", 0.95
    if "baseline" in lower or "failure_baseline" in lower:
        return "test_baseline", "baseline filename", 0.85
    if "handoff" in lower or "checkpoint" in lower:
        return "active_handoff", "handoff/checkpoint filename", 0.75
    if "discovery" in lower:
        return "planning_note", "discovery document filename", 0.75
    if "prompt" in lower or "spec" in lower or "contract" in lower or "plan" in lower:
        return "implementation_spec", "spec/contract/plan filename", 0.7
    if "product" in lower or "vision" in lower:
        return "product_vision", "product/vision filename", 0.7
    if "ux" in lower or "taste" in lower:
        return "ux_taste", "UX/taste filename", 0.7
    if "archives" in parts or "archive" in parts or "legacy" in parts or "project_packets_archive" in lower:
        return "legacy_doc", "archive/legacy path", 0.8
    if lower.startswith("docs/planning/") or "planning" in parts:
        return "planning_note", "planning path", 0.65
    if lower.startswith("docs/operations/") or lower.startswith("operator/"):
        return "operation_doc", "operations/operator document path", 0.7
    if source_role == "docs":
        return "operation_doc", "generic corpus docs role", 0.55
    return "unknown_review", "no document-role heuristic matched", 0.35


def _freshness_status(relative_path: str, row: sqlite3.Row, document_role: str) -> tuple[str, str]:
    lower = relative_path.lower()
    parts = _path_parts(relative_path)
    freshness = row["freshness_label"]
    canonicality = row["canonicality"]
    if relative_path in KNOWN_STALE_PATHS:
        return "stale_possible", "known stale Markdown path"
    if freshness in {"generated_current", "current_source_of_truth"}:
        return "current", f"corpus freshness is {freshness}"
    if canonicality in {"canonical_current", "generated_current"}:
        return "current", f"corpus canonicality is {canonicality}"
    if freshness == "stale_possible":
        return "stale_possible", "corpus marks stale_possible"
    if freshness in {"superseded", "deprecated"} or canonicality == "superseded":
        return "superseded", "corpus marks superseded/deprecated"
    if "archives" in parts or "archive" in parts or "legacy" in parts or "project_packets_archive" in lower:
        return "superseded", "archive/legacy path"
    if row["reorg_bucket"] in {"docs_legacy", "scratch_archive"}:
        return "stale_possible", f"corpus reorg bucket is {row['reorg_bucket']}"
    if document_role in {
        "canonical_doctrine",
        "current_system_map",
        "active_handoff",
        "generated_status",
        "operation_doc",
        "test_baseline",
        "implementation_spec",
    } and row["reorg_bucket"] in {"docs_current", "generated_output", "unknown_review"}:
        return "current", "path role and corpus bucket indicate current working document"
    return "unknown_review", "freshness requires operator review"


def _reorg_status(relative_path: str, row: sqlite3.Row, freshness_status: str, document_role: str) -> tuple[str, str]:
    lower = relative_path.lower()
    parts = _path_parts(relative_path)
    if row["raw_content_eligibility"] == "no_go" or row["retrieval_eligibility"] in {"blocked_no_go", "blocked_sensitive"}:
        return "unknown_review", "no-go/sensitive path requires review before any reorg"
    if "scratch" in parts or row["reorg_bucket"] == "scratch_archive":
        return "scratch", "scratch/archive corpus bucket"
    if freshness_status in {"stale_possible", "superseded"} or row["reorg_bucket"] == "docs_legacy":
        return "archive_candidate", "stale/superseded document is advisory archive candidate"
    if document_role in {
        "canonical_doctrine",
        "current_system_map",
        "active_handoff",
        "generated_status",
        "operation_doc",
        "implementation_spec",
        "test_baseline",
    } and freshness_status == "current":
        return "keep_current", "current document should remain in place"
    if "archive" in lower or "legacy" in lower:
        return "archive_candidate", "archive/legacy path"
    return "unknown_review", "reorg status requires operator review"


def _suggested_bucket(row: sqlite3.Row, reorg_status: str, document_role: str) -> str:
    if reorg_status == "archive_candidate":
        return "docs_legacy"
    if reorg_status == "scratch":
        return "scratch_archive"
    if reorg_status == "keep_current":
        if document_role == "generated_status":
            return "keep_generated"
        return "docs_current"
    if row["retrieval_eligibility"] in {"blocked_no_go", "blocked_sensitive"}:
        return "no_go_boundary"
    return "review_required"


def _superseded_by_path(relative_path: str) -> str | None:
    mapping = {
        "CURRENT_STATE.md": "generated/read_models/generated_current_state.md",
        "NEXT_ACTIONS.md": "generated/read_models/generated_next_actions.md",
    }
    return mapping.get(relative_path)


def classify_markdown_document(row: sqlite3.Row) -> dict[str, Any]:
    relative_path = row["relative_path"]
    role, role_reason, role_confidence = _document_role(relative_path, row)
    sensitivity, sensitivity_reason = _sensitivity_status(row)
    retrieval, retrieval_reason = _retrieval_policy(row, sensitivity)
    freshness, freshness_reason = _freshness_status(relative_path, row, role)
    reorg, reorg_reason = _reorg_status(relative_path, row, freshness, role)
    module_topic = _module_topic_for(relative_path)
    confidence = min(
        role_confidence,
        0.95 if sensitivity != "unknown_review" else 0.45,
        0.9 if retrieval != "needs_operator_review" else 0.55,
        0.9 if freshness != "unknown_review" else 0.45,
        0.9 if reorg != "unknown_review" else 0.45,
    )
    basis = "corpus_path_metadata_and_path_heuristics"
    reason = "; ".join(
        [
            f"role: {role_reason}",
            f"freshness: {freshness_reason}",
            f"reorg: {reorg_reason}",
            f"sensitivity: {sensitivity_reason}",
            f"retrieval: {retrieval_reason}",
        ]
    )
    rule = f"{role}|{freshness}|{reorg}|{sensitivity}|{retrieval}"
    return {
        "document_role": role,
        "freshness_status": freshness,
        "reorg_status": reorg,
        "sensitivity_status": sensitivity,
        "retrieval_policy": retrieval,
        "module_topic": module_topic,
        "source_basis": basis,
        "classification_rule": rule,
        "confidence": confidence,
        "reason": reason,
        "suggested_bucket": _suggested_bucket(row, reorg, role),
        "superseded_by_path": _superseded_by_path(relative_path),
    }


def _markdown_source_rows(conn: sqlite3.Connection, corpus_run_ids: tuple[str, ...]) -> list[sqlite3.Row]:
    if not corpus_run_ids:
        return []
    placeholders = ",".join("?" for _ in corpus_run_ids)
    return conn.execute(
        f"""
SELECT
  p.path_id AS corpus_path_id,
  p.run_id AS corpus_run_id,
  p.root_id,
  r.root_kind,
  r.host_kind,
  r.owner_scope,
  r.project_id,
  r.client_id,
  r.canonical_status,
  r.import_status,
  r.mirror_of_root_id,
  r.lineage_source,
  p.relative_path,
  p.path_name AS filename,
  p.source_role,
  p.freshness_label,
  p.sensitivity_label,
  p.raw_content_eligibility,
  p.retrieval_eligibility,
  p.ingestion_eligibility,
  p.canonicality,
  p.world_binding,
  p.evidence_category,
  p.reorg_bucket,
  p.created_at AS observed_at
FROM corpus_paths p
JOIN corpus_roots r ON r.root_id = p.root_id
WHERE p.run_id IN ({placeholders})
  AND p.path_type = 'file'
  AND lower(p.relative_path) LIKE '%.md'
ORDER BY p.root_id, p.relative_path
""".strip(),
        corpus_run_ids,
    ).fetchall()


def _insert_document(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    row: sqlite3.Row,
    classification: dict[str, Any],
    now: str,
) -> str:
    document_id = _row_id("mdoc", run_id, row["corpus_path_id"])
    conn.execute(
        """
INSERT INTO markdown_documents (
  markdown_document_id, run_id, corpus_path_id, corpus_run_id, root_id,
  root_kind, host_kind, owner_scope, project_id, client_id, canonical_status,
  import_status, mirror_of_root_id, lineage_source, relative_path, filename,
  document_role, freshness_status, reorg_status, sensitivity_status,
  retrieval_policy, world_binding, module_topic, source_basis,
  classification_rule, confidence, reason, observed_at, body_read,
  raw_body_stored, truth_claimed, runtime_authority, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
ON CONFLICT(run_id, corpus_path_id) DO UPDATE SET
  document_role = excluded.document_role,
  freshness_status = excluded.freshness_status,
  reorg_status = excluded.reorg_status,
  sensitivity_status = excluded.sensitivity_status,
  retrieval_policy = excluded.retrieval_policy,
  world_binding = excluded.world_binding,
  module_topic = excluded.module_topic,
  source_basis = excluded.source_basis,
  classification_rule = excluded.classification_rule,
  confidence = excluded.confidence,
  reason = excluded.reason,
  observed_at = excluded.observed_at
""".strip(),
        (
            document_id,
            run_id,
            row["corpus_path_id"],
            row["corpus_run_id"],
            row["root_id"],
            row["root_kind"],
            row["host_kind"],
            row["owner_scope"],
            row["project_id"],
            row["client_id"],
            row["canonical_status"],
            row["import_status"],
            row["mirror_of_root_id"],
            row["lineage_source"],
            row["relative_path"],
            row["filename"],
            classification["document_role"],
            classification["freshness_status"],
            classification["reorg_status"],
            classification["sensitivity_status"],
            classification["retrieval_policy"],
            row["world_binding"],
            classification["module_topic"],
            classification["source_basis"],
            classification["classification_rule"],
            classification["confidence"],
            classification["reason"],
            row["observed_at"],
            now,
        ),
    )
    return document_id


def _insert_axis_labels(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    classification: dict[str, Any],
    now: str,
) -> None:
    for axis in CLASSIFICATION_AXES:
        value = classification[axis]
        conn.execute(
            """
INSERT INTO markdown_document_classifications (
  classification_id, markdown_document_id, axis, value, confidence, basis, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(markdown_document_id, axis) DO UPDATE SET
  value = excluded.value,
  confidence = excluded.confidence,
  basis = excluded.basis,
  reason = excluded.reason
""".strip(),
            (
                _row_id("mdclass", document_id, axis),
                document_id,
                axis,
                value,
                classification["confidence"],
                classification["source_basis"],
                classification["reason"],
                now,
            ),
        )


def _insert_links(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    row: sqlite3.Row,
    now: str,
) -> None:
    links = [
        ("corpus_path", row["corpus_path_id"], row["relative_path"], "source corpus path row"),
        ("corpus_run", row["corpus_run_id"], None, "source corpus atlas run"),
        ("root", row["root_id"], None, "source root registry row"),
    ]
    for link_kind, target_id, target_path, basis in links:
        conn.execute(
            """
INSERT INTO markdown_document_links (
  link_id, markdown_document_id, link_kind, target_id, target_path, basis, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(link_id) DO UPDATE SET
  basis = excluded.basis
""".strip(),
            (
                _row_id("mdlink", document_id, link_kind, target_id or "", target_path or ""),
                document_id,
                link_kind,
                target_id,
                target_path,
                basis,
                now,
            ),
        )


def _insert_reorg_candidate(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    classification: dict[str, Any],
    now: str,
) -> None:
    conn.execute(
        """
INSERT INTO markdown_document_reorg_candidates (
  candidate_id, markdown_document_id, reorg_status, suggested_bucket,
  reason, confidence, advisory_only, moved, created_at
) VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)
ON CONFLICT(markdown_document_id, suggested_bucket) DO UPDATE SET
  reorg_status = excluded.reorg_status,
  reason = excluded.reason,
  confidence = excluded.confidence,
  advisory_only = 1,
  moved = 0
""".strip(),
        (
            _row_id("mdreorg", document_id, classification["suggested_bucket"]),
            document_id,
            classification["reorg_status"],
            classification["suggested_bucket"],
            classification["reason"],
            classification["confidence"],
            now,
        ),
    )


def _insert_supersession(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    classification: dict[str, Any],
    now: str,
) -> None:
    superseded_by_path = classification.get("superseded_by_path")
    if classification["freshness_status"] not in {"stale_possible", "superseded"} and not superseded_by_path:
        return
    relation_kind = "superseded_by_generated_status" if superseded_by_path else "possible_supersession"
    conn.execute(
        """
INSERT INTO markdown_document_supersession (
  relation_id, markdown_document_id, relation_kind, superseded_by_path,
  confidence, reason, operator_review_required, created_at
) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
ON CONFLICT(relation_id) DO UPDATE SET
  confidence = excluded.confidence,
  reason = excluded.reason,
  operator_review_required = 1
""".strip(),
        (
            _row_id("mdsuper", document_id, relation_kind, superseded_by_path or ""),
            document_id,
            relation_kind,
            superseded_by_path,
            classification["confidence"],
            classification["reason"],
            now,
        ),
    )


def _count_documents(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    materialized = list(rows)
    fields = (
        "document_role",
        "freshness_status",
        "reorg_status",
        "sensitivity_status",
        "retrieval_policy",
        "world_binding",
        "module_topic",
        "root_id",
    )
    return {
        field: dict(sorted(Counter(str(row[field]) for row in materialized).items()))
        for field in fields
    }


def build_markdown_knowledge_atlas(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> MarkdownAtlasResult:
    path = init_markdown_knowledge_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        corpus_runs = _latest_corpus_runs_by_root(conn)
        corpus_run_ids = tuple(row["run_id"] for row in corpus_runs)
        resolved_run_id = run_id or f"mdatlas_{_source_digest(corpus_run_ids)}"
        now = utc_now()
        source_runs = [
            {
                "run_id": row["run_id"],
                "root_id": row["root_id"],
                "completed_at": row["completed_at"],
                "started_at": row["started_at"],
            }
            for row in corpus_runs
        ]
        conn.execute(
            """
INSERT INTO markdown_atlas_runs (
  run_id, atlas_version, created_at, completed_at, source_corpus_runs_json,
  source_root_count, document_count, body_read, raw_body_stored,
  runtime_authority, agent_activation_allowed, tool_execution_allowed,
  network_authority, file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  source_corpus_runs_json = excluded.source_corpus_runs_json,
  source_root_count = excluded.source_root_count,
  body_read = 0,
  raw_body_stored = 0,
  runtime_authority = 0,
  agent_activation_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                MARKDOWN_ATLAS_VERSION,
                now,
                now,
                stable_json({"corpus_runs": source_runs}),
                len(source_runs),
                "Corpus-linked Markdown role overlay; metadata-only, no body reads, no file moves.",
            ),
        )
        source_rows = _markdown_source_rows(conn, corpus_run_ids)
        classified_for_counts: list[dict[str, Any]] = []
        for source_row in source_rows:
            classification = classify_markdown_document(source_row)
            document_id = _insert_document(
                conn,
                run_id=resolved_run_id,
                row=source_row,
                classification=classification,
                now=now,
            )
            _insert_axis_labels(conn, document_id=document_id, classification=classification, now=now)
            _insert_links(conn, document_id=document_id, row=source_row, now=now)
            _insert_reorg_candidate(conn, document_id=document_id, classification=classification, now=now)
            _insert_supersession(conn, document_id=document_id, classification=classification, now=now)
            classified_for_counts.append(
                {
                    **classification,
                    "root_id": source_row["root_id"],
                    "world_binding": source_row["world_binding"],
                    "relative_path": source_row["relative_path"],
                }
            )
        conn.execute(
            """
UPDATE markdown_atlas_runs
SET completed_at = ?, document_count = ?
WHERE run_id = ?
""".strip(),
            (now, len(source_rows), resolved_run_id),
        )
        conn.commit()
        counts = _count_documents(classified_for_counts)
        return MarkdownAtlasResult(
            run_id=resolved_run_id,
            db_path=path,
            document_count=len(source_rows),
            source_corpus_runs=corpus_run_ids,
            counts=counts,
        )
    finally:
        conn.close()


def latest_markdown_run_id(db_path: str | Path | None = None) -> str | None:
    path = init_markdown_knowledge_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            """
SELECT run_id
FROM markdown_atlas_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _group_counts(conn: sqlite3.Connection, run_id: str, column: str) -> dict[str, int]:
    allowed = {
        "document_role",
        "freshness_status",
        "reorg_status",
        "sensitivity_status",
        "retrieval_policy",
        "world_binding",
        "module_topic",
        "root_id",
    }
    if column not in allowed:
        raise ValueError(f"unsupported markdown count column: {column}")
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) FROM markdown_documents WHERE run_id = ? GROUP BY {column} ORDER BY {column}",
        (run_id,),
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _document_rows(
    conn: sqlite3.Connection,
    run_id: str,
    where_sql: str = "1 = 1",
    params: tuple[Any, ...] = (),
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT relative_path, root_id, document_role, freshness_status, reorg_status,
       sensitivity_status, retrieval_policy, world_binding, module_topic,
       confidence, reason
FROM markdown_documents
WHERE run_id = ? AND ({where_sql})
ORDER BY
  CASE retrieval_policy
    WHEN 'agent_retrievable' THEN 0
    WHEN 'generated_surface_only' THEN 1
    WHEN 'metadata_only' THEN 2
    WHEN 'needs_operator_review' THEN 3
    ELSE 4
  END,
  relative_path
LIMIT ?
""".strip(),
        (run_id, *params, limit),
    ).fetchall()
    keys = (
        "relative_path",
        "root_id",
        "document_role",
        "freshness_status",
        "reorg_status",
        "sensitivity_status",
        "retrieval_policy",
        "world_binding",
        "module_topic",
        "confidence",
        "reason",
    )
    return [dict(zip(keys, row)) for row in rows]


def build_markdown_report(db_path: str | Path | None = None, run_id: str | None = None) -> dict[str, Any]:
    path = init_markdown_knowledge_atlas_schema(db_path)
    run_id = run_id or latest_markdown_run_id(path)
    if not run_id:
        return {
            "atlas_version": MARKDOWN_ATLAS_VERSION,
            "run_id": None,
            "status": "no_runs",
            **NO_AUTHORITY_FLAGS,
        }
    conn = sqlite3.connect(path)
    try:
        run = conn.execute(
            """
SELECT run_id, atlas_version, created_at, completed_at, source_corpus_runs_json,
       source_root_count, document_count, body_read, raw_body_stored,
       runtime_authority, agent_activation_allowed, tool_execution_allowed,
       network_authority, file_move_allowed, file_delete_allowed
FROM markdown_atlas_runs
WHERE run_id = ?
""".strip(),
            (run_id,),
        ).fetchone()
        if not run:
            return {
                "atlas_version": MARKDOWN_ATLAS_VERSION,
                "run_id": run_id,
                "status": "missing_run",
                **NO_AUTHORITY_FLAGS,
            }
        counts = {
            "document_role": _group_counts(conn, run_id, "document_role"),
            "freshness_status": _group_counts(conn, run_id, "freshness_status"),
            "reorg_status": _group_counts(conn, run_id, "reorg_status"),
            "sensitivity_status": _group_counts(conn, run_id, "sensitivity_status"),
            "retrieval_policy": _group_counts(conn, run_id, "retrieval_policy"),
            "world_binding": _group_counts(conn, run_id, "world_binding"),
            "module_topic": _group_counts(conn, run_id, "module_topic"),
            "root_id": _group_counts(conn, run_id, "root_id"),
        }
        source_runs = json.loads(run[4])
        report = {
            "atlas_version": run[1],
            "run": {
                "run_id": run[0],
                "created_at": run[2],
                "completed_at": run[3],
                "source_corpus_runs": source_runs.get("corpus_runs", []),
                "source_root_count": run[5],
                "document_count": run[6],
                "body_read": bool(run[7]),
                "raw_body_stored": bool(run[8]),
                "runtime_authority": bool(run[9]),
                "agent_activation_allowed": bool(run[10]),
                "tool_execution_allowed": bool(run[11]),
                "network_authority": bool(run[12]),
                "file_move_allowed": bool(run[13]),
                "file_delete_allowed": bool(run[14]),
            },
            "counts": counts,
            "current_documents": _document_rows(
                conn,
                run_id,
                "freshness_status = 'current' AND reorg_status = 'keep_current'",
                limit=20,
            ),
            "stale_superseded_documents": _document_rows(
                conn,
                run_id,
                "freshness_status IN ('stale_possible','superseded')",
                limit=20,
            ),
            "handoffs": _document_rows(conn, run_id, "document_role = 'active_handoff'", limit=20),
            "canonical_documents": _document_rows(conn, run_id, "document_role = 'canonical_doctrine'", limit=20),
            "generated_status_documents": _document_rows(conn, run_id, "document_role = 'generated_status'", limit=20),
            "archive_candidates": _document_rows(
                conn,
                run_id,
                "reorg_status IN ('archive_candidate','scratch')",
                limit=20,
            ),
            "no_go_documents": _document_rows(
                conn,
                run_id,
                "sensitivity_status IN ('no_go','sensitive_metadata_only') OR retrieval_policy IN ('blocked_no_go','metadata_only')",
                limit=20,
            ),
            "agent_retrievable_documents": _document_rows(
                conn,
                run_id,
                "retrieval_policy = 'agent_retrievable'",
                limit=20,
            ),
            "unknown_review_documents": _document_rows(
                conn,
                run_id,
                "document_role = 'unknown_review' OR freshness_status = 'unknown_review' OR reorg_status = 'unknown_review' OR sensitivity_status = 'unknown_review' OR retrieval_policy = 'needs_operator_review'",
                limit=20,
            ),
            "boundary": {
                "body_read": False,
                "raw_body_stored": False,
                "filesystem_moves": False,
                "filesystem_deletes": False,
                "truth_claimed": False,
                **NO_AUTHORITY_FLAGS,
            },
        }
        return report
    finally:
        conn.close()


REPORT_SECTIONS = {
    "summary",
    "current",
    "stale",
    "handoffs",
    "canonical",
    "generated-status",
    "archive-candidates",
    "no-go",
    "agent-retrievable",
}


def query_markdown_report_section(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    section: str = "summary",
) -> dict[str, Any]:
    if section not in REPORT_SECTIONS:
        raise ValueError(f"unknown markdown report: {section}")
    report = build_markdown_report(db_path=db_path, run_id=run_id)
    if report.get("status") in {"no_runs", "missing_run"}:
        return report
    section_map = {
        "current": "current_documents",
        "stale": "stale_superseded_documents",
        "handoffs": "handoffs",
        "canonical": "canonical_documents",
        "generated-status": "generated_status_documents",
        "archive-candidates": "archive_candidates",
        "no-go": "no_go_documents",
        "agent-retrievable": "agent_retrievable_documents",
    }
    if section == "summary":
        return {
            "atlas_version": report["atlas_version"],
            "run": report["run"],
            "counts": report["counts"],
            "samples": {
                "current": report["current_documents"][:8],
                "stale": report["stale_superseded_documents"][:8],
                "archive_candidates": report["archive_candidates"][:8],
                "no_go": report["no_go_documents"][:8],
                "agent_retrievable": report["agent_retrievable_documents"][:8],
            },
            "boundary": report["boundary"],
        }
    key = section_map[section]
    return {
        "atlas_version": report["atlas_version"],
        "run_id": report["run"]["run_id"],
        "section": section,
        "counts": report["counts"],
        "items": report[key],
        "boundary": report["boundary"],
    }


def _count_line(title: str, counts: dict[str, int]) -> str:
    rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"
    return f"- {title}: {rendered}"


def _item_lines(items: list[dict[str, Any]], *, max_items: int = 8) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items[:max_items]:
        lines.append(
            "- "
            + item["relative_path"].replace("\n", "\\n")
            + f" ({item['root_id']}, {item['document_role']}, {item['freshness_status']}, "
            + f"{item['reorg_status']}, {item['sensitivity_status']}, {item['retrieval_policy']})"
        )
    return lines


def format_markdown_report(payload: dict[str, Any]) -> str:
    if payload.get("status") == "no_runs":
        return "Markdown Knowledge Atlas v0\n\nNo markdown atlas runs are recorded."
    if payload.get("status") == "missing_run":
        return f"Markdown Knowledge Atlas v0\n\nRun `{payload.get('run_id')}` was not found."
    if "items" in payload:
        lines = [
            f"Markdown Knowledge Atlas v0 - {payload['section']}",
            "",
            f"Run: `{payload['run_id']}`",
            "",
            "Items:",
            *_item_lines(payload["items"], max_items=20),
            "",
            "Boundary:",
            "- Metadata/document-role overlay only; no Markdown bodies are stored.",
            "- Reorg/archive rows are advisory only; no moves, deletes, or renames are authorized.",
            "- No runtime, agent, tool, Docker/Ollama, or network authority is introduced.",
        ]
        return "\n".join(lines)

    run = payload["run"]
    counts = payload["counts"]
    samples = payload["samples"]
    lines = [
        "Markdown Knowledge Atlas v0",
        "",
        "Evidence:",
        f"- Run `{run['run_id']}` classified {run['document_count']} Markdown documents from {run['source_root_count']} latest Corpus Atlas root runs.",
        f"- Body read: {str(run['body_read']).lower()}; raw body stored: {str(run['raw_body_stored']).lower()}.",
        _count_line("Document roles", counts["document_role"]),
        _count_line("Freshness status", counts["freshness_status"]),
        _count_line("Reorg status", counts["reorg_status"]),
        _count_line("Sensitivity status", counts["sensitivity_status"]),
        _count_line("Retrieval policy", counts["retrieval_policy"]),
        _count_line("World bindings", counts["world_binding"]),
        _count_line("Module topics", counts["module_topic"]),
        "",
        "Current Documents:",
        *_item_lines(samples["current"]),
        "",
        "Stale / Superseded Documents:",
        *_item_lines(samples["stale"]),
        "",
        "Archive / Scratch Candidates:",
        *_item_lines(samples["archive_candidates"]),
        "",
        "No-Go / Metadata-Only Documents:",
        *_item_lines(samples["no_go"]),
        "",
        "Agent-Retrievable Documents:",
        *_item_lines(samples["agent_retrievable"]),
        "",
        "Boundary:",
        "- Markdown Atlas rows are corpus-linked document-role classifications only.",
        "- Unknown or needs-review documents are not agent-retrievable.",
        "- Generated Markdown is exposed as generated_surface_only.",
        "- No filesystem reorganization, broad raw Markdown ingestion, no-go reads, runtime activation, or truth promotion is authorized.",
    ]
    return "\n".join(lines)


__all__ = [
    "CLASSIFICATION_AXES",
    "DOCUMENT_ROLES",
    "FRESHNESS_STATUS",
    "MARKDOWN_ATLAS_VERSION",
    "REORG_STATUS",
    "REPORT_SECTIONS",
    "RETRIEVAL_POLICY",
    "SENSITIVITY_STATUS",
    "build_markdown_knowledge_atlas",
    "build_markdown_report",
    "classify_markdown_document",
    "format_markdown_report",
    "init_markdown_knowledge_atlas_schema",
    "latest_markdown_run_id",
    "markdown_table_names",
    "query_markdown_report_section",
    "stable_json",
]
