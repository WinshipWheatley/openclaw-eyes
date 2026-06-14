"""Cross-Machine Worker Dispatch Package v0.

This deterministic read-model defines how one OpenClaw chat message can be
packaged for the right worker/machine lane without creating live autonomous
dispatch. It models route decisions, worker-specific context packages,
authority boundaries, expected readbacks, and operator cards. It does not send
the package, execute workers, call models, run workflows, access external
systems, handle credentials, ingest raw private bodies, mutate Mission Control,
or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-24T00:00:00+00:00"

SCHEMA_VERSION = "cross_machine_worker_dispatch_package_v0"
READ_MODEL_ID = "cross_machine_worker_dispatch_package"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CROSS_MACHINE_WORKER_DISPATCH_PACKAGE"
MODULE_ROLE = "support_metadata"
CANONICAL_RUNTIME_SPINE_REF = "codex_work_package_lifecycle.py"
MIGRATION_NOTE = (
    "Retained for cross-machine packaging metadata. It must not dispatch workers directly; "
    "canonical runtime package lifecycle is codex_work_package_lifecycle.py."
)

TARGET_WORKER_TYPES = (
    "MAC_CODEX",
    "PC_CODEX",
    "GEMINI_AGY",
    "LOCAL_OLLAMA",
    "GPT_CHAT",
    "GUARDIAN",
    "CASSANDRA",
    "UNKNOWN_NEEDS_ROUTING",
)

TARGET_MACHINES = (
    "MAC",
    "PC_WSL",
    "CLOUD_OR_EXTERNAL_MODEL",
    "LOCAL_ONLY",
    "UNKNOWN",
)

DISPATCH_STATUSES = (
    "PACKAGE_READY_NOT_SENT",
    "ROUTE_SELECTED",
    "WAITING_FOR_OPERATOR_SEND",
    "WAITING_FOR_WORKER",
    "WORKER_RESULT_RECEIVED",
    "BLOCKED_MISSING_CONTEXT",
    "BLOCKED_UNSUPPORTED_WORKER",
    "BLOCKED_AUTHORITY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "WRONG_WORKER_SELECTED",
    "WRONG_MACHINE_SELECTED",
    "MISSING_CONTEXT_PACKAGE",
    "RAW_PII_IN_PACKAGE",
    "CREDENTIAL_IN_PACKAGE",
    "UNSUPPORTED_WORKER",
    "AUTHORITY_TOO_BROAD",
    "NETWORK_UNEXPECTED",
    "EXTERNAL_ACTION_INCLUDED",
    "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_auto_dispatch_allowed": False,
    "live_worker_execution_allowed": False,
    "live_cross_machine_send_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "email_send_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "approval_submission_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_RETURN_SECTIONS = (
    "STATUS",
    "SUMMARY",
    "RESULT",
    "VALIDATION",
    "COMMIT",
    "BOUNDARY CHECK",
)

COMMON_FORBIDDEN_CONTEXT = (
    "credentials",
    "tokens",
    "cookies",
    "raw email bodies",
    "raw PDFs or Excel bodies",
    "protected evidence bodies",
    "private raw bodies",
    "external account data",
)


@dataclass(frozen=True)
class CrossMachineWorkerDispatchPackage:
    dispatch_id: str
    source_chat_request_ref: str
    source_router_intent_ref: str
    target_worker_type: str
    target_machine: str
    target_repo_or_app: str
    task_type: str
    task_summary: str
    context_package_ref: str
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    required_proof: tuple[str, ...]
    validation_commands: tuple[str, ...]
    expected_return_format: tuple[str, ...]
    readback_target: str
    dispatch_status: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerRoutingDecision:
    decision_id: str
    source_message_ref: str
    route_reason: str
    selected_worker_type: str
    selected_machine: str
    selected_environment: str
    confidence: str
    alternate_workers: tuple[str, ...]
    blocked_workers: tuple[str, ...]
    handoff_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkerContextPackage:
    context_package_id: str
    dispatch_ref: str
    included_context: tuple[str, ...]
    excluded_context: tuple[str, ...]
    source_readmodels: tuple[str, ...]
    source_files_allowed: tuple[str, ...]
    source_files_forbidden: tuple[str, ...]
    privacy_class: str
    sensitivity_class: str
    token_budget_hint: str
    operator_goal: str
    success_criteria: tuple[str, ...]
    anti_goals: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerAuthorityBoundary:
    boundary_id: str
    dispatch_ref: str
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    external_authority: bool
    network_allowed: bool
    credential_handling_allowed: bool
    raw_body_ingestion_allowed: bool
    file_write_allowed: bool
    shell_allowed: bool
    tool_allowed: bool
    approval_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkerReturnReadback:
    readback_id: str
    dispatch_ref: str
    expected_status_values: tuple[str, ...]
    required_sections: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    commit_policy: str
    artifact_policy: str
    operator_card_plan: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerDispatchCard:
    card_id: str
    dispatch_ref: str
    title: str
    summary: str
    target_worker_label: str
    target_machine_label: str
    what_will_happen: tuple[str, ...]
    what_will_not_happen: tuple[str, ...]
    operator_choices: tuple[str, ...]
    status_tone: str
    next_safe_move: str


@dataclass(frozen=True)
class CrossMachineDispatchBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


REQUIRED_DISPATCH_FIELDS = tuple(CrossMachineWorkerDispatchPackage.__dataclass_fields__.keys())
REQUIRED_DECISION_FIELDS = tuple(WorkerRoutingDecision.__dataclass_fields__.keys())
REQUIRED_CONTEXT_FIELDS = tuple(WorkerContextPackage.__dataclass_fields__.keys())
REQUIRED_AUTHORITY_FIELDS = tuple(WorkerAuthorityBoundary.__dataclass_fields__.keys())
REQUIRED_RETURN_FIELDS = tuple(WorkerReturnReadback.__dataclass_fields__.keys())
REQUIRED_CARD_FIELDS = tuple(WorkerDispatchCard.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(CrossMachineDispatchBlocker.__dataclass_fields__.keys())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "cross_machine_worker_dispatch_package": {"required_fields": list(REQUIRED_DISPATCH_FIELDS)},
        "worker_routing_decision": {"required_fields": list(REQUIRED_DECISION_FIELDS)},
        "worker_context_package": {"required_fields": list(REQUIRED_CONTEXT_FIELDS)},
        "worker_authority_boundary": {"required_fields": list(REQUIRED_AUTHORITY_FIELDS)},
        "worker_return_readback": {"required_fields": list(REQUIRED_RETURN_FIELDS)},
        "worker_dispatch_card": {"required_fields": list(REQUIRED_CARD_FIELDS)},
        "cross_machine_dispatch_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
    }


def _base_return(dispatch_id: str, *, commit_policy: str) -> WorkerReturnReadback:
    return WorkerReturnReadback(
        readback_id=f"return_readback_{dispatch_id}",
        dispatch_ref=dispatch_id,
        expected_status_values=("SUCCESS", "PARTIAL", "BLOCKED", "WRONG_ENVIRONMENT", "NEEDS_VERIFICATION"),
        required_sections=COMMON_RETURN_SECTIONS,
        proof_requirements=("commands run", "tests or validation notes", "changed files", "boundary check"),
        commit_policy=commit_policy,
        artifact_policy="Return generated artifacts/readbacks only when validation passes and scope allows.",
        operator_card_plan=("worker selected", "package ready", "waiting for result", "result received", "blocked if boundary fails"),
        next_safe_move="Return the result/readback to the same chat surface.",
    )


def _card(
    dispatch_id: str,
    *,
    title: str,
    summary: str,
    worker: str,
    machine: str,
    will: tuple[str, ...],
    will_not: tuple[str, ...],
    tone: str = "ready",
) -> WorkerDispatchCard:
    return WorkerDispatchCard(
        card_id=f"dispatch_card_{dispatch_id}",
        dispatch_ref=dispatch_id,
        title=title,
        summary=summary,
        target_worker_label=worker,
        target_machine_label=machine,
        what_will_happen=will,
        what_will_not_happen=will_not,
        operator_choices=("Send package", "Edit routing", "Cancel"),
        status_tone=tone,
        next_safe_move="Show this as a human card before any worker handoff.",
    )


def _blocker(blocker_type: str, condition: str, severity: str = "BLOCKS_DISPATCH") -> CrossMachineDispatchBlocker:
    return CrossMachineDispatchBlocker(
        blocker_id=f"cross_machine_dispatch_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move="Stop dispatch, strip authority, or ask a clarifying question.",
    )


def build_blockers() -> tuple[CrossMachineDispatchBlocker, ...]:
    conditions = {
        "WRONG_WORKER_SELECTED": "The selected worker does not own the task surface.",
        "WRONG_MACHINE_SELECTED": "The selected machine cannot safely perform the requested work.",
        "MISSING_CONTEXT_PACKAGE": "No bounded context package exists for the worker.",
        "RAW_PII_IN_PACKAGE": "Worker package contains raw private or protected values.",
        "CREDENTIAL_IN_PACKAGE": "Worker package contains credentials or tokens.",
        "UNSUPPORTED_WORKER": "Requested worker is not supported by this routing contract.",
        "AUTHORITY_TOO_BROAD": "Worker package grants broader authority than the task requires.",
        "NETWORK_UNEXPECTED": "Worker package includes network access without explicit gate.",
        "EXTERNAL_ACTION_INCLUDED": "Worker package includes send, submit, browser, account, or approval action.",
        "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR": "Normal operator card exposes implementation contract fields.",
        "UNKNOWN_FAIL_CLOSED": "Unknown routing state fails closed.",
    }
    return tuple(_blocker(kind, condition) for kind, condition in conditions.items())


def _mac_context(dispatch_id: str, goal: str, *, allowed_files: tuple[str, ...]) -> WorkerContextPackage:
    return WorkerContextPackage(
        context_package_id=f"context_{dispatch_id}",
        dispatch_ref=dispatch_id,
        included_context=("operator chat summary", "Mission Control UI target", "Mac validation expectations"),
        excluded_context=COMMON_FORBIDDEN_CONTEXT + ("Repo A backend mutation authority",),
        source_readmodels=("chat_readback_card_mirror", "operator_card_render_packet_contract"),
        source_files_allowed=allowed_files,
        source_files_forbidden=("Repo A backend Python files", "credentials", "external account data"),
        privacy_class="operator_safe_ui_metadata",
        sensitivity_class="low_to_medium",
        token_budget_hint="focused Mac app context only",
        operator_goal=goal,
        success_criteria=("UI behavior matches request", "Mac build/test or screenshot validation reported", "no external authority added"),
        anti_goals=("do not mutate Repo A backend", "do not access external accounts", "do not add watchers or hidden automation"),
        next_safe_move="Send only to Mac Codex after operator confirms.",
    )


def _pc_context(dispatch_id: str, goal: str) -> WorkerContextPackage:
    return WorkerContextPackage(
        context_package_id=f"context_{dispatch_id}",
        dispatch_ref=dispatch_id,
        included_context=("router readback refs", "Repo A backend module refs", "test/export validation commands"),
        excluded_context=COMMON_FORBIDDEN_CONTEXT + ("Mac Swift edit authority",),
        source_readmodels=("conversational_workflow_router_readback", "chat_readback_card_mirror"),
        source_files_allowed=("Repo A Python modules", "scripts", "tests", "generated/read_models"),
        source_files_forbidden=("Mission Control Swift files", "external account data", "credentials"),
        privacy_class="repo_safe_metadata_only",
        sensitivity_class="low_to_medium",
        token_budget_hint="bounded Repo A backend context",
        operator_goal=goal,
        success_criteria=("deterministic export exists", "focused pytest passes", "boundary scans pass"),
        anti_goals=("do not edit Mac app", "do not access external systems", "do not ingest raw private bodies"),
        next_safe_move="Send only to PC Codex after operator confirms.",
    )


def _gemini_context(dispatch_id: str, goal: str) -> WorkerContextPackage:
    return WorkerContextPackage(
        context_package_id=f"context_{dispatch_id}",
        dispatch_ref=dispatch_id,
        included_context=("sanitized repo/read-model summaries", "question to audit", "expected report shape"),
        excluded_context=COMMON_FORBIDDEN_CONTEXT + ("write access", "commit authority", "runtime execution"),
        source_readmodels=("operator_card_render_packet_contract", "chat_readback_card_mirror"),
        source_files_allowed=("read-only sanitized summaries",),
        source_files_forbidden=("source edits", "commits", "external accounts", "credentials"),
        privacy_class="sanitized_read_only",
        sensitivity_class="low",
        token_budget_hint="read-only audit context",
        operator_goal=goal,
        success_criteria=("gotchas identified", "recommendation grounded", "no file edits or execution"),
        anti_goals=("do not modify files", "do not commit", "do not run tools", "do not access external systems"),
        next_safe_move="Send as read-only scout packet only after operator confirms.",
    )


def _authority(
    dispatch_id: str,
    *,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
    file_write: bool,
    shell: bool,
    tool: bool,
    approval_required: bool,
) -> WorkerAuthorityBoundary:
    return WorkerAuthorityBoundary(
        boundary_id=f"authority_{dispatch_id}",
        dispatch_ref=dispatch_id,
        allowed_actions=allowed,
        forbidden_actions=forbidden,
        external_authority=False,
        network_allowed=False,
        credential_handling_allowed=False,
        raw_body_ingestion_allowed=False,
        file_write_allowed=file_write,
        shell_allowed=shell,
        tool_allowed=tool,
        approval_required=approval_required,
        next_safe_move="Keep live dispatch blocked; package is non-executing until operator sends it.",
    )


def _dispatch(
    *,
    dispatch_id: str,
    source_chat: str,
    intent: str,
    worker: str,
    machine: str,
    target: str,
    task_type: str,
    summary: str,
    context_ref: str,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
    allowed_files: tuple[str, ...],
    forbidden_files: tuple[str, ...],
    validation: tuple[str, ...],
    status: str = "PACKAGE_READY_NOT_SENT",
) -> CrossMachineWorkerDispatchPackage:
    return CrossMachineWorkerDispatchPackage(
        dispatch_id=dispatch_id,
        source_chat_request_ref=source_chat,
        source_router_intent_ref=intent,
        target_worker_type=worker,
        target_machine=machine,
        target_repo_or_app=target,
        task_type=task_type,
        task_summary=summary,
        context_package_ref=context_ref,
        allowed_actions=allowed,
        forbidden_actions=forbidden,
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        required_proof=("worker final report", "validation output", "boundary check"),
        validation_commands=validation,
        expected_return_format=COMMON_RETURN_SECTIONS,
        readback_target="same OpenClaw chat surface",
        dispatch_status=status,
        next_safe_move="Show package card and wait for operator send; no live auto-dispatch.",
    )


def build_mac_chat_ui_example() -> dict[str, Any]:
    dispatch_id = "dispatch_mac_codex_mission_control_chat_ui"
    context = _mac_context(
        dispatch_id,
        "Fix Mission Control chat UI so cards render inside chat and composer stays bottom anchored.",
        allowed_files=("Mission Control SwiftUI view files", "Mac UI tests/screenshot harness"),
    )
    allowed = ("SwiftUI view edits", "Xcode build/test", "screenshot validation", "bounded Mac package import/render")
    forbidden = ("Repo A backend mutation", "network", "credentials", "external action", "email/Coupa/browser access")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_mission_control_ui_request",
            intent="intent_mission_control_chat_ui",
            worker="MAC_CODEX",
            machine="MAC",
            target="Mission Control Mac app",
            task_type="SWIFTUI_APP_UI",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("xcodebuild or existing Mac build command", "screenshot validation if available"),
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_mac_codex_mission_control_chat_ui",
            source_message_ref="operator_chat_mission_control_ui_request",
            route_reason="SwiftUI/Mission Control UI work belongs on Mac Codex.",
            selected_worker_type="MAC_CODEX",
            selected_machine="MAC",
            selected_environment="Mission Control Mac repo",
            confidence="HIGH",
            alternate_workers=("GEMINI_AGY for read-only design critique",),
            blocked_workers=("PC_CODEX for direct Swift edits",),
            handoff_required=True,
            next_safe_move="Prepare Mac Codex package and wait for operator send.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=True, shell=True, tool=True, approval_required=False),
        card=_card(
            dispatch_id,
            title="Send this to Mac Codex",
            summary="This is Apple/Mac-side app work. It should go to Mac Codex, not PC Codex.",
            worker="Mac Codex",
            machine="Mac",
            will=("Package SwiftUI UI context", "Ask for build/screenshot validation", "Return result to this chat"),
            will_not=("No Repo A backend mutation", "No network or external action", "No credentials"),
        ),
    )


def build_logic_pro_example() -> dict[str, Any]:
    dispatch_id = "dispatch_mac_codex_logic_pro_project_recognition"
    context = _mac_context(
        dispatch_id,
        "Add Logic Pro project recognition concept to the Mac app.",
        allowed_files=("Mission Control SwiftUI files", "Mac-local project metadata stubs"),
    )
    allowed = ("Mac app UI/read-only metadata concept", "Swift implementation stub", "Mac validation")
    forbidden = ("DAW mutation", "audio file mutation", "destructive project writes", "automation without explicit approval")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_logic_project_request",
            intent="intent_logic_project_recognition",
            worker="MAC_CODEX",
            machine="MAC",
            target="Mission Control Mac app",
            task_type="APPLE_APP_INTEGRATION_SCOUT_OR_UI",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("Mac build/test if implementation is in scope", "operator-visible boundary report"),
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_mac_codex_logic_project_recognition",
            source_message_ref="operator_chat_logic_project_request",
            route_reason="Logic Pro recognition is Apple/Mac-side app integration work.",
            selected_worker_type="MAC_CODEX",
            selected_machine="MAC",
            selected_environment="Mission Control Mac repo",
            confidence="HIGH",
            alternate_workers=("GEMINI_AGY for design/taste scout",),
            blocked_workers=("PC_CODEX for Mac app mutation",),
            handoff_required=True,
            next_safe_move="Package read-only metadata concept with destructive DAW actions forbidden.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=True, shell=True, tool=True, approval_required=True),
        card=_card(
            dispatch_id,
            title="Send Apple-side project recognition to Mac Codex",
            summary="Logic Pro project recognition belongs to the Mac app lane with DAW mutation blocked.",
            worker="Mac Codex",
            machine="Mac",
            will=("Package Mac UI/project metadata context", "Require safe read-only posture", "Return boundary readback"),
            will_not=("No DAW mutation", "No audio file changes", "No automation without approval"),
        ),
    )


def build_final_cut_example() -> dict[str, Any]:
    dispatch_id = "dispatch_mac_codex_final_cut_metadata_display"
    context = _mac_context(
        dispatch_id,
        "Prepare Final Cut project metadata display.",
        allowed_files=("Mission Control SwiftUI files", "Mac-local metadata display stubs"),
    )
    allowed = ("Mac UI/read-only metadata concept", "SwiftUI display work", "Mac validation")
    forbidden = ("project mutation", "export", "render", "automation without explicit approval")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_final_cut_metadata_request",
            intent="intent_final_cut_metadata_display",
            worker="MAC_CODEX",
            machine="MAC",
            target="Mission Control Mac app",
            task_type="APPLE_APP_INTEGRATION_SCOUT_OR_UI",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("Mac UI validation", "operator-readable boundary report"),
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_mac_codex_final_cut_metadata_display",
            source_message_ref="operator_chat_final_cut_metadata_request",
            route_reason="Final Cut metadata display is Mac app/UI integration work.",
            selected_worker_type="MAC_CODEX",
            selected_machine="MAC",
            selected_environment="Mission Control Mac repo",
            confidence="HIGH",
            alternate_workers=("GEMINI_AGY for display critique",),
            blocked_workers=("PC_CODEX for direct Mac UI edits",),
            handoff_required=True,
            next_safe_move="Package Mac read-only metadata display work with export/mutation blocked.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=True, shell=True, tool=True, approval_required=True),
        card=_card(
            dispatch_id,
            title="Send Final Cut display work to Mac Codex",
            summary="This is Mac-side metadata display work; project export or mutation remains blocked.",
            worker="Mac Codex",
            machine="Mac",
            will=("Package Mac UI work", "Keep project metadata read-only", "Return validation/readback"),
            will_not=("No project mutation", "No export/render", "No external action"),
        ),
    )


def build_mail_boundary_example() -> dict[str, Any]:
    dispatch_id = "dispatch_mac_codex_mail_invoice_boundary_blocked"
    context = _mac_context(
        dispatch_id,
        "Review Mac Mail invoice send surface boundary without granting send authority.",
        allowed_files=("Mission Control SwiftUI files", "Mail boundary UI stubs"),
    )
    allowed = ("Mac UI/surface review", "local boundary card design", "approval-gate copy")
    forbidden = ("send email", "create live Mail draft", "access accounts", "credential handling", "external action")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_mail_send_invoice_request",
            intent="intent_mail_invoice_send_boundary",
            worker="MAC_CODEX",
            machine="MAC",
            target="Mission Control Mac app",
            task_type="MAC_MAIL_BOUNDARY_REVIEW",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("boundary review only",),
            status="BLOCKED_AUTHORITY",
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_mac_codex_mail_invoice_boundary_blocked",
            source_message_ref="operator_chat_mail_send_invoice_request",
            route_reason="Mail UI/boundary review can be Mac Codex, but actual send requires governed adapter approval.",
            selected_worker_type="MAC_CODEX",
            selected_machine="MAC",
            selected_environment="Mission Control Mac repo",
            confidence="MEDIUM",
            alternate_workers=("CASSANDRA for future comms drafting role", "GUARDIAN for approval boundary"),
            blocked_workers=("any worker with direct send authority",),
            handoff_required=True,
            next_safe_move="Strip send authority and route only a UI/boundary package.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=True, shell=True, tool=True, approval_required=True),
        card=_card(
            dispatch_id,
            title="Mail send is blocked; Mac UI review only",
            summary="Mac Codex may review the Mail surface, but send authority is not included.",
            worker="Mac Codex",
            machine="Mac",
            will=("Package boundary/UI review", "Name missing approval/send adapter", "Return blocked readback"),
            will_not=("No email sent", "No account access", "No live draft"),
            tone="blocked",
        ),
    )


def build_pc_codex_example() -> dict[str, Any]:
    dispatch_id = "dispatch_pc_codex_chat_readback_card_mirror"
    context = _pc_context(dispatch_id, "Build the chat readback card mirror from router readbacks.")
    allowed = ("Python module edits", "script/export edits", "pytest", "generated read-models", "credential/authority scans")
    forbidden = ("Mac Swift edits", "external action", "credentials", "raw private body ingestion")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_card_mirror_backend_request",
            intent="intent_backend_card_mirror",
            worker="PC_CODEX",
            machine="PC_WSL",
            target="Repo A backend /home/openclaw",
            task_type="BACKEND_READMODEL",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("python3 scripts/export_chat_readback_card_mirror.py --format summary", "focused pytest"),
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_pc_codex_chat_readback_card_mirror",
            source_message_ref="operator_chat_card_mirror_backend_request",
            route_reason="Repo A Python/read-model work belongs on PC Codex.",
            selected_worker_type="PC_CODEX",
            selected_machine="PC_WSL",
            selected_environment="/home/openclaw",
            confidence="HIGH",
            alternate_workers=("GEMINI_AGY for read-only review",),
            blocked_workers=("MAC_CODEX for backend mutation",),
            handoff_required=True,
            next_safe_move="Prepare PC Codex package and wait for operator send.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=True, shell=True, tool=True, approval_required=False),
        card=_card(
            dispatch_id,
            title="Send this to PC Codex",
            summary="This is canonical Repo A backend work. It should go to PC Codex.",
            worker="PC Codex",
            machine="PC/WSL",
            will=("Package backend source/test refs", "Run deterministic validation if sent", "Return commit/readback status"),
            will_not=("No Mac Swift edits", "No external account access", "No raw private body ingestion"),
        ),
    )


def build_gemini_example() -> dict[str, Any]:
    dispatch_id = "dispatch_gemini_agy_chat_first_card_contract_audit"
    context = _gemini_context(dispatch_id, "Audit whether the chat-first pivot should reuse existing card contracts.")
    allowed = ("read-only audit", "design critique", "gotcha discovery", "prompt shaping", "strategy recommendation")
    forbidden = ("file edits", "commits", "live execution", "external action", "credential access")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_card_contract_audit_request",
            intent="intent_read_only_card_contract_audit",
            worker="GEMINI_AGY",
            machine="CLOUD_OR_EXTERNAL_MODEL",
            target="Gemini/Agy read-only scout lane",
            task_type="READ_ONLY_AUDIT",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=context.source_files_allowed,
            forbidden_files=context.source_files_forbidden,
            validation=("read-only report returned", "no diff/commit"),
            status="WAITING_FOR_OPERATOR_SEND",
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_gemini_agy_chat_first_card_contract_audit",
            source_message_ref="operator_chat_card_contract_audit_request",
            route_reason="Read-only scouting and prompt shaping belong to Gemini/Agy.",
            selected_worker_type="GEMINI_AGY",
            selected_machine="CLOUD_OR_EXTERNAL_MODEL",
            selected_environment="read-only scout packet",
            confidence="HIGH",
            alternate_workers=("PC_CODEX for implementation after scout",),
            blocked_workers=("MAC_CODEX for backend audit",),
            handoff_required=True,
            next_safe_move="Prepare read-only scout package; do not grant edit or execution authority.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=False, shell=False, tool=False, approval_required=True),
        card=_card(
            dispatch_id,
            title="Send this to Gemini/Agy",
            summary="This is read-only scouting and prompt shaping, not implementation.",
            worker="Gemini/Agy",
            machine="External model lane",
            will=("Package sanitized summaries", "Ask for critique/recommendation", "Return report to chat"),
            will_not=("No file edits", "No commits", "No execution or external action"),
        ),
    )


def build_ambiguous_example() -> dict[str, Any]:
    dispatch_id = "dispatch_unknown_make_it_better"
    context = WorkerContextPackage(
        context_package_id=f"context_{dispatch_id}",
        dispatch_ref=dispatch_id,
        included_context=("operator message only",),
        excluded_context=COMMON_FORBIDDEN_CONTEXT,
        source_readmodels=(),
        source_files_allowed=(),
        source_files_forbidden=("all files until scope is clarified",),
        privacy_class="unknown_fail_closed",
        sensitivity_class="unknown",
        token_budget_hint="ask clarifying question first",
        operator_goal="Make it better.",
        success_criteria=("operator selects target surface", "operator selects desired outcome"),
        anti_goals=("do not choose hidden scope", "do not dispatch a worker", "do not run anything"),
        next_safe_move="Ask what surface and outcome the operator means.",
    )
    allowed = ("ask a clarifying question", "show routing options")
    forbidden = ("worker dispatch", "file edits", "model call", "external action")
    return _example(
        dispatch=_dispatch(
            dispatch_id=dispatch_id,
            source_chat="operator_chat_make_it_better",
            intent="intent_unknown_needs_routing",
            worker="UNKNOWN_NEEDS_ROUTING",
            machine="UNKNOWN",
            target="unknown",
            task_type="UNKNOWN_NEEDS_FRAMING",
            summary=context.operator_goal,
            context_ref=context.context_package_id,
            allowed=allowed,
            forbidden=forbidden,
            allowed_files=(),
            forbidden_files=context.source_files_forbidden,
            validation=("clarifying question produced",),
            status="BLOCKED_MISSING_CONTEXT",
        ),
        decision=WorkerRoutingDecision(
            decision_id="decision_unknown_make_it_better",
            source_message_ref="operator_chat_make_it_better",
            route_reason="Request is too broad to identify worker, machine, files, or success criteria.",
            selected_worker_type="UNKNOWN_NEEDS_ROUTING",
            selected_machine="UNKNOWN",
            selected_environment="none",
            confidence="LOW",
            alternate_workers=("MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "CASSANDRA", "GUARDIAN"),
            blocked_workers=(),
            handoff_required=False,
            next_safe_move="Ask whether this is Mac app work, Repo A backend work, read-only scouting, comms, or safety review.",
        ),
        context=context,
        authority=_authority(dispatch_id, allowed=allowed, forbidden=forbidden, file_write=False, shell=False, tool=False, approval_required=True),
        card=_card(
            dispatch_id,
            title="I need a target before routing",
            summary="“Make it better” is too broad to pick a worker safely.",
            worker="Needs routing",
            machine="Unknown",
            will=("Ask a clarifying question", "Offer routing options", "Wait for operator choice"),
            will_not=("No worker dispatch", "No file edits", "No external action"),
            tone="waiting",
        ),
    )


def build_wrong_worker_example() -> dict[str, Any]:
    example = build_mac_chat_ui_example()
    dispatch = dict(example["dispatch"])
    dispatch["dispatch_id"] = "dispatch_wrong_worker_swiftui_to_pc_codex"
    dispatch["target_worker_type"] = "PC_CODEX"
    dispatch["target_machine"] = "PC_WSL"
    dispatch["dispatch_status"] = "BLOCKED_AUTHORITY"
    dispatch["next_safe_move"] = "Flag wrong worker and reroute to Mac Codex."
    decision = dict(example["routing_decision"])
    decision["decision_id"] = "decision_wrong_worker_swiftui_to_pc_codex"
    decision["route_reason"] = "SwiftUI app work was incorrectly routed to PC Codex."
    decision["selected_worker_type"] = "PC_CODEX"
    decision["selected_machine"] = "PC_WSL"
    decision["blocked_workers"] = ("PC_CODEX for SwiftUI mutation",)
    decision["next_safe_move"] = "Block dispatch and select Mac Codex."
    card = dict(example["operator_card"])
    card["card_id"] = "dispatch_card_wrong_worker_swiftui_to_pc_codex"
    card["title"] = "Wrong worker selected"
    card["summary"] = "SwiftUI app work should not go to PC Codex."
    card["status_tone"] = "blocked"
    return {
        **example,
        "dispatch": dispatch,
        "routing_decision": decision,
        "operator_card": card,
        "active_blockers": ("WRONG_WORKER_SELECTED", "WRONG_MACHINE_SELECTED"),
    }


def build_authority_too_broad_example() -> dict[str, Any]:
    example = build_mail_boundary_example()
    dispatch = dict(example["dispatch"])
    dispatch["dispatch_id"] = "dispatch_authority_too_broad_mail_coupa_send"
    dispatch["forbidden_actions"] = tuple(dispatch["forbidden_actions"]) + ("Gmail/Coupa/send authority embedded in UI prompt",)
    dispatch["dispatch_status"] = "BLOCKED_AUTHORITY"
    dispatch["next_safe_move"] = "Strip send/submit authority and require governed adapters."
    card = dict(example["operator_card"])
    card["card_id"] = "dispatch_card_authority_too_broad_mail_coupa_send"
    card["title"] = "Authority too broad"
    card["summary"] = "The package included send/Coupa authority for a UI task, so dispatch is blocked."
    card["status_tone"] = "blocked"
    return {
        **example,
        "dispatch": dispatch,
        "operator_card": card,
        "active_blockers": ("AUTHORITY_TOO_BROAD", "EXTERNAL_ACTION_INCLUDED"),
    }


def _example(
    *,
    dispatch: CrossMachineWorkerDispatchPackage,
    decision: WorkerRoutingDecision,
    context: WorkerContextPackage,
    authority: WorkerAuthorityBoundary,
    card: WorkerDispatchCard,
) -> dict[str, Any]:
    return {
        "dispatch": asdict(dispatch),
        "routing_decision": asdict(decision),
        "context_package": asdict(context),
        "authority_boundary": asdict(authority),
        "return_readback": asdict(_base_return(dispatch.dispatch_id, commit_policy="Commit only if validation passes and task scope asks for it.")),
        "operator_card": asdict(card),
        "active_blockers": (),
    }


def build_examples() -> dict[str, Any]:
    return {
        "mac_codex_mission_control_chat_ui": build_mac_chat_ui_example(),
        "mac_codex_logic_pro_project_recognition": build_logic_pro_example(),
        "mac_codex_final_cut_metadata_display": build_final_cut_example(),
        "mac_mail_invoice_send_boundary_blocked": build_mail_boundary_example(),
        "pc_codex_chat_readback_card_mirror": build_pc_codex_example(),
        "gemini_agy_card_contract_audit": build_gemini_example(),
        "ambiguous_make_it_better": build_ambiguous_example(),
        "wrong_worker_swiftui_to_pc_codex": build_wrong_worker_example(),
        "authority_too_broad_mail_coupa_send": build_authority_too_broad_example(),
    }


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload["examples"]
    blockers = payload["cross_machine_dispatch_blockers_by_id"]
    return {
        "cross_machine_worker_dispatch_package_model_present": True,
        "worker_routing_decision_model_present": True,
        "worker_context_package_model_present": True,
        "worker_authority_boundary_model_present": True,
        "worker_return_readback_model_present": True,
        "worker_dispatch_card_model_present": True,
        "cross_machine_dispatch_blocker_model_present": True,
        "target_worker_types_present": all(worker in TARGET_WORKER_TYPES for worker in (
            "MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "LOCAL_OLLAMA", "GUARDIAN", "CASSANDRA", "UNKNOWN_NEEDS_ROUTING"
        )),
        "target_machines_present": all(machine in TARGET_MACHINES for machine in ("MAC", "PC_WSL", "CLOUD_OR_EXTERNAL_MODEL", "LOCAL_ONLY", "UNKNOWN")),
        "dispatch_statuses_present": all(status in DISPATCH_STATUSES for status in (
            "PACKAGE_READY_NOT_SENT", "WAITING_FOR_OPERATOR_SEND", "BLOCKED_AUTHORITY", "BLOCKED_MISSING_CONTEXT", "UNKNOWN_FAIL_CLOSED"
        )),
        "mac_codex_route_exists": examples["mac_codex_mission_control_chat_ui"]["dispatch"]["target_worker_type"] == "MAC_CODEX"
        and examples["mac_codex_mission_control_chat_ui"]["dispatch"]["target_machine"] == "MAC",
        "apple_app_integration_examples_exist": all(
            examples[key]["dispatch"]["target_worker_type"] == "MAC_CODEX"
            for key in ("mac_codex_logic_pro_project_recognition", "mac_codex_final_cut_metadata_display")
        ),
        "mac_mail_boundary_blocks_send": examples["mac_mail_invoice_send_boundary_blocked"]["dispatch"]["dispatch_status"] == "BLOCKED_AUTHORITY",
        "pc_codex_route_exists": examples["pc_codex_chat_readback_card_mirror"]["dispatch"]["target_worker_type"] == "PC_CODEX"
        and examples["pc_codex_chat_readback_card_mirror"]["dispatch"]["target_machine"] == "PC_WSL",
        "gemini_route_exists": examples["gemini_agy_card_contract_audit"]["dispatch"]["target_worker_type"] == "GEMINI_AGY"
        and examples["gemini_agy_card_contract_audit"]["authority_boundary"]["file_write_allowed"] is False,
        "ambiguous_route_exists": examples["ambiguous_make_it_better"]["dispatch"]["target_worker_type"] == "UNKNOWN_NEEDS_ROUTING",
        "wrong_worker_blocker_example_exists": "WRONG_WORKER_SELECTED" in examples["wrong_worker_swiftui_to_pc_codex"]["active_blockers"],
        "authority_too_broad_blocker_example_exists": "AUTHORITY_TOO_BROAD" in examples["authority_too_broad_mail_coupa_send"]["active_blockers"],
        "blockers_present": all(blocker in {item["blocker_type"] for item in blockers.values()} for blocker in BLOCKER_TYPES),
        "operator_cards_hide_machine_contract": all(
            "schema" not in example["operator_card"]["summary"].lower()
            and "handler" not in example["operator_card"]["summary"].lower()
            for example in examples.values()
        ),
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "no_example_grants_external_authority": all(
            example["authority_boundary"]["external_authority"] is False
            and example["authority_boundary"]["network_allowed"] is False
            and example["authority_boundary"]["credential_handling_allowed"] is False
            and example["authority_boundary"]["raw_body_ingestion_allowed"] is False
            for example in examples.values()
        ),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_packages": False,
        "external_action_performed": False,
        "worker_executed": False,
        "cross_machine_send_performed": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_cross_machine_worker_dispatch_package(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    examples = build_examples()
    blockers = build_blockers()
    primary = examples["pc_codex_chat_readback_card_mirror"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "target_worker_types": TARGET_WORKER_TYPES,
        "target_machines": TARGET_MACHINES,
        "dispatch_statuses": DISPATCH_STATUSES,
        "model_schemas": _model_schemas(),
        "cross_machine_worker_dispatch_package": primary["dispatch"],
        "worker_routing_decision": primary["routing_decision"],
        "worker_context_package": primary["context_package"],
        "worker_authority_boundary": primary["authority_boundary"],
        "worker_return_readback": primary["return_readback"],
        "worker_dispatch_card": primary["operator_card"],
        "examples": examples,
        "cross_machine_dispatch_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "relationship_refs": {
            "conversational_workflow_router_contract": "source chat workflow/domain classification",
            "cross_surface_artifact_handoff_registry_contract": "post-office handoff compatibility",
            "agent_execution_packet_compiler_contract": "worker packet shape and authority filtering",
            "agent_conversation_handoff_step_packet_contract": "handoff/readback visibility",
            "package_compiler_contract": "non-executing package compiler boundary",
            "workflow_readback_concierge_contract": "same-chat request/readback loop",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["examples"]
    lines = [
        "# Cross-Machine Worker Dispatch Package v0",
        "",
        "ELIOPERATOR: One OpenClaw chat can prepare the right worker package without auto-dispatching it.",
        "",
        "## What This Means",
        "",
        "- Mac Codex owns Apple/Mac-side ship experience: Mission Control SwiftUI, Xcode validation, Mac-local rendering, screenshots, and Apple app boundaries.",
        "- PC Codex owns canonical Repo A backend / Shipyard substrate: Python, tests, generated read-models, package/shuttle rails, and backend contracts.",
        "- Gemini/Agy owns read-only scouting, audit, taste/design targeting, and prompt shaping.",
        "- Packages carry the context, allowed work, forbidden work, proof requirements, validation, and return format.",
        "- Nothing is auto-dispatched yet.",
        "",
        "## Example Routes",
        "",
    ]
    for key in (
        "mac_codex_mission_control_chat_ui",
        "mac_codex_logic_pro_project_recognition",
        "mac_codex_final_cut_metadata_display",
        "pc_codex_chat_readback_card_mirror",
        "gemini_agy_card_contract_audit",
        "ambiguous_make_it_better",
    ):
        card = examples[key]["operator_card"]
        dispatch = examples[key]["dispatch"]
        lines.extend(
            [
                f"### {card['title']}",
                f"- {card['summary']}",
                f"- Worker: {card['target_worker_label']}.",
                f"- Machine: {card['target_machine_label']}.",
                f"- Status: `{dispatch['dispatch_status']}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Blocked Examples",
            "",
            "- Mail send request: Mac Codex may review UI/boundary only; actual send remains governed and blocked.",
            "- SwiftUI routed to PC Codex: blocked as wrong worker/machine.",
            "- UI package with Gmail/Coupa/send authority: blocked as authority too broad.",
            "",
            "## Boundary",
            "",
            "- No live auto-dispatch.",
            "- No worker execution.",
            "- No cross-machine send.",
            "- No model call, agent dispatch, workflow run, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push.",
            "",
            "Next safe move: show the dispatch card, let the operator send/edit/cancel, and keep readback returning to the same chat.",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    proof = payload["machine_proof"]
    examples = payload["examples"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "primary_worker": payload["cross_machine_worker_dispatch_package"]["target_worker_type"],
        "primary_machine": payload["cross_machine_worker_dispatch_package"]["target_machine"],
        "examples": {
            key: {
                "worker": value["dispatch"]["target_worker_type"],
                "machine": value["dispatch"]["target_machine"],
                "status": value["dispatch"]["dispatch_status"],
            }
            for key, value in examples.items()
        },
        "mac_codex_route_exists": proof["mac_codex_route_exists"],
        "pc_codex_route_exists": proof["pc_codex_route_exists"],
        "gemini_route_exists": proof["gemini_route_exists"],
        "ambiguous_route_exists": proof["ambiguous_route_exists"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the cross-machine worker dispatch package read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_cross_machine_worker_dispatch_package()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
