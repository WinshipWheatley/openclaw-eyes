# Protect List: Do Not Touch

Status: protect-first list from path-name-only audit. Sensitive-looking means protect, not inspect.

## Hard Protect Categories

Do not open, move, delete, archive, rename, clean, or inspect contents for these paths during cleanup triage:

- `.ssh`
- `.google-secrets`
- `vaults`
- `prompt-vault`
- `key`
- `legal`
- `finance`
- `openrouter`
- `brain_dumps`
- `execution_receipts`
- `compliance_verdicts`
- `.chief.env*`
- `.pii_vault.enc*`
- `.mcp.json`
- Shell histories
- Logs
- Lock files
- Provider/runtime config traces

## Runtime And Config Trace Protect List

These paths may contain local runtime state, toolchain state, configuration, history, or provider/runtime traces. They are not cleanup-approved:

- `OpenClaw`
- `.npm`
- `.cargo`
- `.rustup`
- `.nvm`
- `.ollama`
- `.dotnet`
- `.nv`
- `.local`
- `.config`
- `.bash_history`
- `.python_history`
- `.lesshst`
- `.wget-hsts`

## Special Warning: `OpenClaw`

`OpenClaw` looks duplicate from the top-level name alone, but `CURRENT_STATE.md` may indicate legacy session state may live there. Treat it as protected runtime/config trace until a future metadata-only verification workflow proves exactly what it is and how it is referenced.

## Protect Doctrine

- Do not inspect private contents to decide whether something is sensitive.
- Do not treat a stale-looking path as safe if it is also sensitive-looking.
- Do not treat provider/runtime config traces as cleanup candidates from path names alone.
- Do not use this packet as permission to touch private, legal, finance, provider, Gmail, Calendar, queue, vault, token, key, or env material.

## Future Handling

A later cleanup packet may collect metadata only: path, type, size, mtime, and Git tracked/ignored status. It must not read content from protected paths unless the operator gives explicit scope and approval through the proper authority path.