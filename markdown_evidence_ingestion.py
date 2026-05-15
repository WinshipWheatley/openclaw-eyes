"""Approved Markdown Evidence Ingestion v0 for OpenClaw.

This module reads only explicitly approved Markdown documents identified by the
Markdown Knowledge Atlas and stores bounded headings/excerpts as parsed evidence
metadata. It is not broad Markdown ingestion, RAG, vector search, truth
promotion, or private/no-go content access.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from evidence_kettle import init_evidence_kettle_schema
from markdown_knowledge_atlas import init_markdown_knowledge_atlas_schema


ROOT = Path(__file__).resolve().parent
MARKDOWN_EVIDENCE_VERSION = "approved_markdown_evidence_v0"
READ_MODEL_VERSION = "markdown_evidence_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "markdown_evidence.json"
OPERATOR_EXPORT_NAME = "markdown_evidence_OPERATOR.md"
MAX_SOURCE_BYTES = 250_000
MAX_EXCERPT_CHARS = 420
MAX_ITEMS_PER_SOURCE = 24

EXPLICIT_SAFE_ALLOWLIST = {
    "OPENCLAW_RUNTIME.md",
    "USER.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md",
    "docs/operations/OPENCLAW_SUBSTRATE_MISSION_CONTROL_CHECKPOINT_V1.md",
    "docs/operations/OPENCLAW_RECENT_FILE_CONTEXT_V0.md",
}

EVIDENCE_LABELS = {
    "parsed_evidence_not_truth",
    "source_claim",
    "operator_note",
    "generated_status",
    "doctrine_excerpt",
}

NO_AUTHORITY_FLAGS = {
    "truth_promotion_allowed": False,
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "model_call_allowed": False,
    "vector_search_allowed": False,
    "raw_private_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "full_raw_body_stored": False,
}


@dataclass(frozen=True)
class MarkdownEvidenceResult:
    run_id: str
    db_path: str
    source_count: int
    item_count: int
    skipped_count: int
    counts_by_label: dict[str, int]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS markdown_evidence_runs (
  run_id TEXT PRIMARY KEY,
  ingestion_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  source_markdown_run_id TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  item_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  full_raw_body_stored INTEGER NOT NULL DEFAULT 0,
  raw_private_scan_allowed INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  vector_search_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_evidence_sources (
  markdown_evidence_source_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  markdown_document_id TEXT,
  corpus_path_id TEXT,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  document_role TEXT NOT NULL,
  retrieval_policy TEXT NOT NULL,
  sensitivity_status TEXT NOT NULL,
  freshness_status TEXT NOT NULL,
  world_binding TEXT NOT NULL,
  source_hash TEXT,
  hash_algorithm TEXT,
  approved_basis TEXT NOT NULL,
  source_bytes INTEGER,
  body_read INTEGER NOT NULL DEFAULT 1,
  full_raw_body_stored INTEGER NOT NULL DEFAULT 0,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES markdown_evidence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_evidence_items (
  markdown_evidence_item_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  markdown_evidence_source_id TEXT NOT NULL,
  markdown_document_id TEXT,
  source_path TEXT NOT NULL,
  line_number INTEGER,
  heading TEXT,
  excerpt TEXT NOT NULL,
  excerpt_char_count INTEGER NOT NULL,
  evidence_label TEXT NOT NULL,
  evidence_category TEXT NOT NULL,
  parsed_evidence_not_truth INTEGER NOT NULL DEFAULT 1,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  source_claim_only INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES markdown_evidence_runs(run_id) ON DELETE CASCADE,
  FOREIGN KEY (markdown_evidence_source_id) REFERENCES markdown_evidence_sources(markdown_evidence_source_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS markdown_evidence_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  query_text TEXT,
  report TEXT NOT NULL,
  run_id TEXT,
  item_count INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  vector_search_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_markdown_evidence_items_run ON markdown_evidence_items(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_evidence_items_label ON markdown_evidence_items(evidence_label)",
        "CREATE INDEX IF NOT EXISTS idx_markdown_evidence_sources_path ON markdown_evidence_sources(relative_path)",
    )


def init_markdown_evidence_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_evidence_kettle_schema(path)
    init_markdown_knowledge_atlas_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def markdown_evidence_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_markdown_evidence_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'markdown_evidence_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_markdown_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM markdown_atlas_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _eligible_markdown_rows(conn: sqlite3.Connection, markdown_run_id: str) -> tuple[list[sqlite3.Row], int]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
SELECT *
FROM markdown_documents
WHERE run_id = ?
ORDER BY relative_path
""".strip(),
        (markdown_run_id,),
    ).fetchall()
    eligible: list[sqlite3.Row] = []
    skipped = 0
    for row in rows:
        safe_allowlisted = row["relative_path"] in EXPLICIT_SAFE_ALLOWLIST
        safe_atlas_policy = (
            row["retrieval_policy"] == "agent_retrievable"
            and row["sensitivity_status"] == "normal_internal"
        )
        if safe_allowlisted or safe_atlas_policy:
            if row["sensitivity_status"] in {"no_go", "sensitive_metadata_only", "unknown_review"}:
                skipped += 1
                continue
            if not safe_allowlisted and row["retrieval_policy"] in {
                "blocked_no_go",
                "metadata_only",
                "needs_operator_review",
            }:
                skipped += 1
                continue
            eligible.append(row)
        else:
            skipped += 1
    return eligible, skipped


def _resolve_source_path(repo_root: Path, relative_path: str) -> Path:
    root = repo_root.resolve()
    source = (root / relative_path).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"markdown source path escapes repo root: {relative_path}") from exc
    return source


def _read_approved_markdown(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        if not path.is_file():
            return None, None, "not_a_file"
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            return None, size, "over_max_source_bytes"
        text = path.read_text(encoding="utf-8")
        return text, size, None
    except (OSError, UnicodeDecodeError) as exc:
        return None, None, f"read_failed:{type(exc).__name__}"


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_label_for(row: sqlite3.Row, heading: str | None) -> tuple[str, str]:
    role = row["document_role"]
    if role in {"canonical_doctrine", "current_system_map"}:
        return "doctrine_excerpt", "doctrine_or_system_map"
    if role == "generated_status":
        return "generated_status", "generated_status"
    if role in {"active_handoff", "operation_doc", "implementation_spec", "planning_note"}:
        return "operator_note", "operator_context"
    if heading and "status" in heading.lower():
        return "source_claim", "status_claim"
    return "source_claim", "approved_markdown_excerpt"


def _bounded_excerpt(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    if len(normalized) <= MAX_EXCERPT_CHARS:
        return normalized
    return normalized[: MAX_EXCERPT_CHARS - 3].rstrip() + "..."


def _iter_evidence_items(text: str, row: sqlite3.Row) -> list[dict[str, Any]]:
    lines = text.splitlines()
    items: list[dict[str, Any]] = []
    current_heading: str | None = None
    pending: list[str] = []
    pending_line = 1

    def flush() -> None:
        nonlocal pending, pending_line
        if not pending:
            return
        excerpt = _bounded_excerpt(" ".join(pending))
        if excerpt:
            label, category = _evidence_label_for(row, current_heading)
            items.append(
                {
                    "line_number": pending_line,
                    "heading": current_heading,
                    "excerpt": excerpt,
                    "evidence_label": label,
                    "evidence_category": category,
                }
            )
        pending = []

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            current_heading = re.sub(r"^#+\s*", "", stripped).strip() or stripped
            label, category = _evidence_label_for(row, current_heading)
            items.append(
                {
                    "line_number": index,
                    "heading": current_heading,
                    "excerpt": _bounded_excerpt(current_heading),
                    "evidence_label": label,
                    "evidence_category": category,
                }
            )
            continue
        if not stripped:
            flush()
            continue
        if not pending:
            pending_line = index
        pending.append(stripped)
        if len(" ".join(pending)) >= MAX_EXCERPT_CHARS:
            flush()
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break
    flush()

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str]] = set()
    for item in items:
        key = (item["heading"], item["excerpt"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= MAX_ITEMS_PER_SOURCE:
            break
    return deduped


def _source_digest(rows: Iterable[sqlite3.Row]) -> str:
    payload = [(row["markdown_document_id"], row["relative_path"], row["freshness_status"]) for row in rows]
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:20]


def ingest_approved_markdown_evidence(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
    run_id: str | None = None,
) -> MarkdownEvidenceResult:
    path = init_markdown_evidence_schema(db_path)
    root = Path(repo_root)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        markdown_run_id = _latest_markdown_run_id(conn)
        eligible_rows: list[sqlite3.Row] = []
        skipped_count = 0
        if markdown_run_id:
            eligible_rows, skipped_count = _eligible_markdown_rows(conn, markdown_run_id)
        resolved_run_id = run_id or f"markdown_evidence_{_source_digest(eligible_rows)}"

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM markdown_evidence_items WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM markdown_evidence_sources WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM markdown_evidence_runs WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT INTO markdown_evidence_runs (
  run_id, ingestion_version, created_at, completed_at, source_markdown_run_id,
  source_count, item_count, skipped_count, full_raw_body_stored,
  raw_private_scan_allowed, truth_promotion_allowed, runtime_authority,
  agent_activation_allowed, tool_execution_allowed, network_authority,
  model_call_allowed, vector_search_allowed, file_move_allowed,
  file_delete_allowed, notes
) VALUES (?, ?, ?, ?, ?, 0, 0, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                resolved_run_id,
                MARKDOWN_EVIDENCE_VERSION,
                now,
                now,
                markdown_run_id,
                skipped_count,
                "Approved Markdown evidence ingestion; bounded excerpts only, no truth promotion.",
            ),
        )

        item_count = 0
        label_counts: Counter[str] = Counter()
        source_count = 0
        for row in eligible_rows:
            source_path = _resolve_source_path(root, row["relative_path"])
            text, source_bytes, read_error = _read_approved_markdown(source_path)
            if text is None:
                skipped_count += 1
                continue
            source_count += 1
            source_id = _row_id("mdesrc", resolved_run_id, row["markdown_document_id"])
            approved_basis = (
                "explicit_safe_allowlist"
                if row["relative_path"] in EXPLICIT_SAFE_ALLOWLIST
                else "markdown_atlas_agent_retrievable"
            )
            conn.execute(
                """
INSERT INTO markdown_evidence_sources (
  markdown_evidence_source_id, run_id, markdown_document_id, corpus_path_id,
  root_id, relative_path, absolute_path, document_role, retrieval_policy,
  sensitivity_status, freshness_status, world_binding, source_hash,
  hash_algorithm, approved_basis, source_bytes, body_read,
  full_raw_body_stored, truth_claimed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sha256', ?, ?, 1, 0, 0, ?)
""".strip(),
                (
                    source_id,
                    resolved_run_id,
                    row["markdown_document_id"],
                    row["corpus_path_id"],
                    row["root_id"],
                    row["relative_path"],
                    source_path.as_posix(),
                    row["document_role"],
                    row["retrieval_policy"],
                    row["sensitivity_status"],
                    row["freshness_status"],
                    row["world_binding"],
                    _source_hash(text),
                    approved_basis,
                    source_bytes,
                    now,
                ),
            )
            for index, item in enumerate(_iter_evidence_items(text, row)):
                if item["evidence_label"] not in EVIDENCE_LABELS:
                    continue
                item_id = _row_id("mdeitem", source_id, index, item["line_number"], item["excerpt"])
                conn.execute(
                    """
INSERT INTO markdown_evidence_items (
  markdown_evidence_item_id, run_id, markdown_evidence_source_id,
  markdown_document_id, source_path, line_number, heading, excerpt,
  excerpt_char_count, evidence_label, evidence_category,
  parsed_evidence_not_truth, truth_claimed, source_claim_only, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, ?)
""".strip(),
                    (
                        item_id,
                        resolved_run_id,
                        source_id,
                        row["markdown_document_id"],
                        row["relative_path"],
                        item["line_number"],
                        item["heading"],
                        item["excerpt"],
                        len(item["excerpt"]),
                        item["evidence_label"],
                        item["evidence_category"],
                        now,
                    ),
                )
                item_count += 1
                label_counts[item["evidence_label"]] += 1

        conn.execute(
            """
UPDATE markdown_evidence_runs
SET completed_at = ?, source_count = ?, item_count = ?, skipped_count = ?
WHERE run_id = ?
""".strip(),
            (now, source_count, item_count, skipped_count, resolved_run_id),
        )
        conn.commit()
        return MarkdownEvidenceResult(
            run_id=resolved_run_id,
            db_path=path,
            source_count=source_count,
            item_count=item_count,
            skipped_count=skipped_count,
            counts_by_label=dict(sorted(label_counts.items())),
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM markdown_evidence_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


REPORT_SECTIONS = {"summary", "sources"}


def query_markdown_evidence(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    query: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown markdown evidence report: {report}")
    path = init_markdown_evidence_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {
                "status": "no_runs",
                "report": report,
                "query": query,
                "run_id": None,
                "db_path": str(path),
                "counts": {},
                "items": [],
                "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            }
        run = conn.execute("SELECT * FROM markdown_evidence_runs WHERE run_id = ?", (resolved_run_id,)).fetchone()
        sources = [
            dict(row)
            for row in conn.execute(
                """
SELECT markdown_evidence_source_id, relative_path, document_role,
       retrieval_policy, sensitivity_status, freshness_status,
       world_binding, approved_basis, source_bytes
FROM markdown_evidence_sources
WHERE run_id = ?
ORDER BY relative_path
""".strip(),
                (resolved_run_id,),
            ).fetchall()
        ]
        params: list[Any] = [resolved_run_id]
        where = "run_id = ?"
        if query:
            where += " AND (LOWER(excerpt) LIKE ? OR LOWER(COALESCE(heading, '')) LIKE ? OR LOWER(source_path) LIKE ?)"
            needle = f"%{query.lower()}%"
            params.extend([needle, needle, needle])
        items = [
            dict(row)
            for row in conn.execute(
                f"""
SELECT markdown_evidence_item_id, source_path, line_number, heading,
       excerpt, excerpt_char_count, evidence_label, evidence_category,
       parsed_evidence_not_truth, truth_claimed
FROM markdown_evidence_items
WHERE {where}
ORDER BY source_path, line_number, markdown_evidence_item_id
LIMIT 50
""".strip(),
                tuple(params),
            ).fetchall()
        ]
        label_counts = Counter(row["evidence_label"] for row in items)
        if not query:
            label_counts = Counter(
                {
                    row[0]: row[1]
                    for row in conn.execute(
                        """
SELECT evidence_label, COUNT(*)
FROM markdown_evidence_items
WHERE run_id = ?
GROUP BY evidence_label
ORDER BY evidence_label
""".strip(),
                        (resolved_run_id,),
                    ).fetchall()
                }
            )
        receipt_id = _row_id("mdequery", resolved_run_id, report, query or "")
        conn.execute(
            """
INSERT INTO markdown_evidence_query_receipts (
  query_receipt_id, query_text, report, run_id, item_count,
  raw_body_stored, model_call_allowed, vector_search_allowed, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?)
ON CONFLICT(query_receipt_id) DO UPDATE SET
  item_count = excluded.item_count,
  raw_body_stored = 0,
  model_call_allowed = 0,
  vector_search_allowed = 0
""".strip(),
            (receipt_id, query, report, resolved_run_id, len(items), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": report,
            "query": query,
            "run_id": resolved_run_id,
            "db_path": str(path),
            "run": dict(run) if run else None,
            "counts": {
                "source_count": len(sources),
                "item_count": run["item_count"] if run else len(items),
                "skipped_count": run["skipped_count"] if run else 0,
                "by_label": dict(sorted(label_counts.items())),
            },
            "sources": sources if report == "sources" else sources[:10],
            "items": items,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_markdown_evidence_report(payload: dict[str, Any]) -> str:
    if payload["status"] != "ok":
        return "\n".join(
            [
                f"Approved Markdown Evidence v0 - {payload['report']}",
                "",
                f"Status: {payload['status']}",
            ]
        )
    counts = payload["counts"]
    lines = [
        f"Approved Markdown Evidence v0 - {payload['report']}",
        "",
        f"Run: `{payload['run_id']}`",
        f"Sources: {counts['source_count']}",
        f"Items: {counts['item_count']}",
        f"Skipped: {counts['skipped_count']}",
        f"By label: {_counts_line(counts['by_label'])}",
    ]
    if payload.get("query"):
        lines.append(f"Query: `{payload['query']}`")
    lines.extend(["", "Items:"])
    for item in payload.get("items") or []:
        lines.append(
            f"- `{item['source_path']}`:{item['line_number'] or '?'} "
            f"{item['evidence_label']} heading=`{item['heading'] or 'none'}`"
        )
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Approved docs only; bounded excerpts/headings only.",
            "- Parsed evidence is not truth; no model/vector/network/tool/runtime authority.",
        ]
    )
    return "\n".join(lines)


def build_markdown_evidence_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = query_markdown_evidence(db_path=db_path, report="summary")
    generated_at = utc_now()
    if report.get("run"):
        generated_at = report["run"].get("completed_at") or generated_at
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "approved_markdown_evidence_bounded_excerpts",
        "generated_at": generated_at,
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "markdown_evidence_*",
        "latest_run_id": report.get("run_id"),
        "source_count": report.get("counts", {}).get("source_count", 0),
        "item_count": report.get("counts", {}).get("item_count", 0),
        "skipped_count": report.get("counts", {}).get("skipped_count", 0),
        "counts_by_label": report.get("counts", {}).get("by_label", {}),
        "sources": report.get("sources", []),
        "sample_items": report.get("items", [])[:20],
        "eligibility": {
            "default": "Markdown Knowledge Atlas retrieval_policy=agent_retrievable and normal_internal sensitivity",
            "explicit_safe_allowlist": sorted(EXPLICIT_SAFE_ALLOWLIST),
            "blocked": [
                "needs_operator_review",
                "metadata_only",
                "blocked_no_go",
                "sensitive_metadata_only",
                "no_go",
                "unknown_review",
            ],
        },
        "truth_posture": "parsed_evidence_not_truth",
        "next_safe_move": "Use these bounded excerpts as evidence context only; promotion requires a separate gate.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_markdown_evidence_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Approved Markdown Evidence Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over bounded `markdown_evidence_*` excerpts.",
        "- It covers explicitly approved Markdown documents only.",
        "",
        "What this is not:",
        "- It is not broad Markdown ingestion, vector search, model synthesis, truth promotion, or private/no-go content access.",
        "",
        "Summary:",
        f"- Latest run: `{read_model['latest_run_id'] or 'none'}`.",
        f"- Sources: {read_model['source_count']}.",
        f"- Items: {read_model['item_count']}.",
        f"- Skipped: {read_model['skipped_count']}.",
        f"- By label: {_counts_line(read_model['counts_by_label'])}.",
        "",
        "Boundary:",
        "- truth_promotion_allowed=false; model_call_allowed=false; vector_search_allowed=false.",
        "- raw_private_scan_allowed=false; full_raw_body_stored=false.",
        "- runtime_authority=false; agent_activation_allowed=false; tool_execution_allowed=false; network_authority=false.",
    ]
    return "\n".join(lines) + "\n"


def export_markdown_evidence_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_markdown_evidence_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_markdown_evidence_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "source_count": read_model["source_count"],
        "item_count": read_model["item_count"],
        "skipped_count": read_model["skipped_count"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "EXPLICIT_SAFE_ALLOWLIST",
    "JSON_EXPORT_NAME",
    "MARKDOWN_EVIDENCE_VERSION",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "MarkdownEvidenceResult",
    "build_markdown_evidence_read_model",
    "export_markdown_evidence_read_model",
    "format_markdown_evidence_read_model",
    "format_markdown_evidence_report",
    "ingest_approved_markdown_evidence",
    "init_markdown_evidence_schema",
    "markdown_evidence_table_names",
    "query_markdown_evidence",
    "stable_json",
]
