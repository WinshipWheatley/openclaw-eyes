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
    assert report["behavior"] == "mac_sync_generated_read_models"
    assert report["pc_import_not_attempted"] is True
    assert calls == [{"pull": True, "require_share": True, "platform_name": "Darwin"}]


def test_pc_behavior_delegates_to_import_when_manifest_exists(monkeypatch, tmp_path):
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
    assert report["behavior"] == "import_latest_mac_read_model_mirror"
    assert report["mac_sync_not_attempted"] is True
    assert calls == [{"manifest": manifest, "db_path": tmp_path / "ledger.sqlite"}]


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

    assert report["status"] == "missing_manifest"
    assert report["pc_import_not_attempted"] is True
    assert "/mnt/c/openclaw" not in report["message"]


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
