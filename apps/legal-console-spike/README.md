# OpenClaw Legal Console Spike

This is a disposable GUI spike for a controlled OpenClaw Legal desktop console. It is not production software, not a deployment package, and not wired to live Legal processing.

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

## Current Phase

Phase 2B adds exact intake-folder opening only, while preserving the Phase 2A read-only status refresh:

- the Tauri-shaped scaffold exists
- `get_status_snapshot` may read the fixed workstation status file
- `get_status_snapshot` may read the fixed returned Primary Node status file
- `get_status_snapshot` may check whether the fixed output guide exists
- `open_intake_folder` may open only the fixed intake folder: `~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE`
- opening the intake folder does not read, list, copy, write, import, process, or display intake contents
- no command execution is wired
- no file picker is wired
- no bridge script is run
- no intake files, source files, reports, review packets, support packet bodies, audit logs, or arbitrary directories are read
- Add Dummy File, Run Dry Run, Reset Local Test, and Reset All Test State remain disabled placeholders

The status refresh returns sanitized fields only: presence booleans, known status names, optional `Last updated` values, boundary state, warnings, and errors. It does not return raw Markdown contents or file names from private matter folders.

The intake-folder opener returns sanitized success/error state only. It does not return expanded private absolute paths, filenames, source counts, or matter data.

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
