from pathlib import Path


SCRIPT = Path("scripts/windows_wsl_portproxy_resync.ps1")


def test_resync_script_contract():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[int]$ListenPort = 2222" in text
    assert "[int]$TargetPort = 22" in text
    assert '[string]$PreferredDistro = "Ubuntu-E"' in text
    assert "wsl.exe -d $Distro -- hostname -I" in text
    assert "netsh.exe interface portproxy show v4tov4" in text
    assert "netsh.exe interface portproxy delete v4tov4 listenport=$ListenPort listenaddress=$ListenAddress" in text
    assert (
        "netsh.exe interface portproxy add v4tov4 listenport=$ListenPort listenaddress=$ListenAddress "
        "connectport=$TargetPort connectaddress=$wslIp"
    ) in text


def test_resync_only_rewrites_when_the_target_changed():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$current.Address -eq $wslIp -and $current.Port -eq $TargetPort" in text
    assert "already current" in text


def test_firewall_rule_is_private_profile_only():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "-Profile Private" in text
    assert "-Profile Public" not in text
    assert "-Profile Any" not in text
    assert "Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue" in text


def test_scheduled_task_runs_a_copy_from_windows_tasks_root():
    text = SCRIPT.read_text(encoding="utf-8")

    assert '[string]$TaskRoot = "E:\\openclaw\\windows_tasks"' in text
    assert "Copy-Item -Path $PSCommandPath -Destination $copyPath -Force" in text
    assert "New-ScheduledTaskTrigger -AtLogOn" in text
    assert "-RunLevel Highest" in text
    assert "Register-ScheduledTask" in text
    assert "Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false" in text
    assert "*>> '$logPath'" in text


def test_resync_script_has_no_forbidden_paths_or_transports():
    text = SCRIPT.read_text(encoding="utf-8").lower()

    for forbidden in ("c:\\openclaw", "/mnt/c/openclaw", "ssh-keygen", "scp ", "invoke-webrequest", "start-bitstransfer"):
        assert forbidden not in text, forbidden
