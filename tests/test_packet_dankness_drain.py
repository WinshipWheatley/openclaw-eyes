"""Tests for the autonomous dankifier drain.

Pins: it processes only packet_enrich tasks, refreshes via a (stubbed) generator or escalates,
marks them DONE, respects the max_tasks bound, and never touches other task types.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "polish_loop") not in sys.path:
    sys.path.insert(0, str(ROOT / "polish_loop"))

import packet_dankness_drain as drain
from polish_loop.control_plane import ControlPlaneLedger


def _ok(cmd, **kw):
    return subprocess.CompletedProcess(cmd, 0, "", "")


def _ledger(tmp_path):
    return ControlPlaneLedger(tmp_path / "cp.sqlite3", status_view_path=tmp_path / "s.json")


def _enrich_task(ledger, source_ref, kind="stale_source"):
    return ledger.admit_task(
        source="detector", task_type="packet_enrich", requested_status="READY",
        payload={"gap": {"kind": kind, "source_ref": source_ref}, "grounded_only": True},
    )


def test_drain_refreshes_known_source_and_marks_done(tmp_path):
    ledger = _ledger(tmp_path)
    tid = _enrich_task(ledger, "generated/read_models/orchestration_progress.json")
    out = drain.drain_packet_enrich_queue(ledger, runner=_ok, escalations_path=tmp_path / "esc.json")
    assert len(out) == 1 and out[0]["outcome"] == "refreshed"
    assert ledger.get_task(tid)["status"] == "DONE"


def test_drain_escalates_unknown_source_and_marks_done(tmp_path):
    ledger = _ledger(tmp_path)
    tid = _enrich_task(ledger, "generated/read_models/finance_invoice_reconciliation.json")
    out = drain.drain_packet_enrich_queue(ledger, runner=_ok, escalations_path=tmp_path / "esc.json")
    assert out[0]["outcome"] == "escalated"
    assert ledger.get_task(tid)["status"] == "DONE"


def test_drain_ignores_non_packet_enrich_tasks(tmp_path):
    ledger = _ledger(tmp_path)
    heal = ledger.admit_task(
        source="detector", task_type="agent_heal", requested_status="READY",
        payload={"gap": "x", "grounded_only": True},
    )
    out = drain.drain_packet_enrich_queue(ledger, runner=_ok, escalations_path=tmp_path / "esc.json")
    assert out == []  # the heal task is left strictly alone
    assert ledger.get_task(heal)["status"] == "READY"


def test_drain_respects_max_tasks_bound(tmp_path):
    ledger = _ledger(tmp_path)
    for i in range(5):
        _enrich_task(ledger, f"generated/read_models/x{i}.json")
    out = drain.drain_packet_enrich_queue(ledger, max_tasks=2, runner=_ok, escalations_path=tmp_path / "esc.json")
    assert len(out) == 2  # bounded — can't run away
