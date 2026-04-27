# OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec

## Purpose

OpenClaw Legal should present a controlled, calm, truthful legal operations console — not a loose folder of files, not an Obsidian-only vault, and not an experimental agent swarm.

The console must help a law-firm operator or lawyer feel confident because the system is actually bounded, inspectable, local-first, and honest about what it has and has not processed.

This spec defines the first controlled UX target for OpenClaw Legal.

## Core doctrine

```text
Operator confidence must reflect actual system quality.
```

The UX must never create false confidence. It should show real status, blockers, unsupported files, ETA confidence, audit state, local-only state, and review requirements.

The system should be stress-reducing because it is clear and reliable, not because it hides uncertainty.

## Product posture

The console should feel like:

```text
A private local legal operations system for discovery intake, evidence processing, review coordination, and audit-safe output.
```

It should not feel like:

```text
A chatbot making legal guesses.
A generic file browser.
A plugin-heavy Obsidian workspace.
A magical autonomous legal brain.
A system that replaced attorney judgment.
```

## UX principles

- Local-first status should be visible.
- Matter data boundaries should be visible.
- Unsupported files should be actionable.
- ETAs should be conservative and confidence-labeled.
- Updates should be understandable and non-surprising.
- Permissions should be explainable.
- Review handoffs should feel natural to lawyers.
- The system should show “partial,” “blocked,” “needs review,” or “unsupported” when true.
- Internal OpenClaw names must not appear in the legal UX.
- Attorney judgment must remain clearly outside the system.

## Primary navigation

The first controlled console should eventually include these top-level areas.

### 1. Matters

Purpose:

- create/open matters
- show assigned matters
- show shared/review matters
- show matter safety status
- show matter processing status

Key UI elements:

- My Matters
- Shared With Me
- Review Requests
- Matter status cards
- Local-only / vault status
- assigned users and permissions

Example status:

```text
State v. Example
Status: Processing discovery
Local-only: ON
Sources: 438
Extracted: 311
Unsupported: 20
Needs review: 7
ETA: about 4h 30m, Confidence: Medium
```

### 2. Sources

Purpose:

- add/register discovery files
- show hash/source IDs
- show extraction status
- show unsupported files
- show metadata completeness

Key UI elements:

- Add Sources
- Source inventory
- Hash/status columns
- File type grouping
- Unsupported files with Alternative Methods
- Source audit entries

Example statuses:

```text
Registered
Extracted
No extractable text
Unsupported
Failed
Needs Alternative Methods
```

### 3. Extract / Processing

Purpose:

- run extract-all
- show processing queue
- show task status
- show blocked/failed items
- show node usage where available

Key UI elements:

- Start Processing
- Schedule After Hours
- Wait for Approval
- Processing Queue
- Task groups
- ETA confidence
- Blocked reasons

Example:

```text
Discovery Batch 2026-04-25
Status: Processing
Nodes: Primary Node, Paralegal iMac
ETA: about 4h 30m
Confidence: Medium — new node calibrating
```

### 4. Search / Review

Purpose:

- search extracted matter text
- show source-grounded snippets
- route review requests
- prepare attorney-facing review outputs

Key UI elements:

- Search box
- Result snippets
- Source IDs
- Original filenames
- Hash/citation metadata
- Send for Review
- Save to report

Search should be source-grounded. It should not pretend to know more than extracted artifacts support.

### 5. Packet / Export

Purpose:

- generate review packets
- show included/excluded artifacts
- keep exports inside vault by default
- require approval for external export

Key UI elements:

- Generate Review Packet
- Packet contents preview
- Manifest/audit inclusion
- External export warning
- Packet path
- Export history

Example warning:

```text
External export requires approval.
This may copy sensitive matter data outside the protected Legal Vault.
```

### 6. Connect

Purpose:

- add/approve firm computers
- show Primary Node and workstations
- configure compute sharing
- monitor node health
- support future review handoff and distributed processing

Key UI elements:

- This Computer
- Firm Computers
- Join Firm System
- Approve Pending Computer
- Compute Sharing
- Node Health
- Matter Sharing

Example status:

```text
Attorney B MacBook
Status: Paused — user active
Compute sharing: Balanced
Current model: ReviewLite v1.1
New model staged: ReviewLite v1.2
```

### 7. Queue

Purpose:

- show firm/matter/user processing work
- show ETAs
- show priority
- show blockers
- show resource recommendations

Key UI elements:

- Firm Queue
- Matter Queue
- My Queue
- ETA confidence
- Node usage
- Capacity recommendations
- Blocked tasks

Example:

```text
Primary Node only: about 14h
With 3 available firm computers: about 4h 30m
Confidence: Medium
```

### 8. Updates

Purpose:

- show security/stability/module/new-capability updates
- preserve firm stability
- prevent surprise workflow changes
- show rollback and test status

Key UI elements:

- Security Updates
- Stability Updates
- Installed Module Updates
- Optional New Modules
- Update detail view
- Tests passed
- Rollback available
- Matter data touched: yes/no

Example:

```text
Installed Module Update: PDF Extractor v1.2
Workflow changes: No
Matter data touched: No
Rollback: Available
Tests passed: 42
```

### 9. Alternative Methods

Purpose:

- handle unsupported files safely
- show local attempts
- show local build/repair options
- show non-local options and risks
- unlock Request Feature only after local attempt fails or is policy-blocked

Key UI elements:

- Try Local Capability
- View Technical Details
- View Failed Attempts
- Try Local Capability Build
- View Non-Local Options
- Request Feature, gated
- Sanitized Support Packet
- Public Analog Candidates

Request Feature should not be visible until the local pathway has been attempted or policy-blocked.

### 10. Attorney-Gated QA / Review-and-Rework

Purpose:

- review system-generated candidates (timelines, contradictions, summaries)
- verify claims against source records
- manage evidence-verification flags
- authorize rework for rejected or cautionary items
- ensure no silent fixes or unreviewed legal conclusions

Key UI elements:

- Candidate List (e.g., Draft Timelines, Factual Claims)
- Checker View: Verified claims, caution flags, possible errors
- Flag Indicators:
  - **Green:** High-confidence source-supported insight
  - **Yellow:** Caution/ambiguity/low confidence
  - **Red:** Possible system error/unsupported claim
- Source Deep-Dive: Links to source ID, page, frame, or timestamp
- Lawyer Action Menu:
  - Approve Rework
  - Reject Flag
  - Defer
  - Mark Needs Manual Review
  - Mark Attorney-Reviewed
- Rework Status: Pending lawyer approval, In progress, Verified
- Verification Sentinel status (for system reliability check)

Example:

```text
Claim: Speaker A at 14:02:05 mentioned X.
Status: [Yellow Flag]
Reason: Timestamp in source is 14:02:15.
Lawyer Action: [Approve Rework]
```

## Confidence/status bar

The console should have a persistent confidence/status bar.

Suggested fields:

```text
Local-only: ON
Cloud tools: OFF
Legal Vault: Connected
Matter audit: ON
Sources: 438
Extracted: 311
Unsupported: 20 [Alternative Methods]
Needs review: 7
ETA confidence: Medium
Packet ready: No
```

The bar should be actionable. Unsupported count opens Alternative Methods. ETA confidence opens explanation/calibration. Vault status opens vault settings. Needs review opens review queue.

## Status language

Use truthful operational language.

Preferred terms:

- Ready
- Partial
- Blocked
- Needs review
- Unsupported
- No extractable text
- Calibrating
- Waiting for approval
- Waiting for available node
- Paused — user active
- Failed safely

Avoid:

- “All good” when partial
- “Done” when review is still needed
- “AI decided”
- “Autonomous legal conclusion”
- vague happy language that hides risk

## Legal-facing role labels

Use legal/operations roles only.

Allowed role labels include:

- Intake Clerk
- Evidence Clerk
- Records Custodian
- Review Coordinator
- Privilege Screener
- Chronology Clerk
- Compliance Gate
- Systems Clerk
- Research Clerk, optional future role

Forbidden in UX:

- Cassandra
- Chief
- Guardian
- Hermes
- PI
- autonomous legal brain
- AI senior partner
- lawyer replacement language

## Obsidian relationship

Obsidian may be useful as an optional attorney-notes or review surface, but it should not be the primary sellable UX.

Reasons:

- too many ways to misfile/move/delete data
- plugin and sync risks
- too much operator freedom under discovery stress
- unclear boundaries for sensitive legal data
- not enough controlled workflow enforcement

OpenClaw Legal Console should be the controlled front door.

Possible safe Obsidian use later:

- export selected review notes
- read-only attorney notebook
- optional markdown viewer for advanced users
- never the canonical source of matter data by default

## Tauri / controlled desktop shell direction

A future desktop console may use Tauri or a similar controlled shell.

Reasonable early Tauri spike:

- choose Legal Vault root
- call existing legal CLI commands
- display JSON results
- show status cards
- enforce no writes outside selected vault
- no network by default
- no cloud/LLM matter-data access

Do not start by rewriting the legal engine in Rust.

Recommended architecture:

```text
Python legal engine + CLI/API
→ controlled desktop shell
→ firm-local vault
→ future node/connect/update surfaces
```

## Required behavior

- UX must expose local-only/vault/audit status.
- UX must make unsupported files actionable.
- UX must show ETA confidence and calibration when relevant.
- UX must enforce role and permission boundaries.
- UX must not expose internal OpenClaw names.
- UX must not imply final legal advice.
- UX must show when work is incomplete, blocked, partial, or needs review.
- UX must keep external export and non-local options gated.
- UX must preserve firm immutability: no surprise new options in working deployments.
- UX must make updates understandable and deliberate.

## Forbidden behavior

- Do not make Obsidian the primary workflow controller for the sellable product.
- Do not hide unsupported files or blockers.
- Do not show high-confidence status when evidence is weak.
- Do not use agent mythology names in the legal product surface.
- Do not allow new modules to appear in existing firm workflows by default.
- Do not expose non-local/cloud actions as casual one-click actions for matter content.
- Do not make worker-node/distributed-compute complexity visible to ordinary lawyers unless useful.
- Do not replace attorney judgment with system claims.

## Acceptance tests / proof points

A future implementation should prove this spec with checks such as:

- Status bar shows local-only, vault, audit, unsupported, and ETA confidence fields.
- Unsupported count opens Alternative Methods flow.
- Request Feature remains hidden until local attempts fail or are policy-blocked.
- UI strings contain no banned internal OpenClaw names.
- Assigned lawyer sees assigned matters and shared review requests.
- Unauthorized user/device does not see matter data.
- External export requires approval.
- Update screen separates security, stability, installed module, and optional module updates.
- Optional new module does not appear in existing workflow until installed.
- ETA explanation shows confidence/reason.
- Queue screen shows blocked tasks with reason.
- System labels draft/candidate outputs as needing attorney review.

## Failure behavior

If the UX cannot represent a state safely, it should block the action or show a clear unavailable state.

Examples:

- If vault is not configured, block source intake.
- If permission cannot be verified, block matter access.
- If Primary Node is unavailable, block sensitive actions unless offline policy allows them.
- If status is partial, do not show complete.
- If a support packet cannot be sanitized, block Request Feature export.
- If update lane is unknown, block update installation.

## Notes for first law-firm v1 deployment

- The first buyer should experience a controlled legal console, even if the first implementation is simple.
- The first UX should prioritize trust, clarity, local-only boundaries, and visible progress over fancy autonomy.
- A CLI/demo may exist underneath, but the product direction should clearly move toward a guided console.
- The console should make the system feel professional enough to sell without overpromising capabilities.
- Start with single-machine status and workflow clarity before distributed compute.

## Suggested implementation phases

1. CLI-backed status/demo shell.
2. Matter dashboard and vault status.
3. Source inventory and extract-all status.
4. Search/report/review packet workflow.
5. Unsupported Alternative Methods surface.
6. Queue/ETA display.
7. Connect menu skeleton.
8. Updates view.
9. Review handoff UX.
10. Distributed node controls.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/console_spec.py`
- `legal/status_bar.py`
- `legal/ui_labels.py`
- `legal/cli_api.py`
- `legal/connect_menu.py`
- `legal/task_queue.py`
- `legal/update_manager.py`
- `legal/unsupported.py`
- `legal/permissions.py`
- `legal/vault_policy.py`
- `tests/test_legal_console_status.py`
- `tests/test_no_internal_names_in_ui.py`
- `tests/test_console_permission_gates.py`
- `tests/test_alternative_methods_flow.py`

## Relationship to other contracts

This spec depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_ROLE_NAMING_CONTRACT`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST`
- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT`
- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT`
- `LEGAL_ADAPTIVE_ETA_CONTRACT`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`

If this spec is weak, the product may be technically powerful but stressful, confusing, or untrustworthy to a firm operator.
