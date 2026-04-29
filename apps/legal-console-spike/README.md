# OpenClaw Legal Console Spike

This is a disposable GUI spike for a controlled OpenClaw Legal desktop console. It is not production software, not a deployment package, not a sellable product UI, and not wired to live Legal processing.

Use only dummy or synthetic files with this spike. Do not place real matter data, client files, extracted text, reports, review packets, attorney notes, or private vault contents in this app directory.

## Boundary Model

Product code stays in the canonical PC/WSL repo:

```text
/home/openclaw
```

Private runtime data stays outside the product repo:

```text
Mac workstation vault: ~/OpenClawLegalPrivate/Matter_Alpha_Workspace
PC private root: /mnt/c/OpenClawLegalPrivate
PC vault root: /mnt/c/OpenClawLegalPrivate/vault
PC staging path: /mnt/c/OpenClawLegalPrivate/staging/matter_alpha
PC exports path: /mnt/c/OpenClawLegalPrivate/exports/matter_alpha
```

Matter data must not enter `/home/openclaw`.

## Current Spike State

The current bounded spike state includes Phase 2A through Phase 2F-B work: read-only status refresh, controlled Open Intake Folder, controlled status realism, the visual identity checkpoint, frontend-only intake readiness guidance, and one synthetic/test-only file creation action.

- the Tauri-shaped scaffold exists
- `get_status_snapshot` may read the fixed workstation status file
- `get_status_snapshot` may read the fixed returned Primary Node status file
- `get_status_snapshot` may check whether the fixed output guide exists
- `get_status_snapshot` returns controlled status fields for presence, state, scaffold readiness, processing state, GUI bridge state, boundary state, warnings, and errors
- `open_intake_folder` may open only the fixed intake folder: `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE`
- opening the intake folder does not read, list, copy, write, import, process, or display intake contents
- `create_synthetic_test_file` may create only `openclaw_synthetic_dummy_test_file.txt` with fixed synthetic content in the fixed intake folder
- if the fixed synthetic file already exists, the command only checks that exact fixed file for the expected synthetic content and does not display file contents
- the Intake Readiness panel is frontend-only and derives guidance from existing safe status/open-result data
- Mac runtime validation for GUI launch, status refresh, Open Intake Folder, and intake readiness is recorded in the Legal handoff
- no command execution is wired
- no file picker is wired
- no bridge script is run
- no matter selection is wired
- no production installer is built
- no processing queue, ETA, Connect workflow, or update manager is wired
- no real-matter GUI workflow is built
- no intake files, source files, reports, review packets, support packet bodies, audit logs, or arbitrary directories are read
- Create Synthetic Test File is the only write-capable GUI action, and it is synthetic/test-only
- Run Dry Run, Reset Local Test, and Reset All Test State remain disabled placeholders
- future operational controls remain disabled

The status refresh returns sanitized fields only: presence booleans, known status names, optional `Last updated` values, scaffold readiness, processing state, GUI bridge state, boundary state, warnings, and errors. It does not return raw Markdown contents or file names from private matter folders.

The intake-folder opener returns sanitized success/error state only. It does not return expanded private absolute paths, filenames, source counts, or matter data.

The synthetic test-file action returns sanitized state only: whether the fixed synthetic file was created or was already present, the fixed target label, the fixed synthetic filename, boundary state, warnings, and errors. It does not return private absolute paths, folder contents, file counts, discovered filenames, source text, or matter data.

The first proof target represented by the UI is Mac workstation to PC/WSL Primary Node over `ssh`, using dummy or synthetic files only.

## Cross-Platform Shape

The spike is organized around three layers:

- Shared UI: status panels, intake workflow, disabled run/reset controls, output placeholders, and safety language.
- OS adapters: macOS is the current proof path; Windows and Linux are explicit stubs; WSL is represented as the current Primary Node target.
- Primary Node abstraction: `ssh` is the current proof transport; `local` and `firm-local service` are future targets.

Future phases should keep these layers explicit instead of hardcoding one user, one folder layout, or one workstation/Primary Node pairing.

## Local Development

Do not install dependencies or run a GUI from this pass without explicit approval. When dependency installation is approved, the smallest local bootstrap command is:

```bash
cd apps/legal-console-spike && npm install
```

After that, static checks and local development can use:

```bash
npm run check
npm run dev
npm run tauri:dev
```

No global tools are required by the app scripts.
