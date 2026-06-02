# System Question Answering

Status: `SYSTEM_QUESTION_ANSWER_V0_READY`

This workflow answers local questions about OpenClaw state, gates, agents, packages, receipts, and proof refs.

It is deterministic and local-only. It does not call an external LLM, spawn agents, run loops, send email, open browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, submit portals, or mark paid/sent.

## Speaker Routing

- `architecture_system_design` -> `hermes`
- `package_block_gate_diagnostic` -> `chief`
- `safety_authority` -> `guardian`
- `neutral_status` -> `openclaw`

## Source Scope

- `json_read_models`: `generated/read_models/*.json`
- `operator_wiki`: `generated/wiki/openclaw/*.md`
- `sqlite_metadata_only`: `generated/system_knowledge/*.sqlite`
- `operations_docs`: `docs/operations/*.md`
- `doctrine_docs`: `docs/doctrine/*.md`

## Example Answers

- Chief packages work; workers execute packages: Chief is a hardwired diagnostic role, while a spawned worker is a bounded package execution thread. Next: Keep this as explanation only; do not spawn workers without a gated package.
- Capital Hilton is blocked by provider gates: The submit package is blocked because Coupa requires operator assist and a final Submit gate. Next: Stage an operator-assist packet with an explicit final Submit gate if the operator wants to continue later.
- Email send authority is closed: No email can be sent unless a separate explicit send gate is recorded. Next: Keep the business action gate closed until an explicit send approval exists.
- SQLite has work-log metadata: SQLite can report St. Anne's work-log tables and counts without dumping raw event rows. Next: Open the proof drawer if table names/counts are enough; request a separate whitelisted proof read for row-level details.
- No local answer found: I do not have a deterministic local answer for that question yet. Next: Ask with a specific package id, gate name, client, or receipt ref.

## Boundary

- Proof refs should remain collapsed by default.
- SQLite access is schema/count metadata only unless a later workflow explicitly whitelists row-level proof.
- Unknown questions return unknowns and source refs instead of guessing.
