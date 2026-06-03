# Workflow Composer

Status: `WORKFLOW_COMPOSER_READY`

Workflow Composer turns an operator goal into a transparent pre-execution plan. It does not execute workers or perform business actions.

## Roles

- Cassandra summarizes the human meaning.
- Hermes recommends the sequence.
- Chief converts the sequence into packet outlines.
- Guardian marks protected gates.

## Required Examples

### `workflow_plan:st_annes_invoice:b388b5bca40d`

- Goal: Get St. Anne's monthly invoice workflow ready.
- Risk: `medium`
- Safe to stage: `true`
- Safe to execute: `false`
- Recommended next action: Review this invoice workflow plan, then approve a dry-run package only if the evidence sources look right.

### `workflow_plan:capital_hilton_proposal:5e3749700dc8`

- Goal: Follow up on Capital Hilton proposal.
- Risk: `medium`
- Safe to stage: `true`
- Safe to execute: `false`
- Recommended next action: Review the Cassandra/Clara follow-up route, then approve a dry-run package if it matches the relationship context.

### `workflow_plan:helm_noise:8e24bf9e6b7e`

- Goal: Improve Helm so it feels less noisy.
- Risk: `low`
- Safe to stage: `true`
- Safe to execute: `false`
- Recommended next action: Approve a narrow MAC_CODEX UI packet only after choosing the first Helm noise source to fix.

### `workflow_plan:st_annes_work_logging:4804f4abecbe`

- Goal: Set up a workflow for monthly St. Anne's work logging.
- Risk: `medium`
- Safe to stage: `true`
- Safe to execute: `false`
- Recommended next action: Review the receipt fields, then approve only the smallest monthly work-log packet.

### `workflow_plan:overnight_safety:17f93a3b8a69`

- Goal: Can this run while I sleep?
- Risk: `high`
- Safe to stage: `true`
- Safe to execute: `false`
- Recommended next action: Stage at most a small overnight review list after approval; execute nothing while unattended.

## Boundary

- Planning only.
- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, push, worker, child-agent, agent-loop, or external-LLM authority.
- Later package staging requires operator approval.
- Plans must expose bottlenecks and avoid large unreviewed piles of work.

## Contract

- Contract read-model: `generated/read_models/workflow_composer_contract.json`
- Latest read-model: `generated/read_models/workflow_composer_latest.json`
- Preconditions ready: `true`
