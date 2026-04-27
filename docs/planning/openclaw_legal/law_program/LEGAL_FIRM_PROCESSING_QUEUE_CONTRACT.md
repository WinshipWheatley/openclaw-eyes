

# LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT

## Purpose

OpenClaw Legal must give the firm a visible, auditable processing queue for discovery intake, extraction, search preparation, review packet creation, and future distributed work.

The queue should let multiple lawyers submit work without chaos. It should show what is waiting, what is running, who requested it, which matter it belongs to, what resources are being used, and when the work is likely to finish.

This contract defines the firm-level queue model that later supports intake automation, multi-node processing, adaptive ETA, and workload planning.

## Core doctrine

```text
All significant processing work should be queued, visible, prioritized, leased, audited, and recoverable.
```

The queue is not just a backend detail. It is part of the firm’s trust surface.

A lawyer should be able to know:

- whether their discovery is downloaded
- whether it has been registered
- whether processing has started
- whether it is blocked
- what computer(s) are working on it
- when results are expected
- what would reduce the wait

## Queue scope

The processing queue may eventually handle:

- discovery intake downloads/imports
- file registration and hashing
- TXT/MD/PDF extraction
- future OCR
- future email parsing
- future audio/video transcription
- local search indexing
- report generation
- review packet export
- unsupported-file diagnostics
- local repair/build attempts
- public analog fixture search
- model comparison/recheck tasks
- **attorney-approved rework batches**
- **claims-verification rechecks**
- distributed worker-node tasks

The first implementation should start narrower and deterministic.

## Queue levels

### Firm queue

The Firm Queue shows all active work across the firm, subject to the viewer’s permissions.

It should help the Primary Node and firm operator understand total workload and resource use.

### Matter queue

The Matter Queue shows work for a specific matter.

It should help the assigned lawyer understand what is happening on their case.

### User queue

The User Queue shows tasks requested by or assigned to a specific lawyer/staff member.

It should help lawyers see their own work without needing to inspect firm-wide operations.

## Task model

A queued task should include:

- task ID
- task group ID, if part of a batch
- matter ID
- requesting user
- requested timestamp
- task type
- source/artifact IDs involved
- priority
- required capabilities
- eligible node classes
- assigned/claimed node
- lease expiration, if distributed
- status
- progress
- ETA and confidence
- blocker reason, if blocked
- output artifact path(s)
- audit entries

Task groups should represent larger units such as:

- discovery batch
- extraction batch
- review packet generation
- model recheck batch
- unsupported-file repair attempt
- **attorney-authorized rework batch**

## Queue statuses

Recommended statuses:

```text
Planned
Downloading
Staged
Registered
Queued
Waiting for approval
Waiting for available node
Processing
Paused — user active
Paused — policy
Blocked
Failed
Completed
Review ready
Cancelled
```

Statuses should be plain-language and useful to legal staff.

## Discovery intake relationship

When a lawyer triggers discovery intake from an external system or staging folder, the queue should represent the work clearly:

```text
Discovery batch received
→ download/import
→ staging verification
→ source registration
→ processing plan
→ queued extraction/search preparation
→ review ready
```

The lawyer should be able to choose:

- start processing automatically after download
- wait for attorney approval
- schedule after hours
- mark as rush/high priority, if policy allows

The queue should preserve that policy decision.

## Priority model

Priorities should be explicit and auditable.

Possible priority levels:

- Low
- Normal
- High
- Rush
- After Hours

Priority should affect scheduling but must not override permissions, vault policy, node safety, or human-priority compute rules.

Rush priority should be logged and may require approval depending on firm policy.

## Node assignment and leases

The Primary Node should assign tasks based on:

- task type
- matter permission
- node capability
- node availability
- resource headroom
- local model availability
- current queue load
- user activity
- firm policy

Distributed tasks should use leases.

If a worker node drops offline or becomes unavailable:

- the lease expires
- partial progress is checkpointed if possible
- task is requeued
- audit records the interruption
- ETA is recalculated

Worker results must be validated by the Primary Node before acceptance.

## Human-priority behavior

If a lawyer begins using their workstation, that workstation should preempt background tasks.

The queue should reflect this without blaming the lawyer:

```text
Paused — Attorney A is using this computer
Requeued to Primary Node
ETA updated
```

The system should treat human use as expected, not as a failure.

## ETA relationship

The processing queue should display estimated start and completion time where possible.

ETA should include confidence.

Examples:

```text
Estimated completion: 4h 30m
Confidence: Medium
Reason: New node still calibrating
```

```text
Estimated start: after Jones batch completes, about 2h 10m
```

The queue should be conservative by default and should update as node/model performance data becomes available.

Detailed adaptive ETA rules are defined in `LEGAL_ADAPTIVE_ETA_CONTRACT`.

## Capacity recommendations

The queue may show capacity recommendations without hype.

Example:

```text
Primary Node only: about 14h
With 3 available firm computers: about 4h 30m
Confidence: Medium
```

After a new node or model begins processing real tasks, the queue should update estimates based on measured performance.

The system may explain:

- which nodes are available
- which nodes are busy
- which nodes are user-active
- which modules/models are bottlenecks
- estimated time saved by adding or enabling nodes

## Required behavior

- All significant processing work must be represented as queued tasks or task groups.
- Queue entries must be tied to matters and requesting users where applicable.
- Queue status must be visible according to permissions.
- Queue state must be auditable.
- Queue tasks must respect matter permissions and device/node permissions.
- Queue tasks must respect vault boundaries.
- Queue tasks must respect local-only policy.
- Queue tasks must not silently send matter data externally.
- Distributed tasks must use leases.
- ETA must be labeled by confidence where shown.
- Blocked tasks must explain why they are blocked.
- Cancelled/failed tasks must preserve audit history.

## Forbidden behavior

- Do not process matter data outside the queue for significant operations.
- Do not hide long-running work from the lawyer/operator.
- Do not run tasks on unauthorized nodes.
- Do not let priority override privacy/security policy.
- Do not let a worker node keep a task forever after going offline.
- Do not show fake precision in ETA.
- Do not treat active lawyer use as an error.
- Do not distribute matter data to worker nodes unless task/policy allows it.
- Do not allow queue manipulation to bypass matter permissions.
- Do not let external connector downloads auto-process without an explicit matter/intake policy.

## UX requirements

The queue UX should be calm, operational, and truthful.

A matter queue might show:

```text
State v. Example — Discovery Batch 2026-04-25
Status: Processing
Files: 438
Extracted: 311
Unsupported: 20
Blocked: 2
Estimated completion: 4h 30m
Confidence: Medium
Nodes: Primary Node, Paralegal iMac, Attorney B MacBook
```

A firm queue might show:

```text
Current Work
1. Jones discovery — Processing — ETA 4h 30m
2. Smith packet — Queued — starts in about 2h
3. Martinez PDF extraction — Blocked: approval needed
```

Blocked states should be actionable:

```text
Blocked: 2 unsupported files need Alternative Methods review
```

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Creating a processing request creates a queue task.
- Queue task includes matter ID, requesting user, task type, status, and audit entry.
- Unauthorized user cannot view another matter’s queue details.
- Worker node can claim only eligible tasks.
- Lease expiration requeues a task.
- User-active workstation pauses or releases background task.
- Priority changes are audited.
- Blocked task includes clear reason.
- ETA is labeled with confidence.
- Queue does not dispatch work to unauthorized nodes.
- Queue does not dispatch matter data outside vault/local policy.
- Cancelled task remains in audit history.

## Failure behavior

If queue scheduling cannot proceed safely, the system should fail closed or block the task.

Examples:

- If no authorized node is available, mark `Waiting for available node`.
- If matter permission cannot be verified, mark `Blocked`.
- If vault path validation fails, block the task.
- If a worker loses its lease, requeue the task.
- If a task fails, record error and preserve source files.
- If ETA cannot be estimated, show `ETA unavailable` with reason instead of guessing.
- If a user cancels a task, preserve cancellation audit.

## Notes for first law-firm v1 deployment

- Start with a single-machine queue before distributed execution.
- Queue visibility is commercially useful even before multi-node processing exists.
- The first queue should make extract-all, report, and review packet work visible.
- Avoid overbuilding complex scheduling before the firm validates the workflow.
- ETA may start conservative/simple, then become adaptive later.
- Queue + ETA will help firms understand why additional nodes improve throughput.

## Suggested implementation phases

1. Single-machine task queue for extraction/report/packet jobs.
2. Matter-level queue visibility.
3. Firm-level queue visibility.
4. ETA placeholder/confidence labels.
5. Discovery intake staging integration.
6. Lease model for worker nodes.
7. Node-aware scheduling.
8. Adaptive ETA and capacity recommendations.
9. Model/node calibration integration.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/task_queue.py`
- `legal/task_store.py`
- `legal/task_scheduler.py`
- `legal/task_leases.py`
- `legal/queue_eta.py`
- `legal/node_registry.py`
- `legal/resource_policy.py`
- `legal/discovery_intake.py`
- `legal/audit.py`
- `tests/test_firm_processing_queue.py`
- `tests/test_task_leases.py`
- `tests/test_queue_permissions.py`
- `tests/test_queue_eta_display.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT`

This contract supports:

- `LEGAL_ADAPTIVE_ETA_CONTRACT`
- `LEGAL_DISCOVERY_INTAKE_CONNECTOR_CONTRACT`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, multi-lawyer/multi-computer work will become invisible, unfair, or unreliable.