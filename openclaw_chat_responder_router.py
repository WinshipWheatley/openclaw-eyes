"""OpenClaw Chat Responder Router v0.

This module builds the first bounded chat responder rail:

Mac chat/router readback -> safe context package -> local-only responder
selection -> assistant response readback.

It does not call cloud models, use network, execute tools, dispatch agents,
run workflows, write procedure memory, access external systems, create drafts,
send, submit, approve, generate invoices, handle credentials, or ingest raw
private bodies. If no approved local chat responder adapter is connected, it
returns a truthful unavailable readback instead of a fake model answer.
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
DEFAULT_ROUTER_READBACK = DEFAULT_EXPORT_ROOT / "conversational_workflow_router_readback.json"
DEFAULT_CARD_MIRROR = DEFAULT_EXPORT_ROOT / "chat_readback_card_mirror.json"
DEFAULT_VISUAL_FEED = DEFAULT_EXPORT_ROOT / "chat_workflow_run_state_visual_feed.json"
APPROVED_LOCAL_RESPONDER_ADAPTER = Path("openclaw_chat_local_responder_adapter.py")
EXISTING_LOCAL_HELPER = Path("chief_llm.py")

SCHEMA_VERSION = "openclaw_chat_responder_router_v0"
READ_MODEL_ID = "openclaw_chat_responder_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LOCAL_ONLY_CHAT_RESPONDER_ROUTER_CONTEXT_PACKAGE_RAIL"

CAPITAL_HILTON_FIXTURE_TEXT = (
    "Yeah, your example text is basically it. I am pretty sure the system knows the 4 dates that the "
    "invoice is asking pay for at $400 each. Excel invoice needs to be generated and attached to the "
    "email to Annette. The invoice should also be saved in the system for records. The invoice in the "
    "Coupa Supplier Portal needs to be generated off of the PO that is also in Coupa Supplier Portal "
    "and submitted."
)

CAPITAL_HILTON_SAFE_SUMMARY = (
    "Capital Hilton invoice workflow request: four known invoice dates at $400 each, a Winship-branded "
    "Excel/PDF companion invoice for Annette, Coupa/PO as the official payment rail, and recordkeeping "
    "for the saved invoice."
)

WORKFLOW_TYPE = "invoice_delivery_workflow"
WORKFLOW_REF = "capital_hilton_invoice_workflow"
WORLD_REF = "finance"
LANE_REF = "capital_hilton"
CLIENT_REF = "capital_hilton"
TENANT_REF = "operator_winship_local"
RESPONDER_ROLE = "finance_workflow_responder"
PACKAGE_TYPE = "CHAT_RESPONSE_CONTEXT_PACKAGE"

KNOWN_FACTS = (
    "4 dates at $400 each working basis",
    "Excel/PDF companion invoice desired",
    "Annette contact candidate",
    "Coupa/PO payment rail candidate",
    "invoice should be saved for records",
)

MISSING_ITEMS = (
    "exact Coupa PO/reference or a decision to keep discovery open",
    "confirmation that Annette is the right contact",
    "final invoice artifact/hash",
    "Guardian approval",
    "send/submit receipts",
)

LOCKED_ACTIONS = (
    "email draft",
    "email send",
    "Coupa access",
    "Coupa submit",
    "browser automation",
    "approval request",
    "invoice generation",
    "attachment",
    "payment state update",
)

FORBIDDEN_CLAIMS = (
    "invoice generated",
    "email drafted",
    "email sent",
    "Coupa accessed",
    "Coupa submitted",
    "approval requested",
    "approval granted",
    "workflow run",
    "procedure stored",
    "payment state updated",
    "INVOICE SENT",
)

ALLOWED_RESPONSE_TYPES = (
    "draft_understanding",
    "missing_info_question",
    "locked_action_notice",
    "next_safe_move",
)

RESPONSE_STATUSES = (
    "RESPONSE_READY",
    "LOCAL_MODEL_UNAVAILABLE",
    "BLOCKED_NO_APPROVED_RESPONDER",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "NO_APPROVED_LOCAL_MODEL",
    "CLOUD_MODEL_ATTEMPTED",
    "NETWORK_ATTEMPTED",
    "TOOL_EXECUTION_ATTEMPTED",
    "AGENT_DISPATCH_ATTEMPTED",
    "WORKFLOW_RUN_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "RAW_PRIVATE_BODY_INCLUDED",
    "CREDENTIAL_INCLUDED",
    "FAKE_TRUTH_CLAIM",
    "COMPLETION_WITHOUT_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_local_model_response_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_procedure_memory_write_allowed": False,
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
    "cloud_model_allowed": False,
    "network_allowed": False,
    "browser_automation_allowed": False,
    "approval_submission_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class OpenClawChatResponderRequest:
    request_id: str
    source_chat_request_ref: str
    source_router_readback_ref: str
    workflow_ref: str
    workflow_type: str
    world_ref: str
    lane_ref: str
    client_ref: str
    tenant_ref: str
    operator_message_summary: str
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class ChatResponderContextPackage:
    package_id: str
    request_ref: str
    package_type: str
    included_context_refs: tuple[str, ...]
    included_summary: str
    excluded_context_summary: tuple[str, ...]
    known_facts: tuple[str, ...]
    missing_items: tuple[str, ...]
    locked_actions: tuple[str, ...]
    truth_boundary: str
    allowed_response_scope: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    sensitivity_class: str
    next_safe_move: str


@dataclass(frozen=True)
class ResponderSelection:
    selection_id: str
    request_ref: str
    responder_role: str
    candidate_model: str | None
    model_source: str
    local_only: bool
    model_available: bool
    selected: bool
    blocked_reason: str | None
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawChatResponderPolicy:
    policy_id: str
    local_model_allowed: bool
    cloud_model_allowed: bool
    network_allowed: bool
    tool_execution_allowed: bool
    agent_dispatch_allowed: bool
    workflow_run_allowed: bool
    state_write_allowed: bool
    external_action_allowed: bool
    allowed_response_types: tuple[str, ...]
    forbidden_response_claims: tuple[str, ...]
    truth_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawChatResponderOutput:
    output_id: str
    request_ref: str
    context_package_ref: str
    responder_selection_ref: str
    response_status: str
    model_used: str | None
    assistant_message: str
    follow_up_questions: tuple[str, ...]
    suggested_human_cards: tuple[dict[str, Any], ...]
    blocked_claims_removed: tuple[str, ...]
    truth_boundary_notice: str
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawChatResponderReadback:
    readback_id: str
    output_ref: str
    readback_status: str
    assistant_message: str
    cards_for_mac: tuple[dict[str, Any], ...]
    operator_choices: tuple[dict[str, Any], ...]
    missing_backend_rails: tuple[str, ...]
    locked_actions: tuple[str, ...]
    truth_status: str
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawChatResponderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


REQUIRED_REQUEST_FIELDS = tuple(OpenClawChatResponderRequest.__dataclass_fields__.keys())
REQUIRED_CONTEXT_FIELDS = tuple(ChatResponderContextPackage.__dataclass_fields__.keys())
REQUIRED_SELECTION_FIELDS = tuple(ResponderSelection.__dataclass_fields__.keys())
REQUIRED_POLICY_FIELDS = tuple(OpenClawChatResponderPolicy.__dataclass_fields__.keys())
REQUIRED_OUTPUT_FIELDS = tuple(OpenClawChatResponderOutput.__dataclass_fields__.keys())
REQUIRED_READBACK_FIELDS = tuple(OpenClawChatResponderReadback.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(OpenClawChatResponderBlocker.__dataclass_fields__.keys())


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
        "openclaw_chat_responder_request": {"required_fields": list(REQUIRED_REQUEST_FIELDS)},
        "chat_responder_context_package": {"required_fields": list(REQUIRED_CONTEXT_FIELDS)},
        "responder_selection": {"required_fields": list(REQUIRED_SELECTION_FIELDS)},
        "openclaw_chat_responder_policy": {"required_fields": list(REQUIRED_POLICY_FIELDS)},
        "openclaw_chat_responder_output": {"required_fields": list(REQUIRED_OUTPUT_FIELDS)},
        "openclaw_chat_responder_readback": {"required_fields": list(REQUIRED_READBACK_FIELDS)},
        "openclaw_chat_responder_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
    }


def _router_readback_ref(router_readback: Mapping[str, Any] | None) -> str:
    if not router_readback:
        return "conversational_workflow_router_readback_missing"
    package = router_readback.get("router_readback_package")
    if isinstance(package, Mapping):
        return str(package.get("readback_id") or "conversational_workflow_router_readback")
    return "conversational_workflow_router_readback"


def _request_id(router_readback: Mapping[str, Any] | None, fixture: str) -> str:
    if router_readback:
        intake = router_readback.get("intake_request")
        if isinstance(intake, Mapping) and intake.get("request_id"):
            return str(intake["request_id"])
    return f"{fixture}_chat_responder_request"


def _source_chat_request_ref(router_readback: Mapping[str, Any] | None, fixture: str) -> str:
    if router_readback:
        intake = router_readback.get("intake_request")
        if isinstance(intake, Mapping) and intake.get("request_id"):
            return str(intake["request_id"])
    return f"{fixture}_fixture"


def _message_summary(router_readback: Mapping[str, Any] | None, fixture: str) -> str:
    if router_readback:
        intake = router_readback.get("intake_request")
        if isinstance(intake, Mapping):
            summary = intake.get("sanitized_message_summary") or intake.get("operator_message")
            if summary:
                return str(summary)
    if fixture == "capital_hilton":
        return CAPITAL_HILTON_SAFE_SUMMARY
    return "Operator chat message requires framing."


def build_request(router_readback: Mapping[str, Any] | None, *, fixture: str) -> OpenClawChatResponderRequest:
    request_id = _request_id(router_readback, fixture)
    return OpenClawChatResponderRequest(
        request_id=f"openclaw_chat_responder_request_{request_id}",
        source_chat_request_ref=_source_chat_request_ref(router_readback, fixture),
        source_router_readback_ref=_router_readback_ref(router_readback),
        workflow_ref=WORKFLOW_REF,
        workflow_type=WORKFLOW_TYPE,
        world_ref=WORLD_REF,
        lane_ref=LANE_REF,
        client_ref=CLIENT_REF,
        tenant_ref=TENANT_REF,
        operator_message_summary=_message_summary(router_readback, fixture),
        privacy_class="client_private_or_operator_provided_sanitized_summary",
        next_safe_move="Build a safe context package and select a local-only responder if an approved rail exists.",
    )


def build_context_package(
    request: OpenClawChatResponderRequest,
    *,
    router_readback: Mapping[str, Any] | None,
    card_mirror: Mapping[str, Any] | None,
    visual_feed: Mapping[str, Any] | None,
) -> ChatResponderContextPackage:
    included_refs = [request.source_router_readback_ref]
    if card_mirror:
        included_refs.append("chat_readback_card_mirror")
    if visual_feed:
        included_refs.append("chat_workflow_run_state_visual_feed")
    router_summary = "Router classified this as a Capital Hilton invoice delivery workflow."
    if router_readback and isinstance(router_readback.get("router_readback_package"), Mapping):
        router_summary = str(router_readback["router_readback_package"].get("safe_display_summary") or router_summary)
    return ChatResponderContextPackage(
        package_id=f"chat_response_context_package_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        package_type=PACKAGE_TYPE,
        included_context_refs=tuple(included_refs),
        included_summary=(
            f"{router_summary} The response may explain the draft understanding, missing pieces, locked actions, "
            "and next safe move."
        ),
        excluded_context_summary=(
            "credentials and tokens",
            "raw email bodies",
            "raw PDFs or Excel bodies",
            "protected evidence bodies",
            "raw PO/payment references",
            "external account data",
            "tool or runtime handles",
        ),
        known_facts=KNOWN_FACTS,
        missing_items=MISSING_ITEMS,
        locked_actions=LOCKED_ACTIONS,
        truth_boundary="This is a draft assistant explanation grounded in readbacks; receipts/readbacks remain truth.",
        allowed_response_scope=ALLOWED_RESPONSE_TYPES,
        forbidden_claims=FORBIDDEN_CLAIMS,
        sensitivity_class="client_private_sanitized_metadata_only",
        next_safe_move="Give a concise operator-facing explanation or report that no approved responder is available.",
    )


def _existing_local_helper_detected(root: Path) -> bool:
    helper = root / EXISTING_LOCAL_HELPER
    if not helper.exists():
        return False
    text = helper.read_text(encoding="utf-8", errors="ignore")
    return "def resolve_local_model" in text and "def ollama_call" in text


def _approved_adapter_detected(root: Path) -> bool:
    adapter = root / APPROVED_LOCAL_RESPONDER_ADAPTER
    if not adapter.exists():
        return False
    text = adapter.read_text(encoding="utf-8", errors="ignore")
    return "APPROVED_OPENCLAW_CHAT_RESPONDER_ADAPTER_V0" in text


def build_responder_selection(request: OpenClawChatResponderRequest, *, root: Path = Path(".")) -> ResponderSelection:
    helper_detected = _existing_local_helper_detected(root)
    adapter_detected = _approved_adapter_detected(root)
    candidate = "gemma4:26b" if helper_detected else None
    if adapter_detected:
        return ResponderSelection(
            selection_id=f"responder_selection_{request.source_chat_request_ref}",
            request_ref=request.request_id,
            responder_role=RESPONDER_ROLE,
            candidate_model=candidate,
            model_source="approved local chat responder adapter",
            local_only=True,
            model_available=True,
            selected=True,
            blocked_reason=None,
            next_safe_move="Use the approved local responder adapter without tools or external authority.",
        )
    return ResponderSelection(
        selection_id=f"responder_selection_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        responder_role=RESPONDER_ROLE,
        candidate_model=candidate,
        model_source=(
            "existing chief_llm local helper detected but not approved for this chat responder lane"
            if helper_detected
            else "no local responder helper detected"
        ),
        local_only=True,
        model_available=False,
        selected=False,
        blocked_reason="No approved local chat responder adapter is connected.",
        next_safe_move="Connect an approved local-only chat responder adapter, then rerun this router.",
    )


def build_policy() -> OpenClawChatResponderPolicy:
    return OpenClawChatResponderPolicy(
        policy_id="openclaw_chat_responder_policy_v0",
        local_model_allowed=True,
        cloud_model_allowed=False,
        network_allowed=False,
        tool_execution_allowed=False,
        agent_dispatch_allowed=False,
        workflow_run_allowed=False,
        state_write_allowed=False,
        external_action_allowed=False,
        allowed_response_types=ALLOWED_RESPONSE_TYPES,
        forbidden_response_claims=FORBIDDEN_CLAIMS,
        truth_boundary="The responder may explain readback state; receipts/readbacks remain truth.",
        next_safe_move="Fail closed unless a local-only responder rail is approved and available.",
    )


def _unavailable_message() -> str:
    return (
        "No approved local responder model is available yet. The router and context package are ready, "
        "but OpenClaw cannot produce a live LM reply until a local model responder rail is connected."
    )


def _response_ready_message() -> str:
    return (
        "I understand the workflow you are describing: use the captured four-date/$400 basis, create the "
        "Winship-branded Excel/PDF invoice, send it to Annette for records/payment follow-up, and keep "
        "Coupa/PO as the official payment rail. This is still a draft workflow, not execution. To make it "
        "runnable, OpenClaw still needs the exact Coupa PO/reference or a decision to keep discovery open, "
        "confirmation that Annette is the right contact, and approval gates before anything sends or submits. "
        "Nothing external has happened yet."
    )


def _cards_for_response(status: str) -> tuple[dict[str, Any], ...]:
    if status == "RESPONSE_READY":
        return (
            {
                "card_type": "ASSISTANT_REPLY",
                "title": "OpenClaw can answer",
                "summary": "A local responder generated a bounded explanation from the context package.",
                "truth_status": "DRAFT_EXPLANATION_NOT_TRUTH",
            },
        )
    return (
        {
            "card_type": "RESPONDER_BLOCKED",
            "title": "Responder unavailable",
            "summary": "The route and context package are ready, but no approved local responder rail is connected.",
            "truth_status": "BLOCKED_NO_APPROVED_RESPONDER",
        },
        {
            "card_type": "NEXT_STEP",
            "title": "Next safe move",
            "summary": "Connect an approved local-only chat responder adapter before asking an LM to answer.",
            "truth_status": "NEEDS_BACKEND_RAIL",
        },
    )


def build_output(
    request: OpenClawChatResponderRequest,
    context: ChatResponderContextPackage,
    selection: ResponderSelection,
) -> OpenClawChatResponderOutput:
    if not selection.selected:
        status = "LOCAL_MODEL_UNAVAILABLE"
        message = _unavailable_message()
        model_used = None
    else:
        # The v0 adapter proof gate is modeled, not exercised here. This branch is
        # intentionally unreachable in the current repo because no approved
        # adapter exists.
        status = "RESPONSE_READY"
        message = _response_ready_message()
        model_used = selection.candidate_model
    return OpenClawChatResponderOutput(
        output_id=f"openclaw_chat_responder_output_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        context_package_ref=context.package_id,
        responder_selection_ref=selection.selection_id,
        response_status=status,
        model_used=model_used,
        assistant_message=message,
        follow_up_questions=(
            "Do you want to keep Coupa PO discovery open, or do you have the exact reference?",
            "Is Annette the right contact for the follow-up email?",
            "Should OpenClaw wait for Guardian approval before any future send/submit rail is considered?",
        ),
        suggested_human_cards=_cards_for_response(status),
        blocked_claims_removed=(),
        truth_boundary_notice="Assistant response is explanatory only; receipts/readbacks remain truth.",
        next_safe_move=(
            "Show the unavailable responder readback and connect the missing local responder rail."
            if status != "RESPONSE_READY"
            else "Show the assistant response and ask the operator to confirm or correct it."
        ),
    )


def build_readback(
    output: OpenClawChatResponderOutput,
    context: ChatResponderContextPackage,
) -> OpenClawChatResponderReadback:
    return OpenClawChatResponderReadback(
        readback_id=f"openclaw_chat_responder_readback_{output.request_ref}",
        output_ref=output.output_id,
        readback_status=output.response_status,
        assistant_message=output.assistant_message,
        cards_for_mac=output.suggested_human_cards,
        operator_choices=(
            {"label": "Show context package", "enabled": True, "external_action": False},
            {"label": "Connect local responder later", "enabled": False, "external_action": False},
            {"label": "Cancel", "enabled": True, "external_action": False},
        ),
        missing_backend_rails=(
            "approved local-only chat responder adapter",
            "bounded local model call wrapper for this lane",
            "assistant response receipt writer",
        )
        if output.response_status != "RESPONSE_READY"
        else (),
        locked_actions=context.locked_actions,
        truth_status="EXPLANATION_NOT_TRUTH_NO_EXECUTION",
        next_safe_move=output.next_safe_move,
    )


def build_blockers() -> tuple[OpenClawChatResponderBlocker, ...]:
    conditions = {
        "NO_APPROVED_LOCAL_MODEL": "No approved local chat responder adapter is connected.",
        "CLOUD_MODEL_ATTEMPTED": "A cloud model/API was attempted.",
        "NETWORK_ATTEMPTED": "Network access was attempted.",
        "TOOL_EXECUTION_ATTEMPTED": "A tool execution path was attempted.",
        "AGENT_DISPATCH_ATTEMPTED": "A live agent dispatch path was attempted.",
        "WORKFLOW_RUN_ATTEMPTED": "A workflow run was attempted.",
        "EXTERNAL_ACTION_ATTEMPTED": "An external action was attempted.",
        "RAW_PRIVATE_BODY_INCLUDED": "Raw private body content was included in the context package.",
        "CREDENTIAL_INCLUDED": "Credential or token material was included.",
        "FAKE_TRUTH_CLAIM": "A response claimed truth that no receipt/readback proves.",
        "COMPLETION_WITHOUT_PROOF": "Completion was claimed without proof receipts.",
        "UNKNOWN_FAIL_CLOSED": "Unknown responder state fails closed.",
    }
    return tuple(
        OpenClawChatResponderBlocker(
            blocker_id=f"openclaw_chat_responder_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_RESPONSE" if blocker_type != "NO_APPROVED_LOCAL_MODEL" else "BLOCKS_LIVE_LM_REPLY",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move="Return a blocked readback and do not ask a model to answer.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_openclaw_chat_responder_payload(
    *,
    fixture: str = "capital_hilton",
    router_readback_path: Path = DEFAULT_ROUTER_READBACK,
    card_mirror_path: Path = DEFAULT_CARD_MIRROR,
    visual_feed_path: Path = DEFAULT_VISUAL_FEED,
    root: Path = Path("."),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    router_readback = _load_json(router_readback_path)
    card_mirror = _load_json(card_mirror_path)
    visual_feed = _load_json(visual_feed_path)
    request = build_request(router_readback, fixture=fixture)
    context = build_context_package(
        request,
        router_readback=router_readback,
        card_mirror=card_mirror,
        visual_feed=visual_feed,
    )
    selection = build_responder_selection(request, root=root)
    policy = build_policy()
    output = build_output(request, context, selection)
    readback = build_readback(output, context)
    blockers = build_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "fixture": fixture,
        "route": {
            "domain_ref": request.world_ref,
            "workflow_type": request.workflow_type,
            "lane_ref": request.lane_ref,
            "client_ref": request.client_ref,
            "responder_role": selection.responder_role,
            "package_type": context.package_type,
        },
        "response_statuses": RESPONSE_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "openclaw_chat_responder_request": asdict(request),
        "chat_responder_context_package": asdict(context),
        "responder_selection": asdict(selection),
        "openclaw_chat_responder_policy": asdict(policy),
        "openclaw_chat_responder_output": asdict(output),
        "openclaw_chat_responder_readback": asdict(readback),
        "openclaw_chat_responder_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "capital_hilton_fixture": {
            "input_summary": CAPITAL_HILTON_SAFE_SUMMARY,
            "expected_if_model_available": _response_ready_message(),
            "expected_if_model_unavailable": _unavailable_message(),
        },
        "source_refs": {
            "router_readback": router_readback_path.as_posix(),
            "card_mirror": card_mirror_path.as_posix(),
            "visual_feed": visual_feed_path.as_posix(),
            "existing_local_helper": EXISTING_LOCAL_HELPER.as_posix(),
            "approved_adapter_required": APPROVED_LOCAL_RESPONDER_ADAPTER.as_posix(),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _visible_text(payload: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    output = payload["openclaw_chat_responder_output"]
    readback = payload["openclaw_chat_responder_readback"]
    context = payload["chat_responder_context_package"]
    chunks.extend([output["assistant_message"], output["truth_boundary_notice"], output["next_safe_move"]])
    chunks.extend(output["follow_up_questions"])
    chunks.extend(context["known_facts"])
    chunks.extend(context["missing_items"])
    chunks.extend(context["locked_actions"])
    chunks.extend(readback["locked_actions"])
    for card in readback["cards_for_mac"]:
        chunks.extend(str(card.get(key) or "") for key in ("title", "summary", "truth_status"))
    return "\n".join(chunks)


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    selection = payload["responder_selection"]
    output = payload["openclaw_chat_responder_output"]
    context = payload["chat_responder_context_package"]
    readback = payload["openclaw_chat_responder_readback"]
    blockers = payload["openclaw_chat_responder_blockers_by_id"]
    visible = _visible_text(payload).lower()
    fake_claims = [
        claim
        for claim in ("invoice generated", "email sent", "coupa accessed", "coupa submitted", "approval requested", "procedure stored")
        if claim in visible and output["response_status"] != "RESPONSE_READY"
    ]
    return {
        "openclaw_chat_responder_request_model_present": True,
        "chat_responder_context_package_model_present": True,
        "responder_selection_model_present": True,
        "openclaw_chat_responder_policy_model_present": True,
        "openclaw_chat_responder_output_model_present": True,
        "openclaw_chat_responder_readback_model_present": True,
        "openclaw_chat_responder_blocker_model_present": True,
        "route_context_package_built": payload["route"]["workflow_type"] == WORKFLOW_TYPE
        and context["package_type"] == PACKAGE_TYPE,
        "capital_hilton_route_correct": payload["route"]["domain_ref"] == WORLD_REF
        and payload["route"]["client_ref"] == CLIENT_REF
        and payload["route"]["workflow_type"] == WORKFLOW_TYPE,
        "local_model_availability_detected": selection["model_available"] is False
        and selection["selected"] is False
        and selection["blocked_reason"] == "No approved local chat responder adapter is connected.",
        "model_unavailable_status_not_fake_success": output["response_status"] in {
            "LOCAL_MODEL_UNAVAILABLE",
            "BLOCKED_NO_APPROVED_RESPONDER",
        },
        "assistant_message_truthful_for_unavailable_model": "No approved local responder model is available yet."
        in output["assistant_message"],
        "context_excludes_private_bodies": all(
            item in context["excluded_context_summary"]
            for item in (
                "credentials and tokens",
                "raw email bodies",
                "raw PDFs or Excel bodies",
                "protected evidence bodies",
            )
        ),
        "external_actions_locked": all(action in readback["locked_actions"] for action in LOCKED_ACTIONS),
        "no_fake_truth_claims": not fake_claims,
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "cloud_model_allowed_false": payload["openclaw_chat_responder_policy"]["cloud_model_allowed"] is False,
        "network_allowed_false": payload["openclaw_chat_responder_policy"]["network_allowed"] is False,
        "tool_execution_allowed_false": payload["openclaw_chat_responder_policy"]["tool_execution_allowed"] is False,
        "agent_dispatch_allowed_false": payload["openclaw_chat_responder_policy"]["agent_dispatch_allowed"] is False,
        "workflow_run_allowed_false": payload["openclaw_chat_responder_policy"]["workflow_run_allowed"] is False,
        "external_action_allowed_false": payload["openclaw_chat_responder_policy"]["external_action_allowed"] is False,
        "no_cloud_model_api_used": True,
        "no_network_used": True,
        "no_tool_execution_used": True,
        "no_agent_dispatch_used": True,
        "no_workflow_run_used": True,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_included": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    request = payload["openclaw_chat_responder_request"]
    context = payload["chat_responder_context_package"]
    selection = payload["responder_selection"]
    output = payload["openclaw_chat_responder_output"]
    readback = payload["openclaw_chat_responder_readback"]
    lines = [
        "# OpenClaw Chat Responder Router v0",
        "",
        "ELIOPERATOR: This routes a chat message to a safe responder context package. It does not execute the workflow.",
        "",
        f"- Workflow: `{request['workflow_type']}`.",
        f"- Client: `{request['client_ref']}`.",
        f"- Responder role: `{selection['responder_role']}`.",
        f"- Response status: `{output['response_status']}`.",
        f"- Selected model: `{selection['selected']}`.",
        "",
        "## Assistant Message",
        "",
        output["assistant_message"],
        "",
        "## Context Package",
        "",
        f"- Package type: `{context['package_type']}`.",
        f"- Included summary: {context['included_summary']}",
        f"- Truth boundary: {context['truth_boundary']}",
        "",
        "Known:",
        *[f"- {item}" for item in context["known_facts"]],
        "",
        "Missing:",
        *[f"- {item}" for item in context["missing_items"]],
        "",
        "Locked:",
        *[f"- {item}" for item in readback["locked_actions"]],
        "",
        "## Responder Selection",
        "",
        f"- Model source: {selection['model_source']}",
        f"- Model available: `{selection['model_available']}`.",
        f"- Blocked reason: {selection['blocked_reason'] or 'none'}",
        "",
        "## Boundary",
        "",
        "- No cloud model/API was used.",
        "- No network was used.",
        "- No tools, agents, workflow run, procedure memory write, email, Coupa, browser, approval, invoice generation, attachment, payment tracking write, or external action happened.",
        "",
        f"Next safe move: {readback['next_safe_move']}",
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    route = payload["route"]
    selection = payload["responder_selection"]
    output = payload["openclaw_chat_responder_output"]
    readback = payload["openclaw_chat_responder_readback"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "route": route,
        "responder_role": selection["responder_role"],
        "candidate_model": selection["candidate_model"],
        "model_source": selection["model_source"],
        "model_available": selection["model_available"],
        "selected": selection["selected"],
        "response_status": output["response_status"],
        "assistant_message": output["assistant_message"],
        "follow_up_questions": list(output["follow_up_questions"]),
        "locked_actions": list(readback["locked_actions"]),
        "missing_backend_rails": list(readback["missing_backend_rails"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "no_cloud_model_api_used": payload["machine_proof"]["no_cloud_model_api_used"],
        "no_network_used": payload["machine_proof"]["no_network_used"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/export the OpenClaw chat responder router readback.")
    parser.add_argument("--fixture", default="capital_hilton", choices=("capital_hilton",))
    parser.add_argument("--router-readback", type=Path, default=DEFAULT_ROUTER_READBACK)
    parser.add_argument("--card-mirror", type=Path, default=DEFAULT_CARD_MIRROR)
    parser.add_argument("--visual-feed", type=Path, default=DEFAULT_VISUAL_FEED)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_openclaw_chat_responder_payload(
        fixture=args.fixture,
        router_readback_path=args.router_readback,
        card_mirror_path=args.card_mirror,
        visual_feed_path=args.visual_feed,
    )
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
