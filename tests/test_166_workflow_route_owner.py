from __future__ import annotations

import pytest

import workflow_package_queue as queue


@pytest.mark.parametrize(
    "text",
    (
        "get the Live Arts PA invoice moving to whoever owns it",
        "someone needs to handle the Live Arts rental bill — make it happen",
        "the Live Arts PA rental invoice needs to go out — get it to the right agent",
        "can you route the Live Arts PA bill to whoever should own it?",
        "Can you please hand the Live Arts PA rental invoice to Cassandra so she can get it out the door?",
        "Please stage a dry-run handoff of Live Arts' rental bill to the agent who handles invoices.",
    ),
)
def test_canonical_live_arts_route_owner_covers_binding_and_legacy_families(text: str) -> None:
    decision = queue.classify_workflow_route(text)

    assert decision.workflow_ref == "live_arts_md_invoice_workflow"
    assert decision.client_ref == "live_arts_md"
    assert decision.target_agent == "cassandra"
    assert decision.reason == "bounded_live_arts_invoice_handoff"


@pytest.mark.parametrize(
    "text",
    (
        "should I route the Live Arts invoice?",
        "could I hand the Live Arts bill to Cassandra?",
        "would I be better off routing the Live Arts invoice?",
        "is it safe to route the Live Arts invoice?",
        "do you think I should send the Live Arts invoice?",
        "review the finalized Live Arts invoice before it goes out",
        "what is the Live Arts invoice status?",
        "where does the Live Arts invoice stand?",
        "route this diagnostic package",
        "route the St Anne's invoice to the right agent",
        "Cassandra sent me the Live Arts invoice yesterday",
        "did you route the Live Arts invoice?",
        "What is Live Arts' invoice balance?",
    ),
)
def test_route_owner_rejects_advice_review_status_other_workflows_and_history(text: str) -> None:
    decision = queue.classify_workflow_route(text)

    assert decision == queue.WorkflowRouteDecision(None, "none")


@pytest.mark.parametrize(
    "text",
    (
        "who is the right agent for the Live Arts invoice?",
        "which agent handles the Live Arts invoice?",
        "does the Live Arts invoice need to go out?",
        "can you tell me who should own the Live Arts invoice?",
        "can I route the Live Arts invoice?",
        "what stage is the Live Arts invoice at?",
        "get the Live Arts invoice ready for me to eyeball and route it",
        "show me the route for the Live Arts invoice",
        "tell me how the Live Arts invoice handoff works",
        "can you tell me whether to route the Live Arts invoice?",
        "don't route the Live Arts invoice",
        "I do not want you to route the Live Arts invoice",
        "where should I route the Live Arts invoice?",
        "why did you route the Live Arts invoice?",
        "don't get the Live Arts invoice to the right agent",
        "do not hand the Live Arts invoice to Cassandra",
        "do not send the Live Arts invoice to the right agent",
        "never get the Live Arts invoice to the right agent",
        "give me the route for the Live Arts invoice",
        "read back the route for the Live Arts invoice",
        "list the route for the Live Arts invoice",
        "what route was used for the Live Arts invoice?",
    ),
)
def test_route_owner_rejects_authority_questions_and_finalized_review_collisions(
    text: str,
) -> None:
    import typed_contract_decision as typed

    decision = queue.classify_workflow_route(text)
    typed_decision = typed.decide_contract(
        text,
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
        ),
        handoff_stager=lambda *_args, **_kwargs: pytest.fail(
            "route read/advice staged a package"
        ),
        semantic_vote_enabled=False,
    )

    assert decision == queue.WorkflowRouteDecision(None, "none")
    assert queue.classify_intent(text).get("workflow_ref") != (
        "live_arts_md_invoice_workflow"
    )
    assert typed_decision.action is not typed.DecisionAction.STAGE_HANDOFF


@pytest.mark.parametrize(
    "text",
    (
        "get the Live Arts PA invoice moving to whoever owns it",
        "someone needs to handle the Live Arts rental bill — make it happen",
        "the Live Arts PA rental invoice needs to go out — get it to the right agent",
        "can you route the Live Arts PA bill to whoever should own it?",
    ),
)
def test_general_workflow_classifier_consumes_public_route_owner(text: str) -> None:
    owned = queue.classify_workflow_route(text)
    classified = queue.classify_intent(text)

    assert classified["workflow_ref"] == owned.workflow_ref
    assert classified["client_ref"] == owned.client_ref
    assert classified["intent_reason"] == "Detected a bounded Live Arts invoice handoff instruction."


def test_general_classifier_has_no_private_live_arts_route_twin() -> None:
    assert not hasattr(queue, "_live_arts_invoice_handoff_semantics")


@pytest.mark.parametrize(
    "text",
    (
        "draft a nudge for whoever owes the biggest outstanding invoice",
        "prepare a follow-up for the largest outstanding receivable",
        "stage a reminder for whoever owes us money",
    ),
)
def test_canonical_owner_preserves_receivables_nudge_handoff(text: str) -> None:
    decision = queue.classify_workflow_route(text)

    assert decision.workflow_ref == "cassandra_receivables_nudge_handoff"
    assert decision.client_ref is None
    assert decision.target_agent == "cassandra"
    assert decision.reason == "bounded_receivables_nudge_handoff"
    assert queue.classify_intent(text)["workflow_ref"] == decision.workflow_ref


def test_general_classifier_has_no_private_receivables_route_twin() -> None:
    assert not hasattr(queue, "_receivables_nudge_handoff_semantics")


@pytest.mark.parametrize(
    "text",
    (
        "should I draft a nudge for whoever owes the biggest outstanding invoice?",
        "did you draft a nudge for whoever owes the biggest outstanding invoice?",
    ),
)
def test_receivables_nudge_owner_rejects_advice_and_completed_questions(text: str) -> None:
    assert queue.classify_workflow_route(text).workflow_ref is None
