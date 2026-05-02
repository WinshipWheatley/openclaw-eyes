# OpenClaw Legal First Pilot Go/No-Go Review Packet

## Purpose

This packet is an internal review workflow before any law-firm outreach, synthetic/public demo, paid pilot planning, or paid pilot decision.

It does not replace the first-pilot scope, buyer brief, readiness checklist, terms outline, support boundary, or launch criteria. It points to them in the order they should be used so the decision stays bounded, written, and reversible.

This is not buyer-facing copy, not legal advice, not a contract, and not approval to implement new features.

## Current posture

- Synthetic/public demo: Go.
- Paid first pilot: Conditional Go.
- Real deployment: No-Go until separately proven.
- `Run Synthetic Dry Run` exists for synthetic demo validation only, with fixed synthetic values and sanitized status-only output; Real-matter GUI Run, Reset, arbitrary bridge execution, and real matter through the app remain deferred or NO-GO.
- Safe Legal work is buyer/support/proof/terms packaging, not new functionality.

If any review step contradicts this posture, stop and update the source docs before continuing.

## Source packet

Use these documents together:

- `OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md` for the life, support, liability, and launch filter.
- `OPENCLAW_LEGAL_SUPPORT_BOUNDARY.md` for included, paid-extra, and never-included support.
- `OPENCLAW_LEGAL_FIRST_PILOT_SCOPE.md` for the narrow conditional first paid pilot scope.
- `OPENCLAW_LEGAL_FIRST_PILOT_BUYER_BRIEF.md` for buyer-facing draft language and exclusions.
- `OPENCLAW_LEGAL_PILOT_READINESS_CHECKLIST.md` for the internal demo and paid-pilot planning gate.
- `OPENCLAW_LEGAL_PILOT_TERMS_OUTLINE.md` for written agreement terms that must exist before paid pilot.
- `OPENCLAW_LEGAL_FOLDER_3_INTAKE_CHECKPOINT.md` for the active Folder 3 planning lane and implementation boundary.
- `../OPENCLAW_LEGAL_SYNTHETIC_DEMO_VALIDATION.md` for synthetic/public-safe demo proof.

Do not use this packet to weaken any source document.

## Review order

1. Confirm current built status and checkpoint.
2. Confirm no real matter data is needed for the review.
3. Review the support boundary before any buyer language.
4. Review the first-pilot scope before the buyer brief.
5. Review the buyer brief only for plain-language alignment, not as a promise.
6. Run the readiness checklist.
7. Run the terms outline.
8. Decide one outcome: synthetic/public demo, paid pilot planning, or no-go/pause.
9. Record reasons and conditions in writing.

If the decision cannot be written plainly, the answer is no-go/pause.

## Minimum green-light packet

Before moving to a synthetic/public demo, confirm:

- [ ] Synthetic/public demo data only.
- [ ] Current Legal Console checkpoint known.
- [ ] No real matter data used or inspected.
- [ ] Any Run action used in demo is `Run Synthetic Dry Run` only and follows the synthetic demo validation package, fixed synthetic values, and sanitized status-only output.
- [ ] Real-matter Run remains disabled or clearly unavailable.
- [ ] Reset remains disabled or clearly unavailable.
- [ ] No arbitrary bridge execution beyond the fixed synthetic-only dry run allowed by the synthetic demo validation package.
- [ ] No file picker, matter selection, real matter mode, Connect, queue/ETA, or model distribution.
- [ ] No internal OpenClaw agent names in legal UX.
- [ ] Buyer-facing language reviewed for overpromising.

Before moving to paid pilot planning, confirm:

- [ ] First workflow selected.
- [ ] Accepted file types selected.
- [ ] Unsupported-file policy accepted.
- [ ] Support window selected.
- [ ] Emergency/court-deadline support excluded or separately priced.
- [ ] Hardware owner or funder identified.
- [ ] Backup, retention, restore, offboarding, export, and wipe responsibilities assigned.
- [ ] Attorney-review and not legal advice language accepted.
- [ ] Payment, scope, support, data, hardware, liability, and termination terms drafted.
- [ ] No raw matter remote-support expectation.
- [ ] Synthetic demo passed first.

If these are not true, do not move to paid pilot planning.

## Hard stop review

Stop or pause if the buyer or workflow requires:

- legal conclusions
- privilege calls
- emergency or court-deadline support by default
- unsupported critical file types immediately
- raw matter remote review
- full e-discovery replacement
- open-ended custom work
- unlimited support
- broad cloud, email, portal, audio, video, media, timeline, contradiction, or privilege-screening features
- Run/Reset GUI behavior as a condition of pilot
- Connect, queue/ETA, or model distribution now
- real deployment before written support, liability, data, hardware, backup, and offboarding terms exist

Any single hard stop is enough. Do not build features to rescue a bad-fit pilot.

## Outcome rules

### Go to synthetic/public demo

Use only synthetic or public-safe data. Show only bounded built behavior, clearly labeled prototype behavior, and clearly labeled roadmap items. Do not imply real deployment readiness.

### Conditional Go to paid pilot planning

Schedule a planning session only. Draft written scope and terms. Do not implement new features from the planning session without a separate scoped plan and approval.

### No-Go / pause

Pause. Record the reason. Do not create external polish, custom features, emergency promises, or cheap open-ended support to make the deal look ready.

## Decision record template

```text
Date:
Reviewer:
Candidate firm or workflow:
Proposed demo or pilot step:
Current checkpoint:
File types:
Support window:
Hardware plan:
Data/backups/offboarding plan:
Readiness checklist result:
Terms outline result:
Verdict:
Reasons:
Conditions before proceeding:
Next allowed step:
```

## Next-step rule

If the packet produces Go to synthetic/public demo, use the synthetic/public demo validation package only.

If the packet produces Conditional Go to paid pilot planning, the next step is written planning, not implementation.

If the packet produces No-Go / pause, do not build custom features to rescue the deal.

Any implementation slice still needs its own scope, files, proof commands, tests if applicable, rollback expectations, and explicit approval. Anything involving changes to `Run Synthetic Dry Run`, Reset, arbitrary bridge execution, Real-matter GUI Run, real matter workflows, file pickers, Connect, queue/ETA, OCR/model distribution, unsupported-file feature expansion, timeline, contradiction, privilege screening, email/cloud connectors, cloud/external model processing, or OCR/media expansion remains out of scope until separately planned and approved.
