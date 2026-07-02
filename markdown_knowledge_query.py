"""Deterministic work-topic queries over the Markdown Knowledge Atlas.

This is a thin query layer over existing OpenClaw registries. It does not ingest
files, scan roots, call models, start services, or grant runtime authority.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import openclaw_estate_topology_registry as estate_topology
import openclaw_system_knowledge_registry as system_registry
from business_ops_ledger import DEFAULT_DB_PATH, get_canonical_facts_by_source
from markdown_knowledge_atlas import (
    BODY_READ_RETRIEVAL_POLICIES,
    init_markdown_knowledge_atlas_schema,
    latest_markdown_run_id,
    stable_json,
)


STOPWORDS = {
    "about",
    "find",
    "for",
    "how",
    "on",
    "show",
    "the",
    "what",
    "work",
    "working",
}


def _tokens(topic: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9_][a-zA-Z0-9_-]*", topic.lower()):
        if len(token) < 3 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _excerpt(text: str, tokens: list[str], *, width: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= width:
        return compact
    lowered = compact.lower()
    start = 0
    for token in tokens:
        index = lowered.find(token)
        if index >= 0:
            start = max(0, index - 90)
            break
    excerpt = compact[start : start + width].strip()
    prefix = "..." if start else ""
    suffix = "..." if start + width < len(compact) else ""
    return f"{prefix}{excerpt}{suffix}"


def _registry_task_matches(tokens: list[str], limit: int) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for task in system_registry.BUILD_TASKS:
        haystack = " ".join(str(value) for value in task.values()).lower()
        if tokens and not any(token in haystack for token in tokens):
            continue
        matches.append(
            {
                "task_id": task["task_id"],
                "title": task["title"],
                "owner_lane": task["owner_lane"],
                "status": task["status"],
                "boundary": task["boundary"],
            }
        )
        if len(matches) >= limit:
            break
    return matches


def _section_rows(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    tokens: list[str],
    limit: int,
) -> list[sqlite3.Row]:
    params: list[Any] = [run_id, *sorted(BODY_READ_RETRIEVAL_POLICIES)]
    if tokens:
        filters: list[str] = []
        for token in tokens:
            pattern = f"%{token}%"
            filters.append(
                """
(lower(s.section_text) LIKE ?
 OR lower(s.heading) LIKE ?
 OR lower(md.relative_path) LIKE ?
 OR lower(md.module_topic) LIKE ?)
""".strip()
            )
            params.extend([pattern, pattern, pattern, pattern])
        where_sql = " OR ".join(filters)
    else:
        where_sql = "1 = 1"
    params.append(limit)
    return conn.execute(
        f"""
SELECT
  s.section_id,
  s.heading,
  s.heading_path_json,
  s.start_line,
  s.end_line,
  s.section_text,
  s.content_hash,
  s.canonical_fact_id,
  md.relative_path,
  md.root_id,
  md.document_role,
  md.freshness_status,
  md.reorg_status,
  md.sensitivity_status,
  md.retrieval_policy,
  md.module_topic,
  md.confidence,
  cf.truth_status,
  cf.verification_required
FROM markdown_document_sections s
JOIN markdown_documents md ON md.markdown_document_id = s.markdown_document_id
LEFT JOIN canonical_facts cf ON cf.fact_id = s.canonical_fact_id
WHERE md.run_id = ?
  AND md.retrieval_policy IN (?, ?)
  AND ({where_sql})
ORDER BY
  CASE md.freshness_status WHEN 'current' THEN 0 WHEN 'unknown_review' THEN 2 ELSE 1 END,
  md.relative_path,
  s.section_ordinal
LIMIT ?
""".strip(),
        tuple(params),
    ).fetchall()


def query_markdown_work(
    topic: str,
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    path = init_markdown_knowledge_atlas_schema(db_path or DEFAULT_DB_PATH)
    resolved_run_id = run_id or latest_markdown_run_id(path)
    tokens = _tokens(topic)
    if not resolved_run_id:
        return {
            "status": "no_markdown_atlas_run",
            "query": topic,
            "tokens": tokens,
            "results": [],
            "registry_context": _registry_context(tokens, limit=limit),
            "authority_boundary": _authority_boundary(),
        }

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = _section_rows(conn, run_id=resolved_run_id, tokens=tokens, limit=limit)
    finally:
        conn.close()

    results = []
    for row in rows:
        try:
            heading_path = json.loads(row["heading_path_json"])
        except Exception:
            heading_path = [row["heading"]]
        canonical_fact_count = 0
        if row["canonical_fact_id"]:
            canonical_fact_count = len(get_canonical_facts_by_source(row["relative_path"], path))
        results.append(
            {
                "relative_path": row["relative_path"],
                "root_id": row["root_id"],
                "heading": row["heading"],
                "heading_path": heading_path,
                "line_range": [row["start_line"], row["end_line"]],
                "excerpt": _excerpt(row["section_text"], tokens),
                "content_hash": row["content_hash"],
                "canonical_fact_id": row["canonical_fact_id"],
                "canonical_fact_count_for_source": canonical_fact_count,
                "truth_status": row["truth_status"],
                "verification_required": bool(row["verification_required"])
                if row["verification_required"] is not None
                else True,
                "document_role": row["document_role"],
                "freshness_status": row["freshness_status"],
                "reorg_status": row["reorg_status"],
                "sensitivity_status": row["sensitivity_status"],
                "retrieval_policy": row["retrieval_policy"],
                "module_topic": row["module_topic"],
                "confidence": row["confidence"],
            }
        )

    return {
        "status": "ok",
        "query": topic,
        "tokens": tokens,
        "run_id": resolved_run_id,
        "db_path": str(path),
        "result_count": len(results),
        "results": results,
        "registry_context": _registry_context(tokens, limit=limit),
        "source_modules": {
            "markdown_atlas": "markdown_knowledge_atlas.py",
            "ledger": "business_ops_ledger.py",
            "system_registry": "openclaw_system_knowledge_registry.py",
            "estate_topology": "openclaw_estate_topology_registry.py",
        },
        "authority_boundary": _authority_boundary(),
    }


def _registry_context(tokens: list[str], *, limit: int) -> dict[str, Any]:
    return {
        "system_registry_id": system_registry.READ_MODEL_ID,
        "system_registry_schema_version": system_registry.SCHEMA_VERSION,
        "estate_topology_schema_version": estate_topology.SCHEMA_VERSION,
        "estate_topology_read_model_version": estate_topology.READ_MODEL_VERSION,
        "build_task_matches": _registry_task_matches(tokens, limit),
    }


def _authority_boundary() -> dict[str, bool]:
    return {
        "read_only_query": True,
        "filesystem_scan": False,
        "runtime_mutation": False,
        "external_call": False,
        "model_call": False,
        "send_authority": False,
    }


def format_markdown_work_query(payload: dict[str, Any]) -> str:
    if payload["status"] != "ok":
        return f"Markdown Work Query\n\nStatus: {payload['status']}"
    lines = [
        "Markdown Work Query",
        "",
        f"Query: {payload['query']}",
        f"Run: `{payload['run_id']}`",
        f"Results: {payload['result_count']}",
        "",
        "Matches:",
    ]
    if not payload["results"]:
        lines.append("- none")
    for result in payload["results"]:
        lines.append(
            "- "
            + result["relative_path"]
            + f": {result['heading']} "
            + f"({result['freshness_status']}, {result['retrieval_policy']})"
        )
    task_matches = payload["registry_context"]["build_task_matches"]
    lines.extend(["", "Registry Task Matches:"])
    if not task_matches:
        lines.append("- none")
    for task in task_matches:
        lines.append("- " + task["task_id"] + f": {task['title']} ({task['status']})")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Read-only query over existing Markdown Atlas, ledger, system registry, and estate topology modules.",
            "- No scan, runtime mutation, model call, external call, or send authority.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "format_markdown_work_query",
    "query_markdown_work",
    "stable_json",
]
