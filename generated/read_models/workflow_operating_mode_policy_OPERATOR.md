# Workflow Operating Mode Policy

Read-model only. No Telegram, email, Coupa, browser, invoice generation, ledger, model, tool, or production action authority is enabled.

## Access Classes

- WINSHIP_DEVELOPER: build/debug details allowed when the mode calls for them.
- WINSHIP_OPERATOR: runtime use with concise next steps and correction authority.
- CUSTOMER_OPERATOR: no developer prompts; customer-safe setup/blocker copy only.
- CUSTOMER_ADMIN: module setup and policy/admin approval, no code mode.
- SYSTEM_DEVELOPER_AGENT: code-level tasks allowed, production actions still gated.

## Channels

- Mission Control app: rich preview, file picker, proof disclosure, approval buttons.
- Telegram: first-class text operator surface; artifact review and approval are untested, not declared impossible.
- CLI/dev: diagnostics and build tasks for developer access.

## Current Live Arts MD Recommendation

- Mode: `OPERATOR_RUNTIME`
- Channel: `APP`
- Next: Choose or confirm the invoice candidate, then link the invoice artifact and confirm recipients.

## Boundary

- No live Telegram polling or send.
- No email/Gmail, Coupa/browser, workbook/cell read, invoice generation/export, ledger posting, production mutation, live model call, or tool action.
