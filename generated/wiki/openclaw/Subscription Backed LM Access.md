# Subscription Backed LM Access

Status: OPENCLAW_SUBSCRIPTION_CLI_AUTH_STATUS_PROBE_READY

This probe used only local version/help/auth-status inventory commands. It did not invoke models, send prompts, inspect auth stores, print credentials, automate desktop apps, or mutate runtime state.

## Summary
- Worker Run Manager ready: anthropic_claude_cli
- Worker Run Manager candidates: openai_codex_cli, google_gemini_cli, google_antigravity_cli, anthropic_claude_cli, local_ollama_runtime
- Live conversation candidates: none
- Manual-only until proven: openai_codex_cli, google_gemini_cli, google_antigravity_cli, local_ollama_runtime
- API billing required: none

## CLI Status
- openai_codex_cli
  - installed: True
  - version: codex-cli 0.139.0
  - auth_status: authenticated_unknown_billing
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - manual_only: True
  - reason: Status output indicates authentication but does not prove whether billing is subscription-backed or API-key backed.
  - next: operator-approved bounded dry-run only after subscription backing is proven
- google_gemini_cli
  - installed: True
  - version: 0.44.1
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - manual_only: True
  - reason: No safe documented auth status command was available in CLI help.
  - next: find a documented safe Gemini CLI auth/status command or keep manual/API routes separate
- google_antigravity_cli
  - installed: True
  - version: 1.0.8
  - auth_status: unknown
  - subscription_backed: unknown
  - api_billing_required: unknown
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - manual_only: True
  - reason: No safe documented auth status command was available in CLI help.
  - next: find a documented safe Antigravity auth/status command and prove no broad workspace/tool access
- anthropic_claude_cli
  - installed: True
  - version: 2.1.174 (Claude Code)
  - auth_status: authenticated_subscription
  - subscription_backed: True
  - api_billing_required: False
  - worker_candidate: True
  - worker_ready: True
  - live_conversation_candidate: False
  - manual_only: False
  - reason: Status output explicitly indicates subscription or ChatGPT subscription-plan backed access.
  - next: none
- local_ollama_runtime
  - installed: True
  - version: none
  - auth_status: unknown
  - subscription_backed: False
  - api_billing_required: False
  - worker_candidate: True
  - worker_ready: False
  - live_conversation_candidate: False
  - manual_only: True
  - reason: Ollama is local runtime inventory, not subscription-backed CLI auth.
  - next: operator-approved local invocation boundary before any model run

## Policy
- Prefer subscription-backed CLI/app lanes over API-key billing only after subscription backing is proven.
- API-key routes are fallback, not preferred.
- Desktop GUI and browser automation remain disallowed.
- ChatGPT app/web remains manual-only until a supported bridge is proven.
- Worker Run Manager dispatch requires either proven subscription-backed CLI auth or a separate local invocation boundary.
