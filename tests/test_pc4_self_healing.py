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

from polish_loop.answer_auditor import check_agent_claim
from polish_loop.pc4_heal_emitter import emit_heal_task, validate_heal_payload
from polish_loop.control_plane import AcceptanceDecision, ControlPlaneLedger, TaskRejected, make_acceptance_ref
import nl_stress_replay_harness


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
            "agents": [
                {"agent_id": f"agent_{idx}", "actual_state": "online"}
                for idx in range(online_count)
            ],
        },
    )
    _write_json(
        root / "openclaw_capability_index.json",
        {
            "schema_version": "openclaw_capability_index_v0",
            "generic_capabilities": [
                {"capability_id": "status", "capability_status": "LIVE_IMPLEMENTED"},
                {"capability_id": "proof", "capability_status": "LIVE_IMPLEMENTED"},
            ],
        },
    )
    _write_json(root / "openclaw_change_sentinel.json", {"generated_at": "2026-06-19T12:00:00+00:00"})
    return root


def _valid_pc_output(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "RUNNER: harness",
                "PASS: 1",
                "STATUS: DONE",
                "",
                "CHANGES:",
                "- Replayed the self-heal prompt.",
                "",
                "REASONING:",
                "- The auditor now passes against real truth inputs.",
                "",
                "ROLLBACK PLAN:",
                "- Revert the heal patch if the replay regresses.",
                "",
                "COST:",
                "- Local dry-run only.",
                "",
                "TRUTH:",
                "- Real read-model truth inputs were used.",
                "",
                "HEADROOM:",
                "- No provider headroom consumed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _heal_payload(truth_root: Path, *, expected_behavior: int = 6, bad_claim: str = "7 agents online") -> dict:
    return {
        "source_surface": "maestro",
        "bad_exchange": {"request": "how many agents are online?", "answer": bad_claim},
        "expected_behavior": expected_behavior,
        "truth_inputs": [str(truth_root / "agent_presence.json")],
        "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
        "allowed_tools_class": "read_only_readmodels",
        "pii_rules": "no vault, no LegalPrivate, no FinancePrivate, no .chief.env",
        "repro_prompts": ["how many agents are online?"],
        "acceptance_tests": ["tests/test_pc4_self_healing.py"],
        "rollback_no_send": True,
        "agent_id": "maestro",
        "claim_type": "agent_presence_online_count",
        "claim_value": expected_behavior,
    }


def test_wrong_agent_presence_claim_emits_ready_detector_heal_task(tmp_path):
    truth_root = _truth_root(tmp_path, online_count=6)
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")

    finding = check_agent_claim(
        "maestro",
        "agent_presence_online_count",
        "7 agents online",
        read_model_root=truth_root,
    )
    task_id = emit_heal_task(
        ledger,
        finding,
        request_text="how many agents are online?",
        answer_text="7 agents online",
        repro_prompts=("how many agents are online?",),
        acceptance_path=Path(__file__),
    )

    task = ledger.get_task(task_id)
    assert finding.verdict == "fail"
    assert finding.actual_value == 6
    assert task["source"] == "detector"
    assert task["type"] == "agent_heal"
    assert task["status"] == "READY"
    assert task["dispatchable"] == 1


def test_correct_agent_presence_claim_does_not_emit_task(tmp_path):
    truth_root = _truth_root(tmp_path, online_count=6)
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")

    finding = check_agent_claim(
        "maestro",
        "agent_presence_online_count",
        "6 agents online",
        read_model_root=truth_root,
    )
    task_id = emit_heal_task(
        ledger,
        finding,
        request_text="how many agents are online?",
        answer_text="6 agents online",
        repro_prompts=("how many agents are online?",),
        acceptance_path=Path(__file__),
    )

    assert finding.verdict == "pass"
    assert task_id is None
    assert ledger.list_tasks() == []


def test_unverifiable_claim_does_not_fake_pass_or_emit_task(tmp_path):
    truth_root = tmp_path / "empty_read_models"
    truth_root.mkdir()
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")

    finding = check_agent_claim(
        "maestro",
        "agent_presence_online_count",
        "6 agents online",
        read_model_root=truth_root,
    )
    task_id = emit_heal_task(
        ledger,
        finding,
        request_text="how many agents are online?",
        answer_text="6 agents online",
        repro_prompts=("how many agents are online?",),
        acceptance_path=Path(__file__),
    )

    assert finding.verdict == "unverifiable"
    assert task_id is None
    assert ledger.list_tasks() == []


def test_failing_candidate_output_terminalizes_blocked_not_done(tmp_path):
    acceptance = tmp_path / "acceptance.py"
    acceptance.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    task_id = ledger.admit_task(
        source="detector",
        task_type="agent_heal",
        requested_status="READY",
        payload=validate_heal_payload(_heal_payload(_truth_root(tmp_path))),
        acceptance_ref=make_acceptance_ref(acceptance, ROOT / "scripts" / "green_gate.sh"),
    )
    lease = ledger.claim_next_ready(owner="pc4-test")
    assert lease is not None
    pc_output = tmp_path / "pc_output.md"
    pc_output.write_text("RUNNER: harness\nPASS: 1\nSTATUS: BLOCKED\n", encoding="utf-8")
    ledger.submit_candidate_evidence(
        task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        evidence={"pc_output_path": str(pc_output)},
    )

    decision = ledger.decide_acceptance(
        task_id,
        gate_runner=lambda **_: AcceptanceDecision(0, "green", ""),
        trusted_repo=ROOT,
    )

    assert decision.exit_code == 2
    assert ledger.get_task(task_id)["status"] == "BLOCKED"


def test_tampered_acceptance_ref_refuses_done(tmp_path):
    acceptance = tmp_path / "acceptance.py"
    acceptance.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    task_id = ledger.admit_task(
        source="detector",
        task_type="agent_heal",
        requested_status="READY",
        payload=validate_heal_payload(_heal_payload(_truth_root(tmp_path))),
        acceptance_ref=make_acceptance_ref(acceptance, ROOT / "scripts" / "green_gate.sh"),
    )
    lease = ledger.claim_next_ready(owner="pc4-test")
    assert lease is not None
    pc_output = _valid_pc_output(tmp_path / "pc_output.md")
    ledger.submit_candidate_evidence(
        task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        evidence={"pc_output_path": str(pc_output)},
    )
    acceptance.write_text("def test_ok():\n    assert False\n", encoding="utf-8")

    decision = ledger.decide_acceptance(
        task_id,
        gate_runner=lambda **_: AcceptanceDecision(0, "green", ""),
        trusted_repo=ROOT,
    )

    assert decision.exit_code == 2
    assert "hash mismatch" in decision.stderr
    assert ledger.get_task(task_id)["status"] == "BLOCKED"


def test_detector_send_or_money_payload_is_rejected(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    payload = _heal_payload(_truth_root(tmp_path), bad_claim="please send a payment wire")
    payload["bad_exchange"]["answer"] = "please send a payment wire"

    with pytest.raises(TaskRejected):
        ledger.admit_task(
            source="detector",
            task_type="agent_heal",
            requested_status="READY",
            payload=validate_heal_payload(payload),
            acceptance_ref=make_acceptance_ref(Path(__file__), ROOT / "scripts" / "green_gate.sh"),
        )


def test_nl_stress_replay_fails_against_stubbed_truth_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_SEND_HOLD", "1")
    empty_truth_root = tmp_path / "empty_read_models"
    empty_truth_root.mkdir()
    payload_path = _write_json(tmp_path / "payload.json", _heal_payload(empty_truth_root))
    pc_output = tmp_path / "pc_output.md"

    exit_code = nl_stress_replay_harness.run_replay(
        task_payload_path=payload_path,
        read_model_root=empty_truth_root,
        pc_output_path=pc_output,
    )

    assert exit_code == 1
    text = pc_output.read_text(encoding="utf-8")
    assert "STATUS: BLOCKED" in text
    assert "unverifiable" in text
