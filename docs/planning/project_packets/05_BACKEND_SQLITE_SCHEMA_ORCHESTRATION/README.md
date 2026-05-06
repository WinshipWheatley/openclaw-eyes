# Backend SQLite Schema Orchestration Project Packet

Status: ChatGPT Project upload packet export for the inert SQLite schema-definition orchestration phase.

This folder is an export package. `/home/openclaw` remains the canonical repo and build truth.

## Contents

- `24_files/` contains the stable phase source-set for ChatGPT Project upload.
- `00_ACTIVE_HANDOFF.md` sits outside `24_files/` because it is active/current and may change more often than the stable source-set.
- `README.md` explains the packet structure and mirror boundary.

## Mac Mirror Destination

```text
~/OpenClaw_Watch/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/
```

The Mac mirror is for operator review and ChatGPT Project upload convenience. It is not canonical authority.

Future ChatGPT Project packets should use this same structure:

```text
<PROJECT_PACKET_NAME>/
  24_files/
  00_ACTIVE_HANDOFF.md
  README.md
```

## Faster Workflow / Batch Checkpoint Rule

- If a bounded lane is clear, complete implementation + hardening + polish/taste in one batch.
- ChatGPT should not ask for diff review after every micro-step.
- One combined diff/status review is enough unless there is risk.
- Commit/push at meaningful checkpoints, not after every small edit.
- Deep diff review is reserved for authority boundary changes, runtime/persistence/private-data behavior, failed tests, unexpected files, or ambiguity.
- `00_ACTIVE_HANDOFF.md` is milestone-based, not micro-step-based.
- `24_files/` is stable/archive-like during an active lane.
