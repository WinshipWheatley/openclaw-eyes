# Authority Semantics

Status: UNKNOWN

## Short human summary
This page explains the deterministic authority field semantics used by Event Bridge and related finance workflow guards.

## Confirmed facts
- Authority Semantics Registry is the canonical source for prohibition flag and authority grant polarity.
- `no_*` fields are prohibition flags; true means the action is prohibited.
- `*_allowed` fields are authority grants; true means the action is allowed only by the active profile.
- `no_browser=true` belongs in safety_flags or a top-level compatibility guard, not authority_boundary.
- If unsafe authority drift is detected, Event Bridge blocks the envelope and returns positive replacement guidance.
- Registry status: DETERMINISTIC_AUTHORITY_SEMANTICS_REGISTRY_NO_EXECUTION.
- Authority semantics version: authority_semantics_v0.
- no_browser family: PROHIBITION_FLAG.
- browser_access_allowed family: AUTHORITY_GRANT.
- Positive templates: 7.
- Golden fixtures: 7.

## Known unknowns
- none

## Tension / contradiction signals
- none

## Next useful actions
- event_bridge_finance_workflow_action_template
- event_bridge_finance_response_template
- live_arts_prepare_pdf_event_template
- telegram_finance_command_template
- mac_app_event_bridge_writer_template
- mac_excel_helper_authority_template
- guardian_receipt_required_mutation_template

## What not to do
- Do not put no_* prohibition flags inside authority_boundary.
- Do not silently rewrite unsafe live envelopes into safe envelopes.
- Do not grant dangerous *_allowed authority without an explicit receipt-gated profile.
- Do not use legacy chat cards as live finance action sources.

## Source refs / input read-model refs
- generated/read_models/openclaw_authority_semantics_registry.json (authority_semantics_registry)
- generated/read_models/openclaw_business_object_layer_audit.json (business_object_layer_audit)

Last generated timestamp: 2026-05-31T21:39:09+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
