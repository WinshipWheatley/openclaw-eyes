# Purpose-Bound Automation Charter

## Evidence:
- Charter count: `6`
- High-level risk levels: `high, low, medium`
- Default-on modules: `gig_manager, gig_outfit, invoice_manager, client_comms`

## Purpose-bounded contracts:

### charter_gig_manager_v0
Module/Workflow: `gig_manager` / `gig_manager_workflow`
Purpose: Track scheduled gigs, prep requirements, location proof, and invoice readiness.
Customer summary: This module checks location only during scheduled gig windows for check-in and mileage proof.
Allowed windows: Within each scheduled gig event window only.
Data sources: calendar_events, invoice_state.
Sensors: phone_location_point.
Forbidden actions: all_day_or_continuous_location_tracking, infer_private_life_context.
Forbidden inferences: daily_route patterning outside gig windows, relationship inference outside gig context.
- Required controls: `pause, revoke, inspect`

### charter_gig_outfit_laundry_v0
Module/Workflow: `gig_outfit` / `gig_outfit_workflow`
Purpose: Prepare stage/gig clothing and keep outfit logistics bounded.
Customer summary: This module can remind for wash/dry/hang steps and mark gig clothing as ready.
Allowed windows: Two-day pre-gig prep lookback and active gig-prep session only.
Data sources: outfit_task_list, washer_dryer_integration.
Sensors: outfit_task_state.
Forbidden actions: judge_habitual_laundry_patterns, track_clothing_choices_outside_gig_scope.
Forbidden inferences: household_routine_inference, long_term_preference_profileing.
- Required controls: `pause, revoke, inspect`

### charter_invoice_manager_v0
Module/Workflow: `invoice_manager` / `invoice_manager_workflow`
Purpose: Generate, send, and watch invoice states with explicit receipts.
Customer summary: This module tracks scoped invoice workflow states and payment watch after proof.
Allowed windows: Only while invoice workflow steps are active.
Data sources: invoice_state, invoice_thread_state.
Sensors: workflow_state_sensor.
Forbidden actions: mark_sent_without_receipt, mark_paid_without_receipt, mutate_ledger_silently.
Forbidden inferences: infer_cashflow_capacity_from_unrelated_threads, infer_client_financial_behavior_without_context.
- Required controls: `pause, revoke, inspect`

### charter_client_comms_clara_v0
Module/Workflow: `client_comms` / `client_comms_workflow`
Purpose: Draft and respond inside owned client threads while blocking broad inference.
Customer summary: This module watches only the approved Clara-owned threads and asks for approval before sending.
Allowed windows: Scoped thread-window context only.
Data sources: clara_owned_threads, scoped_message_headers.
Sensors: thread_membership_sensor.
Forbidden actions: auto_reply_outside_owned_thread, read_all_client_email_as_surveillance, invent_contact_or_sender_data.
Forbidden inferences: general_client_behavior_inference, private_thread_preference_modeling.
- Required controls: `pause, revoke, inspect`

### charter_phone_location_proof_v0
Module/Workflow: `phone_location_proof` / `phone_location_proof_workflow`
Purpose: Produce arrival and mileage proofs without broad location tracking.
Customer summary: This module uses location for arrival/check-in proof only during declared event windows.
Allowed windows: Declared event/proof window only.
Data sources: phone_location, event_reference.
Sensors: phone_location_point, location_precision_hint.
Forbidden actions: continuous_background_location_tracking, unscoped_geofence_recording, customer_mode_hidden_tracking.
Forbidden inferences: home_location_inference, social_patterning_without_invoice_context.
- Required controls: `pause, revoke, inspect`

### charter_washer_dryer_integration_v0
Module/Workflow: `washer_dryer_integration` / `washer_dryer_workflow`
Purpose: Read workflow-owned washer/dryer state through approved integrations only.
Customer summary: Device state is read only through approved integrations when this workflow is active.
Allowed windows: Active workflow window only.
Data sources: homekit, home_assistant, matter, manufacturer_api.
Sensors: washer_state, dryer_state, cycle_state.
Forbidden actions: scrape_private_devices, credential_bypass, network_intrusion, cross_workflow_device_reuse.
Forbidden inferences: household_behavior_profileing, unowned_device_lifecycle_tracking.
- Required controls: `pause, revoke, inspect`

## Boundary:
- Contracted paths are metadata only and scope-bound.
- No live location polling, email polling, device intrusion, invoice generation, ledger writes.
- No model/tool/agent/runtime execution is performed in this contract.
- All external actions require receipts and explicit operator controls.

## Machine proof:
- All authority flags false: `true`
- Required fields present: `true`
- Content hash: `sha256:fe8337ac83ed5ea000d5f388497bfd0b646e10084cd8090184b51e80a0f587bf`

## Next safe move:
Keep automation bounded to purpose + workflow scope. Add new charters only by adding explicit examples, receipts, and controls.
