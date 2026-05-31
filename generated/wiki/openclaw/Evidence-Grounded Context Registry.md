# Evidence-Grounded Context Registry

Status: PARTIAL

## Short human summary
The context layer is intended to stay deterministic: stable registries, SQLite/read-model exports, receipts, proof references, and compiled Markdown views.

## Confirmed facts
- OpenClaw context v0 is deterministic registry/read-model/receipt work, not generic vector RAG.
- The generated wiki is a compiled view over those structures and does not become source truth.
- Evidence-Grounded Context Registry status: PRESENT_ON_REVIEW_BRANCH on codex/system-knowledge-registry-v0-local at 1a6b7b0b463968f3161e048bd7936dc06505a3bb.
- Registry notes: Resolved from openclaw-eyes branch ref; not canonical or merged to main.

## Known unknowns
- Where should the canonical system knowledge registry live? [generated/read_models/openclaw_estate_topology_registry.json]
- Why Codex Web commits were not reachable from GitHub remotes. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime. [generated/read_models/openclaw_estate_topology_registry.json]
- Which repo Hermes should read first for estate-wide task planning. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

## Tension / contradiction signals
- Input source missing: Expected generated wiki input is missing: generated/system_knowledge/openclaw_system_knowledge_registry.*.
- Codex Web commit unreachable: openclaw-eyes commit 33e00a6 is recorded as unreachable.
- Codex Web commit unreachable: openclaw-eyes commit 4ca4ed42171c23d60ef89493559808ef2789a19e is recorded as unreachable.
- Status conflict in source fields: codex_web_artifacts.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW'}.
- Status conflict in source fields: registry_presence.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.
- Status conflict in source fields: source_of_truth_areas.8 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.

## Next useful actions
- Keep registry commits pending review until reachable and merged.
- Record new facts upstream in registries/read-models/receipts, then regenerate the wiki.

## What not to do
- Do not introduce generic vector RAG or LM synthesis in v0.
- Do not hardcode volatile branch commits as source truth.
- Do not smooth over contradictory source statuses.

## Source refs / input read-model refs
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/system_knowledge/openclaw_system_knowledge_registry.* (openclaw_system_knowledge_registry_files, missing)

Last generated timestamp: 2026-05-31T03:40:20+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
