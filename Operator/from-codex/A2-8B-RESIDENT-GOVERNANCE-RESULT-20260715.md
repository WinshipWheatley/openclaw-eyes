# A2 8B Resident Governance Result - 2026-07-15

## Status

- Branch: `codex/a2-8b-resident-governance-20260715`
- Code commits:
  - `2b4da8969de9f319d9b8057574c9e5cf019ef799` - 8b binding and GPU admission
  - `0c00720b2e80ea3eb8fdd703e46d6f4dfb4034da` - honest receipts and lease cleanup
  - `a6f1e867ce75e157ec910c2b5cc585febc5cade7` - CPU-only Maestro voice path
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
8. `master_voice.sh` now uses the existing warm CPU Kokoro service first, one local CPU
   fallback second, and text fallback last. CUDA is hidden for the entire launcher, and
   its tests can no longer source live credentials or call real Telegram.

## GPU Audit

- GPU: NVIDIA GeForce GTX 1660 Ti, 6144 MiB, compute capability 7.5, 1536 CUDA cores.
- Quiet baseline observed twice: 593-600 MiB used, 5367-5374 MiB free, no Ollama model
  loaded and no NVIDIA compute client reported.
- Contained 8b fit evidence: Ollama reported 5,551,820,928 bytes in VRAM at
  `num_ctx=1024` (fully offloaded); the card reported 5659 MiB used and 308 MiB free.
- Ollama: one loaded model maximum and one parallel request, which is correct for this card.
- Root-owned system Ollama fallback remains `OLLAMA_KEEP_ALIVE=30m`. The OpenClaw user has
  no passwordless sudo, so changing or restarting that service unattended is deliberately
  excluded. Active governed calls override the fallback explicitly: interactive 8b uses
  `10m`; admitted background work uses `0`.
- OpenClaw user services with direct CUDA libraries are masked. Local models are served by
  the central `ollama` service, so request-level model admission is the controlling boundary.
- With qwen3:8b resident, a warm CPU Maestro voice canary completed in 2.7 seconds. GPU
  usage remained exactly 5639 MiB, and Ollama's model digest, `num_ctx=1024`, and expiry
  were unchanged; the voice path neither loaded a second model nor extended the 8b pin.

## Verification

- TDD red states observed for 8b vote identity, actual bound-model use, per-request
  propagation, heavy deferral, scheduler retry, and the Chief direct-call bypass.
- `577 passed, 2 deselected in 25.95s` across vote, front door, interpreter, GPU arbiter,
  scheduler, responder, request processor, adaptive call, router, and fit-wall suites.
- Focused adversarial receipt/lease tests: `11 passed in 1.66s`.
- Maestro CPU-only voice and isolation suites: `20 passed in 2.64s`; `bash -n` passed.
- Python compile check passed for all changed runtime modules.
- `git diff --cached --check` passed before the code commit.
- The two deselected tests are date-sensitive June status fixtures. They fail unchanged on
  the live branch on July 15 because their seeded read models are stale; this patch did not
  cause them.

## Exact Pending Live Action

Rollback material already exists at
`D:\OpenClawBackups\a2-8b-resident-governance-predeploy-20260715T200411Z`
(`/mnt/d/OpenClawBackups/a2-8b-resident-governance-predeploy-20260715T200411Z`).
The verified bundle SHA-256 is
`958bbf4a977ea4b236480efbedffac72bddd9da6f6d6eb2311206411603b9f29`.
The original live `master_voice.sh` was added under the same backup's `files/home/openclaw/`
tree and matches SHA-256
`69fe25004c613b64f9dd9ffebedd3a2749eb82b4bc1bc6b502517af5ccba9718`.

After explicit operator approval of the final commit set:

1. Re-verify the existing D-drive bundle and replaced-file backup.
2. Compose commits `2b4da8969de9f319d9b8057574c9e5cf019ef799` and
   `0c00720b2e80ea3eb8fdd703e46d6f4dfb4034da`, plus the ordered documentation commits
   and `a6f1e867ce75e157ec910c2b5cc585febc5cade7`, onto live HEAD without disturbing
   generated churn or untracked Operator notes.
3. Set the request-response allowlist to only `qwen3:8b-q4_K_M`. Do not mutate the
   root-owned Ollama unit without an operator-attended sudo session.
4. Restart only request-response, briefing scheduler, and Chief listener in a quiet GPU
   window.
5. Run a contained local canary proving LM1 and LM2 both call 8b, only 8b is resident,
   the second call avoids a model swap, and a synthetic heavy request defers.
6. Roll back immediately from D if full offload, latency, or residency does not hold.

No external message/action authority is part of this deployment.
