import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import selected_invoice_pdf_export_operator_assistance_annotation as validator
import simple_invoice_workflow_fixtures as fixtures


def _candidate(*, page_count: int | None = 1, pdf_bridge_path: str | None = None) -> dict:
    payload = {
        "receipt_id": "pdf_export_candidate_receipt:test",
        "receipt_name": "selected_invoice_pdf_export_completed_candidate_receipt",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "candidate_ref": "live_arts_md_test_pdf_candidate",
        "artifact_review_status": "OPERATOR_REVIEW_REQUIRED",
        "attachment_ready": False,
        "approval_ready": False,
        "ledger_posting_allowed": False,
        "sha256": "test-sha256",
        "exported_pdf_mac_path": "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/test.pdf",
        "artifact_filename": "test.pdf",
    }
    if page_count is not None:
        payload["page_count"] = page_count
    if pdf_bridge_path is not None:
        payload["pdf_bridge_path"] = pdf_bridge_path
    return payload


def _annotation(candidate: dict) -> dict:
    return validator.build_annotation(
        candidate_receipt_payload=candidate,
        candidate_receipt_path="unit-test-candidate.json",
        bridge_export_root=None,
    )


def test_one_page_candidate_passes_validator():
    payload = _annotation(_candidate(page_count=1))

    assert payload["candidate_valid_for_operator_review"] is True
    assert payload["artifact_review_status"] == "OPERATOR_REVIEW_REQUIRED"
    assert payload["pdf_scope_validation"]["page_count_source"] == "candidate_receipt.page_count"


def test_seven_page_candidate_fails_validator():
    payload = _annotation(_candidate(page_count=7))

    assert payload["candidate_valid_for_operator_review"] is False
    assert payload["artifact_review_status"] == "SCOPE_MISMATCH_REJECTED"
    assert payload["observed_page_count"] == 7
    assert payload["expected_page_count"] == 1


def test_unknown_page_count_fails_closed(tmp_path):
    payload = _annotation(_candidate(page_count=None, pdf_bridge_path=str(tmp_path / "missing.pdf")))

    assert payload["candidate_valid_for_operator_review"] is False
    assert payload["artifact_review_status"] == "PDF_PAGE_COUNT_UNKNOWN_REJECTED"
    assert payload["observed_page_count"] is None
    assert payload["attachment_ready"] is False
    assert payload["approval_ready"] is False
    assert payload["ledger_posting_allowed"] is False


def test_live_arts_selected_invoice_expected_page_count_defaults_to_one():
    fixture = fixtures.LIVE_ARTS_MD_SIMPLE_INVOICE_FIXTURE
    payload = _annotation(_candidate(page_count=1))

    assert fixture.selected_invoice_expected_page_count == 1
    assert fixture.selected_invoice_export_scope == "selected_invoice_page"
    assert payload["expected_page_count"] == 1
    assert payload["export_scope"] == "selected_invoice_page"


def test_reason_code_for_workbook_wide_multipage_export():
    payload = _annotation(_candidate(page_count=7))

    assert payload["reason_code"] == "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
    assert payload["pdf_scope_validation"]["reason_code"] == payload["reason_code"]


def test_failed_candidate_lineage_is_preserved():
    candidate = _candidate(page_count=7)
    payload = _annotation(candidate)
    lineage = payload["candidate_lineage"]

    assert lineage["candidate_ref"] == candidate["candidate_ref"]
    assert lineage["sha256"] == candidate["sha256"]
    assert lineage["pdf_bridge_path"].endswith("/test.pdf")
    assert lineage["pdf_mac_path"] == candidate["exported_pdf_mac_path"]
    assert lineage["observed_page_count"] == 7
    assert lineage["expected_page_count"] == 1
    assert lineage["selected_invoice_id"] == "2026-1001"
    assert lineage["selected_sheet_label"] == "June 2026 Speaker Rental"
    assert lineage["selected_invoice_amount"] == "$900"


def test_validator_does_not_set_attachment_ready():
    payload = _annotation(_candidate(page_count=1))

    assert payload["attachment_ready"] is False
    assert payload["pdf_scope_validation"]["attachment_ready"] is False


def test_validator_does_not_set_approval_ready():
    payload = _annotation(_candidate(page_count=1))

    assert payload["approval_ready"] is False
    assert payload["pdf_scope_validation"]["approval_ready"] is False


def test_validator_does_not_set_ledger_posting_allowed():
    payload = _annotation(_candidate(page_count=1))

    assert payload["ledger_posting_allowed"] is False
    assert payload["pdf_scope_validation"]["ledger_posting_allowed"] is False


def test_validator_does_not_require_or_invent_observed_desired_pdf_page():
    payload = _annotation(_candidate(page_count=7))

    assert payload["desired_page_known"] is False
    assert "observed_desired_pdf_page" not in payload
    assert "observed_desired_pdf_page" not in payload["pdf_scope_validation"]
    assert "observed_desired_pdf_page" not in payload["candidate_lineage"]


def test_validator_has_no_email_browser_coupa_send_execution_paths():
    source = Path(validator.__file__).read_text(encoding="utf-8")

    forbidden_execution_markers = (
        "import " + "smtp" + "lib",
        "import " + "web" + "browser",
        "sele" + "nium",
        "play" + "wright",
        "send_" + "email(",
        "send_" + "mail(",
        "submit_" + "coupa(",
        "post_" + "ledger(",
        ".un" + "link(",
        "os." + "remove(",
        "shutil." + "rmtree(",
    )
    for marker in forbidden_execution_markers:
        assert marker not in source
