"""Tests for the self-healing drain — supervised proof + the load-bearing safety.

Pins: a bad-claim heal flows to a verified DONE *candidate* (never deployed), real code-gen is
off by default, only agent_heal tasks are touched, and the max_tasks bound holds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "polish_loop") not in sys.path:
    sys.path.insert(0, str(ROOT / "polish_loop"))

import heal_drain as hd
from polish_loop.control_plane import ControlPlaneLedger
from polish_loop.answer_auditor import check_agent_claim
from polish_loop.pc4_heal_emitter import emit_heal_task


def _ledger(tmp_path):
    return ControlPlaneLedger(tmp_path / "cp.sqlite3", status_view_path=tmp_path / "s.json")


def _truth_root(tmp_path: Path, *, online: int = 6) -> Path:
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    (root / "agent_presence.json").write_text(json.dumps({
        "schema_version": "agent_presence_read_model_v0", "online_count": online,
        "agents": [{"agent_id": f"a{i}", "actual_state": "online"} for i in range(online)],
    }, sort_keys=True), encoding="utf-8")
    (root / "openclaw_capability_index.json").write_text(json.dumps({
        "schema_version": "openclaw_capability_index_v0",
        "generic_capabilities": [{"capability_id": "status", "capability_status": "LIVE_IMPLEMENTED"}],
    }, sort_keys=True), encoding="utf-8")
    (root / "openclaw_change_sentinel.json").write_text(json.dumps({"generated_at": "2026-06-19T12:00:00+00:00"}), encoding="utf-8")
    return root


def _heal_task(ledger, tmp_path, *, bad="7 agents online"):
    truth = _truth_root(tmp_path)
    finding = check_agent_claim("maestro", "agent_presence_online_count", bad, read_model_root=truth)
    return emit_heal_task(
        ledger, finding, request_text="how many agents are online?", answer_text=bad,
        repro_prompts=("how many agents are online?",),
        acceptance_path=ROOT / "tests" / "test_pc4_self_healing.py",
    )


def test_heal_drain_controlled_yields_done_candidate_never_deployed(tmp_path):
    ledger = _ledger(tmp_path)
    tid = _heal_task(ledger, tmp_path)
    out = hd.drain_agent_heal_queue(ledger, trusted_repo=ROOT)  # controlled (real_builder off)
    assert len(out) == 1
    assert out[0]["status"] == "DONE"          # candidate verified against the gate
    assert out[0]["deployed"] is False         # NEVER deployed — prod stays the operator's keyboard
    assert out[0]["real_builder"] is False     # no autonomous code-gen by default
    assert ledger.get_task(tid)["status"] == "DONE"


def test_heal_drain_ignores_packet_enrich(tmp_path):
    ledger = _ledger(tmp_path)
    pe = ledger.admit_task(source="detector", task_type="packet_enrich", requested_status="READY",
                           payload={"gap": "x", "grounded_only": True})
    out = hd.drain_agent_heal_queue(ledger)
    assert out == []                            # the dankifier's tasks are strictly off-limits
    assert ledger.get_task(pe)["status"] == "READY"


def test_heal_drain_respects_max_tasks_bound(tmp_path):
    ledger = _ledger(tmp_path)
    for i in range(4):
        ledger.admit_task(source="detector", task_type="agent_heal", requested_status="READY",
                          payload={"i": i, "rollback_no_send": True}, max_attempts=1)
    out = hd.drain_agent_heal_queue(ledger, max_tasks=2, trusted_repo=ROOT)
    assert len(out) == 2                        # bounded — can't run away on a fleet of heals


def test_real_builder_is_off_by_default(monkeypatch):
    monkeypatch.delenv("OPENCLAW_HEAL_REAL_BUILDER", raising=False)
    assert hd.heal_real_builder_enabled() is False
    monkeypatch.setenv("OPENCLAW_HEAL_REAL_BUILDER", "1")
    assert hd.heal_real_builder_enabled() is True
