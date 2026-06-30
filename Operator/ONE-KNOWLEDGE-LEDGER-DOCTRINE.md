# Doctrine: ONE Knowledge Source of Truth

Status: **CANONICAL DOCTRINE** (operator standing directive, 2026-06-30). Every actor — the agents,
the operator, Claude/Opus, Gemini, Codex — must read this and reason accordingly. Point new Codex /
Gemini tasks at this file. (Should also be enshrined in `OPENCLAW_RUNTIME.md`, the source of truth.)

## The invariant
There is exactly **ONE knowledge source of truth: the robust SQLite ledger**
(`/home/openclaw/.openclaw/business_ops/ledger.sqlite`).

1. **It holds everything the system "knows."** What is true, what each thing *is*, and **what it knows
   it does NOT know** (the gaps / known-unknowns). The system must never divide "what's known / what's
   true" across multiple places. One place.
2. **It may be made of many parts, but it is treated as ONE.** It folds many underlying pieces (tables,
   former satellites, live operational stores) into a single unified knowledge view. No actor keeps a
   private fork of truth, and no one queries a side-store as if it were authoritative.
3. **It drives packet creation — enforced.** Every context-packet builder MUST pull from the ledger
   with `ledger_provenance` (source_of_truth = `business_ops_ledger`). The contract test
   (`tests/test_context_packet_ledger_contract.py` + `context_packet_builder_registry`) blocks any
   builder that doesn't. This enforcement is *why* the rule needs no explaining — the structure forbids
   the alternative.
4. **It should ground plugins/skills too.** Plugins/skills that act on "what the system knows" derive
   their grounding from the ledger, not a parallel source.
5. **Gaps flow back IN.** Anything found on disk / in the world that the ledger doesn't yet know feeds
   back into the ledger (auto-refresh keeps it from going stale). The one place stays the one place.

## What this forbids
- Standing up a second store of truth, or letting a satellite/read-model/cache become the de-facto
  authority.
- A packet, plugin, agent, or CLI sourcing "what's true" from anywhere but the ledger.
- Renaming/restructuring that updates a source file but NOT the live ledger (a rename must update the
  LIVE ledger via BOTH ingest paths — see the canonical-ledger ingest rule).

## Enforcement — three layers (the reason no one has to be told)
1. **Test-time gate (BUILT).** The packet contract test fails any builder that doesn't pull from the
   ledger with provenance — new drift can't *land*.
2. **Runtime self-heal guard (to build).** At the packet-build chokepoint, if a registered
   knowledge-builder returns facts without ledger provenance (or from the wrong place), the guard
   auto-pulls the canonical ledger context for that same question/agent and grafts it in — a live
   "didn't pull / pulled wrong" becomes "now pulls right." It self-heals AND flags (logs a drift
   receipt + files a gap); never silently masks; if the ledger can't ground it, it fails HONEST.
3. **Self-repair loop (to wire — reuses the existing self-improvement loop + Guardian-gated factory).**
   A *recurring* drift receipt for builder X becomes a build request: "rewrite X to source from the
   ledger directly AND remove the wrong-source path." → PROPOSED → Guardian BUILDOK → factory builds +
   tests → lands. Old wrong-source code is kicked, right code goes in, so NEXT time X pulls natively
   from the right place. The gap **auto-closes only when the runtime guard goes silent for X**
   (confirmed it now sources correctly on its own) — i.e. the wrong-place-error + right-place-correction
   stops recurring. Code rewrites stay **Guardian + operator-gated** — never an ungated live auto-edit.

Net: test-gate stops new drift, runtime guard self-corrects live drift, self-repair loop fixes the
cause and verifies it stopped. The one source of truth becomes structurally unavoidable.

## Why (operator's words)
"The system should not be able to divide up where what it knows is what and what it knows it doesn't
know anywhere but in one thing. That thing may be made of lots of things, but the system has to think of
it as one thing, and the agents and anybody — including me, you, Gemini, Codex — has to be able to use
it correctly and think of it correctly without me explaining what I for real will not be able to
articulate / I should not have to explain it."

## For any Codex/Gemini task touching knowledge, packets, plugins, or naming
Treat the ledger as the single source of truth. If your work would create or consume "what the system
knows," route it through the ledger. If you find a second store of truth or a packet/plugin bypassing
the ledger, FLAG it as a doctrine violation. Naming work must make the one-ledger model self-evident.
