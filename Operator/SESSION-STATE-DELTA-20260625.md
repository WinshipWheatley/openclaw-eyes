# Session state delta — verified git/audit reality (2026-06-25, late)
*Author: Opus (build-thread). NOT an orchestrator doc — surfaced for orchestrator reconciliation. Doc edits to MASTER_PROGRAM_QUEUE.md / ORCHESTRATOR_HANDOFF.md left to the orchestrator per the standing "orchestrator-only doc edits" rule.*

## Verified git state (read from `git log`/`reflog`, not assumed)
- **Integration branch `codex/stress-fixes` tip = `9e722a76`** (continuity-stamp, re-landed).
- **Continuity-stamp: LANDED `9e722a76`** (content-identical to the audited `1636d142`). Gemini audit **PASS** (`from-gemini/CONTINUITY-STAMP-AUDIT-RESULT.md`, 7/7 dimensions, 38 tests). 14 continuity tests green on the tip.
  - **⚠️ DRIFT EVENT (recorded):** the first cherry-pick landed `6e05536c` (reflog `@{1}`), then `codex/stress-fixes` was **reset back to `29b6b224`** by a parallel process (reflog `@{0}`: `reset: moving to 29b6b224`), silently dropping the continuity cherry-pick. Re-landed as `9e722a76` and verified it stuck. No data lost (work also preserved in `agy-sonnet/continuity-reconcile @ 1636d142`). Lesson: parallel processes are force-moving the integration branch ref; re-verify the tip after any landing.
- **Front-door local-model profile: COMMITTED ISOLATED `5cb81093`** on `agy-sonnet/frontdoor-model-profile` (base was `6e05536c`). **NOT cherry-picked** (awaiting Gemini PASS). 30 new synthetic tests + 158 no-regression green. Gemini audit **PENDING** (`to-gemini/FRONTDOOR-MODEL-PROFILE-AUDIT.md`, cites `5cb81093`).

## Doc discrepancy to reconcile (ORCHESTRATOR_HANDOFF.md line ~50)
The handoff asserts "no continuity-stamping gap remains; the 562 symptom was the pre-fix half-enabled state, now closed" — attributing the close to the flag-enablement + the existing wrapper stamp at `process_request_path` 7756–7779.
- **Correction:** that existing wrapper stamp is **flag-gated (`OPENCLAW_CONTINUITY_CAPSULE`) AND requires a non-empty minted `conversation_id` AND a loaded capsule.** Brain/CHAT responses with the flag OFF, or with no minted id, or on the grounded-fallback path, still carried **no** continuity ids. That residual gap is what the continuity-stamp fix (`9e722a76`) closes with a **flag-INDEPENDENT, CHAT-only** stamper (conversation_id + turn_id + operator_id + agent_id + thread_id, safe fallback id when unminted, mirrored into the brain card machine_proof). So the gap was NOT fully closed by enablement alone; it is closed now by `9e722a76`.

## Holds in effect (operator directive)
- **Model-ladder canary HELD** until Gemini PASS on `FRONTDOOR-MODEL-PROFILE-AUDIT.md` AND system load is lower (load avg was 8–13; latency p50/p90 would be contaminated under load).
- Do NOT cherry-pick `5cb81093` until Gemini PASS.
- Do NOT enable `OPENCLAW_INTERPRETER_LM` in prod; no listener/systemd/Telegram/email/banking/legal/invoice/external action; no draft-only email.

## When the canary runs (recorded for execution): one contained run
qwen3.5:4b → qwen3:8b-q4_K_M → qwen3.5:9b; think:false; capped output; v2 front-door prompt budget. Record per model: latency (p50/p90 over ≥5 turns), prompt size, done_reason, fallback reason, delivered source (model vs grounded), continuity ids, authority flags. Pick the FASTEST model giving a complete, concise, non-reciting answer within the operator-facing budget.
