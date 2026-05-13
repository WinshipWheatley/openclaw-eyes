# OpenClaw Second-Pass Sanitized Concept Map v0

## 1. Source Basis

- **Controlling whitelist:** `docs/operations/OPENCLAW_SYSTEM_MARKDOWN_WHITELIST_PROPOSAL_V0.md`
- **Whitelist commit:** `768a5f5cdf8a62733f2b7d979c181388918e1c67`
- **Canonical trunk:** `/home/openclaw`
- **Remote identity:** `git@github.com:WinshipWheatley/openclaw-eyes.git`
- **Extraction type:** docs-only architecture extraction

This concept map uses only the approved second-pass source groups named in the whitelist proposal. External Markdown is prior art only. Nothing in this document activates runtime behavior, imports code, ingests data into SQLite, creates runtime memory, or claims live system state.

## 2. Extraction Boundary

### Allowed Sources Read

Current canonical repo:

- `docs/operations/OPENCLAW_SYSTEM_MARKDOWN_WHITELIST_PROPOSAL_V0.md`
- `docs/operations/OPENCLAW_MODULE_CONTRACT_AND_LEGACY_RUNTIME_INTEGRATION_PLAN_V0.md`
- `docs/operations/OPENCLAW_TRUTH_RECONCILIATION_GATEWAY_V1_CHECKPOINT.md`
- `docs/operations/OPENCLAW_TRUTH_PACKET_DECISION_RECEIPTS_CHECKPOINT_V0.md`
- `docs/operations/OPENCLAW_OPERATOR_TRUTH_QUERY_CHECKPOINT_V0.md`
- `docs/operations/OPENCLAW_AGENT_CAPABILITY_PATTERN_INVENTORY_V0.md`
- `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`
- `docs/operations/CHIEF_MACHINE_CONTRACT.md`
- `docs/operations/CASSANDRA_MACHINE_CONTRACT.md`
- `docs/operations/GUARDIAN_MACHINE_CONTRACT.md`
- `docs/operations/HERMES_MACHINE_CONTRACT.md`
- `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`
- `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`
- `docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md`
- `docs/planning/launch_ladder/operator_harness_research/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md`
- `docs/planning/launch_ladder/operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md`
- `docs/planning/openclaw_legal/law_program/LEGAL_PRODUCT_CORE_SEPARATION.md`

Legacy runtime prior art:

- `/tmp/openclaw-runtime-audit/polish_loop/tasks/hitl-*`
- `/tmp/openclaw-runtime-audit/polish_loop/tasks/pii-*`
- `/tmp/openclaw-runtime-audit/polish_loop/tasks/sys-*`

Obsidian System prior art:

- `/mnt/c/OpenClawShared/openclaw-vault/System/Overview.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Project Instructions.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Command Authority and Bounded Autonomy.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Capability Registry.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Capability Ladder.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Data Classification.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Privacy Routing Rules.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Autonomy Threshold Map.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Cloud Workload Candidates.md`

Old doctrine export prior art:

- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Architecture_and_Naming_Doctrine.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Doctrine_Alignment_Audit.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Cassandra_Contract.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Chief_Contract.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Guardian_Contract.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Permissions_Matrix.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Canonical_State_Classification.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Implementation_Map.md`

### Explicit Exclusions

No-go paths and categories from the whitelist were not opened. This includes secrets, tokens, credentials, `.env` files, private finance/business records, tax/CPA records, active legal case files, logs/runtime memory, AppData/user profile material, and private creative/business folders unless manually approved.

Excluded due to ambiguity or missing whitelist coverage:

- `/mnt/c/OpenClaw/OpenClaw_Watch_EXPORTS`
- `/mnt/c/OpenClaw/law_program` outside the current repo copy
- `/mnt/c/Users/Winship/OpenClaw_Watch`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Runtime_Action_Ledger.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Action1_Patch_Plan.md`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_Orchestrator_Runtime_Verification.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Chief Continuity.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Remote Access.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Ops*.md`
- `/mnt/c/OpenClawShared/openclaw-vault/Business`
- `/mnt/c/OpenClawShared/openclaw-vault/Billing`
- `/mnt/c/OpenClawShared/openclaw-vault/Calendar`
- `/mnt/c/OpenClawShared/business`
- `/mnt/c/OpenClawShared/album`
- `/mnt/c/OpenClaw/legal/cases/active-case`
- `/mnt/c/OpenClaw/logs`
- `/mnt/c/OpenClaw/memory`
- `/home/openclaw/docs/producer`, because it was not part of the approved current-repo whitelist group for this pass.

## 3. High-Level Architecture Concepts Found

### A. Trust Plane Before Runtime

The current architecture is organized around a trust/control plane before any runtime expansion. The core pieces are:

- truth gateway
- source/evidence registry
- SQLite ledger
- decision receipts
- approval and sensitivity contracts
- operator truth query wrapper
- status/read-model visibility
- tests and boundary audits

The repeated invariant is that modules must plug into the trust plane instead of bypassing it. Receipts and status surfaces make decisions visible, but do not create authority.

### B. Evidence Before Assertion

Across current docs and prior-art sources, OpenClaw consistently values:

- evidence before assertion
- source-bound facts
- explicit provenance
- deterministic validation
- stale/changed-source handling
- withheld surfaces when evidence is missing or sensitive

The truth gateway is the current strongest implementation of this concept. Older runtime/doctrine material expresses the same concept as evidence, authority maps, canonical state classification, and handoff discipline.

### C. Deterministic Rails Before Agentic Reasoning

The architecture favors deterministic parsing, validation, receipts, gates, manifests, and source registries before any model-assisted or agentic behavior. Agentic behavior is last-mile, bounded, and explainable, not the core source of truth.

Candidate atlas implication: every module should declare which parts are deterministic, which are proposal-only, and which require a later approval-gated execution lane.

### D. Authority Is Separate From Capability

The documents repeatedly separate what code can technically do from what OpenClaw allows it to do. Hermes sidecar tools, local models, Google credentials, live listeners, old runtime scripts, and Obsidian notes are not authority by presence.

Candidate atlas implication: each module needs both capability metadata and authority metadata. Authority must be default-deny and explicitly elevated by manifest, tests, receipts, and approval gates.

### E. Operator Surfaces Are Not Execution Engines

Operator query, dashboards, generated status, launch ladders, and future atlas views should show evidence, posture, and next safe actions. They should not become hidden controllers, live health claims, or runtime mutation surfaces.

Candidate atlas implication: the atlas should be a map and evidence browser first. It may later route to approved execution lanes, but should not launch or mutate in v0.

### F. Deployment Profiles Are First-Class Boundaries

The productization docs and multi-deployment control plane point to deployments as separate governed systems. Profiles should isolate personal, company, legal, hospital/health admin, creative/business, and advisory deployments.

Candidate atlas implication: deployments, modules, profiles, data boundaries, evidence roots, and access modes should be modeled explicitly before productization.

### G. Prior Art Is Useful But Stale Until Reconciled

Legacy runtime, Obsidian System notes, and old doctrine exports contain useful concepts: approval tiers, capability ladders, Chief/Cassandra role boundaries, Guardian approval gates, cloud/local routing, and old state-classification maps. They are not current canonical truth.

Candidate atlas implication: imported ideas need freshness labels and source status, not direct promotion.

## 4. Candidate Module Families

All entries below are candidates only.

| Candidate family | Source basis | Current posture | Atlas relevance |
| --- | --- | --- | --- |
| `core/trust` | Current repo | Canonical planning/control plane | Owns truth gateway, ledger, receipts, evidence, approvals, sensitivity policy, and status/read-model contracts. |
| `operator_surfaces` | Current repo | Canonical for current operator query and docs | Includes operator truth query, future dashboards, launch ladder views, and atlas surfaces; read-only/proposal-only by default. |
| `adapters/brokers` | Current repo plus prior art | Candidate module class | Encapsulates Google/Gmail/Calendar, filesystem, model, and future integration brokers behind denied-by-default policy. |
| `runtime_agents` | Current repo plus legacy/Obsidian prior art | Candidate, high-risk | Includes Chief, Cassandra, Guardian, Hermes, Niles-like roles, listeners, schedulers, and worker loops; disabled unless explicitly gated. |
| `domain_modules` | Current repo and productization docs | Candidate module class | Includes legal, creative/business, company assistant, hospital/health admin, music/project, website, calendar/outreach, and billing/reconciliation concepts. |
| `deployment_profiles` | Current repo | Candidate atlas primitive | Selects modules, boundaries, sensitivity rules, storage, approvals, runtime dependencies, and validation per deployment. |
| `approval_gate` | Current repo plus prior art | Strong shared candidate | Normalizes action-specific approvals, Guardian-style HITL, receipts, denial/timeout behavior, and no blanket grants. |
| `capability_registry` | Current repo plus Obsidian prior art | Shared contract candidate | Records actor/module capability, denied actions, connected/disconnected state, and portability conditions. |
| `sensitivity_privacy_boundary` | Current repo plus legacy/Obsidian prior art | Strong shared candidate | Handles PII, local-first handling, model routing constraints, sanitizer/export prerequisites, and tenant privacy boundaries. |
| `source_set_ingest` | Current repo | Candidate support module | Curates safe source sets, tracks freshness/staleness, withholds no-go paths, and prevents broad ingest. |
| `module_manifest` | Current module contract | Next implementation candidate | Inert validator should prove purpose, authority, permissions, sensitivity, storage, dependencies, activation tests, receipts, forbidden actions, and disable path. |
| `legal_product_core` | Current repo | Product module candidate | Separates reusable legal core, firm profiles, matter vaults, suite modules, support packets, and update boundaries. |
| `service_control_kernel` | Current planning docs | Product module candidate | Static inventory, owner table, forbidden controls, dry-run defaults, and separately approved live-state verification plan. |
| `advisory_consultant` | Hermes docs | Candidate, advisory-only | Packet-in/proposal-out review surface with non-canonical output and explicit withheld surfaces. |

## 5. Cross-Cutting Contracts and Gates

### Module Manifest Gate

No module should activate without:

- stable `module_id`
- purpose
- authority level
- required permissions
- data sensitivity
- storage boundaries
- runtime dependencies
- client config schema
- activation tests
- required receipts
- forbidden actions
- rollback/disable path

### Evidence and Source Gate

Any claim that affects model answers, runtime posture, operator status, deployments, or module readiness needs evidence. Evidence should be source-bound, freshness-aware, and inspectable.

### Approval Gate

Consequential actions require explicit approval. Approval must be action-specific, evidence-bound, and receipted. Prior-art approval concepts should be folded into the current Chief/Guardian-style gate only through a formal contract lane.

### Broker Gate

External integrations should use a broker pattern:

- denied by default
- actor/capability/class table
- approval and audit rules
- redaction/omission for sensitive bodies
- no direct credential use by modules

### Sensitivity and Privacy Gate

Protected content stays local/deterministic by default. External model or provider use requires future sanitizer/export design, explicit approval, and logging. Sensitive categories should be defined per deployment and per module.

### Receipt and Read-Model Gate

Receipts are audit evidence, not authorization. Read models and status surfaces must say what they prove and what they do not prove.

### Stale / Duplicate Gate

External prior art must be marked as stale, duplicate, or legacy until reconciled. Current committed `/home/openclaw` docs win when conflicts exist.

### Deployment Profile Gate

Each deployment should declare:

- authority owner
- access mode
- forbidden paths
- private data policy
- source sets
- evidence root
- enabled modules
- approval map
- rollback/decommission path

### Runtime Activation Gate

No listener, scheduler, sender, watcher, runner, provider fallback, Google/Gmail/Calendar integration, or agent loop should activate from this concept map. Activation requires a separate lane with tests, receipts, approval, and rollback.

## 6. Sensitive-Boundary Observations

No no-go sources were opened for this pass.

Sensitive material is present by category/path in the wider system, but this pass treated it as excluded. The concept map extracted only architectural patterns from approved files and headings/structured sections from approved prior-art notes.

Boundary observations:

- Private data must remain outside reusable module code and docs.
- Client/company/legal/health deployments require tenant-specific storage and sensitivity boundaries.
- Matter vaults, Gmail bodies, private business records, finance/tax/CPA material, secrets, logs, runtime memory, and AppData are not atlas source material.
- Old notes may mention sensitive data classes as categories; category names are useful for policy design, but contents are not to be read or summarized.
- Support packets, source sets, and external review packets require sanitizer and withheld-surface discipline.

## 7. Unknowns and Exclusions

Unknowns:

- Whether all Obsidian System notes remain accurate; they are prior art and may conflict with current repo doctrine.
- Whether old doctrine export files are fully superseded by current repo docs; treat them as stale until reconciled.
- Whether legacy runtime HITL/PII/sys task notes map cleanly to current code; they should inform contracts before any import.
- Whether current repo docs outside the whitelist contain additional useful concepts; they were intentionally excluded for this pass.
- Whether deployment-specific module defaults differ for brother's company, law firm, hospital/health admin, and music/business ops; those need profile design, not inference from personal material.

Excluded due to ambiguity:

- mirror/stale exports not explicitly whitelisted
- user profile/OpenClaw Watch material
- old runtime files outside `hitl-*`, `pii-*`, and `sys-*`
- Obsidian non-System folders and System logs/continuity/remote-access notes
- old doctrine export files outside the allowed name patterns
- current repo docs outside `docs/operations`, `docs/planning`, and `Operator`

## 8. Module Atlas Readiness Judgment

**READY for a docs-only `docs/module_atlas` master atlas v0.**

The whitelist and this concept map are sufficient to create a non-executing atlas that records:

- module families
- candidate modules
- source category
- authority posture
- data sensitivity posture
- activation status
- required receipts/tests
- stale/legacy flags
- next safe lane

**NOT_READY for runtime activation, code import, live integrations, agent wiring, autonomous runners, or customer deployment.**

The next atlas lane must remain docs-only and must not create live module registries, start services, read private data, or import legacy runtime code.

## 9. Recommended Next Lane

Create `docs/module_atlas` master atlas v0 as a docs-only artifact.

Minimum atlas contents:

- module taxonomy
- module family table
- candidate module table
- source status: canonical, current planning, legacy prior art, stale export, excluded
- authority status
- sensitivity status
- proof/test status
- receipts required
- activation gate
- do-not-build-yet notes

After the atlas is reviewed, the next implementation lane can be an inert `module_manifest` validator using synthetic examples only.

## 10. Do-Not-Do

- Do not create runtime memory.
- Do not ingest into SQLite.
- Do not read no-go paths.
- Do not copy prior-art notes into the repo.
- Do not quote private or sensitive content.
- Do not create `docs/module_atlas` in this lane.
- Do not wire Chief, Cassandra, Guardian, Hermes, Niles, listeners, schedulers, senders, brokers, or runners.
- Do not import code from `openclaw-runtime`.
- Do not claim live system state from old docs.
- Do not treat Obsidian or old doctrine exports as canonical truth.
