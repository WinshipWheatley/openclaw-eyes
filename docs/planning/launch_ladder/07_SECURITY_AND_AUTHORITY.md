# Security And Authority

Status: docs-only security/authority model. This file does not grant authority.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: runtime law, intent/control map, MCP profiles, model fallback policy, service freeze, Hermes advisory contract, modular readiness ledger.
- Stale when: approval policy, broker policy, MCP profile, service freeze, model fallback, or module authority changes.
- Refresh trigger: update before any route moves beyond planning/source-set readiness.

## Core Rules

- No module promotes itself.
- No advisory output becomes canonical by presence.
- No sensitive data leaves the local boundary without sanitizer, approval, and logging.
- No service/runtime mutation happens without explicit mode and approval.
- No new capability ships without a validation map entry.
- No source-set drift is allowed without refresh.
- No launch-ready claim is valid without evidence, freshness, route, and authority fields.
- Launch-ready is not launch-authorized.

## V1 Hard Boundaries

- The console/atlas is a window/router/evidence browser, not authority; the operator remains authority.
- Guardian may approve/deny exact action packets, but must not handle secrets, store passwords, transmit tokens, paste credentials, unlock SSH passphrases, or inspect vault contents.
- No service/runtime mutation in v1.
- No private/legal/vault/log inspection in v1.
- No provider/model calls in v1.

## Authority Separation

| Surface | Authority in this package | Notes |
| --- | --- | --- |
| Launch Ladder docs | Planning/spec only. | Can shape future implementation prompts. |
| Modular readiness ledger | Source for readiness posture. | Does not authorize runtime work by itself. |
| Service freeze | Static service/process contract. | Does not prove live service state or authorize operations. |
| Hermes advisory | Non-canonical advisory only. | Packet/memo must preserve withheld surfaces. |
| ChatGPT Projects | External advisory/review only. | Generated folders are derived/non-canonical. |
| Codex Desktop | Future build tool only with explicit source set. | Must not receive private/protected data by default. |
| Google/Gmail/Calendar broker | Broker-gated actions only. | Gmail body/draft paths are sensitive and gated. |
| Guardian | Approval gate for high-risk actions. | Approval prompts should avoid raw secrets/private data. |
| macOS/iOS app | Read-only first client. | No service-control authority in first version. |

## Withheld Surfaces By Default

- Runtime state.
- Logs and private logs.
- Secrets, SSH keys, tokens, credentials, `.chief.env`, `.google-secrets`.
- Vaults and shared/private operator vault contents.
- LegalPrivate and private matter data.
- Gmail bodies and private correspondence.
- CPA, Music Law, Publishing sensitive data.
- Hermes runtime home, sessions, state DBs, logs, and provider fallback.
- Live services, installed user units, service/timer commands, launchers, installers, schedulers.
- Provider/model calls unless a future sanitized and approved route exists.
- `.mcp.json` edits unless the task is an explicit MCP profile lane.

## Approval Classes In Console Language

| Console label | Meaning |
| --- | --- |
| `advisory_only` | Can recommend or critique only. |
| `docs_only_write` | Can edit requested non-private docs in repo. |
| `static_check` | Can run static checks named by validation. |
| `broker_gated` | Must go through capability broker. |
| `guardian_required` | Needs high-risk approval. |
| `operator_authorized` | Needs explicit Winship approval for the named step. |
| `forbidden_now` | Not allowed in current package/slice. |

## Anti-Slop Guardrails

- A route with missing evidence defaults to `recommendation`, not `launch-ready`.
- A route with missing freshness defaults to `stale` or `unknown`.
- A route with missing authority defaults to `forbidden_now`.
- A route with private/protected data defaults to local/deterministic handling or blocked.
- A compact button must show deferred work before it can be selected.
- A parallel bundle must show collisions, validations, commit boundaries, and stop conditions before it can be selected.

## Do Not Do Yet

- Do not build a service-control button into the first app.
- Do not expose broad repo, vault, log, or private paths to external tools.
- Do not route advisory outputs into canonical docs without explicit promotion.
- Do not create a new approval system when Chief/Guardian/broker paths already exist.
