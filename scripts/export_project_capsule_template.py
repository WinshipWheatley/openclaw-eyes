#!/usr/bin/env python3
"""Export a synthetic Project Capsule v0 starter folder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from project_capsule import DEMO_PROJECT_ID, get_project_capsule, stable_json


TEMPLATE_VERSION = "project_capsule_template_v0"
DEFAULT_OUTPUT_ROOT = Path("generated/project_capsules")
TEMPLATE_FILES = (
    "README.md",
    "CAPSULE_CONTRACT.md",
    "BOUNDARIES.md",
    "RECEIPTS_PLAN.md",
    "READ_MODELS_PLAN.md",
    "TOOL_POLICY.md",
    "DEPLOYMENT_NOT_AUTHORIZED.md",
    "SUPPORT_POSTURE.md",
    "NEXT_SAFE_MOVE.md",
    "capsule.json",
)


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _output_root_path(output_root: str | Path) -> Path:
    path = Path(output_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def _capsule_payload(capsule: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_version": TEMPLATE_VERSION,
        "synthetic_demo_only": True,
        "project_id": capsule["project_id"],
        "client_id": capsule["client_id"],
        "project_name": capsule["project_name"],
        "project_goal": capsule["project_goal"],
        "target_user_company": capsule["target_user_company"],
        "selected_worlds": [item["world_id"] for item in capsule["worlds"]],
        "selected_tool_candidates": [item["tool_id"] for item in capsule["tools"]],
        "boundaries": capsule["boundaries"],
        "receipt_requirements": capsule["receipt_requirements"],
        "read_model_requirements": capsule["read_model_requirements"],
        "next_moves": capsule["next_moves"],
        "selected_modules": capsule["modules"],
        "authority_flags": {
            "runtime_authority": False,
            "deployment_authority": False,
            "client_data_access": False,
            "agent_activation_allowed": False,
            "tool_execution_allowed": False,
            "network_authority": False,
        },
        "approval_status": capsule["approval_status"],
    }


def _file_contents(capsule: dict[str, Any]) -> dict[str, str]:
    worlds = [item["world_id"] for item in capsule["worlds"]]
    tools = [f"{item['tool_id']} ({item['tool_role']})" for item in capsule["tools"]]
    allowed = [
        f"{item['data_class']}: {item['notes']}"
        for item in capsule["boundaries"]
        if item["boundary_kind"] == "allowed"
    ]
    forbidden = [
        f"{item['data_class']}: {item['notes']}"
        for item in capsule["boundaries"]
        if item["boundary_kind"] == "forbidden"
    ]
    receipts = [
        f"{item['receipt_type']}: {item['notes']}"
        for item in capsule["receipt_requirements"]
    ]
    read_models = [
        f"{item['read_model_name']}: {item['purpose']}"
        for item in capsule["read_model_requirements"]
    ]
    next_moves = [
        f"{item['sequence']}. {item['move_label']}: {item['move_text']}"
        for item in capsule["next_moves"]
    ]
    payload = _capsule_payload(capsule)
    return {
        "README.md": "\n".join(
            [
                f"# {capsule['project_name']}",
                "",
                "Synthetic demo Project Capsule v0 starter.",
                "",
                "This folder is generated planning material only. It is not a real client repository, deployment package, runtime workspace, or support workspace.",
                "",
                f"Project id: `{capsule['project_id']}`",
                f"Client id: `{capsule['client_id']}` (synthetic)",
                f"Status: `{capsule['status']}`",
                f"Approval: `{capsule['approval_status']}`",
                "",
                "Authority:",
                "- runtime_authority=false",
                "- deployment_authority=false",
                "- client_data_access=false",
                "- tool_execution_allowed=false",
                "- agent_activation_allowed=false",
            ]
        )
        + "\n",
        "CAPSULE_CONTRACT.md": "\n".join(
            [
                "# Capsule Contract",
                "",
                f"Goal: {capsule['project_goal']}",
                "",
                "Selected worlds:",
                _bullet(worlds),
                "",
                "This contract is a planning artifact. It does not promote evidence to truth.",
            ]
        )
        + "\n",
        "BOUNDARIES.md": "\n".join(
            [
                "# Boundaries",
                "",
                "Allowed data classes:",
                _bullet(allowed),
                "",
                "Forbidden data classes:",
                _bullet(forbidden),
                "",
                "No real client data, credentials, private/legal/tax/finance material, runtime logs, or production customer data belongs in this synthetic capsule.",
            ]
        )
        + "\n",
        "RECEIPTS_PLAN.md": "\n".join(
            [
                "# Receipts Plan",
                "",
                "Required receipt types:",
                _bullet(receipts),
                "",
                "Future deployment, client-data, runtime, or support work requires explicit approval receipts before any action.",
            ]
        )
        + "\n",
        "READ_MODELS_PLAN.md": "\n".join(
            [
                "# Read-Models Plan",
                "",
                "Required read-model surfaces:",
                _bullet(read_models),
                "",
                "Read-models are inspection surfaces and evidence context, not truth by default.",
            ]
        )
        + "\n",
        "TOOL_POLICY.md": "\n".join(
            [
                "# Tool Policy",
                "",
                "Candidate tools:",
                _bullet(tools),
                "",
                "Candidate tools are not approved, integrated, installed, invoked, or authorized for execution by this template.",
            ]
        )
        + "\n",
        "DEPLOYMENT_NOT_AUTHORIZED.md": "\n".join(
            [
                "# Deployment Not Authorized",
                "",
                "Deployment authority is false.",
                "",
                "This template must not be used to deploy, create infrastructure, create credentials, start services, run containers, run local models, contact networks, or create a real client repository.",
                "",
                "Future deployment requires an explicit lane, rollback plan, dry-run proof, receipts, and operator approval.",
            ]
        )
        + "\n",
        "SUPPORT_POSTURE.md": "\n".join(
            [
                "# Support Posture",
                "",
                f"Support posture: `{capsule['support_management_posture']}`.",
                "",
                "Support and management are planning-only until a later approved lane defines responsibilities, receipts, monitoring, rollback, and data boundaries.",
            ]
        )
        + "\n",
        "NEXT_SAFE_MOVE.md": "\n".join(
            [
                "# Next Safe Move",
                "",
                f"{capsule['next_safe_move']}",
                "",
                "Open moves:",
                _bullet(next_moves),
            ]
        )
        + "\n",
        "capsule.json": stable_json(payload),
    }


def export_project_capsule_template(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    project_id: str = DEMO_PROJECT_ID,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    capsule = get_project_capsule(db_path=db_path, project_id=project_id)
    if capsule is None:
        raise ValueError(f"project capsule not found: {project_id}")
    if not capsule["synthetic_demo"]:
        raise ValueError("Project Capsule Template v0 only exports synthetic demo capsules")

    root = _output_root_path(output_root) / project_id
    root.mkdir(parents=True, exist_ok=True)
    contents = _file_contents(capsule)
    for name in TEMPLATE_FILES:
        (root / name).write_text(contents[name], encoding="utf-8")
    return {
        "template_version": TEMPLATE_VERSION,
        "project_id": project_id,
        "output_path": _display_path(root),
        "file_count": len(TEMPLATE_FILES),
        "files": [_display_path(root / name) for name in TEMPLATE_FILES],
        "synthetic_demo_only": True,
        "runtime_authority": False,
        "deployment_authority": False,
        "client_data_access": False,
        "tool_execution_allowed": False,
        "agent_activation_allowed": False,
    }


def format_operator_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Project Capsule Template Export v0",
        "",
        "Evidence:",
        f"- Exported synthetic template for `{summary['project_id']}` to `{summary['output_path']}`.",
        f"- Files: {summary['file_count']}.",
        "",
        "Boundary:",
        "- Synthetic/demo only; no real client repo, deployment, runtime, client data, tool execution, or agent activation.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a synthetic Project Capsule v0 template folder.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--project-id", default=DEMO_PROJECT_ID, help="Project capsule id.")
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT.as_posix(),
        help="Output root. Defaults to generated/project_capsules.",
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
    summary = export_project_capsule_template(
        db_path=args.db,
        project_id=args.project_id,
        output_root=args.output_root,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_operator_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
