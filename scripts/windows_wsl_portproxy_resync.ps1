<#
.SYNOPSIS
Re-point the Windows portproxy that exposes WSL sshd (Mac -> PC:2222 -> WSL:22) at the current WSL IPv4 address.

.DESCRIPTION
WSL2 receives a fresh 172.x address on every reboot, so a static
`netsh interface portproxy` rule silently breaks the Mac's `ssh openclaw` route
(see generated/wiki/openclaw/SSH Profile Server Side Verification.md).

This script reads the live WSL address, rewrites the v4tov4 mapping only when it
differs, ensures a Private-profile inbound firewall rule for the listen port, and
with -InstallTask registers a per-user Scheduled Task (at logon, highest
privileges) that re-runs a copy of itself from E:\openclaw\windows_tasks.

Run from an elevated Windows PowerShell, not from inside WSL. Idempotent.
It never opens the port on Public networks, never touches other portproxy rows,
installs no packages, and does not modify OpenClaw source.

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-E\home\openclaw\scripts\windows_wsl_portproxy_resync.ps1"

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-E\home\openclaw\scripts\windows_wsl_portproxy_resync.ps1" -InstallTask
#>

[CmdletBinding()]
param(
    [string]$PreferredDistro = "Ubuntu-E",
    [int]$ListenPort = 2222,
    [int]$TargetPort = 22,
    [string]$ListenAddress = "0.0.0.0",
    [string]$TaskName = "OpenClawWslPortProxyResync",
    [string]$TaskRoot = "E:\openclaw\windows_tasks",
    [int]$StartupDelaySeconds = 0,
    [switch]$InstallTask
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "== $Title =="
}

function Normalize-WslLine {
    param([string]$Value)
    return ($Value -replace "`0", "").Trim()
}

function Get-WslIPv4 {
    param([string]$Distro)
    $raw = (& wsl.exe -d $Distro -- hostname -I 2>&1) | ForEach-Object { Normalize-WslLine $_ } | Where-Object { $_ -ne "" }
    $joined = ($raw -join " ").Trim()
    $first = ($joined -split "\s+") | Select-Object -First 1
    if (-not $first -or $first -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
        throw "Could not read an IPv4 address from WSL distro '$Distro' (got: '$joined')."
    }
    return $first
}

function Get-PortProxyTarget {
    param([string]$Address, [int]$Port)
    $rows = (& netsh.exe interface portproxy show v4tov4 2>&1) | ForEach-Object { Normalize-WslLine $_ }
    foreach ($row in $rows) {
        $parts = $row -split "\s+"
        if ($parts.Count -ge 4 -and $parts[0] -eq $Address -and $parts[1] -eq "$Port") {
            return @{ Address = $parts[2]; Port = [int]$parts[3] }
        }
    }
    return $null
}

function Ensure-PrivateFirewallRule {
    param([int]$Port)
    $name = "OpenClaw WSL SSH ($Port)"
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "firewall: rule '$name' already present"
        return
    }
    New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
    Write-Host "firewall: added Private-profile inbound TCP $Port rule '$name'"
}

function Sync-PortProxy {
    Write-Section "portproxy resync"
    $wslIp = Get-WslIPv4 -Distro $PreferredDistro
    Write-Host "wsl ipv4: $wslIp"
    $current = Get-PortProxyTarget -Address $ListenAddress -Port $ListenPort
    if ($current -and $current.Address -eq $wslIp -and $current.Port -eq $TargetPort) {
        Write-Host "portproxy: ${ListenAddress}:$ListenPort -> ${wslIp}:$TargetPort already current"
    } else {
        if ($current) {
            & netsh.exe interface portproxy delete v4tov4 listenport=$ListenPort listenaddress=$ListenAddress | Out-Null
            Write-Host "portproxy: removed stale mapping -> $($current.Address):$($current.Port)"
        }
        & netsh.exe interface portproxy add v4tov4 listenport=$ListenPort listenaddress=$ListenAddress connectport=$TargetPort connectaddress=$wslIp | Out-Null
        Write-Host "portproxy: ${ListenAddress}:$ListenPort -> ${wslIp}:$TargetPort"
    }
    Ensure-PrivateFirewallRule -Port $ListenPort
}

function Install-ResyncTask {
    Write-Section "scheduled task"
    $logDir = Join-Path $TaskRoot "logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $copyPath = Join-Path $TaskRoot "$TaskName.ps1"
    Copy-Item -Path $PSCommandPath -Destination $copyPath -Force
    $logPath = Join-Path $logDir "$TaskName.log"

    $taskPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    $inner = "& '$copyPath' -PreferredDistro '$PreferredDistro' -ListenPort $ListenPort -TargetPort $TargetPort -ListenAddress '$ListenAddress' -StartupDelaySeconds 30 *>> '$logPath'"
    $taskArguments = "-NoProfile -ExecutionPolicy Bypass -Command `"$inner`""
    $action = New-ScheduledTaskAction -Execute $taskPowerShell -Argument $taskArguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    Write-Host "task: '$TaskName' registered (at logon, highest privileges) -> $copyPath"
    Write-Host "log:  $logPath"
}

if ($StartupDelaySeconds -gt 0) {
    Start-Sleep -Seconds $StartupDelaySeconds
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "wsl.exe was not found on PATH."
}

Sync-PortProxy

if ($InstallTask) {
    Install-ResyncTask
}

Write-Host ""
Write-Host "verify from the Mac:  ssh openclaw 'hostname; hostname -I'"
Write-Host "verify from WSL:      bash scripts/home_fabric_check.sh"
