# Agent Handoff Registry

Status: `AGENT_HANDOFF_REGISTRY_READY`

This registry defines deterministic handoff rules for routing agent work to the right channel, agent, or worker packet lane. It does not connect external tools or execute work.

Handoffs: `8`

## Handoffs

### `cassandra_to_chief_package_needed`

- From: `cassandra`
- To: `chief`
- Channel: `operations_chief_workboard`
- Trigger: A work-log, invoice, correspondence, or follow-up item needs a package, diagnostic, or queue decision.
- Package type: `package_request_handoff_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `cassandra_to_guardian_authority_detected`

- From: `cassandra`
- To: `guardian`
- Channel: `security_guardian_gates`
- Trigger: Send, email, calendar, credential, PII, protected access, portal, ledger, or paid authority appears.
- Package type: `protected_authority_gate_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `chief_to_pc_codex_backend_implementation`

- From: `chief`
- To: `pc_codex`
- Channel: `build_openclaw_backend`
- Trigger: A locally bounded backend package is ready for implementation or validation on PC.
- Package type: `pc_codex_backend_worker_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `chief_to_mac_codex_ui_excel_gui_operator_assist`

- From: `chief`
- To: `mac_codex`
- Channel: `build_mission_control_mac`
- Trigger: Mission Control UI, Excel review surface, GUI operator-assist, or Mac-specific display work is ready for a Mac worker packet.
- Package type: `mac_codex_operator_assist_worker_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `chief_to_guardian_protected_authority`

- From: `chief`
- To: `guardian`
- Channel: `security_guardian_gates`
- Trigger: A package asks for send, submit, ledger, credential, browser, Coupa, Gmail, workbook, paid, or other protected authority.
- Package type: `protected_package_gate_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `hermes_to_chief_build_packet`

- From: `hermes`
- To: `chief`
- Channel: `operations_chief_workboard`
- Trigger: An architecture recommendation becomes concrete build work or a package queue candidate.
- Package type: `architecture_to_build_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `niles_to_chief_creative_build_tooling`

- From: `niles`
- To: `chief`
- Channel: `operations_chief_workboard`
- Trigger: A creative recommendation needs app, build, tooling, metadata, or automation support.
- Package type: `creative_to_build_tooling_packet`
- Requires operator approval: `true`
- Receipt required: `true`

### `clara_to_cassandra_internal_review_state`

- From: `clara`
- To: `cassandra`
- Channel: `business_development_capital_hilton`
- Trigger: A client-facing draft artifact exists and needs internal review state, follow-up tracking, or correspondence staging.
- Package type: `external_draft_internal_review_packet`
- Requires operator approval: `true`
- Receipt required: `true`

## Examples

- `customer_reports_bug`: Cassandra records the intake, Chief shapes the build package, then PC_CODEX receives a backend worker packet.
- `capital_hilton_proposal_accepted`: Clara draft state hands back to Cassandra for internal review and finance/business-development follow-up packaging.
- `submit_invoice`: Chief must route to Guardian for a protected gate before any operator-assist path can be considered.

## Boundary

- No external tool connection.
- No email send.
- No Gmail/browser/Coupa access.
- No ledger or workbook mutation.
- No PDF export.
- No submit or mark-paid.
- No git push.
- No worker spawn or agent loop launch.
- Every handoff requires a receipt and operator review.
