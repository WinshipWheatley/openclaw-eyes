"""Task 163 — exact-total asks stay honest about incomplete money truth."""

from __future__ import annotations

from typing import Any

import pytest

from money_truth import classify_money_question, render_money_answer


D6_SENTINEL = "how much is outstanding in total right now, exact number?"


def _row(
    client: str,
    month: str,
    *,
    open_minor_units: Any,
    currency: str | None = "USD",
    amount_known: bool = True,
    status: str = "open",
    settled: bool = False,
) -> dict[str, Any]:
    return {
        "client_ref": client.lower().replace(" ", "_"),
        "client_display_name": client,
        "month": month,
        "currency_iso": currency,
        "amount_known": amount_known,
        "open_minor_units": open_minor_units,
        "payment_status": status,
        "settled_past_no_compound": settled,
        "needs_reconcile": status == "needs_reconcile",
        "structured_fact": True,
    }


def _payload(*rows: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": "2026-07-11T12:00:00+00:00",
        "read_model_id": "receivables_month_bounded",
        "rows": list(rows),
    }


def test_d6_verbatim_reports_known_subtotal_and_unknown_count_without_false_exact_total() -> None:
    payload = _payload(
        _row(
            "Capital Hilton",
            "2026-06",
            open_minor_units=None,
            amount_known=False,
            status="open_amount_unknown",
        ),
        _row(
            "Live Arts MD",
            "2026-06",
            open_minor_units=109_500,
            status="needs_reconcile",
        ),
        _row(
            "St. Anne's",
            "2026-05",
            open_minor_units=0,
            status="settled",
            settled=True,
        ),
        _row(
            "St. Anne's",
            "2026-07",
            open_minor_units=None,
            amount_known=False,
            status="expected_uninvoiced",
        ),
    )

    answer = render_money_answer(payload=payload, question=D6_SENTINEL)

    assert classify_money_question(D6_SENTINEL) == "money_read"
    assert "Confirmed outstanding subtotal: $1,095." in answer
    assert "2 relevant items are unquantified" in answer
    assert "no single exact total" in answer.lower()
    assert "Exact confirmed outstanding total:" not in answer
    assert "settled" not in answer.lower()


def test_d6_flows_through_typed_contract_without_a_model_or_detail_fallback(
    tmp_path, monkeypatch
) -> None:
    import json

    import money_truth
    import typed_contract_decision as contract

    payload = _payload(
        _row("Live Arts MD", "2026-06", open_minor_units=109_500),
        _row(
            "Capital Hilton",
            "2026-06",
            open_minor_units=None,
            amount_known=False,
            status="open_amount_unknown",
        ),
    )
    read_model = tmp_path / "receivables_month_bounded.json"
    read_model.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", read_model, raising=True)

    decision = contract.decide_contract(
        D6_SENTINEL,
        context=contract.ContractContext(agent="maestro", surface="operator_maestro_chat"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *args, **kwargs: pytest.fail("semantic vote ran"),
    )

    assert decision.label is contract.ContractLabel.MONEY_READ
    assert decision.action is contract.DecisionAction.DIRECT_ANSWER
    assert decision.receipt.model_called is False
    assert "Confirmed outstanding subtotal: $1,095." in str(decision.reply)
    assert "1 relevant item is unquantified" in str(decision.reply)
    assert "no single exact total" in str(decision.reply).lower()


@pytest.mark.parametrize(
    "question",
    (
        "give me one number for everything unpaid",
        "what do all open invoices add up to?",
        "sum up what everyone still owes me",
        "what is the combined outstanding amount?",
        "exactly how much is still outstanding?",
        "what's my exact outstanding balance?",
    ),
)
def test_total_request_paraphrases_use_the_honest_total_renderer(question: str) -> None:
    answer = render_money_answer(
        payload=_payload(_row("Live Arts MD", "2026-06", open_minor_units=109_500)),
        question=question,
    )

    assert "Exact confirmed outstanding total: $1,095." in answer
    assert "0 relevant items are unquantified." in answer


def test_single_currency_sums_quantified_open_rows_and_excludes_settled_even_if_inconsistent() -> None:
    payload = _payload(
        _row("Client A", "2026-06", open_minor_units=50_000),
        _row("Client B", "2026-07", open_minor_units=25_000, status="needs_reconcile"),
        # A settled marker outranks this adversarial non-zero open value.
        _row(
            "Paid Client",
            "2026-05",
            open_minor_units=99_999,
            status="settled",
            settled=True,
        ),
    )

    answer = render_money_answer(
        payload=payload,
        question="what's the exact total outstanding across every invoice?",
    )

    assert "Exact confirmed outstanding total: $750." in answer
    assert "0 relevant items are unquantified." in answer
    assert "$999.99" not in answer
    assert "Paid Client" not in answer


def test_all_settled_scope_never_resurfaces_paid_amount_or_invents_a_currency_total() -> None:
    payload = _payload(
        _row(
            "Paid Client",
            "2026-05",
            open_minor_units=62_500,
            status="settled",
            settled=True,
        )
    )

    answer = render_money_answer(
        payload=payload,
        question="what was the exact outstanding total in May 2026?",
    )

    assert "No outstanding items remain" in answer
    assert "settled rows are excluded" in answer
    assert "$625" not in answer
    assert "Exact confirmed outstanding total:" not in answer


def test_empty_total_scope_is_a_data_gap_never_a_zero_balance() -> None:
    answer = render_money_answer(
        payload=_payload(),
        question="give me the exact outstanding total right now",
    )

    assert "not tracked yet" in answer
    assert "not a zero balance" in answer
    assert "No single exact total is claimed" in answer
    assert "Exact confirmed outstanding total: $0" not in answer


def test_multiple_currencies_are_grouped_and_never_collapsed_to_one_number() -> None:
    payload = _payload(
        _row("US Client", "2026-07", open_minor_units=50_000, currency="usd"),
        _row("EU Client", "2026-07", open_minor_units=20_000, currency="EUR"),
    )

    answer = render_money_answer(
        payload=payload,
        question="how much is outstanding altogether?",
    )

    assert "Confirmed outstanding subtotals by currency:" in answer
    assert "$500" in answer
    assert "EUR 200" in answer
    assert "0 relevant items are unquantified." in answer
    assert "multiple currencies" in answer.lower()
    assert "no single exact total" in answer.lower()
    assert "Exact confirmed outstanding total:" not in answer


def test_explicit_month_and_year_scope_total_before_arithmetic() -> None:
    payload = _payload(
        _row("Current Client", "2026-06", open_minor_units=40_000),
        _row("Other Month", "2026-07", open_minor_units=90_000),
        _row("Other Year", "2025-06", open_minor_units=None, amount_known=False),
    )

    answer = render_money_answer(
        payload=payload,
        question="what was the exact outstanding total in June 2026?",
    )

    assert "Exact confirmed outstanding total: $400." in answer
    assert "0 relevant items are unquantified." in answer
    assert "$900" not in answer
    assert "unquantified" in answer


def test_unquantified_row_inside_temporal_scope_blocks_exact_claim() -> None:
    payload = _payload(
        _row("Known", "2025-06", open_minor_units=25_000),
        _row("Unknown", "2025-06", open_minor_units=None, amount_known=False),
        _row("Outside Scope", "2026-06", open_minor_units=None, amount_known=False),
    )

    answer = render_money_answer(
        payload=payload,
        question="give me the total outstanding during June 2025",
    )

    assert "Confirmed outstanding subtotal: $250." in answer
    assert "1 relevant item is unquantified" in answer
    assert "no single exact total" in answer.lower()
    assert "2 relevant items" not in answer


def test_client_scope_applies_before_totaling() -> None:
    payload = _payload(
        _row("Live Arts MD", "2026-06", open_minor_units=109_500),
        _row("Capital Hilton", "2026-06", open_minor_units=None, amount_known=False),
    )

    answer = render_money_answer(
        payload=payload,
        question="what is the exact total Live Arts still owes me?",
    )

    assert "Exact confirmed outstanding total: $1,095." in answer
    assert "0 relevant items are unquantified." in answer
    assert "Capital Hilton" not in answer


def test_malformed_amounts_and_missing_currency_fail_closed_as_unquantified() -> None:
    payload = _payload(
        _row("Valid", "2026-07", open_minor_units=20_000),
        _row("String", "2026-07", open_minor_units="10000"),
        _row("Boolean", "2026-07", open_minor_units=True),
        _row("Float", "2026-07", open_minor_units=12.5),
        _row("Negative", "2026-07", open_minor_units=-5_000),
        _row("No Currency", "2026-07", open_minor_units=30_000, currency=None),
    )

    answer = render_money_answer(
        payload=payload,
        question="exact number: how much is outstanding in total?",
    )

    assert "Confirmed outstanding subtotal: $200." in answer
    assert "5 relevant items are unquantified" in answer
    assert "no single exact total" in answer.lower()
    assert "-$50" not in answer


def test_normal_money_read_keeps_existing_detailed_renderer() -> None:
    payload = _payload(_row("Live Arts MD", "2026-06", open_minor_units=109_500))

    answer = render_money_answer(
        payload=payload,
        question="who owes me money right now?",
    )

    assert "Live Arts MD" in answer
    assert "$1,095" in answer
    assert "Exact confirmed outstanding total:" not in answer
    assert "unquantified" not in answer


@pytest.mark.parametrize(
    "question",
    (
        "the album is a total mess but the mix is outstanding",
        "tell me why the total mix sounds outstanding",
        "is the total invoice copy outstanding?",
        "tell me about outstanding client work",
        "Can you message me the receivables balance?",
    ),
)
def test_totalish_non_money_phrases_do_not_switch_renderers(question: str) -> None:
    payload = _payload(_row("Live Arts MD", "2026-06", open_minor_units=109_500))

    answer = render_money_answer(payload=payload, question=question)

    assert "Exact confirmed outstanding total:" not in answer
    assert "unquantified" not in answer
