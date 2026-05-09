# OpenClaw Map Room Index & Legend

This directory is the durable Map Room for OpenClaw. It contains navigation artifacts that establish ground truth about what is built, what is pending, what to check before building, and how to route next actions.

Future workers must enter the Map Room and consult the relevant artifacts before proposing work, to ensure deterministic navigation and prevent duplication.

**Important:** Not every artifact in the Map Room is itself a map. The room contains different types of artifacts, each with a specific purpose.

## Artifact Taxonomy

- **Frontier Map:** An actual territory map documenting built, partial, not-built, blocked, unknown, and next unfinished edges for a specific lane. Built claims must cite exact proof.
- **Discovery Guide:** A prior-art or no-build source guide. It lists sources to check before proposing custom builds. It is **not** a full territory map and does **not** grant approval to install, connect, or execute.
- **Route Card:** (Future) A deterministic routing artifact for next steps.
- **Atlas:** (Future) A cross-map inventory.
- **Doctrine / Legend:** Rules for how navigation artifacts stay true (this document).

## Map Room Catalog

- [Compiled Knowledge Substrate Frontier Map](./COMPILED_KNOWLEDGE_SUBSTRATE_FRONTIER_MAP.md) - [Frontier Map] Tracks the compiled_knowledge_substrate territory.
- [No-Build / Prior-Art Sources](./NO_BUILD_PRIOR_ART_SOURCES.md) - [Discovery Guide] A check-before-building guide to prevent reinventing existing tools.
- [File Territory / Cleanup Readiness Map](./FILE_TERRITORY_CLEANUP_READINESS_MAP.md) - [Readiness Map] A read-only map defining what exists and dependencies before any cleanup.
- [Dependency Owner Candidate Move Map](./DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md) - [Readiness Map] Classifies file path dependencies by ownership and risk to safely plan future cleanup candidates.
- [Targeted Dry-Run Candidate Move Plan v0](./TARGETED_DRY_RUN_CANDIDATE_MOVE_PLAN_V0.md) - [Readiness Map] A dry-run candidate plan targeting low-risk generated index noise.
- [Plugin Domain Registry v0](./PLUGIN_DOMAIN_REGISTRY.md) - [Registry] A durable registry for future OpenClaw plugin/workflow-package domains defining value spaces and boundaries before implementation.
- **Map Room Query v0:** The read-only lookup surface (`map_room_query.py`) that answers file territory questions purely from durable truth.

## Core Navigation Doctrine

- **Truth Surfaces, Not Authority:** Navigation maps and guides are truth surfaces. They do **not** grant execution authority. Install, use, call, and execute actions still require normal operator gates and covenants.
- **Defects:**
  - A false map is worse than no map and is a defect.
  - Stale map entries are defects. Completed work must not remain pending; unproven work must not be listed as built.
- **Map Requirements:**
  - Each Frontier Map must explicitly name its territory/lane.
  - Every built claim in a Frontier Map must cite proof (a commit, file/module, test, receipt command, or explicit operator promotion).
- **Updates Require Proof:** Modifying a map's "built" territory requires citing the proof that justifies the change.
