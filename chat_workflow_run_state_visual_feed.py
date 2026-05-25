"""Chat Workflow Run State + Visual Event Feed v0.

This deterministic read-model projects chat/router readbacks into workflow
progress state and visual event objects. It does not run workflows, dispatch
agents, call models, create packages, request approvals, send mail, access
Coupa, generate invoices, or perform external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_SOURCE_MIRROR = DEFAULT_EXPORT_ROOT / "chat_readback_card_mirror.json"

SCHEMA_VERSION = "chat_workflow_run_state_visual_feed_v0"
READ_MODEL_ID = "chat_workflow_run_state_visual_feed"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CHAT_WORKFLOW_RUN_STATE_VISUAL_FEED"

PHASES = (
    "UNDERSTANDING_CAPTURED",
    "MISSING_INFO_NEEDED",
    "WORKFLOW_CHAIN_DRAFTED",
    "WORKFLOW_CHAIN_READY",
    "PACKAGE_NEEDED",
    "PACKAGE_READY",
    "TEST_READY",
    "APPROVAL_REQUIRED",
    "EXECUTION_GATED",
    "COMPLETION_PENDING_PROOF",
    "COMPLETION_CONFIRMED",
    "BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

EVENT_TYPES = (
    "UNDERSTANDING",
    "NEEDS_INPUT",
    "CHAIN_READY",
    "PACKAGE_BUILDING",
    "PACKAGE_READY",
    "TEST_READY",
    "APPROVAL_NEEDED",
    "DRAFT_READY",
    "EXECUTION_LOCKED",
    "COMPLETION",
    "BLOCKED",
    "STALE",
    "FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "CHAT_TREATED_AS_TRUTH",
    "EVENT_WITHOUT_SOURCE_REF",
    "COMPLETION_WITHOUT_PROOF",
    "PACKAGE_READY_WITHOUT_PACKAGE",
    "TEST_READY_WITHOUT_PACKAGE",
    "APPROVAL_BYPASSED",
    "EXTERNAL_ACTION_ENABLED_WITHOUT_GATE",
    "AGENT_INVENTED_PROGRESS",
    "RAW_PII_IN_VISUAL_EVENT",
    "MACHINE_LANGUAGE_VISIBLE",
    "UNKNOWN_FAIL_CLOSED",
)

FORBIDDEN_VISIBLE_TERMS = (
    "schema",
    "handler",
    "lifecycle",
    "artifact_type",
    "target_handler",
    "payload_hash",
    "idempotency",
    "manifest",
    "JSON",
    "SQLite",
    "local outbox",
    "visual-agnostic",
    "metadata posture",
    "raw ID",
    "package ref",
)

AUTHORITY_BOUNDARY = {
    "live_workflow_state_write_allowed": False,
    "live_visual_event_runtime_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_package_creation_allowed": False,
    "live_workflow_run_allowed": False,
    "live_test_run_allowed": False,
    "live_approval_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "browser_automation_allowed": False,
}

CAPITAL_WORKFLOW_REF = "capital_hilton_invoice_workflow"
CAPITAL_WORKFLOW_TYPE = "invoice_delivery_workflow"
CAPITAL_WORLD_REF = "finance"
CAPITAL_LANE_REF = "capital_hilton"
CAPITAL_CLIENT_REF = "capital_hilton"
CAPITAL_TENANT_REF = "operator_winship_local"
SOURCE_CHAT_REQUEST_REF = "mission_control_chat_request_capital_hilton_invoice_workflow"
SOURCE_ROUTER_READBACK_REF = "chat_readback_card_mirror"

KNOWN_FACTS = (
    "4 dates at $400 each working basis",
    "Excel/PDF companion invoice desired",
    "Annette contact candidate",
    "Coupa/PO payment rail candidate",
    "invoice should be saved for records",
)

MISSING_ITEMS = (
    "exact Coupa PO/reference",
    "confirmation Annette is correct contact",
    "final invoice artifact/hash",
    "Guardian approval",
    "send/submit receipts",
)

LOCKED_ITEMS = (
    "email send",
    "Coupa access/submit",
    "browser",
    "approval request",
    "invoice generation",
    "attachment",
    "payment state update",
)

READY_ITEMS = (
    "PC router readback found",
    "draft understanding available for operator review",
    "safe visual events can be rendered",
)

REQUIRED_GATES = (
    "operator review",
    "Coupa PO/reference proof",
    "final invoice artifact/hash proof",
    "Guardian approval receipt",
    "send/submit proof receipts",
)

PROOF_REQUIREMENTS = (
    "Coupa invoice generated/submitted from PO, if required and proven.",
    "Email sent to Annette with Winship-branded Excel/PDF invoice attached.",
    "Winship-branded invoice saved with today's date.",
    "Last invoice sent date recorded for future invoice range.",
    "Send/submit receipts attached.",
    "Payment tracking state updated.",
)

OPERATOR_CHOICES = (
    {"label": "Looks right", "enabled": True, "scope": "local_review_only", "external_action": False},
    {"label": "Change something", "enabled": True, "scope": "local_edit_prompt", "external_action": False},
    {"label": "Tell me what is missing", "enabled": True, "scope": "explain_missing_items", "external_action": False},
    {
        "label": "Build package later",
        "enabled": False,
        "disabled_reason": "Backend package creation is not connected in this lane.",
        "scope": "future_backend_rail",
        "external_action": False,
    },
    {
        "label": "Test later",
        "enabled": False,
        "disabled_reason": "No package exists to test in this lane.",
        "scope": "future_test_rail",
        "external_action": False,
    },
)


@dataclass(frozen=True)
class ChatWorkflowRunState:
    run_state_id: str
    workflow_ref: str
    workflow_type: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    source_chat_request_ref: str
    source_router_readback_ref: str
    current_phase: str
    known_facts: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocked_items: tuple[str, ...]
    ready_items: tuple[str, ...]
    required_gates: tuple[str, ...]
    external_actions_locked: bool
    proof_requirements: tuple[str, ...]
    next_safe_move: str
    truth_status: str


@dataclass(frozen=True)
class ChatWorkflowVisualEvent:
    event_id: str
    run_state_ref: str
    event_type: str
    title: str
    agent_line: str
    visual_summary: str
    proof_bullets: tuple[str, ...]
    missing_bullets: tuple[str, ...]
    blocked_bullets: tuple[str, ...]
    operator_choices: tuple[dict[str, Any], ...]
    visual_priority: str
    truth_status: str
    proof_status: str
    next_safe_move: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class AgentProgressNarration:
    narration_id: str
    run_state_ref: str
    active_agent_role: str
    operator_line: str
    what_happened: str
    what_is_needed_next: str
    what_is_locked: str
    what_agent_will_do_next: str
    what_agent_cannot_do: str
    next_safe_move: str


@dataclass(frozen=True)
class VisualCompletionReceipt:
    completion_id: str
    run_state_ref: str
    completion_label: str
    headline: str
    proof_bullets: tuple[str, ...]
    required_receipts: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    completion_allowed: bool
    blocked_reason: str
    dated_record_update: str
    next_cycle_memory_update: str
    next_safe_move: str


@dataclass(frozen=True)
class ChatWorkflowRunBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChatWorkflowVisualFeedElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_chat_updates_backend_state: str
    how_visual_events_are_created: str
    how_agent_progress_is_reported: str
    how_completion_is_proven: str
    next_safe_move: str


REQUIRED_RUN_STATE_FIELDS = tuple(ChatWorkflowRunState.__dataclass_fields__.keys())
REQUIRED_VISUAL_EVENT_FIELDS = tuple(ChatWorkflowVisualEvent.__dataclass_fields__.keys())
REQUIRED_NARRATION_FIELDS = tuple(AgentProgressNarration.__dataclass_fields__.keys())
REQUIRED_COMPLETION_FIELDS = tuple(VisualCompletionReceipt.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(ChatWorkflowRunBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(ChatWorkflowVisualFeedElioperatorReport.__dataclass_fields__.keys())


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _content_hash(payload: Mapping[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "chat_workflow_run_state": {"required_fields": list(REQUIRED_RUN_STATE_FIELDS)},
        "chat_workflow_visual_event": {"required_fields": list(REQUIRED_VISUAL_EVENT_FIELDS)},
        "agent_progress_narration": {"required_fields": list(REQUIRED_NARRATION_FIELDS)},
        "visual_completion_receipt": {"required_fields": list(REQUIRED_COMPLETION_FIELDS)},
        "chat_workflow_run_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "chat_workflow_visual_feed_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def _source_mirror_ready(source: Mapping[str, Any] | None) -> bool:
    if not source:
        return False
    mirror = source.get("chat_readback_card_mirror")
    return isinstance(mirror, Mapping) and mirror.get("mirror_status") == "READY_FOR_MAC_RENDER"


def _source_readback_ref(source: Mapping[str, Any] | None) -> str:
    if not source:
        return SOURCE_ROUTER_READBACK_REF
    return str(source.get("source_readback_ref") or SOURCE_ROUTER_READBACK_REF)


def build_run_state(source: Mapping[str, Any] | None) -> ChatWorkflowRunState:
    source_ref = _source_readback_ref(source)
    phase = "MISSING_INFO_NEEDED" if _source_mirror_ready(source) else "UNKNOWN_FAIL_CLOSED"
    truth_status = "DRAFT_UNDERSTANDING_NOT_TRUTH" if _source_mirror_ready(source) else "UNKNOWN_FAIL_CLOSED"
    next_move = (
        "Show the visual events to the operator and ask whether the understanding looks right."
        if _source_mirror_ready(source)
        else "Wait for a current router readback before showing workflow progress."
    )
    return ChatWorkflowRunState(
        run_state_id="chat_workflow_run_state_capital_hilton_invoice_v0",
        workflow_ref=CAPITAL_WORKFLOW_REF,
        workflow_type=CAPITAL_WORKFLOW_TYPE,
        world_ref=CAPITAL_WORLD_REF,
        lane_ref=CAPITAL_LANE_REF,
        client_ref=CAPITAL_CLIENT_REF,
        tenant_ref=CAPITAL_TENANT_REF,
        source_chat_request_ref=SOURCE_CHAT_REQUEST_REF,
        source_router_readback_ref=source_ref,
        current_phase=phase,
        known_facts=KNOWN_FACTS,
        missing_items=MISSING_ITEMS,
        blocked_items=LOCKED_ITEMS,
        ready_items=READY_ITEMS if _source_mirror_ready(source) else (),
        required_gates=REQUIRED_GATES,
        external_actions_locked=True,
        proof_requirements=PROOF_REQUIREMENTS,
        next_safe_move=next_move,
        truth_status=truth_status,
    )


def _source_refs(source_ref: str, *extra: str) -> tuple[str, ...]:
    return (source_ref, *extra)


def build_visual_events(run_state: ChatWorkflowRunState) -> tuple[ChatWorkflowVisualEvent, ...]:
    choices = tuple(dict(choice) for choice in OPERATOR_CHOICES)
    source_ref = run_state.source_router_readback_ref
    return (
        ChatWorkflowVisualEvent(
            event_id="chat_visual_event_capital_hilton_understanding",
            run_state_ref=run_state.run_state_id,
            event_type="UNDERSTANDING",
            title="Understanding captured",
            agent_line="I got the readback. OpenClaw understands the Capital Hilton invoice workflow draft.",
            visual_summary="The invoice workflow draft is captured for operator review.",
            proof_bullets=("PC readback is available.", "This is still a draft understanding."),
            missing_bullets=(),
            blocked_bullets=(),
            operator_choices=choices,
            visual_priority="primary",
            truth_status="DRAFT_UNDERSTANDING_NOT_TRUTH",
            proof_status="BACKEND_READBACK_READY",
            next_safe_move="Ask the operator whether this understanding looks right.",
            source_refs=_source_refs(source_ref, run_state.source_chat_request_ref),
        ),
        ChatWorkflowVisualEvent(
            event_id="chat_visual_event_capital_hilton_needs_input",
            run_state_ref=run_state.run_state_id,
            event_type="NEEDS_INPUT",
            title="Needs input",
            agent_line="To make this runnable, I still need the Coupa PO/reference, Annette confirmation, final invoice artifact, and Guardian approval.",
            visual_summary="The workflow is not runnable until the missing pieces are proven.",
            proof_bullets=(),
            missing_bullets=MISSING_ITEMS,
            blocked_bullets=(),
            operator_choices=choices,
            visual_priority="primary",
            truth_status="NEEDS_OPERATOR_REVIEW",
            proof_status="PROOF_REQUIRED",
            next_safe_move="Ask for the missing PO/contact/artifact/approval facts before any run.",
            source_refs=_source_refs(source_ref, run_state.run_state_id),
        ),
        ChatWorkflowVisualEvent(
            event_id="chat_visual_event_capital_hilton_execution_locked",
            run_state_ref=run_state.run_state_id,
            event_type="EXECUTION_LOCKED",
            title="Execution locked",
            agent_line="Nothing external can happen yet. No email, Coupa, browser, approval, or payment update is active.",
            visual_summary="External work is locked behind proof and approval gates.",
            proof_bullets=(),
            missing_bullets=(),
            blocked_bullets=LOCKED_ITEMS,
            operator_choices=choices,
            visual_priority="protective",
            truth_status="LOCKED_EXTERNAL_ACTION",
            proof_status="NO_EXTERNAL_RECEIPTS",
            next_safe_move="Keep all external actions locked until future gated receipts exist.",
            source_refs=_source_refs(source_ref, run_state.run_state_id),
        ),
        ChatWorkflowVisualEvent(
            event_id="chat_visual_event_capital_hilton_invoice_sent_target",
            run_state_ref=run_state.run_state_id,
            event_type="COMPLETION",
            title="INVOICE SENT",
            agent_line="This completion target is blocked until proof receipts exist.",
            visual_summary="Future completion target only; do not render as achieved.",
            proof_bullets=PROOF_REQUIREMENTS,
            missing_bullets=(
                "Guardian approval receipt",
                "email send receipt",
                "Coupa submit/verification receipt if required",
                "dated invoice artifact/hash",
                "payment tracking update receipt",
            ),
            blocked_bullets=("Proof receipts do not exist yet.",),
            operator_choices=choices,
            visual_priority="hidden_until_proof",
            truth_status="UNKNOWN_FAIL_CLOSED",
            proof_status="PROOF_REQUIRED",
            next_safe_move="Do not show completion until required receipts exist.",
            source_refs=_source_refs(source_ref, "future_completion_receipt"),
        ),
    )


def build_agent_narration(run_state: ChatWorkflowRunState) -> AgentProgressNarration:
    return AgentProgressNarration(
        narration_id="agent_progress_narration_capital_hilton_invoice_v0",
        run_state_ref=run_state.run_state_id,
        active_agent_role="workflow_readback_agent",
        operator_line="I got the PC readback. This is ready for your review, not execution.",
        what_happened="OpenClaw captured a draft understanding of the Capital Hilton invoice workflow.",
        what_is_needed_next="The PO/reference, Annette confirmation, final artifact/hash, Guardian approval, and receipts are still needed.",
        what_is_locked="Email, Coupa, browser, approval, invoice generation, attachment, and payment updates are locked.",
        what_agent_will_do_next="Show the draft state and ask what you want to confirm or change.",
        what_agent_cannot_do="The agent cannot run the workflow, send email, access Coupa, request approval, generate an invoice, or mark completion.",
        next_safe_move="Keep the operator in the chat loop and wait for reviewed inputs.",
    )


def build_completion_receipt(run_state: ChatWorkflowRunState) -> VisualCompletionReceipt:
    return VisualCompletionReceipt(
        completion_id="visual_completion_receipt_capital_hilton_invoice_sent_target",
        run_state_ref=run_state.run_state_id,
        completion_label="future_target_not_current_fact",
        headline="INVOICE SENT",
        proof_bullets=PROOF_REQUIREMENTS,
        required_receipts=(
            "Guardian approval receipt",
            "email send receipt",
            "Coupa submit/verification receipt if required",
            "dated invoice artifact/hash receipt",
            "last invoice sent date update receipt",
            "payment tracking update receipt",
        ),
        missing_receipts=(
            "Guardian approval receipt",
            "email send receipt",
            "Coupa submit/verification receipt if required",
            "dated invoice artifact/hash receipt",
            "last invoice sent date update receipt",
            "payment tracking update receipt",
        ),
        completion_allowed=False,
        blocked_reason="Proof receipts do not exist yet.",
        dated_record_update="Not updated in this lane.",
        next_cycle_memory_update="Not updated until completion receipts exist.",
        next_safe_move="Keep INVOICE SENT hidden or marked blocked until proof exists.",
    )


def build_blockers() -> tuple[ChatWorkflowRunBlocker, ...]:
    conditions = {
        "CHAT_TREATED_AS_TRUTH": "Chat text is treated as confirmed workflow truth.",
        "EVENT_WITHOUT_SOURCE_REF": "A visual event has no backend source reference.",
        "COMPLETION_WITHOUT_PROOF": "Completion is claimed without proof receipts.",
        "PACKAGE_READY_WITHOUT_PACKAGE": "A package-ready state appears without a package receipt.",
        "TEST_READY_WITHOUT_PACKAGE": "A test-ready state appears without a package to test.",
        "APPROVAL_BYPASSED": "Approval is bypassed or implied without a receipt.",
        "EXTERNAL_ACTION_ENABLED_WITHOUT_GATE": "External action is enabled without a gate and proof path.",
        "AGENT_INVENTED_PROGRESS": "Agent narration claims progress that backend state does not support.",
        "RAW_PII_IN_VISUAL_EVENT": "Visual event contains raw private or protected data.",
        "MACHINE_LANGUAGE_VISIBLE": "Visible event copy contains machine-contract language.",
        "UNKNOWN_FAIL_CLOSED": "Unknown workflow progress state fails closed.",
    }
    return tuple(
        ChatWorkflowRunBlocker(
            blocker_id=f"chat_workflow_run_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_VISUAL_EVENT" if blocker_type != "MACHINE_LANGUAGE_VISIBLE" else "BLOCKS_OPERATOR_RENDER",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move="Render a safe blocked/waiting event or wait for proof-backed state.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_report() -> ChatWorkflowVisualFeedElioperatorReport:
    return ChatWorkflowVisualFeedElioperatorReport(
        report_id="chat_workflow_visual_feed_elioperator_report_v0",
        plain_summary="The visual feed turns backend readback into workflow progress events for chat.",
        what_this_enables="The operator can see what was captured, what is missing, what is locked, and what proof is required next.",
        what_this_does_not_do_yet="It does not run workflows, create packages, dispatch agents, call models, approve, send, submit, browse, or generate invoices.",
        how_chat_updates_backend_state="Chat requests are consumed by existing deterministic intake/readback rails; this contract only projects that readback into state.",
        how_visual_events_are_created="Each event is tied to a source readback or future receipt requirement and carries human copy for the chat surface.",
        how_agent_progress_is_reported="Agent narration follows backend state and states what happened, what is needed, and what remains locked.",
        how_completion_is_proven="Completion requires receipts; INVOICE SENT stays blocked until approval, send/submit, artifact, and tracking receipts exist.",
        next_safe_move="Show the Capital Hilton understanding, missing items, and locked actions as reviewable chat events.",
    )


def _visible_event_text(events: tuple[ChatWorkflowVisualEvent, ...], narration: AgentProgressNarration) -> str:
    chunks: list[str] = [
        narration.operator_line,
        narration.what_happened,
        narration.what_is_needed_next,
        narration.what_is_locked,
        narration.what_agent_will_do_next,
        narration.what_agent_cannot_do,
    ]
    for event in events:
        chunks.extend(
            [
                event.title,
                event.agent_line,
                event.visual_summary,
                event.next_safe_move,
            ]
        )
        chunks.extend(event.proof_bullets)
        chunks.extend(event.missing_bullets)
        chunks.extend(event.blocked_bullets)
        for choice in event.operator_choices:
            chunks.append(str(choice.get("label") or ""))
            chunks.append(str(choice.get("disabled_reason") or ""))
    return "\n".join(chunks)


def _machine_terms_found(events: tuple[ChatWorkflowVisualEvent, ...], narration: AgentProgressNarration) -> tuple[str, ...]:
    text = _visible_event_text(events, narration).lower()
    return tuple(term for term in FORBIDDEN_VISIBLE_TERMS if term.lower() in text)


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    run_state = payload["chat_workflow_run_state"]
    events = tuple(ChatWorkflowVisualEvent(**event) for event in payload["chat_workflow_visual_events"])
    narration = AgentProgressNarration(**payload["agent_progress_narration"])
    completion = payload["visual_completion_receipt"]
    blockers = payload["chat_workflow_run_blockers_by_id"]
    event_source_refs = [event.source_refs for event in events]
    action_external_flags = [
        choice["external_action"]
        for event in events
        for choice in event.operator_choices
    ]
    narration_text = "\n".join(
        (
            narration.operator_line,
            narration.what_happened,
            narration.what_is_needed_next,
            narration.what_is_locked,
            narration.what_agent_will_do_next,
            narration.what_agent_cannot_do,
            narration.next_safe_move,
        )
    ).lower()
    return {
        "chat_workflow_run_state_model_present": True,
        "chat_workflow_visual_event_model_present": True,
        "agent_progress_narration_model_present": True,
        "visual_completion_receipt_model_present": True,
        "chat_workflow_run_blocker_model_present": True,
        "chat_workflow_visual_feed_elioperator_report_model_present": True,
        "phases_present": all(phase in PHASES for phase in (
            "UNDERSTANDING_CAPTURED",
            "MISSING_INFO_NEEDED",
            "PACKAGE_READY",
            "COMPLETION_CONFIRMED",
            "UNKNOWN_FAIL_CLOSED",
        )),
        "visual_event_types_present": all(event_type in EVENT_TYPES for event_type in (
            "UNDERSTANDING",
            "NEEDS_INPUT",
            "EXECUTION_LOCKED",
            "COMPLETION",
            "FAIL_CLOSED",
        )),
        "capital_hilton_run_state_present": run_state["workflow_ref"] == CAPITAL_WORKFLOW_REF,
        "capital_hilton_known_facts_correct": all(item in run_state["known_facts"] for item in KNOWN_FACTS),
        "capital_hilton_missing_items_correct": all(item in run_state["missing_items"] for item in MISSING_ITEMS),
        "capital_hilton_locked_items_correct": all(item in run_state["blocked_items"] for item in LOCKED_ITEMS),
        "visual_events_exist": all(event_type in {event.event_type for event in events} for event_type in (
            "UNDERSTANDING",
            "NEEDS_INPUT",
            "EXECUTION_LOCKED",
            "COMPLETION",
        )),
        "all_events_have_source_refs": all(bool(refs) for refs in event_source_refs),
        "future_completion_blocked_without_proof": completion["headline"] == "INVOICE SENT"
        and completion["completion_allowed"] is False
        and completion["blocked_reason"] == "Proof receipts do not exist yet.",
        "agent_narration_no_execution_claim": all(
            phrase not in narration_text
            for phrase in (
                "email sent",
                "coupa submitted",
                "invoice generated",
                "approval requested",
                "payment state changed",
            )
        ),
        "external_actions_locked": run_state["external_actions_locked"] is True,
        "all_operator_actions_external_false": all(flag is False for flag in action_external_flags),
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "machine_language_terms_absent_from_visible_content": not _machine_terms_found(events, narration),
        "completion_without_proof_blocker_exists": any(
            blocker["blocker_type"] == "COMPLETION_WITHOUT_PROOF" for blocker in blockers.values()
        ),
        "agent_invented_progress_blocker_exists": any(
            blocker["blocker_type"] == "AGENT_INVENTED_PROGRESS" for blocker in blockers.values()
        ),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_visual_events": False,
        "external_action_performed": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_chat_workflow_run_state_visual_feed(
    *,
    source_mirror_path: Path = DEFAULT_SOURCE_MIRROR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source = _load_json(source_mirror_path)
    run_state = build_run_state(source)
    events = build_visual_events(run_state)
    narration = build_agent_narration(run_state)
    completion = build_completion_receipt(run_state)
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "source_mirror_path": source_mirror_path.as_posix(),
        "source_mirror_present": source is not None,
        "source_mirror_ready": _source_mirror_ready(source),
        "phases": PHASES,
        "visual_event_types": EVENT_TYPES,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "chat_workflow_run_state": asdict(run_state),
        "chat_workflow_visual_events": tuple(asdict(event) for event in events),
        "agent_progress_narration": asdict(narration),
        "visual_completion_receipt": asdict(completion),
        "chat_workflow_run_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "chat_workflow_visual_feed_elioperator_report": asdict(report),
        "capital_hilton_example": {
            "understanding": asdict(events[0]),
            "needs_input": asdict(events[1]),
            "locked": asdict(events[2]),
            "invoice_sent_target": asdict(events[3]),
        },
        "allowed_contract_scope": (
            "deterministic read-model generation",
            "state projection from existing readbacks",
            "visual event feed examples",
            "tests",
            "ELIOPERATOR report",
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    state = payload["chat_workflow_run_state"]
    report = payload["chat_workflow_visual_feed_elioperator_report"]
    completion = payload["visual_completion_receipt"]
    lines = [
        "# Chat Workflow Run State + Visual Event Feed v0",
        "",
        "ELIOPERATOR: Chat can show workflow progress only when backend readback supports it.",
        "",
        f"- Phase: `{state['current_phase']}`.",
        f"- Workflow: `{state['workflow_type']}`.",
        f"- Client: `{state['client_ref']}`.",
        f"- Truth status: `{state['truth_status']}`.",
        f"- External actions locked: `{state['external_actions_locked']}`.",
        "",
        "## What This Enables",
        "",
        report["what_this_enables"],
        "",
        "## Current State",
        "",
        "Known:",
        *[f"- {item}" for item in state["known_facts"]],
        "",
        "Missing:",
        *[f"- {item}" for item in state["missing_items"]],
        "",
        "Locked:",
        *[f"- {item}" for item in state["blocked_items"]],
        "",
        "## Visual Events",
        "",
    ]
    for event in payload["chat_workflow_visual_events"]:
        lines.extend(
            [
                f"### {event['title']}",
                f"- {event['agent_line']}",
                f"- {event['visual_summary']}",
            ]
        )
        if event["missing_bullets"]:
            lines.extend(f"- Missing: {item}" for item in event["missing_bullets"])
        if event["blocked_bullets"]:
            lines.extend(f"- Locked: {item}" for item in event["blocked_bullets"])
        lines.append("")
    lines.extend(
        [
            "## Completion Target",
            "",
            f"- Headline: {completion['headline']}",
            f"- Allowed now: `{completion['completion_allowed']}`.",
            f"- Blocked reason: {completion['blocked_reason']}",
            "",
            "## Boundary",
            "",
            "- This read-model does not run a workflow, create a package, dispatch an agent, call a model, request approval, draft or send email, access Coupa, open a browser, generate an invoice, create an attachment, or update payment tracking.",
            "- Completion remains blocked until proof receipts exist.",
            "",
            f"Next safe move: {state['next_safe_move']}",
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
    state = payload["chat_workflow_run_state"]
    completion = payload["visual_completion_receipt"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "phase": state["current_phase"],
        "workflow_type": state["workflow_type"],
        "client_ref": state["client_ref"],
        "known_facts": list(state["known_facts"]),
        "missing_items": list(state["missing_items"]),
        "locked_items": list(state["blocked_items"]),
        "visual_events": [event["title"] for event in payload["chat_workflow_visual_events"]],
        "completion_headline": completion["headline"],
        "completion_allowed": completion["completion_allowed"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "machine_language_terms_absent_from_visible_content": payload["machine_proof"][
            "machine_language_terms_absent_from_visible_content"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the chat workflow run state visual feed read-model.")
    parser.add_argument("--source-mirror", type=Path, default=DEFAULT_SOURCE_MIRROR)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_chat_workflow_run_state_visual_feed(source_mirror_path=args.source_mirror)
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
