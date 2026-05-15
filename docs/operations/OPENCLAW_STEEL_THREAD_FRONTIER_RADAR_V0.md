# OpenClaw Steel Thread Frontier Radar v0

Steel Thread is OpenClaw's narrow strategic radar for AI, tooling, and system patterns that may matter to the backend, Mission Control, and future agent lanes.

It answers:
- What pattern did we notice?
- Why does it matter to OpenClaw?
- Which existing OpenClaw surfaces does it map to?
- Is it aligned, distracting, conflicting, or worth watching?
- Should Chief propose adoption, adaptation, watch, defer, ignore, or review?
- What evidence supports that recommendation?
- What boundaries apply before any lane is built?

## Existing Surface Reconciliation

- `operator_frontier_map.py`: `partial_overlap`. Static, read-only duplicate-work guard for the older Compiled Knowledge Substrate lane. Useful precedent, but not a durable strategic signal registry.
- `docs/navigation_maps/COMPILED_KNOWLEDGE_SUBSTRATE_FRONTIER_MAP.md`: `planning_only` / historical map. Useful pattern, not current Steel Thread state.
- `plugin_domain_registry.py`: `partial_overlap`. Contains an Architecture & Map Gate domain with frontier/prior-art language, but it is a plugin-domain planning registry, not a signal/recommendation ledger.
- Dropped Intent Registry / Intent Router / Agent Work Packets / Work Board: `candidate_to_extend` by metadata links. They should consume Steel Thread outputs later, not become the Steel Thread registry themselves.

No active Steel Thread implementation was found. v0 adds a small `steel_thread_*` namespace in the Business Ops ledger.

## What It Is

Steel Thread is:
- strategic signal intake
- evidence-backed pattern recognition
- OpenClaw alignment review
- recommendation generator
- work-lane proposer

It is intentionally local-first and metadata-first.

## What It Is Not

Steel Thread is not:
- an autonomous updater
- a news bot
- a hype feed
- an unbounded web crawler
- a model-calling agent
- a thing that changes architecture automatically
- an action creator or approval bypass

## Source Types

Allowed source kinds:
- `operator_note`
- `markdown_doc`
- `report_bridge_package`
- `external_research_summary`
- `local_research_packet`
- `uploaded_source`
- `manual_seed`
- `unknown`

v0.1 adds an approved source registry. The initial registry is conservative:
- `operator_manual_frontier_notes`: enabled, manual metadata only.
- `local_frontier_research_packets`: enabled, reads local approved packets under `generated/frontier_research_packets/`.
- `official_ai_tooling_feeds`: disabled until an exact public URL is approved.
- `github_agent_framework_releases`: disabled until exact public release-feed URLs are approved.

Disabled URL sources are not fetched. No arbitrary URL parameter exists in the CLI.

## Local Research Packet Format

Local packets live under:

```text
generated/frontier_research_packets/
```

They are Markdown files with optional front matter:

```markdown
---
source_kind: operator_supplied_summary
verification_status: unverified_external_claim
pattern_category: agent_orchestration
relevance_score: high
confidence: medium
openclaw_alignment: aligned
recommendation: adapt
recommended_lane: Mission Control Work Board Read-Only Surface v0
routed_agent: chief
reviewer: hermes
safety_review: guardian
---

# Pattern title

Short bounded summary and OpenClaw mapping.
```

Steel Thread stores source metadata, hashes, bounded excerpts, classifications, and recommendations. It does not store private/no-go raw bodies and does not treat packet claims as truth.

## Adding A Source Safely

To add an external source later:
- add it to `steel_thread_source_registry`
- keep it disabled until the exact URL is approved
- prefer RSS/Atom or official bounded release feeds
- set a max item limit
- use title/summary/release-note bounded fetch policy only
- never add login-required, paywalled, social-media scraping, browser automation, broad crawling, or recursive crawling
- label claims `external_source_claim` / `unverified_until_review`

## Evidence Rules

- Operator-supplied frontier claims are `source_claim` / `operator_note`, not verified truth.
- Repo-built surfaces may be cited as implementation evidence when paths exist.
- Recommendations are advice for a future lane, not authority to execute it.
- Private/no-go raw content is never read.

## Recommendation Statuses

- `adopt`: OpenClaw should use the pattern as-is within existing boundaries.
- `adapt`: OpenClaw should localize the pattern to its architecture and safety model.
- `watch`: keep on the watchlist; not enough proof or not urgent.
- `defer`: valid direction, but blocked by earlier substrate or approval gates.
- `ignore`: likely distracting or misaligned.
- `needs_review`: insufficient evidence; operator/Chief review required.

## Pattern Categories

- `agent_orchestration`
- `local_first_ai`
- `coding_agents`
- `model_runtime`
- `UI_helm_pattern`
- `workflow_automation`
- `file_context`
- `business_model`
- `security_boundary`
- `unknown`

## Authority Boundaries

Steel Thread grants no authority:
- no autonomous updates
- no action creation
- no auto-approval
- no auto-execution
- no external APIs
- no web crawling
- no model calls
- no agent activation
- no network authority
- no file moves/deletes

## Routing

Steel Thread recommendations route primarily to Chief as system orchestration. Guardian may review safety-boundary signals. Hermes may review advisory synthesis. Work Board and Mission Control should treat Steel Thread as a read-only recommendation source until a separate lane grants UI display or card integration.

In v0.1, Work Board can project high-relevance Steel Thread signals as metadata-only cards. These cards cannot approve, execute, create actions, or activate agents.

## Avoiding Hype-Chasing

Steel Thread must map every signal to existing OpenClaw surfaces, evidence basis, confidence, risk notes, and a next safe lane. If a signal cannot pass that framing, it should be `watch`, `defer`, `ignore`, or `needs_review`, not a build mandate.

## Current v0 Seeds

- Agent work board / orchestration board pattern: adapts the operator-supplied Symphony/Hermes Kanban idea into local Work Board/Mission Control surfaces without cloud dependency or arbitrary execution.
- Context pack generation for external AI tools: adopts the already-built External AI Context Packager as local export-only packaging.
- Helm control path maturity: watches/adapts the request/approve/execute/receipt path toward a future Mission Control Request Path.

## Current v0.1 Source Intake

- Local packet intake is enabled.
- A local packet exists for the agent work board / orchestration board pattern.
- External URL sources are registered disabled until exact URLs are approved.
- No broad crawl, recursive crawl, browser automation, model call, action creation, or notification is introduced.

## Commands

Build:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_steel_thread_radar.py --format operator
```

Query:
```bash
python3 scripts/query_steel_thread_radar.py --report summary --format operator
python3 scripts/query_steel_thread_radar.py --report recommendations --format operator
python3 scripts/query_steel_thread_radar.py --report watchlist --format operator
python3 scripts/query_steel_thread_radar.py --report high-relevance --format operator
python3 scripts/query_steel_thread_radar.py --category agent_orchestration --format operator
```

Fetch approved/local sources:
```bash
python3 scripts/fetch_steel_thread_sources.py --format operator
python3 scripts/fetch_steel_thread_sources.py --dry-run --format operator
```

Export:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_steel_thread_radar_read_model.py --format operator
```
