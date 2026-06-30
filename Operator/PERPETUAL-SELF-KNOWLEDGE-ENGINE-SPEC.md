# Spec (PARKED): Perpetual Self-Knowledge Engine

Status: **PARKED VISION** (operator-designed 2026-06-30; do NOT build until green-gate/promotion + GO).
The answer to "how does the system know — and KEEP knowing — everything that's been built, so the
operator never has to test whether it knows." This is the continuous, self-reinforcing, self-optimizing
upgrade of the one-time completeness sweep. Serves the north star ([[feedback_operator_trust_not_test]]):
when the system perpetually knows itself, the operator trusts-and-uses instead of test-and-checks.

Governing: `Operator/ONE-KNOWLEDGE-LEDGER-DOCTRINE.md` (the ledger is where all this metadata lands)
+ `Operator/SELF-HEALING-DIAGNOSIS-ORDER.md` + `Operator/RESOURCE-AWARE-MODEL-ORCHESTRATION-SPEC.md`
(the GPU arbiter the crawler yields to; the capability router; build-lifecycle governance).

**Reuse-first, never-silent, ground-truth-anchored** (enumerate the REAL artifacts, not the ledger's
self-report — you can't find unknown-unknowns by introspection).

## The loop (6 layers)
1. **Crumb crawler (always-on, LOCAL = $0, tireless).** Continuously walks ground truth — files, git
   objects/branches/worktrees, processes, crons, systemd units, DBs, ports — and drips metadata about
   every artifact into the ledger. Mostly CHEAP DETERMINISTIC enumeration (the bulk); the local LM is
   used SELECTIVELY for "what is this / enrich metadata" judgment. Yields the GPU to interactive agents
   (it IS the opportunistic background workload the arbiter manages).
2. **Gemini deep passes (periodic).** Bigger-brain sweeps reason over the crumbs to find structure +
   meaning the local model can't (purpose, relationships).
3. **Frontier hand-off + cross-verify.** The local crawler works the EDGES Gemini flagged, AND
   re-checks Gemini's findings against ground truth (Gemini is never trusted blind). Converge →
   confidence; diverge → a flag to investigate. = reinforcement.
4. **Self-governance / meta-optimization.** The engine tunes its OWN mechanics — crawl hot areas more,
   stable areas rarely, when to call Gemini, GPU allocation — driven by where new crumbs keep turning
   up. The self-improvement loop pointed at the EXPLORATION itself.
5. **Epistemic closure.** Metric = the UNKNOWN RATE (new untracked artifacts found per pass) trending
   to zero across EVERY enumeration angle. Held at zero long enough → residual unknown-unknown
   probability is negligible = "knows it knows." (Honest: ASYMPTOTIC, not absolute — negligible +
   self-monitored is the achievable, honest form of certainty.)
6. **Steady-state tiny quests.** Once closed, lightweight diffs catch anything new the instant it
   appears → nothing can be built without the system knowing fully. (Pairs with Build Lifecycle
   Governance: a new build registers; if it didn't, the next quest catches it.)

## Reuse anchors (assembling, not inventing)
Cross-repo scanner (the SQLite cross-repo index seed), the ledger (metadata store + the one source of
truth), AGY/Gemini (the explorer — already does ground-truth enumeration + ledger-gap capture), the
self-improvement loop + autonomous_self_check (self-governance), the GPU arbiter (yields the card), the
completeness-diff (ground-truth vs registry).

## Why it matters
This is the engine that makes "trust, don't test" TRUE. The system achieves AND maintains complete,
self-aware self-knowledge — so the operator never has to wonder "did I build something it forgot." It
just knows, forever.
