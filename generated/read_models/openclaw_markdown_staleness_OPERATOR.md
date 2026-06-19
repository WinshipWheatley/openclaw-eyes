# OpenClaw Markdown Staleness Candidates v0

Evidence:
- Classified `233` allowlisted Markdown documents from the bounded body-ingest read model.
- Review queue contains `25` candidates; stale/superseded candidates: `30`.
- Classification is advisory and signal-based; it is not cleanup authority or canonical truth promotion.

Status counts:
- `active_work_candidate`: `28`
- `current_canonical_root`: `3`
- `generated_read_model_candidate`: `90`
- `historical_or_packet_candidate`: `60`
- `review_needed`: `22`
- `stale_or_superseded_candidate`: `30`

Top review queue:
- `Operator/06_GEMINI_AUDIT_RULES.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:stale)
- `docs/doctrine/SURFACE_AUTHORITY.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:archive)
- `docs/navigation_maps/DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:archive)
- `docs/navigation_maps/TARGETED_DRY_RUN_CANDIDATE_MOVE_PLAN_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:archive)
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_MIGRATION_SPEC_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:legacy, stale_hint:old)
- `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:legacy, stale_hint:old)
- `docs/operations/DOC_LIFECYCLE.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:archive, stale_hint:archived, stale_hint:stale)
- `docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:old)
- `docs/operations/GUARDIAN_HITL_DUAL_WRITE_RECEIPT_PROOF_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:old)
- `docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md` -> `stale_or_superseded_candidate` (priority `90`, stale_hint:old)

Boundary:
- No file moves, archive decisions, rewrites, truth promotion, runtime dispatch, model calls, network calls, or external sends.
- Legal Discovery, credentials, finance/private folders, broad private roots, and hidden key stores remain excluded by the source ingest policy.

Next safe move:
- Feed the review queue to a human or relationship-index review before using any candidate as current operator context.
