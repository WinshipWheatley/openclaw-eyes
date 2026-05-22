# Post-Security Governance Batch Manifest v0

## ELIWINSHIP Summary

This closes the PC-only governance batch. Prompt 1 preserved the parked autonomous capital R&D experiment. Prompt 2 added the Security Delta Review Contract. Prompt 3 added the Operator Attention Promotion Contract. Prompt 4 added the Chief Test Harness / Cross-Off Receipt Contract. Prompt 5 validates and checkpoints the batch, refreshes the stable map once, stages the bundle for Mac import, and leaves actual Mac import to `mac_map_import_agent`.

## Batch Status

- Batch id: `post_security_governance_batch_v0`.
- Status: `COMPLETE_PENDING_STABLE_MAP_IMPORT`.
- Current prompt: `5` of `5`.
- Stable-map refresh deferred: `false`.
- Commit deferred until Prompt 5: `false`.
- Next expected actor: `mac_map_import_agent`.

## Planned Lanes

- `parked_autonomous_capital_pipeline_experiment`: Prompt 1 - Batch Manifest + Parked R&D Experiment. Status: `COMPLETED_PROMPT_1`.
- `security_delta_review_contract`: Prompt 2 - Security Delta Review Contract. Status: `COMPLETED_PROMPT_2`.
- `operator_attention_promotion_contract`: Prompt 3 - Operator Attention Promotion Contract. Status: `COMPLETED_PROMPT_3`.
- `chief_test_harness_cross_off_receipt_contract`: Prompt 4 - Chief Test Harness / Cross-Off Receipt Contract. Status: `COMPLETED_PROMPT_4`.
- `integrated_checkpoint_and_stable_map_refresh`: Prompt 5 - Integrated Checkpoint and Stable Map Refresh. Status: `COMPLETED_PROMPT_5_PENDING_MAC_IMPORT`.

## Completed So Far

- `parked_autonomous_capital_pipeline_experiment`: `PROMPT_1_EXPORT_VALIDATION_TARGET`.
- `security_delta_review_contract`: `PROMPT_2_EXPORT_VALIDATION_TARGET`.
- `operator_attention_promotion_contract`: `PROMPT_3_EXPORT_VALIDATION_TARGET`.
- `chief_test_harness_cross_off_receipt_contract`: `PROMPT_4_EXPORT_VALIDATION_TARGET`.
- `integrated_checkpoint_and_stable_map_refresh`: `PROMPT_5_BATCH_CLOSURE_PENDING_MAC_IMPORT`.

## Boundary

- `live_execution_allowed` = `false`
- `model_api_execution_allowed` = `false`
- `actor_agent_activation_allowed` = `false`
- `tool_execution_allowed` = `false`
- `browser_oauth_account_access_allowed` = `false`
- `financial_payment_account_access_allowed` = `false`
- `send_submit_approval_allowed` = `false`
- `runtime_planner_builder_queue_autonomy_execution_allowed` = `false`
- `mission_control_app_changes_allowed` = `false`
- `mac_sync_import_allowed` = `false`
- `network_operation_allowed` = `false`
- `git_push_pull_fetch_allowed` = `false`
- `stable_map_refresh_allowed_before_prompt_5` = `false`
- `commit_allowed_before_prompt_5` = `false`
- `staging_allowed_before_prompt_5` = `false`

## Next Prompt

- `Mac map import/sync agent`.

## Machine Proof

- Planned lane count: `5`.
- Prompt 1 lane marked complete: `true`.
- Prompt 2 lane marked complete: `true`.
- Prompt 3 lane marked complete: `true`.
- Prompt 4 lane marked complete: `true`.
- Prompt 5 lane marked complete pending Mac import: `true`.
- Authority boundary all false: `true`.
- Stable map refresh required: `true`.
- Mac import performed: `false`.
- Content hash: `sha256:c3ab571060d8ed517125352ea20645654fd4ecbf47c1392e3100babeeea303b7`.
