# Codex follow-up — Skills S3: route the attached skill THROUGH the brain (not a deterministic dump)

**Owner:** Codex. **Reviewer:** Opus + operator live-check. **Branch:** `codex/stress-fixes`.
**Repo root:** `/home/openclaw` (WSL `Ubuntu-E`). Builds on the Skills slice
(`Operator/CODEX-SKILLS-SLICE-MUSIC-LAW.md`, S1/S2/S4 verified, registry seeded with
`music_law_advisory`).

## The gap (found in the live audit)
S3's plumbing is real — a music-law question DOES select the skill and attach its content to the
packet. But the live answer is a **deterministic readback dump**, not a brained answer:

- Probe: "How do publishing splits work on a 50/50 co-write with a topliner?"
- Got: `"chief_musiclaw_brain fundamentals: MUSIC INDUSTRY LEGAL FUNDAMENTALS: 1; MASTER vs
  COMPOSITION RIGHTS - ..."` — `selected_model_backend = NONE_DETERMINISTIC`.

So: no `LOCAL_OLLAMA` (the brain never ran), no answer to the actual question (it dumped generic
fundamentals), a machine-y `chief_musiclaw_brain fundamentals:` prefix, and **no real-lawyer flag**.
**This is the same class as the original Bug B** — a deterministic readback path wins over the brain,
so the attached skill is recited, not used. S3's acceptance ("the brain answers *grounded in* the
musiclaw knowledge") is NOT met live.

## Fix
The skill content must be **packet context the brain answers FROM**, never a delivered string.
1. Trace where a music-law / skill-matched question gets rendered: it is currently producing a
   deterministic readback (likely the `chief_musiclaw_brain.handle()` output or a
   skill-content-dump) BEFORE/INSTEAD OF the brain. Find that branch.
2. Route skill-matched conversational questions through the brain
   (`_answer_with_maestro_brain` → `protected_generate`, front-door profile), with the skill's
   `tiers.simple|rich` body + the `chief_musiclaw_brain` knowledge injected into the packet as
   facts/context — NOT emitted as the answer. The LM writes the actual, question-specific reply.
3. Preserve the **real-lawyer flag**: the skill (and `chief_musiclaw_brain._ensure_musiclaw_safety`)
   require flagging when a real entertainment lawyer is needed — that must survive into the brained
   answer (inject it as a required-instruction the LM includes when stakes are real).
4. Keep the deterministic-by-design routes deterministic (calendar/send/workflow). Only the
   skill-backed *conversational knowledge* questions should brain.

## Hard constraints
- Authority unchanged: music-law stays **advisory_only**, no legal action / sends / signing; the
  skill grants no authority. Grounding intact (no invented law). Local model first. Per-agent
  (the skill is owned by chief, reachable via the front-door) — not a Maestro snowglobe.

## Non-snowglobe live verification (the acceptance)
Restart `openclaw-request-response`, inject the same probe through the REAL pipeline, and show:
- `selected_model_backend = LOCAL_OLLAMA` and `protected_generate_audit.jsonl` shows
  `model_call_performed=True` for it (the brain actually ran).
- The answer is **conversational and specific to the question** (addresses the 50/50 co-write /
  topliner split), grounded in the musiclaw knowledge, **with the real-lawyer flag** — NOT a
  `chief_musiclaw_brain fundamentals:` dump.
- A non-music question still routes normally (no regression); calendar/send still deterministic.
- Paste the before/after live reply + receipt into `Operator/CODEX-SKILLS-S3-FOLLOWUP-RESULTS.md`.

## Output protocol
CLI plain-English summary + machine results to `Operator/CODEX-SKILLS-S3-FOLLOWUP-RESULTS.md`
(per item: status, files, commit shas, tests, live-verify output). Commit small on
`codex/stress-fixes`; don't push; respect Guardian gates (don't self-approve prod-state writes).
