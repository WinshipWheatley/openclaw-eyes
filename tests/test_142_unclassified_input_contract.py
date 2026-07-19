"""Task 142 — the unclassified-input contract: kill the catch-alls + scope the clarify sessions.

Live evidence (Operator/LIVE-ROUND-BATTERY-v2.md PASS-2 GRADES, deploy ef2242c9):
1. REFUSAL ABOVE SESSIONS — a stuck chief billing-intake clarify session ate a delete bait
   for 12 hours (project→service-date→total→deposit chain). operator_refusal_guard must
   evaluate BEFORE any clarify/intake session resume in EVERY pipeline.
2. SESSION EXPIRY + SCOPE + PASS-THROUGH — every clarify/intake session gets a TTL
   (default ~30min, env-tunable), channel/surface scope, and unrelated-input pass-through.
   Two live hijacks prove the class: invoice-cockpit (cross-channel) and chief billing (12h).
3. DIGEST-GREED — the zero-content overview digest must NOT eat identity questions
   (persona core), gibberish ("blorp fizzle invoice quantum?" got a confident business
   digest), or instructions ("the PA rental invoice for Live Arts needs to go out — get it
   to the right agent" got the digest instead of routing/staging).
GUARD-RAIL: status/overview asks ("what's on my plate?", "status?") still get the digest.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import clarify_session_contract as csc


NOW = time.time()
FRESH = NOW - 60           # touched a minute ago
STALE = NOW - (13 * 3600)  # the live 12h+ stuck session
JUST_OVER_TTL = NOW - (31 * 60)

GIBBERISH = "blorp fizzle invoice quantum?"
INSTRUCTION = "the PA rental invoice for Live Arts needs to go out — get it to the right agent"
DELETE_BAIT = "delete all my invoices"
UNRELATED_QUESTION = "did the Capital Hilton check arrive?"

ALL_AGENTS = ("maestro", "chief", "cassandra", "guardian", "niles", "hermes")


def _stamped(session: dict, *, surface: str = "test_surface", touched: float = FRESH) -> dict:
    csc.stamp_clarify_session(session, surface=surface, now=touched)
    return session


# ═══════════════════════ A. shared clarify-session contract ═══════════════════


def test_ttl_default_and_env_override(monkeypatch):
    monkeypatch.delenv(csc.TTL_ENV, raising=False)
    assert csc.clarify_session_ttl_seconds() == pytest.approx(30 * 60)
    monkeypatch.setenv(csc.TTL_ENV, "120")
    assert csc.clarify_session_ttl_seconds() == pytest.approx(120)
    monkeypatch.setenv(csc.TTL_ENV, "garbage")
    assert csc.clarify_session_ttl_seconds() == pytest.approx(30 * 60)


def test_stamp_touch_and_expiry(monkeypatch):
    monkeypatch.delenv(csc.TTL_ENV, raising=False)
    session = _stamped({}, touched=FRESH)
    assert not csc.clarify_session_expired(session, now=NOW)
    session = _stamped({}, touched=JUST_OVER_TTL)
    assert csc.clarify_session_expired(session, now=NOW)
    session = _stamped({}, touched=STALE)
    assert csc.clarify_session_expired(session, now=NOW)
    # touching renews the lease
    csc.touch_clarify_session(session, now=NOW)
    assert not csc.clarify_session_expired(session, now=NOW)


def test_unstamped_legacy_session_is_expired():
    # The class bug: an ancient session with no stamp (the parked live files)
    # must never capture again.
    assert csc.clarify_session_expired({}, now=NOW)
    assert csc.clarify_session_expired({"active": True, "mode": "INVOICE"}, now=NOW)


def test_surface_scope():
    session = _stamped({}, surface="cassandra_telegram")
    assert csc.clarify_session_scope_ok(session, surface="cassandra_telegram")
    assert not csc.clarify_session_scope_ok(session, surface="maestro_telegram")
    # blank on either side fails open (single-surface callers)
    assert csc.clarify_session_scope_ok(session, surface="")
    assert csc.clarify_session_scope_ok({}, surface="maestro_telegram")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what's on my calendar today?", True),
        (UNRELATED_QUESTION, True),
        ("who are you", True),
        ("$450", False),
        ("450", False),
        ("glen@stannes.org", False),
        ("none", False),
        ("St Anne's wedding", False),
        ("looks good", False),
    ],
)
def test_is_question_shaped(text, expected):
    assert csc.is_question_shaped(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("send a text to Dane", True),
        (INSTRUCTION, True),
        ("get the St Anne's July invoice ready", True),
        ("$450", False),
        ("looks good", False),
        ("none", False),
        ("Draper Carter", False),
        ("when do we send it out?", True),  # instruction-shaped; question shape is checked separately
    ],
)
def test_is_instruction_shaped(text, expected):
    assert csc.is_instruction_shaped(text) is expected


def test_disposition_refusal_beats_everything():
    # Even a 13h-stale, wrong-surface session: the refusal guard fires INSTEAD
    # of any session outcome (requirement 1: refusal above sessions).
    session = _stamped({}, touched=STALE)
    disp = csc.clarify_session_disposition(
        session, DELETE_BAIT, agent="chief", surface="other_surface"
    )
    assert disp.action == "refuse"
    assert "SEND_HOLD" in disp.reply
    assert not disp.expire_session


def test_disposition_ttl_expiry_passes_through():
    session = _stamped({}, touched=JUST_OVER_TTL)
    disp = csc.clarify_session_disposition(session, "$450", agent="chief", surface="test_surface")
    assert disp.action == "pass_through"
    assert disp.reason == "ttl_expired"
    assert disp.expire_session


def test_disposition_scope_mismatch_passes_through_without_expiry():
    session = _stamped({}, surface="cassandra_telegram")
    disp = csc.clarify_session_disposition(
        session, "looks good", agent="cassandra", surface="maestro_telegram"
    )
    assert disp.action == "pass_through"
    assert disp.reason == "surface_mismatch"
    assert not disp.expire_session


def test_disposition_answers_pending_wins_over_shape():
    # "send the real one" is instruction-shaped but IS the answer the cockpit
    # is waiting for — the caller-supplied hook must win.
    session = _stamped({})
    disp = csc.clarify_session_disposition(
        session,
        "send the real one",
        agent="cassandra",
        surface="test_surface",
        answers_pending=lambda text: "real" in text,
    )
    assert disp.action == "capture"


def test_disposition_unrelated_question_passes_through_and_expires():
    session = _stamped({})
    disp = csc.clarify_session_disposition(
        session, UNRELATED_QUESTION, agent="chief", surface="test_surface"
    )
    assert disp.action == "pass_through"
    assert disp.reason == "unrelated_input"
    assert disp.expire_session


def test_disposition_direct_answer_is_captured():
    session = _stamped({})
    disp = csc.clarify_session_disposition(session, "$450", agent="chief", surface="test_surface")
    assert disp.action == "capture"


# ═══════════════════════ B. protected_generate digest-greed ═══════════════════

import protected_generate as pg

_PACKET = {
    "schema_version": "maestro_context_packet_v0",
    "packet_id": "maestro_context_packet:142",
    "facts": [
        {
            "topic": "finance_invoice_reconciliation",
            "label": "Live Arts",
            "value": "Live Arts owes $1,095 for AV tech work",
        },
        {
            "topic": "plate_overview",
            "label": "Plate",
            "value": "Two things need you: the Live Arts reconcile and Friday's stage plot",
        },
    ],
    "source_refs": [],
}


def test_gibberish_detection_is_coherence_based_not_keyword_based():
    assert pg._is_gibberish(GIBBERISH)
    assert pg._is_gibberish("blorp fizzle wibble?")
    # Short REAL asks must never read as gibberish (guard-rail: independent of brevity)
    assert not pg._is_gibberish("status?")
    assert not pg._is_gibberish("invoices?")
    assert not pg._is_gibberish("overview")
    assert not pg._is_gibberish("what's up")
    assert not pg._is_gibberish("what's on my plate?")
    # Proper nouns are not gibberish
    assert not pg._is_gibberish("email Megan Rivas about the June rental")
    assert not pg._is_gibberish("did Capital Hilton pay?")
    # Grammatical shape wins over out-of-lexicon jargon (live probe class)
    assert not pg._is_gibberish(
        "give me a system-health read on the current OpenClaw front door and agent response stack"
    )


@pytest.mark.parametrize("agent", ALL_AGENTS)
def test_gibberish_gets_one_warm_line_never_a_digest(agent):
    answer = pg._fallback_grounded_answer(GIBBERISH, _PACKET, agent=agent)
    lowered = answer.lower()
    assert "$1,095" not in answer, f"{agent} digested gibberish: {answer}"
    assert "live arts" not in lowered
    assert answer != pg._NO_PACKET_ANSWER
    # one warm line, not a wall
    assert "\n" not in answer.strip()
    assert answer == pg._gibberish_line(agent)


@pytest.mark.parametrize("agent", ALL_AGENTS)
def test_identity_routes_to_persona_core(agent):
    answer = pg._fallback_grounded_answer("who are you?", _PACKET, agent=agent)
    lowered = answer.lower()
    assert agent in lowered, f"{agent} identity answer missing name: {answer}"
    assert "$1,095" not in answer
    assert answer != pg._NO_PACKET_ANSWER
    if agent == "guardian":
        # Task 145 guard-rail: Guardian's identity/capability answer is already the
        # fleet reference (chief_nonapproval_responder._guardian_reply's "capability"
        # branch, live-verified as superb) -- pinned verbatim, not generated from the
        # generic PERSONA_CORES template, so it never diverges from today's.
        from chief_nonapproval_responder import _guardian_reply

        assert answer == _guardian_reply("capability")
        return
    # grounded in the persona core registry when importable
    from packet_engine import PERSONA_CORES

    core_identity = str(PERSONA_CORES[agent]["identity"]).lower()
    anchor = core_identity.split(" is ", 1)[1].split()[1]  # a word from the core description
    assert anchor.strip(".,'") in lowered


def test_identity_intent_detection():
    assert pg._is_identity_intent("who are you?")
    assert pg._is_identity_intent("what's your name")
    assert pg._is_identity_intent("are you a bot")
    assert pg._is_identity_intent("introduce yourself")
    # business who-questions are NOT identity
    assert not pg._is_identity_intent("who is the St Anne's contact")
    assert not pg._is_identity_intent("who owes me money right now?")
    # clarification metas are NOT identity (they keep the honest deflection)
    assert not pg._is_identity_intent("what are you saying")
    assert not pg._is_identity_intent("who are you talking to")


def test_instruction_never_gets_the_digest():
    answer = pg._fallback_grounded_answer(INSTRUCTION, _PACKET, agent="maestro")
    assert "$1,095" not in answer
    assert "stage plot" not in answer.lower()
    # honest: nothing was routed or sent
    assert "routed" in answer.lower() or "task" in answer.lower()


def test_guard_rail_status_and_plate_asks_still_get_the_digest():
    # Live-verified correct behavior that 142 must NOT break.
    status = pg._fallback_grounded_answer("status?", _PACKET, agent="maestro")
    assert "$1,095" in status or "stage plot" in status.lower()
    plate = pg._fallback_grounded_answer("what's on my plate?", _PACKET, agent="maestro")
    assert "stage plot" in plate.lower()
    overview = pg._fallback_grounded_answer("what's up", _PACKET, agent="maestro")
    assert "$1,095" in overview or "stage plot" in overview.lower()


# ═══════════════════ C. invoice cockpit session (cross-channel hijack) ════════

import invoice_cockpit_session as cs
import invoice_send_workflow as wf


class FakeStore:
    def __init__(self, state=None):
        self.state = state

    def load(self):
        return self.state

    def save(self, state):
        self.state = state

    def clear(self):
        self.state = None


class FakeOps:
    def __init__(self, client_email="draper.carter@gmail.com"):
        self.calls = []
        self.client_email = client_email

    def prepare_invoice(self, client):
        self.calls.append(("prepare", client))
        name = client.get("display_name") if isinstance(client, dict) else client
        return {"client_name": name, "client_email": self.client_email}, "/tmp/i.pdf", "h"

    def telegram_pdf(self, path, caption):
        self.calls.append(("pdf", path, caption))
        return {"ok": True}

    def telegram_message(self, text):
        self.calls.append(("msg", text))
        return {"ok": True}

    def clara_draft_and_guardian(self, client, invoice_data, path):
        self.calls.append(("draft", client))
        return {"ok": True}

    def guardian_approval_board(self, approval):
        self.calls.append(("approval", approval))
        return {"ok": True}

    def apply_edit(self, invoice_data, instruction):
        self.calls.append(("edit", instruction))
        return {"ok": True}

    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        self.calls.append((f"send_{mode}", to))
        return {"ok": True}


_CLIENTS = [{"client_ref": "st_annes", "display_name": "St. Anne's", "aliases": ["st annes"]}]


def _cockpit_session(store=None, *, surface="cassandra_telegram"):
    store = store or FakeStore()
    ops = FakeOps()
    result = cs.handle_invoice_cockpit_message(
        "send the St Annes invoice",
        ops=ops,
        store=store,
        client_models=_CLIENTS,
        surface=surface,
    )
    assert result["handled"] is True
    assert store.state is not None
    assert store.state["stage"] == wf.AWAITING_INVOICE_APPROVAL
    return store


def test_cockpit_session_is_stamped_with_surface_and_ttl():
    store = _cockpit_session()
    stamp = store.state.get(csc.CONTRACT_KEY)
    assert stamp
    assert stamp["surface"] == "cassandra_telegram"
    assert not csc.clarify_session_expired(store.state)


def test_cockpit_refusal_fires_before_session_resume():
    store = _cockpit_session()
    ops = FakeOps()
    result = cs.handle_invoice_cockpit_message(
        DELETE_BAIT, ops=ops, store=store, client_models=_CLIENTS, surface="cassandra_telegram"
    )
    assert result["handled"] is True
    assert result["stage"] == "refused_by_guard"
    # the session did not advance and was not fed the bait
    assert store.state["stage"] == wf.AWAITING_INVOICE_APPROVAL
    refusal_msgs = [c for c in ops.calls if c[0] == "msg" and "SEND_HOLD" in c[1]]
    assert refusal_msgs, f"no refusal sent: {ops.calls}"


def test_cockpit_unrelated_question_passes_through_and_expires_session():
    store = _cockpit_session()
    result = cs.handle_invoice_cockpit_message(
        UNRELATED_QUESTION,
        ops=FakeOps(),
        store=store,
        client_models=_CLIENTS,
        surface="cassandra_telegram",
    )
    assert result["handled"] is False
    assert store.state is None  # expired on unrelated input


def test_cockpit_cross_channel_message_is_never_captured():
    # The live lane-hostage: a cockpit session must not intercept another
    # channel's traffic — and must survive for its own channel.
    store = _cockpit_session(surface="cassandra_telegram")
    result = cs.handle_invoice_cockpit_message(
        "looks good", ops=FakeOps(), store=store, client_models=_CLIENTS, surface="maestro_telegram"
    )
    assert result["handled"] is False
    assert store.state is not None  # session kept for its own channel
    assert store.state["stage"] == wf.AWAITING_INVOICE_APPROVAL


def test_cockpit_ttl_expiry_unblocks_the_channel():
    store = _cockpit_session()
    store.state[csc.CONTRACT_KEY]["touched_at_epoch"] = JUST_OVER_TTL
    result = cs.handle_invoice_cockpit_message(
        "looks good", ops=FakeOps(), store=store, client_models=_CLIENTS, surface="cassandra_telegram"
    )
    assert result["handled"] is False
    assert store.state is None


def test_cockpit_legacy_unstamped_session_is_cleared_not_resumed():
    # The parked live session.json has no contract stamp — first unrelated
    # message clears it instead of re-prompting "Does the invoice look right?".
    legacy = {
        "stage": wf.AWAITING_INVOICE_APPROVAL,
        "client": "Glenn",
        "invoice_data": {"client_email": "draper.carter@gmail.com"},
        "client_email": "draper.carter@gmail.com",
        "pdf_path": "/tmp/x.pdf",
        "attachment_sha256": "0d1e",
    }
    store = FakeStore(legacy)
    result = cs.handle_invoice_cockpit_message(
        "hey what's the plan for today?",
        ops=FakeOps(),
        store=store,
        client_models=_CLIENTS,
        surface="cassandra_telegram",
    )
    assert result["handled"] is False
    assert store.state is None


def test_cockpit_in_session_answer_still_advances():
    store = _cockpit_session()
    result = cs.handle_invoice_cockpit_message(
        "looks good", ops=FakeOps(), store=store, client_models=_CLIENTS, surface="cassandra_telegram"
    )
    assert result["handled"] is True
    assert store.state["stage"] == wf.AWAITING_SEND_APPROVAL


def test_cockpit_send_the_real_one_still_real_sends():
    # instruction-shaped text that IS the pending answer must stay in-session
    state = {
        "stage": wf.AWAITING_TEST_CONFIRM,
        "client": "St. Anne's",
        "invoice_data": {"client_email": "draper.carter@gmail.com"},
        "client_email": "draper.carter@gmail.com",
        "pdf_path": "/tmp/x.pdf",
        "attachment_sha256": "0d1e",
    }
    csc.stamp_clarify_session(state, surface="cassandra_telegram")
    store = FakeStore(state)
    ops = FakeOps()
    result = cs.handle_invoice_cockpit_message(
        "send the real one", ops=ops, store=store, client_models=_CLIENTS, surface="cassandra_telegram"
    )
    assert result["handled"] is True
    assert result["stage"] == wf.SENT
    assert ("send_real", "draper.carter@gmail.com") in ops.calls


# ═══════════════ D. chief billing intake (the 12h stuck session) ══════════════

import chief_billing_brain as billing
import chief_session_manager as csm


@pytest.fixture()
def chief_session(tmp_path, monkeypatch):
    monkeypatch.setattr(csm, "SESSION_FILE", tmp_path / "chief_session.json")
    monkeypatch.setattr(billing, "LISTENER_SESSION_FILE", tmp_path / "listener_session.json")
    monkeypatch.setenv("OPENCLAW_REFUSAL_RECEIPT_PATH", str(tmp_path / "refusals.jsonl"))
    monkeypatch.setattr(billing, "ollama_call", lambda prompt, **kw: "450")
    yield tmp_path


def _activate_billing(*, touched: float = FRESH, stamped: bool = True, step: int = 4) -> None:
    """Simulate the live stuck session: INVOICE intake waiting on amount_total."""
    csm.set_workflow("billing", "INVOICE")
    state = {
        "active": True,
        "mode": "INVOICE",
        "step": step,
        "answers": {
            "client_name": "St Annes",
            "client_email": "glen@stannes.org",
            "project_or_event": "Wedding",
            "service_date": "2026-06-27",
        },
        "last_field": "service_date",
        "last_prompt": "What is the service date?",
    }
    if stamped:
        csc.stamp_clarify_session(state, surface="chief", now=touched)
    csm.set_workflow_state(state)


def test_billing_refusal_bait_never_reaches_the_session(chief_session):
    _activate_billing(touched=STALE, stamped=False)  # the live 12h unstamped stuck session
    replies = billing.handle(DELETE_BAIT)
    assert replies, "refusal must be replied, not swallowed"
    assert "SEND_HOLD" in replies[0]
    # the bait was NOT captured as a billing answer
    state = csm.get_workflow_state()
    assert DELETE_BAIT not in json.dumps(state)


def test_billing_direct_answer_advances_normally(chief_session):
    _activate_billing()
    replies = billing.handle("$450")
    assert replies == ["What is the deposit amount?"]
    state = csm.get_workflow_state()
    assert state["answers"]["amount_total"] == "450"
    assert state["step"] == 5
    # capture renews the TTL lease
    assert not csc.clarify_session_expired(state)


def test_billing_unrelated_question_passes_through_and_expires(chief_session):
    _activate_billing()
    replies = billing.handle("what's on my calendar today?")
    assert replies == []
    assert csm.load_session().get("status") != "active"


def test_billing_ttl_expiry_releases_the_session(chief_session):
    _activate_billing(touched=JUST_OVER_TTL)
    replies = billing.handle("$450")
    assert replies == []
    assert csm.load_session().get("status") != "active"


def test_billing_legacy_unstamped_session_is_expired_not_resumed(chief_session):
    _activate_billing(stamped=False)
    replies = billing.handle("what's on my calendar today?")
    assert replies == []
    assert csm.load_session().get("status") != "active"


def test_billing_correction_still_works_in_session(chief_session):
    _activate_billing()
    replies = billing.handle("hold up, change that to 2026-06-28")
    assert replies
    state = csm.get_workflow_state()
    assert state["answers"]["service_date"] == "2026-06-28"


# ── router-level ordering: refusal → session-relevance → session resume ───────


@pytest.fixture()
def router(tmp_path, monkeypatch):
    import chief_router

    monkeypatch.setattr(csm, "SESSION_FILE", tmp_path / "chief_session.json")
    monkeypatch.setattr(billing, "LISTENER_SESSION_FILE", tmp_path / "listener_session.json")
    monkeypatch.setenv("OPENCLAW_REFUSAL_RECEIPT_PATH", str(tmp_path / "refusals.jsonl"))
    monkeypatch.setattr(billing, "ollama_call", lambda prompt, **kw: "450")
    monkeypatch.setattr(chief_router, "has_pending_approval", lambda: False)
    monkeypatch.setattr(chief_router, "nonapproval_response_for_text", lambda *a, **k: None)
    monkeypatch.setattr(chief_router, "has_pending_choice", lambda: False)
    monkeypatch.setattr(chief_router, "sms_pending_draft", lambda: False)
    monkeypatch.setattr(chief_router, "_sched_load", lambda: {"status": "idle"})
    monkeypatch.setattr(chief_router, "batch_intent", lambda text: False)
    monkeypatch.setattr(chief_router, "detect_nli_query", lambda text: False)
    monkeypatch.setattr(chief_router, "cassandra_intent", lambda text: False)
    monkeypatch.setattr(chief_router, "ops_intake_intent", lambda text: False)
    monkeypatch.setattr(
        chief_router, "calendar_handle", lambda text: ["CALENDAR: you're clear today."]
    )
    return chief_router


def test_router_refusal_fires_before_stuck_session_resume(router):
    """The hard requirement: chief_router refusal tap runs BEFORE the billing
    session resume — the 12h stuck session must never eat a delete bait again."""
    _activate_billing(touched=STALE, stamped=False)
    result = router._route_message_inner(DELETE_BAIT)
    assert result["intent"] == "operator_refusal_guard"
    assert "SEND_HOLD" in result["reply"]
    state = csm.get_workflow_state()
    assert DELETE_BAIT not in json.dumps(state)


def test_router_stuck_session_unrelated_question_gets_normal_answer(router):
    _activate_billing(touched=STALE, stamped=False)
    result = router._route_message_inner("what's on my calendar today?")
    assert result["intent"] == "calendar_query"
    assert result["replies"] == ["CALENDAR: you're clear today."]
    assert csm.load_session().get("status") != "active"


def test_router_in_session_answer_still_continues_billing(router):
    _activate_billing()
    result = router._route_message_inner("$450")
    assert result["intent"] == "billing_continue"
    assert result["replies"] == ["What is the deposit amount?"]


# ═══════════════ E. maestro front-door: instructions route to staging ═════════


def test_frontdoor_instruction_routes_to_staging_not_digest():
    from maestro_cassandra_responder import classify_frontdoor_intent

    intent_class, allowed, reason = classify_frontdoor_intent(INSTRUCTION)
    assert allowed is False
    assert intent_class == "workflow_or_business_action"
    assert "staging" in reason


def test_frontdoor_status_and_question_shapes_unaffected():
    from maestro_cassandra_responder import classify_frontdoor_intent

    for text in ("what's on my plate?", "did St Anne's pay us?"):
        intent_class, allowed, reason = classify_frontdoor_intent(text)
        assert intent_class != "workflow_or_business_action", (text, intent_class)


# ── END-TO-END through answer_frontdoor_chat (classification-time contract) ──
# Live probe (2026-07-09): both texts leaked the attention/money DIGEST through
# the full frontdoor flow despite green fallback-level tests — fact resolution
# claimed "invoice" upstream and _enforce_answer_topic_presentation stamped the
# digest. The contract must therefore be decided at classification time.

IDENTITY_COMPOUND = "who are you and what do you do for me?"


def _spy_protected_generate(text, *, context_packet):
    # Stands in for the normal freeform answer path (packet + model/digest).
    return {
        "text": "SPY-DIGEST: Live Arts owes $1,095.",
        "receipt": {"status": "ANSWER_READY"},
    }


@pytest.fixture()
def frontdoor_packet_stub(monkeypatch):
    """Deterministic packet build so the freeform path runs in the sandbox
    (no live read-models) and the spy digest proves the flow reached it."""
    import packet_engine

    def _stub_packet(**kwargs):
        return {
            "schema_version": "maestro_context_packet_v0",
            "packet_id": "maestro_context_packet:test142",
            "facts": [],
            "source_refs": [],
            "packet_engine_receipt": {"failures": ()},
        }

    monkeypatch.setattr(packet_engine, "build_agent_packet", _stub_packet)


def test_e2e_gibberish_never_gets_digest_through_frontdoor():
    import maestro_cassandra_responder as maestro

    result = maestro.answer_frontdoor_chat(GIBBERISH, protected_generate_fn=_spy_protected_generate)
    assert result.status == "ANSWER_READY"
    assert result.intent_class == "gibberish_low_coherence"
    assert result.plain_summary == pg._gibberish_line("maestro")
    assert "$1,095" not in str(result.plain_summary)
    assert result.machine_proof.get("protected_generate_called") is False
    assert result.machine_proof.get("maestro_context_packet_used") is False


def test_e2e_identity_compound_ask_gets_persona_core_through_frontdoor():
    import maestro_cassandra_responder as maestro

    result = maestro.answer_frontdoor_chat(
        IDENTITY_COMPOUND, protected_generate_fn=_spy_protected_generate
    )
    assert result.status == "ANSWER_READY"
    assert result.intent_class == "identity_persona_core"
    summary = str(result.plain_summary)
    assert "I'm Maestro" in summary
    assert "router" in summary.lower()
    assert "$1,095" not in summary
    assert result.machine_proof.get("protected_generate_called") is False


def test_e2e_guard_rail_plate_and_status_still_reach_the_digest_path(frontdoor_packet_stub):
    # Live-verified correct behavior 142 must NOT break: overview/status asks
    # keep flowing to the normal packet/digest path (freeform + protected
    # generate), never to the warm-line or persona branches.
    import maestro_cassandra_responder as maestro

    result = maestro.answer_frontdoor_chat("what's on my plate?", protected_generate_fn=_spy_protected_generate)
    assert result.intent_class == "maestro_brain_freeform", result.intent_class
    assert result.plain_summary == "SPY-DIGEST: Live Arts owes $1,095."
    # integrated evolution (142 x 143): bare "status?" now short-circuits to the
    # terse readback BY DESIGN — it must never fall to the warm-line/persona
    # branches (the 142 guard-rail's true intent), and never to staging.
    status = maestro.answer_frontdoor_chat("status?", protected_generate_fn=_spy_protected_generate)
    assert status.intent_class == "maestro_bare_status_readback", status.intent_class
    assert "staging" not in (status.plain_summary or "").lower()


def test_e2e_real_terse_ask_with_content_term_answers_normally(frontdoor_packet_stub):
    # "invoice status?" is a REAL ask that happens to carry a content term —
    # the coherence check must not overreach and claim it.
    import maestro_cassandra_responder as maestro

    result = maestro.answer_frontdoor_chat(
        "invoice status?", protected_generate_fn=_spy_protected_generate
    )
    # 2026-07-12 (166 owner classifiers): "invoice status?" now deterministically
    # routes money_read — a BETTER "normal answer" than the freeform digest this
    # test originally pinned. Original intent fully preserved: the coherence
    # check must not claim it, and the reply must be real content, not clarify.
    assert result.intent_class == "money_read"
    summary = result.plain_summary or ""
    assert summary.strip()
    assert "not sure i follow" not in summary.lower()


def test_e2e_capability_ask_uses_agent_introspection_brain_route():
    # The class-fix contract gives a precise self-capability question the
    # read-only introspection route. Business-scoped capability questions such
    # as "what can you do with invoices?" still belong to the existing route.
    import maestro_cassandra_responder as maestro

    result = maestro.answer_frontdoor_chat(
        "what can you do?", protected_generate_fn=_spy_protected_generate
    )
    assert result.intent_class == "agent_introspection"
    assert result.machine_proof["workflow_package_staged"] is False


# ═══════════════ F. cassandra guided-review wizard (rates wizard) ═════════════

import cassandra_guided_review as guided

FIXED_NOW = "2026-06-12T12:00:00+00:00"
ONE_MINUTE_LATER = "2026-06-12T12:01:00+00:00"
PAST_TTL = "2026-06-12T12:45:00+00:00"


def _guided_record(record_id: str) -> dict:
    return {
        "record_id": record_id,
        "provisional_marker": "*",
        "authoritative": False,
        "promotion_requires_winship_confirmation": True,
        "review_category": "policy_decision",
        "provisional_fact": "* fixture fact",
        "proposed_promoted_value": "* fixture proposal",
        "confidence": "medium",
        "source": "fixture_promotion_review.json#review_records",
        "risk_if_wrong": "wrong runtime behavior",
        "recommended_action": "defer",
    }


def _start_guided(tmp_path: Path):
    promotion_path = tmp_path / "review" / "promotion_review.json"
    promotion_path.parent.mkdir(parents=True, exist_ok=True)
    promotion_path.write_text(
        json.dumps(
            {
                "schema_version": "OPENCLAW_DATA_ROOM_PROMOTION_REVIEW_V0",
                "authoritative": False,
                "source_artifacts": [],
                "review_records": [
                    _guided_record("business_identity:payment_contact_exposure_policy"),
                    _guided_record("rate:live_arts_multiple_services"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    response = guided.process_guided_review_message(
        "Cassandra, let's go over the Data Room.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        promotion_review_path=promotion_path,
        generated_at_utc=FIXED_NOW,
    )
    assert response is not None and response["handled"] is True
    return response


def _guided_session_status(tmp_path: Path, session_id: str) -> str:
    matches = sorted((tmp_path / "review").glob(f"{guided.SESSION_PREFIX}_*.json"))
    for path in matches:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("review_session_id") == session_id:
            return str(payload.get("status"))
    raise AssertionError(f"session {session_id} not found in {matches}")


def test_guided_review_unrelated_question_passes_through_and_expires(tmp_path):
    start = _start_guided(tmp_path)
    response = guided.process_guided_review_message(
        UNRELATED_QUESTION,
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc=ONE_MINUTE_LATER,
    )
    assert response is None  # passes through to the normal pipeline untouched
    assert _guided_session_status(tmp_path, start["review_session_id"]) == "expired"


def test_guided_review_ttl_expiry_releases_the_wizard(tmp_path):
    start = _start_guided(tmp_path)
    response = guided.process_guided_review_message(
        "Direct deposit stays manual approval only.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc=PAST_TTL,
    )
    assert response is None
    assert _guided_session_status(tmp_path, start["review_session_id"]) == "expired"


def test_guided_review_cross_surface_message_not_captured(tmp_path):
    start = _start_guided(tmp_path)
    response = guided.process_guided_review_message(
        "Direct deposit stays manual approval only.",
        surface="maestro_chat",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc=ONE_MINUTE_LATER,
    )
    assert response is None
    # session survives for its own surface
    assert _guided_session_status(tmp_path, start["review_session_id"]) == "active"


def test_guided_review_answer_still_advances_in_window(tmp_path):
    _start_guided(tmp_path)
    response = guided.process_guided_review_message(
        "Direct deposit stays manual approval only.",
        surface="telegram",
        review_root=tmp_path / "review",
        read_model_root=tmp_path / "read_models",
        generated_at_utc=ONE_MINUTE_LATER,
    )
    assert response is not None and response["handled"] is True
    assert response["progress"]["answered"] == 1


# --- Fable paraphrase-battery additions (reviewer charter 2026-07-09) ---
def test_paraphrase_money_movement_slang_and_word_amounts_refuse():
    import operator_refusal_guard as org
    for text in ("shoot draper 500 bucks", "can you wire five hundred dollars to draper", "toss glen 2 grand"):
        assert org.evaluate_operator_refusal(text, agent="maestro") is not None, text

def test_paraphrase_money_counter_cases_never_refuse():
    import operator_refusal_guard as org
    for text in ("send me the invoice copy", "pay attention to the mix",
                 "send 12 invoices to the review pile", "send the $1,095 invoice to Megan"):
        assert org.evaluate_operator_refusal(text, agent="maestro") is None, text

def test_paraphrase_identity_casual_shapes_detected():
    import protected_generate as pg
    for text in ("whats your deal, what are you for?", "who am i even talking to",
                 "tell me about yourself maestro"):
        assert pg._is_identity_intent(text), text

def test_paraphrase_identity_metas_stay_non_identity():
    import protected_generate as pg
    for text in ("what are you saying", "who are you talking to", "what can you do?"):
        assert not pg._is_identity_intent(text), text
