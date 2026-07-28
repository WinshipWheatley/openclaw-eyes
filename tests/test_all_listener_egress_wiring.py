"""Every listener's real funnel, not one listener's and four hopes.

Maestro was wired first. The point of these tests is that Cassandra, Chief, Niles
and Guardian go through the identical checks, driven through each listener's own
production function — so a fix to one cannot silently skip the other four, which is
exactly how four listeners drift apart.
"""

from __future__ import annotations

import ast
import importlib
import inspect

import pytest

import agent_reply_egress as egress
import agent_telegram_identity as ident
import grounded_answer_contract as gac

NONCE = "send-hold-graduation:abc123def456"

NILES_QUESTION = (
    "For the exact-send gate, what evidence proves a draft was approved before it "
    "was released, and which artifact records it?"
)
PERSONA_DEFLECTION = "What's the main goal: groove, melody, or arrangement?"

#: (module, final-funnel attribute, agent name). Every independent egress in the repo.
LISTENERS = [
    ("maestro_listener", "_final_operator_reply", "maestro"),
    ("cassandra_listener", "_final_operator_reply", "cassandra"),
    ("chief_listener", "_final_operator_text", "chief"),
    ("producer_listener", "_final_operator_reply", "niles"),
    ("chief_guardian_listener", None, "guardian"),
]


def _mod(name: str):
    return importlib.import_module(name)


def _funnel(module_name: str, attr: str):
    return getattr(_mod(module_name), attr)


def _call(module_name: str, attr: str, text: str, question: str = "") -> str:
    fn = _funnel(module_name, attr)
    return fn(text, source_request=question)


ACTIVE = [(m, a, n) for m, a, n in LISTENERS if a]


# ────────────────────────────────────────────── the wiring exists

@pytest.mark.parametrize("module_name,attr,agent", LISTENERS)
def test_every_listener_imports_the_shared_egress(module_name, attr, agent) -> None:
    """AST over the production source: deleting the call breaks this."""

    tree = ast.parse(inspect.getsource(_mod(module_name)))
    imported = any(
        (isinstance(n, ast.ImportFrom) and (n.module or "") == "agent_reply_egress")
        or (isinstance(n, ast.Import) and any(a.name == "agent_reply_egress" for a in n.names))
        for n in ast.walk(tree)
    )
    assert imported, f"{module_name} does not route through the shared egress"


def test_no_listener_reimplements_the_interlock_locally() -> None:
    """Five copies of a guard is four chances to fix only one of them."""

    for module_name, _attr, _agent in LISTENERS:
        source = inspect.getsource(_mod(module_name))
        assert "send-hold-graduation:[A-Za-z0-9" not in source, (
            f"{module_name} carries its own nonce regex instead of using the egress"
        )


# ──────────────────────────────────────── nonce interlock, every agent

@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_no_listener_emits_a_nonce_while_identity_is_unproven(
    module_name, attr, agent, monkeypatch
) -> None:
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    out = _call(module_name, attr, f"Approve with SEND {NONCE}")
    assert NONCE not in out, f"{agent} leaked a nonce over unproven identity"
    assert egress.WITHHELD_PREFIX in out


@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_the_interlock_opens_for_every_listener_once_proven(
    module_name, attr, agent, monkeypatch
) -> None:
    """NON-VACUITY: a gate that never opens is broken, not safe."""

    monkeypatch.setenv(ident.IDENTITY_PROOF_ENV, "1")
    out = _call(module_name, attr, f"Approve with SEND {NONCE}")
    assert NONCE in out, f"{agent} could never emit an approved preview"


@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_the_interlock_is_not_opt_in_for_any_listener(
    module_name, attr, agent, monkeypatch
) -> None:
    monkeypatch.delenv(ident.IDENTITY_PROOF_ENV, raising=False)
    monkeypatch.delenv(ident.IDENTITY_BANNER_ENV, raising=False)
    out = _call(module_name, attr, f"SEND {NONCE}")
    assert NONCE not in out


# ─────────────────────────────────── question dominance, every agent

@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_no_listener_relays_a_persona_deflection(module_name, attr, agent) -> None:
    """The Niles failure, applied to all five — any persona can do this."""

    out = _call(module_name, attr, PERSONA_DEFLECTION, NILES_QUESTION)
    assert "groove" not in out, f"{agent} relayed a deflection as an answer"
    assert "UNKNOWN" in out
    assert gac.UNSAFE_PERSONA_OVERRIDE in out


@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_every_listener_still_relays_a_real_answer(module_name, attr, agent) -> None:
    """NON-VACUITY: over-blocking is its own failure mode."""

    answer = "The scoped graduation receipt records the approved draft and its release."
    out = _call(module_name, attr, answer, NILES_QUESTION)
    assert "scoped graduation receipt" in out, f"{agent} blocked a genuine answer"


@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_an_honest_unknown_is_never_rewritten(module_name, attr, agent) -> None:
    out = _call(module_name, attr, "UNKNOWN — no packet available.", NILES_QUESTION)
    assert "no packet available" in out


# ───────────────────────────────────────────── banner, every agent

@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_the_banner_names_the_right_agent_per_listener(
    module_name, attr, agent, monkeypatch
) -> None:
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    out = _call(module_name, attr, "ordinary reply")
    assert ident.AGENT_IDENTITIES[agent]["username"] in out, (
        f"{module_name} banner did not identify {agent}"
    )


@pytest.mark.parametrize("module_name,attr,agent", ACTIVE)
def test_the_banner_stays_off_by_default_everywhere(
    module_name, attr, agent, monkeypatch
) -> None:
    """Default fail-closed identity state is preserved: no visible change."""

    monkeypatch.delenv(ident.IDENTITY_BANNER_ENV, raising=False)
    out = _call(module_name, attr, "ordinary reply")
    assert not any(r["username"] in out for r in ident.AGENT_IDENTITIES.values())


# ──────────────────────────────── retrieval status through the egress

def test_a_retrieval_failure_suffix_is_shared_by_all_agents() -> None:
    payload = {
        "source_refs": ["chief_status_rail.json"],
        "retrieval_status": {"status": "TABLES_MISSING", "detail": "canonical_facts absent"},
    }
    for agent in ("cassandra", "chief", "niles", "guardian", "maestro"):
        out = egress.finalize_agent_reply(agent, "UNKNOWN.", payload=payload)
        assert "chief_status_rail.json" in out
        assert "TABLES_MISSING" in out


def test_an_honest_empty_adds_no_noise_for_any_agent() -> None:
    payload = {"source_refs": ["cal.json"], "retrieval_status": {"status": "EMPTY_BY_QUERY"}}
    for agent in ("cassandra", "chief", "niles", "guardian", "maestro"):
        out = egress.finalize_agent_reply(agent, "Nothing scheduled.", payload=payload)
        assert "Retrieval failed" not in out


def test_an_unregistered_agent_gets_no_banner_and_no_crash(monkeypatch) -> None:
    monkeypatch.setenv(ident.IDENTITY_BANNER_ENV, "1")
    out = egress.finalize_agent_reply("carter", "hello")
    assert out == "hello"
