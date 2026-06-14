"""OpenClaw Estate Topology Registry v0.

This registry preserves the audited machine/repo ownership map as deterministic
metadata. It writes read-model and SQLite artifacts only; it does not start
services, execute workflows, access external accounts, or read workbook/PDF
content.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openclaw_reference_resolver import (
    OPENCLAW_EYES_MAIN_BRANCH,
    OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
    OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH,
    OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
    build_openclaw_reference_resolver,
    git_branch_ref_by_repo_ref,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")
EXTERNAL_REGISTRY_INDEX_NAME = "external_system_knowledge_registry_index.json"

SCHEMA_VERSION = "openclaw_estate_topology_registry_v0"
READ_MODEL_VERSION = "openclaw_estate_topology_registry_read_model_v0"
JSON_EXPORT_NAME = "openclaw_estate_topology_registry.json"
OPERATOR_EXPORT_NAME = "openclaw_estate_topology_registry_OPERATOR.md"
SQLITE_EXPORT_NAME = "openclaw_estate_topology_registry.sqlite"
SCHEMA_EXPORT_NAME = "openclaw_estate_topology_registry_SCHEMA.sql"
SEED_EXPORT_NAME = "openclaw_estate_topology_registry_SEED.sql"

STATUS_VALUES = (
    "CONFIRMED",
    "PARTIAL",
    "UNKNOWN",
    "MISSING",
    "RESOLVED_LOCAL",
    "RESOLVED_REMOTE",
    "RESOLVED_MAC_BRIDGE",
    "UNREACHABLE",
    "LOCAL_PATH_UNREACHABLE",
    "REMOTE_UNAVAILABLE",
    "MAC_BRIDGE_UNAVAILABLE",
    "PRESENT_ON_REVIEW_BRANCH",
    "PENDING_REVIEW",
    "CANONICAL_ON_MAIN",
    "CANONICAL",
    "EXTERNAL_REGISTRY_MATERIALIZED",
    "PLANNED",
    "STALE",
    "DIRTY",
    "CLEAN",
)

REQUIRED_SQLITE_TABLES = (
    "machine",
    "repo_working_copy",
    "repo_relationship",
    "bridge_path",
    "source_of_truth_area",
    "registry_presence",
    "external_registry_materialization",
    "codex_web_artifact",
    "known_unknown",
    "recommended_action",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "services_modified": False,
    "services_started": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
    "external_lm_or_live_tool_action_run": False,
    "git_push_performed": False,
}


@dataclass(frozen=True)
class EstateTopologyRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    machine_count: int
    repo_working_copy_count: int
    actual_repo_count: int
    known_unknown_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _bool(value: bool) -> int:
    return 1 if value else 0


def _require_status(status: str) -> str:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown estate topology status: {status}")
    return status


def _machine(
    machine_id: str,
    display_name: str,
    machine_role: str,
    operating_system: str,
    evidence_status: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "machine_id": machine_id,
        "display_name": display_name,
        "machine_role": machine_role,
        "operating_system": operating_system,
        "evidence_status": _require_status(evidence_status),
        "notes": notes,
    }


def machines() -> tuple[dict[str, Any], ...]:
    return (
        _machine(
            "pc",
            "PC / WSL backend machine",
            "backend_and_runtime_development",
            "linux_wsl_on_pc",
            "CONFIRMED",
            "Local backend workspace is inspected from /home/openclaw.",
        ),
        _machine(
            "mac",
            "Operator Mac",
            "mac_app_excel_edge_and_runtime_working_copies",
            "macos",
            "CONFIRMED",
            "Mac paths are audit-confirmed from estate topology findings, not inspected from this PC lane.",
        ),
    )


def _working_copy(
    *,
    working_copy_id: str,
    machine_id: str,
    repo_name: str,
    repo_key: str,
    local_path: str,
    classification: str,
    worktree_status: str,
    clean: bool,
    generated_models: bool,
    python: bool,
    swift: bool,
    remote: str,
    remote_status: str,
    evidence_status: str,
    source_note: str,
) -> dict[str, Any]:
    return {
        "working_copy_id": working_copy_id,
        "machine_id": machine_id,
        "repo_name": repo_name,
        "repo_key": repo_key,
        "local_path": local_path,
        "classification": classification,
        "worktree_status": _require_status(worktree_status),
        "clean": clean,
        "generated_models": generated_models,
        "python": python,
        "swift": swift,
        "remote": remote,
        "remote_status": _require_status(remote_status),
        "evidence_status": _require_status(evidence_status),
        "source_note": source_note,
    }


def repo_working_copies() -> tuple[dict[str, Any], ...]:
    return (
        _working_copy(
            working_copy_id="pc_openclaw_eyes_backend",
            machine_id="pc",
            repo_name="openclaw-eyes",
            repo_key="openclaw-eyes",
            local_path="/home/openclaw",
            classification="PC_BACKEND",
            worktree_status="DIRTY",
            clean=False,
            generated_models=True,
            python=True,
            swift=False,
            remote="https://github.com/WinshipWheatley/openclaw-eyes.git",
            remote_status="CONFIRMED",
            evidence_status="CONFIRMED",
            source_note="Local PC working copy inspected; active repo is dirty and ahead of origin.",
        ),
        _working_copy(
            working_copy_id="pc_openclaw_runtime",
            machine_id="pc",
            repo_name="openclaw-runtime",
            repo_key="openclaw-runtime",
            local_path="/home/openclaw_external/openclaw-runtime",
            classification="RUNTIME_ACTORS",
            worktree_status="CLEAN",
            clean=True,
            generated_models=False,
            python=True,
            swift=False,
            remote="https://github.com/WinshipWheatley/openclaw-runtime.git",
            remote_status="CONFIRMED",
            evidence_status="CONFIRMED",
            source_note="Local PC runtime working copy inspected and clean.",
        ),
        _working_copy(
            working_copy_id="mac_mission_control_app",
            machine_id="mac",
            repo_name="OpenClaw Mission Controle",
            repo_key="openclaw-mission-control",
            local_path="/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle",
            classification="MAC_APP",
            worktree_status="DIRTY",
            clean=False,
            generated_models=False,
            python=False,
            swift=True,
            remote="none/local-only",
            remote_status="MISSING",
            evidence_status="CONFIRMED",
            source_note="Audit-confirmed Mac app repo; local-only remote posture must be resolved on Mac.",
        ),
        _working_copy(
            working_copy_id="mac_openclaw_eyes_context",
            machine_id="mac",
            repo_name="openclaw-eyes",
            repo_key="openclaw-eyes",
            local_path="/Users/hwinshipwheatley/Eyes",
            classification="EYES_CONTEXT_REPO",
            worktree_status="CLEAN",
            clean=True,
            generated_models=True,
            python=True,
            swift=False,
            remote="unknown_from_pc_lane",
            remote_status="UNKNOWN",
            evidence_status="CONFIRMED",
            source_note="Audit-confirmed Mac context/mirror working copy; not live backend unless proven.",
        ),
        _working_copy(
            working_copy_id="mac_openclaw_runtime",
            machine_id="mac",
            repo_name="openclaw-runtime",
            repo_key="openclaw-runtime",
            local_path="/Users/hwinshipwheatley/Developer/OpenClawIntake/openclaw-runtime",
            classification="RUNTIME_ACTORS",
            worktree_status="CLEAN",
            clean=True,
            generated_models=False,
            python=True,
            swift=False,
            remote="unknown_from_pc_lane",
            remote_status="UNKNOWN",
            evidence_status="CONFIRMED",
            source_note="Audit-confirmed Mac runtime working copy.",
        ),
    )


def _relationship(
    relationship_id: str,
    relationship_type: str,
    left_working_copy_id: str,
    right_working_copy_id: str,
    status: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "relationship_id": relationship_id,
        "relationship_type": relationship_type,
        "left_working_copy_id": left_working_copy_id,
        "right_working_copy_id": right_working_copy_id,
        "status": _require_status(status),
        "notes": notes,
    }


def repo_relationships() -> tuple[dict[str, Any], ...]:
    return (
        _relationship(
            "openclaw_eyes_pc_backend_to_mac_context",
            "same_repo_name_distinct_working_copy_roles",
            "pc_openclaw_eyes_backend",
            "mac_openclaw_eyes_context",
            "PARTIAL",
            "PC copy owns live backend/read-model work; Mac Eyes copy is context/mirror unless proven otherwise.",
        ),
        _relationship(
            "openclaw_runtime_pc_to_mac",
            "same_repo_name_runtime_actor_working_copies",
            "pc_openclaw_runtime",
            "mac_openclaw_runtime",
            "PARTIAL",
            "Both runtime working copies exist; canonical actor runtime ownership still needs a policy decision.",
        ),
        _relationship(
            "mac_app_local_only_boundary",
            "local_only_unbacked_mac_app_repo",
            "mac_mission_control_app",
            "mac_mission_control_app",
            "PARTIAL",
            "Mac app is a real Swift repo with no remote recorded in the audit.",
        ),
    )


def _bridge_path(
    bridge_id: str,
    machine_id: str,
    local_path: str,
    counterpart_bridge_id: str,
    access_status: str,
    evidence_status: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "bridge_id": bridge_id,
        "machine_id": machine_id,
        "local_path": local_path,
        "counterpart_bridge_id": counterpart_bridge_id,
        "access_status": _require_status(access_status),
        "evidence_status": _require_status(evidence_status),
        "notes": notes,
    }


def bridge_paths() -> tuple[dict[str, Any], ...]:
    return (
        _bridge_path(
            "pc_e_drive_bridge",
            "pc",
            "/mnt/e/openclaw",
            "mac_openclaw_e_bridge",
            "PARTIAL",
            "CONFIRMED",
            "PC side of bridge/mirror transport.",
        ),
        _bridge_path(
            "mac_openclaw_e_bridge",
            "mac",
            "/Volumes/openclaw_e",
            "pc_e_drive_bridge",
            "PARTIAL",
            "CONFIRMED",
            "Mac side of bridge has permission/access issues in some contexts.",
        ),
    )


def _source_area(
    *,
    area_id: str,
    display_name: str,
    owner_repo_key: str,
    primary_working_copy_id: str,
    secondary_working_copy_id: str,
    owner_classification: str,
    status: str,
    ownership_rule: str,
    notes: str,
    current_state: str | None = None,
    canonical_status: str | None = None,
    review_repo: str = "",
    review_branch: str = "",
    review_commit: str = "",
) -> dict[str, Any]:
    resolved_current_state = current_state or status
    resolved_canonical_status = canonical_status or status
    return {
        "area_id": area_id,
        "display_name": display_name,
        "owner_repo_key": owner_repo_key,
        "primary_working_copy_id": primary_working_copy_id,
        "secondary_working_copy_id": secondary_working_copy_id,
        "owner_classification": owner_classification,
        "status": _require_status(status),
        "current_state": _require_status(resolved_current_state),
        "canonical_status": _require_status(resolved_canonical_status),
        "review_repo": review_repo,
        "review_branch": review_branch,
        "review_commit": review_commit,
        "ownership_rule": ownership_rule,
        "notes": notes,
    }


def build_estate_reference_resolver_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    return build_openclaw_reference_resolver(generated_at=generated_at)


def _system_knowledge_registry_branch_resolution(reference_resolver_payload: dict[str, Any]) -> dict[str, Any]:
    return git_branch_ref_by_repo_ref(
        reference_resolver_payload,
        OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
    )


def _system_knowledge_registry_main_resolution(reference_resolver_payload: dict[str, Any]) -> dict[str, Any]:
    return git_branch_ref_by_repo_ref(
        reference_resolver_payload,
        OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
    )


def _review_branch_status(branch_resolution: dict[str, Any]) -> str:
    if (
        branch_resolution.get("dirty_status") == "DIRTY"
        and branch_resolution.get("resolution_status") == "RESOLVED_LOCAL"
    ):
        return "DIRTY"
    if branch_resolution.get("resolution_status") in {
        "RESOLVED_LOCAL",
        "RESOLVED_REMOTE",
        "RESOLVED_MAC_BRIDGE",
    }:
        return "PRESENT_ON_REVIEW_BRANCH"
    if branch_resolution.get("resolution_status") == "REMOTE_UNAVAILABLE":
        return "REMOTE_UNAVAILABLE"
    if branch_resolution.get("resolution_status") == "LOCAL_PATH_UNREACHABLE":
        return "LOCAL_PATH_UNREACHABLE"
    if branch_resolution.get("resolution_status") == "MAC_BRIDGE_UNAVAILABLE":
        return "MAC_BRIDGE_UNAVAILABLE"
    return "UNREACHABLE"


def _review_branch_canonical_status(branch_resolution: dict[str, Any]) -> str:
    return "PENDING_REVIEW" if _review_branch_status(branch_resolution) in {
        "PRESENT_ON_REVIEW_BRANCH",
        "DIRTY",
    } else _review_branch_status(branch_resolution)


def _main_contains_registry_commit(
    branch_resolution: dict[str, Any],
    main_resolution: dict[str, Any],
) -> bool:
    review_commit = branch_resolution.get("current_head_commit", "")
    main_commit = main_resolution.get("current_head_commit", "")
    return bool(
        review_commit
        and main_commit
        and review_commit == main_commit
        and branch_resolution.get("resolution_status")
        in {"RESOLVED_LOCAL", "RESOLVED_REMOTE", "RESOLVED_MAC_BRIDGE"}
        and main_resolution.get("resolution_status")
        in {"RESOLVED_LOCAL", "RESOLVED_REMOTE", "RESOLVED_MAC_BRIDGE"}
    )


def _system_knowledge_registry_posture(reference_resolver_payload: dict[str, Any]) -> dict[str, Any]:
    branch_resolution = _system_knowledge_registry_branch_resolution(reference_resolver_payload)
    main_resolution = _system_knowledge_registry_main_resolution(reference_resolver_payload)
    branch_status = _review_branch_status(branch_resolution)
    canonical_status = _review_branch_canonical_status(branch_resolution)
    current_state = branch_status
    effective_branch = branch_resolution.get("branch") or OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH
    effective_commit = branch_resolution.get("current_head_commit", "")
    owner_classification = "PC_BACKEND_REVIEW_BRANCH"
    source_truth = False
    notes = "Branch name is the source input; current commit is resolved by openclaw_reference_resolver during export."
    if _main_contains_registry_commit(branch_resolution, main_resolution):
        current_state = "CANONICAL_ON_MAIN"
        canonical_status = "CANONICAL"
        effective_branch = OPENCLAW_EYES_MAIN_BRANCH
        effective_commit = main_resolution.get("current_head_commit", "")
        owner_classification = "PC_BACKEND_CANONICAL_MAIN"
        source_truth = True
        notes = (
            "openclaw-eyes main resolves to the registry commit; review branch remains historical evidence."
        )
    return {
        "branch_resolution": branch_resolution,
        "main_resolution": main_resolution,
        "branch_status": branch_status,
        "current_state": current_state,
        "canonical_status": canonical_status,
        "effective_branch": effective_branch,
        "effective_commit": effective_commit,
        "owner_classification": owner_classification,
        "source_truth": source_truth,
        "notes": notes,
        "review_branch": branch_resolution.get("branch") or OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH,
        "review_commit": branch_resolution.get("current_head_commit", ""),
        "main_branch": main_resolution.get("branch") or OPENCLAW_EYES_MAIN_BRANCH,
        "main_commit": main_resolution.get("current_head_commit", ""),
        "main_contains_review_commit": _main_contains_registry_commit(
            branch_resolution,
            main_resolution,
        ),
    }


def _load_external_registry_index(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    path = _rooted(Path(read_model_root) / EXTERNAL_REGISTRY_INDEX_NAME)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _external_registry_materialized(index_payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(index_payload, dict)
        and index_payload.get("import_status") == "IMPORTED"
        and index_payload.get("canonical_owner") == "openclaw-eyes"
        and index_payload.get("local_role") == "READ_ONLY_EXTERNAL_INPUT"
        and index_payload.get("commit_match") is True
    )


def _artifact_hashes(index_payload: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(index_payload, dict):
        return {}
    hashes: dict[str, str] = {}
    for artifact in index_payload.get("artifacts", []):
        if isinstance(artifact, dict):
            cache_path = str(artifact.get("cache_path") or artifact.get("artifact_type") or "")
            digest = str(artifact.get("sha256") or "")
            if cache_path and digest:
                hashes[cache_path] = digest
    return hashes


def external_registry_materialization_rows(
    external_registry_index_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(external_registry_index_payload, dict) or not external_registry_index_payload:
        return ()
    materialized = _external_registry_materialized(external_registry_index_payload)
    local_status = "EXTERNAL_REGISTRY_MATERIALIZED" if materialized else "MISSING"
    return (
        {
            "registry_ref": "openclaw_eyes_system_knowledge_registry_external_input",
            "canonical_owner": str(external_registry_index_payload.get("canonical_owner", "")),
            "local_role": str(external_registry_index_payload.get("local_role", "")),
            "local_status": _require_status(local_status),
            "source_repo": str(external_registry_index_payload.get("source_repo", "")),
            "source_branch": str(external_registry_index_payload.get("source_branch", "")),
            "source_commit": str(external_registry_index_payload.get("source_commit", "")),
            "artifact_count": int(external_registry_index_payload.get("artifact_count", 0)),
            "artifact_hashes_json": stable_json(_artifact_hashes(external_registry_index_payload)).strip(),
            "index_path": f"generated/read_models/{EXTERNAL_REGISTRY_INDEX_NAME}",
            "notes": (
                "openclaw-eyes system knowledge registry imported as read-only external input."
                if materialized
                else str(external_registry_index_payload.get("reason", "external registry import not materialized"))
            ),
        },
    )


def source_of_truth_areas(reference_resolver_payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    posture = _system_knowledge_registry_posture(reference_resolver_payload)
    branch_resolution = posture["branch_resolution"]
    branch_status = posture["current_state"]
    canonical_status = posture["canonical_status"]
    resolution_status = branch_resolution.get("resolution_status", "UNREACHABLE")
    if branch_status == "CANONICAL_ON_MAIN":
        branch_ownership_rule = (
            "openclaw-eyes main is canonical for the system knowledge registry; review branch remains historical."
        )
    elif branch_status == "UNREACHABLE":
        branch_ownership_rule = (
            "Review branch ref is configured, but the resolver cannot reach the branch from this machine."
        )
    elif resolution_status == "REMOTE_UNAVAILABLE":
        branch_ownership_rule = (
            "Git remote branch is canonical, but remote resolution is unavailable from this machine."
        )
    elif branch_status == "DIRTY":
        branch_ownership_rule = (
            "Review branch ref resolves, but the working copy is dirty; not canonical or merged to main."
        )
    elif resolution_status == "RESOLVED_REMOTE":
        branch_ownership_rule = (
            "Git remote branch is canonical and resolved by read-only remote inspection; Mac path is optional mirror."
        )
    elif resolution_status == "RESOLVED_LOCAL":
        branch_ownership_rule = (
            "Review branch resolved from a local working copy; canonical branch ref remains the source input."
        )
    elif resolution_status == "RESOLVED_MAC_BRIDGE":
        branch_ownership_rule = (
            "Review branch resolved from Mac-published bridge state; canonical branch ref remains the source input."
        )
    else:
        branch_ownership_rule = (
            "Present on openclaw-eyes review branch; not canonical or merged to main until review completes."
        )
    return (
        _source_area(
            area_id="mission_control_app",
            display_name="Mission Control app",
            owner_repo_key="openclaw-mission-control",
            primary_working_copy_id="mac_mission_control_app",
            secondary_working_copy_id="",
            owner_classification="MAC_APP",
            status="CONFIRMED",
            ownership_rule="Swift app source belongs in the Mac app repo.",
            notes="Do not edit PC backend files to represent Swift UI ownership.",
        ),
        _source_area(
            area_id="mac_excel_edge_worker",
            display_name="Mac Excel Edge Worker",
            owner_repo_key="openclaw-mission-control",
            primary_working_copy_id="mac_mission_control_app",
            secondary_working_copy_id="",
            owner_classification="MAC_APP",
            status="CONFIRMED",
            ownership_rule="Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.",
            notes="PC backend may emit packages; Mac owns Mac-local execution architecture.",
        ),
        _source_area(
            area_id="access_broker",
            display_name="Access Broker",
            owner_repo_key="split",
            primary_working_copy_id="mac_mission_control_app",
            secondary_working_copy_id="pc_openclaw_eyes_backend",
            owner_classification="SPLIT_MAC_UI_BACKEND_POLICY",
            status="PARTIAL",
            ownership_rule="Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.",
            notes="Do not collapse UI and policy ownership into one repo without evidence.",
        ),
        _source_area(
            area_id="live_arts_invoice_bundle",
            display_name="Live Arts invoice bundle",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="",
            owner_classification="PC_BACKEND",
            status="CONFIRMED",
            ownership_rule="Live Arts backend bundle/read-model state belongs in /home/openclaw.",
            notes="Mac may execute scoped export jobs only after PC emits a safe package.",
        ),
        _source_area(
            area_id="capital_hilton_invoice_bundle",
            display_name="Capital Hilton invoice bundle",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="",
            owner_classification="PC_BACKEND",
            status="CONFIRMED",
            ownership_rule="Capital Hilton backend bundle/read-model state belongs in /home/openclaw.",
            notes="Supplier portal proof not required should not become a topology blocker.",
        ),
        _source_area(
            area_id="request_response_service",
            display_name="Request/Response service",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="",
            owner_classification="PC_BACKEND",
            status="CONFIRMED",
            ownership_rule="The request/response backend service code belongs in /home/openclaw.",
            notes="This registry does not start, restart, or inspect the running service.",
        ),
        _source_area(
            area_id="hermes",
            display_name="Hermes",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="",
            owner_classification="PC_BACKEND",
            status="PARTIAL",
            ownership_rule="Hermes reads /home/openclaw first for estate-wide task planning unless runtime evidence says otherwise.",
            notes="Runtime placement is not promoted beyond the observed backend planning default.",
        ),
        _source_area(
            area_id="chief_guardian_cassandra_clara_runtime",
            display_name="Chief/Guardian/Cassandra/Clara runtime",
            owner_repo_key="openclaw-runtime",
            primary_working_copy_id="pc_openclaw_runtime",
            secondary_working_copy_id="mac_openclaw_runtime",
            owner_classification="RUNTIME_ACTORS",
            status="PARTIAL",
            ownership_rule="Runtime actor implementation is mapped to openclaw-runtime pending canonical-home decision.",
            notes="The canonical runtime-home question remains a known unknown.",
        ),
        _source_area(
            area_id="evidence_grounded_context_registry",
            display_name="Evidence-Grounded Context Registry",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="",
            owner_classification=posture["owner_classification"],
            status=branch_status,
            current_state=branch_status,
            canonical_status=canonical_status,
            review_repo="openclaw-eyes",
            review_branch=posture["effective_branch"],
            review_commit=posture["effective_commit"],
            ownership_rule=branch_ownership_rule,
            notes=posture["notes"],
        ),
        _source_area(
            area_id="mac_openclaw_eyes_context_repo",
            display_name="openclaw-eyes Mac repo",
            owner_repo_key="openclaw-eyes",
            primary_working_copy_id="mac_openclaw_eyes_context",
            secondary_working_copy_id="pc_openclaw_eyes_backend",
            owner_classification="EYES_CONTEXT_REPO",
            status="CONFIRMED",
            ownership_rule="Mac Eyes is context/mirror, not live backend unless later proven.",
            notes="Do not route live backend mutations to the Mac context copy by name alone.",
        ),
        _source_area(
            area_id="bridge_mirror_transport",
            display_name="bridge/mirror transport",
            owner_repo_key="transport",
            primary_working_copy_id="pc_openclaw_eyes_backend",
            secondary_working_copy_id="mac_openclaw_eyes_context",
            owner_classification="BRIDGE_TRANSPORT",
            status="PARTIAL",
            ownership_rule="/mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth.",
            notes="Mac bridge permission failures are represented as partial access on the Mac bridge path.",
        ),
    )


def _registry_presence(
    registry_id: str,
    display_name: str,
    expected_path: str,
    owning_working_copy_id: str,
    status: str,
    notes: str,
    current_state: str | None = None,
    canonical_status: str | None = None,
    repo_name: str = "",
    branch_name: str = "",
    commit_ref: str = "",
) -> dict[str, Any]:
    resolved_current_state = current_state or status
    resolved_canonical_status = canonical_status or status
    return {
        "registry_id": registry_id,
        "display_name": display_name,
        "expected_path": expected_path,
        "owning_working_copy_id": owning_working_copy_id,
        "status": _require_status(status),
        "current_state": _require_status(resolved_current_state),
        "canonical_status": _require_status(resolved_canonical_status),
        "repo_name": repo_name,
        "branch_name": branch_name,
        "commit_ref": commit_ref,
        "notes": notes,
    }


def registry_presence(
    reference_resolver_payload: dict[str, Any],
    external_registry_index_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    posture = _system_knowledge_registry_posture(reference_resolver_payload)
    registry_status = posture["current_state"]
    canonical_status = posture["canonical_status"]
    registry_notes = "Resolved from openclaw-eyes branch ref; not canonical or merged to main."
    if registry_status == "CANONICAL_ON_MAIN":
        registry_notes = (
            "Resolved from openclaw-eyes main; review branch remains historical evidence."
        )
    rows = [
        _registry_presence(
            "openclaw_estate_topology_registry",
            "OpenClaw Estate Topology Registry",
            "openclaw_estate_topology_registry.py",
            "pc_openclaw_eyes_backend",
            "CONFIRMED",
            "This v0 registry is installed in the PC backend repo.",
        ),
        _registry_presence(
            "openclaw_estate_node_registry",
            "OpenClaw Estate Node Registry",
            "openclaw_estate_node_registry.py",
            "pc_openclaw_eyes_backend",
            "CONFIRMED",
            "Existing node-routing registry remains a nearby source, but topology v0 owns machine/repo map.",
        ),
        _registry_presence(
            "evidence_grounded_context_registry",
            "Evidence-Grounded Context Registry",
            "generated/system_knowledge/openclaw_system_knowledge_registry.sqlite",
            "pc_openclaw_eyes_backend",
            registry_status,
            registry_notes,
            current_state=registry_status,
            canonical_status=canonical_status,
            repo_name="openclaw-eyes",
            branch_name=posture["effective_branch"],
            commit_ref=posture["effective_commit"],
        ),
    ]
    if _external_registry_materialized(external_registry_index_payload):
        artifact_hashes = _artifact_hashes(external_registry_index_payload)
        rows.append(
            _registry_presence(
                "openclaw_eyes_system_knowledge_registry_external_input",
                "openclaw-eyes System Knowledge Registry external input",
                "generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.sqlite",
                "pc_openclaw_eyes_backend",
                "EXTERNAL_REGISTRY_MATERIALIZED",
                (
                    "canonical_owner=openclaw-eyes; local_role=READ_ONLY_EXTERNAL_INPUT; "
                    f"source_commit={external_registry_index_payload.get('source_commit')}; "
                    f"artifact_hashes={stable_json(artifact_hashes).strip()}"
                ),
                current_state="EXTERNAL_REGISTRY_MATERIALIZED",
                canonical_status="CANONICAL",
                repo_name="openclaw-eyes",
                branch_name=str(external_registry_index_payload.get("source_branch", "main")),
                commit_ref=str(external_registry_index_payload.get("source_commit", "")),
            )
        )
    rows.extend(
        [
            _registry_presence(
                "codex_web_registry_commits",
                "Codex Web registry commits",
                "33e00a6 and 4ca4ed42171c23d60ef89493559808ef2789a19e",
                "",
                "UNREACHABLE",
                "Recorded as unreachable artifacts, not source truth.",
            ),
            _registry_presence(
                "bridge_mirror_read_models",
                "Bridge/mirror generated read-model transport",
                "/mnt/e/openclaw and /Volumes/openclaw_e",
                "pc_openclaw_eyes_backend",
                "PARTIAL",
                "Transport exists, but Mac bridge access can fail in some contexts.",
            ),
        ]
    )
    return tuple(rows)


def _codex_web_artifact(
    artifact_id: str,
    commit_ref: str,
    status: str,
    source_truth: bool,
    reason: str,
    notes: str,
    repo_name: str = "",
    branch_name: str = "",
    canonical_status: str | None = None,
) -> dict[str, Any]:
    resolved_canonical_status = canonical_status or status
    return {
        "artifact_id": artifact_id,
        "commit_ref": commit_ref,
        "status": _require_status(status),
        "canonical_status": _require_status(resolved_canonical_status),
        "repo_name": repo_name,
        "branch_name": branch_name,
        "source_truth": source_truth,
        "reason": reason,
        "notes": notes,
    }


def codex_web_artifacts(reference_resolver_payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    posture = _system_knowledge_registry_posture(reference_resolver_payload)
    artifact_status = posture["current_state"]
    canonical_status = posture["canonical_status"]
    source_truth = posture["source_truth"]
    artifact_notes = "Canonical status remains PENDING_REVIEW until the branch is reviewed and merged."
    if artifact_status == "CANONICAL_ON_MAIN":
        artifact_notes = (
            "openclaw-eyes main resolves to this registry commit; review branch remains historical evidence."
        )
    reason = "Commit was reported by Codex Web but was not reachable from local repos/remotes during audit."
    return (
        _codex_web_artifact(
            "codex_web_registry_commit_33e00a6",
            "33e00a6",
            "UNREACHABLE",
            False,
            reason,
            "Do not treat as installed code until a branch, PR, or patch is reachable locally.",
            repo_name="openclaw-eyes",
            canonical_status="UNREACHABLE",
        ),
        _codex_web_artifact(
            "codex_web_registry_commit_4ca4ed42171c23d60ef89493559808ef2789a19e",
            "4ca4ed42171c23d60ef89493559808ef2789a19e",
            "UNREACHABLE",
            False,
            reason,
            "Do not treat as installed code until a branch, PR, or patch is reachable locally.",
            repo_name="openclaw-eyes",
            canonical_status="UNREACHABLE",
        ),
        _codex_web_artifact(
            "openclaw_eyes_system_knowledge_registry_review_branch",
            posture["effective_commit"],
            artifact_status,
            source_truth,
            "System knowledge registry commit is resolved from openclaw-eyes branch ref during export.",
            artifact_notes,
            repo_name="openclaw-eyes",
            branch_name=posture["effective_branch"],
            canonical_status=canonical_status,
        ),
    )


def _known_unknown(
    unknown_id: str,
    question: str,
    status: str,
    recommended_next_step: str,
) -> dict[str, Any]:
    return {
        "unknown_id": unknown_id,
        "question": question,
        "status": _require_status(status),
        "recommended_next_step": recommended_next_step,
    }


def known_unknowns(
    reference_resolver_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    registry_is_canonical = False
    if reference_resolver_payload is not None:
        registry_is_canonical = (
            _system_knowledge_registry_posture(reference_resolver_payload)["canonical_status"]
            == "CANONICAL"
        )
    if not registry_is_canonical:
        rows.append(
            _known_unknown(
                "canonical_system_knowledge_registry_home",
                "Where should the canonical system knowledge registry live?",
                "UNKNOWN",
                "Decide canonical repo only after reachable registry code exists locally.",
            )
        )
    rows.extend(
        [
            _known_unknown(
                "codex_web_commits_unreachable",
                "Why Codex Web commits were not reachable from GitHub remotes.",
                "UNKNOWN",
                "Trace branch/PR/export path for Codex Web artifacts before trusting them.",
            ),
            _known_unknown(
                "mac_app_remote_backup_strategy",
                "Whether Mac app should get a GitHub remote and backup/PR flow.",
                "UNKNOWN",
                "Choose remote/back-up strategy before more Mac app mutation lanes.",
            ),
            _known_unknown(
                "dual_openclaw_eyes_long_term",
                "Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term.",
                "UNKNOWN",
                "Define canonical writer, mirror role, and reconciliation rule.",
            ),
            _known_unknown(
                "runtime_actor_canonical_home",
                "Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime.",
                "UNKNOWN",
                "Inspect runtime repos and actor entrypoints in a dedicated lane.",
            ),
            _known_unknown(
                "hermes_first_read_repo",
                "Which repo Hermes should read first for estate-wide task planning.",
                "UNKNOWN",
                "Keep /home/openclaw as default until runtime evidence establishes another first-read source.",
            ),
            _known_unknown(
                "mac_bridge_permission_model",
                "How Mac bridge permission failures should be represented.",
                "UNKNOWN",
                "Model permission failures as partial bridge access until Mac helper architecture is resolved.",
            ),
        ]
    )
    return tuple(rows)


def _recommended_action(
    action_id: str,
    priority: int,
    action: str,
    status: str,
    owner_hint: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "priority": priority,
        "action": action,
        "status": _require_status(status),
        "owner_hint": owner_hint,
        "reason": reason,
    }


def recommended_actions(
    reference_resolver_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    registry_action = _recommended_action(
        "keep_system_knowledge_registry_pending_review",
        4,
        "Keep system knowledge registry pending review until merged to main.",
        "PENDING_REVIEW",
        "PC_BACKEND",
        "The review branch is present, but it is not canonical mainline state.",
    )
    if reference_resolver_payload is not None:
        posture = _system_knowledge_registry_posture(reference_resolver_payload)
        if posture["canonical_status"] == "CANONICAL":
            registry_action = _recommended_action(
                "record_system_knowledge_registry_canonical_main",
                4,
                "Record system knowledge registry as canonical on openclaw-eyes main.",
                "CONFIRMED",
                "PC_BACKEND",
                "Remote main resolves to the same registry commit as the review branch.",
            )
    return (
        _recommended_action(
            "install_estate_topology_registry",
            1,
            "Install estate topology registry in /home/openclaw.",
            "CONFIRMED",
            "PC_BACKEND",
            "Agents need one local map before more cross-repo work.",
        ),
        _recommended_action(
            "mirror_registry_read_model_to_mac",
            2,
            "Mirror registry read-model to Mac.",
            "PLANNED",
            "BRIDGE_TRANSPORT",
            "Mission Control should read the same topology map later.",
        ),
        _recommended_action(
            "add_mission_control_remote_strategy",
            3,
            "Add Mission Control app remote/back-up strategy.",
            "PLANNED",
            "MAC_APP",
            "Mac app is dirty and local-only by audit.",
        ),
        registry_action,
        _recommended_action(
            "defer_cross_registry_merge",
            5,
            "Build cross-registry merge only after each repo's registry is reachable locally.",
            "PLANNED",
            "PC_BACKEND",
            "Avoid merging phantom or unreachable registry state.",
        ),
        _recommended_action(
            "stabilize_mac_app_dirty_state",
            6,
            "Stabilize Mac app dirty state before further PDF trials.",
            "PLANNED",
            "MAC_APP",
            "Dirty app/helper state makes Mac-side trial results ambiguous.",
        ),
        _recommended_action(
            "keep_live_arts_pdf_blocked_until_mac_architecture_resolved",
            7,
            "Keep Live Arts PDF export blocked until Mac permission/helper architecture is resolved.",
            "PLANNED",
            "MAC_APP",
            "Mac bridge/helper permissions must be clear before retrying export.",
        ),
    )


def _actual_repo_keys(working_copies: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(sorted({copy["repo_key"] for copy in working_copies}))


def build_openclaw_estate_topology_registry(
    *,
    generated_at: str | None = None,
    reference_resolver_payload: dict[str, Any] | None = None,
    external_registry_index_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    machine_rows = machines()
    working_copy_rows = repo_working_copies()
    repo_keys = _actual_repo_keys(working_copy_rows)
    reference_payload = reference_resolver_payload or build_estate_reference_resolver_payload(
        generated_at=generated_at
    )
    external_index_payload = external_registry_index_payload or {}
    posture = _system_knowledge_registry_posture(reference_payload)
    branch_resolution = posture["branch_resolution"]
    main_resolution = posture["main_resolution"]
    effective_resolution = (
        main_resolution if posture["current_state"] == "CANONICAL_ON_MAIN" else branch_resolution
    )
    unknown_rows = known_unknowns(reference_payload)
    action_rows = recommended_actions(reference_payload)
    external_materialization_rows = external_registry_materialization_rows(external_index_payload)
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Preserve the audited OpenClaw machine, repo, working-copy, bridge, and ownership topology.",
        "source_basis": [
            "operator_task: OpenClaw Estate Topology Registry v0",
            "local_pc_repo: /home/openclaw",
            "local_pc_runtime_repo: /home/openclaw_external/openclaw-runtime",
            "audit_confirmed_mac_paths: Mac working copies and bridge path",
            "previous_local_audit: Codex Web registry commits unreachable from local remotes",
        ],
        "status_values": list(STATUS_VALUES),
        "required_sqlite_tables": list(REQUIRED_SQLITE_TABLES),
        "machine_count": len(machine_rows),
        "repo_working_copy_count": len(working_copy_rows),
        "actual_repo_count": len(repo_keys),
        "actual_repos": list(repo_keys),
        "machines": list(machine_rows),
        "repo_working_copies": list(working_copy_rows),
        "repo_relationships": list(repo_relationships()),
        "bridge_paths": list(bridge_paths()),
        "source_of_truth_areas": list(source_of_truth_areas(reference_payload)),
        "registry_presence": list(registry_presence(reference_payload, external_index_payload)),
        "external_registry_materialization": list(external_materialization_rows),
        "codex_web_artifacts": list(codex_web_artifacts(reference_payload)),
        "known_unknown_count": len(unknown_rows),
        "known_unknowns": list(unknown_rows),
        "recommended_actions": list(action_rows),
        "reference_resolver_summary": {
            "resolver_schema_version": reference_payload.get("schema_version", ""),
            "system_knowledge_registry_repo_ref": "openclaw-eyes",
            "system_knowledge_registry_target_ref": OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
            "system_knowledge_registry_branch": posture["effective_branch"],
            "system_knowledge_registry_current_head_commit": posture["effective_commit"],
            "system_knowledge_registry_resolution_status": effective_resolution.get(
                "resolution_status", "UNREACHABLE"
            ),
            "system_knowledge_registry_resolution_source": effective_resolution.get(
                "resolution_source", ""
            ),
            "system_knowledge_registry_current_state": posture["current_state"],
            "system_knowledge_registry_canonical_status": posture["canonical_status"],
            "system_knowledge_registry_review_target_ref": OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF,
            "system_knowledge_registry_review_branch": posture["review_branch"],
            "system_knowledge_registry_review_commit": posture["review_commit"],
            "system_knowledge_registry_review_resolution_status": branch_resolution.get(
                "resolution_status", "UNREACHABLE"
            ),
            "system_knowledge_registry_review_resolution_source": branch_resolution.get(
                "resolution_source", ""
            ),
            "system_knowledge_registry_main_target_ref": OPENCLAW_EYES_MAIN_BRANCH_TARGET_REF,
            "system_knowledge_registry_main_branch": posture["main_branch"],
            "system_knowledge_registry_main_commit": posture["main_commit"],
            "system_knowledge_registry_main_resolution_status": main_resolution.get(
                "resolution_status", "UNREACHABLE"
            ),
            "system_knowledge_registry_main_resolution_source": main_resolution.get(
                "resolution_source", ""
            ),
            "system_knowledge_registry_main_contains_review_commit": posture[
                "main_contains_review_commit"
            ],
            "system_knowledge_registry_local_status": branch_resolution.get("local_status", ""),
            "system_knowledge_registry_remote_status": branch_resolution.get("remote_status", ""),
            "system_knowledge_registry_mac_mirror_path": branch_resolution.get(
                "mac_mirror_path", ""
            ),
            "system_knowledge_registry_mac_mirror_status": branch_resolution.get(
                "mac_mirror_status", ""
            ),
            "system_knowledge_registry_mac_bridge_status": branch_resolution.get(
                "mac_bridge_status", ""
            ),
            "system_knowledge_registry_dirty_status": branch_resolution.get(
                "dirty_status", "UNKNOWN"
            ),
            "external_registry_materialized": bool(external_materialization_rows),
        },
        "topology_summary": {
            "actual_machines": ["pc", "mac"],
            "actual_repos": list(repo_keys),
            "actual_working_copies": [copy["working_copy_id"] for copy in working_copy_rows],
            "pc_backend_working_copy": "pc_openclaw_eyes_backend",
            "mac_app_working_copy": "mac_mission_control_app",
            "bridge_transport": "/mnt/e/openclaw <-> /Volumes/openclaw_e",
            "codex_web_artifacts_are_source_truth": False,
            "system_knowledge_registry_current_state": posture["current_state"],
            "system_knowledge_registry_canonical_status": posture["canonical_status"],
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _sqlite_status_check() -> str:
    quoted = ", ".join(f"'{status}'" for status in STATUS_VALUES)
    return f"CHECK(status IN ({quoted}))"


def sqlite_schema_sql() -> str:
    status_check = _sqlite_status_check()
    local_status_check = f"CHECK(local_status IN ({', '.join(f"'{status}'" for status in STATUS_VALUES)}))"
    evidence_check = f"CHECK(evidence_status IN ({', '.join(f"'{status}'" for status in STATUS_VALUES)}))"
    remote_check = f"CHECK(remote_status IN ({', '.join(f"'{status}'" for status in STATUS_VALUES)}))"
    worktree_check = f"CHECK(worktree_status IN ({', '.join(f"'{status}'" for status in STATUS_VALUES)}))"
    access_check = f"CHECK(access_status IN ({', '.join(f"'{status}'" for status in STATUS_VALUES)}))"
    return f"""CREATE TABLE machine (
    machine_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    machine_role TEXT NOT NULL,
    operating_system TEXT NOT NULL,
    evidence_status TEXT NOT NULL {evidence_check},
    notes TEXT NOT NULL
);

CREATE TABLE repo_working_copy (
    working_copy_id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES machine(machine_id),
    repo_name TEXT NOT NULL,
    repo_key TEXT NOT NULL,
    local_path TEXT NOT NULL,
    classification TEXT NOT NULL,
    worktree_status TEXT NOT NULL {worktree_check},
    clean INTEGER NOT NULL CHECK(clean IN (0, 1)),
    generated_models INTEGER NOT NULL CHECK(generated_models IN (0, 1)),
    python INTEGER NOT NULL CHECK(python IN (0, 1)),
    swift INTEGER NOT NULL CHECK(swift IN (0, 1)),
    remote TEXT NOT NULL,
    remote_status TEXT NOT NULL {remote_check},
    evidence_status TEXT NOT NULL {evidence_check},
    source_note TEXT NOT NULL
);

CREATE TABLE repo_relationship (
    relationship_id TEXT PRIMARY KEY,
    relationship_type TEXT NOT NULL,
    left_working_copy_id TEXT NOT NULL REFERENCES repo_working_copy(working_copy_id),
    right_working_copy_id TEXT NOT NULL REFERENCES repo_working_copy(working_copy_id),
    status TEXT NOT NULL {status_check},
    notes TEXT NOT NULL
);

CREATE TABLE bridge_path (
    bridge_id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL REFERENCES machine(machine_id),
    local_path TEXT NOT NULL,
    counterpart_bridge_id TEXT NOT NULL,
    access_status TEXT NOT NULL {access_check},
    evidence_status TEXT NOT NULL {evidence_check},
    notes TEXT NOT NULL
);

CREATE TABLE source_of_truth_area (
    area_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    owner_repo_key TEXT NOT NULL,
    primary_working_copy_id TEXT NOT NULL,
    secondary_working_copy_id TEXT NOT NULL,
    owner_classification TEXT NOT NULL,
    status TEXT NOT NULL {status_check},
    current_state TEXT NOT NULL {status_check},
    canonical_status TEXT NOT NULL {status_check},
    review_repo TEXT NOT NULL,
    review_branch TEXT NOT NULL,
    review_commit TEXT NOT NULL,
    ownership_rule TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE registry_presence (
    registry_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    expected_path TEXT NOT NULL,
    owning_working_copy_id TEXT NOT NULL,
    status TEXT NOT NULL {status_check},
    current_state TEXT NOT NULL {status_check},
    canonical_status TEXT NOT NULL {status_check},
    repo_name TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    commit_ref TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE external_registry_materialization (
    registry_ref TEXT PRIMARY KEY,
    canonical_owner TEXT NOT NULL,
    local_role TEXT NOT NULL,
    local_status TEXT NOT NULL {local_status_check},
    source_repo TEXT NOT NULL,
    source_branch TEXT NOT NULL,
    source_commit TEXT NOT NULL,
    artifact_count INTEGER NOT NULL,
    artifact_hashes_json TEXT NOT NULL,
    index_path TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE codex_web_artifact (
    artifact_id TEXT PRIMARY KEY,
    commit_ref TEXT NOT NULL,
    status TEXT NOT NULL {status_check},
    canonical_status TEXT NOT NULL {status_check},
    repo_name TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    source_truth INTEGER NOT NULL CHECK(source_truth IN (0, 1)),
    reason TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE known_unknown (
    unknown_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL {status_check},
    recommended_next_step TEXT NOT NULL
);

CREATE TABLE recommended_action (
    action_id TEXT PRIMARY KEY,
    priority INTEGER NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL {status_check},
    owner_hint TEXT NOT NULL,
    reason TEXT NOT NULL
);
"""


def _rows_for_sqlite(read_model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "machine": read_model["machines"],
        "repo_working_copy": [
            {
                **copy,
                "clean": _bool(copy["clean"]),
                "generated_models": _bool(copy["generated_models"]),
                "python": _bool(copy["python"]),
                "swift": _bool(copy["swift"]),
            }
            for copy in read_model["repo_working_copies"]
        ],
        "repo_relationship": read_model["repo_relationships"],
        "bridge_path": read_model["bridge_paths"],
        "source_of_truth_area": read_model["source_of_truth_areas"],
        "registry_presence": read_model["registry_presence"],
        "external_registry_materialization": read_model["external_registry_materialization"],
        "codex_web_artifact": [
            {**artifact, "source_truth": _bool(artifact["source_truth"])}
            for artifact in read_model["codex_web_artifacts"]
        ],
        "known_unknown": read_model["known_unknowns"],
        "recommended_action": read_model["recommended_actions"],
    }


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def sqlite_seed_sql(read_model: dict[str, Any]) -> str:
    statements: list[str] = []
    rows_by_table = _rows_for_sqlite(read_model)
    for table in REQUIRED_SQLITE_TABLES:
        for row in rows_by_table[table]:
            columns = list(row)
            column_sql = ", ".join(columns)
            value_sql = ", ".join(_sql_literal(row[column]) for column in columns)
            statements.append(f"INSERT INTO {table} ({column_sql}) VALUES ({value_sql});")
    return "\n".join(statements) + "\n"


def create_sqlite_registry(read_model: dict[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        rows_by_table = _rows_for_sqlite(read_model)
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                column_sql = ", ".join(columns)
                connection.execute(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    summary = read_model["reference_resolver_summary"]
    branch_line = (
        "- System knowledge registry branch is present for review and remains pending, not canonical."
    )
    if summary.get("system_knowledge_registry_current_state") == "CANONICAL_ON_MAIN":
        branch_line = (
            "- System knowledge registry is canonical on openclaw-eyes main; the review branch remains historical evidence."
        )
    elif summary.get("system_knowledge_registry_resolution_status") == "RESOLVED_REMOTE":
        branch_line = (
            "- System knowledge registry review branch resolves from the Git remote; Mac local path is optional mirror state."
        )
    elif summary.get("system_knowledge_registry_resolution_status") == "REMOTE_UNAVAILABLE":
        branch_line = "- System knowledge registry review branch is configured, but the Git remote is unavailable."
    lines = [
        "# OpenClaw Estate Topology Registry",
        "",
        "Plain Summary:",
        f"- Machines: {read_model['machine_count']} (`PC`, `Mac`).",
        f"- Working copies: {read_model['repo_working_copy_count']}.",
        f"- Actual repos: {read_model['actual_repo_count']} ({', '.join(read_model['actual_repos'])}).",
        f"- Known unknowns: {read_model['known_unknown_count']}.",
        branch_line,
        "- Older unreachable Codex Web commits remain recorded as artifacts, not source truth.",
        "",
        "Working Copies:",
    ]
    for copy in read_model["repo_working_copies"]:
        clean_label = "clean" if copy["clean"] else "dirty"
        lines.append(
            f"- `{copy['working_copy_id']}`: `{copy['classification']}` on `{copy['machine_id']}` at `{copy['local_path']}` ({clean_label})."
        )
    lines.extend(["", "Ownership Boundaries:"])
    for area in read_model["source_of_truth_areas"]:
        lines.append(
            f"- {area['display_name']}: `{area['owner_classification']}` / `{area['status']}`. {area['ownership_rule']}"
        )
    if read_model.get("external_registry_materialization"):
        lines.extend(["", "External Registry Materialization:"])
        for row in read_model["external_registry_materialization"]:
            lines.append(
                f"- `{row['registry_ref']}`: `{row['local_status']}` from `{row['source_repo']}` `{row['source_branch']}` at `{row['source_commit']}`."
            )
    lines.extend(["", "Known Unknowns:"])
    for item in read_model["known_unknowns"]:
        lines.append(f"- {item['question']}")
    lines.extend(["", "Recommended Actions:"])
    for action in sorted(read_model["recommended_actions"], key=lambda row: row["priority"]):
        lines.append(f"- {action['priority']}. {action['action']}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- This registry is documentation and generated read-model state only.",
            "- No service, account, browser, Coupa, workbook, PDF, ledger, production, or push action is performed.",
            "",
        ]
    )
    return "\n".join(lines)


def export_openclaw_estate_topology_registry(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
    reference_resolver_payload: dict[str, Any] | None = None,
) -> EstateTopologyRegistryExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)

    read_model = build_openclaw_estate_topology_registry(
        generated_at=generated_at,
        reference_resolver_payload=reference_resolver_payload,
        external_registry_index_payload=_load_external_registry_index(read_model_root=read_root),
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME

    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(read_model), encoding="utf-8")
    create_sqlite_registry(read_model, sqlite_path)

    return EstateTopologyRegistryExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        machine_count=read_model["machine_count"],
        repo_working_copy_count=read_model["repo_working_copy_count"],
        actual_repo_count=read_model["actual_repo_count"],
        known_unknown_count=read_model["known_unknown_count"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw estate topology registry read-model.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_estate_topology_registry(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
    )
    if args.format == "json":
        payload = json.loads(_rooted(result.json_path).read_text(encoding="utf-8"))
        print(stable_json(payload), end="")
    elif args.format == "operator":
        print(_rooted(result.operator_path).read_text(encoding="utf-8"), end="")
    else:
        print(f"OpenClaw Estate Topology Registry: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- SQLite: `{result.sqlite_path}`")
        print(f"- Machines: {result.machine_count}")
        print(f"- Working copies: {result.repo_working_copy_count}")
        print(f"- Actual repos: {result.actual_repo_count}")
        print(f"- Known unknowns: {result.known_unknown_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
