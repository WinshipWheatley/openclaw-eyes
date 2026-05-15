<#
.SYNOPSIS
Install or update the OpenClaw PC read-model import Scheduled Task.

.DESCRIPTION
Registers a per-user Windows Scheduled Task named OpenClawReadModelImport.
The task runs the existing WSL one-shot import agent every minute.
It does not install packages, create remote access, use the deprecated C-drive
transfer folder, or modify OpenClaw source code.
#>

[CmdletBinding()]
param(
    [string]$TaskName = "OpenClawReadModelImport",
    [string]$PreferredDistro = "Ubuntu-E",
    [int]$IntervalMinutes = 1,
    [switch]$SkipRunOnce
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

function Get-WslDistroName {
    param([string]$Preferred)

    $verboseList = (& wsl.exe -l -v 2>&1) | ForEach-Object { Normalize-WslLine $_ }
    Write-Section "WSL distros"
    $verboseList | ForEach-Object { if ($_ -ne "") { Write-Host $_ } }

    $quietList = (& wsl.exe -l -q 2>&1) | ForEach-Object { Normalize-WslLine $_ } | Where-Object { $_ -ne "" }
    if ($quietList -contains $Preferred) {
        return $Preferred
    }

    foreach ($line in $verboseList) {
        if ($line.StartsWith("*")) {
            $parts = ($line.TrimStart("*").Trim() -split "\s+")
            if ($parts.Count -gt 0 -and $parts[0] -ne "NAME") {
                return $parts[0]
            }
        }
    }

    if ($quietList.Count -gt 0) {
        return $quietList[0]
    }

    throw "No WSL distro was detected."
}

function Invoke-WslChecked {
    param(
        [string]$Distro,
        [string]$Command,
        [string]$Description
    )

    Write-Section $Description
    & wsl.exe -d $Distro -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed ($Description): $Command"
    }
}

function Write-LogTail {
    param(
        [string]$Path,
        [int]$LineCount = 40
    )

    if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path -Tail $LineCount
    } else {
        Write-Host "Log not present: $Path"
    }
}

function New-WrapperScriptContent {
    param([string]$DistroName)

    $template = @'
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Distro = "__DISTRO__"
$TaskRoot = "E:\openclaw\windows_tasks"
$LogDir = Join-Path $TaskRoot "logs"
$WindowsLogPath = Join-Path $LogDir "OpenClawReadModelImport.log"
$WslLogPath = "/home/openclaw/.openclaw/logs/windows_task_read_model_import.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-TaskLog {
    param([string]$Message)
    $timestamp = (Get-Date).ToString("o")
    "[$timestamp] $Message" | Out-File -FilePath $WindowsLogPath -Append -Encoding utf8
}

Write-TaskLog "OpenClawReadModelImport started."
Write-TaskLog "Distro: $Distro"

$wslPath = Join-Path $env:WINDIR "System32\wsl.exe"
$wslCommand = "set -o pipefail; mkdir -p /home/openclaw/.openclaw/logs && cd /home/openclaw && PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator 2>&1 | tee -a $WslLogPath"

try {
    & $wslPath -d $Distro -- bash -lc $wslCommand 2>&1 | ForEach-Object {
        $_ | Tee-Object -FilePath $WindowsLogPath -Append
    }
    $exitCode = $LASTEXITCODE
} catch {
    $exitCode = 1
    Write-TaskLog "Exception: $($_.Exception.Message)"
}

Write-TaskLog "OpenClawReadModelImport finished with exit code $exitCode."
exit $exitCode
'@

    return $template.Replace("__DISTRO__", $DistroName)
}

Write-Section "Preflight"
if (-not (Test-Path -LiteralPath "E:\openclaw")) {
    throw "E:\openclaw does not exist. Mount/create the shared E-drive drop before installing the task."
}
Write-Host "E:\openclaw exists."

$wsl = Get-Command wsl.exe -ErrorAction Stop
Write-Host "WSL executable: $($wsl.Source)"

$Distro = Get-WslDistroName -Preferred $PreferredDistro
Write-Host "Selected WSL distro: $Distro"

Invoke-WslChecked -Distro $Distro -Description "Confirm backend repo" -Command "test -d /home/openclaw"
Invoke-WslChecked -Distro $Distro -Description "Prepare log directory" -Command "mkdir -p /home/openclaw/.openclaw/logs"

$TaskRoot = "E:\openclaw\windows_tasks"
$TaskLogDir = Join-Path $TaskRoot "logs"
$WrapperPath = Join-Path $TaskRoot "$TaskName.ps1"
$WindowsTaskLogPath = Join-Path $TaskLogDir "$TaskName.log"
$WslTaskLogPath = "/home/openclaw/.openclaw/logs/windows_task_read_model_import.log"

Write-Section "Write wrapper"
New-Item -ItemType Directory -Force -Path $TaskLogDir | Out-Null
Set-Content -LiteralPath $WrapperPath -Value (New-WrapperScriptContent -DistroName $Distro) -Encoding UTF8
Write-Host "Wrapper: $WrapperPath"
Write-Host "Windows log: $WindowsTaskLogPath"
Write-Host "WSL log: $WslTaskLogPath"

$taskPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$taskArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$WrapperPath`""

Write-Section "Register scheduled task"
Write-Host "Task name: $TaskName"
Write-Host "Interval minutes: $IntervalMinutes"
Write-Host "Action: $taskPowerShell $taskArguments"

$action = New-ScheduledTaskAction -Execute $taskPowerShell -Argument $taskArguments
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Existing task replaced."
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "OpenClaw local PC/WSL read-model mirror import every minute." | Out-Null

if (-not $SkipRunOnce) {
    Write-Section "Run once"
    Start-ScheduledTask -TaskName $TaskName
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $runningTask = Get-ScheduledTask -TaskName $TaskName
        if ($runningTask.State -ne "Running") {
            break
        }
    }
}

Write-Section "Task status"
$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "TaskPath: $($task.TaskPath)"
Write-Host "State: $($task.State)"
Write-Host "LastRunTime: $($info.LastRunTime)"
Write-Host "LastTaskResult: $($info.LastTaskResult)"
Write-Host "NextRunTime: $($info.NextRunTime)"

Write-Section "Windows-side task log"
Write-LogTail -Path $WindowsTaskLogPath -LineCount 60

Write-Section "WSL-side task log"
& wsl.exe -d $Distro -- bash -lc "tail -n 60 /home/openclaw/.openclaw/logs/windows_task_read_model_import.log 2>/dev/null || true"

if (-not $SkipRunOnce) {
    if (-not (Test-Path -LiteralPath $WindowsTaskLogPath)) {
        throw "Scheduled task did not create Windows-side log: $WindowsTaskLogPath"
    }
    if ($task.State -eq "Running") {
        throw "Scheduled task did not finish within the installer wait window."
    }
    if ($info.LastTaskResult -ne 0) {
        throw "Scheduled task run failed. LastTaskResult: $($info.LastTaskResult)"
    }
}

Write-Section "Mirror doctor"
& wsl.exe -d $Distro -- bash -lc "cd /home/openclaw && PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --doctor read_model_mirror --format operator"
if ($LASTEXITCODE -ne 0) {
    throw "Mirror doctor command failed after task registration."
}

Write-Section "Uninstall command"
Write-Host "Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
