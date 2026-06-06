# OpenClaw Runtime Law

This is the canonical vendor-neutral runtime law for OpenClaw.

Tool-specific files such as `AGENTS.md` may point here, but this file is the source of truth.

## Layering

- Global machine defaults may exist in tool-specific locations such as `~/.codex/AGENTS.md`.
- Tool adapter files in this repo may point here for automatic loading.
- Read [USER.md](USER.md) for operator identity and communication preferences.
- Read `CORE_ARCHITECTURE_PRINCIPLES.md` when it exists in the current checkout before proposing new architecture, dependencies, integrations, or control layers.
- Nested subsystem governance files may add local rules, but they must not weaken the safety or architecture rules here.

## Project Goal

Build OpenClaw for safety, power, economy, and bounded agentic execution.

- Default to fully agentic local work when it is reversible, well-bounded, and inside approved scope.
- Preserve full human control for destructive, irreversible, external, credential-bearing, or scope-expanding actions.
- Keep governance lean enough to be obeyed under load.

## Execution Rules

- Inspect real state before editing.
- Use inspect -> plan -> act -> verify for meaningful work.
- For architecture, tooling, workflow, or cost-sensitive decisions, present 3 approaches with tradeoffs and recommend one before committing.
- For straightforward bounded tasks, act without babysitting after a short inspection.
- Choose the lightest capable model and tool that can do the job well.
- TDD first when practical. Add or update the narrowest test that proves the change.
- Run the relevant tests before claiming completion, or say exactly why they were not run.
- Use `bun` by default for JavaScript and TypeScript work unless a repo already standardizes on another package manager.
- Use Conventional Commits when commits are made.

## Safety And Authority

- From the repo root, use `python3 chief_approval_brain.py "plain English description"` before destructive, external, credential, force-git, billing, or unattended high-risk actions.
- Safe local reads, code edits, and test runs are normally in-bounds.
- Never edit `.chief.env`, `.google-secrets/`, SSH keys, tokens, or credential files unless the task explicitly requires it and the approval path is satisfied.
- Never create shadow systems for approvals, memory, task tracking, operator state, or integration state when a canonical system already exists.
- Prefer existing native stack capabilities over new frameworks, plugins, sync layers, or orchestration surfaces.
- Respect the existing authority boundaries and approval policy. Do not self-expand scope.

## Documentation Rules

- Keep runtime-law docs short.
- Put operator identity and communication preferences in `USER.md`.
- Put historical lessons, deep explanations, and reference material in non-governing docs.
- Do not maintain per-model law files. All models working in OpenClaw should follow this same runtime law.
