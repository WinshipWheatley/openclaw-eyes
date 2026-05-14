#!/usr/bin/env python3
"""Export Report Bridge v0 rows as bounded generated read-model files."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from report_bridge import DEFAULT_REPORT_BRIDGE_INBOX, NO_AUTHORITY_FLAGS, stable_json


READ_MODEL_VERSION = "report_bridge_read_model_v0"
MODE = "sanitized_report_package_posture_only"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "report_bridge.json"
OPERATOR_EXPORT_NAME = "report_bridge_OPERATOR.md"

EXTENDED_NO_AUTHORITY_FLAGS = {
    **NO_AUTHORITY_FLAGS,
    "client_data_access": False,
}

CLAIMS_NOT_MADE = (
    "remote_control",
    "remote_management",
    "deployment",
    "runtime_activation",
    "agent_activation",
    "tool_execution",
    "model_execution",
    "container_execution",
    "network_authority",
    "truth_promotion",
    "raw_body_ingestion",
    "client_data_access",
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


def _empty_read_model(*, db_path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": "not_available_no_report_bridge_run",
        "source_ledger_path": _display_path(db_path),
        "source_ledger_namespace": "report_bridge_*",
        "latest_report_bridge_run_id": None,
        "package_count": 0,
        "accepted_package_count": 0,
        "rejected_package_count": 0,
        "node_count": 0,
        "project_count": 0,
        "latest_package_summary": None,
        "latest_rejection_summary": None,
        "package_kinds_represented": {},
        "node_kinds_represented": {},
        "projects_represented": [],
        "clients_represented": [],
        "report_bridge_inbox_path": DEFAULT_REPORT_BRIDGE_INBOX.as_posix(),
        "archive_paths_represented": [],
        "rejected_package_paths_represented": [],
        "authority_flags": dict(EXTENDED_NO_AUTHORITY_FLAGS),
        **EXTENDED_NO_AUTHORITY_FLAGS,
        "sanitized_package_intake_only": True,
        "remote_control": False,
        "deployment": False,
        "accepted_packages_have_raw_bodies": False,
        "accepted_packages_have_client_data": False,
        "package_arrival_is_authority": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def _latest_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
SELECT *
FROM report_bridge_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()


def _package_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT package_id, package_kind, node_id, node_kind, owner_scope, project_id,
       client_id, source_root_id, package_path, generated_at, imported_at,
       file_count, imported_file_count, rejected_file_count, status,
       raw_body_included, client_data_included, runtime_authority,
       deployment_authority, remote_management_allowed, agent_activation_allowed,
       tool_execution_allowed, model_execution_allowed, container_execution_allowed,
       network_authority, truth_promotion_allowed
FROM report_bridge_packages
ORDER BY imported_at DESC, generated_at DESC, package_id DESC
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _node_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT node_id, node_kind, owner_scope, source_root_id, project_id, client_id,
       package_count, status, last_seen_at
FROM report_bridge_nodes
ORDER BY node_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _project_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT project_id, client_id, owner_scope, package_count, status, last_seen_at
FROM report_bridge_projects
ORDER BY project_id, client_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _rejection_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT run_id, package_id, package_path, rejection_type, rejection_reason,
       relative_path, created_at
FROM report_bridge_rejections
ORDER BY created_at DESC, rejection_id DESC
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _safe_package_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "package_id": row["package_id"],
        "package_kind": row["package_kind"],
        "node_id": row["node_id"],
        "node_kind": row["node_kind"],
        "owner_scope": row["owner_scope"],
        "project_id": row["project_id"],
        "client_id": row["client_id"],
        "source_root_id": row["source_root_id"],
        "generated_at": row["generated_at"],
        "imported_at": row["imported_at"],
        "file_count": int(row["file_count"]),
        "imported_file_count": int(row["imported_file_count"]),
        "status": row["status"],
        "raw_body_included": bool(row["raw_body_included"]),
        "client_data_included": bool(row["client_data_included"]),
        "authority_flags": {
            "runtime_authority": bool(row["runtime_authority"]),
            "deployment_authority": bool(row["deployment_authority"]),
            "remote_management_allowed": bool(row["remote_management_allowed"]),
            "agent_activation_allowed": bool(row["agent_activation_allowed"]),
            "tool_execution_allowed": bool(row["tool_execution_allowed"]),
            "model_execution_allowed": bool(row["model_execution_allowed"]),
            "container_execution_allowed": bool(row["container_execution_allowed"]),
            "network_authority": bool(row["network_authority"]),
            "truth_promotion_allowed": bool(row["truth_promotion_allowed"]),
            "client_data_access": False,
        },
    }


def _safe_rejection_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "package_id": row["package_id"],
        "package_path": row["package_path"],
        "rejection_type": row["rejection_type"],
        "rejection_reason": row["rejection_reason"],
        "relative_path": row["relative_path"],
        "created_at": row["created_at"],
    }


def _unique_nonempty(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row[key]) for row in rows if row.get(key)})


def build_report_bridge_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    path = _ledger_path(db_path)
    conn = _connect_readonly(path)
    if conn is None:
        return _empty_read_model(db_path=path)
    try:
        try:
            latest_run = _latest_run(conn)
            packages = _package_rows(conn)
            nodes = _node_rows(conn)
            projects = _project_rows(conn)
            rejections = _rejection_rows(conn)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return _empty_read_model(db_path=path)
            raise

        accepted_packages = [row for row in packages if row["status"] == "imported"]
        raw_body_accepted = any(bool(row["raw_body_included"]) for row in accepted_packages)
        client_data_accepted = any(bool(row["client_data_included"]) for row in accepted_packages)
        authority_claims = {
            flag: any(bool(row[flag]) for row in accepted_packages)
            for flag in NO_AUTHORITY_FLAGS
        }
        generated_at = (
            latest_run["completed_at"] or latest_run["created_at"]
            if latest_run is not None
            else "not_available_no_report_bridge_run"
        )
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "mode": MODE,
            "generated_at": generated_at,
            "generated_at_basis": "latest_report_bridge_run_completed_at",
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "report_bridge_*",
            "latest_report_bridge_run_id": latest_run["run_id"] if latest_run else None,
            "package_count": len(packages),
            "accepted_package_count": len(accepted_packages),
            "rejected_package_count": len(rejections),
            "node_count": len(nodes),
            "project_count": len(projects),
            "latest_package_summary": _safe_package_summary(accepted_packages[0] if accepted_packages else None),
            "latest_rejection_summary": _safe_rejection_summary(rejections[0] if rejections else None),
            "package_kinds_represented": dict(
                sorted(Counter(row["package_kind"] for row in packages).items())
            ),
            "node_kinds_represented": dict(
                sorted(Counter(row["node_kind"] for row in nodes).items())
            ),
            "projects_represented": _unique_nonempty(projects, "project_id"),
            "clients_represented": _unique_nonempty(projects, "client_id"),
            "nodes_represented": [
                {
                    "node_id": row["node_id"],
                    "node_kind": row["node_kind"],
                    "owner_scope": row["owner_scope"],
                    "source_root_id": row["source_root_id"],
                    "project_id": row["project_id"],
                    "client_id": row["client_id"],
                    "package_count": int(row["package_count"]),
                    "status": row["status"],
                }
                for row in nodes
            ],
            "report_bridge_inbox_path": DEFAULT_REPORT_BRIDGE_INBOX.as_posix(),
            "archive_paths_represented": [],
            "rejected_package_paths_represented": _unique_nonempty(rejections, "package_path"),
            "authority_flags": dict(EXTENDED_NO_AUTHORITY_FLAGS),
            **EXTENDED_NO_AUTHORITY_FLAGS,
            "accepted_package_authority_claims_seen": authority_claims,
            "sanitized_package_intake_only": True,
            "remote_control": False,
            "deployment": False,
            "accepted_packages_have_raw_bodies": raw_body_accepted,
            "accepted_packages_have_client_data": client_data_accepted,
            "accepted_packages_are_authority": False,
            "package_arrival_is_authority": False,
            "packages_with_raw_bodies_or_client_data_are_not_accepted_authority": True,
            "claims_not_made": list(CLAIMS_NOT_MADE),
            "boundary": {
                "report_bridge_is_sanitized_package_intake": True,
                "report_bridge_is_remote_control": False,
                "report_bridge_is_deployment": False,
                "raw_bodies_accepted_as_authority": False,
                "client_data_accepted_as_authority": False,
                "truth_promoted": False,
            },
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _list_line(items: list[str]) -> str:
    if not items:
        return "none"
    return ", ".join(f"`{item}`" for item in items)


def format_operator_report_bridge(read_model: dict[str, Any]) -> str:
    latest = read_model.get("latest_package_summary")
    rejection = read_model.get("latest_rejection_summary")
    lines = [
        "# Report Bridge Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `report_bridge_*` SQLite rows.",
        "- It exposes sanitized node/client/project report-package posture without querying raw SQLite directly.",
        "",
        "What this is not:",
        "- Report Bridge is sanitized package intake, not remote control or deployment.",
        "- It is not runtime activation, agent activation, tool execution, model execution, network access, or truth promotion.",
        "",
        "Summary:",
        f"- Latest run: `{read_model['latest_report_bridge_run_id']}`.",
        f"- Packages: {read_model['package_count']} total, {read_model['accepted_package_count']} accepted, {read_model['rejected_package_count']} rejected.",
        f"- Nodes seen: {read_model['node_count']}.",
        f"- Projects seen: {read_model['project_count']}.",
        f"- Package kinds: {_counts_line(read_model['package_kinds_represented'])}.",
        f"- Node kinds: {_counts_line(read_model['node_kinds_represented'])}.",
        f"- Projects: {_list_line(read_model['projects_represented'])}.",
        f"- Clients: {_list_line(read_model['clients_represented'])}.",
        f"- Inbox: `{read_model['report_bridge_inbox_path']}`.",
        "",
        "Latest imported package:",
    ]
    if latest:
        lines.extend(
            [
                f"- Package: `{latest['package_id']}`.",
                f"- Node: `{latest['node_id']}` ({latest['node_kind']}).",
                f"- Project/client: `{latest['project_id'] or 'none'}` / `{latest['client_id'] or 'none'}`.",
                f"- Files imported: {latest['imported_file_count']}/{latest['file_count']}.",
                f"- Raw body included: `{str(latest['raw_body_included']).lower()}`.",
                f"- Client data included: `{str(latest['client_data_included']).lower()}`.",
            ]
        )
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("Latest rejection:")
    if rejection:
        lines.extend(
            [
                f"- Type: `{rejection['rejection_type']}`.",
                f"- Package path: `{rejection['package_path']}`.",
                f"- Reason: {rejection['rejection_reason']}",
            ]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- runtime_authority=false; deployment_authority=false; remote_management_allowed=false.",
            "- agent_activation_allowed=false; tool_execution_allowed=false; model_execution_allowed=false.",
            "- container_execution_allowed=false; network_authority=false; truth_promotion_allowed=false.",
            "- client_data_access=false.",
            "",
            "Next safe move:",
            "- Use this read-model to inspect package posture; any real client data, deployment, remote management, runtime, agent, tool, model, network, or truth-promotion work needs a separate scoped lane.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_report_bridge_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_report_bridge_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_report_bridge(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "export_root": _display_path(root),
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "latest_report_bridge_run_id": read_model["latest_report_bridge_run_id"],
        "package_count": read_model["package_count"],
        "accepted_package_count": read_model["accepted_package_count"],
        "rejected_package_count": read_model["rejected_package_count"],
        "node_count": read_model["node_count"],
        "project_count": read_model["project_count"],
        "metadata_only": True,
        **EXTENDED_NO_AUTHORITY_FLAGS,
    }


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Report Bridge Read-Model Export v0",
            "",
            "Evidence:",
            f"- Exported `{summary['json_path']}` and `{summary['operator_path']}`.",
            f"- Latest run: `{summary['latest_report_bridge_run_id']}`.",
            f"- Packages: {summary['package_count']} total, {summary['accepted_package_count']} accepted, {summary['rejected_package_count']} rejected.",
            f"- Nodes: {summary['node_count']}; projects: {summary['project_count']}.",
            "",
            "Boundary:",
            "- Export reads existing `report_bridge_*` SQLite rows only and writes generated read-model files.",
            "- Report Bridge remains sanitized package intake, not remote control, deployment, runtime, tool execution, network access, or truth promotion.",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Report Bridge v0 generated read-model files.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
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
    summary = export_report_bridge_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_operator_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
