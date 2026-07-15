# A2 8B Resident Governance Result - 2026-07-15

## Status

- Branch: `codex/a2-8b-resident-governance-20260715`
- Code commit: `2b4da8969de9f319d9b8057574c9e5cf019ef799`
- Base: `69fb2eb84d240e8d5249041938869e9d5044600a`
- Live deployment: **not yet performed**
- Red-line authority: unchanged; no send, delete, payment, move, or approval-gate activation

## What Changed

1. The semantic contract vote is bound to `qwen3:8b-q4_K_M`, `num_ctx=1024`,
   `keep_alive=10m`, and the existing eight-second wall.
2. Each operator request gets one immutable local-model binding. The interpreter,
   semantic vote, and protected final response consume the same binding.
3. `protected_generate` now uses the bound model in the actual Ollama call. The
   previous code could record `model_selected=8b` while calling a separately selected
   model.
4. The Chief album listener's two direct Ollama bypasses now use the same governed 8b
   through the shared model-slot path.
5. Async/heavy task classes acquire a build GPU lease, serialize on the one model slot,
   re-check for interactive preemption, defer while the 8b is resident, and force
   `keep_alive=0` when admitted.
6. The briefing scheduler retries a due generation window instead of invoking a heavy
   model while the interactive lane is resident or leased.
7. The fast interactive Cassandra reply route now reuses the resident 8b instead of
   swapping to 4b.

## GPU Audit

- GPU: NVIDIA GeForce GTX 1660 Ti, 6144 MiB, compute capability 7.5, 1536 CUDA cores.
- Quiet baseline: 593 MiB used, 5374 MiB free, no compute process, no Ollama model loaded.
- Ollama: one loaded model maximum and one parallel request, which is correct for this card.
- Gap found: system Ollama fallback `OLLAMA_KEEP_ALIVE=30m`. Proposed live correction is
  `OLLAMA_KEEP_ALIVE=0`; only explicit interactive 8b calls retain the bounded 10-minute pin.
- OpenClaw user services with direct CUDA libraries are masked. Local models are served by
  the central `ollama` service, so request-level model admission is the controlling boundary.

## Verification

- TDD red states observed for 8b vote identity, actual bound-model use, per-request
  propagation, heavy deferral, scheduler retry, and the Chief direct-call bypass.
- `519 passed, 2 deselected in 19.77s` across vote, front door, interpreter, GPU arbiter,
  scheduler, responder, request processor, adaptive call, router, and fit-wall suites.
- Python compile check passed for all changed runtime modules.
- `git diff --cached --check` passed before the code commit.
- The two deselected tests are date-sensitive June status fixtures. They fail unchanged on
  the live branch on July 15 because their seeded read models are stale; this patch did not
  cause them.

## Exact Pending Live Action

After explicit operator approval:

1. Create a D-drive predeploy Git bundle and copy every replaced runtime/config file.
2. Compose commit `2b4da8969de9f319d9b8057574c9e5cf019ef799` onto live HEAD without disturbing
   generated churn or untracked Operator notes.
3. Set request-response allowlist to only `qwen3:8b-q4_K_M` and set the Ollama service
   fallback keep-alive to zero.
4. Restart only Ollama, request-response, briefing scheduler, and Chief listener in a quiet
   GPU window.
5. Run a contained local canary proving LM1 and LM2 both call 8b, only 8b is resident,
   the second call avoids a model swap, and a synthetic heavy request defers.
6. Roll back immediately from D if full offload, latency, or residency does not hold.

No external message/action authority is part of this deployment.
