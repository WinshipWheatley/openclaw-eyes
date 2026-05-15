import json
from pathlib import Path

import scripts.pc_read_model_import_agent as agent


def _write_manifest(path: Path, text: str = '{"root_id": "mac_generated_read_models"}\n') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_manifest_exits_clearly_without_import(tmp_path):
    calls = []
    status = agent.run_import_agent_once(
        manifest_path=tmp_path / "missing.json",
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: calls.append(kwargs),
    )

    assert status["status"] == "manifest_missing"
    assert status["exit_code"] == 0
    assert calls == []
    assert _read_json(tmp_path / "state.json")["status"] == "manifest_missing"
    assert "manifest_missing" in (tmp_path / "agent.log").read_text(encoding="utf-8")


def test_unchanged_manifest_hash_skips_import(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write_manifest(manifest)
    digest = agent.sha256_file(manifest)
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "last_successful_manifest_sha256": digest,
                "last_imported_at": "2026-05-14T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    calls = []

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: calls.append(kwargs),
    )

    assert status["status"] == "skipped_unchanged"
    assert status["exit_code"] == 0
    assert status["manifest_sha256"] == digest
    assert calls == []
    state = _read_json(tmp_path / "state.json")
    assert state["last_skip_reason"] == "unchanged_manifest_hash"
    assert state["last_successful_manifest_sha256"] == digest


def test_changed_manifest_triggers_import_and_records_state(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(manifest, '{"path_records": [{"relative_path": "agent_lanes.json"}]}\n')
    _write_manifest(completion, '{"status": "success"}\n')
    calls = []

    def fake_import(**kwargs):
        calls.append(kwargs)
        return {
            "import_run_id": "import_123",
            "root_id": "mac_generated_read_models",
            "path_count": 30,
            "generated_read_model_mirror": {
                "counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0}
            },
        }

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        completion_marker_path=completion,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        db_path=tmp_path / "ledger.sqlite",
        import_manifest_path=tmp_path / "import_manifests" / "manifest.json",
        importer=fake_import,
    )

    assert status["status"] == "success"
    assert status["import_run_id"] == "import_123"
    assert status["path_count"] == 30
    assert status["completion_marker_present"] is True
    assert calls == [
        {
            "manifest": manifest,
            "db_path": tmp_path / "ledger.sqlite",
            "import_manifest_path": tmp_path / "import_manifests" / "manifest.json",
        }
    ]
    state = _read_json(tmp_path / "state.json")
    assert state["last_successful_manifest_sha256"] == agent.sha256_file(manifest)
    assert state["last_import_run_id"] == "import_123"


def test_failure_records_state_without_marking_success(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write_manifest(manifest)

    def fail_import(**kwargs):
        raise RuntimeError("fixture import failure")

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=fail_import,
    )

    assert status["status"] == "failure"
    assert status["exit_code"] == 1
    assert status["failure_reason"] == "RuntimeError"
    state = _read_json(tmp_path / "state.json")
    assert state["status"] == "failure"
    assert state["last_seen_manifest_sha256"] == agent.sha256_file(manifest)
    assert "last_successful_manifest_sha256" not in state


def test_no_repeated_import_after_success_when_manifest_unchanged(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write_manifest(manifest)
    calls = []

    def fake_import(**kwargs):
        calls.append(kwargs)
        return {
            "import_run_id": f"import_{len(calls)}",
            "root_id": "mac_generated_read_models",
            "path_count": 1,
            "generated_read_model_mirror": {
                "counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0}
            },
        }

    first = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=fake_import,
    )
    second = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=fake_import,
    )

    assert first["status"] == "success"
    assert second["status"] == "skipped_unchanged"
    assert len(calls) == 1


def test_manifest_and_completion_marker_are_not_deleted_or_moved(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(manifest)
    _write_manifest(completion)

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        completion_marker_path=completion,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: {
            "import_run_id": "import_123",
            "root_id": "mac_generated_read_models",
            "path_count": 1,
            "generated_read_model_mirror": {"counts": {}},
        },
    )

    assert status["manifest_deleted"] is False
    assert status["completion_marker_deleted"] is False
    assert status["manifest_moved"] is False
    assert manifest.is_file()
    assert completion.is_file()


def test_cli_defaults_use_e_drive_and_repo_local_state_not_c_drive():
    args = agent.parse_args([])

    assert args.manifest == "/mnt/e/openclaw/mac_generated_read_models_manifest.json"
    assert args.completion_marker == "/mnt/e/openclaw/shuttle/from_mac/read_model_sync_completed.json"
    assert args.state_path.endswith(".openclaw/state/read_model_import_agent_state.json")
    assert args.log_path.endswith(".openclaw/logs/read_model_import_agent.log")
    assert "/mnt/c/openclaw" not in args.manifest.lower()
    assert "/mnt/c/openclaw" not in args.completion_marker.lower()


def test_source_has_no_external_transport_or_destructive_behavior():
    text = Path("scripts/pc_read_model_import_agent.py").read_text(encoding="utf-8").lower()

    forbidden = [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "subprocess",
        "os.system",
        "shell=true",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "rsync ",
        "scp ",
        "ssh ",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
        "shutil.move",
    ]
    for token in forbidden:
        assert token not in text
