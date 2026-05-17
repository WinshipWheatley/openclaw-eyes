import json
from pathlib import Path

from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_planning_ready_packets import (
    PACKET_EXPORTS,
    export_operator_planning_ready_packets,
    main,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write_json(
        root / "docs" / "operations" / "OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json",
        {
            "schema_version": "openclaw_remaining_work_stratifier_v0",
            "generated_by": "codex",
            "runtime_authority_changed": False,
            "data_imported": False,
        },
    )
    _write_json(
        root / "docs" / "operations" / "OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json",
        {
            "schema_version": "openclaw_critical_path_execution_packet_v0",
            "generated_by": "codex",
            "implementation_done": False,
            "runtime_authority_changed": False,
            "data_imported": False,
        },
    )
    return root


def test_exports_planning_packets_into_generated_read_models(tmp_path):
    repo = _repo_root(tmp_path)
    export_root = repo / "generated" / "read_models"

    summary = export_operator_planning_ready_packets(
        repo_root=repo,
        export_root=export_root,
    )

    assert summary["schema_version"] == "operator_planning_ready_packet_exports_v0"
    assert summary["runtime_authority_changed"] is False
    assert summary["data_imported"] is False
    assert summary["app_changes_made"] is False
    assert summary["exported_count"] == len(PACKET_EXPORTS)
    for _, destination_name in PACKET_EXPORTS:
        payload = json.loads((export_root / destination_name).read_text(encoding="utf-8"))
        assert payload["generated_by"] == "codex"
        assert payload["runtime_authority_changed"] is False
        assert payload["data_imported"] is False


def test_exported_packets_are_in_dynamic_mirror_expected_set(tmp_path):
    repo = _repo_root(tmp_path)
    export_root = repo / "generated" / "read_models"
    export_operator_planning_ready_packets(repo_root=repo, export_root=export_root)

    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=export_root,
            repo_root=repo,
        )
    )

    for _, destination_name in PACKET_EXPORTS:
        assert destination_name in expected


def test_cli_writes_machine_readable_summary(tmp_path, capsys, monkeypatch):
    repo = _repo_root(tmp_path)
    monkeypatch.setattr("scripts.export_operator_planning_ready_packets.ROOT", repo)

    exit_code = main(["--export-root", "generated/read_models", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["exported_count"] == len(PACKET_EXPORTS)
    assert (repo / "generated" / "read_models" / "OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json").is_file()
