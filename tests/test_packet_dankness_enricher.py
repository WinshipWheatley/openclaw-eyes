"""Tests for the packet dankness enricher — the GROUNDED other half of the loop.

Pins the contract: refresh real generators, escalate the rest, refuse anything not
grounded-only, never fabricate. Uses a stub runner so no real generator is executed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import packet_dankness_enricher as enr


def _ok(cmd, **kw):
    return subprocess.CompletedProcess(cmd, 0, "", "")


def _fail(cmd, **kw):
    return subprocess.CompletedProcess(cmd, 1, "", "boom")


def test_refresh_known_stale_source(tmp_path):
    esc = tmp_path / "esc.json"
    payload = {"grounded_only": True, "gap": {
        "kind": "stale_source", "source_ref": "generated/read_models/orchestration_progress.json"}}
    out = enr.enrich_one(payload, runner=_ok, escalations_path=esc)
    assert out["outcome"] == "refreshed"
    assert "orchestration_progress" in out["generator"]
    assert not esc.exists()  # refreshed, not escalated


def test_unknown_stale_source_escalates(tmp_path):
    esc = tmp_path / "esc.json"
    payload = {"grounded_only": True, "gap": {
        "kind": "stale_source", "source_ref": "generated/read_models/finance_invoice_reconciliation.json"}}
    out = enr.enrich_one(payload, runner=_ok, escalations_path=esc)
    assert out["outcome"] == "escalated"
    recs = json.loads(esc.read_text())["escalations"]
    assert recs and "no known safe generator" in recs[0]["reason"]


def test_missing_fact_escalates_never_fabricates(tmp_path):
    esc = tmp_path / "esc.json"
    out = enr.enrich_one(
        {"grounded_only": True, "gap": {"kind": "missing_fact", "about": "calendar"}},
        runner=_ok, escalations_path=esc,
    )
    assert out["outcome"] == "escalated"  # flags it for the operator; invents nothing
    assert esc.exists()


def test_refuses_task_without_grounded_only_contract(tmp_path):
    out = enr.enrich_one({"gap": {"kind": "stale_source"}}, runner=_ok, escalations_path=tmp_path / "e.json")
    assert out["outcome"] == "refused"


def test_failed_generator_escalates_not_crashes(tmp_path):
    esc = tmp_path / "esc.json"
    payload = {"grounded_only": True, "gap": {
        "kind": "stale_source", "source_ref": "generated/read_models/work_board.json"}}
    out = enr.enrich_one(payload, runner=_fail, escalations_path=esc)
    assert out["outcome"] == "escalated"
    assert "exit 1" in json.loads(esc.read_text())["escalations"][0]["reason"]


def test_run_dankness_cycle_refreshes_and_escalates(tmp_path):
    esc = tmp_path / "esc.json"
    log = tmp_path / "log.json"
    stale = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    packet = {"facts": [{
        "topic": "progress", "label": "p", "value": "shipped milestones",
        "source_ref": "generated/read_models/orchestration_progress.json",
        "provenance": "generated_read_model", "freshness": {"as_of": stale},
    }]}
    res = enr.run_dankness_cycle(
        packet, "what is on my calendar", "maestro",
        runner=_ok, escalations_path=esc, score_log_path=log,
    )
    outcomes = {o["outcome"] for o in res["outcomes"]}
    assert "refreshed" in outcomes   # stale orchestration_progress -> refreshed
    assert "escalated" in outcomes   # calendar missing_fact -> escalated (not fabricated)
    logged = json.loads(log.read_text())
    assert logged["read_model_id"] == "packet_dankness_log"
    assert logged["records"][-1]["agent_id"] == "maestro"
    assert logged["records"][-1]["refreshed"] >= 1 and logged["records"][-1]["escalated"] >= 1


def test_ensure_dankness_read_models_creates_refreshable_object_payloads(tmp_path):
    esc = tmp_path / "packet_dankness_escalations.json"
    log = tmp_path / "packet_dankness_log.json"

    result = enr.ensure_packet_dankness_read_models(
        escalations_path=esc,
        score_log_path=log,
        generated_at="2026-07-07T00:00:00+00:00",
    )

    assert result["score_log_path"] == str(log)
    log_payload = json.loads(log.read_text(encoding="utf-8"))
    esc_payload = json.loads(esc.read_text(encoding="utf-8"))
    assert log_payload["schema_version"] == "packet_dankness_log_v0"
    assert esc_payload["schema_version"] == "packet_dankness_escalations_v0"
    assert log_payload["generated_at"] == "2026-07-07T00:00:00+00:00"
    assert esc_payload["generated_at"] == "2026-07-07T00:00:00+00:00"
    assert log_payload["records"] == []
    assert esc_payload["escalations"] == []
