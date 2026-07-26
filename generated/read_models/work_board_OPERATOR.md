# OpenClaw Work Board Read-Model v0

What this is:
- A generated read-model over local `work_board_*` control-plane cards.

What this is not:
- It is not execution, approval, agent activation, model calling, external API access, or file operations.

Summary:
- Boards: 1.
- Cards: 96.
- By column: completed_with_receipt=3, deferred=7, needs_review=34, pending_approval=1, planned=8, routed=43.
- By agent: cassandra=33, chief=37, guardian=6, hermes=6, niles=8, report_bridge=6.
- Needs review: 34.
- Pending approval: 1.
- Blocked: 0.
- Completed with receipt: 3.

Latest cards:
- `wbcard_f2d37b1dce085eda7194` needs_review manual_seed:finance_invoice_reconciliation:review_repo_b_finance_helpers - Review Repo B finance helpers
- `wbcard_b3403ca433adbd4f8b37` needs_review manual_seed:finance_invoice_reconciliation:receivables_evidence_requirements - Review receivables evidence requirements
- `wbcard_0ad11f9f87705b71bed6` planned manual_seed:finance_invoice_reconciliation:finance_invoice_helper_v0_proposal - Build Finance Invoice Helper v0 proposal
- `wbcard_e90dddf86d765f017c6a` needs_review manual_seed:cassandra_runtime_wiring_audit:reply_path - Cassandra reply path blocked/missing
- `wbcard_8c35b7333c75580af726` needs_review manual_seed:cassandra_runtime_wiring_audit:capital_hilton_route - Capital Hilton facts via Cassandra route
- `wbcard_7e6119ad90d3531c2c6b` needs_review manual_seed:cassandra_runtime_wiring_audit:receive_path - Cassandra receive path not proven
- `wbcard_470defd2053f212ea3d3` needs_review manual_seed:cassandra_runtime_wiring_audit:repo_b_listener_review - Review/wrap Repo B Cassandra listener logic
- `wbcard_37003d029460d66ea9e0` routed manual_seed:telegram_agent_intake:tgupdate_27a2f7d73046773c6df9 - Telegram intake proof for Cassandra
- `wbcard_1cbbb43684927237ccea` routed manual_seed:telegram_agent_intake:tgupdate_4ea92b2deef77be2b048 - Telegram intake proof for Cassandra
- `wbcard_49c6af5f5c3e694f37ba` routed manual_seed:telegram_agent_intake:tgupdate_666f4a675a355b3a7cf2 - Telegram intake proof for Cassandra

Top next safe moves:
- Do you want Mission Control to draft action request files into the E-drive inbox next? Suggested lane: Mission Control Action Request Writer v0.
- Do you want to build recent-file context resolution over File Event Queue metadata? Suggested lane: Recent File Context Resolver v0.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.
- Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything.
- Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files.

Authority boundary:
- `direct_execution_allowed`: `false`.
- `arbitrary_shell_allowed`: `false`.
- `auto_approval_allowed`: `false`.
- `auto_execute_allowed`: `false`.
- `agent_activation_allowed`: `false`.
- `model_call_allowed`: `false`.
- `tool_execution_allowed`: `false`.
- `network_authority`: `false`.
- `no_go_raw_access_allowed`: `false`.
- `file_move_allowed`: `false`.
- `file_delete_allowed`: `false`.
- `client_deployment_allowed`: `false`.
