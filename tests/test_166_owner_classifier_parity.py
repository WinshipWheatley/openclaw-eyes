from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


STATUS_ROWS = (
    "everything running smooth on your end?",
    "gimme the lay of the land real quick",
    "hows everything looking today?",
    "we in good shape or should i be worried?",
    "Guardian, hows your side of the house looking?",
    "hey hermes, hows the system looking from your seat?",
    "hows the ship holding up chief?",
    "all quiet on the gates tonight?",
)

ROUTE_ROWS = (
    "get the Live Arts PA invoice moving to whoever owns it",
    "someone needs to handle the Live Arts rental bill — make it happen",
    "the Live Arts PA rental invoice needs to go out — get it to the right agent",
    "can you route the Live Arts PA bill to whoever should own it?",
)

FINALIZED_REVIEW_ROWS = (
    "prep the St Anne's July invoice so I can look it over",
    "would you mind getting the July St Anne's invoice set up for my review?",
    "can you line up the st annes july invoice for me to glance at?",
    "have that july st annes bill teed up for my once-over",
)


@pytest.mark.parametrize("text", FINALIZED_REVIEW_ROWS)
def test_cockpit_owner_and_typed_consumer_agree_on_finalized_review(text: str) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        DecisionAction,
        decide_contract,
    )

    session = {"status": "active", "active_workflow": "invoice", "step": 1}
    owned = classify_finalized_invoice_review(text)
    typed = decide_contract(
        text,
        context=ContractContext(
            agent="cassandra",
            surface="telegram",
            active_session=True,
            session_kind="invoice",
            session_snapshot=session,
        ),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )

    assert owned.matched is True
    assert owned.client_ref == "st_annes"
    assert owned.requested_period is not None
    assert ContractLabel.FINALIZED_INVOICE_REVIEW in typed.matches
    assert typed.action is DecisionAction.PASS_THROUGH
    assert typed.receipt.reason == "finalized_artifact_adapter_owns_route"
    assert session == {"status": "active", "active_workflow": "invoice", "step": 1}


@pytest.mark.parametrize(
    "text",
    (
        "send the St Anne's July invoice now",
        "review my rates and clients",
        "what did St Anne's owe on the July invoice?",
        "set up the stage for my review",
    ),
)
def test_finalized_review_owner_rejects_actions_other_domains_and_missing_invoice(
    text: str,
) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    assert classify_finalized_invoice_review(text).matched is False


def test_finalized_review_owner_resolves_one_registered_pronoun_antecedent() -> None:
    """Task 166 compound seam: a bounded pronoun may inherit one registry owner."""
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(
        "did St Anne's pay us, and if not can you get their invoice ready "
        "for my review while you're at it?"
    )

    assert decision.matched is True
    assert decision.client_ref == "st_annes"
    assert decision.client_model is not None
    assert decision.client_model["matched_client_text"] != "their"


@pytest.mark.parametrize(
    "text",
    (
        "did St Anne's pay us and if not can you get their invoice ready for my review?",
        "does St Anne's owe us, and if not could you get their invoice ready for my review?",
        "did St Anne's pay us? If not, can you get their invoice ready for my review?",
    ),
)
def test_finalized_review_owner_accepts_closed_pronoun_paraphrases(text: str) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is True
    assert decision.client_ref == "st_annes"


@pytest.mark.parametrize(
    ("text", "client_ref"),
    (
        (
            "did the Capital Hilton pay us, and if not get their invoice ready for review",
            "capital_hilton",
        ),
        (
            "did the Hilton pay us, and if not get their invoice ready for review",
            "capital_hilton",
        ),
        (
            "did the St Anne's check clear, and if not get their invoice ready for review",
            "st_annes",
        ),
    ),
)
def test_finalized_review_owner_accepts_one_leading_antecedent_determiner(
    text: str,
    client_ref: str,
) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is True
    assert decision.client_ref == client_ref


@pytest.mark.parametrize(
    "text",
    (
        "can you get their invoice ready for my review?",
        "compare St Anne's and Live Arts, then get their invoice ready for my review",
        "compare St Anne's and Acme, then get their invoice ready for my review",
        "Earlier we discussed St Anne's. Did Acme pay? Then get their invoice ready for my review",
        "did the Hiltonian pay us, and if not can you get its invoice ready for my review?",
        "did St Anne's pay Capital Hilton, and if not get their invoice ready for my review",
        "did St Anne's pay Acme, and if not get their invoice ready for my review",
        "did St Anne's pay us for Capital Hilton, and if not get their invoice ready for my review",
        "compare St Anne's payment status with Acme for Live Arts, then get their invoice ready for my review",
        "compare St Anne's payment status for Live Arts, then get their invoice ready for my review",
        "get their overdue invoice ready for my review",
        "get their corrected invoice ready for my review",
        "get her draft invoice ready for my review",
        "did Acme pay us, and if not get their invoice ready for my review",
        "did St Anne's pay us, and if not get their invoice with a Capital Hilton comparison ready for my review",
        "did St Anne's pay us, and if not get their invoice, not Capital Hilton's, ready for my review",
        "did St Anne's pay us, and if not get their invoice using the Capital Hilton template ready for my review",
        "did St Anne's pay us, and if not get their invoice alongside Capital Hilton ready for my review",
        "did St Anne's pay us, and if not get their invoice excluding Capital Hilton ready for my review",
        "does St Anne's owe us, and if not get their Live Arts invoice ready for my review",
        "does St Anne's owe us, and if not get their Capital Hilton invoice ready for my review",
    ),
)
def test_finalized_review_owner_rejects_unbound_or_ambiguous_pronouns(text: str) -> None:
    """Task 166 authority boundary: never manufacture a client named `their`."""
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is False
    assert decision.client_ref is None


@pytest.mark.parametrize(
    "text",
    (
        "get the St Anne's and Live Arts invoice ready for my review",
        "get the St Anne's invoice for Live Arts ready for my review",
        "get the St Anne's invoice for Acme ready for my review",
        "get Acme and St Anne's invoice ready for my review",
        "get the invoice, not Capital Hilton's, ready for my review",
        "get the invoice using the Capital Hilton template ready for my review",
    ),
)
def test_finalized_review_owner_rejects_multi_owner_direct_clauses(text: str) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is False
    assert decision.client_ref is None


@pytest.mark.parametrize(
    ("text", "client_ref", "portal_implied"),
    (
        ("get me the St Anne's invoice ready for review", "st_annes", False),
        ("get Hilton's invoice ready for review", "capital_hilton", False),
        ("prepare Capital Hilton's invoice for review", "capital_hilton", False),
        ("prepare Live Arts MD's invoice for review", "live_arts_md", False),
        ("prepare Reynolds Tavern's invoice for review", "reynolds_tavern", False),
        ("get the Capital Hilton Coupa invoice ready for review", "capital_hilton", True),
        ("get the Capital Hilton PO invoice ready for review", "capital_hilton", True),
        ("get the Capital Hilton P.O. invoice ready for review", "capital_hilton", True),
        (
            "get the Capital Hilton purchase order invoice ready for review",
            "capital_hilton",
            True,
        ),
        ("get the Coupa invoice for Capital Hilton ready for review", "capital_hilton", True),
        ("get the portal invoice for Capital Hilton ready for review", "capital_hilton", True),
        ("get a copy of the St Anne's invoice ready for review", "st_annes", False),
        ("get the latest St Anne's invoice ready for my review", "st_annes", False),
        ("get the existing St Anne's invoice ready for my review", "st_annes", False),
        ("get the issued St Anne's invoice ready for my review", "st_annes", False),
        ("get St Anne's latest invoice ready for my review", "st_annes", False),
        (
            "surface the existing finalized St Anne's invoice",
            "st_annes",
            False,
        ),
        (
            "get Capital Hilton's invoice, not Coupa, ready for my review",
            "capital_hilton",
            False,
        ),
        (
            "get the Capital Hilton invoice excluding Coupa ready for my review",
            "capital_hilton",
            False,
        ),
        (
            "get the St Anne's invoice, not Coupa, ready for my review",
            "st_annes",
            False,
        ),
        (
            "get St Anne's invoice without the portal ready for my review",
            "st_annes",
            False,
        ),
        (
            "get Capital Hilton's invoice with Coupa not required ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with PO excluded ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with the portal disabled ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with Coupa avoided ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's Coupa-free invoice ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice instead of Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice using Excel rather than Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and skip Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice, never Coupa, ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice off Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with Coupa is not the route ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with Coupa not allowed ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with a note about Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice compared with Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice using Coupa ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice via Coupa ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice but don't use Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice instead of using Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice using Excel rather than using Coupa ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with the Coupa route disabled ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with the Coupa path not required ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with the Coupa invoice excluded ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and compare against the Coupa invoice ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with a comparison to the Coupa invoice ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but cannot use Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but can't route through Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but won't upload to Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but shouldn't submit to Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but refuse to use Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's PO invoice excluded from the path ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and submit the invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice and upload it to Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice but didn't use Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but couldn't route through Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice but wouldn't upload to Coupa, and keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and isn't using Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and aren't using Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and submit invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice and upload our invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice with a question about how to submit invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with a note asking whether to upload my invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice while we decide whether to route our bill through Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and ask can we use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and ask should we submit invoice to Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and maybe use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and perhaps upload it to Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice while considering using Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice with a possible Coupa path ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and ask is Coupa required, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and use Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice and can use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and could use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and may use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and would use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and should use Coupa, then keep it ready for review",
            "capital_hilton",
            False,
        ),
        (
            "get Capital Hilton's invoice and will use Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
        (
            "get Capital Hilton's invoice and must use Coupa, then keep it ready for review",
            "capital_hilton",
            True,
        ),
    ),
)
def test_finalized_review_owner_accepts_registered_possessive_alias(
    text: str,
    client_ref: str,
    portal_implied: bool,
) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is True
    assert decision.client_ref == client_ref
    assert decision.client_model is not None
    assert decision.client_model["coupa_or_po_implied"] is portal_implied


def test_finalized_review_owner_uses_the_absolute_bound_clause_start() -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(
        "prepare a payment status for St Anne's, then get their invoice ready for my review"
    )

    assert decision.matched is True
    assert decision.client_ref == "st_annes"


def test_finalized_review_owner_preserves_generator_registry_parity() -> None:
    from invoice_cockpit_client_registry import DEFAULT_CLIENT_MODELS
    from invoice_cockpit_intent import classify_finalized_invoice_review

    text = (
        "did St Anne's pay us, and if not can you get their invoice ready "
        "for my review while you're at it?"
    )
    decision = classify_finalized_invoice_review(
        text,
        client_models=(model for model in DEFAULT_CLIENT_MODELS),
    )

    assert decision.matched is True
    assert decision.client_ref == "st_annes"


@pytest.mark.parametrize(
    "text",
    (
        "is the Hilton payment coming in?",
        "any sign of the Hilton payment arriving?",
        "any sign of the Hilton payment landing yet?",
        "is the Capital Hilton check clearing?",
        "has the Hilton deposit been posting?",
        "are the Hilton funds showing up?",
        "did the bank post the Hilton payment?",
        "did Capital Hilton post the payment?",
        "has Stripe posted the Hilton payment?",
        "was the Hilton payment posted by the bank?",
        "was the Hilton payment cleared by Stripe?",
    ),
)
def test_money_owner_alone_widens_payment_arrival_morphology(text: str) -> None:
    from money_truth import classify_money_question
    from typed_contract_decision import ContractContext, ContractLabel, decide_contract

    assert classify_money_question(text) == "payment_arrival_verify"
    typed = decide_contract(
        text,
        context=ContractContext(agent="cassandra", surface="telegram"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )
    assert typed.label is ContractLabel.PAYMENT_ARRIVAL


@pytest.mark.parametrize(
    "text",
    (
        "create an invoice for Hilton",
        "send the Hilton invoice",
        "how is the album coming?",
        "is the system health check clearing?",
        "is the deployment check posting?",
    ),
)
def test_payment_owner_does_not_overmatch_invoice_actions_or_nonfinancial_checks(
    text: str,
) -> None:
    from money_truth import classify_money_question

    assert classify_money_question(text) != "payment_arrival_verify"


@pytest.mark.parametrize(
    "text",
    (
        "can you post the Hilton payment?",
        "could you mark the Hilton payment as cleared?",
        "did you post the Hilton payment?",
        "did you clear the Hilton check?",
        "did you already post the Hilton payment?",
        "have you already cleared the Hilton check?",
        "was the Hilton check posted by you?",
        "did Cassandra post the Hilton payment?",
        "did you manually post the Hilton payment?",
        "did you recently clear the Hilton check?",
        "did you end up posting the Hilton payment?",
        "did Chief post the Hilton payment?",
        "did the accountant post the Hilton payment?",
        "did the bookkeeper clear the Hilton check?",
        "was the Hilton payment posted by payroll?",
        "was the Hilton check posted by the bookkeeper?",
        "was the Hilton payment cleared by accounting?",
    ),
)
def test_payment_owner_rejects_mutation_and_operator_action_history(text: str) -> None:
    from money_truth import classify_money_question
    from typed_contract_decision import ContractContext, ContractLabel, decide_contract

    assert classify_money_question(text) != "payment_arrival_verify"
    decision = decide_contract(
        text,
        context=ContractContext(agent="cassandra", surface="cassandra_telegram"),
        semantic_vote_enabled=False,
    )
    assert decision.label is not ContractLabel.PAYMENT_ARRIVAL


@pytest.mark.parametrize(
    "text",
    (
        "update the invoice status to paid",
        "set the invoice state to sent",
        "the invoice status should be marked paid",
    ),
)
def test_money_owner_does_not_turn_invoice_mutations_into_reads(text: str) -> None:
    from money_truth import classify_money_question

    assert classify_money_question(text) is None


def test_typed_payment_consumer_has_no_status_invoice_semantic_fallback(
    monkeypatch,
) -> None:
    import money_truth
    import typed_contract_decision as typed

    monkeypatch.setattr(money_truth, "classify_money_question", lambda _text: None)

    assert typed.classify_payment_arrival_request("what is the invoice status?") is False


@pytest.mark.parametrize("text", ROUTE_ROWS)
def test_workflow_owner_typed_and_maestro_consumers_agree_on_route(text: str) -> None:
    import maestro_cassandra_responder as maestro
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        DecisionAction,
        decide_contract,
    )
    from workflow_package_queue import classify_workflow_route

    owned = classify_workflow_route(text)
    typed = decide_contract(
        text,
        context=ContractContext(agent="maestro", surface="operator_maestro_chat"),
        handoff_stager=lambda _text, _ctx: type(
            "Handoff",
            (),
            {
                "reply": "Staged for Cassandra. Say 'show receipt' for proof.",
                "receipt_pointer": "fleet:route",
                "package_id": "package:route",
            },
        )(),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )
    maestro_intent = maestro.classify_frontdoor_intent(text)

    assert owned.workflow_ref == "live_arts_md_invoice_workflow"
    assert ContractLabel.ROUTE_INSTRUCTION in typed.matches
    assert typed.action is DecisionAction.STAGE_HANDOFF
    assert maestro_intent[0] == "workflow_or_business_action"
    assert maestro_intent[1] is False


@pytest.mark.parametrize(
    "text",
    (
        "should I route the Live Arts invoice?",
        "would you mind getting the July St Anne's invoice set up for my review?",
        "what is the Live Arts invoice status?",
        "route this diagnostic package",
    ),
)
def test_route_owner_rejects_advice_review_status_and_other_workflows(text: str) -> None:
    from workflow_package_queue import classify_workflow_route

    assert classify_workflow_route(text).workflow_ref is None


def test_typed_route_consumer_has_no_parallel_handoff_regex(monkeypatch) -> None:
    import typed_contract_decision as typed
    import workflow_package_queue as queue

    monkeypatch.setattr(queue, "classify_workflow_route", lambda _text: queue.WorkflowRouteDecision(None, "none"))

    assert typed.classify_route_instruction(
        "the Live Arts invoice needs to go out — get it to the right agent"
    ) is False


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("show my unread emails", "unread_list"),
        ("did I get an email from Dane this week?", "metadata_read"),
        ("did we get sent anything from Dane this week?", "metadata_read"),
        ("send an email to Dane about Friday", "draft_send"),
        ("draft a message to Dane", "draft_send"),
        ("reply to Dane's email", "reply"),
        ("check email replies from Dad", "reply"),
        ("send the intro emails", "outreach"),
        ("who owes me money?", "none"),
        ("is the system running smooth?", "none"),
    ),
)
def test_email_owner_enum_keeps_read_send_reply_and_outreach_distinct(
    text: str,
    expected: str,
) -> None:
    from email_intent import classify_email_intent

    assert classify_email_intent(text).value == expected


def test_email_consumers_delegate_to_one_owner_without_collapsing_authority() -> None:
    import cassandra_brain
    import maestro_cassandra_responder as maestro
    from email_intent import EmailIntent

    metadata = cassandra_brain.decide_gmail_intent(
        "did we get sent anything from Dane this week?"
    )
    send = cassandra_brain.decide_gmail_intent("send an email to Dane about Friday")

    assert metadata.allowed is True
    assert metadata.trigger == EmailIntent.METADATA_READ.value
    assert send.allowed is True
    assert send.trigger == EmailIntent.DRAFT_SEND.value
    assert cassandra_brain._detect_send_email_intent(
        "did we get sent anything from Dane this week?"
    ) is False
    assert cassandra_brain._detect_send_email_intent(
        "send an email to Dane about Friday"
    ) is True
    assert maestro.classify_frontdoor_intent(
        "did we get sent anything from Dane this week?"
    )[0] == "inbox_gmail_metadata"
    assert maestro.classify_frontdoor_intent(
        "send an email to Dane about Friday"
    )[0] == "send_reply_email_action"


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("did we get sent anything from Dane this week?", "metadata_read"),
        ("show my unread emails", "unread_list"),
        ("send an email to Dane about Friday", "draft_send"),
        ("reply to Dane's email", "reply"),
        ("send the intro emails", "outreach"),
    ),
)
def test_typed_email_consumer_delegates_before_session_or_vote(
    text: str,
    expected: str,
) -> None:
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        DecisionAction,
        decide_contract,
    )

    session = {"status": "active", "active_workflow": "billing", "step": 2}
    before = dict(session)
    decision = decide_contract(
        text,
        context=ContractContext(
            agent="cassandra",
            surface="cassandra_telegram",
            active_session=True,
            session_kind="billing",
            session_snapshot=session,
        ),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )

    assert decision.label is ContractLabel.EMAIL
    assert decision.action is DecisionAction.PASS_THROUGH
    assert decision.receipt.reason == f"email_owner:{expected}"
    assert decision.receipt.model_called is False
    assert session == before


def test_business_ops_has_no_rival_broad_payment_verify_fallback() -> None:
    from business_ops_intent import classify_business_ops_intent

    assert classify_business_ops_intent("prepare the July invoice").intent_name != "payment_verify"


@pytest.mark.parametrize("text", STATUS_ROWS)
def test_typed_status_owner_covers_binding_paraphrases_without_vote(text: str) -> None:
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        DecisionAction,
        classify_status_request,
        decide_contract,
    )

    assert classify_status_request(text) is True
    decision = decide_contract(
        text,
        context=ContractContext(agent="maestro", surface="telegram"),
        status_renderer=lambda: "Deterministic status.",
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )
    assert decision.label is ContractLabel.STATUS
    assert decision.action is DecisionAction.DIRECT_ANSWER
    assert decision.reply == "Deterministic status."
    assert decision.receipt.model_called is False


@pytest.mark.parametrize(
    "text",
    (
        "what is the Live Arts invoice status?",
        "is the Hilton payment in good shape?",
        "the house is looking good today",
        "set the system state to ready",
    ),
)
def test_status_owner_rejects_business_objects_declarations_and_mutations(text: str) -> None:
    from typed_contract_decision import classify_status_request

    assert classify_status_request(text) is False


@pytest.mark.parametrize(
    "text",
    (
        "how is the audio system wired?",
        "what is your state machine design?",
    ),
)
def test_status_owner_rejects_technical_system_design_questions(text: str) -> None:
    from typed_contract_decision import classify_status_request

    assert classify_status_request(text) is False


@pytest.mark.parametrize(
    "text",
    (
        "walk me through what happens when Cassandra wants to send an invoice",
        "if clara fires off an invoice right now, what stops it?",
        "if cassandra fires off an invoice right now what stops it?",
    ),
)
def test_guardian_narration_owner_covers_live_paraphrases(text: str) -> None:
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        classify_guardian_gate_narration,
        decide_contract,
    )

    assert classify_guardian_gate_narration(text) is True
    decision = decide_contract(
        text,
        context=ContractContext(agent="guardian", surface="guardian_listener"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )
    assert decision.label is ContractLabel.GUARDIAN_GATE_NARRATION
    assert "two separate gates" in str(decision.reply)


def test_guardian_narration_owner_covers_frozen_path_wording() -> None:
    from typed_contract_decision import classify_guardian_gate_narration

    assert classify_guardian_gate_narration(
        "whats the actual path an invoice takes from clara to sent?"
    ) is True


@pytest.mark.parametrize(
    "text",
    (
        "Cassandra, send the invoice after Guardian approval",
        "Cassandra can send the invoice after approval",
    ),
)
def test_guardian_narration_owner_rejects_actions_and_declarations(text: str) -> None:
    from typed_contract_decision import classify_guardian_gate_narration

    assert classify_guardian_gate_narration(text) is False


def test_guardian_no_pending_adapter_consumes_shared_status_owner() -> None:
    from chief_nonapproval_responder import guardian_no_pending_reply

    reply = guardian_no_pending_reply("all quiet on the gates tonight?")

    assert reply.startswith("No approval request is currently pending.")
    assert "did not approve, send, or change anything" in reply


@pytest.mark.parametrize(
    "text",
    (
        "whats ur whole deal again lol",
        "wait are you the email one or the money one?",
        "which one of yall handles my mixes?",
        "remind me exactly what falls on your desk",
        "what exactly are you here to do for me?",
        "remind me of your whole deal again",
    ),
)
def test_public_identity_owner_covers_frozen_family_without_vote(text: str) -> None:
    from typed_contract_decision import (
        ContractContext,
        ContractLabel,
        DecisionAction,
        classify_identity_request,
        decide_contract,
    )

    assert classify_identity_request(text) is True
    decision = decide_contract(
        text,
        context=ContractContext(agent="maestro", surface="operator_maestro_chat"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail("semantic vote ran"),
    )
    assert decision.label is ContractLabel.IDENTITY
    assert decision.action is DecisionAction.DIRECT_ANSWER
    assert decision.receipt.model_called is False


def test_ht2_maps_to_hermes_and_returns_deterministic_status(monkeypatch) -> None:
    import agent_contract_renderers
    import openclaw_hermes_gateway_policy as hermes
    import openclaw_request_processor as processor

    text = "hey hermes, hows the system looking from your seat?"
    monkeypatch.setattr(
        agent_contract_renderers,
        "render_hermes_status",
        lambda: "Hermes status is deterministic and current.",
    )

    assert processor._resolved_frontdoor_agent({"operator_message": text}) == "hermes"
    assert hermes.truthful_reply_for_text(text) == "Hermes status is deterministic and current."


def test_ht2_full_frontdoor_preserves_hermes_answer_and_authorship(
    tmp_path,
    monkeypatch,
) -> None:
    import agent_contract_renderers
    import maestro_listener
    import openclaw_request_processor as processor

    text = "hey hermes, hows the system looking from your seat?"
    monkeypatch.setattr(
        agent_contract_renderers,
        "render_hermes_status",
        lambda: "Hermes status is deterministic and current.",
    )
    monkeypatch.setenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", "")
    request = maestro_listener.build_operator_maestro_chat_request(
        text,
        message_id="task-166-ht2",
        chat_id=42,
        created_at="2026-07-11T20:00:00+00:00",
    )
    request_path = (
        tmp_path
        / "mission_control_operator_instruction_request_task_166_ht2.json"
    )
    request_path.write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-11T20:00:00+00:00",
        duplicate_check=False,
    )

    assert response is not None
    assert response.operator_message == "Hermes status is deterministic and current."
    assert response.detail_disclosure["message_provenance"]["actor"] == "hermes"
    assert response.detail_disclosure["message_provenance"]["speaker"] == "Hermes"
    assert response.detail_disclosure["operator_display"]["speaker_ref"] == "hermes"
    assert response.visible_cards[0]["status_label"] == "Hermes"
    assert response.proof_to_response["model_call_performed"] is False

    payload, _status = processor.build_payloads(
        response,
        generated_at="2026-07-11T20:00:00+00:00",
    )
    assert payload["response_author"] == "HERMES"


def test_addressed_target_map_accepts_salutation_without_misrouting_mentions() -> None:
    import openclaw_request_processor as processor

    assert processor._resolved_frontdoor_agent(
        {"operator_message": "hey hermes hows everything looking from your seat?"}
    ) == "hermes"
    assert processor._resolved_frontdoor_agent(
        {"operator_message": "what does Hermes handle in the system?"}
    ) == "maestro"


def test_consumer_modules_no_longer_define_parallel_owner_tables() -> None:
    import cassandra_brain
    import maestro_cassandra_responder as maestro
    import typed_contract_decision as typed

    assert not hasattr(typed, "_FINALIZED_REVIEW_RE")
    assert not hasattr(typed, "_HANDOFF_RE")
    assert not hasattr(maestro, "_DISPATCH_INSTRUCTION_IDIOMS")
    assert not hasattr(cassandra_brain, "_GMAIL_QUERY_WORDS")
    assert not hasattr(cassandra_brain, "_SEND_EMAIL_KEYWORDS")
    assert not hasattr(cassandra_brain, "_OUTREACH_EMAIL_PATTERNS")


@pytest.mark.parametrize(
    "text",
    (
        "any sign of the Hilton payment landing yet?",
        "did we get sent anything from Dane this week?",
        "send an email to Dane about Friday",
        "reply to Dane's email",
        "send the intro emails",
    ),
)
def test_cassandra_listener_sends_payment_and_email_owners_to_brain_before_cockpit(
    text: str,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task-166-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import cassandra_listener as listener
    import typed_contract_decision as typed

    calls: list[str] = []

    def fake_brain(raw: str, _session: dict):
        calls.append(raw)
        return ["owner adapter handled it"]

    monkeypatch.setenv(
        typed.CONTRACT_RECEIPT_DB_ENV,
        str(tmp_path / "typed-contract.sqlite3"),
    )
    monkeypatch.setattr(listener, "cassandra_handle", fake_brain)
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *_args, **_kwargs: pytest.fail("invoice cockpit ran"),
    )

    result = asyncio.run(
        listener._run_cassandra_handle_async(
            text,
            {
                "surface": "cassandra_telegram",
                "source_message_id": "task-166-owner-bypass",
                "invoice_cockpit_session_path": str(tmp_path / "cockpit.json"),
                "workflow_package_sqlite_path": str(tmp_path / "workflow.sqlite3"),
            },
        )
    )

    assert result == ["owner adapter handled it"]
    assert calls == [text]


@pytest.mark.parametrize(
    "text",
    (
        "show my unread emails and hows everything looking?",
        "check my email and get the St Anne's July invoice ready for my review",
        "check my email and route the Live Arts invoice to Cassandra",
    ),
)
def test_cassandra_listener_fails_closed_on_unsupported_owner_compounds(
    text: str,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task-166-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import cassandra_listener as listener
    import typed_contract_decision as typed
    from clarify_session_contract import stamp_clarify_session
    from invoice_cockpit_ops import JsonSessionStore

    cockpit_path = tmp_path / "cockpit.json"
    state = {
        "stage": "awaiting_invoice_approval",
        "client": "St Anne's",
        "client_ref": "st_annes",
        "artifact_reused": True,
        "requested_period": "2026-07",
        "invoice_data": {"invoice_number": "WL-2026-0009"},
        "pdf_path": "/tmp/WL-2026-0009__St_Annes.pdf",
        "attachment_sha256": "finalized-sha256",
    }
    stamp_clarify_session(state, surface="cassandra_telegram")
    store = JsonSessionStore(cockpit_path)
    store.save(state)
    before = cockpit_path.read_bytes()

    monkeypatch.setenv(
        typed.CONTRACT_RECEIPT_DB_ENV,
        str(tmp_path / "typed-contract.sqlite3"),
    )
    monkeypatch.setattr(
        listener,
        "cassandra_handle",
        lambda *_args, **_kwargs: pytest.fail("brain owner silently absorbed compound"),
    )
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *_args, **_kwargs: pytest.fail("cockpit captured compound"),
    )

    result = asyncio.run(
        listener._run_cassandra_handle_async(
            text,
            {
                "surface": "cassandra_telegram",
                "source_message_id": "task-166-owner-compound",
                "invoice_cockpit_session_path": str(cockpit_path),
                "workflow_package_sqlite_path": str(tmp_path / "workflow.sqlite3"),
            },
        )
    )

    assert result == [
        "I caught more than one owner request there. Please ask for each one "
        "in a separate message so I can keep their authority and receipts "
        "separate. I left the open workflow unchanged. Nothing was sent or changed."
    ]
    reply = result[0]
    assert isinstance(reply, listener._ReceiptBoundReply)
    assert reply.descriptor is None
    assert reply.contract_receipt["action"] == typed.DecisionAction.DIRECT_ANSWER.value
    assert (
        reply.contract_receipt["reason"]
        == "unsupported_cross_owner_compound_clarification"
    )
    assert cockpit_path.read_bytes() == before


def test_maestro_fails_closed_on_email_route_compound_with_typed_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    import maestro_cassandra_responder as maestro
    import typed_contract_decision as typed

    monkeypatch.setenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", "")
    sqlite_path = tmp_path / "workflow.sqlite3"
    result = maestro.answer_frontdoor_chat(
        "send an email to Dane and route the Live Arts invoice to Cassandra",
        session={"workflow_package_sqlite_path": str(sqlite_path)},
        source_surface="operator_maestro_chat",
        agent="maestro",
    )

    receipt = result.machine_proof["typed_contract_decision"]
    assert result.plain_summary == typed.UNSUPPORTED_OWNER_COMPOUND_CLARIFICATION
    assert receipt["action"] == typed.DecisionAction.DIRECT_ANSWER.value
    assert receipt["reason"] == "unsupported_cross_owner_compound_clarification"
    assert result.machine_proof["workflow_package_staged"] is False
    assert result.machine_proof["model_call_performed"] is False
    assert sqlite_path.exists() is False


def test_every_route_stager_consumes_the_owner_and_fails_closed_on_no_route() -> None:
    for filename in (
        "maestro_cassandra_responder.py",
        "chief_router.py",
        "cassandra_brain.py",
        "cassandra_listener.py",
    ):
        source = Path(filename).read_text(encoding="utf-8")
        assert "classify_workflow_route" in source
        assert "classify_intent(raw_text)" not in source
        assert "canonical workflow-route owner returned no staged route" in source
