import clara_invoice_email_draft_package as drafts
import invoice_review_bundle
import live_arts_md_invoice_review_bundle


def _st_annes_invoice_data():
    return {
        "client_name": "St. Anne's",
        "line_items": (
            {"event": "Wedding ceremony", "date": "June 6, 2026", "amount": 125},
            {"event": "Community recital", "date": "June 13, 2026", "amount": 125},
        ),
        "total": 250,
        "attachment_filename": "St_Annes_June_2026_invoice.pdf",
    }


def test_general_client_invoice_body_is_human_and_guard_clean():
    body = drafts.build_general_client_invoice_body(
        _st_annes_invoice_data(),
        {"name": "Draper", "email": "draper@example.com"},
    )

    assert "Hi Draper," in body
    assert "St. Anne's" in body
    assert "Wedding ceremony" in body
    assert "June 6, 2026" in body
    assert "Community recital" in body
    assert "June 13, 2026" in body
    assert "$125.00" in body
    assert "$250.00" in body
    assert "attached" in body.lower()
    assert "PDF" in body
    assert "I hope this note finds you well." in body
    assert "coming to $250.00" in body
    assert "There's nothing needed on your end right now" in body
    assert body.endswith("Warmly,\nClara Reid")
    assert "Executive Assistant" not in body
    assert drafts.body_contains_backend_status_language(body) is False
    lowered = body.lower()
    for term in drafts.CLIENT_FACING_FORBIDDEN_TERMS:
        assert term not in lowered


def test_general_client_invoice_body_uses_neutral_greeting_without_contact_name():
    body = drafts.build_general_client_invoice_body(
        _st_annes_invoice_data(),
        {"email": "billing@example.com"},
    )

    assert body.startswith("Hello,\n\n")
    assert "billing@example.com" not in body


def test_client_without_specific_recipe_routes_to_general_body_not_placeholder():
    recipient_package = drafts._recipient_package(  # type: ignore[attr-defined]
        (
            drafts._recipient(  # type: ignore[attr-defined]
                "Draper",
                "primary_invoice_contact",
                "to",
                confirmed=True,
            ),
        )
    )

    draft = drafts.build_clara_invoice_email_draft_package(
        client_ref="st_annes",
        workflow_ref="st_annes_invoice_workflow",
        client_display_name="St. Anne's",
        recipient_package=recipient_package,
        attachment_ready=True,
        attachment_refs=("artifact_ref:st_annes_invoice_pdf",),
        invoice_period_label="June 2026 services",
        supplier_portal_required=False,
        first_contact_intro_required=False,
        present_receipts=("clara_email_draft_receipt",),
        invoice_data=_st_annes_invoice_data(),
        contact={"name": "Draper", "email": "draper@example.com"},
    )

    assert draft["draft_status"] == drafts.FINAL_DRAFT_READY_FOR_APPROVAL
    assert draft["client_facing_draft_ready_for_approval"]["ready"] is True
    assert draft["client_facing_draft_ready_for_approval"]["body"] == draft["body"]
    assert draft["to_recipients"][0]["email"] == "draper@example.com"
    assert "Wedding ceremony" in draft["body"]
    assert "Community recital" in draft["body"]
    assert "St_Annes_June_2026_invoice.pdf" in draft["body"]
    assert "[Name]" not in draft["body"]
    assert "Invoice attachment: [confirmed invoice attachment]" not in draft["body"]
    assert "Work covered: [confirmed invoice period or dates]" not in draft["body"]
    assert drafts.body_contains_backend_status_language(draft["body"]) is False


def test_synthetic_registry_client_routes_to_warm_general_body_without_code_change():
    registry = {
        "north_star_venue": {
            "client_ref": "north_star_venue",
            "client_display_name": "North Star Venue",
            "recipients": (
                {
                    "display_name": "Mira Sol",
                    "role": "primary_invoice_contact",
                    "lane": "to",
                    "email": "mira@example.com",
                },
            ),
        },
    }
    draft = drafts.build_clara_invoice_email_draft_package(
        client_ref="north_star_venue",
        workflow_ref="north_star_invoice_workflow",
        client_display_name="North Star Venue",
        recipient_package=drafts._recipient_package(()),  # type: ignore[attr-defined]
        attachment_ready=True,
        attachment_refs=("artifact_ref:north_star_invoice_pdf",),
        invoice_period_label="July 2026 production support",
        supplier_portal_required=False,
        first_contact_intro_required=False,
        present_receipts=("clara_email_draft_receipt",),
        invoice_data={
            "client_name": "North Star Venue",
            "attachment_filename": "North_Star_July_2026.pdf",
            "line_items": (
                {"description": "Production support", "date": "2026-07-02", "amount": 500.0},
            ),
            "amount_total": 500.0,
        },
        client_registry=registry,
    )

    assert draft["draft_status"] == drafts.FINAL_DRAFT_READY_FOR_APPROVAL
    assert draft["client_facing_draft_ready_for_approval"]["ready"] is True
    assert draft["to_recipients"][0]["display_name"] == "Mira Sol"
    assert draft["to_recipients"][0]["email"] == "mira@example.com"
    assert "Hi Mira," in draft["body"]
    assert "I hope this note finds you well." in draft["body"]
    assert "Winship's invoice for North Star Venue is attached (North_Star_July_2026.pdf)" in draft["body"]
    assert "coming to $500.00" in draft["body"]
    assert "Warmly,\nClara Reid" in draft["body"]
    assert "Please let us know if anything else is needed for processing." not in draft["body"]
    assert drafts.body_contains_backend_status_language(draft["body"]) is False


def test_registered_clients_use_general_warm_body_not_per_client_body_recipes():
    source = drafts.__loader__.get_source(drafts.__name__)  # type: ignore[union-attr]

    assert "def _capital_hilton_body" not in source
    assert "def _live_arts_md_body" not in source
    assert 'client_ref == "capital_hilton"' not in source
    assert 'client_ref == "live_arts_md"' not in source

    capital = drafts.build_clara_invoice_email_draft_package(
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

    assert "I hope this note finds you well." in capital["body"]
    assert "Winship's invoice for Capital Hilton is attached" in capital["body"]
    assert "coming to" not in capital["body"]
    assert "The matching invoice has been submitted through the Coupa supplier portal." in capital["body"]
    assert capital["body"].endswith("Warmly,\nClara Reid")


def test_existing_capital_hilton_ready_body_uses_warm_general_copy():
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

    assert ready["body"] == (
        "Hi Annette,\n\n"
        "I hope this note finds you well. Winship's invoice for Capital Hilton is attached - "
        "it covers May 1, 2026 and May 8, 2026.\n"
        "The matching invoice has been submitted through the Coupa supplier portal.\n\n"
        "There's nothing needed on your end right now; we'll keep things moving from here, "
        "and Winship can take care of payment whenever it's convenient.\n\n"
        "Warmly,\n"
        "Clara Reid"
    )


def test_existing_live_arts_ready_body_uses_warm_general_copy():
    ready = drafts.build_clara_invoice_email_draft_package(
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        client_display_name="Live Arts MD",
        recipient_package=drafts.live_arts_md_recipient_package(confirmed=True),
        attachment_ready=True,
        attachment_refs=("artifact_ref:live_arts_invoice",),
        invoice_period_label="June 2026 Speaker Rental",
        supplier_portal_required=False,
        first_contact_intro_required=True,
        present_receipts=("clara_email_draft_receipt",),
    )

    assert ready["body"] == (
        "Hi Dane,\n\n"
        "I hope this note finds you well. Winship's invoice for Live Arts MD is attached - "
        "it covers June 2026 Speaker Rental.\n\n"
        "There's nothing needed on your end right now; we'll keep things moving from here, "
        "and Winship can take care of payment whenever it's convenient.\n\n"
        "Warmly,\n"
        "Clara Reid"
    )


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
    assert to_names == {"Dane"}
    assert {"Draper", "Earnie", "Winship"} <= set(cc_by_name)
    assert cc_by_name["Winship"]["email"] == "winshiplive@gmail.com"
    assert next(item for item in draft["to_recipients"] if item["display_name"] == "Dane")["email"] is None
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
    assert "confirmed Live Arts MD invoice" in draft["body"]


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


def test_target_blueprint_exists_while_send_ready_draft_is_blocked():
    live = live_arts_md_invoice_review_bundle.build_live_arts_md_bundle()
    draft = live["clara_invoice_email_draft_package"]

    blueprint = draft["target_client_email_blueprint"]
    ready = draft["client_facing_draft_ready_for_approval"]
    sent = draft["sent_email"]

    assert blueprint["status"] == drafts.TARGET_BLUEPRINT_NOT_SEND_READY
    assert blueprint["send_ready"] is False
    assert "selected invoice period or work type" in blueprint["body_template"]
    assert ready["ready"] is False
    assert ready["body"] is None
    assert "attachment_readiness" in ready["blocked_by"]
    assert sent["status"] == drafts.SENT_EMAIL_NOT_SENT
    assert sent["sent"] is False


def test_send_ready_draft_can_claim_attachment_only_when_ready():
    ready = drafts.build_clara_invoice_email_draft_package(
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        client_display_name="Live Arts MD",
        recipient_package=drafts.live_arts_md_recipient_package(confirmed=True),
        attachment_ready=True,
        attachment_refs=("artifact_ref:live_arts_invoice",),
        invoice_period_label="June 2026 Speaker Rental",
        supplier_portal_required=False,
        first_contact_intro_required=True,
        present_receipts=("clara_email_draft_receipt",),
    )

    assert ready["draft_status"] == drafts.FINAL_DRAFT_READY_FOR_APPROVAL
    assert ready["client_facing_draft_ready_for_approval"]["ready"] is True
    assert "Winship's invoice for Live Arts MD is attached" in ready["body"]
    assert "I hope this note finds you well." in ready["client_facing_draft_ready_for_approval"]["body"]
