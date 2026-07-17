# Capability Ledger Reconciler Activation - 2026-07-17

Status: **BUILT + REAL-INPUT DRY-RUN VERIFIED; PRODUCTION CONFIRM PENDING**

## Owner

The reconciler rides the installed 30-minute owner:

`*/30 * * * * cd /home/openclaw && /home/openclaw/chief_env/bin/python scripts/refresh_ledger_knowledge.py --confirm`

No second cron, timer, daemon, or model polling loop is introduced.

## Pre-Activation Evidence

- R0 commit: `2c758b1e`
- R1 commit: `d0f42443`
- production read-only dry run: 170 capability-machine rows
- PC inputs: 45 OpenClaw-related systemd rows, six cron rows, 24 listener process basenames
- Mac inputs: all 34 MacSol table verdict rows, including confirmed running/unregistered `com.openclaw.read-model-sync`
- Mac bridge: mounted, 86 GiB free, 91% used
- production reconciler tables before activation: absent
- production `capability_decisions` before activation: zero rows

## Gates

- default mode: dry run
- production write requires `--confirm`
- register writeback: impossible
- service, cron, process, or Mac mutation: impossible
- activation or authority grant: impossible
- external send, money, workbook, delete, or secret action: impossible

## Pending Live Gate

Deploy the refresh binding, run a confirmed production batch, run it again unchanged, prove injected drift in isolation, and ask the real Maestro front door “what's built and what's actually on?” from the ledger alone. Update this record and the Activation Gate Register only after all four pass.

## Rollback

Remove the reconciler invocation from `scripts/refresh_ledger_knowledge.py`. The existing knowledge-fold refresh continues unchanged; additive capability mirror and receipt tables remain inert historical evidence.
