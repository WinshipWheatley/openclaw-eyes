"""Workflow Composer V0.

Turns an operator goal into a transparent pre-execution workflow plan.
This module only plans. It does not execute workers, stage live work, grant
authority, connect providers, send email, mutate ledgers/workbooks, export PDFs,
submit portals, push git, call external LLMs, or launch child agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workflow Composer.md")

SCHEMA_VERSION = "workflow_composer_v0"
CONTRACT_READ_MODEL_ID = "workflow_composer_contract"
LATEST_READ_MODEL_ID = "workflow_composer_latest"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
LATEST_JSON_EXPORT_NAME = f"{LATEST_READ_MODEL_ID}.json"
READY_STATUS = "WORKFLOW_COMPOSER_READY"
NOT_READY_STATUS = "WORKFLOW_COMPOSER_NOT_READY"

OWNER_VALUES = ("cassandra", "chief", "hermes", "guardian", "pc_codex", "mac_codex")
RISK_VALUES = ("low", "medium", "high")

PRECONDITIONS = {
    "track_a_workroom_backbone": {
        "filename": "track_a_workroom_backbone_status.json",
        "required_status": "TRACK_A_WORKROOM_BACKBONE_READY",
        "status_source": "top_level",
    },
    "track_b_governance_memory_cutover": {
        "filename": "track_b_governance_memory_cutover_status.json",
        "required_status": "TRACK_B_GOVERNANCE_MEMORY_CUTOVER_READY",
        "status_source": "top_level",
    },
    "chief_build_backlog": {
        "filename": "chief_build_backlog.json",
        "required_status": "CHIEF_BUILD_BACKLOG_READY",
        "status_source": "top_level",
    },
    "agent_handoff_registry": {
        "filename": "agent_handoff_registry.json",
        "required_status": "AGENT_HANDOFF_REGISTRY_READY",
        "status_source": "top_level",
    },
    "worker_package_staging": {
        "filename": "worker_package_staging_status.json",
        "required_status": "WORKER_PACKAGE_STAGING_READY",
        "status_source": "top_level",
    },
    "operator_next_decision_workrooms": {
        "filename": "track_a_workroom_backbone_status.json",
        "required_status": "OPERATOR_NEXT_DECISION_WORKROOMS_READY",
        "status_source": "phase",
        "phase": "operator_next_decision_workrooms",
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_mutation_allowed": False,
    "excel_automation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "payment_marking_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "credential_use_allowed": False,
    "provider_access_allowed": False,
    "external_action_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "tool_execution_allowed": False,
    "git_push_allowed": False,
    "push_allowed": False,
    "sent": False,
    "paid": False,
}

COMMON_ALLOWED_ACTIONS = (
    "read_local_generated_read_models",
    "summarize_operator_goal",
    "recommend_pre_execution_sequence",
    "draft_packet_outline_for_operator_review",
    "record_required_receipts",
)

COMMON_BLOCKED_ACTIONS = (
    "send_email",
    "open_gmail",
    "open_browser",
    "open_coupa",
    "mutate_ledger",
    "post_ledger_entry",
    "open_workbook",
    "read_workbook_body",
    "read_spreadsheet_cells",
    "mutate_workbook",
    "run_excel_automation",
    "export_pdf",
    "mark_paid",
    "submit_portal",
    "grant_authority",
    "use_credentials",
    "perform_business_action",
    "stage_live_package_without_operator_approval",
    "spawn_worker",
    "run_worker",
    "run_child_agent",
    "launch_agent_loop",
    "call_external_llm",
    "connect_live_provider",
    "push_git",
)

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "submit_performed",
    "business_action_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "agent_loop_started",
    "external_llm_called",
    "git_push_performed",
}

EXAMPLE_INPUTS = (
    {
        "operator_goal": "Get St. Anne's monthly invoice workflow ready.",
        "desired_outcome": "A reviewed monthly invoice workflow plan with protected Excel and send gates visible.",
        "urgency": "normal",
        "privacy_class": "client_finance",
        "allowed_provider_policy": "local_generated_read_models_only",
    },
    {
        "operator_goal": "Follow up on Capital Hilton proposal.",
        "desired_outcome": "A proposal follow-up packet for internal review before any client-facing send.",
        "urgency": "normal",
        "privacy_class": "client_business_development",
        "allowed_provider_policy": "local_generated_read_models_only",
    },
    {
        "operator_goal": "Improve Helm so it feels less noisy.",
        "desired_outcome": "A Mac UI packet that clarifies Helm hierarchy without running workers.",
        "urgency": "normal",
        "privacy_class": "internal_system",
        "allowed_provider_policy": "local_generated_read_models_only",
    },
    {
        "operator_goal": "Set up a workflow for monthly St. Anne's work logging.",
        "desired_outcome": "A recurring work-log workflow plan with receipt and review gates.",
        "urgency": "normal",
        "privacy_class": "client_finance",
        "allowed_provider_policy": "local_generated_read_models_only",
    },
    {
        "operator_goal": "Can this run while I sleep?",
        "desired_outcome": "A bounded overnight review plan that cannot execute protected work.",
        "urgency": "overnight",
        "privacy_class": "mixed",
        "allowed_provider_policy": "local_generated_read_models_only",
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "workflow"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def _unique(items: tuple[str, ...] | list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _observed_status(payload: Mapping[str, Any], spec: Mapping[str, Any]) -> str:
    if spec.get("status_source") == "phase":
        phase_ref = str(spec.get("phase") or "")
        for phase in payload.get("phases") or []:
            if isinstance(phase, Mapping) and str(phase.get("phase") or "") == phase_ref:
                return str(phase.get("status") or "")
        return ""
    return str(payload.get("status") or payload.get("contract_status") or "")


def build_preconditions(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for precondition_ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        observed = _observed_status(payload, spec)
        required = str(spec["required_status"])
        source_ref = f"generated/read_models/{spec['filename']}"
        if spec.get("status_source") == "phase":
            source_ref += f"#phases.{spec.get('phase')}"
        rows.append(
            {
                "precondition_ref": precondition_ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": source_ref,
            }
        )
    return rows


def _gate(
    *,
    gate_id: str,
    protected_action: str,
    reason: str,
    blocked_actions: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "protected_action": protected_action,
        "status": "blocked_by_default",
        "plain_summary": reason,
        "blocked_actions": _unique(blocked_actions),
        "requires_operator_approval": True,
        "authority_granted": False,
        "safe_to_execute": False,
    }


def _step(
    *,
    plan_ref: str,
    index: int,
    owner: str,
    channel_ref: str,
    package_type: str,
    plain_summary: str,
    allowed_actions: tuple[str, ...] = (),
    blocked_actions: tuple[str, ...] = (),
) -> dict[str, Any]:
    if owner not in OWNER_VALUES:
        raise ValueError(f"unsupported owner: {owner}")
    return {
        "step_id": f"{plan_ref}.step_{index:02d}.{owner}",
        "owner": owner,
        "channel_ref": channel_ref,
        "package_type": package_type,
        "plain_summary": plain_summary,
        "allowed_actions": _unique((*COMMON_ALLOWED_ACTIONS, *allowed_actions)),
        "blocked_actions": _unique((*COMMON_BLOCKED_ACTIONS, *blocked_actions)),
        "requires_operator_approval": True,
        "result_receipt_required": True,
    }


def _speaker_summary(kind: str) -> dict[str, str]:
    summaries = {
        "st_annes_invoice": {
            "cassandra": "This is client finance prep: gather the St. Anne's monthly work context and explain what the invoice workflow is meant to accomplish.",
            "hermes": "Recommended sequence: context summary, package outline, protected gate review, then operator-visible packet staging only after approval.",
            "chief": "Convert the goal into review packets for invoice readiness, source evidence, and a later Mac/Excel review lane without executing the workflow.",
            "guardian": "Email send, Excel mutation, ledger, PDF export, submit, and mark-paid authority remain blocked.",
        },
        "capital_hilton_proposal": {
            "cassandra": "This is business-development follow-up, not a send instruction; the human meaning is to prepare an internal follow-up packet.",
            "hermes": "Recommended sequence: summarize proposal state, route Cassandra and Clara review context, then ask Chief for a dry-run package.",
            "chief": "Prepare a Capital Hilton proposal follow-up packet for operator review; do not send or create client-facing truth.",
            "guardian": "Client send, Gmail/browser/Coupa, ledger, and submit authority remain blocked.",
        },
        "helm_noise": {
            "cassandra": "The operator is asking for a calmer Helm experience, not a business action.",
            "hermes": "Recommended sequence: identify noisy surfaces, choose hierarchy changes, then hand Chief a Mac UI packet.",
            "chief": "Convert Hermes' UX recommendation into a MAC_CODEX packet preview with screenshot receipt requirements.",
            "guardian": "No worker may run, no git push may occur, and no live provider access is granted by this plan.",
        },
        "st_annes_work_logging": {
            "cassandra": "This is monthly work-log structure for St. Anne's, with receipts before it becomes invoice evidence.",
            "hermes": "Recommended sequence: define intake cadence, define receipt shape, then ask Chief for a bounded workflow package.",
            "chief": "Prepare the work-log workflow packet and review requirements without touching workbooks or ledgers.",
            "guardian": "Workbook mutation, ledger posting, send, PDF export, and automated recurrence execution are blocked.",
        },
        "overnight_safety": {
            "cassandra": "The operator is asking about unattended work. Treat it as a safety question first.",
            "hermes": "Recommended sequence: shrink scope to review-only, list gates, and require human review before any package or worker can run.",
            "chief": "At most, prepare a small overnight review workboard after approval; do not create a large work pile.",
            "guardian": "Send, Coupa, ledger, workbook mutation, workers, child agents, and external LLMs are blocked while unattended.",
        },
        "generic": {
            "cassandra": "Summarize the human goal and the current local context before any package exists.",
            "hermes": "Recommend a short pre-execution sequence with bottlenecks and review gates.",
            "chief": "Convert the sequence into bounded packets only if the operator later approves.",
            "guardian": "Protected authority and execution remain blocked by default.",
        },
    }
    return summaries.get(kind, summaries["generic"])


def _classify_goal(goal: str, desired_outcome: str = "") -> str:
    text = f"{goal} {desired_outcome}".lower().replace("'", "'")
    if "sleep" in text or "overnight" in text or "unattended" in text:
        return "overnight_safety"
    if "helm" in text or "noisy" in text or "less noise" in text:
        return "helm_noise"
    if "capital hilton" in text and "proposal" in text:
        return "capital_hilton_proposal"
    if ("st. anne" in text or "st anne" in text) and ("work log" in text or "work logging" in text):
        return "st_annes_work_logging"
    if ("st. anne" in text or "st anne" in text) and "invoice" in text:
        return "st_annes_invoice"
    return "generic"


def _st_annes_invoice_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="cassandra",
            channel_ref="finance_st_annes",
            package_type="client_finance_context_summary_packet",
            plain_summary="Summarize the St. Anne's monthly invoice goal, current work-log evidence, and what must be reviewed before invoice prep.",
            blocked_actions=("send_invoice_email", "mutate_excel_workbook"),
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="workflow_sequence_recommendation_packet",
            plain_summary="Recommend the smallest invoice-readiness sequence: verify source records, identify review gaps, then ask for package staging approval.",
            blocked_actions=("create_invoice", "export_invoice_pdf"),
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="st_annes_monthly_invoice_workflow_packet_preview",
            plain_summary="Convert the recommended sequence into a review packet outline with receipts and bottlenecks, without running the workflow.",
            blocked_actions=("run_worker", "stage_live_package_without_operator_approval"),
        ),
        _step(
            plan_ref=plan_ref,
            index=4,
            owner="guardian",
            channel_ref="security_guardian_gates",
            package_type="protected_invoice_gate_packet",
            plain_summary="Mark Excel, send, ledger, PDF, submit, and mark-paid gates as blocked until explicit operator-present approval.",
            blocked_actions=("send_email", "mutate_workbook", "export_pdf", "mutate_ledger", "submit_portal", "mark_paid"),
        ),
    ]
    gates = [
        _gate(gate_id="st_annes_invoice.email_send", protected_action="send_email", reason="Sending an invoice is a protected external action.", blocked_actions=("send_email", "open_gmail")),
        _gate(gate_id="st_annes_invoice.excel_mutation", protected_action="mutate_workbook", reason="Excel/workbook mutation is blocked during planning.", blocked_actions=("mutate_workbook", "run_excel_automation")),
        _gate(gate_id="st_annes_invoice.pdf_export", protected_action="export_pdf", reason="PDF export is a later artifact action, not composer work.", blocked_actions=("export_pdf",)),
        _gate(gate_id="st_annes_invoice.ledger", protected_action="mutate_ledger", reason="Ledger posting or payment truth is not part of planning.", blocked_actions=("mutate_ledger", "mark_paid")),
    ]
    bottlenecks = [
        "monthly work-log evidence must be reviewed before invoice packet staging",
        "source workbook or invoice artifact gates need operator approval",
        "send/PDF/ledger actions are protected and cannot be bundled into planning",
    ]
    return steps, gates, bottlenecks, "medium", "Review this invoice workflow plan, then approve a dry-run package only if the evidence sources look right.", "st_annes_invoice"


def _capital_hilton_proposal_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="cassandra",
            channel_ref="business_development_capital_hilton",
            package_type="capital_hilton_proposal_context_packet",
            plain_summary="Summarize the Capital Hilton proposal state and the human follow-up intent for internal review.",
            blocked_actions=("send_client_followup", "open_gmail"),
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="proposal_followup_sequence_packet",
            plain_summary="Recommend a short follow-up sequence: Cassandra summary, Clara internal review state, Chief package outline, then operator review.",
            blocked_actions=("send_email", "create_client_commitment"),
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="capital_hilton_cassandra_clara_followup_packet_preview",
            plain_summary="Convert the Cassandra/Clara follow-up route into a dry-run packet; no client-facing send is permitted.",
            allowed_actions=("name_target_agent_refs_cassandra_clara",),
            blocked_actions=("send_email", "submit_portal", "mark_paid"),
        ),
        _step(
            plan_ref=plan_ref,
            index=4,
            owner="guardian",
            channel_ref="security_guardian_gates",
            package_type="protected_correspondence_gate_packet",
            plain_summary="Mark client send, Gmail/browser, Coupa, ledger, and submit authority as blocked.",
            blocked_actions=("send_email", "open_gmail", "open_browser", "open_coupa", "mutate_ledger", "submit_portal"),
        ),
    ]
    gates = [
        _gate(gate_id="capital_hilton_proposal.email_send", protected_action="send_email", reason="Proposal follow-up can be drafted for review, but cannot be sent.", blocked_actions=("send_email", "open_gmail")),
        _gate(gate_id="capital_hilton_proposal.business_commitment", protected_action="perform_business_action", reason="The composer cannot create client-facing commitments or business truth.", blocked_actions=("perform_business_action", "grant_authority")),
    ]
    bottlenecks = [
        "proposal state must be summarized before any draft packet",
        "Clara review is internal only and cannot send to the client",
        "operator must approve any later correspondence package",
    ]
    return steps, gates, bottlenecks, "medium", "Review the Cassandra/Clara follow-up route, then approve a dry-run package if it matches the relationship context.", "capital_hilton_proposal"


def _helm_noise_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="helm_noise_reduction_sequence_packet",
            plain_summary="Identify why Helm feels noisy and recommend a smaller hierarchy for visible next moves.",
            blocked_actions=("run_worker", "push_git"),
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="helm_mac_codex_packet_outline",
            plain_summary="Convert Hermes' recommendation into a MAC_CODEX UI packet preview with screenshot and receipt requirements.",
            blocked_actions=("spawn_worker", "run_worker", "push_git"),
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="mac_codex",
            channel_ref="build_mission_control_mac",
            package_type="mac_codex_helm_ui_worker_packet_preview",
            plain_summary="Define the future Mac UI work packet only; no worker runs and no app code changes happen here.",
            blocked_actions=("run_worker", "run_child_agent", "push_git"),
        ),
    ]
    gates = [
        _gate(gate_id="helm_noise.worker_execution", protected_action="run_worker", reason="Composer may describe a MAC_CODEX packet, but cannot run it.", blocked_actions=("spawn_worker", "run_worker", "run_child_agent")),
        _gate(gate_id="helm_noise.git_push", protected_action="push_git", reason="UI work cannot be pushed by the composer.", blocked_actions=("push_git",)),
    ]
    bottlenecks = [
        "operator needs to choose which noise source matters first",
        "Mac UI work needs a separate approved packet and screenshot proof",
        "avoid bundling unrelated Helm redesigns into one large packet",
    ]
    return steps, gates, bottlenecks, "low", "Approve a narrow MAC_CODEX UI packet only after choosing the first Helm noise source to fix.", "helm_noise"


def _st_annes_work_logging_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="cassandra",
            channel_ref="finance_st_annes",
            package_type="st_annes_work_log_context_packet",
            plain_summary="Summarize the recurring monthly work logging need and the receipt fields that should be reviewed.",
            blocked_actions=("mutate_workbook", "mutate_ledger"),
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="monthly_work_log_sequence_packet",
            plain_summary="Recommend a small recurring workflow shape: intake, review, receipt, then optional invoice rollup after approval.",
            blocked_actions=("launch_agent_loop", "run_worker"),
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="st_annes_monthly_work_logging_packet_preview",
            plain_summary="Convert the monthly work-log route into a staged packet outline with no recurrence execution.",
            blocked_actions=("run_worker", "launch_agent_loop", "mutate_workbook"),
        ),
        _step(
            plan_ref=plan_ref,
            index=4,
            owner="guardian",
            channel_ref="security_guardian_gates",
            package_type="protected_work_log_gate_packet",
            plain_summary="Mark workbook, ledger, send, PDF, and unattended recurrence gates as blocked.",
            blocked_actions=("mutate_workbook", "mutate_ledger", "send_email", "export_pdf", "launch_agent_loop"),
        ),
    ]
    gates = [
        _gate(gate_id="st_annes_work_logging.workbook_mutation", protected_action="mutate_workbook", reason="Work logging may define fields, but cannot edit a workbook.", blocked_actions=("mutate_workbook", "run_excel_automation")),
        _gate(gate_id="st_annes_work_logging.recurrence", protected_action="launch_agent_loop", reason="Recurring unattended execution is outside composer authority.", blocked_actions=("launch_agent_loop", "run_worker")),
    ]
    bottlenecks = [
        "operator must approve the monthly receipt shape",
        "recurrence should start as review reminders, not autonomous execution",
        "invoice rollup remains a separate protected workflow",
    ]
    return steps, gates, bottlenecks, "medium", "Review the receipt fields, then approve only the smallest monthly work-log packet.", "st_annes_work_logging"


def _overnight_safety_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="cassandra",
            channel_ref="operator_safety",
            package_type="overnight_intent_summary_packet",
            plain_summary="Restate the sleep question as an unattended-safety review, not permission to run business workflows.",
            blocked_actions=("send_email", "open_coupa", "mutate_ledger", "mutate_workbook", "run_worker"),
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="bounded_overnight_sequence_packet",
            plain_summary="Recommend only a small review queue that can wait for morning operator approval.",
            blocked_actions=("spawn_worker", "run_child_agent", "launch_agent_loop", "call_external_llm"),
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="overnight_review_workboard_packet_preview",
            plain_summary="Convert the idea into a limited review workboard; do not create a large pile of packages.",
            blocked_actions=("stage_live_package_without_operator_approval", "run_worker", "perform_business_action"),
        ),
        _step(
            plan_ref=plan_ref,
            index=4,
            owner="guardian",
            channel_ref="security_guardian_gates",
            package_type="unattended_execution_gate_packet",
            plain_summary="Block send, Coupa, ledger, workbook mutation, workers, child agents, loops, and external LLM calls while unattended.",
            blocked_actions=("send_email", "open_coupa", "mutate_ledger", "mutate_workbook", "spawn_worker", "run_worker", "run_child_agent", "launch_agent_loop", "call_external_llm"),
        ),
    ]
    gates = [
        _gate(gate_id="overnight.email_send", protected_action="send_email", reason="Unattended send is blocked.", blocked_actions=("send_email", "open_gmail")),
        _gate(gate_id="overnight.coupa", protected_action="open_coupa", reason="Coupa access or submit cannot run while unattended.", blocked_actions=("open_coupa", "submit_portal")),
        _gate(gate_id="overnight.ledger", protected_action="mutate_ledger", reason="Ledger or payment truth cannot change while unattended.", blocked_actions=("mutate_ledger", "mark_paid")),
        _gate(gate_id="overnight.workbook", protected_action="mutate_workbook", reason="Workbook read/write automation is blocked while unattended.", blocked_actions=("open_workbook", "read_workbook_body", "read_spreadsheet_cells", "mutate_workbook")),
        _gate(gate_id="overnight.workers", protected_action="run_worker", reason="No worker, child agent, loop, or external LLM can run from this composer.", blocked_actions=("spawn_worker", "run_worker", "run_child_agent", "launch_agent_loop", "call_external_llm")),
    ]
    bottlenecks = [
        "unattended work must be review-only",
        "protected actions need morning operator approval",
        "scope must be capped to avoid a large unreviewed package pile",
    ]
    return steps, gates, bottlenecks, "high", "Stage at most a small overnight review list after approval; execute nothing while unattended.", "overnight_safety"


def _generic_plan(plan_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str, str, str]:
    steps = [
        _step(
            plan_ref=plan_ref,
            index=1,
            owner="cassandra",
            channel_ref="operator_intake",
            package_type="goal_context_summary_packet",
            plain_summary="Summarize the operator goal and identify what local context should be read.",
        ),
        _step(
            plan_ref=plan_ref,
            index=2,
            owner="hermes",
            channel_ref="workflow_architecture",
            package_type="workflow_sequence_recommendation_packet",
            plain_summary="Recommend a short sequence and likely bottlenecks before any package is staged.",
        ),
        _step(
            plan_ref=plan_ref,
            index=3,
            owner="chief",
            channel_ref="operations_chief_workboard",
            package_type="workflow_packet_outline",
            plain_summary="Convert the recommendation into a reviewable packet outline if the operator approves.",
        ),
        _step(
            plan_ref=plan_ref,
            index=4,
            owner="guardian",
            channel_ref="security_guardian_gates",
            package_type="protected_authority_scan_packet",
            plain_summary="Mark protected actions blocked and require receipts for later work.",
        ),
    ]
    gates = [
        _gate(gate_id="generic.execution", protected_action="run_worker", reason="Composer output is planning only.", blocked_actions=("spawn_worker", "run_worker", "run_child_agent")),
    ]
    bottlenecks = [
        "goal may need a narrower first packet",
        "operator review is required before package staging",
        "protected actions remain blocked",
    ]
    return steps, gates, bottlenecks, "medium", "Review the proposed sequence and narrow it before approving any package staging.", "generic"


PLAN_BUILDERS = {
    "st_annes_invoice": _st_annes_invoice_plan,
    "capital_hilton_proposal": _capital_hilton_proposal_plan,
    "helm_noise": _helm_noise_plan,
    "st_annes_work_logging": _st_annes_work_logging_plan,
    "overnight_safety": _overnight_safety_plan,
    "generic": _generic_plan,
}


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    grants: list[str] = []
    for key, value in _walk_values(payload):
        if key in UNSAFE_TRUE_KEYS and value is True:
            grants.append(key)
    return sorted(set(grants))


def build_workflow_plan(
    *,
    operator_goal: str,
    desired_outcome: str,
    current_world_ref: str | None = None,
    current_thread_ref: str | None = None,
    urgency: str = "normal",
    privacy_class: str = "internal",
    allowed_provider_policy: str = "local_generated_read_models_only",
    no_external_action_by_default: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    kind = _classify_goal(operator_goal, desired_outcome)
    plan_ref = f"workflow_plan:{_slug(kind)}:{_short_hash(operator_goal, desired_outcome, current_world_ref, current_thread_ref)}"
    steps, gates, bottlenecks, risk, recommended_next_action, summary_kind = PLAN_BUILDERS[kind](plan_ref)
    payload: dict[str, Any] = {
        "workflow_plan_id": plan_ref,
        "goal": operator_goal,
        "generated_at": generated_at,
        "composer_mode": "pre_execution_planning_only",
        "composer_input": {
            "operator_goal": operator_goal,
            "current_world_ref": current_world_ref or "",
            "current_thread_ref": current_thread_ref or "",
            "desired_outcome": desired_outcome,
            "urgency": urgency,
            "privacy_class": privacy_class,
            "allowed_provider_policy": allowed_provider_policy,
            "no_external_action_by_default": no_external_action_by_default,
        },
        "speaker_summary": _speaker_summary(summary_kind),
        "steps": steps,
        "guardian_gates": gates,
        "likely_bottlenecks": bottlenecks,
        "work_in_progress_risk": risk,
        "recommended_next_action": recommended_next_action,
        "safe_to_stage": bool(no_external_action_by_default),
        "safe_to_execute": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "composer_only_plans": True,
            "stage_requires_later_operator_approval": True,
            "safe_to_execute_false": True,
            "all_steps_have_receipts": all(step.get("result_receipt_required") is True for step in steps),
            "all_steps_require_operator_approval": all(step.get("requires_operator_approval") is True for step in steps),
            "guardian_gates_blocked_by_default": all(gate.get("status") == "blocked_by_default" for gate in gates),
            "external_action_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "external_llm_called": False,
            "git_push_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = build_preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Transparent pre-execution workflow planning before any worker runs or business action occurs.",
        "preconditions": preconditions,
        "input_contract": {
            "required_fields": [
                "operator_goal",
                "desired_outcome",
                "urgency",
                "privacy_class",
                "allowed_provider_policy",
                "no_external_action_by_default",
            ],
            "optional_fields": ["current_world_ref", "current_thread_ref"],
            "defaults": {
                "allowed_provider_policy": "local_generated_read_models_only",
                "no_external_action_by_default": True,
            },
        },
        "output_contract": {
            "required_fields": [
                "workflow_plan_id",
                "goal",
                "speaker_summary",
                "steps",
                "guardian_gates",
                "work_in_progress_risk",
                "recommended_next_action",
                "safe_to_stage",
                "safe_to_execute",
            ],
            "step_required_fields": [
                "step_id",
                "owner",
                "channel_ref",
                "package_type",
                "plain_summary",
                "allowed_actions",
                "blocked_actions",
                "requires_operator_approval",
                "result_receipt_required",
            ],
            "owner_values": list(OWNER_VALUES),
            "risk_values": list(RISK_VALUES),
        },
        "composer_rules": [
            "Composer only plans.",
            "Hermes recommends the sequence.",
            "Chief converts the sequence into packet outlines.",
            "Guardian marks protected gates.",
            "Cassandra summarizes the human meaning.",
            "A package may be staged only after later operator approval.",
            "No worker is spawned and no child agent is run.",
            "No business action occurs.",
            "Protected authority is never granted by this contract.",
            "Plans must surface bottlenecks and avoid large unreviewed work piles.",
        ],
        "required_examples": [item["operator_goal"] for item in EXAMPLE_INPUTS],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "contract_only": True,
            "read_model_only": True,
            "external_action_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "external_llm_called": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe_true_grants(payload)
    return payload


def build_latest_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    example_plans = [
        build_workflow_plan(
            operator_goal=str(item["operator_goal"]),
            desired_outcome=str(item["desired_outcome"]),
            urgency=str(item["urgency"]),
            privacy_class=str(item["privacy_class"]),
            allowed_provider_policy=str(item["allowed_provider_policy"]),
            generated_at=generated_at,
        )
        for item in EXAMPLE_INPUTS
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": LATEST_READ_MODEL_ID,
        "status": contract["status"],
        "generated_at": generated_at,
        "contract_ref": f"generated/read_models/{CONTRACT_JSON_EXPORT_NAME}",
        "latest_plan": example_plans[0],
        "example_plans": example_plans,
        "example_plan_count": len(example_plans),
        "preconditions": contract["preconditions"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": contract["machine_proof"]["preconditions_ready"],
            "all_example_plans_safe_to_execute_false": all(plan["safe_to_execute"] is False for plan in example_plans),
            "all_example_plans_have_guardian_gates": all(bool(plan["guardian_gates"]) for plan in example_plans),
            "all_example_plans_have_bottlenecks": all(bool(plan["likely_bottlenecks"]) for plan in example_plans),
            "all_steps_have_receipts": all(
                step.get("result_receipt_required") is True
                for plan in example_plans
                for step in plan["steps"]
            ),
            "no_worker_spawn_or_execution": True,
            "external_action_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "external_llm_called": False,
            "git_push_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_wiki(contract: Mapping[str, Any], latest: Mapping[str, Any]) -> str:
    lines = [
        "# Workflow Composer",
        "",
        f"Status: `{latest.get('status', NOT_READY_STATUS)}`",
        "",
        "Workflow Composer turns an operator goal into a transparent pre-execution plan. It does not execute workers or perform business actions.",
        "",
        "## Roles",
        "",
        "- Cassandra summarizes the human meaning.",
        "- Hermes recommends the sequence.",
        "- Chief converts the sequence into packet outlines.",
        "- Guardian marks protected gates.",
        "",
        "## Required Examples",
        "",
    ]
    for plan in latest.get("example_plans") or []:
        if not isinstance(plan, Mapping):
            continue
        lines.extend(
            [
                f"### `{plan.get('workflow_plan_id')}`",
                "",
                f"- Goal: {plan.get('goal')}",
                f"- Risk: `{plan.get('work_in_progress_risk')}`",
                f"- Safe to stage: `{str(plan.get('safe_to_stage')).lower()}`",
                f"- Safe to execute: `{str(plan.get('safe_to_execute')).lower()}`",
                f"- Recommended next action: {plan.get('recommended_next_action')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- Planning only.",
            "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, push, worker, child-agent, agent-loop, or external-LLM authority.",
            "- Later package staging requires operator approval.",
            "- Plans must expose bottlenecks and avoid large unreviewed piles of work.",
            "",
            "## Contract",
            "",
            f"- Contract read-model: `generated/read_models/{CONTRACT_JSON_EXPORT_NAME}`",
            f"- Latest read-model: `generated/read_models/{LATEST_JSON_EXPORT_NAME}`",
            f"- Preconditions ready: `{str(contract.get('machine_proof', {}).get('preconditions_ready')).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workflow_composer(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    latest = build_latest_read_model(read_model_root=read_model_root, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    contract_path.write_text(stable_json(contract), encoding="utf-8")
    latest_path.write_text(stable_json(latest), encoding="utf-8")

    bridge_contract_path = ""
    bridge_latest_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, latest), encoding="utf-8")

    return {
        "status": str(latest["status"]),
        "contract_path": contract_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "example_plan_count": str(latest["example_plan_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Workflow Composer V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workflow_composer(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['example_plan_count']} example plans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
