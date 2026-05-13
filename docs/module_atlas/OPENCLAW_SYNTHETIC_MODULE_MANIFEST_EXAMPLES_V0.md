# OpenClaw Synthetic Module Manifest Examples v0

## 1. Source Basis

These examples are based only on:

- `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md`
- `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md`

This document contains synthetic, inert documentation fixtures only. It does not create validators, tests, runtime code, runtime registries, SQLite writes, broker connections, agent wiring, private data reads, customer deployment, or live module activation.

These examples are not activation authority. They are examples of how future module manifests should be written after review.

## 2. Example Scope

This file includes exactly three synthetic examples:

1. `core/trust` example
2. `operator_surfaces` example
3. `producer_niles_domain` example

All examples include every required draft schema field:

- `module_id`
- `module_family`
- `purpose`
- `authority_level`
- `allowed_inputs`
- `forbidden_inputs`
- `outputs_artifacts`
- `approval_gates`
- `sensitivity_gates`
- `dependencies`
- `tests_required`
- `receipts_required`
- `disable_path`
- `rollback_path`
- `NOT_READY_boundaries`

## 3. Synthetic Example 1: `core/trust`

This example demonstrates a candidate trust-plane manifest. It does not describe an active module.

```yaml
module_id: "core_trust.synthetic_truth_gateway_manifest"
module_family: "core/trust"
purpose: "Describe a proposed trust-plane manifest for source-bound truth posture, evidence summaries, and withheld-surface notices."
authority_level: "docs_only"

allowed_inputs:
  - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
  - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  - "future reviewed source registry docs"
  - "synthetic evidence packet fixtures"

forbidden_inputs:
  - "secrets, tokens, keys, credentials, and .env files"
  - "private financial, tax, CPA, client, or business records"
  - "active legal case files and matter vault contents"
  - "logs, runtime memory, generated live status, and AppData"
  - "private creative/business folders unless manually approved"
  - "whole-machine, whole-vault, whole-mailbox, or broad legacy-runtime ingest"
  - "unreviewed prior art treated as canonical truth"

outputs_artifacts:
  - "proposal-only truth posture summaries"
  - "synthetic evidence packet summaries"
  - "withheld-surface notices"
  - "manifest boundary review notes"

approval_gates:
  - "manifest_review_required_before_commit"
  - "operator_explicit_approval_required_before_any_runtime_lane"
  - "runtime_activation_approval_required_before_runtime_use"
  - "source_registry_review_required_before_non_synthetic_inputs"

sensitivity_gates:
  - "local_only_by_default"
  - "no_sensitive_bodies"
  - "withheld_surface_required_for_excluded_or_ambiguous_sources"
  - "external_model_use_blocked_until_approved"
  - "private_data_processing_blocked_until_separately_approved"

dependencies:
  docs:
    - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
    - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  synthetic_fixtures:
    - "future synthetic evidence packet fixtures"
  brokers:
    - "none"
  runtime_services:
    - "none"

tests_required:
  - "schema_required_fields_present"
  - "authority_level_is_non_runtime"
  - "forbidden_inputs_include_baseline_no_go_categories"
  - "allowed_inputs_are_docs_or_synthetic_fixtures_only"
  - "not_ready_boundaries_include_runtime_and_sensitive_data_processing"
  - "no_live_system_state_claims"

receipts_required:
  - "manifest_review_receipt"
  - "validation_receipt"
  - "withheld_surface_receipt_if_any_source_is_excluded"
  - "approval_receipt_before_any_later_runtime_lane"

disable_path: "Remove the manifest from any future reviewed manifest index and mark the candidate trust-plane module disabled in docs-only status."
rollback_path: "Revert the manifest commit or supersede it with a reviewed rollback receipt and replacement synthetic manifest."

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

## 4. Synthetic Example 2: `operator_surfaces`

This example demonstrates a candidate read-only Operator surface manifest. It does not describe an active surface.

```yaml
module_id: "operator_surfaces.synthetic_manifest_review_view"
module_family: "operator_surfaces"
purpose: "Describe a proposed read-only Operator-facing view for reviewed module manifest posture, gates, and NOT_READY boundaries."
authority_level: "docs_only"

allowed_inputs:
  - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
  - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  - "future reviewed module manifest docs"
  - "synthetic manifest fixture docs"

forbidden_inputs:
  - "secrets, tokens, keys, credentials, and .env files"
  - "private financial, tax, CPA, client, or business records"
  - "active legal case files and matter vault contents"
  - "logs, runtime memory, generated live status, and AppData"
  - "private creative/business folders unless manually approved"
  - "whole-machine, whole-vault, whole-mailbox, or broad legacy-runtime ingest"
  - "live service state unless separately verified in a future lane"

outputs_artifacts:
  - "read-only module manifest summaries"
  - "missing gate summaries"
  - "NOT_READY notices"
  - "proposal-only next-doc-slice notes"

approval_gates:
  - "manifest_review_required_before_commit"
  - "operator_explicit_approval_required_before_any_runtime_lane"
  - "generated_status_mutation_approval_required_before_any_status_write"
  - "customer_deployment_approval_required_before_customer_use"

sensitivity_gates:
  - "local_only_by_default"
  - "no_sensitive_bodies"
  - "withheld_surface_required_for_excluded_or_ambiguous_sources"
  - "external_model_use_blocked_until_approved"
  - "operator_surface_must_not_display_private_data_bodies"

dependencies:
  docs:
    - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
    - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  synthetic_fixtures:
    - "future synthetic manifest fixture docs"
  brokers:
    - "none"
  runtime_services:
    - "none"

tests_required:
  - "schema_required_fields_present"
  - "authority_level_is_non_runtime"
  - "operator_surface_has_no_execution_authority"
  - "forbidden_inputs_include_baseline_no_go_categories"
  - "not_ready_boundaries_include_runtime_customer_deployment_and_generated_status_mutation"
  - "no_live_system_state_claims"

receipts_required:
  - "manifest_review_receipt"
  - "validation_receipt"
  - "withheld_surface_receipt_if_any_source_is_excluded"
  - "approval_receipt_before_any_later_runtime_lane"

disable_path: "Remove the manifest from any future reviewed manifest index and mark the candidate Operator surface hidden or disabled in docs-only status."
rollback_path: "Revert the manifest commit or supersede it with a reviewed rollback receipt and replacement synthetic manifest."

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

## 5. Synthetic Example 3: `producer_niles_domain`

This example demonstrates a bounded candidate Producer/Niles domain manifest. It does not describe an active domain module.

```yaml
module_id: "domain_modules.synthetic_producer_niles_domain"
module_family: "domain_modules"
purpose: "Describe a proposed Producer/Niles-style domain module for synthetic project packet review and proposal-only creative production planning."
authority_level: "proposal_only"

allowed_inputs:
  - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
  - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  - "synthetic project packet fixtures"
  - "future reviewed Producer/Niles planning docs"

forbidden_inputs:
  - "secrets, tokens, keys, credentials, and .env files"
  - "private financial, tax, CPA, client, or business records"
  - "active legal case files and matter vault contents"
  - "logs, runtime memory, generated live status, and AppData"
  - "private creative/business folders unless manually approved"
  - "whole-machine, whole-vault, whole-mailbox, or broad legacy-runtime ingest"
  - "customer communications without separate approval"
  - "publishing channels, senders, schedulers, or external accounts"

outputs_artifacts:
  - "proposal-only project packet summaries"
  - "synthetic draft-review flow notes"
  - "candidate domain boundary summaries"
  - "NOT_READY notices"
  - "withheld-surface notes"

approval_gates:
  - "manifest_review_required_before_commit"
  - "operator_explicit_approval_required_before_non_synthetic_inputs"
  - "producer_domain_approval_required_before_private_project_sources"
  - "publishing_or_sending_approval_required_before_external_action"
  - "customer_deployment_approval_required_before_customer_use"

sensitivity_gates:
  - "local_only_by_default"
  - "no_sensitive_bodies"
  - "withheld_surface_required_for_excluded_or_ambiguous_sources"
  - "external_model_use_blocked_until_approved"
  - "private_creative_business_sources_blocked_until_manually_approved"
  - "tenant_boundary_required_before_customer_or_shared_project_use"

dependencies:
  docs:
    - "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
    - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  synthetic_fixtures:
    - "future synthetic project packet fixtures"
  brokers:
    - "none"
  runtime_services:
    - "none"

tests_required:
  - "schema_required_fields_present"
  - "authority_level_is_proposal_only"
  - "forbidden_inputs_include_private_creative_business_sources"
  - "forbidden_inputs_include_publishing_and_sending_channels"
  - "not_ready_boundaries_include_customer_deployment_autonomous_action_and_sensitive_data_processing"
  - "no_live_system_state_claims"

receipts_required:
  - "manifest_review_receipt"
  - "validation_receipt"
  - "withheld_surface_receipt_if_any_source_is_excluded"
  - "approval_receipt_before_any_later_non_synthetic_domain_lane"
  - "rollback_receipt_if_manifest_is_superseded"

disable_path: "Remove the manifest from any future reviewed manifest index and mark the candidate Producer/Niles domain disabled in docs-only status."
rollback_path: "Revert the manifest commit or supersede it with a reviewed rollback receipt and replacement synthetic manifest."

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
  - "publishing or sending"
```

## 6. Example-Review Notes

Review these examples as documentation fixtures, not as module definitions ready for use.

Review checks:

- Each example has every required draft schema field.
- `authority_level` remains `docs_only` or `proposal_only`.
- `allowed_inputs` are committed docs, future reviewed docs, or synthetic fixtures only.
- `forbidden_inputs` restate baseline no-go categories and domain-specific exclusions.
- `dependencies` declare no brokers and no runtime services.
- `tests_required` names future proof requirements only; no validator or test is created here.
- `receipts_required` names future audit evidence only; no receipt is created here.
- `NOT_READY_boundaries` block runtime activation, customer deployment, autonomous action, sensitive-data processing, broker connection, agent wiring, SQLite writes, legacy imports, generated-status mutation, and live-state claims.

## 7. Common Invalid Manifest Patterns

Invalid patterns include:

- Claiming a module is active, healthy, deployed, connected, or ready.
- Treating `allowed_inputs` as permission to read private or broad source sets.
- Listing secrets, credentials, logs, runtime memory, active legal files, mailbox bodies, private finance records, customer data, or private creative/business folders as allowed inputs.
- Using `authority_level` to grant write, send, mutate, deploy, broker, or autonomous authority.
- Omitting action-specific approval gates for consequential behavior.
- Omitting sensitivity gates for modules that may later touch private, client, legal, health, financial, creative/business, mailbox, calendar, credential, or external-provider data.
- Listing a broker or runtime service as a dependency without marking it inactive and separately approval-gated.
- Treating receipts as authority instead of audit evidence.
- Treating tests_required as proof that tests already exist.
- Using an Operator surface as a hidden execution engine.
- Using a domain module as customer deployment approval.

## 8. Non-Authority Boundary

These examples are not activation authority.

They are NOT_READY for:

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
- validator or test creation
- private data read

Future manifests remain inert until separately approved, tested, receipted, and committed through a future lane.
