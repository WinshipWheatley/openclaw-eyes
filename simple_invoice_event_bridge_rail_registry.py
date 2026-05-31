"""Reusable simple-invoice Event Bridge rail registry.

This compiler describes the bounded invoice PDF artifact route for simple
invoice clients. It only builds deterministic descriptors and generated
read-models; it does not execute handlers, export PDFs, send email, open
browser/Coupa/Gmail, read workbook cells, post ledgers, or mutate production
state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workflow_framework as invoice_framework
import openclaw_event_bridge_contract as event_contract
import openclaw_request_router
import simple_invoice_workflow_builder
import simple_invoice_workflow_fixtures


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "simple_invoice_event_bridge_rail_registry_v0"
READ_MODEL_ID = "simple_invoice_event_bridge_rail_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
RAIL_REF = event_contract.SIMPLE_INVOICE_EVENT_BRIDGE_PDF_ARTIFACT_RAIL_REF
PREPARE_ACTION_KIND = event_contract.SIMPLE_INVOICE_PREPARE_PDF_ACTION_KIND
RESULT_ACTION_KIND = event_contract.SIMPLE_INVOICE_PDF_RESULT_ACTION_KIND

NO_LIVE_ACTION_CLAIMS = {
    "handler_execution_performed": False,
    "processor_execution_performed": False,
    "service_started": False,
    "model_call_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "ledger_post_performed": False,
    "workbook_cell_read_performed": False,
    "pdf_export_performed": False,
    "production_mutation_performed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short_hash(*parts: object) -> str:
    return hashlib.sha256(stable_json(parts).encode("utf-8")).hexdigest()[:16]


def _as_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    return (text,) if text else ()


def _simple_fixtures() -> tuple[simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture, ...]:
    return tuple(
        fixture
        for fixture in simple_invoice_workflow_fixtures.SIMPLE_INVOICE_WORKFLOW_FIXTURES.values()
        if not fixture.allowed_send_coupa and not fixture.allowed_po
    )


def _fixture_config(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> dict[str, Any]:
    return {
        "client_ref": fixture.client_ref,
        "client_display_name": fixture.client_display_name,
        "workflow_ref": fixture.workflow_ref,
        "expected_workbook_name": fixture.expected_workbook_name,
        "expected_workbook_path": fixture.expected_workbook_path,
        "invoice_client_default_candidate_ref": fixture.invoice_client_default_candidate_ref,
        "invoice_candidate_register_ref": fixture.invoice_candidate_register_ref,
        "selection_intended_use": fixture.selection_intended_use,
        "recipient_confirmation_intended_use": fixture.recipient_confirmation_intended_use,
        "manual_send_intended_use": fixture.manual_send_intended_use,
        "proof_capture_required": fixture.proof_capture_required,
        "pdf_export_output_path_template": fixture.pdf_export_output_path_template,
        "pdf_scope_review_template": fixture.pdf_scope_review_template,
        "pdf_package_request_template": fixture.pdf_package_request_template,
        "known_manual_send_defaults": dict(fixture.known_manual_send_defaults),
        "allowed_send_coupa": fixture.allowed_send_coupa,
        "allowed_po": fixture.allowed_po,
        "supplier_portal_provider": fixture.supplier_portal_provider,
        "has_clara_voice": fixture.has_clara_voice,
    }


def _candidate_provider_status(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> tuple[tuple[dict[str, Any], ...], str]:
    candidates = tuple(dict(candidate) for candidate in fixture.invoice_candidates_provider())
    if candidates:
        return candidates, "CANDIDATES_AVAILABLE_FROM_FIXTURE"
    return (), "UNKNOWN_OR_PLANNED_NO_REAL_INVOICE_FACTS_PRESENT"


def _default_selected_candidate(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> dict[str, Any] | None:
    default_invoice_id = str(fixture.known_manual_send_defaults.get("invoice_id") or "").strip()
    if default_invoice_id:
        selected = fixture.candidate_lookup(default_invoice_id)
        if selected:
            return dict(selected)
    candidates, _status = _candidate_provider_status(fixture)
    return dict(candidates[0]) if candidates else None


def _source_workbook(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
) -> dict[str, Any]:
    return {
        "source_workbook_ref": fixture.invoice_client_default_candidate_ref,
        "source_workbook_mac_path": fixture.expected_workbook_path,
        "source_workbook_status": "FIXTURE_CONFIGURED",
        "workbook_body_read": False,
        "cell_read": False,
    }


def _descriptor_thread_ref(fixture: Mapping[str, Any], invoice_id: str) -> str:
    scope = invoice_id or "selected_invoice"
    return f"{fixture['workflow_ref']}:{scope}"


def build_prepare_pdf_action_descriptor(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
    *,
    selected_candidate: Mapping[str, Any] | None = None,
    source_workbook: Mapping[str, Any] | None = None,
    present_receipts: set[str] | None = None,
) -> dict[str, Any]:
    fixture_config = _fixture_config(fixture)
    selected = dict(selected_candidate) if selected_candidate is not None else _default_selected_candidate(fixture)
    source = dict(source_workbook) if source_workbook is not None else _source_workbook(fixture)
    package, completion_receipt = simple_invoice_workflow_builder.build_selected_invoice_pdf_export_package(
        fixture=fixture_config,
        selected_candidate=selected,
        source_workbook=source,
        present_receipts=set(present_receipts or set()),
    )
    request_ready = bool(package.get("request_payload_ready"))
    missing_requirements = tuple(package.get("missing_requirements") or ())
    invoice_id = str(package.get("invoice_id") or "")
    thread_ref = _descriptor_thread_ref(fixture_config, invoice_id)
    status = "READY_FOR_EVENT_BRIDGE_ACTION" if request_ready else "PLANNED_OR_UNKNOWN_SCOPE"
    if missing_requirements:
        status = "BLOCKED_MISSING_SCOPE_OR_SOURCE" if selected else "PLANNED_OR_UNKNOWN_SCOPE"
    return {
        "rail_ref": RAIL_REF,
        "descriptor_id": f"{RAIL_REF}:{fixture.client_ref}:{_short_hash(fixture.client_ref, invoice_id, package)}",
        "status": status,
        "client_ref": fixture.client_ref,
        "client_display_name": fixture.client_display_name,
        "workflow_ref": fixture.workflow_ref,
        "thread_ref": thread_ref,
        "world_ref": "finance",
        "actor_ref": "operator:winship",
        "invoice_id": invoice_id,
        "selected_invoice_summary": package.get("selected_invoice_summary"),
        "selected_sheet_label": package.get("selected_sheet_label"),
        "selected_page_label": package.get("selected_page_label"),
        "selected_print_areas": tuple(package.get("selected_print_areas") or ()),
        "source_workbook_mac_path": package.get("source_workbook_mac_path"),
        "output_filename": package.get("output_filename"),
        "output_mac_path": package.get("output_mac_path"),
        "output_bridge_path": package.get("output_bridge_path"),
        "prepare_action_kind": PREPARE_ACTION_KIND,
        "result_action_kind": RESULT_ACTION_KIND,
        "expected_response_kind": "WORKFLOW_ACTION_RESPONSE",
        "result_receipt_required": True,
        "required_receipts": tuple(package.get("required_receipts") or ()),
        "completion_receipt": completion_receipt,
        "missing_requirements": missing_requirements,
        "request_payload_ready": request_ready,
        "event_envelope_fields": event_contract.EVENT_ENVELOPE_FIELDS,
        "authority_profile_ref": event_contract.DEFAULT_AUTHORITY_PROFILE_REF,
        "authority_semantics_version": event_contract.AUTHORITY_SEMANTICS_VERSION,
        "safety_flags": dict(event_contract.DEFAULT_SAFETY_FLAGS),
        "authority_boundary": dict(event_contract.AUTHORITY_BOUNDARY),
        "manual_attach_link_fallback": {
            "role": "FALLBACK_ONLY",
            "primary_path": False,
            "fallback_intended_use": fixture.manual_send_intended_use,
            "do_not_treat_as_primary_event_bridge_rail": True,
        },
        "source_refs": (
            "simple_invoice_workflow_fixtures.py",
            "simple_invoice_workflow_builder.py",
            "openclaw_event_bridge_contract.py",
        ),
        "claims_not_made": tuple(NO_LIVE_ACTION_CLAIMS),
        "pdf_export_package": package,
    }


def make_prepare_pdf_event_from_descriptor(
    descriptor: Mapping[str, Any],
    *,
    source_channel: str = "MAC_APP",
    event_kind: str = "WORKFLOW_ACTION_REQUEST",
    event_id: str | None = None,
    created_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    return event_contract.make_simple_invoice_prepare_pdf_event(
        client_ref=str(descriptor["client_ref"]),
        workflow_ref=str(descriptor["workflow_ref"]),
        thread_ref=str(descriptor["thread_ref"]),
        invoice_id=str(descriptor.get("invoice_id") or ""),
        selected_invoice_summary=descriptor.get("selected_invoice_summary"),
        selected_sheet_label=str(descriptor.get("selected_sheet_label") or ""),
        selected_page_label=descriptor.get("selected_page_label"),
        selected_print_areas=tuple(descriptor.get("selected_print_areas") or ()),
        source_workbook_mac_path=str(descriptor.get("source_workbook_mac_path") or ""),
        output_bridge_path=str(descriptor.get("output_bridge_path") or ""),
        output_mac_path=str(descriptor.get("output_mac_path") or ""),
        client_display_name=str(descriptor.get("client_display_name") or ""),
        source_channel=source_channel,
        event_kind=event_kind,
        event_id=event_id,
        parent_event_id=f"current_{descriptor['client_ref']}_prepare_pdf_action",
        actor_ref=str(descriptor.get("actor_ref") or "operator:winship"),
        created_at=created_at,
        expires_at=expires_at,
    )


def build_result_candidate_shape(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rail_ref": RAIL_REF,
        "action_kind": RESULT_ACTION_KIND,
        "request_type": "LOCAL_SURFACE_RESULT",
        "client_ref": descriptor["client_ref"],
        "workflow_ref": descriptor["workflow_ref"],
        "thread_ref": descriptor["thread_ref"],
        "invoice_id": descriptor.get("invoice_id"),
        "expected_fields": (
            "exported_pdf_mac_path",
            "artifact_filename",
            "receipt_ref",
            "artifact_review_status",
            "attachment_ready",
            "approval_ready",
        ),
        "candidate_only": True,
        "attachment_ready_default": False,
        "approval_ready_default": False,
        "ledger_posting_allowed_default": False,
        **NO_LIVE_ACTION_CLAIMS,
    }


def build_client_profile(
    fixture: simple_invoice_workflow_fixtures.SimpleInvoiceClientFixture,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidates, candidate_status = _candidate_provider_status(fixture)
    selected = _default_selected_candidate(fixture)
    descriptor = build_prepare_pdf_action_descriptor(fixture, selected_candidate=selected)
    event_template: dict[str, Any] = {}
    if descriptor["request_payload_ready"]:
        event_template = make_prepare_pdf_event_from_descriptor(
            descriptor,
            created_at=generated_at,
        )
    client_rails = simple_invoice_workflow_builder.build_client_invoice_rails(fixture.client_ref, fixture.workflow_ref)
    candidate_selection_rail = simple_invoice_workflow_builder.build_generic_candidate_selection_rail(
        client_ref=fixture.client_ref,
        selection_mode="single_selected_invoice",
        candidate_selection_status=candidate_status,
        selected_invoice_ids=tuple(
            str(candidate.get("invoice_id") or "") for candidate in candidates if str(candidate.get("invoice_id") or "")
        ),
        selected_invoice_candidates=candidates,
        selected_invoice_summary=descriptor.get("selected_invoice_summary"),
        allow_multiple=False,
        max_candidates=1,
    )
    return {
        "client_ref": fixture.client_ref,
        "client_display_name": fixture.client_display_name,
        "workflow_ref": fixture.workflow_ref,
        "uses_rail": RAIL_REF,
        "simple_invoice_rail_only": True,
        "supplier_portal_required": bool(client_rails["supplier_portal_required"]),
        "purchase_order_required": bool(client_rails["purchase_order_required"]),
        "supplier_portal_provider": fixture.supplier_portal_provider,
        "candidate_selection_rail": candidate_selection_rail,
        "selected_invoice_status": "SELECTED_FROM_FIXTURE" if selected else "UNKNOWN_OR_PLANNED",
        "prepare_pdf_action_descriptor": descriptor,
        "prepare_pdf_event_template": event_template,
        "prepare_pdf_event_template_status": "AVAILABLE" if event_template else "PLANNED_REQUIRES_SELECTED_INVOICE_SCOPE",
        "result_candidate_shape": build_result_candidate_shape(descriptor),
        "safety_flags": dict(event_contract.DEFAULT_SAFETY_FLAGS),
        "authority_boundary": dict(event_contract.AUTHORITY_BOUNDARY),
    }


def _capital_hilton_separation() -> dict[str, Any]:
    recipe = invoice_framework.recipes_by_client_ref()["capital_hilton"]
    return {
        "client_ref": "capital_hilton",
        "workflow_ref": recipe["workflow_ref"],
        "simple_invoice_rail_required": False,
        "can_reuse_underlying_source_and_artifact_rails": True,
        "supplier_portal_extension_required": invoice_framework.recipe_selects_rail(
            recipe, invoice_framework.SUPPLIER_PORTAL_RAIL
        ),
        "purchase_order_extension_required": invoice_framework.recipe_selects_rail(
            recipe, invoice_framework.PURCHASE_ORDER_RAIL
        ),
        "portal_provider": recipe["client_specific_portal_requirements"]["portal_provider"],
        "do_not_apply_to_simple_clients": True,
    }


def build_registry_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or utc_now()
    profiles = tuple(build_client_profile(fixture, generated_at=generated) for fixture in _simple_fixtures())
    profile_by_ref = {profile["client_ref"]: profile for profile in profiles}
    safety_flag_sets = {stable_json(profile["safety_flags"]) for profile in profiles}
    router_handlers = tuple(asdict(handler) for handler in openclaw_request_router.default_handler_registrations())
    simple_handler_ids = tuple(
        handler["handler_id"]
        for handler in router_handlers
        if str(handler["handler_id"]).startswith("invoice_review_action_request.")
        and handler["intended_use"] == PREPARE_ACTION_KIND
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated,
        "rail_ref": RAIL_REF,
        "rail_status": "GENERIC_SIMPLE_INVOICE_EVENT_BRIDGE_RAIL_READY",
        "authority_semantics_version": event_contract.AUTHORITY_SEMANTICS_VERSION,
        "authority_profile_ref": event_contract.DEFAULT_AUTHORITY_PROFILE_REF,
        "positive_occupation_template_ref": event_contract.DEFAULT_POSITIVE_OCCUPATION_TEMPLATE_REF,
        "supported_event_bridge_fields": event_contract.EVENT_ENVELOPE_FIELDS,
        "supported_action_kinds": (PREPARE_ACTION_KIND, RESULT_ACTION_KIND),
        "supported_result_kinds": ("WORKFLOW_ACTION_RESPONSE", "LOCAL_SURFACE_RESULT_RESPONSE"),
        "source_refs": (
            "simple_invoice_event_bridge_rail_registry.py",
            "simple_invoice_workflow_fixtures.py",
            "simple_invoice_workflow_builder.py",
            "client_invoice_workflow_framework.py",
            "openclaw_event_bridge_contract.py",
            "openclaw_event_bridge_adapter.py",
            "openclaw_request_router.py",
        ),
        "client_profiles": profiles,
        "capital_hilton_separation": _capital_hilton_separation(),
        "registered_simple_invoice_prepare_handlers": simple_handler_ids,
        "authority_boundary": dict(event_contract.AUTHORITY_BOUNDARY),
        "safety_flags": dict(event_contract.DEFAULT_SAFETY_FLAGS),
        "claims_not_made": tuple(NO_LIVE_ACTION_CLAIMS),
        "machine_proof": {
            "rail_ref": RAIL_REF,
            "client_count": len(profiles),
            "all_simple_clients_use_generic_rail": all(profile["uses_rail"] == RAIL_REF for profile in profiles),
            "simple_clients_have_identical_safety_flags": len(safety_flag_sets) == 1,
            "dangerous_authority_grants_false": all(value is False for value in event_contract.AUTHORITY_BOUNDARY.values()),
            "manual_attach_link_fallback_only": all(
                profile["prepare_pdf_action_descriptor"]["manual_attach_link_fallback"]["role"] == "FALLBACK_ONLY"
                and profile["prepare_pdf_action_descriptor"]["manual_attach_link_fallback"]["primary_path"] is False
                for profile in profiles
            ),
            "capital_hilton_supplier_portal_extension_separate": _capital_hilton_separation()[
                "supplier_portal_extension_required"
            ],
            "capital_hilton_purchase_order_extension_separate": _capital_hilton_separation()[
                "purchase_order_extension_required"
            ],
            "simple_clients_do_not_inherit_coupa": all(
                profile["supplier_portal_required"] is False
                and profile["purchase_order_required"] is False
                and profile["supplier_portal_provider"] is None
                for profile in profiles
            ),
            "router_registers_simple_prepare_handlers": set(simple_handler_ids).issuperset(
                {f"invoice_review_action_request.{profile['client_ref']}" for profile in profiles}
            ),
            "selected_invoice_pdf_export_completed_candidate_shape_present": all(
                profile["result_candidate_shape"]["action_kind"] == RESULT_ACTION_KIND for profile in profiles
            ),
            **NO_LIVE_ACTION_CLAIMS,
        },
        "client_profile_proof": {
            client_ref: {
                "uses_rail": profile["uses_rail"],
                "prepare_pdf_event_template_status": profile["prepare_pdf_event_template_status"],
                "selected_invoice_status": profile["selected_invoice_status"],
                "supplier_portal_required": profile["supplier_portal_required"],
                "purchase_order_required": profile["purchase_order_required"],
            }
            for client_ref, profile in profile_by_ref.items()
        },
    }
    payload["machine_proof"]["content_hash"] = "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return payload


def format_operator_readback(payload: Mapping[str, Any]) -> str:
    profiles = payload.get("client_profiles") or ()
    lines = [
        "# Simple Invoice Event Bridge Rail Registry",
        "",
        f"- Rail: {payload['rail_ref']}",
        "- Status: generated deterministic read-model; no live action authority.",
        "- Pattern: simple invoice clients use one Event Bridge prepare-PDF action and one candidate-result shape.",
        "- Boundary: no email, Gmail, browser, Coupa, ledger, workbook cell read, PDF export, service start, or handler execution.",
        "",
        "## Clients",
    ]
    for profile in profiles:
        descriptor = profile["prepare_pdf_action_descriptor"]
        lines.append(
            f"- {profile['client_display_name']} ({profile['client_ref']}): "
            f"{profile['uses_rail']}; descriptor {descriptor['status']}."
        )
    separation = payload["capital_hilton_separation"]
    lines.extend(
        [
            "",
            "## Separation",
            "",
            (
                "- Capital Hilton remains complex: "
                f"supplier portal={separation['supplier_portal_extension_required']}, "
                f"purchase order={separation['purchase_order_extension_required']}; "
                "these blockers are not inherited by simple clients."
            ),
            "",
            "## Next Safe Move",
            "",
            "- Emit client-specific Event Bridge envelopes from fixture/config scope; keep manual attach/link as fallback only.",
            "- Add real client invoice facts only when a source fixture or receipt exists.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_readback(payload), encoding="utf-8")
    return json_path, operator_path


def export_simple_invoice_event_bridge_rail_registry(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    payload = build_registry_payload(generated_at=generated_at)
    json_path, operator_path = write_exports(payload, export_root=export_root)
    return payload, json_path, operator_path


__all__ = [
    "DEFAULT_EXPORT_ROOT",
    "JSON_EXPORT_NAME",
    "NO_LIVE_ACTION_CLAIMS",
    "OPERATOR_EXPORT_NAME",
    "PREPARE_ACTION_KIND",
    "RAIL_REF",
    "READ_MODEL_ID",
    "RESULT_ACTION_KIND",
    "SCHEMA_VERSION",
    "build_client_profile",
    "build_prepare_pdf_action_descriptor",
    "build_registry_payload",
    "export_simple_invoice_event_bridge_rail_registry",
    "format_operator_readback",
    "make_prepare_pdf_event_from_descriptor",
    "stable_json",
    "write_exports",
]
