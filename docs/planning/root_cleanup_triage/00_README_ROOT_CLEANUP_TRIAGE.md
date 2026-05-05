# Root Cleanup Triage Packet

Status: docs-only top-level cleanup triage packet. This packet preserves a read-only path-name audit of the relocated OpenClaw repo root. It does not authorize cleanup, deletion, movement, archiving, service control, runtime mutation, private-data inspection, provider/model calls, or Git operations.

## Purpose

The `/home/openclaw` repo root is structurally working after relocation to Ubuntu-E, but it contains active code, authority docs, sensitive-looking paths, runtime traces, caches, duplicate-looking folders, and accidental command-fragment-looking paths in the same top-level namespace. This packet exists so future cleanup work does not restart from confusion or accidentally treat noisy paths as safe to remove.

## Confirmed Audit Facts

- Active workspace: `/home/openclaw`.
- Active WSL distro: Ubuntu-E.
- Confirmed user: `openclaw`.
- Git branch/status at audit time: `main...origin/main [ahead 16]`.
- Current local changes at audit time:
  - `A docs/planning/launch_ladder/21_WSL_RELOCATION_AND_C_DRIVE_RELIEF_BREADCRUMB.md`
  - `M docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md`
  - `?? docs/_ai/runtime_snapshot.md`
- Recent safe validations passed:
  - Launch Ladder `py_compile`.
  - `launch_ladder_contract_check.py` returned OK with a freshness-normalization warning.
  - `tests/test_launch_ladder_static_contract.py` passed 20 tests.
  - Focused legal/local tests passed 66 tests.
  - `git diff --check` passed.
- Runtime/services were not tested.
- PowerShell/VS Code terminal wrapper mangled long WSL pipelines during the audit, so metadata depth is limited.

## Classification Doctrine

- Path names are evidence for triage, not deletion authority.
- Duplicate-looking does not mean duplicate.
- Cache-looking does not mean safe to delete.
- Sensitive-looking means protect, not inspect.
- Command-fragment-looking means candidate for later review, not cleanup now.
- No cleanup should happen before a metadata-only verification packet and explicit operator approval.

## Packet Map

| File | Role |
| --- | --- |
| `00_README_ROOT_CLEANUP_TRIAGE.md` | Scope, facts, doctrine, and packet index. |
| `01_TOP_LEVEL_CLASSIFICATION_TABLE.md` | Path-name-only classification table. |
| `02_PROTECT_LIST_DO_NOT_TOUCH.md` | Sensitive, runtime, and authority protect list. |
| `03_ACCIDENTAL_COMMAND_FRAGMENT_CANDIDATES.md` | Odd command-fragment-looking path names to preserve for later review. |
| `04_DUPLICATE_HISTORICAL_AND_BACKUP_CANDIDATES.md` | Duplicate-looking, backup, and historical candidates with warnings. |
| `05_CACHE_BUILD_AND_TOOLCHAIN_CANDIDATES.md` | Cache/build/toolchain-looking paths that are not cleanup-approved. |
| `06_FUTURE_METADATA_VERIFICATION_WORKFLOW.md` | Future metadata-only verification sequence before any cleanup proposal. |
| `07_HANDOFF_PROMPT_FOR_FUTURE_CHAT.md` | Paste-ready prompt for a later metadata-only cleanup verification chat. |

## Authority Notes

- `OPENCLAW_RUNTIME.md` is canonical runtime law.
- `AGENTS.md` is an adapter that points tools to `OPENCLAW_RUNTIME.md`.
- `RUNBOOK.md` contains service commands, but some service-management content is historical/frozen and not cleanup authority.
- Launch Ladder docs are planning-only and do not authorize runtime, service, private-data, provider/model, or cleanup action.

## Stop Rule

If a later cleanup task cannot prove a path is non-sensitive, non-runtime, unreferenced by authority docs, covered by a rollback plan, and explicitly approved by the operator, stop and classify it as `unknown-human-review` or `sensitive/do-not-touch`.