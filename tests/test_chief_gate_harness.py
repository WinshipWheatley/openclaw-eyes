from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_gate_harness as harness


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_live_polish_orchestrator_is_keep():
    verdict = harness.evaluate_candidate(ROOT, "polish_loop/orchestrator.py")

    assert verdict["verdict"] == "KEEP"
    assert "protected_live_path" in verdict["reasons"]


def test_dead_file_is_quarantine_approved(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "dead_tool.py", "VALUE = 1\n")

    verdict = harness.evaluate_candidate(repo, "dead_tool.py")

    assert verdict["verdict"] == "QUARANTINE-APPROVED"
    assert verdict["verification"]["rg_hit_count"] == 0
    assert verdict["quarantine_plan"]["snapshot_first"] is False
    assert verdict["quarantine_plan"]["delete_performed"] is False


def test_constant_inside_served_module_needs_winship(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "served_module.py", "PROVIDER_FAMILIES = ('LOCAL',)\n")
    _write(
        repo / "systemd" / "user" / "served.service.in",
        "ExecStart=/usr/bin/env python3 @REPO_ROOT@/served_module.py\n",
    )

    verdict = harness.evaluate_candidate(repo, "served_module.py:1")

    assert verdict["verdict"] == "NEEDS-WINSHIP"
    assert verdict["serving_path"]["is_served_path"] is True
    assert "served_path_requires_operator_signoff" in verdict["reasons"]


def test_read_model_with_runtime_reader_is_keep(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "generated" / "read_models" / "live_status.json", json.dumps({"ok": True}) + "\n")
    _write(
        repo / "reader.py",
        "from pathlib import Path\n"
        "payload = Path('generated/read_models/live_status.json').read_text(encoding='utf-8')\n",
    )

    verdict = harness.evaluate_candidate(repo, "generated/read_models/live_status.json")

    assert verdict["verdict"] == "KEEP"
    assert verdict["read_model_runtime_readers"]
    assert "read_model_runtime_reader_found" in verdict["reasons"]
