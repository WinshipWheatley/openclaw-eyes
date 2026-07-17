# Invoice Send W0 Activation - 2026-07-17

Status: **DEPLOYED + ACTIVE + REAL-PROCESS VERIFIED**

## Deployment

- worktree commits: `499018e2`, `cbe39ba0`
- production commits: `97c7fca9`, `48ba69fe`
- active owners restarted: `cassandra-listener.service`, `openclaw-request-response.service`
- recurrence owner: `openclaw-autonomous-invoice-prep.timer` enabled and active
- canonical transaction store: `/home/openclaw/generated/system_knowledge/cassandra_operator_objective_loop.sqlite`

## Registry Truth Batch

- receipt: `generated/system_knowledge/w0_lamd_registry_truth_receipt.json`
- receipt id: `w0-lamd-truth:5b19ed6ecd063245bd55`
- receipt sha256: `79c7fd0888eba395764a7c6551748b991af5d66defcbe1e8ab7337aaf246f8a8`
- Live Arts paid through: `2026-06-30`
- next due cycle: `2026-07-16`
- canonical recipient: `Accountant@liveartsmd.org`
- send state: `SEND_REQUIRES_GUARDIAN`
- numbering collision: reconciliation required before allocation
- workbook, payment, draft, send, delete, and invoice-number allocation actions: `0`

## Scheduler Canary

The installed systemd oneshot ran twice against production stores:

- first run: `PREPARED` `workflow_package:057b0f98330cc0a2` for `live_arts_md:2026-07-16`
- operator attention event: `autonomous_invoice_prep:live_arts_md:2026-07-16`
- second run: `IDLE`, reason `already_prepared_for_cycle`
- email, Telegram, ledger mutation, ledger posting, and business actions: `0`

## Front-Door Canary

The deployed `operator_conversation_router.route_conversation_text` called the real Cassandra objective path twice with the exact immutable packet and artifact:

- route: `CASSANDRA_INVOICE_ENVELOPE_PREPARED` twice
- transaction: `invoice-send-tx:2bd8efb929ecbed5376b2204`
- semantic key: `invoice-send:2bd8efb929ecbed5376b2204f2b4debb7573e7248889ae3f622a1bd576c5a261`
- envelope hash: `sha256:11f3d5b1c557e3a0852975fb9ae8f1bdcb498725c168504654208c13ef642801`
- canonical row count: `1`
- first result: created
- second result: idempotent replay
- lifecycle state: `PREPARED`
- Cassandra voice receipts: passed twice
- Gmail lookup/body read, provider call, provider draft, email send, money, workbook mutation, and external actions: `0`

Five deployed-code negative probes failed locally before a second transaction could persist: changed-recipient semantic collision, wrong speaker, wrong sender, `DRAFT`, and altered amount. The isolated negative store remained at one valid baseline row.

## Voice Boundary

The deployed `operator_surface_guard` was exercised for all eight canonical profiles. Own-profile copy passed 8/8; an injected shared canned phrase was substituted 8/8 using each speaker's own fallback while the neighboring verified sentence remained visible. Focused W0 and owner-boundary suite: `47 passed`.

## Authority Boundary

- SEND_HOLD sentinel: present and unchanged
- SEND_HOLD sha256: `cd42d038e22bbd33e83acada144e20299a5767c864b4833ad00b0d04f2cd8abb`
- Guardian approval granted: no
- provider draft or send authority granted: no
- email sends: `0`
- money actions: `0`
- workbook mutations: `0`
- deletes: `0`

July's live `$100.00` Live Arts invoice is an early prepared operator-review target only. It has not been drafted at the provider, sent, posted, marked paid, or assigned a reconciled invoice number.

## Rollback

Revert the two W0 production commits and restart Cassandra plus request-response. Disable `openclaw-autonomous-invoice-prep.timer` only if the recurrence or authority-boundary canary regresses. No provider draft, sent state, payment state, or workbook state requires cleanup.
