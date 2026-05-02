# OpenClaw Legal Synthetic Demo Validation

## 1. Purpose

This is a synthetic/public-safe validation package for the current Legal Console checkpoint.

It exists so a future ChatGPT, Codex session, or operator can validate the safe Legal Console demo flow without drifting into a real matter workflow.

This package is not a real matter workflow, not a production readiness claim, not approval for real-matter GUI Run, and not approval to wire Reset Local Test or Reset All Test State.

## 2. Current checkpoint

Relevant commits:

- `64f5190` - `feat(legal): add synthetic intake test file action`
- `9809e69` - `docs(legal): record synthetic test file validation`
- `2a7737d` - `docs(legal): defer run dry run planning`
- `6348994` - `docs(legal): add Phase 2G-S visual translation brief`
- `a8e5772` - `style(legal): polish Phase 2G-S console shell`
- `f42a33f` - `docs(legal): update handoff after visual proof`

Current posture:

- OpenClaw Legal remains promising / conditional-go.
- Phase 2F-B synthetic write is complete.
- Phase 2G-S synthetic-only GUI Run wrapper is implemented and committed.
- Phase 2G-S synthetic GUI-run proof is now complete.
- Synthetic GUI-run proof passed with status-only sanitized reporting.
- Folder 2 / Phase 2G-S visual polish is complete and checkpointed.
- Mac visual/runtime proof passed for the committed CSS-only polish.
- Real-matter GUI Run remains NO-GO.
- Reset remains NO-GO.
- Real matter through the app remains NO-GO.
- Active next lane is Folder 3 planning/pilot/package/readiness source-set review.
- Folder 3 is not implementation authorization.
- Next safe work is docs-only Folder 3 intake/checkpoint or pilot/readiness/package consistency audit.
- Connect, queue/ETA, OCR/model distribution, Run/Reset, and real-matter behavior must not start unless separately authorized.

## 3. Allowed validation scope

Allowed validation actions:

- Launch the Legal Console from the Mac dev path.
- Click `Refresh Status`.
- Click `Open Intake Folder`.
- Click `Create Synthetic Test File`.
- Verify already-present behavior by clicking `Create Synthetic Test File` again.
- Click `Run Synthetic Dry Run` only when the intake contains approved synthetic fixtures.
- Verify `Reset Local Test` and `Reset All Test State` remain disabled.
- Verify already-present behavior from the existing fixed synthetic file contract.
- Verify no private contents, counts, or filenames are displayed.

Forbidden validation actions:

- Do not use a real matter.
- Do not run real-matter GUI Run.
- Do not run Reset behavior.
- Do not execute the bridge except through `Run Synthetic Dry Run` with fixed synthetic values.
- Do not add a file picker.
- Do not select a matter.
- Do not list intake folder contents.
- Do not display output bodies.
- Do not display review packet bodies.
- Do not display support packet bodies.
- Do not display private absolute paths.
- Do not add or validate Connect, queue, or ETA behavior.
- Do not inspect private matter data.
- Do not touch `/mnt/c/OpenClawLegalPrivate`.

## 4. Preflight

Before validation:

1. Confirm the PC/WSL repo is clean or has only known scoped docs-only changes:

   ```bash
   cd /home/openclaw
   git status -sb
   ```

2. Confirm the WSL canonical repo path is:

   ```text
   /home/openclaw
   ```

3. Confirm the Mac Legal Console dev path is:

   ```text
   ~/OpenClawLegalDev/legal-console-spike
   ```

4. Confirm validation remains synthetic/public-safe only:

   - no real matter inspection
   - no intake listing
   - no private matter filenames, counts, or contents
   - no real-matter bridge execution

5. Confirm no private Legal vault is present under the product repo:

   ```bash
   test ! -e /home/openclaw/OpenClawLegalPrivate
   ```

## 5. Validation steps

1. Sync/build the Legal Console to the Mac dev path only if needed for the current checkpoint.
2. Launch the GUI from `~/OpenClawLegalDev/legal-console-spike`.
3. Confirm the visible checkpoint is Phase 2G-S or the current equivalent synthetic-only Run checkpoint.
4. Click `Refresh Status`.
5. Confirm the status snapshot is safe and does not display private contents, counts, filenames, or absolute private paths.
6. Click `Open Intake Folder`.
7. Confirm the allowed intake folder opens and the UI states no files were read, listed, written, or processed by that action.
8. Click `Create Synthetic Test File` once.
9. Confirm the UI reports `Synthetic test file created` or the equivalent created result for the fixed synthetic test file.
10. Click `Create Synthetic Test File` a second time.
11. Confirm the UI reports `Synthetic test file already exists` or the equivalent already-present result.
12. Confirm `Run Synthetic Dry Run` is available and clearly synthetic/test-only.
13. Run `Run Synthetic Dry Run` only with approved synthetic fixtures.
14. Refresh Status after the run and confirm only sanitized state is displayed.
15. Confirm `Reset Local Test` remains disabled.
16. Confirm `Reset All Test State` remains disabled.
17. Confirm no intake contents, file counts, filenames, output bodies, review packet bodies, or support packet bodies are displayed.
18. Stop the app.

## 6. Expected results

Expected UI outcomes:

- The status snapshot is safe and sanitized.
- The GUI bridge state is synthetic-only.
- The fixed synthetic test file is created on the first click when absent.
- The second click returns already-present behavior for the fixed synthetic test file.
- `Run Synthetic Dry Run` returns sanitized synthetic status only.
- No folder contents are listed.
- No file counts are displayed.
- No filenames are displayed.
- No private matter contents are displayed.
- No private absolute paths are displayed.
- Real-matter GUI Run remains unavailable.
- `Reset Local Test` remains disabled.
- `Reset All Test State` remains disabled.

## 6A. Completed Phase 2G-S proof result

The Phase 2G-S synthetic GUI-run proof passed with status-only sanitized reporting.

Observed proof result:

- Mac GUI showed Phase 2G-S.
- `Run Synthetic Dry Run` was visible.
- Synthetic dry run succeeded.
- Started: yes.
- Status: succeeded.
- Exit code: 0.
- Bridge mode: `synthetic_only`.
- Raw bridge output was captured/suppressed.
- Real-matter GUI Run remained disabled.
- `Reset Local Test` remained disabled.
- `Reset All Test State` remained disabled.
- Refresh Status showed GUI bridge: Synthetic-only GUI run.
- Primary state token: `Done`.

Sanitized post-proof verification passed:

- repo boundary: PASS
- primary status token: `Done`
- `alternative_methods.json`: PRESENT
- `reports` container: PRESENT
- `review_packets` container: PRESENT
- `support` container: PRESENT
- Mac copied primary status file: PRESENT

No filenames, file counts, source text, snippets, hashes, report bodies, review packet bodies, support packet bodies, raw status bodies, raw bridge output, or private file lists were printed.

## 7. Proof commands

PC/WSL docs proof for this validation package:

```bash
cd /home/openclaw
git diff --check
git diff -- docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_SYNTHETIC_DEMO_VALIDATION.md docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_CHAT_HANDOFF.md | sed -n '1,260p'
grep -n "Phase 2G-S\|Run Synthetic Dry Run\|synthetic/public-safe validation" docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_SYNTHETIC_DEMO_VALIDATION.md
git status -sb
```

PC/WSL app proof to rerun only when validating the current console implementation, not while doing docs-only edits:

```bash
cd /home/openclaw/apps/legal-console-spike
npm run check
npm run build
```

Relevant scoped scans for implementation validation:

```bash
cd /home/openclaw

rg -n "Run_OpenClaw_Dry_Run|Reset_Test_Run|Reset_All_Test_State|run_legal_pipeline_v0|std::process|Command::new|ssh |rsync" \
  apps/legal-console-spike/src apps/legal-console-spike/src-tauri/src

rg -n "read_dir|WalkDir|glob|intake.*contents|folder contents|file count|filenames" \
  apps/legal-console-spike/src apps/legal-console-spike/src-tauri/src

rg -n "/mnt/c/OpenClawLegalPrivate|/home/openclaw/OpenClawLegalPrivate|support packet body|review packet body|output body" \
  apps/legal-console-spike/src apps/legal-console-spike/src-tauri/src

git status -sb
```

For the scoped scans above, any match must be inspected before proceeding. A match is not automatically a failure if it is only disabled UI copy or an explicit safety warning, but bridge execution, Run/Reset wiring, intake listing, private reads, private path display, or output body display must halt validation.

## 8. Screenshot/evidence checklist

Useful screenshots or notes:

- Before `Refresh Status`.
- After `Refresh Status`.
- `Create Synthetic Test File` created result.
- `Create Synthetic Test File` already-present result.
- `Run Synthetic Dry Run` success result showing sanitized fields only.
- Disabled `Run Real Matter` control.
- Disabled `Reset Local Test` control.
- Disabled `Reset All Test State` control.
- Note confirming no private filenames, counts, contents, output bodies, review packet bodies, support packet bodies, or private absolute paths were displayed.

Do not capture private matter data in screenshots or notes.

## 9. Stop conditions

Halt validation immediately if any of these occur:

- A real matter appears.
- Private filenames appear.
- Private file counts appear.
- Private contents appear.
- Output body text appears.
- Review packet body text appears.
- Support packet body text appears.
- Real-matter GUI Run becomes enabled.
- `Reset Local Test` becomes enabled.
- `Reset All Test State` becomes enabled.
- Any non-synthetic bridge mode executes.
- Arbitrary input appears for path, filename, file body, query, matter, or mode.
- Private absolute paths are displayed.
- The app implies production readiness.

## 10. Next-step rule

Historical note: this validation package previously directed the next workflow toward Folder 2 visual polish. That Folder 2 / Phase 2G-S CSS-only visual polish lane is now complete and checkpointed, and Mac visual/runtime proof passed.

After validation, the active next lane is Folder 3 planning/pilot/package/readiness source-set review. Folder 3 is not implementation authorization. Next safe work is docs-only Folder 3 intake/checkpoint or pilot/readiness/package consistency audit.

Real-matter GUI Run remains NO-GO. Reset remains NO-GO. Real matter through the app remains NO-GO. Connect, queue/ETA, OCR/model distribution, Run/Reset, and real-matter behavior must not start unless separately authorized. Any behavior expansion requires a separate contract/design and explicit approval before implementation.