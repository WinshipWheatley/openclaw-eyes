# Documentation Lifecycle

This document defines the temporal stages of OpenClaw documentation and the rules for identifying, rotating, and archiving stale material.

## 1. Document Stages

| Stage | Location | Status |
| :--- | :--- | :--- |
| **Draft** | `mac_eyes/Winship/drafts/` | Non-canonical. Unverified. |
| **Active** | `docs/<lane>/` | Canonical. Source of truth for current stack state. |
| **Stale** | `docs/<lane>/` | Canonical but historically flagged. Needs rotation. |
| **Archived** | `docs/archives/` | Non-canonical. Historical residue for forensic use only. |

## 2. Stale Document Criteria

A document in a canonical lane (e.g., `handoffs/`) is considered **Stale** if:
- It describes a module surface or logic that has since been refactored or deleted.
- It contains "Next Steps" or "Pending Tasks" that were completed more than 30 days ago.
- It is a "Context Bundle" or "Handoff" that has been superseded by a newer version (e.g., `cassandra_audit_v1.md` vs `v2.md`).

## 3. The Rotation Process (Active -> Archived)

To prevent the documentation root from becoming a "junkyard" of dead context, follow these steps:

1. **Identify**: During any "Hygiene" or "Review" pass, flag documents that meet the stale criteria.
2. **Review**: Ensure no unique architectural lessons or "hard-won knowledge" will be lost. If valuable lessons exist, move them to a `doctrine/` or `handoffs/` reference doc first.
3. **Move**: Relocate the file to the appropriate sub-folder in `docs/archives/`.
4. **Cleanup Links**: Update `docs/INDEX.md` or other active docs to remove pointers to the archived file.

## 4. Archive Organization

The `docs/archives/` folder should be organized by year or by major milestone to remain navigable.

- **`docs/archives/YYYY/`**: General historical logs and project snapshots.
- **`docs/archives/legacy_models/`**: Specific context about deprecated LLM versions or role-plays.

## 5. Automated Context (The _ai lane)

Files in `docs/_ai/` are transient. They should be overwritten or rotated automatically by agents and do not require manual archiving unless they capture a specific failure state needed for a bug report.
