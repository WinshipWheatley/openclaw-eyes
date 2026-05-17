"""Capital Hilton final send approval gate v0.

This read-model models the Guardian final-send approval gate for the Hilton-only
Capital Hilton Coupa workflow. It defines a reusable final-send approval pattern
and a Capital Hilton instantiation, but does not send Guardian messages, create
email drafts, attach PDFs, submit Coupa, automate browsers, write spreadsheets,
access credentials/PII, or grant runtime/send/submit authority.
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
from guardian_hitl_sqlite_authority_contract import validate_canonical_approval_payload
from post_preflight_batch_gate import evaluate_post_preflight_lane
from capital_hilton_external_artifact_proof_capture import final_send_prerequisite_status_from_records


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_send_approval_gate_v0"
JSON_EXPORT_NAME = "capital_hilton_send_approval_gate.json"
OPERATOR_EXPORT_NAME = "capital_hilton_send_approval_gate_OPERATOR.md"
DEFAULT_EXECUTION_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_coupa_execution_path.json"
DEFAULT_START_APPROVAL_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_coupa_start_approval_packet.json"
DEFAULT_POWER_STAGE_PATH = DEFAULT_EXPORT_ROOT / "operator_sovereignty_power_stage_gate.json"
DEFAULT_PROOF_CAPTURE_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_external_artifact_proof_capture.json"

WORKFLOW_ID = "capital_hilton_coupa_supplier_portal_invoice"
APPROVAL_TYPE = "send_email_with_invoice_approval"
GENERIC_CONTRACT_ID = "generic_final_send_approval_gate_v0"
TTL_SECONDS = 6 * 60 * 60

AVAILABILITY_STATES = (
    "unavailable_missing_coupa_invoice_proof",
    "unavailable_missing_excel_companion_invoice",
    "unavailable_missing_excel_match_proof",
    "unavailable_missing_email_draft",
    "unavailable_missing_attachment_reference",
    "unavailable_unresolved_critical_blockers",
    "available_for_guardian_send_approval",
    "blocked_no_execution_authority",
)

PREREQUISITE_KEYS = (
    "coupa_invoice_proof_exists",
    "coupa_invoice_proof_references_expected_po_invoice_context",
    "excel_companion_invoice_artifact_exists",
    "excel_companion_invoice_verified_to_match_coupa",
    "cassandra_email_draft_exists",
    "attachment_reference_exists",
    "draft_identity_hash_reference_exists",
    "attachment_identity_hash_reference_exists",
    "no_unresolved_critical_blockers",
    "guardian_start_approval_recorded_or_required_upstream",
)

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "send_approval_packet_modeled": True,
    "generic_final_send_approval_contract_added": True,
    "send_approval_executable": False,
    "approval_request_persisted": False,
    "guardian_message_sent": False,
    "telegram_send_triggered": False,
    "gmail_or_email_send_triggered": False,
    "email_send_enabled": False,
    "general_email_authority_added": False,
    "coupa_browser_automation_enabled": False,
    "coupa_submit_enabled": False,
    "spreadsheet_write_enabled": False,
    "credential_or_pii_access_enabled": False,
    "raw_secret_or_pii_stored": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
}


@dataclass(frozen=True)
class SendApprovalGateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    send_approval_packet_modeled: bool
    generic_final_send_approval_contract_added: bool
    send_approval_executable: bool
    current_approval_availability_state: str
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


def _safe_file_probe(path: str) -> dict[str, Any]:
    target = ROOT / path
    return {
        "path": path,
        "present": target.exists(),
        "static_inspection_only": True,
        "imported_or_executed": False,
    }


def generic_final_send_approval_contract() -> dict[str, Any]:
    return {
        "contract_id": GENERIC_CONTRACT_ID,
        "contract_kind": "generic_final_send_approval_gate",
        "reusable_for_future_outward_email_workflows": True,
        "required_fields": [
            "approval_type",
            "workflow",
            "requested_by",
            "approving_actor",
            "target_action",
            "draft_identity",
            "attachment_identity",
            "prerequisite_evidence",
            "blocker_status",
            "approval_scope",
            "explicitly_blocked_authorities",
            "receipt_requirements",
            "availability_status",
            "failure_reasons",
        ],
        "specificity_rule": "approval binds exactly one draft identity and exactly one attachment identity",
        "authority_rule": "final-send approval never creates general send, runtime, browser, credential, spreadsheet, or portal authority",
        "evidence_rule": "approval cannot be requested until prerequisite evidence is present and blocker status is clear",
        "receipt_rule": "future send must record exact approved packet, draft, attachment, actor, timestamp, and result receipt",
        "stage_constraint": "Stage 2 packet/spec only now; Stage 4 controls are required before real send execution",
    }


def default_prerequisite_evidence() -> dict[str, bool]:
    return {
        "coupa_invoice_proof_exists": False,
        "coupa_invoice_proof_references_expected_po_invoice_context": False,
        "excel_companion_invoice_artifact_exists": False,
        "excel_companion_invoice_verified_to_match_coupa": False,
        "cassandra_email_draft_exists": False,
        "attachment_reference_exists": False,
        "draft_identity_hash_reference_exists": False,
        "attachment_identity_hash_reference_exists": False,
        "no_unresolved_critical_blockers": False,
        "guardian_start_approval_recorded_or_required_upstream": True,
    }


def _prerequisite_evidence_from_proof_capture(proof_capture: dict[str, Any]) -> dict[str, bool]:
    records = proof_capture.get("proof_records")
    if not isinstance(records, dict):
        return {}
    required = {
        "coupa_payment_invoice_proof",
        "excel_companion_invoice_artifact",
        "excel_coupa_match_proof",
    }
    if not required.issubset(records):
        return {}
    try:
        return final_send_prerequisite_status_from_records(records)
    except (KeyError, TypeError):
        return {}


def _availability_state(evidence: dict[str, bool]) -> tuple[str, list[str]]:
    failure_reasons: list[str] = []
    if not evidence.get("coupa_invoice_proof_exists"):
        failure_reasons.append("missing_coupa_invoice_proof")
    if not evidence.get("coupa_invoice_proof_references_expected_po_invoice_context"):
        failure_reasons.append("missing_coupa_expected_po_invoice_context_reference")
    if not evidence.get("excel_companion_invoice_artifact_exists"):
        failure_reasons.append("missing_excel_companion_invoice")
    if not evidence.get("excel_companion_invoice_verified_to_match_coupa"):
        failure_reasons.append("missing_excel_match_proof")
    if not evidence.get("cassandra_email_draft_exists"):
        failure_reasons.append("missing_email_draft")
    if not evidence.get("attachment_reference_exists"):
        failure_reasons.append("missing_attachment_reference")
    if not evidence.get("draft_identity_hash_reference_exists"):
        failure_reasons.append("missing_draft_identity_hash_reference")
    if not evidence.get("attachment_identity_hash_reference_exists"):
        failure_reasons.append("missing_attachment_identity_hash_reference")
    if not evidence.get("no_unresolved_critical_blockers"):
        failure_reasons.append("unresolved_critical_blockers")
    if not evidence.get("guardian_start_approval_recorded_or_required_upstream"):
        failure_reasons.append("missing_guardian_start_approval_upstream")

    if not evidence.get("coupa_invoice_proof_exists"):
        return "unavailable_missing_coupa_invoice_proof", failure_reasons
    if not evidence.get("excel_companion_invoice_artifact_exists"):
        return "unavailable_missing_excel_companion_invoice", failure_reasons
    if not evidence.get("excel_companion_invoice_verified_to_match_coupa"):
        return "unavailable_missing_excel_match_proof", failure_reasons
    if not evidence.get("cassandra_email_draft_exists"):
        return "unavailable_missing_email_draft", failure_reasons
    if not evidence.get("attachment_reference_exists"):
        return "unavailable_missing_attachment_reference", failure_reasons
    if not evidence.get("no_unresolved_critical_blockers"):
        return "unavailable_unresolved_critical_blockers", failure_reasons
    if all(evidence.get(key) for key in PREREQUISITE_KEYS):
        return "available_for_guardian_send_approval", []
    return "blocked_no_execution_authority", failure_reasons


def _prerequisite_records(evidence: dict[str, bool]) -> list[dict[str, Any]]:
    descriptions = {
        "coupa_invoice_proof_exists": "Coupa supplier-portal invoice proof exists in SQLite/read-model evidence.",
        "coupa_invoice_proof_references_expected_po_invoice_context": "Coupa proof references the expected PO and invoice context.",
        "excel_companion_invoice_artifact_exists": "Excel companion invoice artifact exists.",
        "excel_companion_invoice_verified_to_match_coupa": "Excel companion invoice is verified to reflect/match Coupa invoice.",
        "cassandra_email_draft_exists": "Cassandra outward email draft exists as a draft record.",
        "attachment_reference_exists": "Excel PDF attachment reference exists.",
        "draft_identity_hash_reference_exists": "Draft identity/hash/reference exists.",
        "attachment_identity_hash_reference_exists": "Attachment identity/hash/reference exists.",
        "no_unresolved_critical_blockers": "No unresolved critical blockers remain.",
        "guardian_start_approval_recorded_or_required_upstream": "Guardian start approval is recorded or modeled as required upstream.",
    }
    protected = {
        "coupa_invoice_proof_exists",
        "attachment_reference_exists",
        "attachment_identity_hash_reference_exists",
    }
    return [
        {
            "evidence_key": key,
            "required_before_send_approval_request": True,
            "present_now": bool(evidence.get(key)),
            "protected_or_redacted_reference_required": key in protected,
            "raw_secret_or_pii_required": False,
            "description": descriptions[key],
        }
        for key in PREREQUISITE_KEYS
    ]


def _draft_identity(evidence: dict[str, bool]) -> dict[str, Any]:
    return {
        "draft_required": True,
        "draft_present_now": bool(evidence.get("cassandra_email_draft_exists")),
        "identity_reference_present_now": bool(evidence.get("draft_identity_hash_reference_exists")),
        "identity_status": "future_placeholder_missing",
        "draft_source": "Cassandra/outward email draft",
        "raw_email_body_stored": False,
        "draft_created_in_this_lane": False,
        "draft_hash_or_reference": "future_required_before_available",
    }


def _attachment_identity(evidence: dict[str, bool]) -> dict[str, Any]:
    return {
        "attachment_required": True,
        "attachment_present_now": bool(evidence.get("attachment_reference_exists")),
        "identity_reference_present_now": bool(evidence.get("attachment_identity_hash_reference_exists")),
        "identity_status": "future_placeholder_missing",
        "attachment_type": "excel_companion_invoice_pdf",
        "raw_attachment_stored": False,
        "attachment_generated_in_this_lane": False,
        "attachment_hash_or_reference": "future_required_before_available",
    }


def _approval_scope() -> dict[str, Any]:
    return {
        "what_send_approval_authorizes": [
            "send the specific Cassandra-drafted email",
            "include the specific Excel-generated PDF invoice attachment",
            "record a send receipt afterward in a future execution lane",
        ],
        "what_send_approval_does_not_authorize": [
            "Coupa submit",
            "browser automation",
            "credential/PII access",
            "spreadsheet writes",
            "new invoice creation",
            "payment status change",
            "general email authority",
            "general runtime authority",
            "future sends",
        ],
        "specific_to_one_draft_and_one_attachment": True,
        "creates_general_email_authority": False,
        "creates_general_runtime_authority": False,
        "send_execution_enabled_now": False,
    }


def _receipt_requirements() -> list[dict[str, Any]]:
    return [
        {
            "receipt_id": "guardian_send_approval_request_receipt",
            "required_before_execution": True,
            "future_only": True,
            "raw_content_stored": False,
        },
        {
            "receipt_id": "guardian_send_approval_decision_receipt",
            "required_before_execution": True,
            "future_only": True,
            "raw_content_stored": False,
        },
        {
            "receipt_id": "specific_draft_attachment_binding_receipt",
            "required_before_execution": True,
            "future_only": True,
            "raw_content_stored": False,
        },
        {
            "receipt_id": "email_send_result_receipt",
            "required_before_paid_tracking": True,
            "future_only": True,
            "raw_content_stored": False,
        },
    ]


def _future_implementation_checklist() -> list[dict[str, Any]]:
    items = (
        ("protected_coupa_invoice_proof", "protected evidence for Coupa invoice proof"),
        ("excel_companion_artifact", "Excel companion invoice artifact and protected/reference path"),
        ("excel_match_proof", "Coupa-vs-Excel match proof"),
        ("cassandra_draft_record", "Cassandra draft record with stable identity"),
        ("attachment_reference", "Excel PDF attachment reference with stable identity"),
        ("guardian_send_approval_delivery", "Guardian send approval request delivery path"),
        ("operator_approval_receipt", "explicit operator approval receipt"),
        ("stage_4_send_controls", "Operator Sovereignty Stage 4 controls before real send authority"),
    )
    return [
        {
            "check_id": check_id,
            "description": description,
            "satisfied_now": False,
            "required_before_executable_authority": True,
        }
        for check_id, description in items
    ]


def _existing_email_approval_machinery_discovery() -> dict[str, Any]:
    surfaces = [
        {
            **_safe_file_probe("templates/agent/guardian_approval_request_packet_template.json"),
            "surface_role": "Guardian approval request packet template",
            "reuse_posture": "candidate_packet_shape_for_send_approval",
        },
        {
            **_safe_file_probe("templates/agent/cassandra_outreach_draft_packet_template.json"),
            "surface_role": "Cassandra outreach draft packet template",
            "reuse_posture": "candidate_draft_shape_for_specific_email",
        },
        {
            **_safe_file_probe("cassandra_outreach.py"),
            "surface_role": "Cassandra draft/outreach machinery",
            "reuse_posture": "reuse_or_detangle_do_not_rebuild",
        },
        {
            **_safe_file_probe("business_ops_ledger.py"),
            "surface_role": "draft receipt helper",
            "reuse_posture": "candidate_receipt_shape_for_draft_identity",
        },
        {
            **_safe_file_probe("google_access_policy.py"),
            "surface_role": "Gmail policy boundary",
            "reuse_posture": "preserve_draft_vs_send_policy_boundary",
        },
        {
            **_safe_file_probe("chief_guardian_sender.py"),
            "surface_role": "Guardian transport",
            "reuse_posture": "future_transport_only_after_packet_and_receipts_exist",
        },
        {
            **_safe_file_probe("chief_guardian_listener.py"),
            "surface_role": "Guardian response listener",
            "reuse_posture": "future_decision_transport_only_after_receipt_binding_is_proven",
        },
    ]
    return {
        "existing_cassandra_guardian_email_approval_inspected": True,
        "inspection_method": "safe_static_repo_a_file_and_pattern_inspection_only",
        "machinery_found": True,
        "existing_machinery_rebuilt_in_this_lane": False,
        "existing_machinery_activated_in_this_lane": False,
        "later_send_approval_should_reuse_or_detangle_existing_pattern": True,
        "reuse_detangle_recommendation": (
            "Reuse existing Cassandra draft and Guardian approval surfaces where safe; detangle any live "
            "Gmail/Telegram/runtime/autonomous-loop paths before making final-send approval executable."
        ),
        "surfaces": surfaces,
    }


def _canonical_approval_payload(
    packet_id: str,
    packet_hash: str,
    generated_at: str,
    *,
    draft_identity: dict[str, Any],
    attachment_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "approval_id": packet_id,
        "action_type": "capital_hilton_send_email_with_invoice",
        "actor": "guardian",
        "target": WORKFLOW_ID,
        "payload_hash": packet_hash,
        "payload_schema_version": SCHEMA_VERSION,
        "source_intent_ref": "modeled:cassandra_outward_email_draft:capital_hilton_final_send",
        "idempotency_key": _row_id("cap_hilton_send_idem", WORKFLOW_ID, packet_hash),
        "requested_at": generated_at,
        "expires_at": _expires_at(generated_at),
        "ttl_seconds": TTL_SECONDS,
        "authority_scope": "specific_email_draft_and_attachment_only_no_general_send",
        "risk_tier": "tier_2_external_communication_future_blocked",
        "action_class": "email_send",
        "explicit_authorized_packet_ref": (
            f"{draft_identity['draft_hash_or_reference']}::"
            f"{attachment_identity['attachment_hash_or_reference']}"
        ),
        "payload_mutable_after_approval": False,
    }


def _packet_basis(
    *,
    availability_state: str,
    evidence_records: list[dict[str, Any]],
    draft_identity: dict[str, Any],
    attachment_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "approval_type": APPROVAL_TYPE,
        "workflow": WORKFLOW_ID,
        "target_action": "send_specific_cassandra_email_with_specific_excel_invoice_pdf",
        "availability_state": availability_state,
        "prerequisite_evidence": evidence_records,
        "draft_identity": draft_identity,
        "attachment_identity": attachment_identity,
        "approval_scope": _approval_scope(),
    }


def _post_preflight_gate_result() -> dict[str, Any]:
    return evaluate_post_preflight_lane(
        lane_name="Capital Hilton Send Approval Gate v0",
        lane_summary="Model the final Guardian send approval requirements without enabling email send.",
        named_operator_workflow="Capital Hilton final invoice email approval",
        shared_bottleneck="evidence_bound_final_send_approval_gate",
        steel_thread_contract_link="capital_hilton_coupa_execution_path_v0",
        reusable_substrate_improvement="Generic final-send approval gate contract for outward email workflows.",
        workflow_proof_output="Capital Hilton final-send approval gate read-model.",
        detangling_scope={
            "serves_lane_directly": True,
            "opportunistic_only": True,
            "physical_module_extraction_requested": False,
            "client_repo_generation_requested": False,
            "detangling_required_before_workflow_proof": False,
            "notes": "Record reuse/detangle requirement for Cassandra/Guardian email machinery without activating it.",
        },
        module_split_disposition={
            "disposition": "record_future_work",
            "recorded_future_work": True,
            "future_work_id": "cassandra_guardian_email_send_detangle",
            "reason": "Existing draft/approval machinery exists but must be detangled before executable send approval.",
        },
        authority_change_requested={
            "requested": False,
            "authority_types": [],
            "reason": "Stage 2 packet/spec only; no execution authority requested.",
        },
        expected_artifacts=[
            {"artifact_kind": "read_model", "path_or_contract": f"generated/read_models/{JSON_EXPORT_NAME}"},
            {
                "artifact_kind": "operator_packet",
                "path_or_contract": f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            },
            {"artifact_kind": "test_proof", "path_or_contract": "tests/test_capital_hilton_send_approval_gate.py"},
        ],
        validation_required=("focused send approval gate tests", "JSON validation", "no send/no submit flags"),
        synthetic_example=False,
    )


def build_capital_hilton_send_approval_gate(
    *,
    execution_path_json: str | Path = DEFAULT_EXECUTION_PATH,
    start_approval_json: str | Path = DEFAULT_START_APPROVAL_PATH,
    power_stage_json: str | Path = DEFAULT_POWER_STAGE_PATH,
    proof_capture_json: str | Path = DEFAULT_PROOF_CAPTURE_PATH,
    prerequisite_evidence: dict[str, bool] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    execution_path = _read_json_if_present(execution_path_json)
    start_approval = _read_json_if_present(start_approval_json)
    power_stage = _read_json_if_present(power_stage_json)
    proof_capture = _read_json_if_present(proof_capture_json)
    evidence = default_prerequisite_evidence()
    if prerequisite_evidence:
        evidence.update({key: bool(value) for key, value in prerequisite_evidence.items()})
    else:
        evidence.update(_prerequisite_evidence_from_proof_capture(proof_capture))
    availability_state, failure_reasons = _availability_state(evidence)
    evidence_records = _prerequisite_records(evidence)
    draft_identity = _draft_identity(evidence)
    attachment_identity = _attachment_identity(evidence)
    basis = _packet_basis(
        availability_state=availability_state,
        evidence_records=evidence_records,
        draft_identity=draft_identity,
        attachment_identity=attachment_identity,
    )
    packet_hash = hashlib.sha256(stable_json(basis).encode("utf-8")).hexdigest()
    packet_id = _row_id("cap_hilton_send_approval", SCHEMA_VERSION, packet_hash)
    canonical_payload = _canonical_approval_payload(
        packet_id,
        packet_hash,
        ts,
        draft_identity=draft_identity,
        attachment_identity=attachment_identity,
    )
    canonical_validation = validate_canonical_approval_payload(canonical_payload)
    approval_scope = _approval_scope()
    discovery = _existing_email_approval_machinery_discovery()
    status_summary = {
        "send_approval_packet_modeled": True,
        "generic_final_send_approval_contract_added": True,
        "send_approval_executable": False,
        "send_approval_blocked_until_coupa_proof_exists": True,
        "send_approval_blocked_until_excel_match_verified": True,
        "send_approval_specific_to_draft_and_attachment": True,
        "current_approval_availability_state": availability_state,
        "general_email_authority_added": False,
        "existing_cassandra_guardian_email_approval_inspected": True,
        "rebuild_existing_email_approval_machinery": False,
        "guardian_message_sent": False,
        "email_send_enabled": False,
        "coupa_browser_automation_enabled": False,
        "coupa_submit_enabled": False,
        "spreadsheet_write_enabled": False,
        "credential_or_pii_access_enabled": False,
        "raw_secret_or_pii_stored": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "packet_kind": "guardian_final_send_approval_gate_spec",
        "packet_status": "review_only_spec_not_dispatched",
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "generic_final_send_approval_contract": generic_final_send_approval_contract(),
        "generic_final_send_approval_contract_added": True,
        "approval_type": APPROVAL_TYPE,
        "workflow": WORKFLOW_ID,
        "workflow_scope": execution_path.get("overlay_scope") or "Capital Hilton / Hilton only",
        "client_specific_overlay": "hilton_coupa_supplier_portal",
        "requested_by": {
            "source": "Cassandra/outward email draft",
            "modeled_source_only": True,
            "draft_created_in_this_lane": False,
            "source_intent_ref": canonical_payload["source_intent_ref"],
        },
        "approving_actor": {
            "actor": "Guardian/operator",
            "guardian_message_sent": False,
            "approval_request_persisted": False,
            "decision_recorded": False,
        },
        "target_action": {
            "action_id": "send_specific_cassandra_email_with_specific_excel_invoice_pdf",
            "action_summary": "send one specific drafted email with one specific Excel companion invoice PDF attachment",
            "specific_to_draft_and_attachment": True,
            "general_email_authority": False,
            "enabled_now": False,
        },
        "execution_path_context": {
            "source_path": _display_path(execution_path_json),
            "source_present": bool(execution_path),
            "schema_version": execution_path.get("schema_version"),
            "send_approval_blocked_until_coupa_proof_exists": bool(
                (execution_path.get("status_summary") or {}).get(
                    "send_approval_blocked_until_coupa_proof_exists"
                )
            ),
            "send_approval_blocked_until_excel_match_verified": bool(
                (execution_path.get("status_summary") or {}).get(
                    "send_approval_blocked_until_excel_match_verified"
                )
            ),
        },
        "external_artifact_proof_capture_context": {
            "source_path": _display_path(proof_capture_json),
            "source_present": bool(proof_capture),
            "schema_version": proof_capture.get("schema_version"),
            "coupa_invoice_proof_status": (proof_capture.get("status_summary") or {}).get("coupa_invoice_proof_status", "pending_not_recorded"),
            "excel_companion_artifact_status": (proof_capture.get("status_summary") or {}).get("excel_companion_artifact_status", "pending_not_recorded"),
            "excel_coupa_match_proof_status": (proof_capture.get("status_summary") or {}).get("excel_coupa_match_proof_status", "pending_not_recorded"),
            "raw_sensitive_artifact_stored_in_read_model": bool((proof_capture.get("status_summary") or {}).get("raw_sensitive_artifact_stored_in_read_model", False)),
            "evidence_only": bool((proof_capture.get("authority_boundary") or {}).get("evidence_only", False)),
        },
        "upstream_start_approval_context": {
            "source_path": _display_path(start_approval_json),
            "source_present": bool(start_approval),
            "schema_version": start_approval.get("schema_version"),
            "start_approval_separate_from_send_approval": True,
            "start_approval_authorizes_send": False,
        },
        "operator_sovereignty_context": {
            "source_path": _display_path(power_stage_json),
            "source_present": bool(power_stage),
            "current_power_stage": (power_stage.get("current_power_stage") or {}).get(
                "current_power_stage_id",
                "stage_1_visibility_read_model_review_packet",
            ),
            "stage_2_spec_only": True,
            "stage_4_required_before_real_send": True,
        },
        "draft_identity": draft_identity,
        "attachment_identity": attachment_identity,
        "prerequisite_evidence": evidence_records,
        "prerequisite_evidence_status": evidence,
        "blocker_status": {
            "availability_state": availability_state,
            "failure_reasons": failure_reasons,
            "no_unresolved_critical_blockers": bool(evidence.get("no_unresolved_critical_blockers")),
            "approval_request_available_now": availability_state == "available_for_guardian_send_approval",
            "send_execution_available_now": False,
        },
        "approval_availability_states": list(AVAILABILITY_STATES),
        "current_approval_availability_state": availability_state,
        "approval_scope": approval_scope,
        "what_send_approval_authorizes": approval_scope["what_send_approval_authorizes"],
        "explicitly_blocked_authorities": approval_scope["what_send_approval_does_not_authorize"],
        "receipt_requirements": _receipt_requirements(),
        "guardian_start_approval_relationship": {
            "start_approval_distinct_from_send_approval": True,
            "start_approval_does_not_authorize_send": True,
            "start_approval_required_upstream": True,
        },
        "canonical_approval_payload_candidate": canonical_payload,
        "canonical_approval_payload_validation": canonical_validation,
        "existing_email_approval_machinery_discovery": discovery,
        "reuse_detangle_recommendation": discovery["reuse_detangle_recommendation"],
        "future_implementation_checklist": _future_implementation_checklist(),
        "post_preflight_batch_gate_result": _post_preflight_gate_result(),
        "authority_boundary": {
            "packet_spec_only": True,
            "approval_request_available_now": availability_state == "available_for_guardian_send_approval",
            "send_approval_executable": False,
            "send_execution_requires_future_stage_4_controls": True,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        },
        "status_summary": status_summary,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Send Approval Operator Surface v0",
    }


def format_capital_hilton_send_approval_gate(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Send Approval Gate",
        "",
        "Status:",
        "- Send approval packet modeled: `true`.",
        f"- Current availability: `{payload['current_approval_availability_state']}`.",
        "- Packet executable now: `false`.",
        "- Guardian message sent: `false`.",
        "- Email/Coupa/browser/spreadsheet/credential/runtime authority added: `false`.",
        "",
        "## Approval Target",
        f"- Approval type: `{payload['approval_type']}`.",
        f"- Workflow: `{payload['workflow']}`.",
        f"- Target action: {payload['target_action']['action_summary']}.",
        "- Scope: exact draft plus exact attachment only; no general email authority.",
        "",
        "## Required Before Send Approval Can Be Requested",
    ]
    for item in payload["prerequisite_evidence"]:
        status = "present" if item["present_now"] else "missing"
        lines.append(f"- `{item['evidence_key']}`: {status} - {item['description']}")
    lines.extend(["", "## If Later Approved, It Would Authorize"])
    lines.extend(f"- {item}" for item in payload["what_send_approval_authorizes"])
    lines.extend(["", "## Still Blocked"])
    lines.extend(f"- {item}" for item in payload["explicitly_blocked_authorities"])
    lines.extend(
        [
            "",
            "## Reuse / Detangle",
            "- Existing Cassandra draft + Guardian approval machinery was inspected statically.",
            "- Later implementation should reuse or detangle existing machinery rather than rebuild it.",
            "- This lane did not activate draft, Guardian transport, or send paths.",
            "",
            "## Future Checklist",
        ]
    )
    for item in payload["future_implementation_checklist"]:
        lines.append(f"- `{item['check_id']}`: {item['description']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "- No Guardian/Telegram/Gmail/email message was sent.",
            "- No email draft, PDF attachment, Coupa submit, browser automation, spreadsheet write, credential/PII access, or runtime authority was added.",
            "- Real send remains blocked until future Stage 4 controls and exact operator approval receipts exist.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_send_approval_gate(
    *,
    execution_path_json: str | Path = DEFAULT_EXECUTION_PATH,
    start_approval_json: str | Path = DEFAULT_START_APPROVAL_PATH,
    power_stage_json: str | Path = DEFAULT_POWER_STAGE_PATH,
    proof_capture_json: str | Path = DEFAULT_PROOF_CAPTURE_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SendApprovalGateExportResult:
    payload = build_capital_hilton_send_approval_gate(
        execution_path_json=execution_path_json,
        start_approval_json=start_approval_json,
        power_stage_json=power_stage_json,
        proof_capture_json=proof_capture_json,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_send_approval_gate(payload), encoding="utf-8")
    status = payload["status_summary"]
    return SendApprovalGateExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        send_approval_packet_modeled=status["send_approval_packet_modeled"],
        generic_final_send_approval_contract_added=status["generic_final_send_approval_contract_added"],
        send_approval_executable=status["send_approval_executable"],
        current_approval_availability_state=status["current_approval_availability_state"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton final send approval gate.")
    parser.add_argument("--execution-path-json", default=str(DEFAULT_EXECUTION_PATH))
    parser.add_argument("--start-approval-json", default=str(DEFAULT_START_APPROVAL_PATH))
    parser.add_argument("--power-stage-json", default=str(DEFAULT_POWER_STAGE_PATH))
    parser.add_argument("--proof-capture-json", default=str(DEFAULT_PROOF_CAPTURE_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_send_approval_gate(
        execution_path_json=args.execution_path_json,
        start_approval_json=args.start_approval_json,
        power_stage_json=args.power_stage_json,
        proof_capture_json=args.proof_capture_json,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "APPROVAL_TYPE",
    "AVAILABILITY_STATES",
    "DEFAULT_EXECUTION_PATH",
    "DEFAULT_PROOF_CAPTURE_PATH",
    "GENERIC_CONTRACT_ID",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PREREQUISITE_KEYS",
    "SCHEMA_VERSION",
    "WORKFLOW_ID",
    "build_capital_hilton_send_approval_gate",
    "default_prerequisite_evidence",
    "export_capital_hilton_send_approval_gate",
    "format_capital_hilton_send_approval_gate",
    "generic_final_send_approval_contract",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
