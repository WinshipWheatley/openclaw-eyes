# Evidence-Grounded Context Registry

Status: PARTIAL

## Short human summary
The context layer is intended to stay deterministic: stable registries, SQLite/read-model exports, receipts, proof references, and compiled Markdown views.

## Confirmed facts
- OpenClaw context v0 is deterministic registry/read-model/receipt work, not generic vector RAG.
- The generated wiki is a compiled view over those structures and does not become source truth.
- Business-object audit freshness: FRESH.
- Business-object audit generated_at: 2026-05-31T21:35:23+00:00.
- Business-object audit inputs tracked: 14.
- Business-object audit missing inputs: none.
- Business-object audit stale reasons: none.
- Evidence-Grounded Context Registry status: CANONICAL_ON_MAIN on main at 1a6b7b0b463968f3161e048bd7936dc06505a3bb.
- Registry notes: Resolved from openclaw-eyes main; review branch remains historical evidence.
- openclaw-eyes system knowledge registry imported as read-only external input.
- External registry source: openclaw-eyes main at 1a6b7b0b463968f3161e048bd7936dc06505a3bb.

## Known unknowns
- Why Codex Web commits were not reachable from GitHub remotes. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime. [generated/read_models/openclaw_estate_topology_registry.json]
- Which repo Hermes should read first for estate-wide task planning. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

## Tension / contradiction signals
- Codex Web commit unreachable: openclaw-eyes commit 33e00a6 is recorded as unreachable.
- Codex Web commit unreachable: openclaw-eyes commit 4ca4ed42171c23d60ef89493559808ef2789a19e is recorded as unreachable.

## Next useful actions
- Keep external registry imports read-only and regenerate after canonical source changes.
- Record new facts upstream in registries/read-models/receipts, then regenerate the wiki.

## What not to do
- Do not introduce generic vector RAG or LM synthesis in v0.
- Do not hardcode volatile branch commits as source truth.
- Do not smooth over contradictory source statuses.

## Source refs / input read-model refs
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/read_models/external_system_knowledge_registry_index.json (external_system_knowledge_registry_index)
- generated/read_models/openclaw_business_object_layer_audit.json (business_object_layer_audit)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.json (openclaw_system_knowledge_registry_ff49c5bc4e)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.sqlite (openclaw_system_knowledge_registry_61df5235c0)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_OPERATOR.md (openclaw_system_knowledge_registry_fc9549f5cc)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_SCHEMA.sql (openclaw_system_knowledge_registry_d500da978d)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_SEED.sql (openclaw_system_knowledge_registry_b7961063f8)

Last generated timestamp: 2026-05-31T21:39:09+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
