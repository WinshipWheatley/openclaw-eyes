@echo off
setlocal

rem Task 150 Windows logon hook. This file only observes running distros and
rem invokes the Ubuntu-E checker. It never stops, terminates, or unregisters one.
set "DISTRO_ARG="
powershell.exe -NoProfile -NonInteractive -Command "$names = @(& wsl.exe -l --running -q | ForEach-Object { $_.Trim() }); if ($names -contains 'Ubuntu') { exit 42 }; exit 0"
set "DISTRO_RESULT=%ERRORLEVEL%"
if "%DISTRO_RESULT%"=="42" set "DISTRO_ARG=--stale-distro-running"
if not "%DISTRO_RESULT%"=="0" if not "%DISTRO_RESULT%"=="42" set "DISTRO_ARG=--stale-distro-unknown"

wsl.exe -d Ubuntu-E -u openclaw --exec /home/openclaw/scripts/openclaw_boot_check.sh --source windows-task %DISTRO_ARG%
exit /b %ERRORLEVEL%
