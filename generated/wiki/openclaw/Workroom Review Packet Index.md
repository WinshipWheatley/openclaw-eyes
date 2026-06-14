# Workroom Review Packet Index

Status: `WORKROOM_REVIEW_PACKET_INDEX_READY`

This read model indexes spawned worker review packets across OpenClaw workrooms like a PR queue.

Review packets: `2`

## Packets

### `review_packet:1ec9dae46a22e6ae`

- Worker: `mac_codex`
- Channel: `build_mission_control_mac`
- Package: `pkg:example:mission_control_ui_patch`
- Status: `REVIEW_PACKET_READY`
- Summary: MAC_CODEX returned UI work with screenshot proof for operator review.
- Next safe action: Inspect the screenshot and validation refs before approval.
- Operator decision required: `true`

### `review_packet:c4ec166103f9aa35`

- Worker: `pc_codex`
- Channel: `build_openclaw_backend`
- Package: `pkg:example:backend_registry_patch`
- Status: `REVIEW_PACKET_READY`
- Summary: PC_CODEX changed backend code and returned local validation proof for operator review.
- Next safe action: Review the packet and approve, request rework, or block by gate.
- Operator decision required: `true`

## Boundary

- No merge.
- No git push.
- No worker spawn or child agent run.
- No email send.
- No Gmail/browser/Coupa access.
- No ledger or workbook mutation.
- No PDF export.
- No submit or mark-paid.
- No business action.
- Worker does not inherit speaker authority.
- Proof refs are collapsed by default.
