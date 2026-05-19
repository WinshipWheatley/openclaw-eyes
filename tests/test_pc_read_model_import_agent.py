import json
from pathlib import Path

import scripts.pc_read_model_import_agent as agent


def _write_manifest(path: Path, text: str = '{"root_id": "mac_generated_read_models"}\n') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_sync_health_refresher(calls: list[dict]) -> agent.SyncHealthRefresher:
    def fake_refresh(**kwargs):
        calls.append(kwargs)
        return {
            "sync_health_refreshed": True,
            "trust_status": "trusted",
            "mirror_status": "ok",
            "canonical_expected": 2,
            "observed": 2,
            "missing_expected": 0,
            "hash_mismatch": 0,
        }

    return fake_refresh


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
    refresh_calls = []

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: calls.append(kwargs),
        sync_health_refresher=_fake_sync_health_refresher(refresh_calls),
    )

    assert status["status"] == "skipped_unchanged"
    assert status["exit_code"] == 0
    assert status["manifest_sha256"] == digest
    assert calls == []
    assert status["sync_health_refresh"]["sync_health_refreshed"] is True
    assert refresh_calls == [
        {
            "db_path": agent.DEFAULT_DB_PATH,
            "manifest_path": manifest,
            "pc_import_state_path": tmp_path / "state.json",
            "mac_completion_path": agent.DEFAULT_COMPLETION_MARKER_PATH,
            "pc_task_log_path": tmp_path / "agent.log",
        }
    ]
    state = _read_json(tmp_path / "state.json")
    assert state["last_skip_reason"] == "unchanged_manifest_hash"
    assert state["last_successful_manifest_sha256"] == digest
    assert state["last_sync_health_refresh"]["sync_health_refreshed"] is True


def test_changed_manifest_triggers_import_and_records_state(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(manifest, '{"path_records": [{"relative_path": "agent_lanes.json"}]}\n')
    _write_manifest(completion, '{"status": "success"}\n')
    calls = []
    refresh_calls = []

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
        sync_health_refresher=_fake_sync_health_refresher(refresh_calls),
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
    assert refresh_calls == [
        {
            "db_path": tmp_path / "ledger.sqlite",
            "manifest_path": manifest,
            "pc_import_state_path": tmp_path / "state.json",
            "mac_completion_path": completion,
            "pc_task_log_path": tmp_path / "agent.log",
        }
    ]
    state = _read_json(tmp_path / "state.json")
    assert state["last_successful_manifest_sha256"] == agent.sha256_file(manifest)
    assert state["last_import_run_id"] == "import_123"
    assert state["last_sync_health_refresh"]["mirror_status"] == "ok"




def test_unchanged_trusted_current_manifest_skips_health_refresh_churn(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    _write_manifest(manifest)
    digest = agent.sha256_file(manifest)
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "last_successful_manifest_sha256": digest,
                "last_imported_at": "2026-05-14T00:00:00+00:00",
                "last_sync_health_refresh": {
                    "sync_lifecycle_state": "trusted_current",
                    "operator_action_required": False,
                },
            }
        ),
        encoding="utf-8",
    )
    refresh_calls = []

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: (_ for _ in ()).throw(AssertionError("import should skip")),
        sync_health_refresher=lambda **kwargs: refresh_calls.append(kwargs),
        read_model_root=tmp_path / "empty_read_models",
    )

    assert status["status"] == "skipped_unchanged"
    assert status["sync_health_refresh_skipped"] is True
    assert status["sync_health_refresh_skip_reason"] == "trusted_current unchanged manifest"
    assert status["final_mac_mirror_request"]["final_mac_mirror_marker_needed"] is False
    assert refresh_calls == []


def test_unchanged_trusted_current_manifest_requests_marker_for_stale_self_report(tmp_path):
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True)
    (read_models / "sync_health.json").write_text('{"canonical": "new"}\n', encoding="utf-8")
    (read_models / "sync_health_OPERATOR.md").write_text("# Canonical New\n", encoding="utf-8")
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    marker = tmp_path / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(completion, '{"status": "synced"}\n')
    manifest_payload = {
        "path_records": [
            {"relative_path": "alpha.json", "content_hash": "a" * 64},
            {"relative_path": "sync_health.json", "content_hash": "1" * 64},
            {"relative_path": "sync_health_OPERATOR.md", "content_hash": "2" * 64},
        ]
    }
    _write_manifest(manifest, json.dumps(manifest_payload) + "\n")
    digest = agent.sha256_file(manifest)
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "last_successful_manifest_sha256": digest,
                "last_imported_at": "2026-05-14T00:00:00+00:00",
                "last_sync_health_refresh": {
                    "sync_lifecycle_state": "trusted_current",
                    "operator_action_required": False,
                },
            }
        ),
        encoding="utf-8",
    )
    refresh_calls = []

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        completion_marker_path=completion,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: (_ for _ in ()).throw(AssertionError("import should skip")),
        sync_health_refresher=lambda **kwargs: refresh_calls.append(kwargs),
        request_marker_path=marker,
        read_model_root=read_models,
    )

    assert status["status"] == "skipped_unchanged"
    assert status["sync_health_refresh_skipped"] is True
    assert refresh_calls == []
    final_request = status["final_mac_mirror_request"]
    assert final_request["final_mac_mirror_marker_needed"] is True
    assert final_request["final_mac_mirror_marker_written"] is True
    assert final_request["sync_lifecycle_state"] == agent.FINAL_MAC_MIRROR_LIFECYCLE_STATE
    assert final_request["self_report_mirror_state"]["stale_files"] == [
        "sync_health.json",
        "sync_health_OPERATOR.md",
    ]
    payload = _read_json(marker)
    assert payload["requested_by"] == "pc_read_model_import_agent"
    assert payload["next_expected_responder"] == "mac_read_model_sync_agent"
    assert payload["operator_action_required"] is False
    assert payload["stale_self_report_files"] == [
        "sync_health.json",
        "sync_health_OPERATOR.md",
    ]
    state = _read_json(tmp_path / "state.json")
    assert state["last_final_mac_mirror_request"]["final_mac_mirror_marker_written"] is True
    assert state["last_self_report_mirror_state"]["marker_needed"] is True


def test_unchanged_manifest_health_export_requests_final_mac_mirror(tmp_path):
    manifest = tmp_path / "mac_generated_read_models_manifest.json"
    marker = tmp_path / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(manifest)
    _write_manifest(completion, '{"status": "synced"}\n')
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

    def refresh(**kwargs):
        return {
            "sync_health_refreshed": True,
            "trust_status": "trusted",
            "mirror_status": "ok",
            "sync_lifecycle_state": "health_exported_waiting_for_mac_mirror",
            "operator_action_required": False,
            "missing_expected": 0,
            "hash_mismatch": 0,
        }

    status = agent.run_import_agent_once(
        manifest_path=manifest,
        completion_marker_path=completion,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=lambda **kwargs: (_ for _ in ()).throw(AssertionError("import should skip")),
        sync_health_refresher=refresh,
        request_marker_path=marker,
    )

    assert status["status"] == "skipped_unchanged"
    assert status["final_mac_mirror_request"]["final_mac_mirror_marker_written"] is True
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["requested_by"] == "pc_read_model_import_agent"
    assert payload["next_expected_responder"] == "mac_read_model_sync_agent"
    assert payload["sync_lifecycle_state"] == "health_exported_waiting_for_mac_mirror"
    assert payload["operator_action_required"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())


def test_pending_final_mac_mirror_marker_is_preserved_not_rewritten(tmp_path):
    marker = tmp_path / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion = tmp_path / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    _write_manifest(marker, '{"request_id": "pending"}\n')
    _write_manifest(completion, '{"status": "synced"}\n')
    now = 1800000000
    import os
    os.utime(completion, (now - 10, now - 10))
    os.utime(marker, (now, now))

    result = agent.write_final_mac_mirror_marker_if_needed(
        sync_health_refresh={"sync_lifecycle_state": "health_exported_waiting_for_mac_mirror"},
        request_marker_path=marker,
        completion_marker_path=completion,
    )

    assert result["final_mac_mirror_marker_needed"] is True
    assert result["final_mac_mirror_marker_written"] is False
    assert json.loads(marker.read_text(encoding="utf-8"))["request_id"] == "pending"


def test_self_report_only_manifest_change_skips_health_refresh_to_avoid_loop(tmp_path):
    previous = tmp_path / "imported" / "mac_generated_read_models_manifest.json"
    current = tmp_path / "mac_generated_read_models_manifest.json"
    previous_payload = {
        "path_records": [
            {"relative_path": "alpha.json", "content_hash": "a" * 64},
            {"relative_path": "sync_health.json", "content_hash": "1" * 64},
            {"relative_path": "sync_health_OPERATOR.md", "content_hash": "2" * 64},
        ]
    }
    current_payload = {
        "path_records": [
            {"relative_path": "alpha.json", "content_hash": "a" * 64},
            {"relative_path": "sync_health.json", "content_hash": "3" * 64},
            {"relative_path": "sync_health_OPERATOR.md", "content_hash": "4" * 64},
        ]
    }
    _write_manifest(previous, json.dumps(previous_payload) + "\n")
    _write_manifest(current, json.dumps(current_payload) + "\n")
    refresh_calls = []

    status = agent.run_import_agent_once(
        manifest_path=current,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        import_manifest_path=previous,
        importer=lambda **kwargs: {
            "import_run_id": "import_self_report",
            "root_id": "mac_generated_read_models",
            "path_count": 3,
            "generated_read_model_mirror": {"counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0}},
        },
        sync_health_refresher=lambda **kwargs: refresh_calls.append(kwargs),
    )

    assert status["status"] == "success"
    assert status["sync_health_refresh_skipped"] is True
    assert "volatile sync_health self-report" in status["sync_health_refresh_skip_reason"]
    assert refresh_calls == []
    state = _read_json(tmp_path / "state.json")
    assert state["last_successful_manifest_sha256"] == agent.sha256_file(current)
    assert state["last_sync_health_refresh_skip_reason"] == status["sync_health_refresh_skip_reason"]


def test_non_self_report_manifest_change_still_refreshes_health(tmp_path):
    previous = tmp_path / "imported" / "mac_generated_read_models_manifest.json"
    current = tmp_path / "mac_generated_read_models_manifest.json"
    _write_manifest(previous, json.dumps({"path_records": [{"relative_path": "alpha.json", "content_hash": "a" * 64}]}) + "\n")
    _write_manifest(current, json.dumps({"path_records": [{"relative_path": "alpha.json", "content_hash": "b" * 64}]}) + "\n")
    refresh_calls = []

    status = agent.run_import_agent_once(
        manifest_path=current,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        import_manifest_path=previous,
        importer=lambda **kwargs: {
            "import_run_id": "import_non_self",
            "root_id": "mac_generated_read_models",
            "path_count": 1,
            "generated_read_model_mirror": {"counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0}},
        },
        sync_health_refresher=_fake_sync_health_refresher(refresh_calls),
    )

    assert status["status"] == "success"
    assert "sync_health_refresh_skipped" not in status
    assert len(refresh_calls) == 1

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
        sync_health_refresher=_fake_sync_health_refresher([]),
    )
    refresh_calls = []
    second = agent.run_import_agent_once(
        manifest_path=manifest,
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "agent.log",
        importer=fake_import,
        sync_health_refresher=_fake_sync_health_refresher(refresh_calls),
    )

    assert first["status"] == "success"
    assert second["status"] == "skipped_unchanged"
    assert len(calls) == 1
    assert len(refresh_calls) == 1


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
        sync_health_refresher=_fake_sync_health_refresher([]),
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
