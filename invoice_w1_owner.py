"""Live no-send owner for W1 invoice verification and finalization."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import invoice_artifact_locator
import invoice_workbook_finalizer as finalizer


SCHEMA_VERSION = "invoice_w1_owner_v1"
AUTHORITY_BOUNDARY = {
    "provider_draft_created": False,
    "external_send_performed": False,
    "money_moved": False,
    "ledger_posted": False,
}


def _paths(value: str | Path | Sequence[str | Path]) -> list[Path]:
    if isinstance(value, (str, Path)):
        return [Path(value)]
    return [Path(item) for item in value]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _idempotent_receipt(
    package: Path,
    receipt_path: Path,
    *,
    source_sha256: str,
) -> dict[str, Any] | None:
    receipt = _json_object(receipt_path)
    manifest = _json_object(package / "invoice_manifest.json")
    workbook = package / "invoice.xlsx"
    pdf = package / "invoice.pdf"
    if (
        receipt.get("status") not in {"PUBLISHED_VERIFIED", "IDEMPOTENT_REPLAY"}
        or receipt.get("source_selection", {}).get("source_sha256") != source_sha256
        or manifest.get("schema") != "openclaw_invoice_manifest_v1"
        or not workbook.is_file()
        or not pdf.is_file()
        or manifest.get("package_workbook_sha256") != _sha256(workbook)
        or manifest.get("current_pdf_sha256") != _sha256(pdf)
    ):
        return None
    result = dict(receipt)
    result["status"] = "IDEMPOTENT_REPLAY"
    result["idempotent_replay"] = True
    result["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
    return result


def run_lamd_july_finalization(
    *,
    source_path: str | Path | Sequence[str | Path],
    package_dir: str | Path,
    receipt_path: str | Path,
    expected_source_sha256: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    candidates = _paths(source_path)
    package = Path(package_dir)
    receipt_target = Path(receipt_path)
    selection = invoice_artifact_locator.locate_source_workbook(
        candidates,
        expected_sha256=expected_source_sha256,
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "SOURCE_BLOCKED",
        "source_selection": selection,
        "source_semantic_marker_count": 0,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if selection["status"] != "FOUND":
        return result
    source = Path(selection["canonical_path"])
    result["source_semantic_marker_count"] = len(
        finalizer.semantic_marker_findings(source, "July 2026")
    )
    if not confirm:
        result["status"] = "DRY_RUN_READY"
        return result

    if package.exists() or receipt_target.exists():
        replay = _idempotent_receipt(
            package,
            receipt_target,
            source_sha256=selection["source_sha256"],
        )
        if replay is not None:
            return replay
        result["status"] = "EXISTING_OUTPUT_CONFLICT"
        return result

    run_id = hashlib.sha256(
        f"{selection['source_sha256']}|2026-07|2026-1004".encode("utf-8")
    ).hexdigest()[:24]
    run_dir = package.parent / ".w1_runs" / f"invoice-w1-{run_id}"
    if run_dir.exists():
        result["status"] = "PRESERVED_FAILED_RUN_REQUIRES_REVIEW"
        return result
    run_dir.mkdir(parents=True, exist_ok=False)
    pre_excel = run_dir / "reconciled_pre_excel.xlsx"
    recalculated = run_dir / "recalculated.xlsx"
    pdf = run_dir / "invoice_2026-1004.pdf"

    reconciliation = finalizer.apply_lamd_truth_reconciliation(source, pre_excel)
    recalculation = finalizer.recalculate_with_excel(pre_excel, recalculated)
    verification = finalizer.verify_recalculated_invoice(
        recalculated,
        sheet_name="July 2026",
        invoice_number="2026-1004",
        expected_amount=100,
        expected_formula_sha256=reconciliation["pre_excel_formula_sha256"],
        balance_cell="G43",
    )
    export = finalizer.export_invoice_pdf_with_excel(
        recalculated,
        sheet_name="July 2026",
        output_path=pdf,
    )
    publication = finalizer.publish_verified_package(
        package,
        workbook_path=recalculated,
        pdf_path=pdf,
        specification={
            "client_ref": "live_arts_md",
            "invoice_number": "2026-1004",
            "service_period": "2026-07",
            "source_sheet": "July 2026",
            "amount": 100,
        },
        verification_receipt=verification,
    )
    result.update(
        {
            "status": "PUBLISHED_VERIFIED",
            "run_id": f"invoice-w1-{run_id}",
            "source_mutated": _sha256(source) != selection["source_sha256"],
            "reconciliation": reconciliation,
            "recalculation": recalculation,
            "verification": verification,
            "export": export,
            "publication": publication,
            "idempotent_replay": False,
        }
    )
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    temporary_receipt = receipt_target.parent / f".{receipt_target.name}.tmp.{uuid.uuid4().hex}"
    temporary_receipt.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_receipt, receipt_target)
    return result
