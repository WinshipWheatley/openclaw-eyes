#!/usr/bin/env python3
"""Export deterministic read-model artifacts to standardized local paths."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.build_artifact_registry import (
        build_artifact_registry,
        format_operator_artifact_registry,
        stable_json,
    )
    from scripts.build_helm_state import build_helm_state, format_operator_helm_state
    from scripts.build_source_inventory import build_inventory, format_operator_inventory
    from scripts.build_world_status import build_world_status, format_operator_world_status
    from scripts.build_world_domain_registry import (
        build_world_domain_registry,
        format_operator_world_domain_registry,
    )
    from scripts.check_runtime_activation_gate import (
        build_activation_gate_report,
        format_operator_activation_gate,
    )
except ImportError:
    from build_artifact_registry import (
        build_artifact_registry,
        format_operator_artifact_registry,
        stable_json,
    )
    from build_helm_state import build_helm_state, format_operator_helm_state
    from build_source_inventory import build_inventory, format_operator_inventory
    from build_world_status import build_world_status, format_operator_world_status
    from build_world_domain_registry import (
        build_world_domain_registry,
        format_operator_world_domain_registry,
    )
    from check_runtime_activation_gate import (
        build_activation_gate_report,
        format_operator_activation_gate,
    )


ROOT = Path(__file__).resolve().parents[1]
EXPORT_VERSION = "read_model_exports_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
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

EXPECTED_EXPORT_PATHS = (
    "source_inventory.json",
    "source_inventory.operator.txt",
    "helm_state.json",
    "helm_state.operator.txt",
    "world_domain_registry.json",
    "world_domain_registry.operator.txt",
    "world_status.json",
    "world_status.operator.txt",
    "artifact_registry.json",
    "artifact_registry.operator.txt",
    "runtime_activation_gate.json",
    "runtime_activation_gate.operator.txt",
    "evidence_freshness.json",
    "evidence_freshness.operator.txt",
    "generated_current_state.md",
    "generated_next_actions.md",
)

SELF_REFERENTIAL_EXPORT_IDS = {
    "evidence_freshness",
    "evidence_freshness_operator",
}


@dataclass(frozen=True)
class ExportSpec:
    artifact_id: str
    relative_path: str
    output_format: str
    producer: str
    safe_for_mac_app: bool
    safe_for_codex_context: bool
    safe_for_nohup_workers: bool
    safe_for_agent_context: bool
    render: Callable[[], str]


def _json_text(payload: dict[str, Any]) -> str:
    return stable_json(payload)


def _read_generated_markdown(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _source_inventory() -> dict[str, Any]:
    return build_inventory()


def _helm_state() -> dict[str, Any]:
    return build_helm_state()


def _world_domain_registry() -> dict[str, Any]:
    return build_world_domain_registry()


def _world_status() -> dict[str, Any]:
    return build_world_status()


def _artifact_registry() -> dict[str, Any]:
    return build_artifact_registry()


def _activation_gate() -> dict[str, Any]:
    return build_activation_gate_report()


def _evidence_freshness() -> dict[str, Any]:
    try:
        from scripts.build_evidence_freshness import build_evidence_freshness
    except ImportError:
        from build_evidence_freshness import build_evidence_freshness

    return build_evidence_freshness(
        git_head="omitted_for_standardized_export_stability",
        git_head_basis="omitted_to_avoid_commit_self_invalidation",
    )


def _format_operator_evidence_freshness(read_model: dict[str, Any]) -> str:
    try:
        from scripts.build_evidence_freshness import format_operator_evidence_freshness
    except ImportError:
        from build_evidence_freshness import format_operator_evidence_freshness

    return format_operator_evidence_freshness(read_model)


def _export_specs() -> tuple[ExportSpec, ...]:
    return (
        ExportSpec(
            artifact_id="source_inventory",
            relative_path="source_inventory.json",
            output_format="json",
            producer="scripts/build_source_inventory.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_source_inventory()),
        ),
        ExportSpec(
            artifact_id="source_inventory_operator",
            relative_path="source_inventory.operator.txt",
            output_format="operator_text",
            producer="scripts/build_source_inventory.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_inventory(_source_inventory()) + "\n",
        ),
        ExportSpec(
            artifact_id="helm_state",
            relative_path="helm_state.json",
            output_format="json",
            producer="scripts/build_helm_state.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_helm_state()),
        ),
        ExportSpec(
            artifact_id="helm_state_operator",
            relative_path="helm_state.operator.txt",
            output_format="operator_text",
            producer="scripts/build_helm_state.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_helm_state(_helm_state()) + "\n",
        ),
        ExportSpec(
            artifact_id="world_domain_registry",
            relative_path="world_domain_registry.json",
            output_format="json",
            producer="scripts/build_world_domain_registry.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_world_domain_registry()),
        ),
        ExportSpec(
            artifact_id="world_domain_registry_operator",
            relative_path="world_domain_registry.operator.txt",
            output_format="operator_text",
            producer="scripts/build_world_domain_registry.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_world_domain_registry(_world_domain_registry()) + "\n",
        ),
        ExportSpec(
            artifact_id="world_status",
            relative_path="world_status.json",
            output_format="json",
            producer="scripts/build_world_status.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_world_status()),
        ),
        ExportSpec(
            artifact_id="world_status_operator",
            relative_path="world_status.operator.txt",
            output_format="operator_text",
            producer="scripts/build_world_status.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_world_status(_world_status()) + "\n",
        ),
        ExportSpec(
            artifact_id="artifact_registry",
            relative_path="artifact_registry.json",
            output_format="json",
            producer="scripts/build_artifact_registry.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_artifact_registry()),
        ),
        ExportSpec(
            artifact_id="artifact_registry_operator",
            relative_path="artifact_registry.operator.txt",
            output_format="operator_text",
            producer="scripts/build_artifact_registry.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_artifact_registry(_artifact_registry()) + "\n",
        ),
        ExportSpec(
            artifact_id="runtime_activation_gate",
            relative_path="runtime_activation_gate.json",
            output_format="json",
            producer="scripts/check_runtime_activation_gate.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_activation_gate()),
        ),
        ExportSpec(
            artifact_id="runtime_activation_gate_operator",
            relative_path="runtime_activation_gate.operator.txt",
            output_format="operator_text",
            producer="scripts/check_runtime_activation_gate.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: format_operator_activation_gate(_activation_gate()) + "\n",
        ),
        ExportSpec(
            artifact_id="evidence_freshness",
            relative_path="evidence_freshness.json",
            output_format="json",
            producer="scripts/build_evidence_freshness.py --format json",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _json_text(_evidence_freshness()),
        ),
        ExportSpec(
            artifact_id="evidence_freshness_operator",
            relative_path="evidence_freshness.operator.txt",
            output_format="operator_text",
            producer="scripts/build_evidence_freshness.py --format operator",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _format_operator_evidence_freshness(_evidence_freshness()) + "\n",
        ),
        ExportSpec(
            artifact_id="generated_current_state",
            relative_path="generated_current_state.md",
            output_format="markdown",
            producer="Operator/GENERATED_CURRENT_STATE.md",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _read_generated_markdown("Operator/GENERATED_CURRENT_STATE.md"),
        ),
        ExportSpec(
            artifact_id="generated_next_actions",
            relative_path="generated_next_actions.md",
            output_format="markdown",
            producer="Operator/GENERATED_NEXT_ACTIONS.md",
            safe_for_mac_app=True,
            safe_for_codex_context=True,
            safe_for_nohup_workers=True,
            safe_for_agent_context=True,
            render=lambda: _read_generated_markdown("Operator/GENERATED_NEXT_ACTIONS.md"),
        ),
    )


def _export_record(spec: ExportSpec, path: Path) -> dict[str, Any]:
    return {
        "artifact_id": spec.artifact_id,
        "path": _display_path(path),
        "format": spec.output_format,
        "producer": spec.producer,
        "safe_for_mac_app": spec.safe_for_mac_app,
        "safe_for_codex_context": spec.safe_for_codex_context,
        "safe_for_nohup_workers": spec.safe_for_nohup_workers,
        "safe_for_agent_context": spec.safe_for_agent_context,
        "metadata_only": True,
        "body_ingested": False,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution_authorized": False,
    }


def build_expected_exports(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    exclude_artifact_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    root = _export_root_path(export_root)
    excluded = exclude_artifact_ids or set()
    expected: list[dict[str, Any]] = []
    for spec in _export_specs():
        if spec.artifact_id in excluded:
            continue
        path = root / spec.relative_path
        expected.append(
            {
                "spec": spec,
                "path": path,
                "content": spec.render(),
                "record": _export_record(spec, path),
            }
        )
    return expected


def _base_summary(
    *,
    export_root: Path,
    exports: list[dict[str, Any]],
    check: bool,
    stale_exports: list[str],
) -> dict[str, Any]:
    return {
        "export_version": EXPORT_VERSION,
        "export_root": _display_path(export_root),
        "metadata_only": True,
        "body_ingested": False,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution_authorized": False,
        "broad_scan": False,
        "hard_drive_scan": False,
        "private_data_access": False,
        "check_mode": check,
        "check_status": "stale" if stale_exports else "current",
        "stale_exports": stale_exports,
        "exports": exports,
        "claims_not_made": CLAIMS_NOT_MADE,
    }


def export_read_models(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    check: bool = False,
    exclude_artifact_ids: set[str] | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    excluded = exclude_artifact_ids or set()
    stale_exports: list[str] = []

    if check:
        expected = build_expected_exports(export_root=root, exclude_artifact_ids=excluded)
        for item in expected:
            path = item["path"]
            if not path.is_file() or path.read_text(encoding="utf-8") != item["content"]:
                stale_exports.append(_display_path(path))
    else:
        root.mkdir(parents=True, exist_ok=True)
        for spec in _export_specs():
            if spec.artifact_id in excluded:
                continue
            path = root / spec.relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

        non_self_excluded = excluded | SELF_REFERENTIAL_EXPORT_IDS
        non_self_expected = build_expected_exports(
            export_root=root,
            exclude_artifact_ids=non_self_excluded,
        )
        for item in non_self_expected:
            item["path"].write_text(item["content"], encoding="utf-8")

        expected = build_expected_exports(export_root=root, exclude_artifact_ids=excluded)
        for item in expected:
            item["path"].write_text(item["content"], encoding="utf-8")

    return _base_summary(
        export_root=root,
        exports=[item["record"] for item in expected],
        check=check,
        stale_exports=stale_exports,
    )


def format_operator_export_summary(summary: dict[str, Any]) -> str:
    exports = summary["exports"]
    json_exports = sum(1 for item in exports if item["format"] == "json")
    operator_exports = sum(1 for item in exports if item["format"] == "operator_text")
    markdown_exports = sum(1 for item in exports if item["format"] == "markdown")
    lines = [
        "Read-Model Exports v0",
        "",
        "Evidence:",
        (
            f"- Exported {len(exports)} deterministic read-model artifacts to "
            f"`{summary['export_root']}/`: {json_exports} JSON, "
            f"{operator_exports} operator text, {markdown_exports} Markdown."
        ),
        "- Exported JSON artifacts validate with `python3 -m json.tool`.",
        "- Mac app, Codex-on-Mac, nohup/background workers, and future agent-context consumers can load these paths instead of guessing scripts or /tmp outputs.",
        "",
        "Boundary:",
        "- Exports are deterministic/read-only artifacts from existing producer scripts and generated status files.",
        "- `body_ingested=false`; no extracted source bodies or raw source bodies are exported.",
        "- `runtime_authority=false`; `activation_allowed=false`; `backend_execution_authorized=false`.",
        "- Exporting files does not authorize runtime/app actions, agents, brokers, external tools, networking, customer deployment, SQLite writes, or live health claims.",
        "",
        "Blocked:",
        "- Full body ingest, extraction artifact export, SQLite body storage, broad repo scan, hard-drive scan, private/legal/tax/CPA/AppData/runtime-log access remain blocked.",
        "- Runtime activation, backend execution, agent activation, broker wiring, external tool calls, networking, and customer deployment remain blocked.",
        "- Dynamic world state, strategic gravity scoring, active agent presence, live health, and process liveness are not claimed.",
        "",
        "Next safe move:",
        "- Point Mission Control, Codex-on-Mac, and nohup/background workers at `generated/read_models/` for registered read-model loading.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export deterministic read-model artifacts to generated/read_models."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check exported read models are current without writing.",
    )
    parser.add_argument(
        "--export-root",
        default=DEFAULT_EXPORT_ROOT.as_posix(),
        help="Export root. Defaults to generated/read_models.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_read_models(export_root=args.export_root, check=args.check)

    if args.check:
        if summary["check_status"] == "current":
            print("OK: read-model exports are current.")
            return 0
        print("STALE: read-model exports differ from expected content.")
        for path in summary["stale_exports"]:
            print(f"- {path}")
        return 1

    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_operator_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
