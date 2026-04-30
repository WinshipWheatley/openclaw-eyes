# OpenClaw Legal Real-Matter Local-Only Validation Protocol

## Purpose

This protocol defines the safest future way to validate one real local matter through the current OpenClaw Legal spine.

It is planning only. Do not run real matter from this document without a separate explicit authorization for that exact validation.

This protocol does not approve GUI Run, Reset, Mac bridge execution, private Obsidian vault actions, production deployment, legal advice, cloud processing, external models, screenshots of matter outputs, or sharing generated matter artifacts outside the local matter environment.

## 1. Pre-authorization gate

Real-matter validation is allowed only after all of the following are true:

- Synthetic/fake-matter operational validation has passed for the current checkout.
- The Legal repo files are clean or only contain an approved docs-only protocol change.
- The operator has explicit approval for one named local-only Lane B validation.
- The validation uses copied matter files only; original evidence is not moved into the product repo.
- The matter owner understands that reports and review packets are content-bearing private matter artifacts.
- The chosen matter ID is operational and non-identifying; do not use a client name, party name, court name, or case caption.
- The chosen query is locally approved and non-sensitive enough to appear in private status files.
- No external LLM, cloud OCR, cloud sync, telemetry, browser upload, screenshot upload, or non-local model will receive matter content.
- The operator will not paste matter contents, filenames, extracted text, reports, review packet contents, audit logs, manifests, hashes, or screenshots into prompts or repo docs.
- The run will use the approved private root only and must keep matter data outside `/home/openclaw`.
- The repo-boundary sentinel must pass immediately before and after the future run:

  ```bash
  test ! -e /home/openclaw/OpenClawLegalPrivate
  ```

## 2. Approved paths

The product code path is:

```text
/home/openclaw
```

That path is code-only for real matter. Matter data, source files, extracted text, reports, review packets, support diagnostics, manifests, and audit logs must not be written under it.

The only approved PC-side private root for the current real-matter validation plan is:

```text
/mnt/c/OpenClawLegalPrivate
```

The future PC-side validation may use only these private subpaths, with a non-identifying `<MATTER_ID>`:

```text
/mnt/c/OpenClawLegalPrivate/staging/<MATTER_ID>
/mnt/c/OpenClawLegalPrivate/vault/<MATTER_ID>
/mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>
```

For later Mac bridge validation only, after PC-side validation passes and a separate authorization is given, the private workstation root remains:

```text
~/OpenClawLegalPrivate
```

The Mac workstation drop/output paths must remain under that private root and must not be placed in cloud sync folders, watch folders, the product repo, or planning workspaces.

## 3. Future PC-side commands

Do not run these commands during protocol planning. They are the exact future command shape for a separately authorized PC-side real-matter validation.

Before the run:

```bash
cd /home/openclaw
git status -sb --untracked-files=all
test ! -e /home/openclaw/OpenClawLegalPrivate
bash -n scripts/run_legal_pipeline_v0.sh
```

After the operator has copied only the approved real matter files into the approved staging path, run:

```bash
cd /home/openclaw
bash scripts/run_legal_pipeline_v0.sh <MATTER_ID> <QUERY>
```

After the run:

```bash
cd /home/openclaw
test ! -e /home/openclaw/OpenClawLegalPrivate
grep -n '^Status: Done$' /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/PRIMARY_NODE_STATUS.md
test -f /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/alternative_methods.json
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/support
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/reports
test -d /mnt/c/OpenClawLegalPrivate/exports/<MATTER_ID>/review_packets
git status -sb --untracked-files=all
```

The future validation report should not include the actual matter ID, query, file names, file counts, source text, snippets, report text, review packet contents, private paths beyond the approved root names above, hashes, audit rows, screenshots, or support packet JSON bodies.

## 4. Files and folders not to inspect or print

Do not inspect private matter files and do not print any of these into terminals, prompts, repo docs, screenshots, cloud tools, or non-local tools:

- source files under staging
- copied source files under the matter vault
- extracted text artifacts
- search report bodies
- review packet bodies
- manifest source entries
- audit log rows
- raw support packet JSON bodies
- private filenames
- private absolute paths below approved root names
- hashes, snippets, OCR text, report excerpts, or attorney notes

Local attorney/operator review may open reports and review packets inside the private matter environment. That is not evidence that those contents are safe to quote elsewhere.

## 5. Safe success and failure signals

Success can be checked without reading matter contents by confirming only:

- the runner exit code is zero
- `PRIMARY_NODE_STATUS.md` has `Status: Done`
- the repo-boundary sentinel still passes
- expected private output directories exist
- sanitized support diagnostics exist
- Alternative Methods JSON exists
- status counts can be summarized locally without filenames, source text, paths, hashes, snippets, or report bodies
- `git status` shows no Legal repo file changes caused by the run

Failure can be checked without reading matter contents by confirming only:

- nonzero runner exit code
- `PRIMARY_NODE_STATUS.md` has `Status: Error`
- expected private output directories are absent
- the repo-boundary sentinel fails
- support diagnostics indicate failed, unsupported, no_text, or pending statuses by count/category only

Do not debug a failure by printing matter contents, filenames, extracted text, reports, review packet bodies, manifests, audit logs, or raw command stderr containing private paths. If a failure requires deeper inspection, stop and move to local-only operator review.

## 6. Status and logs safe to inspect

The following may be inspected locally with redaction discipline:

- `PRIMARY_NODE_STATUS.md`: status line, generic processing state, last-updated time, and approved root-level output categories only.
- `03_WORKSTATION_STATUS.md`: status line and generic next action only, for later Mac bridge validation.
- `support_packet.json`: sanitized status counts, file-extension buckets, extractor names, reason categories, and explicit exclusion proof only. Do not paste the full JSON body into prompts or docs.
- `alternative_methods.json`: unsupported/no-text/failed categories and local-first next-action states only. Do not paste full JSON bodies into prompts or docs.

Treat manifests, audit logs, reports, review packets, extracted artifacts, source files, and staging folders as private matter material. They are not safe report inputs.

## 7. Stop conditions

Any stop condition below immediately aborts validation:

- A command would read, list, print, screenshot, upload, or summarize real matter contents outside the private local environment.
- A command would touch `/mnt/c/OpenClawLegalPrivate` without the separate real-matter authorization.
- Any matter path resolves under `/home/openclaw`.
- `/home/openclaw/OpenClawLegalPrivate` exists before or after the run.
- A path is in a cloud sync folder, watch folder, repo folder, or planning workspace.
- The matter ID exposes a client, party, court, caption, attorney, or case name.
- The query is too sensitive to appear in private status files.
- The run requires an external model, cloud service, browser upload, telemetry, or non-local OCR service.
- A terminal or report starts printing filenames, snippets, extracted text, report bodies, review packet bodies, audit rows, manifest entries, hashes, or private paths below approved root names.
- `run_legal_pipeline_v0.sh` fails or emits an unexpected private path/content-bearing error.
- A support packet contains source text, extracted text, sensitive filenames, private absolute paths, review packet contents, attorney notes, or raw audit logs.
- The scope drifts into GUI Run, Reset, Mac bridge actions, Obsidian vault actions, production readiness, legal advice, or real firm deployment.

## 8. Redaction rule

Any validation report must redact:

- client names
- party names
- case captions
- court names
- attorney names unless explicitly approved
- matter ID if it reveals anything identifying
- query text if sensitive
- filenames
- file counts unless explicitly approved
- source text
- extracted text
- snippets
- report bodies
- review packet contents
- support packet JSON bodies
- private absolute paths below approved root names
- hashes
- timestamps if they reveal case chronology
- screenshots or screen recordings containing matter outputs

Report only high-level pass/fail, approved root names, generic command shape, sanitized counts/categories if approved, repo-boundary status, and whether real matter stayed outside `/home/openclaw`.

## 9. Runner safety assessment

`scripts/run_legal_pipeline_v0.sh` is path-bounded enough to be the underlying PC-side runner for a future real-matter validation, but it should not be treated as safe to run as-is by a general operator.

It needs this protocol wrapper first because it creates private matter workspace state, imports real files, extracts text, searches, creates content-bearing reports, creates content-bearing review packets, creates sanitized support diagnostics, writes private status files, and copies outputs under the private root. The script suppresses normal CLI JSON output and checks that private roots are not inside `/home/openclaw`, but it does not itself handle authorization, redaction decisions, matter-ID naming, query sensitivity, report wording, or local-only operator review.

Future use rule: run the script only inside the approved protocol, with explicit authorization, non-identifying `<MATTER_ID>`, locally approved `<QUERY>`, and no external reporting of content-bearing outputs.

## 10. PC-side before Mac bridge

PC-side real-matter CLI validation should happen before Mac Obsidian/private-vault bridge validation.

Reason: the PC-side run isolates the Legal pipeline and path-boundary behavior without adding SSH, rsync, Finder, Obsidian, GUI, Run, Reset, or workstation-copy complexity. Once PC-side validation passes, Mac bridge validation may be planned as a separate local-only authorization with its own preflight, status-only proof, and no inspection of private matter files.

The Mac bridge should remain after PC-side validation and must not use Reset on real matters.
