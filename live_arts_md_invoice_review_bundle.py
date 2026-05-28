"""Live Arts MD simple invoice review bundle v0.

This module proves the reusable email-invoice rails for a non-Coupa client.
It does not read workbook cells, generate/export invoices, send email, access
Gmail/Coupa/browser, post ledgers, or mutate production business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workflow_framework as workflow
import client_invoice_workbook_registry
import local_artifact_reference


SCHEMA_VERSION = "live_arts_md_invoice_review_bundle_v0"
READ_MODEL_ID = "live_arts_md_invoice_review_bundle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T00:00:00+00:00"

CLIENT_REF = "live_arts_md"
CLIENT_DISPLAY_NAME = "Live Arts MD"
WORKFLOW_REF = "live_arts_md_invoice_workflow"
EXPECTED_WORKBOOK_NAME = "Invoice Live Arts MD! Running.xlsx"

ALLOWED_ARTIFACT_EXTENSIONS = (".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg")

AUTHORITY_BOUNDARY = {
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "invoice_generation_performed": False,
    "pdf_export_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "coupa_access_performed": False,
    "browser_automation_performed": False,
    "ledger_posting_performed": False,
    "production_business_mutation_performed": False,
    "physical_deletion_performed": False,
    "external_action_performed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _workbook_records(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    records: list[dict[str, Any]] = []
    for key in ("active_record", "candidate_record", "existing_record"):
        item = payload.get(key)
        if isinstance(item, Mapping):
            records.append(dict(item))
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    for item in registry.get("client_records") or ():
        if isinstance(item, Mapping):
            records.append(dict(item))
    filtered = [
        record
        for record in records
        if record.get("client_ref") == CLIENT_REF and record.get("workflow_ref") == WORKFLOW_REF
    ]
    deduped: dict[str, dict[str, Any]] = {}
    for record in filtered:
        deduped[str(record.get("workbook_ref") or _short_hash(record))] = record
    return tuple(deduped.values())


def inspect_source_workbook_state(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = (
        workbook_registry_payload
        if workbook_registry_payload is not None
        else client_invoice_workbook_registry.load_existing_payload()
    )
    records = _workbook_records(payload)
    confirmed = next((record for record in records if record.get("workbook_status") == "WORKBOOK_CONFIRMED"), None)
    candidate = confirmed or (records[0] if records else None)
    status = "CONFIRMED" if confirmed else "CANDIDATE_ONLY" if candidate else "SOURCE_WORKBOOK_REQUIRED"
    return {
        "status": status,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "expected_display_name": EXPECTED_WORKBOOK_NAME,
        "workbook_ref": candidate.get("workbook_ref") if candidate else None,
        "workbook_display_name": candidate.get("workbook_display_name") if candidate else None,
        "workbook_path_ref": candidate.get("workbook_path_ref") if candidate else None,
        "approved_for_metadata_read": bool(candidate.get("approved_for_metadata_read")) if candidate else False,
        "approved_for_cell_read": False,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "next_action": "Choose the Live Arts MD source workbook."
        if not confirmed
        else "Select the Live Arts MD invoice page/period.",
    }


def validate_operator_invoice_artifact_metadata(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    result: dict[str, Any] = {
        "path": path.as_posix(),
        "exists": path.exists(),
        "extension": suffix,
        "allowed_extension": suffix in ALLOWED_ARTIFACT_EXTENSIONS,
        "file_size": None,
        "sha256": None,
        "metadata_only": True,
        "body_read": False,
        "content_extracted": False,
    }
    if suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
        result["status"] = "BLOCKED_EXTENSION_NOT_ALLOWED"
        return result
    if not path.exists() or not path.is_file():
        result["status"] = "BLOCKED_ARTIFACT_PATH_NOT_FOUND"
        return result
    data = path.read_bytes()
    result["file_size"] = len(data)
    result["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    result["status"] = "METADATA_VALID"
    return result


def _artifact_state(
    *,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
) -> dict[str, Any]:
    payload = (
        artifact_reference_payload
        if artifact_reference_payload is not None
        else local_artifact_reference.load_existing_payload()
    )
    approved = local_artifact_reference.find_approved_readable_artifact(
        payload,
        world_ref="finance",
        workflow_ref=WORKFLOW_REF,
        client_ref=CLIENT_REF,
        artifact_kind="invoice_artifact",
        intended_use="client_invoice_email_attachment",
    )
    if approved:
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE",
            "artifact_ref": approved.get("artifact_ref"),
            "path_ref": approved.get("pc_path") or approved.get("approved_path_ref"),
            "hash": approved.get("sha256") or approved.get("artifact_hash"),
            "attachment_ready": False,
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata_only": True,
        }
    if operator_artifact_path:
        metadata = validate_operator_invoice_artifact_metadata(Path(operator_artifact_path))
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
            if metadata["status"] == "METADATA_VALID"
            else metadata["status"],
            "artifact_ref": f"operator_invoice_artifact_candidate:{_short_hash(operator_artifact_path, metadata.get('sha256'))}",
            "path_ref": operator_artifact_path,
            "hash": metadata.get("sha256"),
            "attachment_ready": False,
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata": metadata,
            "metadata_only": True,
        }
    return {
        "status": "ARTIFACT_REQUIRED",
        "artifact_ref": None,
        "path_ref": None,
        "hash": None,
        "attachment_ready": False,
        "candidate_only": False,
        "receipt_required_for_attachment_ready": "operator_provided_invoice_artifact_linked_candidate_receipt",
        "next_action": "Export selected invoice page manually, then attach it here.",
    }


def _action(
    action_kind: str,
    label: str,
    *,
    enabled: bool,
    intended_use: str,
    disabled_reason: str | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "action_kind": action_kind,
        "intended_use": intended_use,
        "no_external_action": True,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "coupa_submit_allowed": False,
        "physical_deletion_allowed": False,
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    return {
        "action_ref": f"live_arts_md_invoice_action:{_short_hash(action_kind, label)}",
        "action_kind": action_kind,
        "label": label,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "operator_visible_message": label,
        "hidden_request_payload": payload,
    }


def build_live_arts_md_bundle(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = {str(receipt) for receipt in present_receipts}
    recipe = workflow.recipes_by_client_ref()[CLIENT_REF]
    source = inspect_source_workbook_state(workbook_registry_payload=workbook_registry_payload)
    source_confirmed = source["status"] == "CONFIRMED" or "source_workbook_reference_confirmed_receipt" in receipts
    invoice_selected = "invoice_record_selection_operator_confirmed_receipt" in receipts
    artifact = _artifact_state(
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
    )
    artifact_candidate = artifact["status"] == "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
    attachment_ready = "invoice_attachment_confirmed_receipt" in receipts
    recipient_confirmed = "recipient_confirmation_receipt" in receipts
    clara_ready = artifact_candidate or attachment_ready
    approval_ready = all(
        (
            source_confirmed,
            invoice_selected,
            artifact_candidate,
            attachment_ready,
            recipient_confirmed,
            "guardian_approval_request_receipt" in receipts,
        )
    )
    blockers = []
    if not source_confirmed:
        blockers.append("Choose the Live Arts MD source workbook.")
    if source_confirmed and not invoice_selected:
        blockers.append("Select the Live Arts MD invoice page/period.")
    if not artifact_candidate:
        blockers.append("Attach or link the generated Live Arts MD invoice artifact.")
    if artifact_candidate and not attachment_ready:
        blockers.append("Confirm the invoice artifact as the email attachment.")
    if not recipient_confirmed:
        blockers.append("Confirm the Live Arts MD recipient/contact.")
    if not approval_ready:
        blockers.append("Approval/send remains disabled until receipts exist.")

    clara_body = (
        "Hi [Live Arts MD contact],\n\n"
        "I’m preparing the Live Arts MD invoice for review. I’ll send the invoice once the attachment "
        "and recipient are confirmed.\n\n"
        "Best,\nWinship"
    )
    if attachment_ready:
        clara_body = (
            "Hi [Live Arts MD contact],\n\n"
            "Attached is the Live Arts MD invoice for review. Please let me know if you need anything else.\n\n"
            "Best,\nWinship"
        )

    source_action = _action(
        "choose_source_workbook",
        "Choose Live Arts MD source workbook",
        enabled=not source_confirmed,
        intended_use="choose_source_workbook_reference",
        disabled_reason=None if not source_confirmed else "Source workbook is already confirmed.",
        extra_payload={"expected_workbook_display_name": EXPECTED_WORKBOOK_NAME},
    )
    selection_action = _action(
        "start_invoice_record_selection",
        "Select invoice page",
        enabled=source_confirmed,
        intended_use="select_invoice_record_or_period",
        disabled_reason=None if source_confirmed else "Choose the source workbook first.",
    )
    artifact_action = _action(
        "attach_generated_invoice_artifact",
        "Attach generated invoice artifact",
        enabled=invoice_selected,
        intended_use="manual_operator_link_generated_invoice_artifact",
        disabled_reason=None if invoice_selected else "Select the invoice page/period first.",
        extra_payload={"allowed_extensions": ALLOWED_ARTIFACT_EXTENSIONS},
    )
    recipient_action = _action(
        "review_and_confirm_recipients",
        "Confirm recipient",
        enabled=True,
        intended_use="review_and_confirm_recipients",
    )
    send_action = _action(
        "prepare_manual_send_package",
        "Prepare manual send package",
        enabled=approval_ready,
        intended_use="prepare_manual_send_package",
        disabled_reason=None if approval_ready else "Attachment, recipient, and approval receipts are required first.",
    )
    primary_blocker_action = (
        source_action
        if not source_confirmed
        else selection_action
        if not invoice_selected
        else artifact_action
        if not artifact_candidate
        else recipient_action
    )

    timeline = (
        {
            "step_ref": "live_arts_md_step:source_workbook",
            "title": "Source workbook",
            "status": "COMPLETE" if source_confirmed else "NEEDS_ACTION",
            "operator_summary": source["next_action"],
            "primary_action": source_action,
            "required_receipts": ("source_workbook_reference_confirmed_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:invoice_page_period",
            "title": "Invoice page/period",
            "status": "COMPLETE" if invoice_selected else "NEEDS_ACTION" if source_confirmed else "BLOCKED",
            "operator_summary": "Select the invoice page/period from the source workbook.",
            "primary_action": selection_action,
            "required_receipts": ("invoice_record_selection_operator_confirmed_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:invoice_artifact",
            "title": "Invoice artifact",
            "status": "CANDIDATE" if artifact_candidate else "NEEDS_ACTION" if invoice_selected else "BLOCKED",
            "operator_summary": "Artifact is candidate-only until attachment confirmation receipt exists.",
            "primary_action": artifact_action,
            "required_receipts": (
                "operator_provided_invoice_artifact_linked_candidate_receipt",
                "invoice_attachment_confirmed_receipt",
            ),
        },
        {
            "step_ref": "live_arts_md_step:clara_draft",
            "title": "Clara draft",
            "status": "DRAFT_ONLY" if clara_ready else "PLACEHOLDER_DRAFT",
            "operator_summary": "Draft only. Nothing was sent.",
            "primary_action": None,
            "required_receipts": ("clara_email_draft_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:recipient_send",
            "title": "Recipient and send readiness",
            "status": "READY" if approval_ready else "BLOCKED",
            "operator_summary": "Manual send package can be prepared only after attachment, recipient, and approval receipts.",
            "primary_action": send_action,
            "required_receipts": ("recipient_confirmation_receipt", "operator_approval_receipt", "email_send_receipt"),
        },
        {
            "step_ref": "live_arts_md_step:payment_watch",
            "title": "Payment watch",
            "status": "READINESS_ONLY",
            "operator_summary": "Payment watch pattern exists, but payment is not active or expected until send evidence exists.",
            "primary_action": None,
            "required_receipts": ("email_send_receipt", "payment_watch_configured_receipt"),
        },
    )

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": "invoice_review_bundle:live_arts_md:v0",
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": WORKFLOW_REF,
        "recipe_ref": recipe["workflow_ref"],
        "status": "SIMPLE_EMAIL_INVOICE_REVIEW",
        "selected_rails": tuple(item["rail_ref"] for item in recipe["selected_rails"]),
        "rails_not_selected_by_default": ("supplier_portal_rail", "purchase_order_rail"),
        "supplier_portal_invoice_submission": {
            "required": False,
            "supplier_portal_required": False,
            "supplier_portal_provider": None,
            "portal_submission_proof_required": False,
            "purchase_order_required": False,
            "status": "NOT_REQUIRED_BY_RECIPE",
        },
        "source_workbook": source,
        "invoice_selection": {
            "status": "OPERATOR_CONFIRMED" if invoice_selected else "NEEDS_SELECTION" if source_confirmed else "BLOCKED_NEEDS_SOURCE_WORKBOOK",
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "primary_action": selection_action,
        },
        "invoice_artifact": artifact,
        "clara_email_draft": {
            "selected_voice": "CLARA",
            "draft_only": True,
            "sent": False,
            "subject": "Live Arts MD invoice",
            "body": clara_body,
            "attachment_claim": "attachment confirmed" if attachment_ready else "attachment not ready yet",
        },
        "recipient_state": {
            "status": "CONFIRMED" if recipient_confirmed else "RECIPIENT_INFO_REQUIRED",
            "recipient_email_invented": False,
            "primary_action": recipient_action,
        },
        "send_readiness": {
            "email_send_rail_exists": False,
            "manual_send_package_status": "MANUAL_SEND_PACKAGE_READY" if approval_ready else "BLOCKED_PREREQUISITES",
            "email_send_approval_required": True,
            "email_send_execution_receipt_required": True,
            "sent_receipt_confirmed": "email_send_receipt" in receipts,
            "primary_action": send_action,
        },
        "payment_watch": {
            "payment_watch_status": "READINESS_ONLY",
            "client_ref": CLIENT_REF,
            "invoice_ref": artifact.get("artifact_ref"),
            "expected_amount": None,
            "expected_window": None,
            "bank_ledger_match_required": True,
            "ledger_posting_allowed": False,
        },
        "approval_footer": {
            "approval_ready": approval_ready,
            "approval_disabled_reasons": tuple(blockers),
        },
        "blockers": tuple(blockers),
        "next_safe_move": blockers[0] if blockers else "Prepare manual send package after approval receipts.",
        "actionable_blockers": (
            (
                {
                    "blocker_ref": f"live_arts_md_blocker:{_short_hash(blockers[0])}",
                    "operator_summary": blockers[0],
                    "primary_action": primary_blocker_action,
                },
            )
            if blockers
            else ()
        ),
        "proof_timeline": timeline,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "generated_at": generated_at,
        "machine_proof": {
            "live_arts_md_does_not_require_coupa": True,
            "live_arts_md_does_not_require_po": True,
            "uses_reusable_simple_invoice_rails": True,
            "clara_draft_only": True,
            "no_recipient_email_invented": True,
            "artifact_candidate_not_attachment_ready": artifact.get("attachment_ready") is False,
            "approval_send_disabled_without_receipts": approval_ready is False,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    bundle["machine_proof"]["content_hash"] = _content_hash(bundle)
    return bundle


def build_payload(
    *,
    generated_at: str | None = None,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    bundle = build_live_arts_md_bundle(
        generated_at=generated_at,
        workbook_registry_payload=workbook_registry_payload,
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
        present_receipts=present_receipts,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or DEFAULT_GENERATED_AT,
        "live_arts_md_bundle": bundle,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "live_arts_md_bundle_present": True,
            "bridge_safe": True,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": _content_hash(bundle),
        },
    }


def format_operator(payload: Mapping[str, Any]) -> str:
    bundle = payload["live_arts_md_bundle"]
    lines = [
        "# Live Arts MD Invoice Review Bundle",
        "",
        f"- Status: `{bundle['status']}`",
        f"- Next safe move: {bundle['next_safe_move']}",
        f"- Source workbook: `{bundle['source_workbook']['status']}`",
        f"- Invoice page/period: `{bundle['invoice_selection']['status']}`",
        f"- Artifact: `{bundle['invoice_artifact']['status']}`",
        f"- Clara draft: `{bundle['clara_email_draft']['selected_voice']}` draft-only",
        f"- Recipient state: `{bundle['recipient_state']['status']}`",
        f"- Manual send package: `{bundle['send_readiness']['manual_send_package_status']}`",
        f"- Payment watch: `{bundle['payment_watch']['payment_watch_status']}`",
        "",
        "No email, Coupa, browser, ledger, workbook body/cell read, generation, export, or production action occurred.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Path, Path, Path | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return json_path, operator_path, bridge_path


def export_bundle(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    json_path, operator_path, bridge_path = write_exports(
        payload,
        export_root,
        bridge_export_root=bridge_export_root,
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "source_workbook_status": payload["live_arts_md_bundle"]["source_workbook"]["status"],
        "next_safe_move": payload["live_arts_md_bundle"]["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Live Arts MD simple invoice review bundle.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_bundle(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
