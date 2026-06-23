"""Tests for the packet dankness critic — the score->queue half of the dankifier.

Pins the load-bearing safety property: scoring rewards real-source coverage, gaps are
grounded task-specs, and queueing is DEFAULT OFF (dormant until a supervised enable).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
POLISH = ROOT / "polish_loop"
if str(POLISH) not in sys.path:
    sys.path.insert(0, str(POLISH))

import packet_dankness_critic as crit
from polish_loop.control_plane import ControlPlaneLedger


def _fresh() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()


def _fact(topic, value, *, source="generated/read_models/x.json", prov="generated_read_model", as_of=None):
    return {
        "topic": topic,
        "label": topic,
        "value": value,
        "source_ref": source,
        "provenance": prov,
        "freshness": {"as_of": as_of or _fresh(), "source_ref": source},
    }


def _dank_packet(question_topic="progress"):
    return {
        "facts": [
            _fact("progress", "15 recent milestones on codex/stress-fixes"),
            _fact("finance", "Capital Hilton invoice $2k due Jul 1"),
            _fact("gig", "St Anne's gig $400 confirmed"),
            _fact("agent_presence", "5 of 6 agents online"),
        ]
    }


def test_empty_packet_scores_zero_and_flags_gap():
    score = crit.score_packet_dankness({"facts": []}, "where are we at")
    assert score.overall == 0.0
    assert score.fact_count == 0
    assert any(g["kind"] == "empty_packet" for g in score.gaps)


def test_dank_packet_scores_high_on_matching_question():
    score = crit.score_packet_dankness(_dank_packet(), "where are we at with progress")
    assert score.grounded == 1.0          # every fact sourced
    assert score.current == 1.0           # all fresh
    assert score.useful == 1.0            # 'progress' fact matches
    assert score.lane_rich == 1.0         # 4 distinct topics >= RICH_TARGET
    assert score.overall == 1.0
    assert score.gaps == ()


def test_missing_fact_gap_when_question_unmatched():
    score = crit.score_packet_dankness(_dank_packet(), "what is on my calendar tomorrow")
    assert score.useful == 0.0
    gaps = [g for g in score.gaps if g["kind"] == "missing_fact"]
    assert len(gaps) == 1
    assert "calendar" in gaps[0]["about"]


def test_stale_source_flagged_for_refresh():
    pkt = {"facts": [_fact("wiring", "cassandra wiring posture", source="generated/read_models/cw.json", as_of=_stale())]}
    score = crit.score_packet_dankness(pkt, "")
    assert score.current == 0.0
    stale = [g for g in score.gaps if g["kind"] == "stale_source"]
    assert len(stale) == 1
    assert stale[0]["source_ref"] == "generated/read_models/cw.json"


def test_emit_is_dormant_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_PACKET_DANKIFY_EMIT", raising=False)
    ledger = ControlPlaneLedger(tmp_path / "cp.sqlite3", status_view_path=tmp_path / "s.json")
    score = crit.score_packet_dankness(_dank_packet(), "what is on my calendar")
    assert score.gaps  # there IS a gap
    admitted = crit.emit_packet_enrich_tasks(ledger, score, agent_id="maestro", question="what is on my calendar")
    assert admitted == []                       # but queueing is OFF by default
    assert ledger.counts()["tasks"] == 0


def test_emit_when_enabled_queues_grounded_packet_enrich_tasks(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "cp.sqlite3", status_view_path=tmp_path / "s.json")
    score = crit.score_packet_dankness(_dank_packet(), "what is on my calendar tomorrow")
    admitted = crit.emit_packet_enrich_tasks(
        ledger, score, agent_id="maestro", question="what is on my calendar tomorrow", enabled=True
    )
    assert len(admitted) == len(score.gaps) >= 1
    task = ledger.get_task(admitted[0])
    assert task["type"] == "packet_enrich"
    assert task["source"] == "detector"
    assert task["status"] == "READY"
    # the load-bearing contract travels with the task
    assert task["payload"]["grounded_only"] is True


def test_no_question_terms_is_neutral_not_penalized():
    score = crit.score_packet_dankness(_dank_packet(), "")
    assert score.useful == 1.0  # can't assess relevance with no question -> neutral, no missing_fact gap
    assert not any(g["kind"] == "missing_fact" for g in score.gaps)
