#!/usr/bin/env python3
"""Export Context Selection / Knowledge Packet v0 as generated read-model files."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from context_selection import CONTEXT_SELECTION_VERSION, stable_json


READ_MODEL_VERSION = "context_selection_read_model_v0"
MODE = "bounded_context_packet_posture_only"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "context_selection.json"
OPERATOR_EXPORT_NAME = "context_selection_OPERATOR.md"

KNOWN_SAFE_PACKET_CATEGORIES = (
    "runtime_gate",
    "future_gated_capability",
    "tool_posture",
    "generated_read_model_fact",
)

PACKET_ARTIFACT_PATHS = {
    "json": "generated/context_packets/context_packet_latest.json",
    "operator_markdown": "generated/context_packets/context_packet_latest.md",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "backend_execution_allowed": False,
    "model_call_allowed": False,
    "vector_search_allowed": False,
    "tool_execution_allowed": False,
    "docker_execution_allowed": False,
    "ollama_execution_allowed": False,
    "network_authority": False,
    "truth_promotion_allowed": False,
}

CLAIMS_NOT_MADE = (
    "truth_promotion",
    "runtime_activation",
    "agent_activation",
    "backend_execution",
    "model_call",
    "embedding_generation",
    "vector_search",
    "generic_rag",
    "tool_execution",
    "docker_execution",
    "ollama_execution",
    "network_authority",
    "private_or_no_go_raw_content",
)


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


def _ledger_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    if path.is_absolute():
        return path
    return ROOT / path


def _connect_readonly(db_path: str | Path) -> sqlite3.Connection | None:
    path = _ledger_path(db_path)
    if not path.is_file():
        return None
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM context_selection_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _latest_packet_id(conn: sqlite3.Connection, run_id: str) -> str | None:
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
    return row["packet_id"] if row else None


def _counts(conn: sqlite3.Connection, packet_id: str, field: str) -> dict[str, int]:
    allowed_fields = {
        "evidence_label",
        "evidence_category",
        "world_binding",
        "freshness_label",
        "canonicality",
        "sensitivity_label",
        "retrieval_eligibility",
        "ingestion_eligibility",
    }
    if field not in allowed_fields:
        raise ValueError(f"unsupported count field: {field}")
    rows = conn.execute(
        f"""
SELECT {field} AS label, COUNT(*) AS count
FROM context_packet_items
WHERE packet_id = ?
GROUP BY {field}
ORDER BY {field}
""".strip(),
        (packet_id,),
    ).fetchall()
    return {row["label"]: row["count"] for row in rows}


def _blocked_exclusion_count(conn: sqlite3.Connection, packet_id: str) -> int:
    row = conn.execute(
        """
SELECT COUNT(*) AS count
FROM context_packet_exclusions
WHERE packet_id = ?
  AND (
    no_go_boundary = 1
    OR sensitivity_label IN (
      'private',
      'credential_boundary',
      'finance_boundary',
      'legal_tax_boundary',
      'runtime_log_boundary',
      'no_go',
      'sensitive_metadata_only'
    )
    OR retrieval_eligibility IN (
      'blocked_no_go',
      'blocked_sensitive',
      'blocked_unknown',
      'needs_operator_review'
    )
    OR ingestion_eligibility IN ('no_go', 'needs_review', 'not_for_ingestion')
  )
""".strip(),
        (packet_id,),
    ).fetchone()
    return int(row["count"]) if row else 0


def _packet_query(packet_json: str | None) -> dict[str, Any]:
    if not packet_json:
        return {}
    try:
        packet = json.loads(packet_json)
    except json.JSONDecodeError:
        return {}
    query = packet.get("query")
    return query if isinstance(query, dict) else {}


def _source_tables(packet_json: str | None) -> list[str]:
    if not packet_json:
        return []
    try:
        packet = json.loads(packet_json)
    except json.JSONDecodeError:
        return []
    tables = packet.get("source_tables_used") or []
    if not isinstance(tables, list):
        return []
    return [str(table) for table in tables]


def _available_commands() -> dict[str, str]:
    return {
        "latest_summary": "python3 scripts/query_context_selection.py --report summary --format operator",
        "latest_items": "python3 scripts/query_context_selection.py --report items --format operator",
        "latest_sources": "python3 scripts/query_context_selection.py --report sources --format operator",
        "latest_exclusions": "python3 scripts/query_context_selection.py --report exclusions --format operator",
        "latest_receipts": "python3 scripts/query_context_selection.py --report receipts --format operator",
        "build_runtime_gate_packet": "python3 scripts/build_context_packet.py --category runtime_gate --format operator",
        "build_future_gated_packet": "python3 scripts/build_context_packet.py --category future_gated_capability --format operator",
        "build_tool_posture_packet": "python3 scripts/build_context_packet.py --category tool_posture --format operator",
        "build_build_world_packet": "python3 scripts/build_context_packet.py --world build --format operator",
    }


def _empty_read_model(*, db_path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": "not_available_no_context_selection_run",
        "source_ledger_path": _display_path(db_path),
        "source_ledger_namespace": "context_selection_*",
        "latest_context_selection_run_id": None,
        "latest_context_packet_id": None,
        "selected_item_count": 0,
        "excluded_item_count": 0,
        "no_go_exclusion_count": 0,
        "blocked_sensitive_recorded_exclusion_count": 0,
        "no_go_blocked_sensitive_exclusion_count": 0,
        "worlds_represented": {},
        "evidence_labels_represented": {},
        "evidence_categories_represented": {},
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "packet_artifact_paths": dict(PACKET_ARTIFACT_PATHS),
        "available_packet_reports": _available_commands(),
        "known_safe_packet_categories": list(KNOWN_SAFE_PACKET_CATEGORIES),
        "selected_evidence_not_truth": True,
        "context_packets_are_truth_promotion": False,
        "generic_rag": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def build_context_selection_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
    packet_id: str | None = None,
) -> dict[str, Any]:
    path = _ledger_path(db_path)
    conn = _connect_readonly(path)
    if conn is None:
        return _empty_read_model(db_path=path)
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return _empty_read_model(db_path=path)

        run = conn.execute(
            "SELECT * FROM context_selection_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        if not run:
            return _empty_read_model(db_path=path)

        resolved_packet_id = packet_id or _latest_packet_id(conn, resolved_run_id)
        if not resolved_packet_id:
            return _empty_read_model(db_path=path)

        packet_row = conn.execute(
            "SELECT * FROM context_packets WHERE packet_id = ?",
            (resolved_packet_id,),
        ).fetchone()
        if not packet_row:
            return _empty_read_model(db_path=path)

        packet_json = packet_row["packet_json"]
        query = _packet_query(packet_json)
        worlds = _counts(conn, resolved_packet_id, "world_binding")
        evidence_labels = _counts(conn, resolved_packet_id, "evidence_label")
        evidence_categories = _counts(conn, resolved_packet_id, "evidence_category")

        no_go_exclusion_count = int(packet_row["no_go_exclusion_count"])
        blocked_sensitive_recorded_count = _blocked_exclusion_count(conn, resolved_packet_id)

        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "selector_version": CONTEXT_SELECTION_VERSION,
            "mode": MODE,
            "generated_at": run["completed_at"] or run["created_at"],
            "generated_at_basis": "context_selection_run_completed_at",
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "context_selection_*",
            "latest_context_selection_run_id": resolved_run_id,
            "latest_context_packet_id": resolved_packet_id,
            "query": query,
            "selected_item_count": int(packet_row["selected_item_count"]),
            "excluded_item_count": int(packet_row["excluded_item_count"]),
            "no_go_exclusion_count": no_go_exclusion_count,
            "blocked_sensitive_recorded_exclusion_count": blocked_sensitive_recorded_count,
            "no_go_blocked_sensitive_exclusion_count": max(
                no_go_exclusion_count,
                blocked_sensitive_recorded_count,
            ),
            "worlds_represented": worlds,
            "evidence_labels_represented": evidence_labels,
            "evidence_categories_represented": evidence_categories,
            "freshness_labels_represented": _counts(conn, resolved_packet_id, "freshness_label"),
            "canonicality_represented": _counts(conn, resolved_packet_id, "canonicality"),
            "sensitivity_labels_represented": _counts(conn, resolved_packet_id, "sensitivity_label"),
            "retrieval_eligibility_represented": _counts(
                conn,
                resolved_packet_id,
                "retrieval_eligibility",
            ),
            "ingestion_eligibility_represented": _counts(
                conn,
                resolved_packet_id,
                "ingestion_eligibility",
            ),
            "source_tables_used": _source_tables(packet_json),
            "authority_flags": dict(NO_AUTHORITY_FLAGS),
            **NO_AUTHORITY_FLAGS,
            "packet_artifact_paths": {
                "json": packet_row["run_id"]
                and (run["generated_json_path"] or PACKET_ARTIFACT_PATHS["json"]),
                "operator_markdown": packet_row["run_id"]
                and (run["generated_operator_path"] or PACKET_ARTIFACT_PATHS["operator_markdown"]),
            },
            "available_packet_reports": _available_commands(),
            "known_safe_packet_categories": list(KNOWN_SAFE_PACKET_CATEGORIES),
            "selected_evidence_not_truth": True,
            "context_packets_are_truth_promotion": False,
            "context_for_reasoning_only": bool(packet_row["context_for_reasoning_only"]),
            "truth_claimed": bool(packet_row["truth_claimed"]),
            "generic_rag": False,
            "vector_search_used": False,
            "model_calls_used": False,
            "claims_not_made": list(CLAIMS_NOT_MADE),
            "boundary": {
                "packets_are_selected_evidence": True,
                "packets_are_not_truth_promotion": True,
                "unknown_needs_review_sensitive_and_no_go_excluded": True,
                "raw_private_or_no_go_content_included": False,
            },
        }
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return _empty_read_model(db_path=path)
        raise
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_operator_context_selection(read_model: dict[str, Any]) -> str:
    lines = [
        "# Context Selection Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `context_selection_*` SQLite packet rows.",
        "- It exposes bounded context-packet posture for operators, agents, and Mission Control.",
        "",
        "What this is not:",
        "- It is not generic RAG, vector search, model execution, tool execution, runtime activation, or truth promotion.",
        "- It does not include private/no-go raw content and does not approve any action.",
        "",
        "Latest packet summary:",
        f"- Latest run: `{read_model['latest_context_selection_run_id']}`.",
        f"- Latest packet: `{read_model['latest_context_packet_id']}`.",
        f"- Selected items: {read_model['selected_item_count']}.",
        f"- Excluded records: {read_model['excluded_item_count']}.",
        (
            "- No-go/blocked/sensitive exclusions: "
            f"{read_model['no_go_blocked_sensitive_exclusion_count']}."
        ),
        f"- Worlds represented: {_counts_line(read_model['worlds_represented'])}.",
        f"- Evidence labels: {_counts_line(read_model['evidence_labels_represented'])}.",
        f"- Evidence categories: {_counts_line(read_model['evidence_categories_represented'])}.",
        "",
        "Packet artifacts:",
        f"- JSON: `{read_model['packet_artifact_paths']['json']}`.",
        f"- Operator markdown: `{read_model['packet_artifact_paths']['operator_markdown']}`.",
        "",
        "Authority boundary:",
        "- Context packets are selected evidence and bounded reasoning context, not truth promotion.",
        "- runtime_authority=false; agent_activation_allowed=false; backend_execution_allowed=false.",
        "- model_call_allowed=false; vector_search_allowed=false; tool_execution_allowed=false.",
        "- docker_execution_allowed=false; ollama_execution_allowed=false; network_authority=false.",
        "- truth_promotion_allowed=false.",
        "",
        "Known safe packet categories:",
        "- runtime_gate, future_gated_capability, tool_posture, generated_read_model_fact.",
        "",
        "Next safe move:",
        "- Use this read-model as an inspection surface; any synthesis, write-back, promotion, app wiring, runtime action, model call, or tool use needs a separate scoped lane.",
    ]
    return "\n".join(lines) + "\n"


def export_context_selection_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
    packet_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_context_selection_read_model(
        db_path=db_path,
        run_id=run_id,
        packet_id=packet_id,
    )

    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_context_selection(read_model), encoding="utf-8")

    return {
        "export_version": READ_MODEL_VERSION,
        "export_root": _display_path(root),
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "latest_context_selection_run_id": read_model["latest_context_selection_run_id"],
        "latest_context_packet_id": read_model["latest_context_packet_id"],
        "selected_item_count": read_model["selected_item_count"],
        "excluded_item_count": read_model["excluded_item_count"],
        "no_go_blocked_sensitive_exclusion_count": read_model[
            "no_go_blocked_sensitive_exclusion_count"
        ],
        "metadata_only": True,
        **NO_AUTHORITY_FLAGS,
    }


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Context Selection Read-Model Export v0",
        "",
        "Evidence:",
        f"- Exported `{summary['json_path']}` and `{summary['operator_path']}`.",
        (
            f"- Latest context packet `{summary['latest_context_packet_id']}` from run "
            f"`{summary['latest_context_selection_run_id']}`: "
            f"selected={summary['selected_item_count']}, "
            f"excluded={summary['excluded_item_count']}, "
            f"no_go_blocked_sensitive={summary['no_go_blocked_sensitive_exclusion_count']}."
        ),
        "",
        "Boundary:",
        "- Export reads existing `context_selection_*` SQLite rows only and writes generated read-model files.",
        "- Context packets remain selected evidence/context, not truth promotion.",
        "",
        "Blocked:",
        "- No runtime activation, agent activation, backend execution, model calls, vector search, tool execution, Docker/Ollama execution, network authority, or truth promotion is introduced.",
        "",
        "Next safe move:",
        "- Inspect `generated/read_models/context_selection.json` or `generated/read_models/context_selection_OPERATOR.md` before any future Mission Control/app consumption lane.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Context Selection / Knowledge Packet v0 rows as generated read-model files."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Context selection run id. Defaults to latest.")
    parser.add_argument("--packet-id", help="Context packet id. Defaults to latest for run.")
    parser.add_argument(
        "--export-root",
        default=DEFAULT_EXPORT_ROOT.as_posix(),
        help="Export root. Defaults to generated/read_models.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_context_selection_read_model(
        db_path=args.db,
        export_root=args.export_root,
        run_id=args.run_id,
        packet_id=args.packet_id,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_operator_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
