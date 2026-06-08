# Project Room Sourceset Contract

Status: PROJECT_ROOM_SOURCESET_CONTRACT_READY

The first step for serious work is to build the room: inventory sources, surface conflicts, name missing context, identify duplicate/version families, and apply freshness and authority before synthesis.

## Core Doctrine

- First prompt for serious work is not do the thing.
- First step is build the room.
- Originals are preserved.
- Source inventory is created before synthesis.
- Conflicts are surfaced before drafting.
- Missing context is named before invention.
- Duplicates and version families are identified before weighting.
- Authority and freshness are explicit.
- Agent may not silently resolve contradictions.
- Memory is a hint, not truth.
- Current receipts and proof beat generated summaries.
- Large files and logs are previewed or referenced, not dumped into model context.

## Project Room Fields

- `project_room_id`
- `objective_ref`
- `world_ref`
- `thread_ref`
- `workspace_scope`
- `source_set_ref`
- `source_inventory_ref`
- `conflict_log_ref`
- `missing_context_ref`
- `duplicate_report_ref`
- `decision_trace_ref`
- `authority_ranking_ref`
- `freshness_gate_ref`
- `compaction_policy_ref`
- `allowed_next_steps`
- `blocked_next_steps`
- `synthesis_allowed`

## Source Inventory

- `source:finance:capital_hilton:payment_watch_receipt` (current, receipt_backed): payment_processor_processing, paid_false, ledger_untouched, payment_evidence_missing
- `source:finance:capital_hilton:generated_payment_summary` (historical, generated_summary): may_explain_payment_watch
- `source:bd:capital_hilton:proposal_status` (current, receipt_backed): proposal_followup_state_known, draft_can_be_staged
- `source:bd:capital_hilton:older_followup_note` (stale, unpromoted_memory): possible_followup_status
- `source:build:review_packet_resolved` (historical, receipt_backed): review_packet_informational_or_resolved, prior_review_decision_exists
- `source:niles:music_controller_notes` (current, operator_reported): creative_goal, controller_mapping_target_if_supplied
- `source:self_heal:repair_blocker_validation` (current, validation_backed): blocker_named, validation_failure_known, repair_package_needs_validation_plan
- `source:system:large_error_log` (current, artifact_hash): error_log_exists, safe_preview_available
- `source:system:stale_prior_summary` (stale, generated_summary): possible_prior_context

## Conflicts

- `conflict:bd_capital_hilton_followup_status`: Current proposal/follow-up state and older memory hint may disagree.
- `conflict:finance_generated_summary_vs_receipt`: Generated payment summaries may be stale or less precise than current payment-watch receipts.

## Missing Context

- `missing:finance_capital_hilton_payment_evidence`: Payment evidence is missing. Safe wording: Payment evidence is missing; ledger and paid state remain untouched.
- `missing:niles_controller_or_software_target`: Specific controller or software target may be absent. Safe wording: I can sketch creative mapping options, but I need the controller/software target for exact setup guidance.
- `missing:stale_source_refresh`: A stale source lacks a current receipt. Safe wording: Needs verification before I treat this as current.

## Duplicate / Version Report

- `version_family:capital_hilton_payment_watch_summaries`: current `source:finance:capital_hilton:payment_watch_receipt`, deletion allowed `false`
- `version_family:build_review_packet_history`: current `source:build:review_packet_resolved`, deletion allowed `false`

## Required Scenarios

- `finance_capital_hilton_payment_watch`: explanation_and_next_step_only
- `business_development_capital_hilton_followup`: draft_or_explain_followup_only
- `build_review_packet`: historical_summary_only
- `niles_music_controller_mapping`: creative_options_only_until_target_supplied
- `self_heal_repair`: repair_package_with_validation_plan
- `stale_source`: needs_verification_only
- `large_artifact_log_source`: diagnostic_preview_only

## Boundary

This contract is review/read-model work only. It does not invoke models, touch business systems, mutate ledgers/workbooks, mark paid, submit, push, or delete duplicates.
