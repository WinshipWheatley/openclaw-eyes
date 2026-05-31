# Reference Resolver

Status: PARTIAL

## Short human summary
The resolver separates stable references from volatile resolved values and records drift, unreachable paths, dirty working copies, and mirror status.

## Confirmed facts
- Reference targets: 2; resolutions: 2; drift_count: 0.
- Stable refs live in canonical inputs; resolved volatile values live in generated read-models.
- openclaw_eyes_registry_review_branch: branch=codex/system-knowledge-registry-v0-local, head=1a6b7b0b463968f3161e048bd7936dc06505a3bb, remote=RESOLVED_REMOTE, local=UNREACHABLE, dirty=DIRTY, Mac mirror=LOCAL_PATH_UNREACHABLE.
- Resolution openclaw_eyes_registry_review_branch: status=RESOLVED_REMOTE, value=1a6b7b0b463968f3161e048bd7936dc06505a3bb.
- Resolution estate_topology_registry_read_model_mirror: status=MISSING, value=sha256:8b3e48e23dd812e3f2fe8178bee322c9e0557192aa7e48bb55734f1a811258c1.
- Rule: Canonical sources store stable refs.
- Rule: Generated read-models store resolved values.
- Rule: Do not manually hardcode branch commit hashes as source truth.
- Rule: Resolve Git branches from local working copy, read-only remote, then Mac bridge when configured.
- Rule: If a repo or branch cannot be reached, mark the exact unavailable path and leave the resolved value blank.
- Rule: If a working copy is dirty, record dirty_status=DIRTY without copying it as source truth.
- Rule: If source and bridge hashes differ, mark DRIFT.

## Known unknowns
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

## Tension / contradiction signals
- Reference target unavailable: estate_topology_registry_read_model_mirror resolved as MISSING.
- Mac local path unreachable from PC: /Users/hwinshipwheatley/Eyes is marked LOCAL_PATH_UNREACHABLE.
- Mac bridge unavailable: openclaw_eyes_registry_review_branch has mac_bridge_status=MAC_BRIDGE_UNAVAILABLE.

## Next useful actions
- Resolve Mac bridge/mirror availability before trusting mirrored read-model state.
- Investigate any resolver drift before consuming resolved values downstream.
- Keep branch refs stable and resolve commits at export time.

## What not to do
- Do not fetch, pull, push, or mutate repos from this wiki compiler.
- Do not copy dirty working-copy state as source truth.
- Do not manually hardcode resolved branch commits into canonical source fields.

## Source refs / input read-model refs
- generated/system_knowledge/openclaw_reference_resolver.sqlite (reference_resolver_sqlite)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)

Last generated timestamp: 2026-05-31T03:40:20+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
