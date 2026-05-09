# Targeted Dry-Run Candidate Move Plan v0

**Artifact Type:** Targeted Dry-Run Candidate Move Plan
**Status:** Read-only planning artifact. This map is **NOT execution authority**. It does not authorize moving, deleting, renaming, archiving, ingesting, or reorganizing files on the PC repo or Mac Watch surfaces.

## 0. Cleanup Posture
**CLEANUP REMAINS BLOCKED.**
This pass creates only Map Room/report artifacts. It does not implement a plugin, MCP, connector, runtime hook, Cassandra integration, or live cleanup workflow. Future execution requires a separate approved implementation slice.

## 1. Selected Cleanup Category
**Category:** Generated Report/Index Noise
**Why Lower Risk:** Unlike `mac_eyes`, `OpenClaw_Watch`, `dashboard_gen.py`, `Launchers`, or `Right now.md`, the generated watch index outputs (`reports/mac_watch_index/` and `MAC_WATCH_MARKDOWN_INDEX`) are not active runtime, dashboard, or sync dependencies. The dependency scan confirms that they are exclusively referenced by read-only planning maps, report JSONs, and the dependency scan output itself. No scripts or execution logic rely on their current hardcoded location to function.

## 2. Candidate Items
The following specific paths are selected for this dry-run plan:

- `reports/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.md` (Classification: **Generated-Output Reference**)
- `reports/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.json` (Classification: **Generated-Output Reference**)

*Note on excluded items:* `Right now.md`, `Operator Watch.md`, private roots (`OpenClawShared`, `OpenClawLegalPrivate`, `/mnt/c/*`), and system boundaries (`mac_eyes`, `OpenClaw_Watch`, `Launchers`, `dashboard_gen.py`) are strictly excluded and mapped as Unsafe or Unknown/Manual Review.

## 3. Proposed Destination Shape
**Destination Paths (Candidate-only):**
- Candidate Destination: `reports/archive/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.md`
- Candidate Destination: `reports/archive/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.json`

*(These are candidate-only. No actual moves are being executed.)*

## 4. Dependency Evidence
- **Findings from Dependency Scan v0:** The scan identified 30 matches for `reports/mac_watch_index` and 46 matches for `MAC_WATCH_MARKDOWN_INDEX`.
- **References:** The terms appear exclusively in:
  - `docs/navigation_maps/DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md`
  - `docs/navigation_maps/FILE_TERRITORY_CLEANUP_READINESS_MAP.md`
  - `reports/file_path_dependency_scan/DEPENDENCY_OWNER_REVIEW.json`
  - `reports/file_path_dependency_scan/DEPENDENCY_OWNER_REVIEW.md`
  - `reports/file_path_dependency_scan/FILE_PATH_DEPENDENCY_SCAN.json`
  - `reports/file_path_dependency_scan/FILE_PATH_DEPENDENCY_SCAN.md`
- **Blocker Status:** The references exist entirely within documentation, mapping artifacts, and reports generated *after* the initial scan. Moving the files would simply require generating a fresh dependency scan and updating these reference paths in the maps to reflect the new location. There are **no active runtime or sync dependencies** blocking the move.

## 5. Dry-Run Commands
The following commands would preview the move impact only. **Do not execute them as real moves.**

```bash
# Dry-run copy with rsync to preview what would be moved
rsync -avn reports/mac_watch_index/ reports/archive/mac_watch_index/

# Dry-run echo confirmation
echo "Candidate move: reports/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.md -> reports/archive/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.md"
echo "Candidate move: reports/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.json -> reports/archive/mac_watch_index/MAC_WATCH_MARKDOWN_INDEX.json"
```

## 6. Validation Commands
Before and after any future approved move, the following receipts must be collected:

```bash
# 1. Run the dependency scan to ensure no new runtime references exist
python3 scripts/file_path_dependency_scan.py

# 2. Check for any remaining hardcoded strings referencing the exact old paths
grep -rn "reports/mac_watch_index" . --exclude-dir=.git --exclude-dir=node_modules
grep -rn "MAC_WATCH_MARKDOWN_INDEX" . --exclude-dir=.git --exclude-dir=node_modules

# 3. Verify repo boundary sanity
./scripts/openclaw_receipts.py repo-check

# 4. Verify test suite passes
PYTHONPATH=. pytest tests/test_file_path_dependency_scan.py -q
```

## 7. Rollback Plan
If an approved move fails or breaks a dependency unexpectedly:
1. **Restore Files:**
   ```bash
   # (Rollback execution plan only)
   rsync -av reports/archive/mac_watch_index/ reports/mac_watch_index/
   ```
2. **Update Maps:** Revert any navigation map updates.
3. **Re-run Tests:** Execute `python3 scripts/file_path_dependency_scan.py` and `./scripts/openclaw_receipts.py repo-check` to verify restoration.
4. **Log Incident:** Document the failure in `docs/navigation_maps/FILE_TERRITORY_CLEANUP_READINESS_MAP.md`.

## 8. Approval Gates
- **Operator Approval:** Explicit operator approval is strictly required before any physical move occurs.
- **Chief/Guardian Gate:** A formal sign-off is required before execution (if crossing into system zones, though this category is isolated).
- **No AI-Only Action:** AI agents may propose candidate moves but must **never** decide to perform actual cleanup independently based on files looking "stale."

## 9. Future Scaffolding Classification
This cleanup workflow consists of distinct layers, which should be separated in the future:
- **Map Room artifact (Current):** Durable truth about file territory, dependency pressure, candidate move posture, and cleanup gates.
- **Script:** Deterministic scans/checks that must not depend on model judgment, including path dependency scans, exact reference checks, dry-run validation, and report generation.
- **Skill:** Reusable human/agent procedure for reading Map Room artifacts and proposing cleanup plans without overstepping authority.
- **Plugin/workflow package:** Future bundled cleanup-readiness workflow combining Map Room reading, dependency scan scripts, candidate move-plan generation, validation commands, and approval gates.
- **MCP/connector:** Future access layer only if Cassandra needs controlled access to repo or file-system surfaces. MCP/connectors must not bypass Map Room truth, Covenant gates, or private-root boundaries.
- **Prompt:** One-off operator request only. The prompt should invoke the existing scaffold, not carry the whole process manually.
