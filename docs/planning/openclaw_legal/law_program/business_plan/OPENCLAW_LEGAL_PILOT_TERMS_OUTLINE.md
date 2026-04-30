# OpenClaw Legal Pilot Terms Outline

## 1. Purpose

This is an internal terms checklist for a first paid OpenClaw Legal pilot.

It is not a signed offer, not legal advice, and not a final contract. It is a plain checklist for later attorney and business review before any paid pilot begins.

This outline should protect the pilot boundary: one narrow local workflow, written support limits, clear ownership, no emergency litigation support by default, no legal judgment, and no unbounded custom work.

## 2. Required agreement posture

No paid pilot should begin until written terms cover at least:

- scope
- payment
- support
- hardware
- data ownership
- backups and retention
- offboarding, export, and wipe responsibilities
- liability and risk allocation
- no-legal-advice language
- attorney-review requirement
- emergency-support exclusions or pricing
- unsupported-file policy
- privacy and local-data handling
- termination and pause rights

If these terms are not written, the work remains internal development or synthetic/public demo only.

## 3. Parties and ownership

The agreement should identify the firm, the OpenClaw/provider party, and any separate hardware or support provider.

Ownership terms should state:

- firm owns matter data, source files, attorney work product, outputs generated for its matters, reports, review packets, and production hardware unless a separate hardware agreement says otherwise.
- OpenClaw/provider owns reusable product core, generalized improvements, synthetic fixtures, templates, reusable modules, documentation patterns, and update tooling.
- The firm does not get ownership of the reusable product core unless a separate written agreement says so.
- OpenClaw/provider does not get ownership of the firm's private matter data or legal work product.
- No firm-specific private matter data enters reusable product core.
- Sanitized diagnostics or generalized lessons may be used only if they exclude matter content, client identities, private paths, privileged material, and sensitive filenames.

## 4. Scope of pilot

The first paid pilot should be limited to:

- one firm
- one scoped workflow
- one primary machine
- one local vault
- agreed file types only
- written setup tasks
- written support window
- written success criteria

The pilot is not a full firm rollout, full e-discovery replacement, managed litigation-support service, emergency support service, or approval to add new GUI controls.

## 5. Included services

Included services may cover only the written pilot scope:

- setup and configuration of the agreed local-first workflow
- basic onboarding and workflow training
- supported-file workflow for agreed file types
- source tracking and hashing where supported
- local extraction, search, report, and review-packet workflow where supported
- sanitized support packet workflow explanation
- Alternative Methods explanation for unsupported, failed, or no-text sources
- synthetic demo validation before buyer reliance
- bug fixes within the agreed supported scope
- documentation corrections for the agreed workflow
- bounded support inside the written support window

Everything included should be labeled as built, prototype-only, or roadmap-only before the firm relies on it.

## 6. Excluded services

The pilot should exclude by default:

- legal advice
- privilege calls
- legal conclusions
- attorney replacement
- emergency/court-deadline support
- raw matter review by the provider
- unlimited support
- broad custom development
- unsupported critical file rescue
- free custom file handlers
- Run/Reset GUI behavior
- Connect/queue/ETA/model distribution
- full e-discovery replacement
- email, cloud, portal, audio, video, or broad media workflows unless separately scoped
- guaranteed completeness, search coverage, privilege outcome, or legal outcome
- full firm IT support

Any exception must be written, narrow, paid if appropriate, and separately approved before work starts.

## 7. Support terms

The agreement should define:

- support window
- response expectations
- communication channels
- what counts as included support
- what is paid extra
- what is never included by default
- what information may be shared for support
- when support must pause for privacy or scope reasons

Included support may cover setup help, basic onboarding, supported-scope bug reports, documentation corrections, and review of sanitized diagnostics.

Paid-extra support may cover custom handlers, additional file types, extra training, extra configuration, additional node setup, custom reports, connectors, advanced modules, or periodic system review.

Never included by default: legal advice, legal strategy, privilege review, raw matter review, full manual discovery review, forensic testimony, general firm IT support, unlimited custom work, or taking responsibility for litigation deadlines.

There is no emergency/court-deadline support unless separately priced, accepted, and written. Even then, the terms must preserve no legal advice, no outcome guarantee, limited hours, limited scope, and no routine raw matter access.

## 8. Hardware/data/backups/offboarding

The agreement should state:

- The firm owns or funds production hardware unless separately contracted.
- Any provider-owned leased appliance needs separate terms for term length, damage, replacement, insurance, wipe, return, and support.
- The firm is responsible for backups, retention, restore testing, and hardware failure unless separately contracted.
- Backup setup or backup review is separate scope if offered.
- Offboarding, export, wipe, and decommissioning responsibilities must be written.
- The firm owns its data and generated matter outputs after termination.
- Provider-assisted wipe or export requires written authorization and a clear statement of what will be moved, exported, or deleted.
- The provider should not routinely access raw matter data.

If hardware ownership, backup responsibility, or offboarding is vague, do not start a paid pilot.

## 9. Privacy/data handling

The agreement should require:

- matter data stays local by default
- support uses sanitized diagnostics where possible
- no cloud/non-local processing of matter data without separate written approval
- no secrets, API keys, client files, privileged content, private matter facts, or private paths in prompts or public fixtures
- no raw matter data in the product repo
- no raw matter data in update packages
- support packets exclude source files, extracted text, attorney notes, sensitive names, private paths, reports, review packet contents, raw audit logs, and privileged material
- any raw matter access exception is written, narrow, time-limited, and approved before access

If a support issue appears to require raw matter access, the default response is to pause and seek a safer diagnostic path, public analog, or written exception.

## 10. Attorney review/no legal advice

Terms should state plainly:

- Outputs are review aids.
- OpenClaw Legal is not legal advice.
- Attorneys remain responsible for legal strategy, privilege decisions, legal judgment, completeness decisions, and final use of any output.
- The product and provider do not guarantee legal outcomes.
- The product and provider do not guarantee completeness, privilege determinations, or discovery sufficiency.
- Any summaries, reports, extracted text, search results, or review packets must be reviewed by the firm's attorneys before reliance.

No pilot should proceed if the firm expects the product or provider to make legal judgments.

## 11. File-type limitations

Conservative first-pilot file types should be written into the agreement:

- `.txt`
- `.md`
- text-layer `.pdf`
- `.png`, `.jpg`, and `.jpeg` only as a local Tesseract-backed prototype where Tesseract is installed and verified

Excluded unless separately quoted, tested, and approved:

- scanned-PDF OCR
- video
- audio
- email archives
- phone dumps
- proprietary exports
- broad media processing
- unsupported binary or container formats
- any file type requiring cloud tools by default

The firm must accept the unsupported-file policy before a paid pilot. Unsupported, failed, or no-text files should flow through Alternative Methods metadata and paid custom-scope decisions, not emergency support promises.

## 12. Payment/commercial terms to decide

Do not invent prices in this outline. Decide and write placeholders for:

- setup fee
- support/update plan
- paid add-ons
- custom handler rate
- extra training/configuration
- additional node setup
- custom report shaping
- hardware purchase, reimbursement, lease, or pass-through terms
- rush support if ever offered
- payment schedule
- renewal or end-of-pilot decision point

Pricing should prevent cheap open-ended support. A discount, if any, should be tied to feedback, limited scope, and a narrow first-pilot learning goal.

## 13. Termination/No-Go triggers

The pilot should be paused, declined, or terminated if the buyer:

- demands excluded services
- refuses the support boundary
- requires unsupported critical files immediately
- wants raw-matter remote review
- expects full e-discovery replacement
- needs emergency litigation support
- expects legal conclusions, privilege calls, or legal strategy
- refuses hardware, data, backup, retention, or offboarding responsibility
- wants open-ended custom work for a narrow setup fee
- treats roadmap modules as included deliverables
- requires Run/Reset GUI behavior, Connect, queue, ETA, or model distribution as a condition of pilot
- asks for cloud/non-local matter processing without written approval and privacy review

Do not build custom features to rescue a no-go deal. Rewrite the scope, reprice the work, or stop.

## 14. Attorney/business review needed

This outline must be reviewed by appropriate legal and business counsel before it is used as a real agreement, statement of work, order form, support policy, or buyer-facing contract attachment.

The review should cover contract enforceability, liability limits, professional-responsibility concerns, confidentiality, data handling, support promises, payment terms, hardware ownership, offboarding, and emergency-support language.

This outline is a protective drafting aid only. It does not replace legal review, business judgment, or final written agreement terms.
