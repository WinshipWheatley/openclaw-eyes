"""Tests for the Maestro bare-status doctrine (task 143, CLASS #4).

Live evidence (pass-1): "status?" got staged as diagnostic_package_gate_smoke instead of a
terse, current, scoped answer -- the status_capability_readback matcher requires a co-occurring
qualifier term that a bare "status?" lacks. These tests pin the fix: a bare status ask is
answered deterministically (no model call, no staging) from live read-models, and any stale
source is flagged rather than silently presented as current.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import maestro_cassandra_responder as maestro


@pytest.fixture(autouse=True)
def _freeze_captured_status_fixture_clock(monkeypatch):
    """The July 9 production-shape snapshots must not silently age in CI.

    Freshness behavior remains production code: the captured fixtures are
    evaluated against the date on which they were recorded, while the explicit
    stale/undated cases below still exercise the fail-closed gate.
    """
    import read_model_freshness_audit

    monkeypatch.setattr(read_model_freshness_audit, "_today", lambda: date(2026, 7, 9))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_fresh_status_read_models(tmp_path: Path, *, helm_generated_at: str = "2026-07-08T00:00:00+00:00") -> Path:
    root = tmp_path / "read_models"
    _write_json(
        root / "helm_operator_attention_package.json",
        {"generated_at": helm_generated_at, "primary_cards": [{"id": "a"}, {"id": "b"}]},
    )
    _write_json(
        root / "receivables_month_bounded.json",
        {
            "generated_at": "2026-07-08T20:18:32+00:00",
            "summary": {"open_minor_units_by_client": {"live_arts_md": 109500, "st_annes": 0}},
        },
    )
    _write_json(
        root / "agent_presence.json",
        {"generated_at": "2026-07-09T14:54:32+00:00", "online_count": 4, "agent_count": 6},
    )
    return root


class TestIsBareStatusQuery:
    def test_bare_word_matches(self):
        assert maestro._is_bare_status_query("status") is True

    def test_bare_word_with_question_mark_matches(self):
        assert maestro._is_bare_status_query("status?") is True

    def test_whats_the_status_matches(self):
        assert maestro._is_bare_status_query("What's the status?") is True

    def test_longer_capability_question_does_not_match(self):
        """Distinct from status_capability_readback -- must not swallow that intent."""
        assert maestro._is_bare_status_query("Hermes, what's going on? What can you do now?") is False

    def test_unrelated_text_does_not_match(self):
        assert maestro._is_bare_status_query("send $500 to Bob") is False

    def test_empty_text_does_not_match(self):
        assert maestro._is_bare_status_query("") is False


class TestBuildMaestroBareStatusAnswer:
    def test_all_fresh_sources_produce_three_lines(self, tmp_path):
        root = _seed_fresh_status_read_models(tmp_path)

        answer = maestro.build_maestro_bare_status_answer(session={"read_model_root": root.as_posix()})

        assert "Plate: 2 headline items." in answer["plain_summary"]
        assert "Money: 1 client with open amounts." in answer["plain_summary"]
        assert "Fleet: 4/6 agents online." in answer["plain_summary"]
        assert "(stale" not in answer["plain_summary"]
        assert answer["machine_proof"]["maestro_bare_status_readback_performed"] is True
        assert answer["machine_proof"]["external_llm_invoked"] is False
        assert answer["machine_proof"]["workflow_package_staged"] is False
        assert len(answer["machine_proof"]["source_truth_refs"]) == 3

    def test_stale_source_is_excluded_and_flagged_not_presented_as_current(self, tmp_path):
        """June-orientation-as-now failure class: a 44-day-stale plate source must not be
        silently rendered as current."""
        root = _seed_fresh_status_read_models(tmp_path, helm_generated_at="2026-05-26T00:00:00+00:00")

        answer = maestro.build_maestro_bare_status_answer(session={"read_model_root": root.as_posix()})

        assert "Plate:" not in answer["plain_summary"]
        assert "Money: 1 client with open amounts." in answer["plain_summary"]
        assert "Fleet: 4/6 agents online." in answer["plain_summary"]
        assert "helm_operator_attention_package.json" in answer["plain_summary"]
        assert "helm_operator_attention_package.json" in answer["machine_proof"]["stale_sources_excluded"]
        assert "helm_operator_attention_package.json" not in " ".join(answer["machine_proof"]["source_truth_refs"])

    def test_undated_source_is_unverifiable_and_excluded_not_presented_as_current(self, tmp_path):
        root = _seed_fresh_status_read_models(tmp_path)
        _write_json(
            root / "helm_operator_attention_package.json",
            {"primary_cards": [{"id": "a"}, {"id": "b"}]},
        )

        answer = maestro.build_maestro_bare_status_answer(session={"read_model_root": root.as_posix()})

        assert "Plate:" not in answer["plain_summary"]
        assert "Money: 1 client with open amounts." in answer["plain_summary"]
        assert "Fleet: 4/6 agents online." in answer["plain_summary"]
        assert "helm_operator_attention_package.json" in answer["plain_summary"]
        assert "helm_operator_attention_package.json" in answer["machine_proof"]["stale_sources_excluded"]
        assert "helm_operator_attention_package.json" in answer["machine_proof"]["unverifiable_sources_excluded"]
        assert "helm_operator_attention_package.json" not in " ".join(answer["machine_proof"]["source_truth_refs"])

    def test_missing_read_models_produces_honest_no_data_answer(self, tmp_path):
        root = tmp_path / "empty_read_models"
        root.mkdir()

        answer = maestro.build_maestro_bare_status_answer(session={"read_model_root": root.as_posix()})

        assert "don't have current status data" in answer["plain_summary"]
        assert answer["machine_proof"]["source_truth_refs"] == ()


class TestAnswerFrontdoorChatBareStatus:
    def test_bare_status_answered_deterministically_without_handle(self, tmp_path):
        root = _seed_fresh_status_read_models(tmp_path)

        def forbidden_handle(_text, _session=None):
            raise AssertionError("bare status must not call cassandra_brain.handle")

        result = maestro.answer_frontdoor_chat(
            "status?",
            session={"read_model_root": root.as_posix()},
            handle_fn=forbidden_handle,
        )

        assert result.status == "ANSWER_READY"
        assert result.intent_class == "maestro_bare_status_readback"
        assert result.allowed_to_call_handle is False
        assert "Fleet: 4/6 agents online." in result.plain_summary
        assert result.machine_proof["maestro_bare_status_readback_performed"] is True
        assert result.machine_proof["external_llm_invoked"] is False

    def test_bare_status_never_reaches_diagnostic_gate_smoke_staging(self, tmp_path):
        """Live pass-1 finding: 'status?' was staged as diagnostic_package_gate_smoke.
        answer_frontdoor_chat must now return ANSWER_READY, never ROUTE_TO_STAGING, for a
        surface mismatch that would otherwise fall through to the smoke-staging path."""
        root = _seed_fresh_status_read_models(tmp_path)

        result = maestro.answer_frontdoor_chat(
            "status?",
            session={"read_model_root": root.as_posix()},
            source_surface="mission_control",
        )

        assert result.status == "ANSWER_READY"
        assert result.intent_class == "maestro_bare_status_readback"

    def test_status_capability_longer_phrasing_still_routes_to_its_own_intent(self, tmp_path):
        """The bare-status tap must not swallow the existing richer capability readback."""
        root = tmp_path / "truthful_status_read_models"
        root.mkdir()
        _write_json(
            root / "openclaw_capability_index.json",
            {
                "generated_at": "2026-07-09T14:54:32+00:00",
                "generic_capabilities": [{"capability_id": "request_processing", "capability_name": "Bounded request processor", "capability_status": "LIVE_IMPLEMENTED"}],
            },
        )
        _write_json(
            root / "agent_presence.json",
            {
                "generated_at": "2026-07-09T14:54:32+00:00",
                "agents": [{"agent_id": "maestro", "actual_state": "online"}],
            },
        )

        result = maestro.answer_frontdoor_chat(
            "Hermes, what's going on? What can you do now?",
            session={"read_model_root": root.as_posix()},
        )

        assert result.intent_class == "status_capability_readback"
