#!/usr/bin/env python3
"""Export Tool Intake Registry v0 as bounded generated read-model files."""

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
from tool_intake import stable_json


READ_MODEL_VERSION = "tool_intake_read_model_v0"
MODE = "candidate_policy_metadata_only"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "tool_intake.json"
OPERATOR_EXPORT_NAME = "tool_intake_OPERATOR.md"

CLAIMS_NOT_MADE = [
    "tool_install",
    "tool_execution",
    "tool_approval",
    "tool_integration",
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
    "official_url_claim",
    "license_claim",
    "latest_version_claim",
]

NO_AUTHORITY_FLAGS = {
    "tool_install_allowed": False,
    "tool_execution_allowed": False,
    "integration_authority": False,
    "approval_authority": False,
    "runtime_authority": False,
    "network_authority": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "remote_access_allowed": False,
}


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
FROM tool_intake_runs
ORDER BY completed_at DESC, started_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _counts(conn: sqlite3.Connection, field: str) -> dict[str, int]:
    allowed_fields = {"category", "candidate_status", "install_status", "risk_level"}
    if field not in allowed_fields:
        raise ValueError(f"unsupported count field: {field}")
    rows = conn.execute(
        f"""
SELECT {field} AS label, COUNT(*) AS count
FROM tool_candidates
GROUP BY {field}
ORDER BY {field}
""".strip()
    ).fetchall()
    return {row["label"]: row["count"] for row in rows}


def _safe_candidate(row: sqlite3.Row) -> dict[str, Any]:
    linked = bool(row["inventory_observation_id"])
    detected: bool | None = None
    if row["detected"] is not None:
        detected = bool(row["detected"])
    return {
        "tool_id": row["tool_id"],
        "name": row["name"],
        "category": row["category"],
        "candidate_status": row["candidate_status"],
        "install_status": row["install_status"],
        "approval_status": row["approval_status"],
        "integration_status": row["integration_status"],
        "architecture_fit": row["architecture_fit"],
        "risk_level": row["risk_level"],
        "local_first_fit": row["local_first_fit"],
        "client_capsule_fit": row["client_capsule_fit"],
        "evidence_fit": row["evidence_fit"],
        "source_basis": row["source_basis"],
        "requires_operator_review": bool(row["requires_operator_review"]),
        "inventory_status": {
            "linked": linked,
            "detected": detected,
            "inventory_run_id": row["inventory_run_id"],
            "install_status_at_link": row["install_status_at_link"],
        },
    }


def _candidate_rows(
    conn: sqlite3.Connection,
    *,
    where: str = "1=1",
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT c.tool_id, c.name, c.category, c.candidate_status, c.install_status,
       c.approval_status, c.integration_status, c.architecture_fit,
       c.risk_level, c.local_first_fit, c.client_capsule_fit, c.evidence_fit,
       c.source_basis, c.requires_operator_review, c.inventory_observation_id,
       c.inventory_run_id, c.install_status AS install_status_at_link, o.detected
FROM tool_candidates c
LEFT JOIN tool_observations o ON o.observation_id = c.inventory_observation_id
WHERE {where}
ORDER BY
  CASE c.architecture_fit WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
  CASE c.risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
  c.category,
  c.tool_id
""".strip(),
        params,
    ).fetchall()
    return [_safe_candidate(row) for row in rows]


def _empty_read_model(*, db_path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": "not_available_no_tool_intake_run",
        "source_ledger_path": _display_path(db_path),
        "source_ledger_namespace": "tool_intake_*",
        "latest_tool_intake_run_id": None,
        "candidate_count": 0,
        "inventory_linked_candidate_count": 0,
        "installed_candidate_count": 0,
        "counts_by_category": {},
        "counts_by_candidate_status": {},
        "counts_by_risk_level": {},
        "candidates": [],
        "high_fit_candidates": [],
        "high_risk_candidates": [],
        "sandbox_later_candidates": [],
        "client_capsule_candidates": [],
        "installed_candidates": [],
        "not_detected_candidates": [],
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "claims_not_made": list(CLAIMS_NOT_MADE),
        "metadata_only": True,
        "official_urls_guessed": False,
        "licenses_guessed": False,
        "latest_versions_guessed": False,
    }


def build_tool_intake_read_model(
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
            "SELECT * FROM tool_intake_runs WHERE run_id = ?", (resolved_run_id,)
        ).fetchone()
        if not run:
            return _empty_read_model(db_path=path)

        candidates = _candidate_rows(conn)
        installed_candidates = _candidate_rows(conn, where="c.install_status = 'observed_installed'")
        high_fit_candidates = _candidate_rows(conn, where="c.architecture_fit = 'high'")
        high_risk_candidates = _candidate_rows(conn, where="c.risk_level = 'high'")
        sandbox_later_candidates = _candidate_rows(
            conn,
            where="c.candidate_status = 'sandbox_later'",
        )
        client_capsule_candidates = _candidate_rows(
            conn,
            where="c.client_capsule_fit IN ('high','medium')",
        )
        not_detected_candidates = _candidate_rows(conn, where="c.install_status = 'not_detected'")

        run_action_flags = {
            "install_action_taken": bool(run["install_action_taken"]),
            "integration_action_taken": bool(run["integration_action_taken"]),
            "runtime_authority": bool(run["runtime_authority"]),
            "network_access_attempted": bool(run["network_access_attempted"]),
            "tool_execution_attempted": bool(run["tool_execution_attempted"]),
        }

        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "mode": MODE,
            "generated_at": run["completed_at"] or run["started_at"],
            "generated_at_basis": "tool_intake_run_completed_at",
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "tool_intake_*",
            "latest_tool_intake_run_id": resolved_run_id,
            "candidate_count": run["candidate_count"],
            "inventory_linked_candidate_count": run["linked_inventory_count"],
            "installed_candidate_count": len(installed_candidates),
            "counts_by_category": _counts(conn, "category"),
            "counts_by_candidate_status": _counts(conn, "candidate_status"),
            "counts_by_risk_level": _counts(conn, "risk_level"),
            "candidates": candidates,
            "high_fit_candidates": high_fit_candidates,
            "high_risk_candidates": high_risk_candidates,
            "sandbox_later_candidates": sandbox_later_candidates,
            "client_capsule_candidates": client_capsule_candidates,
            "installed_candidates": installed_candidates,
            "not_detected_candidates": not_detected_candidates,
            "run_action_flags": run_action_flags,
            "authority_flags": dict(NO_AUTHORITY_FLAGS),
            **NO_AUTHORITY_FLAGS,
            "claims_not_made": list(CLAIMS_NOT_MADE),
            "metadata_only": True,
            "official_urls_guessed": False,
            "licenses_guessed": False,
            "latest_versions_guessed": False,
            "boundary": {
                "candidate_does_not_mean_approved": True,
                "installed_does_not_mean_approved": True,
                "approved_later_does_not_authorize_integration": True,
                "detected_does_not_mean_integrated": True,
            },
        }
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return _empty_read_model(db_path=path)
        raise
    finally:
        conn.close()


def _tool_list(candidates: list[dict[str, Any]], *, limit: int | None = None) -> str:
    items = candidates[:limit] if limit is not None else candidates
    if not items:
        return "none"
    rendered = [
        (
            f"`{item['tool_id']}` ({item['candidate_status']}, "
            f"{item['install_status']}, risk={item['risk_level']})"
        )
        for item in items
    ]
    omitted = max(0, len(candidates) - len(items))
    suffix = f" plus {omitted} more" if omitted else ""
    return ", ".join(rendered) + suffix


def format_operator_tool_intake(read_model: dict[str, Any]) -> str:
    lines = [
        "# Tool Intake Read-Model v0",
        "",
        "What this is:",
        "- A generated policy read-model over `tool_intake_*` SQLite candidate rows.",
        "- It is safe metadata for inspection by operators, future agents, and Mission Control.",
        "",
        "What this is not:",
        "- It is not approval, integration authority, runtime authority, install authority, or execution authority.",
        "- It does not include install commands, official URL guesses, license guesses, latest-version guesses, secrets, or private data.",
        "",
        "Evidence:",
        (
            f"- Latest intake run `{read_model['latest_tool_intake_run_id']}` contains "
            f"{read_model['candidate_count']} candidates, "
            f"{read_model['inventory_linked_candidate_count']} inventory-linked candidates, "
            f"and {read_model['installed_candidate_count']} installed candidates."
        ),
        f"- Installed candidates: {_tool_list(read_model['installed_candidates'])}.",
        f"- High-fit candidates: {_tool_list(read_model['high_fit_candidates'])}.",
        f"- High-risk candidates: {_tool_list(read_model['high_risk_candidates'])}.",
        f"- Sandbox-later candidates: {_tool_list(read_model['sandbox_later_candidates'])}.",
        f"- Client-capsule candidates: {_tool_list(read_model['client_capsule_candidates'], limit=20)}.",
        "",
        "Boundary:",
        "- No candidate is approved.",
        "- No candidate is integrated.",
        "- Docker remains high-risk observed-only metadata; containers are not authorized.",
        "- Ollama remains high-risk observed-only metadata; model execution is not authorized.",
        "",
        "Blocked:",
        "- tool_install_allowed=false; tool_execution_allowed=false.",
        "- approval_authority=false; integration_authority=false; runtime_authority=false.",
        "- network_authority=false; model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false.",
        "",
        "Next safe move:",
        "- Use this read-model for policy inspection only; any future sandbox, install, integration, deployment, model, remote-access, or client-capsule action needs a separate scoped lane and operator approval.",
    ]
    return "\n".join(lines) + "\n"


def export_tool_intake_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_tool_intake_read_model(db_path=db_path, run_id=run_id)

    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_tool_intake(read_model), encoding="utf-8")

    return {
        "export_version": READ_MODEL_VERSION,
        "export_root": _display_path(root),
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "latest_tool_intake_run_id": read_model["latest_tool_intake_run_id"],
        "candidate_count": read_model["candidate_count"],
        "inventory_linked_candidate_count": read_model["inventory_linked_candidate_count"],
        "installed_candidate_count": read_model["installed_candidate_count"],
        "high_fit_candidate_count": len(read_model["high_fit_candidates"]),
        "high_risk_candidate_count": len(read_model["high_risk_candidates"]),
        "sandbox_later_candidate_count": len(read_model["sandbox_later_candidates"]),
        "client_capsule_candidate_count": len(read_model["client_capsule_candidates"]),
        "metadata_only": True,
        **NO_AUTHORITY_FLAGS,
    }


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Tool Intake Read-Model Export v0",
        "",
        "Evidence:",
        f"- Exported `{summary['json_path']}` and `{summary['operator_path']}`.",
        (
            f"- Latest intake run `{summary['latest_tool_intake_run_id']}`: "
            f"candidates={summary['candidate_count']}, "
            f"inventory_linked={summary['inventory_linked_candidate_count']}, "
            f"installed={summary['installed_candidate_count']}, "
            f"high_fit={summary['high_fit_candidate_count']}, "
            f"high_risk={summary['high_risk_candidate_count']}, "
            f"sandbox_later={summary['sandbox_later_candidate_count']}."
        ),
        "",
        "Boundary:",
        "- Export reads existing `tool_intake_*` SQLite rows only and writes generated read-model files.",
        "- Candidate rows remain not approved, not integrated, and non-authorizing.",
        "",
        "Blocked:",
        "- No installs, tool execution, approvals, integrations, runtime activation, network authority, model execution, container execution, or remote access are introduced.",
        "",
        "Next safe move:",
        "- Inspect `generated/read_models/tool_intake.json` or `generated/read_models/tool_intake_OPERATOR.md` before any future bounded candidate policy lane.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Tool Intake Registry v0 rows as generated read-model files."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Tool intake run id. Defaults to latest.")
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
    summary = export_tool_intake_read_model(
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
