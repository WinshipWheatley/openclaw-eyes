"""Client invoice workbook lifecycle rules contract v0.

This read-model records the non-executing workbook lifecycle rules OpenClaw
must respect before any future Excel writing or generation lane. It does not
create, duplicate, open, read, parse, or edit workbook files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "client_invoice_workbook_lifecycle_rules_v0"
READ_MODEL_ID = "client_invoice_workbook_lifecycle_rules"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CLIENT_INVOICE_WORKBOOK_LIFECYCLE_RULES_NO_EXCEL_ACTION"

CLIENT_REFS = ("capital_hilton", "st_annes", "live_arts_md")

AUTHORITY_BOUNDARY = {
    "live_excel_write_allowed": False,
    "live_excel_new_tab_allowed": False,
    "live_spreadsheet_create_allowed": False,
    "live_workbook_duplicate_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_schema_inference_allowed": False,
    "live_formula_evaluation_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_email_send_allowed": False,
    "live_gmail_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_external_action_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class ClientWorkbookLifecycleRecord:
    client_ref: str
    client_display_name: str
    workbook_scope: str
    workbook_reuse_policy: str
    separate_workbook_required: bool
    may_share_capital_hilton_workbook: bool
    current_workbook_status: str
    stale_data_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class ClientWorkbookPolicy:
    policy_id: str
    one_workbook_per_client: bool
    client_records: tuple[ClientWorkbookLifecycleRecord, ...]
    cross_client_workbook_sharing_allowed: bool
    capital_hilton_workbook_client_lock: str
    st_annes_workbook_requirement: str
    live_arts_md_workbook_requirement: str
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceTemplatePolicy:
    policy_id: str
    generic_template_allowed: bool
    template_scope: str
    fresh_empty_invoice_page_required: bool
    template_may_be_copied_into_client_workbook_only_by_future_writer: bool
    template_must_not_be_used_as_client_source_of_record: bool
    next_safe_move: str


@dataclass(frozen=True)
class NewInvoiceTabPolicy:
    policy_id: str
    new_invoice_per_tab: bool
    tab_scope: str
    new_tab_creation_status: str
    required_sections: tuple[str, ...]
    payment_acknowledgment_section_required: bool
    existing_tab_overwrite_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class PaymentAcknowledgmentPolicy:
    policy_id: str
    acknowledgment_phrase_template: str
    last_payment_amount_required: bool
    last_payment_source_required: bool
    acceptable_source_refs: tuple[str, ...]
    missing_facts: tuple[str, ...]
    generation_without_last_payment_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class StaleWorkbookPolicy:
    policy_id: str
    capital_hilton_workbook_already_in_use: bool
    may_contain_stale_data: bool
    existing_values_current_truth_without_audit: bool
    required_before_accepting_existing_values: tuple[str, ...]
    stale_value_action: str
    next_safe_move: str


@dataclass(frozen=True)
class FutureExcelWriterRequirement:
    requirement_id: str
    requirement_type: str
    condition: str
    required_before_excel_write: bool
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ClientInvoiceWorkbookLifecycleRulesReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    missing_facts: tuple[str, ...]
    next_action: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _client_record(
    client_ref: str,
    display_name: str,
    *,
    current_workbook_status: str,
    stale_policy: str,
) -> ClientWorkbookLifecycleRecord:
    return ClientWorkbookLifecycleRecord(
        client_ref=client_ref,
        client_display_name=display_name,
        workbook_scope=f"{display_name} invoices only",
        workbook_reuse_policy="Reuse the client workbook across invoices; add a new invoice worksheet/tab for each new invoice.",
        separate_workbook_required=True,
        may_share_capital_hilton_workbook=client_ref == "capital_hilton",
        current_workbook_status=current_workbook_status,
        stale_data_policy=stale_policy,
        next_safe_move=f"Use a dedicated {display_name} workbook before any future Excel writer lane.",
    )


def build_client_workbook_policy() -> ClientWorkbookPolicy:
    records = (
        _client_record(
            "capital_hilton",
            "Capital Hilton",
            current_workbook_status="CURRENT_WORKBOOK_IN_USE_MAY_CONTAIN_STALE_DATA",
            stale_policy="Do not accept existing workbook values as current invoice truth until audited, mapped, and confirmed.",
        ),
        _client_record(
            "st_annes",
            "St. Anne's",
            current_workbook_status="SEPARATE_CLIENT_WORKBOOK_REQUIRED",
            stale_policy="Do not use Capital Hilton workbook values for St. Anne's invoices.",
        ),
        _client_record(
            "live_arts_md",
            "Live Arts MD",
            current_workbook_status="SEPARATE_CLIENT_WORKBOOK_REQUIRED",
            stale_policy="Do not use Capital Hilton or St. Anne's workbook values for Live Arts MD invoices.",
        ),
    )
    return ClientWorkbookPolicy(
        policy_id="client_workbook_policy:v0",
        one_workbook_per_client=True,
        client_records=records,
        cross_client_workbook_sharing_allowed=False,
        capital_hilton_workbook_client_lock="Capital Hilton workbook is only for Capital Hilton invoices.",
        st_annes_workbook_requirement="St. Anne's requires its own client workbook.",
        live_arts_md_workbook_requirement="Live Arts MD requires its own client workbook.",
        next_safe_move="Keep client workbook ownership separate before any future Excel writer lane.",
    )


def build_template_policy() -> ClientInvoiceTemplatePolicy:
    return ClientInvoiceTemplatePolicy(
        policy_id="client_invoice_template_policy:v0",
        generic_template_allowed=True,
        template_scope="Generic invoice start-point only; not a client source of record.",
        fresh_empty_invoice_page_required=True,
        template_may_be_copied_into_client_workbook_only_by_future_writer=True,
        template_must_not_be_used_as_client_source_of_record=True,
        next_safe_move="Use the template only as a future-gated starting point for a fresh invoice tab.",
    )


def build_new_invoice_tab_policy() -> NewInvoiceTabPolicy:
    return NewInvoiceTabPolicy(
        policy_id="new_invoice_tab_policy:v0",
        new_invoice_per_tab=True,
        tab_scope="Every new invoice for a client becomes a new worksheet/tab/page inside that client's workbook.",
        new_tab_creation_status="FUTURE_GATED_EXCEL_WRITER_REQUIRED",
        required_sections=(
            "payment acknowledgment",
            "new invoice details",
            "service/performance date details",
            "rate and subtotal/total",
            "PO/reference or explicit missing marker",
            "notes/status",
        ),
        payment_acknowledgment_section_required=True,
        existing_tab_overwrite_allowed=False,
        next_safe_move="Define the target invoice facts and last payment source before future new-tab creation.",
    )


def build_payment_acknowledgment_policy() -> PaymentAcknowledgmentPolicy:
    return PaymentAcknowledgmentPolicy(
        policy_id="payment_acknowledgment_policy:v0",
        acknowledgment_phrase_template="Thank you for your last payment of $X,",
        last_payment_amount_required=True,
        last_payment_source_required=True,
        acceptable_source_refs=(
            "audited client workbook field",
            "approved payment receipt",
            "approved payment ledger/readback",
            "operator-confirmed payment source",
        ),
        missing_facts=("last_payment_amount", "last_payment_source_ref"),
        generation_without_last_payment_allowed=False,
        next_safe_move="Capture or confirm last payment amount and source before generating the acknowledgment.",
    )


def build_stale_workbook_policy() -> StaleWorkbookPolicy:
    return StaleWorkbookPolicy(
        policy_id="stale_workbook_policy:v0",
        capital_hilton_workbook_already_in_use=True,
        may_contain_stale_data=True,
        existing_values_current_truth_without_audit=False,
        required_before_accepting_existing_values=(
            "approved PC-readable workbook path/ref",
            "explicit sheet/schema mapping",
            "whitelisted sheet audit",
            "operator confirmation or deterministic source promotion",
        ),
        stale_value_action="Treat existing values as untrusted workbook history until mapped/audited/confirmed.",
        next_safe_move="Run the approved whitelisted audit before accepting any existing workbook values as current invoice truth.",
    )


def build_future_writer_requirements() -> tuple[FutureExcelWriterRequirement, ...]:
    return (
        FutureExcelWriterRequirement(
            requirement_id="future_excel_writer_requirement:client_workbook_identity",
            requirement_type="CLIENT_WORKBOOK_IDENTITY",
            condition="Target client workbook must be registered and client-scoped.",
            required_before_excel_write=True,
            fail_closed=True,
            next_safe_move="Confirm the target client workbook before writing.",
        ),
        FutureExcelWriterRequirement(
            requirement_id="future_excel_writer_requirement:new_invoice_tab",
            requirement_type="NEW_INVOICE_TAB",
            condition="New invoice requires a fresh tab/page; do not overwrite stale or prior invoice tabs.",
            required_before_excel_write=True,
            fail_closed=True,
            next_safe_move="Create new-tab support only in a future gated writer lane.",
        ),
        FutureExcelWriterRequirement(
            requirement_id="future_excel_writer_requirement:last_payment_source",
            requirement_type="LAST_PAYMENT_SOURCE",
            condition="Payment acknowledgment requires last payment amount and source proof.",
            required_before_excel_write=True,
            fail_closed=True,
            next_safe_move="Capture last payment amount/source before generating invoice text.",
        ),
        FutureExcelWriterRequirement(
            requirement_id="future_excel_writer_requirement:stale_values",
            requirement_type="STALE_VALUE_GUARD",
            condition="Existing workbook values cannot be promoted without audit/mapping/confirmation.",
            required_before_excel_write=True,
            fail_closed=True,
            next_safe_move="Audit and confirm stale workbook values before reuse.",
        ),
        FutureExcelWriterRequirement(
            requirement_id="future_excel_writer_requirement:authority",
            requirement_type="AUTHORITY_BOUNDARY",
            condition="Excel writing/new-tab creation remains future-gated and has no live authority in this contract.",
            required_before_excel_write=True,
            fail_closed=True,
            next_safe_move="Build a separate approved Excel writer lane before any workbook mutation.",
        ),
    )


def build_readback(missing_facts: tuple[str, ...]) -> ClientInvoiceWorkbookLifecycleRulesReadback:
    return ClientInvoiceWorkbookLifecycleRulesReadback(
        readback_id=f"client_invoice_workbook_lifecycle_rules_readback:{_short_hash(SCHEMA_VERSION, missing_facts)}",
        status="LIFECYCLE_RULES_RECORDED_EXCEL_WRITER_FUTURE_GATED",
        operator_headline="Invoice workbook rules recorded",
        operator_message=(
            "OpenClaw recorded the client workbook lifecycle rules. Excel writing, new tabs, PDF generation, email, "
            "Coupa, and workflow actions remain blocked."
        ),
        missing_facts=missing_facts,
        next_action="Next: capture last payment amount/source and keep workbook values gated behind audit.",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use these rules as the contract before any future Excel writer lane.",
    )


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    client_policy = build_client_workbook_policy()
    template_policy = build_template_policy()
    tab_policy = build_new_invoice_tab_policy()
    payment_policy = build_payment_acknowledgment_policy()
    stale_policy = build_stale_workbook_policy()
    writer_requirements = build_future_writer_requirements()
    missing_facts = tuple(dict.fromkeys(payment_policy.missing_facts + ("approved_future_excel_writer_lane",)))
    readback = build_readback(missing_facts)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "model_schemas": {
            "ClientWorkbookLifecycleRecord": tuple(field.name for field in fields(ClientWorkbookLifecycleRecord)),
            "ClientWorkbookPolicy": tuple(field.name for field in fields(ClientWorkbookPolicy)),
            "ClientInvoiceTemplatePolicy": tuple(field.name for field in fields(ClientInvoiceTemplatePolicy)),
            "NewInvoiceTabPolicy": tuple(field.name for field in fields(NewInvoiceTabPolicy)),
            "PaymentAcknowledgmentPolicy": tuple(field.name for field in fields(PaymentAcknowledgmentPolicy)),
            "StaleWorkbookPolicy": tuple(field.name for field in fields(StaleWorkbookPolicy)),
            "FutureExcelWriterRequirement": tuple(field.name for field in fields(FutureExcelWriterRequirement)),
            "ClientInvoiceWorkbookLifecycleRulesReadback": tuple(
                field.name for field in fields(ClientInvoiceWorkbookLifecycleRulesReadback)
            ),
        },
        "client_workbook_policy": asdict(client_policy),
        "template_policy": asdict(template_policy),
        "new_invoice_tab_policy": asdict(tab_policy),
        "payment_acknowledgment_policy": asdict(payment_policy),
        "stale_workbook_policy": asdict(stale_policy),
        "future_excel_writer_requirements": tuple(asdict(requirement) for requirement in writer_requirements),
        "missing_facts": missing_facts,
        "lifecycle_readback": asdict(readback),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "one_workbook_per_client_represented": client_policy.one_workbook_per_client,
            "capital_hilton_locked_to_own_workbook": next(
                record
                for record in client_policy.client_records
                if record.client_ref == "capital_hilton"
            ).may_share_capital_hilton_workbook
            is True
            and all(
                record.may_share_capital_hilton_workbook is False
                for record in client_policy.client_records
                if record.client_ref != "capital_hilton"
            ),
            "st_annes_separate_workbook_required": next(
                record for record in client_policy.client_records if record.client_ref == "st_annes"
            ).separate_workbook_required,
            "live_arts_md_separate_workbook_required": next(
                record for record in client_policy.client_records if record.client_ref == "live_arts_md"
            ).separate_workbook_required,
            "new_invoice_per_tab_represented": tab_policy.new_invoice_per_tab,
            "payment_acknowledgment_requires_last_payment_fact": payment_policy.last_payment_amount_required
            and payment_policy.last_payment_source_required,
            "stale_workbook_values_not_accepted_without_audit": stale_policy.existing_values_current_truth_without_audit
            is False,
            "excel_writer_future_gated": all(requirement.required_before_excel_write for requirement in writer_requirements),
            "excel_write_performed": False,
            "spreadsheet_created": False,
            "workbook_duplicated": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "pdf_generation_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "coupa_access_or_submit_performed": False,
            "browser_access_performed": False,
            "workflow_execution_performed": False,
            "agent_dispatch_performed": False,
            "model_call_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "external_action_performed": False,
            "network_used": False,
            "mission_control_swift_changed": False,
            "mac_sync_import_run": False,
            "git_push_pull_fetch_run": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    readback = payload.get("lifecycle_readback") if isinstance(payload.get("lifecycle_readback"), Mapping) else {}
    lines = [
        "# Client Invoice Workbook Lifecycle Rules",
        "",
        "ELIOPERATOR: Lifecycle rules only. No Excel file was edited, created, duplicated, opened, read, parsed, converted to PDF, emailed, submitted to Coupa, or used for workflow execution.",
        "",
        f"- Status: `{readback.get('status', 'UNKNOWN')}`",
        f"- One workbook per client: `{payload.get('client_workbook_policy', {}).get('one_workbook_per_client', False)}`",
        f"- New invoice per tab: `{payload.get('new_invoice_tab_policy', {}).get('new_invoice_per_tab', False)}`",
        f"- Excel writer: `{payload.get('new_invoice_tab_policy', {}).get('new_tab_creation_status', 'UNKNOWN')}`",
        f"- Missing facts: `{', '.join(payload.get('missing_facts') or ())}`",
        "",
        f"## {readback.get('operator_headline', 'Invoice workbook rules')}",
        "",
        str(readback.get("operator_message") or "No lifecycle readback was generated."),
        "",
        "## Next",
        "",
        str(readback.get("next_action") or "Keep Excel writing future-gated."),
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: Mapping[str, Any], paths: tuple[Path, Path]) -> dict[str, Any]:
    proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
    readback = payload.get("lifecycle_readback") if isinstance(payload.get("lifecycle_readback"), Mapping) else {}
    return {
        "read_model_id": payload.get("read_model_id"),
        "contract_status": payload.get("contract_status"),
        "json_path": paths[0].as_posix(),
        "operator_path": paths[1].as_posix(),
        "status": readback.get("status"),
        "operator_headline": readback.get("operator_headline"),
        "next_action": readback.get("next_action"),
        "missing_facts": payload.get("missing_facts"),
        "one_workbook_per_client": proof.get("one_workbook_per_client_represented"),
        "new_invoice_per_tab": proof.get("new_invoice_per_tab_represented"),
        "excel_writer_future_gated": proof.get("excel_writer_future_gated"),
        "all_live_authority_false": proof.get("all_live_authority_false"),
        "content_hash": proof.get("content_hash"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export client invoice workbook lifecycle rules.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    paths = write_exports(payload, Path(args.export_root))
    output: Mapping[str, Any] = payload if args.format == "json" else build_summary(payload, paths)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
