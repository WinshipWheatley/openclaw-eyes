# OpenClaw Legal — Business Plan

## Purpose

This document turns the buyer problem statement into a practical business plan for OpenClaw Legal.

It is meant to support a first-firm sales conversation, pitch deck, mockups, pricing discussion, and eventual implementation roadmap. It should stay buyer-facing and commercially grounded, while respecting the technical contracts already defined in the OpenClaw Legal v1 planning package.

## Internal draft warning

This is internal buyer-facing preparation, not final external sales material. Do not send to buyers as-is. Create external-facing versions only after the go/no-go gate clears. Verify current implementation before making capability claims. Roadmap concepts such as Connect, adaptive ETA, model distribution, multi-node throughput, OCR, email/portal connectors, and local model review must be labeled as roadmap unless verified built.

## Business thesis

Small and mid-sized law firms need a private, local-first discovery operations system that gives them control, speed, auditability, and predictable cost without forcing sensitive matter data into a cloud AI or per-GB SaaS workflow.

OpenClaw Legal should become a firm-owned discovery command center:

```text
Private local matter vault
+ source registration and hashing
+ local processing
+ search and review packets
+ visible queue and ETA
+ controlled updates
+ optional modules
+ future multi-node firm compute
```

## Product category

OpenClaw Legal should be positioned as:

```text
Private local discovery infrastructure for law firms.
```

Secondary phrasing:

- local-first discovery operations system
- private discovery command center
- firm-owned evidence processing appliance
- controlled local alternative to cloud-first discovery workflows
- modular legal operations console

Avoid leading with:

- AI lawyer
- autonomous legal brain
- chatbot for discovery
- Relativity replacement
- generic legal AI

## Target customer

### Primary customer

The first target customer is a small or mid-sized law firm handling discovery-heavy matters.

Likely practice areas:

- criminal defense
- civil litigation
- employment litigation
- family law with document-heavy cases
- small firm white collar / investigations
- local government-adjacent or administrative matters where records are heavy

Best early buyer profile:

- already feels discovery pain
- cares about data privacy
- is skeptical of cloud AI
- wants predictable cost
- has enough matter volume to feel the problem
- does not want enterprise e-discovery overhead
- is open to a local workstation/appliance model

### Economic buyer

Likely economic buyer:

- managing partner
- firm owner
- senior attorney responsible for operations
- technically curious attorney
- firm administrator with decision influence

### Daily users

Likely daily users:

- attorneys
- paralegals
- legal assistants
- discovery staff
- outside reviewers, later

## Core problem solved

The firm needs to know:

- what discovery came in
- where it lives
- whether it was processed
- what failed
- what is searchable
- what needs review
- how long processing will take
- whether more compute will help
- whether the output is source-grounded
- whether sensitive data stayed local

Current workflows are often scattered across portals, downloads, email links, shared folders, staff computers, cloud storage, and manual review.

OpenClaw Legal should centralize that into a controlled, local matter vault and legal operations console.

## Value proposition

OpenClaw Legal gives a firm:

- private local control over discovery data
- clear source inventory and hashing
- local processing of supported files
- visible unsupported-file handling
- source-grounded search and reports
- review packet generation
- audit trails
- queue status and ETA
- controlled updates that do not break workflows
- a path to use firm-owned computers for additional throughput
- a modular roadmap for OCR, email evidence, timelines, privilege screening, and other capabilities

## Buyer-facing promise

```text
Your discovery stays organized, local, searchable, auditable, and easier to move through — with clear status instead of guesswork.
```

## Version 1 product promise

Version 1 should be positioned carefully.

A good v1 promise:

```text
OpenClaw Legal v1 gives your firm a private local foundation for discovery intake, source tracking, text extraction, search, review packets, audit trails, and clear processing status — with a controlled path for unsupported files, updates, and future expansion.
```

Do not promise:

- full legal advice automation
- guaranteed privilege decisions
- support for every file type
- full SaaS e-discovery replacement
- fully autonomous legal work
- cloud-scale processing without local constraints
- zero human review
## Strong Product Roadmap

The "Strong Product" vision for OpenClaw Legal is **Private local discovery intelligence for law firms.** The current foundation is the safe local spine that makes the strong product trustworthy. High-value discovery intelligence remains source-linked and attorney-reviewed.

### Phased capability ladder

- **Phase 1: Local Discovery Spine (Current Foundation)**: Vault, registration, hashing, text/PDF extraction, search, review packets, audit trails.
- **Phase 2: Local Staging Intake**: Streamlined local drop-folder staging and automated import.
- **Phase 3: OCR for Screenshots and Scanned PDFs**: Extraction of text messages, scanned documents, and image-based discovery.
- **Phase 4: Audio/Video Extraction**: Transcription and frame-based OCR for media evidence.
- **Phase 5: Timestamp/Text Metadata Model**: Automated extraction of visible time references and source-linked metadata.
- **Phase 6: Timeline Candidate Builder**: Automated drafting of chronological event lists across multi-source evidence.
- **Phase 7: Contradiction Candidate Detector**: Identifying potential factual inconsistencies between sources for attorney review.
- **Phase 8: Attorney-Gated QA / Rework Loop**: Integrated human-in-the-loop validation of automated findings.
- **Phase 9: Local LM-Assisted Synthesis**: Advanced local analysis and drafting under strict Lane B rules.

## Product components

### 1. Legal Vault

The firm’s private local matter-data space.

Stores:

- matters
- sources
- extracted text
- reports
- review packets
- audit logs
- notes, if enabled

Business value:

- data control
- inspectability
- chain-of-custody discipline
- confidence that matter data is not casually mixed with product code or cloud AI

### 2. Source Registration

Tracks incoming discovery with hashes and metadata.

Business value:

- know what arrived
- reduce duplication/confusion
- support auditability
- create confidence in source-grounded outputs

### 3. Local Processing

Processes supported files locally.

Initial supported scope should remain honest.

Business value:

- less manual handling
- faster path to search/review
- no default matter-data cloud upload

### 4. Search and Review Packets

Lets the firm search extracted text and generate review packets/reports.

Business value:

- source-grounded review
- easier attorney handoff
- less manual packet assembly

### 5. Processing Queue and ETA

Shows what is running, queued, blocked, and when work is expected to finish.

Business value:

- operational clarity
- less staff/lawyer uncertainty
- clearer reason to add compute nodes later

### 6. Unsupported File Alternative Methods

Shows unsupported files and provides local-first handling options.

Business value:

- unsupported files stop becoming invisible problems
- firm sees that the system tried safe local methods
- feature requests can be generated without exposing sensitive data

### 7. Update Manager

Separates security, stability, module, and optional new-capability updates.

Business value:

- updates feel controlled
- firms trust that new work will not break working deployments
- features can improve across firms without unsafe bleedover

### 8. Connect Menu / Future Multi-Node Processing

Lets the firm add approved computers later.

Business value:

- firm-owned hardware can reduce processing time
- lawyers’ computers can contribute when idle
- Primary Node remains authoritative
- future scalability without per-GB cloud dependency

## Differentiation

OpenClaw Legal differentiates from common alternatives by combining:

- local-first data residency
- source-grounded outputs
- matter vault discipline
- explicit unsupported-file workflow
- audit-first processing
- controlled update lanes
- per-firm immutability
- future private multi-node compute
- adaptive ETA and visible time savings
- legal-facing controlled UX rather than agent mythology

## Competitive landscape

### Manual workflow

Competes against doing nothing or using folders, email, spreadsheets, and ad hoc notes.

OpenClaw advantage:

- more structured
- more auditable
- easier to search
- clearer status
- less duplicated work

### Generic cloud storage

Competes against Drive, Dropbox, OneDrive, ShareFile, Box, etc.

OpenClaw advantage:

- storage plus processing workflow
- matter-specific audit/status
- source registration and review packet outputs
- local-first option

### SaaS e-discovery platforms

Competes indirectly with large platforms.

OpenClaw advantage for small/mid firms:

- predictable firm-owned infrastructure
- local data control
- less platform overhead
- modular growth
- potential fixed-cost appliance/service model

Do not oversell against enterprise platforms. Position as focused local discovery operations infrastructure for firms that need control and clarity.

### Generic AI tools

Competes against attorneys pasting files/text into chat tools.

OpenClaw advantage:

- controlled vault
- local-first data boundary
- audit trail
- source grounding
- permission model
- unsupported-file workflow
- no casual matter-data upload

## IP / Pilot / Ownership Doctrine
OpenClaw Legal operates under the IP / Pilot / Ownership Doctrine (see `OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` Principle 16). This doctrine establishes developer ownership of the reusable product core and matched reference bench, while the firm maintains ownership of its matter data, work product, and production hardware. Updates follow a Validated Update Pipeline: tested on the reference bench with synthetic data and packaged before being offered to firm production with explicit approval for workflow changes.

## Business model options

These should be refined later, but the likely models are:

### 1. Hardware + setup package

Sell or configure a Mac Studio-class Primary Node with OpenClaw Legal installed.

Pros:

- clear appliance-like value
- firm owns infrastructure
- easier to pitch privacy/control
- easier to standardize environment

Cons:

- upfront cost higher
- hardware procurement/support expectations

### 2. Software license + local deployment

Firm provides compatible hardware; OpenClaw Legal is installed/configured locally.

Pros:

- flexible
- lower barrier if firm already has Mac hardware

Cons:

- support variability
- more environment differences

### 3. Setup fee + maintenance/support subscription

Charge for initial deployment, then ongoing updates/support.

Pros:

- aligns with ongoing update/module support
- recurring revenue

Cons:

- must define support boundaries clearly

### 4. Module-based expansion

Base product plus paid optional modules.

Potential modules:

- OCR module
- email evidence module
- timeline module
- privilege screening module
- discovery connector module
- multi-node processing module
- advanced local model review module

Pros:

- lets firms buy what they need
- supports suite roadmap

Cons:

- requires strong module/version/update architecture

## Pricing principles

Pricing should reflect:

- privacy/control value
- avoided per-GB SaaS costs
- time saved in discovery handling
- reduced operational stress
- hardware utilization
- setup/configuration labor
- ongoing updates/support
- module value

Avoid pricing solely by usage if the pitch is predictable cost.

Potential positioning:

```text
Predictable local discovery infrastructure instead of unpredictable per-GB cloud processing.
```

## Sales wedge

Best first sales wedge:

```text
Let us give your firm a private local command center for discovery intake, processing status, search, and review packets.
```

Do not start by pitching every future module.

Start with:

- messy discovery intake
- what worked / what failed
- searchable text
- review packet
- local/private control
- visible ETA/status

## Buyer demo story

A strong demo story:

1. Create/open matter.
2. Add discovery sources.
3. Show source registration with hashes.
4. Run local extraction.
5. Show source inventory: extracted / no text / unsupported.
6. Search for a key term.
7. Generate a Markdown review report.
8. Generate a review packet.
9. Show audit trail.
10. Show unsupported file Alternative Methods.
11. Show processing queue with ETA.
12. Show future Connect menu concept for adding firm computers.
13. Show update lanes and no-surprise update promise.

The demo should be honest about what is built now and what is roadmap.

## Visual assets needed

The pitch package should include visuals/mockups for:

- Matter Dashboard
- Source Inventory
- Processing Queue + ETA
- Unsupported Files / Alternative Methods
- Review Packet Export
- Connect Menu / Firm Computers
- Update Manager
- Local-only Confidence Bar
- Legal Vault / Product Core separation diagram
- Primary Node + Lawyer Workstations diagram

## Go-to-market strategy

### Phase 1: First firm pilot / first v1 deployment

Goal:

- solve a real discovery workflow for one firm
- validate that the UX reduces stress
- validate local-first boundaries
- learn which modules matter most
- avoid custom-fork architecture

Success criteria:

- firm can use the system on real workflow
- firm trusts local data boundary
- firm understands outputs/status
- system creates review packets/search results useful enough to keep using
- no sensitive firm data enters reusable product code

### Phase 2: Product extraction

After Firm #1 works:

- extract reusable architecture
- remove firm-specific names/data
- package generic core
- identify which custom features become modules
- prepare Firm #2 deployment path

### Phase 3: Second firm deployment

Goal:

- prove product generalizes
- keep Firm #1 stable
- package Firm #2 needs as modules/profile config
- validate update lane architecture

### Phase 4: Suite expansion

Add modules based on repeated firm needs.

Potential suite modules:

- email evidence
- OCR/scanned documents
- chronology
- privilege screener
- bodycam/video evidence
- phone extraction support, if legally/safely scoped
- discovery connector modules
- local model review modules

## Risk and mitigation

### Risk: overpromising AI

Mitigation:

- pitch infrastructure and source-grounded workflows
- label drafts/candidates clearly
- keep attorney review central

### Risk: sensitive data leakage

Mitigation:

- Legal Vault outside repo
- local-only default
- support packet sanitization
- non-local LLM blocking for matter data

### Risk: first firm becomes custom fork

Mitigation:

- firm profile separation
- module architecture
- no hardcoded firm assumptions
- product core separation contract

### Risk: updates break working deployment

Mitigation:

- update lanes
- module version pinning
- no-surprise update contract
- rollback metadata

### Risk: unsupported files disappoint buyer

Mitigation:

- Alternative Methods menu
- visible unsupported status
- local build-first policy
- sanitized feature request path
- clear roadmap

### Risk: UX feels too technical

Mitigation:

- controlled legal console
- simple status language
- buyer-facing visuals
- avoid internal agent names
- hide distributed complexity unless useful

## What v1 should include

Minimum sellable v1 should aim for:

- controlled matter workspace
- explicit Legal Vault boundary
- source registration and hashing
- local extraction for supported files
- search over extracted text
- review report/packet export
- audit trail
- unsupported-file status
- basic CLI or console workflow
- buyer-facing status model
- update/profile architecture, at least as enforced contracts
- clear documentation of what is supported and not supported

## What v1 can roadmap but should not claim as finished unless built

- distributed worker nodes
- local model distribution
- adaptive ETA based on many samples
- OCR
- email evidence modules
- privilege screening
- timeline generation
- portal connectors
- full Tauri desktop app
- cloud/non-local optional workflows

## Key metrics to track

Product/use metrics:

- files registered
- files processed
- unsupported files
- failed files
- extraction success rate
- processing time by task type
- ETA accuracy over time
- review packets generated
- support packets generated
- time saved after new node/model/update

Business metrics:

- setup cost
- support hours per firm
- update frequency
- module adoption
- buyer-reported stress reduction
- renewal/support retention
- number of firms using same core architecture

## Strategic moat

The moat is not just code.

It is the combination of:

- local-first legal data boundary
- practical discovery workflow understanding
- firm-owned hardware strategy
- modular update architecture
- trust-preserving UX
- source-grounded outputs
- ability to grow from one firm without leaking data or forking code

## Open questions

- Which first practice area is the best wedge?
- Should the first deployment be hardware-included or software-only?
- What file types are mandatory for the first buyer?
- What is the minimum UX acceptable for a first sale?
- What update/support level can be promised safely?
- What pricing model best matches the first firm’s budget and perceived value?
- How much local model capability should be included in v1 vs roadmap?
- What public demo matter should be used for pitches?

## Bottom line

OpenClaw Legal should be sold as a private, local-first discovery operations system.

The first version should not try to be every e-discovery product at once. It should do the foundation well: intake, source tracking, local processing, search, packets, audit, visible status, and safe expansion.

If the first firm’s deployment is built with clean product boundaries, it can become the first real deployment of a reusable legal product rather than a one-off custom system.
