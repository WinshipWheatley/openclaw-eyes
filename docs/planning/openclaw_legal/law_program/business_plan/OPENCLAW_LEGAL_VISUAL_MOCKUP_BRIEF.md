

# OpenClaw Legal — Visual Mockup Brief

## Purpose

This document defines the visual mockups needed to pitch OpenClaw Legal clearly.

The goal is to show a law firm what the product will feel like before the full console exists. The mockups should make the value obvious: private local discovery control, clear processing status, source-grounded review, unsupported-file handling, safe updates, and future multi-computer throughput.

These visuals are for sales, planning, and product alignment. They should not imply features are fully implemented unless specifically marked as current v1 capability.

## Internal draft warning

This is internal buyer-facing preparation, not final external sales material. Do not send to buyers as-is. Create external-facing versions only after the go/no-go gate clears. Verify current implementation before making capability claims. Roadmap concepts such as Connect, adaptive ETA, model distribution, multi-node throughput, OCR, email/portal connectors, and local model review must be labeled as roadmap unless verified built.

## Visual thesis

OpenClaw Legal should look like a calm, controlled legal operations console.

The visual language should communicate:

- private
- local
- organized
- source-grounded
- auditable
- operationally clear
- expandable
- not gimmicky
- not chatbot-first
- not mystical AI branding

The buyer should immediately understand:

```text
This system helps my firm know what discovery came in, what processed, what failed, what is searchable, what needs review, and when work will be ready.
```

## Overall style direction

### Mood

- calm
- professional
- precise
- trustworthy
- modern legal-tech
- quietly powerful

### Avoid

- robot imagery
- sci-fi agent swarm visuals
- cartoon lawyers
- glowing “AI brain” clichés
- mystical branding
- cluttered enterprise dashboard overload
- vague happy green checkmarks when status is partial

### Suggested palette

- deep navy
- charcoal
- off-white
- muted blue
- muted green for verified/high-confidence states
- amber for needs-review/calibrating states
- red only for true block/failure/risk states

### Typography and layout

- clean dashboard typography
- generous spacing
- status chips
- clear tables
- left navigation
- persistent status bar
- readable at pitch-deck screenshot size

## Required visual mockups

## 1. Matter Dashboard

### Purpose

Show the buyer the main “home base” for a matter.

### What it should communicate

- matter is local and controlled
- status is visible
- processing progress is clear
- unsupported files are not hidden
- review readiness is obvious
- ETA has confidence, not fake certainty

### Screen elements

- Matter name
- Matter ID or internal reference
- Local-only status
- Legal Vault status
- Audit status
- Sources count
- Extracted count
- Unsupported count
- Needs review count
- ETA and confidence
- Recent activity
- Next recommended action
- Review packet status

### Example text

```text
Matter: State v. Example Client
Local-only: ON
Legal Vault: Connected
Matter audit: ON
Sources: 438
Extracted: 311
Unsupported: 20
Needs review: 7
Estimated completion: about 4h 30m
Confidence: Medium — new node still calibrating
```

### Visual note

This should be the strongest hero mockup. It should look like a real product dashboard, not a concept diagram.

## 2. Source Inventory

### Purpose

Show that the system tracks what came in and what happened to each file.

### What it should communicate

- every source is registered
- hashes support auditability
- extraction status is visible
- unsupported files are actionable
- source IDs connect search results to evidence

### Screen elements

Table columns:

- filename
- file type
- source ID
- SHA-256 or shortened hash
- status
- extracted text available yes/no
- action

### Example rows

```text
statement.pdf       PDF      src_105   a83f...91d   Extracted        View Text
bodycam_01.mp4      Video    src_104   c19a...a22   Unsupported      Alternative Methods
scan_batch_07.pdf   PDF      src_106   83fa...0c8   No Text Layer    Needs OCR Module
email_export.mbox   Email    src_107   ff82...ac3   Unsupported      Alternative Methods
```

### Visual note

Use status chips instead of only text. The buyer should see immediately that the system does not hide failures.

## 3. Processing Queue + ETA

### Purpose

Show the firm how work moves through the system and when it will finish.

### What it should communicate

- multiple lawyers/batches can submit work
- queue is visible
- blockers are clear
- ETA is confidence-labeled
- adding nodes can reduce processing time

### Screen elements

- Current Work
- Queued Work
- Blocked Work
- Available nodes
- ETA confidence
- capacity recommendation

### Example queue

```text
Jones Discovery Batch       Processing   ETA 4h 30m   Confidence: Medium
Smith Review Packet         Queued       Starts ~2h   Confidence: Medium
Martinez PDF Extraction     Blocked      Approval needed
Davis Unsupported Files     Needs Review 2 files need Alternative Methods
```

### Roadmap capacity panel example

```text
Primary Node only: about 14h
With 3 available firm computers: about 4h 30m
Potential time saved: about 9h 30m
Confidence: Medium — Attorney B MacBook still calibrating
```

### Visual note

This mockup should make the business case for additional nodes without sounding like sales pressure.

## 4. Unsupported Files / Alternative Methods

### Purpose

Show that unsupported files are handled through a controlled local-first workflow.

### What it should communicate

- unsupported files are visible
- local attempts happen before escalation
- Request Feature is gated
- non-local options are treated as risky/optional
- feature requests do not include sensitive files

### Screen elements

- unsupported file list
- technical details
- local attempts timeline
- Alternative Methods menu
- gated Request Feature button
- sanitized packet status
- public analog candidates area

### Example state before local attempts

```text
Unsupported file: bodycam_01.xyz
Status: Local classification pending
Available actions:
- Try local capability
- View technical details
- Ignore for now
```

### Example state after local failure

```text
Local attempts failed:
1. MIME classification complete
2. Installed handlers checked
3. Local build attempt failed safely

Request Feature is now available.
No legal file or matter content will be included.
```

### Visual note

This screen is a trust-builder. It should look careful and procedural, not alarming.

## 5. Review Packet Export

### Purpose

Show how the system turns processed discovery into a clean review package.

### What it should communicate

- packet contents are visible before export
- audit/manifest are included
- extracted artifacts and reports are organized
- external export is controlled
- packet is source-grounded

### Screen elements

- packet name
- included files
- excluded files
- reports included yes/no
- manifest included
- audit included
- external export warning
- generate/export button

### Example text

```text
Review Packet: First Discovery Review
Includes:
- manifest.json
- audit.jsonl
- extracted text artifacts
- settlement-search-report.md
- packet_manifest.json

External export: Approval required
```

### Visual note

This should look like a firm-ready work product assembly screen.

## 6. Connect Menu / Firm Computers (roadmap/future)

### Purpose

Show the future private firm network: Primary Node plus approved lawyer workstations.

### What it should communicate

- computers do not join silently
- Primary Node remains authoritative
- lawyer laptops can contribute when idle
- human use preempts compute
- more nodes can reduce processing time

### Screen elements

- This Computer
- Firm Computers
- Pending Join Requests
- Compute Sharing
- Node Health
- Current task
- Last seen
- Model status

### Example node list

```text
Primary Node / Mac Studio       Online      Processing large batch     Model: Evidence v1.2
Attorney A MacBook Pro          Available   Balanced compute           Model staged
Attorney B MacBook Pro          Paused      User active                Current model v1.1
Paralegal iMac                  Processing  PDF extraction batch       ETA contribution: 1h saved
Conference Room Mac             Offline     Last seen yesterday
```

### Visual note

This should feel like a firm-owned private network, not a hacker cluster.

## 7. Update Manager

### Purpose

Show that updates are safe, deliberate, and lane-based.

### What it should communicate

- updates will not silently change firm workflow
- security/stability/module/new-module lanes are separate
- firm can see what changes
- rollback/test status is visible

### Screen elements

Sections:

- Security Updates
- Stability Updates
- Installed Module Updates
- Optional New Modules

Each update card should show:

- title/version
- lane
- affected module
- risk level
- workflow changes yes/no
- matter data touched yes/no
- tests passed
- rollback available
- install/defer action

### Example card

```text
PDF Extractor v1.2
Lane: Installed Module Update
Workflow changes: No
Matter data touched: No
Tests passed: 42
Rollback: Available
Recommended: Install
```

### Visual note

This mockup should reinforce confidence that updates improve the system without breaking it.

## 8. Local-only Confidence / Status Bar

### Purpose

Show the persistent truth surface that keeps the operator oriented.

### What it should communicate

- local-only state
- vault state
- audit state
- source/extraction/unsupported counts
- ETA confidence
- review readiness

### Example bar

```text
Local-only: ON | Cloud tools: OFF | Vault: Connected | Audit: ON | Sources: 438 | Extracted: 311 | Unsupported: 20 | ETA: Medium | Packet: Not Ready
```

### Behavior

- `Unsupported` opens Alternative Methods.
- `ETA` opens confidence explanation/calibration.
- `Vault` opens vault settings/status.
- `Packet` opens review packet workflow.
- `Audit` opens recent audit events.

### Visual note

This bar should appear across multiple mockups for continuity.

## 9. Legal Vault / Product Core Separation Diagram

### Purpose

Explain the privacy architecture simply.

### Visual structure

```text
OpenClaw Legal Core
Reusable product code, modules, tests, updates

Firm Profile
Firm settings, enabled modules, policies, devices

Private Matter Vault
Sources, extracted text, reports, packets, audit, notes
```

### Key labels

- product code does not contain matter data
- updates do not include matter vault data
- support packets are sanitized
- matter vault stays local by default

### Visual note

This should be a clean architecture diagram for privacy-conscious buyers.

## 10. Primary Node + Lawyer Workstations Diagram (roadmap/future)

### Purpose

Explain the future multi-computer architecture.

### Visual structure

```text
Primary Node / Mac Studio
- vault
- policy
- audit
- queue
- updates
- model distribution

Attorney Workstations
- assigned matters
- review requests
- optional idle compute

Worker/Staff Nodes
- bounded processing tasks
- no independent authority
```

### Key labels

- no silent joining
- approved devices only
- human use preempts compute
- worker tasks are leased
- Primary Node validates outputs

## Mockup fidelity guidance

### First pass

Static pitch-deck mockups are enough.

They should look credible but do not need to be clickable.

### Second pass

Clickable prototype or Tauri-style shell mockup.

### Third pass

Actual console backed by CLI/API.

## Suggested mockup tools

Good options:

- Figma
- Canva for quick pitch visuals
- Keynote / PowerPoint mockups
- Tauri later for real shell
- HTML/CSS static prototype if faster

Do not let visual polish outrun architecture truth.

## Copy tone for mockups

Use direct, operational copy.

Good examples:

- `Blocked: 2 unsupported files need Alternative Methods review`
- `ETA confidence: Medium — new node still calibrating`
- `External export requires approval`
- `Local-only: ON`
- `Request Feature available after local handling failed`

Avoid:

- `AI has solved your case`
- `Everything is perfect`
- `Autonomous partner review complete`
- `Guaranteed privilege found`

## Required consistency with contracts

Mockups must preserve:

- no internal OpenClaw names in legal UX
- no surprise-update implication
- no matter-data cloud upload by default
- clear unsupported-file workflow
- confidence-labeled ETA
- Primary Node authority
- attorney/device/matter permission boundaries
- human-priority compute
- attorney review requirement

## Visual mockup checklist

Before pitching, make sure the mockup set includes:

- [ ] Matter Dashboard
- [ ] Source Inventory
- [ ] Processing Queue + ETA
- [ ] Unsupported Files / Alternative Methods
- [ ] Review Packet Export
- [ ] Connect Menu / Firm Computers (roadmap/future)
- [ ] Update Manager
- [ ] Local-only Confidence Bar
- [ ] Legal Vault / Core separation diagram
- [ ] Primary Node / Workstations diagram

## Bottom line

The mockups should make OpenClaw Legal feel like a real private discovery command center.

They should show enough product clarity that a buyer can say:

```text
I understand the problem this solves.
I can see how I would use it.
I can see where my data lives.
I can see what happens when something fails.
I can see why this gets better as the firm adds modules or nodes.
```
