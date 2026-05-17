import json
import re
from pathlib import Path

import cassandra_listener_governed_shadow as shadow
from scripts.export_cassandra_listener_governed_shadow_read_model import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    decision = {
        "schema_version": "active_machinery_quarantine_decision_packet_v0",
        "decision_buckets": {
            "replace_with_governed_path": {
                "items": [
                    {
                        "surface_id": "cassandra_listener.py",
                        "relative_path": "cassandra_listener.py",
                        "decision_bucket": "replace_with_governed_path",
                        "current_risk": "high",
                        "what_it_is": "Listener, watcher, or daemon-style surface",
                        "current_static_references": [
                            "systemd/user/cassandra-listener.service.in references cassandra_listener.py",
                            "start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py",
                        ],
                        "blocks": {
                            "cassandra_chief_utility": True,
                            "send_paths": True,
                            "module_cleanup": True,
                            "remote_builder": False,
                        },
                        "recommended_future_action": "Design a governed replacement before any caller switch.",
                        "what_must_be_proven_before_acting": "Route through governed intake before live listener use.",
                        "why_it_matters": "Verified listener signals on Cassandra intake.",
                    }
                ]
            }
        },
    }
    ready = {
        "schema_version": "active_machinery_replace_with_governed_path_ready_packet_v0",
        "ready_for_implementation": True,
        "ready_for_runtime_replacement": False,
        "readiness_scope": "first_shadow_replacement_no_runtime_change",
        "recommended_lane": "Cassandra Listener Governed Intake Shadow Replacement v0",
        "replace_with_governed_path_items": [
            {
                "relative_path": "cassandra_listener.py",
                "governed_target": "governed_intake_spine_to_work_board_agent_packet_operator_action",
                "runtime_replacement_authorized": False,
            }
        ],
    }
    guardrail = {
        "schema_version": "active_machinery_block_later_guardrail_v0",
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "services_disabled": False,
    }
    return (
        _write_json(tmp_path / "decision.json", decision),
        _write_json(tmp_path / "ready.json", ready),
        _write_json(tmp_path / "guardrail.json", guardrail),
    )


def test_shadow_read_model_preserves_no_runtime_authority_and_no_caller_switch(tmp_path):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    payload = shadow.build_cassandra_listener_governed_shadow(
        decision_packet_path=decision_path,
        ready_packet_path=ready_path,
        guardrail_path=guardrail_path,
        generated_at=FIXED_NOW,
    )

    assert payload["runtime_authority_changed"] is False
    assert payload["runtime_authority"] is False
    assert payload["caller_switched"] is False
    assert payload["live_listener_replaced"] is False
    assert payload["live_listener_touched"] is False
    assert payload["high_risk_file_edited"] is False
    assert payload["services_disabled"] is False
    assert payload["replacement_surface"]["live_listener_imported_or_executed"] is False


def test_shadow_uses_metadata_only_input_and_stores_no_raw_telegram_body(tmp_path):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    payload = shadow.build_cassandra_listener_governed_shadow(
        decision_packet_path=decision_path,
        ready_packet_path=ready_path,
        guardrail_path=guardrail_path,
        generated_at=FIXED_NOW,
    )
    expected_input = payload["expected_input"]

    assert expected_input["input_kind"] == "telegram_update_metadata_only"
    assert expected_input["raw_telegram_body_allowed"] is False
    assert expected_input["raw_telegram_body_stored"] is False
    assert expected_input["message_text_storage_allowed"] is False
    assert payload["raw_telegram_body_stored"] is False
    assert "message_text_hash" in expected_input["allowed_fields"]


def test_governed_target_path_and_boundaries_are_represented(tmp_path):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    payload = shadow.build_cassandra_listener_governed_shadow(
        decision_packet_path=decision_path,
        ready_packet_path=ready_path,
        guardrail_path=guardrail_path,
        generated_at=FIXED_NOW,
    )

    assert payload["governed_path_names"] == [
        "telegram_agent_intake",
        "governed_intake_spine",
        "intent_records",
        "work_board",
        "agent_work_packet",
        "operator_action_guardian_hitl_if_actionable",
    ]
    assert payload["mapping_to_existing_surfaces"]["work_board"] is True
    assert payload["mapping_to_existing_surfaces"]["agent_work_packet"] is True
    assert payload["mapping_to_existing_surfaces"]["operator_action"] is True
    assert "direct listener activation" in payload["blocked_until_proven"]
    assert "metadata-only intake fixture maps to telegram_agent_intake shape" in payload[
        "proof_required_before_caller_switch"
    ]


def test_no_sends_agents_runtime_activation_or_repo_b_execution(tmp_path):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    payload = shadow.build_cassandra_listener_governed_shadow(
        decision_packet_path=decision_path,
        ready_packet_path=ready_path,
        guardrail_path=guardrail_path,
        generated_at=FIXED_NOW,
    )

    assert payload["agents_enabled"] is False
    assert payload["telegram_send_allowed"] is False
    assert payload["gmail_email_send_allowed"] is False
    assert payload["external_send_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert payload["sync_bridge_authority"] is False
    assert payload["shell_execution_allowed"] is False
    assert payload["repo_b_executed"] is False


def test_export_writes_json_and_operator_outputs(tmp_path):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    summary = shadow.export_cassandra_listener_governed_shadow(
        decision_packet_path=decision_path,
        ready_packet_path=ready_path,
        guardrail_path=guardrail_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert summary["runtime_authority_changed"] is False
    assert summary["caller_switched"] is False
    assert summary["live_listener_replaced"] is False
    assert (export_root / "cassandra_listener_governed_shadow.json").is_file()
    operator = (export_root / "cassandra_listener_governed_shadow_OPERATOR.md").read_text(
        encoding="utf-8"
    )
    assert "Governed Replacement Path" in operator
    assert "Raw Telegram body stored: `false`" in operator
    assert "telegram_agent_intake" in operator


def test_cli_outputs_json_summary(tmp_path, capsys):
    decision_path, ready_path, guardrail_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    code = cli_main(
        [
            "--decision-packet-path",
            decision_path.as_posix(),
            "--ready-packet-path",
            ready_path.as_posix(),
            "--guardrail-path",
            guardrail_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["runtime_authority_changed"] is False
    assert payload["caller_switched"] is False
    assert payload["raw_telegram_body_stored"] is False


def test_shadow_source_does_not_import_listener_repo_b_subprocess_network_or_shell_tools():
    source_paths = [
        Path("cassandra_listener_governed_shadow.py"),
        Path("scripts/export_cassandra_listener_governed_shadow_read_model.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    forbidden_patterns = [
        r"^\s*import\s+cassandra_listener\b",
        r"^\s*from\s+cassandra_listener\b",
        r"__import__\(",
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
        r"shell\s*=\s*True",
        r"/home/openclaw_external/openclaw-runtime",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE) is None
