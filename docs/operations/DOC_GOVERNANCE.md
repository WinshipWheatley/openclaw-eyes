# Documentation Governance

This file defines the lifecycle, authority, and organization of OpenClaw documentation.

## Promotion Rule

Drafts are not source of truth. Promotion into `docs/` is an explicit operational step.

1. **Review**: The candidate draft (e.g., from `mac_eyes/Winship/drafts/`) must be reviewed for technical accuracy and alignment with repo law.
2. **Assign Lane**: Decide the canonical lane (`doctrine`, `specs`, `handoffs`, `testing`, or `operations`).
3. **Canonicalize**: Move or rewrite the draft into the selected lane within `docs/`.
4. **Archive**: Leave the original draft in `archive/` or delete it once promoted.

## Documentation Lanes

| Lane | Purpose | Authority |
| :--- | :--- | :--- |
| `doctrine/` | Core naming, authority rules, and architectural mandates. | Human Operator |
| `specs/` | Working functional and technical specifications. | Human + Agent (Review Required) |
| `handoffs/` | Promoted reference docs and context bundles. | Human + Agent |
| `testing/` | Strategy, harness guides, and verification plans. | Human + Agent |
| `operations/` | Repository governance, lifecycle, and runbooks. | Human Operator |
| `_ai/` | Derived briefing files and automated context logs. | Agentic (Deterministic) |

## Editing Authority

- **Human Only**: `doctrine/`, `operations/`, and root-level laws (`OPENCLAW_RUNTIME.md`). Agents may propose changes but MUST NOT commit without explicit operator approval.
- **Collaborative**: `specs/`, `handoffs/`, `testing/`. Agents may update these files when implementing features or fixing bugs, provided they adhere to established patterns.
- **Agentic**: `_ai/` and transient state logs. These are normally managed by automated processes.

## Cross-Linking

- Prefer relative links: `[Context](_ai/AI_WORKING_CONTEXT.md)`.
- Root-level indices should point to specialized sub-indices in `testing/` or `operations/`.
