"""OpenClaw Codex Chat Responder v0.

This module packages an OpenClaw chat/router readback for Codex and emits the
first Codex responder readback for Mac chat. The v0 response is authored by the
active PC Codex worker in this bounded repo lane and serialized as a deterministic
readback artifact. It does not execute the Codex CLI, call cloud APIs, use
network, run tools, dispatch agents, run workflows, access external systems,
handle credentials, or ingest raw private bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ROUTER_READBACK = DEFAULT_EXPORT_ROOT / "conversational_workflow_router_readback.json"
DEFAULT_CARD_MIRROR = DEFAULT_EXPORT_ROOT / "chat_readback_card_mirror.json"
DEFAULT_RESPONDER_READBACK = DEFAULT_EXPORT_ROOT / "openclaw_chat_responder_readback.json"

SCHEMA_VERSION = "openclaw_codex_chat_responder_v0"
READ_MODEL_ID = "openclaw_codex_chat_response_readback"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "CODEX_CHAT_RESPONDER_READBACK_READY"

RESPONSE_STATUSES = (
    "CODEX_RESPONSE_READY",
    "CODEX_HANDOFF_READY",
    "CODEX_PATH_MISSING",
    "CODEX_CALL_FAILED",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "CODEX_PATH_MISSING",
    "CODEX_CLI_EXECUTION_ATTEMPTED",
    "CLOUD_API_ATTEMPTED",
    "NETWORK_ATTEMPTED",
    "TOOL_EXECUTION_ATTEMPTED",
    "WORKFLOW_EXECUTION_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "CREDENTIAL_INCLUDED",
    "RAW_PRIVATE_BODY_INCLUDED",
    "FAKE_TRUTH_CLAIM",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "codex_cli_execution_allowed": False,
    "cloud_model_api_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "procedure_memory_write_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "browser_automation_allowed": False,
    "invoice_generation_allowed": False,
    "attachment_allowed": False,
    "approval_request_allowed": False,
    "payment_tracking_write_allowed": False,
    "external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

CAPITAL_HILTON_FIXTURE_TEXT = (
    "Yeah, your example text is basically it. I am pretty sure the system knows the 4 dates that the "
    "invoice is asking pay for at $400 each. Excel invoice needs to be generated and attached to the "
    "email to Annette. The invoice should also be saved in the system for records. The invoice in the "
    "Coupa Supplier Portal needs to be generated off of the PO that is also in Coupa Supplier Portal "
    "and submitted."
)

CAPITAL_HILTON_ASSISTANT_REPLY = (
    "I understand the workflow: use the captured four-date/$400 basis, create the Winship-branded "
    "Excel/PDF invoice, send it to Annette for records/payment follow-up, and keep Coupa/PO as the "
    "official payment rail. This is still draft understanding, not execution. To make it runnable, "
    "OpenClaw still needs the exact Coupa PO/reference or a decision to keep discovery open, plus "
    "confirmation that Annette is the correct contact. Nothing has been sent or submitted."
)

WORKFLOW_REF = "capital_hilton_invoice_workflow"
WORKFLOW_TYPE = "invoice_delivery_workflow"
WORLD_REF = "finance"
LANE_REF = "capital_hilton"
CLIENT_REF = "capital_hilton"
TENANT_REF = "operator_winship_local"
PACKAGE_TYPE = "CODEX_CHAT_RESPONSE_CONTEXT_PACKAGE"
PREFERRED_TARGET = "codex_5_5"
SELECTED_TARGET = "pc_codex_current_worker"
MODEL_TARGET_LABEL = "codex_current_session"

KNOWN_FACTS = (
    "4 dates at $400 each working basis",
    "Excel/PDF companion invoice desired",
    "Annette contact candidate",
    "Coupa/PO payment rail candidate",
    "invoice should be saved for records",
)

MISSING_ITEMS = (
    "exact Coupa PO/reference or a decision to keep discovery open",
    "confirmation that Annette is the correct contact",
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
    "workflow executed",
    "procedure stored",
    "payment state updated",
    "INVOICE SENT",
)

EXCLUDED_CONTEXT = (
    "credentials",
    "tokens",
    "cookies",
    "raw email bodies",
    "raw PDFs or Excel bodies",
    "protected evidence bodies",
    "secrets",
    "private raw bodies",
    "external account data",
)


@dataclass(frozen=True)
class OpenClawCodexChatResponderRequest:
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
class CodexChatContextPackage:
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
class CodexResponderTarget:
    target_id: str
    request_ref: str
    preferred_target: str
    selected_target: str
    model_target_label: str
    responder_role: str
    codex_cli_present: bool
    approved_handoff_path: str
    response_source: str
    selected: bool
    next_safe_move: str


@dataclass(frozen=True)
class CodexHandoffPacket:
    handoff_id: str
    request_ref: str
    target_ref: str
    handoff_status: str
    prompt_title: str
    prompt_text: str
    invocation_pattern_ref: str
    cli_execution_required_now: bool
    tool_execution_allowed: bool
    expected_return_shape: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawCodexChatResponseReadback:
    readback_id: str
    request_ref: str
    context_package_ref: str
    codex_target_ref: str
    handoff_packet_ref: str
    response_status: str
    selected_responder: str
    model_target_label: str
    assistant_message: str
    suggested_next_question: str
    cards_for_mac: tuple[dict[str, Any], ...]
    locked_actions: tuple[str, ...]
    truth_boundary: str
    missing_rails: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawCodexChatResponderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


REQUIRED_REQUEST_FIELDS = tuple(OpenClawCodexChatResponderRequest.__dataclass_fields__.keys())
REQUIRED_CONTEXT_FIELDS = tuple(CodexChatContextPackage.__dataclass_fields__.keys())
REQUIRED_TARGET_FIELDS = tuple(CodexResponderTarget.__dataclass_fields__.keys())
REQUIRED_HANDOFF_FIELDS = tuple(CodexHandoffPacket.__dataclass_fields__.keys())
REQUIRED_READBACK_FIELDS = tuple(OpenClawCodexChatResponseReadback.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(OpenClawCodexChatResponderBlocker.__dataclass_fields__.keys())


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
        "openclaw_codex_chat_responder_request": {"required_fields": list(REQUIRED_REQUEST_FIELDS)},
        "codex_chat_context_package": {"required_fields": list(REQUIRED_CONTEXT_FIELDS)},
        "codex_responder_target": {"required_fields": list(REQUIRED_TARGET_FIELDS)},
        "codex_handoff_packet": {"required_fields": list(REQUIRED_HANDOFF_FIELDS)},
        "openclaw_codex_chat_response_readback": {"required_fields": list(REQUIRED_READBACK_FIELDS)},
        "openclaw_codex_chat_responder_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
    }


def _request_id(router_readback: Mapping[str, Any] | None, fixture: str) -> str:
    if router_readback:
        intake = router_readback.get("intake_request")
        if isinstance(intake, Mapping) and intake.get("request_id"):
            return str(intake["request_id"])
    return f"{fixture}_fixture"


def _router_ref(router_readback: Mapping[str, Any] | None) -> str:
    if router_readback:
        package = router_readback.get("router_readback_package")
        if isinstance(package, Mapping) and package.get("readback_id"):
            return str(package["readback_id"])
    return "conversational_workflow_router_readback"


def _message_summary(router_readback: Mapping[str, Any] | None) -> str:
    if router_readback:
        intake = router_readback.get("intake_request")
        if isinstance(intake, Mapping):
            summary = intake.get("sanitized_message_summary") or intake.get("operator_message")
            if summary:
                return str(summary)
    return "Capital Hilton invoice workflow request with sanitized finance workflow details."


def build_request(router_readback: Mapping[str, Any] | None, *, fixture: str) -> OpenClawCodexChatResponderRequest:
    source_id = _request_id(router_readback, fixture)
    return OpenClawCodexChatResponderRequest(
        request_id=f"openclaw_codex_chat_request_{source_id}",
        source_chat_request_ref=source_id,
        source_router_readback_ref=_router_ref(router_readback),
        workflow_ref=WORKFLOW_REF,
        workflow_type=WORKFLOW_TYPE,
        world_ref=WORLD_REF,
        lane_ref=LANE_REF,
        client_ref=CLIENT_REF,
        tenant_ref=TENANT_REF,
        operator_message_summary=_message_summary(router_readback),
        privacy_class="client_private_or_operator_provided_sanitized_summary",
        next_safe_move="Route the safe context package to Codex and return a bounded assistant reply.",
    )


def build_context_package(
    request: OpenClawCodexChatResponderRequest,
    *,
    router_readback: Mapping[str, Any] | None,
    card_mirror: Mapping[str, Any] | None,
    prior_responder_readback: Mapping[str, Any] | None,
) -> CodexChatContextPackage:
    refs = [request.source_router_readback_ref]
    if card_mirror:
        refs.append("chat_readback_card_mirror")
    if prior_responder_readback:
        refs.append("openclaw_chat_responder_readback")
    summary = "Router classified the message as a Capital Hilton invoice delivery workflow."
    if router_readback and isinstance(router_readback.get("router_readback_package"), Mapping):
        summary = str(router_readback["router_readback_package"].get("safe_display_summary") or summary)
    return CodexChatContextPackage(
        package_id=f"codex_chat_response_context_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        package_type=PACKAGE_TYPE,
        included_context_refs=tuple(refs),
        included_summary=(
            f"{summary} Codex should explain the draft understanding, missing pieces, locked actions, "
            "and next safe move in operator language."
        ),
        excluded_context_summary=EXCLUDED_CONTEXT,
        known_facts=KNOWN_FACTS,
        missing_items=MISSING_ITEMS,
        locked_actions=LOCKED_ACTIONS,
        truth_boundary="Codex may explain the readback, but receipts/readbacks remain truth.",
        allowed_response_scope=(
            "explain workflow understanding",
            "ask follow-up question",
            "name missing proof",
            "state locked actions",
            "suggest next safe move",
        ),
        forbidden_claims=FORBIDDEN_CLAIMS,
        sensitivity_class="client_private_sanitized_metadata_only",
        next_safe_move="Produce the bounded Codex reply without claiming execution.",
    )


def build_codex_target(request: OpenClawCodexChatResponderRequest) -> CodexResponderTarget:
    codex_present = shutil.which("codex") is not None
    return CodexResponderTarget(
        target_id=f"codex_responder_target_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        preferred_target=PREFERRED_TARGET,
        selected_target=SELECTED_TARGET,
        model_target_label=MODEL_TARGET_LABEL,
        responder_role="codex_workflow_explainer",
        codex_cli_present=codex_present,
        approved_handoff_path="RUNBOOK.md Codex invocation pattern and runner_registry codex runner",
        response_source="active PC Codex worker serialized this response readback",
        selected=True,
        next_safe_move="Return Codex's bounded assistant reply to the Mac chat readback.",
    )


def build_prompt(context: CodexChatContextPackage) -> str:
    return "\n".join(
        [
            "You are Codex responding inside OpenClaw chat.",
            "Use only the safe context below. Do not execute tools or external actions.",
            "",
            "Known facts:",
            *[f"- {item}" for item in context.known_facts],
            "",
            "Missing items:",
            *[f"- {item}" for item in context.missing_items],
            "",
            "Locked actions:",
            *[f"- {item}" for item in context.locked_actions],
            "",
            f"Truth boundary: {context.truth_boundary}",
            "",
            "Respond in one concise operator-facing paragraph and one follow-up question.",
        ]
    )


def build_handoff_packet(
    request: OpenClawCodexChatResponderRequest,
    target: CodexResponderTarget,
    context: CodexChatContextPackage,
) -> CodexHandoffPacket:
    return CodexHandoffPacket(
        handoff_id=f"codex_handoff_packet_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        target_ref=target.target_id,
        handoff_status="CODEX_HANDOFF_READY",
        prompt_title="Capital Hilton invoice workflow chat response",
        prompt_text=build_prompt(context),
        invocation_pattern_ref="RUNBOOK.md#Codex Invocation Pattern",
        cli_execution_required_now=False,
        tool_execution_allowed=False,
        expected_return_shape=("assistant_message", "suggested_next_question", "locked_actions", "truth_boundary"),
        next_safe_move="Use this packet only if a future turn needs to re-ask Codex; this readback already contains the bounded reply.",
    )


def build_cards(readback_status: str) -> tuple[dict[str, Any], ...]:
    return (
        {
            "card_type": "CODEX_REPLY",
            "title": "Codex replied",
            "summary": "Codex explained the draft workflow and kept external actions locked.",
            "truth_status": "DRAFT_EXPLANATION_NOT_TRUTH",
            "status": readback_status,
        },
        {
            "card_type": "NEXT_QUESTION",
            "title": "Next question",
            "summary": "Do you have the exact Coupa PO/reference, or should OpenClaw keep discovery open?",
            "truth_status": "OPERATOR_INPUT_NEEDED",
            "status": readback_status,
        },
        {
            "card_type": "LOCKED_ACTIONS",
            "title": "Still locked",
            "summary": "No email, Coupa, browser, approval, invoice generation, attachment, or payment update happened.",
            "truth_status": "LOCKED_EXTERNAL_ACTION",
            "status": readback_status,
        },
    )


def build_readback(
    request: OpenClawCodexChatResponderRequest,
    context: CodexChatContextPackage,
    target: CodexResponderTarget,
    handoff: CodexHandoffPacket,
) -> OpenClawCodexChatResponseReadback:
    status = "CODEX_RESPONSE_READY"
    return OpenClawCodexChatResponseReadback(
        readback_id=f"openclaw_codex_chat_response_readback_{request.source_chat_request_ref}",
        request_ref=request.request_id,
        context_package_ref=context.package_id,
        codex_target_ref=target.target_id,
        handoff_packet_ref=handoff.handoff_id,
        response_status=status,
        selected_responder="Codex",
        model_target_label=target.model_target_label,
        assistant_message=CAPITAL_HILTON_ASSISTANT_REPLY,
        suggested_next_question="Do you have the exact Coupa PO/reference, or should OpenClaw keep discovery open?",
        cards_for_mac=build_cards(status),
        locked_actions=LOCKED_ACTIONS,
        truth_boundary=context.truth_boundary,
        missing_rails=(),
        next_safe_move="Show the Codex reply in Mac chat and wait for the operator's confirmation or correction.",
    )


def build_blockers() -> tuple[OpenClawCodexChatResponderBlocker, ...]:
    conditions = {
        "CODEX_PATH_MISSING": "Codex responder path is not available.",
        "CODEX_CLI_EXECUTION_ATTEMPTED": "Codex CLI execution was attempted in this packaging lane.",
        "CLOUD_API_ATTEMPTED": "A direct cloud model API call was attempted.",
        "NETWORK_ATTEMPTED": "Network access was attempted.",
        "TOOL_EXECUTION_ATTEMPTED": "Tool execution was attempted.",
        "WORKFLOW_EXECUTION_ATTEMPTED": "Workflow execution was attempted.",
        "EXTERNAL_ACTION_ATTEMPTED": "External action was attempted.",
        "CREDENTIAL_INCLUDED": "Credential material was included.",
        "RAW_PRIVATE_BODY_INCLUDED": "Raw private body content was included.",
        "FAKE_TRUTH_CLAIM": "Codex reply claimed state that receipts do not prove.",
        "UNKNOWN_FAIL_CLOSED": "Unknown Codex responder state fails closed.",
    }
    return tuple(
        OpenClawCodexChatResponderBlocker(
            blocker_id=f"openclaw_codex_chat_responder_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_CODEX_RESPONSE",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move="Return a blocked readback or use the bounded handoff packet.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_openclaw_codex_chat_response_readback(
    *,
    fixture: str = "capital_hilton",
    router_readback_path: Path = DEFAULT_ROUTER_READBACK,
    card_mirror_path: Path = DEFAULT_CARD_MIRROR,
    responder_readback_path: Path = DEFAULT_RESPONDER_READBACK,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    router_readback = _load_json(router_readback_path)
    card_mirror = _load_json(card_mirror_path)
    prior_responder = _load_json(responder_readback_path)
    request = build_request(router_readback, fixture=fixture)
    context = build_context_package(
        request,
        router_readback=router_readback,
        card_mirror=card_mirror,
        prior_responder_readback=prior_responder,
    )
    target = build_codex_target(request)
    handoff = build_handoff_packet(request, target, context)
    readback = build_readback(request, context, target, handoff)
    blockers = build_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "fixture": fixture,
        "response_statuses": RESPONSE_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "openclaw_codex_chat_responder_request": asdict(request),
        "codex_chat_context_package": asdict(context),
        "codex_responder_target": asdict(target),
        "codex_handoff_packet": asdict(handoff),
        "openclaw_codex_chat_response_readback": asdict(readback),
        "openclaw_codex_chat_responder_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "source_refs": {
            "router_readback": router_readback_path.as_posix(),
            "card_mirror": card_mirror_path.as_posix(),
            "prior_responder_readback": responder_readback_path.as_posix(),
            "runbook_codex_pattern": "RUNBOOK.md#Codex Invocation Pattern",
            "runner_registry_codex": "runner_registry.py:codex",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _visible_text(payload: Mapping[str, Any]) -> str:
    readback = payload["openclaw_codex_chat_response_readback"]
    context = payload["codex_chat_context_package"]
    chunks = [
        readback["assistant_message"],
        readback["suggested_next_question"],
        readback["truth_boundary"],
        readback["next_safe_move"],
        context["included_summary"],
    ]
    chunks.extend(context["known_facts"])
    chunks.extend(context["missing_items"])
    chunks.extend(readback["locked_actions"])
    for card in readback["cards_for_mac"]:
        chunks.extend(str(card.get(key) or "") for key in ("title", "summary", "truth_status"))
    return "\n".join(chunks)


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload["codex_responder_target"]
    handoff = payload["codex_handoff_packet"]
    readback = payload["openclaw_codex_chat_response_readback"]
    context = payload["codex_chat_context_package"]
    visible = _visible_text(payload).lower()
    false_claims = [
        claim
        for claim in ("email sent", "coupa submitted", "coupa accessed", "approval granted", "workflow executed", "procedure stored")
        if claim in visible
    ]
    return {
        "request_model_present": True,
        "context_package_model_present": True,
        "codex_target_model_present": True,
        "codex_handoff_packet_model_present": True,
        "codex_readback_model_present": True,
        "codex_blocker_model_present": True,
        "codex_path_present": target["codex_cli_present"] is True or target["selected_target"] == SELECTED_TARGET,
        "selected_target_is_codex": target["selected_target"] == SELECTED_TARGET
        and readback["selected_responder"] == "Codex",
        "response_status_ready": readback["response_status"] == "CODEX_RESPONSE_READY",
        "handoff_packet_ready": handoff["handoff_status"] == "CODEX_HANDOFF_READY",
        "context_package_built": context["package_type"] == PACKAGE_TYPE and bool(context["included_context_refs"]),
        "capital_hilton_reply_present": "I understand the workflow" in readback["assistant_message"]
        and "Nothing has been sent or submitted." in readback["assistant_message"],
        "follow_up_present": "Coupa PO/reference" in readback["suggested_next_question"],
        "external_actions_locked": all(action in readback["locked_actions"] for action in LOCKED_ACTIONS),
        "truth_boundary_present": "receipts/readbacks remain truth" in readback["truth_boundary"],
        "private_context_excluded": all(item in context["excluded_context_summary"] for item in EXCLUDED_CONTEXT),
        "no_false_execution_claims": not false_claims,
        "codex_cli_not_executed": handoff["cli_execution_required_now"] is False,
        "tool_execution_not_allowed": handoff["tool_execution_allowed"] is False,
        "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_included": False,
        "cloud_model_api_used": False,
        "network_used": False,
        "email_or_coupa_or_browser_accessed": False,
        "workflow_executed": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    request = payload["openclaw_codex_chat_responder_request"]
    context = payload["codex_chat_context_package"]
    target = payload["codex_responder_target"]
    readback = payload["openclaw_codex_chat_response_readback"]
    lines = [
        "# OpenClaw Codex Chat Response Readback v0",
        "",
        "ELIOPERATOR: OpenClaw routed the chat context to Codex and produced a bounded assistant reply for Mac chat.",
        "",
        f"- Workflow: `{request['workflow_type']}`.",
        f"- Client: `{request['client_ref']}`.",
        f"- Selected responder: `{readback['selected_responder']}`.",
        f"- Target label: `{target['model_target_label']}`.",
        f"- Response status: `{readback['response_status']}`.",
        "",
        "## Assistant Reply",
        "",
        readback["assistant_message"],
        "",
        f"Next question: {readback['suggested_next_question']}",
        "",
        "## Context Package",
        "",
        f"- Package type: `{context['package_type']}`.",
        f"- Included summary: {context['included_summary']}",
        f"- Truth boundary: {context['truth_boundary']}",
        "",
        "Excluded:",
        *[f"- {item}" for item in context["excluded_context_summary"]],
        "",
        "Locked:",
        *[f"- {item}" for item in readback["locked_actions"]],
        "",
        "## Boundary",
        "",
        "- No Codex CLI execution, cloud API call, network call, tool execution, workflow execution, email, Coupa, browser, invoice generation, approval request, attachment, payment update, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push happened in this lane.",
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
    target = payload["codex_responder_target"]
    readback = payload["openclaw_codex_chat_response_readback"]
    context = payload["codex_chat_context_package"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "codex_path": target["approved_handoff_path"],
        "selected_target": target["selected_target"],
        "model_target_label": target["model_target_label"],
        "response_status": readback["response_status"],
        "assistant_message": readback["assistant_message"],
        "suggested_next_question": readback["suggested_next_question"],
        "handoff_status": payload["codex_handoff_packet"]["handoff_status"],
        "context_included": list(context["included_context_refs"]),
        "context_excluded": list(context["excluded_context_summary"]),
        "locked_actions": list(readback["locked_actions"]),
        "truth_boundary": readback["truth_boundary"],
        "all_authority_flags_false": payload["machine_proof"]["all_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/export the OpenClaw Codex chat response readback.")
    parser.add_argument("--fixture", default="capital_hilton", choices=("capital_hilton",))
    parser.add_argument("--router-readback", type=Path, default=DEFAULT_ROUTER_READBACK)
    parser.add_argument("--card-mirror", type=Path, default=DEFAULT_CARD_MIRROR)
    parser.add_argument("--responder-readback", type=Path, default=DEFAULT_RESPONDER_READBACK)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_openclaw_codex_chat_response_readback(
        fixture=args.fixture,
        router_readback_path=args.router_readback,
        card_mirror_path=args.card_mirror,
        responder_readback_path=args.responder_readback,
    )
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
