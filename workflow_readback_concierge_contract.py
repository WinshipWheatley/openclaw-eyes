"""Workflow Readback Concierge Contract v0.

This deterministic read-model defines how an active OpenClaw workflow surface
can correlate a request with a backend readback and explain the result in human
language. It is not a watcher, live polling loop, model call, agent dispatch,
workflow run, or external-action rail.
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

SCHEMA_VERSION = "workflow_readback_concierge_contract_v0"
READ_MODEL_ID = "workflow_readback_concierge_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WORKFLOW_READBACK_CONCIERGE_CONTRACT"

SUPPORTED_REQUEST_TYPES = (
    "mission_control_chat_request",
    "mission_control_capture_request",
    "post_office_handoff_request",
)

SUPPORTED_READBACK_TYPES = (
    "conversational_workflow_router_readback",
    "capture_request_readback",
    "delivery_facts_readback",
    "operator_closeout_readback",
)

CORRELATION_STATUSES = (
    "MATCHED_READY",
    "WAITING_FOR_BACKEND",
    "NO_REQUEST_FOUND",
    "NO_READBACK_FOUND",
    "STALE_READBACK",
    "HASH_OR_IDEMPOTENCY_MISMATCH",
    "MULTIPLE_CANDIDATES_NEED_REVIEW",
    "BLOCKED_UNSUPPORTED_TYPE",
    "UNKNOWN_FAIL_CLOSED",
)

FRESHNESS_STATUSES = (
    "CURRENT",
    "STALE",
    "UNKNOWN_TIMESTAMP",
    "SOURCE_MISMATCH",
    "FUTURE_TIMESTAMP_INVALID",
    "UNKNOWN_FAIL_CLOSED",
)

AGENT_ROLES = (
    "chat_router_agent",
    "workflow_readback_agent",
    "drafting_agent",
    "approval_agent",
    "protected_evidence_agent",
    "final_readback_agent",
)

CARD_TYPES = (
    "WAITING",
    "READY_FOR_REVIEW",
    "MISSING",
    "STALE",
    "BLOCKED",
    "DUPLICATE_NOOP",
    "COMPLETION",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "READBACK_MISSING",
    "READBACK_STALE",
    "REQUEST_MISSING",
    "SOURCE_MISMATCH",
    "MULTIPLE_READBACKS",
    "AGENT_INVENTED_TRUTH",
    "EXTERNAL_ACTION_ATTEMPTED",
    "RAW_PII_IN_NORMAL_READMODEL",
    "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_CONTRACT_FIELDS = (
    "contract_id",
    "doctrine",
    "supported_request_types",
    "supported_readback_types",
    "correlation_policy",
    "freshness_policy",
    "missing_readback_policy",
    "stale_readback_policy",
    "blocked_readback_policy",
    "ready_readback_policy",
    "agent_responsibility_policy",
    "operator_display_policy",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_CORRELATION_FIELDS = (
    "correlation_id",
    "source_request_ref",
    "source_request_type",
    "workflow_ref",
    "lane_ref",
    "request_id",
    "idempotency_key",
    "payload_hash",
    "expected_readback_type",
    "expected_readback_location",
    "matched_readback_ref",
    "correlation_status",
    "confidence",
    "next_safe_move",
)

REQUIRED_FRESHNESS_FIELDS = (
    "freshness_id",
    "readback_ref",
    "generated_at",
    "source_request_created_at",
    "source_request_id",
    "source_idempotency_key",
    "freshness_status",
    "stale_reason",
    "operator_message",
    "next_safe_move",
)

REQUIRED_RESPONSIBILITY_FIELDS = (
    "responsibility_id",
    "active_agent_role",
    "request_ref",
    "readback_ref",
    "responsibility_status",
    "what_agent_should_do",
    "what_agent_must_not_do",
    "operator_message",
    "next_safe_move",
)

REQUIRED_CARD_FIELDS = (
    "card_id",
    "card_type",
    "title",
    "summary",
    "bullets",
    "status_tone",
    "operator_choices",
    "detail_disclosure_available",
    "source_readback_ref",
    "truth_status",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "fail_closed",
    "next_safe_move",
)

REQUIRED_REPORT_FIELDS = (
    "report_id",
    "plain_summary",
    "what_this_enables",
    "what_this_does_not_do_yet",
    "how_agent_handles_readback",
    "how_operator_sees_status",
    "how_truth_is_confirmed",
    "how_missing_or_stale_readbacks_are_handled",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_readback_polling_allowed": False,
    "live_watcher_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_browser_access_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_approval_allowed": False,
    "live_network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
}

CURRENT_CAPITAL_HILTON_REQUEST = "capital_hilton_invoice_workflow_1779667089053_da4719d0757a"
CURRENT_CAPITAL_HILTON_IDEMPOTENCY = "mission_control_chat:capital_hilton_invoice_workflow:da4719d0757a1178c0e4"
CURRENT_CAPITAL_HILTON_HASH = "da4719d0757a1178c0e44f87559558ce27c5f745248bc8c0296cf47873ca297b"


@dataclass(frozen=True)
class WorkflowReadbackConciergeContract:
    contract_id: str
    doctrine: dict[str, Any]
    supported_request_types: tuple[str, ...]
    supported_readback_types: tuple[str, ...]
    correlation_policy: dict[str, Any]
    freshness_policy: dict[str, Any]
    missing_readback_policy: dict[str, Any]
    stale_readback_policy: dict[str, Any]
    blocked_readback_policy: dict[str, Any]
    ready_readback_policy: dict[str, Any]
    agent_responsibility_policy: dict[str, Any]
    operator_display_policy: dict[str, Any]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ReadbackCorrelation:
    correlation_id: str
    source_request_ref: str | None
    source_request_type: str
    workflow_ref: str | None
    lane_ref: str | None
    request_id: str | None
    idempotency_key: str | None
    payload_hash: str | None
    expected_readback_type: str
    expected_readback_location: str
    matched_readback_ref: str | None
    correlation_status: str
    confidence: str
    next_safe_move: str


@dataclass(frozen=True)
class ReadbackFreshnessCheck:
    freshness_id: str
    readback_ref: str | None
    generated_at: str | None
    source_request_created_at: str | None
    source_request_id: str | None
    source_idempotency_key: str | None
    freshness_status: str
    stale_reason: str | None
    operator_message: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentReadbackResponsibility:
    responsibility_id: str
    active_agent_role: str
    request_ref: str | None
    readback_ref: str | None
    responsibility_status: str
    what_agent_should_do: tuple[str, ...]
    what_agent_must_not_do: tuple[str, ...]
    operator_message: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorReadbackCard:
    card_id: str
    card_type: str
    title: str
    summary: str
    bullets: tuple[str, ...]
    status_tone: str
    operator_choices: tuple[str, ...]
    detail_disclosure_available: bool
    source_readback_ref: str | None
    truth_status: str
    next_safe_move: str


@dataclass(frozen=True)
class ReadbackNavigatorBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowReadbackConciergeElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_agent_handles_readback: str
    how_operator_sees_status: str
    how_truth_is_confirmed: str
    how_missing_or_stale_readbacks_are_handled: str
    next_safe_move: str


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "workflow_readback_concierge_contract": {
            "required_fields": list(REQUIRED_CONTRACT_FIELDS),
        },
        "readback_correlation": {
            "required_fields": list(REQUIRED_CORRELATION_FIELDS),
            "correlation_statuses": list(CORRELATION_STATUSES),
        },
        "readback_freshness_check": {
            "required_fields": list(REQUIRED_FRESHNESS_FIELDS),
            "freshness_statuses": list(FRESHNESS_STATUSES),
        },
        "agent_readback_responsibility": {
            "required_fields": list(REQUIRED_RESPONSIBILITY_FIELDS),
            "agent_roles": list(AGENT_ROLES),
        },
        "operator_readback_card": {
            "required_fields": list(REQUIRED_CARD_FIELDS),
            "card_types": list(CARD_TYPES),
        },
        "readback_navigator_blocker": {
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
        "workflow_readback_concierge_elioperator_report": {
            "required_fields": list(REQUIRED_REPORT_FIELDS),
        },
    }


def build_contract() -> WorkflowReadbackConciergeContract:
    return WorkflowReadbackConciergeContract(
        contract_id="workflow_readback_concierge_contract_v0",
        doctrine={
            "agent_owns_readback_navigation": True,
            "operator_does_not_search_files": True,
            "no_truth_without_readback": True,
            "missing_stale_or_blocked_readbacks_are_explained_plainly": True,
            "never_fake_success": True,
            "no_live_polling_or_watcher": True,
        },
        supported_request_types=SUPPORTED_REQUEST_TYPES,
        supported_readback_types=SUPPORTED_READBACK_TYPES,
        correlation_policy={
            "match_on": ("request_id", "idempotency_key", "payload_hash", "workflow_ref", "lane_ref"),
            "prefer_latest_matching_request": False,
            "multiple_matches_fail_closed": True,
            "hash_or_idempotency_mismatch_status": "HASH_OR_IDEMPOTENCY_MISMATCH",
        },
        freshness_policy={
            "readback_must_reference_source_request": True,
            "future_timestamps_invalid": True,
            "unknown_timestamp_requires_operator_message": True,
            "current_status": "CURRENT",
        },
        missing_readback_policy={
            "status": "WAITING_FOR_BACKEND",
            "operator_message": "Waiting for PC backend. I sent your request. No understanding has returned yet.",
            "truth_claim_allowed": False,
        },
        stale_readback_policy={
            "status": "STALE_READBACK",
            "operator_message": "This readback looks stale. I will not use it as current.",
            "truth_claim_allowed": False,
        },
        blocked_readback_policy={
            "status": "BLOCKED",
            "operator_message": "The readback is blocked or locked. Nothing external happened.",
            "external_action_allowed": False,
        },
        ready_readback_policy={
            "status": "MATCHED_READY",
            "operator_message": "I found the readback. Here is what OpenClaw understood.",
            "requires_operator_review": True,
        },
        agent_responsibility_policy={
            "agent_may_locate_read_readback_and_summarize": True,
            "agent_may_not_invent_state": True,
            "agent_may_not_trigger_external_actions": True,
            "agent_may_not_silently_advance_workflow": True,
        },
        operator_display_policy={
            "plain_language_cards": True,
            "machine_contract_hidden_by_default": True,
            "show_next_safe_move": True,
            "detail_disclosure_allowed": True,
        },
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Use this contract to build deterministic request/readback cards before adding live polling or runtime behavior.",
    )


def _correlation(
    *,
    correlation_id: str,
    source_request_ref: str | None,
    request_id: str | None,
    idempotency_key: str | None,
    payload_hash: str | None,
    matched_readback_ref: str | None,
    status: str,
    confidence: str,
    next_safe_move: str,
) -> ReadbackCorrelation:
    return ReadbackCorrelation(
        correlation_id=correlation_id,
        source_request_ref=source_request_ref,
        source_request_type="mission_control_chat_request",
        workflow_ref="capital_hilton_invoice_workflow" if source_request_ref else None,
        lane_ref="capital_hilton" if source_request_ref else None,
        request_id=request_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        expected_readback_type="conversational_workflow_router_readback",
        expected_readback_location="generated/read_models/conversational_workflow_router_readback.json",
        matched_readback_ref=matched_readback_ref,
        correlation_status=status,
        confidence=confidence,
        next_safe_move=next_safe_move,
    )


def _freshness(
    *,
    freshness_id: str,
    readback_ref: str | None,
    status: str,
    message: str,
    stale_reason: str | None = None,
    source_request_id: str | None = CURRENT_CAPITAL_HILTON_REQUEST,
    idempotency_key: str | None = CURRENT_CAPITAL_HILTON_IDEMPOTENCY,
) -> ReadbackFreshnessCheck:
    return ReadbackFreshnessCheck(
        freshness_id=freshness_id,
        readback_ref=readback_ref,
        generated_at="readback-generated-at" if readback_ref else None,
        source_request_created_at="request-created-at" if source_request_id else None,
        source_request_id=source_request_id,
        source_idempotency_key=idempotency_key,
        freshness_status=status,
        stale_reason=stale_reason,
        operator_message=message,
        next_safe_move="Use only current matched readbacks for operator-facing truth.",
    )


def _responsibility(
    *,
    responsibility_id: str,
    role: str,
    request_ref: str | None,
    readback_ref: str | None,
    status: str,
    operator_message: str,
) -> AgentReadbackResponsibility:
    return AgentReadbackResponsibility(
        responsibility_id=responsibility_id,
        active_agent_role=role,
        request_ref=request_ref,
        readback_ref=readback_ref,
        responsibility_status=status,
        what_agent_should_do=(
            "correlate request to readback",
            "check freshness and source match",
            "summarize the result in human language",
            "show the next safe move",
        ),
        what_agent_must_not_do=(
            "invent success without readback",
            "start a workflow run",
            "dispatch an agent",
            "send email or access Coupa",
            "hide stale or missing readback state",
        ),
        operator_message=operator_message,
        next_safe_move="Explain the current readback state without advancing the workflow.",
    )


def _card(
    *,
    card_id: str,
    card_type: str,
    title: str,
    summary: str,
    bullets: tuple[str, ...],
    tone: str,
    source_readback_ref: str | None,
    truth_status: str,
    next_safe_move: str,
) -> OperatorReadbackCard:
    return OperatorReadbackCard(
        card_id=card_id,
        card_type=card_type,
        title=title,
        summary=summary,
        bullets=bullets,
        status_tone=tone,
        operator_choices=("Review result", "Ask what is missing", "Cancel"),
        detail_disclosure_available=True,
        source_readback_ref=source_readback_ref,
        truth_status=truth_status,
        next_safe_move=next_safe_move,
    )


def build_examples() -> dict[str, Any]:
    ready_ref = "conversational_workflow_router_readback"
    waiting = {
        "correlation": asdict(_correlation(
            correlation_id="correlation_capital_hilton_waiting",
            source_request_ref=CURRENT_CAPITAL_HILTON_REQUEST,
            request_id=CURRENT_CAPITAL_HILTON_REQUEST,
            idempotency_key=CURRENT_CAPITAL_HILTON_IDEMPOTENCY,
            payload_hash=CURRENT_CAPITAL_HILTON_HASH,
            matched_readback_ref=None,
            status="WAITING_FOR_BACKEND",
            confidence="source request present, readback not yet matched",
            next_safe_move="Tell the operator the request is waiting for PC backend.",
        )),
        "freshness": asdict(_freshness(
            freshness_id="freshness_capital_hilton_waiting",
            readback_ref=None,
            status="UNKNOWN_TIMESTAMP",
            message="Waiting for PC backend. I sent your request. No understanding has returned yet.",
            stale_reason="no matched readback exists yet",
        )),
        "responsibility": asdict(_responsibility(
            responsibility_id="responsibility_capital_hilton_waiting",
            role="workflow_readback_agent",
            request_ref=CURRENT_CAPITAL_HILTON_REQUEST,
            readback_ref=None,
            status="WAITING_FOR_BACKEND",
            operator_message="I sent that to PC and I am waiting for the backend readback.",
        )),
        "operator_card": asdict(_card(
            card_id="card_capital_hilton_waiting",
            card_type="WAITING",
            title="Waiting for PC backend",
            summary="I sent your request. No understanding has returned yet.",
            bullets=(
                "The request is tracked.",
                "No backend readback has been matched yet.",
                "I will not claim what OpenClaw understood until the readback exists.",
            ),
            tone="waiting",
            source_readback_ref=None,
            truth_status="NO_TRUTH_WITHOUT_READBACK",
            next_safe_move="Wait for the backend readback or retry the intake if needed.",
        )),
    }
    ready = {
        "correlation": asdict(_correlation(
            correlation_id="correlation_capital_hilton_ready",
            source_request_ref=CURRENT_CAPITAL_HILTON_REQUEST,
            request_id=CURRENT_CAPITAL_HILTON_REQUEST,
            idempotency_key=CURRENT_CAPITAL_HILTON_IDEMPOTENCY,
            payload_hash=CURRENT_CAPITAL_HILTON_HASH,
            matched_readback_ref=ready_ref,
            status="MATCHED_READY",
            confidence="request id, idempotency, payload hash, workflow, and lane match",
            next_safe_move="Show the human cards and ask whether the understanding looks right.",
        )),
        "freshness": asdict(_freshness(
            freshness_id="freshness_capital_hilton_ready",
            readback_ref=ready_ref,
            status="CURRENT",
            message="I found the readback. Here is what OpenClaw understood.",
        )),
        "responsibility": asdict(_responsibility(
            responsibility_id="responsibility_capital_hilton_ready",
            role="chat_router_agent",
            request_ref=CURRENT_CAPITAL_HILTON_REQUEST,
            readback_ref=ready_ref,
            status="READY_FOR_REVIEW",
            operator_message="I found the backend readback and can show the cards for review.",
        )),
        "operator_card": asdict(_card(
            card_id="card_capital_hilton_ready",
            card_type="READY_FOR_REVIEW",
            title="OpenClaw understood",
            summary="I found the readback. Here is what OpenClaw understood.",
            bullets=(
                "Capital Hilton invoice workflow was routed for review.",
                "Excel/PDF companion invoice, Coupa/PO payment rail, and contact follow-up are understood as draft workflow context.",
                "This is ready for review, not execution.",
                "Send, Coupa, approval, browser, and invoice-generation actions remain locked.",
            ),
            tone="ready",
            source_readback_ref=ready_ref,
            truth_status="READBACK_MATCHED_DRAFT_UNDERSTANDING",
            next_safe_move="Ask the operator whether the understanding looks right.",
        )),
    }
    stale = {
        "correlation": asdict(_correlation(
            correlation_id="correlation_capital_hilton_stale",
            source_request_ref="capital_hilton_invoice_workflow_newer_request",
            request_id="capital_hilton_invoice_workflow_newer_request",
            idempotency_key="newer-request-idempotency",
            payload_hash="newer-request-payload-hash",
            matched_readback_ref=ready_ref,
            status="STALE_READBACK",
            confidence="readback source does not match latest request",
            next_safe_move="Do not use the stale readback as current.",
        )),
        "freshness": asdict(_freshness(
            freshness_id="freshness_capital_hilton_stale",
            readback_ref=ready_ref,
            status="STALE",
            message="This readback looks stale. I will not use it as current.",
            stale_reason="latest request id or idempotency does not match the readback source",
            source_request_id="capital_hilton_invoice_workflow_newer_request",
            idempotency_key="newer-request-idempotency",
        )),
        "operator_card": asdict(_card(
            card_id="card_capital_hilton_stale",
            card_type="STALE",
            title="Readback looks stale",
            summary="This readback looks stale. I will not use it as current.",
            bullets=(
                "The readback exists, but it is not proof of the current request.",
                "I will not use it as current.",
                "The safe move is to wait for or regenerate the matching readback.",
            ),
            tone="warning",
            source_readback_ref=ready_ref,
            truth_status="STALE_NOT_CURRENT_TRUTH",
            next_safe_move="Wait for the matching backend readback.",
        )),
    }
    duplicate = {
        "correlation": asdict(_correlation(
            correlation_id="correlation_duplicate_noop",
            source_request_ref=CURRENT_CAPITAL_HILTON_REQUEST,
            request_id=CURRENT_CAPITAL_HILTON_REQUEST,
            idempotency_key=CURRENT_CAPITAL_HILTON_IDEMPOTENCY,
            payload_hash=CURRENT_CAPITAL_HILTON_HASH,
            matched_readback_ref="duplicate_noop_readback",
            status="MATCHED_READY",
            confidence="duplicate readback matched source request",
            next_safe_move="Explain that backend already had this exact information.",
        )),
        "operator_card": asdict(_card(
            card_id="card_duplicate_noop",
            card_type="DUPLICATE_NOOP",
            title="Already captured",
            summary="Backend already had this information; no duplicate was written.",
            bullets=(
                "The request matched an existing receipt or readback.",
                "No duplicate state was written.",
                "This is a safe no-op, not a new external action.",
            ),
            tone="neutral",
            source_readback_ref="duplicate_noop_readback",
            truth_status="READBACK_MATCHED_DUPLICATE_NOOP",
            next_safe_move="Show the existing readback or ask for the next missing fact.",
        )),
    }
    blocked_external = {
        "operator_card": asdict(_card(
            card_id="card_external_action_blocked",
            card_type="BLOCKED",
            title="Ready for review, not execution",
            summary="This is ready for review, not execution. Send/Coupa/approval remain locked.",
            bullets=(
                "No email was sent.",
                "No Coupa or browser access occurred.",
                "No approval was requested.",
                "No invoice was generated or submitted.",
            ),
            tone="blocked",
            source_readback_ref=ready_ref,
            truth_status="LOCKED_EXTERNAL_ACTION",
            next_safe_move="Review the understanding before any future gated package is prepared.",
        )),
    }
    invented_truth = {
        "blocker_ref": "readback_navigator_blocker_agent_invented_truth",
        "operator_card": asdict(_card(
            card_id="card_agent_invented_truth_blocked",
            card_type="UNKNOWN_FAIL_CLOSED",
            title="I cannot claim that yet",
            summary="There is no matching readback or proof for that success claim.",
            bullets=(
                "The agent must not invent state.",
                "The result needs a matched readback or proof receipt.",
                "Until then, the workflow remains unconfirmed.",
            ),
            tone="blocked",
            source_readback_ref=None,
            truth_status="FAIL_CLOSED_NO_READBACK_PROOF",
            next_safe_move="Find the matching readback or explain that it is missing.",
        )),
    }
    return {
        "capital_hilton_waiting": waiting,
        "capital_hilton_ready": ready,
        "stale_readback": stale,
        "duplicate_noop": duplicate,
        "blocked_external_action": blocked_external,
        "agent_invented_truth_blocker": invented_truth,
    }


def build_blockers() -> tuple[ReadbackNavigatorBlocker, ...]:
    conditions = {
        "READBACK_MISSING": "No matching backend readback is available yet.",
        "READBACK_STALE": "The matched readback is stale or source-mismatched.",
        "REQUEST_MISSING": "No source request exists to correlate.",
        "SOURCE_MISMATCH": "The readback does not match the request id, idempotency key, or payload hash.",
        "MULTIPLE_READBACKS": "Multiple candidate readbacks exist and require review.",
        "AGENT_INVENTED_TRUTH": "An agent tried to show success without readback or proof.",
        "EXTERNAL_ACTION_ATTEMPTED": "Concierge cannot send, submit, approve, browse, or dispatch.",
        "RAW_PII_IN_NORMAL_READMODEL": "Raw sensitive values must not enter normal read-models.",
        "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR": "Operator cards must stay plain-language.",
        "UNKNOWN_FAIL_CLOSED": "Unknown readback navigation state fails closed.",
    }
    return tuple(
        ReadbackNavigatorBlocker(
            blocker_id=f"readback_navigator_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_TRUTH_CLAIM" if "TRUTH" in blocker_type or "READBACK" in blocker_type else "BLOCKS_SAFE_NAVIGATION",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move="Explain the blocked state and wait for a matching proof-backed readback.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_report() -> WorkflowReadbackConciergeElioperatorReport:
    return WorkflowReadbackConciergeElioperatorReport(
        report_id="workflow_readback_concierge_elioperator_report_v0",
        plain_summary="The concierge keeps track of the request/readback loop so the operator does not have to hunt for backend files.",
        what_this_enables="An active surface can say whether a request is waiting, ready, stale, blocked, duplicate, or missing.",
        what_this_does_not_do_yet="It does not poll, watch folders, dispatch agents, run workflows, call models, or perform external actions.",
        how_agent_handles_readback="The agent correlates request id, idempotency key, payload hash, workflow, and lane before summarizing.",
        how_operator_sees_status="The operator sees plain cards such as Waiting, Ready for review, Stale, Blocked, or Duplicate no-op.",
        how_truth_is_confirmed="Truth comes from a matched, fresh readback or proof receipt. No readback means no success claim.",
        how_missing_or_stale_readbacks_are_handled="Missing and stale readbacks are explained plainly and fail closed.",
        next_safe_move="Use the ready card to ask the operator whether the Capital Hilton understanding looks right.",
    )


def _relationship_inventory() -> dict[str, str]:
    return {
        "conversational_workflow_router_contract": "defines chat-to-package router shape",
        "conversational_workflow_router_intake": "generates current chat request readback cards",
        "cross_surface_artifact_handoff_registry_contract": "defines typed handoff lifecycle language",
        "cross_surface_handoff_registry_metadata_alignment": "adds post-office-compatible metadata shape",
        "agent_conversation_handoff_step_packet_contract": "future role handoff compatibility",
        "bridge_routing_operator_attention_contract": "operator attention routing compatibility",
        "openclaw_sensitive_policy": "privacy and protected-value posture dependency",
    }


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = payload["readback_navigator_blockers_by_id"]
    examples = payload["examples"]
    markdown_preview = format_operator_markdown_without_hash(payload)
    return {
        "workflow_readback_concierge_contract_model_present": True,
        "readback_correlation_model_present": True,
        "readback_freshness_check_model_present": True,
        "agent_readback_responsibility_model_present": True,
        "operator_readback_card_model_present": True,
        "readback_navigator_blocker_model_present": True,
        "workflow_readback_concierge_elioperator_report_model_present": True,
        "correlation_statuses_present": all(status in CORRELATION_STATUSES for status in (
            "MATCHED_READY",
            "WAITING_FOR_BACKEND",
            "NO_READBACK_FOUND",
            "STALE_READBACK",
            "UNKNOWN_FAIL_CLOSED",
        )),
        "freshness_statuses_present": all(status in FRESHNESS_STATUSES for status in (
            "CURRENT",
            "STALE",
            "UNKNOWN_TIMESTAMP",
            "SOURCE_MISMATCH",
            "UNKNOWN_FAIL_CLOSED",
        )),
        "agent_roles_present": all(role in AGENT_ROLES for role in (
            "chat_router_agent",
            "workflow_readback_agent",
            "final_readback_agent",
        )),
        "operator_cards_present": all(card in CARD_TYPES for card in (
            "WAITING",
            "READY_FOR_REVIEW",
            "STALE",
            "BLOCKED",
            "DUPLICATE_NOOP",
        )),
        "capital_hilton_waiting_example_present": "capital_hilton_waiting" in examples,
        "capital_hilton_ready_example_present": "capital_hilton_ready" in examples,
        "stale_readback_example_present": "stale_readback" in examples,
        "duplicate_noop_example_present": "duplicate_noop" in examples,
        "external_action_blocked_example_present": "blocked_external_action" in examples,
        "agent_invented_truth_blocker_present": "AGENT_INVENTED_TRUTH" in {
            blocker["blocker_type"] for blocker in blockers.values()
        },
        "all_live_authority_flags_false": all(value is False for value in payload["authority_boundary"].values()),
        "no_live_polling": payload["authority_boundary"]["live_readback_polling_allowed"] is False,
        "no_watcher": payload["authority_boundary"]["live_watcher_allowed"] is False,
        "no_agent_dispatch": payload["authority_boundary"]["live_agent_dispatch_allowed"] is False,
        "no_model_call": payload["authority_boundary"]["live_model_call_allowed"] is False,
        "no_workflow_run": payload["authority_boundary"]["live_workflow_run_allowed"] is False,
        "no_external_action": payload["authority_boundary"]["live_external_action_allowed"] is False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "machine_contract_visible_to_operator": any(
            token in markdown_preview.lower()
            for token in ("schema_version", "payload_hash", "idempotency_key", "handler", "manifest")
        ),
        "external_action_performed": False,
        "network_used": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_workflow_readback_concierge_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    contract = build_contract()
    examples = build_examples()
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "supported_request_types": SUPPORTED_REQUEST_TYPES,
        "supported_readback_types": SUPPORTED_READBACK_TYPES,
        "correlation_statuses": CORRELATION_STATUSES,
        "freshness_statuses": FRESHNESS_STATUSES,
        "agent_roles": AGENT_ROLES,
        "operator_card_types": CARD_TYPES,
        "model_schemas": _model_schemas(),
        "workflow_readback_concierge_contract": asdict(contract),
        "readback_correlation": examples["capital_hilton_ready"]["correlation"],
        "readback_freshness_check": examples["capital_hilton_ready"]["freshness"],
        "agent_readback_responsibility": examples["capital_hilton_ready"]["responsibility"],
        "operator_readback_card": examples["capital_hilton_ready"]["operator_card"],
        "readback_navigator_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "workflow_readback_concierge_elioperator_report": asdict(report),
        "examples": examples,
        "relationship_inventory": _relationship_inventory(),
        "allowed_contract_scope": (
            "deterministic read-model generation",
            "tests",
            "metadata-only examples",
            "future agent responsibility model",
            "ELIOPERATOR report",
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown_without_hash(payload: dict[str, Any]) -> str:
    report = payload["workflow_readback_concierge_elioperator_report"]
    ready_card = payload["examples"]["capital_hilton_ready"]["operator_card"]
    waiting_card = payload["examples"]["capital_hilton_waiting"]["operator_card"]
    stale_card = payload["examples"]["stale_readback"]["operator_card"]
    blocked_card = payload["examples"]["blocked_external_action"]["operator_card"]
    return "\n".join(
        [
            "# Workflow Readback Concierge Contract v0",
            "",
            "ELIOPERATOR: The active agent should own the request/readback loop. The operator should not have to hunt for backend files or know where readbacks live.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## How It Works",
            "",
            "- The agent tracks the request it caused.",
            "- It looks for a matching backend readback by request identity and workflow context.",
            "- It checks whether the readback is current before using it.",
            "- It explains waiting, ready, stale, duplicate, blocked, or missing states plainly.",
            "- It never claims success without a matched readback or proof receipt.",
            "",
            "## Example Cards",
            "",
            f"### {waiting_card['title']}",
            f"- {waiting_card['summary']}",
            *[f"- {bullet}" for bullet in waiting_card["bullets"]],
            "",
            f"### {ready_card['title']}",
            f"- {ready_card['summary']}",
            *[f"- {bullet}" for bullet in ready_card["bullets"]],
            "",
            f"### {stale_card['title']}",
            f"- {stale_card['summary']}",
            *[f"- {bullet}" for bullet in stale_card["bullets"]],
            "",
            f"### {blocked_card['title']}",
            f"- {blocked_card['summary']}",
            *[f"- {bullet}" for bullet in blocked_card["bullets"]],
            "",
            "## Boundary",
            "",
            "- No live polling, watcher, model call, agent dispatch, workflow run, or external action exists here.",
            "- No email, Coupa, browser, invoice generation, approval, credential handling, raw-body ingestion, Mac sync/import, Swift change, network, or push occurred.",
            "",
            f"Next safe move: {report['next_safe_move']}",
            "",
        ]
    )


def format_operator_markdown(payload: dict[str, Any]) -> str:
    return format_operator_markdown_without_hash(payload)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "ready_correlation_status": payload["examples"]["capital_hilton_ready"]["correlation"]["correlation_status"],
        "waiting_correlation_status": payload["examples"]["capital_hilton_waiting"]["correlation"]["correlation_status"],
        "stale_freshness_status": payload["examples"]["stale_readback"]["freshness"]["freshness_status"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the workflow readback concierge contract read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_workflow_readback_concierge_contract(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
