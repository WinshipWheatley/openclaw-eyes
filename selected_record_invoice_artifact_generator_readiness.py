"""Selected-record invoice artifact generator readiness v0.

This module defines the missing readiness rail between an operator-confirmed
invoice record/page and a future current invoice artifact. It does not read
workbook cells, automate Excel/Office, send email, access Coupa/browser/Gmail,
post ledgers, or mutate production business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Mapping

import invoice_review_state_machine
import local_artifact_reference
import client_invoice_workbook_registry


SCHEMA_VERSION = "selected_record_invoice_artifact_generator_readiness_v0"
READ_MODEL_ID = "selected_record_invoice_artifact_generator_readiness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ARTIFACT_ROOT = Path("generated/invoice_artifacts/selected_record_invoice_artifact_v0")

SOURCE_WORKBOOK_LINKAGE_RECEIPT = "source_workbook_reference_confirmed_receipt"
SELECTED_RECORD_RECEIPT = "invoice_record_selection_operator_confirmed_receipt"
GENERATION_AUTHORITY_RECEIPT = "selected_record_invoice_artifact_generation_authority_receipt"

REQUIRED_RECEIPTS = (
    SOURCE_WORKBOOK_LINKAGE_RECEIPT,
    SELECTED_RECORD_RECEIPT,
    GENERATION_AUTHORITY_RECEIPT,
)

AUTHORITY_BOUNDARY = {
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "excel_office_automation_performed": False,
    "formula_evaluation_performed": False,
    "pdf_export_performed": False,
    "email_send_performed": False,
    "coupa_browser_action_performed": False,
    "ledger_posting_performed": False,
    "external_action_performed": False,
    "production_business_mutation_performed": False,
}


@dataclass(frozen=True)
class ExistingGeneratorAudit:
    module_ref: str
    found: bool
    input_source: str
    output_kind: str
    selected_record_safe: bool
    blocker: str


@dataclass(frozen=True)
class SelectedRecordGeneratorReadiness:
    generator_ready: bool
    safe_to_generate: bool
    missing_inputs: tuple[str, ...]
    required_authority: tuple[str, ...]
    source_workbook_linkage_status: str
    selected_record_linkage_status: str
    workbook_read_required: bool
    allowed_read_scope: str
    output_artifact_kind: str
    next_operator_action: str


@dataclass(frozen=True)
class SourceWorkbookLinkageReadiness:
    source_workbook_found: bool
    source_workbook_confirmed: bool
    source_workbook_ref: str | None
    source_workbook_pc_path: str | None
    source_workbook_mac_path: str | None
    registry_workbook_ref: str | None
    approved_artifact_ref: str | None
    linkage_status: str
    blocker: str | None
    guided_action: str
    receipt_name_if_confirmed: str
    no_workbook_body_read: bool
    no_cell_read: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def audit_existing_generators() -> tuple[ExistingGeneratorAudit, ...]:
    return (
        ExistingGeneratorAudit(
            module_ref="invoice_artifact_builder",
            found=importlib_util.find_spec("invoice_artifact_builder") is not None,
            input_source="module constants CAPITAL_HILTON_FACTS plus fixed record date",
            output_kind="PDF/XLSX/CSV fixture artifacts",
            selected_record_safe=False,
            blocker="Does not accept source_workbook_ref, invoice_period_label, invoice_record_label, selected-record receipt, or generation authority receipt.",
        ),
        ExistingGeneratorAudit(
            module_ref="capital_hilton_invoice_artifact_generator",
            found=importlib_util.find_spec("capital_hilton_invoice_artifact_generator") is not None,
            input_source="Mission Control capture-state rows for performance dates/rate/subtotal",
            output_kind="Markdown preview only",
            selected_record_safe=False,
            blocker="Preview rail is not a current Excel/PDF invoice artifact generator and does not bind a selected workbook page/record.",
        ),
    )


def _receipt_set(receipts: tuple[str, ...] | list[str] | set[str]) -> set[str]:
    return {str(receipt) for receipt in receipts}


def _active_workbook_record(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    active = payload.get("active_record")
    if isinstance(active, Mapping) and active.get("client_ref") == "capital_hilton":
        return dict(active)
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    for item in registry.get("client_records") or ():
        if (
            isinstance(item, Mapping)
            and item.get("client_ref") == "capital_hilton"
            and item.get("workflow_ref") == "capital_hilton_invoice_workflow"
        ):
            return dict(item)
    return None


def discover_source_workbook_linkage(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
) -> SourceWorkbookLinkageReadiness:
    workbook_registry_payload = (
        workbook_registry_payload
        if workbook_registry_payload is not None
        else client_invoice_workbook_registry.load_existing_payload()
    )
    artifact_reference_payload = (
        artifact_reference_payload
        if artifact_reference_payload is not None
        else local_artifact_reference.load_existing_payload()
    )
    active = _active_workbook_record(workbook_registry_payload)
    approved = local_artifact_reference.find_approved_readable_artifact(
        artifact_reference_payload,
        world_ref="finance",
        workflow_ref="capital_hilton_invoice_workflow",
        client_ref="capital_hilton",
        artifact_kind="invoice_workbook",
        intended_use="client_invoice_sheet_audit",
    )
    registry_ref = str(active.get("workbook_ref")) if active else None
    approved_ref = str(approved.get("artifact_ref")) if approved else None
    pc_path = str(approved.get("pc_path") or approved.get("approved_path_ref") or "") if approved else ""
    mac_path = str(approved.get("mac_path") or "") if approved else ""
    found = bool(active or approved)
    if active and approved and registry_ref == approved_ref:
        return SourceWorkbookLinkageReadiness(
            source_workbook_found=True,
            source_workbook_confirmed=True,
            source_workbook_ref=registry_ref,
            source_workbook_pc_path=pc_path,
            source_workbook_mac_path=mac_path or None,
            registry_workbook_ref=registry_ref,
            approved_artifact_ref=approved_ref,
            linkage_status="CONFIRMED",
            blocker=None,
            guided_action="source_workbook_reference_confirmed",
            receipt_name_if_confirmed=SOURCE_WORKBOOK_LINKAGE_RECEIPT,
            no_workbook_body_read=True,
            no_cell_read=True,
        )
    if active and approved:
        blocker = "ACTIVE_WORKBOOK_REF_DIFFERS_FROM_APPROVED_READABLE_ARTIFACT_REF"
        action = "Confirm which Capital Hilton workbook should be the source workbook before generating the invoice artifact."
    elif active:
        blocker = "APPROVED_READABLE_WORKBOOK_ARTIFACT_MISSING"
        action = "Choose or approve a PC-readable Capital Hilton workbook reference."
    elif approved:
        blocker = "WORKBOOK_REGISTRY_ACTIVE_RECORD_MISSING"
        action = "Confirm the approved workbook as the active Capital Hilton source workbook."
    else:
        blocker = "SOURCE_WORKBOOK_REFERENCE_MISSING"
        action = "Choose or confirm the Capital Hilton source workbook before generating the invoice artifact."
    return SourceWorkbookLinkageReadiness(
        source_workbook_found=found,
        source_workbook_confirmed=False,
        source_workbook_ref=None,
        source_workbook_pc_path=pc_path or None,
        source_workbook_mac_path=mac_path or None,
        registry_workbook_ref=registry_ref,
        approved_artifact_ref=approved_ref,
        linkage_status="BLOCKED",
        blocker=blocker,
        guided_action=action,
        receipt_name_if_confirmed=SOURCE_WORKBOOK_LINKAGE_RECEIPT,
        no_workbook_body_read=True,
        no_cell_read=True,
    )


def wrong_source_workbook_stop_line_active(state: Mapping[str, Any]) -> bool:
    return state.get("source_workbook_status") in {
        "OPERATOR_REPORTED_WRONG_WORKBOOK",
        "SOURCE_WORKBOOK_REPLACEMENT_REQUIRED",
    }


def evaluate_readiness(
    *,
    state: Mapping[str, Any],
    receipts: tuple[str, ...] | list[str] | set[str],
    source_workbook_ref: str | None = None,
    source_workbook_path: str | None = None,
    approved_generation_inputs: Mapping[str, Any] | None = None,
) -> SelectedRecordGeneratorReadiness:
    present = _receipt_set(receipts)
    missing: list[str] = []
    wrong_source = wrong_source_workbook_stop_line_active(state)
    linkage = discover_source_workbook_linkage()
    source_workbook_ref = source_workbook_ref or (linkage.source_workbook_ref if linkage.source_workbook_confirmed else None)
    source_workbook_path = source_workbook_path or (
        linkage.source_workbook_pc_path if linkage.source_workbook_confirmed else None
    )
    if not source_workbook_ref:
        missing.append("source_workbook_ref")
    if not source_workbook_path:
        missing.append("source_workbook_pc_or_mac_path")
    if not state.get("invoice_period_label"):
        missing.append("invoice_period_label")
    if not state.get("invoice_record_label"):
        missing.append("invoice_record_label")
    for receipt in REQUIRED_RECEIPTS:
        if receipt not in present:
            missing.append(receipt)
    if approved_generation_inputs is None:
        missing.append("approved_generation_inputs")
    if wrong_source:
        missing.append("correct_source_workbook_required")

    source_status = (
        "BLOCKED_WRONG_SOURCE_WORKBOOK"
        if wrong_source
        else "LINKED"
        if SOURCE_WORKBOOK_LINKAGE_RECEIPT in present and source_workbook_ref
        else "MISSING_LINKAGE"
    )
    record_status = "LINKED" if SELECTED_RECORD_RECEIPT in present and state.get("invoice_record_label") else "MISSING_SELECTION"
    authority_status = GENERATION_AUTHORITY_RECEIPT in present
    safe = not missing and authority_status
    next_action = (
        "Generate selected invoice artifact candidate from approved selected-record inputs."
        if safe
        else "Choose the correct Capital Hilton source workbook before generating the invoice artifact."
        if wrong_source
        else "OpenClaw needs source workbook linkage and generation authority before creating the selected invoice artifact."
    )
    return SelectedRecordGeneratorReadiness(
        generator_ready=safe,
        safe_to_generate=safe,
        missing_inputs=tuple(dict.fromkeys(missing)),
        required_authority=REQUIRED_RECEIPTS,
        source_workbook_linkage_status=source_status,
        selected_record_linkage_status=record_status,
        workbook_read_required=False,
        allowed_read_scope="approved_selected_record_inputs_only_no_workbook_body_or_cell_read",
        output_artifact_kind="SELECTED_RECORD_INVOICE_CANDIDATE_JSON",
        next_operator_action=next_action,
    )


def _validate_output_path(path: Path, *, repo_root: Path) -> None:
    generated_root = (repo_root / "generated" / "invoice_artifacts").resolve()
    resolved = path.resolve()
    if not str(resolved).startswith(str(generated_root) + "/"):
        raise ValueError(f"output path must stay under generated/invoice_artifacts: {path}")


def generate_selected_record_candidate_artifact(
    *,
    state: Mapping[str, Any],
    receipts: tuple[str, ...] | list[str] | set[str],
    source_workbook_ref: str,
    source_workbook_path: str,
    approved_generation_inputs: Mapping[str, Any],
    repo_root: Path = Path.cwd(),
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    readiness = evaluate_readiness(
        state=state,
        receipts=receipts,
        source_workbook_ref=source_workbook_ref,
        source_workbook_path=source_workbook_path,
        approved_generation_inputs=approved_generation_inputs,
    )
    if not readiness.safe_to_generate:
        return {
            "status": "GENERATOR_NOT_READY",
            "readiness": asdict(readiness),
            "artifact_created": False,
            "receipt_written": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    root = artifact_root if artifact_root.is_absolute() else repo_root / artifact_root
    filename = f"CAPITAL_HILTON_SELECTED_RECORD_{_short_hash(state.get('invoice_period_label'), state.get('invoice_record_label'))}.json"
    artifact_path = root / filename
    _validate_output_path(artifact_path, repo_root=repo_root)
    root.mkdir(parents=True, exist_ok=True)
    artifact_payload = {
        "schema_version": "selected_record_invoice_artifact_candidate_v0",
        "artifact_status": "GENERATED_ARTIFACT_CREATED",
        "client_ref": state["client_ref"],
        "workflow_ref": state["workflow_ref"],
        "source_workbook_ref": source_workbook_ref,
        "source_workbook_path_ref": source_workbook_path,
        "invoice_period_label": state["invoice_period_label"],
        "invoice_record_label": state["invoice_record_label"],
        "approved_generation_inputs": dict(approved_generation_inputs),
        "candidate_only": True,
        "attachment_ready": False,
        "approval_ready": False,
        "no_send_submit_ledger": True,
        "generated_at": generated_at,
    }
    artifact_path.write_text(stable_json(artifact_payload), encoding="utf-8")
    digest = _sha256_file(artifact_path)
    receipt = {
        "receipt_name": "selected_record_invoice_artifact_candidate_created_receipt",
        "receipt_event": "selected_record_invoice_artifact_candidate_created",
        "client_ref": state["client_ref"],
        "workflow_ref": state["workflow_ref"],
        "source_workbook_ref": source_workbook_ref,
        "invoice_period_label": state["invoice_period_label"],
        "invoice_record_label": state["invoice_record_label"],
        "artifact_path": artifact_path.as_posix(),
        "artifact_hash": digest,
        "attachment_ready": False,
        "approval_ready": False,
        "generated_at": generated_at,
    }
    return {
        "status": "GENERATED_ARTIFACT_CREATED",
        "readiness": asdict(readiness),
        "artifact_created": True,
        "artifact_linked_confirmed": False,
        "artifact_path": artifact_path.as_posix(),
        "artifact_hash": digest,
        "receipt": receipt,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_payload(
    *,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    state = invoice_review_state_machine.load_state(db_path, generated_at=generated_at)
    receipts = invoice_review_state_machine.receipt_names(db_path)
    linkage = discover_source_workbook_linkage()
    if wrong_source_workbook_stop_line_active(state):
        linkage = SourceWorkbookLinkageReadiness(
            source_workbook_found=linkage.source_workbook_found,
            source_workbook_confirmed=False,
            source_workbook_ref=None,
            source_workbook_pc_path=linkage.source_workbook_pc_path,
            source_workbook_mac_path=linkage.source_workbook_mac_path,
            registry_workbook_ref=linkage.registry_workbook_ref,
            approved_artifact_ref=linkage.approved_artifact_ref,
            linkage_status="BLOCKED_WRONG_SOURCE_WORKBOOK",
            blocker="CORRECT_SOURCE_WORKBOOK_REQUIRED",
            guided_action="Choose the correct Capital Hilton source workbook before generating the invoice artifact.",
            receipt_name_if_confirmed=SOURCE_WORKBOOK_LINKAGE_RECEIPT,
            no_workbook_body_read=True,
            no_cell_read=True,
        )
    readiness = evaluate_readiness(state=state, receipts=receipts)
    audit = audit_existing_generators()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "existing_generator_audit": tuple(asdict(item) for item in audit),
        "readiness": asdict(readiness),
        "source_workbook_linkage": asdict(linkage),
        "generation_authority_receipt": {
            "receipt_name": GENERATION_AUTHORITY_RECEIPT,
            "status": "MISSING" if GENERATION_AUTHORITY_RECEIPT not in receipts else "PRESENT",
            "scope_required": {
                "client_ref": state.get("client_ref"),
                "workflow_ref": state.get("workflow_ref"),
                "invoice_period_label": state.get("invoice_period_label"),
                "invoice_record_label": state.get("invoice_record_label"),
                "source_workbook_ref": linkage.source_workbook_ref,
                "intended_output_artifact_kind": "SELECTED_RECORD_INVOICE_CANDIDATE_JSON",
            },
            "does_not_equal_execution": True,
            "allows_send_submit_ledger": False,
        },
        "current_state_refs": {
            "client_ref": state.get("client_ref"),
            "workflow_ref": state.get("workflow_ref"),
            "invoice_period_label": state.get("invoice_period_label"),
            "invoice_record_label": state.get("invoice_record_label"),
            "generated_artifact_status": state.get("generated_artifact_status"),
        },
        "operator_copy": readiness.next_operator_action,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "existing_fixture_generators_not_selected_record_safe": all(
                not item.selected_record_safe for item in audit
            ),
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "no_external_action": True,
            "safe_to_generate_now": readiness.safe_to_generate,
            "source_workbook_linkage_confirmed": linkage.source_workbook_confirmed,
            "generation_authority_receipt_required": True,
        },
    }


def format_operator(payload: Mapping[str, Any]) -> str:
    readiness = payload["readiness"]
    lines = [
        "# Selected-Record Invoice Artifact Generator Readiness",
        "",
        f"Ready: `{str(readiness['generator_ready']).lower()}`",
        f"Safe to generate now: `{str(readiness['safe_to_generate']).lower()}`",
        "",
        payload["operator_copy"],
        "",
        "## Missing Inputs",
        "",
    ]
    lines.extend(f"- `{item}`" for item in readiness["missing_inputs"])
    lines.extend(
        [
            "",
            "## Existing Generator Audit",
            "",
        ]
    )
    for item in payload["existing_generator_audit"]:
        lines.append(f"- `{item['module_ref']}`: selected-record-safe=`{str(item['selected_record_safe']).lower()}`; {item['blocker']}")
    lines.append("")
    return "\n".join(lines)


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    return json_path, operator_path


def export_readiness(
    *,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(db_path=db_path, generated_at=generated_at)
    json_path, operator_path = write_exports(payload, export_root)
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "generator_ready": payload["readiness"]["generator_ready"],
        "safe_to_generate": payload["readiness"]["safe_to_generate"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export selected-record invoice artifact generator readiness.")
    parser.add_argument("--db-path", default=invoice_review_state_machine.DEFAULT_DB_PATH.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_readiness(
        db_path=Path(args.db_path),
        export_root=Path(args.export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
