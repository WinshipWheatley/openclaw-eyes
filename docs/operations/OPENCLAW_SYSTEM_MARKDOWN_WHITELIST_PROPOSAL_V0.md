# OpenClaw System Markdown Whitelist Proposal v0

## 1. Purpose

This proposal establishes approved second-pass Markdown sources for OpenClaw architecture and module recovery. It exists to prevent whole-vault, whole-machine, or broad legacy-runtime ingestion.

`/home/openclaw` remains the canonical OpenClaw control-plane trunk. External Markdown is prior art only until specific concepts are explicitly extracted, sanitized, rewritten, reviewed, and committed into current repo docs.

This is a docs-only whitelist proposal. It does not authorize runtime activation, code import, file copying, agent wiring, SQLite mutation, remote changes, generated-status changes, private-data review, or secret inspection.

## 2. Approved Second-Pass Source Groups

### Current Repo

Approved current-canonical sources:

- `/home/openclaw/docs/operations`
- `/home/openclaw/docs/planning`
- `/home/openclaw/Operator`
- `/home/openclaw/docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`
- `/home/openclaw/docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md`
- `/home/openclaw/docs/planning/launch_ladder/operator_harness_research/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md`
- `/home/openclaw/docs/planning/launch_ladder/operator_harness_research/MULTI_DEPLOYMENT_CONTROL_PLANE.md`
- `/home/openclaw/docs/planning/openclaw_legal/law_program/LEGAL_PRODUCT_CORE_SEPARATION.md`

Use: canonical current control plane, truth gateway posture, module contract posture, operator-surface doctrine, productization framing, deployment profile constraints, and current legal product/core boundary thinking.

### Legacy Runtime

Approved legacy prior-art sources:

- `/tmp/openclaw-runtime-audit/polish_loop/tasks/hitl-*`
- `/tmp/openclaw-runtime-audit/polish_loop/tasks/pii-*`
- `/tmp/openclaw-runtime-audit/polish_loop/tasks/sys-*`

Use: runtime, module, agent, HITL, PII, safety, orchestration, and runner lessons as legacy prior art only. These paths are not canonical and do not authorize runtime imports or activation.

### Obsidian Vault System Notes

Approved Obsidian prior-art sources:

- `/mnt/c/OpenClawShared/openclaw-vault/System/Overview.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Project Instructions.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Command Authority and Bounded Autonomy.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Capability Registry.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/Capability Ladder.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Data Classification.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Privacy Routing Rules.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Autonomy Threshold Map.md`
- `/mnt/c/OpenClawShared/openclaw-vault/System/NemoClaw Cloud Workload Candidates.md`

Use: early architecture, authority, capability, privacy-routing, workload-routing, and autonomy-threshold concepts. These notes are prior art and may be stale, personal, or superseded by current repo doctrine.

### Old Doctrine Export

Approved old doctrine prior-art patterns:

- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_*Doctrine*`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_*Contract*`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_*Matrix*`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_*Classification*`
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09/OpenClaw_*Implementation*`

Use: stale-but-useful doctrine, naming, authority, contract, permissions, state-classification, and implementation-map prior art. These files must be treated as older exports unless reconciled against `/home/openclaw`.

### Legal Product Boundary Source

Approved legal product source:

- `/home/openclaw/docs/planning/openclaw_legal/law_program/LEGAL_PRODUCT_CORE_SEPARATION.md`

Use: deployment profile, product boundary, reusable core, and customer-specific legal module separation ideas.

## 3. Contribution Model by Source Group

| Source group | Contribution allowed | Canonical status |
| --- | --- | --- |
| Current repo | Current control plane, truth gateway, receipt spine, operator query, module contracts, validation posture, deployment planning. | Canonical when committed and current. |
| Legacy runtime | Runtime/module/agent prior art, HITL patterns, PII concepts, orchestration failure lessons. | Legacy prior art only. |
| Obsidian System notes | Early architecture, authority, capability, privacy routing, and autonomy concepts. | Prior art only. |
| Doctrine exports | Older naming, contract, permission, classification, and implementation doctrine. | Stale prior art until reconciled. |
| Legal product docs | Deployment/product boundary ideas for reusable modules. | Canonical only for current repo legal docs in scope. |

## 4. Excluded / No-Go Sources

The following categories must not be automatically ingested or summarized:

- taxes
- CPA/tax records
- secrets
- `.env` files
- tokens
- keys
- credentials
- remote access notes
- private financial records
- client/private business records
- legal active-case files
- logs/runtime memory
- AppData/user profile material
- private creative/business folders unless manually approved

Explicit excluded paths and categories:

- `/home/openclaw/.google-secrets`
- `/home/openclaw/.ssh`
- `/home/openclaw/.private`
- `/home/openclaw/finance`
- `/home/openclaw/secrets`
- `/mnt/c/OpenClawShared/business`
- `/mnt/c/OpenClawShared/openclaw-vault/Business`
- `/mnt/c/OpenClawShared/openclaw-vault/Billing`
- `/mnt/c/OpenClawShared/openclaw-vault/Calendar`
- `/mnt/c/OpenClaw/legal/cases/active-case`
- `/mnt/c/OpenClaw/logs`
- `/mnt/c/OpenClaw/memory`
- `/mnt/c/Users/*/AppData`

If a path is ambiguous, treat it as sensitive/manual-review-only and do not read it during automated recovery.

## 5. Rules for Second-Pass Reading

- Read only whitelisted files and patterns listed in this proposal.
- Extract architecture concepts, not personal, private, client, legal, financial, creative, operational, credential, or journal-like contents.
- Do not quote or copy whole notes.
- Do not use snippets from sensitive material.
- Mark stale, duplicate, exported, or legacy material clearly.
- Nothing becomes canonical until rewritten into current repo docs.
- No runtime activation.
- No code import.
- No agent wiring.
- No secret inspection.
- No client/private-data ingestion.
- No whole-vault, whole-machine, or whole-legacy-repo ingest.

## 6. Stale / Duplicate Handling

- `/mnt/c/OpenClaw/OpenClaw_Watch_EXPORTS` is likely mirror/stale and should not be treated as canonical.
- `/mnt/c/OpenClaw/law_program` may duplicate current repo legal docs and should be reconciled against `/home/openclaw/docs/planning/openclaw_legal`.
- `/mnt/c/OpenClaw/doctrine_export_2026-04-09` is older doctrine/export prior art.
- `/tmp/openclaw-runtime-audit` is legacy runtime prior art.

When duplicates conflict, current committed `/home/openclaw` docs win unless a later explicit reconciliation lane changes the canonical repo.

## 7. Recommended Next Lane

The next safe lane is second-pass architecture extraction from only the whitelisted files and patterns in this proposal.

The output should be a sanitized architecture concept map that records concepts, source category, freshness/staleness, module relevance, and whether the idea belongs in the current module atlas.

After the sanitized concept map:

1. Create `docs/module_atlas` master atlas v0.
2. Then implement an inert `module_manifest` validator using synthetic examples only.

No runtime activation, legacy import, agent wiring, broker connection, private-data review, or secret inspection belongs in this lane.

## 8. Do-Not-Do List

- Do not ingest the whole vault.
- Do not ingest the whole machine.
- Do not ingest the whole legacy runtime repo.
- Do not copy old runtime notes.
- Do not summarize private or sensitive content.
- Do not wire agents.
- Do not import runtime code.
- Do not mutate SQLite.
- Do not move files.
- Do not change remotes.
- Do not modify generated status.
- Do not treat old notes as canonical truth.
- Do not inspect secrets, tokens, credentials, keys, remote access notes, private financial records, client/private business records, active legal case files, runtime logs, or AppData material.
