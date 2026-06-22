"""Detector-wire tests for the control-plane cutover (Step 1).

Proves detect_and_emit_heal_task is DORMANT by default (emits nothing) and only
admits a heal task to the ledger when emission is explicitly enabled. This is the
reversible safety seam: wiring the detector into a live audit path changes nothing
in production until OPENCLAW_CONTROL_PLANE_EMIT is turned on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
POLISH_LOOP = ROOT / "polish_loop"
if str(POLISH_LOOP) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP))

from polish_loop.control_plane import ControlPlaneLedger
from polish_loop.pc4_heal_emitter import (
    control_plane_emit_enabled,
    detect_and_emit_heal_task,
)


def _truth_root(tmp_path: Path, *, online_count: int = 6) -> Path:
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    (root / "agent_presence.json").write_text(
        json.dumps(
            {
                "schema_version": "agent_presence_read_model_v0",
                "online_count": online_count,
                "agents": [
                    {"agent_id": f"agent_{i}", "actual_state": "online"}
                    for i in range(online_count)
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "schema_version": "openclaw_capability_index_v0",
                "generic_capabilities": [
                    {"capability_id": "status", "capability_status": "LIVE_IMPLEMENTED"},
                    {"capability_id": "proof", "capability_status": "LIVE_IMPLEMENTED"},
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "openclaw_change_sentinel.json").write_text(
        json.dumps({"generated_at": "2026-06-19T12:00:00+00:00"}) + "\n", encoding="utf-8"
    )
    return root


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(
        tmp_path / "control.sqlite3", status_view_path=tmp_path / "status.json"
    )


def test_emit_enabled_defaults_off(monkeypatch):
    monkeypatch.delenv("OPENCLAW_CONTROL_PLANE_EMIT", raising=False)
    assert control_plane_emit_enabled() is False
    for truthy in ("1", "true", "yes", "on", "ON", "True"):
        monkeypatch.setenv("OPENCLAW_CONTROL_PLANE_EMIT", truthy)
        assert control_plane_emit_enabled() is True
    for falsy in ("0", "", "off", "no", "false"):
        monkeypatch.setenv("OPENCLAW_CONTROL_PLANE_EMIT", falsy)
        assert control_plane_emit_enabled() is False


def test_failing_claim_is_dormant_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_CONTROL_PLANE_EMIT", raising=False)
    truth = _truth_root(tmp_path, online_count=6)
    ledger = _ledger(tmp_path)

    finding, task_id = detect_and_emit_heal_task(
        ledger,
        "maestro",
        "agent_presence_online_count",
        "7 agents online",
        read_model_root=truth,
        request_text="how many agents are online?",
    )
    # The claim genuinely fails...
    assert finding.verdict == "fail"
    assert finding.actual_value == 6
    # ...but emission is OFF by default, so NOTHING is admitted.
    assert task_id is None
    assert ledger.counts()["tasks"] == 0


def test_failing_claim_emits_when_enabled(tmp_path):
    truth = _truth_root(tmp_path, online_count=6)
    ledger = _ledger(tmp_path)

    finding, task_id = detect_and_emit_heal_task(
        ledger,
        "maestro",
        "agent_presence_online_count",
        "7 agents online",
        read_model_root=truth,
        request_text="how many agents are online?",
        enabled=True,
    )
    assert finding.verdict == "fail"
    assert task_id is not None
    task = ledger.get_task(task_id)
    assert task["status"] == "READY"
    assert task["source"] == "detector"
    assert task["type"] == "agent_heal"
    assert task["dispatchable"] == 1
    assert ledger.counts()["tasks"] == 1


def test_passing_claim_never_emits(tmp_path):
    truth = _truth_root(tmp_path, online_count=6)
    ledger = _ledger(tmp_path)

    finding, task_id = detect_and_emit_heal_task(
        ledger,
        "maestro",
        "agent_presence_online_count",
        "6 agents online",
        read_model_root=truth,
        request_text="how many agents are online?",
        enabled=True,  # even forced on, a passing claim emits nothing
    )
    assert finding.verdict == "pass"
    assert task_id is None
    assert ledger.counts()["tasks"] == 0
