# OpenClaw Modular Readiness Ledger

Status: canonical planning/control map. Docs-only. This ledger does not authorize runtime, service, installer, launcher, scheduler, provider, model-default, Gmail, Telegram, Hermes runtime, Legal matter, secret, vault, private-log, or private-data changes.

Source basis:

- `OPENCLAW_RUNTIME.md`
- `USER.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`
- `docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md`
- `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`
- `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`
- `docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md`
- `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md`
- `docs/testing/VALIDATION_MAP.md`
- `capability_registry.py`
- `google_access_policy.py`
- `service_inventory_audit.py`

## 1. Purpose

This ledger reduces fog-of-war across parallel OpenClaw builds by recording each major module's purpose, authority, data boundary, proof level, next safe slice, and portability notes in one planning view.

It supports two tracks:

1. Winship's personal OpenClaw build: local-first operator substrate, bounded agents, approval gates, source-controlled docs, deterministic proofs, and careful service/process ownership.
2. Future modular/productized deployments for other organizations: selectable capability packages such as a Cassandra-like assistant, Hermes-like advisory consultant, Guardian approvals, local-model privacy boundary, Legal-style matter isolation, and service-control SE kernel.

This is not a product-readiness claim. A module is portable only to the extent its proof, authority boundary, data contract, validation map entry, and operator approvals are explicit.

## 2. Status Vocabulary

| Status | Meaning | What it does not mean |
| --- | --- | --- |
| `concept` | Direction is named, but no sufficient implementation/proof exists. | Not ready for runtime integration or customer deployment. |
| `static contract` | Policy, schema, docs, or code contract exists and can be checked without live systems. | Does not prove live service health, model quality, or end-to-end behavior. |
| `read-only proof` | A deterministic read-only checker, parser, or source audit exists. | Does not authorize mutation or ownership changes. |
| `dry-run proof` | A dry-run or no-execution artifact flow exists with tests or explicit validation. | Does not authorize live execution. |
| `bounded action` | A narrow action path exists behind explicit gates, approvals, or mode flags. | Not broad autonomy and not permission to expand adjacent surfaces. |
| `production candidate` | The module has enough policy, tests, and operational shape to be considered for controlled deployment in its exact scope. | Not proven for unrelated customers, broader data, new integrations, or unattended expansion. |
| `frozen / do not expand` | The surface must remain static, advisory, or non-authoritative until a separate lane changes it. | Not abandoned unless explicitly retired. |

## 3. Authority Vocabulary

| Authority | Meaning |
| --- | --- |
| `no authority / advisory only` | May analyze or recommend, but cannot mutate canonical state or trigger side effects. |
| `read-only` | May inspect approved non-private sources or artifacts. |
| `proposal only` | May produce a proposal, packet, manifest, or suggested action for review. |
| `approval gate` | May approve, deny, delay, or route a bounded request according to policy. |
| `broker-gated action` | May act only through a central broker that enforces class, approval, audit, and data rules. |
| `bounded executor` | May execute a narrow, reversible, tested action inside a declared scope and mode. |
| `forbidden` | Must not perform the action or touch the data/surface in the current state. |

## 4. Module Readiness Table

| Module | Purpose | Current status | Authority level | Data allowed | Proof/tests/docs | Dependencies | Next safe slice | Do-not-do-yet | Portability/productization notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Core runtime law / canonical docs | Keep one runtime law, operator context, and architecture principles for all agents. | `production candidate` for governance docs only. | `read-only` for agents; authority comes from the docs, not this ledger. | Repo control docs and explicit task context. No secrets/private logs/vaults by default. | `OPENCLAW_RUNTIME.md`, `USER.md`, `CORE_ARCHITECTURE_PRINCIPLES.md`, `docs/testing/VALIDATION_MAP.md`. | Human operator, git, validation discipline. | Keep governance short; add validation-map entries for every new capability family. | Do not fork per-model law or create shadow authority docs. | Portable as an onboarding/control packet for any deployment if customer-specific identity and private-data rules are separated. |
| Service-control SE kernel | Record service/process owners, forbidden controls, and static disposition without touching live services. | `static contract` plus `read-only proof`; Slice 8 disposition is documented, not live-verified. | `read-only` and `proposal only`. | Repo service docs, systemd templates in source, static launcher/install script text. No live services, logs, process tables, or installed-state reconciliation. | `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md`, `service_inventory_audit.py`, `tests/test_service_inventory_audit.py`, `tests/test_service_owner_classification_static_contract.py`, `tests/test_drift_control_scheduler_static_contract.py`, `tests/test_legacy_ownership_disposition_static_contract.py`. | Validation map, repo templates, explicit future service lane. | Service-freeze docs polish, then a read-only live-state verification plan that is separately approved before any live command. | Do not start/stop/restart/enable/disable services; do not select new owners; do not revive legacy launchers. | Strong productization kernel: every deployment needs a service inventory, owner table, forbidden-control table, and static audit before installation. |
| MCP progressive discovery | Start with narrow docs-only MCP context and unlock surfaces only after a lane-specific gate and reveal artifact. | `static contract`; hardened default documented and tested. | `read-only` by default; unlocks remain `proposal only` until approved. | Default docs roots only: `docs/operations` and `docs/specs`; exact-file packets for root control files. | `docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md`, `.mcp.json`, `tests/test_mcp_progressive_discovery_profiles.py`. | Runtime law, withheld-surface policy, lane unlock records. | Add small reveal-artifact templates for repo-source, runtime-artifact, and shared-vault unlocks. | Do not broaden MCP roots as convenience; do not expose logs, vaults, provider tools, messaging, terminal/process, writes, or Hermes runtime by default. | Portable as a customer deployment access matrix: default context, withheld surfaces, unlock trigger, gate, and artifact. |
| Model routing / fallback policy | Keep local/external model use explicit, privacy-aware, benchmarked, and fail-closed. | `static contract`; local inventory and benchmark checkpoint exist, but quality remains unproven. | `proposal only`; external protected packets are effectively `forbidden` until sanitizer/export gate exists. | Non-sensitive repo/code/docs may be considered for approved external use. Sensitive/professional packets stay deterministic/local by default. | `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`, `chief_llm.py` policy references, `tests/test_chief_llm_router.py`, static external-route guard referenced by policy. | Local models, centralized packet policy, future sanitizer/export gate, benchmark harness. | Model contention/benchmark plan with synthetic fixtures and operator-approved windows. | Do not add silent external fallback; do not send Legal, Gmail bodies, CPA, Music Law, Publishing, secrets, PII, private logs, or vault data external. | Product deployments need per-customer sensitivity categories, model allowlist, benchmark evidence, and external-use approval logs. |
| Cassandra | Personal executive assistant for orientation, briefs, outreach drafts, known-contact reasoning, and operator support. | Mixed: some `bounded action`, some `dry-run proof`, some planned. Not production-ready as broad autonomy. | `broker-gated action` for Google paths; `proposal only` for drafts/previews; no direct autonomous external send. | Approved operator context, bounded Gmail metadata, broker-approved Gmail body/draft actions, calendar reads, synthetic/dry-run triage data. | `capability_registry.py`, `google_access_policy.py`, `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`, Cassandra tests listed in validation map. | Chief, Guardian, Google broker, PII hooks, model fallback policy, known-contact state contracts. | Clarify Cassandra assistant packet boundaries and dashboard/report artifacts before expanding live behavior. | Do not roam Gmail, read bodies without broker policy, create/send without gates, notify arbitrary threads, or use external models on private correspondence. | Portable as a configurable assistant module only after data classes, contact scopes, notification policy, broker gates, and local-only model rules are customer-specific. |
| Hermes | Advisory consultant sidecar for synthesis, critique, and bounded proof packets. | `static contract` for advisory packet/output shape; authority remains frozen and broad technical capability remains a risk. | `no authority / advisory only`. | Bounded non-sensitive packets, checked advisory proofs, repo docs/code only when explicitly scoped. | `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`, `hermes_advisory_packet.py`, `tests/test_hermes_advisory_packet_contract.py`, Hermes orientation/lane policy references in intent/model docs, gateway/advisory profile in MCP profile doc, and nested sidecar gateway policy tests. | OpenClaw gateway mode, file-safety deny rules, static packet checker, explicit non-canonical boundary. | First read-only Hermes advisory trial on a bounded service-freeze closure packet. | Do not grant canonical writes, approval authority, provider fallback, broad terminal/file/MCP access, session-state access, or private-data access. | Portable as an advisory consultant module if delivered as packet-in/proposal-out with no customer canonical authority. |
| Guardian | Human approval path for high-risk or externally consequential actions. | `bounded action` / `approval gate` for known approval flows. | `approval gate`. | Minimal approval prompt summaries and approval IDs; avoid raw secrets/private data. | `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`, Chief/Guardian validation references, `guardian_schema_harness.py`. | Chief approval policy, approval receipts, operator contact path. | Normalize approval receipt artifacts across Google, expert escalation, service-control, and external model exceptions. | Do not let routine chat confirmation substitute for Guardian where Tier 2 approval is required. | Portable as a cross-module approval service if prompts are redacted, receipts are durable, and each capability maps to approval class. |
| Google/Gmail/Calendar broker | Central policy gate for Google API capabilities and audit class decisions. | `bounded action` for listed brokered capabilities; policy is narrow and agent-specific. | `broker-gated action`; unlisted agents/capabilities denied. | Cassandra calendar read, contacts/metadata/unread safe reads, Gmail body and draft Class B, calendar write Class B, Gmail send Class C future path. | `google_access_policy.py`, `google_access_broker.py` references in intent map, policy smoke command, Cassandra tests. | Google credentials, Chief approval brain, audit logging, privacy/model policy. | Add product-ready broker capability manifest: class, actor, executor, audit fields, body/log redaction rule. | Do not bypass broker, auto-send Gmail, downgrade body/draft to Class A, or route Gmail bodies to external models. | Portable as a broker pattern: every integration needs actor/capability/class table, denied-by-default behavior, and audit omission of sensitive bodies. |
| Legal/local discovery product | Deterministic local-first Legal workspace, path guard, support/review packets, and matter isolation. | `dry-run proof` / `bounded action` for synthetic/local v0; real customer production is not claimed. | `bounded executor` only inside local deterministic Legal v0; external model use is `forbidden`. | Synthetic fixtures and approved private Legal vault paths. No matter data in repo or external contexts. | Legal path/support packet tests listed in intent map and validation map; Legal docs referenced but not edited here. | Private vault contract, path guard, deterministic pipeline, support packet sanitizer. | Productize matter isolation rules and support-packet sanitizer as a reusable package after service-freeze closure. | Do not inspect/edit Legal private matter data; do not run cloud/LLM on real matters; do not mix old Legal paths into repo docs as canonical. | Highly portable if sold as local-first matter isolation: customer vault root, no-cloud default, support-packet sanitizer, and synthetic validation are mandatory. |
| Local model privacy boundary | Keep sensitive work deterministic/local-only unless a future sanitizer/export gate approves otherwise. | `static contract`; installed local models are inventoried historically, capability remains unproven. | `proposal only` for model-assisted outputs; deterministic validation owns authority. | Local synthetic fixtures and approved local-only sensitive summaries. External forbidden for protected categories by default. | `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`, benchmark checkpoint, model/router tests in validation map. | Local model server, benchmark fixtures, route logs, privacy categories. | Build a benchmark plan and contention schedule before trusting drafting, summarization, builder, or acceptance behavior. | Do not confuse installed models with trusted models; do not benchmark during active work unless requested; do not externalize protected packets. | Portable as a privacy boundary module with customer-specific sensitivity taxonomy, local hardware profile, and benchmark acceptance thresholds. |
| Expert escalation | Package non-sensitive/sanitized questions for external expert help without execution authority. | `dry-run proof` / `static contract`; no-execution handoff and approval packet rails exist from prior lanes. | `proposal only`; external execution requires explicit approval and checked packets. | Sanitized packets, manifests, hashes, approval receipts. No protected/raw private data. | Expert escalation docs/code/tests referenced by intent map and validation history; validation map has expert evidence chain static contracts. | Packet checker, provider/lane policy, Guardian receipts, hash-preservation rules. | Integrate expert approval packet into dashboard/report artifact view without provider execution. | Do not choose concrete providers/models or execute jobs from a packet alone; do not include secrets, raw private data, or protected matter content. | Portable as a safe external-consulting rail if sanitizer, packet schema, provider policy, and approval receipts are mandatory. |
| Memory/retrieval substrate | Make memory, provenance, redaction, embeddings, and regeneration inspectable and rebuildable. | `concept`; direction is clear but unified system is not landed. | `no authority / advisory only` until architecture and tests exist. | Planned: explicit source packets, metadata, provenance, redaction status, rebuild rules. Current raw private stores remain withheld. | North-star note, runtime law, architecture principles. No canonical unified memory implementation claimed. | Source-set discipline, redaction policy, storage schema, retrieval tests, privacy boundary. | Memory/retrieval substrate plan before implementation: raw/metadata/embedding/provenance/redaction/regeneration separation. | Do not create shadow memory, vendor-owned canonical memory, per-interface state stores, or private-data embeddings without a policy. | Core productization asset, but only after rebuildability and customer data isolation are designed first. |
| Dashboard/operator reporting | Show operator status, evidence, withheld surfaces, approvals, and next safe action without granting execution authority. | `read-only proof` / planned; deterministic snapshot direction exists, but product dashboard is not complete. | `read-only` and `proposal only`. | Bounded artifacts, redacted summaries, source lists, approval receipts. No raw private logs by default. | Intent map dashboard/report row, evidence adapter references, validation map for touched modules. | Evidence artifacts, service freeze, approval receipts, source-set manifests, redaction rules. | Operator dashboard/report artifact after Hermes advisory packet contract. | Do not build a dashboard that controls services, hides source lists, exposes raw logs, or becomes canonical memory. | Portable as an operator console if every widget names source, status, authority, withheld surfaces, and validation freshness. |
| Source-set / ChatGPT ingest workflow | Maintain bounded source packets and ingest mirrors for external review without drifting from source truth. | `bounded action` for known refresh/mirror scripts; still not authority over runtime. | `proposal only` for external interpretation; source repo remains canonical. | Selected non-sensitive docs/source files only; no secrets, private logs, Legal private data, Gmail bodies, or vaults. | North-star source basis, Mac mirror/ingest workflow context, validation map and `git diff --check` style checks. | Source manifests, refresh scripts, no-index checks, explicit withheld-surface rules. | Add a source-set drift check: refresh required when ledger/source docs change. | Do not let ChatGPT Project contents become canonical; do not include sensitive data; do not skip refresh after source-set changes. | Portable as an export-control workflow: each customer needs a manifest, sanitizer, refresh proof, and drift warning. |

## 5. Deployment Recipe Sketch

### Personal OpenClaw

Minimum viable stack:

- Core runtime law / canonical docs.
- Service-control SE kernel.
- MCP progressive discovery.
- Model routing / fallback policy.
- Guardian approvals.
- Google broker only for approved Cassandra surfaces.
- Cassandra as personal assistant with bounded action and broker gates.
- Dashboard/operator reporting as read-only/proposal artifact.
- Source-set ingest workflow for external review packets.

Keep Legal, Hermes provider fallback, broad memory/retrieval, service mutation, and live-state verification behind separate lanes until each has proof and validation-map coverage.

### Local-First Law Firm Discovery

Minimum viable stack:

- Core runtime law / customer-specific operator docs.
- Legal/local discovery product with private vault contract.
- Local model privacy boundary, initially deterministic/no-model for real matters.
- Guardian approvals for export/support packets.
- Source-set ingest workflow only after sanitizer approval.
- Service-control SE kernel if any local services are installed.

Do not include Cassandra Gmail behavior, broad MCP roots, external expert escalation with raw matter data, or cloud model fallback by default.

### Creative/Business Assistant

Minimum viable stack:

- Core runtime law / customer-specific operator docs.
- Cassandra-like assistant with capability registry and broker-gated calendar/email surfaces.
- Guardian approvals for external sends and irreversible actions.
- Google broker with denied-by-default class table.
- Dashboard/operator reporting.
- Local model privacy boundary for drafts/summaries.

Keep payments, bank verification, inbox roaming, Telegram/SMS sends, and autonomous follow-up schedules disabled until each has explicit capability policy and tests.

### Company Internal Advisory Assistant

Minimum viable stack:

- Core runtime law / company policy packet.
- Hermes-like advisory consultant as packet-in/proposal-out.
- MCP progressive discovery with company-approved docs-only default.
- Expert escalation only through sanitized packet and approval receipt.
- Memory/retrieval substrate only after provenance/redaction/rebuild rules exist.
- Dashboard/reporting for advisory artifacts and withheld surfaces.

Do not let advisory outputs become canonical decisions by presence; company systems of record remain external authorities unless a brokered integration is explicitly built and tested.

## 6. Anti-Slop Rules

- No module promotes itself. Promotion requires an explicit status change, proof, validation-map entry, and operator approval when authority expands.
- No advisory output becomes canonical by presence. Canonical state lives in its named source of truth.
- No sensitive data leaves the local boundary without sanitizer, approval, and logging.
- No service/runtime mutation happens without explicit mode, source-of-truth owner, validation plan, and approval where required.
- No new capability ships without a validation map entry and a denied-by-default data/authority rule.
- No source-set drift is allowed without an ingest refresh or a documented withheld-surface note.
- No module gets broader MCP, terminal, provider, messaging, or write access as a convenience shortcut.
- No installed model, installed service, or present script counts as trusted or owned merely because it exists.

## 7. Near-Term Recommended Sequence After Service-Freeze Closure

1. Service-freeze docs polish: keep Slice 8 disposition concrete, remove ambiguous ownership language, and add a short operator-facing closure note.
2. First read-only Hermes advisory trial: use a bounded service-freeze closure packet and produce a non-canonical consultant memo for operator review only.
3. Read-only live-state verification plan: design exact commands, redaction rules, approval requirement, and expected artifacts before any live service check is run.
4. Operator dashboard/report artifact: build a read-only status packet with source list, proof freshness, withheld surfaces, next safe slice, and approval needs.
5. Model contention/benchmark plan: use synthetic fixtures, scheduled windows, local-only defaults, and acceptance thresholds before model trust expands.
6. Memory/retrieval substrate plan: define raw data, metadata, embeddings, provenance, redaction, deletion, rebuild, and customer isolation before implementation.

## 8. Ledger Maintenance Contract

Update this ledger when any module changes status, authority, data boundary, proof, dependency, or productization posture.

Every update should answer:

- What changed?
- Which source of truth proves it?
- Which validation map entry applies?
- Did authority expand, stay the same, or shrink?
- Did any source-set or ingest workflow need refresh?

If those questions cannot be answered, the module remains at its previous status and the change belongs in a planning lane, not in runtime.
