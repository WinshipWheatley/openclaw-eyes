# Mac Thinning Readiness Map

Status: MAC_THINNING_READINESS_MAP_READY

This map identifies which Mission Control Mac surfaces can thin into backend-authored dynamic cards and which must stay bespoke shell/controller UI.

## Rules

- Do not recommend removing a Mac surface unless dynamic card coverage exists.
- Do not recommend converting if action payload or receipt coverage is missing.
- Shell components stay bespoke.
- Developer Proof stays available but hidden.
- Protected/gate surfaces cannot expose execution.

## Classifications

- `keep_bespoke`: `6`
- `convert_to_dynamic_card_now`: `7`
- `convert_after_v1_parity`: `3`
- `hide_developer_proof`: `1`
- `remove_after_receipt_parity`: `1`
- `needs_backend_contract`: `0`
- `do_not_build`: `1`

## Surfaces

- `helm`: `keep_bespoke` confidence=`high` cards=`not_applicable` actions=`not_applicable`
  - Mac action: Keep as native Mac shell/controller navigation.
  - Early-removal risk: The app loses its primary control frame even if cards render correctly.
- `composer`: `keep_bespoke` confidence=`high` cards=`not_applicable` actions=`not_applicable`
  - Mac action: Keep as native text/input controller; dispatch verified controller events.
  - Early-removal risk: The operator loses the generic command/input surface.
- `world_bank_switcher`: `keep_bespoke` confidence=`high` cards=`not_applicable` actions=`not_applicable`
  - Mac action: Keep as native Mac navigation state.
  - Early-removal risk: Dynamic cards cannot replace global world/bank selection.
- `dynamic_card_renderer`: `keep_bespoke` confidence=`high` cards=`not_applicable` actions=`not_applicable`
  - Mac action: Keep a generic renderer; remove workflow-specific card classes behind it.
  - Early-removal risk: Backend cards exist but have nowhere stable to render.
- `evidence_drop_zone`: `keep_bespoke` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Keep native drop/file-picker UX; let backend cards own receipt/status copy.
  - Early-removal risk: The Mac loses local file-intake affordances even though evidence receipts can render.
- `proof_details_drawer`: `keep_bespoke` confidence=`high` cards=`not_applicable` actions=`covered`
  - Mac action: Keep generic drawer shell; populate contents from proof objects and meters.
  - Early-removal risk: Proof remains generated but not inspectable by the operator.
- `finance_capital_hilton`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace workflow-specific payment-watch/status panels with dynamic cards.
  - Early-removal risk: Low if generic renderer, proof drawer, and native navigation stay bespoke.
- `finance_live_arts_md`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace workflow-specific evidence receipt panel with backend evidence-intake card.
  - Early-removal risk: Medium if native drop zone is removed; low for status panel thinning.
- `business_development_capital_hilton`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace bespoke follow-up/proposal status panel with workflow composer plan card.
  - Early-removal risk: Low while send remains blocked and staging remains receipt-backed.
- `build_review_packets`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace bespoke packet cards with backend review-packet cards once using review action slots.
  - Early-removal risk: Medium if review actions are not routed through deterministic payloads.
- `workrooms`: `convert_after_v1_parity` confidence=`medium` cards=`full` actions=`covered`
  - Mac action: Keep workroom navigation shell; convert packet/status contents after all workroom lanes emit v1 cards.
  - Early-removal risk: High. Workroom shell, routing, and navigation are not just card content.
- `approval_gate_surfaces`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Render gate/approval states as dynamic cards; never expose protected execution from these cards.
  - Early-removal risk: Medium if disabled execution affordances are not preserved.
- `memory_candidates`: `convert_after_v1_parity` confidence=`medium` cards=`full` actions=`covered`
  - Mac action: Use dynamic memory candidate cards for display; keep review controls until promotion actions have parity.
  - Early-removal risk: Medium. Candidate display exists, but promotion/rejection control parity is incomplete.
- `st_annes_work_log_review`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace resolved/test-only bespoke status panel with completed historical receipt card.
  - Early-removal risk: Low for resolved history; keep any future active edit controls separate.
- `workbook_registration`: `convert_to_dynamic_card_now` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Replace bespoke workbook metadata panel with current-focus workbook registration card.
  - Early-removal risk: Low if workbook mutation remains blocked and only metadata refs are shown.
- `developer_proof`: `hide_developer_proof` confidence=`high` cards=`full` actions=`covered`
  - Mac action: Keep available behind explicit proof-depth/detail opt-in; hide by default.
  - Early-removal risk: High. Operators and developers lose source refs, hashes, and receipt details.
- `evidence_drawer`: `convert_after_v1_parity` confidence=`medium` cards=`full` actions=`covered`
  - Mac action: Keep generic drawer shell; convert workflow-specific evidence rows after proof drawer parity.
  - Early-removal risk: Medium. Evidence proof exists, but local file preview and redaction UX must stay intact.
- `legacy_invoice_review_panels`: `remove_after_receipt_parity` confidence=`medium` cards=`full` actions=`covered`
  - Mac action: Remove old workflow-specific panels only after card, receipt, proof-drawer, and action parity are confirmed.
  - Early-removal risk: High. Some legacy invoice states may still lack v1 receipt parity.
- `manual_authority_override`: `do_not_build` confidence=`high` cards=`none` actions=`missing`
  - Mac action: Do not build. Incoming authority_granted remains ignored or rejected.
  - Early-removal risk: No removal risk; the surface should not exist.

## Proof

- Surface count: `19`
- Unsafe true grants absent: `true`
- Validation errors: `0`
