#!/usr/bin/env python3
"""Build deterministic freshness posture for generated read-model artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
READ_MODEL_VERSION = "evidence_freshness_v0"
MODE = "deterministic_freshness_read_model"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SELF_EXPORT_ARTIFACT_IDS = {
    "evidence_freshness",
    "evidence_freshness_operator",
}

FALLBACK_EXPECTED_EXPORT_PATHS = (
    "source_inventory.json",
    "source_inventory.operator.txt",
    "helm_state.json",
    "helm_state.operator.txt",
    "world_domain_registry.json",
    "world_domain_registry.operator.txt",
    "artifact_registry.json",
    "artifact_registry.operator.txt",
    "runtime_activation_gate.json",
    "runtime_activation_gate.operator.txt",
    "generated_current_state.md",
    "generated_next_actions.md",
)

EXPORT_ARTIFACT_IDS = {
    "source_inventory.json": "source_inventory",
    "source_inventory.operator.txt": "source_inventory_operator",
    "helm_state.json": "helm_state",
    "helm_state.operator.txt": "helm_state_operator",
    "world_domain_registry.json": "world_domain_registry",
    "world_domain_registry.operator.txt": "world_domain_registry_operator",
    "artifact_registry.json": "artifact_registry",
    "artifact_registry.operator.txt": "artifact_registry_operator",
    "runtime_activation_gate.json": "runtime_activation_gate",
    "runtime_activation_gate.operator.txt": "runtime_activation_gate_operator",
    "generated_current_state.md": "generated_current_state_export",
    "generated_next_actions.md": "generated_next_actions_export",
    "world_status.json": "world_status",
    "world_status.operator.txt": "world_status_operator",
    "evidence_freshness.json": "evidence_freshness",
    "evidence_freshness.operator.txt": "evidence_freshness_operator",
}

CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
    "backend_execution_authorization",
    "agent_activation",
    "active_agent_presence",
    "dynamic_world_state",
    "strategic_gravity_scoring",
    "live_health_claim",
    "process_liveness",
    "broker_connection",
    "networking",
    "external_tool_call",
    "customer_deployment",
    "sqlite_body_storage",
    "sqlite_write",
    "broad_file_scan",
    "hard_drive_scan",
    "private_data_access",
    "full_body_ingest",
    "raw_source_body_export",
]


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _run_generated_status_check(root: Path, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "current": None,
            "status": "not_checked",
            "exit_code": None,
        }

    script_path = root / "scripts" / "generate_operator_status.py"
    if not script_path.is_file():
        return {
            "checked": True,
            "current": False,
            "status": "status_script_missing",
            "exit_code": None,
        }

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--check"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "checked": True,
            "current": False,
            "status": "status_check_error",
            "exit_code": None,
        }

    return {
        "checked": True,
        "current": result.returncode == 0,
        "status": "current" if result.returncode == 0 else "stale_or_missing",
        "exit_code": result.returncode,
    }


def _run_export_check(
    *,
    export_root: Path,
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "current": None,
            "status": "not_checked",
            "stale_exports": [],
        }

    try:
        try:
            from scripts.export_read_models import export_read_models
        except ImportError:
            from export_read_models import export_read_models

        try:
            summary = export_read_models(
                export_root=export_root,
                check=True,
                exclude_artifact_ids=SELF_EXPORT_ARTIFACT_IDS,
            )
        except TypeError:
            summary = export_read_models(export_root=export_root, check=True)
    except Exception:
        return {
            "checked": True,
            "current": False,
            "status": "export_check_error",
            "stale_exports": [],
        }

    stale_exports = list(summary.get("stale_exports", []))
    return {
        "checked": True,
        "current": summary.get("check_status") == "current",
        "status": summary.get("check_status", "unknown"),
        "stale_exports": stale_exports,
    }


def _expected_export_paths() -> tuple[str, ...]:
    try:
        try:
            from scripts.export_read_models import EXPECTED_EXPORT_PATHS
        except ImportError:
            from export_read_models import EXPECTED_EXPORT_PATHS
    except Exception:
        return FALLBACK_EXPECTED_EXPORT_PATHS
    return tuple(EXPECTED_EXPORT_PATHS)


def _export_artifact_id(relative_path: str) -> str:
    if relative_path in EXPORT_ARTIFACT_IDS:
        return EXPORT_ARTIFACT_IDS[relative_path]
    return (
        relative_path.replace("/", "_")
        .replace(".operator.txt", "_operator")
        .replace(".json", "")
        .replace(".md", "_markdown")
        .replace(".", "_")
    )


def _freshness_from_check(
    *,
    exists: bool,
    checked: bool,
    current: bool | None,
    stale: bool,
) -> str:
    if not exists:
        return "missing"
    if not checked:
        return "unknown"
    if current is True:
        return "current"
    if stale:
        return "stale"
    return "current"


def _generated_status_artifacts(
    *,
    root: Path,
    generated_status_check: dict[str, Any],
) -> list[dict[str, Any]]:
    artifacts = []
    for artifact_id, relative_path in (
        ("generated_current_state", "Operator/GENERATED_CURRENT_STATE.md"),
        ("generated_next_actions", "Operator/GENERATED_NEXT_ACTIONS.md"),
    ):
        path = root / relative_path
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": relative_path,
                "exists": path.is_file(),
                "freshness_state": _freshness_from_check(
                    exists=path.is_file(),
                    checked=bool(generated_status_check["checked"]),
                    current=generated_status_check["current"],
                    stale=generated_status_check["current"] is False,
                ),
                "basis": (
                    "generated_status_check"
                    if generated_status_check["checked"]
                    else ("file_exists" if not path.is_file() else "not_checked")
                ),
                "body_ingested": False,
            }
        )
    return artifacts


def _export_artifacts(
    *,
    root: Path,
    export_root: Path,
    expected_export_paths: Iterable[str],
    export_check: dict[str, Any],
) -> list[dict[str, Any]]:
    stale_paths = set(export_check.get("stale_exports", []))
    artifacts = []
    for relative_path in expected_export_paths:
        path = export_root / relative_path
        display_path = _display_path(path, root)
        artifacts.append(
            {
                "artifact_id": _export_artifact_id(relative_path),
                "path": display_path,
                "exists": path.is_file(),
                "freshness_state": _freshness_from_check(
                    exists=path.is_file(),
                    checked=bool(export_check["checked"]),
                    current=export_check["current"],
                    stale=display_path in stale_paths or path.as_posix() in stale_paths,
                ),
                "basis": (
                    "export_check"
                    if export_check["checked"]
                    else ("file_exists" if not path.is_file() else "not_checked")
                ),
                "body_ingested": False,
            }
        )
    return artifacts


def _freshness_counts(artifacts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"current": 0, "missing": 0, "stale": 0, "unknown": 0}
    for artifact in artifacts:
        state = artifact["freshness_state"]
        counts[state] = counts.get(state, 0) + 1
    return counts


def build_evidence_freshness(
    *,
    root: Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_generated_status_check: bool = True,
    run_export_check: bool = True,
    expected_export_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    export_root_path = Path(export_root)
    if not export_root_path.is_absolute():
        export_root_path = root / export_root_path

    generated_status_check = _run_generated_status_check(
        root,
        enabled=run_generated_status_check,
    )
    export_check = _run_export_check(
        export_root=export_root_path,
        enabled=run_export_check,
    )
    expected_paths = tuple(
        expected_export_paths if expected_export_paths is not None else _expected_export_paths()
    )

    artifacts = [
        *_generated_status_artifacts(
            root=root,
            generated_status_check=generated_status_check,
        ),
        *_export_artifacts(
            root=root,
            export_root=export_root_path,
            expected_export_paths=expected_paths,
            export_check=export_check,
        ),
    ]

    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution_authorized": False,
        "body_ingested": False,
        "metadata_only": True,
        "broad_scan": False,
        "hard_drive_scan": False,
        "private_data_access": False,
        "git_head": _git_head(root),
        "generated_status_current": generated_status_check["current"],
        "read_model_exports_current": export_check["current"],
        "generated_status_check": generated_status_check,
        "read_model_exports_check": export_check,
        "artifact_count": len(artifacts),
        "freshness_counts": _freshness_counts(artifacts),
        "artifacts": artifacts,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def _bool_status(value: bool | None) -> str:
    if value is None:
        return "not_checked"
    return "true" if value else "false"


def format_operator_evidence_freshness(read_model: dict[str, Any]) -> str:
    counts = read_model["freshness_counts"]
    lines = [
        "Evidence Freshness Read-Model v0",
        "",
        "Evidence:",
        f"- Git HEAD: `{read_model['git_head']}`.",
        f"- Generated status current: `{_bool_status(read_model['generated_status_current'])}`.",
        f"- Read-model exports current: `{_bool_status(read_model['read_model_exports_current'])}`.",
        (
            f"- Tracked {read_model['artifact_count']} expected artifacts: "
            f"current={counts.get('current', 0)}, stale={counts.get('stale', 0)}, "
            f"missing={counts.get('missing', 0)}, unknown={counts.get('unknown', 0)}."
        ),
        "",
        "Boundary:",
        "- Evidence Freshness v0 uses safe repo-local generated status files and `generated/read_models/` artifacts only.",
        "- It records file existence and producer check outcomes; raw artifact bodies are not emitted or stored.",
        "- `body_ingested=false`; `runtime_authority=false`; `activation_allowed=false`; `backend_execution_authorized=false`.",
        "",
        "Blocked:",
        "- Live runtime health, process liveness, active agents, dynamic world state, strategic gravity scoring, networking, and external tool calls are not checked.",
        "- SQLite writes, body storage, full body ingest, broad repo scans, hard-drive scans, private/legal/tax/CPA/AppData/runtime-log access, and customer deployment remain blocked.",
        "",
        "Next safe move:",
        "- Refresh stale or missing generated artifacts with their explicit producer commands before app consumption; add evidence freshness / strategic gravity inputs before dynamic attention states.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic freshness posture for generated read-model artifacts."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--skip-generated-status-check",
        action="store_true",
        help="Do not run generate_operator_status.py --check.",
    )
    parser.add_argument(
        "--skip-export-check",
        action="store_true",
        help="Do not run export_read_models.py --check.",
    )
    parser.add_argument(
        "--export-root",
        default=DEFAULT_EXPORT_ROOT.as_posix(),
        help="Export root. Defaults to generated/read_models.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    read_model = build_evidence_freshness(
        export_root=args.export_root,
        run_generated_status_check=not args.skip_generated_status_check,
        run_export_check=not args.skip_export_check,
    )

    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_operator_evidence_freshness(read_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
