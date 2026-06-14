# Agent Voice Routing

Status: `AGENT_VOICE_ROUTING_V0_READY`

This contract assigns deterministic speaker references and voice modes for operator-facing package responses. It is machine-contract shaping, not roleplay.

## Speakers

- `openclaw`
- `cassandra`
- `chief`
- `hermes`
- `guardian`
- `niles`
- `clara`

## Routing Priority

- `guardian_protected_authority_or_access_boundary`
- `clara_external_client_facing_draft`
- `chief_provider_gate_check_engine_diagnostic_route_status`
- `hermes_architecture_doctrine_recommendation`
- `cassandra_intake_correspondence_human_layer_coordination`
- `niles_creative_music_art_studio`
- `openclaw_neutral_cockpit_fallback`

## Smoke Mapping

- `st_annes_work_log`: `cassandra` / `operator_intake` / `internal_operator`
- `capital_hilton_proposal_followup`: `cassandra` / `operator_calm` / `internal_operator`
- `capital_hilton_invoice_operator_assist`: `chief` / `diagnostic` / `internal_operator`
- `check_engine_warning`: `chief` / `diagnostic` / `internal_operator`
- `architecture_recommendation`: `hermes` / `recommendation` / `internal_operator`
- `creative_project_session`: `niles` / `recommendation` / `internal_operator`
- `external_client_draft`: `clara` / `client_facing` / `external_client`
- `submit_authority_requested`: `guardian` / `safety_gate` / `internal_operator`

## Boundary

- No Telegram live connection.
- No email send.
- No Gmail/browser/Coupa access.
- No workbook mutation or PDF export.
- No ledger mutation.
- No paid or sent marking.
- External client-facing draft copy uses `clara`; internal system names are not for client-visible copy.
