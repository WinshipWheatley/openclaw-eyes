# Top-Level Classification Table

Status: path-name-only triage. This table records cleanup posture, not cleanup authority.

| Path or pattern | Category | Evidence from path or audit | Risk | Recommended handling |
| --- | --- | --- | --- | --- |
| `OPENCLAW_RUNTIME.md`, `AGENTS.md`, `CURRENT_STATE.md`, `RUNBOOK.md` | authority/orientation | Named root authority and orientation documents. | High if overwritten or treated as cleanup target. | Keep. Use as authority context before future cleanup planning. |
| `docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md`, `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md` | authority/orientation | Launch Ladder planning and bridge surfaces. | Medium drift risk. | Keep. Planning-only, not cleanup authority. |
| `docs/` | docs/planning | Main documentation tree. | Medium. Contains authority, planning, and audit docs. | Keep. Review by docs governance only. |
| `tests/`, `test_*.py`, `*_test.sh`, `launch_ladder_contract_check.py` | test/validation | Recent validation passed and test names are explicit. | Medium if removed before coverage map. | Keep. Inventory before pruning. |
| `apps/`, `api/`, `scripts/`, `tools/`, `bin/`, `runners.d`, `systemd/`, `sidecars/`, `monitoring/` | app/runtime code | App, API, script, tool, service, runner, sidecar, and monitoring names. | High runtime/service impact. | Keep. No service/script execution from this packet. |
| `mac_eyes/`, `polish_loop/` | active-current / likely keep | Operator workflow and active planning names from audit. | Medium. | Keep pending authority/reference map. |
| `chief_*`, `cassandra_*`, `expert_*`, `hitl_*`, `dashboard_*`, `runner_*`, `queue_*` | app/runtime code | Runtime code naming conventions visible at top level and in orientation docs. | High. | Keep. Review only by bounded module task. |
| `.ssh`, `.google-secrets`, `vaults`, `prompt-vault`, `key` | sensitive/do-not-touch | Secret, key, vault, and prompt-vault names. | Very high. | Protect. Do not inspect in cleanup work. |
| `legal/`, `finance/`, `openrouter/`, `brain_dumps/`, `execution_receipts/`, `compliance_verdicts/` | sensitive/do-not-touch | Legal, finance, provider, private work, receipt, and verdict names. | Very high. | Protect. Do not inspect contents from cleanup triage. |
| `.chief.env*`, `.pii_vault.enc*`, `.mcp.json` | sensitive/do-not-touch | Env, encrypted vault, and provider/runtime config names. | Very high. | Protect. Do not open or modify. |
| Shell histories, logs, lock files, provider/runtime config traces | sensitive/do-not-touch | Histories/logs/locks/configs may contain private or live runtime state. | High. | Protect unless a later packet explicitly scopes metadata-only handling. |
| `OpenClaw/` | runtime/config trace | Duplicate-looking, but `CURRENT_STATE.md` may indicate legacy session state lives there. | Very high. | Protect until verified by metadata/reference workflow. |
| `.npm`, `.cargo`, `.rustup`, `.nvm`, `.ollama`, `.dotnet`, `.nv`, `.local`, `.config` | runtime/config trace | Toolchain and local configuration path names. | Medium to high. | Do not clean casually. Verify references and ownership first. |
| `.bash_history`, `.python_history`, `.lesshst`, `.wget-hsts` | runtime/config trace | Shell and tool history path names. | High privacy risk. | Protect. Do not read contents. |
| `openclaw_arko_review/`, `backups/`, `recovery-library/`, `*.bak`, `*.save`, `*.old-key-backup` | duplicate/historical candidate | Duplicate, backup, archive, and old-key-backup names. | Medium to very high. | Candidate only. Do not delete without metadata, sensitivity, and rollback packet. |
| `.cache`, `.pytest_cache`, `__pycache__`, `.aider.tags.cache.v4`, `tmp`, `.vscode-server`, `.venv` | cache/build residue | Cache, temporary, server, and virtualenv names. | Medium. Cache-looking is not cleanup authority. | Candidate only. Need size, tracked/ignored status, and owner check. |
| `chmod`, `chmod 700 4home`, `mkdir -p 49dirname`, `set -euo pipefail`, `printf`, `printf paste`, `umask` | accidental command-fragment candidate | Shell-command-shaped path names. | Medium. | Preserve for future explicit cleanup approval. |
| `4secret-file0`, `secret-file=4home`, `hidden0`, `5s\n`, `4home`, `700`, `31`, `077`, `77`, `9input` | accidental command-fragment candidate / unknown-human-review | Test/command-fragment-looking names; some are secret-ish by name. | Medium to high. | Preserve. Treat secret-ish names as protect-first. |
| `Downloads/`, `rust_test/`, `test_skills/`, `test_skills_sample/`, `staging/` | unknown-human-review | Generic, experimental, or staging path names. | Medium. | Human review after metadata-only verification. |
| Generated logs or JSON state with unclear owner | unknown-human-review | Runtime state may be active or private. | High. | Do not inspect content. Verify by metadata and known references only. |

## Likely Keep Summary

Likely keep paths and patterns include authority docs, `docs/`, `tests/`, `apps/`, `api/`, `scripts/`, `tools/`, `bin/`, `runners.d`, `systemd/`, `sidecars/`, `monitoring/`, `mac_eyes/`, `polish_loop/`, `chief_*`, `cassandra_*`, `expert_*`, `hitl_*`, `dashboard_*`, `runner_*`, `queue_*`, and `launch_ladder_contract_check.py`.