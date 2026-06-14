import json
from pathlib import Path

import operator_human_readability_surface as surface


FIXED_NOW = "2026-06-02T07:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_read_models(root: Path) -> None:
    _write_json(
        root / "st_annes_invoice_status.json",
        {
            "invoice_status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
            "openclaw_send_performed": False,
            "paid": False,
            "ledger_posting_allowed": False,
            "manual_send_out_of_band_known": True,
            "proof_refs": {
                "receipt_ref": "/proof/st_annes_receipt.json",
                "pdf_ref": "/proof/st_annes_invoice.pdf",
            },
        },
    )
    _write_json(
        root / "capital_hilton_invoice_operator_run_status.json",
        {
            "coupa_submission_recorded": True,
            "coupa_submitted": True,
            "coupa_status_observed": "Processing",
            "email_to_annette_recorded": True,
            "ledger_mutation_performed": False,
            "paid": False,
            "autonomous_openclaw_coupa_submit": False,
            "autonomous_openclaw_email_send": False,
            "proof_refs": {
                "receipt_ref": "/proof/capital_receipt.json",
                "run_report_ref": "/proof/capital_run.md",
                "pdf_ref": "/proof/capital_invoice.pdf",
            },
        },
    )
    _write_json(
        root / "capital_hilton_business_development_proposal.json",
        {
            "proposal_status": "SENT_FOR_CLIENT_REVIEW",
            "proposal_accepted": False,
            "finance_handoff_allowed": False,
            "paid": False,
            "proposal_sent_recorded": True,
            "proof_refs": {
                "proposal_send_receipt_ref": "/proof/proposal_send.json",
                "proposal_pdf_ref": "/proof/proposal.pdf",
            },
        },
    )
    _write_json(
        root / "st_annes_work_log_events.json",
        {
            "rules": {
                "operator_confirmation_required_before_invoice_inclusion": True,
                "smoke_or_test_events_not_invoice_included": True,
            },
            "staged_events": [
                {
                    "event_id": "st_annes_work_log:fixture",
                    "operator_confirmed": False,
                    "invoice_inclusion_status": "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED",
                }
            ],
        },
    )


def _card_by_id(read_model: dict, card_id: str) -> dict:
    cards = {card["card_id"]: card for card in read_model["thread_cards"]}
    return cards[card_id]


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_surface_json_parses_and_exports_bridge_equal(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)

    result = surface.export_surface_read_model(
        read_model_root=read_model_root,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Human Readability Surface.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["schema_version"] == surface.SCHEMA_VERSION
    assert local["status"] == surface.CONTRACT_STATUS
    assert Path(result["wiki_path"]).exists()


def test_capital_hilton_submitted_state_produces_submitted_compact_card(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)
    read_model = surface.build_surface_read_model(
        read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )

    card = _card_by_id(read_model, "finance.capital_hilton.invoice_operator_run")
    assert card["headline"] == "Capital Hilton invoice submitted"
    assert card["summary"] == "Coupa is processing, and Annette was emailed."
    assert card["status_label"] == "Submitted"
    assert card["next_safe_action"] == "Watch Coupa and payment."
    assert card["proof_drawer"]["collapsed_by_default"] is True


def test_st_annes_manual_send_produces_sent_outside_openclaw_card(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)
    read_model = surface.build_surface_read_model(
        read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )

    card = _card_by_id(read_model, "finance.st_annes.invoice_may_2026")
    assert card["headline"] == "St. Anne\u2019s invoice sent"
    assert card["summary"] == "May invoice was sent manually and recorded."
    assert card["status_label"] == "Sent outside OpenClaw"
    assert card["next_safe_action"] == "Watch for payment."
    assert card["source_truth_summary"]["openclaw_send_performed"] is False


def test_stale_candidate_override_exists_for_capital_hilton_invoice_panel(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)
    read_model = surface.build_surface_read_model(
        read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )

    overrides = {item["override_id"]: item for item in read_model["stale_surface_overrides"]}
    override = overrides["capital_hilton_invoice_candidate_after_operator_submission"]
    assert override["action"] == "secondary_or_hidden"
    assert override["replacement_card_id"] == "finance.capital_hilton.invoice_operator_run"


def test_proof_collapsed_by_default_and_machine_refs_hidden(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)
    read_model = surface.build_surface_read_model(
        read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )

    assert read_model["display_rules"]["proof_collapsed_by_default"] is True
    assert read_model["display_rules"]["machine_refs_primary_visible"] is False
    assert read_model["helm_briefing"]["proof_drawer"]["collapsed_by_default"] is True
    assert all(card["proof_drawer"]["collapsed_by_default"] is True for card in read_model["thread_cards"])
    assert all(card["machine_refs_primary_visible"] is False for card in read_model["thread_cards"])


def test_no_unsafe_true_grants(tmp_path):
    read_model_root = tmp_path / "source_read_models"
    _fixture_read_models(read_model_root)
    read_model = surface.build_surface_read_model(
        read_model_root=read_model_root,
        generated_at=FIXED_NOW,
    )
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "workbook_mutation_allowed",
        "workbook_source_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "sent",
        "paid",
    }

    assert not [
        key
        for key, value in _walk_values(read_model)
        if key in unsafe_keys and value is True
    ]
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
