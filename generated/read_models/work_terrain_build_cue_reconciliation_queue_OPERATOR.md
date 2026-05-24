# OpenClaw Work Terrain Build Cue / Reconciliation Queue v0

## ELIWINSHIP Summary

This read-model converts Work Terrain gaps into structured candidates for active development or reconciliation.
It prevents good ideas from floating in chat doctrine and solves the '1000 good ideas where nothing lands' problem.
It is strictly planning/read-model only: no automatic building, file mutation, or active execution is allowed.

## Default Candidates

- **Agent Execution Packet Compiler Relationship Cue**: `RELATIONSHIP_NEEDS_ENCODING` (IMPLEMENTED_TESTED)
  - *Why it matters*: Ensures the relationship between the packet compiler and context selection is strictly represented.
  - *Next Safe Move*: Reconcile with Chief and Hermes, then add relationship record.
- **Operator Question Assist / Scope Expansion Cue**: `DOCTRINE_ONLY_BUILD_CANDIDATE` (DOCTRINE_ONLY)
  - *Why it matters*: Winship wants smart help that expands scope and helps answer unfamiliar questions safely.
  - *Next Safe Move*: Present design choices to operator before building.
- **Capital Hilton Capture Rail Cue**: `PARTLY_BUILT_COMPLETION_CANDIDATE` (PARTLY_BUILT)
  - *Why it matters*: Connects the manual capture UI to backend proof metadata rails.
  - *Next Safe Move*: Implement safe guided capture writer contract.
- **Starship Operating Model Stable-Map Cue**: `BUILT_MISSING_STABLE_MAP_CANDIDATE` (IMPLEMENTED_TESTED)
  - *Why it matters*: Integrates Starship commands (Bridge, Worlds, Below Deck) into the dynamic stable-map mapping.
  - *Next Safe Move*: Add stable-map definition and run stable-map refresh in final prompt.
- **Screenshot Harness / Accessibility Cue**: `PARKED_REVISIT_CANDIDATE` (PARKED)
  - *Why it matters*: Leverages Mac accessibility IDs to perform screenshot verification.
  - *Next Safe Move*: Revisit after Mac-import layer is approved.

## Queue Definition

- Queue ID: `reconciliation_queue_v0`
- Priority Order: packet_compiler_relationship_cue, starship_operating_model_cue, capital_hilton_capture_rail_cue, operator_question_assist_cue, screenshot_harness_accessibility_cue
- Stale Candidate Policy: Filter stale prompts from active queue; log them in historical logs only.
- Supersession Policy: Ensure old docs remain traceable but keep them out of active build priority.
- Safety Filter Policy: Strict safety gating: unsafe or unauthorized candidates are placed in quarantine.

## Safety and Authority Boundaries

- All auto-build and auto-dispatch flags are strictly disabled (`false`).
- No file mutations, stable-map promotions, or active tool/agent executions are permitted here.
- The operator remains the final sovereign authority.
