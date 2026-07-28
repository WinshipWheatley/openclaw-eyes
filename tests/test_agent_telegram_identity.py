"""Identity must be proven, not guessed. The Carter regression lives here.

On 2026-07-28 a message meant for Cassandra reached a real person named Carter
because the target was chosen by fuzzy display-name search. Every test below is an
attempt to make that happen again.
"""

from __future__ import annotations

import pytest

import agent_telegram_identity as ident

AGENTS = ("maestro", "chief", "cassandra", "niles", "guardian", "hermes")


def _bot(username: str, chat_id: str = "1001", display: str = "") -> dict:
    return {"username": username, "chat_id": chat_id, "type": "private",
            "is_bot": True, "display_name": display}


def _human(display: str, chat_id: str = "9001") -> dict:
    return {"username": "@" + display.lower(), "chat_id": chat_id, "type": "private",
            "is_bot": False, "display_name": display}


# ------------------------------------------------------------------- registry

def test_every_agent_has_exactly_one_registry_row() -> None:
    assert set(ident.AGENT_IDENTITIES) == set(AGENTS)
    seen: set[str] = set()
    for agent, row in ident.AGENT_IDENTITIES.items():
        assert row["username"].startswith("@"), agent
        assert row["role"].strip(), agent
        assert row["username"] not in seen, f"duplicate username for {agent}"
        seen.add(row["username"])


def test_an_unknown_agent_is_refused_not_defaulted() -> None:
    r = ident.resolve_agent_chat("carter", [_bot("@cassandrastudio_bot")])
    assert r.ok is False
    assert r.reason == ident.REFUSE_UNKNOWN_AGENT


# ------------------------------------------------------------- non-vacuity

def test_a_correctly_registered_agent_resolves() -> None:
    """If this fails, every refusal below proves nothing."""

    r = ident.resolve_agent_chat("cassandra", [_bot("@cassandrastudio_bot", "5150")])
    assert r.ok is True, r.to_dict()
    assert r.chat_id == "5150"
    assert r.username == "@cassandrastudio_bot"


# ---------------------------------------------------------------- refusals

def test_a_display_name_collision_with_a_human_contact_is_refused() -> None:
    """THE CARTER REGRESSION. A real person must never be selected as an agent."""

    r = ident.resolve_agent_chat("cassandra", [_human("Carter"), _human("Cass")])
    assert r.ok is False
    assert r.reason == ident.REFUSE_HUMAN_CONTACT
    assert r.chat_id == "", "a refusal must not hand back a chat id"


def test_targets_resolve_by_username_not_display_name() -> None:
    """Renaming the display name must not change resolution, in either direction."""

    renamed = _bot("@cassandrastudio_bot", "5150", display="Casandra bot")
    assert ident.resolve_agent_chat("cassandra", [renamed]).ok is True

    impostor = _bot("@some_other_bot", "6000", display="Cassandra")
    assert ident.resolve_agent_chat("cassandra", [impostor]).ok is False


def test_username_mismatch_between_registry_and_chat_refuses() -> None:
    """Catches `Casandra bot` masquerading as `@cassandrastudio_bot`."""

    r = ident.resolve_agent_chat("cassandra", [_bot("@casandrastudio_bot", "7000")])
    assert r.ok is False
    assert r.reason in {ident.REFUSE_NO_MATCH, ident.REFUSE_HUMAN_CONTACT}


def test_an_ambiguous_target_is_refused_not_guessed() -> None:
    dupes = [_bot("@cassandrastudio_bot", "1"), _bot("@cassandrastudio_bot", "2")]
    r = ident.resolve_agent_chat("cassandra", dupes)
    assert r.ok is False
    assert r.reason == ident.REFUSE_AMBIGUOUS
    assert "1" in r.detail and "2" in r.detail, "an ambiguous refusal must name the collisions"


def test_zero_candidates_is_refused() -> None:
    r = ident.resolve_agent_chat("cassandra", [])
    assert r.ok is False and r.chat_id == ""


def test_a_chat_without_a_username_can_never_be_selected() -> None:
    r = ident.resolve_agent_chat("cassandra", [{"chat_id": "42", "display_name": "Cassandra"}])
    assert r.ok is False
    assert r.reason == ident.REFUSE_NO_USERNAME


def test_a_bot_username_matching_but_flagged_human_is_refused() -> None:
    sneaky = {"username": "@cassandrastudio_bot", "chat_id": "8", "type": "private",
              "is_bot": False, "display_name": "Cassandra"}
    r = ident.resolve_agent_chat("cassandra", [sneaky])
    assert r.ok is False
    assert r.reason == ident.REFUSE_HUMAN_CONTACT


def test_there_is_no_best_match_path_at_all() -> None:
    """Adversarial: near-misses must all refuse, never rank."""

    for near in ("@openclaw_cassandra", "@cassandrastudio_bot2", "@openclawcassandrabot"):
        r = ident.resolve_agent_chat("cassandra", [_bot(near, "3")])
        assert r.ok is False, f"{near} was accepted as a match"


# ------------------------------------------------------------------- banner

@pytest.mark.parametrize("agent", AGENTS)
def test_every_agent_turn_carries_the_identity_banner(agent: str) -> None:
    banner = ident.identity_banner(agent)
    assert banner.startswith(agent.upper() + " / ")
    assert banner.endswith(ident.AGENT_IDENTITIES[agent]["username"])
    assert banner.count("/") >= 2


def test_a_banner_cannot_be_rendered_for_an_unregistered_agent() -> None:
    with pytest.raises(ident.IdentityError):
        ident.identity_banner("carter")


def test_the_banner_comes_from_the_registry_not_a_label() -> None:
    """The sidebar said Cassandra while the header said Casandra bot. The banner
    cannot drift that way because it IS the registry."""

    assert "@cassandrastudio_bot" in ident.identity_banner("cassandra")
    assert "@casandrastudio_bot" not in ident.identity_banner("cassandra")


# ---------------------------------------------------------------- interlock

def test_no_nonce_preview_is_emitted_while_identity_is_unproven() -> None:
    allowed, reason = ident.nonce_preview_allowed(env={})
    assert allowed is False
    assert ident.IDENTITY_PROOF_ENV in reason


def test_the_interlock_fails_closed_on_junk_values() -> None:
    for value in ("", "0", "false", "yes", "TRUE", "1 "):
        allowed, _ = ident.nonce_preview_allowed(env={ident.IDENTITY_PROOF_ENV: value})
        assert allowed is False, f"{value!r} opened the interlock"


def test_the_interlock_can_actually_open() -> None:
    """Non-vacuity: an interlock that never opens is broken, not safe."""

    allowed, reason = ident.nonce_preview_allowed(env={ident.IDENTITY_PROOF_ENV: "1"})
    assert allowed is True and reason == ""
