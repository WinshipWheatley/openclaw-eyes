"""The two bypasses the live Telegram battery found, pinned by exact message.

Both were mine. Both passed every test I had written, because every one of those
tests drove a function the live path did not use.

1. Cassandra shipped this, verbatim, with NO banner and no named reason:
     "The language model didn't return a usable routing decision. I left your
      request untouched; please try again in a moment."
   The egress ran, produced a bannered reply, and was then discarded by
   `safe_text = enforced` two lines later. A guard that runs and is thrown away is
   worse than one that never ran: it reads as installed.

2. Maestro answered the acceptance prompt with a bannered bare UNKNOWN and no
   evidence, because the live chat responder is openclaw_request_processor_v0 and
   the provenance wiring had gone into a different consumer.
"""

from __future__ import annotations

import inspect

import pytest

import agent_reply_egress as egress
import agent_telegram_identity as ident
import cassandra_listener
import chief_listener
import grounded_answer_contract as gac
import openclaw_request_processor as orp
import vote_timeout_clarification as votes

#: Verbatim from Telegram, 2026-07-28.
LIVE_CASSANDRA_REPLY = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)
LIVE_MAESTRO_PROMPT = (
    "MAESTRO ACCEPTANCE TEST — Use only grounded packets you can actually retrieve. "
    "What is OpenClaw's current owner-first product hypothesis, what is the smallest "
    "v1, and what is the top blocker before it is useful?"
)
LIVE_MAESTRO_REPLY = "- Owner-first product hypothesis: UNKNOWN — relevant packet facts were unavailable."


def _vote_failure_receipt(status: str = "empty") -> dict:
    return {
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "semantic_vote_status": status,
    }


# ───────────────────────── bypass 1: the egress was run then discarded

def test_the_exact_live_cassandra_reply_is_no_longer_producible() -> None:
    """The verbatim string the operator received must not be the final output."""

    out = votes.enforce_vote_timeout_output(
        "what is the send gate", LIVE_CASSANDRA_REPLY, _vote_failure_receipt(),
        agent="cassandra",
    )
    assert out != LIVE_CASSANDRA_REPLY
    assert gac.is_generic_retry(out) is False
    assert "cassandra" in out


def test_the_named_failure_reaches_the_operator_through_cassandras_funnel(monkeypatch) -> None:
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    named = votes.enforce_vote_timeout_output(
        "what is the send gate", LIVE_CASSANDRA_REPLY, _vote_failure_receipt(),
        agent="cassandra",
    )
    out = cassandra_listener._final_operator_reply(named, source_request="what is the send gate")
    assert "@cassandrastudio_bot" in out, "the banner was stripped again"
    assert "routing failed at" in out


@pytest.mark.parametrize("agent,module,attr,handle", [
    ("cassandra", cassandra_listener, "_final_operator_reply", "@cassandrastudio_bot"),
    ("chief", chief_listener, "_final_operator_text", "@sysrelay_bot"),
])
def test_neither_listener_discards_the_egress_result(agent, module, attr, handle, monkeypatch) -> None:
    """Structural: `safe_text = enforced` must not appear after the egress call."""

    # Parsed, not grepped: a substring scan trips on a comment explaining the bug,
    # which would push the next author to delete the explanation rather than keep
    # the guard. Only a real assignment counts.
    import ast

    tree = ast.parse(inspect.getsource(module))
    offenders = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "safe_text" for t in node.targets)
        and isinstance(node.value, ast.Name) and node.value.id == "enforced"
    ]
    assert not offenders, (
        f"{agent} still overwrites the egress result with the raw clarification "
        f"(line {offenders[0].lineno})"
    )
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    out = getattr(module, attr)("plain answer", source_request="q")
    assert handle in out


def test_the_generic_retry_is_still_recognised_as_generic() -> None:
    """NON-VACUITY: the detector must still fire on the string we removed."""

    assert gac.is_generic_retry(LIVE_CASSANDRA_REPLY) is True


def test_a_named_failure_names_agent_stage_and_cause() -> None:
    out = votes.enforce_vote_timeout_output(
        "q", LIVE_CASSANDRA_REPLY, _vote_failure_receipt(), agent="chief"
    )
    assert "chief" in out and "semantic_vote" in out and "MODEL_FAILURE" in out
    assert "nothing was sent" in out.lower()


def test_a_healthy_vote_is_left_completely_alone() -> None:
    """NON-VACUITY: enforcement must not rewrite good answers."""

    good = "The send gate is the scoped graduation."
    out = votes.enforce_vote_timeout_output(
        "q", good, _vote_failure_receipt("accepted_unresolved"), agent="cassandra"
    )
    assert out == good


# ────────────── bypass 2: the live chat responder carried no provenance

def test_the_live_chat_responder_carries_the_operators_question() -> None:
    payload = orp._chat_grounded_provenance(
        type("R", (), {"operator_message": LIVE_MAESTRO_PROMPT})(),
        {"source_text": LIVE_MAESTRO_PROMPT},
    )
    assert payload["source_text"] == LIVE_MAESTRO_PROMPT


def test_the_live_chat_responder_carries_citations() -> None:
    payload = orp._chat_grounded_provenance(
        type("R", (), {"file_readback_refs": ("PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md",)})(),
        {"source_refs": ["chief_status_rail.json"]},
    )
    assert "chief_status_rail.json" in payload["source_refs"]
    assert "PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md" in payload["source_refs"]


def test_the_live_chat_responder_carries_a_retrieval_failure() -> None:
    payload = orp._chat_grounded_provenance(
        type("R", (), {})(),
        {"retrieval_status": {"status": "TABLES_MISSING", "detail": "canonical_facts absent"}},
    )
    assert payload["retrieval_status"]["status"] == "TABLES_MISSING"


def test_the_live_bare_unknown_becomes_actionable_end_to_end() -> None:
    """THE EXACT LIVE FAILURE, repaired: bare UNKNOWN -> named, cited refusal."""

    payload = orp._chat_grounded_provenance(
        type("R", (), {})(),
        {
            "source_text": LIVE_MAESTRO_PROMPT,
            "source_refs": ["PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md"],
            "retrieval_status": {"status": "TABLES_MISSING", "detail": "canonical_facts absent"},
        },
    )
    reply = egress.finalize_agent_reply("maestro", LIVE_MAESTRO_REPLY, payload=payload)
    assert "PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md" in reply
    assert "TABLES_MISSING" in reply
    assert reply.strip() != LIVE_MAESTRO_REPLY


def test_provenance_is_attached_at_the_single_serialization_funnel() -> None:
    """Wiring the many request_type="CHAT" sites is how one gets missed."""

    source = inspect.getsource(orp)
    assert source.count("_chat_grounded_provenance(") >= 2
    assert '"authority_boundary": AUTHORITY_BOUNDARY,\n        **_chat_grounded_provenance(' in source


def test_provenance_extraction_never_breaks_a_response() -> None:
    """NON-VACUITY the other way: a bad shape must degrade, not raise."""

    for bad in (None, object(), 42):
        assert isinstance(orp._chat_grounded_provenance(bad, {}), dict)


def test_nothing_is_attached_when_there_is_nothing_true_to_say() -> None:
    payload = orp._chat_grounded_provenance(type("R", (), {})(), {})
    assert "retrieval_status" not in payload
    assert "source_refs" not in payload
