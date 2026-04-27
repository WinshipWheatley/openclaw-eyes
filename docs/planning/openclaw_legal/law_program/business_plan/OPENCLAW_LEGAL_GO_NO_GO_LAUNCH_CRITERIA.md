

# OpenClaw Legal — Go / No-Go Launch Criteria

## Position in stack

This document sits above the business plan.

The business plan answers:

```text
If this is safe to pursue, how should it be sold and grown?
```

This document answers:

```text
Should this be launched at all?
```

If this document says no-go, the business plan does not matter yet.

## Purpose

This document decides whether OpenClaw Legal is safe, profitable, low-stress, and bounded enough to launch.

It exists to prevent OpenClaw Legal from turning into a stressful custom legal-tech services job, emergency discovery support desk, unpaid product lab, or liability trap.

This is not a hype document. It is a launch filter.

## Core question

```text
Can OpenClaw Legal become a bounded product/support business that can produce passive-ish or remote-managed income, or will it become a high-stress custom legal operations job?
```

Default answer:

```text
No launch until the burden, liability, scope, and support model are proven to be contained.
```

The project should launch only if the answer is clearly closer to:

```text
bounded product/support business
```

and not:

```text
Winship becomes the law firm’s emergency IT, discovery, AI, and litigation support department.
```

## Hard rule

This is a life-protection filter, not a motivation filter.

OpenClaw Legal should be blocked from launch if the likely outcome is any of the following:

- recurring emergency support
- open-ended custom work disguised as product work
- personal assumption of legal-adjacent risk
- unbounded access to sensitive matter data
- revenue that does not justify the stress, time, or liability

Strong buyer enthusiasm is not enough.

Strong product excitement is not enough.

Technical feasibility is not enough.

The launch must be economically sane, contractually bounded, operationally supportable, and personally survivable.

## Personal operating goal

Winship is willing to invest upfront time, engineering work, planning, and some build cost to create a real product.

Winship does not want:

- a stressful daily operations job
- to babysit law-firm matters
- to be responsible for emergency litigation deadlines
- to become the firm’s IT department
- to provide legal advice
- to be exposed to unnecessary lawsuit risk
- to take unlimited support calls
- to be trapped in custom one-off development
- to hold sensitive client data personally
- to front major hardware/software costs without a signed path to recovery

The business should aim for:

- passive-ish recurring revenue where possible
- remote-managed support where necessary
- bounded setup/deployment work
- paid custom modules when needed
- clear liability limits
- productized architecture that can serve more than one firm

## Launch thesis

OpenClaw Legal is launchable only if it can be sold as:

```text
private local discovery infrastructure with defined support, controlled updates, clear legal-data boundaries, and modular expansion.
```

It is not launchable if it is effectively:

```text
unlimited custom discovery support plus emergency technology liability.
```

## Go criteria

The project can move toward launch if all of these are true.

### Buyer and business fit

- The first firm has real discovery pain.
- The first firm has real budget.
- The first firm accepts a focused Version 1 scope.
- The first firm understands this is not legal advice automation.
- The first firm accepts that unsupported files follow a defined workflow, not unlimited emergency handling.
- The first firm will pay for hardware directly or through a signed deployment agreement.
- The first firm is willing to use a bounded pilot or first workflow.
- The first firm understands what is built now versus roadmap.

### Product fit

- The product has a narrow first workflow that works end-to-end.
- The workflow produces clear buyer-visible value.
- The system can show what was received, processed, failed, unsupported, searchable, and packet-ready.
- The product can run locally without sending matter data to non-local systems by default.
- The product can be supported remotely without Winship handling raw sensitive matter data.
- The product can be improved through reusable modules rather than firm-specific hacks.

### Technical fit

- Legal Vault boundaries are enforced.
- Matter data stays outside the product repo.
- Support packets are sanitized.
- Non-local LLMs are blocked from matter-vault content by default.
- Core / Firm Profile / Matter Vault / Module boundaries are clear.
- The first deployment can be tested with synthetic/public fixtures.
- Updates can be packaged without including matter data.
- The system has proof commands/checkpoints for major workflows.

### Support fit

- Support boundaries are written down.
- Included support is limited.
- Paid support categories are defined.
- Rush/emergency support is either excluded or priced very high.
- Custom unsupported-file handlers are paid work unless explicitly included.
- The firm understands that Winship is not providing legal advice.
- The firm understands that attorney review remains required.

### Commercial fit

- Setup fee covers meaningful upfront labor.
- Hardware cost is covered by the firm or a signed agreement.
- Ongoing support/update plan exists.
- Optional modules can become recurring or paid expansion revenue.
- The first deployment can become reusable product architecture.
- Firm #2 can benefit from the architecture without receiving Firm #1 data or workflow changes by default.

## No-go criteria

Do not launch if any of these are true.

Any single item in this section is enough to stop launch until it is fixed.

### Buyer red flags

- The firm expects free or unlimited custom development.
- The firm expects instant support for every file type.
- The firm expects the system to make legal judgments.
- The firm expects privilege decisions without attorney review.
- The firm expects Winship to be available for emergency litigation deadlines.
- The firm will not pay enough to cover setup, hardware, support, and risk.
- The firm refuses a written scope.
- The firm refuses clear support boundaries.
- The firm treats the product as a replacement for staff, counsel, or litigation-support professionals.

### Technical red flags

- Real matter data would enter the repo.
- Real matter data would enter non-local model prompts.
- Support packets would include sensitive content.
- The product cannot enforce vault boundaries.
- Updates cannot be separated from matter data.
- The first workflow cannot be tested safely.
- The system requires constant manual repair to function.
- Unsupported files dominate the first workflow.
- The product cannot produce reliable audit/status output.

### Business red flags

- Hardware must be purchased personally on speculation.
- The firm wants custom ownership of reusable product code.
- The firm wants unlimited support for a one-time fee.
- The firm wants broad connectors before the local workflow is stable.
- The firm requires a full enterprise e-discovery replacement on day one.
- There is no credible path to Firm #2 reuse.
- Pricing does not account for support burden.

### Personal red flags

- Winship feels like he is becoming the firm’s IT department.
- Winship feels responsible for legal deadlines.
- Winship is expected to monitor matters manually.
- Winship would need to touch raw sensitive matter data regularly.
- Winship would be on-call in a way that conflicts with music/life priorities.
- The work feels like a stressful job rather than a product business.

## Stress and liability red flags

The strongest danger signals:

- “Can you just fix this before court tomorrow?”
- “Can you tell us what this evidence means?”
- “Can you determine if this is privileged?”
- “Can you remote in and look at the case files?”
- “Can you guarantee this found everything?”
- “Can we just send you the discovery?”
- “Can you include unlimited support?”
- “Can we pay later after it works?”
- “Can you build the whole platform first and then we decide?”

These indicate legal, support, payment, or scope danger.

## Required contract terms before deployment

No real firm deployment should happen without written terms covering at least:

- scope of work
- what v1 includes
- what v1 excludes
- setup fee
- hardware ownership/payment
- support boundaries
- update/support term
- paid custom work rules
- emergency/rush support rules
- no legal advice disclaimer
- attorney review requirement
- limitation of liability
- data ownership
- data residency/local-only expectation
- support packet sanitization
- permission to use only sanitized diagnostics for product improvement
- no guarantee of legal outcome
- no guarantee every file type is supported
- backup/restore responsibility
- termination/offboarding/wipe process

## Required product proof before launch

Before calling this a launchable v1, the system should prove:

- create matter
- register source files
- hash source files
- extract supported files
- identify unsupported/no-text files
- search extracted text
- generate report
- generate review packet
- preserve audit trail
- keep matter data outside repo
- run proof commands on synthetic/public data
- show clear status for processed/failed/unsupported items
- **Attorney-Gated QA / Review-and-Rework:** Required before deployment of system-generated timelines, contradiction candidates, summaries, or other substantive review outputs. Product proof must show that these outputs are flagged, source-linked, attorney-review framed, and require attorney approval before rework or finalization.
- **Known-Answer Fixtures / Validation Sentinels:** Required before deployment of OCR, substantive review modules, or firm updates. Prove that the system can catch seeded failure cases (OCR misses, timestamp mismatches, citation errors, etc.) in Lane A benchmarks before trusting Lane B workflows.
- document exact limitations

## Required security/privacy proof before launch

Before real matter data is used, prove:

- Legal Vault path is outside repo
- support packets exclude matter content
- update packages exclude matter content
- non-local LLM access to vault is blocked by default
- test/demo fixtures are synthetic or public
- logs do not leak sensitive content unnecessarily
- export outside vault requires explicit approval
- permission model is clear enough for first use
- backup/offboarding behavior is defined

## Required business proof before launch

Before major spend or handoff to a firm, confirm:

- buyer pain is real
- buyer budget is real
- first workflow is narrow
- must-have file types are known
- hardware plan is funded
- support plan is bounded
- paid custom work path exists
- firm accepts phased roadmap
- product can be reused for other firms
- Winship is not personally absorbing open-ended obligations

## Hardware/payment decision gate

Do not buy expensive hardware on speculation unless it is acceptable as Winship-owned dev/demo/test hardware.

Preferred path:

```text
Firm buys or funds Primary Node
+ pays setup/deployment
+ signs support/update terms
+ optional modules/custom work are priced separately
```

Acceptable alternatives:

- firm-owned hardware supplied by firm
- hardware cost covered by signed deployment agreement
- Winship-owned demo/lab machine used before firm purchase

Avoid:

- buying a maxed Mac Studio personally before scope/payment are clear
- promising future 512GB hardware migration without migration plan
- making model-size dreams drive the first business decision

## First-firm pilot gate

A first firm pilot should be allowed only if:

- one specific matter/workflow is selected
- file types are known
- local-only expectations are agreed
- supported/unsupported scope is clear
- success criteria are written down
- payment is agreed
- support boundary is agreed
- no legal advice expectation exists
- no unlimited emergency support expectation exists
- firm understands roadmap versus current capability

Pilot success should mean:

- firm can see matter/source status
- supported files process
- unsupported files are visible and actionable
- search/report/packet outputs are useful
- audit trail is present
- privacy boundaries hold
- firm wants to continue or expand under paid terms

## Passive-income viability score

Before launch, score the opportunity from 1–5 in each area.

```text
1 = bad / high stress / not productized
5 = strong / bounded / productized / remote-manageable
```

Score categories:

- Buyer budget
- Buyer scope discipline
- Product reuse potential
- Support burden
- Hardware risk
- Legal/liability risk
- Data privacy confidence
- Remote support viability
- Module expansion potential
- Personal stress impact

Interpretation:

```text
40–50: strong candidate for launch/pilot
30–39: proceed only with narrowed scope and protections
20–29: planning/demo only, do not deploy real firm data
below 20: no-go
```

If Personal Stress Impact is below 3, no-go unless scope is radically changed.

If Legal/Liability Risk is below 3, no-go until contract/privacy boundaries are improved.

If Support Burden is below 3, no-go unless support is reduced or repriced.

## Launch decision states

### Go

Proceed to first paid pilot/deployment.

Conditions:

- scope is bounded
- payment is real
- data boundaries are proven
- support is limited
- legal disclaimers and liability terms exist
- first workflow is achievable
- productization path is preserved

### Conditional go

Proceed only after specific blockers are fixed.

Examples:

- hardware agreement needed
- support terms needed
- vault path proof needed
- unsupported-file scope needs narrowing
- buyer expectations need correction

### No-go for deployment, yes for demo

Use synthetic/public demo only.

Good when:

- product needs more proof
- buyer interest exists but scope/payment is not clear
- privacy/security boundary is not proven enough for real matter data

### No-go

Stop or pause.

Reasons:

- no budget
- no bounded scope
- too much liability
- too much support burden
- no productization path
- too stressful

## Final launch rule

OpenClaw Legal should not launch just because it is technically possible.

It should launch only if it is:

```text
paid
bounded
local-first
supportable
legally disclaimed
productizable
low enough stress
and valuable enough to the buyer
```

If those conditions are not met, keep building the demo, pitch, mockups, and product foundation — but do not put real firm data or Winship’s personal stress on the line.

## Bottom line

This project is worth pursuing only if it becomes a product business, not a crisis-support job.

This file is the "do not ruin my life" gate.

It is supposed to be stricter than the business plan, stricter than the pitch, and stricter than buyer enthusiasm.

The correct launch posture is:

```text
small paid pilot
clear scope
firm-funded hardware
strict privacy boundaries
limited support
no legal advice
module-based growth
remote-manageable operations
```

Anything else should be treated as no-go or conditional go.

## External-facing version note

If this project ever clears the go/no-go gate, create a separate external-facing version of this document before showing anything to a law firm, investor, partner, vendor, or buyer.

That external version is only necessary if this becomes a real go.

Do not waste time polishing buyer-safe language while the project is still conditional or no-go.

The internal version should stay blunt. Its job is to protect the operator from bad deals, vague obligations, legal-adjacent stress, and fake business momentum.

The external version should preserve the same boundaries, but translate them into professional language such as:

- implementation readiness criteria
- deployment prerequisites
- support boundaries
- privacy and data-handling requirements
- pilot scope requirements
- service limitations
- attorney review requirements
- update and maintenance terms

The external version must not weaken the internal gate.

If the internal answer is no-go, do not create external polish to make the project look more ready than it is.
