# OpenClaw Work Terrain Relationship Index v0

## ELIWINSHIP Summary

This contract defines how OpenClaw terrain records can be linked without pretending the links are proof. A Markdown source note can describe a built contract, a Python file can export a read-model, a test can validate it, a stable-map section can surface it, and a receipt can later prove completion. This lane only models those relationships.

## Why Relationships Matter

- Source notes can describe built artifacts, but the source note does not prove the artifact is complete.
- Built artifacts can exist without a source note; that is a reconciliation gap, not an automatic error.
- Stable-map sections can exist without a clear source origin; that needs lineage review before doctrine promotion.
- Generated read-models and operator Markdown are proof/detail digests by default, not human-authored doctrine.

## Default Relationship Examples

- `chief_test_harness_source_to_contract`: `SOURCE_NOTE_MATCHES_BUILT_ARTIFACT` / `TEST_LINKED`
- `capital_hilton_proof_intake_contract_to_surface`: `SURFACES` / `STABLE_MAP_LINKED`
- `capital_hilton_proof_resolution_backend_links`: `BELONGS_TO_LANE` / `METADATA_LINKED`
- `markdown_knowledge_atlas_built_not_prominently_surfaced`: `BUILT_NOT_SURFACED` / `NEEDS_CHIEF_RECONCILIATION`
- `security_pass_contract_to_security_pass_surface`: `SURFACES` / `STABLE_MAP_LINKED`
- `future_invoicing_audit_to_parked_stress_test`: `DERIVED_FROM` / `RECONCILED_WITH_PROOF`
- `repo_b_planner_builder_reference_only`: `REFERENCES` / `CANDIDATE`
- `generated_operator_markdown_is_proof_detail`: `GENERATED_FROM` / `METADATA_LINKED`

## Review Roles

- Chief: Chief may later reconcile completion, source lineage, tests, receipts, and cross-off proof.
- Hermes: Hermes may later review concept coherence and overlapping doctrine without rewriting files.
- Operator: Operator remains final authority for promotion, archive, rewrite, deletion, action, or source-truth decisions.
- Guardian reviews protected/sensitive metadata lanes only; Guardian review is not action approval.

## Policy

- Metadata only: `true`
- Body ingestion allowed: `false`
- Relationship truth status: `candidate_until_receipted`
- Auto-promotion allowed: `false`
- Auto-archive/rewrite/delete allowed: `false`
- Stable-map update allowed in this lane: `false`

## What The Next Lane Adds

- Prompt 3 will add classification/staleness candidate states: current, old prompt, superseded, overlapping, source-missing, surfaced-missing, and review-needed candidates.

## Boundary

- No file moves, deletes, renames, rewrites, archive actions, body ingestion, broad private scan, semantic review, stable-map refresh, Mac sync/import, network, git push/pull/fetch, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, account/browser/email/Coupa access, credentials, or authority escalation.
