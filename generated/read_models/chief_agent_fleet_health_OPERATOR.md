# Chief Agent Fleet Health v0

Generated: 2026-06-23T00:58:26+00:00

## Fleet Health
- Fleet: 4/6 agents online. Online: cassandra, chief, guardian, hermes. Offline: niles. Blockers: niles(offline).
  - Online: cassandra, chief, guardian, hermes
  - Offline: niles

## Sync Health
- Sync: mirror=needs_pc_import, display=waiting_for_pc_import. Last Mac sync: 2026-06-12T10:49:56+00:00 (synced). No blocking sync problems.

## Recent Milestones
Branch: `codex/stress-fixes` — 10 milestones scanned.
- `35ff950b` feat(dank-1): orchestration-progress grounding for the Maestro packet
- `504fa1f2` fix(niles): run producer_listener under chief_env venv (has python-telegram-bot)
- `5f56bdd0` feat(cutover-1): default-OFF control-plane detector wire (supervised, reversible)
- `c758265a` chore(prune-fin): remove dead 'fin' actor from shared-doctrine facts (SD-1/2/4/5/9)
- `37f52ddf` feat(redesign-2/5): register Maestro in agent_lane_registry (close authority leak)

## Sources
- `generated/read_models/agent_presence.json` (present, as-of: 2026-06-23T00:56:59+00:00)
- `generated/read_models/sync_health.json` (present, as-of: 2026-06-23T00:55:03+00:00)
- `git log (shipped feat/fix/chore/perf/refactor commits)` (present, as-of: 2026-06-23T00:58:26+00:00)

## Boundaries
- No agent activation.
- No repair authority.
- No sends.
