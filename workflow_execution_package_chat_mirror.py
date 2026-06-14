"""Workflow Execution Package Chat Mirror v0.

This deterministic exporter translates the workflow execution package compiler
read-model into Mac-renderable human chat cards. It does not execute packages,
dispatch workers, call models, run workflows, access external systems, generate
invoices, request approvals, send email, access Coupa/browser systems, handle
credentials, ingest raw bodies, import to Mac, or change Mission Control Swift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_SOURCE_READMODEL = DEFAULT_EXPORT_ROOT / "workflow_execution_package_compiler.json"
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "workflow_execution_package_chat_mirror_v0"
READ_MODEL_ID = "workflow_execution_package_chat_mirror"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WORKFLOW_EXECUTION_PACKAGE_CHAT_MIRROR"

MIRROR_STATUSES = (
    "READY_FOR_MAC_RENDER",
    "SOURCE_READMODEL_MISSING",
    "SOURCE_READMODEL_UNSUPPORTED",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

CARD_TYPES = (
    "MAKE_IT_HAPPEN_STATUS",
    "KNOWN",
    "STILL_NEEDED",
    "WORKER_PACKAGES",
    "STILL_LOCKED",
    "COMPLETION_TARGET",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_card_mirror_runtime_allowed": False,
    "live_package_execution_allowed": False,
    "live_worker_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_tool_execution_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_approval_request_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "network_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

FORBIDDEN_VISIBLE_TERMS = (
    "schema",
    "handler",
    "lifecycle",
    "payload_hash",
    "sha256",
    "raw id",
    "file path",
    "manifest",
    "sqlite",
    "package_plan",
    "json dump",
    "workflow_execution_package_compiler.json",
)

LOCKED_ACTIONS = (
    "email send",
    "Coupa access/submit",
    "browser automation",
    "approval request",
    "invoice generation",
    "attachment",
    "payment tracking update",
)

OPERATOR_CHOICES = (
    {
        "label": "Answer missing info",
        "enabled": True,
        "scope": "local_chat_reply",
        "external_authority": False,
    },
    {
        "label": "Review package plan",
        "enabled": True,
        "scope": "local_review_only",
        "external_authority": False,
    },
    {
        "label": "Cancel",
        "enabled": True,
        "scope": "local_chat_only",
        "external_authority": False,
    },
    {
        "label": "Prepare/send packages",
        "enabled": False,
        "disabled_reason": "Backend package send/execution is not connected in this lane.",
        "scope": "future_gated_action",
        "external_authority": False,
    },
)


@dataclass(frozen=True)
class WorkflowExecutionPackageChatMirror:
    mirror_id: str
    source_readmodel_ref: str | None
    workflow_ref: str | None
    workflow_type: str | None
    client_ref: str | None
    mirror_status: str
    assistant_lead_in: str
    cards: tuple[dict[str, Any], ...]
    operator_choices: tuple[dict[str, Any], ...]
    locked_actions: tuple[str, ...]
    truth_boundary: str
    privacy_summary: str
    authority_boundary: dict[str, bool]
    safe_display_summary: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowExecutionChatCard:
    card_id: str
    card_type: str
    title: str
    summary: str
    bullets: tuple[str, ...]
    status_tone: str
    truth_status: str
    proof_status: str
    operator_actions: tuple[str, ...]
    detail_available: bool
    detail_bullets: tuple[str, ...]
    next_safe_move: str


REQUIRED_MIRROR_FIELDS = tuple(WorkflowExecutionPackageChatMirror.__dataclass_fields__.keys())
REQUIRED_CARD_FIELDS = tuple(WorkflowExecutionChatCard.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _card(
    *,
    card_id: str,
    card_type: str,
    title: str,
    summary: str,
    bullets: tuple[str, ...],
    status_tone: str,
    truth_status: str,
    proof_status: str,
    operator_actions: tuple[str, ...],
    detail_bullets: tuple[str, ...] = (),
    next_safe_move: str,
) -> WorkflowExecutionChatCard:
    return WorkflowExecutionChatCard(
        card_id=card_id,
        card_type=card_type,
        title=title,
        summary=summary,
        bullets=bullets,
        status_tone=status_tone,
        truth_status=truth_status,
        proof_status=proof_status,
        operator_actions=operator_actions,
        detail_available=bool(detail_bullets),
        detail_bullets=detail_bullets,
        next_safe_move=next_safe_move,
    )


def _ready_cards(source: dict[str, Any]) -> tuple[WorkflowExecutionChatCard, ...]:
    readiness = source["workflow_execution_readiness"]
    example = source["capital_hilton_example"]
    completion = example["future_completion_target"]
    package_plan_count = len(source["worker_execution_package_plans_by_id"])

    return (
        _card(
            card_id="workflow_execution_card_make_it_happen_status",
            card_type="MAKE_IT_HAPPEN_STATUS",
            title="Make it happen status",
            summary=(
                "I can plan the Capital Hilton invoice workflow, but it is not runnable yet. "
                "Nothing has run."
            ),
            bullets=(
                "OpenClaw can prepare governed worker-package plans.",
                "The workflow still needs missing facts, proof, and approval.",
                "External actions remain locked.",
            ),
            status_tone="waiting",
            truth_status="BACKEND_READBACK_READY",
            proof_status="PROOF_REQUIRED_BEFORE_COMPLETION",
            operator_actions=("Answer missing info", "Review package plan", "Cancel"),
            detail_bullets=(
                "This is a planning readback, not a workflow run.",
                "Receipts are required before completion can be shown.",
            ),
            next_safe_move="Ask for the missing PO/reference or contact confirmation.",
        ),
        _card(
            card_id="workflow_execution_card_known",
            card_type="KNOWN",
            title="Known",
            summary="OpenClaw has enough context to describe the invoice plan, but not enough to execute it.",
            bullets=(
                "4 performance dates are captured.",
                "$400 per show, $1,600 working basis.",
                "Invoice preview exists.",
                "Excel/PDF companion invoice is desired.",
                "Annette and Coupa/PO are still candidate facts.",
            ),
            status_tone="proof",
            truth_status="BACKEND_READBACK_READY",
            proof_status="PARTIAL_PROOF",
            operator_actions=("Review package plan",),
            detail_bullets=tuple(readiness["known_facts"]),
            next_safe_move="Keep candidate facts separate from confirmed facts.",
        ),
        _card(
            card_id="workflow_execution_card_still_needed",
            card_type="STILL_NEEDED",
            title="Still needed",
            summary="These pieces are required before the workflow can become runnable.",
            bullets=(
                "Exact Coupa PO/reference.",
                "Confirmation that Annette is the correct contact.",
                "Final Winship-branded Excel/PDF artifact and hash.",
                "Guardian approval.",
                "Send/submit receipts.",
            ),
            status_tone="warning",
            truth_status="NEEDS_OPERATOR_INPUT",
            proof_status="MISSING_PROOF",
            operator_actions=("Answer missing info",),
            detail_bullets=tuple(readiness["missing_inputs"]),
            next_safe_move="Ask the operator for the PO/reference and contact confirmation.",
        ),
        _card(
            card_id="workflow_execution_card_worker_packages",
            card_type="WORKER_PACKAGES",
            title="Worker packages",
            summary=f"{package_plan_count} worker package plans would be needed. They are plans only.",
            bullets=(
                "PC backend validation.",
                "Mac artifact preparation.",
                "Protected proof references.",
                "Drafting and Guardian approval.",
                "Post office handoff and final readback.",
            ),
            status_tone="waiting",
            truth_status="PACKAGE_PLANS_READY_NOT_SENT",
            proof_status="PACKAGE_PROOF_REQUIRED",
            operator_actions=("Review package plan",),
            detail_bullets=(
                "Backend validation can verify current facts.",
                "Mac artifact preparation stays separate from send/submit authority.",
                "Drafting and approval remain gated.",
                "Final readback is blocked until receipts exist.",
            ),
            next_safe_move="Show this as a plan, not a dispatch.",
        ),
        _card(
            card_id="workflow_execution_card_still_locked",
            card_type="STILL_LOCKED",
            title="Still locked",
            summary="Nothing external happened.",
            bullets=(
                "No email draft or send.",
                "No Coupa access or submit.",
                "No browser automation.",
                "No invoice generation or attachment.",
                "No approval request or payment update.",
            ),
            status_tone="blocked",
            truth_status="LOCKED_EXTERNAL_ACTION",
            proof_status="NO_EXECUTION_PROOF_BY_DESIGN",
            operator_actions=("Cancel",),
            detail_bullets=tuple(readiness["blocked_items"]),
            next_safe_move="Keep external actions locked until future gates and receipts exist.",
        ),
        _card(
            card_id="workflow_execution_card_completion_target",
            card_type="COMPLETION_TARGET",
            title="Completion target",
            summary="INVOICE SENT is the future target, but it is blocked until proof receipts exist.",
            bullets=(
                "Coupa submission proof if required.",
                "Email send receipt with invoice attachment.",
                "Saved invoice artifact proof.",
                "Last invoice date update proof.",
                "Payment tracking update proof.",
            ),
            status_tone="waiting",
            truth_status="FUTURE_TARGET_ONLY",
            proof_status="COMPLETION_BLOCKED_MISSING_PROOF",
            operator_actions=("What proof is missing?",),
            detail_bullets=tuple(completion["proof_bullets"]),
            next_safe_move="Do not show INVOICE SENT until receipts prove it.",
        ),
    )


def _missing_source_mirror() -> WorkflowExecutionPackageChatMirror:
    card = _card(
        card_id="workflow_execution_card_source_missing",
        card_type="UNKNOWN_FAIL_CLOSED",
        title="Waiting on PC readback",
        summary="The workflow execution package compiler readback is not available yet.",
        bullets=("No package plan cards can be rendered until the source readback exists.",),
        status_tone="waiting",
        truth_status="SOURCE_MISSING",
        proof_status="READBACK_REQUIRED",
        operator_actions=("Cancel",),
        next_safe_move="Run the compiler export on PC and mirror the readback again.",
    )
    return WorkflowExecutionPackageChatMirror(
        mirror_id="workflow_execution_package_chat_mirror",
        source_readmodel_ref=None,
        workflow_ref=None,
        workflow_type=None,
        client_ref=None,
        mirror_status="SOURCE_READMODEL_MISSING",
        assistant_lead_in="I do not have the PC package compiler readback yet.",
        cards=(asdict(card),),
        operator_choices=OPERATOR_CHOICES,
        locked_actions=LOCKED_ACTIONS,
        truth_boundary="No truth without source readback.",
        privacy_summary="No private bodies or credentials are included.",
        authority_boundary=AUTHORITY_BOUNDARY,
        safe_display_summary="Waiting for workflow execution package compiler readback.",
        elioperator_summary="The card mirror fails closed when the source read-model is missing.",
        next_safe_move="Export the compiler read-model on PC.",
    )


def _ready_mirror(source: dict[str, Any]) -> WorkflowExecutionPackageChatMirror:
    readiness = source["workflow_execution_readiness"]
    cards = tuple(asdict(card) for card in _ready_cards(source))
    return WorkflowExecutionPackageChatMirror(
        mirror_id="workflow_execution_package_chat_mirror",
        source_readmodel_ref=source.get("read_model_id"),
        workflow_ref=readiness["workflow_ref"],
        workflow_type=readiness["workflow_type"],
        client_ref=readiness["client_ref"],
        mirror_status="READY_FOR_MAC_RENDER",
        assistant_lead_in="I can make this happen as a governed package plan, but it is not runnable yet.",
        cards=cards,
        operator_choices=OPERATOR_CHOICES,
        locked_actions=LOCKED_ACTIONS,
        truth_boundary="Package plans are not execution. Receipts/readbacks decide truth.",
        privacy_summary="Normal cards use sanitized workflow facts only; no private bodies, credentials, PO values, or protected evidence bodies are included.",
        authority_boundary=AUTHORITY_BOUNDARY,
        safe_display_summary="Capital Hilton make-it-happen package plan is ready for chat review.",
        elioperator_summary="OpenClaw can show what is known, what is missing, what packages would be needed, and what remains locked.",
        next_safe_move="Ask the operator for the PO/reference or contact confirmation.",
    )


def _model_schemas() -> dict[str, Any]:
    return {
        "workflow_execution_package_chat_mirror": {"required_fields": list(REQUIRED_MIRROR_FIELDS)},
        "workflow_execution_chat_card": {"required_fields": list(REQUIRED_CARD_FIELDS)},
    }


def _visible_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for card in payload["workflow_execution_package_chat_mirror"]["cards"]:
        chunks.extend([card["title"], card["summary"]])
        chunks.extend(card["bullets"])
        chunks.extend(card["operator_actions"])
    chunks.append(payload["workflow_execution_package_chat_mirror"]["assistant_lead_in"])
    chunks.append(payload["workflow_execution_package_chat_mirror"]["safe_display_summary"])
    return "\n".join(chunks)


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    mirror = payload["workflow_execution_package_chat_mirror"]
    titles = {card["title"] for card in mirror["cards"]}
    visible = _visible_text(payload).lower()
    return {
        "workflow_execution_package_chat_mirror_model_present": True,
        "workflow_execution_chat_card_model_present": True,
        "source_readmodel_present": payload["source_readmodel_present"],
        "ready_for_mac_render": mirror["mirror_status"] == "READY_FOR_MAC_RENDER",
        "required_cards_present": {
            "Make it happen status",
            "Known",
            "Still needed",
            "Worker packages",
            "Still locked",
            "Completion target",
        }.issubset(titles),
        "human_copy_only": all(term not in visible for term in FORBIDDEN_VISIBLE_TERMS),
        "completion_target_future_only": any(
            card["title"] == "Completion target"
            and card["truth_status"] == "FUTURE_TARGET_ONLY"
            and card["proof_status"] == "COMPLETION_BLOCKED_MISSING_PROOF"
            for card in mirror["cards"]
        ),
        "external_actions_locked": "email send" in mirror["locked_actions"] and "Coupa access/submit" in mirror["locked_actions"],
        "all_live_authority_flags_false": not any(AUTHORITY_BOUNDARY.values()),
        "external_action_performed": False,
        "package_execution_performed": False,
        "agent_dispatch_performed": False,
        "workflow_run_performed": False,
        "invoice_generation_performed": False,
        "approval_request_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_cards": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_workflow_execution_package_chat_mirror(
    *,
    source_readmodel_path: Path = DEFAULT_SOURCE_READMODEL,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    source = _read_json(source_readmodel_path)
    source_present = source is not None
    if source is None:
        mirror = _missing_source_mirror()
    elif source.get("read_model_id") != "workflow_execution_package_compiler":
        mirror = _missing_source_mirror()
        mirror = WorkflowExecutionPackageChatMirror(
            **{
                **asdict(mirror),
                "mirror_status": "SOURCE_READMODEL_UNSUPPORTED",
                "safe_display_summary": "Unsupported package compiler readback.",
                "next_safe_move": "Regenerate the workflow execution package compiler read-model.",
            }
        )
    else:
        mirror = _ready_mirror(source)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "source_readmodel_present": source_present,
        "source_readmodel_ref": source.get("read_model_id") if source else None,
        "model_schemas": _model_schemas(),
        "card_types": CARD_TYPES,
        "mirror_statuses": MIRROR_STATUSES,
        "forbidden_visible_terms": FORBIDDEN_VISIBLE_TERMS,
        "workflow_execution_package_chat_mirror": asdict(mirror),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "allowed_scope": (
            "deterministic card mirroring",
            "Mac-readable chat card payload",
            "tests",
            "metadata-only source reference",
        ),
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_export(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> Path:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    return json_path


def build_summary(payload: dict[str, Any], json_path: Path | None) -> dict[str, Any]:
    mirror = payload["workflow_execution_package_chat_mirror"]
    proof = payload["machine_proof"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "mirror_status": mirror["mirror_status"],
        "card_titles": [card["title"] for card in mirror["cards"]],
        "operator_choices": [choice["label"] for choice in mirror["operator_choices"]],
        "ready_for_mac_render": proof["ready_for_mac_render"],
        "required_cards_present": proof["required_cards_present"],
        "human_copy_only": proof["human_copy_only"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export workflow execution package chat mirror.")
    parser.add_argument("--source-readmodel", type=Path, default=DEFAULT_SOURCE_READMODEL)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_workflow_execution_package_chat_mirror(source_readmodel_path=args.source_readmodel)
    json_path = write_export(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
