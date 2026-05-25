# Worker Routing Intelligence v0

ELIOPERATOR: One chat can ask for work without the operator manually choosing the worker. This read-model chooses the right lane and prepares a package recommendation. It does not dispatch anyone.

## Routes

- Mac Codex: Apple/Mac-side app work, SwiftUI, Xcode, screenshots, Mac package import/render, and Apple app integration boundaries.
- PC Codex: Repo A backend, Python, read-models, scripts, tests, router/intake/readback, package compiler, and PC-to-Mac shuttle packages.
- Gemini/Agy: read-only scouting, audit, critique, prompt shaping, and gotcha discovery.
- Guardian: approval, protected evidence, security posture, and sensitive-boundary review.
- Cassandra: communications drafting and operator-facing follow-up language.
- Unknown: asks for clarification instead of guessing.

## Examples

- Mac UI -> `MAC_CODEX` / `SWIFTUI_APP_UI`
- Apple integration -> `MAC_CODEX` / `APPLE_APP_INTEGRATION_SCOUT_OR_UI`
- PC backend -> `PC_CODEX` / `BACKEND_READMODEL`
- PC package -> `PC_CODEX` / `SHUTTLE_PACKAGE`
- Gemini/Agy -> `GEMINI_AGY` / `READ_ONLY_AUDIT`
- Unknown -> `UNKNOWN_NEEDS_ROUTING`

## Blockers

- Wrong worker or wrong machine fails closed.
- External action language is stripped or blocked.
- Credentials, raw private bodies, and raw PII are excluded.
- Vague requests ask for clarification.

## Boundary

No live auto-dispatch, worker execution, cross-machine send, model call, agent dispatch, workflow run, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Use deterministic route decisions to prepare a package recommendation, then wait for explicit operator send.
