# Provider Access Catalog

Status: OPENCLAW_SUBSCRIPTION_BACKED_LM_ACCESS_AUDIT_READY

This is an access-mode audit only. It did not invoke models, send prompts, inspect credential stores, or automate desktop apps.

## Recommended Order
- openai_codex_cli
- google_gemini_cli
- google_antigravity_cli
- anthropic_claude_cli
- openai_codex_desktop_app
- chatgpt_desktop_app_web
- local_ollama_runtime
- api_key_overage_routes

## Access Modes
- openai_codex_cli: cli_authenticated_billing_unknown
  - installed: True
  - auth_status: authenticated_unknown_billing
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: code_worker
  - next_probe_required: operator-approved bounded dry-run only after subscription backing is proven
- openai_codex_desktop_app: desktop_app_manual
  - installed: False
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: False
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: manual_only
  - next_probe_required: operator review of supported Codex app-server/desktop bridge before any automation
- chatgpt_desktop_app_web: manual_handoff
  - installed: False
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: False
  - worker_candidate: False
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: manual_only
  - next_probe_required: operator-confirmed supported bridge or keep manual handoff only
- google_gemini_cli: cli_installed_auth_unknown
  - installed: True
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: form_fill_advisor
  - next_probe_required: find a documented safe Gemini CLI auth/status command or keep manual/API routes separate
- google_antigravity_cli: cli_installed_auth_unknown
  - installed: True
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: architecture_review
  - next_probe_required: find a documented safe Antigravity auth/status command and prove no broad workspace/tool access
- anthropic_claude_cli: cli_authenticated_subscription
  - installed: True
  - auth_status: authenticated_subscription
  - subscription_backed: True
  - api_billing_required: False
  - worker_candidate: True
  - worker_ready: True
  - live_conversation_candidate: False
  - recommended_use: architecture_review
  - next_probe_required: operator-approved claude auth status/proof of subscription mode and one no-tools package smoke
- local_ollama_runtime: local_runtime
  - installed: True
  - auth_status: unknown
  - subscription_backed: False
  - api_billing_required: False
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: local_redaction
  - next_probe_required: operator-approved local invocation boundary before any model run
- api_key_overage_routes: api_key_available_but_not_preferred
  - installed: False
  - auth_status: unknown
  - subscription_backed: False
  - api_billing_required: True
  - worker_candidate: False
  - worker_ready: False
  - live_conversation_candidate: False
  - recommended_use: blocked
  - next_probe_required: none unless operator explicitly chooses API fallback

## Do Not Automate
- ChatGPT/Codex desktop GUI clicking or browser scraping.
- Provider API-key fallback without explicit approval and billing boundary receipt.
- Tool/file access expansion from a model result.
- Business actions, email sends, Coupa/browser actions, ledger/workbook/PDF mutation, paid marking, or Guardian approvals.

## Worker Run Manager
Usable CLI candidates should be dispatched through the existing package lifecycle and ingested only from recorded result files. The model result never mutates runtime directly.
