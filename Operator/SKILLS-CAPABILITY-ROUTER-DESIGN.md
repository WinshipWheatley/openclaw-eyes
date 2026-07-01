# OpenClaw Skills + Capability Router — design spec

**Date:** 2026-06-29 · **Status:** design (brainstorm-approved; pending operator spec-review) ·
**Builder:** Codex (future packet, AFTER the current `CODEX-MAESTRO-BRAIN-ROUTING-FIX` packet) ·
**Reviewer:** Opus.

## Objective function (read this first)
**The point is TASK COMPLETION** — cheapest-sufficient, credit-safe, resource-safe, and HONEST when
it genuinely can't be done. Skills are only the reusable *procedure layer*; a **capability router**
orchestrates the available capability (local-first) to actually finish the task. Never fake success;
defer transparently when truly blocked. Giving an LM a perfect skill but still failing the task is a
failure.

## Principles
- Skills are model-agnostic in **format** (markdown any LM reads), tiered for **capability**.
- **Authority never travels with a skill.** A skill can say "call the CPA brain, then propose a
  send," but send/money/ledger still route through Guardian + the gate layer exactly as today.
- **Completion > speed > parallelism.** Never let parallelism thrash/OOM the box (see §4).
- **Reuse-first, no NemoClaw dependency.** Build on `capability_skill_registry` (native), the
  **model-aware decomposer** (wire its missing step-executor), the **local-first credit ladder**
  (`fail-closed-to-free-local-ladder`), and the **deferred-reprocess queue**. NemoClaw is a
  guardrails/anti-rogue-external wrapper, NOT a skills platform — the `skill-creator` seen under it
  is a vendored dependency; we borrow the skill *format* as reference only.

## Components

### 1. Skill (a registry entry, not code)
```
id, owner_agent, triggers (intent/keywords/packet signals),
tools  = [brains / read-models / adapters it MAY call],
authority = advisory_only | references_gated_action  (never grants authority),
capability_needed = e.g. simple-extraction | multi-step-reasoning | code,
tiers = { simple: "<tight checklist a small local LM can follow>",
          rich:   "<full multi-step procedure for a capable agent>" }
```
Body is markdown. Created only via the factory (operator/Guardian-gated, §6).

### 2. Skill registry
Reuse/extend `capability_skill_registry`. Holds skills + tiers + metadata. Read-only at runtime;
mutation only through the gated factory path.

### 3. Capability router (completion orchestrator) — the heart
On a task:
1. **Match** task → skill(s) (procedure + `capability_needed`).
2. **Route to the cheapest-sufficient AVAILABLE executor:** local-first ($0 floor); prepaid-external
   only if the task needs it AND credits exist; perfect-external unavailable → next-best external →
   local. (Reuse `select_model_class` / `select_frontdoor_model` + the credit-aware ladder; prepaid
   + per-key caps only, never postpaid.)
3. **If no single available LM can do it whole → DECOMPOSE.** Break into ordered steps
   (series/parallel) where each step is small enough that an available *local* LM + a sub-skill
   **can** do it; run the chain; assemble. (Reuse the model-aware decomposer; **wire its
   step-executor** — the one piece still unbuilt.)
4. **If even the local chain can't finish** (real capability/credit wall) → **fail HONESTLY and
   defer** to the reprocess queue ("noted — I'll finish this when capability returns"), same pattern
   as the vision deferred-queue. Never silently fail; never fake completion.

### 4. Resource-aware scheduler (serial-vs-parallel gate) — critical
The decompose/route steps and any concurrent-task scheduling MUST be resource-aware. The box has a
small GPU (~6GB VRAM) + system RAM; loading a local model into VRAM is expensive; multiple models
contending spill VRAM→system RAM (slow) or OOM (fail).
- **Parallel ONLY when the concurrent models genuinely fit** (within VRAM, or a RAM spillover that is
  still net-faster than serial). Otherwise **SERIAL** — one model resident at a time, swap as needed.
- Dipping into system RAM when VRAM can't hold it all is fine — **but only if it still beats serial.**
  If serial (fit-in-VRAM, swap) completes faster AND more reliably, prefer serial.
- **Completion > speed > parallelism:** parallel that thrashes is slower AND may not finish — it is
  forbidden. Default to serial for local-LM-heavy work; allow parallel only when estimated to fit and
  be faster.
- The scheduler estimates step model sizes vs live capacity (probe: `ollama ps` + `free` + GPU mem)
  → chooses serial/parallel/batched, and **orders steps to minimize model swaps** (group steps by
  executor model). Reuse/relate to the in-flight "serial agent stress tests on local fallback
  models" work and ollama `keep_alive`/model-load timing.

### 5. Skill attach (your "the skill gets lumped into the package")
The packet builder injects the **router-chosen tier's** skill text into the executor's packet —
front-door via `maestro_context_packet`, factory/build via `task_routing`. Per-agent aware (the skill
is delivered in the agent's own voice/lane context, not a Maestro snowglobe).

### 6. Authority + governance
Skills never grant authority — gated actions route to Guardian as today. **Skill CREATION is
operator/Guardian-gated** through the factory; a validator rejects any skill referencing a
non-existent agent/tool (the Fin lesson: an LLM must not write a phantom capability into the system).

## Deliverables
- **A — Audit/catalog (read-only):** sweep all brains + agents + the 134 repos → a ranked map of the
  skills the system actually needs, what's already covered (brains/guides), and the gaps. This is the
  "check all my brains for skills" output; it also flags procedures that should stay **deterministic
  brains** rather than become LLM skills (don't LLM what a tool does deterministically).
- **B — Vertical slice:** wire the thin machinery (registry read → capability router →
  resource-aware schedule → tier-attach → live execution + assemble → honest-defer) around the **#1
  skill from the audit**, proven **LIVE** (non-snowglobe). Pick #1 together from the audit,
  coordinated so it does NOT collide with the check→books work Codex is building now.

## Non-snowglobe acceptance gate
Prove through the REAL pipeline, with receipts: (a) a task the front-door 8b can't do whole gets
decomposed into a local chain that COMPLETES it; (b) a resource-heavy case runs SERIAL (not thrashing
parallel) and finishes faster/at all; (c) a truly-impossible-right-now case DEFERS honestly and the
reprocess queue later drains it. Unit tests alone are insufficient.

## Sequencing
After the current `CODEX-MAESTRO-BRAIN-ROUTING-FIX` packet (avoid double-touching the finance path).
The audit (A) can run anytime (read-only). Build (B) waits for that packet's F to land.

## Open items (resolve during the audit / before the build packet)
1. The #1 vertical-slice skill (from the ranked catalog).
2. The exact live capacity-probe on this WSL+GPU box (VRAM/RAM/`ollama ps`).
3. Which candidate "skills" are actually better as deterministic brains.
4. How the router's serial/parallel estimate is calibrated (measured model load/run costs).
