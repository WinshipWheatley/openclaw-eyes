# Dependency Owner Review

Review generated from File Path Dependency Scan v0 output.
This review separates active dependency pressure from historical/archive noise.

## Active Dependency Owners (High Risk)
- `dashboard_gen.py`
- `mac_eyes/Launchers/*` (`sync_operator_harness_to_mac.sh`, `sync_legal_planning_to_mac.sh`, `watch_legal_planning_to_mac.sh`)
- `OpenClaw_Watch` (Target directory for sync operations)

## Generated-Output / Historical References (Medium/Low Risk)
- `reports/mac_watch_index/`
- `MAC_WATCH_MARKDOWN_INDEX.md`
- `Operator Watch.md`
- `Right now.md` (Note: `dashboard_gen.py` writes to this, so it is a generated output but modifying it breaks the dashboard).
- Polish loop archive tasks mentioning absolute paths.

## Unknown / Manual Review Required
- `OpenClawShared`
- `OpenClawLegalPrivate`
- `/mnt/c/OpenClaw`
- `/mnt/c/OpenClawShared`
- `/mnt/c/OpenClawLegalPrivate`

## Conclusion
Cleanup remains explicitly blocked. The dependencies confirm that `mac_eyes` and `OpenClaw_Watch` are deeply integrated into active sync scripts and dashboards.
