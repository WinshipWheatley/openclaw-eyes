# OpenClaw Operating Picture Latest

Status: `OPENCLAW_OPERATING_PICTURE_READY`

## Executive summary

Track A gives the teamroom path a review, handoff, staging, backlog, and Workroom question backbone. Track B gives protected gates, approvals, dead letters, artifact lineage, evidence confidence, memory promotion, lane graduation, cutover status, and an end-to-end smoke plan. Business actions remain gated.

## What is working

- Operator-ready workflows: 3
- Operator-assist workflows: 2
- Workroom review and handoff backbone: ready locally
- Governance, approval, dead-letter, evidence, and memory gates: ready locally

## Current next safe action

- Open review packet: PC_CODEX changed backend code and returned local validation proof for operator review.

## Protected actions

- email send: waits for explicit Guardian approval and a separate executor gate.
- Coupa submit: waits for explicit Guardian approval and a separate executor gate.
- ledger post or mark-paid: waits for explicit Guardian approval and a separate executor gate.
- source workbook mutation: waits for explicit Guardian approval and a separate executor gate.
- PDF export: waits for explicit Guardian approval and a separate executor gate.
- provider/browser/Gmail access: waits for explicit Guardian approval and a separate executor gate.
- worker spawn or child-agent execution: waits for explicit Guardian approval and a separate executor gate.
- git push: waits for explicit Guardian approval and a separate executor gate.

## What can run while Winship sleeps

- Local read-model refresh, gate scans, dead-letter audits, memory candidate distillation, and planning-only teamroom smoke preparation.

## Recommended next build lane

- Mac: Mac should render the operating picture, operator cutover board, review packet controls, and teamroom smoke plan without adding send, submit, ledger, worker-spawn, or live-provider controls.
- PC: Next backend work should stay local: classify remaining unknown SQLite concepts, refine dead-letter recovery, and plan Workroom dry-runs without providers or worker execution.

Proof refs are collapsed by default. This surface grants no send, submit, ledger, workbook, PDF, worker-spawn, push, or paid authority.
