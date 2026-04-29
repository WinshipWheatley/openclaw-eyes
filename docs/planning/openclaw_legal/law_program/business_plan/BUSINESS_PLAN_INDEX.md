# OpenClaw Legal — Business Plan Index

## Purpose

This folder is the business planning layer for the OpenClaw Legal planning package.

It should help Codex and Winship understand the buyer problem, commercial posture, launch risks, upside opportunities, and pitch/mockup preparation. It should not trigger broad implementation work from this Mac workspace.

## Governing principles

`../OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` governs this business planning package too.

The Go/No-Go file remains the launch gate.

`OPENCLAW_LEGAL_SUPPORT_BOUNDARY.md` defines the support, buyer, data, hardware, emergency, and offboarding boundaries that must be clear before paid pilot or deployment.

Business opportunities do not overrule governing principles or go/no-go criteria.

## Decision order

`OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md` sits above the business plan.

If the go/no-go gate does not clear, the business plan, pitch deck, mockups, pricing, and opportunity ideas should remain internal planning material.

External-facing versions should only be created if the internal go/no-go gate clears.

## Document map

### `OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`

Hard launch filter.

Use this first to decide whether OpenClaw Legal should move toward real buyer-facing launch at all. It protects against open-ended support burden, legal-adjacent liability, unfunded hardware risk, sensitive-data exposure, and a stressful custom services trap.

### `OPENCLAW_LEGAL_SUPPORT_BOUNDARY.md`

Support and buyer boundary doctrine.

Use this to define what buyers are buying, what they are not buying, what support includes or excludes, and what must be contracted before paid pilot or deployment.

### `OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`

Buyer problem definition.

Use this to explain the discovery pain in buyer language: messy intake, unclear processing status, unsupported files, audit anxiety, cloud/privacy concerns, and unpredictable e-discovery cost.

### `OPENCLAW_LEGAL_BUSINESS_PLAN.md`

Commercial plan.

Use this after the go/no-go gate to organize target buyer, category, value proposition, packaging, first-firm path, and productization assumptions.

### `OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`

Buyer-facing preparation doc.

Use this to draft a pitch deck that explains the problem, local-first positioning, controlled console, v1 scope, roadmap, and expected buyer value without overclaiming implementation status.

### `OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`

Buyer-facing preparation doc.

Use this to guide visual mockups for the legal console and sales conversation. Mockups should clarify the product feel and workflow, not imply unbuilt features are already working.

### `OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`

Pricing and market-positioning guide.

Use this to keep pricing tied to operational value, local control, auditability, support burden, hardware strategy, modules, and predictable cost. It is not a final price sheet.

### `OPENCLAW_LEGAL_GOTCHAS.md`

Internal risk register.

Use this to track traps that could make the business too custom, too risky, too expensive, too brittle, or too stressful. This is not buyer-facing.

### `OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`

Upside/opportunity register.

Use this to preserve revenue-model and expansion ideas such as managed software, firm-owned hardware, modules, training, support plans, and future node expansion. This is internal until validated.

## Internal vs external use

Internal-only:

- `OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`
- `OPENCLAW_LEGAL_SUPPORT_BOUNDARY.md`
- `OPENCLAW_LEGAL_GOTCHAS.md`
- `OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`
- `BUSINESS_PLAN_INDEX.md`

Buyer-facing preparation:

- `OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`
- `OPENCLAW_LEGAL_BUSINESS_PLAN.md`
- `OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`
- `OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`
- `OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`

Buyer-facing preparation does not mean ready to send. Create separate external-facing versions only after the internal go/no-go gate clears.

## Future PC/WSL handoff use

When Codex returns to the canonical PC/WSL repo, it should verify `/home/openclaw` before implementation.

These docs should inform a build plan, not trigger immediate broad implementation.

The first implementation plan should map existing Legal v0 code and tests to these contracts and business constraints.

Keep implementation slices small, tested, and reversible. Use proof commands/checkpoints after each slice and avoid multi-feature rewrites.
