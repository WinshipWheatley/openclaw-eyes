"""A dead credential must be loud, and must not be quietly worked around."""

from __future__ import annotations

import google_credential_health as health


def _probe(response):
    return lambda agent, capability, params: response


def test_a_revoked_token_is_reported_as_revoked_not_as_no_mail() -> None:
    """The failure that started this: presence is not health."""

    result = health.check_google_credentials(
        probe=_probe({"ok": False, "error": "invalid_grant: Token has been expired or revoked."})
    )

    assert result["status"] == health.STATUS_EXPIRED
    assert not result["healthy"]
    assert health.REAUTH_COMMAND in result["remedy"]


def test_the_blast_radius_is_named_not_left_to_be_discovered() -> None:
    """An armed money-adjacent send sits behind this token."""

    result = health.check_google_credentials(probe=_probe({"ok": False, "error": "invalid_grant"}))

    at_risk = {row["what"] for row in result["downstream_at_risk"]}
    assert "LAMD monthly auto-send" in at_risk
    assert any("money-adjacent" in row["stake"] for row in result["downstream_at_risk"])


def test_no_agent_claims_it_can_fix_this() -> None:
    """Issuing a credential is the operator's act. Saying otherwise invites a bypass."""

    result = health.check_google_credentials(probe=_probe({"ok": False, "error": "invalid_grant"}))

    assert result["agent_can_fix"] is False
    assert result["operator_action_required"] is True
    assert "bypass" in result["agent_cannot_fix_because"]


def test_healthy_access_reports_clean_and_lists_nothing_at_risk() -> None:
    result = health.check_google_credentials(probe=_probe({"ok": True, "data": [], "error": ""}))

    assert result["status"] == health.STATUS_OK
    assert result["healthy"]
    assert result["downstream_at_risk"] == []


def test_missing_libraries_are_not_confused_with_a_revoked_token() -> None:
    """Different wall, different remedy. Telling the operator to re-auth would waste his time."""

    result = health.check_google_credentials(
        probe=_probe({"ok": False, "error": "missing Gmail broker runtime dependencies: googleapiclient.discovery"})
    )

    assert result["status"] == health.STATUS_DEPS_MISSING
    assert health.REAUTH_COMMAND not in result["remedy"]


def test_an_unrecognised_failure_is_unknown_never_ok() -> None:
    """Silence-as-success is the defect this whole module exists to prevent."""

    result = health.check_google_credentials(probe=_probe({"ok": False, "error": "kettle boiled over"}))

    assert result["status"] == health.STATUS_UNKNOWN
    assert not result["healthy"]


def test_a_probe_that_throws_is_a_failed_probe_not_a_pass() -> None:
    def _boom(agent, capability, params):
        raise RuntimeError("network gone")

    result = health.check_google_credentials(probe=_boom)

    assert not result["healthy"]
    assert "network gone" in result["detail"]


def test_the_probe_uses_a_class_a_capability_so_it_never_prompts() -> None:
    """A health check that needs approval is a health check nobody runs."""

    from google_access_policy import get_class

    assert get_class(health.PROBE_AGENT, health.PROBE_CAPABILITY) == "A"


def test_the_remedy_names_the_command_that_actually_works_on_this_host() -> None:
    """A remedy is read only when things are already broken. Wrong = worse than none.

    Both halves of the old string were wrong and cost real time on 2026-07-26:
    `python3` lacks the Google client libraries (the runtime is chief_env, and the
    system interpreter misreports a live token as DEPS_MISSING), and `--auth` runs
    the OAuth callback server inside WSL where the Windows browser cannot reach it,
    so consent succeeds and no token is written. `--auth-manual` is the WSL2 path.
    """
    assert health.REAUTH_COMMAND == (
        "/home/openclaw/chief_env/bin/python google_access_broker.py --auth-manual"
    )
    # The bare flag must not survive: "--auth-manual".startswith("--auth") means a
    # regression to the broken flag would otherwise pass a naive substring check.
    assert "--auth-manual" in health.REAUTH_COMMAND
    assert not health.REAUTH_COMMAND.startswith("python3 ")


def test_every_actionable_remedy_hands_over_the_working_command() -> None:
    """No remedy may name a different, wrong re-auth incantation of its own."""

    for status in (health.STATUS_EXPIRED, health.STATUS_NOT_CONFIGURED):
        remedy = health._remedy(status)
        assert health.REAUTH_COMMAND in remedy, status
        # No stale bare "--auth" outside the canonical command.
        assert "--auth" not in remedy.replace(health.REAUTH_COMMAND, ""), status


def test_the_remedy_says_it_needs_a_real_terminal() -> None:
    """The agent-shell EOFError trap: it must be written down, not rediscovered."""

    remedy = health._remedy(health.STATUS_EXPIRED)
    assert "terminal" in remedy.lower()
    assert "PKCE" in remedy or "start over" in remedy.lower()
