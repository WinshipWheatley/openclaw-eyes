# Spec (PARKED): Resource-Aware, Self-Healing Model Orchestration

Status: **PARKED DESIGN** (operator-designed across 2026-06-30; do NOT build yet — deferred until the
green-gate/promotion is done + operator GO). This consolidates several design threads into ONE coherent
layer so it's built as one thing. The future Codex prompt points here + at the two doctrine docs.

Governing doctrines (read first): `Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md` (one source of truth +
3-layer enforcement) and `Operator/SELF-HEALING-DIAGNOSIS-ORDER.md` (harness-first, fix-last).

**Reuse-first invariant:** every component below EXTENDS existing machinery — do not rebuild. And every
component **flags, never silently masks**; risky code rewrites are **Guardian + operator-gated**.

---

## Component 1 — Capability / Availability Router
**Gap:** the routing instincts exist but are scattered; no single transparent "availability brain."
**Build:** one router that unifies the signals and ALWAYS explains itself + never silently stalls —
free VRAM + resident models (already sensed by `chief_llm.select_frontdoor_model`), external
credit/quota state (`chief_llm.external_language_model_call` already fails-closed-to-local;
`polish_loop/builder_output_validator.py` already detects quota/rate-limit messages), Codex
window state, provider health. Policy: **route to available capability → decompose to a local chain →
defer honestly → never fake** (operator's standing rule). Records WHY for every route (the P1
`model_selection_reason` is the seed).
**Reuse:** `select_frontdoor_model`, `external_language_model_call` (fail-closed), `builder_output_validator`
(quota detect), `Operator/SKILLS-CAPABILITY-ROUTER-DESIGN.md` (already designed), the model-aware
decomposer (`[[project_model_aware_decomposer]]`).

## Component 2 — GPU Arbiter (the cool part)
**Gap:** there is NO preemptive GPU scheduler; continuous build (`--loop`) was DELIBERATELY DISABLED
because it thrashed the 6GB card. This is how to safely turn "build all the time" back on.
**Build:** the card becomes a **leasable resource**.
- **The pass = a lease** that EXTENDS the control plane's existing lease/nonce/staleness primitive
  (the same one guarding build-task ownership today). The build holds it; an interactive agent
  **preempts** and acquires it (unload the build model via `keep_alive=0` to free VRAM); returns it
  on done.
- **The sentinel = heartbeat + TTL + idle-reclaim** (the safety net, so you never depend on an agent
  remembering to hand it back). If the holder goes quiet/dies, the lease **auto-reclaims**.
- **Duration = idle/session-state, NOT a fixed timeout.** A **bounded-task** agent releases the pass on
  completion (done is knowable). An **interactive session** is reclaimed only after interactive demand
  has been quiet for N minutes — so a 15-min conversation is honored and a 30-sec reply isn't
  over-held, WITHOUT asking the agent to predict the operator (which it can't and shouldn't).
- **Granularity:** yield BETWEEN build units (an ollama generation is atomic per call), not mid-token.
**Reuse:** the control-plane lease primitive, the VRAM sensor in `select_frontdoor_model`, `keep_alive`
control (`chief_llm` / `protected_generate._frontdoor_keep_alive`), the polish-loop control plane.
Pairs with `[[reference_fleet_model_tiering]]` (interactive=fit-card / async=spill-OK).

## Component 3 — Ledger-Source Self-Healing (3-layer enforcement)
Per the ledger doctrine: (1) test-time gate (BUILT — packet contract test); (2) runtime guard
(auto-pull from the ledger when a builder lacks provenance / sources wrong, flag + file a gap, fail
honest if it can't ground); (3) self-repair loop (a recurring drift receipt → build request "rewrite
builder X to source from the ledger + remove the wrong path" → Guardian-gated factory → lands →
**gap auto-closes only when the guard goes silent for X**).
**Reuse:** `context_source.facts_have_ledger_provenance` + `build_ledger_context_packet`, the packet
builder registry, the self-improvement loop + polish-loop factory.

## Component 4 — Harness-First Diagnosis (the self-healing reflex)
Per the diagnosis doctrine: when self_monitor recognizes a model going haywire, run the ordered
cascade — **harness → right-model-called/fits → deployment → fix LAST** — recording each layer's
verdict, and only file the root-cause build request after the first three are cleared.
**Reuse:** `self_monitor` / the self-improvement loop's diagnosis step.

## Component 5 — Build Lifecycle Governance (provenance + quality grade + anti-amnesia)
**The question:** how does the system know it (or Codex/operator) built a thing, grade whether it's
cancer / shit / almost-works / works-great, and never forget it, never rebuild it, never fail to USE
it when it should?
**Cancer firewall (real + demonstrated):** nothing bad lands autonomously — build agents are ISOLATED
(worktree, own branch, can't touch prod), the factory is Guardian-gated + the operator approves every
build (BUILDOK), and the clean-room GREEN-GATE proves it from committed state before anything reaches
main. Demonstrated 2026-06-30: the green-gate caught 316 clean-room failures and BLOCKED the promotion.
A runaway can propose garbage but cannot LAND it.
**Build:**
- **Provenance — one registry.** Every build, by ANY builder (autonomous factory, Codex, operator),
  logged ONCE in the ledger (who/when/why/what-changed). Today the factory logs its own builds
  (control-plane receipts) but Codex/operator-driven builds aren't uniformly in one place, and git
  author doesn't distinguish them. Make the ledger the canonical build registry.
- **Quality grade.** One grade per logged build, derived from the gates that already exist — tests +
  the proof harness (candidate EVIDENCE, not self-report) + green-gate + Gemini audit + per-agent
  sanity. cancer/shit/almost/great becomes a recorded score, not a vibe.
- **Anti-amnesia = the same 3-layer enforcement.** The registry knows it's built (can't be rebuilt —
  reuse-first becomes structural); a runtime guard detects a built capability that SHOULD be used but
  isn't and routes to it; the self-repair loop fixes the wiring. This is the operator's "that thing
  never can not be used when it should" — the activation register made ENFORCED, not just tracked.
**Reuse:** polish-loop control plane + receipts, the proof harness (`submit_candidate_evidence` /
`record_failure`), green-gate, build-agent isolation, the activation register, gap-state dedup.

---

## How it hangs together
The **router** knows what it *can* run; the **GPU arbiter** knows *when* to run it; the **self-healing
+ harness-first diagnosis** keep it *correct and honest* and repair the cause when it drifts; the
**ledger doctrine** keeps every one of them grounded in the one source of truth. One layer:
*resource-aware, self-healing, self-explaining model orchestration.*

## Build order (smallest reviewable, all DEFERRED)
1. GPU arbiter lease + idle-reclaim (extend the control-plane lease) — unblocks safe continuous build.
2. Capability/availability router (unify the scattered signals + always-explain).
3. Runtime ledger-provenance guard (Component 3, layer 2).
4. Self-repair loop wiring (Component 3, layer 3) + harness-first diagnosis order (Component 4).
Each step: TDD, Guardian-gated where it rewrites code or touches the live card, never-silent, and it
must leave a visible reason for every route/preempt/repair.
