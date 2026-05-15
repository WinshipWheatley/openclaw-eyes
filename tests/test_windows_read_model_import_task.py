from pathlib import Path


SCRIPT = Path("scripts/windows_install_read_model_import_task.ps1")
DOC = Path("docs/operations/OPENCLAW_WINDOWS_READ_MODEL_IMPORT_TASK_V0.md")


def test_windows_task_installer_contains_expected_task_contract():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "OpenClawReadModelImport" in text
    assert "E:\\openclaw" in text
    assert "Ubuntu-E" in text
    assert "New-ScheduledTaskAction" in text
    assert "New-ScheduledTaskTrigger" in text
    assert "Register-ScheduledTask" in text
    assert "Unregister-ScheduledTask" in text
    assert "PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator" in text
    assert "windows_task_read_model_import.log" in text
    assert "scripts/manage_openclaw_local_services.py --doctor read_model_mirror --format operator" in text


def test_windows_task_interval_is_five_minutes_by_default():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[int]$IntervalMinutes = 5" in text
    assert "-RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)" in text


def test_windows_task_script_has_no_forbidden_paths_or_transports():
    text = SCRIPT.read_text(encoding="utf-8").lower()

    forbidden = [
        "c:\\openclaw",
        "/mnt/c/openclaw",
        "ssh ",
        "scp ",
        "rsync",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
        "remove-item -recurse",
    ]
    for token in forbidden:
        assert token not in text


def test_windows_task_doc_records_install_validate_and_uninstall_commands():
    text = DOC.read_text(encoding="utf-8")

    assert "OpenClawReadModelImport" in text
    assert "windows_install_read_model_import_task.ps1" in text
    assert "wsl.exe -l -v" in text
    assert "Start-ScheduledTask -TaskName OpenClawReadModelImport" in text
    assert "Unregister-ScheduledTask -TaskName OpenClawReadModelImport -Confirm:$false" in text
    assert "missing_expected=0" in text
    assert "hash_mismatch=0" in text
