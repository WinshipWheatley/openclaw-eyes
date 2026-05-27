"""Composable client invoice workflow framework v0.

This read-model defines reusable invoice workflow rails and client-specific
recipes. Capital Hilton is represented as one complex recipe, not as a universal
default. This module does not execute invoice generation, portal submission,
email send, ledger posting, workbook reads, browser automation, or credential
handling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "client_invoice_workflow_framework_v0"
READ_MODEL_ID = "client_invoice_workflow_framework"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "COMPOSABLE_CLIENT_INVOICE_WORKFLOW_FRAMEWORK_NO_ACTIONS"

SOURCE_WORKBOOK_RAIL = "source_workbook_rail"
INVOICE_PERIOD_SHEET_RAIL = "invoice_period_sheet_rail"
PERFORMANCE_DATE_CONFIRMATION_RAIL = "performance_date_confirmation_rail"
PURCHASE_ORDER_RAIL = "purchase_order_rail"
SUPPLIER_PORTAL_RAIL = "supplier_portal_rail"
EXCEL_INVOICE_GENERATION_RAIL = "excel_invoice_generation_rail"
PDF_EXPORT_RAIL = "pdf_export_rail"
CLARA_EMAIL_DRAFT_RAIL = "clara_email_draft_rail"
GUARDIAN_APPROVAL_RAIL = "guardian_approval_rail"
EXTERNAL_SEND_RAIL = "external_send_rail"
PAYMENT_WATCH_RAIL = "payment_watch_rail"
LEDGER_HANDOFF_RAIL = "ledger_handoff_rail"
TAX_EVIDENCE_RAIL = "tax_evidence_rail"

ALL_SUCCESS_LAYERS = (
    "source_ready",
    "facts_proposed",
    "facts_confirmed",
    "package_ready",
    "portal_submitted",
    "client_email_sent",
    "payment_expected",
    "payment_detected",
    "payment_reconciled",
    "ledger_ready",
    "tax_evidence_ready",
    "workflow_complete",
)

RECEIPT_RULES = (
    "A draft is not sent.",
    "A generated invoice is not submitted.",
    "A portal draft is not portal-submitted.",
    "Guardian approval is not execution.",
    "Email sent is not payment.",
    "Payment detected is not ledger-posted.",
    "Ledger-ready is not tax-filed.",
    "A selected rail is complete only when that rail's required receipts exist.",
)

AUTHORITY_BOUNDARY = {
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "invoice_generation_allowed": False,
    "pdf_export_allowed": False,
    "email_draft_send_allowed": False,
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "coupa_access_allowed": False,
    "coupa_submit_allowed": False,
    "browser_automation_allowed": False,
    "credential_handling_allowed": False,
    "external_action_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "tax_filing_allowed": False,
    "payment_mark_paid_allowed": False,
    "production_state_mutation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "network_allowed": False,
}


@dataclass(frozen=True)
class InvoiceWorkflowRail:
    rail_ref: str
    purpose: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    required_receipts: tuple[str, ...]
    output_receipts: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    readiness_states: tuple[str, ...]
    blockers: tuple[str, ...]
    operator_confirmation_points: tuple[str, ...]
    default_optional: bool
    next_safe_move: str


@dataclass(frozen=True)
class RecipeRailSelection:
    rail_ref: str
    required_for_recipe: bool
    recipe_notes: str


@dataclass(frozen=True)
class ClientInvoiceRecipe:
    client_ref: str
    client_display_name: str
    workflow_ref: str
    selected_rails: tuple[RecipeRailSelection, ...]
    rail_order: tuple[str, ...]
    rail_dependencies: dict[str, tuple[str, ...]]
    required_success_layers: tuple[str, ...]
    optional_success_layers: tuple[str, ...]
    client_specific_contacts: tuple[dict[str, Any], ...]
    client_specific_portal_requirements: dict[str, Any]
    client_specific_invoice_artifact_requirements: dict[str, Any]
    client_specific_payment_expectations: dict[str, Any]
    client_specific_ledger_tax_handoff_rules: dict[str, Any]
    candidate_facts_and_policies: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class RailEvaluation:
    rail_ref: str
    selected: bool
    required_for_recipe: bool
    complete: bool
    state: str
    required_receipts: tuple[str, ...]
    present_receipts: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    output_receipts: tuple[str, ...]
    no_action_performed: bool
    next_safe_move: str


@dataclass(frozen=True)
class RecipeSuccessEvaluation:
    recipe_ref: str
    client_ref: str
    required_success_layers: tuple[str, ...]
    success_layers: dict[str, dict[str, Any]]
    rail_evaluations: tuple[dict[str, Any], ...]
    workflow_complete: bool
    missing_required_rails: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _rail(
    rail_ref: str,
    purpose: str,
    *,
    required_inputs: tuple[str, ...],
    optional_inputs: tuple[str, ...] = (),
    required_receipts: tuple[str, ...],
    output_receipts: tuple[str, ...],
    allowed_actions: tuple[str, ...] = ("readiness_readback",),
    forbidden_actions: tuple[str, ...] = (),
    readiness_states: tuple[str, ...] = ("NOT_READY", "READY_WITH_RECEIPTS", "COMPLETE_WITH_RECEIPTS"),
    blockers: tuple[str, ...] = (),
    operator_confirmation_points: tuple[str, ...] = (),
    default_optional: bool = True,
    next_safe_move: str = "Collect required receipts before advancing this rail.",
) -> InvoiceWorkflowRail:
    blocked = (
        "send_without_send_receipt",
        "submit_without_submission_receipt",
        "mark_paid_without_payment_receipt",
        "ledger_post_without_ledger_receipt",
        "credential_or_browser_action_without_future_authority",
    )
    return InvoiceWorkflowRail(
        rail_ref=rail_ref,
        purpose=purpose,
        required_inputs=required_inputs,
        optional_inputs=optional_inputs,
        required_receipts=required_receipts,
        output_receipts=output_receipts,
        allowed_actions=allowed_actions,
        forbidden_actions=tuple(dict.fromkeys(forbidden_actions + blocked)),
        readiness_states=readiness_states,
        blockers=blockers,
        operator_confirmation_points=operator_confirmation_points,
        default_optional=default_optional,
        next_safe_move=next_safe_move,
    )


def build_invoice_workflow_rails() -> tuple[dict[str, Any], ...]:
    rails = (
        _rail(
            SOURCE_WORKBOOK_RAIL,
            "Bind the current source workbook reference for a client without reading workbook body/cells.",
            required_inputs=("client_ref", "workflow_ref", "workbook_reference"),
            required_receipts=("source_workbook_reference_receipt",),
            output_receipts=("source_ready_receipt",),
            forbidden_actions=("workbook_body_read", "spreadsheet_cell_read", "source_workbook_write"),
            default_optional=False,
        ),
        _rail(
            INVOICE_PERIOD_SHEET_RAIL,
            "Identify the invoice period/sheet scope or ask for it when ambiguous.",
            required_inputs=("source_workbook_reference_receipt", "period_or_sheet_candidate"),
            required_receipts=("invoice_period_or_sheet_scope_receipt",),
            output_receipts=("facts_proposed_receipt",),
            forbidden_actions=("spreadsheet_cell_read_without_future_audit",),
        ),
        _rail(
            PERFORMANCE_DATE_CONFIRMATION_RAIL,
            "Confirm service/performance dates before invoice facts become confirmed.",
            required_inputs=("performance_date_candidates", "rate_policy_candidate"),
            required_receipts=("performance_dates_confirmed_receipt", "rate_policy_confirmed_receipt"),
            output_receipts=("facts_confirmed_receipt",),
            operator_confirmation_points=("Confirm dates and rate before invoice package is approved.",),
        ),
        _rail(
            PURCHASE_ORDER_RAIL,
            "Require a PO/reference only for recipes that select this rail.",
            required_inputs=("client_ref", "po_or_reference_candidate"),
            required_receipts=("purchase_order_confirmed_receipt",),
            output_receipts=("po_ready_receipt",),
            forbidden_actions=("invent_purchase_order", "portal_submit_without_po"),
            operator_confirmation_points=("Confirm PO/reference or explicit no-PO posture.",),
        ),
        _rail(
            SUPPLIER_PORTAL_RAIL,
            "Prepare or submit supplier portal invoice only when recipe requires it and receipts exist.",
            required_inputs=("portal_config", "purchase_order_confirmed_receipt", "invoice_package_ready_receipt"),
            required_receipts=("portal_invoice_submission_receipt",),
            output_receipts=("portal_submitted_receipt", "payment_expected_receipt"),
            forbidden_actions=("browser_automation", "coupa_access", "coupa_submit", "credential_handling"),
            operator_confirmation_points=("Approve portal submission separately from draft/package readiness.",),
        ),
        _rail(
            EXCEL_INVOICE_GENERATION_RAIL,
            "Generate or prove the Excel invoice artifact when a recipe requires an invoice file for records.",
            required_inputs=("facts_confirmed_receipt", "client_invoice_template_policy"),
            required_receipts=("excel_invoice_generated_receipt",),
            output_receipts=("invoice_artifact_ready_receipt",),
            forbidden_actions=("excel_write_without_future_generator_receipt", "overwrite_source_workbook"),
        ),
        _rail(
            PDF_EXPORT_RAIL,
            "Export PDF only for recipes that select PDF delivery.",
            required_inputs=("invoice_artifact_ready_receipt",),
            required_receipts=("pdf_exported_receipt",),
            output_receipts=("pdf_artifact_ready_receipt",),
            forbidden_actions=("pdf_export_without_generator_receipt",),
        ),
        _rail(
            CLARA_EMAIL_DRAFT_RAIL,
            "Draft client-facing email wording in Clara voice; draft does not send.",
            required_inputs=("invoice_artifact_ready_receipt", "client_contact_candidate"),
            required_receipts=("clara_email_draft_receipt", "invoice_attachment_proof_receipt"),
            output_receipts=("email_draft_ready_receipt",),
            allowed_actions=("draft_text_only", "readiness_readback"),
            forbidden_actions=("email_send", "gmail_send", "claim_sent", "claim_delivered"),
            operator_confirmation_points=("Review Clara draft and attachment proof before send approval.",),
        ),
        _rail(
            GUARDIAN_APPROVAL_RAIL,
            "Validate that package, portal, email, and attachment proofs are ready for operator approval.",
            required_inputs=("package_ready_receipt", "rail_proof_refs"),
            required_receipts=("guardian_approval_receipt", "operator_approval_receipt"),
            output_receipts=("approval_ready_receipt",),
            allowed_actions=("approval_readiness_readback",),
            forbidden_actions=("execute_approval", "send", "submit"),
            operator_confirmation_points=("Operator approval is separate from Guardian review.",),
        ),
        _rail(
            EXTERNAL_SEND_RAIL,
            "Send email or external delivery only after explicit send receipt exists; not enabled here.",
            required_inputs=("guardian_approval_receipt", "operator_approval_receipt", "email_draft_ready_receipt"),
            required_receipts=("email_send_receipt",),
            output_receipts=("client_email_sent_receipt",),
            forbidden_actions=("email_send", "gmail_access", "claim_sent_without_receipt"),
            operator_confirmation_points=("Confirm final recipient list and attachment before any future send adapter.",),
        ),
        _rail(
            PAYMENT_WATCH_RAIL,
            "Watch for payment/check evidence after expected payment is created by the recipe.",
            required_inputs=("payment_expected_receipt",),
            required_receipts=("payment_detected_receipt",),
            output_receipts=("payment_detected_receipt", "payment_reconciled_candidate_receipt"),
            forbidden_actions=("mark_paid_without_payment_evidence", "bank_access_without_future_authority"),
        ),
        _rail(
            LEDGER_HANDOFF_RAIL,
            "Prepare ledger handoff only after payment evidence exists; handoff is not ledger posting.",
            required_inputs=("payment_detected_receipt", "invoice_package_ready_receipt"),
            required_receipts=("ledger_handoff_ready_receipt",),
            output_receipts=("ledger_ready_receipt",),
            forbidden_actions=("ledger_posting", "mark_paid", "claim_reconciled_without_receipt"),
        ),
        _rail(
            TAX_EVIDENCE_RAIL,
            "Prepare tax evidence package only after invoice/payment/ledger refs exist.",
            required_inputs=("ledger_ready_receipt", "payment_detected_receipt"),
            required_receipts=("tax_evidence_ready_receipt",),
            output_receipts=("tax_evidence_ready_receipt",),
            forbidden_actions=("tax_filing", "ledger_posting", "mark_tax_filed"),
        ),
    )
    return tuple(asdict(rail) for rail in rails)


def _selection(rail_ref: str, required: bool, notes: str) -> RecipeRailSelection:
    return RecipeRailSelection(rail_ref=rail_ref, required_for_recipe=required, recipe_notes=notes)


def _contact(name: str, role: str, *, status: str = "CANDIDATE_UNCONFIRMED") -> dict[str, Any]:
    return {"name": name, "role": role, "status": status}


def build_capital_hilton_recipe() -> dict[str, Any]:
    selected = (
        _selection(SOURCE_WORKBOOK_RAIL, True, "Running source workbook is the source rail."),
        _selection(INVOICE_PERIOD_SHEET_RAIL, True, "Invoice period/sheet scope must be identified."),
        _selection(PERFORMANCE_DATE_CONFIRMATION_RAIL, True, "Performance dates and $400/show policy require confirmation."),
        _selection(PURCHASE_ORDER_RAIL, True, "Coupa invoice must be created from a purchase order/reference."),
        _selection(SUPPLIER_PORTAL_RAIL, True, "Coupa supplier portal invoice is the real payment trigger."),
        _selection(EXCEL_INVOICE_GENERATION_RAIL, True, "Annette needs Excel-generated invoice for records."),
        _selection(CLARA_EMAIL_DRAFT_RAIL, True, "Clara drafts email to Annette, likely CC Chyna and Will after confirmation."),
        _selection(GUARDIAN_APPROVAL_RAIL, True, "Guardian/operator approval required before any send/submit action."),
        _selection(EXTERNAL_SEND_RAIL, True, "Email send receipt required before client_email_sent."),
        _selection(PAYMENT_WATCH_RAIL, True, "Bank/check watch follows expected payment."),
        _selection(LEDGER_HANDOFF_RAIL, True, "Ledger handoff follows payment evidence."),
        _selection(TAX_EVIDENCE_RAIL, True, "Tax evidence follows ledger/payment refs."),
    )
    recipe = ClientInvoiceRecipe(
        client_ref="capital_hilton",
        client_display_name="Capital Hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        selected_rails=selected,
        rail_order=tuple(item.rail_ref for item in selected),
        rail_dependencies={
            SOURCE_WORKBOOK_RAIL: (),
            INVOICE_PERIOD_SHEET_RAIL: (SOURCE_WORKBOOK_RAIL,),
            PERFORMANCE_DATE_CONFIRMATION_RAIL: (INVOICE_PERIOD_SHEET_RAIL,),
            PURCHASE_ORDER_RAIL: (PERFORMANCE_DATE_CONFIRMATION_RAIL,),
            SUPPLIER_PORTAL_RAIL: (PURCHASE_ORDER_RAIL, EXCEL_INVOICE_GENERATION_RAIL, GUARDIAN_APPROVAL_RAIL),
            EXCEL_INVOICE_GENERATION_RAIL: (PERFORMANCE_DATE_CONFIRMATION_RAIL, PURCHASE_ORDER_RAIL),
            CLARA_EMAIL_DRAFT_RAIL: (EXCEL_INVOICE_GENERATION_RAIL,),
            GUARDIAN_APPROVAL_RAIL: (PURCHASE_ORDER_RAIL, EXCEL_INVOICE_GENERATION_RAIL, CLARA_EMAIL_DRAFT_RAIL),
            EXTERNAL_SEND_RAIL: (CLARA_EMAIL_DRAFT_RAIL, GUARDIAN_APPROVAL_RAIL),
            PAYMENT_WATCH_RAIL: (SUPPLIER_PORTAL_RAIL,),
            LEDGER_HANDOFF_RAIL: (PAYMENT_WATCH_RAIL,),
            TAX_EVIDENCE_RAIL: (LEDGER_HANDOFF_RAIL,),
        },
        required_success_layers=(
            "source_ready",
            "facts_proposed",
            "facts_confirmed",
            "package_ready",
            "portal_submitted",
            "client_email_sent",
            "payment_expected",
            "payment_detected",
            "payment_reconciled",
            "ledger_ready",
            "tax_evidence_ready",
            "workflow_complete",
        ),
        optional_success_layers=(),
        client_specific_contacts=(
            _contact("Annette", "primary finance contact candidate"),
            _contact("Chyna", "finance-involved CC candidate"),
            _contact("Will", "relationship/hiring contact candidate"),
        ),
        client_specific_portal_requirements={
            "supplier_portal_required": True,
            "portal_ref": "coupa_supplier_portal",
            "purchase_order_required": True,
            "portal_submission_is_payment_trigger": True,
            "portal_submission_proof_required": True,
        },
        client_specific_invoice_artifact_requirements={
            "excel_invoice_required_for_annette_records": True,
            "excel_invoice_attachment_proof_required": True,
            "pdf_export_required": False,
            "clara_email_draft_required": True,
            "email_to_candidate": "Annette",
            "cc_candidates": ("Chyna", "Will"),
        },
        client_specific_payment_expectations={
            "payment_watch_required": True,
            "expected_payment_signal": "bank/check detection after Coupa invoice",
            "payment_detection_drives_ledger_tax_success": True,
        },
        client_specific_ledger_tax_handoff_rules={
            "ledger_handoff_required": True,
            "tax_evidence_required": True,
            "ledger_posting_requires_future_receipt": True,
        },
        candidate_facts_and_policies=(
            "weekly recurring gig until otherwise noted",
            "default rate candidate: $400/show",
            "possible PO around $2,000",
            "invoice may include 5 gigs if policy/PO/operator approval supports it",
            "3 gigs may already have happened and 2 may be upcoming",
            "all contact roles remain candidate/unconfirmed until confirmed",
        ),
        next_safe_move="Confirm PO/reference, dates/rate, artifact proof, Clara draft, and approvals before any send or Coupa submit.",
    )
    return asdict(recipe)


def _simple_email_recipe(client_ref: str, display_name: str, workflow_ref: str) -> dict[str, Any]:
    selected = (
        _selection(SOURCE_WORKBOOK_RAIL, True, "Client-specific workbook/source rail."),
        _selection(INVOICE_PERIOD_SHEET_RAIL, True, "Invoice period/sheet scope if workbook-based."),
        _selection(EXCEL_INVOICE_GENERATION_RAIL, True, "Invoice artifact generation/proof when configured."),
        _selection(CLARA_EMAIL_DRAFT_RAIL, True, "Client-safe draft or status copy."),
        _selection(GUARDIAN_APPROVAL_RAIL, True, "Approval before any future external send."),
        _selection(EXTERNAL_SEND_RAIL, True, "Send receipt required if email delivery is used."),
        _selection(PAYMENT_WATCH_RAIL, True, "Payment watch after expected payment."),
        _selection(LEDGER_HANDOFF_RAIL, True, "Ledger handoff after payment evidence."),
        _selection(TAX_EVIDENCE_RAIL, True, "Tax evidence after ledger/payment refs."),
    )
    recipe = ClientInvoiceRecipe(
        client_ref=client_ref,
        client_display_name=display_name,
        workflow_ref=workflow_ref,
        selected_rails=selected,
        rail_order=tuple(item.rail_ref for item in selected),
        rail_dependencies={
            SOURCE_WORKBOOK_RAIL: (),
            INVOICE_PERIOD_SHEET_RAIL: (SOURCE_WORKBOOK_RAIL,),
            EXCEL_INVOICE_GENERATION_RAIL: (INVOICE_PERIOD_SHEET_RAIL,),
            CLARA_EMAIL_DRAFT_RAIL: (EXCEL_INVOICE_GENERATION_RAIL,),
            GUARDIAN_APPROVAL_RAIL: (CLARA_EMAIL_DRAFT_RAIL,),
            EXTERNAL_SEND_RAIL: (CLARA_EMAIL_DRAFT_RAIL, GUARDIAN_APPROVAL_RAIL),
            PAYMENT_WATCH_RAIL: (EXTERNAL_SEND_RAIL,),
            LEDGER_HANDOFF_RAIL: (PAYMENT_WATCH_RAIL,),
            TAX_EVIDENCE_RAIL: (LEDGER_HANDOFF_RAIL,),
        },
        required_success_layers=(
            "source_ready",
            "facts_proposed",
            "package_ready",
            "client_email_sent",
            "payment_expected",
            "payment_detected",
            "payment_reconciled",
            "ledger_ready",
            "tax_evidence_ready",
            "workflow_complete",
        ),
        optional_success_layers=("portal_submitted", "facts_confirmed"),
        client_specific_contacts=(),
        client_specific_portal_requirements={
            "supplier_portal_required": False,
            "purchase_order_required": False,
            "portal_ref": None,
            "configure_only_if_client_requires_it": True,
        },
        client_specific_invoice_artifact_requirements={
            "invoice_artifact_generation_required": True,
            "email_delivery_likely": True,
            "pdf_export_required": False,
            "portal_submission_required": False,
        },
        client_specific_payment_expectations={
            "payment_watch_required": True,
            "expected_payment_signal": "client payment evidence/check/bank signal after invoice delivery",
        },
        client_specific_ledger_tax_handoff_rules={
            "ledger_handoff_required": True,
            "tax_evidence_required": True,
            "ledger_posting_requires_future_receipt": True,
        },
        candidate_facts_and_policies=("placeholder recipe; client-specific PO/portal rails are not inherited by default",),
        next_safe_move=f"Use the simple {display_name} recipe until a PO/portal requirement is configured.",
    )
    return asdict(recipe)


def build_client_invoice_recipes() -> tuple[dict[str, Any], ...]:
    return (
        build_capital_hilton_recipe(),
        _simple_email_recipe("st_annes", "St. Anne's", "st_annes_invoice_workflow"),
        _simple_email_recipe("live_arts_md", "Live Arts MD", "live_arts_md_invoice_workflow"),
    )


def rails_by_ref() -> dict[str, dict[str, Any]]:
    return {rail["rail_ref"]: rail for rail in build_invoice_workflow_rails()}


def recipes_by_client_ref() -> dict[str, dict[str, Any]]:
    return {recipe["client_ref"]: recipe for recipe in build_client_invoice_recipes()}


def recipe_requires_rail(recipe: Mapping[str, Any], rail_ref: str) -> bool:
    return any(item["rail_ref"] == rail_ref and item["required_for_recipe"] for item in recipe.get("selected_rails", ()))


def recipe_selects_rail(recipe: Mapping[str, Any], rail_ref: str) -> bool:
    return any(item["rail_ref"] == rail_ref for item in recipe.get("selected_rails", ()))


def _normalize_receipts(receipts: Mapping[str, Any] | set[str] | tuple[str, ...] | list[str]) -> set[str]:
    if isinstance(receipts, Mapping):
        return {str(key) for key, value in receipts.items() if bool(value)}
    return {str(item) for item in receipts}


def evaluate_recipe(client_ref: str, receipts: Mapping[str, Any] | set[str] | tuple[str, ...] | list[str]) -> dict[str, Any]:
    recipes = recipes_by_client_ref()
    if client_ref not in recipes:
        raise KeyError(f"Unknown client recipe: {client_ref}")
    recipe = recipes[client_ref]
    rails = rails_by_ref()
    receipt_set = _normalize_receipts(receipts)
    selected = {item["rail_ref"]: item for item in recipe["selected_rails"]}
    evaluations: list[RailEvaluation] = []
    missing_required: list[str] = []
    completed_rails: set[str] = set()
    for rail_ref in recipe["rail_order"]:
        rail = rails[rail_ref]
        selection = selected[rail_ref]
        required = bool(selection["required_for_recipe"])
        required_receipts = tuple(rail["required_receipts"])
        present = tuple(receipt for receipt in required_receipts if receipt in receipt_set)
        missing = tuple(receipt for receipt in required_receipts if receipt not in receipt_set)
        complete = not missing
        if complete:
            completed_rails.add(rail_ref)
        elif required:
            missing_required.append(rail_ref)
        evaluations.append(
            RailEvaluation(
                rail_ref=rail_ref,
                selected=True,
                required_for_recipe=required,
                complete=complete,
                state="COMPLETE_WITH_RECEIPTS" if complete else "BLOCKED_MISSING_RECEIPTS",
                required_receipts=required_receipts,
                present_receipts=present,
                missing_receipts=missing,
                output_receipts=tuple(rail["output_receipts"]),
                no_action_performed=True,
                next_safe_move="Continue to the next dependent rail." if complete else "Collect missing receipts before advancing.",
            )
        )

    portal_submitted = SUPPLIER_PORTAL_RAIL in completed_rails if recipe_selects_rail(recipe, SUPPLIER_PORTAL_RAIL) else False
    email_sent = EXTERNAL_SEND_RAIL in completed_rails if recipe_selects_rail(recipe, EXTERNAL_SEND_RAIL) else False
    payment_detected = PAYMENT_WATCH_RAIL in completed_rails if recipe_selects_rail(recipe, PAYMENT_WATCH_RAIL) else False
    ledger_ready = LEDGER_HANDOFF_RAIL in completed_rails if recipe_selects_rail(recipe, LEDGER_HANDOFF_RAIL) else False
    tax_ready = TAX_EVIDENCE_RAIL in completed_rails if recipe_selects_rail(recipe, TAX_EVIDENCE_RAIL) else False
    package_ready = (
        EXCEL_INVOICE_GENERATION_RAIL in completed_rails
        and CLARA_EMAIL_DRAFT_RAIL in completed_rails
        and (
            not recipe_selects_rail(recipe, PURCHASE_ORDER_RAIL)
            or PURCHASE_ORDER_RAIL in completed_rails
        )
    )
    facts_confirmed = (
        PERFORMANCE_DATE_CONFIRMATION_RAIL in completed_rails
        if recipe_selects_rail(recipe, PERFORMANCE_DATE_CONFIRMATION_RAIL)
        else INVOICE_PERIOD_SHEET_RAIL in completed_rails
    )
    payment_expected = portal_submitted or email_sent
    payment_reconciled = payment_detected and ledger_ready

    base_layers = {
        "source_ready": SOURCE_WORKBOOK_RAIL in completed_rails,
        "facts_proposed": INVOICE_PERIOD_SHEET_RAIL in completed_rails,
        "facts_confirmed": facts_confirmed,
        "package_ready": package_ready,
        "portal_submitted": portal_submitted,
        "client_email_sent": email_sent,
        "payment_expected": payment_expected,
        "payment_detected": payment_detected,
        "payment_reconciled": payment_reconciled,
        "ledger_ready": ledger_ready,
        "tax_evidence_ready": tax_ready,
    }
    required_without_workflow_complete = tuple(
        layer for layer in recipe["required_success_layers"] if layer != "workflow_complete"
    )
    workflow_complete = not missing_required and all(base_layers.get(layer, False) for layer in required_without_workflow_complete)
    success_layers: dict[str, dict[str, Any]] = {}
    for layer in ALL_SUCCESS_LAYERS:
        if layer == "workflow_complete":
            complete = workflow_complete
        else:
            complete = bool(base_layers.get(layer, False))
        success_layers[layer] = {
            "required_for_recipe": layer in recipe["required_success_layers"],
            "complete": complete,
            "state": "COMPLETE_WITH_RECEIPTS" if complete else "NOT_COMPLETE",
        }
    return asdict(
        RecipeSuccessEvaluation(
            recipe_ref=recipe["workflow_ref"],
            client_ref=client_ref,
            required_success_layers=tuple(recipe["required_success_layers"]),
            success_layers=success_layers,
            rail_evaluations=tuple(asdict(item) for item in evaluations),
            workflow_complete=workflow_complete,
            missing_required_rails=tuple(dict.fromkeys(missing_required)),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=(
                "Workflow complete by selected recipe receipts."
                if workflow_complete
                else "Collect missing required rail receipts; do not claim completion."
            ),
        )
    )


def _receipt_set_for_recipe(client_ref: str, *, omit: tuple[str, ...] = ()) -> tuple[str, ...]:
    recipe = recipes_by_client_ref()[client_ref]
    rails = rails_by_ref()
    receipts: list[str] = []
    for item in recipe["selected_rails"]:
        if item["required_for_recipe"]:
            receipts.extend(rails[item["rail_ref"]]["required_receipts"])
    return tuple(receipt for receipt in dict.fromkeys(receipts) if receipt not in set(omit))


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    rails = build_invoice_workflow_rails()
    recipes = build_client_invoice_recipes()
    capital_incomplete = evaluate_recipe("capital_hilton", _receipt_set_for_recipe("capital_hilton", omit=("email_send_receipt",)))
    capital_complete = evaluate_recipe("capital_hilton", _receipt_set_for_recipe("capital_hilton"))
    st_annes_complete = evaluate_recipe("st_annes", _receipt_set_for_recipe("st_annes"))
    live_arts_complete = evaluate_recipe("live_arts_md", _receipt_set_for_recipe("live_arts_md"))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "rails": rails,
        "recipes": recipes,
        "receipt_rules": RECEIPT_RULES,
        "success_layers": ALL_SUCCESS_LAYERS,
        "examples": {
            "capital_hilton_missing_email_send": capital_incomplete,
            "capital_hilton_complete_with_all_required_receipts": capital_complete,
            "st_annes_complete_without_coupa": st_annes_complete,
            "live_arts_md_complete_without_coupa": live_arts_complete,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "operator_summary": (
            "Client invoice workflows are recipes made from rails. Capital Hilton uses a complex Coupa + Excel + "
            "Clara email + payment watch recipe. St. Anne's and Live Arts MD do not inherit Coupa or PO rails by default."
        ),
        "machine_proof": {
            "reusable_rails_defined": len(rails) >= 12,
            "capital_hilton_has_coupa_recipe": recipe_selects_rail(recipes[0], SUPPLIER_PORTAL_RAIL),
            "st_annes_has_no_coupa_by_default": not recipe_selects_rail(recipes[1], SUPPLIER_PORTAL_RAIL),
            "live_arts_md_has_no_coupa_by_default": not recipe_selects_rail(recipes[2], SUPPLIER_PORTAL_RAIL),
            "capital_hilton_workflow_incomplete_without_email_send": not capital_incomplete["workflow_complete"],
            "non_coupa_recipe_can_complete_without_coupa": st_annes_complete["workflow_complete"]
            and live_arts_complete["workflow_complete"],
            "draft_does_not_equal_sent": "email_send_receipt" not in rails_by_ref()[CLARA_EMAIL_DRAFT_RAIL]["required_receipts"],
            "guardian_approval_is_not_execution": "email_send_receipt"
            not in rails_by_ref()[GUARDIAN_APPROVAL_RAIL]["required_receipts"],
            "payment_detection_is_not_ledger_posting": "ledger_handoff_ready_receipt"
            not in rails_by_ref()[PAYMENT_WATCH_RAIL]["required_receipts"],
            "all_action_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    proof = payload["machine_proof"]
    lines = [
        "# Client Invoice Workflow Framework",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Reusable rails: {len(payload['rails'])}",
        "Capital Hilton: complex Coupa + Excel + Clara + approval + payment watch recipe.",
        "St. Anne's: no Coupa or PO rail unless configured.",
        "Live Arts MD: no Coupa or PO rail unless configured.",
        f"Capital Hilton blocked without send receipt: {str(proof['capital_hilton_workflow_incomplete_without_email_send']).lower()}",
        f"Non-Coupa placeholders can complete without Coupa: {str(proof['non_coupa_recipe_can_complete_without_coupa']).lower()}",
        "",
        "Receipt rules:",
        *[f"- {rule}" for rule in RECEIPT_RULES],
        "",
        "No workbook reads, Coupa access, email send, ledger posting, or production mutation authority is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export client invoice workflow framework read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "rail_count": len(payload["rails"]),
                    "capital_hilton_has_coupa_recipe": payload["machine_proof"]["capital_hilton_has_coupa_recipe"],
                    "all_action_authority_false": payload["machine_proof"]["all_action_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
