"""Operator-assisted annotation for the Live Arts MD PDF export candidate.

This is a separate deterministic annotation over an existing Mac helper
candidate receipt. It does not rewrite the original receipt and does not grant
attachment, approval, ledger, email, browser, Gmail, Coupa, workbook, or export
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "selected_invoice_pdf_export_operator_assistance_annotation_v0"
READ_MODEL_ID = "selected_invoice_pdf_export_operator_assistance_annotation"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
CANDIDATE_RECEIPT_EXPORT_NAME = "selected_invoice_pdf_export_completed_candidate_receipt.json"
DEFAULT_GENERATED_AT = "2026-06-01T01:40:00+00:00"

CLIENT_REF = "live_arts_md"
WORKFLOW_REF = "live_arts_md_invoice_workflow"
INVOICE_ID = "2026-1001"
PDF_PATH = (
    "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
    "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
)
PDF_MAC_PATH = (
    "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
    "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
)
PDF_FILENAME = "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
FILE_SIZE_BYTES = 171899
SHA256 = "fc2b9d9448307ddbcaff7d087b05c8b8e1af5c547caf6103dfc3b14162b84640"
PAGE_COUNT = 7

AUTHORITY_BOUNDARY = {
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "pdf_export_performed": False,
    "ledger_posting_performed": False,
    "production_business_mutation_performed": False,
    "external_action_performed": False,
}


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


def stable_json(payload: Any) -> str:
    return json.dumps(json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _source_commit() -> str | None:
    git_dir = Path(__file__).resolve().parent / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref_path = git_dir / head.removeprefix("ref: ").strip()
            return ref_path.read_text(encoding="utf-8").strip()[:40]
        return head[:40]
    except OSError:
        return None


def _load_candidate_receipt(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Mapping[str, Any] | None, str | None]:
    candidate_paths = [export_root / CANDIDATE_RECEIPT_EXPORT_NAME]
    if bridge_export_root is not None:
        candidate_paths.append(bridge_export_root / CANDIDATE_RECEIPT_EXPORT_NAME)
    for path in candidate_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, Mapping):
            return payload, path.as_posix()
    return None, None


def _candidate_value(candidate: Mapping[str, Any] | None, key: str, default: Any) -> Any:
    if not isinstance(candidate, Mapping):
        return default
    value = candidate.get(key)
    return default if value in (None, "") else value


def build_annotation(
    *,
    candidate_receipt_payload: Mapping[str, Any] | None = None,
    candidate_receipt_path: str | None = None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    candidate = candidate_receipt_payload
    resolved_candidate_path = candidate_receipt_path
    if candidate is None:
        candidate, resolved_candidate_path = _load_candidate_receipt(
            export_root=export_root,
            bridge_export_root=bridge_export_root,
        )

    validation_errors: list[str] = []
    if not isinstance(candidate, Mapping):
        validation_errors.append("MISSING_CANDIDATE_RECEIPT")
        candidate = {}
    if candidate.get("receipt_name") != "selected_invoice_pdf_export_completed_candidate_receipt":
        validation_errors.append("WRONG_RECEIPT_NAME")
    if candidate.get("client_ref") != CLIENT_REF:
        validation_errors.append("WRONG_CLIENT_REF")
    if candidate.get("workflow_ref") != WORKFLOW_REF:
        validation_errors.append("WRONG_WORKFLOW_REF")
    if candidate.get("invoice_id") != INVOICE_ID:
        validation_errors.append("WRONG_INVOICE_ID")
    if candidate.get("artifact_review_status") != "OPERATOR_REVIEW_REQUIRED":
        validation_errors.append("CANDIDATE_NOT_REVIEW_REQUIRED")
    if candidate.get("attachment_ready") is not False:
        validation_errors.append("CANDIDATE_ATTACHMENT_GATE_NOT_CLOSED")
    if candidate.get("approval_ready") is not False:
        validation_errors.append("CANDIDATE_APPROVAL_GATE_NOT_CLOSED")
    if candidate.get("ledger_posting_allowed") is not False:
        validation_errors.append("CANDIDATE_LEDGER_GATE_NOT_CLOSED")

    candidate_sha = str(_candidate_value(candidate, "sha256", SHA256))
    candidate_size = _candidate_value(candidate, "file_size_bytes", FILE_SIZE_BYTES)
    candidate_mac_path = str(_candidate_value(candidate, "exported_pdf_mac_path", PDF_MAC_PATH))
    candidate_filename = str(_candidate_value(candidate, "artifact_filename", PDF_FILENAME))
    annotation_status = "OPERATOR_ASSISTED_ANNOTATED" if not validation_errors else "BLOCKED_INVALID_CANDIDATE"
    annotation_id = f"{READ_MODEL_ID}:{_short_hash(CLIENT_REF, WORKFLOW_REF, INVOICE_ID, candidate_sha)}"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "producer_ref": "selected_invoice_pdf_export_operator_assistance_annotation.py:build_annotation",
        "source_commit": _source_commit(),
        "annotation_id": annotation_id,
        "annotation_status": annotation_status,
        "annotation_receipt_type": READ_MODEL_ID,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "invoice_id": INVOICE_ID,
        "source_candidate_receipt_name": "selected_invoice_pdf_export_completed_candidate_receipt",
        "source_candidate_receipt_id": candidate.get("receipt_id"),
        "source_candidate_receipt_path": resolved_candidate_path,
        "source_candidate_result_status": candidate.get("result_status"),
        "source_candidate_artifact_review_status": candidate.get("artifact_review_status"),
        "pdf_artifact": {
            "path": PDF_PATH,
            "mac_path": candidate_mac_path,
            "artifact_filename": candidate_filename,
            "file_size_bytes": candidate_size,
            "sha256": candidate_sha,
            "page_count": PAGE_COUNT,
        },
        "operator_assisted": True,
        "fully_unattended": False,
        "operator_intervention_kind": "UNKNOWN_EXCEL_WORKBOOK_OR_PERMISSION_PROMPT",
        "prompt_text_known": False,
        "permission_or_access_granted_by_operator": True,
        "export_candidate_remains_review_required": True,
        "artifact_review_status": "OPERATOR_REVIEW_REQUIRED",
        "attachment_ready": False,
        "approval_ready": False,
        "ledger_posting_allowed": False,
        "sent": False,
        "paid": False,
        "final": False,
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_coupa": True,
        "no_workbook_cell_read": True,
        "no_source_workbook_mutation": True,
        "no_physical_printing": True,
        "no_pdf_export_performed_by_annotation": True,
        "validation_errors": tuple(validation_errors),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "separate_annotation_not_original_receipt_rewrite": True,
            "source_candidate_receipt_present": isinstance(candidate, Mapping) and bool(candidate),
            "operator_assisted_not_fully_unattended": True,
            "candidate_still_requires_operator_review": True,
            "attachment_ready_false": True,
            "approval_ready_false": True,
            "ledger_posting_allowed_false": True,
            "no_live_actions_performed": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    return payload


def format_operator(payload: Mapping[str, Any]) -> str:
    artifact = payload["pdf_artifact"]
    lines = [
        "# Selected Invoice PDF Export Operator Assistance Annotation",
        "",
        f"- Status: `{payload['annotation_status']}`",
        f"- Client: `{payload['client_ref']}`",
        f"- Workflow: `{payload['workflow_ref']}`",
        f"- Invoice: `{payload['invoice_id']}`",
        f"- Operator assisted: `{payload['operator_assisted']}`",
        f"- Fully unattended: `{payload['fully_unattended']}`",
        f"- Intervention: `{payload['operator_intervention_kind']}`",
        f"- Prompt text known: `{payload['prompt_text_known']}`",
        f"- Artifact review status: `{payload['artifact_review_status']}`",
        f"- Attachment ready: `{payload['attachment_ready']}`",
        f"- Approval ready: `{payload['approval_ready']}`",
        f"- Ledger posting allowed: `{payload['ledger_posting_allowed']}`",
        f"- PDF path: `{artifact['path']}`",
        f"- SHA256: `{artifact['sha256']}`",
        f"- Page count: `{artifact['page_count']}`",
        "",
        "This annotation does not rewrite the original Mac receipt and does not mark the artifact send-ready.",
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


def export_annotation(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_annotation(
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        generated_at=generated_at,
    )
    json_path, operator_path, bridge_path = write_exports(
        payload,
        export_root,
        bridge_export_root=bridge_export_root,
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "annotation_status": payload["annotation_status"],
        "operator_assisted": payload["operator_assisted"],
        "fully_unattended": payload["fully_unattended"],
        "artifact_review_status": payload["artifact_review_status"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Live Arts PDF operator-assistance annotation.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_annotation(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["annotation_status"] == "OPERATOR_ASSISTED_ANNOTATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
