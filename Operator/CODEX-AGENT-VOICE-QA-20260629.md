# Codex fix packet — agent voice/intent QA after the model retiering (2026-06-29)

**Owner:** Codex. **Reviewer:** Opus + operator live-check. **Branch:** `codex/stress-fixes`.
**Repo root:** `/home/openclaw` (WSL `Ubuntu-E`).

## Context (what's already GOOD — do not regress)
Today's model retiering landed (commits `971235eb` chief_llm + `6131ad17` polish; un-track `a3211aab`).
All agents now answer through the brain on **qwen3:8b** (interactive, fits the 6GB card) instead of the
old gemma swap-death lane that produced "model path returned no usable answer" stubs. A serial brain
probe (`maestro_cassandra_responder.answer_frontdoor_chat(q, agent=X)`, qwen3:8b warm) confirms:
- **Maestro** — TIGHT. Conversational status read, grounded, good voice. (Minor: a touch vague — "some
  invoices… next one's due soon" with no specifics. Low priority.)
- **Chief** — TIGHT. Specific + actionable (named the real PO, Coupa route, Hilton view). Good procedural
  voice. (Minor: assumed the Hilton invoice for a generically-phrased question. Low priority.)
- **Cassandra** — grounded + warm, BUT two real issues (below).

**Full roster = 6 agents:** maestro, **hermes**, chief, cassandra (a.k.a. **Clara Reid** — internal
name Cassandra, client-/outsider-facing name Clara Reid; same agent, tone down to Clara Reid when she
talks to anyone outside the inner circle), niles, guardian.

**Hermes (6th agent) — TIGHT, no fix needed, different path.** Hermes does NOT go through
`answer_frontdoor_chat`; he runs on his **sidecar gateway** (`sidecars/hermes/`, model `qwen3:4b` via
`config.yaml`). Operator confirmed live today that his answer was the best he's gotten. Left as-is
(operator likes the qwen3:4b output). Not part of the brain-probe set below; included here for
completeness so all 6 are accounted for.

These answer well; the goal is to fix the issues below WITHOUT flattening the voice that now works.

## Repro for everything here
```bash
cd /home/openclaw; source .chief.env
export OPENCLAW_FRONTDOOR_MODEL_PROFILE=1 OPENCLAW_FRONTDOOR_REPLY_TIMEOUT=44 \
  OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST=qwen3:8b-q4_K_M OPENCLAW_FRONTDOOR_NUM_CTX=1024 \
  OPENCLAW_FRONTDOOR_NUM_GPU=999 OPENCLAW_FRONTDOOR_KEEP_ALIVE=10m OPENCLAW_CONTINUITY_CAPSULE=1
# then: maestro_cassandra_responder.answer_frontdoor_chat(<question>, agent=<agent>)
```
Verify each fix BOTH via this brain probe AND (where the agent has its own transport) note that the
real listener path should behave the same.

---

## P0 — GUARDIAN can't answer advisory safety questions (misrouted to staging)
**Probe:** `agent="guardian"`, Q: *"Before I send a payment to a brand-new vendor, what should I check first?"*
**Got:** `status=ROUTE_TO_STAGING`, `intent_class='send_reply_email_action'`, `plain_summary=''` (NO ANSWER).
The intent gate (`send_reply_action_intent_routes_to_staging`, `gmail_metadata_queries_route_to_staging`)
fired on the words "send/payment/vendor" and routed an **advisory question** to staging instead of
answering it. The safety agent literally cannot answer a safety question that contains "send".

**Fix:** the intent classifier must distinguish ADVISORY/INTERROGATIVE intent ("what should I check",
"is it safe to…", "should I…", "how do I…") from ACTION intent ("send X", "pay Y", "reply to Z"). An
advisory/question framing — especially TO Guardian, whose whole job is safety advice — should route to
a brained answer, not staging. Only an actual imperative send/pay/reply command should hit staging.
Look at the intent classifier in `maestro_cassandra_responder.py` (the `_is_*_intent` / intent_class
logic around `send_reply_email_action` + `intent_gate_before_handle`). Add an advisory-question guard
BEFORE the send-action gate. Keep real send commands gated.
**Acceptance:** the Guardian probe above returns a real, brained safety checklist (verify bank details
out-of-band, confirm vendor identity, watch for invoice-redirect fraud, etc.) with status `ANSWER_READY`;
an actual "send a $500 payment to X now" still routes to staging.

## P1 — CASSANDRA (a.k.a. Clara Reid) assumes instead of confirming + recites a stale relative date
(Same agent in both personas — Cassandra internally, Clara Reid when facing clients/outsiders. Both
fixes below apply regardless of which name/tone is active.)
**Probe:** `agent="cassandra"`, Q: *"I just landed a $2000 gig next month. What should I be tracking…?"*
**Got:** *"…Keep an eye on that $2000 check from Coupa, it's due on July 1st… next Friday is June 26th…"*
Two problems:
1. **Confirm-don't-assume (operator directive 2026-06):** she silently EQUATED the NEW $2000 gig (next
   month) with the EXISTING $2000 Coupa receivable (due Jul 1). They may be different money. Per the
   operator's "if I get paid before I play a gig, confirm the assumption" rule, she should flag the
   ambiguity ("is this the same $2000 as the Coupa receivable, or new?") rather than merge them.
2. **Stale relative-date recital:** she stated *"next Friday is June 26th"* — today is **June 29th**, so
   that's in the PAST. It's bleeding the operator-truth fact `"In the 2026-06-19 evening correction,
   'next Friday' means 2026-06-26."` A point-in-time correction is being recited as if current.

**Fix:**
- (a) Add a confirm-don't-assume nudge when a NEW money/gig event could correspond to an EXISTING
  receivable: don't silently merge — surface the assumption for confirmation. (This likely lives in the
  Cassandra packet/persona instruction or a finance-grounding step.)
- (b) Stale-dated relative facts: an operator-truth fact that pins a relative date ("next Friday means
  2026-06-26") must NOT be surfaced once that date is in the past. Either drop/expire it in the packet
  builder (`maestro_context_packet.py` truth-fact selection) when its referenced date < today, or
  instruct the model never to state a relative-date correction as current.
**Acceptance:** the probe answer no longer asserts a past date as upcoming, and when a new gig amount
matches an existing receivable it asks to confirm rather than merging silently.

## P2 — NILES is generic/vague (no grounded specifics, personality not showing)
**Probe:** `agent="niles"`, Q: *"Quick vibe check — how do I make my live set feel more alive?"*
**Got:** *"Keep the energy tight, let the crowd breathe with you, and don't forget to let the music do
the talking — that's where the magic happens."*
Pleasant and on-voice but **bland-inspirational** — could be said to anyone, references none of the
operator's actual music/set/gig context, and shows none of Niles's character (he's meant to be the most
playful agent when the system is healthy, per the humor-as-health-signal rule).

**Fix:** ground Niles's packet in his actual domain context (current set/gigs/production state from his
read-models) so the advice is specific, and let his personality land when healthy (a light, characterful
touch — not a comedian, but distinctly Niles). Check whether Niles even gets a domain packet on the
front-door path (he may be getting a generic packet). Compare to how Cassandra/Chief get grounded facts.
**Acceptance:** Niles's answer references something real (a specific song/transition/gig) and reads as
Niles, not a generic motivational quote.

---

---

## VOICE-AUDIO (Kokoro TTS) — each agent needs its own spoken voice

The per-agent Kokoro voice MAP already exists and is correct — `agent_kokoro_voice.py`
`AGENT_KOKORO_VOICES` + `voice_for_agent(agent)`. All six render OK (verified by synth):
| agent | kokoro voice | status |
|---|---|---|
| maestro | am_michael | ✅ heard (good) |
| cassandra / Clara Reid | af_heart | ✅ heard (good) — **deepest-developed voice path** (`cassandra_voice.py`), the reference, don't flatten |
| chief | bm_george | renders OK but **never heard** — no send path |
| guardian | am_onyx | renders OK but **never heard** — no send path |
| niles | am_puck | renders OK but **never heard** — no send path |
| hermes | am_echo | renders OK but **never heard** — no send path |

### VOICE-P0 — Chief / Niles / Guardian / Hermes have NO audio send path
Only `maestro_voice.py` and `cassandra_voice.py` actually `synth_kokoro_wav(...)` + send audio to
Telegram (each correctly uses `voice_for_agent(<self>)`). There is no `chief_voice.py` /
`niles_voice.py` / `guardian_voice.py` / `hermes_voice.py` and nothing else synthesizes for them —
so those four are text-only. That's exactly why the operator has heard only Maestro + Cassandra.
**Fix:** generalize into ONE agent-voice sender that takes the agent, calls
`agent_kokoro_voice.voice_for_agent(agent)`, synthesizes, and delivers the audio to THAT agent's
Telegram lane — then wire all six agents' response delivery through it (Maestro/Cassandra keep their
current voices). Reuse the existing `maestro_voice.py` / `cassandra_voice.py` (314-line, richest)
pattern; do not hardcode a voice per file.
**Acceptance:** sending a reply as each of chief/niles/guardian/hermes produces an audio message in
that agent's lane in its mapped voice (bm_george / am_puck / am_onyx / am_echo).

### VOICE-P1 — Maestro's voice (am_michael) leaks onto Cassandra's lane
`master_voice.sh` hardcodes `VOICE="${KOKORO_VOICE:-am_michael}"` — it defaults to the MAESTRO voice
unless `KOKORO_VOICE` is explicitly set. It's the Maestro-channel sender (called by
`autonomous_self_check.py`, `operator_surface_guard.py`, `self_improvement_request.py`,
`hermes_observer.py`). Any Cassandra-authored (or other-agent) message delivered through this shell
path speaks in am_michael → the operator's reported "Maestro's voice on Cassandra's lane."
**Fix:** thread the agent → `voice_for_agent(agent)` into EVERY send path; `master_voice.sh` must take
the agent/voice explicitly (or the caller must set `KOKORO_VOICE`) and must NOT silently default to
am_michael for non-Maestro content. Cassandra delivery must go through `cassandra_voice.py` (af_heart),
never the Maestro shell sender. The generalized sender from VOICE-P0 should make this structural.
**Acceptance:** a Cassandra reply is never spoken in am_michael; each agent's lane always uses its own
mapped voice even when the message originates from a self-check/observer path.

### VOICE — note on "fits the character"
The voices are assigned + unique but the operator may want to re-pick any that don't FIT (e.g. if
Guardian should sound graver or Niles more playful). That's a one-line change in `AGENT_KOKORO_VOICES`
— leave the assignments operator-tunable; the wiring above is what's actually broken. Cassandra/Clara
Reid has the deepest communication spec — keep her as the gold standard for how a voice should land.

## FOLLOW-UP after Opus verification (2026-06-29, post-commits ecf0e4fa/b4bdf0dc/ca0e1dc4)
Good work — voice sender (agent_voice_sender.py), master_voice fix, Guardian routing repair,
`_is_stale_relative_date_truth`, and the anti-bleed truth filter all landed; 81/82 of the relevant
suite is green. TWO things to close:

1. **RED TEST left behind:** `tests/test_maestro_brain_packet.py::test_maestro_context_packet_uses_operator_truth_and_read_models`
   fails — it asserts the OLD truth content is present, but the new stale-date/relevance dropping
   removes it. You updated test_agent_voice_qa_regressions.py + test_maestro_capability_classifier.py
   but missed this one. Resolve the red.
2. **BUT confirm it's a stale test, not over-drop — this is the real check:** the failing test's
   question is *"What should I know about invoices and next Friday?"* — a FINANCE question — yet the
   invoice/finance truth facts got dropped. The relevance filter must NOT drop a topic's facts when the
   operator is ASKING about that topic. Add/keep a test proving: a finance question KEEPS finance truth
   (Capital Hilton / $2000 / receivable), and a NON-finance question drops it; a stale-dated CLAUSE is
   suppressed without nuking a whole multi-clause fact that also carries still-valid info. If the
   current logic drops finance facts for a finance question, that's a bug — tighten it so "asking about
   X" elevates X's facts (overlap/agent_relevant should win over the drop).

## Notes for Codex
- Telemetry gap (not a blocker): the probe's `machine_proof` returned `model=None` / backend strings
  like `ANSWER_READY` — the per-agent brain result doesn't surface the resolved model id. Ground truth
  for "did the model run" is `/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl`. Optional: thread the
  resolved model id into the result's machine_proof.
- Don't flatten the working voices (Maestro/Chief/Cassandra are tight) while fixing intent/grounding.
- Re-run the repro probe for each fixed agent; paste before/after into
  `Operator/CODEX-AGENT-VOICE-QA-RESULTS.md`. Respect Guardian gates; don't self-approve prod-state writes.
