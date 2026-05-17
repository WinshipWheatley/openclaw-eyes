# Active Machinery Replace-With-Governed-Path Spec v0

This is a replacement specification only. It does not edit runtime files, run
high-risk scripts, disable services, switch callers, enable sends, or execute
Repo B code.

Source evidence:

- `generated/read_models/active_machinery_quarantine_decision_packet.json`
- `generated/read_models/active_machinery_high_risk_quarantine.json`
- `generated/read_models/active_machinery_block_later_guardrail.json`
- `docs/operations/ACTIVE_MACHINERY_HIGH_RISK_QUARANTINE_SPEC_V0.md`

## Doctrine

The four `replace_with_governed_path` surfaces are not safe as direct runtime
entrypoints. They should be replaced by governed OpenClaw paths that produce
SQLite/read-model evidence, Work Board items, Agent Work Packets, Operator
Action requests, and Guardian/HITL receipts before any runtime, send, sync, or
external action can happen.

Replacement does not mean deleting the old file first. The safe order is:

1. Build a shadow/read-model replacement map.
2. Prove inputs, outputs, receipts, idempotency, and no-send posture.
3. Add compatibility adapters only after proof.
4. Switch callers only after explicit operator approval.
5. Retire old services/files only after rollback is proven.

## Current Replace-With-Governed-Path Surfaces

| Surface | Current static role | Current risk | Static references | Replacement target |
| --- | --- | --- | --- | --- |
| `cassandra_listener.py` | Listener-style Cassandra intake with approval/HITL, send, shell/process, importer/exporter, and sync signals. | High | `systemd/user/cassandra-listener.service.in`; `start_cassandra_core.sh` | Governed intake spine plus Work Board / Agent Work Packet / Operator Action. |
| `chief_guardian_listener.py` | Legacy Guardian/HITL listener transport with approval, send, and sync signals. | High | `systemd/user/chief-guardian-listener.service.in` | SQLite Operator Action / Guardian HITL contract and decision receipts. |
| `chief_listener.py` | Central Chief listener/router surface with approval, send, shell/process, scheduler, and sync signals. | High | `systemd/user/chief-listener.service.in`; `start_chief_logged.sh` | Deterministic Chief control-plane over governed intake and Work Board. |
| `producer_listener.py` | Producer/Niles-adjacent listener with scheduler, send, shell/process, and sync signals. | High | `scripts/run_producer_listener.sh` | Module-scoped Producer/Niles work packets with Guardian-gated actions. |

## Shared Replacement Contract

Every replacement must preserve these rules:

- `runtime_authority=false` until a separate approval lane explicitly changes it.
- `callers_switched=false` until replacement equivalence is proven.
- `old_entrypoint_deleted=false`.
- `services_disabled=false`.
- `direct_execution_allowed=false` for legacy surfaces.
- No high-risk script execution during replacement work.
- No raw command/freeform shell approval.
- No send, deploy, runtime, sync bridge, or external action without an exact
  Operator Action / Guardian-approved packet.
- Inputs must be typed and bounded; raw logs, secrets, env files, raw Telegram
  logs, private/client raw data, bank/spreadsheet cells, and no-go roots remain
  out of scope.
- Outputs must be deterministic records, receipts, generated read-models, or
  review-only packets.

## Surface Replacement Plans

### `cassandra_listener.py`

What it currently does:

- Static evidence marks it as a Cassandra listener/intake surface.
- It has approval/HITL, daemon/listener, importer/exporter, send/API,
  shell/process, and sync bridge signals.
- It is referenced by a systemd user service template and
  `start_cassandra_core.sh`.

Why it is unsafe as-is:

- It can behave like a live listener without first passing through the governed
  intake spine.
- Send/API and shell/process signals make it unsafe as an autonomous entrypoint.
- Static service/start references mean caller switches or service edits need
  proof and rollback.

Governed path:

- `telegram_agent_intake` or equivalent receive metadata
  -> `governed_intake_spine`
  -> `intent_router`
  -> `work_board`
  -> `agent_work_packet`
  -> `operator_action` / `operator_action_inbox` / Guardian HITL for any action.
- Cassandra memory facts should route through the memory authority substrate,
  not ad hoc listener state.
- Sync posture should be read-model/export based, not listener-owned authority.

Required inputs:

- Source surface id: `cassandra_listener.py`.
- Typed intake metadata and source refs.
- Tenant/owner scope when available.
- Idempotency key.
- Sensitivity and raw-content policy.
- No-send/no-runtime flags.

Required outputs/receipts:

- Intake shadow record.
- Intent route summary.
- Work Board candidate card or explicit triage outcome.
- Agent Work Packet only for bounded work.
- Operator Action request only for send/runtime/external action.
- Guardian receipt/read-model for any approved action.

Required HITL/Guardian boundary:

- No direct reply/send from listener replacement.
- No shell/process action.
- No freeform command approval.
- Any external action requires immutable Operator Action payload, exact action
  binding, TTL, idempotency, operator/Guardian approval, and receipt.

Mapping:

- Work Board: yes.
- Agent Work Packet: yes, for bounded tasks.
- Operator Action: yes, for any action proposal.
- Memory authority: yes, for parsed facts only.
- Sync bridge: read-model/export posture only.
- Module registry: yes, as part of `cassandra_clara_fact_intake` /
  `operator_comms_stack` boundaries.

Tests needed before implementation:

- Shadow replacement does not import or execute `cassandra_listener.py`.
- Unknown input routes to review/triage.
- Send/runtime/shell paths remain false.
- Work Board / Agent Work Packet outputs are deterministic.
- Operator Action is required for any action-capable proposal.
- Static service references are represented but untouched.

Must remain blocked until replacement is proven:

- Direct listener activation.
- Service/caller switch.
- Reply/send path.
- Runtime recovery action.
- Shell/process execution.
- Sync bridge authority.

Rollback/stop conditions:

- Stop if implementation would require raw logs, secrets, private data, live
  Telegram payloads, service edits, caller switching, or runtime activation.
- Rollback for shadow work is deleting/reverting generated shadow records only;
  no runtime rollback should be needed because runtime must remain untouched.

### `chief_guardian_listener.py`

What it currently does:

- Static evidence marks it as a legacy Guardian/HITL listener transport.
- It carries approval/HITL, listener, send/API, importer/exporter, and sync
  bridge signals.
- It is referenced by `systemd/user/chief-guardian-listener.service.in`.

Why it is unsafe as-is:

- It may keep legacy approval transport paths alive beside the newer SQLite
  Operator Action / Guardian contract.
- Listener and send signals make it unsafe as direct authority.
- Service-template references make runtime edits unsafe without proof.

Governed path:

- Operator Action Inbox
  -> Guardian HITL SQLite authority contract
  -> decision receipt shadow/proof
  -> read-model/operator packet.

Required inputs:

- Operator Action request id.
- Exact action type and immutable payload hash.
- Idempotency key and TTL.
- Legacy callback/reference id when compatibility mapping is needed.
- No raw command text or freeform shell content.

Required outputs/receipts:

- Canonical Operator Action state.
- Guardian decision receipt.
- Legacy compatibility mapping record while old listener remains present.
- Mismatch/unknown callback record that cannot approve anything.

Required HITL/Guardian boundary:

- Old listener transport must not be treated as canonical approval authority.
- SQLite Operator Action / Guardian contract is the target authority.
- Unknown callback or id mismatch is review-only and cannot approve action.
- No send/deploy/runtime action without explicit approved packet.

Mapping:

- Work Board: indirect, via action request origin.
- Agent Work Packet: indirect, via approved task packets.
- Operator Action: primary target.
- Memory authority: no, except receipts as evidence.
- Sync bridge: read-model/export posture only.
- Module registry: `guardian_hitl_gate` substrate.

Tests needed before implementation:

- Legacy callback shadow maps to Operator Action shape without authority change.
- Unknown/mismatched callback cannot approve.
- No raw callback payload stored.
- Old listener/service template untouched.
- Runtime authority remains false.

Must remain blocked until replacement is proven:

- Caller switch from legacy listener to SQLite-only path.
- Service disable/delete/rename.
- Any direct Guardian send/approval expansion.

Rollback/stop conditions:

- Stop if mapping requires raw Telegram logs, secrets, private callback bodies,
  service edits, or live listener activation.
- Rollback only generated compatibility/shadow read-model rows in first lanes.

### `chief_listener.py`

What it currently does:

- Static evidence marks it as the central Chief listener/router surface.
- It carries approval/HITL, daemon/listener, scheduler/watchdog, send/API,
  shell/process, importer/exporter, and sync bridge signals.
- It is referenced by `systemd/user/chief-listener.service.in` and
  `start_chief_logged.sh`.

Why it is unsafe as-is:

- A central listener can become broad autonomous control-plane authority.
- Send/API and shell/process signals are incompatible with direct runtime use
  unless every action is packet-bound and approved.
- It overlaps Cassandra/Chief utility and module cleanup boundaries.

Governed path:

- Deterministic Chief control-plane over:
  - `governed_intake_spine`
  - `intent_router`
  - `work_board`
  - `agent_work_packet`
  - `operator_action`
  - Guardian HITL receipts.
- Chief should route and summarize; it should not directly execute, send, or
  mutate authority state.

Required inputs:

- Typed operator intent or system event metadata.
- Source id and owner scope.
- Module/stack hint when known.
- No raw private bodies.
- No freeform shell command payloads.

Required outputs/receipts:

- Intent record.
- Work Board card or triage result.
- Agent Work Packet for bounded work.
- Operator Action request for any action.
- Read-model status packet showing no runtime authority change.

Required HITL/Guardian boundary:

- Any send/runtime/external action must go through Operator Action / Guardian.
- Chief cannot approve its own action.
- No global single-tenant memory authority from ad hoc state.

Mapping:

- Work Board: primary.
- Agent Work Packet: primary for bounded implementation work.
- Operator Action: primary for action requests.
- Memory authority: read/summary only through governed memory substrate.
- Sync bridge: read-model/export posture only.
- Module registry: `chief_control_plane` / `operator_comms_stack` boundary.

Tests needed before implementation:

- Chief replacement shadow converts sample intent metadata into intent/work-board
  shape without executing code.
- No send/runtime/shell authority is created.
- Unknown intent routes to triage.
- Module/stack hints remain metadata-only.
- Existing listener/start references remain untouched.

Must remain blocked until replacement is proven:

- Live listener activation.
- Caller switch.
- Direct send.
- Shell/process execution.
- Autonomous task execution.
- Ad hoc memory writes.

Rollback/stop conditions:

- Stop if implementation needs live listener state, raw private data, service
  edits, caller switching, or runtime activation.
- Rollback only generated shadow/read-model artifacts for the first safe lanes.

### `producer_listener.py`

What it currently does:

- Static evidence marks it as a Producer/Niles-adjacent listener with scheduler,
  send/API, shell/process, importer/exporter, and sync bridge signals.
- It is referenced by `scripts/run_producer_listener.sh`.

Why it is unsafe as-is:

- It can activate a listener through a shell launcher without module boundary
  proof.
- Producer/Niles work may touch creative/project state and send/sync surfaces.
- It is not yet reconciled as a governed module/stack.

Governed path:

- Module registry / project capsule boundary
  -> Work Board lane
  -> Agent Work Packet
  -> review-only artifacts
  -> Operator Action / Guardian only for external actions.
- Producer/Niles work should first become module-scoped planning and packet
  generation, not autonomous listener runtime.

Required inputs:

- Module id or project capsule id.
- Album/producer task metadata only.
- Source refs and sensitivity policy.
- No raw private content unless a later approved ingest lane permits it.

Required outputs/receipts:

- Module-scoped work packet.
- Project capsule linkage if needed.
- Review-only Niles/producer packet.
- Operator Action request for send/external/API action only.
- Generated read-model showing no runtime authority.

Required HITL/Guardian boundary:

- No send/API behavior without immutable Operator Action / Guardian approval.
- No listener activation through shell launcher.
- No project mutation outside governed work packets.

Mapping:

- Work Board: yes.
- Agent Work Packet: yes.
- Operator Action: yes, only for external actions.
- Memory authority: later, if album/project facts become governed evidence.
- Sync bridge: read-model/export posture only.
- Module registry: yes, likely `niles_album_matrix` or Producer/Niles stack.

Tests needed before implementation:

- Producer/Niles replacement shadow does not execute launcher or listener.
- Module id/project capsule metadata is required.
- Send/API posture remains false.
- Work packet output is deterministic.
- Shell launcher remains untouched.

Must remain blocked until replacement is proven:

- `scripts/run_producer_listener.sh` activation.
- Direct listener execution.
- Send/API behavior.
- Autonomous producer task execution.

Rollback/stop conditions:

- Stop if implementation needs raw project/private content, launcher edits,
  service activation, sends, or runtime execution.
- Rollback only generated replacement shadow artifacts for early lanes.

## First Smallest Safe Implementation Lane

Recommended lane:

`Cassandra Listener Governed Intake Shadow Replacement v0`

Why this is first:

- `cassandra_listener.py` directly blocks Cassandra/Chief utility.
- It already has a clear target: governed intake spine -> Work Board -> Agent
  Work Packet -> Operator Action / Guardian.
- A shadow/read-model adapter can be built without changing runtime behavior or
  switching callers.

Allowed first implementation scope:

- Create a metadata-only replacement shadow read-model for `cassandra_listener.py`.
- Represent legacy static references.
- Map expected governed inputs/outputs.
- Prove no send/runtime/shell authority.
- Do not import live data.
- Do not execute or import `cassandra_listener.py`.
- Do not edit systemd templates or start scripts.

Not safe yet:

- Service disable.
- Launcher edit.
- Caller switch.
- Runtime activation.
- Send/reply path.
- Sync bridge authority.
- Replacing all four surfaces at once.

## Validation Expectations For Future Lanes

Future replacement implementation lanes should run focused tests proving:

- No high-risk script import/execution.
- No Repo B execution.
- No raw/private/no-go content read.
- Runtime authority remains false.
- Callers remain unswitched.
- Services/launchers remain untouched.
- Outputs are deterministic JSON/operator read-models or SQLite records.
- Operator Action / Guardian boundaries are explicit for every action-capable
  path.
