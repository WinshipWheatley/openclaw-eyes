# Dynamic Surface Unbloat Audit

Status: `DYNAMIC_SURFACE_UNBLOAT_AUDIT_READY`

## Executive Summary

Mission Control can become a thinner controller shell now. The backend already emits dynamic cards, lifecycle policy, action payloads, controller protocol, evidence intake status, Workroom review packets, approval requests, gate decisions, memory candidates, and confidence labels. The remaining bloat risk is that Mac still has to understand workflow-specific card ids and domain-specific layouts.

Recommended direction: backend emits `dynamic_card_packet_v1` with explicit card families, action slots, lifecycle, trust/freshness, proof metadata, and source refs. Mac keeps shell, switching, generic rendering, drop zone, proof drawer, safe dispatch, and compact meters.

## Current Backend Card Inventory

The current `dynamic_card_packet_latest.json` has 8 cards:

- `payment_watch`: Capital Hilton payment watch, active/current, visible, no ledger or paid authority.
- `evidence_intake`: Live Arts MD payment-processing evidence receipt, waiting, operator-reported, not paid.
- `answer`: Capital Hilton contextual question answer, active/current, lane-sourced.
- `review_packet`: build review packet, needs operator, review controls only.
- `status`: Capital Hilton proposal follow-up, stage draft/follow-up only, no send.
- `status`: Chief diagnostic, diagnostic only.
- `workbook_registration`: metadata-only workbook registration, no workbook body or mutation.
- `status`: St. Anne's work-log review, resolved/historical and hidden by default.

## Dynamic Card Families

Required families for v1:

- current focus card
- answer card
- payment-watch card
- evidence-intake receipt card
- approval request card
- review packet card
- workflow composer plan card
- gate/lock card
- memory candidate card
- artifact/proof card
- “what should I do here?” contextual card
- completed/historical receipt card

Each family should define required fields, allowed actions, forbidden actions, lifecycle behavior, trust state, proof refs, Mac rendering needs, and backend data sources. The JSON audit contains the full family matrix.

## Fields Missing From Current Dynamic Card Packet

Most important missing v1 fields:

- `card_family`
- `lane_ref`, `workflow_ref`, `entity_refs`, `object_refs`
- `source_read_model_refs`, `source_statuses`, `source_generated_at`, `source_content_hash`
- `confidence_class`, `confidence_score`
- `visibility_reason`, `attention_cost`, `sort_bucket`, `history_group_ref`
- `developer_proof_only`, `operator_mode_visible`, `machine_contract_visible`
- `action_slots`, `controller_event_type`, `requires_operator_envelope`, `receipt_required`
- `stale_after`, `superseded_by_card_ref`
- categorized proof fields for artifacts, hashes, sqlite refs, sensitive detail policy, and redacted summaries

## Lifecycle/Staleness Rules

- Active and `needs_operator` cards show by default only when they provide the next playable control.
- Resolved cards hide by default after a receipt is recorded.
- Historical cards collapse under Completed / History.
- Stale cards must say Needs verification.
- Proof-only cards are hidden unless requested.
- Workroom cards show only when operator attention is needed.
- Finance payment-watch cards stay visible only while payment evidence is missing.
- Payment-processing evidence becomes waiting evidence, not paid truth.
- No card remains primary if a newer receipt supersedes it.
- Machine-contract cards are hidden in operator mode.

## Generic Actions And Controls

Baseline controls:

- open lane
- ask why
- show details

Decision controls:

- approve
- deny
- request rework
- mark informational
- stop/hold/cancel

Staging/proof controls:

- stage plan
- continue
- attach proof
- mark as test

Every mutating controller event needs a verified operator/app/device/session envelope. Incoming `authority_requested` is a request only. `authority_granted` remains backend-only.

## What Mac Can Strip

Mac can replace these with backend cards:

- Capital Hilton payment-watch card
- Capital Hilton proposal follow-up card
- Live Arts MD evidence receipt card
- St. Anne's work-log review summary
- Workroom review packet cards
- approval request and gate cards
- contextual “what should I do here?” answer cards
- workflow composer plan preview cards
- memory candidate review cards
- completed receipt/history rows

## What Mac Must Keep Bespoke

Mac should keep:

- application shell and window layout
- world/bank switcher and lane navigation state
- Composer input surface
- generic dynamic card renderer
- safe action dispatcher and controller-envelope creation
- evidence drop zone, file picker, and local preview
- proof/details drawer
- compact meters for WIP, approvals, proof, bridge, and service health
- local error/offline/bridge status handling
- accessibility, keyboard focus, and view preferences

## Developer Proof Only

Never operator-primary:

- machine-contract cards
- raw artifact/proof cards
- generated summary-only proof
- completed/historical receipt cards
- test-only evidence
- stale service-status cards without a current receipt
- memory candidates that do not require operator approval
- gate ledger rows that do not explain a current blocker
- WIP/watch metrics without a needed decision

## Recommended Dynamic Card Packet V1 Changes

1. Add required `card_family`.
2. Add normalized lane, workflow, entity, and object refs.
3. Replace action ordering with `action_slots`.
4. Add `controller_event_type`, `requires_operator_envelope`, and `receipt_required`.
5. Expand proof into categorized refs and redacted detail metadata.
6. Add source status/hash/generated-at fields.
7. Add `developer_proof_only`, `machine_contract_visible`, and `operator_mode_visible`.
8. Add confidence class/score from evidence confidence scoring.
9. Add `history_group_ref` and `superseded_by_card_ref`.

## Recommended Mac Thinning Sequence

1. Render existing `dynamic_card_packet_latest.json` cards exclusively through the generic renderer for one pane.
2. Add `card_family` and `action_slots` to backend packet v1 while preserving v0 compatibility.
3. Move approval, gate, workflow composer, memory candidate, and historical receipt surfaces into backend cards.
4. Unify proof/details drawer around categorized proof fields.
5. Retire Mac workflow-specific card code after parity screenshots and controller-event smoke tests.

No runtime code was edited for this audit. No email, Gmail, browser, Coupa, ledger, workbook, PDF, paid marking, submit, worker, or external LLM action was performed.
