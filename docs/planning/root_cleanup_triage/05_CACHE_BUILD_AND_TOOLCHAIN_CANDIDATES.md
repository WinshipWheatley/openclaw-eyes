# Cache, Build, And Toolchain Candidates

Status: candidate list only. Cache-looking does not mean safe to delete.

## Cache / Build Residue Candidates

- `.cache`
- `.pytest_cache`
- `__pycache__`
- `.aider.tags.cache.v4`
- `tmp`
- `.vscode-server`
- `.venv`

These are plausible cache, temporary, server, or virtual environment paths. They are not approved cleanup targets yet.

## Toolchain / Config Trace Candidates

- `.npm`
- `.cargo`
- `.rustup`
- `.nvm`
- `.ollama`
- `.dotnet`
- `.nv`
- `.local`
- `.config`

These may be large or stale, but they can also be live toolchain state, model/runtime state, shell environment state, or local configuration. Do not clean them from path names alone.

## Required Metadata Before Any Proposal

A future metadata-only verification packet should capture:

1. Path.
2. Type.
3. Size.
4. Modified time.
5. Git tracked, ignored, or untracked status.
6. Whether any authority docs or runbooks reference the path.
7. Whether deleting or relocating it would affect local tools, VS Code, tests, OpenClaw runtime, model/runtime caches, or language environments.
8. Whether a rollback path exists.

## Stop Rule

If a path might affect a working toolchain, runtime, local model surface, VS Code environment, Python environment, or service, stop and leave it in place until the operator explicitly approves a bounded cleanup packet.