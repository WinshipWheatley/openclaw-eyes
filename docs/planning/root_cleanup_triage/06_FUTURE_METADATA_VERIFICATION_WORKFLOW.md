# Future Metadata Verification Workflow

Status: future docs-only workflow. This file defines the sequence required before any cleanup proposal. It does not authorize cleanup.

## Required Sequence

1. Preserve this packet.
2. Collect metadata only: path, type, size, mtime, and Git tracked/ignored status.
3. Classify sensitivity and authority.
4. Check known references from authority docs.
5. Separate protect list from cleanup candidates.
6. Propose action only after a rollback plan exists.
7. Require explicit operator approval before any move, delete, archive, rename, compression, or cleanup.
8. Validate after any future cleanup.

## Metadata Fields

For each candidate path, capture:

| Field | Requirement |
| --- | --- |
| Path | Exact path, preserving spaces and unusual characters. |
| Type | File, directory, symlink, or other. |
| Size | Human-readable and raw bytes if possible. |
| Modified time | Timestamp from filesystem metadata. |
| Git state | Tracked, modified, untracked, ignored, or outside Git visibility. |
| Sensitivity | `sensitive/do-not-touch`, `runtime/config trace`, `unknown-human-review`, or cleanup-candidate class. |
| Authority references | References from allowed authority docs or safe path-name searches only. |
| Proposed handling | Keep, protect, monitor, review, archive candidate, delete candidate, or unknown. |
| Rollback plan | Required before any destructive or location-changing proposal. |
| Approval state | No action until explicit operator approval is captured. |

## Boundary Rules

- Do not read secrets, keys, vaults, private legal/finance data, Gmail/Calendar stores, provider configs, queue contents, or private logs.
- Do not start or stop services.
- Do not run agents.
- Do not mutate runtime state.
- Do not run broad cleanup commands.
- Do not alter `.gitignore` just to make cleanup easier.
- Do not treat Git ignored status as deletion approval.

## Validation After Any Future Cleanup

If a later approved cleanup packet performs changes, validate with the narrowest relevant checks. At minimum, capture:

- Git status before and after.
- A clear list of paths changed.
- Any rollback artifact location.
- `git diff --check` for docs/code changes.
- Relevant static tests only if the approved cleanup could affect docs, scripts, or runtime references.

Runtime/service validation requires separate explicit operator approval because this packet does not authorize service control.