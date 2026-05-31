# OpenClaw Reference Resolver

Purpose:
- Keep stable refs in canonical config and resolve volatile values during export.

Targets:
- `openclaw_eyes_registry_review_branch` `GIT_BRANCH` -> `RESOLVED_REMOTE` `1a6b7b0b463968f3161e048bd7936dc06505a3bb`.
- `estate_topology_registry_read_model_mirror` `READ_MODEL_MIRROR` -> `MISSING` `sha256:54769dbb71b72fe8153f14e58ab8a22c03903955102177051a8e846d5d6e0b8d`.

Boundary:
- Read-only Git inspection and file hashing only.
- No service, push, browser, email, Coupa, workbook, PDF, ledger, or production action.
