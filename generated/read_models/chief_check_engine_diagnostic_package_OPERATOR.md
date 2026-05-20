Chief Check-Engine Diagnostic Package v0

Status:
- Check Engine: ON
- Current status: `blocked_needs_chief_diagnostic_package`
- Package authority: inspect-only, no repair authority.

Why Check Engine Is On:
- Workbench/bridge proof is degraded enough to need a Chief diagnostic package.
- The current issue is system/workbench reliability, not normal domain lane attention.

What Degraded:
- c_drive_free_space_pressure: PC C: drive free-space pressure (warning, HIGH_TRUST)
- rd_client_trace_growth: RD Client trace growth (warning, MEDIUM_TRUST)
- shuttle_mount_missing: Mac shuttle mount missing (blocked, HIGH_TRUST)
- sync_proof_stale: Sync proof stale (warning, HIGH_TRUST)
- mac_local_mirror_vs_pc_proof_mismatch: Mac local mirror vs PC proof mismatch (warning, MEDIUM_TRUST)
- mac_codex_latency_validation_friction: Mac Codex latency and validation friction (warning, MEDIUM_TRUST)
- screenshot_window_validation_fragility: Screenshot/window validation fragility (warning, MEDIUM_TRUST)
- no_c_drive_write_policy: No C: drive write policy (ok, HIGH_TRUST)

Evidence:
- posture_json: observed - Chief Check-Engine Environment Posture read-model.
- posture_operator: observed_reference - Operator-readable posture output; body is not embedded in this package.
- sync_health_json: observed - Current PC/WSL canonical sync-health proof read-model.
- sync_health_operator: observed_reference - Operator-readable sync-health output; body is not embedded in this package.
- operator_storage_report: operator_reported - Operator-reported C: drive cleanup and RD trace culprit summary.
- operator_mac_bridge_report: operator_reported - Operator-reported missing Mac shuttle mount and helper-pull context.
- operator_sync_checkpoint: operator_reported - Checkpoint sync facts before this diagnostic package added new generated files.
- operator_workbench_report: operator_reported - Operator-reported Mac Codex/Xcode/UI validation latency and fragility.
- operator_storage_policy: operator_policy - No OpenClaw artifacts should be written to PC C: in this workflow.

Likely Vs Unknown:
- Likely: rd_client_trace_growth_external_to_repo_a (MEDIUM_TRUST); not proven: not proven as an OpenClaw code loop.
- Likely: mac_shuttle_mount_unavailable (HIGH_TRUST); not proven: root cause of missing Mac mount is not known.
- Likely: mac_workbench_validation_friction (MEDIUM_TRUST); not proven: specific Mac tooling bottleneck is not isolated.
- Unknown: current live C: free space was not re-measured by this package.
- Unknown: whether RD Client trace growth will recur.
- Unknown: why /Volumes/openclaw_e is missing on Mac.
- Unknown: whether Mac-local helper files match canonical shuttle proof.
- Unknown: which Mac-side component causes validation latency or window-state fragility.

Inspect First:
- sync_proof_stale
- shuttle_mount_missing
- mac_local_mirror_vs_pc_proof_mismatch
- c_drive_free_space_pressure

Safe Diagnostic Steps:
- inspect_current_read_models: Inspect current posture and sync read-models (read_only_metadata).
- compare_operator_report_to_observed_proof: Compare operator-reported facts against observed PC proof (classification_only).
- separate_bridge_from_app_correctness: Separate Mac bridge/workbench failure from Mission Control app correctness (diagnostic_reasoning_only).
- identify_manual_operator_action: Identify whether Winship must manually restore/check the Mac mount (operator_question_only_if_needed).

Must Not Do:
- delete files or caches from this lane
- touch swap.vhdx
- delete NVIDIA, Ableton, StarCraft, broad Temp, or unknown app caches
- write OpenClaw artifacts to C:
- remount Mac shares or enter remount credentials
- mutate Mission Control app code
- activate agents, call models, wire plugins, or run live chats
- send or submit messages, approvals, email, Telegram, Gmail, calendar, or Coupa actions
- store raw private logs, credentials, broad temp listings, or raw private file bodies
- repair backend services from this package
- auto-remount /Volumes/openclaw_e
- handle or store remount credentials
- inspect raw private logs, raw ETL trace contents, or broad Temp listings
- start browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows
- call models or activate agents

Winship Manual Action:
- Required now by this package: `false`
- May be needed if: /Volumes/openclaw_e remains unavailable or Mac sync proof does not advance

What Would Make Check Engine Quiet:
- C: drive remains safely above pressure thresholds and no OpenClaw artifact target writes to C:.
- RD Client trace growth is stable or has a bounded external explanation.
- /Volumes/openclaw_e is available on Mac or the missing mount has a documented non-actionable lifecycle state.
- sync_health reports missing_expected=0 and hash_mismatch=0 for the current expected set.
- Mac-local mirror, Mac manifest/completion, and PC import proof agree.
- Mac Codex/Xcode build/launch/screenshot validation becomes predictable enough to track.

Future-Gated:
- Repair, cleanup, remount, credential handling, app mutation, runtime execution, model calls, agents, browser/OAuth, Gmail/calendar/Coupa/Telegram, send/submit/approval.

Storage Boundary:
- OpenClaw artifacts must not be written to C:.
- Generated output remains under `generated/read_models/` in Repo A.
- C: references here are evidence labels only, not artifact targets.

Expected Chief Output Later:
- plain-language diagnosis
- evidence table with observed/operator-reported/inferred/unknown distinctions
- blocked actions
- safe next diagnostic move
- manual operator action if required
- what would make Check Engine quiet
