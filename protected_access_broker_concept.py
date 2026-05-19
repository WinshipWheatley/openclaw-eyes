"""Protected access broker concept delta v0.

This read-model defines what protected access means before OpenClaw crosses
into credential, OAuth, browser, account, or live execution authority. It is
concept/readiness metadata only: it does not access credentials, call external
accounts, automate browsers, send messages, create approvals, inspect Repo B,
or grant runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "protected_access_broker_concept_v0"
JSON_EXPORT_NAME = "protected_access_broker_concept.json"
OPERATOR_EXPORT_NAME = "protected_access_broker_concept_OPERATOR.md"

CLASSIFICATIONS = (
    "METADATA_ONLY_ALLOWED",
    "PROTECTED_REFERENCE_ALLOWED",
    "NORMAL_READ_MODEL_FORBIDDEN",
    "REQUIRES_GUARDIAN_GATE",
    "REQUIRES_SECURITY_THRESHOLD",
    "LIVE_ACCESS_BLOCKED",
    "UNSAFE_OR_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "concept_readiness_only": True,
    "credentials_enabled": False,
    "credential_or_pii_access_added": False,
    "oauth_access_enabled": False,
    "tokens_or_secrets_accessed": False,
    "raw_secret_or_pii_stored": False,
    "raw_private_document_stored": False,
    "browser_automation_added": False,
    "browser_or_coupa_authority_added": False,
    "gmail_calendar_coupa_accessed": False,
    "email_send_triggered": False,
    "telegram_send_triggered": False,
    "send_or_submit_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "approval_authority_added": False,
    "guardian_live_message_sent": False,
    "tool_execution_authority_added": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "client_deployment_authority_added": False,
    "agents_receive_direct_credentials": False,
}

SAFE_METADATA_FIELDS = (
    "protected_artifact_reference",
    "protected_reference_id",
    "protected_reference_path_token",
    "artifact_identity_or_hash",
    "proof_type",
    "proof_status",
    "source_system_label",
    "captured_at",
    "date_captured",
    "invoice_number",
    "portal_invoice_reference",
    "po_reference",
    "amount",
    "service_dates",
    "operator_confirmation_status",
    "match_status",
    "mismatch_reasons",
    "redaction_status",
    "protection_status",
)

NORMAL_READ_MODEL_FORBIDDEN_VALUES = (
    "raw passwords",
    "raw OAuth client secrets or refresh tokens",
    "raw bot/API tokens",
    "portal usernames paired with secrets",
    "bank account or routing details",
    "remit details",
    "home address",
    "check images or deposit images",
    "raw PDF bodies",
    "raw Excel workbook bodies",
    "raw Gmail/calendar bodies",
    "private legal/client documents",
    "client/company credentials",
)

SOURCE_READ_MODEL_PATHS = (
    ("repo_b_delta", DEFAULT_EXPORT_ROOT / "repo_b_remaining_capability_delta_map.json", "Repo B delta read-model reference from Repo A only"),
    ("power_stage_gate", DEFAULT_EXPORT_ROOT / "operator_sovereignty_power_stage_gate.json", "stage boundary and security-threshold evidence"),
    ("guardian_dna", DEFAULT_EXPORT_ROOT / "guardian_responsibility_dna_audit.json", "Guardian role and request/receipt/execution separation"),
    ("guardian_draft_approval_request", DEFAULT_EXPORT_ROOT / "guardian_draft_approval_request_contract.json", "final-send approval request contract boundary"),
    ("capital_hilton_proof_capture", DEFAULT_EXPORT_ROOT / "capital_hilton_external_artifact_proof_capture.json", "Capital Hilton metadata/protected-reference proof capture"),
    ("capital_hilton_operator_proof_input", DEFAULT_EXPORT_ROOT / "capital_hilton_operator_proof_input_packet.json", "safe proof input template"),
    ("capital_hilton_execution_path", DEFAULT_EXPORT_ROOT / "capital_hilton_coupa_execution_path.json", "Hilton-only execution path model"),
    ("capital_hilton_send_approval_gate", DEFAULT_EXPORT_ROOT / "capital_hilton_send_approval_gate.json", "final send gate prerequisites"),
    ("cassandra_email_calendar_reconciliation", DEFAULT_EXPORT_ROOT / "cassandra_email_calendar_capability_reconciliation.json", "email/calendar live authority reconciliation"),
    ("chief_status", DEFAULT_EXPORT_ROOT / "chief_status_rail.json", "Chief status precondition"),
    ("build_now_vs_hold", DEFAULT_EXPORT_ROOT / "build_now_vs_hold_queue_posture.json", "build-now-vs-hold precondition"),
    ("tool_inventory", DEFAULT_EXPORT_ROOT / "tool_inventory.json", "tool metadata if present"),
    ("tool_intake", DEFAULT_EXPORT_ROOT / "tool_intake.json", "tool intake metadata if present"),
)


@dataclass(frozen=True)
class ProtectedAccessBrokerConceptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    preconditions_satisfied: bool
    surface_count: int
    live_access_blocked: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_record(key: str, path: Path, role: str, payload: dict[str, Any], *, repo_root: str | Path) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    return {
        "key": key,
        "path": path.as_posix(),
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": role,
        "source_mode": "repo_a_generated_read_model_or_repo_a_contract_only",
        "repo_b_filesystem_inspected": False,
        "raw_private_content_read": False,
    }


def _precondition_status(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    chief = sources.get("chief_status", {})
    build_now = sources.get("build_now_vs_hold", {})
    chief_ok = (
        chief.get("schema_version") == "chief_status_rail_v0"
        and chief.get("rail_status") == "completed_visibility_planning_only"
    )
    build_now_ok = (
        build_now.get("schema_version") == "build_now_vs_hold_queue_posture_v0"
        and build_now.get("posture_scope") == "visibility_routing_work_packet_posture_only"
        and build_now.get("chief_status_precondition", {}).get("satisfied") is True
    )
    return {
        "chief_status_rail_completion_v0_satisfied": chief_ok,
        "build_now_vs_hold_queue_posture_v0_satisfied": build_now_ok,
        "all_preconditions_satisfied": chief_ok and build_now_ok,
        "chief_status_schema_version": chief.get("schema_version"),
        "chief_status_rail_status": chief.get("rail_status"),
        "build_now_schema_version": build_now.get("schema_version"),
        "build_now_posture_scope": build_now.get("posture_scope"),
    }


def _surface(
    *,
    surface_id: str,
    display_name: str,
    primary_classification: str,
    policy_classifications: tuple[str, ...],
    examples: tuple[str, ...],
    safe_metadata: tuple[str, ...],
    forbidden_normal_values: tuple[str, ...],
    guardian_gate_required: bool,
    security_threshold_required: bool,
    current_allowed_stage: str,
    live_access_status: str,
    current_repo_a_evidence: tuple[str, ...],
    next_safe_move: str,
) -> dict[str, Any]:
    if primary_classification not in CLASSIFICATIONS:
        raise ValueError(f"unknown protected access classification: {primary_classification}")
    invalid = [item for item in policy_classifications if item not in CLASSIFICATIONS]
    if invalid:
        raise ValueError(f"unknown protected access policy classifications: {invalid}")
    return {
        "surface_id": surface_id,
        "display_name": display_name,
        "examples": list(examples),
        "primary_classification": primary_classification,
        "policy_classifications": list(policy_classifications),
        "current_allowed_stage": current_allowed_stage,
        "normal_read_model_policy": "metadata_or_protected_reference_only"
        if primary_classification in {"METADATA_ONLY_ALLOWED", "PROTECTED_REFERENCE_ALLOWED"}
        else "normal_read_model_forbidden_for_raw_sensitive_values",
        "safe_metadata_or_reference_allowed": list(safe_metadata),
        "forbidden_raw_values": list(forbidden_normal_values),
        "guardian_gate_required_for_live_access": guardian_gate_required,
        "security_threshold_required_for_live_access": security_threshold_required,
        "live_access_status": live_access_status,
        "agent_direct_access_allowed": False,
        "future_proof_required": [
            "exact task scope",
            "operator/Guardian gate where applicable",
            "protected reference or redacted receipt",
            "no raw normal-read-model leakage test",
            "scoped access receipt before any future live access",
        ],
        "current_repo_a_evidence": list(current_repo_a_evidence),
        "unknown_or_ambiguous_access_fails_closed": True,
        "next_safe_move": next_safe_move,
    }


def protected_access_surfaces() -> tuple[dict[str, Any], ...]:
    return (
        _surface(
            surface_id="capital_hilton_coupa_payment_invoice_proof",
            display_name="Capital Hilton Coupa supplier-portal payment invoice proof",
            primary_classification="PROTECTED_REFERENCE_ALLOWED",
            policy_classifications=(
                "METADATA_ONLY_ALLOWED",
                "PROTECTED_REFERENCE_ALLOWED",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_SECURITY_THRESHOLD",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("protected Coupa invoice PDF/download reference", "portal invoice reference", "PO reference"),
            safe_metadata=(
                "protected_artifact_reference",
                "artifact_identity_or_hash",
                "portal_invoice_reference",
                "po_reference",
                "amount",
                "date_captured",
                "protection_status",
            ),
            forbidden_normal_values=(
                "raw PDF body",
                "portal username/password/token",
                "bank/remit details",
                "home address",
            ),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="stage_1_2_metadata_readiness_only",
            live_access_status="live_coupa_access_blocked",
            current_repo_a_evidence=(
                "capital_hilton_external_artifact_proof_capture.json",
                "capital_hilton_operator_proof_input_packet.json",
                "capital_hilton_send_approval_gate.json",
            ),
            next_safe_move="Use protected-reference proof intake; do not access Coupa.",
        ),
        _surface(
            surface_id="capital_hilton_excel_pdf_invoice_artifacts",
            display_name="Excel/PDF companion invoice artifacts",
            primary_classification="PROTECTED_REFERENCE_ALLOWED",
            policy_classifications=(
                "METADATA_ONLY_ALLOWED",
                "PROTECTED_REFERENCE_ALLOWED",
                "REQUIRES_GUARDIAN_GATE",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("Excel companion invoice file reference", "generated PDF reference", "match proof metadata"),
            safe_metadata=(
                "protected_artifact_reference",
                "artifact_identity_or_hash",
                "invoice_number",
                "invoice_date",
                "amount",
                "service_dates",
                "match_status",
                "mismatch_reasons",
            ),
            forbidden_normal_values=("raw Excel workbook body", "raw PDF body", "spreadsheet cell contents", "check images"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="stage_1_2_metadata_readiness_only",
            live_access_status="spreadsheet_or_attachment_generation_blocked",
            current_repo_a_evidence=(
                "capital_hilton_two_invoice_workflow.json",
                "capital_hilton_external_artifact_proof_capture.json",
                "capital_hilton_send_approval_gate.json",
            ),
            next_safe_move="Capture only protected reference and match metadata until a later execution lane.",
        ),
        _surface(
            surface_id="gmail_email_send_or_draft",
            display_name="Gmail/email draft or send",
            primary_classification="LIVE_ACCESS_BLOCKED",
            policy_classifications=(
                "METADATA_ONLY_ALLOWED",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_SECURITY_THRESHOLD",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("Cassandra outward email draft identity", "specific final-send approval request", "future send receipt"),
            safe_metadata=("draft_identity", "payload_hash_requirement", "attachment_identity", "approval_request_status"),
            forbidden_normal_values=("OAuth token", "raw mailbox body", "Gmail credential", "unsanitized private thread"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="stage_2_approval_request_spec_only",
            live_access_status="gmail_draft_send_access_blocked",
            current_repo_a_evidence=(
                "cassandra_email_calendar_capability_reconciliation.json",
                "guardian_draft_approval_request_contract.json",
                "capital_hilton_send_approval_gate.json",
            ),
            next_safe_move="Keep draft/approval request modeled; do not create Gmail drafts or sends.",
        ),
        _surface(
            surface_id="calendar_access",
            display_name="Calendar access",
            primary_classification="LIVE_ACCESS_BLOCKED",
            policy_classifications=(
                "METADATA_ONLY_ALLOWED",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_SECURITY_THRESHOLD",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("calendar posture metadata", "future scoped event read/write approval"),
            safe_metadata=("capability_name", "approval_policy", "calendar_policy", "blocked_status"),
            forbidden_normal_values=("OAuth token", "raw private calendar body", "calendar credential", "private attendee details"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="stage_1_2_reconciliation_metadata_only",
            live_access_status="calendar_live_access_blocked",
            current_repo_a_evidence=("cassandra_email_calendar_capability_reconciliation.json",),
            next_safe_move="Keep calendar as reconciliation metadata until a scoped protected-access lane.",
        ),
        _surface(
            surface_id="bank_remit_home_address_check_images",
            display_name="Bank/remit/home address/check images",
            primary_classification="NORMAL_READ_MODEL_FORBIDDEN",
            policy_classifications=(
                "NORMAL_READ_MODEL_FORBIDDEN",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_SECURITY_THRESHOLD",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("remit details", "home address", "check/deposit proof image", "money-ledger payment evidence"),
            safe_metadata=("protected_reference_id", "payment_verification_status", "ledger_match_status", "redaction_status"),
            forbidden_normal_values=("bank account", "routing number", "home address", "check image", "deposit image"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="protected_reference_slot_only",
            live_access_status="raw_finance_private_data_blocked",
            current_repo_a_evidence=(
                "capital_hilton_coupa_execution_path.json",
                "capital_hilton_two_invoice_workflow.json",
                "openclaw_sensitive_policy.py",
            ),
            next_safe_move="Use protected evidence slots only; money-ledger payment verification remains future-gated.",
        ),
        _surface(
            surface_id="client_company_credentials",
            display_name="Client/company credentials",
            primary_classification="NORMAL_READ_MODEL_FORBIDDEN",
            policy_classifications=(
                "NORMAL_READ_MODEL_FORBIDDEN",
                "REQUIRES_GUARDIAN_GATE",
                "REQUIRES_SECURITY_THRESHOLD",
                "LIVE_ACCESS_BLOCKED",
            ),
            examples=("client portal password", "company OAuth token", "shared service login"),
            safe_metadata=("credential_requirement_id", "scope_label", "broker_required", "access_status"),
            forbidden_normal_values=("password", "token", "client secret", "cookie", "recovery codes"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="requirement_metadata_only",
            live_access_status="credential_access_blocked",
            current_repo_a_evidence=("custom_build_module_detangling_contract.json", "operator_sovereignty_power_stage_gate.json"),
            next_safe_move="Represent only the need and scope; never hand credentials to agents.",
        ),
        _surface(
            surface_id="browser_automation",
            display_name="Browser/Coupa/portal automation",
            primary_classification="REQUIRES_SECURITY_THRESHOLD",
            policy_classifications=("REQUIRES_SECURITY_THRESHOLD", "LIVE_ACCESS_BLOCKED", "REQUIRES_GUARDIAN_GATE"),
            examples=("Coupa portal navigation", "approved field entry", "portal submit"),
            safe_metadata=("automation_scope_id", "approved_fields_required", "blocked_status", "required_controls"),
            forbidden_normal_values=("credential material", "raw private page contents", "unbounded browser command", "submit payload"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="stage_3_4_future_design_only",
            live_access_status="browser_automation_blocked",
            current_repo_a_evidence=(
                "operator_sovereignty_power_stage_gate.json",
                "capital_hilton_coupa_execution_path.json",
            ),
            next_safe_move="Do not build browser automation until protected broker plus Stage 4 controls exist.",
        ),
        _surface(
            surface_id="oauth_tool_bridges",
            display_name="OAuth/tool bridges",
            primary_classification="UNSAFE_OR_BLOCKED",
            policy_classifications=("UNSAFE_OR_BLOCKED", "REQUIRES_SECURITY_THRESHOLD", "LIVE_ACCESS_BLOCKED"),
            examples=("Google OAuth broker", "tool bridge with live account access", "legacy capability bridge"),
            safe_metadata=("capability_name", "risk_label", "blocked_reason", "future_gate_required"),
            forbidden_normal_values=("OAuth client secret", "refresh token", "API key", "raw account payload"),
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="reference_or_reconciliation_metadata_only",
            live_access_status="oauth_tool_bridge_blocked",
            current_repo_a_evidence=(
                "repo_b_remaining_capability_delta_map.json",
                "cassandra_email_calendar_capability_reconciliation.json",
                "tool_inventory.json",
                "tool_intake.json",
            ),
            next_safe_move="Inventory as risk/capability metadata only; do not run or authenticate.",
        ),
        _surface(
            surface_id="unknown_sensitive_surface",
            display_name="Unknown sensitive access surface",
            primary_classification="UNKNOWN_FAIL_CLOSED",
            policy_classifications=("UNKNOWN_FAIL_CLOSED", "LIVE_ACCESS_BLOCKED"),
            examples=("unclassified private source", "unclear account access", "ambiguous operator request"),
            safe_metadata=("surface_label", "unknown_reason", "operator_memory_review_required", "blocked_status"),
            forbidden_normal_values=NORMAL_READ_MODEL_FORBIDDEN_VALUES,
            guardian_gate_required=True,
            security_threshold_required=True,
            current_allowed_stage="metadata_name_only_until_classified",
            live_access_status="blocked_fail_closed",
            current_repo_a_evidence=("openclaw_sensitive_policy.py", "operator_sovereignty_power_stage_gate.json"),
            next_safe_move="Create a narrow classification lane before any access.",
        ),
    )


def _classification_counts(surfaces: tuple[dict[str, Any], ...]) -> dict[str, int]:
    counts = Counter(surface["primary_classification"] for surface in surfaces)
    return {classification: counts.get(classification, 0) for classification in CLASSIFICATIONS}


def _policy_classification_counts(surfaces: tuple[dict[str, Any], ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for surface in surfaces:
        counts.update(surface["policy_classifications"])
    return {classification: counts.get(classification, 0) for classification in CLASSIFICATIONS}


def _eli5_summary() -> dict[str, Any]:
    return {
        "here_is_what_protected_access_means": (
            "OpenClaw may remember that a sensitive thing exists and what proof is needed, but it does not get the secret, "
            "raw document, account, or browser power yet."
        ),
        "what_openclaw_can_safely_track_now": (
            "Metadata, protected reference IDs, hashes, dates, amounts, PO references, match status, blockers, and approval requirements."
        ),
        "what_must_stay_out_of_normal_read_models": (
            "Passwords, tokens, OAuth secrets, bank/remit details, home address, check images, raw PDFs, raw Excel files, and private message bodies."
        ),
        "what_remains_blocked_until_security_threshold": (
            "Credential use, OAuth, Gmail/calendar/Coupa access, browser automation, spreadsheet mutation, sends, submits, and agent-held secrets."
        ),
        "why_this_protects_before_real_workflows": (
            "It lets the system plan and prove readiness without handing dangerous material to agents or pretending live authority exists."
        ),
        "next_1_to_3_sensible_lanes": [
            "Protected Evidence Reference Receipt v0",
            "Capability Skill Registry Metadata Delta v0",
            "Guardian Protected Access Gate Spec v0",
        ],
    }


def _future_broker_requirements() -> dict[str, Any]:
    return {
        "future_broker_status": "not_implemented_not_active",
        "must_prove_before_scoped_access": [
            "local-only protected storage or handoff mechanism",
            "operator-approved exact task scope",
            "Guardian gate for sensitive/live access",
            "field-level minimization and redaction",
            "no raw secret/PII leakage into normal read-model tests",
            "scoped access receipt without revealing sensitive values",
            "revocation/abort behavior",
            "tamper/hard-stop controls before Stage 4 execution",
        ],
        "must_never_do": [
            "give raw credentials to agents",
            "store raw secrets in repo/read-models",
            "treat protected reference as permission to open the artifact",
            "turn OAuth presence into account authority",
            "allow unknown access surfaces to proceed",
        ],
    }


def build_protected_access_broker_concept(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        key: _read_json_if_present(path, repo_root=repo_root)
        for key, path, _role in SOURCE_READ_MODEL_PATHS
    }
    source_records = [
        _source_record(key, path, role, sources[key], repo_root=repo_root)
        for key, path, role in SOURCE_READ_MODEL_PATHS
    ]
    surfaces = protected_access_surfaces()
    preconditions = _precondition_status(sources)
    repo_b_delta = sources.get("repo_b_delta", {})
    power_stage = sources.get("power_stage_gate", {})
    guardian_dna = sources.get("guardian_dna", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Define protected access concept boundaries before credential/OAuth/browser/account/live authority work.",
        "preconditions": preconditions,
        "protected_access_definition": (
            "A future local-only, scoped, receipt-backed mechanism for sensitive credentials, PII, private artifacts, "
            "and account access. At the current stage it is metadata/protected-reference readiness only."
        ),
        "doctrine": {
            "awareness_is_cheap_authority_is_expensive": True,
            "protected_access_does_not_mean_agents_get_credentials": True,
            "protected_access_does_not_mean_broad_raw_private_ingestion": True,
            "credential_browser_oauth_account_access_is_beyond_current_security_threshold": True,
        },
        "current_allowed_stage_1_2": {
            "metadata_only_allowed": True,
            "protected_reference_slots_allowed": True,
            "approval_request_specs_allowed": True,
            "approval_receipts_or_execution_not_created": True,
            "live_access_allowed": False,
        },
        "blocked_until_security_threshold": [
            "credential use",
            "OAuth authorization",
            "Gmail/email account access",
            "calendar account access",
            "Coupa/portal login",
            "browser automation",
            "spreadsheet mutation",
            "external sends/submits",
            "agent-held secret material",
        ],
        "normal_read_model_forbidden_values": list(NORMAL_READ_MODEL_FORBIDDEN_VALUES),
        "safe_metadata_fields": list(SAFE_METADATA_FIELDS),
        "classifications": list(CLASSIFICATIONS),
        "classification_counts": _classification_counts(surfaces),
        "policy_classification_counts": _policy_classification_counts(surfaces),
        "protected_access_surfaces": list(surfaces),
        "guardian_role": {
            "role": "gatekeeper_for_exact_scope_and_future_sensitive_access_receipts",
            "guardian_is_executor": False,
            "approval_request_is_not_approval_receipt": True,
            "approval_receipt_is_not_execution": True,
            "generic_authority_allowed": False,
            "evidence": guardian_dna.get("schema_version", "guardian_dna_read_model_missing"),
        },
        "mission_control_role": {
            "future_role": "visibility_and_operator_approval_surface",
            "backend_command_path_added": False,
            "normal_read_model_source_of_truth": False,
            "may_display_protected_reference_status_later": True,
        },
        "agent_boundary": {
            "agents_receive_direct_credentials": False,
            "agents_may_request_metadata_or_protected_reference_status": True,
            "agents_may_open_raw_sensitive_artifacts": False,
            "agents_may_use_oauth_or_tokens_directly": False,
            "unknown_authority_fails_closed": True,
        },
        "future_broker_requirements": _future_broker_requirements(),
        "current_stage_evidence": {
            "power_stage_schema_version": power_stage.get("schema_version"),
            "current_power_stage": power_stage.get("current_power_stage", {}),
            "stage_3_blocked_without_protected_pii_broker_controls": bool(
                power_stage.get("stage_3_blocked_without_protected_pii_broker_controls", True)
            ),
            "stage_4_blocked_without_hard_stop_and_tamper_controls": bool(
                power_stage.get("stage_4_blocked_without_hard_stop_and_tamper_controls", True)
            ),
        },
        "repo_b_delta_reference": {
            "used_existing_repo_a_delta_read_model_only": bool(repo_b_delta),
            "repo_b_filesystem_inspected": False,
            "repo_b_code_executed": False,
            "worth_bringing_forward_carefully": [
                "protected PII/broker concept",
                "capability/skill registry metadata",
            ],
            "risky_blocked_concepts": [
                "OAuth/tool/browser/credential bridges",
                "old live loops",
                "automatic repair machinery",
            ],
        },
        "operator_eli5_summary": _eli5_summary(),
        "source_read_models": source_records,
        "live_access_blocked": True,
        "unknown_access_surfaces_fail_closed": True,
        "normal_read_model_forbids_raw_pii_private_docs": True,
        "protected_references_allowed_only_in_safe_metadata_form": True,
        "guardian_gate_required_for_live_sensitive_access": True,
        "security_threshold_required_for_live_access": True,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Protected Evidence Reference Receipt v0",
    }


def format_protected_access_broker_concept(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Protected Access Broker Concept Delta v0",
        "",
        "Status:",
        f"- Preconditions satisfied: `{str(payload['preconditions']['all_preconditions_satisfied']).lower()}`.",
        "- Current posture: metadata/protected-reference readiness only.",
        "- Live credential/OAuth/browser/account access: `blocked`.",
        "- Agents receive direct credentials: `false`.",
        "",
        "## ELI5 Summary",
        f"- What protected access means: {eli5['here_is_what_protected_access_means']}",
        f"- What OpenClaw can safely track now: {eli5['what_openclaw_can_safely_track_now']}",
        f"- What must stay out of normal read-models: {eli5['what_must_stay_out_of_normal_read_models']}",
        f"- What remains blocked until security threshold: {eli5['what_remains_blocked_until_security_threshold']}",
        f"- Why this protects before real workflows: {eli5['why_this_protects_before_real_workflows']}",
        "",
        "## Protected Access Surfaces",
    ]
    for surface in payload["protected_access_surfaces"]:
        lines.append(
            f"- `{surface['surface_id']}`: {surface['primary_classification']} "
            f"({surface['live_access_status']})"
        )
    lines.extend(["", "## Safe Metadata / Protected References"])
    for field in payload["safe_metadata_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Never Store Raw In Normal Read-Models"])
    for value in payload["normal_read_model_forbidden_values"]:
        lines.append(f"- {value}")
    lines.extend(["", "## Future Broker Must Prove"])
    for item in payload["future_broker_requirements"]["must_prove_before_scoped_access"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Boundaries"])
    lines.extend(
        [
            "- No credentials, OAuth, Gmail/calendar/Coupa/browser access, sends, submits, approval receipts, execution, Repo B execution, Mission Control changes, or client deployment were added.",
            "- Protected references are not permission to open protected artifacts.",
            "- Unknown sensitive access fails closed.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_protected_access_broker_concept(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ProtectedAccessBrokerConceptExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_protected_access_broker_concept(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_protected_access_broker_concept(payload), encoding="utf-8")
    return ProtectedAccessBrokerConceptExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        preconditions_satisfied=payload["preconditions"]["all_preconditions_satisfied"],
        surface_count=len(payload["protected_access_surfaces"]),
        live_access_blocked=payload["live_access_blocked"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export protected access broker concept read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_protected_access_broker_concept(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "CLASSIFICATIONS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "NORMAL_READ_MODEL_FORBIDDEN_VALUES",
    "OPERATOR_EXPORT_NAME",
    "SAFE_METADATA_FIELDS",
    "SCHEMA_VERSION",
    "build_protected_access_broker_concept",
    "export_protected_access_broker_concept",
    "format_protected_access_broker_concept",
    "protected_access_surfaces",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
