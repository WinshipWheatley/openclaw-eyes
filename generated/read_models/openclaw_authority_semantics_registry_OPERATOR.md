# OpenClaw Authority Semantics Registry

- Status: DETERMINISTIC_AUTHORITY_SEMANTICS_REGISTRY_NO_EXECUTION
- Semantics version: authority_semantics_v0
- Prohibition flags: `no_* = true` means the action is prohibited.
- Authority grants: `*_allowed = true` means the action is allowed only by the active profile.
- Event Bridge finance profile: safety flags assert prohibitions; authority_boundary carries denied grants.
- `no_browser`: PROHIBITION_FLAG (The action is prohibited and must not happen.)
- `browser_access_allowed`: AUTHORITY_GRANT (The action is explicitly allowed by the active authority profile.)

## Positive Templates
- `event_bridge_finance_workflow_action_template`: Canonical hot-path finance workflow event envelope.
- `event_bridge_finance_response_template`: Canonical routed workflow response.
- `live_arts_prepare_pdf_event_template`: Golden example for Live Arts Prepare invoice PDF.
- `telegram_finance_command_template`: Telegram compact surface emits the same event shape.
- `mac_app_event_bridge_writer_template`: Mac app writer emits canonical event envelope and receives response.
- `mac_excel_helper_authority_template`: Future helper authority profile for scoped PDF export packages.
- `guardian_receipt_required_mutation_template`: Canonical pattern for any future business mutation.

## Remediation

- Unsafe envelopes are blocked before routing.
- Live payloads are not silently rewritten.
- Generated views may be regenerated from this registry.
- Source-code fixes must be proposed as bounded work with tests and commits.
- Business mutation remains blocked without required receipts and authority.

## Boundary

- Deterministic registry/export only.
- No service start, Chief run, LM call, email, Gmail, browser, Coupa, workbook read, PDF export, ledger mutation, production mutation, or push.
