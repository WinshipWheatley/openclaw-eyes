#!/usr/bin/env python3
"""Export Project Capsule v0 rows as bounded generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from project_capsule import (
    NO_AUTHORITY_FLAGS,
    build_project_capsule_report,
    get_project_capsule,
    stable_json,
)


READ_MODEL_VERSION = "project_capsule_read_model_v0"
MODE = "synthetic_project_capsule_metadata_only"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "project_capsules.json"
OPERATOR_EXPORT_NAME = "project_capsules_OPERATOR.md"

CLAIMS_NOT_MADE = (
    "real_client_data_access",
    "deployment_authority",
    "runtime_activation",
    "agent_activation",
    "tool_execution",
    "network_authority",
    "client_repo_creation",
    "credential_creation",
    "truth_promotion",
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


def _safe_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": capsule["project_id"],
        "client_id": capsule["client_id"],
        "project_name": capsule["project_name"],
        "project_goal": capsule["project_goal"],
        "target_user_company": capsule["target_user_company"],
        "owner_scope": capsule["owner_scope"],
        "status": capsule["status"],
        "approval_status": capsule["approval_status"],
        "runtime_authority": bool(capsule["runtime_authority"]),
        "deployment_authority": bool(capsule["deployment_authority"]),
        "client_data_access": bool(capsule["client_data_access"]),
        "agent_activation_allowed": bool(capsule["agent_activation_allowed"]),
        "tool_execution_allowed": bool(capsule["tool_execution_allowed"]),
        "network_authority": bool(capsule["network_authority"]),
        "synthetic_demo": bool(capsule["synthetic_demo"]),
        "deployment_posture": capsule["deployment_posture"],
        "support_management_posture": capsule["support_management_posture"],
        "next_safe_move": capsule["next_safe_move"],
        "selected_worlds": [item["world_id"] for item in capsule["worlds"]],
        "selected_tool_candidates": [
            {
                "tool_id": item["tool_id"],
                "tool_role": item["tool_role"],
                "approval_status": item["approval_status"],
                "integration_status": item["integration_status"],
                "execution_authority": bool(item["execution_authority"]),
            }
            for item in capsule["tools"]
        ],
        "boundaries": capsule["boundaries"],
        "receipt_requirements": capsule["receipt_requirements"],
        "read_model_requirements": capsule["read_model_requirements"],
        "next_moves": capsule["next_moves"],
        "selected_modules": capsule["modules"],
    }


def _empty_read_model(*, db_path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": "not_available_no_project_capsule_run",
        "source_ledger_path": _display_path(db_path),
        "source_ledger_namespace": "project_capsule_*",
        "latest_project_capsule_run_id": None,
        "capsule_count": 0,
        "demo_capsule": None,
        "capsules": [],
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "approval_status": "not_approved",
        "real_client_data_present": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
        "metadata_only": True,
    }


def build_project_capsule_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = _ledger_path(db_path)
    report = build_project_capsule_report(db_path=path, run_id=run_id)
    if report.get("status") == "no_runs":
        return _empty_read_model(db_path=path)

    capsules = []
    for item in report.get("capsules") or []:
        capsule = get_project_capsule(db_path=path, project_id=item["project_id"])
        if capsule is not None:
            capsules.append(_safe_capsule(capsule))

    demo = next((item for item in capsules if item["project_id"] == "demo_project_capsule_v0"), None)
    run = report["run"]
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "generated_at": run["completed_at"] or run["created_at"],
        "generated_at_basis": "project_capsule_run_completed_at",
        "source_ledger_path": _display_path(path),
        "source_ledger_namespace": "project_capsule_*",
        "latest_project_capsule_run_id": report["run_id"],
        "capsule_count": len(capsules),
        "counts": report["counts"],
        "demo_capsule": demo,
        "capsules": capsules,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "approval_status": "not_approved",
        "real_client_data_present": False,
        "client_data_classes_are_synthetic_or_metadata_only": True,
        "project_capsules_are_truth_promotion": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
        "metadata_only": True,
    }


def _list_line(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"


def format_operator_project_capsules(read_model: dict[str, Any]) -> str:
    demo = read_model.get("demo_capsule")
    lines = [
        "# Project Capsule Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `project_capsule_*` SQLite planning rows.",
        "- It exposes synthetic project-capsule posture without querying raw SQLite directly.",
        "",
        "What this is not:",
        "- It is not deployment, runtime activation, client-data access, tool execution, agent activation, or truth promotion.",
        "",
        "Summary:",
        f"- Latest run: `{read_model['latest_project_capsule_run_id']}`.",
        f"- Capsule count: {read_model['capsule_count']}.",
    ]
    if demo:
        lines.extend(
            [
                f"- Demo capsule: `{demo['project_id']}` - {demo['project_name']}.",
                f"- Worlds: {_list_line(demo['selected_worlds'])}.",
                f"- Tool candidates: {_list_line([item['tool_id'] for item in demo['selected_tool_candidates']])}.",
                f"- Next safe move: {demo['next_safe_move']}",
            ]
        )
    else:
        lines.append("- Demo capsule: none.")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- runtime_authority=false; deployment_authority=false; client_data_access=false.",
            "- agent_activation_allowed=false; tool_execution_allowed=false; network_authority=false.",
            "- approval_status=not_approved.",
            "",
            "Next safe move:",
            "- Use this read-model for inspection and prompt grounding only; real-client, deployment, runtime, tool, or agent work needs a separate scoped lane.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_project_capsule_read_model(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_project_capsule_read_model(db_path=db_path, run_id=run_id)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_project_capsules(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "latest_project_capsule_run_id": read_model["latest_project_capsule_run_id"],
        "capsule_count": read_model["capsule_count"],
        "metadata_only": True,
        **NO_AUTHORITY_FLAGS,
    }


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Project Capsule Read-Model Export v0",
            "",
            "Evidence:",
            f"- Exported `{summary['json_path']}` and `{summary['operator_path']}`.",
            f"- Latest run: `{summary['latest_project_capsule_run_id']}`.",
            f"- Capsule count: {summary['capsule_count']}.",
            "",
            "Boundary:",
            "- Export reads `project_capsule_*` SQLite rows only and writes generated read-model files.",
            "- No runtime, deployment, client-data, tool, network, or agent authority is introduced.",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Project Capsule v0 generated read-model files.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Project capsule run id. Defaults to latest.")
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
    summary = export_project_capsule_read_model(
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
