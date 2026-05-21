# Steel Thread Lane Template Registry v0

Status:
- Deterministic metadata-only template registry.
- Backend/read-model contract only; no UI lane, execution lane, or live integration lane.
- Mission Control should render one consistent workflow instead of inventing a new pattern per lane.

## Steel-Thread Pattern
- Top: ELI5 / operator orientation.
- Middle: machine contract / proof.
- Bottom: package / detour / fix path.

## Template Types
- `helm_lane`: Helm Lane | visible_summary
- `check_light_lane`: Check-Light Lane | health_light_row_when_on_or_warning
- `world_lane`: World Lane | compact_world_launcher_unless_attention
- `nested_lane`: Nested Lane | parent_plus_immediate_focus
- `proof_detail_lane`: Proof / Detail Lane | proof_shelf_only
- `package_preview_lane`: Package Preview Lane | visible_when_package_relevant
- `confidence_detour_lane`: Confidence Detour Lane | visible_only_when_confidence_blocks_or_changes_action
- `parked_lane`: Parked Lane | hidden_until_relevant_or_requested

## Top / Operator Layer
- what_is_this, why_it_matters, current_status, safe_next_move, operator_seconds_summary.

## Middle / Proof Layer
- read_model_refs, receipt_refs, marker_refs, evidence_refs, known, partly_known, unknown, stale, blocked, trusted_vs_not_yet_trusted, proof_that_would_make_quiet.

## Bottom / Package Layer
- package_preview, actor_model_candidate, agent_character, context_included, context_excluded, plugins_capabilities_tools_allowed, security_clearance, steps, stop_conditions, proof_receipt_must_return, confidence_state_if_below_deterministic, detour_that_raises_confidence, available_now_vs_future_gated.

## Allowed Now Controls
- `explain_this`, `what_can_i_do`, `raise_confidence`, `preview_package`, `show_proof`, `inspect_detail`.

## Future-Gated Controls
- `future_chat_workspace_target`.

## Capture Preview Controls
- `tell_system_whats_missing`, `keep_parked`.

## Confidence Behavior
- Below deterministic: show confidence issue, missing evidence, and detours.
- Deterministic/full trust: hide confidence score and detour UI.
- Failed deterministic job: reset confidence and surface proof failure/detours.

## Quiet Behavior
- Lanes become quiet when proof is deterministic or blocker/parking is intentional and no attention is needed.
- Do not display confidence theater when proof is deterministic.

## Mac Rendering Guidance
- Render operator orientation first.
- Put machine proof and package bodies behind Show Proof, Preview Package, Raise Confidence, or Inspect Detail.
- Nested lanes show active parent, immediate focus, and next safe move by default.
- Do not make the helm a backend inventory or card browser.

## What Should Not Be Built Yet
- live execution controls
- send/submit/approval controls
- model or agent calls from buttons
- tool or plugin execution from buttons
- remount or credential handling
- generated read-model mutation controls
- SQLite mutation controls beyond metadata-only receipts
- broad file write controls
- PC C-drive artifact writes
- cleanup/delete/repair controls

## Boundary
- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, generated read-model mutation controls, SQLite mutation controls, C-drive artifact writes, deletes, cleanup, repair, remount, or credential handling.

## SQLite / Ledger Receipt
- Existing safe pattern: `business_ops_ledger.record_receipt`.
- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.
- Secrets, credentials, raw private file bodies, raw logs, and broad file dumps are not stored.

## Next Safe Lane
- Mission Control Steel Thread Template Readback Surface v0
