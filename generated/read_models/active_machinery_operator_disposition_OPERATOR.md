# Active Machinery Operator Disposition v0

Status:
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Repo B executed: `false`.
- Gemini output treated as truth: `false`.

## Summary
- High-risk items reviewed: `17`.
- Test-only high-risk items: `3`.
- Live/script high-risk items: `14`.
- Dispositions: `{'block_no_go': 5, 'keep_test_only': 3, 'replace_with_governed_path': 4, 'retire_later': 2, 'wrap_with_guardian': 3}`.

## High-Risk Item Dispositions
### `builder_watcher.sh`
- Disposition: `block_no_go`.
- Risk: `high`; type: `daemon_listener`.
- Affects: remote builder.
- Why it matters: Verified watcher/daemon signals on a builder surface; legacy watchdog-style build loops should not run outside a governed Operator Action packet.
- Static evidence: daemon_listener, importer_exporter, path_daemon_listener_hint.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: no external send capability proven from safe static signals.
- Before it can run: Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher.

### `cassandra_listener.py`
- Disposition: `replace_with_governed_path`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Cassandra, Guardian/HITL, send paths, sync.
- Why it matters: Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener.
- Static evidence: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api, shell_or_process, sync_bridge.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use.

### `cassandra_watcher.py`
- Disposition: `retire_later`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Cassandra, send paths.
- Why it matters: Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows.
- Static evidence: daemon_listener, importer_exporter, mcp_tool_plugin_surface, path_daemon_listener_hint, send_external_api, shell_or_process.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Prove it is still needed; otherwise retire after equivalent governed path is confirmed.

### `chief_brainstorm_watcher.py`
- Disposition: `retire_later`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Chief.
- Why it matters: Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path.
- Static evidence: daemon_listener, importer_exporter, path_daemon_listener_hint, state_mutator.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate local state or generated artifact mutation; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: no external send capability proven from safe static signals.
- Before it can run: Keep disabled until an operator-approved use case proves it should become a governed Work Board source.

### `chief_email_brain.py`
- Disposition: `wrap_with_guardian`.
- Risk: `high`; type: `send_external_api`.
- Affects: Chief, Guardian/HITL, send paths.
- Why it matters: Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved.
- Static evidence: approval_hitl, importer_exporter, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior.

### `chief_guardian_listener.py`
- Disposition: `replace_with_governed_path`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Chief, Guardian/HITL, send paths, sync.
- Why it matters: Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract.
- Static evidence: approval_hitl, daemon_listener, importer_exporter, path_approval_hitl_hint, path_daemon_listener_hint, send_external_api, sync_bridge.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists.

### `chief_guardian_sender.py`
- Disposition: `wrap_with_guardian`.
- Risk: `high`; type: `send_external_api`.
- Affects: Chief, Guardian/HITL, send paths.
- Why it matters: Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries.
- Static evidence: approval_hitl, importer_exporter, path_approval_hitl_hint, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Allow only approved notification packets and receipts; no raw or freeform send authority.

### `chief_listener.py`
- Disposition: `replace_with_governed_path`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Chief, Guardian/HITL, send paths, sync.
- Why it matters: Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority.
- Static evidence: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, scheduler_watchdog, send_external_api, shell_or_process, sync_bridge.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Prove caller scope, HITL boundary, and receipt path before live listener activation.

### `chief_sender.py`
- Disposition: `wrap_with_guardian`.
- Risk: `high`; type: `send_external_api`.
- Affects: Chief, send paths.
- Why it matters: Verified send/API signals on a sender surface; external sends require Guardian/operator approval.
- Static evidence: importer_exporter, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Require approved immutable packet, recipient binding, no raw command text, and receipt proof.

### `chief_watcher_brain.py`
- Disposition: `block_no_go`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Chief, Guardian/HITL.
- Why it matters: Verified watcher plus shell/process signals; this is too risky to run as active machinery without a replacement contract.
- Static evidence: approval_hitl, daemon_listener, importer_exporter, path_daemon_listener_hint, shell_or_process, state_mutator.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate local state or generated artifact mutation; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: no external send capability proven from safe static signals.
- Before it can run: Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly.

### `producer_listener.py`
- Disposition: `replace_with_governed_path`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Producer/Niles, send paths, sync.
- Why it matters: Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime.
- Static evidence: daemon_listener, importer_exporter, path_daemon_listener_hint, scheduler_watchdog, send_external_api, shell_or_process, sync_bridge.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Define Producer/Niles module boundary and route actions through Guardian/HITL before activation.

### `retry_send_demo_dashboard.sh`
- Disposition: `block_no_go`.
- Risk: `high`; type: `send_external_api`.
- Affects: send paths.
- Why it matters: Verified send-path signal on a shell demo/retry surface; demos must not become live send machinery.
- Static evidence: path_send_api_hint.
- Capability posture: reads: no read capability proven from safe static signals; writes: no write capability proven from safe static signals; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Keep as blocked unless replaced by a no-send proof fixture or explicitly approved bounded demo.

### `scripts/run_producer_listener.sh`
- Disposition: `block_no_go`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Producer/Niles.
- Why it matters: Verified launcher for listener machinery; shell launchers should not activate daemons outside governed runtime approval.
- Static evidence: daemon_listener, path_daemon_listener_hint.
- Capability posture: reads: no read capability proven from safe static signals; writes: no write capability proven from safe static signals; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: no external send capability proven from safe static signals.
- Before it can run: Do not run until Producer listener has a governed contract and operator-approved activation lane.

### `send_demo_dashboard.py`
- Disposition: `block_no_go`.
- Risk: `high`; type: `send_external_api`.
- Affects: send paths.
- Why it matters: Verified send/API signal on a demo dashboard sender; demo send paths should remain blocked.
- Static evidence: importer_exporter, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Replace with read-only dashboard proof or approved no-send review artifact.

### `tests/test_cassandra_email_thread_analysis.py`
- Disposition: `keep_test_only`.
- Risk: `high`; type: `send_external_api`.
- Affects: Cassandra, send paths.
- Why it matters: The file is under tests/; treat it as test-only unless a later audit proves it exposes a live unsafe path.
- Static evidence: importer_exporter, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Run only as a focused test under normal test validation; never treat it as runtime machinery.

### `tests/test_chief_listener_lifecycle.py`
- Disposition: `keep_test_only`.
- Risk: `high`; type: `daemon_listener`.
- Affects: Chief, send paths, sync.
- Why it matters: The file is under tests/; treat it as test-only unless a later audit proves it exposes a live unsafe path.
- Static evidence: daemon_listener, importer_exporter, path_daemon_listener_hint, send_external_api, state_mutator, sync_bridge.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate local state or generated artifact mutation; executes: safe static signals indicate listener/watcher/scheduler runtime behavior; sends: safe static signals indicate external send/API posture.
- Before it can run: Run only as a focused test under normal test validation; never treat it as runtime machinery.

### `tests/test_send_truth.py`
- Disposition: `keep_test_only`.
- Risk: `high`; type: `send_external_api`.
- Affects: send paths.
- Why it matters: The file is under tests/; treat it as test-only unless a later audit proves it exposes a live unsafe path.
- Static evidence: importer_exporter, path_send_api_hint, send_external_api.
- Capability posture: reads: safe static signals indicate local file/generated read-model metadata access; writes: safe static signals indicate importer/exporter or sync output behavior; executes: no execution capability proven from safe static signals; sends: safe static signals indicate external send/API posture.
- Before it can run: Run only as a focused test under normal test validation; never treat it as runtime machinery.

## Major Machinery Groups
- `verified_high_risk_active_machinery` (17): `operator_decision_required` - Use the high-risk item table; tests stay test-only, live listeners/senders need governed replacement or Guardian wrapping.
- `likely_active_machinery_needing_operator_review` (76): `operator_decision_required` - Run a later no-execution static review lane by subgroup: HITL, sync, importer/exporter, and plugin/tool surfaces.
- `false_positives_safe_docs_generated_files` (316): `keep_canonical` - Keep as documentation/generated artifacts unless a future lane proves a specific file is executable.
- `repo_b_reference_only_machinery` (1): `keep_reference_only` - Inspect only as reference in explicit reconciliation lanes; never execute Repo B code.
- `send_api_surfaces` (7): `wrap_with_guardian` - Keep no-send by default; require immutable packet, exact binding, Guardian approval, and receipts.
- `sync_bridge_surfaces` (151): `operator_decision_required` - Review safe canonical sync paths separately from launchers/watchers before any activation.
- `approval_hitl_surfaces` (134): `replace_with_governed_path` - Reconcile legacy paths against current Guardian/HITL contract before any caller switch.
- `unknown_needs_deeper_review` (357): `operator_decision_required` - Leave untouched until a narrower static review lane is approved.

## Operator Decisions Needed
- Approve which legacy listener/watcher surfaces should be replaced, retired, or blocked.
- Approve whether any send/API surface should receive a Guardian-wrapped no-send-to-send transition lane.
- Approve a separate sync/bridge disposition lane before any launcher or watcher is activated.
- Approve HITL surface convergence before any caller switch or old JSON retirement.

## Next Safe Move
- Active Machinery High-Risk Quarantine Spec v0
