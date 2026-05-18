"""Guardian draft approval request contract v0.

This read-model defines when a Guardian final-send approval request may be
formed for a Cassandra draft review packet. It does not notify Guardian, create
approval receipts, create Gmail drafts, send email, access external accounts, or
grant execution authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json
from guardian_hitl_sqlite_authority_contract import (
    CANONICAL_PAYLOAD_REQUIRED_FIELDS,
    validate_canonical_approval_payload,
)


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "guardian_draft_approval_request_contract_v0"
JSON_EXPORT_NAME = "guardian_draft_approval_request_contract.json"
OPERATOR_EXPORT_NAME = "guardian_draft_approval_request_contract_OPERATOR.md"

DEFAULT_DRAFT_PACKET_PATH = DEFAULT_EXPORT_ROOT / "cassandra_draft_review_packet.json"
DEFAULT_SEND_GATE_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_send_approval_gate.json"
DEFAULT_GUARDIAN_DNA_PATH = DEFAULT_EXPORT_ROOT / "guardian_responsibility_dna_audit.json"
DEFAULT_START_APPROVAL_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_coupa_start_approval_packet.json"

WORKFLOW_ID = "capital_hilton_companion_invoice_email"
WORKFLOW_NAME = "Capital Hilton companion invoice email"
REQUESTED_ACTION_TYPE = "final_send_email"
APPROVAL_TYPE = "guardian_final_send_approval_request"
TARGET_ACTION_ID = "send_specific_cassandra_email_with_specific_excel_invoice_pdf"
TTL_SECONDS = 6 * 60 * 60

AVAILABLE_STATUS = "available_for_guardian_final_send_approval_request"
BLOCKED_STATUS = "blocked_unavailable_missing_prerequisites"
IMPOSSIBLE_STATUS = "impossible_ambiguous_or_invalid_authority"

NO_AUTHORITY_FLAGS = {
    "review_only_contract": True,
    "approval_request_created": False,
    "approval_request_persisted": False,
    "approval_receipt_created": False,
    "execution_enabled": False,
    "guardian_message_sent": False,
    "telegram_send_triggered": False,
    "gmail_draft_created": False,
    "gmail_or_email_send_triggered": False,
    "email_send_enabled": False,
    "oauth_or_credentials_accessed": False,
    "calendar_access_triggered": False,
    "coupa_access_triggered": False,
    "browser_automation_added": False,
    "pdf_generated_or_attached": False,
    "spreadsheet_mutation_triggered": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "generic_approval_authority_added": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
}

REQUIRED_PROOF_KEYS = (
    "coupa_invoice_proof_exists",
    "coupa_invoice_proof_references_expected_po_invoice_context",
    "excel_companion_invoice_artifact_exists",
    "excel_companion_invoice_verified_to_match_coupa",
)

REQUIRED_DRAFT_ATTACHMENT_KEYS = (
    "cassandra_email_draft_exists",
    "attachment_reference_exists",
    "draft_identity_hash_reference_exists",
    "attachment_identity_hash_reference_exists",
)


@dataclass(frozen=True)
class GuardianDraftApprovalRequestContractExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    approval_request_contract_id: str
    current_availability_status: str
    approval_request_available_now: bool
    approval_request_created: bool
    approval_receipt_created: bool
    execution_enabled: bool
    guardian_message_sent: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _expires_at(requested_at: str) -> str:
    parsed = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(seconds=TTL_SECONDS)).replace(microsecond=0).isoformat()


def _source_ref(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _display_path(_rooted(path)),
        "present": bool(payload),
        "schema_version": payload.get("schema_version"),
        "raw_private_content_read": False,
        "external_account_accessed": False,
        "executed_or_dispatched": False,
    }


def _proof_requirements(send_gate: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = send_gate.get("prerequisite_evidence_status")
    if not isinstance(evidence, dict):
        evidence = {}
    labels = {
        "coupa_invoice_proof_exists": "Coupa supplier-portal payment invoice proof exists",
        "coupa_invoice_proof_references_expected_po_invoice_context": "Coupa proof references expected PO/invoice context",
        "excel_companion_invoice_artifact_exists": "Excel companion invoice artifact/reference exists",
        "excel_companion_invoice_verified_to_match_coupa": "Excel companion invoice is verified to reflect/match Coupa invoice",
    }
    return [
        {
            "proof_key": key,
            "label": labels[key],
            "required_before_approval_request_available": True,
            "present_now": bool(evidence.get(key)),
            "metadata_or_protected_reference_only": True,
            "raw_artifact_required": False,
        }
        for key in REQUIRED_PROOF_KEYS
    ]


def _attachment_requirements(send_gate: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = send_gate.get("prerequisite_evidence_status")
    if not isinstance(evidence, dict):
        evidence = {}
    labels = {
        "cassandra_email_draft_exists": "Cassandra draft review packet has a specific draft record",
        "attachment_reference_exists": "Excel companion invoice PDF attachment reference exists",
        "draft_identity_hash_reference_exists": "Draft identity/hash/reference exists",
        "attachment_identity_hash_reference_exists": "Attachment identity/hash/reference exists",
    }
    protected_keys = {"attachment_reference_exists", "attachment_identity_hash_reference_exists"}
    return [
        {
            "field_key": key,
            "label": labels[key],
            "required_before_approval_request_available": True,
            "present_now": bool(evidence.get(key)),
            "protected_reference_required": key in protected_keys,
            "raw_body_or_attachment_required": False,
        }
        for key in REQUIRED_DRAFT_ATTACHMENT_KEYS
    ]


def _draft_packet_reference(draft_packet: dict[str, Any], draft_path: str | Path) -> dict[str, Any]:
    return {
        "source_path": _display_path(_rooted(draft_path)),
        "source_present": bool(draft_packet),
        "source_schema_version": draft_packet.get("schema_version"),
        "workflow_id": draft_packet.get("workflow_id") or WORKFLOW_ID,
        "workflow_name": draft_packet.get("workflow_name") or WORKFLOW_NAME,
        "draft_packet_kind": draft_packet.get("packet_kind"),
        "draft_id": draft_packet.get("draft_id", ""),
        "draft_status": draft_packet.get("draft_status", ""),
        "packet_status": draft_packet.get("packet_status", ""),
        "review_only": bool(draft_packet.get("review_only", True)),
        "gmail_draft_created": bool(draft_packet.get("gmail_draft_created", False)),
        "email_sent": bool(draft_packet.get("email_sent", False)),
        "raw_email_body_copied_into_request_contract": False,
    }


def _start_approval_relationship(start_approval: dict[str, Any], send_gate: dict[str, Any]) -> dict[str, Any]:
    upstream = send_gate.get("upstream_start_approval_context")
    if not isinstance(upstream, dict):
        upstream = {}
    return {
        "source_present": bool(start_approval) or bool(upstream),
        "start_approval_type": start_approval.get("approval_type", "start_workflow_approval"),
        "final_send_approval_type": "send_email_with_invoice_approval",
        "start_approval_distinct_from_final_send_approval": True,
        "start_approval_authorizes_send": False,
        "final_send_requires_separate_guardian_request": True,
        "start_approval_reused_as_send_approval": False,
    }


def _scope_requirements() -> dict[str, Any]:
    return {
        "requested_action_type": REQUESTED_ACTION_TYPE,
        "target_action_id": TARGET_ACTION_ID,
        "target_action_summary": "send one specific Cassandra-drafted email with one specific Excel companion invoice PDF attachment",
        "workflow_id": WORKFLOW_ID,
        "workflow_name": WORKFLOW_NAME,
        "specific_action_scoped": True,
        "specific_draft_required": True,
        "specific_attachment_required": True,
        "immutable_scope_required": True,
        "generic_approval_authority_allowed": False,
        "general_email_authority_allowed": False,
        "payload_mutable_after_request": False,
    }


def _explicitly_excluded_authorities() -> list[str]:
    return [
        "live Guardian notification",
        "Telegram send",
        "Gmail draft creation",
        "email send",
        "OAuth or credential access",
        "calendar access",
        "Coupa access or submit",
        "browser automation",
        "PDF attachment generation",
        "spreadsheet mutation",
        "payment status change",
        "generic approval authority",
        "general runtime authority",
        "future sends beyond the exact draft and attachment",
    ]


def _request_receipt_execution_separation() -> dict[str, Any]:
    return {
        "review_packet": "Cassandra draft review packet; visible proposal, not approval or execution.",
        "approval_request": "Future specific immutable Guardian request with TTL/idempotency/payload hash; not dispatched here.",
        "approval_receipt": "Future exact operator decision evidence bound to the request payload hash; not created here.",
        "execution": "Future separately gated send path; not enabled here.",
        "approval_request_created_in_this_lane": False,
        "approval_receipt_created_in_this_lane": False,
        "execution_enabled_in_this_lane": False,
    }


def _availability(
    *,
    draft_packet: dict[str, Any],
    send_gate: dict[str, Any],
    proof_requirements: list[dict[str, Any]],
    attachment_requirements: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    if not draft_packet:
        blockers.append(
            {
                "blocker_id": "missing_cassandra_draft_review_packet",
                "severity": "impossible_until_source_exists",
                "description": "Cassandra draft review packet read-model is missing.",
            }
        )
    if not send_gate:
        blockers.append(
            {
                "blocker_id": "missing_capital_hilton_send_approval_gate",
                "severity": "impossible_until_source_exists",
                "description": "Capital Hilton send approval gate read-model is missing.",
            }
        )
    if blockers:
        return IMPOSSIBLE_STATUS, blockers

    if draft_packet.get("gmail_draft_created") or draft_packet.get("email_sent"):
        blockers.append(
            {
                "blocker_id": "draft_packet_has_live_external_action_state",
                "severity": "impossible_ambiguous_authority",
                "description": "Draft packet indicates live Gmail draft or email send state; fail closed.",
            }
        )
    if not draft_packet.get("review_only", False):
        blockers.append(
            {
                "blocker_id": "draft_packet_not_review_only",
                "severity": "impossible_ambiguous_authority",
                "description": "Draft packet is not clearly review-only.",
            }
        )
    if send_gate.get("guardian_message_sent") or send_gate.get("email_send_enabled"):
        blockers.append(
            {
                "blocker_id": "send_gate_has_live_authority_state",
                "severity": "impossible_ambiguous_authority",
                "description": "Send gate indicates live Guardian/email authority; fail closed.",
            }
        )
    if blockers:
        return IMPOSSIBLE_STATUS, blockers

    failure_reasons = ((send_gate.get("blocker_status") or {}).get("failure_reasons") or [])
    for reason in failure_reasons:
        blockers.append(
            {
                "blocker_id": str(reason),
                "severity": "blocks_approval_request",
                "description": str(reason).replace("_", " "),
            }
        )
    covered_failure_ids = {blocker["blocker_id"] for blocker in blockers}
    equivalent_failure_id = {
        "coupa_invoice_proof_exists": "missing_coupa_invoice_proof",
        "coupa_invoice_proof_references_expected_po_invoice_context": "missing_coupa_expected_po_invoice_context_reference",
        "excel_companion_invoice_artifact_exists": "missing_excel_companion_invoice",
        "excel_companion_invoice_verified_to_match_coupa": "missing_excel_match_proof",
        "cassandra_email_draft_exists": "missing_email_draft",
        "attachment_reference_exists": "missing_attachment_reference",
        "draft_identity_hash_reference_exists": "missing_draft_identity_hash_reference",
        "attachment_identity_hash_reference_exists": "missing_attachment_identity_hash_reference",
    }
    for item in proof_requirements:
        if (
            not item["present_now"]
            and item["proof_key"] not in covered_failure_ids
            and equivalent_failure_id[item["proof_key"]] not in covered_failure_ids
        ):
            blockers.append(
                {
                    "blocker_id": item["proof_key"],
                    "severity": "blocks_approval_request",
                    "description": item["label"],
                }
            )
    for item in attachment_requirements:
        if (
            not item["present_now"]
            and item["field_key"] not in covered_failure_ids
            and equivalent_failure_id[item["field_key"]] not in covered_failure_ids
        ):
            blockers.append(
                {
                    "blocker_id": item["field_key"],
                    "severity": "blocks_approval_request",
                    "description": item["label"],
                }
            )

    source_gate_available = (
        send_gate.get("current_approval_availability_state") == "available_for_guardian_send_approval"
        and bool((send_gate.get("blocker_status") or {}).get("approval_request_available_now"))
    )
    all_proof_present = all(item["present_now"] for item in proof_requirements)
    all_draft_attachment_present = all(item["present_now"] for item in attachment_requirements)
    if source_gate_available and all_proof_present and all_draft_attachment_present and not blockers:
        return AVAILABLE_STATUS, []
    return BLOCKED_STATUS, blockers


def _payload_identity_requirement(
    *,
    contract_id: str,
    generated_at: str,
    draft_ref: dict[str, Any],
    proof_requirements: list[dict[str, Any]],
    attachment_requirements: list[dict[str, Any]],
    availability_status: str,
) -> dict[str, Any]:
    scope = _scope_requirements()
    hash_basis = {
        "approval_type": APPROVAL_TYPE,
        "workflow_id": WORKFLOW_ID,
        "requested_action_type": REQUESTED_ACTION_TYPE,
        "draft_packet_reference": {
            "source_schema_version": draft_ref["source_schema_version"],
            "draft_id": draft_ref["draft_id"],
            "draft_status": draft_ref["draft_status"],
        },
        "proof_requirements": proof_requirements,
        "attachment_requirements": attachment_requirements,
        "approval_scope": scope,
        "excluded_authorities": _explicitly_excluded_authorities(),
    }
    payload_hash = hashlib.sha256(stable_json(hash_basis).encode("utf-8")).hexdigest()
    idempotency_key = _row_id("guardian_draft_send_idem", WORKFLOW_ID, payload_hash)
    canonical_template = {
        "approval_id": contract_id,
        "action_type": REQUESTED_ACTION_TYPE,
        "actor": "guardian",
        "target": WORKFLOW_ID,
        "payload_hash": payload_hash,
        "payload_schema_version": SCHEMA_VERSION,
        "source_intent_ref": draft_ref["draft_id"] or "modeled:cassandra_draft_review_packet",
        "idempotency_key": idempotency_key,
        "requested_at": generated_at,
        "expires_at": _expires_at(generated_at),
        "ttl_seconds": TTL_SECONDS,
        "authority_scope": "specific_draft_specific_attachment_final_send_only_no_execution",
        "risk_tier": "tier_2_external_communication_request_contract_only",
        "action_class": "email_send",
        "explicit_authorized_packet_ref": "blocked_until_specific_draft_and_attachment_identity_present",
        "payload_mutable_after_approval": False,
    }
    return {
        "payload_hash_required": True,
        "payload_hash_basis_required": [
            "workflow_id",
            "requested_action_type",
            "draft_packet_reference",
            "specific_draft_identity",
            "specific_attachment_identity",
            "proof_references",
            "approval_scope",
            "excluded_authorities",
        ],
        "contract_payload_hash": payload_hash,
        "contract_hash_status": "request_ready_hash" if availability_status == AVAILABLE_STATUS else "contract_hash_not_live_request",
        "usable_for_live_request_now": availability_status == AVAILABLE_STATUS,
        "canonical_approval_payload_template": canonical_template,
        "canonical_approval_payload_validation": validate_canonical_approval_payload(canonical_template),
    }


def _ttl_idempotency_requirement(payload_identity: dict[str, Any]) -> dict[str, Any]:
    template = payload_identity["canonical_approval_payload_template"]
    return {
        "ttl_required": True,
        "ttl_seconds": TTL_SECONDS,
        "expires_at_required": True,
        "expires_at": template["expires_at"],
        "idempotency_key_required": True,
        "idempotency_key": template["idempotency_key"],
        "idempotency_basis": [
            "actor",
            "action_type",
            "target",
            "payload_hash",
            "source_intent_ref",
        ],
        "duplicate_rule": "same active idempotency key must return the same active request rather than creating another authority record",
    }


def _future_receipt_requirements(payload_identity: dict[str, Any]) -> dict[str, Any]:
    template = payload_identity["canonical_approval_payload_template"]
    return {
        "required_future_request_receipt_type": "guardian_final_send_approval_request_receipt_v0",
        "required_future_approval_receipt_type": "guardian_final_send_approval_decision_receipt_v0",
        "required_future_execution_receipt_type": "email_send_result_receipt_v0_future_only",
        "approval_receipt_required_before_execution": True,
        "receipt_must_bind": [
            "approval_id",
            "decision",
            "decided_by",
            "decided_at",
            "approved_payload_hash",
            "draft_identity",
            "attachment_identity",
        ],
        "expected_approval_id": template["approval_id"],
        "expected_payload_hash": template["payload_hash"],
        "receipt_created_now": False,
    }


def build_guardian_draft_approval_request_contract(
    *,
    draft_packet_json: str | Path = DEFAULT_DRAFT_PACKET_PATH,
    send_gate_json: str | Path = DEFAULT_SEND_GATE_PATH,
    guardian_dna_json: str | Path = DEFAULT_GUARDIAN_DNA_PATH,
    start_approval_json: str | Path = DEFAULT_START_APPROVAL_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    draft_packet = _read_json_if_present(draft_packet_json)
    send_gate = _read_json_if_present(send_gate_json)
    guardian_dna = _read_json_if_present(guardian_dna_json)
    start_approval = _read_json_if_present(start_approval_json)

    proof_requirements = _proof_requirements(send_gate)
    attachment_requirements = _attachment_requirements(send_gate)
    availability_status, blockers = _availability(
        draft_packet=draft_packet,
        send_gate=send_gate,
        proof_requirements=proof_requirements,
        attachment_requirements=attachment_requirements,
    )
    draft_ref = _draft_packet_reference(draft_packet, draft_packet_json)
    contract_id = _row_id(
        "guardian_draft_approval_request_contract",
        SCHEMA_VERSION,
        WORKFLOW_ID,
        draft_ref.get("draft_id"),
    )
    payload_identity = _payload_identity_requirement(
        contract_id=contract_id,
        generated_at=ts,
        draft_ref=draft_ref,
        proof_requirements=proof_requirements,
        attachment_requirements=attachment_requirements,
        availability_status=availability_status,
    )
    request_available = availability_status == AVAILABLE_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "contract_kind": "guardian_draft_final_send_approval_request_contract",
        "approval_request_contract_id": contract_id,
        "workflow_id": WORKFLOW_ID,
        "workflow_name": WORKFLOW_NAME,
        "approval_type": APPROVAL_TYPE,
        "requested_action_type": REQUESTED_ACTION_TYPE,
        "target_action": {
            "action_id": TARGET_ACTION_ID,
            "action_summary": _scope_requirements()["target_action_summary"],
            "enabled_now": False,
            "future_only_after_request_receipt_and_execution_gate": True,
        },
        "current_availability_status": availability_status,
        "approval_request_available_now": request_available,
        "approval_request_created_in_this_lane": False,
        "approval_request_persisted": False,
        "approval_receipt_created_in_this_lane": False,
        "execution_enabled": False,
        "blockers": blockers,
        "source_read_models": {
            "cassandra_draft_review_packet": _source_ref(draft_packet_json, draft_packet),
            "capital_hilton_send_approval_gate": _source_ref(send_gate_json, send_gate),
            "guardian_responsibility_dna_audit": _source_ref(guardian_dna_json, guardian_dna),
            "capital_hilton_start_approval_packet": _source_ref(start_approval_json, start_approval),
        },
        "draft_packet_reference": draft_ref,
        "required_proof_references": proof_requirements,
        "required_attachment_and_identity_fields": attachment_requirements,
        "approval_scope": _scope_requirements(),
        "payload_hash_requirement": payload_identity,
        "ttl_idempotency_requirement": _ttl_idempotency_requirement(payload_identity),
        "future_receipt_requirements": _future_receipt_requirements(payload_identity),
        "start_approval_relationship": _start_approval_relationship(start_approval, send_gate),
        "request_receipt_execution_separation": _request_receipt_execution_separation(),
        "explicitly_excluded_authorities": _explicitly_excluded_authorities(),
        "guardian_dna_alignment": {
            "source_present": bool(guardian_dna),
            "guardian_is_not_executor": True,
            "approval_specific_action_scoped": True,
            "unknown_or_ambiguous_authority_fails_closed": True,
            "legacy_hitl_telegram_json_paths_are_reference_not_new_authority": True,
            "request_receipt_execution_are_distinct": True,
        },
        "status_summary": {
            "approval_request_contract_modeled": True,
            "approval_request_available_now": request_available,
            "approval_request_created": False,
            "approval_receipt_created": False,
            "execution_enabled": False,
            "guardian_message_sent": False,
            "telegram_send_triggered": False,
            "gmail_draft_created": False,
            "email_send_enabled": False,
            "runtime_authority_added": False,
            "send_or_submit_authority_added": False,
            "approval_authority_added": False,
            "current_availability_status": availability_status,
        },
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "operator_next_safe_move": (
            "Record Coupa payment-invoice proof, Excel companion artifact reference, and Excel-Coupa match proof "
            "through governed metadata/protected-reference rails before any Guardian final-send approval request lane."
            if not request_available
            else "A future lane may create or deliver the specific Guardian request packet; this lane still did not send or approve it."
        ),
        "next_recommended_lane": "Capital Hilton Proof Metadata Capture v0",
    }


def format_guardian_draft_approval_request_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Guardian Draft Approval Request Contract v0",
        "",
        "Status:",
        f"- Workflow: `{payload['workflow_name']}`.",
        f"- Approval request available now: `{str(payload['approval_request_available_now']).lower()}`.",
        f"- Current status: `{payload['current_availability_status']}`.",
        "- Approval request created: `false`.",
        "- Approval receipt created: `false`.",
        "- Guardian/Telegram notification sent: `false`.",
        "- Gmail draft/email send/execution enabled: `false`.",
        "",
        "## Draft Packet",
        f"- Draft packet: `{payload['draft_packet_reference']['draft_id'] or 'missing'}`.",
        f"- Draft status: `{payload['draft_packet_reference']['draft_status'] or 'missing'}`.",
        "- Scope: one specific Cassandra draft plus one specific Excel companion invoice attachment.",
        "",
        "## Required Proof",
    ]
    for item in payload["required_proof_references"]:
        status = "present" if item["present_now"] else "missing"
        lines.append(f"- `{item['proof_key']}`: {status} - {item['label']}.")
    lines.extend(["", "## Required Draft / Attachment Identity"])
    for item in payload["required_attachment_and_identity_fields"]:
        status = "present" if item["present_now"] else "missing"
        lines.append(f"- `{item['field_key']}`: {status} - {item['label']}.")
    lines.extend(["", "## Blockers"])
    if payload["blockers"]:
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker['blocker_id']}`: {blocker['description']}")
    else:
        lines.append("- No modeled blockers remain, but this contract still does not dispatch or execute.")
    lines.extend(
        [
            "",
            "## Guardian Contract Boundary",
            "- Start approval and final-send approval are distinct.",
            "- Review packet, approval request, approval receipt, and execution remain distinct.",
            "- Payload hash, TTL, idempotency, exact draft identity, and exact attachment identity are required.",
            "- No generic approval, send, runtime, Coupa, browser, credential, spreadsheet, OAuth, or calendar authority is granted.",
            "",
            "## Next Safe Move",
            f"- {payload['operator_next_safe_move']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_guardian_draft_approval_request_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    draft_packet_json: str | Path = DEFAULT_DRAFT_PACKET_PATH,
    send_gate_json: str | Path = DEFAULT_SEND_GATE_PATH,
    guardian_dna_json: str | Path = DEFAULT_GUARDIAN_DNA_PATH,
    start_approval_json: str | Path = DEFAULT_START_APPROVAL_PATH,
    generated_at: str | None = None,
) -> GuardianDraftApprovalRequestContractExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_draft_approval_request_contract(
        draft_packet_json=draft_packet_json,
        send_gate_json=send_gate_json,
        guardian_dna_json=guardian_dna_json,
        start_approval_json=start_approval_json,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_guardian_draft_approval_request_contract(payload), encoding="utf-8")
    return GuardianDraftApprovalRequestContractExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        approval_request_contract_id=payload["approval_request_contract_id"],
        current_availability_status=payload["current_availability_status"],
        approval_request_available_now=payload["approval_request_available_now"],
        approval_request_created=payload["approval_request_created"],
        approval_receipt_created=payload["approval_receipt_created"],
        execution_enabled=payload["execution_enabled"],
        guardian_message_sent=payload["guardian_message_sent"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Guardian draft approval request contract read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--draft-packet-json", default=str(DEFAULT_DRAFT_PACKET_PATH), help="Cassandra draft review packet JSON path.")
    parser.add_argument("--send-gate-json", default=str(DEFAULT_SEND_GATE_PATH), help="Capital Hilton send approval gate JSON path.")
    parser.add_argument("--guardian-dna-json", default=str(DEFAULT_GUARDIAN_DNA_PATH), help="Guardian DNA audit JSON path.")
    parser.add_argument("--start-approval-json", default=str(DEFAULT_START_APPROVAL_PATH), help="Capital Hilton start approval packet JSON path.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_guardian_draft_approval_request_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
        draft_packet_json=args.draft_packet_json,
        send_gate_json=args.send_gate_json,
        guardian_dna_json=args.guardian_dna_json,
        start_approval_json=args.start_approval_json,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            "Guardian draft approval request contract exported: "
            f"{result.json_path} and {result.operator_path} "
            f"(status={result.current_availability_status}; available={str(result.approval_request_available_now).lower()})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
