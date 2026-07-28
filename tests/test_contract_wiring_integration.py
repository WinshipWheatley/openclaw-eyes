"""Proof that the RUNTIME calls the contracts — not that the contracts exist.

A standalone module with passing unit tests changes nothing about what the
operator sees. These tests drive the real listener functions and the real
clarification path, and assert on their actual output.

Where a test asserts an import edge it does so against the parsed source of the
production module, not against a mock, so deleting the call breaks the test.
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
from pathlib import Path

import pytest

import agent_lanes_registry as lanes
import agent_telegram_identity as ident
import grounded_answer_contract as gac
import maestro_listener as listener
import vote_timeout_clarification as votes

NONCE = "send-hold-graduation:abc123def456"


def _vote_failure_receipt(status: str = "empty") -> dict:
    """Task 167's exact outside-session fail-open receipt. Anything looser
    classifies as NONE, which is correct: this path must fire only on the real
    shape, never on a passing resemblance."""

    return {
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "semantic_vote_status": status,
    }




def _calls_module(module, name: str) -> bool:
    """Does the production source actually import this contract?"""

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == name for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == name:
            return True
    return False


# ─────────────────────────────────────────────── listener ↔ identity

def test_the_listener_actually_imports_the_identity_contract() -> None:
    assert _calls_module(listener, "agent_telegram_identity")


def test_every_operator_reply_carries_the_identity_banner(monkeypatch) -> None:
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    out = listener._identity_gated_reply("The invoice is queued.")
    assert out.startswith(ident.identity_banner("maestro"))
    assert "@openclaw_maestro_bot" in out
    assert "The invoice is queued." in out


def test_the_banner_is_not_doubled_on_an_already_bannered_reply(monkeypatch) -> None:
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    once = listener._identity_gated_reply("hello")
    twice = listener._identity_gated_reply(once)
    assert twice.count("@openclaw_maestro_bot") == 1


def test_a_nonce_is_withheld_at_egress_while_identity_is_unproven(monkeypatch) -> None:
    """THE INTERLOCK, at the real egress. Not at a caller that could forget to ask."""

    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    out = listener._identity_gated_reply(f"Approve with SEND {NONCE}")
    assert NONCE not in out, "a nonce escaped over an unproven identity"
    assert "Withheld" in out
    assert "nothing was sent" in out.lower()


def test_the_nonce_gate_opens_once_identity_is_proven(monkeypatch) -> None:
    """NON-VACUITY: a gate that never opens is broken, not safe."""

    monkeypatch.setenv(ident.IDENTITY_PROOF_ENV, "1")
    out = listener._identity_gated_reply(f"Approve with SEND {NONCE}")
    assert NONCE in out


def test_ordinary_replies_are_unaffected_by_the_nonce_gate(monkeypatch) -> None:
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    out = listener._identity_gated_reply("It is Tuesday.")
    assert "It is Tuesday." in out
    assert "Withheld" not in out


# ─────────────────────────────────────────── listener ↔ retrieval status

def test_the_listener_actually_imports_the_retrieval_contract() -> None:
    assert "packet_retrieval_status" in inspect.getsource(listener)


def test_a_retrieval_failure_reaches_the_operator_reply() -> None:
    """The Maestro regression, end to end through the real reply funnel."""

    payload = {
        "one_line_answer": "UNKNOWN.",
        "source_refs": ["chief_status_rail.json"],
        "retrieval_status": {"status": "TABLES_MISSING", "detail": "canonical_facts absent",
                             "source_path": "/x/ledger.sqlite"},
    }
    reply = listener.reply_text_from_bridge_response(payload, request_id="r1")
    assert "chief_status_rail.json" in reply
    assert "TABLES_MISSING" in reply


def test_an_honest_empty_does_not_manufacture_a_failure_suffix() -> None:
    """NON-VACUITY: EMPTY_BY_QUERY must stay silent, or every answer grows noise."""

    payload = {
        "one_line_answer": "Nothing scheduled today.",
        "source_refs": ["calendar.json"],
        "retrieval_status": {"status": "EMPTY_BY_QUERY", "detail": ""},
    }
    reply = listener.reply_text_from_bridge_response(payload, request_id="r2")
    assert "Retrieval failed" not in reply


def test_a_payload_without_retrieval_status_is_unchanged() -> None:
    payload = {"one_line_answer": "It is Tuesday."}
    reply = listener.reply_text_from_bridge_response(payload, request_id="r3")
    assert "Retrieval failed" not in reply
    assert "Tuesday" in reply


# ────────────────────────────────────── listener ↔ question dominance

def test_the_listener_actually_imports_the_answer_contract() -> None:
    assert "grounded_answer_contract" in inspect.getsource(listener)


def test_the_niles_deflection_is_not_relayed_as_an_answer() -> None:
    """The exact battery failure, through the real reply funnel."""

    payload = {
        "source_text": ("For the exact-send gate, what evidence proves a draft was "
                        "approved before it was released, and which artifact records it?"),
        "one_line_answer": "What's the main goal: groove, melody, or arrangement?",
    }
    reply = listener.reply_text_from_bridge_response(payload, request_id="r4")
    assert "groove" not in reply, "a persona deflection was relayed as an answer"
    assert "UNKNOWN" in reply
    assert gac.UNSAFE_PERSONA_OVERRIDE in reply


def test_a_real_answer_still_reaches_the_operator() -> None:
    """NON-VACUITY: over-blocking would be its own failure."""

    payload = {
        "source_text": "what evidence proves a draft was approved?",
        "one_line_answer": "The scoped graduation receipt records the approved draft.",
    }
    reply = listener.reply_text_from_bridge_response(payload, request_id="r5")
    assert "scoped graduation receipt" in reply


# ────────────────────────────────────────── routing ↔ named failure

def test_the_vote_path_actually_imports_the_named_failure_contract() -> None:
    assert "grounded_answer_contract" in inspect.getsource(votes)


@pytest.mark.parametrize("agent", ["cassandra", "chief"])
def test_the_observed_routing_failure_now_names_itself(agent: str) -> None:
    """Both agents returned the same generic retry in the battery."""

    named = votes.named_clarification_for_vote_failure(_vote_failure_receipt(), agent=agent)
    assert named is not None
    assert agent in named
    assert gac.is_generic_retry(named) is False
    assert "MODEL_FAILURE" in named


def test_the_named_failure_keeps_the_old_safety_claim() -> None:
    named = votes.named_clarification_for_vote_failure(_vote_failure_receipt(), agent="chief")
    assert "not run" in named.lower()
    assert "nothing was sent" in named.lower()


def test_a_healthy_vote_produces_no_clarification() -> None:
    assert votes.named_clarification_for_vote_failure(_vote_failure_receipt("accepted_unresolved")) is None


def test_the_legacy_generic_message_is_still_detected_as_generic() -> None:
    """Guard against the old string creeping back in."""

    assert gac.is_generic_retry(votes.MODEL_FAILURE_CLARIFICATION) is True


# ──────────────────────────────────────────────── agent_lanes schema

def test_the_production_schema_materializes_and_seeds(tmp_path: Path) -> None:
    conn = lanes.connect(tmp_path / "lanes.sqlite")
    written = lanes.seed_rows(conn)
    assert written == 6
    row = conn.execute(
        "SELECT telegram_bot_username FROM agent_lanes WHERE agent_id = 'cassandra'"
    ).fetchone()
    assert row["telegram_bot_username"] == "@openclaw_cassandra_bot"


def test_a_declared_lane_is_refused_until_live_verification(tmp_path: Path) -> None:
    """Declaring is not proving. This is the fail-closed half."""

    conn = lanes.connect(tmp_path / "lanes.sqlite")
    lanes.seed_rows(conn)
    lane = lanes.resolve_lane(conn, "cassandra")
    assert lane.ok is False
    assert lane.reason == lanes.UNVERIFIED


def test_a_verified_lane_resolves(tmp_path: Path) -> None:
    """NON-VACUITY: the registry must be able to say yes."""

    conn = lanes.connect(tmp_path / "lanes.sqlite")
    lanes.seed_rows(conn)
    lanes.record_live_verification(conn, "cassandra", chat_id="5150",
                                   username="@openclaw_cassandra_bot",
                                   verified_at="2026-07-28T04:00:00Z")
    lane = lanes.resolve_lane(conn, "cassandra")
    assert lane.ok is True and lane.chat_id == "5150"


def test_verification_refuses_a_username_the_registry_does_not_declare(tmp_path: Path) -> None:
    """`Casandra bot` must not be recordable as Cassandra."""

    conn = lanes.connect(tmp_path / "lanes.sqlite")
    lanes.seed_rows(conn)
    with pytest.raises(lanes.LaneRegistryError):
        lanes.record_live_verification(conn, "cassandra", chat_id="5150",
                                       username="@casandra_bot",
                                       verified_at="2026-07-28T04:00:00Z")


def test_the_schema_stores_no_token_or_secret(tmp_path: Path) -> None:
    conn = lanes.connect(tmp_path / "lanes.sqlite")
    lanes.seed_rows(conn)
    columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(agent_lanes)")}
    for forbidden in ("token", "secret", "credential", "password", "api_key"):
        assert not any(forbidden in c for c in columns), f"{forbidden} column present"
    assert "token" not in lanes.SCHEMA_SQL.lower()


def test_the_banner_is_off_by_default_so_visible_replies_do_not_change(monkeypatch) -> None:
    """Three existing listener tests assert the exact operator-visible reply and are
    right to. Turning the banner on is a deployment decision, not a code one."""

    monkeypatch.delenv(ident.IDENTITY_BANNER_ENV, raising=False)
    assert listener._identity_gated_reply("It is Tuesday.") == "It is Tuesday."


def test_the_nonce_interlock_is_NOT_opt_in(monkeypatch) -> None:
    """Cosmetics are flagged; guards are not. With every identity flag unset, a
    nonce must still be withheld."""

    monkeypatch.delenv(ident.IDENTITY_BANNER_ENV, raising=False)
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    out = listener._identity_gated_reply(f"SEND {NONCE}")
    assert NONCE not in out
    assert "Withheld" in out
