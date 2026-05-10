# OpenClaw Generated Status Promotion Plan

## 1. Current State
- **Generated Read-Models Exist**: `Operator/GENERATED_CURRENT_STATE.md` and `Operator/GENERATED_NEXT_ACTIONS.md` are programmatically updated via `scripts/generate_operator_status.py`.
- **Legacy Surfaces**: Root `CURRENT_STATE.md` and `NEXT_ACTIONS.md` are manual, static, and prone to staleness.
- **Verification Tools**: `scripts/generate_operator_status.py --check` exists and verifies that the generated read-models match the current ledger and git state.
- **Cassandra Integration**: Cassandra already uses the generated read-models for `ops_status` inquiries, ensuring deterministic and read-only orientation responses.

## 2. Promotion Goal
- **Primary Source**: The generated status becomes the canonical operator-facing source for current state and next actions.
- **Legacy Demotion**: Legacy static files are safely demoted/archived without breaking existing references or workflows that depend on their file paths.
- **Zero Drift**: Ensure the operator is always looking at evidence-backed state rather than manual, potentially stale notes.

## 3. Safe Promotion Options
To transition from legacy files to generated files safely, the following options are proposed:
- **Warning Header**: Add a clear, high-visibility header to `CURRENT_STATE.md` and `NEXT_ACTIONS.md` stating they are legacy/static and pointing to the `Operator/GENERATED_*` files.
- **Redirect Pointer**: Replace the content of legacy files with a single pointer/link to the generated versions.
- **Archive Legacy**: Move legacy files to a `docs/archive/legacy_status/` directory once the generated files are universally accepted as the source of truth.
- **No Symlinks (Current Policy)**: Do not use symlinks at this stage to avoid potential cross-platform or toolchain issues until explicitly chosen as a strategy.

## 4. Acceptance Criteria
- **Generator Consistency**: `python scripts/generate_operator_status.py --check` must pass in all CI/verification loops.
- **No Manual Status Drift**: Edits to status must be performed via ledger events or evidence updates, not by manual editing of the generated files.
- **Orientation Snapshot Integrity**: `scripts/orientation_snapshot.py` and Cassandra's status replies must remain deterministic and based on the promoted surfaces.
- **Documentation Alignment**: `docs/INDEX.md` and other navigational docs must point users to the generated surfaces as the primary truth.

## 5. Non-Goals
- **No Runtime Activation**: This plan does not authorize live runtime health monitoring or automated recovery based on status.
- **No Cassandra Logic Changes**: No changes to Cassandra's `handle()` or intent classification are required by this promotion plan.
- **No Deletion/Symlinking**: Implementation of file deletion or symlinking is out of scope for this planning phase.
- **No Side Effects**: Promotion must remain read-only; no ledger writes or file mutations should occur during a status check.

## 6. Verification
Before final promotion, verify the state with:
```bash
python scripts/generate_operator_status.py --check
python scripts/inspect_business_ops_ledger.py --summary
git diff --check
```
