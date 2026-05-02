# OpenClaw Personal AI Substrate North Star

Status: planning note. Docs-only direction capture. This file does not authorize runtime, service, model, provider, Gmail, Telegram, MCP, Hermes, Legal, or private-data changes.

Source basis:

- `/home/openclaw/OPENCLAW_RUNTIME.md`
- `/home/openclaw/USER.md`
- `/home/openclaw/CORE_ARCHITECTURE_PRINCIPLES.md`
- `/home/openclaw/docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`
- `/home/openclaw/docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md`
- `/home/openclaw/docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md`
- `/home/openclaw/docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md`
- `/home/openclaw/docs/testing/VALIDATION_MAP.md`

## 1. Purpose

This note captures where OpenClaw is building toward so future lanes can keep the same center of gravity.

OpenClaw is meant to become a local-first personal AI substrate: owned files, owned memory, owned workflows, bounded agents, swappable models, permissioned tools, clear approval gates, and interface surfaces that call into one governed stack.

This is not a capability claim. It separates what is already landed, what is actively being built, and what remains future direction.

## 2. North Star

OpenClaw should make the operator stronger without making the operator dependent on one AI app, one model vendor, one chat history, one dashboard, or one hidden memory system.

The durable asset is the stack: repo source, project memory, decisions, docs, transcripts, validation maps, approval records, evidence chains, workflow state, and the rules for rebuilding derived artifacts. Models may help operate the stack, but they should not own it.

The long-term shape is many surfaces with one governed substrate underneath. Telegram, dashboard/app views, VS Code, Finder/Mac mirrors, voice, documents, and future interfaces should use the same authority boundaries, memory rules, approval gates, and evidence artifacts instead of creating separate memory and control layers.

## 3. What OpenClaw Is Not

OpenClaw is not just a local model box. Local models are important, but the project is about durable control of files, memory, workflows, permissions, and evidence.

OpenClaw is not a cloud LLM product with local files attached. Cloud/frontier/external models may be useful visitors or specialists for rare, hard, non-sensitive or sanitized work, but they must not own memory, workflow state, private data, or approval authority.

OpenClaw is not an unrestricted tool surface. MCP, shell, filesystem access, Gmail, Telegram, services, providers, and dashboards are permissioned surfaces, not magic. Default exposure should stay narrow.

OpenClaw is not a collection of separate assistant memories. Interfaces should not each invent their own canonical state, private context store, queue, or control plane.

OpenClaw is not ready for broad always-on autonomy just because parts of the stack can run unattended. Always-on agents require service/process ownership, watchdog clarity, model contention control, bounded inputs, deterministic status artifacts, and approval gates before expansion.

## 4. Build-Toward Principles

### Own The Substrate

Source files, project memory, decisions, docs, transcripts, code, evidence, validation maps, and workflow state should remain durable outside any one AI app. Derived artifacts should be rebuildable from inspectable inputs and rules.

### Models Are Replaceable

The stack is the durable asset. Local and external models should be swappable execution aids, not sources of truth. Model capability must be benchmarked before trust, and malformed model output should fail closed where authority is involved.

### Local-First, Not Local-Only

Sensitive/private data defaults to deterministic or local-only handling. External models may be useful for non-sensitive repo/code/docs or explicitly sanitized packets with approval and logging. Real Legal/client/matter data, Gmail bodies/private correspondence, secrets, private logs, vault data, and raw PII must not go external by default.

### Tools Are Permissioned Surfaces

Default MCP and tool exposure should remain narrow. Unlocks should be explicit, gated, logged, reversible, and scoped to a lane. Broad filesystem roots, private logs, shared vaults, provider tools, messaging sends, write tools, and terminal/process controls should not be default context.

### Agents Need Role-Specific Access

A writing agent does not need shell access. A coding agent does not need bank, Legal, Gmail, CPA, Music Law, Publishing, private-vault, or private-log data unless a task explicitly and safely requires a bounded subset. A summarizer does not need delete permissions. Capability should follow role and lane, not model confidence.

### Memory Must Be Inspectable And Rebuildable

Memory/retrieval should become unified, auditable, and rebuildable. Raw data, metadata, embeddings, provenance, redaction status, and regeneration rules should be separable. No hidden vendor memory should become canonical.

### Operator UX Should Remove Context Hand-Management

The operator should not have to constantly hand-manage source sets, prompts, folders, context loading, and tool exposure. Interfaces should request governed packets or bounded artifacts from the substrate, then show what was used and what was withheld.

### Boring First Enables The Cool Layer

Static contracts, validation maps, service freeze, MCP hardening, evidence chains, approval gates, path hygiene, and source-set discipline are intentionally boring. That layer is what makes higher-agency UX safe enough to use.

## 5. Current Foundation Already Landed

Already landed or documented as active foundation:

- A canonical runtime law in `OPENCLAW_RUNTIME.md`, with `USER.md` and core architecture principles as durable operator and architecture context.
- A single-source-of-truth architecture preference: avoid shadow state, duplicated memory, extra control planes, and heavyweight orchestration unless a clear gap is proven.
- A hardened default MCP discovery profile that limits default filesystem MCP access to non-sensitive docs/spec roots and keeps broad repo, vault, logs, Hermes runtime, messaging, provider, write, terminal, and plugin surfaces withheld by default.
- A service-management freeze that records current systemd-owned and legacy/manual-owned processes without changing runtime behavior.
- A model fallback policy direction: no silent external fallback, sensitive/private data defaults local-only or deterministic, and external models require non-sensitive or sanitized packets with approval/logging.
- A validation map that links modified areas to targeted tests and harnesses.
- Deterministic and bounded safety work in several lanes, including approval gates, evidence chains, dashboard/report snapshot direction, mocked/non-live Cassandra triage, known-contact safety checkpoints, expert escalation contracts, and Legal private-boundary documentation.

Actively being built:

- More deterministic report/status artifacts that can be shown to the operator without exposing raw private logs or creating execution authority.
- Cleaner evidence chains and approval records for expert escalation, dashboard/report surfaces, overnight readiness, and safe handoff packets.
- Progressive-discovery patterns where each lane starts from a bounded packet and unlocks only the minimum next surface.

Future direction, not yet real:

- A unified memory/retrieval layer with separable raw data, metadata, embeddings, provenance, redaction status, and rebuild rules.
- A simple operator UX that hides source-set micromanagement while still showing exact inputs, withheld surfaces, and approval boundaries.
- Many interfaces sharing one governed substrate instead of each owning separate state.

## 6. Gaps Before The Cool Version Is Real

OpenClaw still needs these gaps closed before it can honestly feel like the intended substrate:

- Unified memory and retrieval are not yet a single inspectable, rebuildable system.
- Role-specific access is partly policy and partly convention; more structural enforcement is still needed across tools, agents, sidecars, and interfaces.
- External model use needs a complete sanitizer/export gate before protected or professional packets can safely leave local execution.
- Always-on operation needs clearer service/process ownership, watchdog behavior, model contention control, and deterministic status artifacts before expanding autonomy.
- Interface surfaces still risk drifting into separate prompts, folders, memories, and control paths unless they are deliberately made clients of the same governed substrate.
- Some authority boundaries remain decision points in the intent/control map, including messaging sends, stale/noisy folders, Hermes technical capability versus advisory policy, and future live Gmail/Cassandra behavior.
- Local model quality is not proven by installation. Benchmarks and lane-specific validation remain required before model-heavy autonomy can be trusted.

## 7. Interface/Operator UX Direction

The operator experience should become simpler, not more ceremonial.

Near-term UX should favor deterministic packets and reports: status snapshots, evidence manifests, bounded summaries, approval receipts, source lists, withheld-surface notes, and next-action recommendations that do not mutate state by themselves.

Medium-term UX should let the operator ask from any surface, then receive the same governed answer shape: what was read, what was not read, what is recommended, what is blocked, what needs approval, and what command or lane would do the next safe action.

Long-term UX should make Telegram, dashboards, VS Code, Finder/Mac mirrors, voice, and documents feel like windows into one substrate. Each surface can have its own ergonomics, but it should not own separate memory, private context, approval policy, or execution state.

The operator should be able to inspect and rebuild important memory and status. If a summary, embedding, report, or recommendation matters, there should be a way to trace its source, provenance, redaction level, and regeneration rule.

## 8. Guardrails / Do Not Do Yet

Do not treat this note as authorization to change runtime code, services, timers, schedulers, provider wiring, model defaults, Gmail/Telegram behavior, Hermes runtime, `.mcp.json`, secrets, vaults, private logs, LegalPrivate, Gmail bodies, CPA/Music Law/Publishing sensitive data, or private matter data.

Do not expand MCP/tool exposure as a convenience shortcut. Use explicit lane unlocks, gates, and reveal artifacts.

Do not make external models owners of memory, workflow state, private data, or approval authority.

Do not build separate per-interface memory and control layers when a governed substrate packet or artifact would do.

Do not promote legacy/manual processes into always-on service ownership without a narrow service-management lane and verification.

Do not claim OpenClaw already has unified memory, unified UX, proven local model quality, complete sanitizer/export gates, or safe broad autonomy. Those are build-toward goals.

## 9. Near-Term Next Lanes

Good next lanes stay boring and compound the substrate:

1. Add or extend deterministic report/status artifacts for dashboard and operator review without adding execution authority.
2. Strengthen static contract tests around no-execution flags, withheld surfaces, private markers, and source-reference-only behavior.
3. Define a memory/retrieval architecture note that separates raw data, metadata, embeddings, provenance, redaction, and regeneration rules before implementation.
4. Add role-specific tool-access contracts for common agent types before broad interface work.
5. Continue service/process ownership cleanup through documented slices rather than opportunistic runtime changes.
6. Design external-model sanitizer/export gates as a separate approval/logging lane before any protected packet can go external.
7. Shape the operator UX around bounded packets: inputs used, surfaces withheld, status, recommendation, approval need, and next safe command.

The direction is ambitious, but the implementation path should stay concrete: document the boundary, prove it with tests or static checks, then only unlock the next surface when the artifact and approval path are clear.