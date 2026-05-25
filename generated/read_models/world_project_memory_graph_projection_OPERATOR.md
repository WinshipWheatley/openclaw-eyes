# World Project Memory Graph Projection v0

ELIOPERATOR: The semantic graph is truth. The folder tree is a Mac/sidebar projection.

## What This Enables

Mac can read a deterministic sidebar projection for worlds, projects, topic slices, source refs, artifacts, procedures, receipts, and visual workspaces.

## What This Does Not Do Yet

It does not write memory, migrate SQLite, ingest transcripts or files, run retrieval, reorganize folders, move/delete files, or call agents.

## Mac Sidebar Projection

- Projection status: `UPDATED_READY_FOR_MAC`
- Mac render ready: `True`
- Root nodes: proj_music, proj_finance, proj_build

## Examples

- music_live_x32: music / live_music / x32 / routing / show_files
- music_studio_album_song: music / studio / album / song_name
- finance_capital_hilton: finance / capital_hilton / invoices
- build_mission_control: build / mission_control / chat_surface
- struna_mac_version: build / struna / mac_version
- multi_folder_chat: music / live_music / setlists

## Scope Boundaries

- music / local_operator: Fail closed if a music graph edge would expose client-private finance or legal facts.
- finance / capital_hilton: Capital Hilton invoice graph edges must not leak to other clients without explicit reviewed reusable summary.
- build / openclaw: Build knowledge can link to workflow examples only through safe summaries and provenance refs.
- build / struna: Struna summaries are private summary refs and must not be mixed into unrelated client scopes.

## Blockers

- STRICT_TREE_ASSUMED_AS_TRUTH: Use semantic graph refs as truth and folder paths as projections only.
- CROSS_CLIENT_LEAK: Fail closed and require reviewed scope boundary.
- MISSING_TENANT_SCOPE: Do not project unscopeable memory.
- MISSING_CLIENT_SCOPE: Do not project client-ambiguous memory.
- RAW_TRANSCRIPT_EXPOSURE: Use topic summaries and source refs only.
- RAW_FILE_BODY_EXPOSURE: Use metadata/source refs only.
- PROVENANCE_MISSING: Keep it out of current projection until provenance exists.
- DESTRUCTIVE_MOVE_ATTEMPTED: Block move/delete and show a suggested projection update only.
- SILENT_REORG_ATTEMPTED: Require operator review for disruptive reorganization.
- STALE_PROJECTION: Mark stale and regenerate from graph/readbacks.
- UNKNOWN_FAIL_CLOSED: Fail closed and ask for review.

## Boundary

No live memory write, DB migration, raw transcript ingestion, raw file body ingestion, agent retrieval, cross-scope query, reorganization, move/delete, folder tree update, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Export this deterministic projection for Mac/sidebar rendering; do not write memory or move folders.
