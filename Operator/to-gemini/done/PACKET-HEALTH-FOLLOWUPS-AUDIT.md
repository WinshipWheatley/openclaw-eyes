# GEMINI AUDIT SPEC — Packet-Health Follow-ups (P1–P7)

Dispatched by: Opus (program orchestrator)
Date: 2026-06-30
Audit ID: PACKET-HEALTH-FOLLOWUPS-AUDIT
Write result to: `Operator/from-gemini/PACKET-HEALTH-FOLLOWUPS-AUDIT-RESULT.md`

## Why this audit
A 12-agent packet-health audit found the deterministic context packets are BUILT correctly; the historical "agents reciting" was a model-fit/consumption problem already fixed in prod. Codex then built the 7 prioritized follow-ups (P1–P7) from the audit job in an ISOLATED branch. Opus has verified it read-only (all 167 added/changed tests reproduced GREEN in an isolated worktree; branch is clean off the audit-doc commit; P1 selection logic reviewed). This is the independent external-audit gate before the work is integrated into `codex/stress-fixes` and the brain services are restarted to activate it. **Do NOT build, merge, move branches, restart services, run the live brain/ollama, send Telegram/email, touch banking/legal/invoices, or mutate production ledgers — audit the exact commits by reading + (optionally) re-running the SYNTHETIC tests only.**

## Exact targets
- **Branch:** `codex/packet-health-audit-20260630`
- **Base (must be UNMOVED):** `4ad65ddc31a1d208787753a3ce51509bec36e71a` ("docs(audit): packet-health verdict + Codex morning job")
- **`codex/stress-fixes` tip (integration target, must stay UNMOVED during audit):** `7c9d848aa737074ae9dd06f1dc6c6f4b56087b02`
- **Commits (audit these 7, oldest→newest):**
  - `eca346de520645c98e19c05c5e37cd419f8c851e` — P1 fix(frontdoor): step down under vram contention
  - `e042bc47029808b72dbeb49d89990b16438cf5bb` — P2 fix(frontdoor): thread live agent persona
  - `8f4f1566a84cc5d326e0e485ade3da73bd68b650` — P3 fix(frontdoor): keep question-domain facts per agent
  - `d15ed20e7b062bb0bae2f348fb2a8bc2c3f53e3e` — P4 fix(protected-generate): record receipt agent
  - `c8b95209255c32e913afe908d985b4a6cc5ca15e` — P5 fix(read-model): refresh capability index timestamp
  - `42f951ea0dff12b4061953f5da61f86464f89f67` — P6 test(frontdoor): add live model lane probe
  - `8597217408d52ba51b4f9aa02f12a0913e6f2d57` — P7 fix(intake): normalize operator payments into g2c records
- **Files changed (17, +1122/−30):** `chief_llm.py`, `protected_generate.py`, `maestro_cassandra_responder.py`, `openclaw_request_processor.py`, `operator_controller_event_router.py`, `frontdoor_prompt.py`, `openclaw_capability_index.py`, `generated/read_models/openclaw_capability_index.json`, `operator_universal_intake.py` (NEW, 358 lines), `scripts/frontdoor_live_probe.py` (NEW), + 7 test files.
- **Spec to audit against:** `Operator/CODEX-PACKET-HEALTH-AUDIT-2026-06-30.md` (the P1–P7 requirements + ACCEPTANCE CRITERIA section).

## Required checks (READ-ONLY) — per item, with file:line evidence

1. **P1 — VRAM step-down (`chief_llm.select_frontdoor_model`, `protected_generate.py` receipt):**
   Confirm that under free-VRAM contention it steps down to the SMALLEST fitting local model and tags a step-down reason; that `no_fitting_model` fires ONLY when no local model fits at all; that `unreachable`/ollama-down still falls SAFE to deterministic. **Scrutinize for a false `no_fitting_model`** (a regression that would force recitation when a small model actually fits). Confirm `model_selection_reason` is recorded in the receipt without breaking the existing schema.

2. **P2 — thread agent persona (THE sensitive one):** Confirm `agent=` is threaded from the live call sites (`openclaw_request_processor.py`, `operator_controller_event_router.py`) → `answer_frontdoor_chat`/`_answer_with_maestro_brain` → `build_frontdoor_prompt(agent=)`. **CRITICAL:** verify it does NOT add an `agent` param to `build_maestro_context_packet` — the shared facts packet must be byte-identical regardless of agent; only persona/render may vary. Confirm the Maestro path is unchanged (default still maestro). Cite the exact threading.

3. **P3 — non-destructive relevance filter (`frontdoor_prompt.build_frontdoor_prompt`):** Confirm an in-scope fact (domain matches the question) is no longer dropped for any agent (the gig→cassandra case), while the cosmetic re-rank is preserved. Check it does not now OVER-retain (packet bloat / leak of unrelated facts back in).

4. **P4 — `agent` in the receipt (`protected_generate.py`):** Confirm it's a pure additive field (default "maestro" when unthreaded) and that existing `protected_generate_audit.jsonl` records still parse.

5. **P5 — capability-index refresh (`openclaw_capability_index.py` + the read-model JSON):** Confirm the generator now advances `as_of`/`generated_at` on refresh rather than a hand-edited stale JSON; confirm the JSON change is a regenerated artifact consistent with the generator, not a manual fudge.

6. **P7 — Universal Operator Intake (`operator_universal_intake.py`, NEW 358 lines — HIGHEST SCRUTINY, scope-expanded beyond the LOW-priority ask):** The module claims it "does not approve, execute, send, call live services, mutate external systems, or mark invoices paid." **Verify that claim against the code.** Specifically: does any path send Telegram/email, call a live broker/ollama/external API, mark an invoice paid, move money, or mutate a PRODUCTION ledger/store at import or on the normal intake call? Is it INERT until explicitly invoked (not auto-wired into a live listener)? What store does it write (temp/local receipts vs production `ar_gig_to_cash_store`/G2C)? Flag any boundary violation or unbounded write.

7. **No live fire in tests:** confirm the 7 test files use temp SQLite/dirs/injected fakes and do not launch a real ollama/LM call, real subprocess, real Telegram/email, or open production stores. `scripts/frontdoor_live_probe.py` (P6) is a probe HARNESS — confirm it only runs the model lane when explicitly invoked, not during the test suite.

8. **Scope + branch safety:** only the 17 files above; nothing under `generated/` except the one regenerated `openclaw_capability_index.json`; no `*.sqlite3`, no systemd units, no Telegram/email/banking/legal/invoice/credential/external-action wiring turned on; `codex/stress-fixes` == `7c9d848a` (UNMOVED); 7 clean commits; no merge/cherry-pick performed.

## Opus has already verified (for your cross-check, re-derive independently)
- All 167 added/changed tests GREEN, re-run in an isolated worktree with the live gitignored deps on the path (`PYTHONPATH=<worktree>:/home/openclaw`, 22.99s).
- Branch is 7 commits off `4ad65ddc`, no other base movement.
- P1 `select_frontdoor_model` logic reviewed: step-down picks `card_fitting[0]` (smallest) under contention.

## Return (in the result file)
- Exact branch/base/commits/spec; the 8 checks above with file:line evidence; tests re-run + observed counts.
- **Verdict: PASS / PARTIAL / FAIL** per item AND overall, with required corrections if not PASS.
- Explicit attention to: P2 (shared facts packet unchanged) and P7 (Universal Intake is genuinely bounded + inert).
- Explicit confirmation that nothing was built, merged, moved, run live, sent, or mutated during the audit, and that `codex/stress-fixes` remained at `7c9d848a`.
