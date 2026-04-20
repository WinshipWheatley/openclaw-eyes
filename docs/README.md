# OpenClaw Docs Flow

`/home/openclaw/docs/` is the canonical documentation root for OpenClaw.

## Canonical lanes

- `docs/doctrine/` — canonical doctrine and naming/authority rules
- `docs/specs/` — canonical working specs
- `docs/handoffs/` — promoted handoff/reference docs worth keeping in the repo
- `docs/_ai/` — AI-facing briefing files derived from canonical docs and live runtime truth

## Non-canonical lanes

- `docs/exports/` — snapshot exports; useful reference, not the editing target
- `mac_eyes/Winship/drafts/` — candidate AI-written artifacts in the Mac reflection layer
- `mac_eyes/Winship/archive/` — stale or superseded draft artifacts kept for reference

## Promotion rule

Drafts are not source of truth.

Promotion into `docs/` is explicit:

1. Review the candidate draft.
2. Decide the canonical lane (`doctrine`, `specs`, `handoffs`, or `_ai`).
3. Move or rewrite it into `docs/`.
4. Leave the draft in `archive/` if historical trace is useful.

## Default tool-loading rule

For AI/context loading by default:

1. Read [`AI_WORKING_CONTEXT.md`](/home/openclaw/docs/_ai/AI_WORKING_CONTEXT.md).
2. Read [`OPENCLAW_RUNTIME.md`](/home/openclaw/OPENCLAW_RUNTIME.md).
3. Read the relevant canonical doc in `docs/`.

Do not treat `docs/exports/`, `mac_eyes/`, or draft folders as source of truth unless explicitly asked.
