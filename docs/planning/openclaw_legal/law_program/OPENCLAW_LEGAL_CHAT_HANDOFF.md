# OpenClaw Legal — Chat Handoff

## Purpose

This handoff is for a new ChatGPT or Codex session.

The new chat should use this file to orient, then verify current facts before acting.

## Authority warning

`OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` governs this package.

If this handoff conflicts with governing principles, governing principles win unless intentionally updated.

This handoff is current-state guidance, not permanent doctrine.

PC/WSL Legal v0 was audited in `/home/openclaw` before the first safety slice was implemented.

The new chat should use the handoff to orient, not as implementation proof.


This file summarizes:

- what was already built in the canonical PC/WSL OpenClaw repo
- what was planned in the Mac `OpenClaw_Watch` workspace
- the critical product/safety/business doctrine
- the recommended next step

## Freshness rule

This handoff is session-current, not permanent doctrine.

This file should be the live handoff that new ChatGPT/Codex sessions check first, but it must be replaced when material facts change.

Replace and archive this handoff when any of these happen:

- PC/WSL Codex produces a materially newer implementation map
- Legal v0 changes materially
- the next 3–5 build slices are chosen
- a first firm/pilot scope becomes concrete
- the business/go-no-go decision changes
- the Mac planning docs get reorganized

When stale, move the old file to:

```text
law_program/archive/
```

Use a dated name such as:

```text
OPENCLAW_LEGAL_CHAT_HANDOFF_2026-04-25_mac-planning.md
```

Then replace `law_program/OPENCLAW_LEGAL_CHAT_HANDOFF.md` with a fresh current handoff.

Any new chat, Codex session, or implementation agent should treat this freshness rule as a first-order instruction. If the handoff appears stale, stop and ask for or create a replacement before relying on it.

## Canonical implementation authority

The canonical implementation repo is:

```text
/home/openclaw
```

That repo lives on the PC/WSL OpenClaw system and remains the implementation authority.

The Mac workspace is:

```text
/Users/hwinshipwheatley/OpenClaw_Watch
```

The Mac workspace is a planning/reflection surface. It is not canonical implementation truth.

Do not implement blindly from the Mac planning docs. First verify the current PC/WSL repo state.

## Known Legal v0 work already built on PC/WSL

The Legal v0 foundation was built in `/home/openclaw` before this Mac planning session, then audited in the canonical PC/WSL repo.

Before the first safety slice, the focused Legal v0 suite was verified at:

```text
80 passed
```

Verified Legal v0 pieces include:

- `legal/matter_workspace.py`
  - matter workspace creation
  - manifest
  - audit log
  - source copy/registration
  - SHA-256 source tracking

- `legal/local_ingestion.py`
  - local extraction for `.txt`
  - local extraction for `.md`
  - text-layer `.pdf` extraction through local `pdftotext` path
  - unsupported / no-text / failed extraction statuses

- `legal/local_search.py`
  - literal case-insensitive search over extracted text

- `legal/search_report.py`
  - Markdown search report export

- `legal/review_packet.py`
  - folder-based review packet export
  - manifest/audit/extracted/report packet structure

- `legal/deployment_profile.py`
  - local-first deployment profile helper
  - default profile
  - validation
  - save/load stable JSON

- `legal/cli.py`
  - CLI wrapper over the legal APIs
  - known commands:
    - `create-matter`
    - `add-source`
    - `extract`
    - `extract-all`
    - `search`
    - `report`
    - `review-packet`
    - `default-profile`

- `scripts/demo_legal_matter_workflow.py`
  - deterministic demo workflow

- Legal docs/checkpoints
  - `legal/README.md`
  - `legal/CLI_DEMO_WALKTHROUGH.md`
  - `legal/CHECKPOINT.md`

- Legal tests
  - focused Legal v0 suite passed before the safety slice: `80 passed`

## Completed first safety slice

The first Legal safety slice is implemented in `/home/openclaw`.

New file:

- `legal/path_guard.py`

Updated implementation files:

- `legal/matter_workspace.py`
- `legal/local_ingestion.py`
- `legal/local_search.py`
- `legal/search_report.py`
- `legal/review_packet.py`

Implemented behavior:

- matter roots are canonicalized/resolved before use
- matter workspaces resolving under `/home/openclaw` are rejected
- symlink/traversal into the product repo is rejected
- manifest `stored_path` values are validated before extraction/search/report/review-packet trust them
- tampered `stored_path` values outside the matter root fail closed

Proof:

- `py_compile` passed for changed legal modules
- focused new/updated path-guard tests: `7 passed`
- full focused Legal suite after the slice: `87 passed in 1.37s`

Remaining risks:

- the repo-boundary guard is not yet a full configured Legal Vault allowlist
- review packets remain content-bearing and are not sanitized support packets
- firm/update/profile policy boundaries remain future slices

## What was planned in the Mac workspace

The Mac planning session created and organized a planning package under:

```text
/Users/hwinshipwheatley/OpenClaw_Watch/law_program
```

The planning package includes technical/product contracts, UX specs, business planning docs, risk docs, and launch decision gates.

## Technical/product contracts created or populated

These documents define product architecture, safety boundaries, update behavior, role naming, vault separation, node connection, queueing, ETA, and model distribution:

- `LEGAL_PRODUCT_CORE_SEPARATION.md`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT.md`
- `LEGAL_VAULT_PATH_CONTRACT.md`
- `LEGAL_ROLE_NAMING_CONTRACT.md`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST.md`
- `LEGAL_UPDATE_LANE_CONTRACT.md`
- `LEGAL_CONNECT_MENU_CONTRACT.md`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT.md`
- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT.md`
- `LEGAL_ADAPTIVE_ETA_CONTRACT.md`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT.md`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`
- `LEGAL_V1_CONTRACT_INDEX.md`

## Business planning docs created or populated

These documents define the buyer problem, business plan, pitch deck, mockups, pricing, gotchas, opportunity models, and go/no-go launch criteria:

- `business_plan/BUSINESS_PLAN_INDEX.md`
- `business_plan/OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_PLAN.md`
- `business_plan/OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`
- `business_plan/OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`
- `business_plan/OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`
- `business_plan/OPENCLAW_LEGAL_GOTCHAS.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`
- `business_plan/OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`

## Critical doctrine

The following points are binding planning doctrine for the next chat:

- Mac `OpenClaw_Watch` docs are planning/reflection only.
- PC/WSL `/home/openclaw` is canonical implementation authority.
- Do not implement blindly from Mac docs.
- First inspect existing Legal v0 code, tests, docs, and commits.
- No real legal data should enter the repo, prompts, support packets, update packages, or non-local LLM context.
- Legal product UX must not expose internal OpenClaw agent names such as Cassandra, Chief, Guardian, Hermes, or PI.
- Legal-facing roles should use plain law-office labels such as Intake Clerk, Evidence Clerk, Records Custodian, Review Coordinator, Compliance Gate, and Systems Clerk.
- The Go/No-Go Launch Criteria sits above the business plan.
- This should become a bounded product/support business, not a stressful law-firm emergency support job.
- Firm #2 changes must never affect Firm #1 unless Firm #1 explicitly installs/enables them.
- Matter Vault must stay separate from product core and firm profile.
- Unsupported files must use local-first Alternative Methods before feature-request escalation.
- Updates must be lane-based: security, stability, installed module updates, and optional new modules.
- Primary Node should own vault, policy, audit, updates, model distribution, and orchestration.
- Worker/lawyer nodes must not silently join or receive broad matter access by default.
- ETA must be conservative, confidence-labeled, and calibrated before high-confidence claims.
- Huge local models are not the product foundation; deterministic vault/source/search/report/audit/queue boundaries come first.

## Current strategic posture

OpenClaw Legal should be framed as:

```text
Private local discovery infrastructure for law firms that need control, speed, auditability, and predictable cost.
```

It should not be framed as:

- an AI lawyer
- a lawyer replacement
- a generic chatbot
- a complete enterprise e-discovery replacement on day one
- a system that gives legal advice
- a system that removes the need for attorney review

The first sellable version should focus on a controlled local foundation:

- Legal Vault boundary
- matter/source tracking
- hashing
- local extraction
- search
- reports
- review packets
- audit trail
- visible status
- unsupported-file workflow
- update/profile architecture

## Business/launch caution

The user is willing to invest upfront time and build effort, but does not want this to become:

- a painful daily operations job
- a law-firm emergency support desk
- a source of lawsuit risk
- an unlimited custom development trap
- a personally stressful on-call role

The business should aim for passive-ish or remote-managed income where possible, with bounded setup, bounded support, paid modules, clear legal disclaimers, and strict support limits.

No real firm deployment should happen without:

- written scope
- payment/hardware agreement
- support boundary
- liability limitation
- no-legal-advice language
- attorney review requirement
- data ownership terms
- local-only/data residency expectations
- update/support terms
- emergency/rush support pricing or exclusion
- permission to use only sanitized diagnostics for product improvement

## Recommended next step

The next ChatGPT/Codex session should choose the next small safety/product-boundary slice after the completed path guard work.

Likely candidates:

1. configured Legal Vault allowlist / vault profile boundary
2. sanitized support packet v0
3. role-key/legal-facing naming cleanup
4. unsupported-file Alternative Methods next-action model
5. update lane metadata skeleton

The next slice should remain small, testable, reversible, and Legal-only. It should include exact files, tests, proof commands, and rollback/checkpoint expectations.

The likely best next engineering move is still not distributed compute or huge local models. It is continuing boundary hardening around the Legal v0 spine.

## What not to do next

Do not immediately build:

- distributed worker nodes
- model distribution
- full desktop app
- OCR pipeline
- cloud connectors
- email/portal ingest
- privilege screening
- legal advice/synthesis
- broad LLM review modules
- hardware leasing operations

Those are later modules or business decisions. They should follow boundary hardening and first workflow proof.

## Next-chat instruction

The new chat should verify current repo state, read this handoff, then help choose and execute only the next small Legal safety/product-boundary slice.

The new chat should not spend time re-summarizing every planning doc unless asked.

The next useful output is either a tight Codex implementation prompt for the chosen slice or a direct implementation pass if the user asks Codex to proceed in `/home/openclaw`.
