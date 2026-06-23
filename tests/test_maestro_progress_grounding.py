"""Progress grounding: the Maestro packet must surface real 'where are we at' data.

Baseline gap (BASELINE-MEASUREMENT-2026-06-22): "what's the progress" returned general
doctrine only, ZERO progress data. This pins the fix -- orchestration_progress.json
(git-sourced shipped milestones) becomes a grounded 'progress' fact in the packet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import maestro_context_packet as mcp


def _write(root: Path, name: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _presence(root: Path) -> None:
    _write(
        root,
        "agent_presence.json",
        {
            "schema_version": "agent_presence_read_model_v0",
            "online_count": 1,
            "agents": [{"agent_id": "maestro", "actual_state": "online"}],
        },
    )


def test_progress_read_model_surfaces_in_packet(tmp_path):
    root = tmp_path / "read_models"
    _presence(root)
    _write(
        root,
        "orchestration_progress.json",
        {
            "schema_version": "orchestration_progress_read_model_v0",
            "generated_at": "2026-06-22T20:00:00+00:00",
            "branch": "codex/stress-fixes",
            "shipped_milestones": [
                {"commit": "abc123", "at": "2026-06-22T19:00:00+00:00",
                 "summary": "feat(cutover-1): control-plane detector wire"},
                {"commit": "def456", "at": "2026-06-22T18:00:00+00:00",
                 "summary": "chore(prune-fin): remove dead fin actor"},
            ],
            "shipped_count": 2,
        },
    )
    pkt = mcp.build_maestro_context_packet(
        question="where are we at", read_model_root=root, require_real_truth=False
    )
    prog = [f for f in pkt.get("facts", []) if f.get("topic") == "progress"]
    assert len(prog) == 1
    fact = prog[0]
    assert "2 recent" in fact["value"]
    assert "control-plane detector wire" in fact["value"]
    assert fact["source_ref"] == "generated/read_models/orchestration_progress.json"
    assert fact["freshness"].get("as_of")  # grounded + dated


def test_no_progress_read_model_means_no_progress_fact(tmp_path):
    root = tmp_path / "read_models"
    _presence(root)  # packet has presence but no progress read-model
    pkt = mcp.build_maestro_context_packet(
        question="where are we at", read_model_root=root, require_real_truth=False
    )
    assert [f for f in pkt.get("facts", []) if f.get("topic") == "progress"] == []
