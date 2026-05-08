#!/usr/bin/env python3
"""Read-only OpenClaw receipt commands for low-context repo proof snapshots."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
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
from operator_intent_core import (
    FORBIDDEN_ACTIONS as OPERATOR_INTENT_CORE_FORBIDDEN_ACTIONS,
    INTENT_CLASSES as OPERATOR_INTENT_CORE_REQUIRED_INTENTS,
    classify_operator_intent,
    classify_phrase_matrix,
    frame_operator_intent,
    sample_phrase_matrix,
)
from operator_action_covenant import (
    AUTHORITY_LEVELS as ACTION_COVENANT_AUTHORITY_LEVELS,
    RESTRICTED_DOMAINS as ACTION_COVENANT_RESTRICTED_DOMAINS,
    RISK_LEVELS as ACTION_COVENANT_RISK_LEVELS,
    STATUSES as ACTION_COVENANT_STATUSES,
    can_operator_confirmation_approve,
    create_action_covenant,
    render_action_covenant_summary,
    validate_action_covenant,
)
from operator_extension_simulator import (
    APPROVAL_SENSITIVE_PHRASES as OPERATOR_EXTENSION_APPROVAL_PHRASES,
    RESTRICTED_PHRASES as OPERATOR_EXTENSION_RESTRICTED_PHRASES,
    STATUS_ORIENTATION_PHRASES as OPERATOR_EXTENSION_STATUS_PHRASES,
    USES_OPERATOR_ACTION_COVENANT,
    USES_OPERATOR_INTENT_CORE,
    render_operator_extension_simulation,
    simulate_operator_extension_request,
    simulation_phrase_matrix,
)
from operator_evidence_bridge import (
    BRIDGE_NEVER_EXECUTES as OPERATOR_EVIDENCE_BRIDGE_NEVER_EXECUTES,
    EVIDENCE_SURFACES_ARE_NAMES_ONLY,
    EXTRA_RESTRICTED_DOMAIN_IDS as OPERATOR_EVIDENCE_EXTRA_RESTRICTED_DOMAINS,
    REQUIRED_BRIDGE_DOMAIN_IDS as OPERATOR_EVIDENCE_REQUIRED_DOMAINS,
    RESTRICTED_BRIDGE_DOMAIN_IDS as OPERATOR_EVIDENCE_RESTRICTED_DOMAINS,
    USES_OPERATOR_ACTION_COVENANT as BRIDGE_USES_OPERATOR_ACTION_COVENANT,
    USES_OPERATOR_EXTENSION_SIMULATOR as BRIDGE_USES_OPERATOR_EXTENSION_SIMULATOR,
    USES_OPERATOR_INTENT_CORE as BRIDGE_USES_OPERATOR_INTENT_CORE,
    bridge_operator_request,
    bridge_phrase_matrix,
    render_operator_evidence_bridge_result,
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

RUNTIME_AUTHORITY_RAILS = (
    "19_GATED_ACTIVATION_READINESS_MAP.md",
    "20_RUNTIME_AUTHORITY_AND_LEGACY_GATING_PLAN.md",
    "21_RUNTIME_INTEGRATION_AND_RECOVERY_ACTIVATION_PLAN.md",
    "24_VISIBLE_ROAD_BIG_STRIDES_AND_RENEWAL_DISCIPLINE.md",
)

RUNTIME_DRY_RUN_FUTURE_PATH = (
    "static guard",
    "dry-run readiness harness",
    "approval gate",
    "future live authorization",
)

RUNTIME_FORBIDDEN_NOW = (
    "live runtime launch",
    "service start/restart/enable/disable",
    "process scan or service crawl",
    "runtime state mutation",
    "provider/model call",
    "MCP call or connector mutation",
    "invoice action",
    "legal/private-root inspection",
)

RUNTIME_LEGACY_SURFACE_GROUPS = (
    {
        "surface": "legacy_launch_scripts",
        "classification": "blocked",
        "paths": (
            "scripts/start_all.sh",
            "start_chief.sh",
            "start_openclaw_brains.sh",
            "scripts/launch_pc.sh",
        ),
        "reason": "prevents unsafe activation through frozen launch shortcuts",
    },
    {
        "surface": "legacy_stack_installer",
        "classification": "blocked",
        "paths": ("scripts/install_openclaw_stack.sh",),
        "reason": "prevents broad stack mutation before exact approval",
    },
    {
        "surface": "hermes_gateway_installer",
        "classification": "dry-run-only",
        "paths": ("scripts/install_hermes_gateway_service.sh",),
        "reason": "clarifies the only currently visible installer path is dry-run planning",
    },
    {
        "surface": "service_inventory_audit",
        "classification": "review-required",
        "paths": (
            "scripts/audit_openclaw_services.sh",
            "tests/test_audit_openclaw_services_static.py",
        ),
        "reason": "reduces rediscovery of existing static audit proof without running it",
    },
    {
        "surface": "systemd_user_templates",
        "classification": "future-approval-required",
        "paths": (
            "systemd/user/openclaw-stack.target.in",
            "systemd/user/chief-listener.service.in",
            "systemd/user/chief-worker.service.in",
            "systemd/user/chief-memory-worker.service.in",
            "systemd/user/chief-state-worker.service.in",
            "systemd/user/chief-watcher-brain.service.in",
            "systemd/user/chief-guardian-listener.service.in",
            "systemd/user/cassandra-listener.service.in",
            "systemd/user/cassandra-watcher.service.in",
            "systemd/user/cassandra-briefing-scheduler.service.in",
            "systemd/user/hermes-gateway.service.in",
        ),
        "reason": "preserves operator leverage by naming service templates without mutating units",
    },
    {
        "surface": "runtime_entrypoints_and_lifecycle_tests",
        "classification": "review-required",
        "paths": (
            "chief_listener.py",
            "backend_sqlite_runtime.py",
            "tests/test_chief_listener_lifecycle.py",
            "tests/test_backend_sqlite_runtime.py",
        ),
        "reason": "clarifies exact future review surfaces without launching runtime code",
    },
)

PROMPT_PACK_PROFILES = (
    {
        "profile": "gemini_planning_prompt",
        "tool": "Gemini",
        "role": "planning",
        "use_for": (
            "rail interpretation",
            "architecture/design judgment",
            "tradeoffs and risk",
            "scope and campaign shaping",
            "READY/NOT_READY recommendation",
        ),
        "requires": (
            "roadmap rail references",
            "visible mile markers",
            "explicit forbidden surfaces",
            "review boundary",
        ),
        "forbids": (
            "repo mutation",
            "execution approval",
            "provider/runtime/MCP action",
        ),
        "north_star_purpose": "clarifies next safe action",
    },
    {
        "profile": "codex_implementation_prompt",
        "tool": "Codex",
        "role": "implementation",
        "use_for": (
            "bounded repo mutation",
            "convention inspection",
            "focused tests",
            "diff production",
            "validation receipts",
        ),
        "requires": (
            "clean baseline proof",
            "exact allowed files or surfaces",
            "focused validation commands",
            "no staging or commit unless explicitly requested",
        ),
        "drift_guards": (
            "invented architecture",
            "adjacent-file cleanup",
            "dirty-worktree mistakes",
            "broad staging",
            "overclaiming completion",
        ),
        "north_star_purpose": "preserves operator leverage",
    },
    {
        "profile": "gemini_architecture_scope_review_prompt",
        "tool": "Gemini",
        "role": "architecture_scope_review",
        "use_for": (
            "architecture alignment",
            "scope risk",
            "rail alignment",
            "overreach/underreach review",
        ),
        "requires": (
            "changed-file summary",
            "receipt outputs",
            "mile marker acceptance criteria",
            "READY/NOT_READY finding",
        ),
        "forbids": (
            "commit approval by implication",
            "live activation permission",
            "private-root or runtime expansion",
        ),
        "north_star_purpose": "prevents unsafe activation",
    },
    {
        "profile": "codex_diff_commit_readiness_review_prompt",
        "tool": "Codex",
        "role": "diff_commit_readiness_review",
        "use_for": (
            "dirty diff inspection",
            "line behavior",
            "tests and failure modes",
            "boundary leaks",
            "commit readiness",
        ),
        "requires": (
            "git diff",
            "test outputs",
            "exact changed files",
            "READY_TO_COMMIT or NOT_READY_TO_COMMIT",
        ),
        "forbids": (
            "broad refactor review drift",
            "model-only approval",
            "unstated staging",
        ),
        "north_star_purpose": "reduces future discovery",
    },
    {
        "profile": "codex_commit_mechanics_prompt",
        "tool": "Codex",
        "role": "commit_mechanics",
        "use_for": (
            "explicit staging",
            "final checks",
            "Conventional Commit",
            "post-commit receipts",
            "no push",
        ),
        "requires": (
            "prior review returned READY_TO_COMMIT",
            "explicit staging scope",
            "final validation receipt",
            "post-commit receipt",
        ),
        "forbids": (
            "commit before READY_TO_COMMIT",
            "broad staging",
            "push",
        ),
        "north_star_purpose": "preserves evidence boundaries",
    },
)

ACTIVATION_EVIDENCE_ITEMS = (
    {
        "item": "repo_receipt",
        "command": f"{CANONICAL_RECEIPT_COMMAND} repo-check",
        "purpose": "reduces future discovery of repo cleanliness and Packet state",
    },
    {
        "item": "packet_receipt",
        "command": f"{CANONICAL_RECEIPT_COMMAND} packet-status",
        "purpose": "preserves File 01 roadmap authority and active Packet 07 proof",
    },
    {
        "item": "operator_harness_read_model_receipt",
        "command": f"{CANONICAL_RECEIPT_COMMAND} operator-harness-status",
        "purpose": "reduces operator context load through low-context cards",
    },
    {
        "item": "dry_run_readiness_receipt",
        "command": f"{CANONICAL_RECEIPT_COMMAND} runtime-dry-run-readiness",
        "purpose": "prevents unsafe activation by proving dry-run-only scope",
    },
    {
        "item": "boundary_non_authority_receipt",
        "command": f"{CANONICAL_RECEIPT_COMMAND} gated-activation-status",
        "purpose": "preserves evidence boundaries by showing receipts are not approval",
    },
    {
        "item": "targeted_test_receipt",
        "command": "pytest tests/test_openclaw_receipts.py -q",
        "purpose": "ties readiness to focused tests instead of model judgment alone",
    },
    {
        "item": "approval_gate_note",
        "command": "future explicit operator approval note",
        "purpose": "clarifies the next safe action before any live lane",
    },
)

CONTROLLED_ACTIVATION_LANE_PLAN = {
    "lane": "runtime_authority_and_legacy_gating",
    "selected": True,
    "selection_reason": (
        "Packet 07 already names runtime/legacy gating as the first visible "
        "future activation lane, and it can advance through static dry-run "
        "proof without launching services."
    ),
    "surface_category": "legacy launch scripts, service templates, and runtime entrypoints",
    "evidence_required": tuple(item["item"] for item in ACTIVATION_EVIDENCE_ITEMS),
    "failure_modes": (
        "legacy script bypasses approval",
        "dry-run wording implies launch permission",
        "service template mutation appears in a readiness step",
        "receipt treated as approval",
        "process or runtime state is inspected as proof",
    ),
    "approval_required_before": (
        "any service launch",
        "any process/service inspection",
        "any runtime mutation",
        "any installer apply/restart path",
    ),
    "rollback_boundary": (
        "dry-run readiness is static only; no runtime rollback is needed until "
        "a future approved live lane exists"
    ),
    "forbidden_now": RUNTIME_FORBIDDEN_NOW,
}

MCP_SHARED_MEMORY_STATIC_POINTERS = (
    {
        "surface": "mcp_profile_config",
        "classification": "future-approval-required",
        "paths": (".mcp.json",),
        "reason": "prevents connector configuration from becoming hidden authority",
    },
    {
        "surface": "knowledge_substrate_review",
        "classification": "review-required",
        "paths": (
            "backend_knowledge_packet.py",
            "backend_sqlite_repository.py",
            "backend_storage_intelligence.py",
            "tests/test_backend_agent_context.py",
        ),
        "reason": "keeps canonical memory review tied to existing local-first substrate",
    },
    {
        "surface": "receipt_read_model_bridge",
        "classification": "dry-run-only",
        "paths": (
            "scripts/openclaw_receipts.py",
            "openclaw_sensitive_policy.py",
            "tests/test_openclaw_receipts.py",
        ),
        "reason": "allows static evidence without MCP calls or hidden writes",
    },
)

OPERATOR_INTAKE_DOC_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / (
    "NATURAL_LANGUAGE_OPERATOR_INTAKE_AND_ACTION_RIGHTS_V0.md"
)

OPERATOR_INTAKE_REQUIRED_SECTIONS = (
    "Purpose",
    "North Star alignment",
    "What this v0 authorizes",
    "What this v0 does not authorize",
    "Stage 1: Intent and response framing",
    "Stage 2: Prompt/handoff generation",
    "Stage 3: Safe read-only action rights",
    "Stage 4: Earned bounded autonomy",
    "Intent map",
    "Action-rights ladder",
    "Approval and stop rules",
    "Tool-specific routing",
    "Examples",
    "Tests / receipt expectations",
    "Remaining risks",
)

OPERATOR_INTAKE_STAGE_HEADINGS = (
    "Stage 1: Intent and response framing",
    "Stage 2: Prompt/handoff generation",
    "Stage 3: Safe read-only action rights",
    "Stage 4: Earned bounded autonomy",
)

OPERATOR_INTAKE_REQUIRED_INTENTS = (
    "status_brief",
    "next_safe_action",
    "codex_prompt_request",
    "gemini_review_request",
    "commit_review_request",
    "push_confirmation_context",
    "handoff_request",
    "activation_readiness_question",
    "approval_required_action",
    "unsafe_or_ambiguous_action",
    "stop_or_wait_instruction",
    "do_the_next_thing",
    "send_that_to_codex",
    "ask_gemini",
    "where_are_we",
    "can_we_move_forward",
    "make_my_life_easier",
    "tired_tell_me_what_matters",
)

OPERATOR_INTAKE_ACTION_RIGHT_LEVELS = (
    {
        "level": "level_0_static_framing_only",
        "heading": "Level 0 - Static framing only",
        "currently_authorized": True,
        "authority": "classify intent, explain next safe action, prepare static prompts/handoffs",
    },
    {
        "level": "level_1_read_only_local_evidence",
        "heading": "Level 1 - Read-only local evidence",
        "currently_authorized": False,
        "authority": "future approved receipt and packet/handoff reads only",
    },
    {
        "level": "level_2_draft_proposal_generation",
        "heading": "Level 2 - Draft/proposal generation",
        "currently_authorized": False,
        "authority": "future prompt, handoff, and review-plan drafts",
    },
    {
        "level": "level_3_bounded_repo_mutation",
        "heading": "Level 3 - Bounded repo mutation",
        "currently_authorized": False,
        "authority": "future scoped Codex repo edits with tests and review",
    },
    {
        "level": "level_4_pre_approved_low_risk_execution",
        "heading": "Level 4 - Pre-approved low-risk execution",
        "currently_authorized": False,
        "authority": "future low-risk lanes after receipts, rollback, stop conditions, and audit",
    },
    {
        "level": "level_5_restricted_high_risk_actions",
        "heading": "Level 5 - Restricted/high-risk actions",
        "currently_authorized": False,
        "authority": "always requires explicit approval gate; not authorized by this v0",
    },
)

OPERATOR_INTAKE_DANGEROUS_PHRASE_FRAMES = (
    {
        "intent": "do_the_next_thing",
        "phrase": "do the next thing",
        "execution_authority_now": False,
        "safe_frame": "infer likely next safe lane; do not cross mutation/external/runtime gates",
        "requires_follow_up_for_risky_action": True,
    },
    {
        "intent": "unsafe_or_ambiguous_action",
        "phrase": "just handle it",
        "execution_authority_now": False,
        "safe_frame": "narrow scope and propose the smallest safe next move",
        "requires_follow_up_for_risky_action": True,
    },
    {
        "intent": "approval_required_action",
        "phrase": "go ahead and launch",
        "execution_authority_now": False,
        "safe_frame": "route to explicit approval gate and current non-authority statement",
        "requires_follow_up_for_risky_action": True,
    },
)

OPERATOR_INTAKE_FORBIDDEN_CROSSINGS = (
    "live runtime launch",
    "assistant daemons",
    "Telegram",
    "process scans",
    "service scans",
    "systemd/launchctl/service/timer/daemon/launcher mutation",
    "provider/model/API calls",
    "MCP calls",
    "hidden memory writes",
    "external sends",
    "invoice, money, legal, private-root, or sensitive-data actions",
    "commits, pushes, destructive operations",
)

OPERATOR_INTENT_CORE_MODULE_RELATIVE_PATH = Path("operator_intent_core.py")
OPERATOR_ACTION_COVENANT_MODULE_RELATIVE_PATH = Path("operator_action_covenant.py")
OPERATOR_ACTION_COVENANT_TEST_RELATIVE_PATH = Path("tests/test_operator_action_covenant.py")
OPERATOR_EXTENSION_SIMULATOR_MODULE_RELATIVE_PATH = Path(
    "operator_extension_simulator.py"
)
OPERATOR_EXTENSION_SIMULATOR_TEST_RELATIVE_PATH = Path(
    "tests/test_operator_extension_simulator.py"
)
OPERATOR_EVIDENCE_BRIDGE_MODULE_RELATIVE_PATH = Path("operator_evidence_bridge.py")
OPERATOR_EVIDENCE_BRIDGE_TEST_RELATIVE_PATH = Path(
    "tests/test_operator_evidence_bridge.py"
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


def _present_paths(root: Path, paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if (root / path).is_file())


def _surface_groups_with_presence(
    root: Path,
    groups: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    enriched: list[dict[str, object]] = []
    for group in groups:
        paths = tuple(str(path) for path in group["paths"])
        enriched.append(
            {
                **group,
                "paths": paths,
                "present_paths": _present_paths(root, paths),
                "executes_surface": False,
                "mutates_surface": False,
            }
        )
    return tuple(enriched)


def _approval_gate_shape(
    lane: str,
    required_evidence: Sequence[str],
) -> dict[str, object]:
    return {
        "lane": lane,
        "current_approval_granted": False,
        "future_explicit_authority_required": True,
        "live_approval_engine_implemented": False,
        "approval_decision_fields": (
            "lane",
            "scope",
            "evidence_receipts",
            "targeted_tests",
            "rollback_or_reversal_boundary",
            "forbidden_surfaces_confirmed",
            "operator_approval_timestamp",
        ),
        "required_evidence": tuple(required_evidence),
        "not_sufficient": (
            "model recommendation alone",
            "receipt existence alone",
            "dry-run readiness alone",
            "stale handoff note",
        ),
        "authority_note": "Approval is a future explicit operator authority, not current permission.",
    }


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


def prompt_pack_status(root: Path = ROOT) -> dict[str, object]:
    doctrine = prompt_doctrine_status(root)
    profile_ids = tuple(profile["profile"] for profile in PROMPT_PACK_PROFILES)
    implementation_profile = next(
        profile
        for profile in PROMPT_PACK_PROFILES
        if profile["profile"] == "codex_implementation_prompt"
    )
    commit_profile = next(
        profile
        for profile in PROMPT_PACK_PROFILES
        if profile["profile"] == "codex_commit_mechanics_prompt"
    )

    checks = {
        "file14_doctrine_passed": bool(doctrine["passed"]),
        "profile_count_is_5": len(PROMPT_PACK_PROFILES) == 5,
        "required_profiles_present": profile_ids
        == (
            "gemini_planning_prompt",
            "codex_implementation_prompt",
            "gemini_architecture_scope_review_prompt",
            "codex_diff_commit_readiness_review_prompt",
            "codex_commit_mechanics_prompt",
        ),
        "gemini_and_codex_profiles_distinct": len(
            {(profile["tool"], profile["role"]) for profile in PROMPT_PACK_PROFILES}
        )
        == len(PROMPT_PACK_PROFILES),
        "codex_real_drift_risks_guarded": all(
            risk in implementation_profile["drift_guards"]
            for risk in (
                "invented architecture",
                "adjacent-file cleanup",
                "dirty-worktree mistakes",
                "broad staging",
                "overclaiming completion",
            )
        ),
        "commit_mechanics_requires_ready_to_commit": (
            "prior review returned READY_TO_COMMIT" in commit_profile["requires"]
        ),
        "static_read_only_no_generation": True,
    }

    return {
        "receipt_type": "openclaw.prompt_pack_status",
        "mode": "read-only/static-prompt-profile-check",
        "target_packet": doctrine["target_packet"],
        "active_packet": doctrine["active_packet"],
        "authority_note": (
            "Prompt-pack profiles are static guidance; this receipt does not "
            "generate prompts or grant execution authority."
        ),
        "mutates_files": False,
        "generates_prompts": False,
        "generated_prompt_count": 0,
        "profiles": PROMPT_PACK_PROFILES,
        "checks": checks,
        "passed": all(checks.values()),
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
        "runtime_dry_run_readiness_receipt_exposed": True,
        "mcp_shared_memory_gate_receipt_exposed": True,
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
        "runtime_dry_run_readiness_command": (
            f"{CANONICAL_RECEIPT_COMMAND} runtime-dry-run-readiness"
        ),
        "mcp_shared_memory_gate_command": (
            f"{CANONICAL_RECEIPT_COMMAND} mcp-shared-memory-gate-status"
        ),
        "future_activation_path": RUNTIME_DRY_RUN_FUTURE_PATH,
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def runtime_dry_run_readiness(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    rails_dir = _active_rails_dir_from_packet(packet, root)
    rail_texts = {
        name: _read_rail_text(rails_dir, name)
        for name in RUNTIME_AUTHORITY_RAILS
    }
    combined_text = "\n".join(rail_texts.values())
    surface_groups = _surface_groups_with_presence(root, RUNTIME_LEGACY_SURFACE_GROUPS)
    approval_gate = _approval_gate_shape(
        CONTROLLED_ACTIVATION_LANE_PLAN["lane"],
        CONTROLLED_ACTIVATION_LANE_PLAN["evidence_required"],
    )

    checks = {
        "packet07_runtime_rails_present": all(bool(text) for text in rail_texts.values()),
        "runtime_activation_not_authorized": (
            "No live service launch" in combined_text
            and "does not authorize live runtime launch" in combined_text
        ),
        "legacy_surfaces_classified": all(
            group["classification"]
            in {
                "blocked",
                "review-required",
                "dry-run-only",
                "future-approval-required",
            }
            for group in surface_groups
        ),
        "dry_run_path_defined": RUNTIME_DRY_RUN_FUTURE_PATH
        == (
            "static guard",
            "dry-run readiness harness",
            "approval gate",
            "future live authorization",
        ),
        "approval_gate_is_future_shape_only": (
            approval_gate["current_approval_granted"] is False
            and approval_gate["future_explicit_authority_required"] is True
            and approval_gate["live_approval_engine_implemented"] is False
        ),
        "no_runtime_or_external_effects": True,
    }

    return {
        "receipt_type": "openclaw.runtime_dry_run_readiness",
        "mode": "read-only/static-repo-pointers/no-runtime-inspection",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "authority_note": (
            "Runtime activation is not authorized; this receipt is dry-run "
            "readiness evidence only."
        ),
        "runtime_activation_authorized": False,
        "receipt_grants_execution_authority": False,
        "runtime_launched": False,
        "process_scan_used": False,
        "service_state_inspected": False,
        "runtime_state_mutated": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "invoice_action_taken": False,
        "private_root_inspected": False,
        "future_path": RUNTIME_DRY_RUN_FUTURE_PATH,
        "future_path_text": " -> ".join(RUNTIME_DRY_RUN_FUTURE_PATH),
        "surface_groups": surface_groups,
        "approval_gate": approval_gate,
        "first_controlled_activation_lane": CONTROLLED_ACTIVATION_LANE_PLAN,
        "forbidden_now": RUNTIME_FORBIDDEN_NOW,
        "north_star_filter": (
            "reduce future discovery",
            "prevent unsafe activation",
            "clarify next safe action",
            "preserve operator leverage",
        ),
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def activation_evidence_status(root: Path = ROOT) -> dict[str, object]:
    runtime = runtime_dry_run_readiness(root)
    gated = gated_activation_status(root)
    approval_gate = _approval_gate_shape(
        CONTROLLED_ACTIVATION_LANE_PLAN["lane"],
        tuple(item["item"] for item in ACTIVATION_EVIDENCE_ITEMS),
    )
    evidence_names = tuple(item["item"] for item in ACTIVATION_EVIDENCE_ITEMS)

    checks = {
        "required_evidence_items_present": evidence_names
        == (
            "repo_receipt",
            "packet_receipt",
            "operator_harness_read_model_receipt",
            "dry_run_readiness_receipt",
            "boundary_non_authority_receipt",
            "targeted_test_receipt",
            "approval_gate_note",
        ),
        "runtime_lane_supported_first": (
            CONTROLLED_ACTIVATION_LANE_PLAN["lane"]
            == "runtime_authority_and_legacy_gating"
        ),
        "generalizable_future_lanes_named": True,
        "dry_run_readiness_non_authorizing": (
            runtime["runtime_activation_authorized"] is False
            and runtime["receipt_grants_execution_authority"] is False
        ),
        "boundary_receipt_non_authorizing": (
            gated["receipt_grants_execution_authority"] is False
        ),
        "approval_gate_future_only": (
            approval_gate["current_approval_granted"] is False
            and approval_gate["live_approval_engine_implemented"] is False
        ),
        "evidence_tied_to_receipts_and_tests": all(
            "receipt" in item["item"]
            or "test" in item["item"]
            or item["item"] == "approval_gate_note"
            for item in ACTIVATION_EVIDENCE_ITEMS
        ),
    }

    return {
        "receipt_type": "openclaw.activation_evidence_status",
        "mode": "read-only/static-evidence-bundle/non-authorizing",
        "target_lane": CONTROLLED_ACTIVATION_LANE_PLAN["lane"],
        "authority_note": (
            "This evidence packet is a structure/check, not activation authority."
        ),
        "execution_authority_granted": False,
        "live_activation_implemented": False,
        "supported_future_lanes": (
            "runtime_legacy_activation",
            "mcp_shared_memory_activation",
            "legal_export_activation",
            "invoice_billing_activation",
        ),
        "required_evidence": ACTIVATION_EVIDENCE_ITEMS,
        "approval_gate": approval_gate,
        "first_controlled_activation_lane": CONTROLLED_ACTIVATION_LANE_PLAN,
        "checks": checks,
        "passed": bool(runtime["passed"]) and bool(gated["passed"]) and all(checks.values()),
    }


def mcp_shared_memory_gate_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    rails_dir = _active_rails_dir_from_packet(packet, root)
    rail_text = _read_rail_text(
        rails_dir,
        "22_MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md",
    )
    final_contract = packet06_final_static_boundary_contract()
    mcp_contract = final_contract["mcp_shared_memory"]
    static_pointers = _surface_groups_with_presence(root, MCP_SHARED_MEMORY_STATIC_POINTERS)

    checks = {
        "file22_present": bool(rail_text),
        "external_mcp_calls_blocked": (
            "No MCP invocation" in rail_text
            and "No external MCP calls" in rail_text
            and mcp_contract["external_mcp_calls_allowed"] is False
        ),
        "hidden_memory_writes_blocked": (
            "No hidden memory writes" in rail_text
            and mcp_contract["hidden_canonical_memory_writes_allowed"] is False
        ),
        "single_source_of_truth_required": "Single-source-of-truth requirements" in rail_text,
        "receipts_not_execution_authority": (
            "Receipts/read models as evidence, not approval" in rail_text
            and mcp_contract["receipts_are_execution_authority"] is False
        ),
        "private_context_leakage_blocked": "No private-root exposure" in rail_text,
        "static_pointers_classified": all(
            group["classification"]
            in {"review-required", "dry-run-only", "future-approval-required"}
            for group in static_pointers
        ),
    }

    return {
        "receipt_type": "openclaw.mcp_shared_memory_gate_status",
        "mode": "read-only/static-mcp-gate/no-connector-call",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "authority_note": (
            "MCP/shared memory remains a future gate; this receipt performs no "
            "MCP calls and writes no memory."
        ),
        "external_mcp_calls_allowed": False,
        "external_mcp_calls_used": False,
        "mcp_connector_mutated": False,
        "hidden_canonical_memory_writes_allowed": False,
        "hidden_canonical_memory_writes_used": False,
        "private_context_leakage_allowed": False,
        "shared_memory_is_execution_authority": False,
        "receipts_are_execution_authority": False,
        "static_pointers": static_pointers,
        "required_future_evidence": (
            "source authority",
            "single source of truth",
            "context provenance",
            "no hidden writer",
            "privacy boundary",
            "receipt/read-model non-authority",
            "explicit approval",
        ),
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_intake_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    doc_path = root / OPERATOR_INTAKE_DOC_RELATIVE_PATH
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    section_checks = {
        section: f"## {section}" in doc_text
        for section in OPERATOR_INTAKE_REQUIRED_SECTIONS
    }
    stage_checks = {
        stage: f"## {stage}" in doc_text
        for stage in OPERATOR_INTAKE_STAGE_HEADINGS
    }
    intent_checks = {
        intent: f"| {intent} |" in doc_text
        for intent in OPERATOR_INTAKE_REQUIRED_INTENTS
    }
    action_right_checks = {
        str(level["level"]): f"### {level['heading']}" in doc_text
        for level in OPERATOR_INTAKE_ACTION_RIGHT_LEVELS
    }
    phrase_checks = {
        str(frame["intent"]): str(frame["phrase"]) in doc_text
        for frame in OPERATOR_INTAKE_DANGEROUS_PHRASE_FRAMES
    }

    checks = {
        "doc_present": doc_path.is_file(),
        "required_sections_present": all(section_checks.values()),
        "stage_1_to_4_headings_present": all(stage_checks.values()),
        "required_intent_classes_present": all(intent_checks.values()),
        "action_rights_ladder_present": all(action_right_checks.values()),
        "dangerous_phrases_framed": all(phrase_checks.values()),
        "do_the_next_thing_not_execution_authority": (
            '"do the next thing" is not execution authority' in doc_text
            and "Natural language can express operator intent. It cannot by itself grant hidden execution authority."
            in doc_text
        ),
        "stage_4_future_gated_not_current_authority": (
            "Stage 4 remains future-gated, not current authority." in doc_text
            and "Current v0 authorization: future gated, not active." in doc_text
        ),
        "level_5_restricted_high_risk_actions_remain_restricted": (
            "Level 5 - Restricted/high-risk actions" in doc_text
            and "always require explicit approval gate" in doc_text
            and "not authorized by this v0" in doc_text
        ),
        "stage_1_only_current_authority": (
            "Level 0 static framing is the only action-right level authorized by this v0."
            in doc_text
        ),
        "no_live_autonomy_authorized": (
            "This v0 does not authorize live autonomy." in doc_text
            and "It is not a live classifier, prompt generator, action router, approval engine, or daemon."
            in doc_text
        ),
        "forbidden_crossings_named": all(
            crossing in doc_text for crossing in OPERATOR_INTAKE_FORBIDDEN_CROSSINGS
        ),
    }

    return {
        "receipt_type": "openclaw.operator_intake_status",
        "mode": "read-only/static-doc-proof/no-classifier",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "doc_path": str(OPERATOR_INTAKE_DOC_RELATIVE_PATH),
        "authority_note": (
            "Natural-language intake v0 is static framing only; it grants no "
            "execution, runtime, provider, MCP, send, commit, push, invoice, "
            "legal, private-root, or hidden-memory authority."
        ),
        "stage_1_static_v0_implemented": bool(
            checks["doc_present"] and checks["stage_1_only_current_authority"]
        ),
        "stage_2_to_4_future_gated": bool(
            checks["stage_4_future_gated_not_current_authority"]
        ),
        "live_classifier_implemented": False,
        "prompt_generator_implemented": False,
        "action_router_implemented": False,
        "approval_engine_implemented": False,
        "natural_language_is_execution_authority": False,
        "do_the_next_thing_execution_authority": False,
        "runtime_activation_authorized": False,
        "external_calls_used": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "section_checks": section_checks,
        "stage_checks": stage_checks,
        "intent_checks": intent_checks,
        "required_intents": OPERATOR_INTAKE_REQUIRED_INTENTS,
        "action_right_levels": OPERATOR_INTAKE_ACTION_RIGHT_LEVELS,
        "action_right_checks": action_right_checks,
        "dangerous_phrase_frames": OPERATOR_INTAKE_DANGEROUS_PHRASE_FRAMES,
        "dangerous_phrase_checks": phrase_checks,
        "forbidden_crossings": OPERATOR_INTAKE_FORBIDDEN_CROSSINGS,
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_intent_core_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    module_path = root / OPERATOR_INTENT_CORE_MODULE_RELATIVE_PATH
    phrase_rows = classify_phrase_matrix()
    phrase_checks = {row["phrase"]: bool(row["passed"]) for row in phrase_rows}
    frames = {
        row["phrase"]: frame_operator_intent(classify_operator_intent(str(row["phrase"])))
        for row in phrase_rows
    }
    dangerous_phrases = ("do the next thing", "go ahead", "launch it", "activate it")
    dangerous_rows = tuple(
        row for row in phrase_rows if row["phrase"] in dangerous_phrases
    )
    codex_frame = frames["send that to Codex"]
    gemini_frame = frames["ask Gemini"]
    tired_frame = frames["I'm tired, tell me what matters"]
    stop_frame = frames["stop"]

    checks = {
        "module_present": module_path.is_file(),
        "required_intent_classes_present": OPERATOR_INTENT_CORE_REQUIRED_INTENTS
        == (
            "status_brief",
            "next_safe_action",
            "tired_tell_me_what_matters",
            "codex_prompt_request",
            "gemini_review_request",
            "commit_review_request",
            "push_confirmation_context",
            "handoff_request",
            "activation_readiness_question",
            "approval_required_action",
            "unsafe_or_ambiguous_action",
            "stop_or_wait_instruction",
        ),
        "required_phrase_coverage_passed": all(phrase_checks.values()),
        "dangerous_phrases_non_authorizing": all(
            row["execution_authority"] is False for row in dangerous_rows
        ),
        "do_the_next_thing_not_execution_authority": (
            frames["do the next thing"].execution_authority is False
            and frames["do the next thing"].follow_up_required is True
        ),
        "go_ahead_requires_future_pending_approval_gate": (
            frames["go ahead"].execution_authority is False
            and frames["go ahead"].follow_up_required is True
            and frames["go ahead"].tool_route == "approval_gate_required"
        ),
        "activation_phrases_do_not_authorize_launch": (
            frames["launch it"].execution_authority is False
            and frames["activate it"].execution_authority is False
            and "live runtime launch" in frames["launch it"].forbidden_actions
        ),
        "codex_and_gemini_routes_are_distinct": (
            codex_frame.tool_route == "codex_bounded_repo_prompt"
            and gemini_frame.tool_route == "gemini_architecture_scope_review"
            and codex_frame.tool_route != gemini_frame.tool_route
        ),
        "tired_frame_is_operator_relief": (
            tired_frame.intent_name == "tired_tell_me_what_matters"
            and "state, the risk, the next safe move" in tired_frame.recommended_response_frame
        ),
        "stop_wait_classifies_as_stop": (
            stop_frame.intent_name == "stop_or_wait_instruction"
            and stop_frame.request_category == "stop"
        ),
        "frames_include_forbidden_actions_and_follow_up_posture": all(
            frames[row["phrase"]].forbidden_actions
            and row["follow_up_required"] in {True, False}
            for row in phrase_rows
        ),
        "surface_neutral_no_runtime_authority": True,
    }

    return {
        "receipt_type": "openclaw.operator_intent_core_status",
        "mode": "read-only/importable-local-core/no-execution",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "module_path": str(OPERATOR_INTENT_CORE_MODULE_RELATIVE_PATH),
        "authority_note": (
            "Operator Intent Core v0 classifies and frames natural language only; "
            "it grants no runtime, MCP, provider, external-send, commit, push, "
            "invoice, legal, private-root, hidden-memory, or destructive authority."
        ),
        "execution_authority_granted": False,
        "runtime_activation_authorized": False,
        "external_calls_used": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "cassandra_specific": False,
        "chief_specific": False,
        "telegram_specific": False,
        "required_intents": OPERATOR_INTENT_CORE_REQUIRED_INTENTS,
        "required_phrase_matrix": sample_phrase_matrix(),
        "phrase_rows": phrase_rows,
        "forbidden_actions": OPERATOR_INTENT_CORE_FORBIDDEN_ACTIONS,
        "tool_routes": {
            "codex": codex_frame.tool_route,
            "gemini": gemini_frame.tool_route,
            "activation": frames["launch it"].tool_route,
            "stop": stop_frame.tool_route,
        },
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_action_covenant_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    module_path = root / OPERATOR_ACTION_COVENANT_MODULE_RELATIVE_PATH
    test_path = root / OPERATOR_ACTION_COVENANT_TEST_RELATIVE_PATH
    low_read_only = create_action_covenant(
        requested_action="read Packet 07 status receipts",
        risk_level="low",
        authority_level="read_only",
        evidence_basis=(
            f"{CANONICAL_RECEIPT_COMMAND} repo-check",
            f"{CANONICAL_RECEIPT_COMMAND} operator-harness-status",
        ),
        forbidden_boundaries_checked=(
            "no runtime launch",
            "no MCP/provider call",
            "no external send",
        ),
        expires_at="2099-01-01T00:00:00+00:00",
    )
    bounded_repo_mutation = create_action_covenant(
        requested_action="apply a bounded repo patch with focused tests",
        risk_level="medium",
        authority_level="bounded_repo_mutation",
        evidence_basis=(
            f"{CANONICAL_RECEIPT_COMMAND} repo-check",
            "targeted pytest receipt",
        ),
        forbidden_boundaries_checked=(
            "no runtime launch",
            "no external send",
            "no private-root action",
        ),
        rollback_plan="revert only the scoped diff before commit",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    restricted_runtime = create_action_covenant(
        requested_action="launch live runtime",
        risk_level="restricted",
        authority_level="restricted",
        evidence_basis=("runtime dry-run readiness receipt",),
        forbidden_boundaries_checked=("live runtime launch remains forbidden",),
        rollback_plan="future runtime rollback architecture required",
        restricted_domains=("live runtime launch",),
        expires_at="2099-01-01T00:00:00+00:00",
    )
    external_sensitive = create_action_covenant(
        requested_action="send an external message",
        risk_level="high",
        authority_level="external_or_runtime_sensitive",
        evidence_basis=("future external-send evidence packet",),
        forbidden_boundaries_checked=("external sends remain separately gated",),
        rollback_plan="future external-send reversal plan required",
        expires_at="2099-01-01T00:00:00+00:00",
    )
    low_validation = validate_action_covenant(low_read_only)
    bounded_validation = validate_action_covenant(bounded_repo_mutation)
    restricted_validation = validate_action_covenant(restricted_runtime)
    external_sensitive_validation = validate_action_covenant(external_sensitive)
    exact_confirmation = can_operator_confirmation_approve(
        bounded_repo_mutation,
        bounded_repo_mutation.confirmation_phrase,
    )
    plain_go_ahead = can_operator_confirmation_approve(
        bounded_repo_mutation,
        "go ahead",
    )
    no_pending = can_operator_confirmation_approve(None, "go ahead")
    model_advisory = can_operator_confirmation_approve(
        low_read_only,
        "Gemini says approve this",
    )
    summary = render_action_covenant_summary(bounded_repo_mutation)

    checks = {
        "module_present": module_path.is_file(),
        "tests_present": test_path.is_file(),
        "required_statuses_present": ACTION_COVENANT_STATUSES
        == ("pending", "approved", "denied", "expired", "executed"),
        "required_risk_levels_present": ACTION_COVENANT_RISK_LEVELS
        == ("low", "medium", "high", "restricted"),
        "required_authority_levels_present": ACTION_COVENANT_AUTHORITY_LEVELS
        == (
            "read_only",
            "draft_or_proposal",
            "bounded_repo_mutation",
            "external_or_runtime_sensitive",
            "restricted",
        ),
        "restricted_domains_represented": ACTION_COVENANT_RESTRICTED_DOMAINS
        == (
            "live runtime launch",
            "MCP writes/shared memory",
            "provider/model/API calls",
            "invoice generation/reconciliation/sending",
            "legal/private-root/sensitive-data access",
            "external sends",
            "destructive filesystem operations",
            "hidden memory writes",
            "Packet 08 creation",
        ),
        "low_read_only_covenant_valid": low_validation.passed,
        "bounded_repo_mutation_requires_confirmation_and_rollback": (
            bounded_validation.passed
            and bounded_repo_mutation.requires_explicit_operator_confirmation is True
            and bool(bounded_repo_mutation.rollback_plan)
        ),
        "restricted_approval_blocked_in_v0": (
            restricted_validation.passed is False
            and "restricted_authority_not_approvable_in_v0"
            in restricted_validation.blocking_reasons
            and "restricted_domain_not_approvable_in_v0"
            in restricted_validation.blocking_reasons
        ),
        "external_runtime_sensitive_approval_blocked_in_v0": (
            external_sensitive_validation.passed is False
            and "external_or_runtime_sensitive_not_approvable_in_v0"
            in external_sensitive_validation.blocking_reasons
        ),
        "exact_confirmation_required_for_mutation": (
            exact_confirmation.can_approve is True
            and plain_go_ahead.can_approve is False
            and "exact_confirmation_phrase_required" in plain_go_ahead.reasons
        ),
        "go_ahead_without_pending_covenant_blocked": (
            no_pending.can_approve is False
            and no_pending.reasons == ("no_pending_covenant",)
        ),
        "model_advisory_cannot_approve": (
            model_advisory.can_approve is False
            and model_advisory.reasons == ("model_advisory_text_cannot_approve",)
        ),
        "summary_is_compact_operator_facing": (
            summary.startswith("ACTION COVENANT\n")
            and "Approval required: APPROVE " in summary
            and len(summary.splitlines()) == 10
        ),
        "no_live_execution_authority": True,
    }

    return {
        "receipt_type": "openclaw.operator_action_covenant_status",
        "mode": "read-only/importable-local-approval-object/no-execution",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "module_path": str(OPERATOR_ACTION_COVENANT_MODULE_RELATIVE_PATH),
        "test_path": str(OPERATOR_ACTION_COVENANT_TEST_RELATIVE_PATH),
        "authority_note": (
            "Operator Action Covenant v0 is a local approval object and static "
            "validation layer. It executes nothing, persists nothing, calls no "
            "providers/MCP/runtime surfaces, and grants no restricted authority."
        ),
        "execution_authority_granted": False,
        "restricted_authority_approvable_in_v0": False,
        "runtime_activation_authorized": False,
        "external_calls_used": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "persistence_or_database_used": False,
        "cassandra_specific": False,
        "chief_specific": False,
        "telegram_specific": False,
        "statuses": ACTION_COVENANT_STATUSES,
        "risk_levels": ACTION_COVENANT_RISK_LEVELS,
        "authority_levels": ACTION_COVENANT_AUTHORITY_LEVELS,
        "restricted_domains": ACTION_COVENANT_RESTRICTED_DOMAINS,
        "sample_summary_lines": tuple(summary.splitlines()),
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_extension_simulator_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    module_path = root / OPERATOR_EXTENSION_SIMULATOR_MODULE_RELATIVE_PATH
    test_path = root / OPERATOR_EXTENSION_SIMULATOR_TEST_RELATIVE_PATH
    phrase_rows = []
    for phrase, expected_intent in simulation_phrase_matrix():
        simulation = simulate_operator_extension_request(phrase)
        phrase_rows.append(
            {
                "phrase": phrase,
                "expected_intent": expected_intent,
                "actual_intent": simulation.inferred_intent,
                "passed": simulation.inferred_intent == expected_intent,
                "source": simulation.input_source_guess,
                "request_category": simulation.request_category,
                "execution_authority": simulation.execution_authority,
                "covenant_required": simulation.covenant_required,
                "covenant_allowed_in_v0": simulation.covenant_allowed_in_v0,
                "restricted_block": simulation.restricted_block,
                "has_yes_no_reframe": bool(simulation.yes_no_reframe),
            }
        )

    status_sims = tuple(
        simulate_operator_extension_request(phrase)
        for phrase in ("where are we", "are we good", "what needs my attention")
    )
    restricted_sims = tuple(
        simulate_operator_extension_request(phrase)
        for phrase in (
            "launch it",
            "write to MCP memory",
            "send the invoice",
            "touch legal files",
            "delete the files",
            "create Packet 08",
        )
    )
    approval_sims = tuple(
        simulate_operator_extension_request(phrase)
        for phrase in ("go ahead", "do it", "do the next thing", "ship it")
    )
    codex = simulate_operator_extension_request("send that to Codex")
    gemini = simulate_operator_extension_request("ask Gemini")
    commit_proposal = simulate_operator_extension_request("I recommend committing this")
    handoff_proposal = simulate_operator_extension_request("I can update the handoff")
    renderer_sample = render_operator_extension_simulation(
        simulate_operator_extension_request("go ahead")
    )

    checks = {
        "module_present": module_path.is_file(),
        "tests_present": test_path.is_file(),
        "imports_operator_intent_core": USES_OPERATOR_INTENT_CORE is True,
        "imports_operator_action_covenant": USES_OPERATOR_ACTION_COVENANT is True,
        "required_phrase_matrix_passed": all(row["passed"] for row in phrase_rows),
        "status_orientation_phrases_represented": (
            set(OPERATOR_EXTENSION_STATUS_PHRASES)
            >= {
                "where are we",
                "are we good",
                "what changed",
                "what needs my attention",
            }
            and all(
                sim.execution_authority is False
                and sim.covenant_required is False
                and sim.restricted_block is False
                for sim in status_sims
            )
        ),
        "restricted_phrases_represented": (
            "launch it" in OPERATOR_EXTENSION_RESTRICTED_PHRASES
            and "write to mcp memory" in OPERATOR_EXTENSION_RESTRICTED_PHRASES
            and "send the invoice" in OPERATOR_EXTENSION_RESTRICTED_PHRASES
            and all(
                sim.execution_authority is False
                and sim.restricted_block is True
                and sim.covenant_required is True
                and sim.covenant_allowed_in_v0 is False
                and sim.suggested_covenant is None
                for sim in restricted_sims
            )
        ),
        "approval_sensitive_reframes_represented": (
            "go ahead" in OPERATOR_EXTENSION_APPROVAL_PHRASES
            and "ship it" in OPERATOR_EXTENSION_APPROVAL_PHRASES
            and all(
                sim.execution_authority is False
                and sim.follow_up_required is True
                and bool(sim.yes_no_reframe)
                for sim in approval_sims
            )
        ),
        "codex_and_gemini_routes_are_distinct": (
            codex.tool_route == "codex_bounded_repo_prompt"
            and gemini.tool_route == "gemini_architecture_scope_review"
            and codex.tool_route != gemini.tool_route
        ),
        "send_to_codex_is_not_external_send": (
            codex.restricted_block is False
            and codex.covenant_required is False
            and "not an external send" in codex.operator_facing_summary
        ),
        "agent_proposals_can_suggest_only_safe_covenants": (
            commit_proposal.input_source_guess == "agent_proposal"
            and handoff_proposal.input_source_guess == "agent_proposal"
            and commit_proposal.suggested_covenant is not None
            and handoff_proposal.suggested_covenant is not None
            and commit_proposal.suggested_covenant.authority_level
            == "bounded_repo_mutation"
            and handoff_proposal.suggested_covenant.authority_level
            == "bounded_repo_mutation"
            and commit_proposal.suggested_covenant.restricted_domains == ()
            and handoff_proposal.suggested_covenant.restricted_domains == ()
        ),
        "renderer_includes_authority_covenant_and_reframe": (
            "Authority: execution_authority=False" in renderer_sample
            and "Covenant: required=True" in renderer_sample
            and "Reframe:" in renderer_sample
            and "Summary:" in renderer_sample
        ),
        "simulator_remains_non_live_non_executing": True,
    }

    return {
        "receipt_type": "openclaw.operator_extension_simulator_status",
        "mode": "read-only/local-simulation/no-execution",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "module_path": str(OPERATOR_EXTENSION_SIMULATOR_MODULE_RELATIVE_PATH),
        "test_path": str(OPERATOR_EXTENSION_SIMULATOR_TEST_RELATIVE_PATH),
        "authority_note": (
            "Operator Extension Simulator v0 connects natural language to Intent "
            "Core and Action Covenant posture for simulation only. It executes "
            "nothing, persists nothing, calls no providers/MCP/runtime surfaces, "
            "and grants no action authority."
        ),
        "execution_authority_granted": False,
        "runtime_activation_authorized": False,
        "external_calls_used": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "persistence_or_database_used": False,
        "cassandra_specific": False,
        "chief_specific": False,
        "telegram_specific": False,
        "status_orientation_phrase_count": len(OPERATOR_EXTENSION_STATUS_PHRASES),
        "approval_sensitive_phrase_count": len(OPERATOR_EXTENSION_APPROVAL_PHRASES),
        "restricted_phrase_count": len(OPERATOR_EXTENSION_RESTRICTED_PHRASES),
        "phrase_rows": tuple(phrase_rows),
        "checks": checks,
        "passed": bool(packet["passed"]) and all(checks.values()),
    }


def operator_evidence_bridge_status(root: Path = ROOT) -> dict[str, object]:
    packet = packet_status(root)
    module_path = root / OPERATOR_EVIDENCE_BRIDGE_MODULE_RELATIVE_PATH
    test_path = root / OPERATOR_EVIDENCE_BRIDGE_TEST_RELATIVE_PATH
    phrase_rows = []
    for phrase, expected_domain in bridge_phrase_matrix():
        result = bridge_operator_request(phrase)
        phrase_rows.append(
            {
                "phrase": phrase,
                "expected_domain": expected_domain,
                "actual_domain": result.bridge_domain,
                "passed": result.bridge_domain == expected_domain,
                "intent": result.inferred_intent,
                "request_category": result.request_category,
                "evidence_selection_mode": result.evidence_selection_mode,
                "evidence_surface_count": len(result.approved_evidence_surfaces),
                "execution_authority_granted": result.execution_authority_granted,
                "restricted_block": result.restricted_block,
                "covenant_posture": result.covenant_posture,
                "follow_up_required": result.follow_up_required,
            }
        )

    status = bridge_operator_request("where are we")
    relief = bridge_operator_request("I'm tired, tell me what matters")
    codex = bridge_operator_request("send that to Codex")
    gemini = bridge_operator_request("ask Gemini")
    approval = bridge_operator_request("go ahead")
    do_next = bridge_operator_request("do the next thing")
    packet08 = bridge_operator_request("should we make Packet 08")
    taste = bridge_operator_request("where is the taste")
    restricted_results = tuple(
        bridge_operator_request(phrase)
        for phrase in (
            "launch it",
            "write to MCP memory",
            "call the provider",
            "send the invoice",
            "touch legal files",
            "send the email",
            "delete it",
            "create Packet 08",
        )
    )
    rendered = render_operator_evidence_bridge_result(approval)
    actual_domains = tuple(dict.fromkeys(row["actual_domain"] for row in phrase_rows))
    all_results = (
        status,
        relief,
        codex,
        gemini,
        approval,
        do_next,
        packet08,
        taste,
    ) + restricted_results

    checks = {
        "module_present": module_path.is_file(),
        "tests_present": test_path.is_file(),
        "imports_operator_intent_core": BRIDGE_USES_OPERATOR_INTENT_CORE is True,
        "imports_operator_action_covenant": BRIDGE_USES_OPERATOR_ACTION_COVENANT is True,
        "imports_operator_extension_simulator": (
            BRIDGE_USES_OPERATOR_EXTENSION_SIMULATOR is True
        ),
        "required_phrase_matrix_passed": all(row["passed"] for row in phrase_rows),
        "required_domains_a_to_s_represented": set(OPERATOR_EVIDENCE_REQUIRED_DOMAINS)
        <= set(actual_domains),
        "restricted_domains_represented": set(OPERATOR_EVIDENCE_RESTRICTED_DOMAINS)
        <= set(actual_domains),
        "provider_api_restricted_extra_domain_represented": set(
            OPERATOR_EVIDENCE_EXTRA_RESTRICTED_DOMAINS
        )
        <= set(actual_domains),
        "evidence_surfaces_selected_by_name_only": (
            EVIDENCE_SURFACES_ARE_NAMES_ONLY is True
            and all(
                result.evidence_selection_mode == "names_only"
                and all(
                    not surface.startswith("./scripts/")
                    and "openclaw_receipts.py" not in surface
                    for surface in result.approved_evidence_surfaces
                )
                for result in all_results
            )
        ),
        "status_orientation_no_covenant": (
            status.bridge_domain == "status_orientation"
            and status.covenant_posture == "not_required_read_only_status"
            and status.restricted_block is False
        ),
        "operator_relief_short_practical": (
            relief.bridge_domain == "operator_relief"
            and "Cut the noise" in relief.operator_facing_summary
            and len(relief.operator_facing_summary) < 130
        ),
        "codex_and_gemini_routes_are_distinct": (
            codex.bridge_domain == "codex_coder_routing"
            and gemini.bridge_domain == "gemini_planning_architecture_routing"
            and codex.approved_evidence_surfaces != gemini.approved_evidence_surfaces
        ),
        "approval_phrases_reframe_without_authority": (
            approval.execution_authority_granted is False
            and approval.covenant_posture == "pending_covenant_required"
            and bool(approval.yes_no_reframe)
        ),
        "do_next_does_not_execute": (
            do_next.execution_authority_granted is False
            and do_next.covenant_posture == "proposal_only_until_specific_action"
            and do_next.follow_up_required is True
        ),
        "restricted_lanes_blocked": all(
            result.execution_authority_granted is False
            and result.restricted_block is True
            and result.covenant_posture == "restricted_not_approvable_in_v0"
            for result in restricted_results
        ),
        "taste_uses_manifesto_evidence": (
            taste.bridge_domain == "taste_product_feel_beauty"
            and "OPERATOR_EXTENSION_MANIFESTO.md" in taste.approved_evidence_surfaces
        ),
        "packet08_creation_not_authorized": (
            packet08.bridge_domain == "packet_renewal_next_packet"
            and packet08.restricted_block is True
            and "Packet 08 creation" in packet08.forbidden_boundaries
        ),
        "renderer_includes_bridge_posture": (
            "OPERATOR EVIDENCE BRIDGE" in rendered
            and "Evidence surfaces:" in rendered
            and "Covenant:" in rendered
            and "Forbidden boundaries:" in rendered
            and "Next move:" in rendered
        ),
        "bridge_remains_non_live_non_executing": (
            OPERATOR_EVIDENCE_BRIDGE_NEVER_EXECUTES is True
            and all(
                result.execution_authority_granted is False
                and result.receipts_executed is False
                and result.shell_commands_executed is False
                and result.runtime_or_external_action_used is False
                for result in all_results
            )
        ),
    }

    return {
        "receipt_type": "openclaw.operator_evidence_bridge_status",
        "mode": "read-only/local-evidence-selection/no-execution",
        "target_packet": packet["target_packet"],
        "active_packet": packet["active_packet"],
        "module_path": str(OPERATOR_EVIDENCE_BRIDGE_MODULE_RELATIVE_PATH),
        "test_path": str(OPERATOR_EVIDENCE_BRIDGE_TEST_RELATIVE_PATH),
        "authority_note": (
            "Operator Evidence Bridge v0 selects approved evidence surface names "
            "and frames Covenant posture only. It does not run receipts, execute "
            "shell commands, read private roots, call providers/MCP/runtime "
            "surfaces, mutate state, or grant action authority."
        ),
        "execution_authority_granted": False,
        "runtime_activation_authorized": False,
        "external_calls_used": False,
        "provider_or_model_called": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "persistence_or_database_used": False,
        "receipts_executed": False,
        "shell_commands_executed": False,
        "evidence_surfaces_are_names_only": True,
        "cassandra_specific": False,
        "chief_specific": False,
        "telegram_specific": False,
        "required_domains": OPERATOR_EVIDENCE_REQUIRED_DOMAINS,
        "extra_restricted_domains": OPERATOR_EVIDENCE_EXTRA_RESTRICTED_DOMAINS,
        "restricted_domains": OPERATOR_EVIDENCE_RESTRICTED_DOMAINS,
        "domain_count": len(actual_domains),
        "phrase_rows": tuple(phrase_rows),
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
    runtime_dry_run = runtime_dry_run_readiness(root)
    operator_intake = operator_intake_status(root)
    operator_intent_core = operator_intent_core_status(root)
    operator_action_covenant = operator_action_covenant_status(root)
    operator_extension_simulator = operator_extension_simulator_status(root)
    operator_evidence_bridge = operator_evidence_bridge_status(root)
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
                "card": "natural_language_operator_intake",
                "passed": operator_intake["passed"],
                "status_command": f"{CANONICAL_RECEIPT_COMMAND} operator-intake-status",
                "stage_1_static_v0_implemented": operator_intake[
                    "stage_1_static_v0_implemented"
                ],
                "stage_2_to_4_future_gated": operator_intake[
                    "stage_2_to_4_future_gated"
                ],
                "natural_language_is_execution_authority": operator_intake[
                    "natural_language_is_execution_authority"
                ],
                "do_the_next_thing_execution_authority": operator_intake[
                    "do_the_next_thing_execution_authority"
                ],
                "runtime_activation_authorized": operator_intake[
                    "runtime_activation_authorized"
                ],
                "intent_count": len(operator_intake["required_intents"]),
            },
            {
                "card": "operator_intent_core",
                "passed": operator_intent_core["passed"],
                "status_command": (
                    f"{CANONICAL_RECEIPT_COMMAND} operator-intent-core-status"
                ),
                "module_path": operator_intent_core["module_path"],
                "execution_authority_granted": operator_intent_core[
                    "execution_authority_granted"
                ],
                "runtime_activation_authorized": operator_intent_core[
                    "runtime_activation_authorized"
                ],
                "intent_count": len(operator_intent_core["required_intents"]),
                "phrase_count": len(operator_intent_core["phrase_rows"]),
                "codex_route": operator_intent_core["tool_routes"]["codex"],
                "gemini_route": operator_intent_core["tool_routes"]["gemini"],
            },
            {
                "card": "operator_action_covenant",
                "passed": operator_action_covenant["passed"],
                "status_command": (
                    f"{CANONICAL_RECEIPT_COMMAND} operator-action-covenant-status"
                ),
                "module_path": operator_action_covenant["module_path"],
                "execution_authority_granted": operator_action_covenant[
                    "execution_authority_granted"
                ],
                "restricted_authority_approvable_in_v0": operator_action_covenant[
                    "restricted_authority_approvable_in_v0"
                ],
                "runtime_activation_authorized": operator_action_covenant[
                    "runtime_activation_authorized"
                ],
                "status_count": len(operator_action_covenant["statuses"]),
                "restricted_domain_count": len(
                    operator_action_covenant["restricted_domains"]
                ),
            },
            {
                "card": "operator_extension_simulator",
                "passed": operator_extension_simulator["passed"],
                "status_command": (
                    f"{CANONICAL_RECEIPT_COMMAND} "
                    "operator-extension-simulator-status"
                ),
                "module_path": operator_extension_simulator["module_path"],
                "execution_authority_granted": operator_extension_simulator[
                    "execution_authority_granted"
                ],
                "runtime_activation_authorized": operator_extension_simulator[
                    "runtime_activation_authorized"
                ],
                "status_orientation_phrase_count": operator_extension_simulator[
                    "status_orientation_phrase_count"
                ],
                "approval_sensitive_phrase_count": operator_extension_simulator[
                    "approval_sensitive_phrase_count"
                ],
                "restricted_phrase_count": operator_extension_simulator[
                    "restricted_phrase_count"
                ],
            },
            {
                "card": "operator_evidence_bridge",
                "passed": operator_evidence_bridge["passed"],
                "status_command": (
                    f"{CANONICAL_RECEIPT_COMMAND} "
                    "operator-evidence-bridge-status"
                ),
                "module_path": operator_evidence_bridge["module_path"],
                "execution_authority_granted": operator_evidence_bridge[
                    "execution_authority_granted"
                ],
                "runtime_activation_authorized": operator_evidence_bridge[
                    "runtime_activation_authorized"
                ],
                "evidence_surfaces_are_names_only": operator_evidence_bridge[
                    "evidence_surfaces_are_names_only"
                ],
                "domain_count": operator_evidence_bridge["domain_count"],
                "restricted_domain_count": len(
                    operator_evidence_bridge["restricted_domains"]
                ),
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
                "card": "runtime_dry_run_readiness",
                "passed": runtime_dry_run["passed"],
                "runtime_activation_authorized": runtime_dry_run[
                    "runtime_activation_authorized"
                ],
                "receipt_grants_execution_authority": runtime_dry_run[
                    "receipt_grants_execution_authority"
                ],
                "readiness_command": (
                    f"{CANONICAL_RECEIPT_COMMAND} runtime-dry-run-readiness"
                ),
                "future_path": runtime_dry_run["future_path"],
                "surface_group_count": len(runtime_dry_run["surface_groups"]),
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
            and bool(runtime_dry_run["passed"])
            and bool(operator_intake["passed"])
            and bool(operator_intent_core["passed"])
            and bool(operator_action_covenant["passed"])
            and bool(operator_extension_simulator["passed"])
            and bool(operator_evidence_bridge["passed"])
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


def _print_records(
    name: str,
    values: Iterable[dict[str, object]],
    *,
    label_key: str,
) -> None:
    print(f"{name}:")
    records = list(values)
    if not records:
        print("- none")
        return
    for record in records:
        print(f"- {record[label_key]}:")
        for key, value in record.items():
            if key == label_key:
                continue
            print(f"  {key}: {value}")


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


def print_prompt_pack_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Prompt-Pack Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("authority_note", report["authority_note"]),
            ("mutates_files", report["mutates_files"]),
            ("generates_prompts", report["generates_prompts"]),
            ("generated_prompt_count", report["generated_prompt_count"]),
            ("passed", report["passed"]),
        ),
    )
    _print_records("profiles", report["profiles"], label_key="profile")
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
            (
                "runtime_dry_run_readiness_command",
                report["runtime_dry_run_readiness_command"],
            ),
            ("mcp_shared_memory_gate_command", report["mcp_shared_memory_gate_command"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("future_activation_path", report["future_activation_path"])
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_runtime_dry_run_readiness(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Runtime Dry-Run Readiness Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("authority_note", report["authority_note"]),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            (
                "receipt_grants_execution_authority",
                report["receipt_grants_execution_authority"],
            ),
            ("runtime_launched", report["runtime_launched"]),
            ("process_scan_used", report["process_scan_used"]),
            ("service_state_inspected", report["service_state_inspected"]),
            ("runtime_state_mutated", report["runtime_state_mutated"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("invoice_action_taken", report["invoice_action_taken"]),
            ("private_root_inspected", report["private_root_inspected"]),
            ("future_path_text", report["future_path_text"]),
            ("passed", report["passed"]),
        ),
    )
    _print_records("surface_groups", report["surface_groups"], label_key="surface")
    print("approval_gate:")
    for key, value in report["approval_gate"].items():
        print(f"- {key}: {value}")
    print("first_controlled_activation_lane:")
    for key, value in report["first_controlled_activation_lane"].items():
        print(f"- {key}: {value}")
    _print_list("forbidden_now", report["forbidden_now"])
    _print_list("north_star_filter", report["north_star_filter"])
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_activation_evidence_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Activation Evidence Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_lane", report["target_lane"]),
            ("authority_note", report["authority_note"]),
            ("execution_authority_granted", report["execution_authority_granted"]),
            ("live_activation_implemented", report["live_activation_implemented"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("supported_future_lanes", report["supported_future_lanes"])
    _print_records("required_evidence", report["required_evidence"], label_key="item")
    print("approval_gate:")
    for key, value in report["approval_gate"].items():
        print(f"- {key}: {value}")
    print("first_controlled_activation_lane:")
    for key, value in report["first_controlled_activation_lane"].items():
        print(f"- {key}: {value}")
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_mcp_shared_memory_gate_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw MCP Shared Memory Gate Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("authority_note", report["authority_note"]),
            ("external_mcp_calls_allowed", report["external_mcp_calls_allowed"]),
            ("external_mcp_calls_used", report["external_mcp_calls_used"]),
            ("mcp_connector_mutated", report["mcp_connector_mutated"]),
            (
                "hidden_canonical_memory_writes_allowed",
                report["hidden_canonical_memory_writes_allowed"],
            ),
            (
                "hidden_canonical_memory_writes_used",
                report["hidden_canonical_memory_writes_used"],
            ),
            (
                "private_context_leakage_allowed",
                report["private_context_leakage_allowed"],
            ),
            (
                "shared_memory_is_execution_authority",
                report["shared_memory_is_execution_authority"],
            ),
            (
                "receipts_are_execution_authority",
                report["receipts_are_execution_authority"],
            ),
            ("passed", report["passed"]),
        ),
    )
    _print_records("static_pointers", report["static_pointers"], label_key="surface")
    _print_list("required_future_evidence", report["required_future_evidence"])
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_intake_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Intake Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("doc_path", report["doc_path"]),
            ("authority_note", report["authority_note"]),
            (
                "stage_1_static_v0_implemented",
                report["stage_1_static_v0_implemented"],
            ),
            ("stage_2_to_4_future_gated", report["stage_2_to_4_future_gated"]),
            ("live_classifier_implemented", report["live_classifier_implemented"]),
            ("prompt_generator_implemented", report["prompt_generator_implemented"]),
            ("action_router_implemented", report["action_router_implemented"]),
            ("approval_engine_implemented", report["approval_engine_implemented"]),
            (
                "natural_language_is_execution_authority",
                report["natural_language_is_execution_authority"],
            ),
            (
                "do_the_next_thing_execution_authority",
                report["do_the_next_thing_execution_authority"],
            ),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            ("external_calls_used", report["external_calls_used"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("hidden_memory_write_used", report["hidden_memory_write_used"]),
            ("passed", report["passed"]),
        ),
    )
    print("section_checks:")
    for key, value in report["section_checks"].items():
        print(f"- {key}: {value}")
    print("stage_checks:")
    for key, value in report["stage_checks"].items():
        print(f"- {key}: {value}")
    print("intent_checks:")
    for key, value in report["intent_checks"].items():
        print(f"- {key}: {value}")
    _print_records(
        "action_right_levels",
        report["action_right_levels"],
        label_key="level",
    )
    _print_records(
        "dangerous_phrase_frames",
        report["dangerous_phrase_frames"],
        label_key="intent",
    )
    _print_list("forbidden_crossings", report["forbidden_crossings"])
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_intent_core_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Intent Core Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("module_path", report["module_path"]),
            ("authority_note", report["authority_note"]),
            ("execution_authority_granted", report["execution_authority_granted"]),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            ("external_calls_used", report["external_calls_used"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("hidden_memory_write_used", report["hidden_memory_write_used"]),
            ("cassandra_specific", report["cassandra_specific"]),
            ("chief_specific", report["chief_specific"]),
            ("telegram_specific", report["telegram_specific"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("required_intents", report["required_intents"])
    print("phrase_rows:")
    for row in report["phrase_rows"]:
        print(f"- {row['phrase']}:")
        for key, value in row.items():
            if key == "phrase":
                continue
            print(f"  {key}: {value}")
    _print_list("forbidden_actions", report["forbidden_actions"])
    print("tool_routes:")
    for key, value in report["tool_routes"].items():
        print(f"- {key}: {value}")
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_action_covenant_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Action Covenant Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("module_path", report["module_path"]),
            ("test_path", report["test_path"]),
            ("authority_note", report["authority_note"]),
            ("execution_authority_granted", report["execution_authority_granted"]),
            (
                "restricted_authority_approvable_in_v0",
                report["restricted_authority_approvable_in_v0"],
            ),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            ("external_calls_used", report["external_calls_used"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("hidden_memory_write_used", report["hidden_memory_write_used"]),
            ("persistence_or_database_used", report["persistence_or_database_used"]),
            ("cassandra_specific", report["cassandra_specific"]),
            ("chief_specific", report["chief_specific"]),
            ("telegram_specific", report["telegram_specific"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("statuses", report["statuses"])
    _print_list("risk_levels", report["risk_levels"])
    _print_list("authority_levels", report["authority_levels"])
    _print_list("restricted_domains", report["restricted_domains"])
    _print_list("sample_summary_lines", report["sample_summary_lines"])
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_extension_simulator_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Extension Simulator Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("module_path", report["module_path"]),
            ("test_path", report["test_path"]),
            ("authority_note", report["authority_note"]),
            ("execution_authority_granted", report["execution_authority_granted"]),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            ("external_calls_used", report["external_calls_used"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("hidden_memory_write_used", report["hidden_memory_write_used"]),
            ("persistence_or_database_used", report["persistence_or_database_used"]),
            ("cassandra_specific", report["cassandra_specific"]),
            ("chief_specific", report["chief_specific"]),
            ("telegram_specific", report["telegram_specific"]),
            (
                "status_orientation_phrase_count",
                report["status_orientation_phrase_count"],
            ),
            (
                "approval_sensitive_phrase_count",
                report["approval_sensitive_phrase_count"],
            ),
            ("restricted_phrase_count", report["restricted_phrase_count"]),
            ("passed", report["passed"]),
        ),
    )
    print("phrase_rows:")
    for row in report["phrase_rows"]:
        print(f"- {row['phrase']}:")
        for key, value in row.items():
            if key == "phrase":
                continue
            print(f"  {key}: {value}")
    print("checks:")
    for key, value in report["checks"].items():
        print(f"- {key}: {value}")


def print_operator_evidence_bridge_status(report: dict[str, object]) -> None:
    _print_scalar_lines(
        "OpenClaw Operator Evidence Bridge Status Receipt",
        (
            ("receipt_type", report["receipt_type"]),
            ("mode", report["mode"]),
            ("target_packet", report["target_packet"]),
            ("active_packet", report["active_packet"]),
            ("module_path", report["module_path"]),
            ("test_path", report["test_path"]),
            ("authority_note", report["authority_note"]),
            ("execution_authority_granted", report["execution_authority_granted"]),
            (
                "runtime_activation_authorized",
                report["runtime_activation_authorized"],
            ),
            ("external_calls_used", report["external_calls_used"]),
            ("provider_or_model_called", report["provider_or_model_called"]),
            ("mcp_called", report["mcp_called"]),
            ("hidden_memory_write_used", report["hidden_memory_write_used"]),
            ("persistence_or_database_used", report["persistence_or_database_used"]),
            ("receipts_executed", report["receipts_executed"]),
            ("shell_commands_executed", report["shell_commands_executed"]),
            (
                "evidence_surfaces_are_names_only",
                report["evidence_surfaces_are_names_only"],
            ),
            ("cassandra_specific", report["cassandra_specific"]),
            ("chief_specific", report["chief_specific"]),
            ("telegram_specific", report["telegram_specific"]),
            ("domain_count", report["domain_count"]),
            ("passed", report["passed"]),
        ),
    )
    _print_list("required_domains", report["required_domains"])
    _print_list("extra_restricted_domains", report["extra_restricted_domains"])
    _print_list("restricted_domains", report["restricted_domains"])
    print("phrase_rows:")
    for row in report["phrase_rows"]:
        print(f"- {row['phrase']}:")
        for key, value in row.items():
            if key == "phrase":
                continue
            print(f"  {key}: {value}")
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the receipt as a JSON object instead of human-readable text.",
    )

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
        "prompt-pack-status",
        help="Print Packet 07 static prompt-pack profile status.",
    )
    subparsers.add_parser(
        "gated-activation-status",
        help="Print Packet 07 gated activation boundary status.",
    )
    subparsers.add_parser(
        "runtime-dry-run-readiness",
        help="Print runtime authority and legacy gating dry-run readiness.",
    )
    subparsers.add_parser(
        "activation-evidence-status",
        help="Print static activation evidence packet status.",
    )
    subparsers.add_parser(
        "mcp-shared-memory-gate-status",
        help="Print static MCP/shared-memory hidden-authority gate status.",
    )
    subparsers.add_parser(
        "operator-intake-status",
        help="Print static natural-language operator intake and action-rights status.",
    )
    subparsers.add_parser(
        "operator-intent-core-status",
        help="Print shared Operator Intent Core v0 status.",
    )
    subparsers.add_parser(
        "operator-action-covenant-status",
        help="Print shared Operator Action Covenant v0 status.",
    )
    subparsers.add_parser(
        "operator-extension-simulator-status",
        help="Print shared Operator Extension Simulation Harness v0 status.",
    )
    subparsers.add_parser(
        "operator-evidence-bridge-status",
        help="Print shared Operator Evidence Bridge v0 status.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root

    # Collect report
    report: dict[str, object] | None = None
    if args.command == "repo-check":
        report = repo_check_receipt(root)
    elif args.command == "changed-files-receipt":
        files = changed_files(root)
        findings = path_policy_findings((item.path for item in files), root=root)
        report = {
            "receipt_type": "openclaw.changed_files",
            "files": [asdict(f) for f in files],
            "findings": findings,
            "passed": not findings,
        }
    elif args.command == "packet-status":
        report = packet_status(root, target=args.target)
    elif args.command == "docs-only-guard":
        report = docs_only_guard_report(
            changed_files(root),
            allowed_prefixes=tuple(args.allowed),
            root=root,
        )
    elif args.command == "no-private-root-check":
        paths = _paths_from_args_or_changes(args, root)
        findings = path_policy_findings(paths, root=root)
        report = {
            "receipt_type": "openclaw.no_private_root_check",
            "paths": paths,
            "findings": findings,
            "passed": not findings,
        }
    elif args.command == "sensitive-root-contract":
        report = sensitive_root_contract()
    elif args.command == "operator-harness-status":
        report = operator_harness_read_model(root=root)
    elif args.command == "prompt-doctrine-status":
        report = prompt_doctrine_status(root=root)
    elif args.command == "prompt-pack-status":
        report = prompt_pack_status(root=root)
    elif args.command == "gated-activation-status":
        report = gated_activation_status(root=root)
    elif args.command == "runtime-dry-run-readiness":
        report = runtime_dry_run_readiness(root=root)
    elif args.command == "activation-evidence-status":
        report = activation_evidence_status(root=root)
    elif args.command == "mcp-shared-memory-gate-status":
        report = mcp_shared_memory_gate_status(root=root)
    elif args.command == "operator-intake-status":
        report = operator_intake_status(root=root)
    elif args.command == "operator-intent-core-status":
        report = operator_intent_core_status(root=root)
    elif args.command == "operator-action-covenant-status":
        report = operator_action_covenant_status(root=root)
    elif args.command == "operator-extension-simulator-status":
        report = operator_extension_simulator_status(root=root)
    elif args.command == "operator-evidence-bridge-status":
        report = operator_evidence_bridge_status(root=root)

    if report is None:
        parser.error(f"unknown command: {args.command}")
        return 2

    if args.json:
        # Simple JSON conversion for dataclasses if any remain in values
        def _json_serializable(obj: object) -> object:
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)  # type: ignore
            if isinstance(obj, (datetime, Path)):
                return str(obj)
            return str(obj)

        print(json.dumps(report, indent=2, default=_json_serializable))
        return 0 if report.get("passed", True) else 1

    # Human-readable output
    if args.command == "repo-check":
        print_repo_check(report)
    elif args.command == "changed-files-receipt":
        # files and findings were handled above for the dict, but we reuse the local vars here
        files = changed_files(root)
        findings = path_policy_findings((item.path for item in files), root=root)
        print_changed_files_receipt(files, findings)
    elif args.command == "packet-status":
        print_packet_status(report)
    elif args.command == "docs-only-guard":
        print_docs_only_guard(report)
    elif args.command == "no-private-root-check":
        paths = _paths_from_args_or_changes(args, root)
        findings = path_policy_findings(paths, root=root)
        print_no_private_root_check(paths, findings)
    elif args.command == "sensitive-root-contract":
        print_sensitive_root_contract(report)
    elif args.command == "operator-harness-status":
        print_operator_harness_read_model(report)
    elif args.command == "prompt-doctrine-status":
        print_prompt_doctrine_status(report)
    elif args.command == "prompt-pack-status":
        print_prompt_pack_status(report)
    elif args.command == "gated-activation-status":
        print_gated_activation_status(report)
    elif args.command == "runtime-dry-run-readiness":
        print_runtime_dry_run_readiness(report)
    elif args.command == "activation-evidence-status":
        print_activation_evidence_status(report)
    elif args.command == "mcp-shared-memory-gate-status":
        print_mcp_shared_memory_gate_status(report)
    elif args.command == "operator-intake-status":
        print_operator_intake_status(report)
    elif args.command == "operator-intent-core-status":
        print_operator_intent_core_status(report)
    elif args.command == "operator-action-covenant-status":
        print_operator_action_covenant_status(report)
    elif args.command == "operator-extension-simulator-status":
        print_operator_extension_simulator_status(report)
    elif args.command == "operator-evidence-bridge-status":
        print_operator_evidence_bridge_status(report)

    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
