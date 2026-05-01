# OpenClaw Legal Real-Matter Mac Bridge Validation Protocol

## Purpose

This protocol defines the safest future way to validate one real local matter through the Mac workstation bridge after synthetic and fake-data bridge validation have passed.

It is planning only. Do not run real matter from this document without a separate explicit authorization for the exact matter, exact operator, exact local paths, exact query, and exact run window.

This protocol does not approve GUI Run, Reset, real firm deployment, legal advice, cloud processing, external models, screenshots of matter outputs, or sharing matter artifacts outside the local matter environment.

## Known validation baseline

The current readiness baseline is:

- synthetic CLI demos: PASS
- synthetic stress pack: PASS
- fake data through PC real-shaped paths: PASS
- fake data through Mac bridge path: PASS
- Phase 2G-S synthetic GUI-run proof: PASS / complete with status-only sanitized reporting
- GUI real-matter readiness: NO-GO, because the GUI Run wrapper is synthetic-only and has no real-matter mode

This baseline permits planning a real-matter Mac bridge validation protocol. It does not authorize execution.

The completed synthetic GUI-run proof does not change the real-matter boundary: Real-matter GUI Run remains NO-GO, Reset remains NO-GO, and real matter through the app remains NO-GO.

## 1. Preconditions before Mac intake receives real matter

All conditions below must be true before any real matter is placed in the Mac intake folder:

- The operator has explicit approval for one named local-only Lane B validation.
- The PC-side real-matter local-only validation protocol has already been read and accepted for this matter.
- The matter ID is operational and non-identifying; do not use a client name, party name, court name, case caption, attorney name, or other identifying phrase.
- The query is locally approved and safe enough to appear in private status files.
- The matter owner understands that reports, review packets, extracted text, manifests, audit logs, and returned outputs are content-bearing private matter artifacts.
- Only copied evidence files are used. Original evidence is not moved into the product repo, Mac planning workspace, cloud sync folder, watch folder, or prompt context.
- The Mac intake folder is confirmed to be the exact approved folder and not a symlink, repo path, cloud path, watch folder, or planning workspace.
- The Mac intake folder has been reviewed locally by the operator and contains only evidence intended for this validation.
- The PC-side private roots are configured under the approved PC private root only.
- The repo-boundary sentinel is ready to be checked immediately before and after the future run:

  ```bash
  test ! -e /home/openclaw/OpenClawLegalPrivate
  ```

Do not run real matter if any precondition is uncertain.

## 2. Operator confirmation gate

Immediately before any future bridge run, the operator must confirm all of the following in local-only context:

- The selected matter is authorized for this validation.
- The Mac intake folder contains only copied evidence intended for this matter.
- No unknown files, instruction notes, planning docs, fake fixtures, synthetic marker directories, screenshots for prompts, or unrelated files are present in intake.
- `.DS_Store` has been handled safely under Section 4.
- The Mac config points only to the approved product repo, PC staging path, PC vault path, PC exports path, matter ID, and query.
- `PC_SSH_TARGET` is the intended local primary node target.
- The operator will not paste or upload matter content, filenames, extracted text, report bodies, review packet bodies, raw support packet JSON, audit rows, manifests, hashes, snippets, screenshots, or private path details into prompts, docs, tickets, or non-local tools.
- The operator accepts that the bridge creates content-bearing outputs and that those outputs must be reviewed only in the local private environment.

If the operator cannot confirm every item, stop.

## 3. Evidence-only Mac intake rule

The Mac intake folder is evidence-only for the authorized matter.

Allowed in intake for a future real-matter validation:

- copied source evidence files for the approved matter
- only files the operator intentionally wants processed

Forbidden in intake:

- original evidence that should not be copied
- attorney notes not approved for processing
- instruction notes, README files, planning docs, fake fixtures, synthetic marker directories, test files, old dummy files, screenshots intended for prompts, exports from earlier runs, manifests, reports, review packets, support packets, audit logs, symlinks, aliases, and unrelated files

Do not use drag/drop surfaces that may place files outside the exact intake folder. The safe path is Finder/manual placement into the exact approved intake folder.

## 4. `.DS_Store` handling

`.DS_Store` is not evidence. It must not be treated as proof that intake contains real matter, and it must not be used as a reason to delete other files.

Safe handling rule:

- If the intake folder contains only `.DS_Store`, the operator may remove that one metadata file locally before the run.
- If the intake folder contains `.DS_Store` plus any other item, do not bulk delete anything. The operator must review locally and move unknown or unrelated items out of intake without printing names or contents into prompts or terminals.
- Do not use recursive deletion, Reset, broad cleanup commands, or wildcard removal on a real-matter intake folder.
- Do not print `.DS_Store` alongside private filenames or use file listings as report artifacts.

If there is any uncertainty about what is in intake, stop and perform local-only operator review.

## 5. Approved paths

Product code path:

```text
/home/openclaw
```

This path is code-only for real matter. Matter data, source files, extracted text, reports, review packets, support diagnostics, manifests, and audit logs must not be written under it.

Approved Mac private workstation root:

```text
~/OpenClawLegalPrivate
```

Approved Mac bridge workspace:

```text
~/OpenClawLegalPrivate/Matter_Alpha_Workspace
```

Approved Mac intake and outputs paths:

```text
~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE
~/OpenClawLegalPrivate/Matter_Alpha_Workspace/03_WORKSTATION_STATUS.md
~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS
~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md
~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/00_OPEN_THIS_FIRST.md
```

Approved PC private root:

```text
/mnt/c/OpenClawLegalPrivate
```

Approved PC-side real-matter validation subpaths, with a non-identifying `<MATTER_ID>`:

```text
/mnt/c/OpenClawLegalPrivate/staging/<MATTER_ID>
/mnt/c/OpenClawLegalPrivate/vault/<MATTER_ID>
/mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>
```

Forbidden path classes:

- `/home/openclaw` and descendants for matter data
- `~/OpenClaw_Watch` and planning workspaces
- iCloud, Dropbox, OneDrive, Google Drive, Obsidian Sync, OpenClaw_Watch, or any cloud/watch folder
- symlinks or aliases used to bypass approved roots

## 6. Later allowed commands and actions

Do not run these commands during protocol drafting. They are the future command shape only, after separate explicit authorization.

Allowed preflight checks:

```bash
cd /home/openclaw
git status -sb --untracked-files=all
test ! -e /home/openclaw/OpenClawLegalPrivate
bash -n scripts/run_legal_pipeline_v0.sh
bash -n mac_eyes/Launchers/scaffold_mac_legal_vault.sh
```

Allowed manual Mac action:

```text
Open the exact Mac intake folder for manual evidence placement only.
```

Allowed bridge action after approval:

```text
Run ~/OpenClawLegalPrivate/Matter_Alpha_Workspace/Run_OpenClaw_Dry_Run.command for the approved matter only.
```

Allowed status-only checks after the run:

```bash
cd /home/openclaw
test ! -e /home/openclaw/OpenClawLegalPrivate
grep -q '^Status: Done$' /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/PRIMARY_NODE_STATUS.md
test -f /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/alternative_methods.json
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/support
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/reports
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/review_packets
ssh mac 'test -f "$HOME/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md"'
git status -sb --untracked-files=all
```

These checks must be adapted to avoid printing private filenames, private path details below approved roots, source text, hashes, snippets, report bodies, review packet bodies, support packet bodies, manifests, or audit rows.

## 7. Outputs safe to check without reading contents

The following may be checked without reading matter contents:

- bridge command exit status
- repo-boundary sentinel pass/fail
- presence of `PRIMARY_NODE_STATUS.md`
- `Status:` token from `PRIMARY_NODE_STATUS.md`, limited to known tokens such as `Done` or `Error`
- presence of `alternative_methods.json`
- presence of output container directories: `reports`, `review_packets`, and `support`
- presence of copied Mac primary status file
- final `git status -sb --untracked-files=all`
- sanitized count/category summaries only if locally approved and generated without filenames, paths, hashes, snippets, source text, report bodies, review packet bodies, or raw JSON bodies

Treat reports, review packets, extracted text, manifests, audit logs, source files, staging folders, copied vault files, raw support packet JSON, and Alternative Methods bodies as private matter material.

## 8. Materials that must not be printed or shared

Do not inspect private matter files and do not print, paste, screenshot, summarize, upload, or share any of the following outside the local private matter environment:

- source files under Mac intake, PC staging, or PC vault
- private filenames
- file contents
- extracted text
- OCR text
- snippets
- hashes
- manifest entries
- audit log rows
- search report bodies
- review packet bodies
- raw support packet JSON bodies
- Alternative Methods JSON bodies
- attorney notes
- screenshots or screen recordings containing matter outputs
- private absolute paths below the approved root names
- terminal stderr/stdout that reveals any of the above

Local attorney/operator review may open content-bearing outputs inside the private environment. That does not make those contents safe to quote in prompts, repo docs, support tickets, emails, or non-local tools.

## 9. GUI Run and Reset remain forbidden

GUI Run and Reset remain forbidden for real matter.

Reason: the current GUI is intentionally limited to status refresh, exact intake-folder open, one fixed synthetic test-file write, and one fixed synthetic-only dry run. The synthetic-only Run wrapper is not a real-matter run mode. It does not make real-matter authorization, redaction, matter-ID, query-sensitivity, or reset-safety decisions.

Reset is especially forbidden for real matter because reset behavior can delete local drop/output folders and, in full test-reset mode, configured PC-side staging, vault, and exports. Reset is a test-only action unless a separate real-matter preservation and cleanup protocol exists.

Do not wire real-matter GUI Run, Reset, matter selection, file picker, report display, review packet display, support packet display, or real-matter bridge execution as part of this protocol.

## 10. Current GUI allowance

For real-matter protocol purposes, the current GUI may be used only to open the exact Mac intake folder for manual drop and to refresh fixed status files, if those actions remain within their current bounded implementation.

Allowed current GUI actions:

- Open Intake Folder, because it opens only the exact approved folder and does not list, read, or process files.
- Refresh Status, because it reads fixed status files and returns sanitized status tokens and timestamps only.

Not allowed for real matter:

- Create Synthetic Test File
- Run Synthetic Dry Run
- GUI real-matter Run
- Reset Local Test
- Reset All Test State
- file picker
- matter selector
- report/review/support body display
- any GUI action that lists, counts, reads, hashes, previews, or uploads intake contents

The synthetic-only GUI Run wrapper was proven only for Lane A synthetic proof with status-only sanitized reporting. It is not authorization to place real matter in the app or to trigger a real-matter bridge run from the GUI. If the GUI behavior changes before the future validation, re-audit it before use.

## 11. Stop conditions

Real-matter Mac bridge validation must stop immediately if any of the following occur:

- The operator has not explicitly authorized the exact real-matter bridge validation.
- The intake folder is not evidence-only.
- Unknown files, instruction notes, fake fixtures, synthetic marker directories, symlinks, aliases, or unrelated files are present in intake.
- `.DS_Store` appears with any other uncertain item and cannot be handled by local-only operator review.
- Any path resolves under `/home/openclaw` for matter data.
- `/home/openclaw/OpenClawLegalPrivate` exists before or after the run.
- Any approved path is in a cloud sync folder, watch folder, product repo, or planning workspace.
- The matter ID, query, output, status, or report wording exposes identifying matter information outside the local private environment.
- `PC_SSH_TARGET` or Mac config is uncertain.
- The bridge command fails or emits unexpected content-bearing output.
- The runner fails, reports `Status: Error`, or produces missing expected containers.
- Any command would print, paste, screenshot, upload, summarize, hash, list, or inspect private matter contents or private filenames outside local-only review.
- A support packet or Alternative Methods output appears to contain source text, extracted text, private filenames, private absolute paths, review packet contents, attorney notes, raw audit rows, or raw manifest rows.
- The scope drifts into GUI Run, Reset, new code, production deployment, legal advice, cloud/external tools, non-local models, or real firm rollout.

If failure requires deeper diagnosis, stop and move to local-only operator review. Do not debug by printing private matter artifacts.

## 12. Sanitized pass/fail report

A future validation report may contain only:

- bridge command exit status
- repo-boundary sentinel pass/fail
- primary status token, such as `Done` or `Error`
- expected output containers present/missing
- Mac copied primary status present/missing
- whether the Mac real-matter bridge validation passed at status/container level
- whether the GUI remains not real-matter-ready
- generic approved root names only, without private path detail below the approved roots
- sanitized counts/categories only if locally approved and free of filenames, source text, snippets, hashes, report bodies, review packet bodies, raw support JSON bodies, manifests, and audit rows

The report must not include actual matter names, client names, party names, court names, case captions, attorney names, private filenames, file contents, query text if sensitive, source text, extracted text, OCR text, snippets, hashes, report bodies, review packet bodies, raw support packet bodies, Alternative Methods bodies, manifests, audit rows, screenshots, or private absolute paths below approved root names.

## 13. Local models and future model gate

No local model processing is involved in the current Mac bridge validation protocol.

The current bridge uses deterministic local Legal CLI steps and may use local deterministic extraction tools already supported by the repo, such as text extraction and locally installed OCR tooling where applicable. That is not approval for local LLM, embedding model, summarizer, classifier, timeline model, contradiction model, or other model-based matter processing.

Before any local-model processing is allowed for real matter, all of the following must exist:

- a separate written local-model Lane B protocol
- explicit operator and matter-owner authorization
- verified no-network model execution
- documented model inventory, storage path, runtime path, and data-retention behavior
- synthetic/fake-data validation of the model path first
- proof that prompts, embeddings, caches, logs, screenshots, telemetry, and outputs stay inside approved local private roots
- a plan for attorney review and no-legal-advice boundaries
- a sanitized reporting rule at least as strict as this protocol

Until that exists, local-model processing is not approved.

## Relationship to the PC-side protocol

This Mac bridge protocol extends the PC-side real-matter local-only validation protocol. The PC-side protocol remains the root authority for the underlying runner and path-boundary checks.

If this document conflicts with `OPENCLAW_LEGAL_REAL_MATTER_LOCAL_ONLY_VALIDATION_PROTOCOL.md`, use the stricter rule.