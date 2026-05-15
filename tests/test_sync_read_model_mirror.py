from pathlib import Path

import pytest

import scripts.sync_read_model_mirror as runner


def test_environment_detection_chooses_mac_for_darwin(tmp_path):
    assert runner.detect_environment(platform_name="Darwin", e_drive_root=tmp_path / "missing") == "mac"


def test_environment_detection_chooses_pc_wsl_for_linux_with_e_drive(tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()

    assert runner.detect_environment(platform_name="Linux", e_drive_root=e_drive) == "pc_wsl"


def test_unknown_environment_fails_clearly(tmp_path):
    with pytest.raises(RuntimeError, match="Unsupported read-model mirror environment"):
        runner.detect_environment(platform_name="Linux", e_drive_root=tmp_path / "missing")


def test_mac_behavior_delegates_to_mac_sync(monkeypatch, tmp_path):
    calls = []

    def fake_sync(**kwargs):
        calls.append(kwargs)
        return {
            "copied_count": 2,
            "destination_root": "/Users/hwinshipwheatley/openclaw_generated_read_models",
            "local_manifest_path": "/Users/hwinshipwheatley/Desktop/openclaw_mac_manifests/mac_generated_read_models_manifest.json",
            "manifest_sha256": "abc123",
            "pc_drop_written": True,
            "pc_drop_manifest_path": "/Volumes/openclaw_e/mac_generated_read_models_manifest.json",
            "share_mounted": True,
            "key_files_present": {"context_selection.json": True},
        }

    monkeypatch.setattr(runner, "sync_generated_read_models", fake_sync)

    report = runner.sync_read_model_mirror(
        pull=True,
        require_share=True,
        platform_name="Darwin",
        e_drive_root=tmp_path / "missing",
    )

    assert report["environment"] == "mac"
    assert report["status"] == "needs_pc_import"
    assert report["behavior"] == "mac_sync_generated_read_models"
    assert report["pc_import_not_attempted"] is True
    assert "sync_read_model_mirror.py --format operator" in report["next_pc_command"]
    assert calls == [{"pull": True, "require_share": True, "platform_name": "Darwin"}]


def test_pc_current_mirror_returns_ok_when_manifest_exists(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()
    manifest = e_drive / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    calls = []

    def fake_import(**kwargs):
        calls.append(kwargs)
        return {
            "manifest_path": str(manifest),
            "generated_read_model_mirror": {"counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0}},
        }

    monkeypatch.setattr(runner, "import_latest_mac_read_model_mirror", fake_import)

    report = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=manifest,
        db_path=tmp_path / "ledger.sqlite",
    )

    assert report["environment"] == "pc_wsl"
    assert report["status"] == "ok"
    assert report["behavior"] == "import_latest_mac_read_model_mirror"
    assert report["mirror_health"]["counts"]["missing_expected"] == 0
    assert report["mac_sync_not_attempted"] is True
    assert calls == [{"manifest": manifest, "db_path": tmp_path / "ledger.sqlite"}]


def test_pc_missing_expected_returns_needs_mac_sync_and_writes_marker(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()
    manifest = e_drive / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    marker = e_drive / "shuttle" / "to_mac" / "read_model_sync_required.json"

    def fake_import(**kwargs):
        return {
            "manifest_path": str(manifest),
            "generated_read_model_mirror": {
                "counts": {
                    "canonical_expected": 34,
                    "observed": 32,
                    "missing_expected": 2,
                    "extra": 0,
                    "hash_mismatch": 0,
                    "matched_hash": 32,
                },
                "missing_expected_files": [
                    "dropped_intents.json",
                    "dropped_intents_OPERATOR.md",
                ],
                "extra_files": [],
                "hash_mismatch_files": [],
            },
        }

    monkeypatch.setattr(runner, "import_latest_mac_read_model_mirror", fake_import)

    report = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=manifest,
        request_marker_path=marker,
    )

    assert report["status"] == "needs_mac_sync"
    assert report["mirror_health"]["missing_expected_files"] == [
        "dropped_intents.json",
        "dropped_intents_OPERATOR.md",
    ]
    assert "sync_read_model_mirror.py --pull --format operator" in report["next_mac_command"]
    assert report["request_marker_path"] == marker.as_posix()
    marker_payload = __import__("json").loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["requested_by"] == "pc_wsl_auto_runner"
    assert marker_payload["next_expected_responder"] == "mac_read_model_sync_agent"
    assert marker_payload["missing_expected_files"] == [
        "dropped_intents.json",
        "dropped_intents_OPERATOR.md",
    ]
    assert marker_payload["hash_mismatch_files"] == []
    assert all(value is False for value in marker_payload["no_authority_flags"].values())


def test_pc_hash_mismatch_returns_needs_mac_sync_and_writes_marker(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()
    manifest = e_drive / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    marker = e_drive / "shuttle" / "to_mac" / "read_model_sync_required.json"

    def fake_import(**kwargs):
        return {
            "manifest_path": str(manifest),
            "generated_read_model_mirror": {
                "counts": {
                    "canonical_expected": 48,
                    "observed": 48,
                    "missing_expected": 0,
                    "extra": 0,
                    "hash_mismatch": 2,
                    "matched_hash": 46,
                },
                "missing_expected_files": [],
                "hash_mismatch_files": ["steel_thread_radar.json", "work_board.json"],
            },
        }

    monkeypatch.setattr(runner, "import_latest_mac_read_model_mirror", fake_import)

    report = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=manifest,
        request_marker_path=marker,
    )

    assert report["status"] == "needs_mac_sync"
    assert report["mirror_health"]["hash_mismatch_files"] == ["steel_thread_radar.json", "work_board.json"]
    assert report["request_marker_path"] == marker.as_posix()
    assert report["next_expected_responder"] == "mac_read_model_sync_agent"
    marker_payload = __import__("json").loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["requested_by"] == "pc_wsl_auto_runner"
    assert marker_payload["next_expected_responder"] == "mac_read_model_sync_agent"
    assert marker_payload["missing_expected_files"] == []
    assert marker_payload["hash_mismatch_files"] == ["steel_thread_radar.json", "work_board.json"]
    assert "manual_fallback_mac_command" in marker_payload
    assert all(value is False for value in marker_payload["no_authority_flags"].values())


def test_pc_extra_files_return_review_needed(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()
    manifest = e_drive / "mac_generated_read_models_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")

    def fake_import(**kwargs):
        return {
            "manifest_path": str(manifest),
            "generated_read_model_mirror": {
                "counts": {"missing_expected": 0, "extra": 1, "hash_mismatch": 0},
                "extra_files": ["old_extra.json"],
            },
        }

    monkeypatch.setattr(runner, "import_latest_mac_read_model_mirror", fake_import)

    report = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=manifest,
    )

    assert report["status"] == "review_needed"
    assert report["mirror_health"]["extra_files"] == ["old_extra.json"]


def test_pc_missing_manifest_reports_missing_without_import(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()

    def fail_import(**kwargs):
        raise AssertionError("import must not run when manifest is missing")

    monkeypatch.setattr(runner, "import_latest_mac_read_model_mirror", fail_import)
    report = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=e_drive / "missing.json",
    )

    assert report["status"] == "manifest_missing"
    assert report["pc_import_not_attempted"] is True
    assert "/mnt/c/openclaw" not in report["message"]


def test_mac_missing_share_reports_share_missing(monkeypatch, tmp_path):
    def fake_sync(**kwargs):
        raise RuntimeError("required Mac share is not mounted: /Volumes/openclaw_e")

    monkeypatch.setattr(runner, "sync_generated_read_models", fake_sync)

    report = runner.sync_read_model_mirror(
        platform_name="Darwin",
        e_drive_root=tmp_path / "missing",
        require_share=True,
    )

    assert report["status"] == "share_missing"
    assert report["pc_import_not_attempted"] is True
    assert "/Volumes/openclaw_e" in report["message"]


def test_dry_run_reports_planned_behavior_without_delegating(monkeypatch, tmp_path):
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()

    monkeypatch.setattr(
        runner,
        "sync_generated_read_models",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("mac sync should not run")),
    )
    monkeypatch.setattr(
        runner,
        "import_latest_mac_read_model_mirror",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("pc import should not run")),
    )

    mac = runner.sync_read_model_mirror(
        platform_name="Darwin",
        e_drive_root=tmp_path / "missing",
        pull=True,
        dry_run=True,
    )
    pc = runner.sync_read_model_mirror(
        platform_name="Linux",
        e_drive_root=e_drive,
        manifest=e_drive / "mac_generated_read_models_manifest.json",
        dry_run=True,
    )

    assert mac["planned_behavior"] == "mac_sync_generated_read_models"
    assert mac["mac_share_root"] == "/Volumes/openclaw_e"
    assert pc["planned_behavior"] == "import_latest_mac_read_model_mirror"
    assert pc["manifest_path"].endswith("/mac_generated_read_models_manifest.json")


def test_cli_defaults_use_e_drive_and_mac_share_not_c_drive():
    args = runner.parse_args([])

    assert args.manifest == "/mnt/e/openclaw/mac_generated_read_models_manifest.json"
    assert not args.manifest.startswith("/mnt/c/openclaw")
    assert runner.MAC_SHARE_ROOT.as_posix() == "/Volumes/openclaw_e"


def test_wrapper_sources_have_no_remote_copy_install_or_destructive_behavior():
    text = Path("scripts/sync_read_model_mirror.py").read_text(encoding="utf-8").lower()

    forbidden = [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "rsync ",
        "scp ",
        "ssh ",
        "launchctl",
        "git commit",
        "git push",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
    ]
    for token in forbidden:
        assert token not in text
