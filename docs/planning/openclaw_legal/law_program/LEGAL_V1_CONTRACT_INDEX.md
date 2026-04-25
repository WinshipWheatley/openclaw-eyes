

# OpenClaw Legal v1 Contract Index

## Purpose

This folder is an off-network planning package for OpenClaw Legal v1.

It was created while away from the home network / full PC-WSL OpenClaw runtime. The Mac `OpenClaw_Watch` workspace is a planning and reflection surface, not canonical implementation truth.

The PC/WSL OpenClaw repo remains the implementation authority. Before any build work begins, Codex should verify these contracts against the canonical PC/WSL repo and inspect what Legal v0 has already built.

## Governing principles

`OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` governs this planning package.

The contract docs should be read under those principles.

The principles are not implementation proof. They are behavioral constraints for future work.

## Referenced but not yet created contracts

Some docs reference future/uncreated contracts, including:

- `LEGAL_NO_SURPRISE_UPDATE_CONTRACT`
- `LEGAL_MODULE_VERSION_PINNING`
- `LEGAL_SANITIZED_SUPPORT_PACKET`
- `LEGAL_LOCAL_ONLY_MODEL_POLICY`
- `LEGAL_AI_ACCESS_CLASSIFICATION`
- `LEGAL_WORKER_DATA_RETENTION_CONTRACT`
- `LEGAL_MODEL_COMPARISON_CONTRACT`
- `LEGAL_ARTIFACT_RECHECK_CONTRACT`
- `LEGAL_NODE_PERFORMANCE_HISTORY_CONTRACT`
- `LEGAL_UPDATE_VALUE_REPORTING_CONTRACT`
- `LEGAL_DISCOVERY_INTAKE_CONNECTOR_CONTRACT`
- `LEGAL_HUMAN_PRIORITY_NODE_CONTRACT`
- `LEGAL_RESOURCE_HEADROOM_CONTRACT`
- `LEGAL_LOCAL_REPAIR_AGENT_BOUNDARY`
- `LEGAL_PUBLIC_ANALOG_FIXTURE_SEARCH`

These references are roadmap/placeholders unless the file actually exists.

They do not carry authority yet.

Do not implement from a missing contract title. Create and populate the contract first if it becomes necessary.

## Current planning package

This package contains the first contract/spec batch for turning the existing Legal v0 spine into a reusable, sellable Legal v1 product architecture.

The central product idea:

```text
OpenClaw Legal Core
+ Firm Profile
+ Private Matter Vault
+ Optional Suite Modules
+ Controlled Legal Console
```

The architecture must support the first law-firm deployment without becoming a one-off custom fork.

## Package map

This index maps the planning package only. It does not prove implementation status.

### Technical/product contracts

Use these later to compare against the canonical PC/WSL Legal v0 code and tests:

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

### UX/spec docs

Use these later to inform controlled-console design, not as proof that the console already exists:

- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`

### Business-plan folder

The business planning package lives in:

- `business_plan/`

Start with:

- `business_plan/BUSINESS_PLAN_INDEX.md`

That folder contains buyer-problem, business-plan, pitch, mockup, pricing, risk, opportunity, and go/no-go planning docs.

## Internal-only vs buyer-facing prep

### Internal-only docs

These documents are for operator/Codex planning and should not be handed to buyers without creating a separate external version:

- `OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md`
- `LEGAL_V1_CONTRACT_INDEX.md`
- `law_program plan_bulletpoints.md`
- all `LEGAL_*_CONTRACT.md` files
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`
- `business_plan/OPENCLAW_LEGAL_GOTCHAS.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`
- `business_plan/OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`
- `business_plan/BUSINESS_PLAN_INDEX.md`

### Buyer-facing preparation docs

These documents can inform buyer-facing material, but external versions should be created separately and only after the internal go/no-go gate clears:

- `business_plan/OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_PLAN.md`
- `business_plan/OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`
- `business_plan/OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`
- `business_plan/OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`

## Mac planning warning

This Mac workspace is a planning/reflection surface.

It is not the canonical implementation repo, not the deployment authority, and not proof that Legal v1 exists in code.

Future Codex work should treat these documents as input for a build plan after verifying the canonical PC/WSL repo at `/home/openclaw`.

## Non-canonical warning

These files are planning documents.

They should not be treated as proof that a feature is implemented.

Before implementation, Codex should:

1. Open the PC/WSL repo at `/home/openclaw`.
2. Inspect the existing `legal/` package and tests.
3. Verify recent commits and checkpoint docs.
4. Confirm what Legal v0 actually contains.
5. Build a staged plan with tests and rollback/checkpoint points.

## Contract files by theme

### Productization and firm stability

#### `LEGAL_PRODUCT_CORE_SEPARATION.md`

Defines the core product boundary:

- reusable OpenClaw Legal Core
- firm-specific profile/config
- private Matter Vault
- optional suite modules

This is the upstream doctrine. It prevents the first firm deployment from becoming an unmaintainable custom branch and ensures future firms can receive reusable architecture without sensitive data carryover.

#### `LEGAL_FIRM_IMMUTABILITY_CONTRACT.md`

Defines the strict rule that Firm #2 changes must never affect Firm #1 unless Firm #1 explicitly installs/enables the relevant update or module.

Key ideas:

- no surprise menu/options/workflow changes
- security/stability/module/new-capability lanes
- firm profile isolation
- pinned firm/module versions
- updates must preserve working deployments

### Privacy and vault boundaries

#### `LEGAL_VAULT_PATH_CONTRACT.md`

Defines where sensitive matter data may and may not live.

Key ideas:

- real legal data must stay outside the product repo
- matter roots must live under an approved Legal Vault
- vault paths must be checked before processing/export/support/update actions
- non-local LLMs must not read matter vault data by default
- path boundary violations fail closed

### Legal-facing roles and UX language

#### `LEGAL_ROLE_NAMING_CONTRACT.md`

Defines legal-facing role names and forbids internal OpenClaw names from the legal product UX.

Key ideas:

- no Cassandra / Chief / Guardian / Hermes / PI names in the law-firm product
- use bounded legal/operations roles such as Intake Clerk, Evidence Clerk, Records Custodian, Review Coordinator, Compliance Gate, Systems Clerk
- every role needs allowed and forbidden actions
- attorney judgment remains with attorneys

#### `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`

Defines the first controlled UX target.

Key ideas:

- the product should be a controlled legal operations console, not Obsidian-only and not an agent swarm
- persistent confidence/status bar
- matter/source/extract/search/packet/connect/queue/update/alternative-methods screens
- truthful operational language
- Tauri or similar controlled shell may be useful later

### Unsupported files and update pathways

#### `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST.md`

Defines the Alternative Methods workflow for unsupported files.

Key ideas:

- unsupported does not mean external
- try local classification and installed handlers first
- attempt local sandbox build/repair when policy allows
- Request Feature appears only after local attempt fails or is policy-blocked
- feature requests must be sanitized and may include public analog/stress-test fixture candidates

#### `LEGAL_UPDATE_LANE_CONTRACT.md`

Defines update lanes and firm-facing update behavior.

Key ideas:

- Security Updates
- Stability Updates
- Installed Module Updates
- Optional New Modules
- update manifests must disclose lane, risk, affected module, workflow impact, matter-data impact, tests, rollback
- updates must not silently change firm workflow

### Connect menu and multi-node processing

#### `LEGAL_CONNECT_MENU_CONTRACT.md`

Defines the Connect menu and multi-computer firm network model.

Key ideas:

- Primary Node owns vault, policy, audit, updates, model distribution, and orchestration
- attorney workstations can be assigned-matter workstations and optional compute nodes
- no computer joins silently
- worker tasks are leased
- human use always preempts background compute

#### `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT.md`

Defines attorney/device/matter permission logic.

Key ideas:

- matter access requires attorney identity + approved device + matter assignment/share + firm policy
- review handoffs must be scoped and auditable
- lawyer workstations show My Matters, Shared With Me, Review Requests
- Primary Node remains permission authority

### Queue, ETA, calibration, and model distribution

#### `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT.md`

Defines the firm-level processing queue.

Key ideas:

- significant processing work should be queued, visible, prioritized, leased, audited, and recoverable
- queue supports matter/user/firm views
- queue statuses include downloading, staged, queued, processing, blocked, review ready, failed, completed
- later supports discovery intake, distributed work, and ETA

#### `LEGAL_ADAPTIVE_ETA_CONTRACT.md`

Defines conservative, evidence-based ETA behavior.

Key ideas:

- ETA is a measured operational forecast with confidence
- new models/nodes/updates start in calibration
- projected vs measured time savings must be labeled
- performance history should be task/model/node/workload specific
- high-confidence ETA requires enough local samples

#### `LEGAL_MODEL_DISTRIBUTION_CONTRACT.md`

Defines model download, verification, staging, activation, and calibration across firm computers.

Key ideas:

- Primary Node downloads and verifies models
- worker nodes do not independently download models
- workers stage new models while continuing current work
- activation happens at safe task boundaries
- new models calibrate before being claimed as improvements

## How to use this package later

When back on the PC/WSL OpenClaw system, Codex should use this package as planning input, not direct implementation truth.

Recommended process:

1. Verify the PC/WSL repo state.
2. Read Legal v0 files, tests, README, CLI walkthrough, and checkpoint docs.
3. Map what is already built against these contracts.
4. Identify reusable components already present.
5. Identify missing hard boundaries that need tests before features.
6. Produce a staged implementation plan.
7. Keep implementation slices small, testable, and reversible.
8. Prefer proof/checkpoint commands after each slice.
9. Do not implement everything at once.

## Recommended first PC/WSL build-plan questions

Codex should answer these before writing code:

- Which contracts are already partially implemented by Legal v0?
- What Legal v0 modules can be reused directly?
- What existing tests already prove parts of these contracts?
- What hard boundaries need tests before UX/features are expanded?
- Where are legal data paths currently allowed?
- Does the current deployment profile already support vault/profile separation?
- What is the smallest next build slice that increases product safety?
- What should be the first three implementation slices?
- What proof commands/checkpoints are required after each slice?
- Which features should remain planning-only until later?

## Do not do yet

Do not start by building distributed LLM agents.

Do not wire cloud connectors before vault/privacy/local-only contracts are enforced.

Do not expose Cassandra, Chief, Guardian, Hermes, PI, or other internal OpenClaw names in legal product UX.

Do not let Firm #2 changes affect Firm #1 by default.

Do not place real legal data in the repo, support packets, public fixtures, or non-local LLM context.

Do not build portal/discovery connectors before the staging/vault/queue model is clear.

Do not implement model distribution before update lanes and node enrollment boundaries are defined.

Do not make Obsidian the primary sellable UX controller.

Do not overbuild the Tauri/desktop shell before the Python Legal engine boundaries are hardened.

## Suggested staged direction

A reasonable build order to verify later:

1. **Harden Legal v0 boundaries**
   - vault outside repo
   - support/update packet exclusions
   - profile/core separation tests

2. **Profile and immutability layer**
   - firm profile isolation
   - module version pins
   - no-surprise update metadata

3. **Controlled console groundwork**
   - status model
   - legal-facing role labels
   - no internal-name UX audit

4. **Queue foundation**
   - single-machine task queue
   - matter queue visibility
   - basic ETA/confidence labels

5. **Unsupported-file Alternative Methods**
   - local classification
   - local handler attempts
   - gated support packet

6. **Connect menu skeleton**
   - Primary Node / this computer only
   - node identity model
   - no distributed compute yet

7. **Matter assignment and review handoff**
   - assigned matters
   - shared review requests
   - scoped permissions

8. **Distributed deterministic work**
   - worker node enrollment
   - task leases
   - hash/extract/search-index work

9. **Model distribution and adaptive ETA**
   - Primary Node model registry
   - staging/activation
   - calibration/time-savings reporting

10. **Future modules**
   - discovery intake connectors
   - OCR
   - email evidence
   - timelines
   - privilege screening
   - local model review modules

## Current first-batch status

The following first-batch planning docs should now exist and be populated:

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

The broader bullet capture remains in:

- `law_program plan_bulletpoints.md`

## Final instruction for future Codex use

When Codex reads this folder later, it should produce a build plan first.

It should not immediately implement these contracts.

The build plan must:

- verify canonical PC/WSL repo state
- inspect existing Legal v0 work
- map existing code/tests to these contracts
- choose the next smallest safe implementation slice
- include exact proof commands
- include rollback/checkpoint expectations
- avoid broad multi-feature implementation in one pass
