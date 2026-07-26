Chief Check-Engine Environment Posture v0

Status:
- Check Engine: ON
- Overall posture: blocked
- Issue type: system/workbench reliability, not a normal domain lane.

Why:
- Google access is down. Every capability behind the shared authorisation fails together: inbox reads, calendar reads, and outbound Gmail send.
- The PC C: drive recently reached critical free-space pressure before conservative cleanup.
- The main recovered space came from Remote Desktop-style ETL trace growth, not from Repo A generated artifacts.
- The expected Mac mount for the Windows E: OpenClaw shuttle is missing, so the normal Mac bridge cannot be treated as complete.
- Canonical sync health is not currently proving full Mac mirror completion for the latest expected read-model set.
- Operator report says the Mac local mirror had 194 files after a helper pull, while PC proof still observed fewer files.
- Mac Codex/Desktop work is slow and hard to track, making operator validation less reliable.
- Window, screenshot, and app-launch validation has been fragile enough to degrade proof gathering.

Degraded:
- PC/WSL storage pressure risk from recent C: free-space collapse.
- Remote Desktop-style trace growth may recur outside Repo A.
- Mac shuttle/mirror completion proof is stale or incomplete.
- Mac Codex/Desktop validation is slow or fragile.

Safe Next Step:
- Chief Check-Engine Diagnostic Packet: compare disk-pressure posture, RD trace-growth clue, Mac mount status, sync proof, and workbench validation friction without repair authority.

Do Not:
- delete files or caches from this lane
- touch swap.vhdx
- delete NVIDIA, Ableton, StarCraft, broad Temp, or unknown app caches
- write OpenClaw artifacts to C:
- remount Mac shares or enter remount credentials
- mutate Mission Control app code
- activate agents, call models, wire plugins, or run live chats
- send or submit messages, approvals, email, Telegram, Gmail, calendar, or Coupa actions
- store raw private logs, credentials, broad temp listings, or raw private file bodies

Signals:
- google_access_authorisation_health: blocked - Google access is down. Every capability behind the shared authorisation fails together: inbox reads, calendar reads, and outbound Gmail send. (lights Check Engine).
- c_drive_free_space_low: warning - The PC C: drive recently reached critical free-space pressure before conservative cleanup. (lights Check Engine).
- rd_client_trace_growth: warning - The main recovered space came from Remote Desktop-style ETL trace growth, not from Repo A generated artifacts. (lights Check Engine).
- shuttle_mount_missing: blocked - The expected Mac mount for the Windows E: OpenClaw shuttle is missing, so the normal Mac bridge cannot be treated as complete. (lights Check Engine).
- sync_completion_proof_stale: warning - Canonical sync health is not currently proving full Mac mirror completion for the latest expected read-model set. (lights Check Engine).
- mac_local_mirror_ahead_of_pc_proof: warning - Operator report says the Mac local mirror had 194 files after a helper pull, while PC proof still observed fewer files. (lights Check Engine).
- codex_mac_latency_or_validation_friction: warning - Mac Codex/Desktop work is slow and hard to track, making operator validation less reliable. (lights Check Engine).
- launch_window_screenshot_fragility: warning - Window, screenshot, and app-launch validation has been fragile enough to degrade proof gathering. (lights Check Engine).
- no_c_drive_write_policy: ok - OpenClaw artifacts should stay in Repo A and established E: shuttle paths, not on the PC C: drive. (does not light Check Engine).

Chief Package Preview:
- Character: Chief
- Actor/model: unspecified_candidate_not_live
- Mission: Diagnose environment, bridge, and tooling degradation without repair authority.
- Capabilities: inspect-only/read-only diagnostics.
- Dispatchable now: false.
- Future-gated: true.

Storage Boundary:
- OpenClaw artifacts must not be written to C:.
- Generated output remains under `generated/read_models/` in Repo A.
- C: references here are evidence labels only, not artifact targets.

SQLite Evidence Record:
- Existing safe pattern: `business_ops_ledger.record_receipt`.
- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.
- Raw logs, credentials, broad temp listings, and private file bodies are not stored.

Future-Gated:
- Delete/cleanup, remount, credentials, app mutation, live agents, model calls, sends/submits, and runtime execution.

Next Lane:
- Chief Check-Engine Diagnostic Package v0: Turn this posture into an inspect-only Chief diagnostic package that compares current PC/Mac proof, without cleanup, remount, credentials, app mutation, or runtime execution.
