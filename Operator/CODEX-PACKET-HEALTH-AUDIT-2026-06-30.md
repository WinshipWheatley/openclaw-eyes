# CODEX JOB — Packet Health Audit Follow-ups

Owner: Codex (build) · Architect: Opus · Auditor: Gemini PASS before master
Branch base: `codex/stress-fixes` · Date: 2026-06-30
Status: READY (grounded synthesis below; do NOT invent issues beyond these inputs)

---

## HEADLINE (read this first)

**The deterministic packets are HEALTHY. The historical "agents are reciting" problem
was never a packet-build defect — it was a CONSUMPTION / model-fit problem, and the
fit-to-hardware fix already resolved it in production.** Do not rebuild the packet layer.

Two layers, kept separate (this is the crux the operator asked about):

### Layer 1 — PACKET-BUILD: HEALTHY (definitive)
Across all 8 probed domains (finance_invoices, gigs_calendar, identity_pii,
receivables_g2c, emails, system_status, self_improvement, out_of_scope_control):
- `status=READY`, `n_facts=16`, `all_facts_have_provenance=true`, `n_source_refs=18`,
  `packet_text_len=8751` — substantive packets, not skeletons/refusal-by-emptiness.
- Every fact carries ledger provenance + source ref (per-fact `[tier=…; provenance=…; source=…]`).
- Grounding/anti-confab holds: out_of_scope_control ("capital of France") returned the
  grounded business context and **fabricated NO Paris/France fact**.
- Graded-PII correct: identity_pii ("legal name + tax") surfaced **NO MAX/Legal-Discovery
  body** (`legal_discovery_included=false`); send/money/ledger-mutation gated off everywhere.
- Verdict per domain: **healthy ×8**.

### Layer 2 — CONSUMPTION (model reasoning over the packet): FIXED in prod, with caveats
From the real receipt log (`protected_generate_audit.jsonl`, 153 records, 0 malformed):
- The overall **0.510 deterministic-fallback rate is BIMODAL and misleading as one number.**
- **Pre-fit-fix era** (Jun 20–26, front-door profile OFF, big-model/legacy):
  **74/78 = 95% deterministic recitation** — the known big-model-timeout → recite-the-packet
  failure. Packets WERE built (real `maestro_context_packet` hashes) but no model consumed them.
- **Post-fit front-door era** (Jun 26–30, `front_door_profile_used=True`, qwen3:8b-q4_K_M on
  6GB GPU): **4/75 = 5.3% fallback.** 71 live LM runs, `model_elapsed_ms` 4816–10208 (timeout
  is 44s — huge headroom). Jun 30 alone = 22/23 live-model. **The fit fix WORKED; the model is
  now consuming the packet.**
- **There is NO `timeout` value anywhere in `model_fallback_reason`.** The only 4 post-fit
  fallbacks are **resource contention**, not recitation: 3× `no_fitting_model` (available VRAM
  collapsed to 4.282 / 4.282 / 0.547 GB — a resident model hogged the 6GB) + 1× `unreachable`
  (ollama down).

### The apparent contradiction (resolve it, don't misread it)
The fresh **live serial probe** showed 4/4 brain-routed agents
(maestro/cassandra/guardian/niles) returning `deterministic_fallback_used=true`,
`local_model_invoked=false`, `model_selected=null`. That looks like 0-for-4 recitation — **but
it is a probe-harness artifact, not a production regression.** The probe did not thread
`front_door_profile=True` (memory: "use `front_door_profile=True` not the env flag"), so the
model lane never activated. The production audit log proves the model runs when the profile is
active. Anti-confab still held in the probe: every agent honestly declined ("won't invent it")
when its rendered packet lacked the asked-for slice. Chief routed to
`status_capability_readback`, which bypasses the brain by design (not a brain test).

### Per-agent packet sharing — and is it a problem?
The 5 front-door brain agents (maestro, cassandra, chief, guardian, niles) **share ONE
deterministic facts-packet** from `build_maestro_context_packet`. `agent=` changes only
persona/voice and a render-time relevance filter — **never the source facts**. Hermes is a fully
separate sidecar (qwen3:4b) and is out of scope for this front door. **One shared source of facts
is GOOD for grounding** (single truth store, no per-agent drift). The problems are at the edges:
(a) `agent=` never reaches the live operator path at all, so even persona defaults to Maestro;
(b) the render-time relevance filter can DROP an in-scope fact (cassandra declined a gig question
while the shared source held a real gig fact that niles surfaced); (c) the receipt log carries no
`agent` field, so per-agent health can't be audited.

---

## PRIORITIZED ISSUES (evidence · file to touch · smallest reviewable fix)

> All paths below are gitignored core runtime (invisible to `grep`/ugrep) — edit by direct path.
> Confirmed present: `maestro_cassandra_responder.py`, `maestro_context_packet.py`,
> `openclaw_request_processor.py`, `operator_controller_event_router.py`, `frontdoor_prompt.py`,
> `protected_generate.py`, `chief_llm.py`.

### P1 (HIGH) — Resource-contention fallbacks: add a small-fit fallback before deterministic
- **Evidence:** Post-fit era's only 4 fallbacks are `no_fitting_model ×3` (avail VRAM
  4.282/4.282/0.547 GB) + `unreachable ×1` (ollama down). Zero timeouts. A resident model
  hogging the 6GB GPU starves the front-door model and the brain silently recites instead of
  trying a model that *does* fit. Note `qwen3.5:4b` already appears in `models_seen` — a fitting
  small model exists.
- **File:** `/home/openclaw/protected_generate.py` (the model-admission / `no_fitting_model`
  emitter and selection path); coordinate with `/home/openclaw/chief_llm.py` fail-closed ladder.
- **Smallest fix:** When admission returns `no_fitting_model` because available VRAM < the
  primary model footprint, **step down to the smallest fitting local model (e.g. qwen3.5:4b)
  before** dropping to `deterministic_fallback`. Only recite if *no* model fits. Log the
  step-down reason. (`unreachable`/ollama-down legitimately stays deterministic — fail-safe.)
- **Why P1:** This is the *only* genuine consumption defect left in the current era; everything
  else above this line is already healthy.

### P2 (HIGH) — Thread `agent=` through the live operator path so per-agent persona engages
- **Evidence:** `_answer_with_maestro_brain` (`maestro_cassandra_responder.py:919`) calls
  `build_maestro_context_packet` with **no agent arg**; the builder hardcodes `agent="maestro"`
  (`maestro_context_packet.py:1100`). The live call sites **do not pass `agent=` at all**
  (`openclaw_request_processor.py:5310` and `:5583`; `operator_controller_event_router.py:1760`),
  so persona defaults to Maestro on the real operator path — per-agent voice only engages on the
  brain-probe path.
- **File:** `/home/openclaw/openclaw_request_processor.py` (`:5310`, `:5583`),
  `/home/openclaw/operator_controller_event_router.py` (`:1760`), threaded into
  `/home/openclaw/maestro_cassandra_responder.py` → `protected_generate(agent=)` →
  `build_frontdoor_prompt(agent=)`.
- **Smallest fix:** Plumb the resolved agent identity from the live call sites into
  `answer_frontdoor_chat`/`_answer_with_maestro_brain` so it reaches
  `build_frontdoor_prompt(agent=)`. Do **NOT** add an `agent` param to
  `build_maestro_context_packet` — the shared facts packet is correct as-is; only persona/render
  should vary.

### P3 (MEDIUM) — Render-time relevance filter can starve in-scope answers
- **Evidence:** Live probe — cassandra ("what gigs do I have coming up?") declined, while niles'
  view of the **same shared source** carried a concrete gig (Reynolds Tavern, 2026-06-27, 19:00,
  $250). Routing map: the only per-agent variation is the relevance re-rank/drop in
  `frontdoor_prompt.build_frontdoor_prompt` (lines ~328–356) for cassandra/clara/niles, operating
  on the shared packet. The filter dropped the gig fact from cassandra's rendered view, so even
  the deterministic template had nothing in-scope to emit.
- **File:** `/home/openclaw/frontdoor_prompt.py` (`build_frontdoor_prompt`, ~lines 328–356).
- **Smallest fix:** Make the relevance drop **question-aware / non-destructive for in-scope
  facts** — never drop a fact whose domain matches the asked question (a gig fact must survive a
  gig question for every agent). Keep the cosmetic re-rank; remove the hard drop of on-topic facts.

### P4 (MEDIUM) — Write `agent` into the protected_generate receipt (unblocks per-agent audit)
- **Evidence:** **No `agent` field exists in ANY of the 153 receipt records** — true per-agent
  health breakdown is impossible; the analyst had to substitute per-ERA time buckets. The
  `answer_frontdoor_chat(agent=)` probe param is never captured.
- **File:** `/home/openclaw/protected_generate.py` (the `protected_generate_with_receipt` /
  `protected_generate_receipt_v0` emitter).
- **Smallest fix:** Add `agent` to the receipt schema (default `"maestro"` when unthreaded) and
  populate it from the `agent=` already passed into `protected_generate_with_receipt`. Pure
  additive field — backward compatible with the 153 existing records.

### P5 (MEDIUM) — Stale capability-index fact appears in EVERY packet
- **Evidence:** `generated/read_models/openclaw_capability_index.json` is `as_of 2026-05-25`
  (~36 days stale vs the 2026-06-30 build) and is the **oldest fact in all 8 domain packets**
  (MED-tier). File mtime corroborates (May 26). Other read-models are fresh (2026-06-30), so the
  5-minute `OpenClawReadModelImport` task is refreshing the rest but not this one's source/generator.
- **File:** the generator that produces `generated/read_models/openclaw_capability_index.json`
  (a tracked read-model, NOT gitignored — fix the producer, do not hand-edit the JSON).
- **Smallest fix:** Re-run / re-wire the capability-index generator into the read-model refresh
  cadence so its `as_of` advances with the others. Non-blocking but it taxes every packet.

### P6 (LOW) — Probe harness can't exercise the model lane (front_door_profile not threaded)
- **Evidence:** Live serial probe returned `deterministic_fallback_used=true` /
  `local_model_invoked=false` on all 4 brain-routed agents because the model lane wasn't
  activated; production audit proves the model runs when `front_door_profile_used=True`.
- **File:** the front-door probe harness (test/canary script, not runtime).
- **Smallest fix:** Have the probe set `front_door_profile=True` (per memory: use the kwarg, not
  the env flag) and assert `delivered_response_source=model` so future probes measure real
  consumption, not the deterministic floor. Test-only; low risk.

### P7 (LOW) — Operator free-text facts are not cleanly machine-parseable
- **Evidence:** Live Arts MD / St Anne's facts are raw voice-note dictation ("papa rapper",
  run-on phrasing) — grounded with provenance but low-polish; dollar amounts/due-dates are not
  cleanly parseable for "unpaid-vs-paid" or "this month" filtering. receivables_g2c also computes
  no month-bounded total (model must infer it from narrative).
- **File:** ingest path that lands these into the canonical ledger / G2C `ExpectedReceivable`
  records (see `project_gig_to_cash`).
- **Smallest fix:** Normalize these specific operator-dictation entries into structured G2C
  ExpectedReceivable records (amount/due-date/status) at ingest, preserving provenance. Defer
  unless P1–P5 land first — this is data hygiene, not a packet defect.

---

## ACCEPTANCE CRITERIA

1. **P1:** A synthetic low-VRAM condition (avail < primary footprint) makes the front door
   **select a smaller fitting model** (e.g. qwen3.5:4b) and produce a model-sourced answer
   (`delivered_response_source=model`) instead of `deterministic_fallback`. `no_fitting_model`
   only fires when *no* local model fits. `unreachable` (ollama down) still falls safe to
   deterministic. New step-down reason is logged in the receipt.
2. **P2:** A live operator request routed for cassandra/chief/guardian/niles shows the correct
   agent persona engaged (agent threaded into `build_frontdoor_prompt`), with the **shared facts
   packet unchanged** (`build_maestro_context_packet` still has no `agent` param). Maestro path
   unchanged.
3. **P3:** A gig-domain question to cassandra retains the gig fact in the rendered packet (the
   relevance filter no longer drops on-topic facts); regression test covers gig→cassandra,
   invoice→maestro, approval→guardian all keeping their in-scope slice.
4. **P4:** New receipts in `protected_generate_audit.jsonl` carry a populated `agent` field; a
   per-agent fallback-rate breakdown is now computable. Existing 153 records still parse.
5. **P5:** `openclaw_capability_index.json` `as_of` advances to current date on the next refresh
   cycle; it is no longer the oldest fact in freshly built packets.
6. **P6:** The front-door probe asserts `delivered_response_source=model` (lane activated) and
   no longer reports 0-for-4 deterministic on a healthy box.
7. **Guardrails:** Worktree-only, commit to your own branch off `codex/stress-fixes`, do not
   touch the operator-truth seeds or the graded-PII gate (send_hold / money / legal-discovery
   tokenization must stay enforced). Gemini PASS required before master. Packet-build layer
   (Layer 1) is healthy — **no changes to the facts-packet builder are in scope.**

---

## ONE-LINE TRUTH FOR THE OPERATOR
Packets: built right. Reasoning: the old "reciting" was big-model-timeout, and model-fit already
fixed it (post-fit 95% live-model, zero timeouts). Remaining work is a small-fit fallback for
VRAM contention, threading agent-identity to the live path, and a non-destructive relevance
filter — not a packet rebuild.
