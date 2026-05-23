# OpenClaw Work Terrain Classification / Staleness Candidate v0

## ELIWINSHIP Summary

This contract gives OpenClaw safe candidate labels for work terrain: current, supporting, old prompt, stale, duplicate, overlapping, generated, reference-only, source-card candidate, stable-map candidate, consolidation candidate, archive candidate, quarantine candidate, and fail-closed unknown. These labels are not final truth and do not allow cleanup.

## What Candidate Classification Means

- A current/stale/superseded label is a review candidate until receipts, source lineage, and review gates support it.
- Old prompts can be history, residue, or future source-card candidates; they are not current doctrine by default.
- Generated files are proof/detail, not human-authored doctrine by default.
- Consolidation candidates are review packets, not permission to rewrite.
- Supersession candidates keep old refs traceable; they are not permission to delete.

## Default Examples

- `security_pass_contract_current_canonical`: `CURRENT_CANONICAL` / Current backend security contract exists, tests passed, stable map surfaced it, and the Mac Security Pass surface is represented as read-only.
- `capital_hilton_proof_intake_current_supporting`: `CURRENT_SUPPORTING` / Supports the active Finance lane by structuring the 10 missing proof questions while action remains locked.
- `capital_hilton_proof_resolution_batch_current_supporting`: `CURRENT_SUPPORTING` / Models answer receipts, protected placeholders, Guardian packets, and proof progress rails; follow-through depends on stable-map/Mac import state.
- `old_invoicing_automation_prompt_archive_candidate`: `ARCHIVE_CANDIDATE` / High-risk future automation prompt should be preserved as history or stress-test material, not execution authority.
- `markdown_knowledge_atlas_built_not_surfaced`: `BUILT_NOT_SURFACED` / Backend capability exists while app/stable-map prominence may be incomplete.
- `repo_b_planner_builder_reference_only`: `REFERENCE_ONLY` / Repo B concept exists as reference terrain but no active authority is granted.
- `generated_operator_markdown_generated_artifact`: `GENERATED_ARTIFACT` / Generated digest/proof detail is not human-authored doctrine by default.
- `duplicated_chief_concepts_overlap`: `OVERLAPPING_CONCEPT` / Chief reconciliation, cross-off, test harness, and repair queue concepts overlap across terrain records.
- `source_note_matches_security_pass_surface`: `SOURCE_NOTE_MATCHES_BUILT_ARTIFACT` / Security Pass concept is implemented in backend contract and surfaced through stable-map/Mac read-only surfaces.
- `built_artifact_lacks_source_note_example`: `BUILT_ARTIFACT_LACKS_SOURCE_NOTE` / Built artifact exists but a source-lineage note is missing or not linked.

## Consolidation / Supersession Boundary

- Rewrite allowed: `false`
- Archive old fragments allowed: `false`
- Delete old fragments allowed: `false`
- Receipt required before action: `true`

## Future AI Judgment Policy

- Allowed later after metadata and relationship classification: compare selected safe excerpts, propose canonical/stale/duplicate labels, propose consolidation candidates, recommend source-card promotion, recommend stable-map promotion, recommend archive/supersession candidates
- Blocked now: broad body summarization, automatic truth promotion, moving/deleting/rewriting files, vector memory over all docs, private-note use without approval, AI deciding final doctrine without Hermes/Chief/Operator review
- Hermes reviews concept coherence. Chief reconciles completion/source lineage. Winship remains final authority.

## Next Batch Lane

- Prompt 4 will add a gap detector: missing source notes, built-but-unsurfaced artifacts, source notes without implementation, stable-map origin gaps, and receipt/test/commit gaps.

## Boundary

- No commit, staging, stable-map refresh, broad AI semantic review, raw body ingestion, broad private scan, file moves/deletes/rewrites/archive operations, network, git push/pull/fetch, Mac sync/import, Mission Control Swift changes, model/tool/agent/runtime, queue/autonomy, C-drive scan/write, credential/account/browser/email/Coupa access, or authority escalation.
