# Harness Provider Selection Registry

Status: `HARNESS_PROVIDER_SELECTION_READY`

This registry chooses the right harness/provider class per outcome. It is planning-only and does not invoke models, connect providers, run Codex automation, or grant authority.

## Provider Classes

### `openclaw_local_deterministic`

- Default policy: default_for_private_invoices_and_deterministic_safety
- Data boundary: local_generated_read_models_and_metadata
- Unattended policy: review_only_possible_no_business_action

### `pc_codex_backend_worker`

- Default policy: default_for_backend_code_tasks
- Data boundary: local_repo_only_after_operator_packet
- Unattended policy: not_unattended_from_registry

### `mac_codex_ui_worker`

- Default policy: default_for_mac_ui_or_gui_helper_outcomes
- Data boundary: Mac-visible UI/context after operator packet
- Unattended policy: not_unattended_from_registry

### `codex_desktop_operator_assist`

- Default policy: only_behind_operator_present_gate
- Data boundary: operator_present_local_desktop
- Unattended policy: never_unattended

### `local_llm_shadow_mode`

- Default policy: shadow_only_until_local_runtime_gate_exists
- Data boundary: redacted_local_prompt_only
- Unattended policy: shadow_review_only_no_execution

### `future_local_open_model`

- Default policy: future_candidate_not_current_execution
- Data boundary: future_local_runtime_only
- Unattended policy: not_unattended_until_sleep_safe_registry_approves

### `external_llm_blocked_by_default`

- Default policy: blocked_for_local_code_client_files_and_private_invoices_unless_approved
- Data boundary: none_by_default
- Unattended policy: never_unattended_by_default

### `google_workspace_connector_sunk_cost_exception`

- Default policy: may_be_considered_only_behind_google_workspace_gate
- Data boundary: connector_scope_only_after_gate
- Unattended policy: never_unattended

### `browser_coupa_operator_assist`

- Default policy: only_for_coupa_or_browser_outcomes_with_final_human_gate
- Data boundary: operator_present_browser_only_after_gate
- Unattended policy: never_unattended

## Example Selections

- `private_workbook_workflow` -> `mac_codex_ui_worker`
  - Reason: GUI/Mac/workbook-helper work belongs in a future MAC_CODEX UI packet, not an external model.
  - Usable now: `false`
  - Gate required: `true`
- `backend_code_task` -> `pc_codex_backend_worker`
  - Reason: Backend code generation belongs in a future PC_CODEX worker packet with receipts.
  - Usable now: `false`
  - Gate required: `true`
- `ui_task` -> `mac_codex_ui_worker`
  - Reason: GUI/Mac/workbook-helper work belongs in a future MAC_CODEX UI packet, not an external model.
  - Usable now: `false`
  - Gate required: `true`
- `coupa_operator_assist` -> `browser_coupa_operator_assist`
  - Reason: Coupa/browser work requires operator-present browser assist with a final human gate.
  - Usable now: `false`
  - Gate required: `true`
- `external_llm_request` -> `external_llm_blocked_by_default`
  - Reason: External LLM was requested, but it is blocked by default for local code/client/private data.
  - Usable now: `false`
  - Gate required: `true`
- `gmail_calendar_sunk_cost` -> `google_workspace_connector_sunk_cost_exception`
  - Reason: Google Workspace may use the sunk-cost connector exception only behind a gate.
  - Usable now: `false`
  - Gate required: `true`

## Boundary

- No model invocation.
- No external provider connection.
- No Codex automation run.
- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, worker, child-agent, agent-loop, or git push authority.
- Provider choice is per outcome and never grants authority.
