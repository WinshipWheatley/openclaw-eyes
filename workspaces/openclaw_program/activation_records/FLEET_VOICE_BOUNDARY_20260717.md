# Fleet Voice Boundary Activation - 2026-07-17

Status: **DEPLOYED + ACTIVE + OWNER-SURFACE VERIFIED**

## Deployment

- production commit: `f807c94e`
- activation flag: `OPENCLAW_FLEET_VOICE_BOUNDARY=1`
- active owners: Cassandra/Clara, Chief, Guardian, Niles, Maestro, Hermes, OpenClaw
- service restart: 2026-07-17 10:47 EDT
- active service count: 7/7

## Owner-Surface Canary

The canary imported and called the deployed owner adapters, not test doubles:

- Cassandra: `cassandra_listener._final_operator_reply`
- Chief: `chief_listener._final_operator_text`
- Guardian: `chief_guardian_listener.guardian_resilient_reply`
- Niles: `producer_listener._final_operator_reply`
- Maestro: `maestro_listener._final_operator_reply`
- Hermes: `openclaw_hermes_gateway_policy.sanitize_gateway_response`
- OpenClaw: `operator_surface_guard.guard_operator_reply_with_receipt`
- Clara: `clara_invoice_email_draft_package.build_general_client_invoice_body`

Result: 8/8 canonical profiles passed. Each interactive owner recorded its own `speaker_ref` and `voice_profile_ref`. An injected shared canned phrase was substituted at every interactive owner while the neighboring verified sentence remained visible.

Clara's St. Anne's body passed the external-copy gate with:

- workflow: `st_annes_invoice_forward_tracking`
- milestone: `glenn_acknowledged`
- ask hash: `sha256:d6dd6c3e4f14554b4eb2aa834d1b28fc1e5004fe4d1d805b8c1f9b23ee192bb0`
- why hash: `sha256:ded6c51c99e51cc39f026be8302918ad41aab84c128611345e219460b6c7339d`
- raw body stored in receipt: false

## Authority Boundary

- Telegram/email/provider transport calls: 0
- email sends: 0
- money actions: 0
- deletes: 0
- secrets read or stored: 0

## Rollback

Set `OPENCLAW_FLEET_VOICE_BOUNDARY=0` in the seven owner-service drop-ins, reload the user manager, and restart those services. The existing control-language and machine-output guards remain active.
