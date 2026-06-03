# OpenClaw Workroom Registry

Status: `OPENCLAW_WORKROOM_REGISTRY_READY`

This registry defines local channel-like workrooms for agent status, handoffs, and review packets. It does not connect Slack or Telegram and does not send messages.

Channels: `11`

## Channels

### `helm_daily_desk`

- Display: Helm Daily Desk
- World: `helm`
- Thread: `workroom:helm_daily_desk:main`
- Primary agent: `openclaw`
- Allowed speakers: `openclaw`, `chief`, `cassandra`, `hermes`, `guardian`, `niles`, `pc_codex`, `mac_codex`
- Allowed package types: `status_packet`, `handoff_packet`, `review_packet`, `daily_desk_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `finance_st_annes`

- Display: Finance - St. Anne's
- World: `finance`
- Thread: `workroom:finance_st_annes:main`
- Primary agent: `cassandra`
- Allowed speakers: `cassandra`, `chief`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `work_log_status_packet`, `correspondence_draft_packet`, `finance_handoff_packet`, `invoice_review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `finance_capital_hilton`

- Display: Finance - Capital Hilton
- World: `finance`
- Thread: `workroom:finance_capital_hilton:main`
- Primary agent: `chief`
- Allowed speakers: `chief`, `cassandra`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `invoice_status_packet`, `provider_gate_diagnostic_packet`, `finance_handoff_packet`, `review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `finance_live_arts_md`

- Display: Finance - Live Arts MD
- World: `finance`
- Thread: `workroom:finance_live_arts_md:main`
- Primary agent: `cassandra`
- Allowed speakers: `cassandra`, `chief`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `work_log_status_packet`, `correspondence_draft_packet`, `finance_handoff_packet`, `review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `business_development_capital_hilton`

- Display: Business Development - Capital Hilton
- World: `business_development`
- Thread: `workroom:business_development_capital_hilton:main`
- Primary agent: `clara`
- Allowed speakers: `clara`, `cassandra`, `hermes`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `proposal_status_packet`, `external_draft_artifact_packet`, `follow_up_draft_packet`, `architecture_note_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `build_mission_control_mac`

- Display: Build - Mission Control Mac
- World: `build`
- Thread: `workroom:build_mission_control_mac:main`
- Primary agent: `chief`
- Allowed speakers: `chief`, `hermes`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `build_status_packet`, `build_review_packet`, `handoff_packet`, `architecture_note_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `build_openclaw_backend`

- Display: Build - OpenClaw Backend
- World: `build`
- Thread: `workroom:build_openclaw_backend:main`
- Primary agent: `chief`
- Allowed speakers: `chief`, `hermes`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `build_status_packet`, `build_review_packet`, `diagnostic_packet`, `architecture_note_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `creative_niles_studio`

- Display: Creative - Niles Studio
- World: `creative`
- Thread: `workroom:creative_niles_studio:main`
- Primary agent: `niles`
- Allowed speakers: `niles`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `creative_review_packet`, `studio_status_packet`, `metadata_review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `security_guardian_gates`

- Display: Security - Guardian Gates
- World: `security`
- Thread: `workroom:security_guardian_gates:main`
- Primary agent: `guardian`
- Allowed speakers: `guardian`, `chief`, `hermes`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `protected_gate_packet`, `authority_review_packet`, `risk_note_packet`, `proof_review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `architecture_hermes`

- Display: Architecture - Hermes
- World: `architecture`
- Thread: `workroom:architecture_hermes:main`
- Primary agent: `hermes`
- Allowed speakers: `hermes`, `chief`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `architecture_recommendation_packet`, `doctrine_packet`, `tradeoff_packet`, `build_handoff_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

### `operations_chief_workboard`

- Display: Operations - Chief Workboard
- World: `operations`
- Thread: `workroom:operations_chief_workboard:main`
- Primary agent: `chief`
- Allowed speakers: `chief`, `cassandra`, `hermes`, `guardian`, `openclaw`, `pc_codex`, `mac_codex`
- Allowed package types: `operations_workboard_packet`, `diagnostic_packet`, `handoff_packet`, `review_packet`, `spawned_worker_output_packet`
- Proof: collapsed by default

## Agent Mapping

- `Cassandra`: finance work logs, correspondence, follow-ups
- `Chief`: diagnostics, build packets, provider gates
- `Hermes`: architecture recommendations
- `Guardian`: protected action gates
- `Niles`: creative work
- `Clara`: external draft artifacts only
- `OpenClaw`: neutral system status
- `PC_CODEX`: spawned worker outputs only
- `MAC_CODEX`: spawned worker outputs only

## Boundary

- No Slack connection.
- No Telegram live connection.
- No message send.
- No email send.
- No Gmail/browser/Coupa access.
- No workbook mutation or PDF export.
- No ledger mutation.
- No paid marking or portal submit.
- No git push.
- Spawned worker entries are output packets only; this registry cannot spawn workers.
