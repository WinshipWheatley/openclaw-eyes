# Project Room Sourceset Contract

Status: PROJECT_ROOM_SOURCESET_CONTRACT_READY

This contract says serious OpenClaw work starts by building the room: source inventory first, conflicts and gaps surfaced before synthesis, and receipts outranking generated summaries.

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

## Rules

- Do not synthesize final output until source inventory exists.
- Do not treat old versions as current.
- Do not delete duplicates automatically.
- Do not let duplicated docs overweight synthesis.
- Do not use missing context as permission to invent.
- Do not let generated summaries outrank receipts.
- Project room may stage a package only after source room gates are satisfied.

## Project Rooms

- `finance_capital_hilton_payment_watch`: synthesis `true` (explanation_and_next_step_only); allowed: explain payment-watch state, ask for payment evidence, stage next-step wording; blocked: mark paid, mutate ledger, export PDF, read workbook cells as proof
- `business_development_capital_hilton_follow_up`: synthesis `false` (blocked_until_conflict_or_operator_decision_resolves); allowed: surface proposal/follow-up conflict, ask for current receipt, draft only after source gate; blocked: send follow-up, claim follow-up sent, silently resolve status conflict
- `build_review_packet`: synthesis `true` (historical_summary_only); allowed: summarize historical packet, cite prior review decision, ask if reopened; blocked: treat resolved packet as active work, show as ready-for-review
- `niles_music_controller_mapping`: synthesis `true` (creative_options_only); allowed: offer creative options, ask for controller/software target; blocked: make factual controller claims, import unrelated finance proof, claim integration exists
- `self_heal_repair`: synthesis `true` (repair_package_proposal_only); allowed: propose repair package with validation plan, name blocker proof, include rollback plan; blocked: execute repair, restart services, claim repair success without receipt
- `stale_source`: synthesis `false` (blocked_or_needs_verification); allowed: mark Needs verification, ask for current source, preserve originals as history; blocked: final synthesis, current truth claim, delete older versions

## Conflicts

- `conflict:bd_proposal_follow_up_status`: Proposal status and follow-up status disagree or are not proven by the same current receipt.
- `conflict:stale_summary_vs_current_truth`: Stale generated summary and older source version cannot establish current truth.

## Missing Context

- `missing_context:finance_payment_evidence`: Payment evidence is missing. Safe wording: Payment evidence is missing; I can explain the watch state and next step, but cannot mark paid.
- `missing_context:bd_send_authority`: No send authority is present. Safe wording: I can prepare a draft or list missing context, but I cannot send it.
- `missing_context:niles_controller_target`: Software/controller target is absent. Safe wording: I can offer creative mapping options and questions; I cannot make factual controller claims without a source.
- `missing_context:stale_current_source`: Current source or receipt is missing. Safe wording: This source appears stale and needs verification before final synthesis.

## Duplicate / Version Families

- `version_family:finance_payment_watch`: likely current `source:finance_payment_watch_state`, deletion allowed `false`
- `version_family:bd_capital_hilton_follow_up`: likely current `operator_decision_required`, deletion allowed `false`
- `version_family:build_review_packet`: likely current `source:build_resolved_review_packet`, deletion allowed `false`
- `version_family:niles_music_controller_mapping`: likely current `source:niles_creative_notes`, deletion allowed `false`
- `version_family:self_heal_repair`: likely current `source:self_heal_blocker_proof`, deletion allowed `false`
- `version_family:stale_source`: likely current `current_source_missing`, deletion allowed `false`

## Authority

- Authority order: current_receipts_and_proof > operator_decisions_with_receipts > preserved_original_sources > current_source_inventory_rows > generated_summaries > memory_hints
- Current receipts/proof beat generated summaries and memory hints.
