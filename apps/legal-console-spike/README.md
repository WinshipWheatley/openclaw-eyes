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

Phase 0 and Phase 1 are static display only:

- the Tauri-shaped scaffold exists
- no command execution is wired
- no file picker is wired
- no bridge script is run
- no private vault contents are read
- all controls are disabled placeholders

The first proof target represented by the UI is Mac workstation to PC/WSL Primary Node over `ssh`, using dummy or synthetic files only.

## Cross-Platform Shape

The spike is organized around three layers:

- Shared UI: status panels, intake workflow, disabled run/reset controls, output placeholders, and safety language.
- OS adapters: macOS is the current proof path; Windows and Linux are explicit stubs; WSL is represented as the current Primary Node target.
- Primary Node abstraction: `ssh` is the current proof transport; `local` and `firm-local API` are future targets.

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
