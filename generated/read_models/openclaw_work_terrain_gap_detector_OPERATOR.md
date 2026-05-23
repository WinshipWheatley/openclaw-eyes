# OpenClaw Work Terrain Gap Detector v0

## ELIWINSHIP Summary

This contract defines safe candidate gaps between OpenClaw terrain records, relationships, classifications, read-models, stable-map visibility, receipts, tests, and built-artifact claims. A gap is a review target, not an automatic task, cleanup order, archive instruction, or build request.

## What A Terrain Gap Means

- A source note can describe something built, but completion still needs tests, receipts, commits, or stable-map/read-model evidence.
- A built artifact can lack source lineage without being wrong; it becomes a Chief reconciliation candidate.
- Old prompts and generated artifacts are filtered so they do not become build-now gaps.
- Built-but-unsafe terrain routes to Guardian or security delta review, never activation.

## Priority Buckets

- CRITICAL_SECURITY_GAP, INCOMPLETE_LINEAGE, OPERATOR_DECISION_NEEDED, HERMES_REVIEW_NEEDED, CHIEF_RECONCILIATION_NEEDED, STABLE_MAP_VISIBILITY_GAP, PROOF_DETAIL_ONLY, MINOR_ORPHAN, PARKED_OR_PREMATURE, QUARANTINE_REQUIRED, UNKNOWN_FAIL_CLOSED

## Negative Filters

- `old_prompt_filter`: Prevent old prompts from becoming build-now implementation gaps by default.
- `generated_artifact_filter`: Prevent generated files from being treated as doctrine or source notes.
- `reference_only_filter`: Prevent reference terrain from becoming active tasks or activation gaps.
- `historical_residue_filter`: Keep history visible for reconciliation without treating it as missing implementation.
- `premature_concept_filter`: Route premature concepts to parked/future terrain instead of build-now gaps.
- `unsafe_execution_filter`: Route unsafe implementation posture to Guardian/security delta instead of surface or execution.

## Built Status Validation

- File existence alone is not enough to claim built.
- `VALIDATED_BY_TEST` is represented as a relationship signal for stronger built-status evidence.
- Worker reports, screenshots, generated files, tests, receipts, and commits remain evidence inputs, not doctrine by themselves.

## Default Gap Examples

- `chief_source_notes_vs_built_contracts_gap`: `CHIEF_RECONCILIATION_NEEDED` / `SOURCE_NOTE_DESCRIBES_BUILT_ARTIFACT` / Chief concepts may be spread across prompts, Markdown, contracts, and generated digests.
- `markdown_knowledge_atlas_visibility_gap`: `STABLE_MAP_VISIBILITY_GAP` / `STABLE_MAP_REPRESENTATION_MISSING` / The backend terrain capability exists but may not be prominent enough in app-facing truth.
- `capital_hilton_proof_resolution_surface_gap`: `INCOMPLETE_LINEAGE` / `MISSION_CONTROL_SURFACE_MISSING` / Backend rails exist, but answer capture UI is not implemented by this lane and action remains blocked.
- `repo_b_planner_builder_reference_gap`: `PARKED_OR_PREMATURE` / `REPO_B_REFERENCE_NOT_PROMOTED` / Repo B concepts may be useful reference terrain but have no active authority.
- `future_invoicing_audit_parked_gap`: `PARKED_OR_PREMATURE` / `CONCEPTUALLY_VALID_BUT_PREMATURE` / The audit can inform safety but must not be confused with executable invoicing workflow.
- `generated_operator_markdown_truth_gap`: `PROOF_DETAIL_ONLY` / `GENERATED_ARTIFACT_CONFUSED_AS_DOCTRINE` / Generated operator Markdown is useful proof/detail but not doctrine by default.
- `stable_map_summary_missing_for_work_terrain`: `STABLE_MAP_VISIBILITY_GAP` / `STABLE_MAP_REPRESENTATION_MISSING` / Work Terrain should eventually be app-visible as compact proof, not a full file browser.
- `old_prompt_not_implementation_gap`: `PROOF_DETAIL_ONLY` / `HISTORICAL_RESIDUE_ONLY` / Old prompts preserve context but must not silently become build-now work.
- `built_artifact_missing_test_receipt_gap`: `INCOMPLETE_LINEAGE` / `TEST_VALIDATION_MISSING` / A file existing is not enough to claim work is built or complete.
- `implementation_exists_but_doctrine_stale_gap`: `HERMES_REVIEW_NEEDED` / `IMPLEMENTATION_EXISTS_BUT_DOCTRINE_STALE` / Implementation can move beyond source notes, leaving doctrine misleading.
- `doctrine_exists_but_implementation_superseded_gap`: `HERMES_REVIEW_NEEDED` / `DOCTRINE_EXISTS_BUT_IMPLEMENTATION_SUPERSEDED` / Docs can describe an approach that later implementation replaced.
- `built_but_unsafe_execution_gap`: `CRITICAL_SECURITY_GAP` / `BUILT_BUT_UNSAFE` / Implementation that violates safety posture must be quarantined, not activated.

## Policy

- Metadata only: `true`
- Body ingestion allowed: `false`
- Semantic review allowed now: `false`
- File mutation allowed: `false`
- Auto archive/consolidation/stable-map promotion/implementation allowed: `false` / `false` / `false` / `false`
- Chief reconciles source lineage and built-status claims.
- Hermes reviews concept coherence and stale/supersession candidates.
- Guardian quarantines protected, unsafe, or authority-conflicting terrain.
- Winship remains final authority.

## Next Batch Lane

- Prompt 5 validates the Work Terrain batch, commits it if clean, refreshes the stable map once, and stages the bundle for Mac import. This prompt does none of those things.

## Boundary

- No commit, staging, stable-map refresh, broad AI semantic review, raw body ingestion, broad private scan, file moves/deletes/rewrites/archive operations, network, git push/pull/fetch, Mac sync/import, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, C-drive scan/write, credential/account/browser/email/Coupa access, or authority escalation.
