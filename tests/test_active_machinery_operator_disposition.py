import json
import re
from pathlib import Path

import active_machinery_operator_disposition as disposition
from scripts.build_active_machinery_operator_disposition import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _verification_fixture(tmp_path: Path) -> Path:
    payload = {
        "schema_version": "active_machinery_gemini_verification_v0",
        "groups": {
            "verified_high_risk_active_machinery": {
                "count": 4,
                "items": [
                    {
                        "relative_path": "chief_sender.py",
                        "repo_root": tmp_path.as_posix(),
                        "repo_role": "canonical_repo_a",
                        "machinery_type": "send_external_api",
                        "verification_status": "deterministically_verified_from_safe_header",
                        "authority_risk": "high",
                        "sends_external": "network_api",
                        "signal_groups": ["path_send_api_hint", "send_external_api"],
                    },
                    {
                        "relative_path": "builder_watcher.sh",
                        "repo_root": tmp_path.as_posix(),
                        "repo_role": "canonical_repo_a",
                        "machinery_type": "daemon_listener",
                        "verification_status": "deterministically_verified_from_safe_header",
                        "authority_risk": "high",
                        "sends_external": "none",
                        "signal_groups": ["daemon_listener", "path_daemon_listener_hint"],
                    },
                    {
                        "relative_path": "tests/test_send_truth.py",
                        "repo_root": tmp_path.as_posix(),
                        "repo_role": "canonical_repo_a",
                        "machinery_type": "send_external_api",
                        "verification_status": "deterministically_verified_from_safe_header",
                        "authority_risk": "high",
                        "sends_external": "network_api",
                        "signal_groups": ["path_send_api_hint", "send_external_api"],
                    },
                    {
                        "relative_path": "chief_watcher_brain.py",
                        "repo_root": tmp_path.as_posix(),
                        "repo_role": "canonical_repo_a",
                        "machinery_type": "daemon_listener",
                        "verification_status": "deterministically_verified_from_safe_header",
                        "authority_risk": "high",
                        "sends_external": "none",
                        "signal_groups": ["daemon_listener", "shell_or_process", "state_mutator"],
                    },
                ],
            },
            "likely_active_machinery_needing_operator_review": {"count": 2, "items": []},
            "false_positives_safe_docs_generated_files": {"count": 5, "items": []},
            "repo_b_reference_only_machinery": {"count": 1, "items": []},
            "send_api_surfaces": {"count": 2, "items": []},
            "sync_bridge_surfaces": {"count": 3, "items": []},
            "approval_hitl_surfaces": {"count": 4, "items": []},
            "unknown_needs_deeper_review": {"count": 7, "items": []},
        },
    }
    return _write_json(tmp_path / "verification.json", payload)


def _by_path(payload):
    return {item["relative_path"]: item for item in payload["high_risk_dispositions"]}


def test_high_risk_items_get_allowed_dispositions_and_tests_stay_test_only(tmp_path):
    verification_path = _verification_fixture(tmp_path)
    payload = disposition.build_disposition_payload(
        verification_path=verification_path,
        generated_at=FIXED_NOW,
    )
    by_path = _by_path(payload)

    assert by_path["chief_sender.py"]["recommended_disposition"] == "wrap_with_guardian"
    assert by_path["builder_watcher.sh"]["recommended_disposition"] == "block_no_go"
    assert by_path["chief_watcher_brain.py"]["recommended_disposition"] == "block_no_go"
    assert by_path["tests/test_send_truth.py"]["recommended_disposition"] == "keep_test_only"
    assert by_path["tests/test_send_truth.py"]["is_test_only"] is True
    assert set(payload["counts"]["by_high_risk_disposition"]) <= disposition.ALLOWED_DISPOSITIONS


def test_static_capabilities_are_derived_from_signal_groups_only(tmp_path):
    verification_path = _verification_fixture(tmp_path)
    payload = disposition.build_disposition_payload(
        verification_path=verification_path,
        generated_at=FIXED_NOW,
    )
    chief_sender = _by_path(payload)["chief_sender.py"]
    watcher = _by_path(payload)["chief_watcher_brain.py"]

    assert any("external send/API" in value for value in chief_sender["static_capabilities"]["sends"])
    assert any("shell/process" in value for value in watcher["static_capabilities"]["executes"])
    assert chief_sender["static_capabilities"]["static_evidence_basis"].startswith(
        "active_machinery_gemini_verification"
    )
    assert payload["gemini_output_treated_as_truth"] is False


def test_major_groups_have_dispositions_and_boundaries_remain_false(tmp_path):
    verification_path = _verification_fixture(tmp_path)
    payload = disposition.build_disposition_payload(
        verification_path=verification_path,
        generated_at=FIXED_NOW,
    )
    groups = {item["group_id"]: item for item in payload["major_machinery_group_dispositions"]}

    assert groups["false_positives_safe_docs_generated_files"]["recommended_disposition"] == "keep_canonical"
    assert groups["repo_b_reference_only_machinery"]["recommended_disposition"] == "keep_reference_only"
    assert groups["send_api_surfaces"]["recommended_disposition"] == "wrap_with_guardian"
    assert payload["runtime_changed"] is False
    assert payload["files_moved_or_deleted"] is False
    assert payload["repo_b_executed"] is False


def test_run_disposition_writes_json_operator_and_doc(tmp_path):
    verification_path = _verification_fixture(tmp_path)
    read_model_root = tmp_path / "generated" / "read_models"
    doc_path = tmp_path / "docs" / "operations" / "ACTIVE_MACHINERY_OPERATOR_DISPOSITION_V0.md"

    summary = disposition.run_disposition(
        verification_path=verification_path,
        read_model_root=read_model_root,
        doc_path=doc_path,
        generated_at=FIXED_NOW,
    )

    assert summary["runtime_changed"] is False
    assert (read_model_root / "active_machinery_operator_disposition.json").is_file()
    assert (read_model_root / "active_machinery_operator_disposition_OPERATOR.md").is_file()
    assert doc_path.is_file()
    operator = (read_model_root / "active_machinery_operator_disposition_OPERATOR.md").read_text(encoding="utf-8")
    assert "High-Risk Item Dispositions" in operator
    assert "keep_test_only" in operator
    assert "wrap_with_guardian" in operator


def test_cli_outputs_json_summary(tmp_path, capsys):
    verification_path = _verification_fixture(tmp_path)
    code = cli_main(
        [
            "--verification-path",
            verification_path.as_posix(),
            "--read-model-root",
            (tmp_path / "generated" / "read_models").as_posix(),
            "--doc-path",
            (tmp_path / "docs" / "operations" / "ACTIVE_MACHINERY_OPERATOR_DISPOSITION_V0.md").as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["high_risk_items"] == 4
    assert payload["runtime_changed"] is False
    assert payload["files_moved_or_deleted"] is False
    assert payload["repo_b_executed"] is False


def test_disposition_source_does_not_import_or_call_execution_network_or_shell_tools():
    source_paths = [
        Path("active_machinery_operator_disposition.py"),
        Path("scripts/build_active_machinery_operator_disposition.py"),
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
