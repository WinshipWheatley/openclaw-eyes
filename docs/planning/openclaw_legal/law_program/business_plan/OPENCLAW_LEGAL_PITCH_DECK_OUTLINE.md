

# OpenClaw Legal — Pitch Deck Outline

## Purpose

This document outlines a buyer-facing pitch deck for OpenClaw Legal.

The pitch should explain the discovery problem clearly, show why local-first matters, make the product visually understandable, and avoid overclaiming what Version 1 can do.

The deck should sell confidence, control, and operational clarity — not vague AI magic.

## Internal draft warning

This is internal buyer-facing preparation, not final external sales material. Do not send to buyers as-is. Create external-facing versions only after the go/no-go gate clears. Verify current implementation before making capability claims. Roadmap concepts such as Connect, adaptive ETA, model distribution, multi-node throughput, OCR, email/portal connectors, and local model review must be labeled as roadmap unless verified built.

## Deck thesis

```text
OpenClaw Legal gives law firms a private local command center for discovery: intake, source tracking, local processing, search, review packets, audit trails, clear status, and a controlled path for expansion.
```

## Slide 1 — Title

### Title

OpenClaw Legal

### Subtitle

Private local discovery infrastructure for law firms.

### Visual

Clean hero image/mockup of the console dashboard on a Mac Studio / MacBook setup.

### Speaker point

This is not a chatbot. It is a controlled local discovery operations system designed to help firms know what they received, what processed, what failed, what is searchable, and what is ready for review.

## Slide 2 — The discovery problem

### Title

Discovery is messy, high-volume, and high-stakes.

### Key bullets

- Files arrive from portals, email links, cloud folders, hard drives, opposing counsel, prosecutors, and court systems.
- Batches include PDFs, scans, videos, audio, emails, phone exports, and unexpected file types.
- Lawyers need fast answers, but the workflow often becomes manual, fragmented, and stressful.
- The firm needs to know what arrived, what processed, what failed, and what is ready for review.

### Visual

Messy intake diagram: portals, email, drives, PDFs, video, scans all flowing into a confusing folder pile.

### Speaker point

The problem is not just storage. It is knowing the operational state of discovery.

## Slide 3 — Why current approaches fall short

### Title

The usual options leave gaps.

### Columns

#### Manual folders/spreadsheets

- flexible but error-prone
- unclear processing status
- difficult audit trail
- hard to scale

#### Generic cloud storage

- stores files but does not process discovery
- weak legal workflow visibility
- privacy concerns remain

#### Large SaaS e-discovery

- powerful but often expensive
- cloud-dependent
- may be overbuilt for smaller firms
- per-GB costs can be unpredictable

#### Generic AI tools

- unclear data boundaries
- weak chain-of-custody model
- no matter vault or controlled review workflow

### Visual

Four-column comparison with red/yellow warning icons.

## Slide 4 — The OpenClaw Legal answer

### Title

A private local command center for discovery.

### Key bullets

- Discovery enters a controlled local matter vault.
- Files are registered with hashes and metadata.
- Supported files are processed locally.
- Unsupported files are surfaced clearly.
- Search and reports are source-grounded.
- Review packets and audit trails are generated from the matter record.
- Processing status and ETA are visible.

### Visual

Clean pipeline:

```text
Discovery Intake → Legal Vault → Local Processing → Search / Review → Review Packet
```

### Speaker point

OpenClaw Legal is designed to make discovery inspectable and manageable inside the firm’s own local system.

## Slide 5 — Local-first trust model

### Title

Sensitive matter data stays under firm control.

### Key bullets

- Matter data lives in a local Legal Vault.
- Product code stays separate from firm data.
- Non-local AI does not receive matter content by default.
- Support packets are sanitized.
- Updates do not include matter data.
- The system is designed to fail closed on privacy boundary problems.

### Visual

Three-layer diagram:

```text
OpenClaw Legal Core
Firm Profile
Private Matter Vault
```

Show the Matter Vault locked inside the firm environment.

## Slide 6 — What Version 1 does

### Title

Version 1: the controlled local foundation.

### Key bullets

- Matter workspace and Legal Vault boundary
- Source registration and hashing
- Local text extraction for supported files
- Search across extracted text
- Review report and packet generation
- Audit trail
- Unsupported-file visibility
- Clear status and processing workflow
- Controlled update/profile architecture

### Visual

Product capability checklist with “Built / v1 target / roadmap” styling.

### Speaker point

Version 1 is intentionally focused. It does the foundation well before adding more automation.

## Slide 7 — What Version 1 does not claim

### Title

Clear boundaries build trust.

### Key bullets

OpenClaw Legal v1 is not claiming to be:

- a replacement for attorney judgment
- full legal advice automation
- instant support for every file type
- a guaranteed privilege decision engine
- a complete enterprise e-discovery replacement
- a cloud AI analysis platform
- a system that never requires human review

### Visual

“Honest boundaries” panel with checkmark: controlled, local, expandable.

### Speaker point

The system is more trustworthy because it is explicit about what it can and cannot do.

## Slide 8 — Matter dashboard mockup

### Title

One clear view of a matter.

### Mockup elements

- Matter name
- Local-only: ON
- Legal Vault: Connected
- Sources count
- Extracted count
- Unsupported count
- Needs review count
- ETA and confidence
- Recent activity
- Review packet status

### Example status bar

```text
Local-only: ON | Vault: Connected | Sources: 438 | Extracted: 311 | Unsupported: 20 | ETA: 4h 30m, Medium confidence
```

### Visual

Full-screen UI mockup of matter dashboard.

## Slide 9 — Source inventory mockup

### Title

Know what arrived and what happened to it.

### Key bullets

- Every source gets tracked.
- Hashes support auditability.
- Extraction status is visible.
- Unsupported and failed files are not hidden.
- Source-grounded search starts from this inventory.

### Visual

Table mockup:

```text
Filename | Type | SHA-256 | Status | Source ID | Action
bodycam_01.mp4 | video | ... | Unsupported | src_104 | Alternative Methods
statement.pdf | PDF | ... | Extracted | src_105 | View Text
```

## Slide 10 — Unsupported files / Alternative Methods

### Title

Unsupported files become a workflow, not a mystery.

### Key bullets

- Unsupported files are counted and visible.
- The system tries local classification and installed handlers first.
- If policy allows, it can attempt local repair/build in a sandbox.
- Request Feature appears only after local attempts fail or are policy-blocked.
- Feature requests are sanitized and do not include the legal file.

### Visual

Menu mockup:

```text
Unsupported files: 2 [Alternative Methods]

- Try local capability
- View technical details
- View failed attempts
- View non-local options and risks
- Request feature, available after local failure
```

## Slide 11 — Processing queue and ETA

### Title

The firm can see what is running and when it will finish.

### Key bullets

- Processing work is queued and visible.
- Tasks show status, blockers, and ETA.
- ETA is conservative and confidence-labeled.
- The system can show how available nodes may reduce processing time.
- New models/nodes calibrate before high-confidence ETA claims.

### Visual

Queue mockup:

```text
Jones Discovery — Processing — ETA 4h 30m — Confidence: Medium
Smith Packet — Queued — Starts in about 2h
Martinez PDFs — Blocked — Approval needed
```

### Speaker point

ETA is not a fake progress bar. It is a measured forecast that improves as the system learns local performance.

## Slide 12 — Connect menu / firm computers (roadmap/future)

### Title

Roadmap: use firm-owned hardware to increase throughput.

### Key bullets

- Main Primary Node owns vault, policy, audit, updates, and orchestration.
- Approved lawyer workstations can join the firm system.
- Computers do not join silently.
- Lawyer use always preempts background compute.
- Workstations can help process work when idle.

### Visual

Network diagram:

```text
Primary Node / Mac Studio
  ↳ Attorney A MacBook
  ↳ Attorney B MacBook
  ↳ Paralegal iMac
  ↳ Conference Room Mac
```

Show statuses:

```text
Available | User active | Processing | Offline
```

## Slide 13 — Review handoff

### Title

Lawyers can send bounded review requests.

### Key bullets

- Send a packet, search result, timeline segment, or note for review.
- Recipient sees it in Shared With Me / Review Requests.
- Access is scoped to what was shared.
- Handoffs are auditable.
- Collaboration does not require broad matter access expansion.

### Visual

Simple flow:

```text
Attorney A → Send for Review → Attorney B → Comment / Return / Approve
```

## Slide 14 — Updates that do not break working firms

### Title

Updates are deliberate, visible, and lane-based.

### Key bullets

- Security Updates
- Stability Updates
- Installed Module Updates
- Optional New Modules

Each update shows:

- what changes
- what does not change
- risk level
- tests passed
- rollback availability
- whether matter data is touched

### Visual

Update Manager mockup with lanes.

### Speaker point

Firm #2’s feature should not suddenly change Firm #1’s working deployment.

## Slide 15 — Modular roadmap

### Title

A focused foundation that can grow module by module.

### Columns

#### Version 1 foundation

- matter vault
- source tracking
- text extraction
- search
- reports/packets
- audit/status

#### Next modules

- OCR
- email evidence
- timeline
- privilege screening
- discovery connectors
- multi-node processing
- local model review

### Visual

Roadmap ladder or module tiles.

## Slide 16 — Business value

### Title

Control, clarity, and predictable cost.

### Key bullets

OpenClaw Legal helps firms:

- reduce discovery chaos
- keep sensitive data local by default
- see what worked and what failed
- search faster
- package review materials faster
- avoid unpredictable cloud/per-GB dependency where possible
- use existing firm hardware more effectively
- expand capabilities deliberately

### Visual

Before/after comparison:

```text
Before: scattered files, unclear status, manual packets, cloud uncertainty
After: local vault, visible queue, source-grounded search, review packets, audit trail
```

## Slide 17 — First deployment / pilot plan

### Title

Start with a real workflow, not a giant platform migration.

### Key bullets

Pilot goals:

- configure local Legal Vault
- process a representative discovery batch
- show source inventory and extraction status
- generate search/report/packet outputs
- identify unsupported file needs
- validate UX and privacy boundaries
- define next modules based on real use

### Visual

Pilot timeline:

```text
Setup → Demo Matter → Real Batch → Review Feedback → v1 Refinement → Module Roadmap
```

## Slide 18 — Closing

### Title

Private discovery infrastructure your firm can trust.

### Key message

OpenClaw Legal is built around a simple promise:

```text
Your discovery stays organized, local, searchable, auditable, and easier to move through — with clear status instead of guesswork.
```

### Call to action

Start with a focused pilot on one discovery-heavy matter.

## Appendix slide ideas

### Technical architecture appendix

Show:

```text
OpenClaw Legal Core
Firm Profile
Matter Vault
Module Registry
Update Manager
Primary Node
Worker Nodes
```

### Privacy appendix

Show what never leaves by default:

- source files
- extracted text
- attorney notes
- audit logs
- review packets
- matter names/client names

### Support packet appendix

Show sanitized feature request packet flow:

```text
Unsupported file detected
→ local attempts fail
→ sanitized diagnostics
→ public analog fixtures
→ feature built/tested
→ update returned
```

### Pricing appendix

Possible pricing structures:

- hardware + setup
- software license + deployment
- support subscription
- optional modules

## Deck tone

Use plain language.

Avoid hype.

Avoid “AI lawyer.”

Emphasize:

- private
- local
- controlled
- source-grounded
- auditable
- expandable
- predictable
- honest about limitations

## Visual style notes

Recommended visual direction:

- calm legal-tech aesthetic
- dark navy / charcoal / white / muted blue accents
- clean dashboard mockups
- status chips and confidence badges
- simple architecture diagrams
- no sci-fi robot imagery
- no cartoon lawyer imagery
- no mystical agent branding

## Must-have mockups before pitching

Minimum mockups needed:

1. Matter Dashboard
2. Source Inventory
3. Processing Queue + ETA
4. Unsupported Files / Alternative Methods
5. Review Packet Export
6. Connect Menu / Firm Computers (roadmap/future)
7. Update Manager
8. Local-only Confidence Bar

## Pitch discipline

The pitch should make the buyer think:

```text
This solves a real workflow problem.
My data stays under control.
The system tells the truth about what it can and cannot do.
I can start with a focused deployment and expand later.
```
