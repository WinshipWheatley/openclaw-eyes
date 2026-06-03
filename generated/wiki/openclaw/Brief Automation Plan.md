# Brief Automation Plan

Status: BRIEF_AUTOMATION_PLAN_READY

## Purpose

Plan how Cassandra-led homecoming, morning, evening, and manual status briefs can be generated automatically without granting business authority. This is planning only. No timers, providers, messages, or business actions are created by this plan.

## Trigger Plan

- Manual Helm Composer trigger: Winship asks Cassandra for a brief, and Helm shows the local brief inside the app.
- Morning brief: a future approved scheduler can refresh the brief for the morning review window.
- Evening/homecoming brief: a future approved scheduler can refresh the brief near the evening/homecoming window.
- Telegram/Cassandra future trigger: a future adapter can route Telegram-shaped asks through the same local generator after explicit provider approval.
- TTS future trigger: a future adapter can read the TTS-safe spoken text after explicit live-audio approval.

## Required Pieces

- `homecoming_brief.json`
- `operator_next_decision.json`
- client closeout, overnight workboard, package event index, operator conversation journal, Capital Hilton, St. Anne's, automation permission, and voice profile read models
- Helm Composer for manual asks
- A future scheduler only after a separate approval task
- Future Telegram and TTS adapters only after separate approval tasks

## While Winship Sleeps

Allowed:

- Regenerate local brief read models from existing local sources.
- Refresh bridge copies.
- Run JSON parse and unsafe-scan validation.
- Preserve proof refs collapsed.

Must wait for approval:

- Create cron or systemd timers.
- Send messages outside Helm.
- Connect Telegram live.
- Use TTS live playback.
- Open Gmail, browser, Coupa, or portal surfaces.
- Submit portal actions.
- Mutate ledger or workbook state.
- Export PDFs.
- Mark paid or sent truth.

## Failure Modes

- Missing source read model: keep output local and report the missing source.
- Stale next-decision surface: fall back to opening the workboard.
- Bridge unavailable: keep the local brief and report bridge publish failure.
- Unsafe authority detected: stop publish and require Guardian review.
- Scheduler disabled: manual Helm Composer trigger remains the only path.
- Provider credentials absent: generate local text only.

## Boundary

This plan does not send email, open Gmail, open browser or Coupa, connect Telegram, use TTS live, submit portal actions, mutate ledgers, mutate workbooks, export PDFs, mark paid, mark sent, create timers, or push.
