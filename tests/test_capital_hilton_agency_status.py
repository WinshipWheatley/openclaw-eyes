import json

import capital_hilton_agency_status as agency_status


def test_capital_hilton_agency_status_is_read_only_and_attributed():
    payload = agency_status.build_capital_hilton_agency_status(
        generated_at="2026-06-19T00:00:00+00:00"
    )

    assert payload["schema_version"] == agency_status.SCHEMA_VERSION
    assert payload["evidence_tier"] == "operator_supplied_current_status_not_bank_or_payment_proof"
    assert payload["authority_flags"]["external_action_performed"] is False
    assert payload["authority_flags"]["money_movement_performed"] is False
    assert payload["authority_flags"]["ledger_mutation_performed"] is False
    assert payload["authority_flags"]["paid_marking_performed"] is False
    assert payload["machine_proof"]["autonomous_completion_false"] is True
    assert payload["content_hash"].startswith("sha256:")


def test_capital_hilton_answers_do_not_overclaim_payment_or_watch_status():
    agency_answer = agency_status.format_capital_hilton_agency_answer(
        "Capital Hilton provenance: who did what because Codex Desktop did the work?"
    )
    openclaw_answer = agency_status.format_capital_hilton_openclaw_status_answer(
        "What is the OpenClaw status for Capital Hilton email watch, ledger, and next invoice?"
    )

    assert agency_answer is not None
    assert "not bank or payment-processor proof" in agency_answer
    assert "did not autonomously send messages" in agency_answer
    assert openclaw_answer is not None
    assert "payment-watch, not paid" in openclaw_answer
    assert "do not claim a live Capital Hilton-specific Gmail watch" in openclaw_answer
    assert "do not mark paid from memory or email alone" in openclaw_answer


def test_cassandra_brain_imports_capital_hilton_agency_status_route():
    import cassandra_brain

    assert cassandra_brain.format_capital_hilton_agency_answer(
        "Capital Hilton agency attribution: how do you know who supplied the truth?"
    )
    assert cassandra_brain.format_capital_hilton_openclaw_status_answer(
        "What is the Capital Hilton OpenClaw status for incoming emails?"
    )


def test_capital_hilton_agency_status_stable_json_is_sorted():
    payload = agency_status.build_capital_hilton_agency_status(
        generated_at="2026-06-19T00:00:00+00:00"
    )

    encoded = agency_status.stable_json(payload)
    assert json.loads(encoded)["schema_version"] == agency_status.SCHEMA_VERSION
    assert encoded.endswith("\n")
