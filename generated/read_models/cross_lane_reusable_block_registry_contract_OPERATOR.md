# Cross-Lane Reusable Block Registry / Tokenization Contract v0

## ELIOPERATOR Summary

Reusable blocks let one safe answer help multiple workflows, but sensitive values stay protected. A reusable fact can carry a safe label or token reference without exposing the raw value.

This is not live reuse yet. It does not write the PII vault, de-tokenize, auto-apply facts, run agents, or touch external systems.

## Why It Exists

- Answer low-hanging-fruit blocks out of order.
- Reuse high-leverage facts only inside the right tenant/client/scope.
- Show conflicts and stale facts instead of silently overwriting.
- Keep proof-heavy and protected blocks parked until a safe path exists.
- Derive calculated values like subtotal instead of copying them as truth.

## Protected Values

- Raw values allowed in normal read-models: `false`
- Public hash allowed for protected values: `false`
- Matching strategy: scoped/keyed local HMAC-style comparison reference; no public raw SHA-256 of PII/protected values
- De-tokenization authority: `none in this contract; future protected local authority required`

## Workbench Buckets

- `LOW_HANGING_FRUIT`
- `HIGH_LEVERAGE`
- `NEEDS_PROOF`
- `NEEDS_PROTECTED_EVIDENCE`
- `PARKED_FOR_LATER`
- `CONFLICTS_AND_STALE`
- `BLOCKED_BY_AUTHORITY`
- `NEXT_SAFE_MOVE`

## Examples

- Rate can be suggested as a non-sensitive reusable fact; subtotal still derives from source facts.
- AP route and PO/payment references use token refs and safe labels, not raw values.
- Protected evidence references point to protected material without placing raw bodies in read-models.
- Telegram/Cassandra may front a request later, but receipt-backed backend state remains truth.

## Authority

- live_reusable_fact_write_allowed: `false`
- live_pii_vault_write_allowed: `false`
- live_de_tokenization_allowed: `false`
- live_cross_lane_auto_apply_allowed: `false`
- live_operator_workbench_ui_allowed: `false`
- model_call_allowed: `false`
- agent_activation_allowed: `false`
- tool_execution_allowed: `false`
- queue_execution_allowed: `false`
- runtime_dispatch_allowed: `false`
- browser_automation_allowed: `false`
- coupa_access_allowed: `false`
- gmail_access_allowed: `false`
- telegram_send_allowed: `false`
- email_send_allowed: `false`
- credential_handling_allowed: `false`
- raw_body_ingestion_allowed: `false`
- mission_control_swift_change_allowed: `false`
- mac_sync_import_allowed: `false`
- git_push_pull_fetch_allowed: `false`
- network_operation_allowed: `false`
- file_cleanup_archive_promotion_allowed: `false`

## Next Safe Move

Review the contract, then build a Cross-Surface Artifact Handoff Registry before any live reusable-fact write path.
