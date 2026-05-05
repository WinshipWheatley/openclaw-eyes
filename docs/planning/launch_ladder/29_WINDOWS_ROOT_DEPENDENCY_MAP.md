# Windows Root Dependency Map

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a metadata-only active-dependency map for Windows root references found from repo-local docs, scripts, configs, and filename/path metadata.

It is not runtime truth, cleanup authority, migration authority, source-set authority, service authority, bridge authority, MCP authority, provider/model authority, Operator Harness ingestion authority, backend build-prep, or permission to inspect private contents.

This map records candidate references only. A discovered path does not mean read, safe, fresh, canonical, active, ingestible, displayable, movable, or deletable.

## 2. Source Basis

Source basis:

- `docs/planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md`
- `docs/planning/launch_ladder/28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md`
- `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`
- `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- `docs/planning/launch_ladder/knowledge_substrate/README.md`
- `docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md`
- `docs/planning/launch_ladder/knowledge_substrate/02_SQLITE_LAYER_MODEL.md`
- `docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md`
- `docs/planning/launch_ladder/19_STORAGE_AND_SOURCE_REGISTRY_READINESS_PLAN.md`
- Repo-local reference hits in docs, shell scripts, Python files, configs, systemd templates, JSON configs, and Mac launcher scripts.

No Windows private roots, private file contents, services, users, permissions, runtime state, provider/model state, MCPs, source sets, databases, indexes, embeddings, chunks, or bridge payloads were inspected or modified.

## 3. Knowledge Substrate Classification-Only Boundary

Knowledge Substrate doctrine is used here only as classification guidance.

Rules carried forward:

- This is not vanilla RAG and not flat chunk-vector RAG.
- Retrieval/search finds candidates; it does not create authority.
- Discovered does not mean read.
- Raw files are evidence, not truth.
- Unknown/unclassified items remain quarantined.
- Source registry and owner review must precede ingestion, extraction, compilation, promotion, SQLite, FTS, embeddings, context packets, Operator Harness display, or provider/model context.

Knowledge-Substrate Status values in this map are labels only. They do not authorize implementation.

## 4. Audit Method

Method used:

- Read the required planning and doctrine docs.
- Searched repo-local docs, scripts, configs, systemd templates, JSON configs, and Mac launcher scripts for explicit references to `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, `openclawssh`, and related `/mnt/c/...` paths.
- Used filename-only search for `OpenClaw`, `OpenClawShared`, `OpenClawLegalPrivate`, and `openclawssh` path-name metadata.
- Read only repo-local source/config snippets needed to classify references by path/name/reference metadata.
- Treated all results as candidate references until owner review.

No private root traversal, content inspection, service inspection, sync, migration, indexing, extraction, or runtime probing was performed.

## 5. Active Dependency-Map Table

| Path / Reference | Observed Source | Likely Owner | Dependency Categories | Classification Label | Allowed Next Action | Forbidden Next Action | Private-Data Risk | Evidence Basis | Knowledge-Substrate Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/home/openclaw` | Runtime law, Command Atlas, current repo status | OpenClaw repo owner | canonical code/docs/planning repo | `canonical-repo` | Keep as canonical planning source | Treat mounted Windows paths as canonical by association | low for repo metadata; private roots still excluded | required docs and `pwd`/git status | `generated-report-candidate` |
| `C:\OpenClaw` / `/mnt/c/OpenClaw` | Planning docs, `config.yaml`, scripts, systemd templates, Python path constants | runtime/system owner TBD | runtime/service, script/config, generated output, legacy legal/business residue | `active-runtime-candidate`, `active-config-candidate`, `legacy-residue-candidate`, `unknown-quarantine` | Create runtime/log/state/bin/config dependency map by metadata only | Clean, move, canonicalize, browse contents, source-set include, ingest | unknown/high | repo-local path strings only | `candidate-reference`, `runtime-dependency-candidate`, `not-for-ingestion`, `owner-review-required` |
| `/mnt/c/OpenClaw/logs` | `loop_supervisor.sh`, `systemd/user/*.service.in`, `dashboard_gen.py`, Chief/Cassandra scripts | runtime/log owner TBD | runtime/service logs, generated output | `active-runtime-candidate`, `shared-generated-candidate`, `unknown-quarantine` | Map log producers and retention/redaction policy by reference only | Open raw logs, delete, rotate manually, sync, ingest, expose in Harness | medium/high unknown | many repo-local write/read path constants | `runtime-dependency-candidate`, `not-for-ingestion` |
| `/mnt/c/OpenClaw/state` and `/mnt/c/OpenClaw/memory` | Chief worker scripts and dashboard references | runtime/state owner TBD | runtime state, memory/status surface | `active-runtime-candidate`, `unknown-quarantine` | Metadata-only dependency ownership review | Treat as cleanup, source truth, or app display without contract | unknown | repo-local path constants | `runtime-dependency-candidate`, `not-for-ingestion` |
| `/mnt/c/OpenClaw/billing` and `/mnt/c/OpenClaw/data/tax_docs` | finance/billing scripts and state JSON path references | finance/business owner TBD | billing, finance/CPA source dependency, generated invoices | `finance-private-candidate`, `private-source-candidate`, `active-runtime-candidate`, `unknown-quarantine` | Owner review and finance-private contract question | Browse invoices/tax files, ingest, model-context include, migrate | high | path/name references only | `blocked-private-source`, `owner-review-required` |
| `/mnt/c/OpenClaw/legal` | older legal scripts, stale-folder docs, legal modules | legal owner TBD | old legal-private workflow, legacy residue | `legal-private-candidate`, `private-source-candidate`, `legacy-residue-candidate`, `do-not-touch` | Legal-private contract and legacy-path disposition review | Run legacy pipeline, browse cases, migrate, clean | high | repo-local path constants and planning docs | `blocked-private-source`, `unknown-quarantine` |
| `/mnt/c/OpenClaw/law_program` | operations stale-folder planning docs | legal/planning owner TBD | old/duplicate legal planning/runtime surface | `legacy-residue-candidate`, `unknown-quarantine` | Metadata comparison plan only | Move, delete, merge, or treat as canonical | medium/high unknown | docs-only reference | `unknown-quarantine`, `not-for-ingestion` |
| `C:\OpenClawShared` / `/mnt/c/OpenClawShared` | boundary docs, many Chief/Cassandra scripts, handoff scripts | shared/business owner TBD | bridge/sync, shared generated output, business/album/finance/music-law source | `shared-generated-candidate`, `private-source-candidate`, `active-bridge-candidate`, `unknown-quarantine` | Owner review and generated/shared contract | Treat as safe shared storage, browse, sync, ingest, source-set include | high | repo-local path constants and boundary docs | `candidate-reference`, `blocked-private-source`, `mirror-reference`, `owner-review-required` |
| `/mnt/c/OpenClawShared/openclaw-vault` | docs, scripts, `harness_config.json`, vault write/read constants | operator vault owner TBD | shared/generated reports, operator vault, possible sensitive notes | `shared-generated-candidate`, `private-source-candidate`, `unknown-quarantine` | Exact-path owner-approved review only after contract | Whole-vault browse, MCP exposure expansion, source-set include, ingestion | medium/high | repo-local path constants only | `mirror-reference`, `not-for-ingestion` |
| `/mnt/c/OpenClawShared/OpenClaw-Handoff` | `eyes_sync.sh`, `observer.sh`, `eyes_queue_push.sh`, `system_audit.py` | bridge/handoff owner TBD | bridge/sync, generated handoff packets | `active-bridge-candidate`, `shared-generated-candidate`, `unknown-quarantine` | Bridge dependency map and generated-packet contract | Sync redesign, payload inspection, Harness ingestion | medium/high unknown | repo-local output path constants | `mirror-reference`, `generated-report-candidate`, `not-for-ingestion` |
| `/mnt/c/OpenClawShared/business` and `/mnt/c/OpenClawShared/album` | Chief business, CPA, publishing, music-law, album, email, marketing scripts | business/finance/music owner TBD | business source/state, finance/CPA, music-law/publishing, active app state | `private-source-candidate`, `active-config-candidate`, `unknown-quarantine`, `do-not-touch` | Owner review and private-root separation plan | Browse JSON contents, summarize, ingest, sync, source-set include | high | path/name references only | `blocked-private-source`, `owner-review-required` |
| `C:\OpenClawShared\business\source_docs\finance_admin` and descendants | boundary docs and template | finance/CPA owner TBD | finance/CPA source dependency, ledger/tax source material | `finance-private-candidate`, `private-source-candidate`, `do-not-touch` | Boundary note; finance-private root contract question | Inspect contents, move, clean, ingest, model-context include | high | planning-doc path/name facts only | `blocked-private-source`, `not-for-ingestion` |
| `C:\OpenClawLegalPrivate` / `/mnt/c/OpenClawLegalPrivate` | boundary docs, legal validation docs, `scripts/run_legal_pipeline_v0.sh`, Mac launcher scaffold | legal owner TBD | legal-private workflow, staging, vault, exports | `legal-private-candidate`, `private-source-candidate`, `do-not-touch` | Legal-private root contract and owner review | Browse, merge, migrate, index, source-set include, provider/model context | high | repo-local path constants only | `blocked-private-source`, `owner-review-required` |
| `/mnt/c/OpenClawLegalPrivate/vault`, `/staging`, and `/exports` | legal v0 script, legal docs, Mac bridge launcher | legal owner TBD | legal-private vault/staging/export workflow | `legal-private-candidate`, `active-bridge-candidate`, `private-source-candidate`, `do-not-touch` | Contract review; exact-path validation rules only when separately authorized | Open matter contents, run pipeline, sync, ingest, display | high | repo-local script/config references | `blocked-private-source`, `runtime-dependency-candidate`, `not-for-ingestion` |
| `openclawssh`, `C:\Users\openclawssh`, `C:\Users\openclawssh.DESKTOP-HP` | boundary docs and C-drive breadcrumb | account/access owner TBD | SSH/service-account surface, user profile residue | `active-config-candidate`, `unknown-quarantine`, `do-not-touch` | Separate account/access audit with no credential inspection | Delete, disable, rely on, repurpose, chmod/chown, inspect profile contents | unknown/high | operator-provided audit summary in planning docs | `owner-review-required`, `not-for-ingestion` |
| `/mnt/c/OpenClaw` in `config.yaml` vs docs/specs-only `.mcp.json` | repo configs | MCP/config owner TBD | config exposure candidate, policy drift candidate | `active-config-candidate`, `unknown-quarantine` | Config authority review only | Invoke MCP, edit config, expand filesystem access, inspect mounted roots | medium/high unknown | config path strings only | `candidate-reference`, `owner-review-required`, `not-for-ingestion` |
| `harness_config.json` redirects from `/mnt/c/OpenClaw/logs` and `/mnt/c/OpenClawShared/openclaw-vault/System` | repo JSON config | harness/test owner TBD | bridge/test redirect, generated report candidate | `active-bridge-candidate`, `shared-generated-candidate`, `unknown-quarantine` | Owner review of redirect contract | Run harness, copy logs/vault, ingest staged outputs | medium/high unknown | repo-local config path strings | `generated-report-candidate`, `not-for-ingestion` |

## 6. Unknown / Quarantine List

Keep these in `unknown-quarantine` until owner review:

- `C:\OpenClaw` as a whole.
- `/mnt/c/OpenClaw/law_program`.
- `/mnt/c/OpenClaw/logs` until redaction, retention, and producer ownership are mapped.
- `/mnt/c/OpenClaw/state` and `/mnt/c/OpenClaw/memory` until runtime ownership is mapped.
- `C:\OpenClawShared` as a whole.
- `/mnt/c/OpenClawShared/openclaw-vault` as a whole.
- `/mnt/c/OpenClawShared/OpenClaw-Handoff` until generated-packet boundaries are documented.
- `/mnt/c/OpenClawShared/business` and `/mnt/c/OpenClawShared/album`.
- Any `/mnt/c/OpenClaw...` reference found only as a repo path string with no current owner proof.
- `openclawssh` user/profile references.

## 7. Private-Source Candidate List

Private-source candidates:

- `C:\OpenClawShared\business\source_docs\finance_admin`
- `C:\OpenClawShared\business\source_docs\finance_admin\ledger`
- `C:\OpenClawShared\business\source_docs\finance_admin\tax_docs`
- `/mnt/c/OpenClawShared/business`
- `/mnt/c/OpenClawShared/album`
- `/mnt/c/OpenClaw/billing`
- `/mnt/c/OpenClaw/data/tax_docs`
- `/mnt/c/OpenClaw/legal`
- `C:\OpenClawLegalPrivate`
- `/mnt/c/OpenClawLegalPrivate/vault`
- `/mnt/c/OpenClawLegalPrivate/staging`
- `/mnt/c/OpenClawLegalPrivate/exports`
- `C:\Users\openclawssh` and `C:\Users\openclawssh.DESKTOP-HP` until account/profile audit proves otherwise.

## 8. Runtime / Bridge Dependency Candidates

Runtime and bridge dependency candidates:

- `/mnt/c/OpenClaw/logs` used by loop supervisor scripts, systemd service templates, dashboard generation, Chief/Cassandra logs, broker audit logs, and HITL/dashboard adapters.
- `/mnt/c/OpenClaw/state` and `/mnt/c/OpenClaw/memory` used by Chief state/memory surfaces.
- `/mnt/c/OpenClawShared/OpenClaw-Handoff` used by handoff/update scripts.
- `/mnt/c/OpenClawShared/openclaw-vault/System` used by shared report/status surfaces and harness redirect config.
- `/mnt/c/OpenClawLegalPrivate/vault`, `/staging`, and `/exports` referenced by legal v0 scripts and Mac bridge scaffolding.
- `config.yaml` still references `/mnt/c/OpenClaw` for filesystem MCP-style config, while current `.mcp.json` is docs/specs-only.
- `harness_config.json` redirects mounted Windows log/vault paths into repo-local staging paths.

These are dependency candidates, not permission to run, inspect, modify, or migrate anything.

## 9. Source-Set Exclusion Notes

Exclude by default from source sets, agent browsing, Gemini/Codex context, provider/model context, Operator Harness ingestion, backend/data-contract source sets, and Knowledge Substrate ingestion:

- `C:\OpenClaw`
- `C:\OpenClawShared`
- `C:\OpenClawLegalPrivate`
- `C:\OpenClawShared\business\source_docs\finance_admin`
- `/mnt/c/OpenClaw/logs`
- `/mnt/c/OpenClaw/legal`
- `/mnt/c/OpenClaw/billing`
- `/mnt/c/OpenClaw/data`
- `/mnt/c/OpenClawShared/business`
- `/mnt/c/OpenClawShared/album`
- `/mnt/c/OpenClawShared/openclaw-vault`
- `/mnt/c/OpenClawLegalPrivate`
- `C:\Users\openclawssh` and related profile roots.

Generated does not mean non-sensitive. Shared does not mean safe. Mirrored does not mean canonical. Searchable does not mean authorized.

## 10. Operator Review Questions

Open questions for owner review:

1. Which `/mnt/c/OpenClaw/logs` producers are still active, and which logs are safe only as redacted summaries?
2. Which `/mnt/c/OpenClaw/state` and `/mnt/c/OpenClaw/memory` paths are still runtime dependencies?
3. Is `/mnt/c/OpenClaw/legal` legacy residue, an active private legal surface, or both?
4. Which `/mnt/c/OpenClawShared/openclaw-vault` subtrees are generated/shared outputs versus operator-private material?
5. Which `/mnt/c/OpenClawShared/business` and `/album` paths are active source-of-truth stores, and which require finance/music-law/private-root separation?
6. What legal-private root contract governs `/mnt/c/OpenClawLegalPrivate/vault`, `/staging`, and `/exports`?
7. Is `openclawssh` currently required for VS Code Remote, Windows OpenSSH, historical access, or no longer needed?
8. Should `config.yaml` retain `/mnt/c/OpenClaw` as an MCP-style filesystem arg, given current `.mcp.json` is docs/specs-only?
9. What generated/shared report contract is needed before any OpenClawShared output is considered safe to display?
10. What source-registry fields are safe to collect later without content inspection?

## 11. Forbidden Next Actions

Do not:

- inspect private contents;
- traverse Windows private roots;
- run broad root scans;
- move, delete, rename, clean, archive, deduplicate, or sync files;
- chmod/chown or change permissions;
- edit services, users, SSH settings, launchers, bridge behavior, MCP config, or runtime state;
- run providers/models, Hermes, MCPs, source-set generation, ingestion, extraction, indexing, chunking, embedding, SQLite, FTS, or database creation;
- include Windows/Mac private roots in agent context, source sets, Operator Harness, backend build-prep, or provider/model context;
- treat path strings, search hits, generated outputs, shared folders, vault names, or mirrors as authority.

## 12. Safe Next Actions After Owner Review

Safe next actions after owner review may include:

- Create a separate `openclawssh` account/access audit plan with no credential or profile-content inspection.
- Create a runtime/log/state/bin/config dependency map using explicit path strings and owner-provided metadata only.
- Create a generated/shared output contract for OpenClawShared after raw private material is separated.
- Create legal-private, finance-private, and music-law/private root contracts.
- Create a source-registry field contract that records candidates without reading, extracting, or ingesting them.
- Create an approved move-manifest template only after dependency ownership, backup, retention, rollback, and private-source exclusions are resolved.
- Review `config.yaml` and `.mcp.json` authority drift as a docs/config planning question, without invoking or editing MCPs.

## 13. Final Boundary Statement

No action was taken; this is a proposed metadata-only map.
