

# LEGAL_CONNECT_MENU_CONTRACT

## Purpose

OpenClaw Legal should include a Connect menu that lets a firm add, approve, view, pause, resume, and remove local computers from the firm system.

The Connect menu is how a law firm grows from one Primary Node into a private local legal work network. It should make additional lawyer workstations useful without creating silent access expansion, data leakage, or chaos.

The goal is a firm-local system where:

- the Primary Node owns vault, policy, updates, audit, orchestration, and model distribution
- lawyer workstations can serve as assigned-matter workstations
- approved computers can contribute bounded compute when idle
- human use always preempts background work
- every node has explicit permissions, task classes, and audit visibility

## Core doctrine

```text
No computer joins silently.
No node receives more access than explicitly approved.
The Primary Node remains the authority.
Human use always wins over background compute.
```

The Connect menu must feel simple to the firm, but the underlying model must be strict.

## Node classes

### Primary Node

The Primary Node is the firm-controlled main machine, likely a Mac Studio-class computer.

Responsibilities:

- owns the canonical Legal Vault
- owns firm profile and policy
- owns update manager
- owns model downloads and distribution
- owns task queue and orchestration
- owns audit records
- approves/denies node enrollment
- validates returned artifacts from worker nodes
- runs the largest approved local models
- maintains the authoritative view of matters and assignments

Forbidden:

- silently enrolling devices
- sending matter data externally by default
- allowing worker nodes to override policy
- allowing another node to become authority without explicit migration/failover plan

### Attorney Workstation Node

A lawyer’s MacBook Pro or desktop can be both a personal legal workstation and an optional compute node.

Responsibilities:

- show assigned matters
- receive shared review requests
- allow lawyer work on authorized matters
- optionally process bounded tasks when idle
- immediately yield resources when the lawyer uses the machine

Default posture:

- matter access follows attorney identity + approved device + matter assignment/share
- compute sharing defaults to Conservative or Balanced
- heavy model work defaults to Primary Node unless explicitly approved

### Worker Node

A worker node is an approved firm computer allowed to process bounded tasks.

Responsibilities:

- claim eligible tasks
- process within permission/task-class limits
- return artifacts to Primary Node
- preserve source files
- release task leases if unavailable
- obey resource headroom policy

Forbidden:

- becoming a second authority
- retaining matter data unless policy allows encrypted caching
- downloading models independently
- running tasks outside approved task classes

### Observer / Reviewer Node

A limited node for read-only or review-only access.

Responsibilities:

- view assigned/shared review materials
- comment or respond if permitted
- receive bounded review requests

Forbidden:

- source ingestion
- export
- policy changes
- update approval
- background compute unless explicitly converted to a worker node

## Connect menu screens

The Connect menu should include:

### This Computer

Shows:

- device name
- node class
- assigned user
- enrollment status
- current permissions
- compute sharing mode
- current task, if any
- local model status
- last sync/heartbeat
- resource state: user active, idle, battery, thermal pressure, memory pressure

### Firm Computers

Shows all approved nodes:

- Primary Node
- attorney workstations
- worker nodes
- observer/reviewer nodes
- offline nodes
- paused nodes
- nodes needing attention

Each row should show:

- node name
- node class
- assigned user
- status
- current task
- capabilities
- last seen
- ETA contribution where relevant

### Join / Approve

Supports:

- request to join firm system
- approve pending computer
- deny pending computer
- assign node class
- assign user
- assign default permissions
- assign resource mode

### Compute Sharing

Controls:

- Off
- Conservative
- Balanced
- Performance
- Overnight Only

Each mode should show plain-language impact.

### Matter Sharing

Supports future collaboration flows:

- send review request
- receive review request
- share bounded packet/materials
- revoke shared access
- show who can access what

### Node Health

Shows:

- online/offline
- heartbeat status
- local model availability
- available disk/RAM/CPU class
- current workload
- failed tasks
- pending updates
- calibration status

## Enrollment flow

A safe enrollment flow should be:

1. New computer opens OpenClaw Legal.
2. User selects `Join Firm System`.
3. New computer discovers or enters Primary Node address.
4. New computer sends a join request.
5. Primary Node shows pending request.
6. Authorized operator approves or denies.
7. Operator assigns node class, user, permissions, and resource mode.
8. Primary Node issues a signed/local enrollment token.
9. Node becomes visible in Firm Computers.
10. Node receives only permitted tasks and matter access.

No computer should auto-join because it is on the same network.

## Permission model

Node access should depend on:

```text
attorney identity + approved device + matter assignment/share + node permissions + firm policy
```

A user on an approved device does not automatically get all firm data.

A device on the network does not automatically get matter data.

A worker node does not automatically receive source files unless task/policy requires it.

## Matter assignment and workstation access

A lawyer should open the app and see:

- My Matters
- Shared With Me
- Review Requests
- Firm Queue, if permitted

For assigned matters, permissions may include:

- view sources
- search extracted text
- create notes
- generate reports
- request colleague review
- create review packets
- approve limited actions, if role allows

Permissions that should remain restricted by default:

- delete source files
- change matter policy
- export outside vault
- enable cloud tools
- approve updates
- alter firm profile

## Review handoff support

The Connect system should support lawyer-to-lawyer handoffs later.

Examples:

- Send for Review
- Opinion Request
- Privilege Review
- Timeline Check
- Draft Review
- Packet Review

A handoff should include:

- scoped materials
- sender
- recipient
- question/note
- permission scope
- due date, optional
- status
- audit trail

The receiving lawyer should see the request in `Shared With Me` or `Review Requests`.

## Human-priority compute

Attorney workstations may contribute compute only when it does not interfere with the lawyer.

The system should pause/checkpoint/release work when:

- user becomes active
- battery is low
- device is unplugged, if policy says so
- memory pressure rises
- CPU/thermal pressure rises
- video call or high-priority local task is detected, if available
- the lawyer manually pauses compute sharing

The UI should make this simple:

```text
Compute sharing: Balanced
Status: Paused — user active
```

## Task and lease model

Distributed processing should use a lease-based task model.

A task should include:

- task ID
- matter ID
- source/artifact ID
- task type
- required capability
- allowed node class
- assigned/claimed node
- lease expiration
- status
- progress
- output artifact path
- audit entries

If a node drops offline, the lease should expire and the Primary Node should requeue the work.

Worker results should be validated by the Primary Node before being accepted into the matter vault.

## Required behavior

- Connect menu must be explicit and approval-based.
- Primary Node must remain authoritative.
- Nodes must have explicit classes, permissions, and task eligibility.
- Node enrollment must be auditable.
- Worker tasks must be lease-based.
- Human use must preempt background compute.
- Worker nodes must obey resource headroom policy.
- Worker nodes must not independently download models.
- Worker nodes must not retain matter data unless policy allows encrypted caching.
- Worker nodes must report health/status.
- Matter sharing between lawyers must be bounded and audited.

## Forbidden behavior

- Do not auto-enroll computers from the local network.
- Do not grant broad vault access to a node by default.
- Do not make worker nodes independent authorities.
- Do not let worker nodes override Primary Node policy.
- Do not let worker nodes download models independently.
- Do not run heavy background work while the lawyer is actively using the computer.
- Do not retain source files on worker nodes unless policy permits.
- Do not share matter access between attorneys without explicit assignment/share.
- Do not use internal OpenClaw names in node/role UX.

## UX requirements

The Connect menu should feel calm and predictable.

Example status lines:

```text
Primary Node: Online
Attorney A MacBook: Available, Balanced compute
Attorney B MacBook: Paused — user active
Paralegal iMac: Processing extraction batch
Conference Room Mac: Offline
```

The UI should show when adding nodes changes throughput, but should not oversell.

Example:

```text
3 approved computers are available.
Using them may reduce this batch estimate by about 2 hours.
Confidence: Medium — still calibrating Attorney B MacBook.
```

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Pending node cannot join without approval.
- Approved node receives only its assigned node class/permissions.
- Unknown node cannot access matter vault.
- Attorney workstation sees only assigned/shared matters.
- Worker node can claim only eligible task classes.
- Lease expiration requeues task after worker dropout.
- User activity pauses workstation compute.
- Worker cannot retain matter data when retention policy forbids it.
- Worker cannot independently download models.
- Primary Node records enrollment, task claim, task completion, and failures in audit.
- Review handoff shares only scoped material.

## Failure behavior

If connection or node policy fails, the system should fail closed.

Examples:

- If node identity cannot be verified, deny enrollment.
- If Primary Node is unreachable, worker must not process new tasks.
- If task lease expires, requeue work.
- If worker returns invalid artifact, reject it and record failure.
- If user becomes active, pause/checkpoint background task.
- If node attempts unauthorized matter access, block and audit.
- If model version mismatch occurs, hold model-dependent tasks until resolved.

## Notes for first law-firm v1 deployment

- The first version does not need full distributed compute.
- A Connect menu skeleton can first show only the Primary Node and this computer.
- Worker enrollment should come after vault/profile/permission boundaries are strong.
- Deterministic distributed jobs should come before distributed LLM tasks.
- Review handoff can be useful before full worker compute.
- Keep node UX simple enough that a law firm does not need IT expertise to understand it.

## Suggested implementation phases

1. Single-machine Legal v1 with strict vault/profile/update boundaries.
2. Identity and matter assignment model.
3. Connect menu skeleton showing Primary Node / this computer.
4. Review handoff workflow.
5. Worker node enrollment.
6. Deterministic distributed jobs: hash, extract, search index, packet assembly.
7. Model routing and distributed local LLM tasks, heavily gated.
8. Local repair/build/update system.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/connect_menu.py`
- `legal/node_registry.py`
- `legal/node_enrollment.py`
- `legal/node_permissions.py`
- `legal/task_queue.py`
- `legal/task_leases.py`
- `legal/node_health.py`
- `legal/review_handoff.py`
- `legal/resource_policy.py`
- `legal/model_distribution.py`
- `tests/test_node_enrollment.py`
- `tests/test_node_permissions.py`
- `tests/test_task_leases.py`
- `tests/test_human_priority_compute.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_ROLE_NAMING_CONTRACT`

This contract supports:

- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT`
- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`
- `LEGAL_ADAPTIVE_ETA_CONTRACT`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, adding computers will feel powerful but unsafe.