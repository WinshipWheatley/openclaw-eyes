# Codex note event wake

`openclaw-codex-note-wake.path` uses `systemd.path` and the kernel's file-change
notifications to wake the Sol Codex task when a new or changed Markdown note lands in
`/home/openclaw/Operator/to-codex`. There is no periodic polling.

The installer primes a mode-0600 signature ledger before enabling the path unit. Files
present at activation are therefore historical and cannot replay. When several notes land
together, the newest note is sent to the task and the startup snapshot is marked handled.
A failed Codex resume leaves the state unchanged and receives three bounded service retries.

The bridge is context, not authority. The wake prompt identifies each note as untrusted and
preserves the hard red line against unattended external authority, business sends, deletes,
moves, payments, and approval-gate activation.

## Status

```bash
systemctl --user status openclaw-codex-note-wake.path --no-pager
systemctl --user status openclaw-codex-note-wake.service --no-pager
```

## Install

```bash
scripts/install_openclaw_stack.sh --apply --enable --codex-note-watch-only
```

## Rollback

```bash
systemctl --user disable --now openclaw-codex-note-wake.path
```

Disabling the path unit stops all future event wakes. It does not alter coordination notes
or the handled-state ledger.
