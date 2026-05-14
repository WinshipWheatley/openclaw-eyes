#!/usr/bin/env python3
"""Export Local Tool Inventory v0 as bounded generated read-model files."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from tool_inventory import stable_json


READ_MODEL_VERSION = "tool_inventory_read_model_v0"
MODE = "observed_installed_tool_metadata_only"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "tool_inventory.json"
OPERATOR_EXPORT_NAME = "tool_inventory_OPERATOR.md"

CLAIMS_NOT_MADE = [
    "tool_approval",
    "tool_integration",
    "tool_activation",
    "runtime_activation_authority",
    "backend_execution",
    "agent_activation",
    "model_execution",
    "model_pull",
    "container_execution",
    "container_pull",
    "remote_access",
    "network_authority",
    "package_install",
    "package_upgrade",
    "package_remove",
    "git_clone",
    "server_or_daemon_start",
    "secret_access",
    "private_path_scan",
]


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
FROM tool_inventory_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _counts(conn: sqlite3.Connection, run_id: str, field: str, *, detected_only: bool = False) -> dict[str, int]:
    allowed_fields = {"category", "risk_level", "install_status", "integration_status", "action_status"}
    if field not in allowed_fields:
        raise ValueError(f"unsupported count field: {field}")
    where = "run_id = ?"
    if detected_only:
        where += " AND detected = 1"
    rows = conn.execute(
        f"""
SELECT {field} AS label, COUNT(*) AS count
FROM tool_observations
WHERE {where}
GROUP BY {field}
ORDER BY {field}
""".strip(),
        (run_id,),
    ).fetchall()
    return {row["label"]: row["count"] for row in rows}


def _safe_observation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "tool_id": row["tool_id"],
        "observed_name": row["observed_name"],
        "canonical_name": row["canonical_name"],
        "category": row["category"],
        "detected": bool(row["detected"]),
        "executable_path": row["executable_path"],
        "version_text": row["version_text"],
        "install_status": row["install_status"],
        "integration_status": row["integration_status"],
        "action_status": row["action_status"],
        "approval_status": "not_approved",
        "authorization_status": "not_authorized",
        "risk_level": row["risk_level"],
        "requires_operator_review": bool(row["requires_operator_review"]),
        "package_manager_hint": row["package_manager_hint"],
        "relevance_label": row["relevance_label"],
        "architecture_fit": row["architecture_fit"],
    }


def _observation_rows(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    where: str = "1=1",
    params: tuple[Any, ...] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    limit_sql = f"LIMIT {limit}" if limit is not None else ""
    rows = conn.execute(
        f"""
SELECT tool_id, observed_name, canonical_name, category, detected, executable_path,
       version_text, install_status, integration_status, action_status, risk_level,
       requires_operator_review, package_manager_hint, relevance_label, architecture_fit
FROM tool_observations
WHERE run_id = ? AND {where}
ORDER BY category, tool_id
{limit_sql}
""".strip(),
        (run_id, *params),
    ).fetchall()
    return [_safe_observation(row) for row in rows]


def _future_candidates(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT o.tool_id, o.observed_name, o.canonical_name, o.category, o.executable_path,
       o.version_text, o.risk_level, o.requires_operator_review,
       c.candidate_scope, c.candidate_status, c.candidate_basis, c.action_status
FROM tool_future_candidates c
JOIN tool_observations o ON o.observation_id = c.observation_id
WHERE o.run_id = ?
ORDER BY o.category, o.tool_id
""".strip(),
        (run_id,),
    ).fetchall()
    return [
        {
            "tool_id": row["tool_id"],
            "observed_name": row["observed_name"],
            "canonical_name": row["canonical_name"],
            "category": row["category"],
            "executable_path": row["executable_path"],
            "version_text": row["version_text"],
            "risk_level": row["risk_level"],
            "requires_operator_review": bool(row["requires_operator_review"]),
            "candidate_scope": row["candidate_scope"],
            "candidate_status": row["candidate_status"],
            "candidate_basis": row["candidate_basis"],
            "action_status": row["action_status"],
            "approval_status": "not_approved",
            "authorization_status": "not_authorized",
        }
        for row in rows
    ]


def _empty_read_model(*, db_path: str | Path) -> dict[str, Any]:
    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": "not_available_no_tool_inventory_run",
        "source_ledger_path": _display_path(db_path),
        "source_ledger_namespace": "tool_inventory_*",
        "latest_tool_inventory_run_id": None,
        "observed_candidate_count": 0,
        "detected_count": 0,
        "not_detected_count": 0,
        "counts_by_category": {},
        "detected_counts_by_category": {},
        "counts_by_risk_level": {},
        "detected_tools": [],
        "not_detected_tools": [],
        "high_risk_detected_tools": [],
        "local_llm_findings": {"tools": [], "detected_count": 0},
        "sqlite_findings": {"tools": [], "detected_count": 0},
        "future_candidates": [],
        "tool_activation_allowed": False,
        "runtime_authority": False,
        "integration_authority": False,
        "model_execution_allowed": False,
        "container_execution_allowed": False,
        "remote_access_allowed": False,
        "network_authority": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def build_tool_inventory_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
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
            "SELECT * FROM tool_inventory_runs WHERE run_id = ?", (resolved_run_id,)
        ).fetchone()
        if not run:
            return _empty_read_model(db_path=path)

        detected_tools = _observation_rows(conn, resolved_run_id, where="detected = 1")
        not_detected_tools = _observation_rows(conn, resolved_run_id, where="detected = 0")
        high_risk = _observation_rows(
            conn,
            resolved_run_id,
            where="detected = 1 AND risk_level IN ('high','critical')",
        )
        local_llm = _observation_rows(conn, resolved_run_id, where="category = ?", params=("local_llm",))
        sqlite_tools = _observation_rows(conn, resolved_run_id, where="category = ?", params=("sqlite",))

        inventory_action_flags = {
            "install_action_taken": bool(run["install_action_taken"]),
            "integration_action_taken": bool(run["integration_action_taken"]),
            "runtime_authority": bool(run["runtime_authority"]),
            "network_access_attempted": bool(run["network_access_attempted"]),
            "daemon_started": bool(run["daemon_started"]),
            "model_execution_attempted": bool(run["model_execution_attempted"]),
            "container_execution_attempted": bool(run["container_execution_attempted"]),
            "remote_access_attempted": bool(run["remote_access_attempted"]),
        }

        return {
            "read_model_version": READ_MODEL_VERSION,
            "mode": MODE,
            "generated_at": run["completed_at"] or run["started_at"],
            "generated_at_basis": "tool_inventory_run_completed_at",
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "tool_inventory_*",
            "latest_tool_inventory_run_id": resolved_run_id,
            "observed_candidate_count": run["observed_count"],
            "detected_count": run["detected_count"],
            "not_detected_count": run["not_detected_count"],
            "counts_by_category": _counts(conn, resolved_run_id, "category"),
            "detected_counts_by_category": _counts(
                conn,
                resolved_run_id,
                "category",
                detected_only=True,
            ),
            "counts_by_risk_level": _counts(conn, resolved_run_id, "risk_level"),
            "detected_tools": detected_tools,
            "not_detected_tools": not_detected_tools,
            "high_risk_detected_tools": high_risk,
            "local_llm_findings": {
                "detected_count": sum(1 for tool in local_llm if tool["detected"]),
                "tools": local_llm,
                "boundary": "Local LLM tooling is observed metadata only; models are not listed, pulled, run, or authorized.",
            },
            "sqlite_findings": {
                "detected_count": sum(1 for tool in sqlite_tools if tool["detected"]),
                "tools": sqlite_tools,
                "boundary": "SQLite tooling observations do not change the existing Python-stdlib ledger access path.",
            },
            "future_candidates": _future_candidates(conn, resolved_run_id),
            "inventory_action_flags": inventory_action_flags,
            "tool_activation_allowed": False,
            "runtime_authority": False,
            "integration_authority": False,
            "model_execution_allowed": False,
            "container_execution_allowed": False,
            "remote_access_allowed": False,
            "network_authority": False,
            "tool_install_allowed": False,
            "tool_upgrade_allowed": False,
            "tool_remove_allowed": False,
            "agent_activation_allowed": False,
            "body_ingested": False,
            "raw_sensitive_data_stored": False,
            "claims_not_made": list(CLAIMS_NOT_MADE),
        }
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return _empty_read_model(db_path=path)
        raise
    finally:
        conn.close()


def _tool_list(tools: list[dict[str, Any]], *, include_versions: bool = True) -> str:
    if not tools:
        return "none"
    rendered = []
    for tool in tools:
        version = f" ({tool['version_text']})" if include_versions and tool.get("version_text") else ""
        rendered.append(f"`{tool['tool_id']}`{version}")
    return ", ".join(rendered)


def format_operator_tool_inventory(read_model: dict[str, Any]) -> str:
    local_llm_tools = read_model["local_llm_findings"]["tools"]
    sqlite_tools = read_model["sqlite_findings"]["tools"]
    detected = read_model["detected_tools"]
    not_detected = read_model["not_detected_tools"]
    high_risk = read_model["high_risk_detected_tools"]
    not_detected_sample = not_detected[:16]
    omitted = max(0, len(not_detected) - len(not_detected_sample))

    lines = [
        "# Tool Inventory Read-Model v0",
        "",
        "Evidence:",
        (
            f"- Latest inventory run `{read_model['latest_tool_inventory_run_id']}` observed "
            f"{read_model['observed_candidate_count']} candidates: detected={read_model['detected_count']}, "
            f"not_detected={read_model['not_detected_count']}."
        ),
        f"- Detected tools: {_tool_list(detected)}.",
        f"- Not detected sample: {_tool_list(not_detected_sample, include_versions=False)}"
        + (f" plus {omitted} more." if omitted else "."),
        f"- High-risk detected tools: {_tool_list(high_risk)}.",
        f"- Local LLM findings: {_tool_list(local_llm_tools)}.",
        f"- SQLite findings: {_tool_list(sqlite_tools, include_versions=False)}.",
        "",
        "Boundary:",
        "- Installed does not mean approved.",
        "- Detected does not mean integrated.",
        "- Available does not mean authorized.",
        "- Ollama installed does not mean models may be listed, pulled, run, or used by agents.",
        "- Docker installed does not mean containers may be built, pulled, run, or composed.",
        "- This export reads existing SQLite inventory rows only; it does not probe tools.",
        "",
        "Blocked:",
        "- tool_activation_allowed=false; integration_authority=false; runtime_authority=false.",
        "- model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false; network_authority=false.",
        "- No installs, upgrades, removals, git clones, remote access, server starts, daemon starts, model pulls, model runs, or container runs are authorized.",
        "",
        "Next safe move:",
        "- Use this read-model for inspection only; any future tool integration, sandbox, local model, deployment, sync, or client-capsule lane needs separate operator-scoped approval and tests.",
    ]
    return "\n".join(lines) + "\n"


def export_tool_inventory_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_tool_inventory_read_model(db_path=db_path, run_id=run_id)

    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_tool_inventory(read_model), encoding="utf-8")

    return {
        "export_version": READ_MODEL_VERSION,
        "export_root": _display_path(root),
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "latest_tool_inventory_run_id": read_model["latest_tool_inventory_run_id"],
        "observed_candidate_count": read_model["observed_candidate_count"],
        "detected_count": read_model["detected_count"],
        "not_detected_count": read_model["not_detected_count"],
        "high_risk_detected_count": len(read_model["high_risk_detected_tools"]),
        "metadata_only": True,
        "body_ingested": False,
        "tool_activation_allowed": False,
        "runtime_authority": False,
        "integration_authority": False,
        "model_execution_allowed": False,
        "container_execution_allowed": False,
        "remote_access_allowed": False,
        "network_authority": False,
    }


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Tool Inventory Read-Model Export v0",
        "",
        "Evidence:",
        f"- Exported `{summary['json_path']}` and `{summary['operator_path']}`.",
        (
            f"- Latest inventory run `{summary['latest_tool_inventory_run_id']}`: "
            f"observed={summary['observed_candidate_count']}, detected={summary['detected_count']}, "
            f"not_detected={summary['not_detected_count']}, high_risk_detected={summary['high_risk_detected_count']}."
        ),
        "",
        "Boundary:",
        "- Export reads existing `tool_inventory_*` SQLite rows only and writes generated read-model files.",
        "- Installed tools remain observations only: not approved, not integrated, and not authorized.",
        "",
        "Blocked:",
        "- No installs, integrations, runtime activation, network authority, model execution, container execution, or remote access are introduced.",
        "",
        "Next safe move:",
        "- Inspect `generated/read_models/tool_inventory.json` or `generated/read_models/tool_inventory_OPERATOR.md` before any future bounded integration lane.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Local Tool Inventory v0 rows as generated read-model files."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Tool inventory run id. Defaults to latest.")
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
    summary = export_tool_inventory_read_model(
        db_path=args.db,
        export_root=args.export_root,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_operator_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
