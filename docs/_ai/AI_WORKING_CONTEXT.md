# AI Working Context

Default high-signal briefing file for AI work in OpenClaw.

## Canonical truth

- Canonical docs root: `/home/openclaw/docs/`
- Runtime law: [`OPENCLAW_RUNTIME.md`](/home/openclaw/OPENCLAW_RUNTIME.md)
- Canonical doctrine:
  [`docs/doctrine/OpenClaw_Architecture_and_Naming_Doctrine.md`](/home/openclaw/docs/doctrine/OpenClaw_Architecture_and_Naming_Doctrine.md)

## Runtime vs docs truth

- Runtime/code truth lives in `/home/openclaw` plus the authoritative runtime-state roots defined in `OPENCLAW_RUNTIME.md`.
- Canonical documentation truth lives in `/home/openclaw/docs/`.
- Generated surfaces, mirrors, exports, and drafts are never source of truth by default.

## Naming and identity

- Internal canonical assistant name: `Cassandra`
- Outward-facing short name: `Clara`
- Outward-facing full name: `Clara Reid`
- These are the same assistant identity, not separate agents.

## Non-canonical by default

- `mac_eyes/` and the Mac Local AI Watch workspace
- `docs/exports/`
- `mac_eyes/Winship/drafts/`
- `mac_eyes/Winship/archive/`

## Current priorities

- Keep canonical docs in `/home/openclaw/docs/`
- Keep AI draft/reflection work out of canonical truth unless explicitly promoted
- Keep recipient-facing pilot work draft-first, review-first, and truthful

## Current guards

- No draft or mirror artifact becomes canonical by mere presence
- No autonomous send claims for the pilot path
- Prefer runtime-derived evidence over summaries when truth is in question

## Default read order

1. Read this file.
2. Read [`BUILD_INTENT.md`](/home/openclaw/docs/_ai/BUILD_INTENT.md).
3. Read the relevant canonical doc in `docs/`.
4. Read runtime evidence only if the task needs live truth.
