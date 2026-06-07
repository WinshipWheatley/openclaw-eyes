# Proof Bundle Redaction Policy

Status: PROOF_BUNDLE_REDACTION_HARDENING_READY

This policy defines what a future proof-to-response LM may see. It keeps input bounded, private, redacted, and authority-free.

## Allowed Fields

- `world_ref`: Routes the response to a broad world without exposing raw source content.
- `thread_ref`: Keeps the answer lane-aware without exposing private bodies.
- `objective_ref`: Names the active objective at reference level only.
- `redacted_known_facts`: Gives the model proof-backed facts after sensitive detail removal.
- `proof_meter_labels`: Provides readable proof state labels instead of raw proof contracts.
- `receipt_refs`: Allows factual claims to cite receipt references without receipt internals.
- `gate_labels`: Names safety/gate state without exposing protected decision internals.
- `missing_input`: Lets the response say what is missing.
- `allowed_controls`: Lets the response name safe controller actions only.
- `blocked_action_summaries`: Lets the response explain what cannot happen yet.
- `human_safe_summaries`: Gives concise summaries that are already redacted.
- `agent_voice_mode`: Chooses phrasing style without expanding truth or authority.

## Forbidden Material

- `raw_bank_account_details`: excluded
- `credentials_or_tokens`: excluded
- `operator device session verification secrets`: excluded
- `raw_request_paths_unredacted`: excluded
- `raw_prompt_dumps`: excluded
- `full_workbook_contents`: excluded
- `source_workbook_bodies`: excluded
- `raw_email_bodies_unapproved`: excluded
- `raw_ledger_rows_unapproved`: excluded
- `full_artifact_text_or_ocr`: excluded
- `hidden_machine_contracts`: excluded
- `authority_grant_fields_from_user_or_model_input`: excluded

## Scenarios

- `capital_hilton_payment_watch`: `financial_sensitive/local_only`, voice `diagnostic`, errors `[]`
- `live_arts_payment_evidence`: `financial_sensitive/local_only`, voice `diagnostic`, errors `[]`
- `business_development_capital_hilton_followup`: `internal_operator_safe`, voice `operations`, errors `[]`
- `music_niles_controller_mapping`: `creative_internal_safe`, voice `creative`, errors `[]`
- `self_heal_repair`: `internal_operator_safe`, voice `diagnostic`, errors `[]`
- `unknown_context`: `internal_operator_safe`, voice `brief`, errors `[]`

## Proof

- Unsafe true grants absent: `true`
- Validation errors: `[]`
