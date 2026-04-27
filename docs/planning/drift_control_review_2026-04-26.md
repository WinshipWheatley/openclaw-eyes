# Drift Control Review — 2026-04-26

Status: reviewed, not applied wholesale.

The weekly drift scanner was restored via a systemd user timer:
- `openclaw-drift-control-scan.timer`
- `openclaw-drift-control-scan.service`

The OpenClaw cron version was removed because it routed the scan text through the embedded OpenClaw agent and hit Codex quota. The systemd timer runs the scanner deterministically.

Latest report:
- `/home/openclaw/mac_eyes/drift_report.md`
- 12 proposed changes
- 0 stale references

Decision:
Do not run `python3 drift_control_scanner.py --apply-proposal` wholesale yet.

Safe / likely acceptable:
- runner version updates for codex, gemini, ollama, claude
- aider remains unavailable
- add custom slash commands: cassandra, ops-intake

Hold / inspect first:
- `effortLevel` changed from max to medium
- `permissions.defaultMode` disappeared
- `permissions.allow` disappeared
- `permissions.deny` disappeared
- `permissions.ask` disappeared

Reason:
The scanner's `--apply-proposal --dry-run` showed an all-or-nothing list of 12 updates, not a selective patch. The permissions disappearance may reflect scanner detection limitations or config relocation, not actual policy intent.

Next correct work:
Implement selective proposal application or manually review/update `settings_suite_registry.json` in a controlled commit.
