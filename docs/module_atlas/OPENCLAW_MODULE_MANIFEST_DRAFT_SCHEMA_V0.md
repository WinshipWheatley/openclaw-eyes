# OpenClaw Module Manifest Draft Schema v0

## 1. Source Basis

This draft schema is based only on:

- `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md`
- `docs/operations/OPENCLAW_SECOND_PASS_SANITIZED_CONCEPT_MAP_V0.md`
- `docs/operations/OPENCLAW_SYSTEM_MARKDOWN_WHITELIST_PROPOSAL_V0.md`

It follows the atlas recommendation to define an inert module manifest schema using synthetic examples only.

This document is docs-only architecture design. It does not create a validator, runtime registry, SQLite entry, broker connection, agent wire-up, deployment profile, or live module.

## 2. Authority Boundary

Module manifests are inert until separately approved, tested, receipted, and committed through a future implementation lane.

A manifest may describe proposed authority, inputs, outputs, gates, dependencies, tests, receipts, and rollback posture. It does not grant that authority. It does not prove runtime readiness. It does not permit private data reads, customer deployment, external access, or autonomous action.

No module becomes active from this schema.

## 3. Draft Manifest Shape

Future manifests should be structured documents with explicit field names. YAML is used below for readability, but this schema does not choose a runtime serialization format.

Required top-level fields:

| Field | Required | Expected value | Purpose |
| --- | --- | --- | --- |
| `module_id` | yes | Stable string id. | Names one proposed module. |
| `module_family` | yes | One atlas module family. | Places the module in the atlas taxonomy. |
| `purpose` | yes | Short text. | States the proposed responsibility without claiming activation. |
| `authority_level` | yes | Explicit authority label. | Declares what the module is allowed to do, if anything. |
| `allowed_inputs` | yes | List of input classes or paths. | Defines what the module may consume after approval. |
| `forbidden_inputs` | yes | List of excluded input classes or paths. | Defines material the module must not consume. |
| `outputs_artifacts` | yes | List of document, packet, receipt, or validation outputs. | Defines proposed outputs without treating them as authority. |
| `approval_gates` | yes | List of required approval gates. | Defines human or policy approvals required before use. |
| `sensitivity_gates` | yes | List of privacy and data-sensitivity gates. | Defines withholding, sanitizer, local-only, and export controls. |
| `dependencies` | yes | List of docs, manifests, brokers, tests, or services. | Declares dependencies without activating them. |
| `tests_required` | yes | List of required tests or proof checks. | Defines future validation requirements. |
| `receipts_required` | yes | List of receipt types. | Defines future audit evidence. |
| `disable_path` | yes | Short procedure or reference. | Explains how the module is disabled. |
| `rollback_path` | yes | Short procedure or reference. | Explains how to roll back module changes. |
| `NOT_READY_boundaries` | yes | List of explicit blocked uses. | Prevents manifest text from being treated as runtime authority. |

## 4. Field Semantics

### `module_id`

Stable identifier for one proposed module. It should be lowercase, descriptive, and scoped by family when useful.

Examples:

- `core_trust.truth_gateway`
- `operator_surfaces.module_atlas_view`
- `adapters_brokers.google_broker`

### `module_family`

One of the candidate families named in the atlas:

- `core/trust`
- `operator_surfaces`
- `adapters/brokers`
- `runtime_agents`
- `domain_modules`
- `deployment_profiles`
- `approval_gate`
- `capability_registry`
- `sensitivity_privacy_boundary`
- `source_set_ingest`
- `module_manifest`
- `legal_product_core`
- `service_control_kernel`
- `advisory_consultant`

### `purpose`

A concise responsibility statement. It must avoid live-state claims.

Good shape:

- "Defines a proposed read-only atlas view for reviewed module manifests."

Bad shape:

- "Runs the module atlas service."
- "Confirms all modules are healthy."

### `authority_level`

Suggested labels:

| Label | Meaning |
| --- | --- |
| `docs_only` | Descriptive documentation only. |
| `proposal_only` | May produce proposals but no canonical state or external action. |
| `read_only_after_approval` | May read approved sources only after explicit approval and tests. |
| `dry_run_after_approval` | May produce dry-run plans only after explicit approval and tests. |
| `runtime_blocked` | Must not run until a separate runtime activation lane is approved. |

No manifest should default to write, send, mutate, deploy, or autonomous authority.

### `allowed_inputs`

Allowed inputs must be narrow and explicit. They may include committed repo docs, reviewed manifests, synthetic fixtures, approved source-set manifests, or approved evidence packets.

Allowed inputs must not imply broad repository, whole-machine, whole-vault, mailbox, calendar, credential, log, runtime memory, active legal case, customer, private finance, or private business access.

### `forbidden_inputs`

Forbidden inputs should restate all relevant no-go categories for the module. If a path or category is ambiguous, the manifest should forbid it until a later manual approval lane names it explicitly.

Baseline forbidden inputs:

- secrets, tokens, keys, credentials, and `.env` files
- private financial, tax, CPA, client, or business records
- active legal case files and matter vault contents
- logs, runtime memory, generated live status, and AppData
- private creative/business folders unless manually approved
- broad source sets, whole-machine scans, and whole-vault ingestion

### `outputs_artifacts`

Outputs are proposed artifacts only. Examples:

- module contract docs
- read-model summaries
- evidence packets
- validation results
- approval, denial, timeout, or rollback receipts
- withheld-surface notes

Outputs must say whether they are advisory, proposal-only, evidence-backed, or canonical after future approval.

### `approval_gates`

Approval gates should be action-specific. They must not describe blanket grants.

Examples:

- `operator_explicit_approval_required`
- `guardian_denial_timeout_receipt_required`
- `broker_access_approval_required`
- `runtime_activation_approval_required`
- `customer_deployment_approval_required`

### `sensitivity_gates`

Sensitivity gates define privacy posture before data access or output.

Examples:

- `local_only_by_default`
- `no_sensitive_bodies`
- `withheld_surface_required`
- `sanitizer_required_before_export`
- `tenant_boundary_required`
- `external_model_use_blocked_until_approved`

### `dependencies`

Dependencies must distinguish documentation, synthetic fixtures, test tools, brokers, runtime services, and external systems. Listing a dependency does not activate it.

If a dependency would require credentials, external access, runtime mutation, or private data, mark it as blocked until a separate approval lane exists.

### `tests_required`

Tests should prove boundaries before capability. Future tests may include:

- manifest schema validation
- forbidden-input rejection
- allowed-input allowlist checks
- no-live-state-claim checks
- approval-gate presence checks
- sensitivity-gate presence checks
- receipt requirement checks
- disable and rollback path checks

This document does not implement those tests.

### `receipts_required`

Receipts should be named before activation. Common receipt classes:

- `manifest_review_receipt`
- `validation_receipt`
- `approval_receipt`
- `denial_receipt`
- `withheld_surface_receipt`
- `runtime_activation_receipt`
- `rollback_receipt`

Receipts are audit evidence, not authority by themselves.

### `disable_path`

The disable path should explain how to make the module unavailable without deleting history. Future manifests should prefer explicit flags, profile removal, broker denial, service stop procedures, or documented rollback steps.

For this draft schema, disable paths are descriptions only.

### `rollback_path`

The rollback path should describe how to reverse module-related docs, config, tests, or runtime enablement after approval. A rollback path must not depend on hidden state.

For this draft schema, rollback paths are descriptions only.

### `NOT_READY_boundaries`

Every manifest must list blocked uses. Baseline NOT_READY boundaries:

- runtime activation
- customer deployment
- autonomous action
- sensitive-data processing
- broker connection
- agent wiring
- SQLite write
- legacy runtime import
- generated-status mutation
- live system health claim

## 5. Synthetic Example Manifest

This example is synthetic. It does not describe a live module.

```yaml
module_id: "operator_surfaces.synthetic_module_atlas_view"
module_family: "operator_surfaces"
purpose: "Describe a proposed read-only view of reviewed module atlas and manifest documents."
authority_level: "docs_only"

allowed_inputs:
  - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
  - "future reviewed module manifest docs"
  - "synthetic fixture manifests"

forbidden_inputs:
  - "secrets, tokens, keys, credentials, and .env files"
  - "private financial, tax, CPA, client, or business records"
  - "active legal case files and matter vault contents"
  - "logs, runtime memory, generated live status, and AppData"
  - "private creative/business folders unless manually approved"
  - "whole-machine, whole-vault, whole-mailbox, or broad legacy-runtime ingest"

outputs_artifacts:
  - "read-only module family summaries"
  - "manifest boundary summaries"
  - "NOT_READY notices"
  - "withheld-surface notes"

approval_gates:
  - "manifest_review_required_before_commit"
  - "operator_explicit_approval_required_before_any_runtime_lane"
  - "customer_deployment_approval_required_before_customer use"

sensitivity_gates:
  - "local_only_by_default"
  - "no_sensitive_bodies"
  - "withheld_surface_required_for_excluded_or_ambiguous_sources"
  - "external_model_use_blocked_until_approved"

dependencies:
  docs:
    - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
  synthetic_fixtures:
    - "future synthetic manifest examples"
  brokers:
    - "none"
  runtime_services:
    - "none"

tests_required:
  - "schema_required_fields_present"
  - "forbidden_inputs_include_baseline_no_go_categories"
  - "authority_level_is_non_runtime"
  - "not_ready_boundaries_include_runtime_and_customer_deployment"
  - "no_live_system_state_claims"

receipts_required:
  - "manifest_review_receipt"
  - "validation_receipt"
  - "approval_receipt_before_any_later_runtime_lane"

disable_path: "Remove the manifest from any future reviewed manifest index and mark it disabled in the relevant docs-only registry."
rollback_path: "Revert the manifest commit or supersede it with a reviewed rollback receipt and replacement manifest."

NOT_READY_boundaries:
  - "runtime activation"
  - "customer deployment"
  - "autonomous action"
  - "sensitive-data processing"
  - "broker connection"
  - "agent wiring"
  - "SQLite write"
  - "legacy runtime import"
  - "generated-status mutation"
  - "live system health claim"
```

## 6. Validation Principles

Future validation should be deterministic and boundary-first.

Required principles:

- Reject manifests missing any required top-level field.
- Reject manifests that omit baseline NOT_READY boundaries.
- Reject manifests that claim runtime, broker, customer deployment, or autonomous authority without a separate approved lane.
- Reject manifests that list broad source sets, no-go paths, or ambiguous private material as allowed inputs.
- Require forbidden inputs to include relevant whitelist no-go categories.
- Require approval gates for consequential actions.
- Require sensitivity gates for any module that might touch private, client, legal, health, financial, creative/business, mailbox, calendar, credential, or external-provider data.
- Require receipts before readiness can be claimed.
- Treat tests as future proof requirements, not proof that exists.
- Treat dependencies as declarations, not activation.
- Treat advisory outputs as non-canonical unless a future committed contract says otherwise.

## 7. Explicit Non-Readiness

This draft schema is READY for docs-only review.

It is NOT_READY for:

- runtime validators
- runtime registries
- SQLite writes
- broker connections
- agent wiring
- private data reads
- customer deployment
- autonomous action
- sensitive-data processing
- legacy runtime imports
- generated-status mutation
- live-state claims

The next safe lane, after review, is still docs-only: add additional synthetic manifest examples for selected families or draft a validation test plan without implementing runtime code.
