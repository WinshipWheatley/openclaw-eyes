# OpenClaw Agent Presence v0

Agent Presence v0 records whether OpenClaw’s core agent roles have actual runtime evidence, not just registry/readiness metadata.

It covers:
- `chief`
- `cassandra`
- `guardian`
- `niles`
- `hermes`
- `report_bridge`

## Purpose

The presence layer answers deterministic operator questions such as:
- Is Cassandra expected online?
- Is Cassandra actually online?
- Which expected-online agents are offline, degraded, or unknown?
- Is recovery available, blocked, or not needed?
- What evidence supports that state?

This is a status and recovery-policy registry. It does not start agents, send Telegram messages, inspect secrets, or restart services unless a later explicit recovery command passes every policy gate and writes a receipt.

## Existing Runtime Surfaces Found

Discovery found repo-evident runtime/service surfaces:

- Chief: systemd user service templates for listener, worker, memory worker, state worker, and watcher brain.
- Cassandra: systemd user service templates for listener, watcher, and briefing scheduler; Telegram-ready listener metadata exists, but token contents are not inspected.
- Guardian: Chief Guardian listener service/template and approval-listener code paths.
- Niles: Producer/Niles listener and intake scripts exist; this is a partial runtime overlap and not treated as proof of online presence.
- Hermes: Hermes gateway service/template and advisory packet surfaces.
- Report Bridge: metadata/read-model/package intake surface; not a live daemon in v0.

Service-management freeze docs mark older broad launchers as frozen/deprecated. Presence v0.1 records candidate recovery actions, but keeps execution blocked unless the action is fixed, allowlisted, policy-approved, cooldown-safe, and receipt-backed.

## Desired Versus Actual State

Presence tracks:
- `desired_state`: `online`, `offline_intentional`, `maintenance`, `hard_kill`, `unknown_review`
- `actual_state`: `online`, `offline`, `degraded`, `unknown`, `metadata_available`, `not_configured`

The initial desired state is `online` for Chief, Cassandra, Guardian, Niles, and Hermes unless an operator/policy override says otherwise. Report Bridge defaults to `unknown_review` because it is currently a metadata/package-intake surface rather than a live daemon.

Agent Lane Registry membership is not presence. A role can be registered and still offline.

## Recovery Policy

Autorecovery is blocked by default. Recovery actions are separate from presence checks.

Recovery is never allowed for:
- `hard_kill`
- `offline_intentional`
- `maintenance`
- unknown/review-only runtime state

Recovery can become available only if:
- the agent is expected online
- actual state is offline or degraded
- a real safe local recovery path is known
- policy explicitly allows the attempt
- an explicit local operator clearance is approved when the action requires it
- cooldown permits it
- a receipt can be written

Presence writes recovery receipts. A blocked execute request writes a blocked receipt. An attempted recovery writes stdout/stderr excerpts, exit code, duration, and no-authority flags.

Current first-pass recovery status:

- Cassandra: candidate fixed systemd user start path exists for listener/watcher/scheduler, but execution is blocked in v0 because the listener is Telegram-facing and the unit templates have legacy runtime/log side effects.
- Chief: candidate fixed systemd user start path exists for Chief listener/workers/watcher, but execution is blocked in v0 because broad runtime startup side effects are not yet cleared.
- Niles: Producer/Niles script path exists, but execution is blocked because it requires a secret-backed environment and may call Telegram.
- Guardian/Hermes: runtime surfaces exist and may be online; recovery remains blocked unless explicitly allowed by policy.
- Report Bridge: metadata/read-model only; no live daemon recovery is represented.

## Commands

Build a live presence snapshot:

```bash
python3 scripts/check_agent_presence.py --format operator
```

Query Cassandra:

```bash
python3 scripts/query_agent_presence.py --agent cassandra --format operator
```

Query offline expected-online agents:

```bash
python3 scripts/query_agent_presence.py --report offline --format operator
```

Check recovery policy/status:

```bash
python3 scripts/check_agent_recovery_status.py --report summary --format operator
python3 scripts/check_agent_recovery_status.py --agent cassandra --format operator
```

Dry-run recovery:

```bash
python3 scripts/recover_agent.py --agent cassandra --dry-run --format operator
```

Execute recovery only if the report says policy allows it:

```bash
python3 scripts/recover_agent.py --agent cassandra --execute --format operator
```

If the command reports `blocked`, do not bypass it with a launcher script. Open a narrow recovery lane to change policy.

Request and approve Cassandra recovery clearance:

```bash
python3 scripts/request_agent_recovery_clearance.py \
  --agent cassandra \
  --requested-by operator \
  --reason "Cassandra expected online but offline; request one fixed systemd-owned start attempt"

python3 scripts/query_agent_recovery_clearances.py --agent cassandra

python3 scripts/approve_agent_recovery_clearance.py \
  --clearance-id <clearance_id> \
  --approved-by operator \
  --approval-note "Approve one Cassandra fixed start attempt" \
  --confirm-agent cassandra \
  --confirm-action cassandra_systemd_user_start
```

The clearance path is local-only, single-agent, single-action, single-use, fixed-argv, and receipt-backed. It does not create a Telegram, network, arbitrary-shell, or app-side approval path.

Export the read-model:

```bash
python3 scripts/export_agent_presence_read_model.py --format operator
```

Generated read-models:
- `generated/read_models/agent_presence.json`
- `generated/read_models/agent_presence_OPERATOR.md`

## No-Authority Posture

- `broad_agent_activation_allowed=false`
- `telegram_api_allowed=false`
- `message_send_allowed=false`
- `arbitrary_command_allowed=false`
- `secret_access_allowed=false`
- `recovery_without_policy_allowed=false`
- `hard_kill_bypass_allowed=false`
- `network_authority=false`
- `model_call_allowed=false`
- `client_deployment_allowed=false`

## Next Safe Move

Use this read-model in Mission Control as a read-only surface. Chief can answer “Is Cassandra online?” from `agent_presence.json`: Cassandra is expected online, actual state is based on runtime/service evidence, and recovery is either blocked, available, attempted, succeeded, or failed with a receipt.
