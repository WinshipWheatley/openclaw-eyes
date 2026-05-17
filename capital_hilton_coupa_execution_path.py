"""Capital Hilton Coupa execution path contract v0.

This read-model describes the future Hilton-only execution path for the
Capital Hilton invoice workflow. It models phases, gates, actors, protected
evidence, and two distinct Guardian approvals without enabling Coupa browser
automation, portal submit, email send, spreadsheet write, credential access, or
runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_coupa_execution_path_v0"
JSON_EXPORT_NAME = "capital_hilton_coupa_execution_path.json"
OPERATOR_EXPORT_NAME = "capital_hilton_coupa_execution_path_OPERATOR.md"
DEFAULT_TWO_INVOICE_WORKFLOW_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_two_invoice_workflow.json"

BASE_INVOICE_WORKFLOW_ID = "base_invoice_workflow"
HILTON_COUPA_OVERLAY_ID = "hilton_coupa_supplier_portal"
OVERLAY_SCOPE = "Capital Hilton / Hilton only"

NO_AUTHORITY_FLAGS = {
    "modeled_not_enabled": True,
    "execution_ready_now": False,
    "coupa_browser_automation_enabled": False,
    "coupa_submit_enabled": False,
    "email_send_enabled": False,
    "spreadsheet_write_enabled": False,
    "credential_broker_active": False,
    "protected_secret_pii_broker_active": False,
    "telegram_command_execution_enabled": False,
    "approval_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "raw_secret_or_pii_stored": False,
    "repo_b_executed": False,
}

EXECUTION_PHASE_IDS = (
    "requested_from_operator_channel",
    "governed_intent_routed",
    "guardian_start_approval_required",
    "start_approval_recorded",
    "facts_verified",
    "credential_access_required",
    "local_browser_execution_required",
    "coupa_invoice_creation_pending",
    "coupa_invoice_proof_capture_pending",
    "excel_companion_invoice_update_pending",
    "invoice_match_verification_required",
    "outward_email_draft_pending",
    "guardian_send_approval_required",
    "outward_email_send_blocked_until_gate",
    "expected_payment_tracking_pending",
    "money_ledger_payment_verification_pending",
)

REQUIRED_GATE_IDS = (
    "operator_intent_gate",
    "guardian_start_approval_gate",
    "invoice_fact_readiness_gate",
    "credential_pii_access_gate",
    "browser_automation_scope_gate",
    "coupa_submit_gate",
    "coupa_invoice_proof_capture_gate",
    "excel_write_generation_gate",
    "coupa_vs_excel_invoice_match_gate",
    "email_draft_gate",
    "guardian_send_approval_gate",
    "email_send_gate",
    "payment_verification_gate",
)


@dataclass(frozen=True)
class CoupaExecutionPathExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    end_to_end_hilton_workflow_modeled: bool
    base_invoice_workflow_remains_simple: bool
    hilton_overlay_scoped_only_to_hilton: bool
    guardian_start_approval_modeled: bool
    guardian_send_approval_modeled: bool
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


def _base_invoice_workflow() -> dict[str, Any]:
    return {
        "workflow_id": BASE_INVOICE_WORKFLOW_ID,
        "scope": "client_agnostic_default",
        "simple_default_preserved": True,
        "payment_generating_artifact_default": (
            "A normal client invoice may use a single operator invoice artifact as payment-generating "
            "unless a client-specific portal, PO, or payment rule requires an overlay."
        ),
        "assumes_coupa": False,
        "assumes_two_invoices": False,
        "assumes_two_guardian_approvals": False,
        "assumes_portal_login": False,
        "assumes_po_budget_tracking": False,
        "client_specific_complexity_policy": (
            "Portal, PO, two-invoice, two-approval, browser, credential, or payment-rule complexity must be added "
            "as client-specific overlays/adapters, not as default invoice architecture."
        ),
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }


def _hilton_overlay() -> dict[str, Any]:
    return {
        "overlay_id": HILTON_COUPA_OVERLAY_ID,
        "overlay_scope": OVERLAY_SCOPE,
        "applies_to_all_clients": False,
        "generalized_to_all_clients": False,
        "overlay_reason": (
            "Hilton requires supplier-portal invoice creation from a Hilton-created PO for payment."
        ),
        "payment_generating_invoice": "coupa_payment_invoice",
        "companion_invoice": "excel_companion_invoice",
        "two_guardian_approval_model": "hilton_only",
        "portal_submit_enabled": False,
        "browser_automation_enabled": False,
        "credential_insertion_enabled": False,
    }


def _overlay_adapter_policy() -> dict[str, Any]:
    return {
        "default_invoice_architecture": "simple_base_invoice_workflow",
        "client_specific_complexity_extension": "overlay_or_adapter_only",
        "hilton_complexity_becomes_default": False,
        "future_client_specific_overlays_should_reuse": [
            "operator_intent_gate",
            "guardian_start_approval_gate_when_action_capable",
            "protected_sensitive_data_requirements",
            "proof_artifacts",
            "client_specific_authority_boundary",
            "payment_verification_gate",
        ],
        "future_overlay_examples": [
            "client_portal_invoice_overlay",
            "client_purchase_order_overlay",
            "client_payment_processor_overlay",
            "client_companion_invoice_overlay",
        ],
        "migration_rule": (
            "Add or replace client-specific adapters only when evidence says that client requires the extra process; "
            "do not promote one client's process into the base invoice workflow."
        ),
    }


def _execution_phases() -> list[dict[str, Any]]:
    phase_details = {
        "requested_from_operator_channel": {
            "actor": "Cassandra",
            "status": "future_supported_intake_shape_modeled",
            "description": "Operator may request the workflow from Telegram/Cassandra in a future gated lane.",
            "enabled_now": False,
            "proof_required": "governed intent intake receipt",
        },
        "governed_intent_routed": {
            "actor": "workflow_router",
            "status": "modeled_not_executing",
            "description": "Route must select the Capital Hilton Hilton-Coupa overlay, not a generic invoice path.",
            "enabled_now": False,
            "proof_required": "route selection receipt bound to workflow id",
        },
        "guardian_start_approval_required": {
            "actor": "Guardian",
            "status": "required_before_workflow_start",
            "description": "Guardian must request approval to begin the Capital Hilton invoice workflow.",
            "enabled_now": False,
            "proof_required": "start_workflow_approval request receipt",
        },
        "start_approval_recorded": {
            "actor": "Guardian",
            "status": "not_recorded_for_execution",
            "description": "Start approval only authorizes beginning this workflow; it does not authorize final send.",
            "enabled_now": False,
            "proof_required": "start_workflow_approval decision receipt",
        },
        "facts_verified": {
            "actor": "workflow_router",
            "status": "pending_evidence_review",
            "description": "Current packet facts, PO posture, and manual confirmations must be checked after start approval.",
            "enabled_now": False,
            "proof_required": "fact readiness receipt",
        },
        "credential_access_required": {
            "actor": "protected_secret_pii_broker",
            "status": "future_blocked",
            "description": "Sensitive values may be inserted only by a protected local mechanism at the approved time.",
            "enabled_now": False,
            "proof_required": "redacted protected access receipt",
        },
        "local_browser_execution_required": {
            "actor": "local_mac_execution_agent",
            "status": "future_blocked",
            "description": "A local Mac/Codex Desktop actor may control Coupa only inside approved scope in a future lane.",
            "enabled_now": False,
            "proof_required": "browser scope approval receipt",
        },
        "coupa_invoice_creation_pending": {
            "actor": "local_mac_execution_agent",
            "status": "blocked",
            "description": "Create the payment-generating invoice from the Hilton PO in Coupa only after gates pass.",
            "enabled_now": False,
            "proof_required": "Coupa invoice creation receipt and protected proof reference",
        },
        "coupa_invoice_proof_capture_pending": {
            "actor": "local_mac_execution_agent",
            "status": "blocked",
            "description": "Capture Coupa invoice proof/download as protected evidence and link it through read-model evidence.",
            "enabled_now": False,
            "proof_required": "protected Coupa invoice proof reference",
        },
        "excel_companion_invoice_update_pending": {
            "actor": "local_mac_execution_agent",
            "status": "blocked",
            "description": "Update or generate the Excel companion invoice with Coupa-aligned facts and stakeholder context.",
            "enabled_now": False,
            "proof_required": "Excel companion artifact reference",
        },
        "invoice_match_verification_required": {
            "actor": "workflow_router",
            "status": "required_before_send_approval",
            "description": "Verify the Excel companion invoice reflects/matches the Coupa supplier-portal invoice.",
            "enabled_now": False,
            "proof_required": "Coupa-vs-Excel match proof",
        },
        "outward_email_draft_pending": {
            "actor": "Cassandra",
            "status": "draft_only_future",
            "description": "Cassandra may draft outward-facing email text after invoice artifacts are ready.",
            "enabled_now": False,
            "proof_required": "draft record bound to attachment artifact",
        },
        "guardian_send_approval_required": {
            "actor": "Guardian",
            "status": "blocked_until_artifact_proofs_exist",
            "description": "Guardian send approval is unavailable until Coupa proof and Excel match proof exist.",
            "enabled_now": False,
            "proof_required": "send_email_with_invoice_approval request receipt",
        },
        "outward_email_send_blocked_until_gate": {
            "actor": "Clara/Cassandra",
            "status": "blocked",
            "description": "Email send remains blocked until the specific draft plus attachment receives Guardian approval.",
            "enabled_now": False,
            "proof_required": "specific send approval decision receipt",
        },
        "expected_payment_tracking_pending": {
            "actor": "money_ledger",
            "status": "future_pending",
            "description": "Expected payment can be tracked after Coupa invoice proof exists.",
            "enabled_now": False,
            "proof_required": "payment expectation record",
        },
        "money_ledger_payment_verification_pending": {
            "actor": "money_ledger",
            "status": "required_for_paid_status",
            "description": "Paid status must only be set after money-ledger payment verification.",
            "enabled_now": False,
            "proof_required": "money ledger payment match receipt",
        },
    }
    phases: list[dict[str, Any]] = []
    for index, phase_id in enumerate(EXECUTION_PHASE_IDS, start=1):
        phases.append(
            {
                "phase_index": index,
                "phase_id": phase_id,
                **phase_details[phase_id],
            }
        )
    return phases


def _required_gates() -> list[dict[str, Any]]:
    gate_details = {
        "operator_intent_gate": ("Cassandra/governed intake must capture a bounded operator intent.", "governed intent receipt"),
        "guardian_start_approval_gate": ("Guardian must approve starting this Capital Hilton workflow.", "start approval receipt"),
        "invoice_fact_readiness_gate": ("Required facts, PO posture, and manual confirmations must be reviewed.", "fact readiness proof"),
        "credential_pii_access_gate": ("Protected values must be inserted only through a future local broker.", "redacted access receipt"),
        "browser_automation_scope_gate": ("Browser automation must be scoped to the approved Coupa task.", "browser scope approval"),
        "coupa_submit_gate": ("Coupa submit is separate from browser navigation and must be explicitly gated.", "Coupa submit receipt"),
        "coupa_invoice_proof_capture_gate": ("Coupa invoice proof/download must be captured as protected evidence.", "protected proof reference"),
        "excel_write_generation_gate": ("Excel companion generation/write must be explicitly gated.", "Excel artifact receipt"),
        "coupa_vs_excel_invoice_match_gate": ("Excel companion invoice must reflect/match the Coupa payment invoice.", "match proof"),
        "email_draft_gate": ("Cassandra may only produce a draft record, not send.", "draft receipt"),
        "guardian_send_approval_gate": ("Guardian must approve the specific draft and attachment.", "send approval receipt"),
        "email_send_gate": ("Email send remains blocked until specific Guardian send approval.", "future send receipt"),
        "payment_verification_gate": ("Paid status requires money-ledger verification.", "money ledger match"),
    }
    return [
        {
            "gate_id": gate_id,
            "gate_status": "not_satisfied",
            "required": True,
            "description": gate_details[gate_id][0],
            "required_proof": gate_details[gate_id][1],
            "authority_granted_now": False,
        }
        for gate_id in REQUIRED_GATE_IDS
    ]


def _guardian_approval_requests() -> list[dict[str, Any]]:
    return [
        {
            "approval_request_id": "start_workflow_approval",
            "approval_kind": "guardian_start_approval",
            "sent_by": "Guardian",
            "workflow_scope": OVERLAY_SCOPE,
            "client_specific_overlay": HILTON_COUPA_OVERLAY_ID,
            "purpose": "Authorize beginning the Capital Hilton invoice workflow after governed operator intent.",
            "authorizes_workflow_start": True,
            "authorizes_email_send": False,
            "authorizes_final_external_communication": False,
            "authorizes_coupa_submit": False,
            "creates_general_runtime_authority": False,
            "creates_general_send_authority": False,
            "required_before_phase": "facts_verified",
            "status_now": "modeled_not_requested",
        },
        {
            "approval_request_id": "send_email_with_invoice_approval",
            "approval_kind": "guardian_send_approval",
            "sent_by": "Guardian",
            "workflow_scope": OVERLAY_SCOPE,
            "client_specific_overlay": HILTON_COUPA_OVERLAY_ID,
            "purpose": "Authorize only Cassandra's specific drafted email and specified Excel invoice attachment.",
            "approval_scope": "specific_draft_email_and_attachment_only",
            "available_now": False,
            "cannot_be_requested_unless_coupa_invoice_proof_exists": True,
            "cannot_be_requested_unless_excel_companion_matches_coupa": True,
            "requires_coupa_invoice_proof_in_sqlite": True,
            "requires_excel_match_proof": True,
            "authorizes_email_send": True,
            "authorizes_general_send": False,
            "authorizes_coupa_submit": False,
            "creates_general_runtime_authority": False,
            "creates_general_send_authority": False,
            "status_now": "blocked_until_coupa_proof_and_excel_match",
        },
    ]


def _actors_and_roles() -> list[dict[str, Any]]:
    return [
        {
            "actor_id": "cassandra",
            "role": "telegram_intake_and_outward_comms_participant",
            "executor": False,
            "can_send_now": False,
            "summary": "Entry point for operator request and future email draft participant, not the portal/browser executor.",
        },
        {
            "actor_id": "guardian",
            "role": "approval_requester_and_safety_gatekeeper",
            "executor": False,
            "can_send_now": False,
            "summary": "Owns start and send approval requests without granting broad authority.",
        },
        {
            "actor_id": "workflow_router",
            "role": "selects_capital_hilton_workflow",
            "executor": False,
            "can_send_now": False,
            "summary": "Routes governed intent to the Hilton overlay only when evidence selects it.",
        },
        {
            "actor_id": "local_mac_execution_agent",
            "role": "future_browser_and_spreadsheet_operator",
            "executor": "future_blocked",
            "can_send_now": False,
            "summary": "Future local actor for Coupa and Excel steps after approvals; inactive in this lane.",
        },
        {
            "actor_id": "protected_secret_pii_broker",
            "role": "future_sensitive_insertion_mechanism",
            "executor": "future_blocked",
            "can_send_now": False,
            "summary": "Future local mechanism for scoped secret/PII insertion; no raw values stored in read-models.",
        },
        {
            "actor_id": "clara_cassandra",
            "role": "future_email_draft_and_send_participant",
            "executor": "future_blocked",
            "can_send_now": False,
            "summary": "May draft and later send only a specifically approved email with attachment.",
        },
        {
            "actor_id": "money_ledger",
            "role": "payment_verification_source",
            "executor": False,
            "can_send_now": False,
            "summary": "Paid status requires ledger verification, not invoice or email evidence alone.",
        },
        {
            "actor_id": "mission_control",
            "role": "operator_helm_read_model_surface",
            "executor": False,
            "can_send_now": False,
            "summary": "Displays posture and proof; does not execute backend commands.",
        },
    ]


def _protected_sensitive_data_requirements() -> dict[str, Any]:
    return {
        "protected_secret_pii_broker_modeled": True,
        "active_now": False,
        "raw_values_stored_in_repo_or_read_models": False,
        "requirements": [
            "credentials inserted only through a protected local mechanism",
            "raw secrets, remit PII, bank data, token material, and check images are not stored in repo/read-models",
            "sensitive value visibility is minimized",
            "access is scoped to the approved Capital Hilton task",
            "receipts show protected use occurred without revealing values",
            "failed or aborted runs must not leak sensitive values",
        ],
        "protected_value_classes": [
            {"value_class": "portal_credentials", "raw_value_stored": False, "future_use_requires_gate": "credential_pii_access_gate"},
            {"value_class": "remit_pii", "raw_value_stored": False, "future_use_requires_gate": "credential_pii_access_gate"},
            {"value_class": "bank_or_payment_details", "raw_value_stored": False, "future_use_requires_gate": "payment_verification_gate"},
            {"value_class": "token_material", "raw_value_stored": False, "future_use_requires_gate": "credential_pii_access_gate"},
            {"value_class": "check_or_deposit_images", "raw_value_stored": False, "future_use_requires_gate": "payment_verification_gate"},
        ],
    }


def _proof_artifacts() -> list[dict[str, Any]]:
    return [
        {"artifact_id": "start_approval_receipt", "artifact_status": "future_required", "protected": False},
        {"artifact_id": "coupa_invoice_proof_download_reference", "artifact_status": "future_required", "protected": True},
        {"artifact_id": "excel_invoice_artifact_reference", "artifact_status": "future_required", "protected": True},
        {"artifact_id": "coupa_vs_excel_match_proof", "artifact_status": "future_required", "protected": False},
        {"artifact_id": "cassandra_email_draft_record", "artifact_status": "future_required", "protected": False},
        {"artifact_id": "guardian_send_approval_receipt", "artifact_status": "future_required", "protected": False},
        {"artifact_id": "email_send_receipt_future_only", "artifact_status": "future_blocked", "protected": False},
        {"artifact_id": "payment_expectation_record", "artifact_status": "future_required", "protected": False},
        {"artifact_id": "money_ledger_payment_match", "artifact_status": "future_required_for_paid_status", "protected": True},
        {"artifact_id": "check_deposit_proof_protected_artifact", "artifact_status": "future_optional", "protected": True},
    ]


def _send_approval_preconditions() -> dict[str, Any]:
    return {
        "send_approval_available_now": False,
        "send_approval_blocked_until_coupa_proof_exists": True,
        "send_approval_blocked_until_excel_match_verified": True,
        "required_before_guardian_send_approval_request": [
            "Coupa supplier-portal invoice proof exists in SQLite/read-model evidence as protected artifact reference",
            "Excel companion invoice artifact exists",
            "Coupa-vs-Excel match proof says the companion invoice reflects/matches the Coupa payment invoice",
            "Cassandra email draft is bound to the exact Excel PDF attachment",
        ],
        "approval_scope_after_available": "specific_draft_email_and_attachment_only",
        "general_send_authority_created": False,
    }


def _readiness_summary() -> dict[str, Any]:
    return {
        "execution_ready_now": False,
        "modeled_not_enabled": True,
        "current_readiness": "contract_modeled_execution_not_authorized",
        "missing_gates": list(REQUIRED_GATE_IDS),
        "what_is_modeled": [
            "Hilton-only Coupa overlay execution phases",
            "two distinct Guardian approval requests",
            "protected sensitive-data broker requirements",
            "proof required before final send approval",
            "payment verification dependency on money ledger",
        ],
        "what_is_not_enabled": [
            "Coupa browser automation",
            "Coupa submit",
            "email send",
            "spreadsheet write",
            "credential insertion",
            "Telegram command execution",
            "runtime authority",
        ],
    }


def build_capital_hilton_coupa_execution_path(
    *,
    two_invoice_workflow_path: str | Path = DEFAULT_TWO_INVOICE_WORKFLOW_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    two_invoice_workflow = _read_json_if_present(two_invoice_workflow_path)
    phases = _execution_phases()
    gates = _required_gates()
    approvals = _guardian_approval_requests()
    status_summary = {
        "end_to_end_hilton_workflow_modeled": True,
        "base_invoice_workflow_remains_simple": True,
        "hilton_overlay_scoped_only_to_hilton": True,
        "cassandra_modeled_as_intake_not_executor": True,
        "guardian_start_approval_modeled": True,
        "guardian_send_approval_modeled": True,
        "send_approval_blocked_until_coupa_proof_exists": True,
        "send_approval_blocked_until_excel_match_verified": True,
        "protected_secret_pii_broker_modeled": True,
        "raw_secret_or_pii_stored": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "contract_kind": "client_specific_execution_path_contract",
        "workflow_domain": "finance_ap_invoice",
        "workflow_name": "capital_hilton_invoice_execution_path",
        "base_invoice_workflow": _base_invoice_workflow(),
        "client_specific_invoice_overlay": _hilton_overlay(),
        "overlay_adapter_policy": _overlay_adapter_policy(),
        "overlay_scope": OVERLAY_SCOPE,
        "overlay_reason": _hilton_overlay()["overlay_reason"],
        "two_invoice_workflow_context": {
            "source_path": _display_path(two_invoice_workflow_path),
            "source_present": bool(two_invoice_workflow),
            "schema_version": two_invoice_workflow.get("schema_version"),
            "coupa_payment_invoice_modeled": bool(
                (two_invoice_workflow.get("status_summary") or {}).get("coupa_payment_invoice_modeled")
            ),
            "excel_companion_invoice_modeled": bool(
                (two_invoice_workflow.get("status_summary") or {}).get("excel_companion_invoice_modeled")
            ),
            "po_budget_context_modeled": bool(
                (two_invoice_workflow.get("status_summary") or {}).get("po_budget_context_modeled")
            ),
            "protected_evidence_slots_modeled": bool(
                (two_invoice_workflow.get("status_summary") or {}).get("protected_evidence_slots_modeled")
            ),
        },
        "execution_phases": phases,
        "execution_phase_ids": [phase["phase_id"] for phase in phases],
        "required_gates": gates,
        "required_gate_ids": [gate["gate_id"] for gate in gates],
        "guardian_approval_requests": approvals,
        "guardian_approval_request_ids": [approval["approval_request_id"] for approval in approvals],
        "send_approval_preconditions": _send_approval_preconditions(),
        "actors_and_roles": _actors_and_roles(),
        "protected_sensitive_data_requirements": _protected_sensitive_data_requirements(),
        "proof_artifacts": _proof_artifacts(),
        "readiness_summary": _readiness_summary(),
        "status_summary": status_summary,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Coupa Start Approval Packet Spec v0",
    }


def format_capital_hilton_coupa_execution_path(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Coupa Execution Path Contract",
        "",
        "Status:",
        "- End-to-end Hilton workflow modeled: `true`.",
        "- Execution enabled now: `false`.",
        "- Coupa submit enabled: `false`.",
        "- Email send enabled: `false`.",
        "- Spreadsheet write enabled: `false`.",
        "- Runtime authority added: `false`.",
        "",
        "## Scope",
        f"- Base workflow: {payload['base_invoice_workflow']['payment_generating_artifact_default']}",
        f"- Hilton overlay: `{payload['client_specific_invoice_overlay']['overlay_id']}`.",
        f"- Overlay scope: {payload['overlay_scope']}.",
        "- This two-invoice/two-approval/Coupa portal process is not generalized to all clients.",
        "- Future client-specific complexity should be added as overlays/adapters using the same gates, proof, and protected-evidence substrate.",
        "",
        "## Phases",
    ]
    for phase in payload["execution_phases"]:
        lines.append(f"- `{phase['phase_id']}`: {phase['status']} ({phase['actor']})")
    lines.extend(
        [
            "",
            "## Required Gates",
        ]
    )
    for gate in payload["required_gates"]:
        lines.append(f"- `{gate['gate_id']}`: {gate['description']}")
    lines.extend(
        [
            "",
            "## Guardian Approvals",
        ]
    )
    for approval in payload["guardian_approval_requests"]:
        lines.append(
            f"- `{approval['approval_request_id']}`: {approval['purpose']} "
            f"General send authority: `{str(approval.get('creates_general_send_authority', False)).lower()}`."
        )
    lines.extend(
        [
            "",
            "## Send Approval Blockers",
            "- Coupa invoice proof must exist in SQLite/read-model evidence.",
            "- Excel companion invoice must be verified to reflect/match the Coupa invoice.",
            "- Approval can only cover one specific draft email and attachment.",
            "",
            "## Protected Data",
            "- Protected broker is modeled for a future lane, but inactive now.",
            "- Raw secrets, remit PII, bank data, token material, and check/deposit images are not stored in normal read-models.",
            "",
            "## Not Enabled",
            "- No Coupa automation, Coupa submit, email send, spreadsheet write, credential insertion, Telegram command execution, or runtime authority.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_coupa_execution_path(
    *,
    two_invoice_workflow_path: str | Path = DEFAULT_TWO_INVOICE_WORKFLOW_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CoupaExecutionPathExportResult:
    payload = build_capital_hilton_coupa_execution_path(
        two_invoice_workflow_path=two_invoice_workflow_path,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_coupa_execution_path(payload), encoding="utf-8")
    status = payload["status_summary"]
    return CoupaExecutionPathExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        end_to_end_hilton_workflow_modeled=status["end_to_end_hilton_workflow_modeled"],
        base_invoice_workflow_remains_simple=status["base_invoice_workflow_remains_simple"],
        hilton_overlay_scoped_only_to_hilton=status["hilton_overlay_scoped_only_to_hilton"],
        guardian_start_approval_modeled=status["guardian_start_approval_modeled"],
        guardian_send_approval_modeled=status["guardian_send_approval_modeled"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Coupa execution path contract.")
    parser.add_argument("--two-invoice-workflow-json", default=str(DEFAULT_TWO_INVOICE_WORKFLOW_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_coupa_execution_path(
        two_invoice_workflow_path=args.two_invoice_workflow_json,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_capital_hilton_coupa_execution_path(
            two_invoice_workflow_path=args.two_invoice_workflow_json,
        )
        print(format_capital_hilton_coupa_execution_path(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
