"""Conversational Workflow Router intake/readback rail v0.

This module accepts a visual-agnostic Mission Control chat request JSON file,
routes it through the deterministic conversational workflow router posture, and
writes a human-card readback for Mac to render.

It is local and non-executing. It does not call a live model, dispatch agents,
write procedure memory, start a workflow run, create Gmail drafts, access Coupa
or browser sessions, generate invoices, attach files, request approval, send,
submit, mutate payment tracking, handle credentials, ingest raw private bodies,
use network, or touch Mission Control Swift code.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import conversational_workflow_router_contract as router_contract


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
APPROVED_INBOX = Path("/mnt/e/openclaw/mission_control_capture_requests/inbox")
REQUEST_FILENAME_PATTERN = "mission_control_chat_request_*.json"

SCHEMA_VERSION = "conversational_workflow_router_intake_v0"
READ_MODEL_ID = "conversational_workflow_router_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CHAT_ROUTER_INTAKE_READBACK_RAIL"

CAPITAL_HILTON_FIXTURE_TEXT = (
    "Yeah, your example text is basically it. I am pretty sure the system knows the 4 dates that the "
    "invoice is asking pay for at $400 each. Excel invoice needs to be generated and attached to the "
    "email to Annette. The invoice should also be saved in the system for records. The invoice in the "
    "Coupa Supplier Portal needs to be generated off of the PO that is also in Coupa Supplier Portal "
    "and submitted."
)

CAPITAL_HILTON_SANITIZED_SUMMARY = (
    "Prepare Capital Hilton invoice workflow: four known invoice dates at $400 each, generate a "
    "Winship-branded Excel/PDF companion invoice for Annette, use Coupa Supplier Portal from PO as "
    "official payment rail, save dated invoice record, and keep send/submit behind gates."
)

REQUIRED_REQUEST_FIELDS = (
    "request_id",
    "workflow_ref",
    "workflow_type",
    "world_ref",
    "lane_ref",
    "client_ref",
    "tenant_ref",
    "origin_surface",
    "source_channel",
    "operator_message",
    "sanitized_message_summary",
    "privacy_class",
    "idempotency_key",
    "payload_hash",
    "authority_boundary",
    "created_at",
)

REQUIRED_INTAKE_RESULT_FIELDS = (
    "intake_result_id",
    "source_request_ref",
    "parse_status",
    "parser_mode",
    "model_parser_available",
    "routed_intent_ref",
    "human_card_readback_ref",
    "backend_package_request_ref",
    "duplicate_status",
    "operator_review_required",
    "external_authority",
    "next_safe_move",
)

REQUIRED_CARD_FIELDS = (
    "card_id",
    "card_type",
    "title",
    "bullets",
    "operator_actions",
    "truth_status",
    "proof_status",
    "next_safe_move",
)

REQUIRED_READBACK_FIELDS = (
    "readback_id",
    "source_request_ref",
    "intake_result_ref",
    "cards",
    "backend_package_target",
    "operator_choices",
    "missing_backend_rails",
    "locked_actions",
    "safe_display_summary",
    "elioperator_summary",
    "next_safe_move",
)

REQUIRED_BACKEND_TARGET_FIELDS = (
    "package_target_id",
    "routed_intent_ref",
    "package_type",
    "workflow_type",
    "role_targets",
    "required_inputs",
    "required_artifacts",
    "required_proofs",
    "required_gates",
    "blocked_actions",
    "ready_actions",
    "output_readback_target",
    "can_create_now",
    "create_block_reason",
    "next_safe_move",
)

REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "source_request_ref",
    "idempotency_key",
    "payload_hash",
    "intake_status",
    "readback_ref",
    "duplicate_result",
    "external_authority",
    "raw_body_ingestion",
    "credential_handling",
    "created_at_policy",
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

PARSE_STATUSES = (
    "ROUTED_DRAFT_READY",
    "NEEDS_MORE_DETAIL",
    "DUPLICATE_NOOP",
    "BLOCKED_UNSUPPORTED_SHAPE",
    "REJECTED_INVALID_REQUEST",
    "UNKNOWN_FAIL_CLOSED",
)

TRUTH_STATUSES = (
    "DRAFT_UNDERSTANDING_NOT_TRUTH",
    "NEEDS_OPERATOR_REVIEW",
    "BACKEND_READBACK_REQUIRED",
    "PROOF_REQUIRED",
    "LOCKED_EXTERNAL_ACTION",
)

BLOCKER_TYPES = (
    "MESSAGE_TREATED_AS_TRUTH",
    "MODEL_PARSER_CLAIMED_BUT_NOT_AVAILABLE",
    "AGENT_DISPATCH_ATTEMPTED",
    "PROCEDURE_MEMORY_WRITE_ATTEMPTED",
    "WORKFLOW_RUN_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "RAW_PII_IN_NORMAL_READMODEL",
    "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR",
    "MISSING_IDEMPOTENCY_KEY",
    "MISSING_PAYLOAD_HASH",
    "UNSUPPORTED_REQUEST_SHAPE",
    "UNKNOWN_FAIL_CLOSED",
)

OPERATOR_CHOICES = (
    "Looks right",
    "Edit understanding",
    "Store as procedure later",
    "Prepare package later",
    "Cancel",
)

LOCKED_ACTIONS = (
    "email send",
    "Coupa access",
    "browser automation",
    "invoice submission",
    "approval request",
    "invoice generation",
    "attachment",
    "payment state change",
)

AUTHORITY_BOUNDARY = {
    "live_chat_parser_allowed": False,
    "live_model_call_allowed": False,
    "live_router_dispatch_allowed": False,
    "live_package_creation_allowed": False,
    "live_procedure_memory_write_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_cassandra_draft_allowed": False,
    "live_guardian_approval_allowed": False,
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
    "browser_automation_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "approval_submission_allowed": False,
    "network_operation_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}


@dataclass(frozen=True)
class ConversationalWorkflowRouterIntakeRequest:
    request_id: str
    workflow_ref: str
    workflow_type: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    origin_surface: str
    source_channel: str
    operator_message: str
    sanitized_message_summary: str
    privacy_class: str
    idempotency_key: str
    payload_hash: str
    authority_boundary: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class ConversationalWorkflowRouterIntakeResult:
    intake_result_id: str
    source_request_ref: str
    parse_status: str
    parser_mode: str
    model_parser_available: bool
    routed_intent_ref: str | None
    human_card_readback_ref: str | None
    backend_package_request_ref: str | None
    duplicate_status: str
    operator_review_required: bool
    external_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class RouterHumanCard:
    card_id: str
    card_type: str
    title: str
    bullets: tuple[str, ...]
    operator_actions: tuple[str, ...]
    truth_status: str
    proof_status: str
    next_safe_move: str


@dataclass(frozen=True)
class RouterBackendPackageTarget:
    package_target_id: str
    routed_intent_ref: str
    package_type: str
    workflow_type: str
    role_targets: tuple[str, ...]
    required_inputs: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_proofs: tuple[str, ...]
    required_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    ready_actions: tuple[str, ...]
    output_readback_target: str
    can_create_now: bool
    create_block_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class RouterReadbackPackage:
    readback_id: str
    source_request_ref: str
    intake_result_ref: str
    cards: tuple[dict[str, Any], ...]
    backend_package_target: dict[str, Any]
    operator_choices: tuple[dict[str, Any], ...]
    missing_backend_rails: tuple[str, ...]
    locked_actions: tuple[str, ...]
    safe_display_summary: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class RouterIntakeReceipt:
    receipt_id: str
    source_request_ref: str
    idempotency_key: str | None
    payload_hash: str | None
    intake_status: str
    readback_ref: str | None
    duplicate_result: str
    external_authority: bool
    raw_body_ingestion: bool
    credential_handling: bool
    created_at_policy: str


@dataclass(frozen=True)
class RouterIntakeBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def compute_request_payload_hash(request: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(request)))
    clone.pop("payload_hash", None)
    return _sha256_payload(clone)


def payload_hash_acceptance_reason(
    request: Mapping[str, Any],
    *,
    request_path: Path | None = None,
) -> str | None:
    provided = str(request.get("payload_hash") or "")
    if not provided:
        return None
    expected = compute_request_payload_hash(request)
    if provided == expected:
        return "pc_canonical_sha256"
    expected_hex = expected.removeprefix("sha256:")
    if provided == expected_hex:
        return "pc_canonical_raw_hex"
    # Mission Control currently emits a raw hex hash and binds its short prefix
    # into both the request_id and filename. Accept that format without treating
    # it as a PC canonical content hash.
    is_raw_hex = len(provided) == 64 and all(ch in "0123456789abcdef" for ch in provided.lower())
    short = provided[:12]
    request_id = str(request.get("request_id") or "")
    filename = request_path.name if request_path else ""
    if is_raw_hex and short and short in request_id and (not request_path or short in filename):
        return "mac_filename_bound_raw_hex"
    return None


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256_payload(clone)


def _short_hash(*parts: Any) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:20]


def _model_schemas() -> dict[str, Any]:
    return {
        "conversational_workflow_router_intake_request": {
            "required_fields": list(REQUIRED_REQUEST_FIELDS),
        },
        "conversational_workflow_router_intake_result": {
            "required_fields": list(REQUIRED_INTAKE_RESULT_FIELDS),
            "parse_statuses": list(PARSE_STATUSES),
        },
        "router_human_card": {
            "required_fields": list(REQUIRED_CARD_FIELDS),
            "truth_statuses": list(TRUTH_STATUSES),
        },
        "router_readback_package": {"required_fields": list(REQUIRED_READBACK_FIELDS)},
        "router_backend_package_target": {"required_fields": list(REQUIRED_BACKEND_TARGET_FIELDS)},
        "router_intake_receipt": {"required_fields": list(REQUIRED_RECEIPT_FIELDS)},
        "router_intake_blocker": {
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
    }


def make_capital_hilton_fixture_request(*, created_at: str = "2026-05-25T00:00:00+00:00") -> dict[str, Any]:
    request: dict[str, Any] = {
        "request_id": "mission_control_chat_request_capital_hilton_invoice_delivery_fixture",
        "workflow_ref": "capital_hilton_invoice_payment_workflow",
        "workflow_type": "invoice_delivery_workflow",
        "world_ref": "finance",
        "lane_ref": "Capital Hilton",
        "client_ref": "capital_hilton",
        "tenant_ref": "openclaw_repo_a_local",
        "origin_surface": "Mission Control chat",
        "source_channel": "mission_control_chat",
        "operator_message": CAPITAL_HILTON_FIXTURE_TEXT,
        "sanitized_message_summary": CAPITAL_HILTON_SANITIZED_SUMMARY,
        "privacy_class": "sanitized_client_business_context",
        "idempotency_key": "mc_chat_capital_hilton_invoice_delivery_fixture",
        "payload_hash": "",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "created_at": created_at,
    }
    request["payload_hash"] = compute_request_payload_hash(request)
    return request


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def find_latest_request(inbox: Path = APPROVED_INBOX) -> Path | None:
    if not inbox.exists():
        return None
    matches = sorted(
        path for path in inbox.iterdir()
        if path.is_file() and fnmatch.fnmatch(path.name, REQUEST_FILENAME_PATTERN)
    )
    return matches[-1] if matches else None


def _blocker(blocker_type: str, condition: str, *, severity: str = "BLOCKS_SAFE_INTAKE") -> RouterIntakeBlocker:
    return RouterIntakeBlocker(
        blocker_id=f"router_intake_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move="Reject or park the request until the shape is safe.",
    )


def build_standard_blockers() -> tuple[RouterIntakeBlocker, ...]:
    conditions = {
        "MESSAGE_TREATED_AS_TRUTH": "Chat text is candidate meaning, not stored truth.",
        "MODEL_PARSER_CLAIMED_BUT_NOT_AVAILABLE": "No live model parser is available in this rail.",
        "AGENT_DISPATCH_ATTEMPTED": "Router intake cannot dispatch agents.",
        "PROCEDURE_MEMORY_WRITE_ATTEMPTED": "Router intake cannot write procedure memory.",
        "WORKFLOW_RUN_ATTEMPTED": "Router intake cannot start a workflow run.",
        "EXTERNAL_ACTION_ATTEMPTED": "Router intake cannot perform email, Coupa, browser, send, submit, or approval actions.",
        "RAW_PII_IN_NORMAL_READMODEL": "Raw sensitive values must not enter normal read-models.",
        "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR": "Mac cards must use human language, not schema or handler language.",
        "MISSING_IDEMPOTENCY_KEY": "Request must include idempotency_key.",
        "MISSING_PAYLOAD_HASH": "Request must include payload_hash.",
        "UNSUPPORTED_REQUEST_SHAPE": "Request shape or filename pattern is unsupported.",
        "UNKNOWN_FAIL_CLOSED": "Ambiguous router intake state fails closed.",
    }
    return tuple(_blocker(blocker_type, condition) for blocker_type, condition in conditions.items())


def validate_request_shape(request: Mapping[str, Any], *, request_path: Path | None = None) -> tuple[bool, tuple[RouterIntakeBlocker, ...]]:
    blockers: list[RouterIntakeBlocker] = []
    if request_path is not None and not fnmatch.fnmatch(request_path.name, REQUEST_FILENAME_PATTERN):
        blockers.append(
            _blocker("UNSUPPORTED_REQUEST_SHAPE", f"Filename must match {REQUEST_FILENAME_PATTERN}.")
        )
    missing = [field for field in REQUIRED_REQUEST_FIELDS if field not in request]
    if missing:
        blockers.append(_blocker("UNSUPPORTED_REQUEST_SHAPE", f"Missing required fields: {', '.join(missing)}."))
    if not request.get("idempotency_key"):
        blockers.append(_blocker("MISSING_IDEMPOTENCY_KEY", "Request is missing idempotency_key."))
    if not request.get("payload_hash"):
        blockers.append(_blocker("MISSING_PAYLOAD_HASH", "Request is missing payload_hash."))
    if request.get("payload_hash"):
        if payload_hash_acceptance_reason(request, request_path=request_path) is None:
            blockers.append(_blocker("UNSUPPORTED_REQUEST_SHAPE", "payload_hash does not match request body."))
    authority = request.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append(_blocker("UNSUPPORTED_REQUEST_SHAPE", "authority_boundary must be an object."))
    elif any(value is True for value in authority.values()):
        blockers.append(_blocker("EXTERNAL_ACTION_ATTEMPTED", "Request asks for authority this rail cannot grant."))
    return not blockers, tuple(blockers)


def normalize_request(request: Mapping[str, Any]) -> ConversationalWorkflowRouterIntakeRequest:
    sanitized = str(request.get("sanitized_message_summary") or "")
    return ConversationalWorkflowRouterIntakeRequest(
        request_id=str(request.get("request_id")),
        workflow_ref=str(request.get("workflow_ref")),
        workflow_type=str(request.get("workflow_type")),
        world_ref=str(request.get("world_ref")),
        lane_ref=str(request.get("lane_ref")),
        client_ref=str(request.get("client_ref")),
        tenant_ref=str(request.get("tenant_ref")),
        origin_surface=str(request.get("origin_surface")),
        source_channel=str(request.get("source_channel")),
        operator_message=sanitized or "REDACTED_IN_NORMAL_READ_MODEL",
        sanitized_message_summary=sanitized,
        privacy_class=str(request.get("privacy_class")),
        idempotency_key=str(request.get("idempotency_key")),
        payload_hash=str(request.get("payload_hash")),
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=str(request.get("created_at")),
    )


def _is_capital_hilton_invoice_request(request: ConversationalWorkflowRouterIntakeRequest) -> bool:
    text = (
        request.sanitized_message_summary
        + " "
        + request.workflow_type
        + " "
        + request.world_ref
        + " "
        + request.lane_ref
        + " "
        + request.client_ref
    ).lower()
    return (
        "invoice" in text
        and ("capital hilton" in text or "capital_hilton" in text)
        and ("coupa" in text or "po" in text)
    )


def _build_capital_hilton_cards(source_ref: str) -> tuple[RouterHumanCard, ...]:
    actions = OPERATOR_CHOICES
    return (
        RouterHumanCard(
            card_id="router_card_openclaw_understood_capital_hilton",
            card_type="OPENCLAW_UNDERSTOOD",
            title="OpenClaw understood",
            bullets=(
                "Goal: prepare the Capital Hilton invoice workflow.",
                "Invoice basis: 4 dates at $400 each appear to be the working basis.",
                "Companion invoice: generate a Winship-branded Excel/PDF invoice.",
                "Destination/contact: Annette appears to be the email/payment follow-up contact.",
                "Official payment rail: Coupa supplier portal invoice from PO.",
                "Records: save the generated invoice with today's date for future invoice range tracking.",
                "Still missing: confirmed Coupa PO/reference, final artifact, approval/send gates.",
                "External actions: locked.",
            ),
            operator_actions=actions,
            truth_status="DRAFT_UNDERSTANDING_NOT_TRUTH",
            proof_status="PROOF_REQUIRED",
            next_safe_move="Ask whether this understanding looks right.",
        ),
        RouterHumanCard(
            card_id="router_card_proposed_workflow_capital_hilton",
            card_type="PROPOSED_WORKFLOW",
            title="Proposed workflow",
            bullets=(
                "1. Confirm captured dates/rate.",
                "2. Generate or update Winship-branded Excel/PDF invoice.",
                "3. Confirm/discover Coupa PO/reference.",
                "4. Prepare Coupa supplier portal invoice path.",
                "5. Prepare email draft to Annette with PDF attached.",
                "6. Request Guardian approval.",
                "7. Send/submit only after gates.",
                "8. Save dated invoice artifact.",
                "9. Record proof and last invoice date.",
                "10. Track payment state.",
            ),
            operator_actions=actions,
            truth_status="NEEDS_OPERATOR_REVIEW",
            proof_status="BACKEND_READBACK_REQUIRED",
            next_safe_move="Review or edit the proposed workflow.",
        ),
        RouterHumanCard(
            card_id="router_card_missing_info_capital_hilton",
            card_type="MISSING_INFO",
            title="What still needs to be confirmed",
            bullets=(
                "Exact Coupa PO/reference.",
                "Whether Annette is confirmed as the correct contact.",
                "Whether the final invoice artifact exists and has a hash.",
                "Whether Guardian approval exists.",
                "Whether send/submit receipts exist.",
            ),
            operator_actions=actions,
            truth_status="NEEDS_OPERATOR_REVIEW",
            proof_status="PROOF_REQUIRED",
            next_safe_move="Ask for the Coupa PO/reference or contact confirmation next.",
        ),
        RouterHumanCard(
            card_id="router_card_blocked_capital_hilton",
            card_type="BLOCKED",
            title="What is not happening yet",
            bullets=(
                "No email sent.",
                "No Coupa access.",
                "No browser opened.",
                "No invoice submitted.",
                "No approval requested.",
                "No payment state changed.",
            ),
            operator_actions=actions,
            truth_status="LOCKED_EXTERNAL_ACTION",
            proof_status="PROOF_REQUIRED",
            next_safe_move="Keep all external actions locked until future approval/proof rails exist.",
        ),
    )


def _build_backend_target(routed_intent_ref: str, *, workflow_type: str) -> RouterBackendPackageTarget:
    return RouterBackendPackageTarget(
        package_target_id=f"router_backend_package_target_{_short_hash(routed_intent_ref, workflow_type)}",
        routed_intent_ref=routed_intent_ref,
        package_type="WORKFLOW_MEMORY_PROPOSAL" if workflow_type == "invoice_delivery_workflow" else "UNKNOWN_NEEDS_FRAMING",
        workflow_type=workflow_type,
        role_targets=(
            "drafting_agent",
            "finance_delivery_agent",
            "protected_evidence_agent",
            "approval_agent",
            "artifact_generation_agent",
            "post_office_handoff",
            "final_readback_agent",
        ),
        required_inputs=(
            "operator-reviewed understanding",
            "confirmed Coupa PO/reference",
            "confirmed recipient/contact",
        ),
        required_artifacts=(
            "final invoice artifact path/hash",
            "reviewed draft packet",
            "approval packet",
        ),
        required_proofs=(
            "Coupa proof or not-required proof",
            "Guardian/operator approval receipt",
            "send/submit receipts before completion",
        ),
        required_gates=(
            "operator review gate",
            "artifact hash gate",
            "protected evidence gate",
            "Guardian/operator approval gate",
            "external adapter gate",
        ),
        blocked_actions=LOCKED_ACTIONS,
        ready_actions=(
            "show cards to operator",
            "ask whether the understanding looks right",
            "ask for missing Coupa/contact facts",
        ),
        output_readback_target="Mac human card readback",
        can_create_now=False,
        create_block_reason="No safe deterministic package creation path is enabled in this rail.",
        next_safe_move="Show cards to operator and ask whether the understanding looks right.",
    )


def route_request(request: ConversationalWorkflowRouterIntakeRequest) -> tuple[ConversationalWorkflowRouterIntakeResult, RouterReadbackPackage, RouterIntakeReceipt]:
    if _is_capital_hilton_invoice_request(request):
        workflow_type = "invoice_delivery_workflow"
        routed_intent_ref = "routed_intent_capital_hilton_invoice_delivery_from_chat"
        cards = _build_capital_hilton_cards(request.request_id)
        parse_status = "ROUTED_DRAFT_READY"
        safe_summary = "OpenClaw routed the Capital Hilton invoice message to draft human cards."
    else:
        workflow_type = "unknown_needs_framing"
        routed_intent_ref = "routed_intent_unknown_needs_framing_from_chat"
        cards = (
            RouterHumanCard(
                card_id="router_card_unknown_needs_framing",
                card_type="MISSING_INFO",
                title="I need one more detail",
                bullets=("What outcome do you want OpenClaw to prepare?",),
                operator_actions=("Edit understanding", "Cancel"),
                truth_status="NEEDS_OPERATOR_REVIEW",
                proof_status="BACKEND_READBACK_REQUIRED",
                next_safe_move="Ask a clarifying question before routing.",
            ),
        )
        parse_status = "NEEDS_MORE_DETAIL"
        safe_summary = "OpenClaw needs more detail before routing this chat message."
    backend_target = _build_backend_target(routed_intent_ref, workflow_type=workflow_type)
    readback = RouterReadbackPackage(
        readback_id=f"router_readback_{_short_hash(request.request_id, request.payload_hash)}",
        source_request_ref=request.request_id,
        intake_result_ref=f"router_intake_result_{_short_hash(request.request_id, parse_status)}",
        cards=tuple(asdict(card) for card in cards),
        backend_package_target=asdict(backend_target),
        operator_choices=tuple(
            {"label": choice, "available_now": choice in {"Looks right", "Edit understanding", "Cancel"}}
            for choice in OPERATOR_CHOICES
        ),
        missing_backend_rails=(
            "procedure memory writer",
            "workflow package creator",
            "final artifact generator",
            "Guardian approval request rail",
            "email/Coupa gated adapters",
            "payment tracking writer",
        ),
        locked_actions=LOCKED_ACTIONS,
        safe_display_summary=safe_summary,
        elioperator_summary=(
            "ELIOPERATOR: This is a routed draft understanding. Nothing was sent, submitted, opened, "
            "approved, stored as procedure memory, or run."
        ),
        next_safe_move="Show cards to the operator and ask whether the understanding looks right.",
    )
    result = ConversationalWorkflowRouterIntakeResult(
        intake_result_id=readback.intake_result_ref,
        source_request_ref=request.request_id,
        parse_status=parse_status,
        parser_mode="deterministic_draft_router",
        model_parser_available=False,
        routed_intent_ref=routed_intent_ref,
        human_card_readback_ref=readback.readback_id,
        backend_package_request_ref=backend_target.package_target_id,
        duplicate_status="NOT_PERSISTED_NO_DUPLICATE_CHECK",
        operator_review_required=True,
        external_authority=False,
        next_safe_move=readback.next_safe_move,
    )
    receipt = RouterIntakeReceipt(
        receipt_id=f"router_intake_receipt_{_short_hash(request.idempotency_key, request.payload_hash)}",
        source_request_ref=request.request_id,
        idempotency_key=request.idempotency_key,
        payload_hash=request.payload_hash,
        intake_status=parse_status,
        readback_ref=readback.readback_id,
        duplicate_result="NOT_PERSISTED_NO_DUPLICATE_CHECK",
        external_authority=False,
        raw_body_ingestion=False,
        credential_handling=False,
        created_at_policy="metadata-only deterministic readback timestamp; no SQLite write",
    )
    return result, readback, receipt


def build_rejected_readback(
    *,
    request: ConversationalWorkflowRouterIntakeRequest,
    blockers: tuple[RouterIntakeBlocker, ...],
    parse_status: str = "REJECTED_INVALID_REQUEST",
) -> tuple[ConversationalWorkflowRouterIntakeResult, RouterReadbackPackage, RouterIntakeReceipt]:
    card = RouterHumanCard(
        card_id="router_card_request_blocked",
        card_type="BLOCKED",
        title="Request blocked",
        bullets=tuple(blocker.elioperator_warning for blocker in blockers) or ("Request shape was not safe.",),
        operator_actions=("Edit understanding", "Cancel"),
        truth_status="LOCKED_EXTERNAL_ACTION",
        proof_status="BACKEND_READBACK_REQUIRED",
        next_safe_move="Fix the request shape and retry.",
    )
    backend_target = _build_backend_target("routed_intent_blocked_request", workflow_type="unknown_needs_framing")
    readback = RouterReadbackPackage(
        readback_id=f"router_readback_blocked_{_short_hash(request.request_id, parse_status)}",
        source_request_ref=request.request_id,
        intake_result_ref=f"router_intake_result_blocked_{_short_hash(request.request_id, parse_status)}",
        cards=(asdict(card),),
        backend_package_target=asdict(backend_target),
        operator_choices=tuple({"label": choice, "available_now": choice in {"Edit understanding", "Cancel"}} for choice in OPERATOR_CHOICES),
        missing_backend_rails=("valid request shape",),
        locked_actions=LOCKED_ACTIONS,
        safe_display_summary="Request blocked before routing.",
        elioperator_summary="ELIOPERATOR: The chat request did not pass safe intake validation.",
        next_safe_move="Fix the request shape and retry.",
    )
    result = ConversationalWorkflowRouterIntakeResult(
        intake_result_id=readback.intake_result_ref,
        source_request_ref=request.request_id,
        parse_status=parse_status,
        parser_mode="deterministic_draft_router",
        model_parser_available=False,
        routed_intent_ref=None,
        human_card_readback_ref=readback.readback_id,
        backend_package_request_ref=backend_target.package_target_id,
        duplicate_status="NOT_PERSISTED_NO_DUPLICATE_CHECK",
        operator_review_required=True,
        external_authority=False,
        next_safe_move=readback.next_safe_move,
    )
    receipt = RouterIntakeReceipt(
        receipt_id=f"router_intake_receipt_blocked_{_short_hash(request.request_id, parse_status)}",
        source_request_ref=request.request_id,
        idempotency_key=request.idempotency_key or None,
        payload_hash=request.payload_hash or None,
        intake_status=parse_status,
        readback_ref=readback.readback_id,
        duplicate_result="NOT_PERSISTED_NO_DUPLICATE_CHECK",
        external_authority=False,
        raw_body_ingestion=False,
        credential_handling=False,
        created_at_policy="metadata-only deterministic readback timestamp; no SQLite write",
    )
    return result, readback, receipt


def build_no_request_payload(*, generated_at: str | None = None, inbox: Path = APPROVED_INBOX) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    request = ConversationalWorkflowRouterIntakeRequest(
        request_id="no_mission_control_chat_request_available",
        workflow_ref="unknown",
        workflow_type="unknown_needs_framing",
        world_ref="unknown",
        lane_ref="unknown",
        client_ref="unknown",
        tenant_ref="unknown",
        origin_surface="none",
        source_channel="none",
        operator_message="",
        sanitized_message_summary=f"No {REQUEST_FILENAME_PATTERN} file was found in the approved inbox.",
        privacy_class="no_request",
        idempotency_key="",
        payload_hash="",
        authority_boundary=AUTHORITY_BOUNDARY,
        created_at=generated_at,
    )
    blocker = _blocker(
        "UNSUPPORTED_REQUEST_SHAPE",
        f"No Mission Control chat request is available at {inbox.as_posix()}.",
        severity="NEEDS_INPUT",
    )
    result, readback, receipt = build_rejected_readback(
        request=request,
        blockers=(blocker,),
        parse_status="NEEDS_MORE_DETAIL",
    )
    return _build_payload(
        generated_at=generated_at,
        source_request_path=None,
        intake_request=request,
        intake_result=result,
        readback=readback,
        receipt=receipt,
        blockers=(blocker,),
        route_mode="NO_REQUEST_AVAILABLE",
    )


def build_payload_from_request_file(
    request_path: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    raw_request = _load_json(request_path)
    ok, blockers = validate_request_shape(raw_request, request_path=request_path)
    request = normalize_request(raw_request)
    if ok:
        result, readback, receipt = route_request(request)
        route_mode = "REQUEST_ROUTED"
    else:
        result, readback, receipt = build_rejected_readback(request=request, blockers=blockers)
        route_mode = "REQUEST_REJECTED"
    return _build_payload(
        generated_at=generated_at,
        source_request_path=request_path,
        intake_request=request,
        intake_result=result,
        readback=readback,
        receipt=receipt,
        blockers=blockers,
        route_mode=route_mode,
    )


def _build_payload(
    *,
    generated_at: str,
    source_request_path: Path | None,
    intake_request: ConversationalWorkflowRouterIntakeRequest,
    intake_result: ConversationalWorkflowRouterIntakeResult,
    readback: RouterReadbackPackage,
    receipt: RouterIntakeReceipt,
    blockers: tuple[RouterIntakeBlocker, ...],
    route_mode: str,
) -> dict[str, Any]:
    standard_blockers = build_standard_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "route_mode": route_mode,
        "source_request_path": source_request_path.as_posix() if source_request_path else None,
        "approved_inbox": APPROVED_INBOX.as_posix(),
        "supported_filename_pattern": REQUEST_FILENAME_PATTERN,
        "model_schemas": _model_schemas(),
        "intake_request": asdict(intake_request),
        "intake_result": asdict(intake_result),
        "router_readback_package": asdict(readback),
        "router_intake_receipt": asdict(receipt),
        "active_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "standard_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in standard_blockers},
        "operator_markdown_mode": "ELIOPERATOR",
        "relationship_refs": {
            "router_contract": "conversational_workflow_router_contract_v0",
            "workflow_memory_contract": "conversational_workflow_memory_contract_v0",
            "handoff_registry": "cross_surface_artifact_handoff_registry_contract_v0",
            "metadata_alignment": "cross_surface_handoff_registry_metadata_alignment_v0",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    readback = payload["router_readback_package"]
    cards = readback["cards"]
    backend_target = readback["backend_package_target"]
    card_types = {card["card_type"] for card in cards}
    card_text = stable_json(cards).lower()
    return {
        "intake_request_model_present": True,
        "intake_result_model_present": True,
        "router_human_card_model_present": True,
        "router_readback_package_model_present": True,
        "router_backend_package_target_model_present": True,
        "router_intake_receipt_model_present": True,
        "router_intake_blocker_model_present": True,
        "capital_hilton_cards_available_if_routed": (
            payload["intake_result"]["parse_status"] != "ROUTED_DRAFT_READY"
            or {"OPENCLAW_UNDERSTOOD", "PROPOSED_WORKFLOW", "MISSING_INFO", "BLOCKED"}.issubset(card_types)
        ),
        "workflow_type_invoice_delivery_if_routed": (
            payload["intake_result"]["parse_status"] != "ROUTED_DRAFT_READY"
            or backend_target["workflow_type"] == "invoice_delivery_workflow"
        ),
        "backend_package_type_workflow_memory_proposal_if_routed": (
            payload["intake_result"]["parse_status"] != "ROUTED_DRAFT_READY"
            or backend_target["package_type"] == "WORKFLOW_MEMORY_PROPOSAL"
        ),
        "can_create_backend_package_now": backend_target["can_create_now"],
        "external_actions_locked": all(action in readback["locked_actions"] for action in LOCKED_ACTIONS),
        "operator_review_required": payload["intake_result"]["operator_review_required"],
        "message_treated_as_truth": False,
        "model_parser_available": payload["intake_result"]["model_parser_available"],
        "external_authority": payload["intake_result"]["external_authority"],
        "raw_body_ingestion": payload["router_intake_receipt"]["raw_body_ingestion"],
        "credential_handling": payload["router_intake_receipt"]["credential_handling"],
        "machine_contract_visible_to_operator": any(
            token in card_text for token in ("schema", "handler", "manifest", "payload_hash", "package_request")
        ),
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
        "network_used": False,
        "external_action_performed": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def format_operator_markdown(payload: dict[str, Any]) -> str:
    readback = payload["router_readback_package"]
    cards = readback["cards"]
    lines = [
        "# Conversational Workflow Router Readback v0",
        "",
        "ELIOPERATOR: This readback is for the Mac chat surface. It shows what OpenClaw understood, what is proposed, what is missing, and what stays locked. It does not execute anything.",
        "",
        f"- Route mode: `{payload['route_mode']}`.",
        f"- Parse status: `{payload['intake_result']['parse_status']}`.",
        f"- Source request: `{payload['source_request_path'] or 'none yet'}`.",
        "",
        "## Cards",
        "",
    ]
    for card in cards:
        lines.append(f"### {card['title']}")
        lines.extend(f"- {bullet}" for bullet in card["bullets"])
        lines.append("")
    lines.extend(
        [
            "## Operator Choices",
            "",
        ]
    )
    for choice in readback["operator_choices"]:
        availability = "available now" if choice["available_now"] else "future rail needed"
        lines.append(f"- {choice['label']}: {availability}.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No live LM/model parser was used.",
            "- No agent dispatch, workflow run, procedure memory write, Cassandra draft, or Guardian approval occurred.",
            "- No email, Coupa, browser, invoice generation, attachment, approval request, send, submit, or payment-state change occurred.",
            "- No credentials, raw bodies, network, Mac sync/import, Swift change, or push occurred.",
            "",
            f"Next safe move: {readback['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    target = payload["router_readback_package"]["backend_package_target"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "route_mode": payload["route_mode"],
        "parse_status": payload["intake_result"]["parse_status"],
        "source_request_path": payload["source_request_path"],
        "workflow_type": target["workflow_type"],
        "package_type": target["package_type"],
        "can_create_now": target["can_create_now"],
        "external_authority": payload["intake_result"]["external_authority"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def build_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = args.generated_at
    if args.request_json:
        return build_payload_from_request_file(Path(args.request_json), generated_at=generated_at)
    latest = find_latest_request(Path(args.inbox))
    if latest is None:
        return build_no_request_payload(generated_at=generated_at, inbox=Path(args.inbox))
    return build_payload_from_request_file(latest, generated_at=generated_at)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import/export conversational workflow router chat readback.")
    parser.add_argument(
        "--request-json",
        "--file",
        dest="request_json",
        default=None,
        help="Path to a mission_control_chat_request_*.json file.",
    )
    parser.add_argument("--inbox", default=str(APPROVED_INBOX))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_payload_from_args(args)
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
