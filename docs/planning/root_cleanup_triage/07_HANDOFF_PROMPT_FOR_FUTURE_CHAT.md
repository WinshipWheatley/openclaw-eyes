# Handoff Prompt For Future Chat

Status: paste-ready prompt for a later metadata-only verification chat.

```text
You are in PC WSL Ubuntu-E at /home/openclaw.

Task: metadata-only verification for the OpenClaw top-level cleanup triage packet.

Hard boundaries:
- Do not delete, move, rename, archive, compress, clean, install, upgrade, commit, push, start services, stop services, run agents, mutate runtime state, or make provider/model calls.
- Do not inspect secrets, keys, vaults, .env files, tokens, credentials, legal/client/tax/private/finance raw data, Gmail/Calendar stores, runtime queues, private logs, or provider configs.
- Do not treat duplicate-looking paths as safe to delete.
- Do not treat cache-looking paths as safe to delete.
- Do not treat command-fragment-looking paths as cleanup-approved.
- This is classification and metadata only.

Read first:
- docs/planning/root_cleanup_triage/00_README_ROOT_CLEANUP_TRIAGE.md
- docs/planning/root_cleanup_triage/01_TOP_LEVEL_CLASSIFICATION_TABLE.md
- docs/planning/root_cleanup_triage/02_PROTECT_LIST_DO_NOT_TOUCH.md
- docs/planning/root_cleanup_triage/03_ACCIDENTAL_COMMAND_FRAGMENT_CANDIDATES.md
- docs/planning/root_cleanup_triage/04_DUPLICATE_HISTORICAL_AND_BACKUP_CANDIDATES.md
- docs/planning/root_cleanup_triage/05_CACHE_BUILD_AND_TOOLCHAIN_CANDIDATES.md
- docs/planning/root_cleanup_triage/06_FUTURE_METADATA_VERIFICATION_WORKFLOW.md

Known audit facts to preserve:
- /home/openclaw was structurally working in Ubuntu-E as user openclaw.
- Git state was main...origin/main [ahead 16].
- Local changes included:
  - A docs/planning/launch_ladder/21_WSL_RELOCATION_AND_C_DRIVE_RELIEF_BREADCRUMB.md
  - M docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md
  - ?? docs/_ai/runtime_snapshot.md
- Recent validations passed:
  - launch_ladder py_compile
  - launch_ladder_contract_check.py returned OK with freshness-normalization warning
  - tests/test_launch_ladder_static_contract.py passed 20 tests
  - focused legal tests passed 66 tests
  - git diff --check passed
- Runtime/services were not tested.
- PowerShell/VS Code terminal wrapper mangled long WSL pipelines during the prior audit, so handle command output carefully and report metadata gaps clearly.

Goal:
Create a metadata-only verification table for candidate paths. Capture exact path, type, size, mtime, Git tracked/ignored/untracked status, sensitivity class, authority references by path-name search only, risk, and recommended next handling.

Stop conditions:
- Stop if a path is sensitive-looking and the next step would require content inspection.
- Stop if verification would require service control, runtime mutation, provider/model calls, or private-data access.
- Stop if shell quoting or terminal behavior risks running a different command than intended.

Output:
1. Verdict
2. Confirmed environment and Git status
3. Metadata verification table
4. Protect list deltas
5. Cleanup-candidate deltas
6. Unknown/human-review list
7. Red flags
8. Next smallest safe docs-only action

Do not make cleanup changes.
```