"""Shared fixtures for simple invoice workflow clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import live_arts_md_workbook_handoff


SimpleInvoiceProofDefaults = dict[str, Any]
SimpleInvoiceRecipientBuilder = Callable[[bool], Mapping[str, Any]]
SimpleInvoiceCandidateLookup = Callable[[str], Mapping[str, Any] | None]
SimpleInvoiceCandidates = Callable[[], tuple[dict[str, Any], ...]]
SimpleInvoiceCandidateRegisterBuilder = Callable[[], Mapping[str, Any]]


@dataclass(frozen=True)
class SimpleInvoiceClientFixture:
    client_ref: str
    client_display_name: str
    workflow_ref: str
    expected_workbook_name: str
    expected_workbook_path: str
    invoice_client_default_candidate_ref: str
    invoice_candidate_register_ref: str
    selection_intended_use: str
    recipient_confirmation_intended_use: str
    manual_send_intended_use: str
    proof_capture_required: tuple[str, ...]
    pdf_export_output_path_template: str
    pdf_scope_review_template: str
    pdf_package_request_template: str
    known_manual_send_defaults: SimpleInvoiceProofDefaults
    invoice_candidates_provider: SimpleInvoiceCandidates
    candidate_register_builder: SimpleInvoiceCandidateRegisterBuilder
    candidate_lookup: SimpleInvoiceCandidateLookup
    recipient_package_builder: SimpleInvoiceRecipientBuilder
    allowed_send_coupa: bool = False
    allowed_po: bool = False
    supplier_portal_provider: str | None = None
    has_clara_voice: str = "CLARA"

    def known_manual_send_value(self, key: str, fallback: Any) -> Any:
        return self.known_manual_send_defaults.get(key, fallback)


LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE = SimpleInvoiceClientFixture(
    client_ref="live_arts_md",
    client_display_name="Live Arts MD",
    workflow_ref="live_arts_md_invoice_workflow",
    expected_workbook_name="Invoice Live Arts MD! Running.xlsx",
    expected_workbook_path=live_arts_md_workbook_handoff.SOURCE_WORKBOOK_MAC_PATH,
    invoice_client_default_candidate_ref="workbook_ref:client_invoice:live_arts_md:running_operator_confirmed",
    invoice_candidate_register_ref="generated/read_models/live_arts_md_invoice_candidate_register.json",
    selection_intended_use="select_live_arts_md_invoice_candidate",
    recipient_confirmation_intended_use="review_or_provide_recipient",
    manual_send_intended_use="prepare_manual_send_package",
    proof_capture_required=("screenshot_ref", "sent_mail_proof_ref"),
    pdf_export_output_path_template="scoped_live_arts_md_export/{selected_sheet_slug}/{invoice_id}.pdf",
    pdf_scope_review_template="Confirm the selected sheet/print area for invoice {invoice_id}.",
    pdf_package_request_template="Prepare the selected Live Arts MD invoice PDF from {selected_sheet_label} on Mac with scoped print area.",
    known_manual_send_defaults={
        "execution_venue": "MAC_LOCAL",
        "execution_actor": "OPERATOR",
        "assistant_actor": "CODEX_DESKTOP_SPARK",
        "openclaw_executed": False,
        "manual_execution": True,
        "send_method": "manual_gmail",
        "artifact_exported_on": "MAC_EXCEL",
        "proof_required": True,
        "invoice_id": "2026-1001",
        "work_or_period": "June 2026 Speaker Rental",
        "amount": 900,
        "attachment_filename": "Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf",
        "to": ("Dane",),
        "cc": ("Draper", "Earnie", "Winship"),
        "subject": "Live Arts MD invoice",
        "sent_timestamp": "2026-05-28T14:32:00-04:00",
        "artifact_path": "/Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf",
    },
    invoice_candidates_provider=live_arts_md_workbook_handoff.invoice_candidates,
    candidate_register_builder=live_arts_md_workbook_handoff.build_candidate_register,
    candidate_lookup=lambda invoice_id: next(
        (candidate for candidate in live_arts_md_workbook_handoff.invoice_candidates() if str(candidate.get("invoice_id") or "") == str(invoice_id).strip()),
        None,
    ),
    recipient_package_builder=lambda confirmed: __import__("clara_invoice_email_draft_package").live_arts_md_recipient_package(confirmed=confirmed),
)


def _st_annes_candidate_register() -> Mapping[str, Any]:
    return {
        "schema_version": "simple_invoice_workbook_register_v0",
        "read_model_id": "simple_invoice_workbook_register_st_annes",
        "generated_at": "2026-05-28T00:00:00+00:00",
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "workflow_ref": "st_annes_invoice_workflow",
        "source_workbook": {
            "source_workbook_ref": "workbook_ref:client_invoice:st_annes:placeholder",
            "source_workbook_mac_path": "/Users/hwinshipwheatley/Documents/Invoices/Placeholder/Invoice ST Anne's Running.xlsx",
            "source_workbook_status": "PLACEHOLDER_PENDING_OPERATOR_HANDOFF",
            "workbook_body_read": False,
            "cell_read": False,
        },
        "receipt_payment_block_pattern": {
            "invoice_status": "C50",
            "amount_received": "E50",
            "balance_due": "G50",
            "receipt_status": "C51",
            "payment_date": "E51",
            "ledger_match": "G51",
        },
        "candidate_count": 0,
        "invoice_candidates": (),
        "primary_next_action": "Choose which St. Anne's invoice to prepare.",
        "urgent_actions": (),
    }


def _st_annes_invoice_candidates() -> tuple[dict[str, Any], ...]:
    return ()


def _st_annes_candidate_lookup(invoice_id: str) -> Mapping[str, Any] | None:
    return None


def _st_annes_recipient_package(confirmed: bool = False) -> Mapping[str, Any]:
    import clara_invoice_email_draft_package as drafts

    return drafts._recipient_package(  # type: ignore[attr-defined]
        (
            {
                "label": "St. Anne's Accounts",
                "canonical_client_ref": "st_annes",
                "canonical_display_name": "St. Anne's",
                "email": None,
                "is_invented": True,
                "status": "NEEDS_OPERATOR_CONFIRMATION",
            },
        )
    ) | ({} if not confirmed else {})


ST_ANNES_SIMPLE_INVOICE_FIXTURE = SimpleInvoiceClientFixture(
    client_ref="st_annes",
    client_display_name="St. Anne's",
    workflow_ref="st_annes_invoice_workflow",
    expected_workbook_name="Invoice St. Anne's Running.xlsx",
    expected_workbook_path="/Users/hwinshipwheatley/Documents/Invoices/Placeholder/Invoice ST Anne's Running.xlsx",
    invoice_client_default_candidate_ref="workbook_ref:client_invoice:st_annes:running_placeholder",
    invoice_candidate_register_ref="generated/read_models/simple_invoice_workbook_register_st_annes.json",
    selection_intended_use="select_st_annes_invoice_candidate",
    recipient_confirmation_intended_use="review_or_provide_recipient",
    manual_send_intended_use="prepare_manual_send_package",
    proof_capture_required=("screenshot_ref", "sent_mail_proof_ref"),
    pdf_export_output_path_template="scoped_st_annes_export/{selected_sheet_slug}/{invoice_id}.pdf",
    pdf_scope_review_template="Confirm the selected sheet/print area for invoice {invoice_id}.",
    pdf_package_request_template="Prepare the selected St. Anne's invoice PDF from {selected_sheet_label} on Mac with scoped print area.",
    known_manual_send_defaults={
        "execution_venue": "MAC_LOCAL",
        "execution_actor": "OPERATOR",
        "assistant_actor": "CODEX_DESKTOP_SPARK",
        "openclaw_executed": False,
        "manual_execution": True,
        "send_method": "manual_gmail",
        "artifact_exported_on": "MAC_EXCEL",
        "proof_required": True,
    },
    invoice_candidates_provider=_st_annes_invoice_candidates,
    candidate_register_builder=_st_annes_candidate_register,
    candidate_lookup=_st_annes_candidate_lookup,
    recipient_package_builder=_st_annes_recipient_package,
)


SIMPLE_INVOICE_WORKFLOW_FIXTURES: dict[str, SimpleInvoiceClientFixture] = {
    LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE.client_ref: LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE,
    ST_ANNES_SIMPLE_INVOICE_FIXTURE.client_ref: ST_ANNES_SIMPLE_INVOICE_FIXTURE,
}


def get_simple_invoice_fixture(client_ref: str) -> SimpleInvoiceClientFixture:
    return SIMPLE_INVOICE_WORKFLOW_FIXTURES[client_ref]


__all__ = [
    "SimpleInvoiceClientFixture",
    "LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE",
    "ST_ANNES_SIMPLE_INVOICE_FIXTURE",
    "SIMPLE_INVOICE_WORKFLOW_FIXTURES",
    "get_simple_invoice_fixture",
]
