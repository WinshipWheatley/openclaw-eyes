# Codex punch-list — fixes from the audit of the fleet packet

**Owner:** Codex. **Reviewer:** Opus + operator live-check. **Branch:** `codex/stress-fixes`.
**Repo root:** `/home/openclaw` (WSL `Ubuntu-E`). These are the CONCERN-level fixes the audit found
on the prior packet (which is otherwise PASS: A/B/I live-verified, C live-recovered, F records-only).

## 0. HOW TO RUN (read first)
- Cross-repo aware (~134 repos via `system_catalog.sqlite3`); primary stack `/home/openclaw`.
  Don't edit `worktrees/*` or `sidecars/*` upstreams.
- Do **P1 → P2 → P3 → P4** in order. Each is **BUILD**: TDD (red→green) AND a non-snowglobe LIVE
  verification (a green unit test alone is NOT acceptance). Commit small on `codex/stress-fixes`.
  **Do NOT push.** Keep authority Guardian-gated; do NOT self-approve any prod-state mutation.
  **STOP-RULE SCOPE:** if a SPECIFIC step is Guardian-gated (e.g. a prod-state DB write), SKIP ONLY
  THAT STEP — emit the exact command, mark it `operator_pending` — and **CONTINUE with the remaining
  items.** Do NOT abandon the rest of the punch-list. (P1's `--confirm` ledger write is the ONLY
  operator-gated step; P2/P3/P4 are ungated code changes and MUST still be completed.)
- **Output:** (1) plain-English CLI summary; (2) machine-readable results to
  `Operator/CODEX-FLEET-PUNCHLIST-RESULTS.md` (per item: status, files, commit shas, tests pass/fail,
  the live verification output). State that path in the CLI summary.

## P1 — Rebuild the doctrine ledger so live stops reciting the wrong name (+ phantom-actor guard)
**Symptom:** the prior commit fixed `canonical_doctrine_facts.py` ("Clara Reed"→"Clara Reid", and
Clara modeled as Cassandra's register) but the **live materialized store was never rebuilt** —
`.openclaw/business_ops/ledger.sqlite` (`canonical_facts` + `fts_canonical_facts*`) still holds 6
stale "Clara Reed" rows, so the brain's roster answers still recite the wrong name.
**Fix:**
1. Rebuild the SD-4 / canonical-facts ledger row + FTS index from the corrected
   `canonical_doctrine_facts.py` (the reviewer pointed at `scripts/populate_real_ledger.py` — confirm
   that's the right rebuild path; it mutates `.openclaw/business_ops/ledger.sqlite`, a prod-state
   write, so if Guardian-gated, emit the command + mark operator-pending, do NOT self-approve).
2. Add the **doctrine-fact actor validator**: every actor named in a fact's `text`/`allowed_actors`
   must exist in `DEFAULT_AGENT_LANE_SEEDS` (+ the live `agent_lanes` table) or the fact is rejected
   at load/seed — so an LLM can never write a phantom actor (like "fin") into canonical truth again.
   TDD it.
**Live verify (non-snowglobe):** over the live ledger `canonical_facts`/`fts_canonical_facts*`,
`grep -ic "Clara Reed"` → **0** AND `grep -ic "fin ("` (the SD-4 `fin (finance/...)` residue) → **0**;
a live roster probe (inject "who are the agents?") returns "Clara Reid" and does NOT name "fin".
(Fin Option 1 is CONFIRMED — see the operator note below.)

**P1b — COMPLETENESS (found in audit after the operator ran the doctrine rebuild):** the doctrine
populator re-seeds ONLY the 3 doctrine sources; it does NOT cover **doc-ingested** facts (path:
`scripts/ingest_canonical_docs.py`). After the rebuild, `fin`=0 and SD-4="Clara Reid" ✅, BUT the
Cassandra **Machine Contract** fact `fact_4735dc85` (source `docs/operations/CASSANDRA_MACHINE_CONTRACT.md`,
section "Role") still reads "Clara Reed" in the live ledger (3 rows: canonical_facts + 2 FTS shadows),
even though the .md doc itself is already corrected. **Re-ingest it** via the doc-ingest path
(`python3 scripts/ingest_canonical_docs.py --db /home/openclaw/.openclaw/business_ops/ledger.sqlite
--source docs/operations/CASSANDRA_MACHINE_CONTRACT.md`) — but FIRST confirm the replace semantics:
the fact_id is content-hash-derived, so changed text yields a NEW fact_id; ensure the OLD
`fact_4735dc85` row + its FTS shadows are removed (no orphan), not just a new row added. This is a
prod-ledger write → operator-pending command, do NOT self-approve. **Verify:** live ledger
`grep -ic "Clara Reed"` over canonical_facts + fts → **0**.

## P2 — No-response watchdog: stop dropping silent NON-maestro agents
**Symptom:** `no_response_watchdog.py` correctly detects an inbox request with no `to_mac` response
after the timeout, but only `no_response_maestro` has a package profile —
`compile_self_improvement_package` raises for `no_response_<other>` (`self_improvement_request.py`
:289-291) → `route_to_chief` swallows it as `filed=False` (`hermes_observer.py`:181-184) → the loop
marks it "failed" silently. So a silent **Hermes** (the exact thing that started all this) is detected
then **dropped**.
**Fix:** add bounded package profiles for the non-maestro gap ids (`no_response_hermes`,
`no_response_cassandra`, `no_response_niles`, `no_response_chief`, `no_response_guardian`) so a
detected silence files a real PROPOSED + Guardian-gated fix request (reuse the existing maestro
profile shape; per-agent allowed_files/tests scoped to that agent's listener/path). Fail-closed,
never auto-approve.
**Live verify:** simulate a silent non-maestro request (an aged inbox envelope with no response) →
the watchdog FILES a PROPOSED+Guardian request for that agent (not dropped, not auto-approved).

## P3 — Image intake: the deferred "reprocess when vision returns" queue (the operator's explicit ask)
**Symptom:** E wires the safe part correctly (photo downloaded, **local Tesseract OCR only, no raw
image bytes to any model**), but: (a) there is **no deferred queue** — when Tesseract is missing/OCR
fails it just sends a generic error and drops the image; (b) it's **maestro-only**; (c) the test
uses a **mock** `ocr_fn`, so real Tesseract + `handle_photo` + the live bridge are unverified.
**Fix:**
1. Deferred path: when OCR is unavailable/empty, store the image ref + sha256 (reuse
   `operator_file_metadata_intake` pending markers) and reply "noted — I can't read it yet, I'll
   reprocess when vision's back," then a small drain worker (niles/chief-worker pattern) reprocesses
   pending markers once OCR/vision is available. Honest-defer, never silent-drop.
2. Make it per-agent (not a maestro snowglobe) where the other listeners accept photos.
3. Replace the mock-OCR unit test with a **real-Tesseract** test over a sample image fixture.
**Live verify:** inject/sent an image with OCR disabled → deferred reply + a pending marker that the
drain worker later resolves; with OCR enabled → the real extracted text reaches the brain.

## P4 — A/B latent fixes (per-agent contract + honest defaults)
From the A/B review (commit dba57c58), all non-blocking but real:
1. **Per-agent hardcode:** `_answer_status_capability_with_brain` hardcodes `agent='maestro'`
   (`maestro_cassandra_responder.py`:691) and its call site (:513) doesn't forward `agent`, while the
   freeform path threads `agent=agent` (:940). Forward the real `agent` param so the per-agent
   contract holds when the front-door is shared (don't snowglobe to Maestro).
2. **Honest default:** `_protected_generate_receipt_machine_proof` defaults `model_call_performed` to
   `True` on a missing key — change to default `False` so a non-`protected_generate` receipt shape
   can't fabricate a model claim.
3. **Regression-check** the out-of-scope behavior change: the brain-receipt→backend mapping now also
   intercepts controller-event LM2 `proof_to_response` payloads (`openclaw_request_processor.py`
   :2214). Confirm that path's telemetry is still correct (add/extend a test).
**Live verify:** a per-agent (non-maestro) capability reply reports that agent's identity, not
maestro; a deterministic/non-brain reply still reports `model_call_performed=False` honestly.

## Operator note (Fin) — OPTION 1 CONFIRMED (2026-06-29)
The operator **confirmed Fin Option 1**: do NOT build Fin (no agent, no lane, no token). In the SAME
P1 rebuild, ALSO strip the residual "fin (finance/...)" string from the SD-4 doctrine sentence in
`canonical_doctrine_facts.py`, then rebuild the ledger/FTS so BOTH "Clara Reed" and "fin" are gone
from the live store. The phantom-actor validator (P1.2) stays. Finance source-of-truth consolidation
and any future Fin agent are a SEPARATE later project (bundled with real agent-to-agent handoff) —
out of scope here.
