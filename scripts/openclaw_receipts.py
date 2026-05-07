#!/usr/bin/env python3
"""Read-only OpenClaw receipt commands for low-context repo proof snapshots."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path("/home/openclaw")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_sensitive_policy import (
    PathPolicyFinding,
    broad_source_set_prefix_findings,
    is_under,
    normalize_repo_path,
    packet06_final_static_boundary_contract,
    path_policy_findings,
    sensitive_root_contract,
)


CANONICAL_RECEIPT_COMMAND = "./scripts/openclaw_receipts.py"

PACKET_ROOT_RELATIVE_PATH = Path("docs/planning/project_packets")
PACKET_ARCHIVE_ROOT_RELATIVE_PATH = Path("docs/planning/project_packets_archive")
PACKET_INDEX_RELATIVE_PATH = PACKET_ROOT_RELATIVE_PATH / "README.md"

PACKET06_RELATIVE_PATH = PACKET_ROOT_RELATIVE_PATH / (
    "06_OPERATOR_HARNESS_ACTOR_EFFICIENCY_AND_SENSITIVE_WORKFLOWS"
)
PACKET06_ARCHIVE_RELATIVE_PATH = PACKET_ARCHIVE_ROOT_RELATIVE_PATH / (
    "06_OPERATOR_HARNESS_ACTOR_EFFICIENCY_AND_SENSITIVE_WORKFLOWS_SNAPSHOT"
)
PACKET07_RELATIVE_PATH = PACKET_ROOT_RELATIVE_PATH / (
    "07_OPERATOR_HARNESS_PROMPT_DOCTRINE_AND_GATED_ACTIVATION"
)

ACTIVE_PACKET_RELATIVE_PATH = PACKET07_RELATIVE_PATH
ACTIVE_HANDOFF_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / "00_ACTIVE_HANDOFF.md"
ACTIVE_RAILS_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / "24_files"

PACKET06_REQUIRED_RAIL_FILES = (
    "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
    "02_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md",
    "03_CORE_ARCHITECTURE_PRINCIPLES.md",
    "04_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md",
    "05_OPERATOR_NORTH_STAR_MACHINE_CONTRACT.md",
    "06_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md",
    "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
    "08_BACKEND_DATA_CONTRACT_AND_SCHEMA_TRUTH.md",
    "09_BACKEND_REPOSITORY_AND_RUNTIME_TRUTH.md",
    "10_CONTEXT_SUBSTRATE_AND_TRAVERSAL_TRUTH.md",
    "11_ACTOR_REGISTRY_AND_TRUST_BRIDGE_TRUTH.md",
    "12_STORAGE_INTELLIGENCE_AND_AUTHORIZATION.md",
    "13_PERFORMANCE_DIRECTOR_SHOW_MAP_TRUTH.md",
    "14_CLI_RECEIPT_LAYER_AND_LOW_CONTEXT_INTERFACE.md",
    "15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md",
    "16_INVOICE_ARTIFACT_AND_BILLING_BRIDGE_PLAN.md",
    "17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md",
    "18_OPERATOR_HARNESS_READ_MODEL_PLAN.md",
    "19_LEGAL_CONTEXT_EXPORT_POLICY_PLAN.md",
    "20_RUNTIME_INTEGRATION_AND_RECOVERY_ARCHITECTURE.md",
    "21_MCP_SHARED_MEMORY_ARCHITECTURE_REVIEW.md",
    "22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md",
    "23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md",
    "24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md",
)

PACKET07_REQUIRED_RAIL_FILES = (
    "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
    "02_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md",
    "03_CORE_ARCHITECTURE_PRINCIPLES.md",
    "04_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md",
    "05_OPERATOR_NORTH_STAR_MACHINE_CONTRACT.md",
    "06_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md",
    "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
    "08_BACKEND_DATA_CONTRACT_AND_SCHEMA_TRUTH.md",
    "09_BACKEND_REPOSITORY_AND_RUNTIME_TRUTH.md",
    "10_CONTEXT_SUBSTRATE_AND_TRAVERSAL_TRUTH.md",
    "11_ACTOR_REGISTRY_AND_TRUST_BRIDGE_TRUTH.md",
    "12_STORAGE_INTELLIGENCE_AND_AUTHORIZATION.md",
    "13_PERFORMANCE_DIRECTOR_SHOW_MAP_TRUTH.md",
    "14_MODEL_AND_TOOL_SPECIFIC_PROMPT_DOCTRINE.md",
    "15_RECEIPT_LAYER_AND_OPERATOR_READ_MODEL_V1.md",
    "16_SENSITIVE_ROOT_AND_LEGAL_EXPORT_BOUNDARIES.md",
    "17_INVOICE_ARTIFACT_AND_BILLING_BRIDGE_BOUNDARIES.md",
    "18_ACTOR_CONTEXT_EXPORT_AND_NO_ECHO_HARDENING.md",
    "19_GATED_ACTIVATION_READINESS_MAP.md",
    "20_RUNTIME_AUTHORITY_AND_LEGACY_GATING_PLAN.md",
    "21_RUNTIME_INTEGRATION_AND_RECOVERY_ACTIVATION_PLAN.md",
    "22_MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md",
    "23_BROAD_SOURCE_SET_EXCLUSION_AND_PACKET_RENEWAL_GUARD.md",
    "24_VISIBLE_ROAD_BIG_STRIDES_AND_RENEWAL_DISCIPLINE.md",
)

REQUIRED_RAIL_FILES = PACKET07_REQUIRED_RAIL_FILES

PACKET_REQUIRED_RAILS = {
    PACKET06_RELATIVE_PATH.name: PACKET06_REQUIRED_RAIL_FILES,
    PACKET07_RELATIVE_PATH.name: PACKET07_REQUIRED_RAIL_FILES,
}

PACKET_KEY_RAILS = {
    PACKET06_RELATIVE_PATH.name: (
        "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
        "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
        "14_CLI_RECEIPT_LAYER_AND_LOW_CONTEXT_INTERFACE.md",
        "15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md",
        "17_ACTOR_SIDECAR_AND_CONTEXT_EXPORT_HARDENING_PLAN.md",
        "18_OPERATOR_HARNESS_READ_MODEL_PLAN.md",
        "20_RUNTIME_INTEGRATION_AND_RECOVERY_ARCHITECTURE.md",
        "22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md",
        "23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md",
        "24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md",
    ),
    PACKET07_RELATIVE_PATH.name: (
        "01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
        "07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md",
        "14_MODEL_AND_TOOL_SPECIFIC_PROMPT_DOCTRINE.md",
        "15_RECEIPT_LAYER_AND_OPERATOR_READ_MODEL_V1.md",
        "19_GATED_ACTIVATION_READINESS_MAP.md",
        "20_RUNTIME_AUTHORITY_AND_LEGACY_GATING_PLAN.md",
        "21_RUNTIME_INTEGRATION_AND_RECOVERY_ACTIVATION_PLAN.md",
        "22_MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md",
        "23_BROAD_SOURCE_SET_EXCLUSION_AND_PACKET_RENEWAL_GUARD.md",
        "24_VISIBLE_ROAD_BIG_STRIDES_AND_RENEWAL_DISCIPLINE.md",
    ),
}

KEY_RAIL_FILES = PACKET_KEY_RAILS[PACKET07_RELATIVE_PATH.name]

PROMPT_DOCTRINE_RAIL = "14_MODEL_AND_TOOL_SPECIFIC_PROMPT_DOCTRINE.md"
GATED_ACTIVATION_RAILS = (
    "16_SENSITIVE_ROOT_AND_LEGAL_EXPORT_BOUNDARIES.md",
    "17_INVOICE_ARTIFACT_AND_BILLING_BRIDGE_BOUNDARIES.md",
    "19_GATED_ACTIVATION_READINESS_MAP.md",
    "20_RUNTIME_AUTHORITY_AND_LEGACY_GATING_PLAN.md",
    "21_RUNTIME_INTEGRATION_AND_RECOVERY_ACTIVATION_PLAN.md",
    "22_MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md",
    "23_BROAD_SOURCE_SET_EXCLUSION_AND_PACKET_RENEWAL_GUARD.md",
)

@dataclass(frozen=True)
class GitCommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ChangedFile:
    status: str
    path: str


def _run_git(root: Path, args: Sequence[str]) -> GitCommandResult:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return GitCommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _first_line(text: str) -> str:
    return text.splitlines()[0] if text.splitlines() else ""


def _clean_git_path(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            parsed = ast.literal_eval(cleaned)
        except (SyntaxError, ValueError):
            return cleaned.strip('"')
        if isinstance(parsed, str):
            return parsed
    return cleaned


def parse_porcelain_status(output: str) -> list[ChangedFile]:
    changed: list[ChangedFile] = []
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2].strip() or line[:2]
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            old_path, new_path = raw_path.split(" -> ", 1)
            changed.append(ChangedFile(status=status, path=_clean_git_path(old_path)))
            changed.append(ChangedFile(status=status, path=_clean_git_path(new_path)))
            continue
        changed.append(ChangedFile(status=status, path=_clean_git_path(raw_path)))
    return changed


def changed_files(root: Path = ROOT) -> tuple[ChangedFile, ...]:
    result = _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return tuple(parse_porcelain_status(result.stdout))


def _active_packet_from_index(index_text: str) -> Path | None:
    in_active_section = False
    for line in index_text.splitlines():
        stripped = line.strip()
        if stripped == "## Active Packet":
            in_active_section = True
            continue
        if in_active_section and stripped.startswith("## "):
            return None
        if not in_active_section or not stripped.startswith("- `"):
            continue

        start = stripped.find("`")
        end = stripped.find("`", start + 1)
        if start == -1 or end == -1:
            continue
        candidate = stripped[start + 1 : end].strip().rstrip("/")
        if not candidate or "/24_files/" in candidate or candidate.endswith(".md"):
            continue
        if candidate.startswith(str(PACKET_ROOT_RELATIVE_PATH).replace("\\", "/") + "/"):
            packet_path = Path(candidate)
        else:
            packet_path = PACKET_ROOT_RELATIVE_PATH / candidate
        if packet_path.parent == PACKET_ROOT_RELATIVE_PATH:
            return packet_path
    return None


def _target_packet_path(target: str | None, index_text: str) -> Path:
    if target in (None, "", "active", "current"):
        return _active_packet_from_index(index_text) or ACTIVE_PACKET_RELATIVE_PATH
    normalized = target.strip().rstrip("/")
    if normalized.startswith(str(PACKET_ROOT_RELATIVE_PATH).replace("\\", "/") + "/"):
        return Path(normalized)
    return PACKET_ROOT_RELATIVE_PATH / normalized


def _markdown_files(path: Path) -> tuple[str, ...]:
    if not path.is_dir():
        return ()
    return tuple(
        sorted(
            child.name
            for child in path.iterdir()
            if child.is_file() and child.suffix == ".md"
        )
    )


def _packet06_archive_status(root: Path) -> dict[str, object]:
    archive_dir = root / PACKET06_ARCHIVE_RELATIVE_PATH
    handoff = archive_dir / "00_ACTIVE_HANDOFF.md"
    rails_dir = archive_dir / "24_files"
    rails = _markdown_files(rails_dir)
    missing = tuple(name for name in PACKET06_REQUIRED_RAIL_FILES if name not in rails)
    extra = tuple(name for name in rails if name not in PACKET06_REQUIRED_RAIL_FILES)
    preserved = (
        archive_dir.is_dir()
        and handoff.is_file()
        and rails_dir.is_dir()
        and len(rails) == 24
        and not missing
        and not extra
    )
    return {
        "path": str(PACKET06_ARCHIVE_RELATIVE_PATH),
        "dir_present": archive_dir.is_dir(),
        "handoff_present": handoff.is_file(),
        "rails_dir_present": rails_dir.is_dir(),
        "rail_count": len(rails),
        "missing_rails": missing,
        "extra_rails": extra,
        "preserved": preserved,
    }


def docs_only_guard_report(
    files: Iterable[ChangedFile],
    *,
    allowed_prefixes: Sequence[str],
    root: Path = ROOT,
) -> dict[str, object]:
    normalized_allowed = tuple(
        normalize_repo_path(prefix, root)[0].rstrip("/") for prefix in allowed_prefixes
    )
    changed = tuple(files)
    changed_paths = tuple(item.path for item in changed)
    private_findings = path_policy_findings(changed_paths, root=root)
    broad_allowed_prefixes = broad_source_set_prefix_findings(
        normalized_allowed,
        root=root,
    )
    outside_allowed = tuple(
        item.path
        for item in changed
        if normalized_allowed
        and not any(
            is_under(normalize_repo_path(item.path, root)[0], prefix)
            for prefix in normalized_allowed
        )
    )

    return {
        "receipt_type": "openclaw.docs_only_guard",
        "mode": "read-only/static-path-policy",
        "allowed_prefixes": normalized_allowed,
        "broad_allowed_prefixes": broad_allowed_prefixes,
        "changed_files": changed,
        "private_findings": private_findings,
        "outside_allowed": outside_allowed,
        "passed": not private_findings and not outside_allowed and not broad_allowed_prefixes,
    }


def packet_status(root: Path = ROOT, target: str | None = None) -> dict[str, object]:
    packet_index = root / PACKET_INDEX_RELATIVE_PATH
    index_text = packet_index.read_text(encoding="utf-8") if packet_index.is_file() else ""
    active_packet = _active_packet_from_index(index_text)
    target_packet = _target_packet_path(target, index_text)
    packet_dir = root / target_packet
    handoff = packet_dir / "00_ACTIVE_HANDOFF.md"
    rails_dir = packet_dir / "24_files"

    existing_rails = _markdown_files(rails_dir)
    required_rails = PACKET_REQUIRED_RAILS.get(target_packet.name, ())
    key_rail_names = PACKET_KEY_RAILS.get(target_packet.name, ())
    missing_rails = tuple(name for name in required_rails if name not in existing_rails)
    extra_rails = tuple(name for name in existing_rails if name not in required_rails)
    key_rails = {name: (rails_dir / name).is_file() for name in key_rail_names}

    handoff_first_line = _first_line(handoff.read_text(encoding="utf-8")) if handoff.is_file() else ""
    target_is_active = active_packet == target_packet
    archive = _packet06_archive_status(root)

    return {
        "receipt_type": "openclaw.packet_status",
        "mode": "read-only/exact-packet-paths",
        "target_packet": str(target_packet),
        "active_packet": str(active_packet) if active_packet else "",
        "target_is_active": target_is_active,
        "packet_index_present": packet_index.is_file(),
        "packet_index_points_to_active": target_is_active,
        "packet_index_active_parseable": active_packet is not None,
        "packet_dir_present": packet_dir.is_dir(),
        "handoff_present": handoff.is_file(),
        "handoff_first_line": handoff_first_line,
        "rails_dir_present": rails_dir.is_dir(),
        "rail_count": len(existing_rails),
        "missing_rails": missing_rails,
        "extra_rails": extra_rails,
        "key_rails": key_rails,
        "packet06_archive": archive,
        "passed": (
            packet_index.is_file()
            and target_is_active
            and active_packet is not None
            and packet_dir.is_dir()
            and handoff.is_file()
            and rails_dir.is_dir()
            and len(existing_rails) == 24
            and len(required_rails) == 24
            and not missing_rails
            and not extra_rails
            and all(key_rails.values())
            and bool(archive["preserved"])
        ),
    }


def repo_check_receipt(root: Path = ROOT) -> dict[str, object]:
    status = _run_git(root, ["status", "-sb", "--untracked-files=all"])
    head = _run_git(root, ["--no-pager", "log", "--oneline", "-1"])
    diff_check = _run_git(root, ["diff", "--check"])
    cached_diff_check = _run_git(root, ["diff", "--cached", "--check"])
    packet = packet_status(root)
    changed = parse_porcelain_status(
        _run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout
    )

    return {
        "receipt_type": "openclaw.repo_check",
        "mode": "read-only/git-and-exact-packet-paths",
        "root": str(root),
        "canonical_command": CANONICAL_RECEIPT_COMMAND,
        "branch_status": _first_line(status.stdout),
        "head": _first_line(head.stdout),
        "worktree_clean": not changed,
        "changed_file_count": len(changed),
        "diff_check_passed": diff_check.returncode == 0,
        "cached_diff_check_passed": cached_diff_check.returncode == 0,
        "packet_status_passed": bool(packet["passed"]),
        "git_failures": tuple(
            name
            for name, result in (
                ("status", status),
                ("head", head),
                ("diff_check", diff_check),
                ("cached_diff_check", cached_diff_check),
            )
            if result.returncode != 0
        ),
        "passed": (
            status.returncode == 0
            and head.returncode == 0
            and diff_check.returncode == 0
            and cached_diff_check.returncode == 0
            and bool(packet["passed"])
        ),
    }


def _active_rails_dir_from_packet(report: dict[str, object], root: Path) -> Path:
    return root / Path(str(report["target_packet"])) / "24_files"


def _read_rail_text(rails_dir: Path, name: str) -> str:
    path = rails_dir / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def prompt_doctrine_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    rails_dir = _active_rails_dir_from_packet(packet, root)
    rail_path = rails_dir / PROMPT_DOCTRINE_RAIL
    text = _read_rail_text(rails_dir, PROMPT_DOCTRINE_RAIL)

    checks = {
        "file14_present": rail_path.is_file(),
        "gemini_planning_profile_present": (
            "Gemini planning/audit prompts" in text
            and "READY/NOT_READY" in text
            and "Gemini plans are not automatic execution authority" in text
        ),
        "codex_implementation_profile_present": (
            "Codex implementation prompts" in text
            and "bounded repo mutation" in text
            and "produce reviewable diffs" in text
        ),
        "review_prompt_split_present": (
            "Gemini review:" in text
            and "Codex review:" in text
            and "commit readiness" in text
        ),
        "non_generic_prompting_doctrine_present": (
            "generic forbiddance" in text
            and "Guard the real risks" in text
            and "actual strengths and failure modes" in text
        ),
    }

    return {
        "receipt_type": "openclaw.prompt_doctrine_status",
        "mode": "read-only/exact-packet07-rail",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "authority_note": "This receipt checks prompt doctrine presence; it does not generate prompts.",
        "mutates_files": False,
        "generates_prompts": False,
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def gated_activation_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    rails_dir = _active_rails_dir_from_packet(packet, root)
    rail_texts = {
        name: _read_rail_text(rails_dir, name)
        for name in GATED_ACTIVATION_RAILS
    }
    combined_text = "\n".join(rail_texts.values())

    checks = {
        "gated_activation_rail_present": bool(
            rail_texts["19_GATED_ACTIVATION_READINESS_MAP.md"]
        ),
        "runtime_activation_not_authorized": (
            "No live service launch" in combined_text
            and "does not authorize live runtime launch" in combined_text
        ),
        "mcp_hidden_authority_blocked": (
            "No MCP invocation" in combined_text
            and "No hidden memory writes" in combined_text
            and "hidden authority" in combined_text
        ),
        "invoice_legal_private_root_activation_gated": (
            "Do not generate final invoices" in combined_text
            and "No legal-private content reads" in combined_text
            and "No private-root inspection" in combined_text
        ),
        "broad_source_set_laundering_blocked": (
            "No broad filesystem crawling" in combined_text
            and "No path-metadata-as-authority" in combined_text
            and "No source-set generation from hidden chat memory" in combined_text
        ),
    }

    return {
        "receipt_type": "openclaw.gated_activation_status",
        "mode": "read-only/static-activation-boundaries",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "authority_note": "Readiness evidence is not activation approval.",
        "runtime_activation_authorized": False,
        "receipt_grants_execution_authority": False,
        "mcp_hidden_memory_write_authorized": False,
        "invoice_legal_private_root_activation_authorized": False,
        "filesystem_inspected": False,
        "runtime_launched": False,
        "provider_or_model_called": False,
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_harness_read_model(
    *,
    root: Path = ROOT,
    files: Sequence[ChangedFile] | None = None,
) -> dict[str, object]:
    changed = tuple(files) if files is not None else changed_files(root)
    changed_paths = tuple(item.path for item in changed)
    private_findings = path_policy_findings(changed_paths, root=root)
    packet = packet_status(root)
    prompt_doctrine = prompt_doctrine_status(root)
    gated_activation = gated_activation_status(root)
    sensitive_contract = sensitive_root_contract()
    final_contract = packet06_final_static_boundary_contract()
    status = _run_git(root, ["status", "-sb", "--untracked-files=all"])
    head = _run_git(root, ["--no-pager", "log", "--oneline", "-1"])
    invoice_artifact = final_contract["invoice_artifact"]
    legal_context_export = final_contract["legal_context_export"]
    runtime_gating = final_contract["runtime_and_legacy_gating"]
    source_set_exclusion = final_contract["source_set_exclusion"]
    mcp_shared_memory = final_contract["mcp_shared_memory"]

    return {
        "receipt_type": "openclaw.operator_harness_read_model",
        "mode": "read-only/low-context",
        "authority_note": "Receipts are proof snapshots; File 01 remains roadmap authority.",
        "cards": (
            {
                "card": "command_surface",
                "canonical_command": CANONICAL_RECEIPT_COMMAND,
                "read_only": True,
                "write_capable": False,
            },
            {
                "card": "repo",
                "branch_status": _first_line(status.stdout),
                "head": _first_line(head.stdout),
                "changed_file_count": len(changed),
                "private_path_policy": "blocked" if private_findings else "clear",
            },
            {
                "card": "packet",
                "target_packet": packet["target_packet"],
                "active_packet": packet["active_packet"],
                "target_is_active": packet["target_is_active"],
                "rail_count": packet["rail_count"],
                "packet_status": "present" if packet["passed"] else "review",
                "roadmap_authority": "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
            },
            {
                "card": "packet06_archive",
                "path": packet["packet06_archive"]["path"],
                "preserved": packet["packet06_archive"]["preserved"],
                "rail_count": packet["packet06_archive"]["rail_count"],
                "handoff_present": packet["packet06_archive"]["handoff_present"],
            },
            {
                "card": "active_handoff",
                "present": packet["handoff_present"],
                "first_line": packet["handoff_first_line"],
                "roadmap_authority": "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md",
                "is_roadmap_authority": False,
            },
            {
                "card": "sensitive_root_policy",
                "contract_mode": sensitive_contract["mode"],
                "path_policy_only": sensitive_contract["path_policy_only"],
                "content_access_allowed": sensitive_contract["content_access_allowed"],
                "filesystem_inspected": sensitive_contract["filesystem_inspected"],
            },
            {
                "card": "prompt_doctrine",
                "passed": prompt_doctrine["passed"],
                "generates_prompts": prompt_doctrine["generates_prompts"],
                "mutates_files": prompt_doctrine["mutates_files"],
                **prompt_doctrine["checks"],
            },
            {
                "card": "gated_activation",
                "passed": gated_activation["passed"],
                "runtime_activation_authorized": gated_activation[
                    "runtime_activation_authorized"
                ],
                "receipt_grants_execution_authority": gated_activation[
                    "receipt_grants_execution_authority"
                ],
                "mcp_hidden_memory_write_authorized": gated_activation[
                    "mcp_hidden_memory_write_authorized"
                ],
                "invoice_legal_private_root_activation_authorized": gated_activation[
                    "invoice_legal_private_root_activation_authorized"
                ],
                "filesystem_inspected": gated_activation["filesystem_inspected"],
                "runtime_launched": gated_activation["runtime_launched"],
                "provider_or_model_called": gated_activation[
                    "provider_or_model_called"
                ],
            },
            {
                "card": "invoice_artifact",
                "draft_only": invoice_artifact["draft_only"],
                "approval_before_send_required": invoice_artifact[
                    "approval_before_send_required"
                ],
                "invoice_generation_allowed": invoice_artifact[
                    "invoice_generation_allowed"
                ],
                "invoice_send_allowed": invoice_artifact["invoice_send_allowed"],
                "invoice_reconciliation_authority": invoice_artifact[
                    "invoice_reconciliation_authority"
                ],
                "private_finance_access_allowed": invoice_artifact[
                    "private_finance_access_allowed"
                ],
            },
            {
                "card": "legal_context_export",
                "metadata_only": legal_context_export["metadata_only"],
                "blocked_source_refs_only": legal_context_export[
                    "blocked_source_refs_only"
                ],
                "content_access_allowed": legal_context_export[
                    "content_access_allowed"
                ],
                "private_legal_root_inspection_allowed": legal_context_export[
                    "private_legal_root_inspection_allowed"
                ],
                "outside_model_access_allowed": legal_context_export[
                    "outside_model_access_allowed"
                ],
                "no_echo_required": legal_context_export["no_echo_required"],
            },
            {
                "card": "source_set_exclusion",
                "broad_scan_used": False,
                "broad_preload_allowed": source_set_exclusion["broad_preload_allowed"],
                "broad_source_set_authority": source_set_exclusion[
                    "broad_source_set_authority"
                ],
                "path_metadata_is_authority": source_set_exclusion[
                    "path_metadata_is_authority"
                ],
                "private_root_inspection_used": False,
                "packet07_carry_forward_constraint": source_set_exclusion[
                    "packet07_carry_forward_constraint"
                ],
                "withheld_surfaces": (
                    "private roots",
                    "secrets/env/credentials",
                    "legal/client/private folders",
                    "runtime/provider/billing surfaces",
                ),
            },
            {
                "card": "runtime_authority",
                "static_review_only": runtime_gating["static_review_only"],
                "live_service_inspection_used": runtime_gating[
                    "live_service_launch_allowed"
                ],
                "runtime_mutation_allowed": runtime_gating["runtime_mutation_allowed"],
                "process_scan_allowed": runtime_gating["process_scan_allowed"],
                "legacy_bypass_allowed": runtime_gating["legacy_bypass_allowed"],
                "receipt_grants_execution": False,
                "static_review_pointer": "service_inventory_audit.py",
            },
            {
                "card": "recovery",
                "runtime_launched": False,
                "self_authorizing": False,
                "static_review_pointer": "tests/test_chief_listener_lifecycle.py",
            },
            {
                "card": "mcp_shared_memory",
                "external_mcp_calls_allowed": mcp_shared_memory[
                    "external_mcp_calls_allowed"
                ],
                "external_mcp_calls_used": False,
                "hidden_memory_writes_allowed": mcp_shared_memory[
                    "hidden_canonical_memory_writes_allowed"
                ],
                "receipts_are_execution_authority": mcp_shared_memory[
                    "receipts_are_execution_authority"
                ],
                "shared_memory_is_roadmap_authority": mcp_shared_memory[
                    "shared_memory_is_roadmap_authority"
                ],
            },
            {
                "card": "packet07_carry_forward",
                "read_from_handoff_before_renewal": True,
                "receipt_is_roadmap_authority": False,
                "constraints": final_contract["packet07_carry_forward"],
            },
        ),
        "private_findings": private_findings,
        "passed": (
            bool(packet["passed"])
            and bool(prompt_doctrine["passed"])
            and bool(gated_activation["passed"])
            and not private_findings
        ),
    }


def _print_scalar_lines(title: str, rows: Iterable[tuple[str, object]]) -> None:
    print(f"# {title}")
    for key, value in rows:
        print(f"{key}: {value}")


def _print_list(name: str, values: Iterable[object]) -> None:
    print(f"{name}:")
    items = list(values)
    if not items:
        print("- none")
        return
    for value in items:
        print(f"- {value}")


def _redacted_path(path: str, findings: Sequence[PathPolicyFinding]) -> str:
    if any(finding.path == path for finding in findings):
        return "<withheld_by_static_path_policy>"
    return path


def _redacted_match(finding: PathPolicyFinding) -> str:
    if finding.finding == "outside_repo_or_parent_escape":
        return "<withheld_by_static_path_policy>"
    return finding.matched


def print_packet_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Packet Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("target_is_active", report["target_is_active"]),
            ("packet_index_present", report["packet_index_present"]),
            ("packet_index_points_to_active", report["packet_index_points_to_active"]),
            ("packet_index_active_parseable", report["packet_index_active_parseable"]),
            ("packet_dir_present", report["packet_dir_present"]),
            ("handoff_present", report["handoff_present"]),
            ("rails_dir_present", report["rails_dir_present"]),
            ("rail_count", report["rail_count"]),
            ("passed", report["passed"]),
        ),
    )
    print(f"handoff_first_line: {report['handoff_first_line']}")
    _print_list("missing_rails", report["missing_rails"])
    _print_list("extra_rails", report["extra_rails"])
    print("key_rails:")
    for name, present in report["key_rails"].items():
        print(f"- {name}: {present}")
    archive = report["packet06_archive"]
    print("packet06_archive:")
    for key in (
        "path",
        "dir_present",
        "handoff_present",
        "rails_dir_present",
        "rail_count",
        "preserved",
    ):
        print(f"- {key}: {archive[key]}")
    for key in ("missing_rails", "extra_rails"):
        print(f"- {key}:")
        values = list(archive[key])
        if not values:
            print("  - none")
            continue
        for value in values:
            print(f"  - {value}")


def print_repo_check(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Repo Check Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("root", report["root"]),
            ("canonical_command", report["canonical_command"]),
            ("branch_status", report["branch_status"]),
            ("head", report["head"]),
            ("worktree_clean", report["worktree_clean"]),
            ("changed_file_count", report["changed_file_count"]),
            ("diff_check_passed", report["diff_check_passed"]),
            ("cached_diff_check_passed", report["cached_diff_check_passed"]),
            ("packet_status_passed", report["packet_status_passed"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("git_failures", report["git_failures"])


def print_changed_files_receipt(files: Sequence[ChangedFile], findings: Sequence[PathPolicyFinding]) -> None:
    _print_scalar_lines(
        "OpenClaw Changed Files Receipt",
        (
            ("receipt_type", "openclaw.changed_files"),
            ("mode", "read-only/git-status-and-static-path-policy"),
            ("changed_file_count", len(files)),
            ("private_path_policy", "blocked" if findings else "clear"),
        ),
    )
    print("changed_files:")
    if not files:
        print("- none")
    for item in files:
        print(f"- {item.status} {_redacted_path(item.path, findings)}")
    print_findings(findings)


def print_findings(findings: Sequence[PathPolicyFinding]) -> None:
    print("path_policy_findings:")
    if not findings:
        print("- none")
        return
    for finding in findings:
        print(f"- <withheld_by_static_path_policy>: {finding.finding} ({_redacted_match(finding)})")


def print_no_private_root_check(paths: Sequence[str], findings: Sequence[PathPolicyFinding]) -> None:
    _print_scalar_lines(
        "OpenClaw No Private Root Check Receipt",
        (
            ("receipt_type", "openclaw.no_private_root_check"),
            ("mode", "read-only/path-strings-only"),
            ("path_policy_only", True),
            ("filesystem_inspected", False),
            ("content_accessed", False),
            ("path_count", len(paths)),
            ("passed", not findings),
        ),
    )
    print_findings(findings)


def print_docs_only_guard(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Docs-Only Guard Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("allowed_prefixes", report["allowed_prefixes"])
    _print_list("broad_allowed_prefixes", report["broad_allowed_prefixes"])
    print("changed_files:")
    for item in report["changed_files"]:
        print(f"- {item.status} {_redacted_path(item.path, report['private_findings'])}")
    _print_list(
        "outside_allowed",
        (
            _redacted_path(path, report["private_findings"])
            for path in report["outside_allowed"]
        ),
    )
    print_findings(report["private_findings"])


def print_sensitive_root_contract(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Sensitive Root Static Contract Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("content_access_allowed", report["content_access_allowed"]),
            ("path_policy_only", report["path_policy_only"]),
            ("filesystem_inspected", report["filesystem_inspected"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("registry_fields", report["registry_fields"])
    _print_list("quarantine_states", report["quarantine_states"])
    print("quarantine_intake_contract:")
    for key, value in report["quarantine_intake_contract"].items():
        print(f"- {key}: {value}")
    _print_list("forbidden_actions", report["forbidden_actions"])


def print_prompt_doctrine_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Prompt Doctrine Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("authority_note", report["authority_note"]),
            ("mutates_files", report["mutates_files"]),
            ("generates_prompts", report["generates_prompts"]),
            ("passed", report["passed"]),
        ),
    )
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_gated_activation_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Gated Activation Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("authority_note", report["authority_note"]),
            ("runtime_activation_authorized", report["runtime_activation_authorized"]),
            (
                "receipt_grants_execution_authority",
                report["receipt_grants_execution_authority"],
            ),
            (
                "mcp_hidden_memory_write_authorized",
                report["mcp_hidden_memory_write_authorized"],
            ),
            (
                "invoice_legal_private_root_activation_authorized",
                report["invoice_legal_private_root_activation_authorized"],
            ),
            ("filesystem_inspected", report["filesystem_inspected"]),
            ("runtime_launched", report["runtime_launched"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("passed", report["passed"]),
        ),
    )
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_harness_read_model(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Harness Read Model Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("authority_note", report["authority_note"]),
            ("passed", report["passed"]),
        ),
    )
    print("cards:")
    for card in report["cards"]:
        print(f"- {card['card']}:")
        for key, value in card.items():
            if key == "card":
                continue
            print(f"  {key}: {value}")
    print_findings(report["private_findings"])


def _paths_from_args_or_changes(args: argparse.Namespace, root: Path) -> tuple[str, ...]:
    paths = tuple(args.paths or ())
    if args.from_changed_files or not paths:
        paths = tuple(item.path for item in changed_files(root))
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CANONICAL_RECEIPT_COMMAND,
        description="Read-only OpenClaw proof receipts.",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("repo-check", help="Print git and active-packet proof receipt.")
    subparsers.add_parser("changed-files-receipt", help="Print changed files with static path policy.")
    packet_status_parser = subparsers.add_parser(
        "packet-status",
        help="Print active packet status receipt.",
    )
    packet_status_parser.add_argument(
        "target",
        nargs="?",
        help="Optional packet folder name; default is the active packet from the packet index.",
    )

    docs_guard = subparsers.add_parser(
        "docs-only-guard",
        help="Fail if changed files leave allowed prefixes.",
    )
    docs_guard.add_argument(
        "--allowed",
        action="append",
        required=True,
        help="Allowed repo-relative path or prefix. Repeat for multiple prefixes.",
    )

    private_check = subparsers.add_parser(
        "no-private-root-check",
        help="Check path strings against private/sensitive deny policy.",
    )
    private_check.add_argument("paths", nargs="*", help="Path strings to check.")
    private_check.add_argument(
        "--from-changed-files",
        action="store_true",
        help="Check current git changed-file paths.",
    )

    subparsers.add_parser(
        "sensitive-root-contract",
        help="Print metadata-only Sensitive Root Registry static contract.",
    )
    subparsers.add_parser(
        "operator-harness-status",
        help="Print low-context read-only operator harness receipt cards.",
    )
    subparsers.add_parser(
        "prompt-doctrine-status",
        help="Print Packet 07 model/tool-specific prompt doctrine status.",
    )
    subparsers.add_parser(
        "gated-activation-status",
        help="Print Packet 07 gated activation boundary status.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root

    if args.command == "repo-check":
        report = repo_check_receipt(root)
        print_repo_check(report)
        return 0 if report["passed"] else 1
    if args.command == "changed-files-receipt":
        files = changed_files(root)
        findings = path_policy_findings((item.path for item in files), root=root)
        print_changed_files_receipt(files, findings)
        return 0 if not findings else 1
    if args.command == "packet-status":
        report = packet_status(root, target=args.target)
        print_packet_status(report)
        return 0 if report["passed"] else 1
    if args.command == "docs-only-guard":
        report = docs_only_guard_report(
            changed_files(root),
            allowed_prefixes=tuple(args.allowed),
            root=root,
        )
        print_docs_only_guard(report)
        return 0 if report["passed"] else 1
    if args.command == "no-private-root-check":
        paths = _paths_from_args_or_changes(args, root)
        findings = path_policy_findings(paths, root=root)
        print_no_private_root_check(paths, findings)
        return 0 if not findings else 1
    if args.command == "sensitive-root-contract":
        report = sensitive_root_contract()
        print_sensitive_root_contract(report)
        return 0
    if args.command == "operator-harness-status":
        report = operator_harness_read_model(root=root)
        print_operator_harness_read_model(report)
        return 0 if report["passed"] else 1
    if args.command == "prompt-doctrine-status":
        report = prompt_doctrine_status(root=root)
        print_prompt_doctrine_status(report)
        return 0 if report["passed"] else 1
    if args.command == "gated-activation-status":
        report = gated_activation_status(root=root)
        print_gated_activation_status(report)
        return 0 if report["passed"] else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
