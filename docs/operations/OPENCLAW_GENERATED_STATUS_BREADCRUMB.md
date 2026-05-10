# OpenClaw Generated Status Breadcrumb

## Overview
This document captures the future direction for replacing stale, hand-edited status files like `CURRENT_STATE.md` and `NEXT_ACTIONS.md` with deterministic, generated read-models.

## Current Limitations
- `CURRENT_STATE.md` and `NEXT_ACTIONS.md` are legacy/static surfaces.
- They are prone to going stale quickly as they require manual updates.
- They should not be treated as durable authority in their current form.

## Future Direction: Generated Status
Future current-state and next-actions surfaces should be generated programmatically rather than manually maintained.

### Inputs for Generation
The generated read-models should be sourced from:
- **SQLite Ledger Receipts:** Confirmed events and state transitions (e.g., `orientation_snapshot_receipt` receipts).
- **Repository Evidence:** `git HEAD`, `git status`, and committed source.
- **Orientation Contract/Snapshot:** Doctrine compliance and high-level orientation.
- **Runtime/Readiness Maps:** Verified health and capability checks.
- **Test Results:** Empirical validation of system state.
- **Explicit Operator Promotions:** Manually verified and promoted state checkpoints.

### Output Requirements
- **Marked as Generated:** Must include a clear disclaimer, timestamp, source commit hash, and listing of source tables/documents.
- **Staleness Conditions:** Must define conditions under which the output should be considered stale or invalid.
- **Privacy & Security:** Must not store or print raw sensitive data (e.g., PII, raw email bodies). Use hashes or redaction where necessary.
- **Runtime Health:** Must not imply live runtime health unless an explicit, fresh check has been performed.

### Content Structure
Generated status should clearly separate:
1. **confirmed_current:** Evidence-backed state of the system.
2. **historical_context:** Recent events and transitions leading to the current state.
3. **blocked_or_unknown:** Areas where evidence is missing or conflicts exist.
4. **next_safe_move:** Recommended actions based on doctrine and current state.
5. **visible_road_horizon:** Bounded near-term moves, stop boundary, and evidence required to extend the horizon.

## Stopping Boundaries
This breadcrumb is for planning and direction only. It **does not** authorize:
- Implementation of generation tools.
- Scheduler writes or runtime mutations.
- Ledger schema changes or broad database migrations.
- Integration with Cassandra or Chief for automated status reporting.
- Replacement of existing `CURRENT_STATE.md` or `NEXT_ACTIONS.md` files yet.
