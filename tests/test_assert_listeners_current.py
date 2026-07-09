"""Tests for the task-149 deploy-hygiene assertion script.

These tests exercise ONLY the pure logic (find_stale_units, _is_target_unit,
_parse_systemd_timestamp) with injected/mocked data -- they must NEVER shell out to the
real systemctl or restart a real service.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.assert_listeners_current as als


class TestIsTargetUnit:
    def test_listener_units_match(self):
        assert als._is_target_unit("niles-listener.service") is True
        assert als._is_target_unit("cassandra-listener.service") is True
        assert als._is_target_unit("chief-guardian-listener.service") is True

    def test_gateway_units_match(self):
        assert als._is_target_unit("hermes-gateway.service") is True
        assert als._is_target_unit("openclaw-gateway.service") is True

    def test_processor_unit_matches(self):
        assert als._is_target_unit("openclaw-request-response.service") is True

    def test_unrelated_units_do_not_match(self):
        assert als._is_target_unit("chief-memory-worker.service") is False
        assert als._is_target_unit("kokoro-voice.service") is False
        assert als._is_target_unit("openclaw-morning-brief.service") is False


class TestParseSystemdTimestamp:
    def test_parses_standard_format(self):
        assert als._parse_systemd_timestamp("Wed 2026-07-09 11:50:23 EDT") == datetime(2026, 7, 9, 11, 50, 23)

    def test_na_sentinel_returns_none(self):
        assert als._parse_systemd_timestamp("n/a") is None

    def test_empty_string_returns_none(self):
        assert als._parse_systemd_timestamp("") is None

    def test_unparseable_value_returns_none(self):
        assert als._parse_systemd_timestamp("garbage") is None


class TestFindStaleUnits:
    def test_unit_restarted_after_deploy_is_current(self):
        deploy_ts = datetime(2026, 7, 9, 12, 0, 0)
        lookup = lambda unit: datetime(2026, 7, 9, 12, 5, 0)

        stale = als.find_stale_units(deploy_ts, ["niles-listener.service"], timestamp_lookup=lookup)

        assert stale == []

    def test_unit_restarted_before_deploy_is_stale(self):
        """The exact root-cause scenario: niles-listener.service ran a pre-deploy binary
        through the deploy window because it was never actually restarted."""
        deploy_ts = datetime(2026, 7, 9, 12, 0, 0)
        lookup = lambda unit: datetime(2026, 6, 30, 9, 0, 0)

        stale = als.find_stale_units(deploy_ts, ["niles-listener.service"], timestamp_lookup=lookup)

        assert stale == ["niles-listener.service"]

    def test_unit_with_no_timestamp_is_treated_as_stale(self):
        deploy_ts = datetime(2026, 7, 9, 12, 0, 0)
        lookup = lambda unit: None

        stale = als.find_stale_units(deploy_ts, ["some-unit.service"], timestamp_lookup=lookup)

        assert stale == ["some-unit.service"]

    def test_mixed_fleet_reports_only_the_stale_ones(self):
        deploy_ts = datetime(2026, 7, 9, 12, 0, 0)
        timestamps = {
            "niles-listener.service": datetime(2026, 6, 30, 9, 0, 0),  # stale
            "chief-listener.service": datetime(2026, 7, 9, 12, 1, 0),  # current
            "maestro-listener.service": datetime(2026, 7, 9, 11, 59, 0),  # stale
        }
        lookup = lambda unit: timestamps[unit]

        stale = als.find_stale_units(deploy_ts, list(timestamps.keys()), timestamp_lookup=lookup)

        assert set(stale) == {"niles-listener.service", "maestro-listener.service"}

    def test_exact_boundary_timestamp_counts_as_current(self):
        deploy_ts = datetime(2026, 7, 9, 12, 0, 0)
        lookup = lambda unit: deploy_ts

        stale = als.find_stale_units(deploy_ts, ["some-unit.service"], timestamp_lookup=lookup)

        assert stale == []


class TestMainNeverCallsRealSystemctl:
    def test_main_uses_injected_discovery_not_real_systemctl(self, monkeypatch, capsys):
        """Sanity guard: main() must route through discover_target_units/find_stale_units,
        which this test replaces -- proving no real subprocess call is required to reach
        a correct exit code."""
        monkeypatch.setattr(als, "discover_target_units", lambda: ["fake-listener.service"])
        monkeypatch.setattr(
            als, "find_stale_units", lambda deploy_ts, units, **kwargs: []
        )

        exit_code = als.main(["--deploy-timestamp", "2026-07-09T12:00:00"])

        assert exit_code == 0
        assert "All 1 listener/gateway/processor unit(s) are current" in capsys.readouterr().out

    def test_main_reports_stale_units_and_nonzero_exit(self, monkeypatch, capsys):
        monkeypatch.setattr(als, "discover_target_units", lambda: ["fake-listener.service"])
        monkeypatch.setattr(
            als, "find_stale_units", lambda deploy_ts, units, **kwargs: ["fake-listener.service"]
        )

        exit_code = als.main(["--deploy-timestamp", "2026-07-09T12:00:00"])

        assert exit_code == 1
        assert "fake-listener.service" in capsys.readouterr().err
