

# OpenClaw Legal — Buyer Problem Statement

## Purpose

This document defines the buyer-facing problem OpenClaw Legal is meant to solve.

It is written for small and mid-sized law firms that handle discovery-heavy matters and need a private, controlled, local-first way to receive, organize, process, search, and package discovery without losing confidence, leaking data, or getting trapped in unpredictable per-GB SaaS costs.

This is not a technical architecture document. It explains the pain clearly enough to support a pitch deck, visual mockups, pricing, and a first-firm sales conversation.

## Internal draft warning

This is internal buyer-facing preparation, not final external sales material. Do not send to buyers as-is. Create external-facing versions only after the go/no-go gate clears. Verify current implementation before making capability claims. Roadmap concepts such as Connect, adaptive ETA, model distribution, multi-node throughput, OCR, email/portal connectors, and local model review must be labeled as roadmap unless verified built.

## One-sentence problem

Law firms receive discovery in messy, high-volume, high-stakes batches, but the tools they use to process it are often fragmented, expensive, cloud-dependent, hard to audit, and stressful for lawyers who need fast, trustworthy answers.

## Short buyer-facing version

Discovery arrives from many places: portals, emails, shared folders, opposing counsel, prosecutor systems, court systems, hard drives, PDFs, videos, phone exports, scanned documents, and file types nobody expected.

Once it arrives, the firm has to answer basic questions quickly:

- What did we receive?
- Is everything accounted for?
- What can be searched?
- What failed to process?
- How long will review take?
- Who is working on it?
- What needs attorney review?
- Can we produce a clean packet or report?
- Can we do this without sending sensitive data into another cloud system?

Most firms do not have a calm, private, local command center for that work.

OpenClaw Legal is meant to become that command center.

## The buyer’s real pain

The firm is not just buying “AI.”

The firm is trying to reduce operational stress around discovery.

The real pain includes:

- discovery comes in too many formats
- files are scattered across portals, emails, downloads, drives, and staff computers
- lawyers do not always know what has been processed yet
- unsupported files become mystery problems
- large batches take unpredictable amounts of time
- cloud discovery tools can become expensive or overbuilt
- sensitive client data may leave the firm’s control
- staff may duplicate work because the status is unclear
- review packets and reports are often assembled manually
- attorneys need confidence that search/results are grounded in actual files
- firms need an audit trail without turning every action into technical busywork
- adding more computers or better models should clearly improve throughput, but firms need to see that value

## The current workflow problem

A common discovery workflow looks like this:

1. Discovery arrives through a portal, email link, shared folder, drive, or physical media.
2. Someone downloads it to a computer.
3. Someone tries to organize it manually.
4. PDFs, videos, emails, scans, and odd file types get mixed together.
5. Some files process, some fail, and some are ignored because nobody knows what to do with them.
6. Lawyers ask whether something is searchable yet.
7. Staff may re-download, re-process, or re-check the same material.
8. Reports or review packets are built manually.
9. If a cloud/SaaS tool is used, the firm may pay by data volume and send sensitive material outside its local control.
10. The firm still may not have a clear answer to: “What do we have, what worked, what failed, and what is ready for review?”

This is the gap OpenClaw Legal should fill.

## Why existing approaches are not enough

### Manual file handling

Manual handling is flexible, but it is error-prone and stressful.

Problems:

- hard to track what was received
- hard to know what was processed
- hard to prove what happened
- hard to scale with large discovery batches
- easy to misplace or duplicate files
- no reliable ETA for completion

### Generic cloud storage

Cloud storage helps move files, but it does not solve discovery processing.

Problems:

- storage is not review workflow
- little insight into extraction/search readiness
- unsupported files still require manual handling
- local privacy and data-sovereignty concerns remain
- audit trails are not tailored to legal review

### Full SaaS e-discovery platforms

Large e-discovery platforms can be powerful, but they are not always the right fit for every small or mid-sized firm.

Problems:

- unpredictable or high per-GB costs
- cloud dependency
- overbuilt workflows for smaller matters
- data leaves the firm’s direct local control
- staff may still need training and support
- firm may pay for a large platform when it needs a focused local workflow

### Generic AI tools

Generic AI tools can summarize text, but they are not enough for legal discovery operations.

Problems:

- unclear data boundaries
- risk of sending sensitive matter content outside the firm
- weak chain of custody / audit model
- no matter vault
- no controlled unsupported-file workflow
- no firm-specific permission model
- no source-grounded review packet by default
- no local processing queue or ETA

## The OpenClaw Legal answer

OpenClaw Legal should be positioned as:

```text
A private, local-first discovery operations system for law firms.
```

It should help the firm:

- pull or import discovery into a controlled local matter vault
- register sources with hashes and metadata
- process supported files locally
- identify unsupported files clearly
- search extracted text with source references
- generate review packets and reports
- show queue status and estimated completion
- use firm computers as approved processing nodes over time
- keep sensitive matter data local by default
- update modules deliberately without breaking working deployments
- build confidence through visible status, audit trails, and bounded workflows

## What the first version should promise

The first sellable version should promise a controlled local foundation, not a magical full e-discovery replacement.

A careful v1 promise:

```text
OpenClaw Legal gives your firm a private local command center for discovery intake, source tracking, local text extraction, search, review packets, audit trails, and clear processing status — with a roadmap for controlled expansion into more file types, worker nodes, and local AI review modules.
```

## What the first version should not overpromise

Do not pitch v1 as:

- a replacement for attorney judgment
- full legal advice automation
- instant support for every file type
- a complete Relativity replacement
- a guaranteed privilege review engine
- a fully autonomous legal agent system
- a cloud AI analysis platform
- a system that never requires human review

The stronger pitch is that OpenClaw Legal is controlled, local, expandable infrastructure.

## Buyer persona

Primary buyer:

- managing partner
- solo/small-firm owner
- discovery-heavy criminal defense or civil litigation attorney
- operations-minded attorney
- firm administrator who handles discovery workflows

Secondary users:

- associate attorneys
- paralegals
- legal assistants
- outside reviewers
- IT/support person, if the firm has one

## Buyer’s emotional state

The buyer is likely not relaxed about discovery.

They may feel:

- behind
- overloaded
- unsure what has been processed
- worried about missing something
- annoyed by portals and file dumps
- frustrated by expensive tools
- cautious about cloud AI
- skeptical of vague AI promises
- interested in speed if privacy is preserved

OpenClaw Legal should meet that buyer with clarity, not hype.

## High-value buyer questions

The pitch should answer these questions quickly:

- Where does my data live?
- Does my client data leave the firm?
- What file types can you handle now?
- What happens to unsupported files?
- Can I see what worked and what failed?
- Can I search across the discovery?
- Can I produce a packet/report for review?
- How long will processing take?
- Can more computers speed it up?
- What happens after updates?
- Will another firm’s custom feature break my system?
- What happens if I need a file type you do not support yet?

## The trust problem

The buyer does not just need output.

They need to trust the output.

Trust comes from:

- local-first data residency
- visible source inventory
- file hashes
- audit logs
- clear supported/unsupported status
- source-grounded search snippets
- conservative ETA with confidence labels
- review packets that show what is included
- update lanes that do not surprise the firm
- role/permission boundaries
- no hidden cloud processing of matter content

The UX should make trust inspectable.

## The business opportunity

The opportunity is to give smaller and mid-sized firms something they usually do not have:

```text
A private discovery operations appliance/workstation that feels like firm-owned infrastructure rather than another cloud subscription meter.
```

The strongest value themes:

- predictable cost
- local privacy
- faster discovery processing
- clearer review status
- lower operational stress
- auditability
- expandable modules
- better use of firm-owned hardware
- confidence that updates will not break a working deployment

## Differentiation

OpenClaw Legal should differentiate on:

- local-first matter vault
- no matter-data cloud dependency by default
- controlled legal UX
- source-grounded outputs
- audit-first workflow
- explicit unsupported-file pathway
- update lanes and per-firm stability
- multi-node firm compute roadmap
- adaptive ETA and time-savings visibility
- reusable product architecture without firm data carryover

## Example pitch language

```text
OpenClaw Legal is a private local discovery command center for law firms. It helps your firm bring discovery into a controlled matter vault, process supported files locally, see what worked and what failed, search extracted text, generate review packets, and track processing time — without making sensitive matter data dependent on a cloud AI system.
```

```text
Instead of paying unpredictable per-GB discovery costs or juggling files manually, your firm gets a local system that shows the status of the work, preserves audit trails, and can grow module by module as your needs expand.
```

```text
The system is designed to be honest. If a file cannot be processed, it says so. If an estimate is uncertain, it shows the confidence level. If an update adds a new capability, it does not silently change your working setup.
```

## Core buyer promise

OpenClaw Legal should promise:

```text
Your discovery stays organized, local, searchable, auditable, and easier to move through — with clear status instead of guesswork.
```

## What visual mockups must show

Future pitch visuals should show:

- matter dashboard with local-only/vault/audit status
- source inventory with hashes and extraction status
- unsupported files with Alternative Methods menu
- processing queue with ETA and confidence
- review packet export screen
- Connect menu showing firm computers/nodes
- update screen with security/stability/module lanes
- status bar showing local-only, unsupported count, ETA confidence, and review readiness

## Success criteria for the pitch

After hearing the pitch, a buyer should understand:

- the exact problem being solved
- why local-first matters
- why this is not generic AI chat
- what v1 can do
- what v1 does not claim to do yet
- how unsupported files are handled
- why updates are safe and deliberate
- how more firm hardware can improve throughput
- why the system should reduce discovery stress

## Short final framing

OpenClaw Legal is not mainly “AI for lawyers.”

It is better framed as:

```text
Private local discovery infrastructure for law firms that need control, speed, auditability, and predictable cost.
```
