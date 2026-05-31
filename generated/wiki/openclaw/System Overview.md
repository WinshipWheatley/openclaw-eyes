# System Overview

Status: PARTIAL

## Short human summary
OpenClaw is currently described as a PC backend/read-model workspace plus Mac app, Mac edge/helper responsibilities, openclaw-eyes context, openclaw-runtime actor work, and a bridge transport layer.

## Confirmed facts
- Current topology repos: ['openclaw-eyes', 'openclaw-mission-control', 'openclaw-runtime']
- PC backend working copy: pc_openclaw_eyes_backend
- Mac app working copy: mac_mission_control_app
- Bridge transport: /mnt/e/openclaw <-> /Volumes/openclaw_e
- Codex Web artifacts are source truth: False
- pc_openclaw_eyes_backend: openclaw-eyes on pc as PC_BACKEND (DIRTY, remote CONFIRMED).
- pc_openclaw_runtime: openclaw-runtime on pc as RUNTIME_ACTORS (CLEAN, remote CONFIRMED).
- mac_mission_control_app: OpenClaw Mission Controle on mac as MAC_APP (DIRTY, remote MISSING).
- mac_openclaw_eyes_context: openclaw-eyes on mac as EYES_CONTEXT_REPO (CLEAN, remote UNKNOWN).
- mac_openclaw_runtime: openclaw-runtime on mac as RUNTIME_ACTORS (CLEAN, remote UNKNOWN).
- Codex Web commit 33e00a6 for openclaw-eyes is UNREACHABLE and not installed source truth.
- Codex Web commit 4ca4ed42171c23d60ef89493559808ef2789a19e for openclaw-eyes is UNREACHABLE and not installed source truth.

## Known unknowns
- Why Codex Web commits were not reachable from GitHub remotes. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime. [generated/read_models/openclaw_estate_topology_registry.json]
- Which repo Hermes should read first for estate-wide task planning. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

## Tension / contradiction signals
- Reference target unavailable: estate_topology_registry_read_model_mirror resolved as MISSING.
- Mac local path unreachable from PC: /Users/hwinshipwheatley/Eyes is marked LOCAL_PATH_UNREACHABLE.
- Mac bridge unavailable: openclaw_eyes_registry_review_branch has mac_bridge_status=MAC_BRIDGE_UNAVAILABLE.
- Codex Web commit unreachable: openclaw-eyes commit 33e00a6 is recorded as unreachable.
- Codex Web commit unreachable: openclaw-eyes commit 4ca4ed42171c23d60ef89493559808ef2789a19e is recorded as unreachable.
- Status conflict in source fields: codex_web_artifacts.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW'}.
- Status conflict in source fields: registry_presence.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.
- Status conflict in source fields: source_of_truth_areas.8 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.

## Next useful actions
- Install estate topology registry in /home/openclaw. (CONFIRMED; owner PC_BACKEND)
- Mirror registry read-model to Mac. (PLANNED; owner BRIDGE_TRANSPORT)
- Add Mission Control app remote/back-up strategy. (PLANNED; owner MAC_APP)
- Keep system knowledge registry pending review until merged to main. (PENDING_REVIEW; owner PC_BACKEND)
- Build cross-registry merge only after each repo's registry is reachable locally. (PLANNED; owner PC_BACKEND)

## What not to do
- Do not treat Codex Web unreachable commits as installed code.
- Do not route Swift app ownership into the PC backend by convenience.
- Do not collapse bridge transport into source truth.

## Source refs / input read-model refs
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/read_models/estate_topology.json (estate_topology)
- generated/read_models/openclaw_estate_node_registry.json (openclaw_estate_node_registry)

Last generated timestamp: 2026-05-31T03:40:20+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
