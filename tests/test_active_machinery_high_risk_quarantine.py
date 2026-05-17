import json
import re
from pathlib import Path

import active_machinery_high_risk_quarantine as quarantine
from scripts.export_active_machinery_high_risk_quarantine_read_model import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _disposition_item(path: str, disposition: str, *, test_only: bool = False) -> dict:
    return {
        "relative_path": path,
        "repo_root": "/home/openclaw",
        "repo_role": "canonical_repo_a",
        "is_test_only": test_only,
        "machinery_type": "send_external_api" if "sender" in path or "send" in path else "daemon_listener",
        "verification_status": "deterministically_verified_from_safe_header",
        "current_authority_risk": "high",
        "signal_groups": ["send_external_api"] if "send" in path else ["daemon_listener"],
        "static_capabilities": {
            "reads": ["safe static signals indicate local file/generated read-model metadata access"],
            "writes": ["safe static signals indicate importer/exporter or sync output behavior"],
            "executes": ["safe static signals indicate listener/watcher/scheduler runtime behavior"],
            "sends": ["safe static signals indicate external send/API posture"],
        },
        "why_it_matters": f"{path} is high-risk active machinery.",
        "recommended_disposition": disposition,
        "what_must_happen_before_it_can_run": "Operator-approved governed replacement or wrapper proof.",
        "operator_decision_required": not test_only and disposition != "block_no_go",
        "affected_domains": ["send paths"] if "send" in path else ["Chief"],
    }


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    live_targets = [
        ("chief_sender.py", "wrap_with_guardian"),
        ("builder_watcher.sh", "block_no_go"),
        ("scripts/run_producer_listener.sh", "block_no_go"),
        ("cassandra_watcher.py", "retire_later"),
        ("chief_listener.py", "replace_with_governed_path"),
    ]
    test_targets = ["tests/test_send_truth.py"]
    disposition = {
        "schema_version": "active_machinery_operator_disposition_v0",
        "runtime_changed": False,
        "files_moved_or_deleted": False,
        "repo_b_executed": False,
        "high_risk_dispositions": [
            *[_disposition_item(path, disposition) for path, disposition in live_targets],
            *[_disposition_item(path, "keep_test_only", test_only=True) for path in test_targets],
        ],
    }
    ready_packet = {
        "schema_version": "active_machinery_high_risk_quarantine_ready_packet_v0",
        "ready_for_implementation": True,
        "implementation_scope": "metadata_read_model_warning_only",
        "high_risk_live_script_items": [path for path, _ in live_targets],
        "test_only_items_excluded_from_runtime_quarantine": test_targets,
        "static_active_reference_findings": [
            "systemd/user/chief-listener.service.in references chief_listener.py",
            "loop_supervisor.sh restarts builder_watcher.sh",
            "scripts/run_producer_listener.sh starts producer_listener.py",
            "Chief brain files reference chief_sender.py",
        ],
        "not_ready_for": [
            "service_disable",
            "file_rename",
            "file_delete",
            "file_move",
            "chmod_change",
            "launcher_edit",
            "caller_switch",
            "send_wrapper_change",
            "runtime_activation",
        ],
    }
    return (
        _write_json(tmp_path / "disposition.json", disposition),
        _write_json(tmp_path / "ready.json", ready_packet),
    )


def _by_path(items):
    return {item["relative_path"]: item for item in items}


def test_all_ready_packet_live_items_appear_as_warning_only_surfaces(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)

    payload = quarantine.build_quarantine_payload(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        generated_at=FIXED_NOW,
    )

    by_path = _by_path(payload["high_risk_warnings"])
    assert set(by_path) == {
        "chief_sender.py",
        "builder_watcher.sh",
        "scripts/run_producer_listener.sh",
        "cassandra_watcher.py",
        "chief_listener.py",
    }
    assert all(item["quarantine_status"] == "warning_only" for item in by_path.values())
    assert all(item["activation_allowed"] is False for item in by_path.values())
    assert all(item["live_runtime_machinery"] is True for item in by_path.values())


def test_test_only_files_are_not_live_runtime_machinery(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    payload = quarantine.build_quarantine_payload(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        generated_at=FIXED_NOW,
    )

    high_risk_paths = set(_by_path(payload["high_risk_warnings"]))
    test_only = _by_path(payload["test_only_items"])["tests/test_send_truth.py"]

    assert "tests/test_send_truth.py" not in high_risk_paths
    assert test_only["disposition"] == "keep_test_only"
    assert test_only["live_runtime_machinery"] is False
    assert test_only["operator_approval_required_for_runtime_change"] is False


def test_non_destructive_flags_are_false_everywhere(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    payload = quarantine.build_quarantine_payload(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        generated_at=FIXED_NOW,
    )

    assert payload["warning_only"] is True
    assert payload["runtime_changed"] is False
    assert payload["files_moved_or_deleted"] is False
    assert payload["services_disabled"] is False
    assert payload["destructive_quarantine_allowed"] is False
    assert payload["repo_b_executed"] is False
    assert payload["subprocess_or_shell_execution_used"] is False
    for item in payload["high_risk_warnings"]:
        assert item["runtime_changed"] is False
        assert item["files_moved_or_deleted"] is False
        assert item["services_disabled"] is False
        assert item["destructive_quarantine_allowed"] is False
        assert item["launcher_edit_allowed"] is False


def test_static_references_are_represented_if_captured(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    payload = quarantine.build_quarantine_payload(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        generated_at=FIXED_NOW,
    )
    by_path = _by_path(payload["high_risk_warnings"])

    assert payload["counts"]["static_reference_count"] == 4
    assert by_path["chief_listener.py"]["static_references"] == [
        "systemd/user/chief-listener.service.in references chief_listener.py"
    ]
    assert by_path["builder_watcher.sh"]["static_references"] == [
        "loop_supervisor.sh restarts builder_watcher.sh"
    ]
    assert by_path["chief_sender.py"]["static_references"] == [
        "Chief brain files reference chief_sender.py"
    ]


def test_exporter_writes_json_and_operator_outputs(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    summary = quarantine.export_quarantine_read_model(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        read_model_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert summary["warning_only"] is True
    assert summary["runtime_changed"] is False
    assert summary["files_moved_or_deleted"] is False
    assert (export_root / "active_machinery_high_risk_quarantine.json").is_file()
    operator = (export_root / "active_machinery_high_risk_quarantine_OPERATOR.md").read_text(
        encoding="utf-8"
    )
    assert "High-Risk Warning Surfaces" in operator
    assert "What Did Not Happen" in operator
    assert "chief_sender.py" in operator


def test_operator_review_groups_items_and_cross_cutting_decisions(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    quarantine.export_quarantine_read_model(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        read_model_root=export_root,
        generated_at=FIXED_NOW,
    )

    payload = quarantine.build_operator_review_payload(
        quarantine_path=export_root / "active_machinery_high_risk_quarantine.json",
        disposition_path=disposition_path,
        generated_at=FIXED_NOW,
    )

    assert payload["runtime_changed"] is False
    assert payload["files_moved_or_deleted"] is False
    assert payload["services_disabled"] is False
    assert payload["counts"]["block_later"] == 2
    assert payload["counts"]["replace_with_governed_path"] == 1
    assert payload["counts"]["wrap_with_guardian"] == 1
    assert payload["counts"]["retire_later"] == 1
    assert payload["counts"]["keep_for_now_current_dependency"] == 0
    assert payload["counts"]["needs_operator_decision"] == 3

    chief_sender = payload["review_groups"]["wrap_with_guardian"]["items"][0]
    assert chief_sender["relative_path"] == "chief_sender.py"
    assert chief_sender["blocks"]["send_paths"] is True
    assert chief_sender["runtime_action_allowed_now"] is False
    assert "Chief brain files reference chief_sender.py" in chief_sender["current_static_references"]


def test_operator_review_export_writes_json_and_concise_markdown(tmp_path):
    disposition_path, ready_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    quarantine.export_quarantine_read_model(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        read_model_root=export_root,
        generated_at=FIXED_NOW,
    )

    summary = quarantine.export_operator_review(
        quarantine_path=export_root / "active_machinery_high_risk_quarantine.json",
        disposition_path=disposition_path,
        read_model_root=export_root,
        generated_at=FIXED_NOW,
    )

    assert summary["runtime_changed"] is False
    assert summary["services_disabled"] is False
    assert (export_root / "active_machinery_quarantine_operator_review.json").is_file()
    operator = (export_root / "active_machinery_quarantine_operator_review_OPERATOR.md").read_text(
        encoding="utf-8"
    )
    for heading in [
        "Block later",
        "Replace with governed path",
        "Wrap with Guardian",
        "Retire later",
        "Keep for now / current dependency",
        "Needs operator decision",
    ]:
        assert heading in operator
    assert "No high-risk scripts were executed" in operator


def test_cli_outputs_json_summary(tmp_path, capsys):
    disposition_path, ready_path = _fixtures(tmp_path)
    code = cli_main(
        [
            "--disposition-path",
            disposition_path.as_posix(),
            "--ready-packet-path",
            ready_path.as_posix(),
            "--read-model-root",
            (tmp_path / "generated" / "read_models").as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["high_risk_warning_count"] == 5
    assert payload["static_reference_count"] == 4
    assert payload["services_disabled"] is False


def test_cli_outputs_operator_review_json_summary(tmp_path, capsys):
    disposition_path, ready_path = _fixtures(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    quarantine.export_quarantine_read_model(
        disposition_path=disposition_path,
        ready_packet_path=ready_path,
        read_model_root=export_root,
        generated_at=FIXED_NOW,
    )
    code = cli_main(
        [
            "--packet",
            "operator-review",
            "--disposition-path",
            disposition_path.as_posix(),
            "--quarantine-path",
            (export_root / "active_machinery_high_risk_quarantine.json").as_posix(),
            "--read-model-root",
            export_root.as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["counts"]["block_later"] == 2
    assert payload["counts"]["needs_operator_decision"] == 3
    assert payload["files_moved_or_deleted"] is False


def test_quarantine_source_does_not_import_or_call_subprocess_network_or_shell_tools():
    source_paths = [
        Path("active_machinery_high_risk_quarantine.py"),
        Path("scripts/export_active_machinery_high_risk_quarantine_read_model.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    forbidden_patterns = [
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
        r"shell\s*=\s*True",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE) is None
