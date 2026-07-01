# Dirty Worktree Audit - 2026-07-01

## Executive Summary
- **Release refs status**: All 4 release refs (`local main`, `origin/main`, `local codex/stress-fixes`, `origin/codex/stress-fixes`) are confirmed identically matched at `814259044ad3dbe6c482757da2df45e4e98f82a3`.
- **Dirty item counts by category**:
  - `SAFE_IGNORE_RUNTIME_CHURN`: 3 items (polish loop runtime state)
  - `GENERATED_READ_MODEL_CHURN`: 21 items (generated models and schemas)
  - `SOURCE_CHANGE_NEEDS_REVIEW`: 5 items (code and service files)
  - `OPERATOR_PACKET_OR_REPORT`: 19 untracked items
  - `STALE_DELETE_OR_ARCHIVE_CANDIDATE`: 4 deleted items (processed task files)
  - `POSSIBLE_SECRET_OR_SENSITIVE_DO_NOT_PRINT`: 0 items explicitly detected
  - `UNKNOWN_NEEDS_OPERATOR_DECISION`: 0 items
- **Highest-risk dirty items**: `google_access_broker.py` and `systemd/user/hermes-gateway.service.in` (OAuth credential parsing pathways and mock environment toggles).
- **Recommended next action**: Review and selectively commit the source/service diffs, commit the deletion of processed tasks, and leave generated models alone as they churn natively.

## Ref Verification
- local `main`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- remote `origin/main`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- local `codex/stress-fixes`: `814259044ad3dbe6c482757da2df45e4e98f82a3`
- remote `origin/codex/stress-fixes`: `814259044ad3dbe6c482757da2df45e4e98f82a3`

## Dirty State Categories

### `SOURCE_CHANGE_NEEDS_REVIEW`
- `google_access_broker.py` (M): New OAuth environment variable parsing logic.
- `polish_loop/control_plane.py` (M): Mock dispatch toggle added for testing.
- `polish_loop_backlog_ingest.py` (M): Minor parsing cleanup.
- `systemd/user/hermes-gateway.service.in` (M): Mock dispatch environment toggle explicitly added.
- `workspaces/gig_to_cash_audit/ORCHESTRATOR_HANDOFF.md` (M): Comprehensive audit and handoff documentation rewrite.
Rationale: Core system file modifications requiring explicit review before integrating into the mainline repository.

### `GENERATED_READ_MODEL_CHURN`
- 17 modified `.json` and `.md` models in `generated/read_models/`
- 3 untracked `.json` models in `generated/read_models/`
- 1 modified `.sql` seed in `generated/system_knowledge/`
Rationale: Safe, expected read-model churn caused by the backend processing events and dynamically regenerating materializations during tests/runs.

### `SAFE_IGNORE_RUNTIME_CHURN`
- `polish_loop/status.json` (M)
- `polish_loop/task.md` (??)
- `polish_loop/tasks/` (??)
Rationale: Transitory operational state data created by the active Polish Loop processes.

### `STALE_DELETE_OR_ARCHIVE_CANDIDATE`
- `Operator/to-gemini/NAMING-AUDIT-1-HIGH.md` (D)
- `Operator/to-gemini/NAMING-AUDIT-2-MID.md` (D)
- `Operator/to-gemini/NAMING-AUDIT-3-DETAIL.md` (D)
- `Operator/to-gemini/PACKET-HEALTH-FOLLOWUPS-AUDIT.md` (D)
Rationale: Already consumed tasks that were moved to the `done` folder, leaving the repository tracking their deletion.

### `OPERATOR_PACKET_OR_REPORT`
- 19 untracked `.md` reports in `Operator/` (e.g., `CODEX-*`, `GEMINI-*`, `SKILLS-*`, `POLISH-LOOP-*`)
Rationale: Operational reports, logs, and task files created by agents and the operator during prior workloads.

## Source/Service Diff Review

1. `google_access_broker.py`
   - **Type:** Modified
   - **Summary:** Adjusts Google OAuth secret loading to explicitly check for environment variables and gracefully parse `.chief.env` structures if the main secrets file is missing.
   - **Risk:** Medium. Alters how credentials are read. Does not expose secrets in plain text, but directly affects authentication pathways.
   - **Recommended disposition:** Operator decision (commit if OAuth CLI support via environment variables is the current objective).

2. `polish_loop/control_plane.py`
   - **Type:** Modified
   - **Summary:** Introduces a `POLISH_LOOP_MOCK_DISPATCH_ONLY` environment variable check to bypass active agent invocation and simply return simulated success.
   - **Risk:** Low. Safe feature toggle primarily for test scaffolding.
   - **Recommended disposition:** Commit.

3. `polish_loop_backlog_ingest.py`
   - **Type:** Modified
   - **Summary:** Clean up of parameter extraction logic during ingest packet parsing.
   - **Risk:** Low. No architectural impact.
   - **Recommended disposition:** Commit.

4. `systemd/user/hermes-gateway.service.in`
   - **Type:** Modified
   - **Summary:** Hardcodes `Environment=POLISH_LOOP_MOCK_DISPATCH_ONLY=1` into the service file.
   - **Risk:** Medium. Will globally mock dispatch behaviors if this service file is deployed to production or shared staging environments.
   - **Recommended disposition:** Operator decision (discard if this is just for local testing; commit only if creating a dedicated mocked environment).

5. `workspaces/gig_to_cash_audit/ORCHESTRATOR_HANDOFF.md`
   - **Type:** Modified
   - **Summary:** Overwrote the previous "Gig-to-Cash" orchestration details with a comprehensive "Durability and Lifecycle" audit, outlining schema extension steps for `system_catalog`.
   - **Risk:** Low technical risk, but high project management impact (changes the pointer for the next scheduled work).
   - **Recommended disposition:** Commit (safely preserves recent agent audit output).

## Generated/Runtime Churn
- **Counts**: 21 files across `generated/` and 3 runtime files across `polish_loop/`.
- **Recommended handling**: Leave them unmodified and uncommitted in the working tree. They are safely generated from the canonical ledger and will continue to churn. Can be mass-committed in a chore bundle later if snapshotting is required.

## Operator Docs/Packets
- **Files**: 19 untracked markdown documents located in `Operator/`.
- **Nature**: These appear to be highly durable work-order documents, handover protocols, and audit results generated during extensive recent sessions.
- **Recommended handling**: Keep untracked for now. The operator should review and manually commit them as a documentation/history record once the current operational sprint is fully concluded.

## Sensitive/Secret Check
- No clear occurrences of raw tokens, credentials, or `.chief.env` contents are exposed in the Git diffs or untracked file listings.
- The `google_access_broker.py` change explicitly handles environment variable names but does not leak any secret keys.

## Recommended Cleanup Plan
1. **Commit verified source changes**: Commit `polish_loop/control_plane.py`, `polish_loop_backlog_ingest.py`, and `ORCHESTRATOR_HANDOFF.md`.
2. **Review security/service toggles**: Operator must explicitly review the mock environment variable in `systemd/user/hermes-gateway.service.in` and the OAuth changes in `google_access_broker.py`.
3. **Commit task deletions**: Stage and commit the deletion of the processed `to-gemini` queue items.
4. **Persist docs**: Commit the 19 untracked `Operator/` files as a single documentation chore commit if they are finalized.
5. **Ignore churn**: Leave `generated/` and `polish_loop/` state files uncommitted to churn naturally.
