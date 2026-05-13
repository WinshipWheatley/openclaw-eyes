# OpenClaw Module Atlas v0

## 1. Source Basis And Commit References

This is the first docs-only module atlas for OpenClaw. It is based on the committed sanitized concept map and the controlling whitelist proposal.

Source basis:

- `docs/operations/OPENCLAW_SECOND_PASS_SANITIZED_CONCEPT_MAP_V0.md`
  - commit: `53442e9f3ec6cefcd6e43182167e03fa26f6e5ce`
  - short: `53442e9 docs(ops): checkpoint sanitized concept map`
- `docs/operations/OPENCLAW_SYSTEM_MARKDOWN_WHITELIST_PROPOSAL_V0.md`
  - commit: `768a5f5cdf8a62733f2b7d979c181388918e1c67`
  - short: `768a5f5 docs(ops): propose system markdown whitelist`

This atlas does not reopen broad source sets. It does not read no-go categories, import legacy files, create runtime code, ingest SQLite, wire agents, or claim live system state.

## 2. Purpose And Non-Authority Boundary

The purpose of this atlas is to name candidate OpenClaw module families and define their proposed responsibilities, allowed inputs, forbidden inputs, outputs, gates, and relationships.

This atlas is architecture documentation only. It is not:

- runtime authority
- customer deployment authority
- proof that any module is active
- proof that any live service is healthy
- permission to read sensitive data
- permission to connect external brokers
- permission to start agents, listeners, schedulers, senders, runners, or provider fallbacks
- permission to mutate SQLite or any runtime ledger

Every module family and module listed here is proposed or candidate unless explicitly marked as supported by current committed repo docs. Current-doc support means the concept is documented, not that it is active.

## 3. Atlas Taxonomy

| Level | Meaning | Authority |
| --- | --- | --- |
| Module family | A broad category of related OpenClaw capabilities. | Candidate map only. |
| Module | A named proposed unit of responsibility inside a family. | Candidate unless later proven by manifest, tests, receipts, and approval. |
| Gate | A required review, approval, sensitivity, evidence, or validation condition. | Documentation requirement only in this atlas. |
| Output/artifact | A document, manifest, receipt, read model, packet, or validation result a module may produce. | Not authority unless later bound by an approved contract. |
| Operator surface | A read-only or proposal-oriented surface for the Operator. | Must not become a hidden execution engine. |

## 4. Candidate Module Families

| Family | Current status | Proposed role |
| --- | --- | --- |
| `core/trust` | Current-doc-supported candidate | Owns truth, evidence, receipts, source status, approval posture, and read-model contracts. |
| `operator_surfaces` | Current-doc-supported candidate | Presents query, status, atlas, launch ladder, and review surfaces without hidden execution authority. |
| `adapters/brokers` | Candidate | Encapsulates external systems and provider access behind denied-by-default policy. |
| `runtime_agents` | Candidate, high-risk | Names actor roles and loops that must remain disabled until separately approved. |
| `domain_modules` | Candidate | Holds bounded product/domain modules such as Legal and Producer/Niles-style work. |
| `deployment_profiles` | Candidate | Defines per-deployment boundaries, enabled modules, data policy, and approval maps. |
| `approval_gate` | Strong shared candidate | Normalizes action-specific approval, denial, timeout, receipts, and escalation policy. |
| `capability_registry` | Shared contract candidate | Records capabilities, denied actions, connected state, and portability conditions. |
| `sensitivity_privacy_boundary` | Strong shared candidate | Defines PII, private data, sanitizer, export, and model-routing limits. |
| `source_set_ingest` | Candidate support module | Curates allowed source sets and withholds excluded material. |
| `module_manifest` | Next implementation candidate, inert only | Provides synthetic-example validation of module declarations. |
| `legal_product_core` | Bounded domain candidate | Separates reusable legal core from firm, matter, and customer-specific layers. |
| `service_control_kernel` | Candidate | Maps service inventory and dry-run controls before any live verification. |
| `advisory_consultant` | Candidate, advisory-only | Produces advisory packets and review notes without canonical authority. |

## 5. Candidate Module Details

### `core/trust`

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `truth_gateway` | Source-bound truth evaluation and assertion control. | Current committed docs, approved source registries, explicit evidence packets, synthetic tests. | Private data, logs/runtime memory, secrets, broad vaults, stale prior art treated as canonical. | Truth packets, source status, withheld-surface notes, evidence summaries. | Evidence gate, freshness gate, sensitivity gate. |
| `source_registry` | Records source identity, source class, freshness, and exclusion posture. | Whitelisted docs, committed repo references, explicit source declarations. | No-go paths, ambiguous paths, AppData, active-case files, runtime memory. | Source tables, freshness labels, exclusion lists. | Whitelist gate, stale/duplicate gate. |
| `decision_receipts` | Captures why a decision was made and what evidence supported it. | Approved truth packets, approval records, deterministic validation results. | Unapproved private material, unaudited model output as sole proof. | Decision receipts, denial receipts, withheld receipts. | Receipt gate, evidence gate. |
| `read_models` | Presents derived status without creating authority. | Receipts, source summaries, validation outputs. | Live system claims without verification, private bodies, credential material. | Status docs, operator-readable summaries, atlas views. | Read-model boundary gate. |

### `operator_surfaces`

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `operator_truth_query` | Lets the Operator inspect evidence-backed truth posture. | Truth gateway outputs, source registry entries, receipts. | Direct private mailbox/body reads, unapproved live integrations, runtime memory. | Query responses, cited summaries, withheld notices. | Evidence gate, sensitivity gate. |
| `module_atlas_view` | Presents module families, status, gates, and NOT_READY boundaries. | This atlas, later reviewed module manifests, committed docs. | Runtime control state unless separately verified, customer private data. | Atlas pages, module status summaries. | Non-authority gate. |
| `launch_ladder_view` | Surfaces deployment/productization planning status. | Current planning docs, approved profile docs, receipts. | Customer live data, inferred readiness claims. | Launch ladder summaries, next-lane recommendations. | Deployment profile gate. |

### `adapters/brokers`

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `filesystem_broker` | Mediates file access through explicit allow/deny boundaries. | Approved repo paths, whitelisted docs, synthetic examples. | Secrets, credentials, active legal case files, private financial records, logs/runtime memory, broad machine scans. | Access decisions, denied-path receipts, source-set manifests. | Whitelist gate, sensitivity gate. |
| `google_broker` | Candidate wrapper for Google/Gmail/Calendar access. | Future approved connector contracts, explicit Operator approval, redacted metadata where allowed. | Credential files, mailbox bodies without approval, private calendar details, client data. | Broker packets, redacted summaries, approval receipts. | Broker gate, approval gate, sensitivity gate. |
| `model_broker` | Routes model/provider use according to capability and privacy policy. | Approved prompts, redacted packets, non-sensitive synthetic examples. | Sensitive data without sanitizer/export approval, hidden fallback behavior, credential material. | Provider decision receipts, denial notes, routing summaries. | Model routing gate, privacy gate. |
| `integration_broker` | General boundary for future external integrations. | Approved connector specs, capability declarations, test packets. | Direct credentials, unapproved external mutations, customer data by default. | Capability packets, audit receipts, dry-run outputs. | Broker gate, approval gate. |

### `runtime_agents`

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `chief_actor` | Candidate coordinator role for bounded local work. | Future manifests, approved task packets, receipts. | Autonomous scope expansion, destructive actions without approval, private data by default. | Task plans, execution receipts, denial/escalation records. | Approval gate, runtime activation gate. |
| `cassandra_actor` | Candidate reasoning/research actor role. | Approved research packets, source-bound questions, synthetic examples. | Sensitive material without privacy routing, live claims without evidence. | Advisory analyses, research packets, uncertainty notes. | Evidence gate, sensitivity gate. |
| `guardian_actor` | Candidate human-in-the-loop approval guard. | Approval requests, action descriptions, evidence packets. | Blanket grants, hidden approvals, credential access. | Approval/denial/timeout receipts. | Approval gate. |
| `hermes_actor` | Candidate sidecar/advisory packet role. | Advisory packets, bounded tool outputs, non-sensitive summaries. | Canonical state mutation, unapproved broker access. | Advisory packets, proposal notes, withheld-surface flags. | Advisory-only gate. |
| `niles_actor` | Candidate producer/domain actor role, not live. | Future bounded Producer/Niles profile docs and approved project packets. | Private creative/business folders, customer data, autonomous sending or publishing. | Draft packets, project summaries, proposal-only plans. | Domain gate, approval gate, privacy gate. |

All runtime agent modules are NOT_READY for activation.

### `domain_modules`

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `legal_domain` | Bounded candidate legal product/domain layer. | Current repo legal product/core boundary docs, synthetic examples, approved support packet designs. | Active legal case files, client private records, matter vault contents, legal advice outputs as authoritative. | Legal module contracts, reusable-core boundaries, support packet templates. | Legal domain gate, privacy gate, customer deployment gate. |
| `producer_niles_domain` | Bounded candidate creative/producer domain layer. | Future approved Producer/Niles planning docs, synthetic project examples. | Private creative/business folders unless manually approved, customer communications, autonomous publishing. | Project packet schemas, draft-review flows, proposal notes. | Domain approval gate, privacy gate. |
| `company_assistant_domain` | Candidate deployment for company operations. | Future company profile docs, synthetic examples, approved source sets. | Private business records by default, finance/tax/CPA records, customer data. | Profile plans, source-set manifests, approval maps. | Deployment profile gate, privacy gate. |
| `health_admin_domain` | Candidate hospital/health admin style deployment. | Future profile docs, synthetic examples, non-sensitive policy designs. | PHI or live patient data, credentials, private health records. | Profile plan, sensitivity map, denied-data policy. | High-sensitivity gate, customer deployment gate. |

### Shared Support Modules

| Module | Proposed responsibility | Allowed inputs | Forbidden inputs | Outputs/artifacts | Gates |
| --- | --- | --- | --- | --- | --- |
| `deployment_profiles` | Defines deployment-specific module selection, owner, data boundary, approvals, and rollback. | Current productization docs, future profile docs, synthetic profile examples. | Live customer data, inferred readiness claims, secrets. | Deployment profile docs, module enablement maps, rollback plans. | Deployment gate, approval gate. |
| `approval_gate` | Normalizes action-specific approvals. | Action descriptions, evidence packets, risk classifications. | Blanket authorization, vague requests, credential-bearing hidden actions. | Approval, denial, timeout, and escalation receipts. | Human approval gate. |
| `capability_registry` | Records actor/module capabilities and denied actions. | Module manifests, current docs, synthetic test results. | Claimed live state without verification, hidden external capabilities. | Capability tables, denied-action maps, portability notes. | Capability proof gate. |
| `sensitivity_privacy_boundary` | Defines data sensitivity, routing, withholding, and sanitizer requirements. | Category definitions, approved policy docs, synthetic examples. | Sensitive contents, secrets, private bodies, active-case material. | Sensitivity maps, sanitizer requirements, withheld-surface policy. | Privacy gate. |
| `source_set_ingest` | Curates explicitly allowed source sets. | Whitelist proposals, reviewed source lists, committed docs. | Whole-vault ingest, whole-machine ingest, logs/runtime memory, ambiguous paths. | Source-set manifests, denied-source notes, freshness labels. | Whitelist gate. |
| `module_manifest` | Declares module purpose, authority, data, dependencies, tests, receipts, and disable path. | Synthetic examples, committed atlas docs, future reviewed manifests. | Runtime activation, live connectors, legacy imports. | Inert validation results, manifest schema docs, fixture examples. | Inert-only implementation gate. |
| `service_control_kernel` | Models service inventory and dry-run control surfaces before live verification. | Static inventories, current planning docs, synthetic service examples. | Live service mutation, process control without approval, unverified health claims. | Static inventory docs, dry-run command plans, forbidden-control tables. | Service control gate, approval gate. |
| `advisory_consultant` | Produces advisory review packets without canonical authority. | Bounded packets, non-sensitive evidence summaries, approved docs. | Direct state mutation, private source bodies, hidden authority. | Advisory packets, review comments, proposal-only recommendations. | Advisory-only gate. |

## 6. Relationship To Operator Surfaces

Operator surfaces should help the Operator see evidence, posture, uncertainty, and next safe docs-only steps. They must not become hidden controllers.

Allowed Operator-surface behavior:

- show module family status
- show source basis and commit references
- show candidate responsibilities and gates
- show why a module is NOT_READY
- show missing manifest, test, receipt, approval, or sensitivity work
- route the Operator toward explicit future approval lanes

Forbidden Operator-surface behavior:

- starting agents, listeners, schedulers, senders, runners, or brokers
- claiming live health without a separate verification lane
- mutating SQLite or generated status
- treating an advisory packet as canonical truth
- exposing private or sensitive data bodies
- using atlas status as deployment approval

## 7. Relationship To Adapters And Brokers

Adapters and brokers are candidate boundary modules. Their purpose is to prevent direct credential use and direct external mutation by domain modules, agents, or Operator surfaces.

Broker principles:

- denied by default
- capability declared before use
- approval required for consequential access or mutation
- redaction and withheld surfaces for sensitive material
- receipts for approval, denial, and output
- no module gets direct credential ownership
- no live connector is enabled by this atlas

The atlas may describe broker responsibilities, but broker connection requires a separate docs-and-tests lane followed by explicit approval before any live use.

## 8. Relationship To Domain Modules

Domain modules are product or workflow modules built on top of the trust plane, approval gates, sensitivity boundaries, and brokers.

Legal is a bounded candidate domain only. The legal module may define reusable legal product architecture, support packet shapes, and firm/matter separation. It must not read active case files, client records, matter vaults, private legal material, or produce authoritative legal advice from this atlas.

Producer/Niles is a bounded candidate domain only. It may later describe project packet flows, creative production support, and proposal-only reviews. It must not read private creative/business folders, publish content, contact people, or act autonomously from this atlas.

Other candidate domains, such as company assistant and health admin, require separate deployment profiles, synthetic examples, sensitivity maps, and approval gates before any customer or sensitive-data posture can be considered.

## 9. Approval And Sensitivity Gates

Required gates before any module can move beyond documentation:

- `manifest_gate`: stable module id, purpose, authority, permissions, data sensitivity, storage boundary, runtime dependencies, client config, activation tests, receipts, forbidden actions, and disable path.
- `evidence_gate`: every consequential assertion must have source-bound evidence and freshness posture.
- `approval_gate`: consequential actions require explicit, action-specific approval and receipts.
- `broker_gate`: external integrations require denied-by-default capability tables, audit rules, and no direct credential ownership.
- `privacy_gate`: sensitive data requires local-first handling, sanitizer/export design, approval, and logging before external model or provider use.
- `read_model_gate`: read models must say what they prove and what they do not prove.
- `deployment_profile_gate`: each deployment must define owner, access mode, forbidden paths, private data policy, source sets, enabled modules, approval map, and rollback/decommission path.
- `runtime_activation_gate`: runtime activation requires a separate lane with tests, receipts, explicit approval, and rollback.

## 10. Explicit NOT_READY Boundaries

This atlas is READY for docs-only architectural review.

This atlas is NOT_READY for:

- runtime activation
- customer deployment
- autonomous action
- sensitive-data processing
- active legal work
- live Gmail, Google, Calendar, filesystem, model-provider, or external broker access
- agent wiring
- listener, scheduler, sender, watcher, runner, or fallback activation
- SQLite ingestion or mutation
- generated-status mutation
- legacy runtime import
- production claims

No module listed here should be treated as deployable until a future reviewed manifest, synthetic tests, evidence receipts, approval gates, privacy boundaries, and rollback path exist.

## 11. Recommended Next Docs-Only Slice

The next docs-only slice should be:

`docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md`

Scope:

- define an inert module manifest schema
- use synthetic examples only
- include required fields for authority, sensitivity, inputs, outputs, brokers, receipts, tests, forbidden actions, and disable path
- include examples for `core/trust`, `operator_surfaces`, `adapters/brokers`, `domain_modules`, and `runtime_agents`
- include validation expectations without runtime code

Still out of scope for the next docs-only slice:

- live validators
- runtime registries
- SQLite writes
- broker connections
- agent wiring
- private data reads
- customer deployment
