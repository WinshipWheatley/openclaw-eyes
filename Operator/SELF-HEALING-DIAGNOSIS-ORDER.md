# Doctrine: Self-Healing Diagnosis Order (harness-first, fix-last)

Status: **CANONICAL DOCTRINE** (operator standing directive, 2026-06-30). The self-healing loop's
diagnosis step MUST follow this order. Point self-healing / model-reliability Codex tasks at this file.

## The rule
When the system notices a model (LOCAL or any) going haywire during build/deploy, it does NOT blame
the model. It self-assesses in this exact order, and prepares the fix LAST:

1. **Harness first** — is the scaffolding/framework around the model broken, not the model? Most
   "model failures" are harness artifacts (e.g. a `/tmp`-sqlite collision at schema-init that looks
   like a logic bug). READ THE ACTUAL ERROR before declaring a model/logic regression.
2. **Right model called + fits the box?** — verify the correct model/tier was actually invoked and
   fits the hardware. A big model "going fucko" is usually wrong-model-for-hardware (swap-death), not
   a bad model.
3. **Deployment-stage issues** — what broke in the deploy/activation itself (env on the right service,
   restart needed, wrong distro/path, etc.).
4. **THEN prepare the fix for the actual failure** — last, on purpose. Harness / model-selection /
   deployment are already ruled out, so the fix targets the REAL cause, not a symptom, and never
   "fixes" a model that was fine.

## Why
The fix is last so a broken harness can't mislead the repair. You only write the fix once you KNOW the
lower layers aren't lying to you. This is the antidote to "being disappointed by the harness being
shit." It is the systematic-debugging discipline (evidence at each component boundary; find WHERE it
breaks before fixing) made the self-healing loop's STANDING REFLEX.

## For self-healing / model-reliability Codex tasks
Implement the diagnosis step as this ordered cascade in the self-improvement loop: on a recognized
model-haywire signal, run harness → model-call/fit → deployment checks, recording the verdict at each
layer; only file the root-cause build request after the first three are cleared. Each layer's check
flags (never silently masks). Pairs with the ONE-KNOWLEDGE-LEDGER doctrine's 3-layer enforcement —
same self-improvement-loop + Guardian-gated factory.
