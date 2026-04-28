# OpenClaw Intent And Control Map

Status: draft operational control map. Pending user approval.

Source basis: Pass 0 and Pass 1 audit findings, plus:

- `/home/openclaw/OPENCLAW_RUNTIME.md`
- `/home/openclaw/USER.md`
- `/home/openclaw/CORE_ARCHITECTURE_PRINCIPLES.md`

This document records what the system appears intended to do, what current code appears to allow, what current policy appears to forbid, and where user decisions are still required.

Required uncertainty labels:

- CONFIRMED BY CODE/DOCS
- INFERRED FROM CODE/DOCS
- CONFLICT / NEEDS USER DECISION
- UNKNOWN

## Pending User Decisions

These decisions are not approved by this document. They are candidate control policies for user review.

1. Gmail draft approval policy
   - Candidate policy: Class B / Tier 1 approval for first contact, new recipient, sensitive topic, or attachment; Class A only for known-safe draft revisions.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/home/openclaw/cassandra_capability.py`, `/home/openclaw/google_access_policy.py`, `/home/openclaw/google_access_broker.py`.

2. SMS approval policy
   - Candidate policy: SMS send should be Chief/Guardian gated, not only chat YES/NO.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/home/openclaw/chief_sms_brain.py`, `/home/openclaw/chief_router.py`, `/home/openclaw/chief_email_brain.py`.

3. Hermes boundary
   - Candidate policy: Hermes remains advisory-only and non-canonical. Current docs say this, but code does not structurally enforce it yet. No canonical writes until hardened.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/home/openclaw/sidecars/hermes_home/HERMES_ORIENTATION.md`, `/home/openclaw/sidecars/hermes/LANE_POLICY.md`, `/home/openclaw/sidecars/hermes/tools/file_tools.py`, `/home/openclaw/sidecars/hermes/tools/approval.py`.

4. `/mnt/c/OpenClaw`
   - Candidate policy: Treat as active runtime/log root with stale/noisy subtrees. Do not delete as a whole. Later cleanup must use manifest -> user review -> quarantine -> delayed deletion.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/mnt/c/OpenClaw`, `/home/openclaw/.mcp.json`, repo path references found in Pass 1.

5. Legal private data
   - Candidate policy: Real Legal/client/matter data belongs only in approved private vaults such as `/mnt/c/OpenClawLegalPrivate`. It must not live in repo, `/mnt/c/OpenClaw/legal`, prompts, support packets, update packages, public fixtures, or external LLM contexts.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/home/openclaw/scripts/run_legal_pipeline_v0.sh`, `/home/openclaw/legal/path_guard.py`, `/home/openclaw/legal/support_packet.py`, `/home/openclaw/legal/README.md`, `/home/openclaw/docs/planning/openclaw_legal/law_program/LEGAL_VAULT_PATH_CONTRACT.md`.

6. Local/external model fallback
   - Candidate policy: Local models are default for sensitive/private data. External models are allowed only for non-sensitive repo/code/docs or sanitized packets with explicit approval/logging. No silent external fallback.
   - Status: PENDING USER APPROVAL.
   - Evidence: `/home/openclaw/chief_llm.py`, `/home/openclaw/cassandra_pii_hooks.py`, `/home/openclaw/headroom_routing_policy.json`, `/home/openclaw/runner_profiles.py`, `/home/openclaw/runner_registry.py`.

## 1. Executive Summary

- CONFIRMED BY CODE/DOCS: OpenClaw is intended to be a bounded local-agentic operating system. Local work is allowed when reversible and scoped. Destructive, external, credential-bearing, irreversible, or scope-expanding actions require human control. Evidence: `/home/openclaw/OPENCLAW_RUNTIME.md`.
- CONFIRMED BY CODE/DOCS: The strongest proven control areas are Chief approval policy, Guardian approval routing, Legal v0 path guarding/support packet design, planner-builder harness mechanics, and Chief acceptance gate behavior. Evidence: `/home/openclaw/chief_approval_policy.py`, `/home/openclaw/chief_approval_brain.py`, `/home/openclaw/legal/path_guard.py`, `/home/openclaw/legal/support_packet.py`, `/home/openclaw/polish_loop/orchestrator.py`, `/home/openclaw/chief_acceptance_gate.py`.
- CONFLICT / NEEDS USER DECISION: The riskiest unresolved areas are external sends, Gmail draft approval semantics, SMS confirmation, Hermes broad technical capability, `.mcp.json` filesystem exposure, stale Windows-visible folders, and model fallback boundaries.
- CONFLICT / NEEDS USER DECISION: Before fixes or broad tests, the user should approve the intended boundaries for Gmail drafts, SMS, Hermes, stale folder quarantine, local/external model fallback, and Legal private-data separation.

## 2. Global Operating Principles

| Principle | Status | Evidence path(s) | User approval needed? |
|---|---|---|---|
| One canonical source of truth per concern. Avoid shadow state and duplicate control systems. | CONFIRMED BY CODE/DOCS | `/home/openclaw/CORE_ARCHITECTURE_PRINCIPLES.md` | No, unless changing architecture |
| Repo source of truth is `/home/openclaw`; runtime law is `/home/openclaw/OPENCLAW_RUNTIME.md`. | CONFIRMED BY CODE/DOCS | `/home/openclaw/AGENTS.md`, `/home/openclaw/OPENCLAW_RUNTIME.md` | No |
| Safe local reads, bounded code edits, and tests are normally allowed. | CONFIRMED BY CODE/DOCS | `/home/openclaw/OPENCLAW_RUNTIME.md` | No |
| Destructive, external, credential, force-git, billing, or unattended high-risk actions require Chief approval. | CONFIRMED BY CODE/DOCS | `/home/openclaw/OPENCLAW_RUNTIME.md`, `/home/openclaw/chief_approval_policy.py` | No |
| Sensitive secrets and credentials must not be edited or inspected casually. | CONFIRMED BY CODE/DOCS | `/home/openclaw/OPENCLAW_RUNTIME.md`, `.gitignore`, `/home/openclaw/chief_approval_policy.py` | No |
| Sensitive/private data should not reach external models unless explicitly sanitized and lane-approved. | INFERRED FROM CODE/DOCS | `/home/openclaw/chief_llm.py`, `/home/openclaw/cassandra_pii_hooks.py`, `/home/openclaw/headroom_routing_policy.json` | Yes |
| Deterministic-first is preferred for Legal, approvals, path guards, harnesses, and routing. | CONFIRMED BY CODE/DOCS | `/home/openclaw/legal/README.md`, `/home/openclaw/google_access_policy.py`, `/home/openclaw/polish_loop/harness_task_runner.py` | No |
| Sidecars may advise but should not become canonical authorities unless explicitly approved. | CONFIRMED BY CODE/DOCS for Hermes docs; CONFLICT with technical capability | `/home/openclaw/sidecars/hermes_home/HERMES_ORIENTATION.md`, `/home/openclaw/sidecars/hermes/tools/file_tools.py` | Yes |
| Stale/noisy folders should follow manifest -> user review -> quarantine -> delayed deletion. | INFERRED FROM CODE/DOCS and audit risk | `/home/openclaw/CORE_ARCHITECTURE_PRINCIPLES.md`, Pass 1 host path inventory | Yes |

## 3. Lane/Component Intent Map

| Lane/component | Intended role | Status | Allowed actions | Forbidden actions | Approval points | Sensitive-data rule | External-model rule | Evidence paths | User decision needed |
|---|---|---|---|---|---|---|---|---|---|
| Chief | Runtime operator/orchestrator, approval brain, acceptance reviewer, notification surface. | CONFIRMED BY CODE/DOCS | Local reads, scoped edits/tests, approval routing, bounded acceptance verdicts. | Credential reads/edits, destructive/force/external high-risk actions without approval. | Tier 1 local confirm, Tier 2 Guardian. | Must not casually expose secrets/PII. | Local primary; external calls only after privacy routing. | `/home/openclaw/OPENCLAW_RUNTIME.md`, `/home/openclaw/chief_approval_policy.py`, `/home/openclaw/chief_approval_brain.py`, `/home/openclaw/chief_acceptance_gate.py` | No for role; yes for direct notification bypass treatment |
| Cassandra | Operator-support assistant for briefs, outreach drafts, Google access through broker, PII-aware replies. | INFERRED FROM CODE/DOCS | Draft Gmail, read allowed Google data, user-facing Telegram replies, PII tokenization. | Direct Gmail send currently disabled; unsafe PII-to-LLM if tokenization fails. | Broker gates Class B/C; HITL sometimes; unclear for Telegram. | PII vault/tokenization expected. | Local first; external only sanitized/non-sensitive. | `/home/openclaw/cassandra_brain.py`, `/home/openclaw/cassandra_capability.py`, `/home/openclaw/cassandra_pii_hooks.py` | Yes for Gmail draft and Telegram/SMS behavior |
| Guardian | Human approval bot and high-risk approval path. | CONFIRMED BY CODE/DOCS | Receive approval prompts, record expected approval IDs, approve/deny/delay/why. | Should not be bypassed for Tier 2 actions. | Tier 2 external/high-risk approval. | Approval prompts may contain sensitive summaries; should avoid secrets. | No model role found. | `/home/openclaw/chief_guardian_listener.py`, `/home/openclaw/chief_guardian_sender.py` | No |
| Hermes | Advisory sidecar, non-canonical synthesis/tooling gateway. | CONFLICT / NEEDS USER DECISION | Docs allow evidence-bound advisory work. Code allows broad file/terminal/MCP tools. | Docs forbid canonical mutation/governance/approval authority. | Hermes has its own command approval modes; not OpenClaw canonical approval. | No OpenClaw-specific denylist found for LegalPrivate or repo-sensitive paths. | Unclear; Hermes has synthesis/tool surface. | `/home/openclaw/sidecars/hermes_home/HERMES_ORIENTATION.md`, `/home/openclaw/sidecars/hermes/LANE_POLICY.md`, `/home/openclaw/sidecars/hermes/tools/file_tools.py`, `/home/openclaw/sidecars/hermes/tools/approval.py` | Yes |
| PI/PII/operator-support | Sensitive identity and private data containment. | CONFIRMED BY CODE/DOCS for vault/hooks; UNKNOWN for all caller discipline | Tokenize/redact, encrypted vault access, audit without originals. | Raw PII to external LLM; credential exposure. | Credential and sensitive reads are hard Tier 2. | `.pii_vault.enc` is private and ignored by git. | Local-only or sanitized external. | `/home/openclaw/pii_vault.py`, `/home/openclaw/cassandra_pii_hooks.py`, `/home/openclaw/.gitignore` | Yes for external model policy |
| Planner-builder loop | Bounded autonomous planning/building harness with artifact validation and Chief acceptance. | CONFIRMED BY CODE/DOCS with one conflict | Write `pc_output.md`, harness artifacts, logs; bounded tests. | Unbounded mutation outside declared surfaces. | Chief acceptance gate and orchestrator state machine. | Should avoid private data unless task explicitly permits. | Planner/Builder runners may use external tools depending profile. | `/home/openclaw/polish_loop/orchestrator.py`, `/home/openclaw/polish_loop/local_builder.py`, `/home/openclaw/runner_profiles.py` | Yes for tests-write authority |
| Harness/proof/evidence system | Deterministic proof capture, dry-run promotion/retest, evidence manifests. | CONFIRMED BY CODE/DOCS | Run approved dry-run harnesses, validate artifacts, record evidence. | Live service mutation unless explicitly approved. | Harness qualification and Chief acceptance. | Synthetic/non-sensitive preferred. | Mostly no model; acceptance may use local model. | `/home/openclaw/polish_loop/harness_task_runner.py`, `/home/openclaw/chief_acceptance_gate.py` | No |
| Model router | Route local/external models by task, cost, privacy, and lane. | INFERRED FROM CODE/DOCS | Local Ollama, external Nemotron/Claude only under controls. | Sensitive data to external fallback without sanitization. | External use should be logged; approval unclear. | Sensitive tasks route local-only. | External allowed for non-sensitive architecture/code/docs. | `/home/openclaw/chief_llm.py`, `/home/openclaw/headroom_routing_policy.json`, `/home/openclaw/runner_profiles.py` | Yes |
| Google/Gmail/Calendar broker | Central policy gate for Google APIs. | CONFIRMED BY CODE/DOCS with Gmail draft conflict | Class A auto, Class B Tier 1, Class C Tier 2. | Chief denied Google access in policy. | Broker calls Chief approval for B/C. | Gmail bodies are sensitive; audit omits body text. | No direct model role. | `/home/openclaw/google_access_policy.py`, `/home/openclaw/google_access_broker.py` | Yes for draft create |
| Legal v0 | Deterministic local-first Legal workspace pipeline with private vault separation. | CONFIRMED BY CODE/DOCS | Matter creation/import/search/report/review/support packet under private vault contract. | LLM/cloud/API/network/legal advice; product repo as matter root. | Not approval-focused; path-guard focused. | Private matter data belongs in `/mnt/c/OpenClawLegalPrivate`. | External forbidden. | `/home/openclaw/legal/README.md`, `/home/openclaw/legal/path_guard.py`, `/home/openclaw/scripts/run_legal_pipeline_v0.sh` | No, except old pipeline disposition |
| Mac mirror/mac_eyes | Mac/operator mirror, launchers, sync bridge, some legacy docs. | INFERRED FROM CODE/DOCS | Sync/planning mirror, launchers, watcher logs. | Canonical authority unclear; private vault contents not to inspect. | Unknown. | May reference Legal planning but should not expose private matter contents. | Unknown. | `/home/openclaw/mac_eyes`, `/home/openclaw/mac_eyes/Launchers/scaffold_mac_legal_vault.sh` | Yes for stale/legacy handling |
| `/mnt/c/OpenClaw` | Windows-visible runtime/log/state/shared legacy location. | CONFLICT / NEEDS USER DECISION | Active logs/state plus old legal/billing/data trees. | Should not be treated as clean canonical repo. | Path-specific. | May contain sensitive logs/data; unclear by subtree. | Logs may be exposed through MCP. | `/mnt/c/OpenClaw`, `/home/openclaw/.mcp.json`, repo path references | Yes |
| `/mnt/c/OpenClawShared` | Shared/operator vault/mirror area. | INFERRED FROM CODE/DOCS | Operator vault, shared handoffs, approval log. | Unclear root artifacts/screenshots should not become canonical. | Unknown. | May contain private operator material. | Exposed to filesystem MCP. | `/mnt/c/OpenClawShared/openclaw-vault`, `/home/openclaw/.mcp.json` | Yes |
| `/mnt/c/OpenClawLegalPrivate` | Private Legal vault/staging/exports. | CONFIRMED BY CODE/DOCS | Legal private matter roots, staging, exports. | Repo storage; public/shared exposure; external model exposure. | Path guard, script contract. | Sensitive Legal matter data allowed here. | External forbidden. | `/home/openclaw/scripts/run_legal_pipeline_v0.sh`, `/home/openclaw/docs/planning/openclaw_legal/law_program/LEGAL_VAULT_PATH_CONTRACT.md` | No |
| `/home/openclaw/OpenClaw/state` | Legacy/current runtime state path. | INFERRED FROM CODE/DOCS | Chief/session/state files. | Manual deletion/migration without manifest. | Unknown. | Could contain operational/private state. | Should not be externally prompted blindly. | `/home/openclaw/OpenClaw/state` | Yes for migration/cleanup |
| `/home/openclaw/sidecars/hermes_home` | Hermes runtime home. | CONFIRMED BY CODE/DOCS | Hermes config, logs, sessions, state DB. | Secret/session inspection without approval. | Hermes gateway approval modes. | May contain private sessions/secrets; ignored by git. | Unknown. | `/home/openclaw/systemd/user/hermes-gateway.service.in`, `/home/openclaw/sidecars/hermes_home` | Yes for boundary |

## 4. Action Authority Map

| Action | Current implementation | Intended policy | Current gate | Desired gate candidate | Conflict? | Sensitivity risk | Evidence | User decision needed |
|---|---|---|---|---|---|---|---|---|
| Telegram send | Direct sender wrappers can post externally. | CONFIRMED: external sends should be controlled. | Some paths no approval wrapper. | Tier by content/action; routine notifications may be allowlisted. | Yes | Medium/high | `/home/openclaw/chief_sender.py`, `/home/openclaw/chief_notify.py`, `/home/openclaw/OPENCLAW_RUNTIME.md` | Yes |
| Chief notify | Silent Telegram notification helper. | INFERRED: operational notify may be allowed if non-sensitive. | Env presence only. | Explicit allowlist for non-sensitive notify. | Yes | Medium | `/home/openclaw/chief_notify.py` | Yes |
| Cassandra Telegram send | Sends Telegram/voice; harness no-send mode exists. | INFERRED: user-facing replies allowed; risky sends gated if sensitive/external. | Harness guard only. | Content/action tier gate. | Yes | Medium | `/home/openclaw/cassandra_sender.py` | Yes |
| Gmail read metadata | Broker Class A for Cassandra; Chief denied. | CONFIRMED by broker policy. | Auto-allowed for Cassandra. | Keep Class A if user approves. | No obvious conflict | Medium | `/home/openclaw/google_access_policy.py` | Yes |
| Gmail read body | Broker Class A for Cassandra; audit omits body text. | CONFIRMED by broker policy; privacy risk remains. | Auto-allowed for Cassandra. | Consider body-specific sensitivity gate. | Possible | High | `/home/openclaw/google_access_policy.py`, `/home/openclaw/google_access_broker.py` | Yes |
| Gmail draft create | Broker Class A/no approval. Cassandra capability comment says L1 approval. | CONFLICT / NEEDS USER DECISION. | Auto-allowed. | Class A or Tier 1, user decision. | Yes | Medium/high | `/home/openclaw/google_access_policy.py`, `/home/openclaw/google_access_broker.py`, `/home/openclaw/cassandra_capability.py` | Yes |
| Gmail send | Broker Class C; Cassandra send disabled/future. | CONFIRMED: high-risk external send. | Tier 2 if reachable through broker. | Guardian Tier 2. | No | High | `/home/openclaw/google_access_policy.py`, `/home/openclaw/cassandra_capability.py` | No |
| Calendar read | Broker Class A for Cassandra. | CONFIRMED by broker policy. | Auto-allowed. | Keep Class A if user approves. | No | Medium | `/home/openclaw/google_access_policy.py` | Yes |
| Calendar write | Broker Class B for Cassandra. | CONFIRMED by broker policy. | Tier 1 via Chief approval brain. | Tier 1 or Tier 2 depending destructiveness. | No | Medium/high | `/home/openclaw/google_access_policy.py`, `/home/openclaw/google_access_broker.py` | Yes |
| SMS send | Router confirms YES/NO in chat. | CONFLICT: external send should use stronger approval. | Weak chat confirmation. | Guardian or Chief approval for send. | Yes | High | `/home/openclaw/chief_sms_brain.py`, `/home/openclaw/chief_router.py` | Yes |
| SMTP email send | Draft preview then Chief approval before send. | CONFIRMED: external email send gated. | Chief approval brain. | Keep; verify Tier. | No | High | `/home/openclaw/chief_email_brain.py` | No |
| File write inside repo | Generally allowed for bounded work; approval policy has hard T2 for secrets/sensitive files. | CONFIRMED. | Tool/runtime plus approval policy. | Existing policy. | No | Varies | `/home/openclaw/OPENCLAW_RUNTIME.md`, `/home/openclaw/chief_approval_policy.py` | No |
| File write to `/mnt/c/OpenClaw/logs` | Many runtime logs/audits write there. | CONFIRMED operational runtime logs. | Usually ungated deterministic write. | Deterministic safe write if log content redacted. | Possible | Medium/high | `/home/openclaw/chief_approval_brain.py`, `/home/openclaw/google_access_broker.py`, `/home/openclaw/cassandra_brain.py` | Yes |
| File write to `/mnt/c/OpenClawShared` | Approval log/vault/shared artifacts. | INFERRED operator mirror/shared vault. | Ungated in some paths. | Allow known audit/handoff writes only. | Possible | Medium/high | `/home/openclaw/chief_approval_brain.py`, `/home/openclaw/.mcp.json` | Yes |
| File write to `/mnt/c/OpenClawLegalPrivate` | Legal v0 scripts create vault/staging/exports. | CONFIRMED private Legal write. | Path guard/script contract. | Legal-only deterministic path guard. | No for v0 | Very high | `/home/openclaw/scripts/run_legal_pipeline_v0.sh`, `/home/openclaw/legal/path_guard.py` | No |
| Legal export/write | Deterministic support/review/report outputs. | CONFIRMED local-only Legal v0. | Path guards, matter root validation. | Keep deterministic; no model/cloud. | No | Very high | `/home/openclaw/legal/support_packet.py`, `/home/openclaw/legal/README.md` | No |
| Support packet creation | Sanitized packet excludes source/private paths/content. | CONFIRMED. | Deterministic exclusions. | Keep. | No | Lower if code works | `/home/openclaw/legal/support_packet.py` | No |
| Model call local | Ollama local endpoint. | CONFIRMED allowed for appropriate lanes. | Routing logic, not approval. | Allow local for non-secret bounded tasks; sensitive by lane. | No | Medium | `/home/openclaw/chief_llm.py` | Yes for sensitive data |
| Model call external | Nemotron/Claude/Codex/Gemini references. | INFERRED allowed only non-sensitive/sanitized/manual. | Logging; manual env flag for Claude. | Explicit policy by task type. | Yes/unclear | High | `/home/openclaw/chief_llm.py`, `/home/openclaw/runner_profiles.py`, `/home/openclaw/runner_registry.py` | Yes |
| Hermes file read/write | Generic file tools; limited system-path denylist. | CONFLICT with advisory/non-canonical docs. | Generic denylist only. | OpenClaw-specific deny/allow policy. | Yes | Very high | `/home/openclaw/sidecars/hermes/tools/file_tools.py`, `/home/openclaw/sidecars/hermes_home/HERMES_ORIENTATION.md` | Yes |
| Hermes terminal command | Approval tool supports manual/smart/off/yolo and environment bypasses. | CONFLICT with advisory intent. | Hermes approval modes, not Chief. | Canonical OpenClaw gate for repo/private paths. | Yes | High | `/home/openclaw/sidecars/hermes/tools/approval.py` | Yes |
| Planner-builder `pc_output` write | Orchestrator/builder writes pass artifact. | CONFIRMED. | Format/state validation. | Keep. | No | Low/medium | `/home/openclaw/polish_loop/orchestrator.py`, `/home/openclaw/polish_loop/local_builder.py` | No |
| Planner-builder tests write | Code permits writes under `/home/openclaw/tests`; comment says read-only/pc_output-only. | CONFLICT / NEEDS USER DECISION. | Path restriction only. | Approve or remove tests-write authority. | Yes | Medium | `/home/openclaw/polish_loop/local_builder.py` | Yes |
| Chief acceptance approval/rejection | Bounded local model verdict with fail-closed malformed output. | CONFIRMED. | Local acceptance gate. | Keep with tests. | No | Medium | `/home/openclaw/chief_acceptance_gate.py` | No |
| HITL action approval | HITL store exists; disabled by default except threshold/superflag/auto-deny logic. | CONFLICT / NEEDS USER DECISION. | Env/flag-dependent. | Decide mandatory vs optional HITL classes. | Yes | High | `/home/openclaw/hitl_pending_store.py`, `/home/openclaw/hitl_action_service.py` | Yes |

## 5. Sensitive-Data Boundary Map

| Path/surface | Intended role | Sensitive data allowed? | External model allowed? | Local model allowed? | Repo/git risk | Current guard | Conflict/unknown | User decision needed |
|---|---|---|---|---|---|---|---|---|
| `/home/openclaw` | Canonical repo/source. | No private client/matter/secrets except ignored operational files. | Non-sensitive code/docs only. | Yes for code/docs; sensitive only by lane. | `.gitignore` allowlist reduces risk. | `.gitignore`, runtime law. | Some ignored runtime state exists inside repo. | Yes |
| `/home/openclaw/.chief.env` | Secret env file. | Yes, secrets only. | No. | No unless explicit approved secret handling. | Ignored. | Runtime law and approval hard T2. | Contents not inspected. | No |
| `/home/openclaw/.google-secrets` | Google OAuth credentials/token. | Yes, credentials only. | No. | No. | Ignored. | Runtime law and approval hard T2. | Contents not inspected. | No |
| `/home/openclaw/.pii_vault.enc` | Encrypted PII vault. | Yes. | No raw PII. | Local only if lane-approved. | Ignored. | Encryption/key in env; PII hooks. | Caller discipline unknown. | Yes |
| `/mnt/c/OpenClaw` | Windows-visible runtime/log/state/legacy root. | Possible by subtree. | No blanket permission. | Possible for logs if approved/sanitized. | Outside git. | None global. | Active and stale/noisy simultaneously. | Yes |
| `/mnt/c/OpenClaw/logs` | Runtime logs/audits. | Possible sensitive operational data. | Only sanitized summaries. | Yes with caution. | Outside git; MCP exposed. | Some log redaction in broker/PII hooks. | Broad MCP exposure may be too wide. | Yes |
| `/mnt/c/OpenClaw/legal` | Old Legal path. | Possible private matter data. | No. | No unless explicitly migrated/synthetic. | Outside git. | Old scripts only. | Conflicts with v0 private vault contract. | Yes |
| `/mnt/c/OpenClaw/law_program` | Old/duplicate Legal planning/runtime tree. | Unknown/possible. | No. | No until classified. | Outside git. | Unknown. | Likely stale/noisy. | Yes |
| `/mnt/c/OpenClawShared` | Shared/operator mirror. | Possible operator-sensitive data. | No blanket permission. | Only approved/sanitized. | Outside git; MCP exposed. | None global. | Root artifacts/screenshots noisy. | Yes |
| `/mnt/c/OpenClawShared/openclaw-vault` | Operator vault/shared docs. | Yes/possible. | No blanket permission. | Only approved/sanitized. | Outside git; MCP exposed. | `.mcp.json` grants filesystem MCP. | Exposure may be intentional or too broad. | Yes |
| `/mnt/c/OpenClawLegalPrivate` | Private Legal vault/staging/exports. | Yes, Legal matter data. | No. | Not for v0; future only if approved. | Outside git. | Legal path guard/script contract. | Contents not inspected. | No |
| `/home/openclaw/legal` | Legal v0 code. | No matter data. | Code/docs only. | Code/tests only. | Tracked code. | Path guard rejects repo matter roots. | No. | No |
| `/home/openclaw/docs/planning/openclaw_legal` | Legal planning/docs. | No private matter contents. | Non-sensitive planning only. | Yes for docs. | Tracked docs. | Policy by convention. | Must not drift into matter content. | Yes |
| `/home/openclaw/mac_eyes` | Mac mirror/launchers/legacy. | Possible planning/private references. | No blanket permission. | Only approved/sanitized. | In repo. | Unknown. | Legacy/noisy subtree. | Yes |
| `/home/openclaw/sidecars/hermes` | Hermes code. | No private data expected. | Code/docs only. | Yes for code/docs. | Tracked/controlled by repo. | Normal repo controls. | No. | No |
| `/home/openclaw/sidecars/hermes_home` | Hermes runtime home/config/logs/sessions. | Possible secrets/session data. | No blanket permission. | No unless explicit. | Ignored by git. | Not inspected; service config points here. | Hermes session contents private. | Yes |

## 6. Local/External Model Policy Draft

This section is a policy draft, not an approved capability claim. Where no benchmark or harness proves quality, capability is marked UNPROVEN.

| Task type | Local model primary? | External model allowed? | Fallback direction | Sensitive-data rule | Approval/logging requirement | Evidence/notes |
|---|---|---|---|---|---|---|
| Deterministic classification | Prefer no model. | No unless explicitly needed. | Deterministic -> local only. | No sensitive raw data to external. | Log if operational. | CONFIRMED: deterministic policies in Google/Legal/harness. |
| Summaries of non-sensitive logs | Yes. | Yes if explicitly non-sensitive. | Local -> external only after sensitivity check. | Logs may contain private data; default caution. | External metadata logging required. | INFERRED from `/home/openclaw/chief_llm.py`. |
| Summaries of sensitive/private data | Local only, UNPROVEN quality. | No. | No external fallback. | Raw sensitive data stays local/private. | Approval should precede any exception. | CONFIRMED direction in `/home/openclaw/headroom_routing_policy.json`; capability UNPROVEN. |
| Email drafting | Yes, with PII controls. | Only sanitized/non-sensitive and user-approved. | Local -> sanitized external only if approved. | Gmail body/private context high-risk. | Draft/send policy must be explicit. | CONFLICT: Gmail draft gate mismatch. |
| Gmail body analysis | Yes, with strict redaction/tokenization. | No by default. | Local only. | Body text is sensitive. | Audit should omit body text. | CONFIRMED broker audit omits body text; model boundary needs approval. |
| Legal matter analysis | No model in v0. | Forbidden in v0. | Deterministic only. | Matter data remains in LegalPrivate. | Path guard/audit. | CONFIRMED: `/home/openclaw/legal/README.md`. |
| Architecture review | Local or external allowed if repo-only/non-sensitive. | Yes for non-sensitive code/docs. | Local -> external if no secrets/private data. | Do not include secrets/private logs. | External metadata logging. | INFERRED from runner profiles and runtime law. |
| Code review | Local or external allowed for repo code. | Yes for non-sensitive code. | Local -> external allowed after path check. | Do not include ignored secrets/runtime private files. | Normal audit/logging. | INFERRED. |
| Planner-builder work | Depends on runner. | Gemini/Codex references exist; Claude blocked autonomously. | Approved runner profile only. | No private data unless task-specific approval. | Harness/acceptance evidence. | CONFIRMED: `/home/openclaw/runner_profiles.py`, `/home/openclaw/runner_registry.py`. |
| Chief acceptance gates | Yes, local fast lane. | No evidence external is intended. | Fail closed on bad output. | Evidence should be bounded. | Test coverage required. | CONFIRMED: `/home/openclaw/chief_acceptance_gate.py`. |
| Cassandra user-facing replies | Yes. | Sanitized only; UNPROVEN broad safety. | Local -> external only after PII hook success. | If PII tokenization fails, block. | Route logs. | CONFIRMED: `/home/openclaw/cassandra_pii_hooks.py`, `/home/openclaw/cassandra_brain.py`. |
| Hermes synthesis | UNKNOWN. | UNKNOWN. | Unknown. | Hermes should avoid canonical/private data unless approved. | Unknown. | Hermes docs advisory; code capability broad. |
| Support packet generation | No model. | No. | Deterministic only. | Exclude source/private paths/content. | Legal audit/support output. | CONFIRMED: `/home/openclaw/legal/support_packet.py`. |
| Long-context audit synthesis | Local preferred for sensitive logs; external allowed only for non-sensitive repo facts. | Yes for non-sensitive repo/docs only. | Local/private -> sanitized external if approved. | Do not include secrets, client docs, Gmail bodies, private vault contents. | Audit should cite paths and uncertainty. | INFERRED from runtime law and current audit constraints. |

## 7. Known Conflicts Requiring User Decision

1. Gmail draft create approval
   - Evidence: `/home/openclaw/cassandra_capability.py` says Gmail draft create is L1 approval; `/home/openclaw/google_access_policy.py` marks `google.gmail.draft.create` Class A; `/home/openclaw/google_access_broker.py` only approval-gates Class B/C.
   - Why it matters: Current code allows Cassandra Gmail draft creation without approval.
   - Decision options: Keep Class A/no approval; change to Class B/Tier 1; split by recipient/content/sensitivity.

2. Old Legal pipeline vs Legal v0 private-vault contract
   - Evidence: `/home/openclaw/run_legal_pipeline.sh` uses `/mnt/c/OpenClaw/legal/cases`; `/home/openclaw/scripts/run_legal_pipeline_v0.sh` uses `/mnt/c/OpenClawLegalPrivate`.
   - Why it matters: Old path may expose or confuse private Legal matter storage.
   - Decision options: Mark old pipeline stale; quarantine after manifest; preserve read-only historical reference.

3. Planner-builder write authority mismatch
   - Evidence: `/home/openclaw/polish_loop/local_builder.py` comment says read-only/pc_output-only, but code permits writes under `/home/openclaw/tests`.
   - Why it matters: Actual model-mediated write authority is broader than the comment says.
   - Decision options: Approve test-write authority; restrict to `pc_output.md`; update docs later.

4. HITL disabled by default for most non-threshold actions
   - Evidence: `/home/openclaw/hitl_pending_store.py` returns allow when HITL disabled except special cases; `/home/openclaw/hitl_action_service.py` approval hook is placeholder.
   - Why it matters: HITL may sound stronger than it is.
   - Decision options: Keep optional HITL; make HITL mandatory for defined classes; retire unused placeholder language.

5. SMS weaker than email approval
   - Evidence: `/home/openclaw/chief_email_brain.py` uses Chief approval before send; `/home/openclaw/chief_sms_brain.py` and `/home/openclaw/chief_router.py` use chat YES/NO.
   - Why it matters: SMS is external and high-impact but less gated.
   - Decision options: Require Guardian/Chief approval; keep YES/NO for trusted low-risk recipients; disable SMS send.

6. Direct Telegram sender wrappers may bypass approval intent
   - Evidence: `/home/openclaw/chief_sender.py`, `/home/openclaw/chief_notify.py`, `/home/openclaw/cassandra_sender.py`.
   - Why it matters: External sends can occur without central approval if called directly.
   - Decision options: Treat as notification-only allowlisted path; require a central send broker; classify by content.

7. Hermes advisory docs vs broad technical capability
   - Evidence: `/home/openclaw/sidecars/hermes_home/HERMES_ORIENTATION.md`, `/home/openclaw/sidecars/hermes/LANE_POLICY.md`, `/home/openclaw/sidecars/hermes/tools/file_tools.py`, `/home/openclaw/sidecars/hermes/tools/approval.py`.
   - Why it matters: Docs say non-canonical/advisory, but file/terminal/MCP tools are broad.
   - Decision options: Keep convention-only; add structural OpenClaw path limits later; disable risky tools for this repo.

8. `.mcp.json` filesystem exposure may be intentional or too broad
   - Evidence: `/home/openclaw/.mcp.json` grants `/home/openclaw`, `/mnt/c/OpenClaw/logs`, `/mnt/c/OpenClawShared/openclaw-vault`.
   - Why it matters: Logs and shared vault can contain sensitive operator data.
   - Decision options: Keep as trusted operator MCP; narrow paths; add redaction/export-only surface.

9. `/mnt/c/OpenClaw` is both active and stale/noisy
   - Evidence: Active logs/state plus old `legal`, `law_program`, exports, billing/data trees under `/mnt/c/OpenClaw`.
   - Why it matters: Operators and agents may confuse canonical, runtime, stale, and private surfaces.
   - Decision options: Manifest and label active subtrees; quarantine stale subtrees after review; keep untouched.

## 8. Stale/Noisy Folder Control Draft

Rule: no immediate deletion. Use manifest -> user review -> quarantine -> delayed deletion.

| Path | Current classification | Likely role | Risk | Delete now? | Quarantine first? | Migration candidate? | Required manifest before action | User decision needed |
|---|---|---|---|---|---|---|---|---|
| `/mnt/c/OpenClaw/legal` | Likely stale/high-risk | Old Legal case path | Private matter exposure/confusion | No | Yes | Yes, if useful non-private metadata exists | Names/counts/sizes/mtime only; no matter contents | Yes |
| `/mnt/c/OpenClaw/law_program` | Likely duplicate/noisy | Old Legal planning/runtime | Drift from repo docs | No | Yes | Maybe | File list and repo reference map | Yes |
| `/mnt/c/OpenClawShared` root artifacts/screenshots | Noisy/unknown | Shared scratch/operator artifacts | Sensitive screenshots possible | No | Yes | Maybe | Filename/count/mtime manifest only | Yes |
| `/home/openclaw/mac_eyes/legacy` | Likely stale/noisy | Old Mac bridge backups/docs | Confusing stale instructions | No | Yes | Maybe docs only | File list, dates, referenced-by search | Yes |
| `/home/openclaw/OpenClaw/exports/inspection-*` | Likely old proof outputs | Inspection/export history | Confusing old evidence | No | Maybe | Archive candidate | Manifest with dates and owning process | Yes |
| `/home/openclaw/openclaw_arko_review` | Unknown/likely stale duplicate | Review artifact/tree | Unknown authority | No | Yes | Maybe | Top-level manifest and reference search | Yes |
| `/home/openclaw/openclaw-builder` | Unknown/experimental | Builder side tree | Unknown write authority | No | Yes after inspection | Maybe | Top-level manifest and reference search | Yes |

## 9. User Approval Checklist

- Approve / change / reject: Chief intended role
- Approve / change / reject: Cassandra intended role
- Approve / change / reject: Guardian intended role
- Approve / change / reject: Hermes boundary
- Approve / change / reject: Gmail draft approval policy
- Approve / change / reject: SMS approval policy
- Approve / change / reject: Legal private data boundary
- Approve / change / reject: stale folder quarantine policy
- Approve / change / reject: local/external model fallback policy
- Approve / change / reject: test plan

## What This Document Does Not Do

- It does not prove tests pass.
- It does not approve implementation changes.
- It does not authorize deletion/quarantine.
- It does not authorize broader external LLM use.
- It does not grant Hermes canonical authority.

## Next Verification Phase

Tests should run only after user approval of the pending decisions, or after explicit permission to run tests before approval. This document does not run or approve the tests by itself.

| Order | Working directory | Command | What it proves | Pass condition | Sensitivity risk | Model use | Live services? | Approval first? |
|---|---|---|---|---|---|---|---|---|
| 1 | `/home/openclaw` | `python3 -m pytest tests/test_chief_approval_brain.py` | Chief approval boundaries and decision behavior. | Tests pass. | Low/medium; may touch approval temp/log fixtures. | No model expected. | No. | Yes |
| 2 | `/home/openclaw` | `python3 guardian_schema_harness.py --fixture staging/guardian_schema_harness/fixtures/guardian_validation.json` | Guardian schema/approval validation. | Harness reports valid expected cases. | Low if fixture synthetic. | No model expected. | No. | Yes |
| 3 | `/home/openclaw` | `python3 google_access_broker.py --test-policy` | Google Class A/B/C policy smoke test, including Gmail draft Class A. | Exit 0; expected cases OK. | Low; policy only. | No model. | No. | Yes |
| 4 | `/home/openclaw` | `python3 -m pytest tests/test_cassandra_outreach.py tests/test_cassandra_email_thread_analysis.py tests/test_cassandra_identity.py` | Cassandra outreach/thread/identity boundary behavior. | Tests pass without live sends. | Medium; inspect tests before running if uncertain. | Mock/local only expected. | No expected. | Yes |
| 5 | `/home/openclaw` | `python3 -m pytest tests/test_topic_sensitivity_gate.py` | Topic/sensitivity gating behavior. | Tests pass. | Low if fixtures synthetic. | No model expected. | No. | Yes |
| 6 | `/home/openclaw` | `python3 -m pytest tests/test_matter_workspace.py tests/test_local_ingestion.py tests/test_local_search.py tests/test_search_report.py tests/test_review_packet.py tests/test_support_packet.py tests/test_legal_mock_discovery_demo.py` | Legal synthetic/path-guard/support-packet behavior. | Tests pass using synthetic data only. | Medium; confirm no private vault reads first. | No model expected. | No. | Yes |
| 7 | `/home/openclaw` | `python3 -m pytest tests/test_chief_acceptance_gate.py tests/test_harness_task_runner.py tests/test_builder_fallback.py tests/test_pc_review_fallback.py` | Planner-builder, harness, fallback, acceptance gates. | Tests pass. | Low/medium; may write temp artifacts/cache. | Local model may be mocked. | No expected. | Yes |
| 8 | `/home/openclaw/sidecars/hermes` | `HERMES_HOME=$(mktemp -d) python -m pytest tests/tools/test_approval.py tests/tools/test_file_write_safety.py tests/tools/test_write_deny.py tests/test_mcp_serve.py` | Hermes generic approval/file/MCP boundaries. | Tests pass using temp Hermes home. | Low if temp home only. | No model expected. | No. | Yes |
| 9 | `/home/openclaw` | `python3 -m pytest tests/test_chief_acceptance_gate.py` plus targeted `chief_llm.py` dry inspection before any live call | Local model routing/acceptance behavior. | Acceptance tests pass; no external call. | Low. | Local/mocked only. | No. | Yes |
| 10 | `/home/openclaw` | Optional: `ollama list`, `systemctl --user status ...`, service log tails | Live service health only. | Services healthy; no restarts. | Medium; logs may contain private data. | Local service check only. | Yes. | Yes |

## Recommended Next Step

1. User corrects or approves this control map.
2. Run the bounded verification phase above only after approval or explicit permission.
3. Create read-only quarantine manifests for stale/noisy folders.
4. Patch confirmed control conflicts only after the approved map and test results exist.
