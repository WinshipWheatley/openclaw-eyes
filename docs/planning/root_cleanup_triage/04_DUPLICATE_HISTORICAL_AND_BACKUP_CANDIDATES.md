# Duplicate, Historical, And Backup Candidates

Status: path-name-only candidate list. Duplicate-looking does not mean duplicate.

## Candidate Paths And Patterns

- `openclaw_arko_review`
- `backups`
- `recovery-library`
- `*.bak`
- `*.save`
- `*.old-key-backup`

## Special Protected Runtime Case

- `OpenClaw`

`OpenClaw` is not classified as a cleanup candidate in this packet. It looks duplicate by top-level name, but `CURRENT_STATE.md` may indicate legacy session state may live there. Treat it as runtime/config trace and protect it until verified.

## Why These Need Care

Backup and duplicate-looking paths may contain:

- Rollback material.
- Historical source context.
- Runtime state copied from older layouts.
- Private material.
- Keys or encrypted vault backups.
- Files still referenced by scripts, docs, or services.

## Future Verification Requirements

Any later packet must verify metadata before proposing action:

1. Path and type.
2. Size and modified time.
3. Git tracked, ignored, or untracked status.
4. Whether the path name is sensitive-looking.
5. Whether authority docs, runbooks, scripts, or active planning docs reference the path.
6. Whether it is a rollback artifact that must be retained until a separate recovery policy exists.
7. Whether the proposed action has a reversible rollback plan.

## Non-Authority Rule

This list does not approve deletion, movement, archiving, renaming, compression, or deduplication. It only records that these paths deserve later human review.