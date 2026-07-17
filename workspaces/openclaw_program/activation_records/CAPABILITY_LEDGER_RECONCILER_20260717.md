# Capability Ledger Reconciler Activation - 2026-07-17

Status: **DEPLOYED + SCHEDULED + PRODUCTION VERIFIED**

## Owner

The reconciler rides the installed 30-minute owner:

`*/30 * * * * cd /home/openclaw && /home/openclaw/chief_env/bin/python scripts/refresh_ledger_knowledge.py --confirm`

No second cron, timer, daemon, or model polling loop is introduced.

## Deployment

- R0 commit: `2c758b1e`
- R1 commit: `d0f42443`
- R2 wiring commit: `690f3e8d`
- typed-contract owner fix: `4700ffcb`
- production deploy commits: `3b7790a9`, `745ebc96`, `abdf8200`, `1a7caeea`
- active owners restarted: `maestro-listener.service`, `openclaw-request-response.service`

## Production Evidence

- production read-only dry run: 170 capability-machine rows
- PC inputs: 45 OpenClaw-related systemd rows, six cron rows, 24 listener process basenames
- Mac inputs: all 34 MacSol table verdict rows, including confirmed running/unregistered `com.openclaw.read-model-sync`
- Mac bridge: mounted, 86 GiB free, 91% used
- installed refresh-owner batch: `capability-reconcile:753374209b6299cd719b6bd6`, 172 rows / 172 changed decisions
- next scheduled snapshot correctly appended one runtime transition for `openclaw-gpu-model-health.service`
- repeated exact current snapshot: `IDEMPOTENT_REPLAY`, changed 0, decisions 0
- isolated real-process drift injection: running to dark emitted `REGISTERED_RUNTIME_DARK` and exactly one changed decision
- deployed Maestro answer: 172 rows, 30 runtime-confirmed on, 21 running/unregistered, 96 registered artifact proofs honestly unknown
- Maestro proof: ledger only; no read model, runtime collection, protected generation, external model, Cassandra handler, or send

## Gates

- default mode: dry run
- production write requires `--confirm`
- register writeback: impossible
- service, cron, process, or Mac mutation: impossible
- activation or authority grant: impossible
- external send, money, workbook, delete, or secret action: impossible

## Authority Boundary

- register writeback: `0`
- service, cron, process, or Mac mutation by reconciler: `0`
- activation or authority grants by reconciler: `0`
- external sends: `0`
- money, workbook, or delete actions: `0`
- SEND_HOLD: unchanged

## Rollback

Remove the reconciler invocation from `scripts/refresh_ledger_knowledge.py`. The existing knowledge-fold refresh continues unchanged; additive capability mirror and receipt tables remain inert historical evidence.
