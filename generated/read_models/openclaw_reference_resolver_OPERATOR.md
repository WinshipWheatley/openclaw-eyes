# OpenClaw Reference Resolver

Purpose:
- Keep stable refs in canonical config and resolve volatile values during export.

Targets:
- `openclaw_eyes_registry_review_branch` `GIT_BRANCH` -> `UNREACHABLE` `none`.
- `estate_topology_registry_read_model_mirror` `READ_MODEL_MIRROR` -> `MISSING` `sha256:5bd68b9e9cccbef34eddc9df87c861f861559d5a8a13cb2627aff648dd6eed62`.

Boundary:
- Read-only Git inspection and file hashing only.
- No service, push, browser, email, Coupa, workbook, PDF, ledger, or production action.
