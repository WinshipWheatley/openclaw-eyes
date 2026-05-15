# Safety Boundaries

This pack is an offline source bundle. It does not grant authority.

No-authority flags:
- `external_upload_allowed`: `false`
- `browser_automation_allowed`: `false`
- `network_authority`: `false`
- `raw_private_included`: `false`
- `no_go_included`: `false`
- `secrets_included`: `false`
- `agent_activation_allowed`: `false`
- `action_auto_execute_allowed`: `false`

Blocked in this lane:
- No automatic upload to ChatGPT, Claude, Gemini, Codex, or any external service.
- No browser/UI automation.
- No network API calls.
- No private/no-go raw content.
- No file moves, deletes, renames, deployment, runtime activation, or agent activation.
