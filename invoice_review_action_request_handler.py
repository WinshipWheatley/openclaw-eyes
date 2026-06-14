"""Invoice review guided action request handler v0.

Consumes invoice review bundle action payloads and returns guided fix-path
readbacks only. It does not execute external actions, open Coupa/browser/Gmail,
send email, generate/export invoices, read workbook cells, or mutate production
state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import invoice_review_bundle
import invoice_review_state_machine
import live_arts_md_invoice_review_bundle
import live_arts_md_workbook_handoff
import operator_action_event_journal


READ_MODEL_ID = "invoice_review_action_request_receipt"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SCHEMA_VERSION = "invoice_review_action_request_handler_v0"

SUPPORTED_ACTIONS = {
    "confirm_source_workbook_reference",
    "replace_source_workbook_reference",
    "operator_reported_wrong_source_workbook",
    "start_invoice_record_selection",
    "regenerate_or_link_invoice_artifact",
    "request_supplier_portal_submission_proof",
    "request_coupa_submission_proof",
    "review_and_confirm_recipients",
    "show_approval_prerequisites",
    "review_clara_draft_prerequisites",
    "edit_clara_draft_request",
    "prepare_send_approval_request",
    "setup_payment_watch_after_submission",
    "explain_invoice_review",
    "confirm_invoice_review_candidate",
    "open_invoice_workbook_candidate",
    "select_invoice_candidate",
    "select_live_arts_md_invoice_candidate",
    "prepare_selected_invoice_pdf_artifact",
    "approve_pdf_candidate",
    "reject_pdf_candidate",
}

PDF_CANDIDATE_DECISION_ACTIONS = {
    "approve_pdf_candidate",
    "reject_pdf_candidate",
}

PDF_CANDIDATE_DECISION_RECEIPT_EXPORT_NAME = "selected_invoice_pdf_candidate_review_decision_receipt.json"

EXTERNAL_AUTHORITY_GRANT_FIELDS = (
    "browser_access_allowed",
    "browser_action",
    "browser_automation_allowed",
    "coupa_access_allowed",
    "coupa_submit_allowed",
    "email_send_allowed",
    "external_action_allowed",
    "gmail_access_allowed",
    "ledger_post_allowed",
    "ledger_posting_allowed",
    "portal_access_allowed",
    "portal_submission_action_allowed",
    "production_mutation_allowed",
    "supplier_portal_submit_allowed",
)

DECISION_FORBIDDEN_TRUE_FIELDS = (
    *EXTERNAL_AUTHORITY_GRANT_FIELDS,
    "attachment_ready",
    "approval_ready",
    "paid",
    "sent",
)

CLIENT_BUNDLES = {
    "capital_hilton": {
        "client_display_name": "Capital Hilton",
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "bundle_id": invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
    },
    "live_arts_md": {
        "client_display_name": "Live Arts MD",
        "workflow_ref": live_arts_md_invoice_review_bundle.WORKFLOW_REF,
        "bundle_id": "invoice_review_bundle:live_arts_md:v0",
    },
}

REQUEST_KINDS = {
    "INVOICE_REVIEW_ACTION_REQUEST",
    "INVOICE_REVIEW_ACTION_RESULT",
    "INVOICE_REVIEW_GUIDED_ACTION_REQUEST",
    "invoice_review_guided_action_request",
}

AUTHORITY_BOUNDARY = {
    "coupa_browser_automation_allowed": False,
    "supplier_portal_submit_allowed": False,
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "ledger_posting_allowed": False,
    "invoice_generation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "production_mutation_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((json_safe(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return str(value)


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _bridge_path_from_mac_path(path_text: str) -> str | None:
    path_text = str(path_text or "").strip()
    if path_text.startswith("/Volumes/openclaw_e/"):
        return path_text.replace("/Volumes/openclaw_e/", "/mnt/e/openclaw/", 1)
    return None


def _selected_invoice_candidate_from_payload(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    invoice_id = str(payload.get("invoice_id") or payload.get("candidate_ref") or "")
    selected_print_areas = payload.get("selected_print_areas")
    if isinstance(selected_print_areas, str):
        selected_print_areas = (selected_print_areas,)
    if isinstance(selected_print_areas, list):
        selected_print_areas = tuple(selected_print_areas)
    if isinstance(selected_print_areas, tuple):
        selected_print_areas = tuple(str(item) for item in selected_print_areas if str(item).strip())
    elif selected_print_areas is None:
        selected_print_areas = tuple()

    candidate: dict[str, Any] = {
        "invoice_id": invoice_id or "",
        "sheet_label": str(payload.get("selected_sheet_label") or payload.get("sheet_label") or ""),
        "work_type": str(payload.get("work_type") or ""),
        "amount": payload.get("amount"),
        "operator_provided_ranges": selected_print_areas,
    }
    if not candidate["invoice_id"] and not candidate["sheet_label"]:
        return None
    if candidate["amount"] is None and isinstance(payload.get("amount"), (int, float)):
        candidate["amount"] = payload.get("amount")
    return candidate


def _live_arts_candidate_from_invoice_id(invoice_id: str) -> dict[str, Any] | None:
    target = str(invoice_id or "").strip()
    if not target:
        return None
    for candidate in live_arts_md_workbook_handoff.invoice_candidates():
        if str(candidate.get("invoice_id") or "") == target:
            selected = dict(candidate)
            selected["selection_status"] = "OPERATOR_CONFIRMED"
            selected["selection_source"] = "selected_invoice_pdf_export_completed_candidate_receipt"
            return selected
    return None


def _action_payload(raw_request: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw_request.get("hidden_request_payload")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        for key in (
            "request_id",
            "source_request_id",
            "idempotency_key",
            "payload_hash",
            "created_at",
            "authority_boundary",
            "source_request_filename",
        ):
            if key in raw_request and key not in merged:
                merged[key] = raw_request[key]
        return merged
    return raw_request


def is_invoice_review_action_request(raw_request: Mapping[str, Any]) -> bool:
    payload = _action_payload(raw_request)
    request_type = str(payload.get("request_type") or payload.get("type") or raw_request.get("request_type") or raw_request.get("type") or "")
    action_kind = str(payload.get("action_kind") or raw_request.get("action_kind") or "")
    intended_use = str(payload.get("intended_use") or raw_request.get("intended_use") or "")
    return (
        request_type in REQUEST_KINDS
        or action_kind in SUPPORTED_ACTIONS
        or intended_use in SUPPORTED_ACTIONS
    )


def is_invoice_record_selection_result(raw_request: Mapping[str, Any]) -> bool:
    payload = _action_payload(raw_request)
    request_type = str(payload.get("request_type") or payload.get("type") or raw_request.get("request_type") or raw_request.get("type") or "")
    intended_use = str(payload.get("intended_use") or raw_request.get("intended_use") or "")
    return request_type in {"LOCAL_SURFACE_RESULT", "INVOICE_REVIEW_ACTION_RESULT"} and intended_use == "confirm_invoice_record_selection"


def is_source_workbook_selection_result(raw_request: Mapping[str, Any]) -> bool:
    payload = _action_payload(raw_request)
    request_type = str(payload.get("request_type") or payload.get("type") or raw_request.get("request_type") or raw_request.get("type") or "")
    intended_use = str(payload.get("intended_use") or raw_request.get("intended_use") or "")
    return request_type in {
        "LOCAL_SURFACE_RESULT",
        "INVOICE_REVIEW_ACTION_RESULT",
        "OPERATOR_CORRECTION",
        "OPERATOR_CORRECTION_TO_PENDING_REQUEST",
    } and intended_use in {
        "confirm_source_workbook_reference",
        "replace_source_workbook_reference_result",
    }


def is_selected_invoice_pdf_export_completed_candidate_result(raw_request: Mapping[str, Any]) -> bool:
    payload = _action_payload(raw_request)
    request_type = str(
        payload.get("request_type")
        or payload.get("type")
        or raw_request.get("request_type")
        or raw_request.get("type")
        or ""
    )
    intended_use = str(payload.get("intended_use") or raw_request.get("intended_use") or "")
    return request_type in {"LOCAL_SURFACE_RESULT", "INVOICE_REVIEW_ACTION_RESULT"} and intended_use == "selected_invoice_pdf_export_completed_candidate"


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _mapping_value(payload: Mapping[str, Any], key: str) -> Any:
    value = payload.get(key)
    nested = payload.get("payload")
    if value in (None, "") and isinstance(nested, Mapping):
        value = nested.get(key)
    return value


def _read_json_if_exists(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _true_decision_authority_paths(payload: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for field in DECISION_FORBIDDEN_TRUE_FIELDS:
        if _mapping_value(payload, field) is True:
            paths.append(field)
    for container_name in ("authority_boundary", "event_authority_boundary", "safety_flags"):
        container = payload.get(container_name)
        if not isinstance(container, Mapping):
            continue
        for field in DECISION_FORBIDDEN_TRUE_FIELDS:
            if container.get(field) is True:
                paths.append(f"{container_name}.{field}")
    return tuple(dict.fromkeys(paths))


def _no_external_authority(payload: Mapping[str, Any], *, action_kind: str) -> bool:
    true_grants = _true_decision_authority_paths(payload)
    if action_kind in PDF_CANDIDATE_DECISION_ACTIONS:
        return not true_grants
    return payload.get("no_external_action") is True and not true_grants


def _bundle_review_from_payload(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    bundle = payload.get("live_arts_md_bundle", payload)
    if not isinstance(bundle, Mapping):
        return None
    artifact = bundle.get("invoice_artifact")
    if not isinstance(artifact, Mapping):
        return None
    review = artifact.get("artifact_candidate_review")
    return review if isinstance(review, Mapping) else None


def _load_live_arts_pdf_candidate_review(
    *,
    export_root: Path,
    bridge_export_root: Path | None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    paths: list[Path] = [export_root / live_arts_md_invoice_review_bundle.JSON_EXPORT_NAME]
    if bridge_export_root is not None:
        paths.append(bridge_export_root / live_arts_md_invoice_review_bundle.JSON_EXPORT_NAME)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, Mapping):
            continue
        review = _bundle_review_from_payload(payload)
        if review is not None:
            return review, path.as_posix()
    return None, None


def _pdf_candidate_decision_validation_errors(
    payload: Mapping[str, Any],
    *,
    action_kind: str,
    active_review: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    errors: list[str] = []
    true_grants = _true_decision_authority_paths(payload)
    errors.extend(f"EXTERNAL_AUTHORITY_GRANTED:{path}" for path in true_grants)

    invoice_id = str(_mapping_value(payload, "invoice_id") or "").strip()
    if invoice_id != "2026-1001":
        errors.append("WRONG_INVOICE_ID")
    if _mapping_value(payload, "operator_visual_review") is not True:
        errors.append("OPERATOR_VISUAL_REVIEW_REQUIRED")

    observed = _positive_int(_mapping_value(payload, "observed_page_count") or _mapping_value(payload, "page_count"))
    expected = _positive_int(
        _mapping_value(payload, "expected_page_count") or _mapping_value(payload, "expected_output_page_count")
    )
    if observed is None:
        errors.append("MISSING_OR_INVALID_OBSERVED_PAGE_COUNT")
    if expected is None:
        errors.append("MISSING_OR_INVALID_EXPECTED_PAGE_COUNT")

    if active_review is None:
        errors.append("UNKNOWN_OR_UNTRUSTED_CANDIDATE")
        active_sha = ""
        active_ref = ""
    else:
        active_sha = str(active_review.get("sha256") or active_review.get("observed_sha256") or "").removeprefix("sha256:")
        active_ref = str(active_review.get("candidate_ref") or "")
        active_invoice_id = str(active_review.get("invoice_id") or active_review.get("selected_invoice_id") or "")
        active_observed = _positive_int(active_review.get("observed_page_count") or active_review.get("page_count"))
        active_expected = _positive_int(active_review.get("expected_page_count"))
        if active_invoice_id and invoice_id and active_invoice_id != invoice_id:
            errors.append("CANDIDATE_INVOICE_MISMATCH")
        if active_observed is not None and observed is not None and active_observed != observed:
            errors.append("CANDIDATE_PAGE_COUNT_MISMATCH")
        if active_expected is not None and expected is not None and active_expected != expected:
            errors.append("CANDIDATE_EXPECTED_PAGE_COUNT_MISMATCH")

    candidate_ref = str(_mapping_value(payload, "candidate_ref") or "").strip()
    candidate_sha = str(_mapping_value(payload, "candidate_sha256") or _mapping_value(payload, "sha256") or "").removeprefix("sha256:")
    if active_ref and candidate_ref and candidate_ref != active_ref:
        errors.append("CANDIDATE_REF_MISMATCH")
    if candidate_sha and active_sha and candidate_sha != active_sha:
        errors.append("CANDIDATE_SHA_MISMATCH")

    if action_kind == "approve_pdf_candidate":
        if not candidate_sha:
            errors.append("MISSING_CANDIDATE_SHA256")
        if active_review is not None:
            if active_review.get("candidate_valid_for_operator_review") is not True:
                errors.append("CANDIDATE_NOT_VALID_FOR_OPERATOR_REVIEW")
            if str(active_review.get("artifact_review_status") or active_review.get("status") or "") != "OPERATOR_REVIEW_REQUIRED":
                errors.append("CANDIDATE_NOT_OPERATOR_REVIEW_REQUIRED")
        if observed is not None and expected is not None and (observed != expected or observed != 1):
            errors.append("PDF_CANDIDATE_PAGE_COUNT_MISMATCH")
    elif action_kind == "reject_pdf_candidate":
        if not str(_mapping_value(payload, "reason_code") or "").strip():
            errors.append("MISSING_REASON_CODE")
        desired_page_known = _mapping_value(payload, "desired_page_known")
        if desired_page_known not in (None, True, False):
            errors.append("INVALID_DESIRED_PAGE_KNOWN")
        if desired_page_known is False and _mapping_value(payload, "observed_desired_pdf_page") not in (None, ""):
            errors.append("DESIRED_PAGE_UNKNOWN_BUT_OBSERVED_DESIRED_PDF_PAGE_PRESENT")
        if not candidate_sha and not candidate_ref:
            errors.append("MISSING_CANDIDATE_IDENTIFIER")
    else:
        errors.append("UNSUPPORTED_PDF_CANDIDATE_DECISION")

    return tuple(dict.fromkeys(errors))


def _write_pdf_candidate_decision_receipt(
    receipt: Mapping[str, Any],
    *,
    export_root: Path,
    bridge_export_root: Path | None,
) -> tuple[str, str | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    receipt_path = export_root / PDF_CANDIDATE_DECISION_RECEIPT_EXPORT_NAME
    receipt_path.write_text(stable_json(receipt), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_receipt_path = bridge_export_root / PDF_CANDIDATE_DECISION_RECEIPT_EXPORT_NAME
        bridge_receipt_path.write_text(stable_json(receipt), encoding="utf-8")
        bridge_path = bridge_receipt_path.as_posix()
    return receipt_path.as_posix(), bridge_path


def _client_context(payload: Mapping[str, Any], raw_request: Mapping[str, Any] | None = None) -> dict[str, str]:
    raw_request = raw_request or {}
    client_ref = str(payload.get("client_ref") or raw_request.get("client_ref") or "capital_hilton")
    context = CLIENT_BUNDLES.get(client_ref, CLIENT_BUNDLES["capital_hilton"])
    return {
        "client_ref": client_ref if client_ref in CLIENT_BUNDLES else "capital_hilton",
        "client_display_name": str(context["client_display_name"]),
        "workflow_ref": str(payload.get("source_workflow_id") or payload.get("workflow_ref") or raw_request.get("workflow_ref") or context["workflow_ref"]),
        "bundle_id": str(payload.get("source_bundle_id") or raw_request.get("bundle_id") or raw_request.get("source_bundle_id") or context["bundle_id"]),
    }


def _current_action_index(client_ref: str = "capital_hilton") -> dict[str, dict[str, Any]]:
    bundle = (
        live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
        if client_ref == "live_arts_md"
        else invoice_review_bundle.build_capital_hilton_bundle()
    )
    actions: dict[str, dict[str, Any]] = {}
    for action in bundle.get("correction_actions") or ():
        if isinstance(action, Mapping):
            _remember_action(actions, action)
    for step in bundle.get("review_proof_timeline") or ():
        if not isinstance(step, Mapping):
            continue
        for action in (step.get("primary_action"), *(step.get("secondary_actions") or ())):
            if isinstance(action, Mapping):
                _remember_action(actions, action)
    for step in bundle.get("proof_timeline") or ():
        if not isinstance(step, Mapping):
            continue
        for action in (step.get("primary_action"), *(step.get("secondary_actions") or ())):
            if isinstance(action, Mapping):
                _remember_action(actions, action)
    return actions


def _remember_action(actions: dict[str, dict[str, Any]], action: Mapping[str, Any]) -> None:
    action_kind = str(action.get("action_kind") or "")
    existing = actions.get(action_kind)
    if existing is None or (not existing.get("enabled") and action.get("enabled")):
        actions[action_kind] = dict(action)


def _missing_prerequisites() -> tuple[str, ...]:
    bundle = invoice_review_bundle.build_capital_hilton_bundle()
    return tuple(bundle.get("approval_footer", {}).get("approval_disabled_reasons") or ())


def _invoice_record_selection_surface(
    *,
    request_id: str,
    action_kind: str,
    payload: Mapping[str, Any],
    context: Mapping[str, str],
) -> dict[str, Any] | None:
    if action_kind != "start_invoice_record_selection":
        return None
    client_ref = str(context["client_ref"])
    workflow_ref = str(context["workflow_ref"])
    bundle_id = str(context["bundle_id"])
    client_display_name = str(context["client_display_name"])
    if client_ref == "live_arts_md":
        register = live_arts_md_workbook_handoff.build_candidate_register()
        artifact: Mapping[str, Any] = {}
        operator_copy = "Let's select the Live Arts MD invoice page/period. No workbook cells will be read."
        completion_receipt = "live_arts_md_invoice_candidate_selected_receipt"
        artifact_receipt = "operator_provided_invoice_artifact_linked_candidate_receipt"
        invoice_candidate_context = {
            "candidate_register_ref": "generated/read_models/live_arts_md_invoice_candidate_register.json",
            "primary_next_action": register["primary_next_action"],
            "invoice_candidates": register["invoice_candidates"],
            "urgent_actions": register["urgent_actions"],
            "contact_ambiguity": register["contact_ambiguity"],
        }
        source_workbook_ref = register["source_workbook"]["source_workbook_ref"]
        source_workbook_mac_path = register["source_workbook"]["source_workbook_mac_path"]
    else:
        bundle = invoice_review_bundle.build_capital_hilton_bundle()
        artifact = bundle.get("excel_invoice_artifact") if isinstance(bundle.get("excel_invoice_artifact"), Mapping) else {}
        operator_copy = (
            "Let's pick the Capital Hilton invoice page/period. Choose the page or period from the running workbook "
            "so OpenClaw can link the generated invoice artifact correctly."
        )
        completion_receipt = "invoice_record_selected_receipt"
        artifact_receipt = "generated_invoice_artifact_linkage_receipt"
        invoice_candidate_context = None
        source_workbook_ref = payload.get("source_workbook_ref")
        source_workbook_mac_path = payload.get("source_workbook_mac_path")
    return {
        "surface_type": "SHOW_INVOICE_RECORD_SELECTION_PANEL",
        "surface_ref": f"invoice_record_selection_surface:{_short_hash(request_id, bundle_id)}",
        "source_request_id": request_id,
        "client_ref": client_ref,
        "client_display_name": client_display_name,
        "workflow_ref": workflow_ref,
        "bundle_id": bundle_id,
        "action_ref": "start_invoice_record_selection",
        "action_kind": "start_invoice_record_selection",
        "intended_use": "select_invoice_record_or_period",
        "operator_copy": operator_copy,
        "fields_requested": (
            "active_source_workbook",
            "client",
            "invoice_period",
            "invoice_page_sheet_record_label",
            "generated_candidate_disposition",
            "optional_notes",
        ),
        "generated_candidate_disposition_options": (
            "WRONG",
            "STALE",
            "REGENERATE_AFTER_SELECTION",
            "LINK_AFTER_SELECTION",
            "UNSURE",
        ),
        "source_workbook_ref": source_workbook_ref,
        "source_workbook_mac_path": source_workbook_mac_path,
        "invoice_candidate_context": invoice_candidate_context,
        "generated_candidate_ref": artifact.get("artifact_ref"),
        "generated_candidate_status": artifact.get("proof_status") or "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
        "generated_candidate_mac_path": artifact.get("mac_visible_ref"),
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "no_external_action": True,
        "completion_requires_future_operator_selection_result": True,
        "completion_receipt_required": completion_receipt,
        "artifact_linkage_receipt_required": artifact_receipt,
        "response_completion_behavior": "TERMINAL_AFTER_SURFACE_REQUEST_PUBLISHED",
    }


def _source_workbook_selection_surface(
    *,
    request_id: str,
    action_kind: str,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if action_kind != "replace_source_workbook_reference":
        return None
    context = _client_context(payload)
    client_ref = context["client_ref"]
    client_display_name = context["client_display_name"]
    workflow_ref = context["workflow_ref"]
    bundle_id = context["bundle_id"]
    return {
        "surface_type": "SHOW_SOURCE_WORKBOOK_SELECTION_PANEL",
        "surface_ref": f"source_workbook_selection_surface:{_short_hash(request_id, bundle_id)}",
        "source_request_id": request_id,
        "client_ref": client_ref,
        "client_display_name": client_display_name,
        "workflow_ref": workflow_ref,
        "bundle_id": bundle_id,
        "action_ref": "replace_source_workbook_reference",
        "action_kind": "replace_source_workbook_reference",
        "intended_use": "replace_source_workbook_reference",
        "result_intended_use": "confirm_source_workbook_reference",
        "operator_copy": f"Choose the {client_display_name} source workbook. No workbook cells will be read.",
        "allowed_file_types": ("xlsx",),
        "surface_actions": (
            {
                "action_kind": "confirm_source_workbook_reference",
                "label": f"Use this workbook as the {client_display_name} source workbook",
                "enabled": True,
                "intended_use": "confirm_source_workbook_reference",
                "no_external_action": True,
                "physical_deletion_allowed": False,
            },
            {
                "action_kind": "choose_different_source_workbook",
                "label": "Choose a different workbook",
                "enabled": True,
                "intended_use": "replace_source_workbook_reference_result",
                "no_external_action": True,
                "physical_deletion_allowed": False,
            },
            {
                "action_kind": "keep_previous_workbook_reference",
                "label": "Keep previous workbook reference",
                "enabled": True,
                "intended_use": "keep_previous_workbook_reference",
                "no_external_action": True,
                "physical_deletion_allowed": False,
            },
            {
                "action_kind": "cancel_source_workbook_replacement",
                "label": "Cancel",
                "enabled": True,
                "intended_use": "cancel_source_workbook_replacement",
                "no_external_action": True,
                "physical_deletion_allowed": False,
            },
        ),
        "candidate_workbooks": invoice_review_state_machine.source_workbook_candidates() if client_ref == "capital_hilton" else (),
        "current_wrong_workbook_ref": payload.get("current_wrong_workbook_ref") or payload.get("source_workbook_ref"),
        "physical_deletion_allowed": False,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "no_external_action": True,
        "completion_requires_future_operator_selection_result": True,
        "completion_receipt_required": "source_workbook_reference_confirmed_receipt",
        "response_completion_behavior": "TERMINAL_AFTER_SURFACE_REQUEST_PUBLISHED",
    }


def _operator_copy(action_kind: str, *, context: Mapping[str, str] | None = None) -> tuple[str, str, str, str, tuple[str, ...]]:
    context = context or CLIENT_BUNDLES["capital_hilton"]
    client_ref = str(context.get("client_ref") or "capital_hilton")
    missing = _missing_prerequisites()
    if action_kind == "start_invoice_record_selection":
        if client_ref == "live_arts_md":
            return (
                "Starting invoice page selection",
                "Let's select the Live Arts MD invoice page/period. No workbook cells will be read.",
                "OpenClaw needs the invoice candidate or page selection before it can link an invoice artifact.",
                "Choose the Live Arts MD invoice page or period in Mission Control.",
                ("live_arts_md_invoice_candidate_selected_receipt",),
            )
        return (
            "Starting invoice page selection",
            "Let's pick the Capital Hilton invoice page/period. Choose the page or period from the running workbook so OpenClaw can link the generated invoice artifact correctly.",
            "OpenClaw needs the invoice record before it can link the generated artifact.",
            "Choose the invoice page or period in Mission Control.",
            ("invoice_record_selection_request_receipt",),
        )
    if action_kind in {"request_supplier_portal_submission_proof", "request_coupa_submission_proof"}:
        return (
            "Starting Coupa proof step",
            "Coupa proof is required before this invoice can be treated as sent.",
            "Upload or provide the Coupa submission proof when it is available. Nothing will be submitted from this step.",
            "Provide supplier portal submission proof when available.",
            (
                "supplier_portal_proof_intake_requested_receipt",
                "coupa_submission_proof_intake_receipt",
            ),
        )
    if action_kind == "prepare_selected_invoice_pdf_artifact":
        return (
            "Prepare selected invoice PDF",
            "Prepare a scoped Live Arts MD invoice PDF on Mac for the selected invoice.",
            "OpenClaw exposes a strict export package for the selected sheet/print area. No export happens on this control plane.",
            "Run the scoped export package on Mac and then provide receipt proof.",
            ("selected_invoice_pdf_export_requested_receipt",),
        )
    if action_kind == "review_and_confirm_recipients":
        return (
            "Review recipients",
            "Review the Capital Hilton recipient candidates: Annette, Chyna, and Will.",
            "Confirm or edit the contact details before any email approval request can be prepared.",
            "Confirm or edit recipient details.",
            ("recipient_confirmation_request_receipt",),
        )
    if action_kind == "show_approval_prerequisites":
        missing_text = ", ".join(missing) if missing else "approval prerequisites"
        return (
            "Approval is not ready yet",
            f"Missing: {missing_text}.",
            "Guardian output validation is only safe-to-show proof. It is not operator approval or send authority.",
            "Resolve the missing prerequisites first.",
            ("approval_prerequisite_review_receipt",),
        )
    if action_kind == "replace_source_workbook_reference":
        return (
            "Choose the correct source workbook",
            "Choose the correct source workbook.",
            "OpenClaw will replace the reference only after the new workbook is selected and approved. No file will be deleted.",
            "Choose the correct workbook in Mission Control.",
            ("source_workbook_replacement_request_receipt",),
        )
    if action_kind == "regenerate_or_link_invoice_artifact":
        return (
            "Invoice artifact needs linkage",
            "OpenClaw needs to regenerate or link the invoice artifact after the correct invoice page/period is selected.",
            "No invoice was generated or exported from this step.",
            "Select the invoice page/period, then link or regenerate the artifact through the governed path.",
            ("generated_invoice_artifact_linkage_request_receipt",),
        )
    if action_kind == "review_clara_draft_prerequisites":
        return (
            "Review Clara draft prerequisites",
            "Clara's draft can stay visible as draft-only.",
            "Recipients, invoice selection, artifact linkage, Coupa proof, and approval remain separate.",
            "Review the missing prerequisites before requesting approval.",
            ("clara_draft_prerequisite_review_receipt",),
        )
    if action_kind == "edit_clara_draft_request":
        return (
            "Draft edit is not wired yet",
            "The Clara draft edit path is not wired yet.",
            "Nothing was changed or sent.",
            "Use the visible draft text for manual review until the edit path is connected.",
            ("clara_draft_edit_request_receipt",),
        )
    if action_kind == "prepare_send_approval_request":
        missing_text = ", ".join(missing) if missing else "send prerequisites"
        return (
            "Send approval is blocked",
            f"Prepare-send is blocked until prerequisites are ready. Missing: {missing_text}.",
            "No send approval, email send, or Coupa submission happened.",
            "Resolve the invoice review blockers first.",
            ("send_approval_preparation_receipt",),
        )
    if action_kind == "setup_payment_watch_after_submission":
        return (
            "Payment watch is not ready",
            "Payment watch can be set up after submission/send proof exists.",
            "No payment status, ledger, or tax record was changed.",
            "Capture portal/email receipts first.",
            ("payment_watch_setup_receipt",),
        )
    if action_kind == "confirm_source_workbook_reference":
        return (
            "Confirm source workbook",
            "Confirm the source workbook for the Capital Hilton invoice review.",
            "This starts workbook-reference confirmation only. It does not read workbook cells.",
            "Confirm or replace the workbook reference.",
            ("active_workbook_confirmed_receipt",),
        )
    if action_kind == "confirm_invoice_review_candidate":
        return (
            "Invoice review confirmation started",
            "Confirm this invoice only after the workbook, page/period, artifact linkage, Coupa proof, and recipients are right.",
            "This does not approve sending or submitting anything.",
            "Review the missing prerequisites before approval.",
            ("invoice_review_confirmation_intake_receipt",),
        )
    if action_kind == "open_invoice_workbook_candidate":
        return (
            "Open workbook candidate",
            "Open the Mac-visible candidate file for inspection.",
            "This is an inspection action only. It does not mark the artifact current or attachment-ready.",
            "Inspect the candidate file, then confirm or correct the invoice page.",
            ("local_artifact_inspection_receipt",),
        )
    return (
        "Explain this review",
        "This review separates draft display, Coupa proof, Guardian approval, operator approval, and execution receipts.",
        "Nothing has been sent, submitted, posted, generated, or changed.",
        "Use a timeline action to start the next safe fix path.",
        ("invoice_review_explanation_receipt",),
    )


def _journal_classification(
    *,
    action_kind: str,
    status: str,
    supported: bool,
    valid_scope: bool,
    no_external: bool,
    action_enabled: bool,
    progress_status: str | None,
) -> tuple[str, str, bool, str]:
    if not supported:
        return (
            "UNSUPPORTED_PENDING",
            "PENDING_NOT_WIRED",
            False,
            "Operator clicked an invoice review action that is not wired yet.",
        )
    if not valid_scope or not no_external:
        return (
            "BLOCKED",
            "BLOCKED",
            True,
            "OpenClaw blocked the operator action before starting a guided path.",
        )
    if not action_enabled:
        return (
            "DISABLED",
            "DISABLED",
            True,
            "Operator clicked a disabled invoice review action; no workflow step was completed.",
        )
    if action_kind == "open_invoice_workbook_candidate":
        return (
            "LOCAL_INSPECTION",
            "HANDLED",
            True,
            "Operator requested local inspection of a candidate artifact.",
        )
    if progress_status and str(progress_status).startswith("BLOCKED"):
        return (
            "BLOCKED",
            "BLOCKED",
            True,
            "OpenClaw handled the operator action as a blocked guided request.",
        )
    if status.startswith("BLOCKED"):
        return (
            "BLOCKED",
            "BLOCKED",
            True,
            "OpenClaw returned a blocked response for the operator action.",
        )
    return (
        "GOVERNED_REQUEST",
        "HANDLED",
        True,
        "OpenClaw handled the operator action as a governed backend request.",
    )


def _journal_summary(action_kind: str, label: str, body: str, next_action: str) -> str:
    if action_kind in {"replace_source_workbook_reference", "operator_reported_wrong_source_workbook"}:
        return "Operator indicated the current workbook reference may be wrong."
    if action_kind == "start_invoice_record_selection":
        return "Operator started invoice page/period selection."
    if action_kind in {"request_supplier_portal_submission_proof", "request_coupa_submission_proof"}:
        return "Operator started supplier portal proof intake."
    if action_kind == "review_and_confirm_recipients":
        return "Operator started recipient review."
    if action_kind == "show_approval_prerequisites":
        return "Operator requested current approval prerequisites."
    if body:
        return body
    return f"Operator clicked {label or action_kind}."


def process_action_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = invoice_review_state_machine.DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT,
    event_db_path: Path = operator_action_event_journal.DEFAULT_DB_PATH,
    event_export_root: Path = operator_action_event_journal.DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    payload = _action_payload(raw_request)
    request_id = str(raw_request.get("request_id") or payload.get("request_id") or payload.get("source_request_id") or "unknown_invoice_review_action")
    action_kind = str(payload.get("action_kind") or payload.get("request_kind") or payload.get("intended_use") or "")
    if action_kind == "invoice_review_guided_action_request":
        action_kind = str(payload.get("request_kind") or "")
    context = _client_context(payload, raw_request)
    local_surface_request = _invoice_record_selection_surface(
        request_id=request_id,
        action_kind=action_kind,
        payload=payload,
        context=context,
    ) or _source_workbook_selection_surface(
        request_id=request_id,
        action_kind=action_kind,
        payload=payload,
    )
    bundle_id = context["bundle_id"]
    workflow_ref = context["workflow_ref"]
    client_ref = context["client_ref"]
    no_external = _no_external_authority(payload, action_kind=action_kind)
    current_actions = _current_action_index(client_ref)
    bundle_action = current_actions.get(action_kind)
    valid_scope = (
        client_ref in CLIENT_BUNDLES
        and bundle_id == CLIENT_BUNDLES[client_ref]["bundle_id"]
        and workflow_ref == CLIENT_BUNDLES[client_ref]["workflow_ref"]
    )
    supported = action_kind in SUPPORTED_ACTIONS
    action_enabled = bool(bundle_action.get("enabled")) if bundle_action else supported
    action_disabled_reason = str((bundle_action or {}).get("disabled_reason") or "")
    can_start = valid_scope and supported and no_external and action_enabled
    if action_kind in {"prepare_send_approval_request", "setup_payment_watch_after_submission", "edit_clara_draft_request"}:
        can_start = False
        action_disabled_reason = action_disabled_reason or "This guided path is blocked until prerequisites exist."
    progress_result = None
    live_arts_selection_result = None
    pdf_candidate_decision_receipt = None
    live_arts_bundle_paths: tuple[str | None, str | None, bool] = (None, None, False)
    if (
        valid_scope
        and supported
        and no_external
        and client_ref == "live_arts_md"
        and action_kind in PDF_CANDIDATE_DECISION_ACTIONS
    ):
        active_review, active_bundle_path = _load_live_arts_pdf_candidate_review(
            export_root=export_root,
            bridge_export_root=bridge_export_root,
        )
        validation_errors = _pdf_candidate_decision_validation_errors(
            payload,
            action_kind=action_kind,
            active_review=active_review,
        )
        decision_accepted = not validation_errors
        decision_status = (
            "APPROVED_FOR_DRAFT_ATTACHMENT_PACKAGE"
            if action_kind == "approve_pdf_candidate"
            else "REJECTED_BY_OPERATOR"
        )
        if not decision_accepted:
            decision_status = "BLOCKED_INVALID_DECISION"
        candidate_sha = str(
            _mapping_value(payload, "candidate_sha256")
            or _mapping_value(payload, "sha256")
            or (active_review or {}).get("sha256")
            or ""
        ).removeprefix("sha256:")
        candidate_ref = str(
            _mapping_value(payload, "candidate_ref")
            or (active_review or {}).get("candidate_ref")
            or ""
        )
        observed = _positive_int(_mapping_value(payload, "observed_page_count") or _mapping_value(payload, "page_count"))
        expected_page_count = _positive_int(
            _mapping_value(payload, "expected_page_count") or _mapping_value(payload, "expected_output_page_count")
        )
        receipt = {
            "receipt_id": f"pdf_candidate_review_decision:{_short_hash(request_id, action_kind, candidate_sha, decision_status)}",
            "receipt_type": "selected_invoice_pdf_candidate_review_decision_receipt",
            "receipt_name": "selected_invoice_pdf_candidate_review_decision_receipt",
            "source_request_id": request_id,
            "client_ref": "live_arts_md",
            "workflow_ref": "live_arts_md_invoice_workflow",
            "invoice_id": "2026-1001",
            "action_kind": action_kind,
            "decision_status": decision_status,
            "operator_decision_only": True,
            "candidate_ref": candidate_ref,
            "candidate_sha256": candidate_sha or None,
            "observed_page_count": observed,
            "expected_page_count": expected_page_count,
            "operator_visual_review": _mapping_value(payload, "operator_visual_review") is True,
            "selected_sheet_label": _mapping_value(payload, "selected_sheet_label")
            or (active_review or {}).get("selected_sheet_label"),
            "selected_invoice_amount": _mapping_value(payload, "selected_invoice_amount")
            or (active_review or {}).get("selected_invoice_amount"),
            "pdf_bridge_path": (active_review or {}).get("pdf_bridge_path"),
            "pdf_mac_path": (active_review or {}).get("pdf_mac_path"),
            "active_candidate_bundle_path": active_bundle_path,
            "validation_errors": validation_errors,
            "attachment_ready": False,
            "approval_ready": False,
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "sent": False,
            "paid": False,
            "final": False,
            "external_action_performed": False,
            "email_send_performed": False,
            "ledger_posting_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "underlying_blocker_completed": decision_accepted and action_kind == "approve_pdf_candidate",
            "completion_receipt_written": decision_accepted,
            "generated_at": generated_at,
        }
        if decision_accepted:
            receipt_path, bridge_receipt_path = _write_pdf_candidate_decision_receipt(
                receipt,
                export_root=export_root,
                bridge_export_root=bridge_export_root,
            )
            receipt["receipt_path"] = receipt_path
            receipt["bridge_receipt_path"] = bridge_receipt_path
            if action_kind == "approve_pdf_candidate":
                export_receipt_payload = _read_json_if_exists(
                    export_root / live_arts_md_invoice_review_bundle.PDF_EXPORT_RESULT_RECEIPT_EXPORT_NAME
                )
                if export_receipt_payload is None and bridge_export_root is not None:
                    export_receipt_payload = _read_json_if_exists(
                        bridge_export_root / live_arts_md_invoice_review_bundle.PDF_EXPORT_RESULT_RECEIPT_EXPORT_NAME
                    )
                operator_assistance_annotation_payload = _read_json_if_exists(
                    export_root / live_arts_md_invoice_review_bundle.PDF_EXPORT_OPERATOR_ASSISTANCE_ANNOTATION_EXPORT_NAME
                )
                if operator_assistance_annotation_payload is None and bridge_export_root is not None:
                    operator_assistance_annotation_payload = _read_json_if_exists(
                        bridge_export_root
                        / live_arts_md_invoice_review_bundle.PDF_EXPORT_OPERATOR_ASSISTANCE_ANNOTATION_EXPORT_NAME
                    )
                bundle_payload = live_arts_md_invoice_review_bundle.build_payload(
                    generated_at=generated_at,
                    consume_existing_selection_receipt=False,
                    export_receipt_payload=export_receipt_payload,
                    operator_assistance_annotation_payload=operator_assistance_annotation_payload,
                    pdf_candidate_decision_receipt_payload=receipt,
                )
                approved_artifact = (
                    bundle_payload.get("live_arts_md_bundle", {})
                    .get("invoice_artifact", {})
                    .get("approved_pdf_artifact")
                )
                if isinstance(approved_artifact, Mapping):
                    source_json, _source_operator, bridge_json = live_arts_md_invoice_review_bundle.write_exports(
                        bundle_payload,
                        export_root,
                        bridge_export_root=bridge_export_root,
                    )
                    live_arts_bundle_paths = (
                        source_json.as_posix(),
                        bridge_json.as_posix() if bridge_json else None,
                        bridge_json is not None,
                    )
        pdf_candidate_decision_receipt = receipt
        headline = (
            "PDF candidate approval recorded"
            if decision_accepted and action_kind == "approve_pdf_candidate"
            else "PDF candidate rejection recorded"
            if decision_accepted
            else "PDF candidate decision blocked"
        )
        body = (
            "Recorded the operator PDF candidate approval as a decision receipt only. No email, ledger, browser, Gmail, Coupa, sent, or paid authority was granted."
            if decision_accepted and action_kind == "approve_pdf_candidate"
            else "Recorded the operator PDF candidate rejection as a decision receipt only. No PDF was deleted or overwritten."
            if decision_accepted
            else "OpenClaw blocked the PDF candidate decision before any lifecycle advance."
        )
        detail = (
            "The candidate SHA and page count matched the active one-page Live Arts PDF review candidate."
            if decision_accepted and action_kind == "approve_pdf_candidate"
            else "The rejection receipt keeps desired_page_known=false valid when the desired page is unknown."
            if decision_accepted
            else "; ".join(validation_errors)
        )
        next_action = (
            "Prepare the Clara draft attachment package for operator review without sending email."
            if decision_accepted and action_kind == "approve_pdf_candidate"
            else "Keep or replace the PDF candidate before any attachment package is prepared."
            if decision_accepted
            else "Retry with the active candidate SHA, one-page count, visual-review proof, and no true authority grants."
        )
        status = "GUIDED_RESULT_RECORDED" if decision_accepted else "BLOCKED_PREREQUISITES"
        expected = ("selected_invoice_pdf_candidate_review_decision_receipt",) if decision_accepted else ()
        if not live_arts_bundle_paths[0]:
            live_arts_bundle_paths = (active_bundle_path, None, False)
    elif (
        valid_scope
        and supported
        and no_external
        and client_ref == "live_arts_md"
        and action_kind in {"select_invoice_candidate", "select_live_arts_md_invoice_candidate"}
    ):
        live_arts_selection_result = live_arts_md_workbook_handoff.process_invoice_candidate_selection(
            payload,
            generated_at=generated_at,
        )
        source_json, _source_operator, bridge_json = live_arts_md_invoice_review_bundle.write_exports(
            live_arts_md_invoice_review_bundle.build_payload(
                generated_at=generated_at,
                selected_invoice_candidate=live_arts_selection_result["selected_candidate"],
                present_receipts=(
                    "live_arts_md_invoice_candidate_selected_receipt",
                )
                if live_arts_selection_result["status"] == "SELECTED_REQUIRES_ARTIFACT_AND_APPROVAL"
                else (),
            ),
            export_root,
            bridge_export_root=bridge_export_root,
        )
        live_arts_bundle_paths = (
            source_json.as_posix(),
            bridge_json.as_posix() if bridge_json else None,
            bridge_json is not None,
        )
        receipt = live_arts_selection_result["receipt"]
        if not receipt["validation_errors"]:
            export_root.mkdir(parents=True, exist_ok=True)
            selection_receipt_path = export_root / live_arts_md_invoice_review_bundle.SELECTION_RECEIPT_EXPORT_NAME
            selection_receipt_path.write_text(stable_json(receipt), encoding="utf-8")
            if bridge_export_root:
                bridge_export_root.mkdir(parents=True, exist_ok=True)
                bridge_selection_receipt_path = (
                    bridge_export_root / live_arts_md_invoice_review_bundle.SELECTION_RECEIPT_EXPORT_NAME
                )
                bridge_selection_receipt_path.write_text(stable_json(receipt), encoding="utf-8")
        headline = "Live Arts MD invoice selected" if not receipt["validation_errors"] else "Invoice selection blocked"
        body = (
            "Live Arts MD invoice candidate recorded. Next: prepare the selected invoice PDF package through the governed scope before attaching or sending. "
            if not receipt["validation_errors"]
            else "OpenClaw could not record that invoice candidate because the selection payload was incomplete or unsafe."
        )
        detail = "No workbook cells were read."
        next_action = live_arts_selection_result["next_action"]
        expected = (receipt["receipt_event"],)
        status = "GUIDED_ACTION_STARTED" if not receipt["validation_errors"] else "BLOCKED_PREREQUISITES"
    elif valid_scope and supported and no_external and action_kind == "prepare_selected_invoice_pdf_artifact":
        selected_candidate = _selected_invoice_candidate_from_payload(payload)
        if selected_candidate is not None:
            bundle_payload = live_arts_md_invoice_review_bundle.build_payload(
                generated_at=generated_at,
                selected_invoice_candidate=selected_candidate,
            )
            package = bundle_payload["live_arts_md_bundle"]["invoice_artifact"]["pdf_export_package"]
            source_json, _source_operator, bridge_json = live_arts_md_invoice_review_bundle.write_exports(
                bundle_payload,
                export_root,
                bridge_export_root=bridge_export_root,
            )
            live_arts_bundle_paths = (
                source_json.as_posix(),
                bridge_json.as_posix() if bridge_json else None,
                bridge_json is not None,
            )
            if package["status"] in {
                live_arts_md_invoice_review_bundle.PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE,
                live_arts_md_invoice_review_bundle.PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY,
                live_arts_md_invoice_review_bundle.PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT,
                live_arts_md_invoice_review_bundle.PDF_EXPORT_REQUIRES_OPERATOR_REVIEW,
            }:
                headline = "Prepare selected invoice PDF package is blocked"
                body = str(
                    package.get("operator_review_prompt")
                    or "Prepare a scoped invoice PDF package requires additional invoice scope inputs."
                )
                detail = "OpenClaw can only start the guided package path once the invoice print scope is complete."
                next_action = str(
                    package.get("operator_review_prompt")
                    or "Confirm the selected invoice scope for PDF export."
                )
                status = "BLOCKED_PREREQUISITES"
                expected = tuple()
            else:
                headline = "Prepare selected invoice PDF package"
                body = "Prepared a scoped invoice PDF export package request for the selected invoice. No export was executed."
                detail = (
                    "Use the scoped Mac package to create the PDF for the selected invoice sheet and print area, then return a completion receipt."
                )
                next_action = "Prepare the selected invoice PDF on Mac."
                status = "GUIDED_ACTION_STARTED"
                expected = ("selected_invoice_pdf_export_requested_receipt",)
        else:
            headline, body, detail, next_action, expected = _operator_copy(
                "prepare_selected_invoice_pdf_artifact",
                context={"client_ref": client_ref},
            )
            status = "BLOCKED_PREREQUISITES"
            if action_disabled_reason:
                body = f"{body} {action_disabled_reason}"
            live_arts_bundle_paths = (None, None, False)
    elif valid_scope and supported and no_external:
        progress_result = invoice_review_state_machine.process_action(
            raw_request,
            db_path=db_path,
            export_root=export_root,
            bridge_export_root=bridge_export_root,
            generated_at=generated_at,
        )
        headline = progress_result.headline
        body = progress_result.body
        detail = progress_result.detail
        next_action = progress_result.next_action
        expected = (progress_result.action_receipt["receipt_name"],)
        status = "BLOCKED_PREREQUISITES" if str(progress_result.status).startswith("BLOCKED") else "GUIDED_ACTION_STARTED"
        if client_ref == "live_arts_md" and action_kind == "start_invoice_record_selection":
            headline = "Starting Live Arts MD invoice selection"
            body = "Let's select the Live Arts MD invoice page/period. No workbook cells will be read."
            detail = "OpenClaw will use the operator-provided candidate register and wait for an operator selection result."
            next_action = "Choose the Live Arts MD invoice page or period in Mission Control."
            expected = ("live_arts_md_invoice_candidate_selected_receipt",)
    elif not valid_scope:
        headline = "Invoice review action blocked"
        body = "OpenClaw could not start that invoice review action because the bundle, workflow, or client did not match."
        detail = "No guided path started; the current invoice review bundle scope did not match the request."
        status = "BLOCKED_SCOPE_MISMATCH"
        next_action = "Use the current Capital Hilton invoice review card."
        expected = ()
    elif not no_external:
        headline = "Invoice review action blocked"
        body = "OpenClaw blocked this action because the request tried to include external authority."
        detail = "No guided path started; invoice review buttons cannot carry external action authority."
        status = "BLOCKED_EXTERNAL_AUTHORITY"
        next_action = "Retry with no external action authority."
        expected = ()
    elif not supported:
        headline = "Invoice review action not wired"
        body = "That invoice review action is not wired yet."
        detail = "No guided path started; the backend has no supported handler for this invoice review action."
        status = "BLOCKED_UNSUPPORTED_ACTION"
        next_action = "Use one of the visible enabled invoice review actions."
        expected = ()
    elif not can_start:
        headline, body, detail, next_action, expected = _operator_copy(action_kind, context=context)
        status = "BLOCKED_PREREQUISITES"
        if action_disabled_reason:
            body = f"{body} {action_disabled_reason}"
    else:
        headline, body, detail, next_action, expected = _operator_copy(action_kind, context=context)
        status = "GUIDED_ACTION_STARTED"
    if pdf_candidate_decision_receipt is not None:
        receipt = pdf_candidate_decision_receipt
        receipt["status"] = status
        receipt["expected_receipt_types"] = expected
    else:
        receipt = {
            "receipt_id": f"invoice_review_action_start:{_short_hash(request_id, action_kind, status)}",
            "receipt_type": "guided_action_start_receipt",
            "source_request_id": request_id,
            "bundle_id": bundle_id,
            "workflow_ref": workflow_ref,
            "client_ref": client_ref,
            "action_kind": action_kind,
            "status": status,
            "expected_receipt_types": expected,
            "underlying_blocker_completed": False,
            "completion_receipt_written": False,
            "external_action_performed": False,
            "generated_at": generated_at,
        }
    if progress_result is not None:
        receipt["receipt_id"] = progress_result.action_receipt["receipt_id"]
        receipt["receipt_type"] = progress_result.action_receipt["receipt_type"]
        receipt["receipt_name"] = progress_result.action_receipt["receipt_name"]
        receipt["progress_status"] = progress_result.status
        receipt["underlying_blocker_completed"] = progress_result.action_receipt["underlying_blocker_completed"]
        receipt["completion_receipt_written"] = progress_result.action_receipt["completion_receipt_written"]
    if live_arts_selection_result is not None:
        receipt.update(live_arts_selection_result["receipt"])
        receipt["receipt_type"] = "invoice_review_action_progress_receipt"
        receipt["receipt_name"] = live_arts_selection_result["receipt"]["receipt_event"]
        receipt["underlying_blocker_completed"] = False
        receipt["completion_receipt_written"] = False
    label_clicked = str(
        payload.get("label_clicked")
        or payload.get("label")
        or (bundle_action or {}).get("label")
        or action_kind
    )
    journal_category, journal_status, journal_handled, default_summary = _journal_classification(
        action_kind=action_kind,
        status=status,
        supported=supported,
        valid_scope=valid_scope,
        no_external=no_external,
        action_enabled=action_enabled,
        progress_status=progress_result.status if progress_result else None,
    )
    journal_event = operator_action_event_journal.record_operator_action_event(
        source_request_id=request_id,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
        bundle_id=bundle_id,
        action_ref=str(payload.get("action_ref") or action_kind),
        intended_use=str(payload.get("intended_use") or action_kind),
        label_clicked=label_clicked,
        action_category=journal_category,
        emitted_backend_request=True,
        handled=journal_handled,
        handler_ref=f"invoice_review_action_request.{client_ref}",
        status=journal_status,
        operator_visible_summary=(
            _journal_summary(action_kind, label_clicked, body, next_action)
            if journal_status != "PENDING_NOT_WIRED"
            else default_summary
        ),
        no_external_action=no_external,
        physical_deletion_allowed=bool(payload.get("physical_deletion_allowed") is True),
        proof_refs=(receipt.get("receipt_id"),),
        expected_next_safe_move=next_action,
        db_path=event_db_path,
        generated_at=generated_at,
    )
    journal_payload, journal_json, journal_operator = operator_action_event_journal.export_read_model(
        db_path=event_db_path,
        export_root=event_export_root,
        generated_at=generated_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "source_request_id": request_id,
        "action_kind": action_kind,
        "status": status,
        "headline": headline,
        "body": body,
        "detail": detail,
        "next_action": next_action,
        "expected_receipt_types": expected,
        "action_start_receipt": receipt,
        "operator_action_event": journal_event,
        "operator_action_event_journal": {
            "readback_ref": journal_json.as_posix(),
            "operator_readback_ref": journal_operator.as_posix(),
            "pending_operator_intent_count": len(journal_payload.get("pending_operator_intents") or ()),
        },
        "state_machine_progress": {
            "used": progress_result is not None or pdf_candidate_decision_receipt is not None,
            "progress_status": progress_result.status
            if progress_result
            else live_arts_selection_result["status"]
            if live_arts_selection_result
            else receipt.get("decision_status")
            if pdf_candidate_decision_receipt is not None
            else None,
            "state_snapshot": progress_result.state_snapshot if progress_result else None,
            "action_progress_receipt": progress_result.action_receipt
            if progress_result
            else live_arts_selection_result["receipt"]
            if live_arts_selection_result
            else receipt
            if pdf_candidate_decision_receipt is not None
            else None,
            "source_bundle_path": progress_result.source_bundle_path if progress_result else live_arts_bundle_paths[0],
            "bridge_bundle_path": progress_result.bridge_bundle_path if progress_result else live_arts_bundle_paths[1],
            "bridge_mirror_written": progress_result.bridge_mirror_written if progress_result else live_arts_bundle_paths[2],
        },
        "local_surface_request": local_surface_request,
        "bundle_action": bundle_action,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "bundle_scope_valid": valid_scope,
            "supported_action": supported,
            "current_bundle_action_found": bundle_action is not None,
            "no_external_action": no_external,
            "guided_path_started": status == "GUIDED_ACTION_STARTED",
            "local_surface_request_present": local_surface_request is not None,
            "local_surface_type": local_surface_request.get("surface_type") if local_surface_request else None,
            "completion_receipt_written": bool(progress_result.action_receipt["completion_receipt_written"])
            if progress_result
            else bool(receipt.get("completion_receipt_written")),
            "underlying_blocker_completed": bool(progress_result.action_receipt["underlying_blocker_completed"])
            if progress_result
            else bool(receipt.get("underlying_blocker_completed")),
            "bundle_refreshed": bool(progress_result) or bool(live_arts_bundle_paths[0]),
            "bridge_bundle_mirrored": bool(progress_result and progress_result.bridge_mirror_written) or bool(live_arts_bundle_paths[2]),
            "coupa_browser_automation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "supplier_portal_submit_performed": False,
            "email_send_performed": False,
            "ledger_posting_performed": False,
            "invoice_generation_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "production_mutation_performed": False,
            "all_authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def process_invoice_record_selection_result_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = invoice_review_state_machine.DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT,
    event_db_path: Path = operator_action_event_journal.DEFAULT_DB_PATH,
    event_export_root: Path = operator_action_event_journal.DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    progress_result = invoice_review_state_machine.process_invoice_record_selection_result(
        raw_request,
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
    )
    response_ready = progress_result.status == "REQUESTED"
    journal_event = operator_action_event_journal.record_operator_action_event(
        source_request_id=progress_result.source_request_id,
        client_ref="capital_hilton",
        workflow_ref=invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        bundle_id=invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID,
        action_ref="confirm_invoice_record_selection",
        intended_use="confirm_invoice_record_selection",
        label_clicked="Confirm invoice page/period",
        action_category="GOVERNED_REQUEST" if response_ready else "BLOCKED",
        emitted_backend_request=True,
        handled=True,
        handler_ref="invoice_record_selection_result.capital_hilton",
        status="HANDLED" if response_ready else "BLOCKED",
        operator_visible_summary=(
            "Operator confirmed the invoice page/period selection."
            if response_ready
            else "OpenClaw blocked an incomplete or unsafe invoice page/period selection result."
        ),
        no_external_action=True,
        physical_deletion_allowed=False,
        proof_refs=(progress_result.action_receipt["receipt_id"],),
        expected_next_safe_move=progress_result.next_action,
        db_path=event_db_path,
        generated_at=generated_at,
    )
    journal_payload, journal_json, journal_operator = operator_action_event_journal.export_read_model(
        db_path=event_db_path,
        export_root=event_export_root,
        generated_at=generated_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "source_request_id": progress_result.source_request_id,
        "action_kind": "confirm_invoice_record_selection",
        "status": "GUIDED_RESULT_RECORDED" if response_ready else "BLOCKED_INVALID_RESULT",
        "headline": progress_result.headline,
        "body": progress_result.body,
        "detail": progress_result.detail,
        "next_action": progress_result.next_action,
        "expected_receipt_types": (progress_result.action_receipt["receipt_name"],),
        "action_start_receipt": progress_result.action_receipt,
        "operator_action_event": journal_event,
        "operator_action_event_journal": {
            "readback_ref": journal_json.as_posix(),
            "operator_readback_ref": journal_operator.as_posix(),
            "pending_operator_intent_count": len(journal_payload.get("pending_operator_intents") or ()),
        },
        "state_machine_progress": {
            "used": True,
            "progress_status": progress_result.status,
            "state_snapshot": progress_result.state_snapshot,
            "action_progress_receipt": progress_result.action_receipt,
            "source_bundle_path": progress_result.source_bundle_path,
            "bridge_bundle_path": progress_result.bridge_bundle_path,
            "bridge_mirror_written": progress_result.bridge_mirror_written,
        },
        "local_surface_result": {
            "intended_use": "confirm_invoice_record_selection",
            "result_recorded": response_ready,
            "validation_errors": progress_result.action_receipt.get("validation_errors") or (),
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "invoice_generation_performed": False,
            "artifact_linked": False,
            "attachment_ready": False,
            "approval_ready": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "bundle_scope_valid": "WRONG_CLIENT" not in progress_result.action_receipt.get("validation_errors", ())
            and "WRONG_WORKFLOW" not in progress_result.action_receipt.get("validation_errors", ()),
            "supported_action": True,
            "no_external_action": True,
            "guided_path_started": response_ready,
            "completion_receipt_written": False,
            "underlying_blocker_completed": False,
            "bundle_refreshed": True,
            "bridge_bundle_mirrored": progress_result.bridge_mirror_written,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "ocr_performed": False,
            "invoice_generation_performed": False,
            "email_send_performed": False,
            "coupa_browser_automation_performed": False,
            "ledger_posting_performed": False,
            "production_mutation_performed": False,
            "all_authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def process_source_workbook_selection_result_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = invoice_review_state_machine.DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT,
    event_db_path: Path = operator_action_event_journal.DEFAULT_DB_PATH,
    event_export_root: Path = operator_action_event_journal.DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    payload = _action_payload(raw_request)
    context = _client_context(payload, raw_request)
    progress_result = invoice_review_state_machine.process_source_workbook_selection_result(
        raw_request,
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
    )
    response_ready = progress_result.status == "COMPLETED"
    journal_event = operator_action_event_journal.record_operator_action_event(
        source_request_id=progress_result.source_request_id,
        client_ref=str(progress_result.state_snapshot.get("client_ref") or context["client_ref"]),
        workflow_ref=str(progress_result.state_snapshot.get("workflow_ref") or context["workflow_ref"]),
        bundle_id=str(progress_result.state_snapshot.get("bundle_id") or context["bundle_id"]),
        action_ref="confirm_source_workbook_reference",
        intended_use="confirm_source_workbook_reference",
        label_clicked="Confirm source workbook",
        action_category="GOVERNED_REQUEST" if response_ready else "BLOCKED",
        emitted_backend_request=True,
        handled=True,
        handler_ref=f"source_workbook_selection_result.{progress_result.state_snapshot.get('client_ref') or context['client_ref']}",
        status="HANDLED" if response_ready else "BLOCKED",
        operator_visible_summary=(
            f"Operator confirmed the {CLIENT_BUNDLES.get(str(progress_result.state_snapshot.get('client_ref') or context['client_ref']), context)['client_display_name']} source workbook reference."
            if response_ready
            else "OpenClaw blocked an incomplete or unsafe source workbook selection result."
        ),
        no_external_action=True,
        physical_deletion_allowed=False,
        proof_refs=(progress_result.action_receipt["receipt_id"],),
        expected_next_safe_move=progress_result.next_action,
        db_path=event_db_path,
        generated_at=generated_at,
    )
    journal_payload, journal_json, journal_operator = operator_action_event_journal.export_read_model(
        db_path=event_db_path,
        export_root=event_export_root,
        generated_at=generated_at,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "source_request_id": progress_result.source_request_id,
        "action_kind": "confirm_source_workbook_reference",
        "status": "GUIDED_RESULT_RECORDED" if response_ready else "BLOCKED_INVALID_RESULT",
        "headline": progress_result.headline,
        "body": progress_result.body,
        "detail": progress_result.detail,
        "next_action": progress_result.next_action,
        "expected_receipt_types": (progress_result.action_receipt["receipt_name"],),
        "action_start_receipt": progress_result.action_receipt,
        "operator_action_event": journal_event,
        "operator_action_event_journal": {
            "readback_ref": journal_json.as_posix(),
            "operator_readback_ref": journal_operator.as_posix(),
            "pending_operator_intent_count": len(journal_payload.get("pending_operator_intents") or ()),
        },
        "state_machine_progress": {
            "used": True,
            "progress_status": progress_result.status,
            "state_snapshot": progress_result.state_snapshot,
            "action_progress_receipt": progress_result.action_receipt,
            "source_bundle_path": progress_result.source_bundle_path,
            "bridge_bundle_path": progress_result.bridge_bundle_path,
            "bridge_mirror_written": progress_result.bridge_mirror_written,
        },
        "local_surface_result": {
            "intended_use": "confirm_source_workbook_reference",
            "result_recorded": response_ready,
            "validation_errors": progress_result.action_receipt.get("validation_errors") or (),
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "physical_deletion_allowed": False,
            "invoice_generation_performed": False,
            "artifact_linked": False,
            "attachment_ready": False,
            "approval_ready": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "bundle_scope_valid": "WRONG_CLIENT" not in progress_result.action_receipt.get("validation_errors", ())
            and "WRONG_WORKFLOW" not in progress_result.action_receipt.get("validation_errors", ()),
            "supported_action": True,
            "no_external_action": True,
            "guided_path_started": response_ready,
            "completion_receipt_written": response_ready,
            "underlying_blocker_completed": response_ready,
            "bundle_refreshed": True,
            "bridge_bundle_mirrored": progress_result.bridge_mirror_written,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "invoice_generation_performed": False,
            "email_send_performed": False,
            "coupa_browser_automation_performed": False,
            "ledger_posting_performed": False,
            "production_mutation_performed": False,
            "all_authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }



def process_selected_invoice_pdf_export_completed_candidate_result_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = invoice_review_state_machine.DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT,
    event_db_path: Path = operator_action_event_journal.DEFAULT_DB_PATH,
    event_export_root: Path = operator_action_event_journal.DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    payload = _action_payload(raw_request)
    context = _client_context(payload, raw_request)
    export_attempted = payload.get("export_attempted") is True or bool(payload.get("failure_code"))
    export_success = payload.get("export_success")
    failure_receipt = export_attempted and export_success is False
    failure_code = str(payload.get("failure_code") or "").strip()
    failure_message = str(payload.get("failure_message") or "").strip()
    artifact_review_status = "EXPORT_FAILED" if failure_receipt else str(payload.get("artifact_review_status") or "").strip()
    output_bridge_path = str(
        payload.get("pdf_bridge_path")
        or payload.get("output_bridge_path")
        or _bridge_path_from_mac_path(str(payload.get("exported_pdf_mac_path") or ""))
        or ""
    )
    page_count = payload.get("page_count") if payload.get("page_count") not in (None, "") else payload.get("observed_page_count")
    expected_page_count = (
        payload.get("expected_page_count")
        if payload.get("expected_page_count") not in (None, "")
        else payload.get("expected_output_page_count")
    )
    failed_candidate_sha256 = payload.get("failed_candidate_sha256")
    failed_candidate_status = (
        payload.get("failed_candidate_artifact_review_status")
        or "SCOPE_MISMATCH_REJECTED"
        if failed_candidate_sha256
        else None
    )
    failed_candidate_reason_code = (
        payload.get("failed_candidate_reason_code")
        or "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
        if failed_candidate_sha256
        else None
    )

    validation_errors = []
    if str(context["client_ref"]) != "live_arts_md":
        validation_errors.append("WRONG_CLIENT")
    if str(context["workflow_ref"]) != "live_arts_md_invoice_workflow":
        validation_errors.append("WRONG_WORKFLOW")
    if str(payload.get("invoice_id") or "") != "2026-1001":
        validation_errors.append("WRONG_INVOICE_ID")

    pdf_path = str(payload.get("exported_pdf_mac_path") or "")
    if failure_receipt:
        if not failure_code:
            validation_errors.append("MISSING_FAILURE_CODE")
    elif not pdf_path:
        validation_errors.append("MISSING_PDF_PATH")
    elif not pdf_path.lower().endswith(".pdf"):
        validation_errors.append("INVALID_FILE_EXTENSION")

    result_accepted = len(validation_errors) == 0
    success_result = result_accepted and not failure_receipt
    failure_result = result_accepted and failure_receipt
    result_status = "EXPORT_FAILED" if failure_result else "PDF_EXPORT_COMPLETED_CANDIDATE" if success_result else "BLOCKED_INVALID_RESULT"

    action_receipt = {
        "receipt_id": f"pdf_export_candidate_receipt:{_short_hash(pdf_path or failure_code, generated_at)}",
        "receipt_type": "selected_invoice_pdf_export_completed_candidate_receipt",
        "receipt_name": "selected_invoice_pdf_export_completed_candidate_receipt",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "exported_pdf_mac_path": pdf_path,
        "pdf_bridge_path": output_bridge_path or None,
        "output_bridge_path": output_bridge_path or None,
        "artifact_filename": payload.get("artifact_filename"),
        "file_size_bytes": payload.get("file_size_bytes"),
        "sha256": payload.get("sha256"),
        "page_count": page_count,
        "expected_page_count": expected_page_count,
        "selected_sheet_label": payload.get("selected_sheet_label"),
        "selected_page_label": payload.get("selected_page_label"),
        "selected_invoice_amount": payload.get("selected_invoice_amount"),
        "operator_assisted": payload.get("operator_assisted"),
        "fully_unattended": payload.get("fully_unattended"),
        "failed_candidate_sha256": failed_candidate_sha256,
        "failed_candidate_artifact_review_status": failed_candidate_status,
        "failed_candidate_reason_code": failed_candidate_reason_code,
        "observed_failed_candidate_page_count": payload.get("observed_failed_candidate_page_count"),
        "final_candidate_parent_ref": payload.get("final_candidate_parent_ref"),
        "scope_correction_applied": payload.get("scope_correction_applied"),
        "source_correction": payload.get("source_correction"),
        "exported_by": "MAC_EXCEL",
        "execution_venue": "MAC_LOCAL",
        "export_attempted": export_attempted,
        "export_success": bool(success_result),
        "failure_code": failure_code or None,
        "failure_message": failure_message or None,
        "failed_stage": payload.get("failed_stage"),
        "result_status": result_status,
        "artifact_review_status": "EXPORT_FAILED" if failure_result else "OPERATOR_REVIEW_REQUIRED" if success_result else "NOT_READY",
        "attachment_ready": False,
        "approval_ready": False,
        "ledger_posting_allowed": False,
        "sent": False,
        "paid": False,
        "final": False,
        "validation_errors": validation_errors,
        "underlying_blocker_completed": True if success_result else False,
        "completion_receipt_written": True if success_result else False,
        "failure_receipt_written": True if failure_result else False,
        "result_receipt_written": True if result_accepted else False,
    }

    if result_accepted:
        export_root.mkdir(parents=True, exist_ok=True)
        receipts_path = export_root / "selected_invoice_pdf_export_completed_candidate_receipt.json"
        receipts_path.write_text(stable_json(action_receipt))
        if bridge_export_root:
            bridge_export_root.mkdir(parents=True, exist_ok=True)
            bridge_receipts_path = bridge_export_root / "selected_invoice_pdf_export_completed_candidate_receipt.json"
            bridge_receipts_path.write_text(stable_json(action_receipt))

    source_bundle_path = None
    bridge_bundle_path = None
    if result_accepted:
        selected_candidate = _live_arts_candidate_from_invoice_id(str(action_receipt.get("invoice_id") or ""))
        bundle_payload = live_arts_md_invoice_review_bundle.build_payload(
            generated_at=generated_at,
            selected_invoice_candidate=selected_candidate,
            export_receipt_payload=action_receipt if failure_result else None,
            present_receipts=(live_arts_md_invoice_review_bundle.PDF_EXPORT_COMPLETION_RECEIPT,) if success_result else (),
        )
        bundle = bundle_payload["live_arts_md_bundle"]
        if success_result:
            bundle["invoice_artifact"]["pdf_export_package"]["status"] = "PDF_EXPORT_COMPLETED_CANDIDATE"
            bundle["invoice_artifact"]["artifact_review_status"] = "OPERATOR_REVIEW_REQUIRED"
        if failure_result:
            bundle["invoice_artifact"]["pdf_export_package"]["status"] = "EXPORT_FAILED"
            bundle["invoice_artifact"]["pdf_export_package"]["failure_code"] = failure_code
            bundle["invoice_artifact"]["pdf_export_package"]["failure_message"] = failure_message
            bundle["invoice_artifact"]["artifact_review_status"] = "EXPORT_FAILED"
        bundle["clara_email_draft"]["attachment_ready"] = False
        bundle["send_readiness"]["approval_ready"] = False
        bundle["payment_watch"]["ledger_posting_allowed"] = False
        bundle["machine_proof"]["content_hash"] = live_arts_md_invoice_review_bundle._content_hash(bundle)
        bundle_payload["machine_proof"]["content_hash"] = live_arts_md_invoice_review_bundle._content_hash(bundle)

        source_bundle_path, _source_operator_path, bridge_bundle_path = live_arts_md_invoice_review_bundle.write_exports(
            bundle_payload,
            export_root,
            bridge_export_root=bridge_export_root,
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "source_request_id": str(raw_request.get("request_id") or "unknown"),
        "action_kind": "selected_invoice_pdf_export_completed_candidate",
        "status": "GUIDED_FAILURE_RECORDED" if failure_result else "GUIDED_RESULT_RECORDED" if success_result else "BLOCKED_INVALID_RESULT",
        "headline": "PDF Export Failed" if failure_result else "PDF Export Candidate Recorded" if success_result else "PDF Export Blocked",
        "body": failure_message or "Mac helper reported PDF export failure." if failure_result else "Recorded" if success_result else "Blocked",
        "detail": {
            "failure_code": failure_code or None,
            "failure_message": failure_message or None,
            "artifact_review_status": "EXPORT_FAILED" if failure_result else artifact_review_status or None,
        },
        "next_action": (
            "Review the Mac helper failure, fix the Excel/print-scope issue, then rerun the scoped export package."
            if failure_result
            else "Operator review"
        ),
        "action_start_receipt": action_receipt,
        "state_machine_progress": {
            "used": True,
            "progress_status": "FAILED_RECORDED" if failure_result else "COMPLETED" if success_result else "BLOCKED",
            "state_snapshot": {},
            "action_progress_receipt": action_receipt,
            "source_bundle_path": source_bundle_path.as_posix() if source_bundle_path else None,
            "bridge_bundle_path": bridge_bundle_path.as_posix() if bridge_bundle_path else None,
            "bridge_mirror_written": bool(bridge_bundle_path),
        },
        "local_surface_result": {
            "intended_use": "selected_invoice_pdf_export_completed_candidate",
            "result_recorded": result_accepted,
            "result_status": result_status,
            "failure_code": failure_code or None,
            "failure_message": failure_message or None,
            "artifact_review_status": "EXPORT_FAILED" if failure_result else "OPERATOR_REVIEW_REQUIRED" if success_result else "NOT_READY",
            "validation_errors": validation_errors,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "invoice_generation_performed": False,
            "artifact_linked": True if success_result else False,
            "attachment_ready": False,
            "approval_ready": False,
            "ledger_posting_allowed": False,
            "sent": False,
            "paid": False,
            "final": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "bundle_scope_valid": result_accepted,
            "supported_action": True,
            "no_external_action": True,
            "guided_path_started": result_accepted,
            "completion_receipt_written": success_result,
            "failure_receipt_written": failure_result,
            "result_receipt_written": result_accepted,
            "underlying_blocker_completed": success_result,
            "bundle_refreshed": result_accepted,
            "bridge_bundle_mirrored": bool(bridge_bundle_path),
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "invoice_generation_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_browser_automation_performed": False,
            "ledger_posting_performed": False,
            "production_mutation_performed": False,
            "all_authority_boundary_false": True,
        },
    }

def write_exports(payload: Mapping[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    lines = [
        "# Invoice Review Action Request",
        "",
        str(payload["headline"]),
        str(payload["body"]),
        "",
        f"- Action: {payload['action_kind']}",
        f"- Status: {payload['status']}",
        f"- Next: {payload['next_action']}",
        "- No email, Coupa, browser, ledger, generation, workbook read, or production action occurred.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path
