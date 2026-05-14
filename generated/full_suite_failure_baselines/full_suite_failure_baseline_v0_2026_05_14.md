# Full-Suite Failure Baseline v0

Generated: `2026-05-14T00:05:36-04:00`
Repo root: `/home/openclaw`
Lane: `Full-Suite Failure Baseline v0 - Classification Only`

This baseline records the current full-suite failure landscape. It does not fix tests, install packages, change runtime behavior, alter generated read-model contracts, activate agents, run Docker/Ollama, or call network APIs.

## Commands

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q`
   - Result: collection stopped with exit code `2`.
   - Blocker: `tests/test_cassandra_voice.py` imports `numpy`, which is not installed.
   - Boundary: `numpy` was not installed.

2. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q --ignore=tests/test_cassandra_voice.py --tb=short --junitxml=/tmp/openclaw_full_suite_ignore_voice.xml`
   - Result: exit code `1`.
   - Summary: `83 failed, 2623 passed, 1 skipped in 422.64s`.

## Baseline Interpretation

- The normal full suite is currently collection-blocked by the missing `numpy` dependency in `tests/test_cassandra_voice.py`.
- With only that file ignored, the current executable baseline is `83 failed, 2623 passed, 1 skipped`.
- This supersedes the earlier remembered `82 failed, 2624 passed, 1 skipped` observation for the current workspace state.
- No failures were observed in the recent Corpus Atlas, Evidence Kettle, Tool Inventory, Tool Intake, or Context Selection scoped test files during this voice-ignored full-suite run.

## Classification Summary

| Classification | Count | Meaning |
| --- | ---: | --- |
| `artifact_checkpoint_generated_status_length` | 1 | Generated status artifact-receipt section is longer than the older static line-count contract. |
| `chief_failure_report_copy_contract_drift` | 1 | Chief failure investigation output changed from older manual-fix copy to queued/auditable copy. |
| `cli_subprocess_import_path_failures` | 11 | Subprocess CLI tests launch scripts without repo import path, causing business_ops_ledger import failure and empty JSON output. |
| `dashboard_output_contract_drift` | 2 | Dashboard/headroom tests expect older helper names or section headings. |
| `docs_static_contract_drift` | 2 | Static documentation tests expect older required phrases/sections. |
| `environment_external_fixture_or_dependency` | 3 | Local external fixture/package is absent; no package or fixture was installed. |
| `future_action_behavior_contract_drift` | 1 | Future-action behavior no longer raises or routes exactly as the older test expects. |
| `identity_contact_fixture_drift` | 7 | Identity/contact matching tests return None against current fixtures/state. |
| `morning_orchestration_script_exit` | 1 | Morning orchestration smoke command exits nonzero under current environment/state. |
| `orientation_payment_status_context_contract_drift` | 11 | Cassandra/payment/orientation status tests expect older route output or stale relative-date context. |
| `outreach_state_fixture_accumulation` | 1 | Outreach wrapper smoke sees accumulated outbound records rather than the older single-record fixture. |
| `router_precedence_contract_drift` | 1 | Approval-code parsing currently precedes the older CPA route expectation for this phrase. |
| `test_double_signature_drift` | 39 | Tests patch older call signatures while runtime now passes metadata or ops_packet keyword arguments. |
| `timeout_copy_contract_drift` | 2 | Listener timeout copy changed from older escalation wording. |

## Failing Modules

| Test module | Failures |
| --- | ---: |
| `tests.test_inner_circle_integration` | 29 |
| `tests.test_file_verify_e2e` | 9 |
| `tests.test_cassandra_payment_verify` | 6 |
| `tests.test_query_file_inventory` | 6 |
| `tests.test_payment_verify_brain_wire` | 4 |
| `tests.test_query_canonical_facts` | 4 |
| `tests.test_cassandra_connectors` | 3 |
| `tests.test_future_action_e2e` | 3 |
| `tests.test_send_truth.TestCassandraRouterPolicy` | 3 |
| `tests.test_cassandra_listener_timeout` | 2 |
| `tests.test_cut4_outreach_helpers.TestBrainWrapperSmoke` | 2 |
| `tests.test_dashboard_headroom` | 2 |
| `tests.test_artifact_checkpoint_receipts` | 1 |
| `tests.test_cassandra_email_draft_and_payment_routing.TestCassandraEmailDraftAndPaymentRouting` | 1 |
| `tests.test_chief_cassandra_failure` | 1 |
| `tests.test_chief_router_table` | 1 |
| `tests.test_evidence_map_taxonomy` | 1 |
| `tests.test_morning_orchestration` | 1 |
| `tests.test_orientation_snapshot` | 1 |
| `tests.test_query_truth_registry` | 1 |
| `tests.test_runtime_service_model_backlog_static_contract` | 1 |
| `tests.test_send_truth.TestCalendarDeleteRouting` | 1 |

## Collection Blocker

- `tests/test_cassandra_voice.py`: `ModuleNotFoundError: No module named 'numpy'`.

## Failure Inventory

### `artifact_checkpoint_generated_status_length` (1)
- `tests.test_artifact_checkpoint_receipts::test_generated_status_surfaces_module_atlas_artifact_receipts` - AssertionError: assert 32 <= 11

### `chief_failure_report_copy_contract_drift` (1)
- `tests.test_chief_cassandra_failure::test_investigate_timeout_reports_pending_approval` - assert 'Outcome: Winship must fix it manually' in "Chief investigated Cassandra's failure for: Can you email Winship and ask if it worked?\n\nOutcome: Chief can queue/a...act next step: I queued chief-cassandra-failure-20260513T235844 to in

### `cli_subprocess_import_path_failures` (11)
- `tests.test_query_canonical_facts::test_query_by_source` - AssertionError: assert 1 == 0
- `tests.test_query_canonical_facts::test_query_by_heading` - AssertionError: assert 1 == 0
- `tests.test_query_canonical_facts::test_no_filter_fails` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- `tests.test_query_canonical_facts::test_missing_db_fails` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- `tests.test_query_file_inventory::test_cli_requires_db` - assert 'the following arguments are required: --db' in 'Traceback (most recent call last):\n  File "/home/openclaw/scripts/query_file_inventory.py", line 5, in <module>\n    from business_ops_ledger import (\nModuleNotFoundError: No module 
- `tests.test_query_file_inventory::test_cli_requires_filter` - assert 'one of the arguments --root-id --extension --file-name is required' in 'Traceback (most recent call last):\n  File "/home/openclaw/scripts/query_file_inventory.py", line 5, in <module>\n    from business_ops_ledger import (\nModuleN
- `tests.test_query_file_inventory::test_query_by_root_id` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- `tests.test_query_file_inventory::test_query_by_extension` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- `tests.test_query_file_inventory::test_query_by_name` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- `tests.test_query_file_inventory::test_missing_db_fails` - assert 'Error: Database not found' in 'Traceback (most recent call last):\n  File "/home/openclaw/scripts/query_file_inventory.py", line 5, in <module>\n    from business_ops_ledger import (\nModuleNotFoundError: No module named \'business_
- `tests.test_query_truth_registry::test_query_filters` - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

### `dashboard_output_contract_drift` (2)
- `tests.test_dashboard_headroom::test_window1_outputs_use_stable_folder_and_names` - AttributeError: module 'dashboard_gen' has no attribute '_window1_outputs'. Did you mean: '_winship_outputs'?
- `tests.test_dashboard_headroom::test_ai_companion_generators_emit_dense_diagnostic_sections` - assert '# For AI 1' in '# AI Right now - Loop Diagnostics\n*Updated: 2026-05-13 23:59:57*\n\n## Status Snapshot\n```json\n{\n  "pass": 1,\n  ...\n## Queue and Completion\n- Successful loop cycles: 3\n- Completed meaningful tasks: 2\n- Next 

### `docs_static_contract_drift` (2)
- `tests.test_evidence_map_taxonomy::test_evidence_map_sections` - AssertionError: Evidence Map doc missing required section: ## 6. Future Growth Pattern
- `tests.test_runtime_service_model_backlog_static_contract::test_service_management_freeze_is_runtime_neutral_and_ordered` - AssertionError: assert 'Do not expand any of these controls in this slice' in '# OpenClaw Service Management Freeze\n\n_Created: 2026-04-29. Runtime-neutral documentation freeze only._\n\nThis doc...tion, or process ownership change must be

### `environment_external_fixture_or_dependency` (3)
- `tests.test_cassandra_connectors::test_financial_log_file_exists` - AssertionError: FINANCIAL_LOG_CONNECTED is True but log file is missing: /mnt/c/OpenClaw/logs/expense_log.json
- `tests.test_cassandra_connectors::test_financial_log_valid_json` - AssertionError: Missing expense log: /mnt/c/OpenClaw/logs/expense_log.json
- `tests.test_cassandra_connectors::test_invoice_pdf_reportlab_importable` - AssertionError: Module not found: reportlab

### `future_action_behavior_contract_drift` (1)
- `tests.test_future_action_e2e::test_sender_error_leaves_item_pending` - Failed: DID NOT RAISE <class 'ConnectionError'>

### `identity_contact_fixture_drift` (7)
- `tests.test_cut4_outreach_helpers.TestBrainWrapperSmoke::test_brain_match_outbound_email_record_delegates` - assert None is not None
- `tests.test_inner_circle_integration::test_a1_dad_identified_by_name` - assert None is not None
- `tests.test_inner_circle_integration::test_a2_mom_identified_by_name` - assert None is not None
- `tests.test_inner_circle_integration::test_a3_draper_identified_by_name` - assert None is not None
- `tests.test_inner_circle_integration::test_a5_sampleclient_not_treated_as_inner_circle` - assert None is not None
- `tests.test_inner_circle_integration::test_a6_contact_identified_by_chat_id_when_pinned` - assert None is not None
- `tests.test_inner_circle_integration::test_e3_client_tier_treated_differently_from_inner_circle` - assert None is not None

### `morning_orchestration_script_exit` (1)
- `tests.test_morning_orchestration::test_morning_orchestration_trigger` - assert 1 == 0

### `orientation_payment_status_context_contract_drift` (11)
- `tests.test_cassandra_payment_verify::test_hilton_status_question_routes_directly_from_finance_state` - assert ['--- OpenCla...on snapshot.'] == ['Two Capital... SmartSpend.']
- `tests.test_cassandra_payment_verify::test_session_fact_correction_overrides_stale_finance_status_in_followup` - assert ['--- OpenCla...on snapshot.'] == ['Waiting for...ome through.']
- `tests.test_cassandra_payment_verify::test_implicit_same_session_correction_uses_last_finance_entity` - assert 'Chyna' in '--- OpenClaw Orientation Status ---\nBased on the latest deterministic surfaces:\n\n* Active Lane:\nHardening the "Bu...nd explicit operator promotions.\n\nNOTE: No live runtime health is claimed. This is a read-only orie
- `tests.test_cassandra_payment_verify::test_st_annes_general_status_uses_recurring_lane` - assert 'recurring Sunday-services and parish-tech lane' in '--- OpenClaw Orientation Status ---\nBased on the latest deterministic surfaces:\n\n* Active Lane:\nHardening the "Bu...nd explicit operator promotions.\n\nNOTE: No live runtime he
- `tests.test_cassandra_payment_verify::test_live_arts_general_status_uses_recurring_lane` - assert 'event-based and rental-based lane' in '--- OpenClaw Orientation Status ---\nBased on the latest deterministic surfaces:\n\n* Active Lane:\nHardening the "Bu...nd explicit operator promotions.\n\nNOTE: No live runtime health is claim
- `tests.test_cassandra_payment_verify::test_build_context_snapshot_ignores_stale_relative_day_noise` - AssertionError: assert 'the next day cleaning company at 9:30' in 'Time: late night (2026-05-13 23:58, EDT)\nRelative date anchors: yesterday is 2026-05-12 (Tuesday); today is 2026-05-...d event match.\n\nSENTRY: target timestamp passed - r
- `tests.test_orientation_snapshot::test_render_markdown_truth_summary` - AssertionError: assert '## 4. Truth Substrate Status' in '# OpenClaw Orientation Snapshot v0\n*Generated: 2026-05-12T12:00:00*\n\n## 1. Where are we?\n- **CWD**: `/home/opencl... 11. North Star\nNone\n\n## 12. Manifesto / Anti-Slop Posture\
- `tests.test_payment_verify_brain_wire::test_handler_gmail_found` - AssertionError: assert 'verified a matching notification' in 'You confirmed the first Capital Hilton payment was received in full: 400 dollars via Venmo from Chyna Hardin on 2026-...for Will Valcovic to talk to Chyna on Monday and get two t
- `tests.test_payment_verify_brain_wire::test_handler_gmail_missing_log_found` - assert "don't see a Gmail notification" in 'You confirmed the first Capital Hilton payment was received in full: 400 dollars via Venmo from Chyna Hardin on 2026-...for Will Valcovic to talk to Chyna on Monday and get two to three Capital Hi
- `tests.test_payment_verify_brain_wire::test_handler_nothing_found` - assert "didn't see any matching that payment yet" in 'You confirmed the first Capital Hilton payment was received in full: 400 dollars via Venmo from Chyna Hardin on 2026-...for Will Valcovic to talk to Chyna on Monday and get two to three 
- `tests.test_payment_verify_brain_wire::test_payment_verify_connected_flag` - assert False is True

### `outreach_state_fixture_accumulation` (1)
- `tests.test_cut4_outreach_helpers.TestBrainWrapperSmoke::test_brain_load_outbound_email_records_delegates` - AssertionError: assert 106 == 1

### `router_precedence_contract_drift` (1)
- `tests.test_chief_router_table::test_routing_precedence_table[what did i make-cpa_query]` - AssertionError: route_message('what did i make') returned intent='approval_response', expected 'cpa_query'

### `test_double_signature_drift` (39)
- `tests.test_cassandra_email_draft_and_payment_routing.TestCassandraEmailDraftAndPaymentRouting::test_payment_verify_route_bypasses_llm` - TypeError: TestCassandraEmailDraftAndPaymentRouting.test_payment_verify_route_bypasses_llm.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_e2e_existing_file_through_handle` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_e2e_nonexistent_file_through_handle` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_e2e_no_path_returns_guidance` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_disconnected_capability_honest_reply` - TypeError: stub_side_effects.<locals>.<lambda>() got an unexpected keyword argument 'ops_packet'
- `tests.test_file_verify_e2e::test_no_false_certainty_claims` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_tool_error_graceful_reply` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_non_matching_input_falls_through` - TypeError: stub_side_effects.<locals>.<lambda>() got an unexpected keyword argument 'ops_packet'
- `tests.test_file_verify_e2e::test_no_unrelated_state_mutation` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_file_verify_e2e::test_route_string_is_file_verify` - TypeError: stub_side_effects.<locals>._capture() got an unexpected keyword argument 'metadata'
- `tests.test_future_action_e2e::test_brain_routes_future_action_correctly` - TypeError: _install_brain_stubs.<locals>.fake_log() got an unexpected keyword argument 'metadata'
- `tests.test_future_action_e2e::test_non_matching_input_falls_through` - TypeError: _install_brain_stubs.<locals>.<lambda>() got an unexpected keyword argument 'ops_packet'
- `tests.test_inner_circle_integration::test_b1_dad_allowed_topic_falls_through_to_handler` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b2_mom_caution_topic_holds_for_winship` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b3_dad_escalation_topic_escalates` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b4_draper_allowed_operational_topic` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b5_draper_caution_family_topic_holds` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b5b_draper_financial_query_escalates_per_spec` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b6_pii_request_always_escalates` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_b7_winship_own_message_skips_gate` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_c1_email_send_success_says_sent_only_after_ok` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_c2_email_send_denied_does_not_say_sent` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_c3_email_send_failure_reports_honestly` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_c4_outreach_partial_send_is_honest` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_c5_email_draft_prompt_does_not_say_sending` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_d1_future_action_disconnected_honest_reply` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_d2_pii_vault_disconnected_honest_reply` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_d3_multiple_capabilities_disconnected_does_not_crash` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_d4_notify_failure_does_not_block_gate_reply` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_e1_unknown_sender_not_routed_as_inner_circle` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_e2_name_match_with_wrong_chat_id_gets_identity_challenge` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_f1_correspondence_log_written_on_send_success` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_f4_outreach_draft_log_uses_truthful_route` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_f2_correspondence_log_written_on_send_failure` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_inner_circle_integration::test_f3_correspondence_log_marks_broker_exception_as_send_failed_per_spec` - TypeError: stub_side_effects.<locals>._capture_route() got an unexpected keyword argument 'metadata'
- `tests.test_send_truth.TestCalendarDeleteRouting::test_handle_routes_exact_delete_request_to_calendar_delete` - TypeError: TestCalendarDeleteRouting.test_handle_routes_exact_delete_request_to_calendar_delete.<locals>.<lambda>() got an unexpected keyword argument 'metadata'
- `tests.test_send_truth.TestCassandraRouterPolicy::test_handle_gmail_metadata_context_passes_cloud_ok_false` - TypeError: TestCassandraRouterPolicy._patch_handle_to_llm_path.<locals>.<lambda>() got an unexpected keyword argument 'metadata'
- `tests.test_send_truth.TestCassandraRouterPolicy::test_handle_payment_gmail_notification_context_passes_cloud_ok_false` - TypeError: TestCassandraRouterPolicy._patch_handle_to_llm_path.<locals>.<lambda>() got an unexpected keyword argument 'metadata'
- `tests.test_send_truth.TestCassandraRouterPolicy::test_handle_calendar_fallback_logs_llm_deep_without_name_error` - TypeError: TestCassandraRouterPolicy.test_handle_calendar_fallback_logs_llm_deep_without_name_error.<locals>.<lambda>() got an unexpected keyword argument 'metadata'

### `timeout_copy_contract_drift` (2)
- `tests.test_cassandra_listener_timeout::test_timeout_contract_escalates_after_timeout` - assert ['Cassandra i... the result.'] == ['Cassandra i... went wrong.']
- `tests.test_cassandra_listener_timeout::test_timeout_contract_delivers_late_success_once` - assert ['Cassandra i... at 2:30 PM.'] == ['Cassandra i... at 2:30 PM.']

## Operator Notes

- Treat these failures as known baseline debt unless a future lane touches the matching module, route, CLI, fixture, or document contract.
- Do not treat this report as approval to install dependencies, restore external files, alter Cassandra live connector behavior, or relax static contracts.
- Future implementation lanes should compare their scoped failures against this baseline before claiming regressions.
- The full-suite run left or confirmed untracked `polish_loop/tasks/chief-cassandra-failure-*.md` files in the workspace; this lane did not delete or modify them.
