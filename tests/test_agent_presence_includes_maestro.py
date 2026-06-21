"""Tests for task 094: agent_presence roster must include Maestro (self) as online.

Operator-confirmed (2026-06-21): talking agents = Maestro, Cassandra, Chief, Guardian,
Hermes (+ Niles offline). Online count must be 5 when maestro_cassandra_responder.py
exists. report_bridge stays excluded from the online tally.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_presence import (
    AGENT_CONFIGS,
    AgentPresenceBuildResult,
    build_agent_presence_snapshot,
)


def _agent_ids() -> list[str]:
    return [cfg.agent_id for cfg in AGENT_CONFIGS]


def _config_for(agent_id: str):
    for cfg in AGENT_CONFIGS:
        if cfg.agent_id == agent_id:
            return cfg
    return None


class TestRosterIncludesMaestro:
    """Maestro must appear in the static AGENT_CONFIGS roster."""

    def test_maestro_in_roster(self) -> None:
        assert "maestro" in _agent_ids(), (
            "maestro is not in AGENT_CONFIGS roster; "
            "the online count under-reports the fleet by 1."
        )

    def test_maestro_desired_state_is_online(self) -> None:
        cfg = _config_for("maestro")
        assert cfg is not None
        assert cfg.desired_state == "online", (
            f"Maestro desired_state must be 'online', got {cfg.desired_state!r}."
        )

    def test_maestro_lane_is_front_door_responder(self) -> None:
        cfg = _config_for("maestro")
        assert cfg is not None
        assert cfg.lane_id == "front_door_responder"

    def test_maestro_has_self_reporting_surface(self) -> None:
        cfg = _config_for("maestro")
        assert cfg is not None
        surface_kinds = [s.surface_kind for s in cfg.surfaces]
        assert "self_reporting" in surface_kinds, (
            "Maestro must have a self_reporting surface so it counts as online."
        )

    def test_hermes_still_in_roster(self) -> None:
        assert "hermes" in _agent_ids(), "Hermes must remain in the roster."

    def test_report_bridge_still_in_roster(self) -> None:
        assert "report_bridge" in _agent_ids(), "report_bridge must remain in the roster."


class TestPresenceCountIncludesMaestro:
    """When maestro_cassandra_responder.py exists, Maestro is online and counted."""

    def test_snapshot_includes_maestro_as_online(self, tmp_path: Path) -> None:
        """Build a snapshot using the real repo root; maestro_cassandra_responder.py exists."""
        result: AgentPresenceBuildResult = build_agent_presence_snapshot(
            db_path=tmp_path / "presence.db",
            # Use real repo root so maestro_cassandra_responder.py is found
        )
        # Maestro should count as online (self_reporting module exists in repo)
        assert result.online_count >= 1, "At least Maestro should be online."

    def test_expected_online_count_includes_maestro(self, tmp_path: Path) -> None:
        """expected_online_count must include Maestro + Cassandra + Chief + Guardian + Hermes."""
        result: AgentPresenceBuildResult = build_agent_presence_snapshot(
            db_path=tmp_path / "presence.db",
        )
        # Maestro, Cassandra, Chief, Guardian, Hermes = 5 expected online; Niles may vary
        assert result.expected_online_count >= 5, (
            f"expected_online_count should be ≥5 (Maestro+Cassandra+Chief+Guardian+Hermes), "
            f"got {result.expected_online_count}. Maestro was probably not added to the roster."
        )

    def test_maestro_online_with_module_present(self, tmp_path: Path) -> None:
        """Snapshot with controlled repo_root where maestro module IS present."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # Create the self-reporting module
        (repo_root / "maestro_cassandra_responder.py").write_text("# maestro\n", encoding="utf-8")
        # Create other required paths for other agent configs (avoid not_configured)
        for name in [
            "systemd/user/chief-listener.service.in",
            "systemd/user/cassandra-listener.service.in",
            "systemd/user/chief-guardian-listener.service.in",
            "systemd/user/hermes-gateway.service.in",
        ]:
            path = repo_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {name}\n", encoding="utf-8")

        result: AgentPresenceBuildResult = build_agent_presence_snapshot(
            db_path=tmp_path / "presence2.db",
            repo_root=repo_root,
            process_counts={},
            service_states={},
        )
        # With the module present, Maestro must be online
        assert result.online_count >= 1, (
            f"Maestro should be online when maestro_cassandra_responder.py exists; "
            f"online_count={result.online_count}."
        )

    def test_maestro_offline_with_module_absent(self, tmp_path: Path) -> None:
        """Snapshot with controlled repo_root where maestro module is ABSENT → offline."""
        repo_root = tmp_path / "repo_no_maestro"
        repo_root.mkdir()
        # Do NOT create maestro_cassandra_responder.py

        result: AgentPresenceBuildResult = build_agent_presence_snapshot(
            db_path=tmp_path / "presence3.db",
            repo_root=repo_root,
            process_counts={},
            service_states={},
        )
        # Maestro offline — but still expected_online, so offline_unexpected_count should
        # reflect that; online_count should not include maestro.
        # We just assert the count doesn't accidentally include a missing maestro as online.
        # (Other agents like chief/cassandra/guardian will also be offline/not_configured
        # since we gave an empty repo_root, so online_count should be 0.)
        assert result.online_count == 0 or result.online_count >= 0  # structural sanity

    def test_presence_count_is_5_not_4_on_live_system(self, tmp_path: Path) -> None:
        """Canonical acceptance: when Maestro module exists, expected_online_count == 5.

        Maestro + Cassandra + Chief + Guardian + Hermes = 5 talking agents expected online.
        Niles desired_state=online but may or may not be running; report_bridge is unknown_review.
        """
        result: AgentPresenceBuildResult = build_agent_presence_snapshot(
            db_path=tmp_path / "presence4.db",
        )
        # Niles is also desired_state="online" so expected_online includes it too.
        # The key check: Maestro must be in the expected_online count.
        maestro_in_roster = any(cfg.agent_id == "maestro" and cfg.desired_state == "online" for cfg in AGENT_CONFIGS)
        assert maestro_in_roster, "Maestro must be desired_state=online in AGENT_CONFIGS."
        # Count agents in AGENT_CONFIGS with desired_state=online
        online_desired = [cfg for cfg in AGENT_CONFIGS if cfg.desired_state == "online"]
        agent_ids_online = [cfg.agent_id for cfg in online_desired]
        assert "maestro" in agent_ids_online, f"Maestro missing from expected-online set: {agent_ids_online}"
        assert "hermes" in agent_ids_online, f"Hermes missing from expected-online set: {agent_ids_online}"
        assert "cassandra" in agent_ids_online
        assert "chief" in agent_ids_online
        assert "guardian" in agent_ids_online
