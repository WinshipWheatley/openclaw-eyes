# Goldilocks Gate Calibration

Status: GOLDILOCKS_GATE_CALIBRATION_READY

This is a contract/read-model calibration surface. It does not loosen live gates, grant business authority, invoke LMs, connect providers, spawn workers, send, submit, mutate ledgers/workbooks, export PDFs, mark paid, or push.

## Goldilocks Zone

Agents should have enough room to plan, draft, inspect locally, stage packets, collect proof, prepare review packets, and perform scoped deterministic repo work. Protected external, financial, credential, source-data, provider, worker, push, and merge actions stay gated.

## Gate Levels

### 0. readback

- Allowed: answer_from_existing_proof, summarize_verified_read_models, explain_missing_proof, name_blocked_gate
- Forbidden: mutation, command_execution, stage_package, create_draft_artifact, external_action, authority_grant
- Required proof: proof/read-model/receipt reference for factual claims, explicit no-mutation boundary
- Required receipt: source_refs_only_no_state_change_receipt
- Stop conditions: operator asks for mutation or execution, proof is missing for a factual claim, answer would imply paid/sent/submitted truth without receipt
- Too strict: Agents become status surfaces that cannot explain blockers or next safe moves.
- Too loose: Generated text becomes unproven truth or quietly triggers state changes.

### 1. plan

- Allowed: propose_plan, decompose_scope, identify_required_proof, recommend_next_gate_level, draft_package_outline_in_response_only
- Forbidden: stage_package, create_package_or_draft_artifact, edit_files, run_checks, external_action, authority_grant
- Required proof: objective reference, scope boundary, known precondition refs
- Required receipt: planning_receipt_no_artifact_created
- Stop conditions: package artifact would be created, execution would begin, scope or authority is ambiguous
- Too strict: Agents ask for too much babysitting before they can reason through the work.
- Too loose: Plans quietly become staged artifacts or execution without promotion.

### 2. stage

- Allowed: stage_package, create_draft_artifact_in_approved_workspace, create_review_packet, collect_proof_refs, prepare_non_executing_artifact_manifest
- Forbidden: external_action, send_submit_post_or_mark_paid, source_workbook_mutation, git_push_or_merge, worker_spawn, authority_grant
- Required proof: package scope and approved workspace path, artifact manifest, source/proof refs for claims in the staged package
- Required receipt: staging_receipt, artifact_manifest_receipt, no_external_action_receipt
- Stop conditions: artifact would leave approved workspace, request asks for final external action, draft would claim completed business truth
- Too strict: Useful drafts, review packets, and proof packages never materialize.
- Too loose: A staged artifact is mistaken for send/submit/ledger authority.

### 3. safe_internal_work

- Allowed: local_deterministic_checks, local_draft_generation, local_artifact_prep, repo_inspect_edit_test, commit_after_validation_if_package_grants, read_model_generation
- Forbidden: send_email, open_gmail, open_browser_or_coupa, submit_portal, post_ledger, mark_paid, mutate_source_workbook, export_pdf, use_credentials_or_secrets, invoke_external_llm, connect_local_model_runtime, expand_live_provider_or_tool, spawn_worker_or_live_loop, git_push, git_merge
- Required proof: package grants local workspace/repo scope, diff or artifact manifest, focused test/check receipt, no protected action proof
- Required receipt: command/test receipt, diff summary, artifact manifest, commit hash only when package grants commit and validation passes
- Stop conditions: protected external action requested, scope expands beyond package/workspace, secret or credential access is required, network/provider/runtime connection would be needed, git push or merge would be needed
- Too strict: OpenClaw collapses into forms/cards/status and cannot repair or prepare useful work.
- Too loose: Local work crosses into protected business, external, provider, or source-data authority.

### 4. prepare_approval

- Allowed: fill_approval_package, prepare_operator_review_packet, attach_operator_provided_screenshot_or_proof, draft_exact_payload_for_future_gate, queue_non_executing_approval_request
- Forbidden: final_submit, send_email, post_ledger, mark_paid, git_push_or_merge, execute_approval_as_action, authority_grant
- Required proof: exact requested action and scope, payload hash or artifact id, supporting proof refs, explicit list of blocked final actions
- Required receipt: approval_request_receipt, proof_package_manifest, no_execution_receipt
- Stop conditions: payload is broad or ambiguous, supporting proof is missing, operator wording could be interpreted as final execution authority
- Too strict: Protected work never reaches an operator-ready decision package.
- Too loose: Approval preparation is treated as send/submit/post/paid/push execution.

### 5. execute_after_approval

- Allowed: future_scoped_execution_after_verified_operator_approval, guardian_gate_required, receipt_requirements_required, rollback_or_stop_conditions_required
- Forbidden: current_execution_from_this_read_model, execution_without_verified_operator_approval, execution_without_guardian_gate, execution_without_receipt, broad_or_ambient_authority
- Required proof: verified operator approval, Guardian gate decision, exact payload hash and scope, preflight proof, rollback/stop plan
- Required receipt: execution_receipt, post_action_verification_receipt, rollback_or_stop_receipt_when_triggered
- Stop conditions: approval missing or stale, payload hash mismatch, receipt path unavailable, rollback/stop condition unavailable, operator revokes or scope changes
- Too strict: Even explicitly approved work cannot complete, so operators must do everything manually.
- Too loose: Final protected actions happen without a verified, scoped, receipted approval chain.

### 6. never_or_future_gated

- Allowed: model_as_blocked, draft_future_risk_analysis, route_to_guardian_or_operator_for_new_contract
- Forbidden: secrets_or_broad_credentials, unbounded_browser_gmail_or_coupa, ledger_posting, paid_marking, source_workbook_mutation, git_push_or_merge, live_worker_swarms, live_provider_or_tool_expansion, business_authority_grant
- Required proof: separate explicit authority contract before any future consideration, risk analysis and owner, rollback/decommission plan for any future exception
- Required receipt: blocked_gate_receipt, future_contract_required_receipt
- Stop conditions: direct request for secret/credential/material authority, unbounded or ambient access requested, ledger/paid/source-workbook/push/merge authority requested, live swarm or provider expansion requested
- Too strict: Safe local planning or repo work gets overclassified as impossible.
- Too loose: The system crosses protected authority boundaries that LMs must never invent.

## Scenarios

### Codex-like code patch inside repo

- Gate: `safe_internal_work`
- Allowed now: inspect_repo, edit_repo_files_in_package_scope, run_focused_tests, run_py_compile, run_git_diff_check, commit_after_validation_if_package_grants
- Blocked now: git_push, git_merge, external_llm, worker_spawn
- Note: Local repo work is useful safe_internal_work; push remains protected.

### Finance payment watch

- Gate: `stage`
- Allowed now: readback_payment_state_from_proof, attach_payment_proof_reference, stage_ledger_review_packet
- Blocked now: post_ledger, mark_paid, create_paid_truth_without_receipt
- Note: Proof attachment and review staging are useful; ledger/paid truth stays gated.

### Coupa invoice submit

- Gate: `prepare_approval`
- Allowed now: prepare_coupa_approval_package, attach_operator_provided_screenshot, draft_exact_submit_payload_for_review
- Blocked now: open_coupa_unbounded, final_submit, mark_submitted_without_receipt
- Note: Approval prep can become operator-ready; final submit waits for a future explicit gate.

### Excel invoice export

- Gate: `prepare_approval`
- Allowed now: stage_export_helper_package, prepare_scoped_permission_request, prepare_export_review_checklist
- Blocked now: source_workbook_mutation, pdf_export_without_gate, open_or_rewrite_private_workbook_unbounded
- Note: A helper may run only under scoped permission with receipts; source mutation needs its own explicit gate.

### Business Development follow-up

- Gate: `stage`
- Allowed now: draft_followup, stage_review_copy, prepare_send_approval_request
- Blocked now: send_email, open_gmail, mark_sent_without_receipt
- Note: Drafting and staging keep momentum; sending remains a protected action.

### OpenClaw self-repair

- Gate: `safe_internal_work`
- Allowed now: diagnose_local_failure, patch_repo_scope, run_focused_tests, commit_after_validation_if_package_grants
- Blocked now: service_restart_without_explicit_package, live_loops, worker_spawn, git_push
- Note: Self-repair can patch and test locally; restart/live loops require explicit package authority.

## Boundary

No email, Gmail/browser/Coupa access, portal submit, ledger post/mutation, paid marking, source workbook mutation, PDF export, credential/secret use, external LLM invocation, local model runtime connection, provider expansion, worker spawn, live loop, git push, or merge authority is granted here.
