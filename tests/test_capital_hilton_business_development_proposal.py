import json
from pathlib import Path

import pytest

import capital_hilton_business_development_proposal as proposal


FIXED_NOW = "2026-06-01T22:00:00+00:00"


def _write_fixture(input_dir: Path, *, unsafe: bool = False) -> dict[str, str]:
    input_dir.mkdir(parents=True, exist_ok=True)
    markdown = input_dir / proposal.EXPECTED_MARKDOWN_NAME
    pdf = input_dir / proposal.OPTIONAL_PDF_NAME
    packet = input_dir / proposal.EXPECTED_PACKET_NAME
    receipt = input_dir / proposal.EXPECTED_RECEIPT_NAME
    markdown.write_text("# Capital Hilton Fight Weekend Entertainment Proposal\n", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4\nfixture proposal pdf\n")
    markdown_sha = proposal.sha256_file(markdown)
    pdf_sha = proposal.sha256_file(pdf)
    packet_payload = {
        "schema_version": "capital_hilton_fight_weekend_proposal_packet_v2",
        "status": "CAPITAL_HILTON_PROPOSAL_FILE_READY_FOR_REVIEW",
        "world": "Business Development",
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "proposal_ref": "capital_hilton_fight_weekend_2026",
        "title": "Capital Hilton Fight Weekend Entertainment Proposal",
        "subtitle": "Hybrid Live + DJ Lounge Set | Friday & Saturday",
        "markdown_path": "/Volumes/openclaw_e/artifacts/proposals/capital_hilton/fight_weekend_2026/" + proposal.EXPECTED_MARKDOWN_NAME,
        "markdown_sha256": markdown_sha,
        "pdf_path": "/Volumes/openclaw_e/artifacts/proposals/capital_hilton/fight_weekend_2026/" + proposal.OPTIONAL_PDF_NAME,
        "pdf_sha256": pdf_sha,
        "pdf_created": True,
        "pricing": {
            "two_night_hybrid_live_dj_package_total_usd": 1200,
            "expanded_sound_system_add_on_usd": 400,
            "optional_subwoofer_each_usd": 100,
            "dj_only_pricing_note": "DJ-only is not cheaper as a standalone service.",
        },
        "email_send_allowed": unsafe,
        "ledger_posting_allowed": False,
        "sent": False,
        "paid": False,
        "proposal_accepted": False,
        "business_authority_boundary": {
            "email_send_allowed": unsafe,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "finance_invoice_allowed": False,
            "sent": False,
            "paid": False,
            "proposal_accepted": False,
        },
        "provider_decision": "local_only",
        "privacy_impact": "local_only",
    }
    packet.write_text(json.dumps(packet_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_payload = {
        "schema_version": "capital_hilton_fight_weekend_proposal_review_receipt_v2",
        "status": "CAPITAL_HILTON_PROPOSAL_FILE_READY_FOR_REVIEW",
        "client_ref": "capital_hilton",
        "proposal_ref": "capital_hilton_fight_weekend_2026",
        "markdown_path": packet_payload["markdown_path"],
        "markdown_sha256": markdown_sha,
        "pdf_path": packet_payload["pdf_path"],
        "pdf_sha256": pdf_sha,
        "pdf_created": True,
        "packet_path": "/Volumes/openclaw_e/artifacts/proposals/capital_hilton/fight_weekend_2026/" + proposal.EXPECTED_PACKET_NAME,
        "packet_sha256": proposal.sha256_file(packet),
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "sent": False,
        "paid": False,
        "proposal_accepted": False,
        "safety_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "finance_invoice_allowed": False,
            "sent": False,
            "paid": False,
            "proposal_accepted": False,
        },
        "actions_performed": {
            "email_send_performed": False,
            "gmail_used": False,
            "browser_used": False,
            "coupa_used": False,
            "invoice_created": False,
            "ledger_mutation_performed": False,
            "proposal_accepted": False,
        },
        "provider_decision": "local_only",
        "privacy_impact": "local_only",
    }
    receipt.write_text(json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"markdown_sha": markdown_sha, "pdf_sha": pdf_sha, "packet_sha": proposal.sha256_file(packet)}


def _write_send_receipt(input_dir: Path, *, unsafe: str = "") -> Path:
    pdf = input_dir / proposal.OPTIONAL_PDF_NAME
    receipt = input_dir / "capital_hilton_proposal_email_sent_receipt_20260601T223704Z.json"
    payload = {
        "status": "CAPITAL_HILTON_PROPOSAL_EMAIL_SENT",
        "client_ref": "capital_hilton",
        "proposal_ref": "capital_hilton_fight_weekend_2026",
        "proposal_sent": True,
        "email_send_performed": True,
        "sent_by_openclaw": False,
        "operator_assisted": True,
        "recipient": "lawrencevalcovic@hilton.com",
        "recipient_display_name": "Will / Lawrence Valcovic",
        "subject": "Capital Hilton Fight Weekend Entertainment Proposal",
        "body": "raw proposal email body should not be copied into the read model",
        "attachment_path": "/Volumes/openclaw_e/artifacts/proposals/capital_hilton/fight_weekend_2026/" + proposal.OPTIONAL_PDF_NAME,
        "attachment_sha256": proposal.sha256_file(pdf),
        "attachment_size_bytes": pdf.stat().st_size,
        "sent_gmail_message_id": "19e855535bff299a",
        "sent_gmail_thread_id": "19e8552e276fe4d3",
        "finance_handoff_allowed": False,
        "ledger_posting_allowed": False,
        "ledger_mutation_performed": False,
        "invoice_created": False,
        "coupa_used": False,
        "paid": False,
        "proposal_accepted": False,
    }
    if unsafe == "accepted":
        payload["proposal_accepted"] = True
    if unsafe == "ledger":
        payload["ledger_mutation_performed"] = True
    if unsafe == "sent_by_openclaw":
        payload["sent_by_openclaw"] = True
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def test_build_read_model_records_proposal_for_review_without_business_authority(tmp_path):
    hashes = _write_fixture(tmp_path)

    payload = proposal.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)

    assert payload["schema_version"] == proposal.SCHEMA_VERSION
    assert payload["read_model_id"] == proposal.READ_MODEL_ID
    assert payload["world"] == "business_development"
    assert payload["client_ref"] == "capital_hilton"
    assert payload["proposal_status"] == "DRAFT_READY_FOR_OPERATOR_REVIEW"
    assert payload["finance_handoff_allowed"] is False
    assert payload["email_send_allowed"] is False
    assert payload["ledger_posting_allowed"] is False
    assert payload["sent"] is False
    assert payload["paid"] is False
    assert payload["proposal_accepted"] is False
    assert payload["artifact_refs"]["markdown"]["sha256"] == hashes["markdown_sha"]
    assert payload["artifact_refs"]["pdf"]["sha256"] == hashes["pdf_sha"]
    assert payload["artifact_refs"]["packet"]["sha256"] == hashes["packet_sha"]
    assert payload["proposal_terms"]["two_night_total_usd"] == 1200
    assert all(value is False for value in payload["safety_boundary"].values())


def test_build_read_model_rejects_unsafe_source_packet(tmp_path):
    _write_fixture(tmp_path, unsafe=True)

    with pytest.raises(ValueError, match="unsafe"):
        proposal.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)


def test_export_writes_local_and_bridge_read_model(tmp_path):
    _write_fixture(tmp_path / "input")

    result = proposal.export_read_model(
        input_dir=tmp_path / "input",
        export_root=tmp_path / "local",
        bridge_export_root=tmp_path / "bridge",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result.read_model_path).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result.bridge_read_model_path).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["proposal_status"] == "DRAFT_READY_FOR_OPERATOR_REVIEW"
    assert local["machine_proof"]["no_business_action_performed"] is True


def test_build_read_model_records_sent_proposal_without_finance_or_acceptance(tmp_path):
    _write_fixture(tmp_path)
    send_receipt = _write_send_receipt(tmp_path)

    payload = proposal.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)

    assert payload["proposal_status"] == "SENT_FOR_CLIENT_REVIEW"
    assert payload["proposal_sent_recorded"] is True
    assert payload["email_send_recorded"] is True
    assert payload["email_send_record"]["sent_by_openclaw"] is False
    assert payload["email_send_record"]["raw_message_included"] is False
    assert payload["artifact_refs"]["proposal_send_receipt"]["path"] == str(send_receipt)
    assert payload["proposal_accepted"] is False
    assert payload["finance_handoff_allowed"] is False
    assert payload["ledger_posting_allowed"] is False
    assert payload["paid"] is False
    assert payload["machine_proof"]["proposal_status_sent_for_client_review"] is True
    assert payload["machine_proof"]["no_new_business_action_performed_by_ingest"] is True
    payload_text = json.dumps(payload)
    assert "body" not in payload_text
    assert "raw proposal email body should not be copied" not in payload_text


@pytest.mark.parametrize("unsafe", ["accepted", "ledger", "sent_by_openclaw"])
def test_build_read_model_rejects_unsafe_send_receipt(tmp_path, unsafe):
    _write_fixture(tmp_path)
    _write_send_receipt(tmp_path, unsafe=unsafe)

    with pytest.raises(ValueError):
        proposal.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)
