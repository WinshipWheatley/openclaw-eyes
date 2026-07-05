from __future__ import annotations

import copy

from packet_request_gate import validate_request, validate_requests


def _source() -> dict:
    return {
        "invoice_records": {
            "st_annes": [
                {
                    "label": "St Anne's June invoice total",
                    "value": "$875 due",
                    "source_ref": "ledger://invoice_records/st_annes_june",
                    "pii_tier": "LIGHT",
                    "provenance": "sqlite_ledger_mirror",
                }
            ]
        },
        "client_model": {
            "st_annes": {
                "label": "St Anne's client model",
                "value": "simple email invoice workflow",
                "source_ref": "registry://client_model/st_annes",
                "pii_tier": "PUBLIC",
            }
        },
        "payment_status": {
            "st_annes": {
                "label": "St Anne's payment status",
                "value": "matched bank deposit present",
                "source_ref": "ledger://payment_status/st_annes",
                "pii_tier": "LIGHT",
            }
        },
        "ledger_fact_by_topic": {
            "invoice_doctrine": {
                "label": "Invoice source of truth",
                "value": "Workbook owns billed lines; bank owns paid truth.",
                "source_ref": "operator://invoice_source_of_truth_doctrine",
                "pii_tier": "PUBLIC",
            }
        },
    }


def test_catalog_request_within_tier_returns_fetcher_with_provenance():
    result = validate_request(
        {
            "need": "invoice_records",
            "entity": "st_annes",
            "reason": "Need the invoice total before answering.",
        },
        caller_pii_tier="LIGHT",
        source=_source(),
    )

    assert result["allowed"] is True
    assert callable(result["fetch"])
    facts = result["fetch"]()
    assert facts == [
        {
            "need": "invoice_records",
            "entity": "st_annes",
            "label": "St Anne's June invoice total",
            "value": "$875 due",
            "source_ref": "ledger://invoice_records/st_annes_june",
            "pii_tier": "LIGHT",
            "provenance": "sqlite_ledger_mirror",
        }
    ]


def test_over_tier_request_is_denied():
    result = validate_request(
        {"need": "payment_status", "entity": "st_annes", "reason": "Need paid status."},
        caller_pii_tier="PUBLIC",
        source=_source(),
    )

    assert result["allowed"] is False
    assert result["fetch"] is None
    assert "PII tier" in result["reason"]


def test_unknown_need_and_unknown_entity_are_denied():
    unknown_need = validate_request(
        {"need": "raw_spreadsheet", "entity": "st_annes", "reason": "Need raw cells."},
        caller_pii_tier="MAX",
        source=_source(),
    )
    unknown_entity = validate_request(
        {"need": "client_model", "entity": "mystery_client", "reason": "Need client."},
        caller_pii_tier="MAX",
        source=_source(),
    )

    assert unknown_need["allowed"] is False
    assert unknown_need["fetch"] is None
    assert "not in grounded catalog" in unknown_need["reason"]
    assert unknown_entity["allowed"] is False
    assert unknown_entity["fetch"] is None
    assert "unknown entity" in unknown_entity["reason"]


def test_hard_deny_control_and_secret_requests_are_refused():
    hard_denied = [
        {"need": "send_approval", "entity": "st_annes", "reason": "Approve send."},
        {"need": "send_hold_override", "entity": "st_annes", "reason": "Lift hold."},
        {"need": "legal_body", "entity": "case_file", "reason": "Need legal body."},
        {"need": "credentials", "entity": "gmail", "reason": "Need secret token."},
        {"need": "money_move_authority", "entity": "bank", "reason": "Move funds."},
        {
            "need": "ledger_fact_by_topic",
            "entity": "send_hold_override",
            "reason": "Benign status lookup for the control gate.",
        },
    ]

    for req in hard_denied:
        result = validate_request(req, caller_pii_tier="MAX", source=_source())
        assert result["allowed"] is False, req
        assert result["fetch"] is None, req
        assert "hard-denied" in result["reason"], req


def test_validate_requests_caps_at_three_and_denies_extras():
    req = {"need": "client_model", "entity": "st_annes", "reason": "Need client model."}
    results = validate_requests([req, req, req, req], caller_pii_tier="PUBLIC", source=_source())

    assert [item["allowed"] for item in results] == [True, True, True, False]
    assert results[3]["fetch"] is None
    assert "request cap exceeded" in results[3]["reason"]


def test_fetchers_are_read_only_and_do_not_emit_actions():
    source = _source()
    before = copy.deepcopy(source)
    result = validate_request(
        {"need": "ledger_fact_by_topic", "entity": "invoice_doctrine", "reason": "Need doctrine."},
        caller_pii_tier="PUBLIC",
        source=source,
    )

    assert result["allowed"] is True
    facts = result["fetch"]()
    assert source == before
    assert result["writes_performed"] is False
    assert all("action" not in fact and "write" not in fact for fact in facts)
