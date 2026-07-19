# Fleet Wake/Notify v2b Operations

Status: built but inactive
Mission: `WAKE-V2B-DESIGN-DELTA-AND-BUILD`

Installation is not performed by this build. Confer with the operator before running any enable command or live same-turn acceptance probe.

The substrate has two tiers: a normal event rings an idle task's doorbell, and a verified urgent v2 WAKE steers the exact active Codex/Claude turn. It uses no model polling and no model heartbeat. A five-second plumbing debounce coalesces bursts, and the finite dispatcher caps doorbells at three per minute. Coordination files never grant action authority.

## PC-Sol

Reviewed binding:

- task: `019f7780-d5f8-76b0-9dde-ead4bf0735f4`
- inbound: `/home/openclaw/Operator/to-codex`
- board WAKE: `/mnt/e/openclaw/fleet_coord/WAKE`
- rollout/Codex home: `/mnt/c/Users/Open Claw/.codex`
- managed control home: `/home/openclaw/.codex`

The idle doorbell is built, but mid-turn activation is blocked: the live Desktop task is stored in the Windows Codex home while the only managed control socket is in the WSL Codex home. A read-only `thread/read` probe through that WSL proxy produced no protocol response. Enabling app-server remote control would change a control gate, so a board relay cannot authorize it. Keep coverage at `midturn: no` and do not enable the combined unit until direct terminal authority plus an exact-task control-plane proof resolves this split.

After that blocker is resolved and the operator confirms activation directly, render and prime the inactive units:

```bash
install -d -m 700 /home/openclaw/.openclaw/fleet-wake-v2b
install -d -m 755 /home/openclaw/.config/systemd/user
sed \
  -e 's|@PYTHON@|/usr/bin/python3|g' \
  -e 's|@REPO_ROOT@|/home/openclaw|g' \
  -e 's|@INBOUND_DIR@|/home/openclaw/Operator/to-codex|g' \
  -e 's|@WAKE_DIR@|/mnt/e/openclaw/fleet_coord/WAKE|g' \
  -e 's|@STATE_PATH@|/home/openclaw/.openclaw/fleet-wake-v2b/PC-Sol.cursor.json|g' \
  -e 's|@WATCHER_STATE_PATH@|/mnt/e/openclaw/fleet_coord/WATCHER/WATCHER-PC-Sol.json|g' \
  -e 's|@THREAD_ID@|019f7780-d5f8-76b0-9dde-ead4bf0735f4|g' \
  -e 's|@CODEX_HOME@|/mnt/c/Users/Open Claw/.codex|g' \
  -e 's|@CODEX_CLI@|/home/openclaw/.nvm/versions/node/v24.14.0/bin/codex|g' \
  /home/openclaw/systemd/user/openclaw-fleet-wake-v2b@.service.in \
  > /home/openclaw/.config/systemd/user/openclaw-fleet-wake-v2b@.service
sed \
  -e 's|@REPO_ROOT@|/home/openclaw|g' \
  -e 's|@INBOUND_DIR@|/home/openclaw/Operator/to-codex|g' \
  -e 's|@WAKE_DIR@|/mnt/e/openclaw/fleet_coord/WAKE|g' \
  /home/openclaw/systemd/user/openclaw-fleet-wake-v2b@.path.in \
  > '/home/openclaw/.config/systemd/user/openclaw-fleet-wake-v2b@PC-Sol.path'
/usr/bin/python3 /home/openclaw/fleet_coordination_watcher.py \
  --prime --seat PC-Sol \
  --inbound-dir /home/openclaw/Operator/to-codex \
  --wake-dir /mnt/e/openclaw/fleet_coord/WAKE \
  --state-path /home/openclaw/.openclaw/fleet-wake-v2b/PC-Sol.cursor.json \
  --watcher-state-path /mnt/e/openclaw/fleet_coord/WATCHER/WATCHER-PC-Sol.json \
  --thread-id 019f7780-d5f8-76b0-9dde-ead4bf0735f4 \
  --repo-root /home/openclaw \
  --codex-home '/mnt/c/Users/Open Claw/.codex' \
  --codex-cli /home/openclaw/.nvm/versions/node/v24.14.0/bin/codex
systemctl --user daemon-reload
systemctl --user enable --now 'openclaw-fleet-wake-v2b@PC-Sol.path'
```

Exact rollback stops only the new monitor and preserves evidence/cursors:

```bash
systemctl --user disable --now 'openclaw-fleet-wake-v2b@PC-Sol.path'
systemctl --user daemon-reload
```

## Mac-Sol-Desktop

Do not arm this seat yet. `FAIL-SEAT-BINDING-V2-20260717` did not prove a distinct current task; reusing the Mac-Sol-VSCode task could steer the wrong seat. The bootstrap gate is a new receipt proving the desktop seat's task ID, local Codex CLI 0.144.5 path, Codex home, and managed app-server proxy. Until then coverage is `doorbell: no`, `midturn: no`, `needs_operator_kick: true`.

## Mac-Sol-VSCode

The historical task `019f6ca6-0647-7010-a57c-e579d153ac15` is recorded, but v2b stays unarmed until that seat re-proves current ownership plus its exact Codex CLI and managed app-server proxy. After that proof, wire one finite command into the existing `mac_sol_bridge_wake` kqueue handler; do not add a timer or sleep loop:

```bash
/usr/bin/python3 /Users/hwinshipwheatley/openclaw/fleet_coordination_watcher.py \
  --once --seat Mac-Sol-VSCode \
  --inbound-dir /Volumes/openclaw_e/codex_mac_bridge/to-codex-mac \
  --wake-dir /Volumes/openclaw_e/fleet_coord/WAKE \
  --state-path '/Users/hwinshipwheatley/Library/Application Support/OpenClaw/FleetWake/Mac-Sol-VSCode.cursor.json' \
  --watcher-state-path /Volumes/openclaw_e/fleet_coord/WATCHER/WATCHER-Mac-Sol-VSCode.json \
  --thread-id 019f6ca6-0647-7010-a57c-e579d153ac15 \
  --repo-root /Users/hwinshipwheatley/openclaw \
  --codex-home /Users/hwinshipwheatley/.codex \
  --codex-cli /REPLACE/WITH/PROVEN/CODEX-0.144.5
```

The placeholder is intentional and fail-closed; do not guess the binary path.

## Mac-Fable

Paste this instruction into the existing Claude Code seat after operator confirmation:

```text
Arm the native harness Monitor for /Volumes/openclaw_e/codex_mac_bridge/to-fable-mac and exact WAKE-Mac-Fable-* records under /Volumes/openclaw_e/fleet_coord/WAKE. Coalesce a five-second burst into one event. Map normal to the idle doorbell and urgent to native same-turn Monitor injection. Never abort, never model-poll, and write WATCHER-Mac-Fable.json after each delivery outcome.
```

Rollback is to disarm only those two Monitor registrations; do not alter the lane files.

## Gemini

No proven Antigravity trigger exists. Keep this seat operator-kicked and report `doorbell: no`, `midturn: unsupported`. Do not claim wake coverage and do not emulate it with an LM polling turn.

## Opus

Paste this instruction into the existing Claude Code coordination seat after operator confirmation:

```text
Keep the native Monitor mappings on PC-Sol, Gemini, both Mac-Sol outboxes, Mac-Fable outbox, NEEDS-OPUS, and exact WAKE-Opus-* records. Normal is the idle doorbell; urgent is native same-turn injection. Coalesce five-second bursts, never abort, and surface delivery/urgent/failure counts in WATCHER-Opus.json.
```

## Coverage

Generate the advisory read model after monitor state changes:

```bash
/usr/bin/python3 /home/openclaw/fleet_coordination_coverage.py \
  --registry /home/openclaw/config/fleet_coordination.v2.json \
  --watcher-dir /mnt/e/openclaw/fleet_coord/WATCHER \
  --checkin-dir /mnt/e/openclaw/fleet_coord/CHECKIN \
  --output /home/openclaw/generated/read_models/fleet_coordination_coverage.json \
  --output /mnt/e/openclaw/fleet_coord/FLEET-WATCH-COVERAGE.json
```

Missing watcher state is `infrastructure: missing` and forces `needs_operator_kick: true`; CHECKIN timestamps are not treated as heartbeats.

## Live acceptance after separate authorization

1. Idle normal: drop one validated normal WAKE and prove the exact idle seat resumes once.
2. Busy urgent: start a long turn, drop one validated urgent WAKE, and prove its marker is incorporated before the same turn ends.
3. Confirm no abort and preserved work.
4. Drop ten messages inside five seconds and prove exactly one delivery with `coalesced += 9`.
5. Regenerate coverage and retain the event IDs and counts.
