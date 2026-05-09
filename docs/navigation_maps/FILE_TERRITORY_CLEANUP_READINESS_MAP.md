# File Territory / Cleanup Readiness Map

**Artifact Type:** File Territory / Cleanup Readiness Map
**Status:** Read-only planning artifact. This map is **not execution authority**. It does not authorize moving, deleting, renaming, archiving, ingesting, or reorganizing files on the PC repo or Mac Watch surfaces.

## 1. Mac Watch Index Status
Mac Watch markdown files are only **partly indexed**.
- The `MAC_WATCH_MARKDOWN_INDEX.md` confirms 537 files were indexed, but this covers **markdown files only**.
- Non-markdown files, nested structures, and their dependencies remain unknown.

## 2. Repo-Side Cleanup Readiness
Repo-side folders are **not cleanup-ready**.
- Scripts and sync logic heavily depend on these folders (e.g., 52 references to `OpenClaw_Watch`, 120 references to `mac_eyes`, 43 references to `dashboard_gen.py`).
- No cleanup can begin until a comprehensive cross-repository dependency map resolves all hardcoded paths.

## 3. Known Mac Watch / Watch-Surface Categories
Based on the partial index, the watch surfaces contain:
- Generated watch surfaces
- Dashboards / current status files
- Handoffs / checkpoints
- Source-set mirrors
- Research / scratch / support files
- Stale candidates
- Active or dependency-sensitive paths

## 4. Known Repo-Side Territory
The PC repository is divided into explicit lanes:
- **Source code:** Functional python scripts.
- **Docs/source-set authority:** `docs/` containing doctrinal truth, planning packets, and Navigation Maps.
- **Reports/generated output:** `reports/` and index receipts.
- **Tests/proof:** `tests/` for validation and static contracts.
- **Sidecars/external references:** `mac_eyes/` and specific project handoffs.
- **Ignored/noisy/runtime/private/sensitive areas:** Private roots, `.google-secrets/`, `.chief.env`, and hidden configurations.

## 5. Blockers Before Cleanup
The following steps block any file reorganization or cleanup:
- Path dependency scan (must capture all references to targeted folders).
- Generated-vs-source classification.
- Active dashboard / watch file identification.
- Stale / scratch / archive candidate review.
- Dry-run move plan.
- Rollback plan.
- Validation commands (to prove scripts won't break).

## 6. Cleanup Gates
No cleanup can proceed unless it passes these strict gates:
- No move unless the path-dependency scan is clean.
- No delete without an archive/rollback strategy.
- No rename if scripts, sync tools, or dashboard paths reference it.
- No private-root traversal.
- No generated output promoted to source authority.
- No AI-only "looks stale" decisions.

## 7. Next Safe Edge
- **Completed:** A read-only dependency/reference scan has been built and executed. See `reports/file_path_dependency_scan/FILE_PATH_DEPENDENCY_SCAN.md` for results.
- **Completed:** Dependency owners reviewed and risk classified. See [Dependency Owner Candidate Move Map](./DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md).
- **Completed:** Formulated targeted, dry-run candidate move plans for specific safe categories with explicit validation commands and rollback procedures. See [Targeted Dry-Run Candidate Move Plan v0](./TARGETED_DRY_RUN_CANDIDATE_MOVE_PLAN_V0.md).
- **Completed:** Built Map Room Query layer (`map_room_query.py`) to answer file territory queries directly from durable truth.
- Proposed cleanup actions must remain candidate-only.
