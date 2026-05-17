# Active Machinery High-Risk Quarantine Spec v0

This is a planning/spec packet only. It does not move, delete, rename, disable,
or edit runtime files. It defines the smallest safe quarantine path for high-risk
active machinery identified by:

- `generated/read_models/active_machinery_operator_disposition.json`
- `generated/read_models/active_machinery_operator_disposition_OPERATOR.md`
- `docs/operations/ACTIVE_MACHINERY_OPERATOR_DISPOSITION_V0.md`

## Quarantine Doctrine

High-risk machinery is not automatically bad. It is unsafe when it can listen,
watch, send, mutate state, launch subprocesses, or bridge systems without the
current governed spine.

Quarantine should start with visibility and policy, not destructive cleanup.

Allowed first implementation:

- generated read-model warning
- docs warning
- metadata denylist for launch/activation planning
- no runtime behavior change
- no service disable
- no rename
- no file move/delete

Not allowed in the first implementation:

- disabling systemd/user services
- editing runtime files
- renaming scripts
- moving files
- deleting files
- changing launchers
- blocking tests
- changing send/Telegram/Gmail behavior
- enabling replacement paths

## Static Reference Finding

A tracked-file static reference check found references that matter for planning,
but it did not prove live runtime state.

Important static references:

- `systemd/user/chief-listener.service.in` points at `chief_listener.py`.
- `systemd/user/chief-watcher-brain.service.in` points at `chief_watcher_brain.py`.
- `systemd/user/cassandra-listener.service.in` points at `cassandra_listener.py`.
- `systemd/user/cassandra-watcher.service.in` points at `cassandra_watcher.py`.
- `systemd/user/chief-guardian-listener.service.in` points at `chief_guardian_listener.py`.
- `start_cassandra_core.sh` starts `cassandra_listener.py` and `cassandra_watcher.py`.
- `start_chief_logged.sh` starts `chief_listener.py`.
- `loop_supervisor.sh` restarts `builder_watcher.sh`.
- `scripts/run_producer_listener.sh` starts `producer_listener.py`.
- `retry_send_demo_dashboard.sh` invokes `send_demo_dashboard.py`.
- Several Chief brains reference `chief_sender.py`.
- Guardian/HITL docs and code reference `chief_guardian_sender.py`.

These references mean file rename, service disable, or launcher edits are not
safe as a first step. They require an explicit operator-approved implementation
lane with rollback.

## First Safe Quarantine Shape

The first safe implementation lane should create only a review/read-model
quarantine surface:

- `generated/read_models/active_machinery_high_risk_quarantine.json`
- `generated/read_models/active_machinery_high_risk_quarantine_OPERATOR.md`
- optional query/export script if consistent with repo patterns
- tests proving no runtime files are changed and no launch behavior changes

The read-model should mark each high-risk live/script item with:

- `quarantine_status`
- `activation_allowed=false`
- `runtime_changed=false`
- `service_disabled=false`
- `files_moved_or_deleted=false`
- `operator_approval_required_for_runtime_change=true`
- `first_safe_action=generated_read_model_warning`

## Item Quarantine Plan

| File | Current disposition | Why risky | Quarantine meaning now | Static active-service/reference status | Must prove before action | Rollback plan | Tests needed | Operator approval needed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `builder_watcher.sh` | `block_no_go` | Builder/watchdog loop can launch runner workflows and is referenced by restart-style supervision. | `denylist` + `docs warning` + `generated read-model warning`; no rename/disable yet. | Referenced by `loop_supervisor.sh`, `polish_loop/orchestrator.py`, runner docs/tests. Static reference suggests activation risk. | Prove no active supervisor depends on it, prove Work Board / Operator Action replacement, prove no runner launch path is still needed. | Remove denylist/read-model warning only; no runtime rollback should be needed because first lane is metadata-only. | Assert quarantine read-model marks activation disallowed; assert no runtime files edited; assert no launcher invocation. | Yes for any runtime block/rename/disable; no for metadata-only warning. |
| `cassandra_listener.py` | `replace_with_governed_path` | Telegram/listener-style Cassandra intake with send/HITL/sync signals should not bypass governed intake. | `generated read-model warning`; later `wrapper guard` or governed replacement. | Referenced by `systemd/user/cassandra-listener.service.in`, `start_cassandra_core.sh`, `telegram_agent_intake.py`, and Cassandra runtime audit docs. | Prove governed intake replacement covers receive, classification, Work Board projection, receipts, and no-send posture. | Revert only generated warning for phase 1; for later wrapper changes, keep old service file intact until replacement proof. | Assert warnings include service-template reference; assert activation remains disallowed; focused Cassandra intake tests before later wrapper. | Yes before wrapper/service/caller changes. |
| `cassandra_watcher.py` | `retire_later` | Watcher/shell/send signals indicate ambient runtime risk and likely superseded governed flows. | `generated read-model warning` + `retire candidate`; no deletion. | Referenced by `systemd/user/cassandra-watcher.service.in`, `start_cassandra_core.sh`, Cassandra capability docs, and runtime audit tests. | Prove watcher behavior has governed equivalent or is no longer needed; prove no active service uses it. | Remove retirement warning if needed; no file rollback because no file change in first lane. | Assert marked `retire_later_not_deleted`; assert no old HITL/send path change. | Yes before retirement, service disable, or delete. |
| `chief_brainstorm_watcher.py` | `retire_later` | Chief watcher/state-mutator signals are not on the current canonical Work Board path. | `generated read-model warning` + `retire candidate`; no deletion. | Referenced by current-state docs and legacy Trinity/scan surfaces; no service template found in the static check. | Prove brainstorming watcher has no active launcher and any useful logic is represented by Work Board or future governed intake. | Remove warning; no runtime rollback for metadata-only lane. | Assert retire candidate remains non-destructive; assert no watcher launch. | Yes before retirement/delete. |
| `chief_email_brain.py` | `wrap_with_guardian` | Email/send capability can affect external recipients if activated. | `wrapper guard required` + `generated read-model warning`; no send enablement. | Referenced by current-state docs, known gaps, Trinity audit, and file-path scans; no service template found. | Prove all outputs are draft-only by default; prove immutable Operator Action / Guardian approval before send. | Revert warning only in phase 1; later wrapper must be behind feature-free no-send tests. | Assert send authority remains false; assert no credentials/env read; assert wrapper-required flag. | Yes before any send-capable runtime use. |
| `chief_guardian_listener.py` | `replace_with_governed_path` | Legacy Guardian listener is an approval/HITL transport surface and may keep old authority paths alive. | `generated read-model warning`; later replace with SQLite Operator Action / Guardian contract. | Referenced by `systemd/user/chief-guardian-listener.service.in`, Guardian reconciliation docs/code, and Telegram intake surfaces. | Prove SQLite Operator Action / Guardian path covers callback/decision receipt semantics before caller switch. | Remove warning only for first lane; later preserve compatibility until receipt equivalence is proven. | Assert marked compatibility/replacement; assert old HITL not deleted; assert no caller switch. | Yes before service/caller changes. |
| `chief_guardian_sender.py` | `wrap_with_guardian` | Guardian sender is send-capable approval transport; dangerous if treated as authority or arbitrary send path. | `wrapper guard required` + `generated read-model warning`; no send enablement. | Referenced by Guardian reconciliation/contract/disposition code and HITL flowchart. | Prove notification-only semantics, exact action binding, no raw/freeform send payload, and receipt recording. | Remove warning only in phase 1; later revert wrapper if it changes approval delivery unexpectedly. | Assert send path remains disabled unless approved packet exists; assert no raw command approval. | Yes before send/caller changes. |
| `chief_listener.py` | `replace_with_governed_path` | Central listener can route commands and sends; current direction is deterministic control-plane over governed intake. | `generated read-model warning`; later replace/wrap entrypoint. | Referenced by `systemd/user/chief-listener.service.in`, `start_chief_logged.sh`, current-state/runbook docs, Telegram intake, and approval choice docs. | Prove governed intake and Chief control-plane can cover current receive/routing without direct autonomous authority. | Remove warning only in phase 1; for later caller changes, keep old entrypoint restorable. | Assert no service disable; assert runtime authority unchanged; later add control-plane equivalence tests. | Yes before wrapper/caller/service changes. |
| `chief_sender.py` | `wrap_with_guardian` | Send-capable Telegram path is referenced by other Chief brains and can affect external/chat state. | `wrapper guard required` + `generated read-model warning`; no send enablement. | Referenced by Chief approval, billing, invoice, watcher, album, and current-state docs. | Prove all sends originate from immutable approved packets with exact recipient binding and receipt proof. | Remove warning only in phase 1; later wrapper must be reversible and not block existing approved paths without plan. | Assert no raw command text, no env/credential access in tests, no send without approved packet. | Yes before send-path wrapper/caller changes. |
| `chief_watcher_brain.py` | `block_no_go` | Watcher plus shell/process and state-mutator signals; static references indicate active service posture. | `denylist` + `generated read-model warning`; no service disable yet. | Referenced by `systemd/user/chief-watcher-brain.service.in`, current-state/runbook docs, Guardian reconciliation, and approval replay docs. | Prove watcher function is replaced by bounded Work Board/receipt flow, or prove it is inactive and safe to retire. | Remove warning only in phase 1; for later service changes, keep unit file and startup restoration instructions. | Assert activation disallowed; assert service templates untouched; assert old approval state untouched. | Yes before service disable/rename/delete. |
| `producer_listener.py` | `replace_with_governed_path` | Producer/Niles listener has listener/scheduler/send/sync signals and a launcher. | `generated read-model warning`; later governed Producer/Niles module boundary. | Referenced by `scripts/run_producer_listener.sh`, `agent_presence.py`, `telegram_agent_intake.py`, and read-models. | Prove Producer/Niles module boundary, no-send default, and Guardian/HITL routing before activation. | Remove warning only in phase 1; later keep launcher restorable until replacement proven. | Assert no listener launch; assert no send/daemon enablement; add Niles boundary tests later. | Yes before runtime use. |
| `retry_send_demo_dashboard.sh` | `block_no_go` | Shell retry path invokes send demo dashboard and could normalize a demo send path. | `denylist` + `generated read-model warning`; no rename/delete. | Directly invokes `send_demo_dashboard.py`; no service template found. | Prove it is a no-send fixture or replace with read-only dashboard proof. | Remove warning only in phase 1. | Assert marked demo-send blocked; assert no shell invocation. | Yes before any demo send use or deletion. |
| `scripts/run_producer_listener.sh` | `block_no_go` | Shell launcher starts `producer_listener.py`; can activate listener without governed runtime approval. | `denylist` + `generated read-model warning`; no chmod/rename/delete. | Direct launcher for `producer_listener.py`; referenced by `agent_presence.py` and `telegram_agent_intake.py`. | Prove Producer listener has governed contract and operator-approved activation lane. | Remove warning only in phase 1; later preserve launcher restoration if changed. | Assert launcher remains unmodified; assert activation_allowed=false. | Yes before launcher changes or service activation. |
| `send_demo_dashboard.py` | `block_no_go` | Demo sender has send/API signals and is invoked by retry shell script. | `denylist` + `generated read-model warning`; no rename/delete. | Invoked by `retry_send_demo_dashboard.sh`; file-path scan references it. | Prove it is read-only/no-send or replace with review-only dashboard artifact. | Remove warning only in phase 1. | Assert demo send surface marked blocked; assert no network/send action. | Yes before use/delete/replacement. |

## Test-Only High-Risk Rows

These are not runtime quarantine targets in the first implementation:

- `tests/test_cassandra_email_thread_analysis.py`
- `tests/test_chief_listener_lifecycle.py`
- `tests/test_send_truth.py`

They should remain `keep_test_only`. Future cleanup can improve names or mocks, but
they should not be treated as live active machinery unless a separate audit proves
they expose a real runtime path.

## Implementation Readiness

The first implementation is safe only if it is metadata/read-model warning
work. It must not touch runtime files or services.

Ready now:

- create a generated quarantine read-model
- create an operator Markdown warning packet
- optionally add a query/export helper following existing read-model patterns
- add tests proving no runtime files changed and all high-risk live/script items
  have warning/quarantine metadata

Not ready now:

- service disable
- file rename
- file deletion
- chmod changes
- launcher edits
- caller switch
- send wrapper changes
- Guardian/HITL adapter changes

## Recommended First Implementation Lane

`Active Machinery High-Risk Quarantine Read-Model v0`

Goal: generate a non-authoritative quarantine/readiness read-model that marks
the 14 high-risk live/script items as activation-disallowed and records the
required proof before any later runtime change.

The lane should produce:

- `generated/read_models/active_machinery_high_risk_quarantine.json`
- `generated/read_models/active_machinery_high_risk_quarantine_OPERATOR.md`
- focused tests

It must not move, delete, rename, chmod, disable, activate, or wrap runtime
files.
