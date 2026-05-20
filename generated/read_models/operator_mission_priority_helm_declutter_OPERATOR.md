# Operator Mission Priority / Helm Declutter Taxonomy v0

Status:
- Deterministic metadata-only taxonomy.
- Backend/read-model contract only; no UI lane, execution lane, or integration lane.
- The Mac app should not render every read-model as an equal card.

## Current Mission
- Finish Mission Control into a clean, calm, usable helm so Winship can start working from it.
- Deadline label: `approximately_5_days_app_finish_sprint`.
- Helm mode: `DEVELOPER_MODE_BUILD_MODE`; target: `QUIET_OPERATIONAL_HELM`.

## Mission Success Conditions
- system health is obvious
- current build/developer work is organized
- worlds/domains are visible and ready to enter
- package/detour/proof flow is consistent
- operator stops mentally tracking the system manually

## What Belongs On The Helm
- `current_mission_app_finish`: Current mission: Mission Control app finish sprint | above_fold | Render the mission, mode, first attention item, and next safe move before any proof shelves.
- `system_awareness_discovery`: System Awareness / Discovery | visible_summary | Show the top lane and one immediate child/focus, not the whole nested tree.
- `agent_awareness_tracking`: Chief / Cassandra / Guardian / Niles / Hermes awareness tracking | collapsed_by_default | Collapse agent sublanes into the System Awareness parent unless one has a mission-relevant attention flag.
- `mission_control_visual_ux_app_finish`: Mission Control visual/UX and app finish work | above_fold | Render the next Mac UI change from this taxonomy rather than showing every backend artifact.
- `workbench_actor_host_registry`: Workbench / Actor Host Registry | visible_summary | Show a small routing summary; keep per-host proof and policies in detail.
- `package_preview_detour_flow`: Package preview / detour / proof flow | visible_summary | Show only orientation and next move above the fold; put package/proof lower.
- `design_memory_inventory`: Design memory inventory | collapsed_by_default | Keep as a bounded classification lane; do not ingest broad old archives here.

## What Belongs In Check Lights
- `check_engine`: Check Engine | status `WARNING` | Open the Chief diagnostic/system health lane when inspected.
- `check_transmission`: Check Transmission | status `ON` | Use the existing sync lifecycle to restore trusted/current mirror proof.
- `resources`: Resources | status `WARNING` | Show only if resource pressure materially affects the mission.
- `parking_brake`: Parking Brake | status `ON_NORMAL` | Show as intentional lock posture; do not imply malfunction.
- `traction_control`: Traction Control | status `QUIET` | Keep quiet unless a package is below deterministic confidence.

## What Belongs In Worlds
- `worlds_teleport_targets`: Worlds / domains as teleport targets | Worlds are places to enter after the helm is calm; they should not clutter the front door.

## What Belongs Only In Proof / Detail
- `raw_contracts_receipts_long_paths`: Raw contracts, receipts, paths, and machine proof | proof_detail_shelf
- `nested_lane_tree`: Deep nested lane tree | collapsed_by_default

## What Should Be Collapsed
- nested_lane_children
- agent_awareness_sublanes
- workbench_host_detail
- design_memory_inventory
- domain_world_detail

## What Should Be Worked First
- `1` `system_health_intelligible`: System health/check lights must be obvious and quiet when resolved.
- `2` `bridge_transmission_trusted`: PC/Mac bridge proof must be trusted before Mission Control can claim mirror current.
- `3` `helm_front_door_calm`: The helm front door must stop being a backend card wall.
- `4` `steel_thread_pattern_consistent`: Every lane/light/world should use orientation, proof, then package/detour path.
- `5` `workbench_actor_host_registry_clear`: Mission Control must know which tools do what before package launch is useful.
- `6` `package_preview_detour_flow`: Package preview/detour workflow must exist before live worlds matter.
- `7` `worlds_as_teleport_targets`: Worlds/domains should become compact destinations after the helm is clean.
- `8` `deep_domain_work_waits`: Deep domain work waits unless it blocks app finish.

## What Mission Control Should Render Next
- `mode_mission_health_strip`: Developer Mode / app finish sprint strip plus health-light row.
- `top_priority_next_move`: Show the top current priority and next safe move, not a full read-model wall.
- `system_awareness_single_focus`: Show active parent lane and one immediate focus child.
- `compact_world_launcher`: Render worlds/domains as compact teleport targets with attention badges only when relevant.
- `proof_detail_shelf`: Move raw contracts, receipts, long paths, machine proof, and package bodies behind inspect/drill-in affordances.

## What Should Not Be Built Yet
- live workflow execution
- all future worlds
- browser/OAuth/account integrations
- send/submit/approval flows
- full deep nested lane tree on the front door
- every read-model as an equal card

## Front Door Rule
- Above fold: mode_and_mission_strip, system_health_light_row, active_mission_next_safe_move, top_priority_stack_limited_to_current_mission, compact_world_launcher_hint.
- Proof shelf: raw_contracts_and_receipts, machine_proof, long_paths, source_refs, package_body_preview.
- Do not top-level: every_read_model_as_equal_card, deep_nested_lane_tree, raw_machine_tokens, receipt_rows, long_path_lists, future_gated_live_actions.

## Boundary
- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, C-drive artifact writes, deletes, cleanup, remount, or credential handling.

## SQLite / Ledger Receipt
- Existing safe pattern: `business_ops_ledger.record_receipt`.
- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.
- Secrets, credentials, raw private file bodies, raw logs, and broad file dumps are not stored.

## Next Safe Lane
- Mission Control Helm Declutter Readback Surface v0
