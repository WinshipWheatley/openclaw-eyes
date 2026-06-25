# SYSTEM-CATALOG: Discovery Synchronizer + metadata catalog (durable consolidation spec)

## Acceptance Criteria
**Version / Hash:** 20260625-SYSCAT-v1
**Architecture owner:** Opus (this spec). Narrow build units may be split to Sonnet; **Gemini must audit
coverage (all registered repos) + freshness before merge.**
**Grounded in:** `workspaces/cross_repo_discovery_legal_readiness_audit/` (AUDIT.md, SYNCHRONIZER_REQUIREMENTS.md,
SQLITE_SYSTEM_CATALOG_AUDIT.md, MAP_ROOM_AUDIT.md, GRAPHIFY_AUDIT.md, SCAN_RECEIPT.json, ORCHESTRATOR_HANDOFF.md).
Scan reference: `AUDIT-20260625-CROSS-REPO` (15 repos discovered across `/home/openclaw` + `/mnt/e`).

---

## A. Principles (binding — violations fail the Gemini audit)
1. **Metadata-only inventory, NEVER truth.** The catalog stores POINTERS (repo path, branch, head_commit,
   file path, scan_id) to authoritative sources (git + the domain DBs). It MUST NOT store business domain
   data, invoices, raw PII, message bodies, or Legal Sealed evidence. (Git + domain DBs stay authoritative.)
2. **One scan_id, single source — no competing truth.** ONE `scan_id` drives `system_catalog.sqlite3`,
   Map Room, and Graphify together. Map Room **visualizes the catalog**; Graphify is a **rebuildable
   relationship index derived FROM the catalog** — both supersede the stale filesystem-spidering scripts.
3. **Freshness-first; capture dirty.** Every catalog row + Map Room + Graphify + receipt carries the
   `scan_id` (+ timestamp) that produced it. **Uncommitted/dirty state IS captured** (the current systems'
   gap). Staleness is queryable (age of latest complete scan; whether a repo HEAD advanced / went dirty since).
4. **PARTIAL = block, never a half-truth.** If ANY registered repo is unavailable/unreadable, the scan is
   `PARTIAL` and MUST NOT be promoted as the current catalog. Per-repo `coverage` status is recorded.
5. **Read-only, bounded discovery.** The synchronizer NEVER writes to a scanned repo. It respects
   `excluded_paths`/`blocked_paths`. **Legal-message / PII ingestion is OUT OF SCOPE** (a separate gated
   track — do not touch it here). No network/send/money/bank behavior.

---

## B. Scope, modules, exclusions
- **Catalog DB:** `system_catalog.sqlite3` — canonical default `/home/openclaw/state/system_catalog/system_catalog.sqlite3`
  (D2), **injectable**; tests use temp-file DBs. Metadata-only (§C).
- **Modules (narrow units, §G):** catalog store/DAL; discovery+capture; consumer rebuilders + pipeline.
- **Consumers it rebuilds:** Map Room (`openclaw_filesystem_map_room_terrain.json`) and Graphify
  (`openclaw_filesystem_graphiffy.json`) — now **catalog-derived + scan_id-tagged** (keep filenames so
  existing readers work; D4).
- **Reuse, don't compete:** read/relate to the existing `openclaw_filesystem_atlas.*`, the
  `system_knowledge_registry.sqlite` snapshot, and the spine's orphaned `file_inventory` — the catalog
  **consolidates/supersedes** these, it does not duplicate provenance.
- **Out of scope / do NOT touch:** Legal Sealed vault, PII tokenization, message ingestion, G2C domain
  models + `ar_gig_to_cash_*`, any business/financial data.

---

## C. Schema (DDL — exact; SQLite; the 8 audit tables, all scan-scoped)
`PRAGMA foreign_keys = ON;` Every content table carries `scan_id TEXT NOT NULL` (FK → `catalog_scans.scan_id`).
1. **`catalog_scans`** — `scan_id TEXT PRIMARY KEY`, `started_utc`, `completed_utc` NULLABLE, `tool_version`,
   `status TEXT CHECK(status IN ('RUNNING','COMPLETE','PARTIAL','FAILED'))`, `repo_count INT`, `dirty_count INT`,
   `coverage_gaps_json TEXT`, `excluded_paths_json TEXT`, `receipt_json TEXT`. The scan provenance + the receipt.
2. **`repositories`** — `scan_id`, `repo_path` NOT NULL, `branch`, `head_commit`, `dirty INT`,
   `coverage TEXT CHECK(coverage IN ('VERIFIED','PARTIAL','UNAVAILABLE'))`, `is_root INT`. UNIQUE(`scan_id`,`repo_path`).
3. **`worktrees`** — `scan_id`, `repo_path`, `worktree_path`, `branch`, `head_commit`, `dirty INT`.
4. **`components`** — `scan_id`, `repo_path`, `component_id`, `name`, `kind`, `source_ref` (path/module pointer).
5. **`capabilities`** — `scan_id`, `repo_path`, `capability_id`, `name`, `status`, `source_ref`.
6. **`queues`** — `scan_id`, `repo_path`, `queue_path`, `item_count INT`, `states_json` (parsed task states).
7. **`handoffs`** — `scan_id`, `repo_path`, `handoff_path`, `checkpoint`, `updated_utc`.
8. **`tests`** — `scan_id`, `repo_path`, `test_path`, `count INT` (or last-known status pointer; metadata only).
9. **`schema_migrations`** — `version INT PK`, `applied_utc`, `description` (forward-only, idempotent open).

**Current = the latest `catalog_scans` row with `status='COMPLETE'`.** History is retained per scan_id
(append-versioned, D1) for freshness/diff + audit. No mutable "current" flag stored.

---

## D. The Synchronizer pipeline (exact 9-step contract — SYNCHRONIZER_REQUIREMENTS)
A single run (`run_discovery_scan(registry, *, catalog_db, now)`):
1. **Discover** every registered repo + active worktree from the **repository registry** (D3:
   `REPOSITORY_REGISTRY.md` is authoritative, seeded from the 15; registry-driven, not blind auto-discovery,
   so PARTIAL is detectable).
2. **Capture** per repo/worktree: `branch`, `head_commit`, `dirty` (via read-only `git` — `rev-parse`,
   `status --porcelain`). Unreadable repo → `coverage=UNAVAILABLE`.
3. **Parse** durable specs, queues, tests (+ components, capabilities, handoffs) per repo — metadata only.
4. **Generate ONE immutable `scan_id`** (format `SYSCAT-<UTC-compact>-<short-content-hash>`; deterministic
   from the captured set; `now` injected for testability).
5. **Populate** `system_catalog.sqlite3` transactionally, all rows tagged with the scan_id (`catalog_scans`
   row first as `RUNNING`, finalized to `COMPLETE`/`PARTIAL`).
6. **Rebuild Graphify** JSON strictly from catalog nodes (relationship index; no raw domain/PII).
7. **Rebuild Map Room** JSON strictly from catalog layout (terrain view of the catalog, not the filesystem).
8. **Emit Scan Receipt** JSON matching the audit shape: `{scan_id, timestamp, tool_version, repositories:[{path,
   branch, head_commit, worktrees, dirty, coverage}], failures, coverage_gaps, excluded_paths}` (also stored in
   `catalog_scans.receipt_json`).
9. **PARTIAL-block:** if any repo is `UNAVAILABLE`, finalize the scan `PARTIAL`, do NOT promote it as current,
   and surface the gap. A `COMPLETE` scan requires every registered repo `VERIFIED`.

---

## E. Freshness / staleness semantics
- `get_current_scan()` → latest `COMPLETE` scan (or None). `is_stale(max_age, repo_head_map)` → True if the
  latest complete scan is older than `max_age` OR a repo's live HEAD/dirty differs from the catalogued one.
- Map Room / Graphify / receipt each embed `scan_id` + `generated_utc` so a consumer can detect staleness.
- The synchronizer captures dirty state so "uncommitted work" is never silently omitted.

---

## F. Required tests (contract-exact; authored INDEPENDENTLY of the impl, per the G2C pattern)
1. Migration idempotent across reopen; all 9 tables + `schema_migrations` present.
2. Scan-scoped writes: a scan tags every row with its scan_id; two scans coexist; `get_current_scan` returns
   the latest COMPLETE.
3. **Metadata-only guard:** no table column/row holds business/invoice/PII/message-body content (assert schema
   + a fixture attempt to store domain data is rejected/has no home).
4. **PARTIAL-block:** a registry with one UNAVAILABLE repo → scan `PARTIAL`, not promoted as current; gap surfaced.
5. **Dirty capture:** a dirty repo fixture → `dirty=1` recorded (proves the current-systems gap is closed).
6. **Consumer rebuild:** Map Room + Graphify are rebuilt FROM the catalog (assert their nodes trace to catalog
   rows + the scan_id; not from a live filesystem walk).
7. Scan receipt shape matches the audit contract; stored in `catalog_scans.receipt_json`.
8. Idempotent re-scan of an unchanged registry yields a consistent catalog (same logical content; new scan_id ok).
9. **Read-only/security:** the synchronizer performs no writes to any scanned repo; `excluded_paths` honored;
   no network/send/PII path. All tests run on temp DBs + synthetic/temp repo fixtures (no real repo mutation).
10. Freshness: `is_stale` flips when a repo HEAD advances or goes dirty vs the catalogued scan.

---

## G. Build plan (Opus spec → narrow Sonnet units, isolated worktrees → Gemini freshness/coverage audit → merge)
Decompose into **narrow, independently-testable units** (each: Sonnet impl + independent Sonnet tests in
separate worktrees, Opus reconcile, spec as arbiter — the G2C-006 pattern that caught real bugs):
- **Unit 1 — Catalog store/DAL:** `system_catalog_store.py` — schema (§C), migrations, scan-scoped writes,
  `get_current_scan`, queries, `is_stale`. Metadata-only.
- **Unit 2 — Discovery + capture:** `discovery_scan.py` — registry load, read-only git branch/HEAD/dirty per
  repo+worktree, spec/queue/test/component/capability/handoff parsing, scan_id generation, coverage status.
- **Unit 3 — Consumers + pipeline:** rebuild Map Room + Graphify from the catalog, emit the Scan Receipt,
  PARTIAL-block, and the `run_discovery_scan` orchestration wiring 1→9.
Opus reconciles + integrates the units; **Gemini audits coverage (every registered repo represented) +
freshness (scan_id tying, dirty captured, no stale promotion) before merge**; cherry-pick onto
`codex/stress-fixes` ONLY on operator GO; re-verify the suite on the integrated branch (G2C pattern).

---

## H. Decisions (Opus — operator may override before dispatch)
- **D1 — scan scoping:** RECOMMEND **append-versioned by scan_id** (retain scan history; current = latest
  COMPLETE) over replace-per-scan — gives freshness/diff + an audit trail, matches the immutable-snapshot ethos.
- **D2 — catalog DB path:** `/home/openclaw/state/system_catalog/system_catalog.sqlite3` (injectable; sibling of
  the G2C store dir). Confirm.
- **D3 — registry-driven discovery:** authoritative repo list = `REPOSITORY_REGISTRY.md` (seeded from the 15),
  not blind auto-discovery — so missing repos are detectable as PARTIAL. Confirm.
- **D4 — consumer filenames:** keep `openclaw_filesystem_map_room_terrain.json` + `openclaw_filesystem_graphiffy.json`
  (now catalog-derived, scan_id-tagged) so existing readers keep working. Confirm vs new names.
- **D5 — C/D drives:** the audit found no repos on C/D; registry covers `/home/openclaw` + `/mnt/e`. Treat C/D as
  out of registry (note as a coverage_gap), not a blocker. Confirm.
