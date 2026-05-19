"""Guardian protected-access gate spec v0.

This read-model defines the future Guardian gate that must be satisfied before
any protected reference could be used, inspected, opened, transmitted, or passed
to an execution workflow. It is a specification only: it does not grant access,
inspect raw protected content, approve anything, create receipts, send messages,
access credentials/OAuth/browser/account surfaces, or add runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protected_access_broker_concept import (
    SAFE_METADATA_FIELDS,
    build_protected_access_broker_concept,
)
from protected_evidence_reference_receipt import (
    FORBIDDEN_RAW_CONTENT_FIELDS,
    RECEIPT_TYPES,
    build_protected_evidence_reference_receipt,
    stable_json,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "guardian_protected_access_gate_spec_v0"
JSON_EXPORT_NAME = "guardian_protected_access_gate_spec.json"
OPERATOR_EXPORT_NAME = "guardian_protected_access_gate_spec_OPERATOR.md"

ACCESS_STATES = (
    "ACCESS_NOT_REQUESTED",
    "REFERENCE_MISSING",
    "REFERENCE_RECORDED_ACCESS_BLOCKED",
    "METADATA_INCOMPLETE",
    "SECURITY_THRESHOLD_REQUIRED",
    "GUARDIAN_REVIEW_REQUIRED",
    "ACCESS_DENIED",
    "ACCESS_READY_FOR_FUTURE_GATED_REVIEW",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "gate_spec_only": True,
    "protected_access_allowed_now": False,
    "protected_artifact_access_granted": False,
    "raw_content_inspected": False,
    "raw_content_transmitted": False,
    "raw_content_stored": False,
    "approval_created": False,
    "approval_receipt_created": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "browser_automation_added": False,
    "coupa_accessed": False,
    "gmail_calendar_accessed": False,
    "oauth_flow_started": False,
    "credentials_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "pdf_generated_or_attached": False,
    "spreadsheet_mutation_triggered": False,
    "guardian_live_message_sent": False,
    "mission_control_app_changed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "security_pass_started": False,
}

LIVE_OR_EXECUTION_ACTION_KEYWORDS = (
    "open",
    "inspect",
    "use",
    "transmit",
    "attach",
    "send",
    "submit",
    "execute",
    "browser",
    "oauth",
    "credential",
)


@dataclass(frozen=True)
class GuardianProtectedAccessGateSpecExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    gate_record_count: int
    protected_access_allowed_now: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _gate_id(workflow_id: object, receipt_type: object, requested_action: object) -> str:
    digest = hashlib.sha256(f"{workflow_id}\0{receipt_type}\0{requested_action}".encode("utf-8")).hexdigest()
    return f"guardian_protected_access_gate_{digest[:20]}"


def _gate_definitions() -> tuple[dict[str, Any], ...]:
    return (
        {
            "gate_key": "capital_hilton_coupa_payment_invoice_proof_access",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Capital Hilton Coupa supplier-portal invoice",
            "requested_future_action": "future_use_coupa_payment_invoice_proof_reference",
            "protected_evidence_type": "coupa_payment_invoice_proof",
            "receipt_type_required": "coupa_payment_invoice_proof_reference",
            "example_surface": "Coupa proof reference",
        },
        {
            "gate_key": "capital_hilton_excel_companion_artifact_access",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Capital Hilton Excel companion invoice",
            "requested_future_action": "future_use_excel_companion_artifact_reference",
            "protected_evidence_type": "excel_companion_invoice_artifact",
            "receipt_type_required": "excel_companion_artifact_reference",
            "example_surface": "Excel/PDF invoice artifacts",
        },
        {
            "gate_key": "capital_hilton_pdf_invoice_attachment_access",
            "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
            "workflow_name": "Capital Hilton PDF invoice attachment",
            "requested_future_action": "future_attach_pdf_invoice_reference",
            "protected_evidence_type": "pdf_invoice_artifact",
            "receipt_type_required": "pdf_invoice_artifact_reference",
            "example_surface": "PDF invoice artifact reference",
        },
        {
            "gate_key": "cassandra_gmail_email_evidence_access",
            "workflow_id": "cassandra_outward_email_review",
            "workflow_name": "Cassandra email evidence",
            "requested_future_action": "future_use_gmail_email_evidence_reference",
            "protected_evidence_type": "gmail_email_evidence",
            "receipt_type_required": "gmail_email_evidence_reference",
            "example_surface": "Gmail/email evidence",
        },
        {
            "gate_key": "calendar_evidence_access",
            "workflow_id": "calendar_governed_reference",
            "workflow_name": "Calendar evidence reference",
            "requested_future_action": "future_use_calendar_evidence_reference",
            "protected_evidence_type": "calendar_evidence",
            "receipt_type_required": "calendar_evidence_reference",
            "example_surface": "calendar evidence",
        },
        {
            "gate_key": "payment_sensitive_reference_access",
            "workflow_id": "payment_verification_reference",
            "workflow_name": "Payment/remit/check image protected reference",
            "requested_future_action": "future_use_payment_sensitive_reference",
            "protected_evidence_type": "bank_remit_home_check_image_reference",
            "receipt_type_required": "bank_remit_home_check_image_sensitive_reference",
            "example_surface": "bank/remit/home/check image sensitive references",
        },
        {
            "gate_key": "client_credential_reference_access",
            "workflow_id": "client_specific_protected_access",
            "workflow_name": "Client/company credential protected reference",
            "requested_future_action": "future_use_client_credential_reference",
            "protected_evidence_type": "client_credential_reference",
            "receipt_type_required": "client_credential_reference",
            "example_surface": "client credential references",
        },
        {
            "gate_key": "browser_oauth_tool_bridge_reference_access",
            "workflow_id": "future_tool_browser_bridge_reference",
            "workflow_name": "Browser/OAuth/tool bridge reference",
            "requested_future_action": "future_use_browser_oauth_tool_bridge_reference",
            "protected_evidence_type": "browser_oauth_tool_bridge_reference",
            "receipt_type_required": "not_supported_by_current_receipt_contract",
            "example_surface": "browser/OAuth/tool bridge references",
        },
        {
            "gate_key": "unknown_sensitive_surface_access",
            "workflow_id": "unknown_sensitive_surface",
            "workflow_name": "Unknown sensitive surface",
            "requested_future_action": "future_use_unknown_sensitive_surface_reference",
            "protected_evidence_type": "unknown_sensitive_surface",
            "receipt_type_required": "unknown_sensitive_surface_reference",
            "example_surface": "unknown sensitive surfaces",
        },
    )


def _receipt_by_type(receipt_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = receipt_payload.get("receipt_records")
    if not isinstance(records, list):
        return {}
    return {record.get("receipt_type"): record for record in records if isinstance(record, dict)}


def _request_for(gate_requests: dict[str, Any] | None, gate_key: str, receipt_type: str) -> dict[str, Any]:
    if not isinstance(gate_requests, dict):
        return {}
    source = gate_requests.get("protected_access_requests")
    if not isinstance(source, dict):
        source = gate_requests
    raw = source.get(gate_key) or source.get(receipt_type)
    return raw if isinstance(raw, dict) else {}


def _blocked_request_text(request: dict[str, Any]) -> bool:
    text = " ".join(str(value).lower() for value in request.values() if isinstance(value, str))
    return any(keyword in text for keyword in LIVE_OR_EXECUTION_ACTION_KEYWORDS)


def _blockers_for_state(
    *,
    state: str,
    receipt_record: dict[str, Any] | None,
    request: dict[str, Any],
    receipt_type_required: str,
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if state == "ACCESS_NOT_REQUESTED":
        blockers.append({"blocker_id": "no_protected_access_request", "description": "No protected access request is active."})
    if state == "REFERENCE_MISSING":
        blockers.append({"blocker_id": "protected_reference_receipt_missing", "description": "Required protected evidence reference receipt is missing."})
    if state == "METADATA_INCOMPLETE":
        missing = receipt_record.get("missing_required_metadata", []) if receipt_record else []
        blockers.append({"blocker_id": "metadata_incomplete", "description": f"Required safe metadata is incomplete: {', '.join(missing) or 'unknown'}."})
    if state == "ACCESS_DENIED":
        blockers.append({"blocker_id": "access_denied_or_invalid", "description": "Protected access request is denied or invalid under current metadata."})
    if state == "REFERENCE_RECORDED_ACCESS_BLOCKED":
        blockers.append({"blocker_id": "reference_recorded_but_access_blocked", "description": "A protected reference exists, but it is not a validated access/use approval."})
    if state == "SECURITY_THRESHOLD_REQUIRED":
        blockers.append({"blocker_id": "security_threshold_required", "description": "Future security-threshold controls are required before access/use can be reviewed."})
    if state == "GUARDIAN_REVIEW_REQUIRED":
        blockers.append({"blocker_id": "guardian_review_required", "description": "Guardian review is required before protected access could be reviewed further."})
    if state == "UNKNOWN_FAIL_CLOSED":
        blockers.append({"blocker_id": "unknown_or_unsupported_protected_access", "description": "Unknown or unsupported protected access fails closed."})
    if receipt_type_required not in RECEIPT_TYPES:
        blockers.append({"blocker_id": "receipt_contract_missing_for_surface", "description": "No current protected evidence receipt type supports this surface."})
    if _blocked_request_text(request):
        blockers.append({"blocker_id": "live_or_execution_action_remains_blocked", "description": "The requested future action mentions live use/open/send/submit/execute behavior, which remains blocked now."})
    return blockers


def _access_state(
    *,
    definition: dict[str, Any],
    receipt_record: dict[str, Any] | None,
    request: dict[str, Any],
) -> str:
    receipt_type = definition["receipt_type_required"]
    if receipt_type not in RECEIPT_TYPES:
        return "UNKNOWN_FAIL_CLOSED"
    if definition["protected_evidence_type"] == "unknown_sensitive_surface":
        return "UNKNOWN_FAIL_CLOSED"
    if not bool(request.get("access_requested", False)):
        return "ACCESS_NOT_REQUESTED"
    if str(request.get("gate_decision", "")).lower() == "denied":
        return "ACCESS_DENIED"
    if not receipt_record:
        return "REFERENCE_MISSING"
    receipt_status = str(receipt_record.get("receipt_status", "REFERENCE_MISSING"))
    if receipt_status == "REFERENCE_MISSING":
        return "REFERENCE_MISSING"
    if receipt_status == "METADATA_INCOMPLETE":
        return "METADATA_INCOMPLETE"
    if receipt_status in {"METADATA_INVALID", "RAW_CONTENT_REJECTED"}:
        return "ACCESS_DENIED"
    if receipt_status == "UNKNOWN_FAIL_CLOSED":
        return "UNKNOWN_FAIL_CLOSED"
    if receipt_status == "REFERENCE_RECORDED":
        return "REFERENCE_RECORDED_ACCESS_BLOCKED"
    if not bool(request.get("security_threshold_controls_ready", False)):
        return "SECURITY_THRESHOLD_REQUIRED"
    if not bool(request.get("guardian_review_ready", False)):
        return "GUARDIAN_REVIEW_REQUIRED"
    return "ACCESS_READY_FOR_FUTURE_GATED_REVIEW"


def _source_ref(path: str | Path, payload: dict[str, Any], *, repo_root: str | Path) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    return {
        "path": _display_path(target),
        "present": bool(payload),
        "schema_version": payload.get("schema_version"),
        "raw_private_content_read": False,
        "external_account_accessed": False,
        "executed_or_dispatched": False,
    }


def _gate_record(
    definition: dict[str, Any],
    *,
    receipt_record: dict[str, Any] | None,
    request: dict[str, Any],
) -> dict[str, Any]:
    state = _access_state(definition=definition, receipt_record=receipt_record, request=request)
    receipt_status = receipt_record.get("receipt_status") if receipt_record else "missing"
    requested_action = request.get("requested_action") or definition["requested_future_action"]
    return {
        "protected_access_gate_id": _gate_id(definition["workflow_id"], definition["receipt_type_required"], requested_action),
        "gate_key": definition["gate_key"],
        "workflow_id": definition["workflow_id"],
        "workflow_name": definition["workflow_name"],
        "workflow_action_requesting_future_protected_use": requested_action,
        "requested_by": request.get("requested_by", "future_workflow_or_operator_intake_modeled_only"),
        "example_surface": definition["example_surface"],
        "protected_evidence_type": definition["protected_evidence_type"],
        "protected_evidence_reference_receipt_requirement": {
            "receipt_type_required": definition["receipt_type_required"],
            "receipt_present": bool(receipt_record),
            "receipt_id": receipt_record.get("receipt_id", "") if receipt_record else "",
            "receipt_status": receipt_status,
            "receipt_does_not_grant_access": True,
            "receipt_does_not_grant_approval": True,
            "receipt_does_not_grant_execution": True,
        },
        "proof_receipt_metadata_exists": bool(receipt_record and receipt_status not in {"REFERENCE_MISSING", "UNKNOWN_FAIL_CLOSED"}),
        "allowed_metadata_fields": list(SAFE_METADATA_FIELDS),
        "forbidden_raw_content_fields": list(FORBIDDEN_RAW_CONTENT_FIELDS),
        "required_guardian_security_gate_status": {
            "guardian_review_required": True,
            "guardian_review_ready_now": bool(request.get("guardian_review_ready", False)),
            "security_threshold_required": True,
            "security_threshold_controls_ready_now": bool(request.get("security_threshold_controls_ready", False)),
            "future_power_stage_required_before_live_access": "stage_3_for_broker_design_and_stage_4_before_real_execution",
            "current_power_stage_allows_live_access": False,
        },
        "current_access_state": state,
        "protected_access_allowed_now": False,
        "available_for_future_gated_review": state == "ACCESS_READY_FOR_FUTURE_GATED_REVIEW",
        "blockers": _blockers_for_state(
            state=state,
            receipt_record=receipt_record,
            request=request,
            receipt_type_required=definition["receipt_type_required"],
        ),
        "raw_content_boundaries": {
            "raw_content_required": False,
            "raw_content_allowed_in_normal_read_model": False,
            "raw_content_inspected": False,
            "raw_content_transmitted": False,
        },
        "explicit_authority_exclusions": [
            "raw protected content access",
            "credential/OAuth access",
            "browser automation",
            "Gmail/calendar/Coupa access",
            "approval receipt creation",
            "execution workflow activation",
            "send/submit authority",
            "runtime authority",
        ],
        "operator_next_safe_move": (
            "Keep the protected reference as metadata only; complete future Guardian/security-threshold gates before any access or use."
        ),
    }


def build_gate_records(
    *,
    receipt_payload: dict[str, Any],
    gate_requests: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    receipts = _receipt_by_type(receipt_payload)
    records: list[dict[str, Any]] = []
    for definition in _gate_definitions():
        receipt_type = definition["receipt_type_required"]
        records.append(
            _gate_record(
                definition,
                receipt_record=receipts.get(receipt_type),
                request=_request_for(gate_requests, definition["gate_key"], receipt_type),
            )
        )
    return tuple(records)


def _gate_summary(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    counts = Counter(record["current_access_state"] for record in records)
    return {
        "gate_record_count": len(records),
        "protected_access_allowed_now": False,
        "available_for_future_gated_review_count": sum(1 for record in records if record["available_for_future_gated_review"]),
        "blocked_gate_count": sum(1 for record in records if record["current_access_state"] != "ACCESS_READY_FOR_FUTURE_GATED_REVIEW"),
        "access_state_counts": {state: counts.get(state, 0) for state in ACCESS_STATES},
    }


def _gate_contract() -> dict[str, Any]:
    return {
        "contract_id": "guardian_protected_access_gate_spec_v0",
        "contract_kind": "guardian_protected_access_gate_spec",
        "required_fields": [
            "protected_access_gate_id",
            "workflow_id",
            "workflow_action_requesting_future_protected_use",
            "protected_evidence_reference_receipt_requirement",
            "protected_evidence_type",
            "allowed_metadata_fields",
            "forbidden_raw_content_fields",
            "required_guardian_security_gate_status",
            "current_access_state",
            "blockers",
            "explicit_authority_exclusions",
            "operator_next_safe_move",
        ],
        "access_states": list(ACCESS_STATES),
        "gate_answers": [
            "whether protected access is allowed now",
            "why access is blocked",
            "what protected reference type is involved",
            "what workflow/action is asking to use it",
            "what receipt metadata exists",
            "what Guardian/security prerequisites are still required",
            "what raw-content boundaries apply",
            "what authority remains excluded",
        ],
        "gate_does_not_do": [
            "open protected artifacts",
            "validate raw artifact truth",
            "create approval requests or receipts",
            "send or upload anything",
            "start browser/OAuth/credential flows",
            "activate execution or runtime authority",
        ],
    }


def _eli5_summary() -> dict[str, str]:
    return {
        "openclaw_can_know_protected_proof_exists": "OpenClaw can know protected proof exists through a safe receipt/reference.",
        "receipt_is_not_the_key": "The receipt is not the key and does not let agents open the protected proof.",
        "guardian_decides_if_future_use_is_reviewable": (
            "Guardian's gate decides whether a future use request is even eligible for later gated review."
        ),
        "nothing_opens_sends_uploads_or_executes_yet": "Nothing opens, sends, uploads, submits, or executes in this lane.",
        "prepares_safety_gate_before_real_workflows": (
            "This prepares the safety gate so later live workflows cannot skip proof, scope, Guardian review, or security-threshold controls."
        ),
    }


def build_guardian_protected_access_gate_spec(
    *,
    repo_root: str | Path = ROOT,
    receipt_inputs: dict[str, Any] | None = None,
    gate_requests: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    concept_payload = _read_json_if_present(DEFAULT_EXPORT_ROOT / "protected_access_broker_concept.json", repo_root=repo_root)
    if not concept_payload:
        concept_payload = build_protected_access_broker_concept(repo_root=repo_root, generated_at=ts)
    receipt_payload = _read_json_if_present(DEFAULT_EXPORT_ROOT / "protected_evidence_reference_receipt.json", repo_root=repo_root)
    if receipt_inputs is not None or not receipt_payload:
        receipt_payload = build_protected_evidence_reference_receipt(
            repo_root=repo_root,
            receipt_inputs=receipt_inputs,
            generated_at=ts,
        )
    power_stage_payload = _read_json_if_present(DEFAULT_EXPORT_ROOT / "operator_sovereignty_power_stage_gate.json", repo_root=repo_root)
    guardian_dna_payload = _read_json_if_present(DEFAULT_EXPORT_ROOT / "guardian_responsibility_dna_audit.json", repo_root=repo_root)
    records = build_gate_records(receipt_payload=receipt_payload, gate_requests=gate_requests)
    summary = _gate_summary(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "purpose": "Define Guardian's future protected-access gate before any protected reference use/access/execution path.",
        "gate_contract": _gate_contract(),
        "access_states": list(ACCESS_STATES),
        "gate_records": list(records),
        "gate_summary": summary,
        "current_availability_status": "protected_access_blocked_now",
        "protected_access_allowed_now": False,
        "guardian_review_required": True,
        "security_threshold_required": True,
        "source_read_models": {
            "protected_access_broker_concept": _source_ref(
                DEFAULT_EXPORT_ROOT / "protected_access_broker_concept.json",
                concept_payload,
                repo_root=repo_root,
            ),
            "protected_evidence_reference_receipt": _source_ref(
                DEFAULT_EXPORT_ROOT / "protected_evidence_reference_receipt.json",
                receipt_payload,
                repo_root=repo_root,
            ),
            "operator_sovereignty_power_stage_gate": _source_ref(
                DEFAULT_EXPORT_ROOT / "operator_sovereignty_power_stage_gate.json",
                power_stage_payload,
                repo_root=repo_root,
            ),
            "guardian_responsibility_dna_audit": _source_ref(
                DEFAULT_EXPORT_ROOT / "guardian_responsibility_dna_audit.json",
                guardian_dna_payload,
                repo_root=repo_root,
            ),
        },
        "source_alignment": {
            "protected_access_concept_schema_version": concept_payload.get("schema_version"),
            "protected_evidence_receipt_schema_version": receipt_payload.get("schema_version"),
            "receipt_is_not_key": True,
            "receipt_is_not_approval": True,
            "receipt_is_not_execution": True,
            "normal_read_models_store_metadata_only": True,
            "repo_b_filesystem_inspected": False,
        },
        "raw_content_boundary": {
            "forbidden_raw_content_fields": list(FORBIDDEN_RAW_CONTENT_FIELDS),
            "raw_content_access_allowed_now": False,
            "raw_content_inspected": False,
            "raw_content_transmitted": False,
            "raw_content_stored": False,
        },
        "operator_eli5_summary": _eli5_summary(),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capability Skill Registry Metadata Delta v0",
    }


def format_guardian_protected_access_gate_spec(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Guardian Protected Access Gate Spec v0",
        "",
        "Status:",
        "- Protected access allowed now: `false`.",
        "- Guardian review required before future protected use: `true`.",
        "- Security threshold required before live access/use: `true`.",
        "- Raw protected content inspected/transmitted/stored: `false`.",
        "- Approval, execution, browser, OAuth, credential, send, submit, and runtime authority: `false`.",
        "",
        "## ELI5 Summary",
        f"- {eli5['openclaw_can_know_protected_proof_exists']}",
        f"- {eli5['receipt_is_not_the_key']}",
        f"- {eli5['guardian_decides_if_future_use_is_reviewable']}",
        f"- {eli5['nothing_opens_sends_uploads_or_executes_yet']}",
        f"- {eli5['prepares_safety_gate_before_real_workflows']}",
        "",
        "## Access State Counts",
    ]
    for state in ACCESS_STATES:
        lines.append(f"- `{state}`: {payload['gate_summary']['access_state_counts'].get(state, 0)}")
    lines.extend(["", "## Gate Records"])
    for record in payload["gate_records"]:
        lines.append(
            f"- `{record['gate_key']}`: `{record['current_access_state']}`; "
            f"allowed now: `{str(record['protected_access_allowed_now']).lower()}`."
        )
    lines.extend(["", "## Boundary"])
    lines.extend(
        [
            "- Protected evidence receipts do not grant access.",
            "- Unknown or unsupported protected access fails closed.",
            "- Future use must pass exact scope, Guardian review, and security-threshold controls before live access exists.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_guardian_protected_access_gate_spec(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> GuardianProtectedAccessGateSpecExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_protected_access_gate_spec(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_guardian_protected_access_gate_spec(payload), encoding="utf-8")
    return GuardianProtectedAccessGateSpecExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        gate_record_count=len(payload["gate_records"]),
        protected_access_allowed_now=payload["protected_access_allowed_now"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Guardian protected-access gate spec read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_guardian_protected_access_gate_spec(repo_root=args.repo_root, export_root=args.export_root)
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "ACCESS_STATES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_gate_records",
    "build_guardian_protected_access_gate_spec",
    "export_guardian_protected_access_gate_spec",
    "format_guardian_protected_access_gate_spec",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
