from __future__ import annotations

from dataclasses import dataclass
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

import nl_stress_replay_harness
from pc4_answer_capture import detect_probe_timeout
from polish_loop.answer_auditor import check_agent_claim
from polish_loop.control_plane import ControlPlaneLedger, make_acceptance_ref
from polish_loop.orchestrator import phase_c_dispatch_local_builder
from polish_loop.pc4_heal_emitter import emit_heal_task, validate_heal_payload
from polish_loop.worker_runtime import WorkerRuntimeConfig


@pytest.fixture(autouse=True)
def _pc4_isolated_auto_heal_state(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_AUTO_HEAL_STATE", str(tmp_path / "loop_auto_heal_state.json"))


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _truth_root(tmp_path: Path, *, online_count: int = 6) -> Path:
    root = tmp_path / "read_models"
    _write_json(
        root / "agent_presence.json",
        {
            "schema_version": "agent_presence_read_model_v0",
            "online_count": online_count,
            "agents": [{"agent_id": f"agent_{idx}", "actual_state": "online"} for idx in range(online_count)],
        },
    )
    return root


def _heal_payload(truth_root: Path, *, claim_value: int | str = 6) -> dict:
    return {
        "source_surface": "maestro",
        "bad_exchange": {"request": "how many agents are online?", "answer": "7 agents online"},
        "expected_behavior": 6,
        "truth_inputs": [str(truth_root / "agent_presence.json")],
        "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
        "allowed_tools_class": "read_only_readmodels",
        "pii_rules": "no vault, no LegalPrivate, no FinancePrivate, no .chief.env",
        "repro_prompts": ["how many agents are online?"],
        "acceptance_tests": ["tests/test_pc4_self_healing.py"],
        "rollback_no_send": True,
        "agent_id": "maestro",
        "claim_type": "agent_presence_online_count",
        "claim_value": claim_value,
    }


@dataclass(frozen=True)
class _FakeOpenClawResponse:
    operator_headline: str
    operator_message: str
    detail_disclosure: dict


def test_nl_stress_replay_audits_actual_processor_answer_not_expected_behavior(tmp_path, monkeypatch):
    truth_root = _truth_root(tmp_path, online_count=6)
    payload_path = _write_json(tmp_path / "payload.json", _heal_payload(truth_root, claim_value=6))
    pc_output = tmp_path / "pc_output.md"

    def fake_process(prompt: str, *, read_model_root: Path):
        return _FakeOpenClawResponse(
            operator_headline="7 agents online",
            operator_message="There are 7 agents online.",
            detail_disclosure={"layered_response_fields": {"one_line_answer": "7 agents online"}},
        )

    monkeypatch.setattr(nl_stress_replay_harness.openclaw_request_processor, "process", fake_process)

    exit_code = nl_stress_replay_harness.run_replay(
        task_payload_path=payload_path,
        read_model_root=truth_root,
        pc_output_path=pc_output,
    )

    text = pc_output.read_text(encoding="utf-8")
    assert exit_code == 1
    assert "STATUS: BLOCKED" in text
    assert "Auditor verdict: fail" in text
    assert "7 agents online" in text


def test_duplicate_heal_finding_admits_one_active_task(tmp_path):
    truth_root = _truth_root(tmp_path, online_count=6)
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    finding = check_agent_claim(
        "maestro",
        "agent_presence_online_count",
        "7 agents online",
        read_model_root=truth_root,
    )

    first = emit_heal_task(
        ledger,
        finding,
        request_text="how many agents are online?",
        answer_text="7 agents online",
        repro_prompts=("how many agents are online?",),
        acceptance_path=Path(__file__),
    )
    second = emit_heal_task(
        ledger,
        finding,
        request_text="how many agents are online?",
        answer_text="7 agents online",
        repro_prompts=("how many agents are online?",),
        acceptance_path=Path(__file__),
    )

    tasks = ledger.list_tasks()
    assert first == second
    assert len(tasks) == 1
    assert tasks[0]["status"] == "READY"


def test_phase_c_dispatch_writes_fix_directive_without_inline_build(tmp_path, monkeypatch):
    truth_root = _truth_root(tmp_path, online_count=6)
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    task_id = ledger.admit_task(
        source="detector",
        task_type="agent_heal",
        requested_status="READY",
        payload=validate_heal_payload(_heal_payload(truth_root)),
        acceptance_ref=make_acceptance_ref(Path(__file__), ROOT / "scripts" / "green_gate.sh"),
    )
    lease = ledger.claim_next_ready(owner="orchestrator")
    assert lease is not None
    assert lease.task_id == task_id

    def forbidden_inline_builder(*args, **kwargs):
        raise AssertionError("orchestrator must not run the builder inline")

    monkeypatch.setattr("polish_loop.orchestrator.run_local_builder_worker", forbidden_inline_builder)
    loop_dir = tmp_path / "loop"
    config = WorkerRuntimeConfig(
        loop_dir=loop_dir,
        task_path=loop_dir / "task.md",
        pc_output_path=loop_dir / "current" / "pc_output.md",
        artifact_dir=loop_dir / "current",
    )

    phase_c_dispatch_local_builder(lease, ledger=ledger, config=config)

    directives = sorted((loop_dir / "to-pc").glob("FIX-*.md"))
    assert len(directives) == 1
    text = directives[0].read_text(encoding="utf-8")
    assert "FIX:" in text
    assert lease.task_id in text
    assert lease.lease_nonce in text


def test_probe_timeout_emits_fail_finding_and_heal_task(tmp_path):
    response_dir = tmp_path / "responses"
    response_dir.mkdir()
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")

    finding = detect_probe_timeout(
        agent_id="niles",
        request_text="probe Niles status",
        response_dir=response_dir,
        before_files=(),
        timeout_seconds=0,
    )
    assert finding.verdict == "fail"
    assert finding.claim_type == "probe_response_timeout"

    task_id = emit_heal_task(
        ledger,
        finding,
        request_text="probe Niles status",
        answer_text="",
        source_surface="niles",
        repro_prompts=("probe Niles status",),
        acceptance_path=Path(__file__),
    )

    task = ledger.get_task(task_id)
    assert task["source"] == "detector"
    assert task["type"] == "agent_heal"
    assert task["status"] == "READY"
