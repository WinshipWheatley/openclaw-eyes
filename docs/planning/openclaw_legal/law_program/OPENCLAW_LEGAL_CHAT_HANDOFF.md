# OpenClaw Legal — Chat Handoff

## Purpose

This handoff is for a new ChatGPT or Codex session.

The new chat should use this file to orient, then verify current facts before acting.

## Authority warning

`OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` governs this package.

If this handoff conflicts with governing principles, governing principles win unless intentionally updated.

This handoff is current-state guidance, not permanent doctrine.

PC/WSL Legal v0 was audited in `/home/openclaw` before the first safety slice was implemented.

The new chat should use the handoff to orient, not as implementation proof.


This file summarizes:

- what was already built in the canonical PC/WSL OpenClaw repo
- what was planned in the Mac `OpenClaw_Watch` workspace
- the critical product/safety/business doctrine
- the recommended next step

## Freshness rule

This handoff is session-current, not permanent doctrine.

This file should be the live handoff that new ChatGPT/Codex sessions check first, but it must be replaced when material facts change.

Replace and archive this handoff when any of these happen:

- PC/WSL Codex produces a materially newer implementation map
- Legal v0 changes materially
- the next 3–5 build slices are chosen
- a first firm/pilot scope becomes concrete
- the business/go-no-go decision changes
- the Mac planning docs get reorganized

When stale, move the old file to:

```text
law_program/archive/
```

Use a dated name such as:

```text
OPENCLAW_LEGAL_CHAT_HANDOFF_2026-04-25_mac-planning.md
```

Then replace `law_program/OPENCLAW_LEGAL_CHAT_HANDOFF.md` with a fresh current handoff.

Any new chat, Codex session, or implementation agent should treat this freshness rule as a first-order instruction. If the handoff appears stale, stop and ask for or create a replacement before relying on it.

## Canonical implementation authority

The canonical implementation repo is:

```text
/home/openclaw
```

That repo lives on the PC/WSL OpenClaw system and remains the implementation authority.

The Mac workspace is:

```text
/Users/hwinshipwheatley/OpenClaw_Watch
```

The Mac workspace is a planning/reflection surface. It is not canonical implementation truth.

When editing Legal planning docs, agents may start the short-lived sync window:
`/home/openclaw/mac_eyes/Launchers/start_legal_planning_sync_window.sh`
It self-expires and must not be treated as a permanent watcher.

Do not implement blindly from the Mac planning docs. First verify the current PC/WSL repo state.

## Known Legal v0 work already built on PC/WSL

The Legal v0 foundation was built in `/home/openclaw` before this Mac planning session, then audited in the canonical PC/WSL repo.

Before the first safety slice, the focused Legal v0 suite was verified at:

```text
80 passed
```

Verified Legal v0 pieces include:

- `legal/matter_workspace.py`
  - matter workspace creation
  - manifest
  - audit log
  - source copy/registration
  - SHA-256 source tracking

- `legal/local_ingestion.py`
  - local extraction for `.txt`
  - local extraction for `.md`
  - text-layer `.pdf` extraction through local `pdftotext` path
  - unsupported / no-text / failed extraction statuses

- `legal/local_search.py`
  - literal case-insensitive search over extracted text

- `legal/search_report.py`
  - Markdown search report export

- `legal/review_packet.py`
  - folder-based review packet export
  - manifest/audit/extracted/report packet structure

- `legal/deployment_profile.py`
  - local-first deployment profile helper
  - default profile
  - legal-facing `role_labels` in new default profiles
  - validation
  - save/load stable JSON

- `legal/cli.py`
  - CLI wrapper over the legal APIs
  - known commands:
    - `create-matter`
    - `add-source`
    - `extract`
    - `extract-all`
    - `search`
    - `report`
    - `review-packet`
    - `support-packet`
    - `default-profile`

- `scripts/demo_legal_matter_workflow.py`
  - deterministic demo workflow

- `scripts/demo_legal_mock_discovery.py`
  - synthetic mock discovery CLI run-through
  - strict `--vault-root` demo outside `/home/openclaw`

- Legal docs/checkpoints
  - `legal/README.md`
  - `legal/CLI_DEMO_WALKTHROUGH.md`
  - `legal/CHECKPOINT.md`

- Legal tests
  - focused Legal v0 suite passed before the safety slice: `80 passed`

## Completed first safety slice

The first Legal safety slice is implemented in `/home/openclaw`.

Commit:

```text
f086b3c feat(legal): enforce matter vault path boundaries
```

New file:

- `legal/path_guard.py`

Updated implementation files:

- `legal/matter_workspace.py`
- `legal/local_ingestion.py`
- `legal/local_search.py`
- `legal/search_report.py`
- `legal/review_packet.py`

Implemented behavior:

- matter roots are canonicalized/resolved before use
- matter workspaces resolving under `/home/openclaw` are rejected
- symlink/traversal into the product repo is rejected
- manifest `stored_path` values are validated before extraction/search/report/review-packet trust them
- tampered `stored_path` values outside the matter root fail closed

Proof:

- `py_compile` passed for changed legal modules
- focused new/updated path-guard tests: `7 passed`
- full focused Legal suite after the slice: `87 passed in 1.37s`

Remaining risks:

- review packets remain content-bearing and are not sanitized support packets
- firm/update/profile policy boundaries remain future slices

## Completed second safety slice

The second Legal safety slice is implemented in `/home/openclaw`.

Commit:

```text
9474b7c feat(legal): add optional vault root allowlist
```

The slice added optional strict Legal Vault allowlist behavior.

Strict mode is opt-in through:

- `allowed_vault_roots` in Legal APIs
- `--vault-root` in CLI matter-root workflows
- optional `storage.vault_roots` validation in deployment profiles

Calls without a vault root preserve the existing repo-boundary guard behavior from the first safety slice.

Updated implementation files:

- `legal/path_guard.py`
- `legal/matter_workspace.py`
- `legal/local_ingestion.py`
- `legal/local_search.py`
- `legal/search_report.py`
- `legal/review_packet.py`
- `legal/cli.py`
- `legal/deployment_profile.py`

Updated tests:

- `tests/test_matter_workspace.py`
- `tests/test_legal_cli.py`
- `tests/test_deployment_profile.py`

Implemented behavior:

- configured vault roots are canonicalized/resolved
- vault roots under `/home/openclaw` are rejected
- matter roots outside configured vault roots are rejected when strict mode is provided
- symlinked/traversal vault roots into the product repo are rejected
- temp/synthetic workflows remain allowed when strict vault mode is not provided

Proof:

- `py_compile` passed for changed legal modules
- focused vault/profile/CLI tests: `43 passed`
- vault/approved focused test subset: `11 passed, 32 deselected`
- full focused Legal suite after the slice: `98 passed in 0.89s`

Remaining risks:

- strict vault roots are still opt-in, not mandatory for all real deployments
- profile support validates `storage.vault_roots` when present but does not yet make profiles the source of truth for CLI workflows
- review packets remain content-bearing and are not sanitized support packets
- firm/update/profile policy boundaries remain future slices

## Completed handoff refresh after vault allowlist

Commit:

```text
132830a docs(legal): update handoff after vault allowlist
```

## Completed third safety slice

The sanitized support packet v0 slice is implemented in `/home/openclaw`.

Commit:

```text
202d7f0 feat(legal): add sanitized support packet
```

New file:

- `legal/support_packet.py`

Updated files:

- `legal/cli.py`
- `tests/test_support_packet.py`
- `tests/test_legal_cli.py`
- `.gitignore` narrow allowlist for `legal/support_packet.py` and `tests/test_support_packet.py`

CLI command added:

```text
support-packet --root ... [--vault-root ...] [--packet-name ...]
```

Implemented behavior:

- `export_support_packet()` creates a separate sanitized support artifact path
- support packets are distinct from review packets
- packets write under `support/support-packet-*/support_packet.json` inside the matter root
- packets include counts, file extensions, size ranges, source status diagnostics, module info, and explicit exclusion proof
- packets exclude source files, extracted text, review packet contents, attorney notes, matter/client names, sensitive filenames, private absolute paths, and raw audit logs

Proof:

- `py_compile` passed for `legal/support_packet.py` and `legal/cli.py`
- support-packet focused tests: `6 passed, 12 deselected`
- full focused Legal suite after the slice: `104 passed in 1.07s`

Remaining risks:

- support packet v0 is minimal
- it does not yet include unsupported-file Alternative Methods
- it does not include public analog fixture search
- it does not make escalation/support policy decisions
- unrelated Cassandra/Chief/Hermes dirty files remain outside Legal

## Completed role-label cleanup

Commit:

```text
efc9c70 fix(legal): use legal-facing role labels
```

Implemented behavior:

- default deployment profiles now emit `role_labels`, not `agent_labels`
- default role IDs/labels are legal-facing:
  - `intake_clerk`: Intake Clerk
  - `evidence_clerk`: Evidence Clerk
  - `records_custodian`: Records Custodian
  - `review_coordinator`: Review Coordinator
  - `compliance_gate`: Compliance Gate
  - `systems_clerk`: Systems Clerk
- `validate_deployment_profile()` still accepts legacy saved profiles with `agent_labels`
- Legal README no longer directly lists internal OpenClaw agent names

Proof:

- `py_compile` passed for `legal/deployment_profile.py`
- focused deployment profile / CLI tests: `31 passed`
- full focused Legal suite after the slice: `107 passed in 1.05s`

Remaining risks:

- legacy saved profiles with `agent_labels` still validate by design
- no on-disk profile migration exists yet
- planning docs may still mention forbidden names as “do not expose” examples

## Completed synthetic mock discovery demo harness

Commit:

```text
7e238de test(legal): add mock discovery demo harness
```

New files:

- `scripts/demo_legal_mock_discovery.py`
- `tests/test_legal_mock_discovery_demo.py`

Usable command:

```bash
python3 scripts/demo_legal_mock_discovery.py /tmp/openclaw_legal_mock_discovery_run
```

Implemented behavior:

- creates a synthetic mock discovery batch under a temp/demo-safe vault root outside `/home/openclaw`
- uses strict `--vault-root` mode
- registers TXT, MD, text-layer PDF, valid synthetic no-text PDF behavior, and unsupported fake extension
- runs `extract-all`, search, report, review packet, and sanitized support packet
- verifies product repo data written: `false`

Demo output summary from the initial implementation pass:

- source count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `0`
- failed: `1`
- search results: `3`
- report generated
- review packet generated
- support packet generated
- product repo data written: `false`

Note: this initial placeholder behavior was superseded by the later no-OCR PDF status hardening slice.

Proof:

- `pytest -q tests/test_legal_mock_discovery_demo.py`: `1 passed`
- full focused Legal suite including demo test: `108 passed in 1.22s`

## Completed status consistency fix

Commit:

```text
068212e fix(legal): align extraction status diagnostics
```

Implemented behavior:

- extraction now records private per-source `extraction_status`, `extraction_extractor`, timestamp, and reason in the matter manifest for every attempted source
- tracked statuses include `extracted`, `unsupported`, `no_text`, and `failed`
- support packets prefer manifest extraction status over inferred status
- failed attempted PDF extraction no longer appears as `pending`
- mock discovery demo status counts now match support packet diagnostics
- sanitized support packet boundaries remain preserved: no source content, extracted text, private paths, or sensitive filenames

Demo rerun status counts:

- extracted: `3`
- failed: `1`
- no_text: `0`
- pending: `0`
- unsupported: `1`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for changed Legal modules/scripts
- support/demo focused tests: `7 passed`
- ingestion/pdf focused tests: `19 passed`
- full focused Legal suite: `109 passed in 1.18s`

Remaining gaps:

- `pending` still means extraction was never attempted
- the initial placeholder scanned-style PDF behavior was superseded by the later no-OCR PDF status hardening slice
- unsupported-file Alternative Methods is still not implemented

## Completed Alternative Methods next-action model

Commit:

```text
328eaf1 feat(legal): add alternative methods actions
```

New files:

- `legal/alternative_methods.py`
- `tests/test_alternative_methods.py`

Updated files:

- `legal/cli.py`
- `scripts/demo_legal_mock_discovery.py`
- `tests/test_legal_cli.py`
- `tests/test_legal_mock_discovery_demo.py`

CLI command added:

```bash
python3 -m legal.cli alternative-methods --root ... [--vault-root ...]
```

Implemented behavior:

- `alternative_methods_for_matter()` returns deterministic JSON-ready records for unsupported, failed, or no_text sources
- output excludes source text, extracted text, filenames, private paths, and raw audit logs
- `request_feature` remains locked by default
- no OCR, UI, local repair/build, request-feature export, or public analog search was implemented
- mock discovery demo now reports `alternative_methods_count`

Demo rerun summary:

- alternative_methods_count: `2`
- extracted: `3`
- failed: `1`
- no_text: `0`
- pending: `0`
- unsupported: `1`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for `legal/alternative_methods.py`, `legal/cli.py`, and `scripts/demo_legal_mock_discovery.py`
- focused Alternative Methods/CLI/demo tests: `20 passed`
- full focused Legal suite: `115 passed in 1.27s`

Remaining gaps:

- `try_local_capability` is only an action label
- `request_feature` stays locked unless a future policy enables escalation
- OCR is not implemented
- public analog fixture search is not implemented

## Completed no-OCR PDF status hardening

Commit:

```text
20312df fix(legal): harden no-text PDF status
```

Updated files:

- `scripts/demo_legal_mock_discovery.py`
- `tests/test_pdf_ingestion.py`
- `tests/test_alternative_methods.py`
- `tests/test_support_packet.py`
- `tests/test_legal_mock_discovery_demo.py`

Implemented behavior:

- mock discovery demo now uses a valid synthetic no-text PDF instead of a malformed placeholder PDF
- valid no-text PDF reports `no_text`, not `failed`
- malformed/minimal PDF remains `failed`, not `no_text`
- Alternative Methods surfaces `ocr_module_needed` for valid no-text PDF
- support packet diagnostics preserve `no_text`
- OCR is still not implemented

Demo rerun summary:

- source_count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `1`
- failed: `0`
- pending: `0`
- alternative_methods_count: `2`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed
- focused PDF/Alternative Methods/support/demo tests: `22 passed`
- full focused Legal suite: `117 passed in 1.46s`

Remaining gaps:

- OCR is still not implemented
- local repair/build is not implemented
- public analog fixture search is not implemented
- malformed/corrupt PDFs correctly remain `failed`

## Completed local capability policy/stub

Commit:

```text
92e16e5 feat(legal): add local capability policy states
```

New file:

- `legal/local_capability_policy.py`

Updated files:

- `legal/alternative_methods.py`
- `tests/test_alternative_methods.py`

Implemented behavior:

- Alternative Methods items now include deterministic local capability policy metadata:
  - `local_capability_state`
  - `local_capability_kind`
  - `local_capability_reason_category`
  - `request_feature_state`
- unsupported unknown extension maps to `local_capability_not_attempted` / `unknown_local_handler`
- no-text PDF maps to `local_capability_not_installed` / `ocr`
- failed PDF maps to `local_capability_failed_safely` / `pdf_text_extraction`
- `request_feature` remains locked by default
- no manifest mutation
- no new CLI command
- no OCR
- no local repair/build

Demo rerun summary:

- source_count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `1`
- failed: `0`
- pending: `0`
- alternative_methods_count: `2`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for `legal/local_capability_policy.py`, `legal/alternative_methods.py`, and `tests/test_alternative_methods.py`
- focused Alternative Methods/support/demo tests: `13 passed`
- full focused Legal suite: `117 passed in 1.27s`

Remaining gaps:

- OCR is still not implemented
- local repair/build and sandbox execution are still not implemented
- public analog search and request-feature export are still not implemented
- support packet diagnostics were not enriched in this slice

## Completed dual-mode staging intake

Commit:

```text
b45ff57 feat(legal): add dual-mode staging intake
```

Changed files:

- `legal/cli.py`
- `legal/matter_workspace.py`
- `tests/test_legal_cli.py`
- `tests/test_matter_workspace.py`

CLI command added:

```bash
python3 -m legal.cli import-staging \
  --vault-root <vault_root> \
  --root <matter_root> \
  --staging-dir <staging_dir> \
  --lane <synthetic|real-matter>
```

Implemented behavior:

- `--lane` is mandatory, no default
- `--staging-dir` is mandatory
- `--vault-root` is mandatory
- invalid lane rejected by `argparse`
- staging/matter/vault paths must resolve outside `/home/openclaw`/product repo boundaries
- matter root must resolve inside approved vault root
- symlink/traversal staging escapes rejected
- imports regular files only; skips directories
- original staging files are preserved
- files are copied/registered through existing source registration path
- hashes/source IDs preserved through existing source registration
- audit entry written for `staging_import` including lane, context, counts, path validation, and timestamp
- manifest sources tagged with `staging_import_lane`, `staging_import_context`, and `staging_imported_at`
- `synthetic` lane maps to `synthetic`
- `real-matter` lane maps to `real_matter_local_only`
- explicitly marked synthetic fixture packs are rejected for real-matter intake
- raw staging absolute path was removed from audit and CLI JSON output for privacy
- no OCR, video/audio, timeline, contradiction, LLM, email/cloud, or external tool scope was added

Proof:

- `py_compile` passed for `legal/cli.py` and `legal/matter_workspace.py`
- focused tests passed: `52 passed`
- full focused Legal suite passed: `127 passed in 1.74s`

## Completed local image OCR prototype

Commit:

```text
88177ac feat(legal): add local image OCR prototype
```

Changed files:

- `legal/local_ingestion.py`
- `legal/alternative_methods.py`
- `legal/local_capability_policy.py`
- `legal/support_packet.py`
- `tests/test_local_ingestion.py`
- `tests/test_alternative_methods.py`
- `tests/test_support_packet.py`

Implemented behavior:

- local-only OCR prototype for image files:
  - `.png`
  - `.jpg`
  - `.jpeg`
- uses local Tesseract CLI only
- dynamically checks for Tesseract
- if Tesseract is present:
  - runs `tesseract <input_path> stdout`
  - uses bounded timeout
  - writes OCR text through existing extracted artifact path
  - marks status `extracted`
  - uses extractor `tesseract_ocr_v0`
  - prepends `[Extracted via local OCR]`
- if Tesseract is missing:
  - no crash
  - no subprocess call
  - image files record safe OCR-needed/unsupported behavior
  - reason `ocr_module_not_installed`
  - Alternative Methods surfaces `ocr_module_needed`
- if Tesseract fails or times out:
  - status `failed`
  - reason `ocr_process_failed`
  - raw stderr/exceptions/private paths are not stored in sanitized outputs
- support packet reports sanitized extension/status/extractor/reason metadata only
- no OCR text/private paths in support packets
- no scanned PDF OCR
- no video/audio OCR
- no cloud OCR
- no external OCR services
- no LLM OCR cleanup
- no timeline/contradiction candidates

Proof:

- `py_compile` passed for OCR-touched Legal modules
- focused OCR/support tests passed: `29 passed`
- full focused Legal suite passed: `133 passed in 1.59s`

## Completed short-lived planning sync helper

Commit:

```text
f0f4707 docs(legal): add short-lived planning sync helper
```

Helper path:

- `/home/openclaw/mac_eyes/Launchers/start_legal_planning_sync_window.sh`

Implemented behavior:

- short-lived PC→Mac Legal planning sync window
- self-expires after 20 minutes (1200 seconds max)
- checks every 60 seconds
- not a permanent watcher; no cron or background daemon installed

## Completed Known-Answer Fixture Pack v0

Commit:

```text
96eb365 test(legal): add known-answer fixture pack
```

Changed files:

- `.gitignore`
- `scripts/demo_legal_known_answer_fixtures.py`
- `tests/test_known_answer_fixtures.py`

Command added:

```bash
python3 scripts/demo_legal_known_answer_fixtures.py [OUTPUT_ROOT]
```

Optional generation-only mode:

```bash
python3 scripts/demo_legal_known_answer_fixtures.py --generate-only [OUTPUT_ROOT]
```

Implemented behavior:

- creates a synthetic Lane A known-answer fixture pack outside `/home/openclaw`
- default output root: `/tmp/openclaw_legal_known_answer_fixtures`
- creates `fixture_staging/`
- creates explicit synthetic fixture marker: `.openclaw-synthetic-fixture-pack/manifest.json`
- creates known searchable text fixture: `known_answer_note.txt` with term `fixture-omega-42`
- creates synthetic image fixture: `synthetic_scan.png`
- creates unsupported fake extension: `unsupported_payload.openclawfake`
- imports through existing `import-staging --lane synthetic` flow
- runs existing extraction/search/support/Alternative Methods paths
- returns/writes expected-vs-actual summary including source counts, extraction/status behavior, searchable term found, support packet redaction, and `product_repo_data_written` false
- existing real-matter marker rejection blocks explicitly marked fixture packs from real-matter intake
- no real matter data
- no external LLMs/cloud tools
- no scanned PDF OCR
- no video/audio
- no timeline/contradiction candidates
- no checker AI

Proof:

- focused fixture/Legal tests passed: `75 passed`
- full focused Legal suite including known-answer fixtures passed: `139 passed in 1.79s`
- script smoke run completed with `known_answer_passed: true`

## Completed Phase 1 workstation bridge scripts

Commit:

```text
4c77421 feat(legal): add workstation bridge scripts
```

Changed files:

- `.gitignore`
- `mac_eyes/Launchers/scaffold_mac_legal_vault.sh`
- `scripts/run_legal_pipeline_v0.sh`

Implemented behavior:

- Added Mac Obsidian control vault scaffold script.
- Default Mac vault target: `~/OpenClawLegalPrivate/Matter_Alpha_Workspace`.
- Creates:
  - `00_START_HERE.md`
  - `01_DROP_FILES_HERE/`
  - `03_STATUS.md`
  - `04_OUTPUTS/`
  - `05_SUPPORT_PACKET_REVIEW.md`
  - `.openclaw_config/matter_config.env`
  - `Run_OpenClaw_Dry_Run.command`
  - Desktop symlink: `~/Desktop/OpenClaw Legal Matter Alpha`
- Config includes editable `PC_SSH_TARGET` plus PC repo/vault/staging/export paths.
- Added PC-side runner: `scripts/run_legal_pipeline_v0.sh`.
- PC private paths (outside `/home/openclaw`):
  - `/mnt/c/OpenClawLegalPrivate/vault`
  - `/mnt/c/OpenClawLegalPrivate/staging/<matter_id>`
  - `/mnt/c/OpenClawLegalPrivate/exports/<matter_id>`
- Runner uses existing Legal CLI: `create-matter`, `import-staging --lane real-matter`, `extract-all`, `search`, `report`, `review-packet`, `support-packet`, `alternative-methods`.
- Keeps real matter data outside `/home/openclaw`.
- Mac button/launcher flow: Open vault → drop copied files → double-click `Run_OpenClaw_Dry_Run.command` → read `03_STATUS.md` and `04_OUTPUTS/`.
- No Legal Python implementation code changed.
- No scanned PDF OCR, video/audio, timeline, contradiction, checker AI, cloud tool, or external LLM behavior added.

Proof:

- `bash -n` passed for both scripts.
- Scaffold proof generated expected files/directories with safe temp override.
- Generated launcher mode: `700`.
- Desktop symlink proof passed in temp proof desktop.
- Default WSL/openclaw vault creation was refused without creating private vault data.
- PC runner proof with one synthetic dummy file succeeded.
- Export proof: `reports=1`, `review_packets=1`, `support_files=1`.
- Verified no `/home/openclaw/OpenClawLegalPrivate` was created.
- Final git status after commit was clean.

## Completed Mac Obsidian control-surface proof

A Mac-side local Obsidian prototype now exists in the private vault, providing a real control-surface proof of concept for operator comfort.

Key proven facts:

- **Prototype Status:** Proven as a prototype operator comfort layer. It is NOT the final sellable Legal Console UX.
- **Path Boundary Proof:** Mac vault at `~/OpenClawLegalPrivate/Matter_Alpha_Workspace`. PC private paths remain outside `/home/openclaw` at `/mnt/c/OpenClawLegalPrivate/`.
- **Action Buttons:** Real Obsidian buttons (via `openclaw-legal-actions` local plugin) for Open Drop Folder, Create Dummy Test File, Run OpenClaw Dry Run, Reset Local Test, and Reset All Test State.
- **Intake Safety Discovery:**
  - **Direct Drag/Drop is UNSAFE:** Proven ambiguous because attachments can land outside `01_DROP_FILES_HERE/`.
  - **Safe Path:** Click "Open Drop Folder" → use Finder → put files in exact intake folder.
- **Evidence-Only Intake:** `01_DROP_FILES_HERE/` must contain only evidence intended for processing. Instruction notes were moved to `02_ACTIONS/ADD_FILES.md`.
- **Clean Dummy Proof Result:** After full reset, processing a single dummy file resulted in `Status: Done`, Search Report result count 1, and no stale/instruction files in the output.
- **Reset Logic:** Functional, test-only, and confirmation-gated state reset.

### Remaining gaps

- **Scaffold Packaging:** The Obsidian prototype (action-note/plugin pattern) is not yet packaged into the reusable PC `scaffold_mac_legal_vault.sh` script.
- **Improved Summaries:** Cleaner `04_CASE_NOTES` output summaries and the PC-side `agent_readable` area are still future work.
- **Real Matter Proof:** Real personal matter has not been run through this bridge yet.
- **Safety Warning:** Real matter should not be used until the dummy/scaffold pattern is packaged and reviewed. First bridge use should remain dummy/synthetic files only.
- **macOS Native Alias:** The desktop shortcut is currently a symlink, not a native macOS alias.

## Completed static Legal Console spike scaffold

Commit: `c35c58a feat(legal): add static console spike scaffold`

App path:
`apps/legal-console-spike/`

What was built (Phase 0 + Phase 1 only):
- A static/disposable Tauri-shaped GUI scaffold was created.
- Scaffolding includes `package.json`, `index.html`, `tsconfig.json`, `src` TypeScript files (`main.ts`, `legalConsole.ts`, etc.), and `src-tauri` Rust files (`Cargo.toml`, `main.rs`, etc.).
- Narrow `.gitignore` allowlist for `apps/legal-console-spike/`.

What was intentionally not built:
- No command execution is wired.
- No bridge invocation.
- No file picker.
- No private vault reading.
- No Legal Python engine edits.
- No dependency install.
- No GUI launch.

Proof summary:
- `git diff --check` passed.
- `bash -n` checks on related shell scripts passed.
- Verified no `/home/openclaw/OpenClawLegalPrivate` exists.
- Forbidden UX string scan passed (no "Cassandra", "AI lawyer", "lawyer replacement", etc.).
- JSON parsing and Cargo metadata checks passed without installing dependencies.
- Expected app files are visible to git and VS Code diagnostics showed no errors.

Why this is a rollback/checkpoint boundary:
- This confirms the static GUI shell exists, but does not prove runtime Tauri launch, command execution, file selection, bridge invocation, status refresh, or real legal use.
- It acts as a clean checkpoint before any Phase 2 command wiring.

Next step: Phase 2B command wiring is separate and should remain gated by audit findings. Status refresh is now completed as the narrow Phase 2A checkpoint below.

## Completed Phase 2A Legal Console status refresh

Commit: `4b4710c feat(legal): add console status refresh`

App path:
`apps/legal-console-spike/`

What was built (Phase 2A only):
- Added a read-only Legal Console status refresh path.
- Added Tauri/Rust command: `get_status_snapshot`.
- Added frontend status refresh handling in `apps/legal-console-spike/src/legalStatus.ts`.
- Added Rust status implementation in `apps/legal-console-spike/src-tauri/src/status.rs`.
- Fixed the `.gitignore` allowlist so `apps/legal-console-spike/src-tauri/src/*.rs` files are visible/tracked.
- Tauri capabilities remain minimal: `core:default` only.

Allowed fixed status reads:
- `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/03_WORKSTATION_STATUS.md`
- `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md`
- Existence check only for `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/00_OPEN_THIS_FIRST.md`

Sanitized fields returned:
- `workstation_status_present`
- `workstation_state`
- `workstation_last_updated`
- `primary_status_present`
- `primary_state`
- `primary_last_updated`
- `outputs_guide_present`
- `boundary_state`
- `warnings`
- `errors`

What remains intentionally unwired:
- No command execution.
- No file picker/open folder.
- No dummy-file creation.
- No bridge invocation.
- No Legal Python engine edits.
- No broad filesystem, shell, dialog, opener, or network permissions.
- No reads of intake files, source files, extracted text, reports, review packets, support packet bodies, audit logs, arbitrary files/directories, or real matter contents.

Proof summary:
- `git diff --check` passed.
- `bash -n mac_eyes/Launchers/scaffold_mac_legal_vault.sh` passed.
- `bash -n scripts/run_legal_pipeline_v0.sh` passed.
- `test ! -e /home/openclaw/OpenClawLegalPrivate` passed.
- Forbidden UX string scan passed.
- JSON parse checks passed.
- `cargo metadata --no-deps` passed.
- VS Code diagnostics showed no errors.
- `npm run check/build` was intentionally skipped because `node_modules` is missing and dependency install was not approved.
- `cargo check` was intentionally skipped because offline mode could not resolve uncached `serde_json` and dependency fetch was not approved.

Why this is a rollback/checkpoint boundary:
- This proves the narrow read-only status-refresh implementation at the code/scaffold level.
- It does not prove runtime Tauri launch, command execution, file selection/open folder, bridge invocation, or real legal use.
- It keeps Phase 2A reversible and reviewable before any Phase 2B control expansion.

Next step: Phase 2B should be planned separately. The likely next GUI slice is open-intake-folder, not dummy creation or command execution yet.

## Dual-Lane Development Model

OpenClaw Legal now adopts a **Dual-Lane Development Model** to balance innovation with data safety:

- **Lane A: Synthetic Product R&D Lane**
  - For experimenting with synthetic/public-safe data.
  - External LLMs/tools are permitted for R&D and fixture generation.
  - No real matter data allowed.

- **Lane B: Real Matter Local-Only Lane**
  - For processing real evidence/matter data.
  - External LLMs/tools are prohibited by default.
  - Only local deterministic tools allowed until local models are approved.

Both lanes share the OpenClaw Legal product core but maintain strict data separation. Fake data is for experimentation; real data is for proving trust.

## Strong Product Roadmap

The "Strong Product" vision for OpenClaw Legal is **Private local discovery intelligence for law firms.** The current foundation is the safe local spine that makes the strong product trustworthy.

Phased capability ladder:
1. **Current local discovery spine:** Vault, registration, extraction (text/PDF), search, packets.
2. **Local drop-folder intake:** Streamlined staging and import.
3. **OCR for screenshots/scanned PDFs:** Processing text messages and image-only discovery.
4. **Audio/video extraction:** Transcription and frame-based OCR.
5. **Timestamp/text metadata:** Extracting visible time references and metadata.
6. **Timeline candidates:** Automated draft chronology from multi-source evidence.
7. **Contradiction candidates:** Identifying factual inconsistencies across sources.
8. **Attorney-gated QA/rework loop:** Human-in-the-loop review and refinement of candidates.
9. **Later local LM synthesis:** Advanced analysis under strict Lane B rules.

The roadmap ensures that high-value outputs (timelines, contradictions) remain source-linked attorney-review aids, never substitute legal advice.

## What was planned in the Mac workspace

The Mac planning session created and organized a planning package under:

```text
/Users/hwinshipwheatley/OpenClaw_Watch/law_program
```

The planning package includes technical/product contracts, UX specs, business planning docs, risk docs, and launch decision gates.

## Technical/product contracts created or populated

These documents define product architecture, safety boundaries, update behavior, role naming, vault separation, node connection, queueing, ETA, and model distribution:

- `LEGAL_PRODUCT_CORE_SEPARATION.md`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT.md`
- `LEGAL_VAULT_PATH_CONTRACT.md`
- `LEGAL_ROLE_NAMING_CONTRACT.md`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST.md`
- `LEGAL_UPDATE_LANE_CONTRACT.md`
- `LEGAL_CONNECT_MENU_CONTRACT.md`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT.md`
- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT.md`
- `LEGAL_ADAPTIVE_ETA_CONTRACT.md`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT.md`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`
- `LEGAL_V1_CONTRACT_INDEX.md`

## Business planning docs created or populated

These documents define the buyer problem, business plan, pitch deck, mockups, pricing, gotchas, opportunity models, and go/no-go launch criteria:

- `business_plan/BUSINESS_PLAN_INDEX.md`
- `business_plan/OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_PLAN.md`
- `business_plan/OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`
- `business_plan/OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`
- `business_plan/OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`
- `business_plan/OPENCLAW_LEGAL_GOTCHAS.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`
- `business_plan/OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`

## Critical doctrine

The following points are binding planning doctrine for the next chat:

- Mac `OpenClaw_Watch` docs are planning/reflection only.
- PC/WSL `/home/openclaw` is canonical implementation authority.
- **Dual-Lane Development Model** is mandatory: Lane A uses only synthetic/public-safe data and may use external tools; Lane B uses real matter data and is local-only by default.
- **Personal Matter Local-Only Usage Doctrine** is mandatory: The user's personal matter is strictly Lane B. No external LLM or tool may process personal case contents. Local-only capabilities may be used to generate attorney-review aids, not legal advice. Personal matter content must not leak into Lane A (no fixtures, prompts, or demos).
- **IP / Pilot / Ownership Doctrine** is mandatory: Developer owns reusable product core and reference bench; Firm owns private matter data, work product, and production hardware; Validated Update Pipeline (test on bench first, then offer packaged updates) is required.
- **Attorney-Gated QA / Review-and-Rework Doctrine** is mandatory: System creates first pass; separate checker performs evidence-verification (claims verification against source records); flag model (Green/Yellow/Red); attorney-controlled rework loop; no silent fixes; no legal conclusions without review.
- **Known-Answer Fixtures / Validation Sentinels Doctrine** is mandatory: Use seeded synthetic/public-safe evidence packs to benchmark and validate OCR, checker reliability, and update safety; Lane A only; no matter contamination.
- **Hardware Ladder / Capability Tiers Doctrine** is mandatory: Firm buys private local discovery infrastructure, not a chatbot; hardware tiers affect speed and capacity; developer reference bench is separate from firm production hardware; capability claims must be benchmarked; no unvalidated hype.
- **Strong Product Roadmap:** Current work is the safe local spine; future phases include OCR (screenshots/scanned), A/V extraction, timeline candidates, and contradiction detection.
- Do not implement blindly from Mac docs.
- First inspect existing Legal v0 code, tests, docs, and commits.
- No real legal data should enter the repo, prompts, support packets, update packages, or non-local LLM context.
- Legal product UX must not expose internal OpenClaw agent names such as Cassandra, Chief, Guardian, Hermes, or PI.
- Legal-facing roles should use plain law-office labels such as Intake Clerk, Evidence Clerk, Records Custodian, Review Coordinator, Compliance Gate, and Systems Clerk.
- The Go/No-Go Launch Criteria sits above the business plan.
- This should become a bounded product/support business, not a stressful law-firm emergency support job.
- Firm #2 changes must never affect Firm #1 unless Firm #1 explicitly installs/enables them.
- Matter Vault must stay separate from product core and firm profile.
- Unsupported files must use local-first Alternative Methods before feature-request escalation.
- Updates must be lane-based: security, stability, installed module updates, and optional new modules.
- Primary Node should own vault, policy, audit, updates, model distribution, and orchestration.
- Worker/lawyer nodes must not silently join or receive broad matter access by default.
- ETA must be conservative, confidence-labeled, and calibrated before high-confidence claims.
- Huge local models are not the product foundation; deterministic vault/source/search/report/audit/queue boundaries come first.

## Current strategic posture

OpenClaw Legal should be framed as:

```text
Private local discovery infrastructure for law firms that need control, speed, auditability, and predictable cost.
```

It should not be framed as:

- an AI lawyer
- a lawyer replacement
- a generic chatbot
- a complete enterprise e-discovery replacement on day one
- a system that gives legal advice
- a system that removes the need for attorney review

The first sellable version should focus on a controlled local foundation:

- Legal Vault boundary
- matter/source tracking
- hashing
- local extraction
- search
- reports
- review packets
- audit trail
- visible status
- unsupported-file workflow
- update/profile architecture

## Business/launch caution

The user is willing to invest upfront time and build effort, but does not want this to become:

- a painful daily operations job
- a law-firm emergency support desk
- a source of lawsuit risk
- an unlimited custom development trap
- a personally stressful on-call role

The business should aim for passive-ish or remote-managed income where possible, with bounded setup, bounded support, paid modules, clear legal disclaimers, and strict support limits.

No real firm deployment should happen without:

- written scope
- payment/hardware agreement
- support boundary
- liability limitation
- no-legal-advice language
- attorney review requirement
- data ownership terms
- local-only/data residency expectations
- update/support terms
- emergency/rush support pricing or exclusion
- permission to use only sanitized diagnostics for product improvement

## GUI pre-plan recommendation

Date/context: 2026-04-28, after the Phase 1 Mac Obsidian control-surface proof and clean dummy bridge proof.

Recommendation: start a controlled desktop GUI spike now.

Mac execution lane and tooling gate, verified 2026-04-28:

- PC/WSL Codex can reach the Mac with `ssh mac`; the scout command `ssh mac 'hostname; pwd; whoami'` returned the Mac host/user context successfully.
- Bounded `rsync` works PC to Mac and Mac to PC when both sides use only synthetic `/tmp/openclaw_legal_*` paths.
- Allowed Mac paths for future GUI-spike work are `~/OpenClawLegalPrivate/Matter_Alpha_Workspace`, `~/OpenClawLegalDev`, `~/OpenClaw_Watch/law_program`, and `/tmp/openclaw_legal_*`.
- `~/OpenClawLegalPrivate/Matter_Alpha_Workspace` exists, is writable, and is not a symlink. Only top-level vault names were listed; real matter contents were not read.
- `~/OpenClawLegalDev` did not exist during the scout but its parent is writable, so it may be created later only when an implementation prompt explicitly authorizes it.
- The Mac has Rust/Cargo, Xcode Command Line Tools, and Python available. The Mac shell does not currently expose `node` or `npm` on `PATH`.
- Do not install or enable tooling from Codex without explicit approval. Do not start building Tauri until the Node/npm decision is approved.
- Future Mac commands must stay path-bounded. Do not search the Mac home directory broadly, do not copy private matter files, do not read real matter file contents, and do not create symlinks between the product repo and the private vault.

Cross-platform architecture requirement for the GUI spike:

- Treat the first GUI as a cross-platform-shaped console, not a Mac-only one-off.
- Separate shared UI from OS adapters. Shared UI covers status display, intake workflow, run/reset controls, output links, and boundary warnings.
- Document adapters for macOS, Windows, Linux, and WSL-backed Primary Node operation even if only the macOS workstation to PC/WSL Primary Node path is proven first.
- Define a Primary Node abstraction with `local`, `ssh`, and future firm-local API transport options so the UX model does not change when transport changes.
- Use config for product code path, workstation vault path, primary node vault root, staging path, exports path, transport type (`local` or `ssh`), and OS type (`macos`, `windows`, `linux`, or `wsl`).
- Do not hardcode the spike to one user, one machine pair, WSL-only primary nodes, Mac-only workstations, or one folder layout beyond configured defaults.
- Unimplemented OS adapters should be explicit stubs or documentation targets, not hidden assumptions.

Tooling decision for the next implementation prompt:

- Preferred path: keep Tauri as the intended desktop direction, but gate implementation on an approved Node/npm plan for the Mac.
- Do not use PC-side static build plus Mac asset sync as the primary path unless native-window behavior is deliberately deferred; it weakens the desktop proof.
- Do not switch to a Rust-only alternative unless the team accepts a smaller UI toolkit/prototyping surface than Tauri.
- If Node/npm remains unavailable and no install/enable step is approved, defer Tauri and use a local web/static shell only as a temporary architecture sketch, not as the desktop-console proof.

Why:

- The Obsidian prototype proved operator comfort, real local buttons, the safe Finder drop-folder path, dummy bridge processing, and reset behavior.
- It also proved the core risk: direct Obsidian drag/drop is ambiguous and can place files outside `01_DROP_FILES_HERE/`.
- Obsidian remains useful as a prototype/private operator surface, but it should not receive more credit-heavy polish as the final sellable UX unless the product contract deliberately changes.
- The controlled console direction is already supported by `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`: the sellable product should be a bounded legal operations console, not an Obsidian-only vault.
- The existing local bridge is enough to support a thin GUI spike without rewriting the Legal engine.

Smallest next slice:

- Create a disposable controlled GUI spike that reuses existing bridge commands and shows only a narrow status/intake flow.
- Mac workstation surface: choose/open the exact evidence-only drop folder, select or drag/drop copied files into that folder safely, run the existing bridge command, and show workstation/output status.
- PC/WSL Primary Node surface: show configured vault/staging/export paths, last primary-node status, local-only/security boundary status, and whether outputs exist.
- Reuse existing commands rather than replacing Legal logic: `Run_OpenClaw_Dry_Run.command`, `Reset_Test_Run.command`, `Reset_All_Test_State.command`, and `scripts/run_legal_pipeline_v0.sh`.
- Keep product code in `/home/openclaw`, Mac workstation data in `~/OpenClawLegalPrivate`, and PC matter data in `/mnt/c/OpenClawLegalPrivate`.
- Use dummy/synthetic files only. Real matter data has not been run through this bridge and must stay out of prompts, repo, support packets, update packages, and non-local tools.

What must not be built yet:

- Connect/distributed workers, node enrollment, model distribution, model routing, timeline candidates, contradiction candidates, privilege screening, email/cloud import, scanned-PDF expansion, broad OCR expansion, attorney-replacement language, legal advice, or any UI using internal OpenClaw agent names.
- Do not build an Obsidian plugin polish pass as the main next product slice.
- Do not migrate matter data into `/home/openclaw`.
- Do not use real legal data for GUI proof.

Stop conditions:

- The spike cannot prove matter data stays outside `/home/openclaw`.
- The GUI needs broad Legal backend rewrites instead of reusing the bridge.
- The spike requires cloud services, external LLMs, telemetry, or non-local matter-data handling.
- File intake cannot be constrained to the exact evidence-only folder.
- Dependencies or packaging complexity exceed a one-screen proof.
- The scope drifts toward Connect, distributed workers, model distribution, timeline/privilege/email/OCR expansion, or real-matter operation.

Proof expectations for the later build slice:

- `git diff --check` passes for changed files.
- `bash -n mac_eyes/Launchers/scaffold_mac_legal_vault.sh` passes if touched.
- `bash -n scripts/run_legal_pipeline_v0.sh` passes if touched.
- GUI/static smoke test proves the drop target resolves to `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE` or a safe temp equivalent.
- Dummy run still produces `Status: Done`, one known search result for the dummy query, and no stale instruction files in the output summary.
- Reset commands remain distinct: local reset clears only Mac drop/outputs; full test reset remains confirmation-gated and refuses unsafe PC paths.
- Proof verifies no `/home/openclaw/OpenClawLegalPrivate` exists and no matter artifacts are written under `/home/openclaw`.
- UI string scan finds no internal OpenClaw agent names in legal UX.
- Final proof uses dummy/synthetic files only and does not print file contents.

Reminder: the Obsidian prototype is proven but is not the final sellable UX. It should remain a private prototype/operator comfort surface unless a future contract deliberately reclassifies it.

Reminder: real matter data has not been run through this bridge. It must stay out of prompts, repo, public fixtures, support packets, update packages, and non-local tools.

## Recommended next step

Current Legal now has Phase 1 workstation bridge scripts, a proven Obsidian prototype control surface, dual-mode staging, local image OCR, known-answer fixtures, a short-lived planning sync helper, a static Legal Console scaffold, and the Phase 2A read-only Legal Console status refresh checkpoint.

Immediate next work:

1. **Phase 2B Legal Console planning:** Plan the next GUI slice separately, likely open-intake-folder next, while keeping dummy creation and command execution out of scope until separately approved.
2. **Runtime/dependency validation:** Future Tauri runtime launch and dependency validation remain unproven and should wait for an approved dependency/runtime check lane.
3. **Read-only OpenClaw audit Pass 0:** A broader OpenClaw audit Pass 0 may run in parallel if it stays read-only and does not inspect real matter data or private vault contents.
4. **Boundary proof:** Continue proving product code stays in `/home/openclaw`, PC matter data stays in `/mnt/c/OpenClawLegalPrivate`, Mac workstation data stays in `~/OpenClawLegalPrivate`, and no internal OpenClaw agent names appear in legal UX.

Future possible targets:

1. package or retire the Obsidian prototype pattern after the GUI spike teaches what should become product UX
2. cleaner output summaries for operator review
3. PC-side local-only agent-readable output planning under `/mnt/c/OpenClawLegalPrivate/agent_readable/<matter_id>/`, if still needed and kept invisible to non-local tools
4. first checker/QA planning over known-answer outputs

Do not imply scanned PDFs/video/audio/timeline/contradiction/checker AI are implemented.

Do not use real matter for the GUI spike. Do not jump to email import, cloud import, real discovery, Connect, distributed workers, model distribution, or cloud connectors.

The next slice should remain small, testable, reversible, and Legal-only. It should include exact files, tests, proof commands, and rollback/checkpoint expectations.

## What not to do next

Do not immediately build:

- distributed worker nodes
- model distribution
- full desktop app
- OCR pipeline
- email/video/audio ingestion
- cloud connectors
- email/portal ingest
- privilege screening
- legal advice/synthesis
- broad LLM review modules
- hardware leasing operations

Those are later modules or business decisions. They should follow boundary hardening and first workflow proof.

## Next-chat instruction

The new chat should verify current repo state, read this handoff, then help choose and execute only the next small Legal safety/product-boundary slice.

The new chat should not spend time re-summarizing every planning doc unless asked.

The next useful output is either a tight Codex implementation prompt for the chosen slice or a direct implementation pass if the user asks Codex to proceed in `/home/openclaw`.
