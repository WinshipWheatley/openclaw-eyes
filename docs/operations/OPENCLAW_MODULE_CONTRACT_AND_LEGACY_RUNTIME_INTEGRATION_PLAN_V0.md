# OpenClaw Module Contract and Legacy Runtime Integration Plan v0

## 1. Executive Summary

`/home/openclaw` and `WinshipWheatley/openclaw-eyes` are the current canonical OpenClaw control-plane trunk.

`WinshipWheatley/openclaw-runtime` is read-only legacy/source material unless it is separately reactivated by a gated migration decision. It is useful for mined concepts, but it is not the canonical runtime for this lane and must not be treated as a direct import source.

This is a docs-only planning lane. No runtime code is copied, wired, or activated. No remotes are changed. No repository moves are authorized. No private runtime data, secrets, tokens, or user-specific content are ingested.

The purpose of this plan is to define how legacy runtime ideas can plug into the current hardened control plane without contaminating trust, evidence, approval, tenant, or runtime boundaries.

## 2. Evidence Basis

- The local canonical working tree is `/home/openclaw`.
- The current remote is `git@github.com:WinshipWheatley/openclaw-eyes.git`.
- `/home/openclaw` contains the current truth gateway, SQLite ledger, decision receipts, operator truth query wrapper, source/evidence rules, operations checkpoints, tests, and boundary audits.
- `openclaw-runtime` was inspected as older private runtime material. It contains older Chief/Cassandra runtime stack, Telegram listeners, routing, approval policy, Google broker, PII vault, memory/state workers, scheduler/watchers, start scripts, polish-loop/autonomous build material, and personal/business assistant modules.
- The runtime audit classified `openclaw-runtime` as `MINE_FOR_IDEAS`, not a direct migration source.

## 3. Core Trust Plane

The current OpenClaw trust/control plane is made of:

- truth gateway
- ledger
- decision receipts
- evidence/source registry
- approval/sensitivity contracts
- operator truth query surface
- status/read-model visibility
- tests and boundary audits

Modules must plug into this plane rather than bypass it. A module may propose, read, route, or execute only according to the authority granted by the trust plane. A module must not create a parallel source of truth, a shadow approval system, a hidden memory store, or an unreceipted runtime path.

Truth posture, approval posture, runtime health, and execution authority remain separate. A status surface or receipt may make behavior visible, but visibility does not authorize execution. A module that needs to write, send, schedule, listen, broker, or call an external integration must have a manifest, tests, receipts, and an explicit gate before activation.

## 4. Module Runtime Contract

Every module must have a manifest before activation. The required fields are:

| Field | Required meaning |
| --- | --- |
| `module_id` | Stable identifier that does not leak private customer, matter, patient, client, or secret details. |
| `purpose` | Bounded purpose in plain language. |
| `authority_level` | One of the declared authority classes, such as read-only, proposal-only, approval-gated, broker-gated action, bounded executor, or forbidden. |
| `required_permissions` | Exact filesystem, network, broker, credential, model, process, data, or integration permissions needed. |
| `data_sensitivity` | Data classes the module may see, plus data classes it must never see. |
| `storage_boundaries` | Canonical storage locations, tenant/client boundaries, and forbidden storage locations. |
| `runtime_dependencies` | Required scripts, services, brokers, models, queues, credentials, or external systems. |
| `client_config_schema` | Configuration fields that vary by deployment, client, company, firm, hospital, or operator. |
| `activation_tests` | Tests or dry-run proofs required before activation. |
| `required_receipts` | Audit, decision, approval, execution, or visibility receipts the module must emit or consume. |
| `forbidden_actions` | Actions the module is not allowed to perform even if adjacent code exists. |
| `rollback_or_disable_path` | How the module is disabled, reverted, or quarantined without corrupting canonical state. |

No module should activate without a manifest, tests, receipts, and an explicit gate. Installed code, existing scripts, credentials on disk, or legacy runtime behavior do not imply module authority.

## 5. Module Taxonomy

### `core/trust`

Core trust modules define evidence, truth posture, receipts, approvals, sensitivity rules, and canonical state. They may describe or validate authority, but they must not silently execute runtime actions.

Examples: truth gateway, ledger, receipt contracts, source registry, approval policy, sensitivity taxonomy, status/read-model contracts.

### `adapters/brokers`

Adapters and brokers connect OpenClaw to external systems or local resources through explicit policy. They must be denied-by-default, auditable, and capability-scoped.

Examples: Google/Gmail/Calendar broker, filesystem adapters, model routers, future integration brokers. They must not grant broad API access or direct sends merely because credentials exist.

### `operator_surfaces`

Operator surfaces present state, queries, summaries, decisions, and proposed next actions to the human operator. They may be read-only or proposal-only unless separately gated.

Examples: operator truth query wrapper, generated status, dashboards, orientation snapshots. They must not imply live runtime health or execution authority unless proven by a separate receipt path.

### `domain_modules`

Domain modules encode workflow-specific logic for a company, legal matter, hospital admin process, music/business operation, website workflow, billing process, or similar domain.

They must use customer/deployment-specific configuration, not personal Winship assumptions. They must not mix tenant data or promote private workflows into reusable product code without sanitization and tests.

### `runtime_agents`

Runtime agents are active personas, workers, listeners, schedulers, or routing surfaces. They are the highest-risk category and must remain disabled by default until the trust plane grants a bounded role.

Examples: Chief, Cassandra, Guardian, Hermes, Niles, listener processes, scheduler loops, runner loops. Names and personas do not create authority.

### `deployment_profiles`

Deployment profiles select modules, data boundaries, approvals, storage, and integration rules for a specific operator, company, firm, hospital, or business use case.

A profile is configuration and policy. It is not a brain dump, a private data export, or a shortcut around module manifests.

## 6. Deployment Profiles

### Personal Winship Deployment

Likely modules: core trust plane, operator truth query, selected Chief/Cassandra assistant surfaces, Guardian approval patterns, Google broker patterns, music/business ops modules, dashboard/status surfaces.

Sensitivity concerns: personal records, Gmail content, calendar context, business data, credentials, private logs, financial information, music/business strategy, and local runtime state.

Activation restrictions: brokered integrations only, approval before sends or external effects, local-first handling for sensitive content, no autonomous runners until disabled-by-default safety is proven.

### Brother's Company

Likely modules: company assistant profile, task/status reporting, calendar/email broker patterns, internal advisory surfaces, lightweight domain modules.

Sensitivity concerns: company records, client/customer data, employee or vendor information, operational plans, private communications, credentials, and business-specific workflows.

Activation restrictions: no personal Winship modules, no copied private config, explicit tenant/company storage boundary, company-specific source registry, approval rules, and synthetic tests before activation.

### Law Firm

Likely modules: local-first legal discovery, matter isolation, evidence registry, support/export packet sanitizer, attorney review/approval gates, read-only dashboards.

Sensitivity concerns: privileged matter data, client identities, litigation strategy, discovery material, chain of custody, confidentiality duties, and professional responsibility constraints.

Activation restrictions: no cloud or external model fallback for real matter content by default, no broad MCP roots, no Cassandra Gmail behavior by default, no matter data in repo, and no live integration without attorney-approved policy.

### Hospital/Health Admin

Likely modules: health-admin intake, appointment/admin workflow support, authorization or claim packet review, evidence registry, strict approval and audit surfaces.

Sensitivity concerns: PHI, patient identifiers, clinical-adjacent admin data, insurance details, appointment records, authorization records, and regulated retention requirements.

Activation restrictions: no PHI ingestion until privacy/security contracts are defined, no live EHR/portal integration, no external model use on protected content by default, no autonomous actions, and no deployment without a client-specific compliance review.

### Music/Business Ops

Likely modules: Producer/Niles concepts, music project intake, website workflow, outreach drafting, calendar/outreach broker, billing/reconciliation support, business status surfaces.

Sensitivity concerns: unreleased creative work, contracts, publishing information, client/partner details, financial records, emails, and strategy documents.

Activation restrictions: draft-only outreach until approval, no autonomous sends, no payment/bank actions, no inbox roaming, no external sharing of protected creative/business content without sanitizer and approval.

## 7. Legacy Runtime Extraction Rules

- Port concepts before code.
- No direct imports without a module manifest.
- Remove hardcoded paths and environment assumptions, including `/home/openclaw`, `/mnt/c/OpenClaw`, and `.chief.env` dependencies, before any reusable module lane.
- No live listeners, senders, schedulers, watchers, or runner loops before an explicit approval gate.
- No secrets, tokens, private logs, vault contents, personal messages, or private runtime content may be migrated.
- Tests and receipts are required before activation.
- Brokered integration patterns are required for Google, Gmail, Calendar, and similar external systems.
- A PII/sensitive-data boundary is required before any client, company, law firm, hospital, or other third-party deployment.
- No autonomous runners until a disabled-by-default safety model is proven with synthetic fixtures, receipts, bounded authority, and rollback.
- Existing runtime files are evidence for ideas, not authority to execute.

## 8. Candidate Runtime Material Inventory

| Material | Initial label | Reason |
| --- | --- | --- |
| Chief/Cassandra routing and assistant patterns | port as concept | Useful for intake, response routing, and operator support, but too coupled to personal runtime paths and live services for direct import. |
| Guardian approval concepts | port as docs/contract | Approval gate and receipt patterns are reusable, but approval authority must remain centralized and explicit. |
| Hermes advisory-only pattern | port as docs/contract | Packet-in/proposal-out consulting is useful if kept non-authorizing. |
| Niles/Producer concepts | future module candidate | Useful domain module for music/creative workflows; must remain suggested-only until tool execution is separately gated. |
| Google broker/integration patterns | port as docs/contract | Denied-by-default broker design is reusable; credentials and live API paths must not be copied. |
| PII vault/sensitive storage pattern | port as concept | Sensitive storage boundary is valuable, but hardcoded paths/env and key handling must be redesigned before reuse. |
| Capability registry/approval policy | port as docs/contract | Useful shared vocabulary for authority, capability, and denied-by-default behavior. |
| Polish-loop/runner ideas | quarantine / do not reuse yet | Autonomous build loops and runner orchestration are too risky until disabled-by-default safety is proven. |
| Input adapter pattern from Whisper relay | future module candidate | Confidence-gated input routing is useful, but transcript/log privacy and activation gates must be defined first. |
| Music domain modules | future module candidate | Useful for Winship and possible creative/business deployments after tenant config and private content boundaries exist. |
| Business ops modules | future module candidate | Useful if anchored to the current ledger, receipts, approval policy, and tenant-specific configuration. |
| Legal modules | future module candidate | Strong local-first product candidate, but real matter data must remain outside repo and external models by default. |
| Website modules | future module candidate | Potentially reusable if separated from personal brand/config and backed by approval-gated publish paths. |
| Calendar/outreach modules | keep separate | Useful but externally consequential; no live sends, notifications, or schedule mutation without broker and approval gates. |

## 9. Repo Strategy

Recommended strategy: hybrid staged model.

- Keep the current repo as the monorepo/control plane for now.
- Keep `openclaw-runtime` separate and read-only.
- Do not split repos yet.
- Split later into core plus module repositories only after module manifests exist and at least two deployments prove clean boundaries.

Rejected for now:

- merging repos now
- splitting repos now
- treating `openclaw-runtime` as canonical
- copying runtime code directly
- productizing personal modules before tenant boundaries exist

The current repo should remain the place where trust-plane contracts, module manifests, synthetic examples, tests, and reusable docs are stabilized. Legacy runtime code should remain a reference source until a specific module migration passes the gates in this plan.

## 10. Packaging / Sellable Module Direction

This plan supports future reuse by separating product modules from personal runtime assumptions.

Modules can be selected per deployment. A client, company, hospital, law firm, or business deployment should receive profile configuration and approved module selections, not a copy of Winship's personal assistant stack.

Sensitive data must stay tenant-scoped. Reusable module code must be separated from private/user-specific config, source paths, credentials, operator identity, contact lists, personal logs, and deployment-specific storage.

Receipts and activation tests become part of the product contract. A module is not sellable merely because it works locally; it becomes reusable only when its purpose, permissions, sensitivity, storage, dependencies, client configuration, activation tests, receipts, forbidden actions, and disable path are explicit.

## 11. Migration Gates

Before importing any runtime code, the migration lane must satisfy all of these gates:

- static diff review against current equivalent files
- module manifest created
- hardcoded personal paths removed
- environment and secret access brokered
- tenant/client storage boundary defined
- sensitivity taxonomy assigned
- no side effects before activation
- receipts/audit path defined
- tests proving no secret, token, private content, or protected tenant data is read, logged, exported, or sent
- explicit operator approval before any live listener, scheduler, broker, sender, or external integration

If any gate is missing, the legacy material remains read-only source material.

## 12. Recommended Next Lane

The next safest implementation lane is an inert `module_manifest` validator using synthetic examples only.

That lane should not activate runtime code, import legacy files, wire agents, connect brokers, read secrets, touch client data, or start listeners/senders/schedulers. It should prove only that module manifests can be declared, validated, tested, and reviewed without side effects.

## 13. Do-Not-Do List

- Do not merge repos.
- Do not import runtime code yet.
- Do not activate Chief, Cassandra, or polish-loop agents.
- Do not wire Telegram, Gmail, hospital, legal, or client data.
- Do not split repos yet.
- Do not productize personal modules until paths, secrets, tenant config, and approval gates are separated.
- Do not change origin/remotes.
- Do not move truth gateway or ledger commits.
- Do not treat receipts, status views, or installed scripts as runtime authority.
- Do not migrate secrets, tokens, private logs, vault data, personal messages, or sensitive runtime content.
