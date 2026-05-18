"""Cassandra draft review packet read-model v0.

Builds a governed, review-only Cassandra draft packet for a specific workflow.
This module does not read Gmail, create Gmail drafts, send email, access OAuth
or credentials, attach PDFs, mutate spreadsheets, run Repo B, or grant runtime
or approval authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cassandra_email_calendar_capability_reconciliation import (
    JSON_EXPORT_NAME as RECONCILIATION_JSON_EXPORT_NAME,
    SCHEMA_VERSION as RECONCILIATION_SCHEMA_VERSION,
)
from capital_hilton_actionable_review_packet import stable_json


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "cassandra_draft_review_packet_v0"
JSON_EXPORT_NAME = "cassandra_draft_review_packet.json"
OPERATOR_EXPORT_NAME = "cassandra_draft_review_packet_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_RECONCILIATION_PATH = DEFAULT_EXPORT_ROOT / RECONCILIATION_JSON_EXPORT_NAME
DEFAULT_PROOF_CAPTURE_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_external_artifact_proof_capture.json"
DEFAULT_SEND_GATE_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_send_approval_gate.json"

WORKFLOW_ID = "capital_hilton_companion_invoice_email"
WORKFLOW_NAME = "Capital Hilton companion invoice email"
DRAFT_PURPOSE = "review_companion_invoice_email_before_any_future_send"
NEXT_RECOMMENDED_LANE = "Mission Control Cassandra Draft Review Surface v0"

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "read_model_only": True,
    "live_gmail_read_triggered": False,
    "gmail_draft_created": False,
    "email_sent": False,
    "gmail_or_email_send_triggered": False,
    "oauth_or_credentials_accessed": False,
    "calendar_access_triggered": False,
    "browser_automation_added": False,
    "pdf_generated_or_attached": False,
    "spreadsheet_mutation_triggered": False,
    "raw_private_contact_scraped": False,
    "raw_inbox_or_calendar_content_read": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
}


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


def _source_ref(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _display_path(_rooted(path)),
        "present": bool(payload),
        "schema_version": payload.get("schema_version"),
        "raw_private_body_read": False,
        "external_account_accessed": False,
    }


def _required_proofs(proof_capture: dict[str, Any], send_gate: dict[str, Any]) -> list[dict[str, Any]]:
    proof_records = proof_capture.get("proof_records") if isinstance(proof_capture.get("proof_records"), dict) else {}
    evidence_status = send_gate.get("prerequisite_evidence_status") if isinstance(send_gate.get("prerequisite_evidence_status"), dict) else {}
    definitions = (
        (
            "coupa_payment_invoice_proof",
            "Coupa supplier-portal payment invoice proof",
            "coupa_invoice_proof_exists",
            "payment_invoice_proof",
        ),
        (
            "excel_companion_invoice_artifact",
            "Excel companion invoice protected artifact/reference",
            "excel_companion_invoice_artifact_exists",
            "companion_invoice_reference",
        ),
        (
            "excel_coupa_match_proof",
            "Excel companion invoice matches Coupa/payment invoice proof",
            "excel_companion_invoice_verified_to_match_coupa",
            "companion_match_proof",
        ),
    )
    results: list[dict[str, Any]] = []
    for proof_type, label, evidence_key, reference_role in definitions:
        record = proof_records.get(proof_type) if isinstance(proof_records, dict) else None
        present = bool(evidence_status.get(evidence_key))
        results.append(
            {
                "proof_type": proof_type,
                "label": label,
                "required_before_final_send": True,
                "present_now": present,
                "proof_status": (record or {}).get("proof_status", "pending_not_recorded"),
                "reference_role": reference_role,
                "protected_reference_only": True,
                "raw_artifact_stored": False,
            }
        )
    return results


def _blockers(required_proofs: list[dict[str, Any]], send_gate: dict[str, Any]) -> list[dict[str, Any]]:
    blocker_rows = [
        {
            "blocker_id": f"missing_{proof['proof_type']}",
            "severity": "blocks_final_send",
            "description": f"Missing governed {proof['label']}.",
            "next_safe_move": "Record protected proof metadata through the governed Capital Hilton proof rail when real proof exists.",
        }
        for proof in required_proofs
        if not proof["present_now"]
    ]
    for reason in ((send_gate.get("blocker_status") or {}).get("failure_reasons") or []):
        if reason in {
            "missing_email_draft",
            "missing_attachment_reference",
            "missing_draft_identity_hash_reference",
            "missing_attachment_identity_hash_reference",
            "unresolved_critical_blockers",
        }:
            blocker_rows.append(
                {
                    "blocker_id": reason,
                    "severity": "blocks_final_send",
                    "description": reason.replace("_", " "),
                    "next_safe_move": "Keep the packet review-only until proof, draft identity, attachment reference, and Guardian gate conditions are satisfied.",
                }
            )
    return blocker_rows


def _draft_subject(send_gate: dict[str, Any]) -> str:
    state = send_gate.get("current_approval_availability_state") or "blocked_review_only"
    return f"Review only: Capital Hilton companion invoice ({state})"


def _draft_body_summary(blockers: list[dict[str, Any]]) -> str:
    if blockers:
        return (
            "Review-only companion invoice email packet. Final send remains blocked until governed proof "
            "and specific draft/attachment approval requirements are satisfied."
        )
    return (
        "Review-only companion invoice email packet. Proof prerequisites are modeled as present, but execution "
        "still requires a future specific Guardian approval and send controls."
    )


def build_cassandra_draft_review_packet(
    *,
    reconciliation_json: str | Path = DEFAULT_RECONCILIATION_PATH,
    proof_capture_json: str | Path = DEFAULT_PROOF_CAPTURE_PATH,
    send_gate_json: str | Path = DEFAULT_SEND_GATE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    reconciliation = _read_json_if_present(reconciliation_json)
    proof_capture = _read_json_if_present(proof_capture_json)
    send_gate = _read_json_if_present(send_gate_json)
    draft_id = _row_id("cass_draft_review", WORKFLOW_ID, SCHEMA_VERSION)
    required_proofs = _required_proofs(proof_capture, send_gate)
    blockers = _blockers(required_proofs, send_gate)
    send_gate_state = send_gate.get("current_approval_availability_state") or "unknown_missing_send_gate_read_model"
    send_eligible = send_gate_state == "available_for_guardian_send_approval" and not blockers
    approval_requirements = {
        "guardian_required_before_any_send": True,
        "approval_scope": "specific_draft_specific_attachment_specific_workflow_only",
        "generic_send_authority_allowed": False,
        "approval_request_created_in_this_lane": False,
        "approval_receipt_present": False,
        "approval_receipt_required_before_execution": True,
        "future_approval_gate_reference": _source_ref(send_gate_json, send_gate),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "packet_kind": "cassandra_email_draft_review_packet",
        "packet_status": "review_only_blocked_before_send" if not send_eligible else "review_only_eligible_for_future_guardian_request",
        "review_status": "operator_review_packet_ready_send_blocked",
        "workflow_id": WORKFLOW_ID,
        "workflow_name": WORKFLOW_NAME,
        "intended_workflow": "capital_hilton_two_invoice_final_send_review",
        "draft_id": draft_id,
        "draft_purpose": DRAFT_PURPOSE,
        "draft_status": "proposed_review_packet_not_gmail_draft",
        "recipient_group": {
            "recipient_roles_only": True,
            "to_role_labels": ["Capital Hilton payment/invoice recipient role - pending safe modeled confirmation"],
            "cc_role_labels": ["operator review copy role", "finance context stakeholders - pending safe modeled confirmation"],
            "raw_private_contact_expanded": False,
        },
        "subject": {
            "subject_status": "generated_from_governed_workflow_state",
            "subject_text": _draft_subject(send_gate),
            "contains_private_contact_data": False,
        },
        "body": {
            "body_mode": "summary_preview_only",
            "body_summary": _draft_body_summary(blockers),
            "body_text_available_for_operator_review": True,
            "body_text": (
                "Hello - this is a review-only companion invoice note for the Capital Hilton workflow. "
                "It should not be sent until Coupa payment-invoice proof, Excel companion match proof, "
                "attachment identity, and specific Guardian final-send approval are recorded."
            ),
            "raw_private_inbox_content_used": False,
            "live_gmail_content_used": False,
        },
        "attachments_expected": [
            {
                "attachment_role": "excel_companion_invoice_pdf",
                "status": "protected_reference_placeholder_only",
                "required_before_send": True,
                "protected_reference_present_now": bool((send_gate.get("prerequisite_evidence_status") or {}).get("attachment_reference_exists")),
                "raw_pdf_attached": False,
                "pdf_generated_in_this_lane": False,
            }
        ],
        "source_facts_used": [
            _source_ref(reconciliation_json, reconciliation),
            _source_ref(proof_capture_json, proof_capture),
            _source_ref(send_gate_json, send_gate),
        ],
        "required_proofs": required_proofs,
        "blockers": blockers,
        "approval_requirements": approval_requirements,
        "send_eligibility": {
            "final_send_gate_state": send_gate_state,
            "eligible_for_guardian_final_send_approval_later": send_eligible,
            "send_available_now": False,
            "gmail_draft_available_now": False,
            "attachment_available_now": bool((send_gate.get("prerequisite_evidence_status") or {}).get("attachment_reference_exists")),
            "why_blocked": [item["blocker_id"] for item in blockers],
        },
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "bridged_capabilities": {
            "from_reconciliation_schema": reconciliation.get("schema_version") or RECONCILIATION_SCHEMA_VERSION,
            "keep_and_bridge": [
                "cassandra_email_triage.py",
                "cassandra_send_status_dry_run.py",
                "cassandra_governed_review_packet_request.py",
                "guardian_hitl_authority_reconciliation.py",
                "templates/agent/*.json",
            ],
            "keep_as_reference": ["cassandra_outreach.py", "cassandra_brain.py email/calendar intent paths"],
            "blocked": ["google_access_broker.py", "generic calendar cleanup", "unknown future email/calendar capability"],
        },
        "receipt_proof_status": {
            "draft_review_packet_created": True,
            "gmail_draft_created": False,
            "email_sent": False,
            "live_account_accessed": False,
            "pdf_attached": False,
            "final_send_remains_blocked": not send_eligible,
            "approval_specific_action_scoped": True,
            "generic_send_authority_added": False,
            "unknown_capability_fails_closed": True,
        },
        "next_safe_move": "Review the packet only; record Coupa proof and Excel match proof through governed evidence rails before any final-send approval lane.",
        "next_recommended_lane": NEXT_RECOMMENDED_LANE,
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_cassandra_draft_review_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Cassandra Draft Review Packet v0",
        "",
        "Status:",
        f"- Workflow: `{payload['workflow_name']}`.",
        f"- Draft status: `{payload['draft_status']}`.",
        f"- Final send gate: `{payload['send_eligibility']['final_send_gate_state']}`.",
        "- Gmail draft created: `false`.",
        "- Email sent: `false`.",
        "- Live account accessed: `false`.",
        "",
        "## Operator Meaning",
        "- Cassandra can prepare a review-only companion invoice email packet for Capital Hilton.",
        "- This packet is not a Gmail draft, not a send, and not an approval receipt.",
        "",
        "## Draft Preview",
        f"- Subject: {payload['subject']['subject_text']}",
        f"- Body summary: {payload['body']['body_summary']}",
        "- Recipients are role labels only; no raw private contact expansion happened.",
        "",
        "## Required Proof Before Final Send",
    ]
    for proof in payload["required_proofs"]:
        lines.append(f"- {proof['label']}: present_now=`{str(proof['present_now']).lower()}`; status=`{proof['proof_status']}`.")
    lines.extend([
        "",
        "## Blockers",
    ])
    if payload["blockers"]:
        for blocker in payload["blockers"]:
            lines.append(f"- {blocker['description']} (`{blocker['blocker_id']}`).")
    else:
        lines.append("- No proof blockers modeled, but execution still requires future Guardian/send controls.")
    lines.extend([
        "",
        "## Authority Boundary",
        "- No Gmail draft creation, email send, live Gmail read, OAuth, browser automation, PDF attachment, spreadsheet mutation, or runtime authority was added.",
        "- Future approval must be specific to one draft, one attachment, and one workflow scope.",
        "",
        "## Next Safe Move",
        f"- {payload['next_safe_move']}",
    ])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class DraftReviewPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    draft_id: str
    packet_status: str
    final_send_gate_state: str
    gmail_draft_created: bool
    email_sent: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


def export_cassandra_draft_review_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    reconciliation_json: str | Path = DEFAULT_RECONCILIATION_PATH,
    proof_capture_json: str | Path = DEFAULT_PROOF_CAPTURE_PATH,
    send_gate_json: str | Path = DEFAULT_SEND_GATE_PATH,
    generated_at: str | None = None,
) -> DraftReviewPacketExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_cassandra_draft_review_packet(
        reconciliation_json=reconciliation_json,
        proof_capture_json=proof_capture_json,
        send_gate_json=send_gate_json,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cassandra_draft_review_packet(payload), encoding="utf-8")
    return DraftReviewPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        draft_id=payload["draft_id"],
        packet_status=payload["packet_status"],
        final_send_gate_state=payload["send_eligibility"]["final_send_gate_state"],
        gmail_draft_created=payload["gmail_draft_created"],
        email_sent=payload["email_sent"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        approval_authority_added=payload["approval_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra draft review packet read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--reconciliation-json", default=str(DEFAULT_RECONCILIATION_PATH), help="Capability reconciliation read-model path.")
    parser.add_argument("--proof-capture-json", default=str(DEFAULT_PROOF_CAPTURE_PATH), help="Capital Hilton proof capture read-model path.")
    parser.add_argument("--send-gate-json", default=str(DEFAULT_SEND_GATE_PATH), help="Capital Hilton send gate read-model path.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_cassandra_draft_review_packet(
        repo_root=args.repo_root,
        export_root=args.export_root,
        reconciliation_json=args.reconciliation_json,
        proof_capture_json=args.proof_capture_json,
        send_gate_json=args.send_gate_json,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            "Cassandra draft review packet exported: "
            f"{result.json_path} and {result.operator_path} "
            f"(status={result.packet_status}; final_send_gate={result.final_send_gate_state})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
