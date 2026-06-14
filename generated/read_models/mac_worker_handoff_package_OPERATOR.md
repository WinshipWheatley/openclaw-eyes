# PC-to-Mac Worker Handoff Package

Status: DETERMINISTIC_PC_TO_MAC_WORKER_HANDOFF_PACKAGE_NO_EXECUTION
Output path: /mnt/e/openclaw/mission_control_handoffs/to_mac
Mac-visible path: /Volumes/openclaw_e/mission_control_handoffs/to_mac

Examples:
- Mac UI: MAC_CODEX / package created: True
- Xcode build: MAC_XCODE_BUILD / package created: True
- Visual workspace: MAC_VISUAL_WORKSPACE / package created: True
- Blocked Mail send: blockers APP_AUTOMATION_REQUESTED, EXTERNAL_ACTION_REQUESTED
- Audio playback: MAC_AUDIO_PLAYBACK / package created: True

Boundary:
- No Mac execution, Mac automation, Xcode execution, screenshot capture, file mutation, external action, send/submit, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push.

Next safe move: Use this package only to hand Mac-owned work to a future Mac lane; do not execute from PC.
