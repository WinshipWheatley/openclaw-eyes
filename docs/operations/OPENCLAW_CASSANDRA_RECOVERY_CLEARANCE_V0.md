# OpenClaw Cassandra Recovery Clearance v0

This lane adds an explicit local clearance record for Cassandra recovery. It does not start Cassandra by itself.

## What It Allows

- One agent: `cassandra`
- One fixed action: `cassandra_systemd_user_start`
- One argv shape:

```bash
systemctl --user start cassandra-listener.service cassandra-watcher.service cassandra-briefing-scheduler.service
```

- One bounded attempt after explicit local approval
- Receipt-backed execution through `scripts/recover_agent.py`

## What It Does Not Allow

- arbitrary command text
- network, Telegram, API, model, Docker, or Ollama calls
- broad agent activation
- approval bypass
- external or remote approval sources
- hard-kill, maintenance, or intentional-offline bypass

## Operator Flow

Request clearance:

```bash
python3 scripts/request_agent_recovery_clearance.py \
  --agent cassandra \
  --requested-by operator \
  --reason "Cassandra expected online but offline; approve one fixed systemd-owned start path"
```

Inspect pending clearance:

```bash
python3 scripts/query_agent_recovery_clearances.py --agent cassandra
```

Approve only after the operator chooses to allow this exact attempt:

```bash
python3 scripts/approve_agent_recovery_clearance.py \
  --clearance-id <clearance_id> \
  --approved-by operator \
  --approval-note "Approve one Cassandra fixed start attempt" \
  --confirm-agent cassandra \
  --confirm-action cassandra_systemd_user_start
```

Dry-run recovery:

```bash
python3 scripts/recover_agent.py --agent cassandra --dry-run
```

Execute only if the dry-run/status report says recovery is available:

```bash
python3 scripts/recover_agent.py --agent cassandra --execute
```

## Abuse Resistance

The clearance is local-CLI-only and stored in the local ledger. It is not created from Telegram, Mission Control UI, network requests, or shared-drop files. The approval command requires the clearance id plus exact `cassandra` / `cassandra_systemd_user_start` confirmation. The recovery path still uses fixed allowlisted argv with `shell=False`, cooldown, max-attempt checks, and a receipt.

An attacker who only has an outside network path cannot approve or run this clearance through OpenClaw. A local OS compromise is out of scope for this v0 gate and must be handled by host hardening.
