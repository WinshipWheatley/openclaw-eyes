# First Class Operator Envelope

Status: `FIRST_CLASS_OPERATOR_ENVELOPE_READY`

This contract verifies operator controller envelopes from Mission Control-class surfaces.
It proves operator/app/device/session/request integrity only. It does not grant business authority.

## Required Envelope Fields

`envelope_id`, `operator_ref`, `app_instance_ref`, `device_ref`, `device_class`, `session_ref`, `request_hash`, `created_at`, `source_surface`, `current_world_ref`, `current_thread_ref`, `authority_requested`, `operator_verified`, `app_instance_verified`, `device_verified`, `session_verified`, `verification_status`, `proof_refs`

## Backend-Only Fields

`authority_granted`, `gate_decision_ref`, `approval_receipt_ref`

Incoming requests may ask for `authority_requested`, but only backend gates may later produce `authority_granted`.

## Latest Example

- Envelope: `operator_authority_envelope:e0a4f72ec0d9ce66`
- Device: `mac` / `device:macbook`
- Surface: `card`
- Action: `show_details`
- Verification status: `verified`
- Authority requested: `[]`
- Authority granted: `[]`

## Safety

- LMs cannot mint verification fields.
- Local-dev verification is not production authority.
- Business actions still require package, gate, Guardian, and operator review.
- Email, Gmail, browser, Coupa, ledger, workbook, PDF, paid, submit, push, worker, and provider actions remain unavailable from this envelope.
