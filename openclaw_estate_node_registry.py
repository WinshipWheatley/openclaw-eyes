"""OpenClaw estate node registry v0.

This module records deterministic metadata about OpenClaw repos, mirrors,
machines, and planned nodes so work can be routed to the correct environment.
It creates no networking setup, deployment path, runtime authority, browser
automation, send path, or client/customer authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "openclaw_estate_node_registry_v0"
READ_MODEL_VERSION = "openclaw_estate_node_registry_read_model_v0"
JSON_EXPORT_NAME = "openclaw_estate_node_registry.json"
OPERATOR_EXPORT_NAME = "openclaw_estate_node_registry_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

REQUIRED_NODE_FIELDS = (
    "node_id",
    "display_name",
    "node_type",
    "known_paths",
    "operating_system",
    "hardware_class",
    "mobility_class",
    "authority_level",
    "canonicality",
    "suited_work",
    "blocked_work",
    "allowed_access_patterns",
    "sync_or_bridge_surfaces",
    "promotion_required_for_authority",
    "evidence_status",
    "operator_notes",
)

NO_AUTHORITY_FLAGS = {
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "browser_automation_authority_added": False,
    "customer_deployment_authority_added": False,
    "repo_b_runtime_authority_added": False,
    "mission_control_app_changed": False,
    "ssh_configured": False,
    "services_started": False,
    "repo_b_executed": False,
    "client_deployment_created": False,
    "broad_private_scan_performed": False,
}


@dataclass(frozen=True)
class EstateNodeRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    node_count: int
    repo_a_canonical_backend_modeled: bool
    repo_b_reference_only_modeled: bool
    mac_mission_control_app_surface_modeled: bool
    mac_planner_builder_node_modeled: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parent / candidate


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(__file__).resolve().parent).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _node(
    *,
    node_id: str,
    display_name: str,
    node_type: str,
    known_paths: tuple[dict[str, Any], ...],
    operating_system: str,
    hardware_class: str,
    mobility_class: str,
    authority_level: str,
    canonicality: str,
    suited_work: tuple[str, ...],
    blocked_work: tuple[str, ...],
    allowed_access_patterns: tuple[dict[str, Any], ...],
    sync_or_bridge_surfaces: tuple[str, ...],
    promotion_required_for_authority: str,
    evidence_status: str,
    operator_notes: str,
    active_authority: bool = False,
    repo_b_runtime_authority: bool = False,
) -> dict[str, Any]:
    payload = {
        "node_id": node_id,
        "display_name": display_name,
        "node_type": node_type,
        "known_paths": list(known_paths),
        "operating_system": operating_system,
        "hardware_class": hardware_class,
        "mobility_class": mobility_class,
        "authority_level": authority_level,
        "canonicality": canonicality,
        "suited_work": list(suited_work),
        "blocked_work": list(blocked_work),
        "allowed_access_patterns": list(allowed_access_patterns),
        "sync_or_bridge_surfaces": list(sync_or_bridge_surfaces),
        "promotion_required_for_authority": promotion_required_for_authority,
        "evidence_status": evidence_status,
        "operator_notes": operator_notes,
        "active_authority": active_authority,
        "runtime_authority": False,
        "send_or_submit_authority": False,
        "deployment_authority": False,
        "browser_automation_authority": False,
        "repo_b_runtime_authority": repo_b_runtime_authority,
    }
    _validate_node(payload)
    return payload


def _validate_node(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_NODE_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"estate node missing fields: {', '.join(missing)}")
    if payload.get("runtime_authority") is not False:
        raise ValueError(f"runtime authority is forbidden in node registry: {payload['node_id']}")
    if payload.get("send_or_submit_authority") is not False:
        raise ValueError(f"send/submit authority is forbidden in node registry: {payload['node_id']}")
    if payload.get("deployment_authority") is not False:
        raise ValueError(f"deployment authority is forbidden in node registry: {payload['node_id']}")
    if payload.get("repo_b_runtime_authority") is not False:
        raise ValueError(f"Repo B runtime authority is forbidden in node registry: {payload['node_id']}")


def _path(kind: str, value: str, *, status: str = "known") -> dict[str, Any]:
    return {"path_kind": kind, "path": value, "status": status}


def _access(pattern: str, *, allowed: bool, boundary: str) -> dict[str, Any]:
    return {"access_pattern": pattern, "allowed": allowed, "boundary": boundary}


def estate_nodes() -> tuple[dict[str, Any], ...]:
    return (
        _node(
            node_id="repo_a_pc_wsl_backend",
            display_name="Repo A / PC-WSL Canonical Backend",
            node_type="repo_workspace",
            known_paths=(_path("wsl_repo", "/home/openclaw"),),
            operating_system="linux_wsl_on_pc",
            hardware_class="pc_workstation_wsl",
            mobility_class="stationary_backend",
            authority_level="canonical_backend_read_model_contract_test_authority",
            canonicality="canonical_current_backend",
            suited_work=(
                "SQLite/read-model work",
                "packets/gates/receipts/contracts/tests",
                "backend Codex implementation",
                "generated read-model exports",
            ),
            blocked_work=(
                "Mac/Xcode UI builds",
                "Mac browser automation",
                "direct Mac filesystem-path work",
                "Coupa/browser/desktop automation",
            ),
            allowed_access_patterns=(
                _access("local_backend_codex_work", allowed=True, boundary="repo_a_only"),
                _access("scoped_ssh_development_from_mac_or_pc", allowed=True, boundary="does_not_grant_task_authority"),
            ),
            sync_or_bridge_surfaces=("generated/read_models", "/mnt/e/openclaw shuttle"),
            promotion_required_for_authority="already canonical for backend/read-model/contracts/tests only",
            evidence_status="confirmed_from_current_workspace",
            operator_notes="Default node for PC/WSL backend lanes.",
            active_authority=True,
        ),
        _node(
            node_id="repo_b_pc_wsl_reference",
            display_name="Repo B / PC-WSL Reference Capability Tree",
            node_type="reference_repo_workspace",
            known_paths=(_path("wsl_reference_repo", "/home/openclaw_external/openclaw-runtime"),),
            operating_system="linux_wsl_on_pc",
            hardware_class="pc_workstation_wsl",
            mobility_class="stationary_reference",
            authority_level="reference_evidence_only",
            canonicality="not_canonical_pre_split_capability_tree",
            suited_work=("read-only capability/name/logic reference", "migration comparison evidence"),
            blocked_work=(
                "blind execution",
                "direct production authority",
                "client deployment",
                "runtime/service activation",
            ),
            allowed_access_patterns=(
                _access("read_only_static_inspection", allowed=True, boundary="do_not_import_or_execute"),
            ),
            sync_or_bridge_surfaces=(),
            promotion_required_for_authority="explicit migration lane and Repo A governance adoption proof",
            evidence_status="known_path_operator_provided",
            operator_notes="Treat as reference/capability evidence, not current runtime authority.",
        ),
        _node(
            node_id="mac_mission_control_xcode_repo",
            display_name="Mac Mission Control Xcode Repo",
            node_type="app_repo_workspace",
            known_paths=(
                _path(
                    "mac_app_repo",
                    "/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle",
                ),
            ),
            operating_system="macos",
            hardware_class="mac_development_machine",
            mobility_class="operator_mac",
            authority_level="app_surface_only",
            canonicality="non_canonical_backend_consumer",
            suited_work=(
                "SwiftUI/Xcode app work",
                "read-model parser/display compatibility",
                "build/launch verification",
            ),
            blocked_work=(
                "backend authority",
                "SQLite truth mutation",
                "Coupa execution unless later gated to Mac-local executor",
                "backend command execution from app",
            ),
            allowed_access_patterns=(
                _access("local_xcode_build_launch", allowed=True, boundary="app_repo_only"),
                _access("read_mirrored_generated_read_models", allowed=True, boundary="read_only_visibility"),
            ),
            sync_or_bridge_surfaces=("Mac generated read-model mirror", "Request Sync marker-only flow"),
            promotion_required_for_authority="not promotable to backend authority; app remains helm surface",
            evidence_status="known_path_operator_provided",
            operator_notes="Use this node for Mission Control UI lanes, not PC backend lanes.",
        ),
        _node(
            node_id="mac_generated_read_model_mirror",
            display_name="Mac Generated Read-Model Mirror",
            node_type="read_model_mirror",
            known_paths=(_path("mac_mirror", "/Users/hwinshipwheatley/openclaw_generated_read_models"),),
            operating_system="macos",
            hardware_class="mac_development_machine",
            mobility_class="operator_mac",
            authority_level="mirrored_visibility_only",
            canonicality="mirror_not_truth",
            suited_work=("Mission Control read-only consumption", "display verification"),
            blocked_work=("source-of-truth edits", "manual truth mutation", "backend authority"),
            allowed_access_patterns=(
                _access("app_read_only_file_load", allowed=True, boundary="mirror_visibility_not_canonical_truth"),
            ),
            sync_or_bridge_surfaces=("read_model_shuttle", "sync_health", "Mac manifest import"),
            promotion_required_for_authority="never becomes canonical truth; refresh from Repo A/export pipeline",
            evidence_status="known_path_operator_provided",
            operator_notes="If missing, request sync through existing marker flow rather than faking data.",
        ),
        _node(
            node_id="shared_e_drive_shuttle",
            display_name="Shared E-Drive Shuttle",
            node_type="sync_transport_surface",
            known_paths=(
                _path("wsl_mount", "/mnt/e/openclaw"),
                _path("mac_volume", "/Volumes/openclaw_e"),
            ),
            operating_system="shared_storage_bridge",
            hardware_class="external_or_shared_drive",
            mobility_class="portable_transport",
            authority_level="transport_proof_surface",
            canonicality="transport_not_truth",
            suited_work=("sync markers", "manifests", "completion markers", "shuttle packages"),
            blocked_work=("arbitrary manual copy as primary fix", "source-of-truth mutation", "secret staging"),
            allowed_access_patterns=(
                _access("existing_marker_manifest_sync", allowed=True, boundary="transport_only_not_canonical_truth"),
            ),
            sync_or_bridge_surfaces=("mac_generated_read_models_manifest", "sync request/completion markers"),
            promotion_required_for_authority="not promotable; remains controlled shuttle/proof surface",
            evidence_status="known_paths_operator_provided",
            operator_notes="Use existing sync machinery; do not treat drive reachability as authority.",
        ),
        _node(
            node_id="mac_openclaw_planner_builder_harness",
            display_name="Mac OpenClaw Planner/Builder/Harness Node",
            node_type="mac_local_builder_planner_node",
            known_paths=(_path("mac_planner_builder_path", "unknown", status="unknown_not_discovered_in_this_lane"),),
            operating_system="macos",
            hardware_class="mac_development_machine",
            mobility_class="operator_mac_or_laptop",
            authority_level="non_canonical_candidate",
            canonicality="candidate_non_canonical_unless_promoted",
            suited_work=(
                "Mac-local planner/builder support",
                "harness testing",
                "Xcode/browser/desktop automation lanes after explicit gates",
                "laptop or semi-mobile workflows",
            ),
            blocked_work=(
                "hidden authority",
                "uncontrolled second brain",
                "canonical backend truth by default",
                "ungated browser/Coupa/desktop automation",
            ),
            allowed_access_patterns=(
                _access("scoped_mac_local_development", allowed=True, boundary="non_canonical_until_promoted"),
            ),
            sync_or_bridge_surfaces=("future guarded receipts/read-models",),
            promotion_required_for_authority="explicit operator approval, path discovery, tests, receipts, and authority contract",
            evidence_status="planned_candidate_path_unknown",
            operator_notes="Model role now; do not pretend active path or authority exists.",
        ),
        _node(
            node_id="mac_studio_future_workstation",
            display_name="Future Mac Studio Workstation Node",
            node_type="future_workstation_node",
            known_paths=(_path("future_path", "not_configured", status="planned_non_active"),),
            operating_system="macos",
            hardware_class="high_memory_local_workstation",
            mobility_class="stationary_mac",
            authority_level="planned_no_active_authority",
            canonicality="planned_non_canonical",
            suited_work=("future media-heavy automation", "future high-memory local workloads"),
            blocked_work=("current authority", "deployment", "send/submit paths"),
            allowed_access_patterns=(
                _access("future_scoped_development", allowed=False, boundary="not_active"),
            ),
            sync_or_bridge_surfaces=(),
            promotion_required_for_authority="future operator approval plus node bootstrap contract",
            evidence_status="planned_non_active",
            operator_notes="Listed for role/capability planning only.",
        ),
        _node(
            node_id="mac_laptop_future_execution_node",
            display_name="Future Mac Laptop Semi-Mobile Node",
            node_type="future_mobile_mac_node",
            known_paths=(_path("future_path", "not_configured", status="planned_non_active"),),
            operating_system="macos",
            hardware_class="laptop",
            mobility_class="semi_mobile",
            authority_level="planned_no_active_authority",
            canonicality="planned_non_canonical",
            suited_work=("future semi-mobile Mac execution/planning", "future local desktop verification"),
            blocked_work=("current authority", "canonical backend truth", "ungated automation"),
            allowed_access_patterns=(
                _access("future_scoped_development", allowed=False, boundary="not_active"),
            ),
            sync_or_bridge_surfaces=(),
            promotion_required_for_authority="future operator approval plus node bootstrap contract",
            evidence_status="planned_non_active",
            operator_notes="Role/capability placeholder only.",
        ),
        _node(
            node_id="ipad_iphone_operator_surface_future",
            display_name="Future iPad/iPhone Operator Surface",
            node_type="future_lightweight_operator_surface",
            known_paths=(_path("future_app_surface", "not_configured", status="planned_non_active"),),
            operating_system="ios_ipados",
            hardware_class="mobile_device",
            mobility_class="mobile",
            authority_level="planned_visibility_or_approval_surface_only",
            canonicality="planned_non_canonical",
            suited_work=("future intake", "future approval", "future visibility"),
            blocked_work=("backend truth", "desktop automation", "deployment", "ungated sends"),
            allowed_access_patterns=(
                _access("future_operator_visibility", allowed=False, boundary="not_active"),
            ),
            sync_or_bridge_surfaces=(),
            promotion_required_for_authority="future app/security/approval contract",
            evidence_status="planned_non_active",
            operator_notes="Listing does not grant active mobile authority.",
        ),
        _node(
            node_id="client_friend_company_node_future",
            display_name="Future Client/Friend/Company Node",
            node_type="future_client_capsule_node",
            known_paths=(_path("future_client_path", "not_configured", status="planned_non_active"),),
            operating_system="unknown_future",
            hardware_class="client_or_company_environment",
            mobility_class="external",
            authority_level="planned_capsule_reporting_only",
            canonicality="external_non_canonical",
            suited_work=("future capsule/reporting node", "sanitized proof/status exchange"),
            blocked_work=("customer deployment authority", "private data copy into Repo A", "runtime authority"),
            allowed_access_patterns=(
                _access("future_sanitized_report_bridge", allowed=False, boundary="not_active"),
            ),
            sync_or_bridge_surfaces=("future report_bridge packages", "future project_capsules"),
            promotion_required_for_authority="explicit customer/capsule deployment contract and operator approval",
            evidence_status="planned_non_active",
            operator_notes="No deployment authority exists because this placeholder is listed.",
        ),
    )


def _node_by_id(nodes: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    return {node["node_id"]: node for node in nodes}


def work_routing_rules() -> tuple[dict[str, Any], ...]:
    return (
        {
            "work_kind": "pc_wsl_backend_contract_read_model_tests",
            "recommended_node_id": "repo_a_pc_wsl_backend",
            "wrong_environment_warning": "Do not run backend contract/read-model/test lanes from the Mac app repo.",
        },
        {
            "work_kind": "mission_control_xcode_app_surface",
            "recommended_node_id": "mac_mission_control_xcode_repo",
            "wrong_environment_warning": "Do not attempt SwiftUI/Xcode build or launch from /home/openclaw.",
        },
        {
            "work_kind": "mission_control_read_only_data_display",
            "recommended_node_id": "mac_generated_read_model_mirror",
            "wrong_environment_warning": "Do not edit mirror files as truth; refresh through governed sync.",
        },
        {
            "work_kind": "mac_browser_coupa_desktop_automation",
            "recommended_node_id": "mac_openclaw_planner_builder_harness",
            "wrong_environment_warning": "Do not run browser/Coupa/desktop automation from PC/WSL; require future Mac-local gates.",
        },
        {
            "work_kind": "repo_b_capability_reference",
            "recommended_node_id": "repo_b_pc_wsl_reference",
            "wrong_environment_warning": "Repo B may be inspected read-only but must not be imported or executed.",
        },
        {
            "work_kind": "read_model_sync_transport",
            "recommended_node_id": "shared_e_drive_shuttle",
            "wrong_environment_warning": "Use existing marker/manifest flow; do not manually copy as the primary fix.",
        },
        {
            "work_kind": "mobile_operator_visibility_or_approval",
            "recommended_node_id": "ipad_iphone_operator_surface_future",
            "wrong_environment_warning": "Future mobile surfaces have no active authority yet.",
        },
    )


def derive_wrong_environment_guidance(nodes: tuple[dict[str, Any], ...] | None = None) -> list[dict[str, Any]]:
    known_nodes = _node_by_id(nodes or estate_nodes())
    guidance: list[dict[str, Any]] = []
    for rule in work_routing_rules():
        node = known_nodes[rule["recommended_node_id"]]
        guidance.append(
            {
                **rule,
                "recommended_node_display_name": node["display_name"],
                "recommended_node_authority_level": node["authority_level"],
                "recommended_node_canonicality": node["canonicality"],
                "authority_escalation_allowed": False,
            }
        )
    return guidance


def machine_access_policy() -> dict[str, Any]:
    return {
        "ssh_between_mac_and_pc_wsl": "allowed_for_scoped_development_workflows",
        "ssh_availability_should_be_treated_as_normal_blocker": False,
        "ssh_grants_task_authority": False,
        "ssh_grants_runtime_authority": False,
        "correct_node_workspace_still_required": True,
        "mac_xcode_lanes_run_on_mac": True,
        "pc_wsl_backend_lanes_run_in_home_openclaw": True,
        "browser_coupa_desktop_automation_requires_mac_local_gated_lane": True,
        "repo_b_executable_because_reachable": False,
        "configured_in_this_lane": False,
    }


def build_openclaw_estate_node_registry(*, generated_at: str | None = None) -> dict[str, Any]:
    nodes = estate_nodes()
    counts_by_type = Counter(node["node_type"] for node in nodes)
    counts_by_evidence = Counter(node["evidence_status"] for node in nodes)
    active_authority_nodes = [node["node_id"] for node in nodes if node["active_authority"]]
    future_nodes = [node["node_id"] for node in nodes if node["evidence_status"] == "planned_non_active"]
    status_summary = {
        "repo_a_canonical_backend_modeled": True,
        "repo_b_reference_only_modeled": True,
        "mac_mission_control_app_surface_modeled": True,
        "mac_planner_builder_node_modeled": True,
        "ssh_scoped_dev_access_policy_modeled": True,
        "wrong_environment_guidance_modeled": True,
        "future_nodes_active_authority_granted": False,
        "repo_b_runtime_authority_added": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Distinguish canonical backend authority, reference repos, Mac app workspaces, mirrors, shuttles, and future nodes.",
        "required_node_fields": list(REQUIRED_NODE_FIELDS),
        "node_count": len(nodes),
        "counts_by_node_type": dict(sorted(counts_by_type.items())),
        "counts_by_evidence_status": dict(sorted(counts_by_evidence.items())),
        "active_authority_nodes": active_authority_nodes,
        "future_or_planned_nodes": future_nodes,
        "nodes": list(nodes),
        "machine_access_policy": machine_access_policy(),
        "wrong_environment_guidance": derive_wrong_environment_guidance(nodes),
        "status_summary": status_summary,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Mission Control Estate Node Registry Surface v0",
    }


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Estate Node Registry",
        "",
        "What this is:",
        "- A deterministic registry of repos, mirrors, shuttles, Mac workspaces, and future nodes.",
        "- It helps route work to the right environment before a lane starts.",
        "",
        "What this is not:",
        "- No SSH configuration, service start, Repo B execution, browser automation, send/submit path, deployment, or Mission Control app change.",
        "",
        "Summary:",
        f"- Nodes: {read_model['node_count']}.",
        f"- Active authority nodes: {', '.join(read_model['active_authority_nodes']) or 'none'}.",
        f"- Future/planned nodes: {len(read_model['future_or_planned_nodes'])}.",
        "",
        "Key Nodes:",
    ]
    for node in read_model["nodes"]:
        lines.append(
            f"- `{node['node_id']}`: {node['display_name']} | `{node['authority_level']}` | `{node['canonicality']}`"
        )
    lines.extend(
        [
            "",
            "Machine Access Policy:",
            f"- SSH Mac <-> PC/WSL: `{read_model['machine_access_policy']['ssh_between_mac_and_pc_wsl']}`.",
            "- SSH reachability does not grant task, runtime, send, submit, or Repo B authority.",
            "- PC/WSL backend lanes run in `/home/openclaw`; Mac/Xcode lanes run on the Mac app repo.",
            "- Browser/Coupa/desktop automation must be a future Mac-local gated lane.",
            "",
            "Wrong-Environment Guidance:",
        ]
    )
    for item in read_model["wrong_environment_guidance"]:
        lines.append(
            f"- `{item['work_kind']}` -> `{item['recommended_node_id']}`. {item['wrong_environment_warning']}"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Future nodes are listed for role/capability planning only and gain no active authority.",
            "- Repo B remains reference-only and not runtime authority.",
            "- The E-drive shuttle is transport/proof surface, not canonical truth or manual-copy authority.",
            "",
            f"Next safe lane: {read_model['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_openclaw_estate_node_registry(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> EstateNodeRegistryExportResult:
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_openclaw_estate_node_registry(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    status = read_model["status_summary"]
    return EstateNodeRegistryExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        node_count=read_model["node_count"],
        repo_a_canonical_backend_modeled=status["repo_a_canonical_backend_modeled"],
        repo_b_reference_only_modeled=status["repo_b_reference_only_modeled"],
        mac_mission_control_app_surface_modeled=status["mac_mission_control_app_surface_modeled"],
        mac_planner_builder_node_modeled=status["mac_planner_builder_node_modeled"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw estate node registry read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_estate_node_registry(export_root=args.export_root)
    if args.format == "json":
        print((_rooted(args.export_root) / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((_rooted(args.export_root) / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REQUIRED_NODE_FIELDS",
    "SCHEMA_VERSION",
    "build_openclaw_estate_node_registry",
    "derive_wrong_environment_guidance",
    "estate_nodes",
    "export_openclaw_estate_node_registry",
    "format_operator_read_model",
    "machine_access_policy",
    "stable_json",
    "work_routing_rules",
]


if __name__ == "__main__":
    raise SystemExit(main())
