import json
from pathlib import Path

import phase_c_conductor_foundation as phase_c


FIXED_NOW = "2026-06-18T22:20:00+00:00"


def _write_marker(path: Path, text: str = "marker\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_builds_scheduler_gate_and_writeback_state_without_mutation(tmp_path):
    orchestration_root = tmp_path / "orchestration"
    inbox = orchestration_root / "inbox" / "to-claude"
    done_text = "branch codex/E-phase-c-conductor-foundation\ncommit abc123\n"
    _write_marker(
        inbox / "LANE-E-CLAIM-B3-phase-c-conductor-foundation-20260618T220416-0400.md",
        "claim\n",
    )
    _write_marker(
        inbox / "LANE-E-DONE-B3-phase-c-conductor-foundation-20260618T221000-0400.md",
        done_text,
    )
    _write_marker(
        inbox / "LANE-E-DONE-B3-phase-c-conductor-foundation-20260618T221001-0400.md",
        done_text,
    )
    _write_marker(inbox / "CLAIM-GATE-TOKEN-E-20260618T220000-0400.md", "claim e\n")
    _write_marker(inbox / "RELEASE-GATE-TOKEN-E-20260618T220100-0400.md", "release e\n")
    _write_marker(inbox / "CLAIM-GATE-TOKEN-C-20260618T220200-0400.md", "claim c\n")

    payload = phase_c.build_phase_c_conductor_state(
        orchestration_root=orchestration_root,
        generated_at=FIXED_NOW,
    )

    assert payload["schema_version"] == phase_c.READ_MODEL_VERSION
    assert payload["task_summary"]["task_count"] == 1
    assert payload["task_summary"]["done_task_count"] == 1
    assert payload["gate_state"]["active_gate_token_count"] == 1
    assert payload["gate_state"]["active_gate_tokens"][0]["lane"] == "C"
    assert payload["writeback_state"]["completion_writeback_count"] == 1
    writeback = payload["writeback_state"]["completion_writebacks"][0]
    assert writeback["task_id"] == "B3-phase-c-conductor-foundation"
    assert writeback["status"] == "READY_FOR_AUTO_WRITEBACK"
    assert writeback["live_write_performed"] is False
    assert payload["machine_proof"]["external_send_performed"] is False
    assert payload["production_state_mutated"] is False
    assert payload["legal_discovery_accessed"] is False


def test_done_suffix_marker_keeps_lane_and_task_identity():
    parsed = phase_c.parse_marker_filename(
        "LANE-E-SEND-SAFETY-BROKER-GATE-DONE-20260618T192659-0400.md"
    )

    assert parsed["kind"] == "DONE"
    assert parsed["lane"] == "LANE-E"
    assert parsed["task_id"] == "SEND-SAFETY-BROKER-GATE"


def test_operator_and_export_files_use_cockpit_grammar(tmp_path):
    orchestration_root = tmp_path / "orchestration"
    inbox = orchestration_root / "inbox" / "to-claude"
    _write_marker(inbox / "APP-CLAIM-B1-fleet-contracts-20260618T220209-0400.md")
    payload = phase_c.build_phase_c_conductor_state(
        orchestration_root=orchestration_root,
        generated_at=FIXED_NOW,
    )
    paths = phase_c.write_phase_c_conductor_exports(
        payload,
        export_root=tmp_path / "generated" / "read_models",
    )

    json_payload = json.loads(Path(paths["json_path"]).read_text(encoding="utf-8"))
    operator_text = Path(paths["operator_path"]).read_text(encoding="utf-8")
    assert json_payload["schema_version"] == phase_c.READ_MODEL_VERSION
    assert "Evidence:" in operator_text
    assert "Boundary:" in operator_text
    assert "Blocked:" in operator_text
    assert "Next safe move:" in operator_text
