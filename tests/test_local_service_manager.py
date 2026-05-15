import json
import os
import subprocess
import time
from pathlib import Path

import scripts.manage_openclaw_local_services as manager


def _completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def test_detect_machine_for_mac_pc_wsl_and_unknown(tmp_path):
    assert manager.detect_machine(platform_name="Darwin", pc_share_root=tmp_path / "missing") == "mac"
    e_drive = tmp_path / "openclaw"
    e_drive.mkdir()
    assert manager.detect_machine(platform_name="Linux", pc_share_root=e_drive) == "pc_wsl"
    assert (
        manager.detect_machine(
            platform_name="Linux",
            pc_share_root=tmp_path / "missing",
            proc_version_text="plain linux",
        )
        == "unsupported"
    )


def test_status_works_without_installing_on_pc(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "PC_SHARE_ROOT", tmp_path / "openclaw")
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (False, []),
    )
    monkeypatch.setattr(manager, "PC_SERVICE_TARGET", tmp_path / "systemd" / "openclaw-read-model-import.service")
    monkeypatch.setattr(manager, "PC_TIMER_TARGET", tmp_path / "systemd" / "openclaw-read-model-import.timer")

    payload = manager.manage_service(
        operation="status",
        machine="pc_wsl",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert payload["machine"] == "pc_wsl"
    assert payload["local_task_id"] == "read_model_mirror_pc_import"
    assert payload["service"]["scheduler_available"] is False
    assert payload["service"]["service_file_installed"] is False


def test_pc_install_defers_when_user_systemd_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (False, [{"command": ["systemctl"], "returncode": 1}]),
    )

    payload = manager.manage_service(operation="install", machine="pc_wsl")

    assert payload["status"] == "deferred_no_scheduler"
    assert payload["other_machine_not_controlled"] is True
    assert "WSL user systemd is not available" in payload["result"]["message"]


def test_pc_install_renders_user_service_files_when_systemd_is_available(monkeypatch, tmp_path):
    service_target = tmp_path / "systemd" / "openclaw-read-model-import.service"
    timer_target = tmp_path / "systemd" / "openclaw-read-model-import.timer"
    monkeypatch.setattr(manager, "PC_SYSTEMD_USER_DIR", tmp_path / "systemd")
    monkeypatch.setattr(manager, "PC_SERVICE_TARGET", service_target)
    monkeypatch.setattr(manager, "PC_TIMER_TARGET", timer_target)
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (True, [{"command": ["systemctl", "--user", "show-environment"], "returncode": 0}]),
    )

    payload = manager.manage_service(
        operation="install",
        machine="pc_wsl",
        runner=lambda command: _completed(command, 0),
    )

    assert payload["status"] == "installed"
    assert service_target.is_file()
    assert timer_target.is_file()
    assert "pc_read_model_import_agent.py --once --format operator" in service_target.read_text(encoding="utf-8")
    assert "/mnt/c/openclaw" not in service_target.read_text(encoding="utf-8").lower()


def test_pc_start_requires_install(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "PC_SERVICE_TARGET", tmp_path / "missing.service")
    monkeypatch.setattr(manager, "PC_TIMER_TARGET", tmp_path / "missing.timer")
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (True, []),
    )

    payload = manager.manage_service(operation="start", machine="pc_wsl")

    assert payload["status"] == "needs_install"


def test_pc_uninstall_removes_only_openclaw_service_files_not_data(monkeypatch, tmp_path):
    service_target = tmp_path / "systemd" / "openclaw-read-model-import.service"
    timer_target = tmp_path / "systemd" / "openclaw-read-model-import.timer"
    service_target.parent.mkdir(parents=True)
    service_target.write_text("service\n", encoding="utf-8")
    timer_target.write_text("timer\n", encoding="utf-8")
    data_file = tmp_path / "state" / "read_model_import_agent_state.json"
    data_file.parent.mkdir()
    data_file.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(manager, "PC_SERVICE_TARGET", service_target)
    monkeypatch.setattr(manager, "PC_TIMER_TARGET", timer_target)
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (False, []),
    )

    payload = manager.manage_service(operation="uninstall", machine="pc_wsl")

    assert payload["status"] == "uninstalled"
    assert not service_target.exists()
    assert not timer_target.exists()
    assert data_file.is_file()
    assert payload["result"]["data_deleted"] is False


def test_mac_status_uses_launchagent_path_without_installing(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "MAC_SHARE_ROOT", tmp_path / "openclaw_e")
    monkeypatch.setattr(manager, "_launchctl_available", lambda: False)
    monkeypatch.setattr(manager, "MAC_PLIST_TARGET", tmp_path / "LaunchAgents" / "com.openclaw.read-model-sync.plist")

    payload = manager.manage_service(
        operation="status",
        machine="mac",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert payload["machine"] == "mac"
    assert payload["local_task_id"] == "read_model_mirror_mac_sync"
    assert payload["service"]["scheduler_available"] is False
    assert payload["service"]["plist_installed"] is False


def test_doctor_reports_missing_pc_share(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "PC_SHARE_ROOT", tmp_path / "missing_openclaw")
    monkeypatch.setattr(manager, "PC_MANIFEST_PATH", tmp_path / "missing_openclaw" / "mac_generated_read_models_manifest.json")
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (False, []),
    )

    payload = manager.manage_service(
        operation="doctor",
        machine="pc_wsl",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert payload["doctor_status"] == "share_missing"
    assert "Mount or restore /mnt/e/openclaw" in payload["next_safe_move"]


def test_doctor_reports_stale_manifest_as_needs_mac_sync(monkeypatch, tmp_path):
    share = tmp_path / "openclaw"
    share.mkdir()
    manifest = share / "mac_generated_read_models_manifest.json"
    manifest.write_text(json.dumps({"path_records": []}) + "\n", encoding="utf-8")
    monkeypatch.setattr(manager, "PC_SHARE_ROOT", share)
    monkeypatch.setattr(manager, "PC_MANIFEST_PATH", manifest)
    monkeypatch.setattr(
        manager,
        "_systemd_user_available",
        lambda runner=manager.default_runner: (False, []),
    )

    payload = manager.manage_service(
        operation="doctor",
        machine="pc_wsl",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert payload["doctor_status"] == "needs_mac_sync"
    assert payload["manifest_health"]["counts"]["missing_expected"] > 0


def test_mac_doctor_treats_answered_marker_as_needs_pc_import(monkeypatch, tmp_path):
    share = tmp_path / "openclaw_e"
    request = share / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    status_marker = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    request.parent.mkdir(parents=True)
    completion.parent.mkdir(parents=True)
    request.write_text('{"request_id": "fixture"}\n', encoding="utf-8")
    completion.write_text('{"status": "synced"}\n', encoding="utf-8")
    status_marker.write_text('{"status": "idle"}\n', encoding="utf-8")
    now = time.time()
    os.utime(request, (now - 10, now - 10))
    os.utime(completion, (now, now))
    monkeypatch.setattr(manager, "MAC_SHARE_ROOT", share)
    monkeypatch.setattr(manager, "MAC_REQUEST_MARKER", request)
    monkeypatch.setattr(manager, "MAC_COMPLETION_MARKER", completion)
    monkeypatch.setattr(manager, "MAC_STATUS_MARKER", status_marker)
    monkeypatch.setattr(manager, "_launchctl_available", lambda: False)

    payload = manager.manage_service(
        operation="doctor",
        machine="mac",
        db_path=tmp_path / "ledger.sqlite",
    )

    assert payload["doctor_status"] == "needs_pc_import"
    assert payload["request_marker_answered"] is True
    assert payload["status_marker_present"] is True


def test_source_has_no_c_drive_defaults_or_disallowed_remote_copy_strings():
    text = Path("scripts/manage_openclaw_local_services.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "/mnt/c/openclaw",
        "c:\\openclaw",
        "shell=true",
        "os.system",
        "rsync ",
        "scp ",
        "ssh ",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
        "shutil.rmtree",
        "shutil.move",
    ]
    for token in forbidden:
        assert token not in text
