# Guardian/HITL Authority Reconciliation v0

## Bottom Line

OpenClaw currently has more than one approval shape in play. The safest governed local path is the SQLite Operator Action Path, but Chief/Guardian approvals still actively use old JSON state, and Cassandra HITL has a separate JSON-backed queue. Old HITL JSON cannot be deleted or labeled obsolete yet.

## What Is Safe Now

- Use Operator Action only for its existing allowlisted local actions.
- Treat Cassandra recovery clearance as a fixed-scope special case only.
- Keep Guardian/Chief approval paths running as-is; this lane changed no runtime authority.

## Mixed Or Unclear

- `chief_approval_brain`: Chief tiered approval gate - Reconcile into a receipt-backed SQLite contract before expanding action classes.
- `chief_guardian_listener`: Guardian approval listener - Keep role-separated as approval-only; route future action receipts through a unified contract.
- `chief_guardian_sender`: Guardian approval sender - Retain fail-closed button behavior; no new send paths until contract consolidation.
- `chief_router_approval_reply`: Chief router approval reply path - Document as current fallback; reconcile with Guardian listener before removing old JSON.
- `chief_watcher_approval_replay`: Chief watcher approval replay - Keep bounded; future contract should model replay as notification receipt only.
- `google_access_broker_approval_hook`: Google access broker approval hook - Do not expand Gmail/calendar send/write until approval authority is consolidated.
- `hitl_pending_store`: Cassandra HITL pending store - Quarantine as mixed authority until unified with Operator Action/Guardian contract.
- `hitl_action_service`: HITL action service wrapper - Treat as service candidate only; do not connect to execution until receipts are defined.

## Why Old HITL Cannot Be Blocked Yet

Old HITL cannot be deleted or labeled obsolete yet.

`approval_pending.json`, `hitl_pending_state.json`, `hitl_audit.jsonl`, and related files are still referenced by current Repo A code paths. They are not clean authority, but they are also not proven obsolete.

## Cassandra Recovery Trace

- Request creates a SQLite clearance record; no recovery command runs.
- Guardian approval can approve or reject that exact clearance; still no recovery command runs.
- `recover_agent.py --execute` is a separate step and may use only the fixed Cassandra systemd start action.
- Receipts are recorded through `agent_recovery_*` tables when execution is attempted.

## Must Wait

- Cassandra/Chief memory import is not safe yet.
- Remote-builder bridge is not safe yet.
- New send paths are not safe yet.
- Old HITL JSON/JSONL must not be deleted or migrated as truth.

## Next Safe Move

Define a Guardian HITL SQLite authority contract and migration plan before memory import, remote builder, or send-path expansion.
