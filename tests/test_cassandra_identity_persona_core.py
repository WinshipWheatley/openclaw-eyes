"""Tests for Cassandra's identity-question wiring (task 145, CLASS #6).

Task 142 built is_identity_question/identity_persona_reply (protected_generate.py) and
wired them into maestro_cassandra_responder.answer_frontdoor_chat -- Cassandra's PROBE
path, not her REAL Telegram surface (cassandra_listener.py -> cassandra_brain.handle()).
Pass-1 live evidence: "who are you and what do you do for me?" got a generic-assistant-
with-emoji answer with zero "Clara" and cross-domain bleed from another agent's work
items. These tests pin the fix: a deterministic, packet-free identity tap in handle()
itself.
"""

from __future__ import annotations

import importlib.util
import sys
import types


def _stub_if_missing(module_name, **attrs):
    if importlib.util.find_spec(module_name) is not None:
        return
    module = types.ModuleType(module_name)
    for name, value in attrs.items():
        setattr(module, name, value)
    sys.modules[module_name] = module


_stub_if_missing("cassandra_email_config", get_review_inbox=lambda: "review@example.com")
_stub_if_missing(
    "finance_state",
    build_finance_snapshot=lambda *args, **kwargs: {},
    detect_finance_status_intent=lambda *args, **kwargs: False,
    find_finance_account=lambda *args, **kwargs: None,
    finance_entity_terms=lambda *args, **kwargs: (),
    format_finance_context=lambda *args, **kwargs: "",
    get_finance_payment_answer=lambda *args, **kwargs: None,
    get_finance_status_answer=lambda *args, **kwargs: None,
    load_finance_state=lambda *args, **kwargs: {},
)
_stub_if_missing(
    "capability_registry",
    get_actor=lambda *args, **kwargs: None,
    registry_context_for_query=lambda *args, **kwargs: None,
)
_stub_if_missing("cassandra_custom_tools", handle_operator_objective=lambda *args, **kwargs: None)
_stub_if_missing("operator_universal_intake", try_process_surface_operator_intake=lambda *args, **kwargs: None)
_stub_if_missing("cassandra_guided_review", process_guided_review_message=lambda *args, **kwargs: None)
_stub_if_missing("operator_context_switchboard", process_operator_context_switchboard_message=lambda *args, **kwargs: None)
_stub_if_missing(
    "cassandra_pii_hooks",
    tokenize_prompt=lambda prompt: (prompt, None),
    rehydrate_reply=lambda reply, _ctx: reply,
    detokenize_for_dashboard=lambda text, *_args, **_kwargs: text,
)

import cassandra_brain
import protected_generate as pg


def test_who_are_you_answers_deterministically_with_clara_and_no_emoji(monkeypatch):
    logged = []
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **k: logged.append(k), raising=False)

    replies = cassandra_brain.handle("who are you and what do you do for me?")

    assert replies == [pg.identity_persona_reply("cassandra")]
    assert "clara" in replies[0].lower()
    assert not any(ch in replies[0] for ch in "😊🙂😀🤖")
    assert "i'm your ai assistant" not in replies[0].lower()
    assert logged[-1]["route"] == "identity_persona_core"


def test_identity_answer_never_mentions_another_agents_domain(monkeypatch):
    """No cross-domain bleed -- this tap is packet-free by construction, so another
    agent's work items (e.g. Niles' song count) can never leak in."""
    monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **k: None, raising=False)

    replies = cassandra_brain.handle("who are you and what do you do for me?")

    lowered = replies[0].lower()
    for other_domain_term in ("song", "track", "x32", "rig", "album", "mix"):
        assert other_domain_term not in lowered


def test_identity_tap_is_before_refusal_irrelevant_normal_routing_unaffected(monkeypatch):
    """Sanity: the new tap must not swallow unrelated messages."""
    called = {"ops": False}

    def _fake_classify(query):
        called["ops"] = True
        raise _StopEarly()

    class _StopEarly(Exception):
        pass

    monkeypatch.setattr(cassandra_brain, "classify_business_ops_intent", _fake_classify, raising=False)

    try:
        cassandra_brain.handle("what's the status of the St Anne's invoice?")
    except _StopEarly:
        pass

    assert called["ops"] is True


def test_business_who_question_is_not_treated_as_identity(monkeypatch):
    """'who is the St Anne's contact' is a business question, not identity -- must not
    be swallowed by the new tap."""
    called = {"ops": False}

    class _StopEarly(Exception):
        pass

    def _fake_classify(query):
        called["ops"] = True
        raise _StopEarly()

    monkeypatch.setattr(cassandra_brain, "classify_business_ops_intent", _fake_classify, raising=False)

    try:
        cassandra_brain.handle("who is the St Anne's contact?")
    except _StopEarly:
        pass

    assert called["ops"] is True
