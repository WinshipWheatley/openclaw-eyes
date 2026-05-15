# OpenClaw Markdown Knowledge Atlas Discovery v0

Date: `2026-05-14`

Purpose: reconcile existing OpenClaw document/Markdown classification, retrieval,
trust, sensitivity, and reorganization systems before building any new Markdown
Knowledge Atlas layer.

This is discovery only. No files were moved, renamed, deleted, reorganized, or
raw-ingested.

## Long-Term Direction

This Markdown/docs discovery lane is the first narrow slice of a broader
OpenClaw File Atlas direction.

Eventually OpenClaw should be able to map and tag every operator-owned
drive/root across PC, Mac, external drives, project folders, archives, client
roots, music/video/business drives, and mirrors. That future File Atlas should
understand canonical roots, mirror roots, archive roots, project/client roots,
runtime roots, no-go/private roots, and media/business drives without confusing
visibility with retrieval authority.

This lane does not implement that broader File Atlas.

Boundaries for this discovery remain:

- Do not scan all drives.
- Do not broaden beyond OpenClaw Markdown/docs and existing substrate discovery.
- Do not inspect private/no-go roots raw.
- Do not move, rename, delete, or reorganize files.
- Do not write to `/mnt/c/openclaw`.
- Do not treat future-drive visibility as agent retrieval authority.

The recommendation below is therefore future-root-ready, but the immediate
output remains: **Markdown Knowledge Atlas Discovery v0 - identify what already
exists, what is missing, and the smallest safe extension point.**

## Search Scope

Search terms used across safe repo surfaces included:

- `markdown`, `md`, `docs`, `doc inventory`, `document inventory`
- `knowledge atlas`, `corpus`, `evidence`, `source inventory`, `artifact registry`
- `context packet`, `handoff`, `current system map`, `doctrine`, `canonical`
- `stale`, `superseded`, `reorg`, `archive`, `freshness`, `source_of_truth`
- `truth registry`, `promotion`, `accepted context`, `working context`
- `retrieval`, `no_go`, `sensitive`, `Mac mirror`, `multi-root`

Safe searched/inspected areas:

- `corpus_atlas.py`, `evidence_kettle.py`, `context_selection.py`, `mac_mirror_atlas.py`
- source inventory, artifact registry, accepted-context, extraction, source-card,
  and packet scripts
- `docs/operations/`
- `generated/read_models/`
- `generated/corpus_atlas/`
- `generated/context_packets/`
- focused corpus/evidence/context/source/artifact tests
- Business Ops ledger schema/counts via SQLite metadata queries

Raw no-go/private content was not inspected. `polish_loop/tasks/` was not
inspected.

## Existing Systems Found

| Surface | Status | What It Already Covers | Gap For Markdown Knowledge Atlas |
|---|---:|---|---|
| Corpus Atlas v0.6, `corpus_*` | current_active / candidate_to_extend | Metadata-first path inventory, sensitivity, freshness, canonicality, retrieval eligibility, ingestion eligibility, world binding, reorg buckets, multi-root records. It already classifies `.md` paths. | Markdown roles are coarse: `docs`, `handoff`, `ux_product_synthesis`. No document-specific role/trust taxonomy, supersession graph, heading index, or current-doc query surface. |
| Mac Mirror Atlas v0 | current_active / candidate_to_extend | Imports explicit Mac manifests into `corpus_*`; Mac generated read-model Markdown is represented as non-canonical mirror metadata. | Covers generated read-model mirror Markdown, not arbitrary Mac app/docs Markdown. Mac app root currently has no Markdown rows. |
| Evidence Kettle v0.1, `evidence_*` | current_active / partial_overlap | Ingests bounded generated read-model snapshots, receipt summaries, and safe `ingest_allowed` canonical docs. Evidence is not truth. | Does not broadly ingest Markdown content. Should remain downstream of atlas/promotion gates, not become a broad Markdown crawler. |
| Context Selection v0, `context_selection_*` | current_active / downstream consumer | Selects bounded evidence/read-model facts into deterministic packets; excludes no-go/unknown/sensitive records. | It consumes eligible evidence; it does not classify Markdown documents or decide doc authority. |
| Source Inventory v0 | current_active / partial_overlap | Explicit allowlist metadata inventory with no-go examples and agent-context flags. | Small allowlist, not a repo-wide Markdown map. Mostly older module/receipt/status focus. |
| Accepted Context Promotion / Safe Extraction / Source Cards / Working Packets | current_active / partial_overlap | Provides a governed path from allowlisted metadata to extracted text, compact cards, and accepted working packets. | Artifact-driven, not SQLite-first for all Markdown. Good model for future selective document extraction, not a replacement for Markdown path atlas. |
| Artifact Registry v0 | current_active / partial_overlap | Tracks generated read-model artifact contracts, safe-for-agent flags, hashes, and no-authority claims. | Focuses on generated artifacts, not ordinary docs and handoffs. |
| Canonical Docs Ingestion / Truth Registry | current_active but narrow | `scripts/ingest_canonical_docs.py` has a `SOURCE_REGISTRY` of 9 docs; ledger currently has 83 `canonical_facts` and 9 `truth_registry_entries`. | This is an older explicit canonical fact path, not a Markdown discovery atlas. It should not be used for broad document intake. |
| `DOC_GOVERNANCE.md` / `DOC_LIFECYCLE.md` | current_active | Human-readable doc lanes, promotion rules, active/stale/archive concepts. | Not queryable in SQLite and not connected to every Markdown path. |
| `OPENCLAW_SYSTEM_MARKDOWN_WHITELIST_PROPOSAL_V0.md` | planning_only / guardrail | Whitelisted second-pass Markdown groups and no-go sources. Strong boundary language for prior-art sources. | Proposal only; references old C-drive paths and external prior-art scopes. Not an implemented atlas. |
| `OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md` | planning_only / guardrail | Metadata-only stale/noisy folder candidates and explicit no-cleanup rules. | Folder-level and draft; not a document-level Markdown classifier. |
| Generated system maps / handoffs | current_active | Current posture surfaces and next-lane references. | Human-readable; not normalized enough for agents to query all Markdown safely. |

## Ledger Findings

Current root registry includes:

- `pc_wsl_home_openclaw`: canonical PC/WSL operating repo, scanned metadata-only.
- `mac_generated_read_models`: non-canonical generated read-model mirror, manifest-imported metadata.
- `mac_mission_control_app`: non-canonical app root, manifest-imported metadata.
- `mac_openclaw_mirror`: future mirror root, not scanned.
- `github_legacy_openclaw`: legacy git repo placeholder, not imported.
- `client_project_root` and `client_runtime_root`: placeholders requiring allowlists.

Important run note: the latest global `corpus_atlas_runs` row is the Mac
generated read-model manifest import. For PC Markdown analysis, use the latest
run for `root_id=pc_wsl_home_openclaw`:
`catlas_2026-05-14T021239Z0000_9aaa57b413ec`. A future implementation should
report latest rows per root, not just latest run globally.

PC/WSL latest atlas Markdown counts:

- Total `.md` paths: `142`.
- Source role: `docs=137`, `generated_read_model=4`, `secret_boundary=1`.
- Freshness: `source_claim=130`, `current_source_of_truth=4`, `generated_current=4`, `stale_possible=3`, `no_go_boundary=1`.
- Canonicality: `operator_note=130`, `canonical_current=4`, `generated_current=4`, `superseded=3`, `no_go_boundary=1`.
- Retrieval/ingestion: `needs_operator_review/needs_review=117`, `blocked_unknown/needs_review=14`, `generated_read_model_only/generated_snapshot_only=4`, `retrievable/ingest_allowed=4`, `metadata_only/metadata_only=2`, `blocked_no_go/no_go=1`.
- Reorg buckets: `docs_current=133`, `docs_legacy=3`, `generated_output=3`, `unknown_review=2`, `sensitive_no_go=1`.

Canonical/retrievable Markdown in the PC atlas is intentionally tiny:

- `AGENTS.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`
- `OPENCLAW_RUNTIME.md`
- `USER.md`

Known stale/superseded Markdown candidates already flagged:

- `CURRENT_STATE.md`
- `NEXT_ACTIONS.md`
- `docs/operations/OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md`

Evidence Kettle Markdown sources are also narrow:

- The four canonical root docs above as `ingest_allowed_source`.
- Generated Markdown snapshots such as `Operator/GENERATED_CURRENT_STATE.md`,
  `Operator/GENERATED_NEXT_ACTIONS.md`, `generated/read_models/generated_current_state.md`,
  and `generated/read_models/generated_next_actions.md`.

Mac generated read-model mirror currently reports generated read-model files as
healthy and metadata-only. Current report output observed `28` generated
read-model files with `missing_expected=0`, `extra=0`, and hash-backed matches.
Markdown operator/read-model companions are represented as generated snapshots,
not Mac truth authority.

## Direct Answers

1. **Does Corpus Atlas already track Markdown paths?**
   Yes. It tracks Markdown paths as corpus path rows with freshness, sensitivity,
   retrieval, ingestion, canonicality, world, and advisory reorg labels. It is
   already the correct base layer.

2. **Does Corpus Atlas classify enough authority/freshness/sensitivity/retrieval eligibility?**
   Partially. It has the right generic gates, but Markdown-specific document
   roles and trust states are missing. Today most docs become `source_claim` /
   `operator_note` and `needs_operator_review`, which is safe but not very
   useful for agents asking "which handoff is current?" or "which docs are stale?"

3. **Does Evidence Kettle already ingest Markdown content/chunks?**
   No broad Markdown content ingestion exists, and that is good. Evidence Kettle
   ingests generated snapshots and a tiny explicit safe doc set. Older canonical
   doc ingestion extracts sections from 9 allowlisted docs into `canonical_facts`,
   but it is not a repo-wide Markdown atlas.

4. **Does Context Selection already use Markdown-derived evidence?**
   Only indirectly and narrowly: generated Markdown/read-model snapshots and
   eligible evidence rows can be selected. Context Selection is not responsible
   for document discovery or trust classification.

5. **Do existing docs/reports identify stale/current Markdown?**
   Yes, partially. Corpus Atlas flags a few known stale files. `DOC_GOVERNANCE.md`,
   `DOC_LIFECYCLE.md`, current system maps, handoffs, and stale-folder manifests
   define policy and examples. There is no normalized SQLite doc-role/supersession
   layer yet.

6. **Is there already a reorg candidate system?**
   Yes. Corpus Atlas has `corpus_reorg_candidates` and `reorg_bucket` labels such
   as `docs_current`, `docs_legacy`, `scratch_archive`, `sensitive_no_go`, and
   `unknown_review`. It is advisory only and should be extended, not replaced.

7. **Is there already Mac mirror Markdown coverage?**
   Yes for `mac_generated_read_models`, via manifest import. The Mac Mission
   Control app manifest currently has no Markdown rows. Mac roots remain
   non-canonical metadata surfaces.

8. **What is missing for "ask agents questions about Markdown and trust the result"?**
   A document-specific overlay: role taxonomy, trust status, latest/supersedes
   relationships, active-handoff selection, canonical-vs-mirror distinction,
   review queue, and a read-model/query surface. Agents should query this overlay
   and Evidence/Context Selection, not raw docs directly.

## Recommendation

Do not create a parallel filesystem atlas.

Recommended extension point: **extend Corpus Atlas with a small Markdown document
overlay, then let Evidence Kettle and Context Selection consume only the approved
subset.**

Use existing `corpus_paths` as the source of path truth. Add a small `markdown_*`
namespace only for document-specific classifications that do not fit the generic
path labels.

Recommended SQLite location: existing Business Ops ledger
`.openclaw/business_ops/ledger.sqlite`.

Design the overlay so future roots can be represented later without broadening
this lane. Preserve root metadata such as `root_id`, `root_kind`, `host_kind`,
`owner_scope`, `project_id`, `client_id`, `canonical_status`, `import_status`,
`mirror_of_root_id`, and `lineage_source` where available from Corpus Atlas.
Future root categories should be representable as metadata labels, including:

- external drives
- Mac mirrors
- video/music drives
- archive drives
- client project roots
- client runtime roots
- no-go/private roots

These labels are planning hooks only in this discovery. They do not authorize
drive scans, raw reads, ingestion, reorganization, or agent retrieval.

Recommended tables if implementing:

- `markdown_atlas_runs`
- `markdown_documents`
- `markdown_document_labels`
- `markdown_document_links`
- `markdown_retrieval_policies`
- `markdown_reorg_reviews`
- `markdown_supersession_candidates`

Each `markdown_documents` row should link back to `corpus_paths.path_id` and
preserve `root_id`, `corpus_run_id`, relative path, git status, sensitivity,
retrieval/ingestion eligibility, canonicality, freshness, world binding, and
reorg bucket. The overlay should not store raw bodies by default.

## Proposed Taxonomy

`document_role`:

- `canonical_doctrine`
- `current_system_map`
- `active_handoff`
- `generated_status`
- `generated_read_model_operator_note`
- `implementation_spec`
- `operation_doc`
- `test_baseline`
- `product_vision`
- `ux_taste`
- `planning_note`
- `legacy_doc`
- `stale_possible`
- `superseded`
- `scratch`
- `archive_candidate`
- `sensitive_metadata_only`
- `no_go`
- `unknown_review`

`trust_status`:

- `canonical_current`
- `generated_current`
- `operator_promoted`
- `evidence_surface`
- `source_claim`
- `historical_context`
- `stale_possible`
- `superseded`
- `unknown_review`

`retrieval_policy`:

- `agent_retrievable`
- `metadata_only`
- `blocked_no_go`
- `needs_operator_review`
- `generated_surface_only`

`reorg_policy`:

- `keep_canonical`
- `keep_generated`
- `docs_current`
- `docs_legacy`
- `archive_candidate`
- `scratch_archive`
- `no_go_boundary`
- `review_required`

## Proposed First Implementation Lane

**Markdown Knowledge Atlas v0 - Corpus-Linked Document Role Overlay**

Implement narrowly:

1. Re-run or refresh Corpus Atlas for `pc_wsl_home_openclaw` so current docs are represented.
2. Add `markdown_*` tables linked to `corpus_paths`, not a new path crawler.
3. Classify only Markdown already present in safe Corpus Atlas rows.
4. Do not read raw bodies except for explicitly safe tiny canonical files if tests require it.
5. Use path/name/location heuristics plus existing generated read-models and docs governance.
6. Produce reports:
   - current/canonical docs
   - active handoffs/checkpoints
   - generated status/operator read-model Markdown
   - stale/superseded docs
   - unknown-review queue
   - safe-for-agent retrieval queue
   - reorg review queue
   - Mac mirror Markdown summary
7. Export standalone read-models:
   - `generated/read_models/markdown_knowledge_atlas.json`
   - `generated/read_models/markdown_knowledge_atlas_OPERATOR.md`
8. Keep Evidence Kettle ingestion limited to approved generated snapshots and explicit `agent_retrievable` docs.

Suggested commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_markdown_knowledge_atlas.py --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_markdown_knowledge_atlas.py --report summary --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_markdown_knowledge_atlas.py --report current --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_markdown_knowledge_atlas.py --report stale --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_markdown_knowledge_atlas_read_model.py --format operator
```

## Risks

- Treating Markdown prose as truth instead of source claims or evidence surfaces.
- Creating a duplicate path inventory instead of linking to `corpus_paths`.
- Letting the latest global atlas run hide PC/WSL rows because a Mac manifest run
  is newer.
- Over-promoting `docs_current` into `canonical_current`.
- Reading broad bodies from private/no-go/sensitive folders.
- Reintroducing C-drive prior-art paths from old whitelist proposals.
- Confusing Mac mirror read-model Markdown with backend canonical authority.
- Letting stale handoffs or generated status files answer as current.
- Moving/reorganizing docs before the advisory map is reviewed.

## Stop Conditions

Stop before implementation if:

- The lane would need raw content from private/no-go/sensitive roots.
- The document role cannot be inferred from path/name/current reports without
  reading broad bodies.
- Existing Corpus Atlas labels are stale and need a refresh first.
- The implementation would change generated read-model central contracts.
- The implementation would move/rename/delete docs.
- The implementation would promote Markdown claims into truth automatically.
- The implementation would require Mac scanning, network calls, Docker/Ollama,
  runtime activation, or Mission Control changes.

## Next Exact Implementation Prompt

```text
You are working in /home/openclaw on PC/WSL.

Lane:
Markdown Knowledge Atlas v0 - Corpus-Linked Document Role Overlay

Goal:
Build a bounded Markdown/document role overlay on top of existing Corpus Atlas
rows so OpenClaw can answer which Markdown docs are canonical, current,
generated, handoff/status/spec/planning/stale/superseded/scratch/no-go, and safe
for agent retrieval.

Hard boundaries:
- Do not create a new filesystem atlas.
- Link to existing corpus_paths rows in .openclaw/business_ops/ledger.sqlite.
- Do not move, delete, rename, or reorganize files.
- Do not read broad Markdown bodies.
- Do not inspect private/no-go/sensitive roots raw.
- Do not write to /mnt/c/openclaw.
- Do not activate agents/runtime/tools, Docker, Ollama, or network.
- Do not change Mission Control.
- Do not promote Markdown text into truth.

Before implementation:
- Inspect corpus_atlas.py, evidence_kettle.py, context_selection.py, generated/corpus_atlas/corpus_atlas_latest.md, docs/operations/DOC_GOVERNANCE.md, docs/operations/DOC_LIFECYCLE.md, and this discovery report.
- Refresh or explicitly select the latest Corpus Atlas run for root_id=pc_wsl_home_openclaw.

Implement:
- markdown_atlas_runs
- markdown_documents
- markdown_document_labels
- markdown_document_links
- markdown_retrieval_policies
- markdown_reorg_reviews
- markdown_supersession_candidates
- scripts/build_markdown_knowledge_atlas.py
- scripts/query_markdown_knowledge_atlas.py
- scripts/export_markdown_knowledge_atlas_read_model.py
- tests/test_markdown_knowledge_atlas.py
- generated/read_models/markdown_knowledge_atlas.json
- generated/read_models/markdown_knowledge_atlas_OPERATOR.md

Classify from corpus metadata first using document_role, trust_status,
retrieval_policy, and reorg_policy. Unknown means needs_operator_review. No-go
and sensitive rows remain metadata-only or blocked. Generated read-model Markdown
is generated_surface_only. Only explicit canonical docs may become
agent_retrievable.

Validation:
Run focused tests for Markdown Atlas plus Corpus Atlas/Evidence Kettle/Context
Selection read-model tests.

After completion, report schema changes, counts by role/trust/retrieval/reorg,
current docs, stale docs, unknown-review docs, Mac mirror docs, generated files,
test results, and git status.
```
