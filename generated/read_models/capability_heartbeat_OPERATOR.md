# Capability Heartbeat Report

Generated: 2026-07-26T04:57:59.743062+00:00
Registry: `/mnt/e/openclaw/orchestration/artifacts/CAPABILITY_HEALTH_REGISTRY.md`
Capabilities: 54
Drift count: 8
Live status counts: {'broken': 1, 'dark': 16, 'dormant': 11, 'lit': 24, 'unknown': 2}

| capability | registry | live | confidence | flags |
| --- | --- | --- | --- | --- |
| Gmail Send | dormant | dormant | medium | blocked_by_hold |
| Gmail Draft Create | lit | lit | high | - |
| Gmail Read Metadata | lit | lit | high | - |
| Gmail Read Body | lit | lit | high | - |
| Gmail Unread Count | lit | lit | high | - |
| Google Contacts Read | lit | lit | high | - |
| Telegram Message Send | dormant | dormant | medium | blocked_by_hold |
| Telegram Voice Note Send | dormant | dormant | medium | blocked_by_hold |
| Telegram Document Send | dormant | dormant | medium | blocked_by_hold |
| Operator Brief Send (Text) | dormant | dormant | medium | blocked_by_hold |
| Email Reply Bridge | dormant | dormant | medium | partial_live_evidence |
| cassandra-briefing-scheduler | lit | lit | high | - |
| cassandra-listener | lit | lit | high | - |
| cassandra-watcher | lit | lit | high | - |
| cassandra-voice-synthesis (piper) | lit | dark | medium | no_live_evidence, DRIFT |
| cassandra-messaging | lit | dark | medium | no_live_evidence, DRIFT |
| chief-email-brain | lit | dark | medium | no_live_evidence, DRIFT |
| chief-memory-worker | lit | lit | high | - |
| chief-state-worker | lit | lit | high | - |
| chief-watcher-brain | lit | lit | high | - |
| chief-worker | lit | lit | high | - |
| chief-guardian-listener | lit | lit | high | - |
| guardian-output-validation | lit | dark | medium | no_live_evidence, DRIFT |
| hermes-gateway | lit | lit | high | - |
| niles-notification-service (HITL tokens/callbacks) | lit | dark | medium | no_live_evidence, DRIFT |
| maestro-correspondence-watching | lit | dark | medium | no_live_evidence, DRIFT |
| openclaw-request-response | lit | lit | high | - |
| capability-registry | lit | dark | medium | no_live_evidence, DRIFT |
| hitl-action-dispatcher | lit | lit | high | - |
| google-calendar-read | lit | lit | high | - |
| google-calendar-write | broken | broken | medium | expected_breakage_still_observed |
| google-calendar-delete | lit | lit | high | - |
| email_send (general) | dormant | dormant | medium | blocked_by_hold |
| sms | dormant | dark | medium | no_live_evidence, DRIFT |
| social_post | dormant | unknown | low | declaration_only |
| file_open | unknown | unknown | low | declaration_only |
| financial_transfer | dark | dark | medium | no_live_evidence |
| payment | dark | dark | medium | no_live_evidence |
| bill_pay | dark | dark | medium | no_live_evidence |
| wire_transfer | dark | dark | medium | no_live_evidence |
| invoice_send | dark | dark | medium | no_live_evidence |
| refund | dark | dark | medium | no_live_evidence |
| charge | dark | dark | medium | no_live_evidence |
| morning_brief | lit | lit | high | - |
| pii_tokenization_redaction | lit | lit | high | - |
| privacy_request_readiness_gate1 | lit | lit | high | - |
| steel_thread_radar | dormant | dormant | medium | partial_live_evidence |
| pii_vault_encrypted_store | lit | lit | high | - |
| polish_loop (autonomous build pipeline) | dormant | dormant | medium | partial_live_evidence |
| Hermes Agent (Nous Research) | partly_lit | lit | high | - |
| GBrain (self-wiring knowledge graph) | dormant | dormant | medium | partial_live_evidence |
| NemoClaw (NVIDIA reference stack) | dark | dark | medium | no_live_evidence |
| openclaw-builder | unknown | lit | high | - |
| .openclaw/workspace | dormant | dormant | medium | partial_live_evidence |

Safety: read-only probes only; no send, dispatch, merge, deploy, restart, or service mutation attempted.
