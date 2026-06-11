import json
from pathlib import Path

from operator_universal_intake import (
    JSON_EXPORT_NAME,
    SUPPORTED_ACTION_TYPES,
    parse_operator_intake_text,
    process_operator_intake,
)
from watch_desk_feed import build_watch_desk_feed


FIXED_NOW = "2026-06-11T15:00:00+00:00"


def _process(tmp_path: Path, text: str, **kwargs):
    return process_operator_intake(
        raw_text=text,
        surface=kwargs.pop("surface", "local_cli"),
        operator=kwargs.pop("operator", "Winship"),
        received_at_utc=kwargs.pop("received_at_utc", FIXED_NOW),
        read_model_root=tmp_path / "read_models",
        receipt_root=tmp_path / "receipts",
        **kwargs,
    )


def test_all_required_examples_parse_expected_action_lane_and_risk():
    examples = [
        ("Sign this as Winship.", "identity_signature_preference", "chief_identity", "low"),
        ("Start using Clara Reid.", "identity_signature_preference", "chief_identity", "low"),
        ("I did a St. Anne\u2019s gig tonight.", "gig_event_log", "cassandra_business/niles_context", "low"),
        ("I got paid $900 from Live Arts MD.", "income_payment_log", "cassandra_finance", "low"),
        ("I got paid $1250 from St. Anne's.", "income_payment_log", "cassandra_finance", "low"),
        ("I spent $106 on Claude Code Fable 5.", "expense_log", "cassandra_finance", "low"),
    ]

    for text, action_type, lane, risk in examples:
        parsed = parse_operator_intake_text(text, received_at_utc=FIXED_NOW)
        assert parsed["parsed"]["action_type"] == action_type
        assert parsed["parsed"]["lane"] == lane
        assert parsed["risk_tier"] == risk


def test_relative_tonight_normalizes_to_absolute_date():
    parsed = parse_operator_intake_text("I did a St. Anne's gig tonight.", received_at_utc=FIXED_NOW)

    assert parsed["parsed"]["fields"]["event_date"] == "2026-06-11"
    assert parsed["parsed"]["fields"]["date_basis"] == "implied_tonight"


def test_low_risk_income_writes_receipt_read_model_and_watch_item(tmp_path):
    result = _process(tmp_path, "I got paid $900 from Live Arts MD.")
    read_model_path = tmp_path / "read_models" / JSON_EXPORT_NAME

    assert result["approval_required"] is False
    assert result["receipts"]
    assert Path(result["receipts"][0]["path"]).is_file()
    assert read_model_path.is_file()
    receipt = json.loads(Path(result["receipts"][0]["path"]).read_text(encoding="utf-8"))
    assert receipt["external_calls_performed"] is False
    assert receipt["approval_required"] is False
    assert receipt["parsed_fields"]["invoice_marked_paid"] is False
    assert receipt["mutation_scope"] == "local_read_model_or_receipt_only"

    read_model = json.loads(read_model_path.read_text(encoding="utf-8"))
    assert read_model["event_count"] == 1
    assert read_model["events"][0]["parsed"]["fields"]["amount"] == 900
    assert read_model["events"][0]["safe_actions_taken"] == ["record_local_income_payment_receipt"]

    feed = build_watch_desk_feed(read_model_root=tmp_path / "read_models", task_root=tmp_path / "tasks")
    plain_lines = [item["plain_line"] for item in feed["feed_items"]]
    assert "Logged income: $900 from Live Arts MD. Missing: invoice/project link, payment method." in plain_lines


def test_ambiguous_sign_this_asks_for_referent_and_does_not_mutate(tmp_path):
    result = _process(tmp_path, "Sign this as Winship.")

    assert result["parsed"]["action_type"] == "identity_signature_preference"
    assert result["needs_clarification"] == ["referent:this"]
    assert result["safe_actions_taken"] == []
    assert result["receipts"] == []
    assert result["watch_desk_items"] == []
    assert result["approval_required"] is False
    assert not (tmp_path / "read_models" / JSON_EXPORT_NAME).exists()


def test_st_annes_payment_associates_with_recent_gig_context(tmp_path):
    gig = _process(tmp_path, "I did a St. Anne's gig tonight.")
    payment = _process(
        tmp_path,
        "I got paid $1250 from St. Anne's.",
        session_context={"recent_gigs": [gig]},
    )

    fields = payment["parsed"]["fields"]
    assert fields["payer"] == "St. Anne's"
    assert fields["amount"] == 1250
    assert fields["associated_gig_intake_id"] == gig["intake_id"]
    assert fields["associated_gig_date"] == "2026-06-11"


def test_expense_log_labels_category_without_tax_advice(tmp_path):
    result = _process(tmp_path, "I spent $106 on Claude Code Fable 5.")

    fields = result["parsed"]["fields"]
    assert fields["amount"] == 106
    assert fields["vendor"] == "Claude Code"
    assert fields["purchase_label"] == "Claude Code Fable 5"
    assert fields["category_label"] == "AI tools/software"
    assert fields["tax_advice_given"] is False
    assert "tax advice" not in result["normalized_summary"].lower()


def test_unknown_low_confidence_input_only_requests_clarification(tmp_path):
    result = _process(tmp_path, "Handle that confusing thing.")

    assert result["parsed"]["action_type"] == "unknown"
    assert result["parsed"]["confidence"] < 0.5
    assert result["needs_clarification"] == ["action_type"]
    assert result["safe_actions_taken"] == []
    assert result["receipts"] == []
    assert result["watch_desk_items"] == []


def test_remote_surfaces_store_hash_ref_not_raw_text(tmp_path):
    result = _process(tmp_path, "I got paid $900 from Live Arts MD.", surface="telegram")

    assert "raw_text" not in result
    assert result["raw_text_ref"].startswith("sha256:")
    assert result["raw_text_stored"] is False


def test_no_external_or_approval_side_effects_for_supported_local_events(tmp_path):
    for text in [
        "Start using Clara Reid.",
        "I did a St. Anne's gig tonight.",
        "I got paid $900 from Live Arts MD.",
        "I spent $106 on Claude Code Fable 5.",
    ]:
        result = _process(tmp_path, text)
        assert result["approval_required"] is False
        assert result["authority_boundary"]["external_calls_performed"] is False
        assert result["authority_boundary"]["approval_request_created"] is False
        assert result["authority_boundary"]["gmail_or_broker_called"] is False
        assert result["authority_boundary"]["coupa_bank_external_ledger_mutated"] is False
        assert result["authority_boundary"]["invoice_marked_paid"] is False

    assert set(SUPPORTED_ACTION_TYPES) == {
        "income_payment_log",
        "expense_log",
        "gig_event_log",
        "identity_signature_preference",
    }
