import clara_invoice_email_draft_package as drafts
import invoice_review_bundle
import live_arts_md_invoice_review_bundle


def test_capital_hilton_draft_does_not_claim_coupa_submission_without_receipt():
    payload = invoice_review_bundle.build_capital_hilton_bundle()
    draft = payload["clara_invoice_email_draft_package"]

    assert draft["supplier_portal_provider"] == "COUPA"
    assert draft["portal_submission_status"] == "MISSING"
    assert "submitted through the Coupa supplier portal" not in draft["body"]
    assert "Coupa" not in payload["clara_email_draft"]["body"]


def test_capital_hilton_draft_does_not_claim_attachment_until_ready():
    payload = invoice_review_bundle.build_capital_hilton_bundle()
    draft = payload["clara_invoice_email_draft_package"]

    assert draft["attachment_ready"] is False
    assert draft["attachment_refs"] == ()
    assert "Attached is" not in draft["body"]
    assert draft["draft_status"] == drafts.DRAFT_BLOCKED_PENDING_PREREQUISITES


def test_capital_hilton_period_dates_only_when_confirmed():
    missing = invoice_review_bundle.build_capital_hilton_bundle()["clara_invoice_email_draft_package"]
    ready = drafts.build_clara_invoice_email_draft_package(
        client_ref="capital_hilton",
        workflow_ref="capital_hilton_invoice_workflow",
        client_display_name="Capital Hilton",
        recipient_package=drafts.capital_hilton_recipient_package(confirmed=True),
        attachment_ready=True,
        attachment_refs=("artifact_ref:linked_excel",),
        invoice_period_label="May 2026",
        invoice_dates_covered=("May 1, 2026", "May 8, 2026"),
        supplier_portal_required=True,
        supplier_portal_provider="COUPA",
        portal_submission_status="SUBMITTED_RECEIPT_CONFIRMED",
        first_contact_intro_required=False,
        present_receipts=("clara_email_draft_receipt",),
    )

    assert "May 2026" not in missing["body"]
    assert "May 1, 2026, May 8, 2026" in ready["body"]
    assert "submitted through the Coupa supplier portal" in ready["body"]


def test_capital_hilton_client_body_has_no_backend_status_terms():
    draft = invoice_review_bundle.build_capital_hilton_bundle()["clara_invoice_email_draft_package"]

    assert draft["client_facing_body_has_backend_status_language"] is False
    lowered = draft["body"].lower()
    for term in drafts.CLIENT_FACING_FORBIDDEN_TERMS:
        assert term not in lowered


def test_live_arts_md_draft_has_no_coupa_language():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    assert draft["supplier_portal_provider"] is None
    assert "Coupa" not in draft["body"]
    assert "supplier portal" not in draft["body"]


def test_live_arts_md_recipient_package_includes_required_candidates():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    to_names = {item["display_name"] for item in draft["to_recipients"]}
    cc_by_name = {item["display_name"]: item for item in draft["cc_recipients"]}
    assert to_names == {"Dance"}
    assert {"Draper", "Earnie", "Winship"} <= set(cc_by_name)
    assert cc_by_name["Winship"]["email"] == "winshiplive@gmail.com"
    assert cc_by_name["Draper"]["email"] is None
    assert cc_by_name["Earnie"]["email"] is None
    assert draft["recipient_email_invented"] is False


def test_live_arts_missing_contact_info_blocks_send_readiness():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    assert "recipient_confirmation" in draft["missing_prerequisites"]
    assert draft["send_readiness"] == "BLOCKED_PREREQUISITES"
    assert live["recipient_state"]["status"] == "RECIPIENT_INFO_REQUIRED"


def test_live_arts_draft_does_not_claim_attachment_if_not_ready():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    assert draft["attachment_ready"] is False
    assert "Attached is" not in draft["body"]
    assert "invoice file" in draft["body"]


def test_live_arts_body_is_client_facing_not_backend_status_copy():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    assert draft["client_facing_body_has_backend_status_language"] is False
    lowered = draft["body"].lower()
    for term in drafts.CLIENT_FACING_FORBIDDEN_TERMS:
        assert term not in lowered


def test_arts_alive_md_alias_is_preserved_as_correction_candidate():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    alias = live["client_alias_readiness"]

    assert alias["canonical_client_ref"] == "live_arts_md"
    assert "Arts Alive MD!" in alias["aliases"]
    assert alias["status"] == "ALIAS_CORRECTION_CANDIDATE"


def test_guardian_approval_and_send_execution_remain_separate():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    capital = invoice_review_bundle.build_capital_hilton_bundle()

    for draft in (
        live["clara_invoice_email_draft_package"],
        capital["clara_invoice_email_draft_package"],
    ):
        assert draft["guardian_approval_required"] is True
        assert draft["guardian_approval_request_status"] == "NOT_CREATED"
        assert draft["send_execution_receipt_required"] is True
        assert draft["send_execution_status"] == "NOT_SENT"
        assert draft["sent"] is False
