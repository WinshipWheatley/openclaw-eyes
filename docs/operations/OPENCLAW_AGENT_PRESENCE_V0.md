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

This is a status and recovery-policy registry only. It does not start agents, send Telegram messages, inspect secrets, or restart services.

## Existing Runtime Surfaces Found

Discovery found repo-evident runtime/service surfaces:

- Chief: systemd user service templates for listener, worker, memory worker, state worker, and watcher brain.
- Cassandra: systemd user service templates for listener, watcher, and briefing scheduler; Telegram-ready listener metadata exists, but token contents are not inspected.
- Guardian: Chief Guardian listener service/template and approval-listener code paths.
- Niles: Producer/Niles listener and intake scripts exist; this is a partial runtime overlap and not treated as proof of online presence.
- Hermes: Hermes gateway service/template and advisory packet surfaces.
- Report Bridge: metadata/read-model/package intake surface; not a live daemon in v0.

Service-management freeze docs mark older broad launchers as frozen/deprecated. Presence v0 records candidate recovery policy but does not invoke those paths.

## Desired Versus Actual State

Presence tracks:
- `desired_state`: `online`, `offline_intentional`, `maintenance`, `hard_kill`, `unknown_review`
- `actual_state`: `online`, `offline`, `degraded`, `unknown`, `metadata_available`, `not_configured`

The initial desired state is `online` for Chief, Cassandra, Guardian, Niles, and Hermes unless an operator/policy override says otherwise. Report Bridge defaults to `unknown_review` because it is currently a metadata/package-intake surface rather than a live daemon.

Agent Lane Registry membership is not presence. A role can be registered and still offline.

## Recovery Policy

Autorecovery is blocked by default.

Recovery is never allowed for:
- `hard_kill`
- `offline_intentional`
- `maintenance`
- unknown/review-only runtime state

Recovery can become available only in a future explicit lane if:
- the agent is expected online
- actual state is offline or degraded
- a real safe local recovery path is known
- policy explicitly allows the attempt
- cooldown permits it
- a receipt can be written

Presence v0 writes recovery receipts that say no recovery command was executed.

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

Use this read-model in Mission Control as a read-only surface. A later recovery lane may define one narrow receipt-backed recovery action for a specific agent/service, but it should not restart all agents or bypass hard-kill/maintenance/intentional-offline state.
