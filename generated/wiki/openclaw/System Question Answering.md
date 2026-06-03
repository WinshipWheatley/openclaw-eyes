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
- Safe next is review, not action: The safe next move is to review local proof and keep business-action gates closed. Next: Pick one proof ref or package id to inspect locally.
- SQLite databases are classified by ownership: OpenClaw has workflow state, generated evidence, generated status, test harness, protected ledger, and unknown-review database classes. Next: Ask for one domain, such as package truth, work logs, ledger, or cleanup posture.
- Package truth lives in the package queue: Package status truth comes from the workflow package queue, with the package event index as the request/response index. Next: Use the package id or workflow_ref to inspect local package proof; do not mutate package rows from an answer.
- St Anne's work-log truth has a local owner: Operator-facing St Anne's work-log truth comes from the work-log read model, backed by the local staging SQLite database. Next: Ask for confirmed versus staged work-log status; do not mutate workbook cells or invoice inclusion from this answer.
- SQLite consolidation is plan-only: Do not consolidate yet; the safe first move is a package-event-index-backed views/indexes overlay, not migration. Next: Review the plan and create a non-mutating overlay design; do not create views, indexes, or migrations yet.
- Ledger stays isolated: The ledger is not a package/read-model truth store and must not be mixed into SQLite consolidation. Next: Keep ledger and protected stores out of package/event consolidation unless a separate approved payment-evidence workflow exists.
- Cleanup is review-only for now: Nothing is safe to delete from this answer; safe cleanup means classify, review, and plan non-mutating overlays first. Next: Create a review checklist from the plan; do not delete or move any database.
- Protected stores must never merge: Never merge ledgers, secrets, raw prompt bodies, or test harness data into package or read-model state. Next: Keep these stores isolated and require a separate operator-approved classification packet before any future change.
- The team is working in local Workrooms: Chief sees current work split across Build, Operations, Finance, Architecture, Security, and related Workroom channels. Next: Open the specific Workroom channel you want to review.
- Build / Mission Control Mac has review context: The Mac build Workroom contains local UI review packet and activity context. Next: Open the Workroom review packet controls; no merge or push is authorized by this answer.
- MAC_CODEX output is in review packets: Chief can summarize MAC_CODEX output from local review packet refs without running the worker. Next: Review the packet proof; do not merge, push, or run worker actions from this answer.
- Review packets need local operator decisions: Chief filters Workroom review packets to unresolved items that need your attention. Next: Open the first unresolved review packet and choose a review-only decision.
- Cassandra hands package needs to Chief: Cassandra hands operational package needs to Chief through registered local handoff refs. Next: Record or stage only a local handoff packet; do not spawn workers from the answer.
- Hermes routes build recommendations to Chief: When Hermes recommends a build, the route is a local build packet to Chief before any worker packet exists. Next: Record or stage only a local handoff packet; do not spawn workers from the answer.
- PC_CODEX cannot push from this workflow: PC_CODEX can produce local result receipts or review packets, but git_push_allowed=false in these Workroom surfaces. Next: Keep review packet decisions local; do not push.

## Boundary

- Proof refs should remain collapsed by default.
- SQLite access is schema/count metadata only unless a later workflow explicitly whitelists row-level proof.
- Unknown questions return unknowns and source refs instead of guessing.
