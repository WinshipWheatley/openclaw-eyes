# Producer Machine Contract

**STATUS: ACTIVE / COMPILED CONTEXT**
**VERSION: v0.1 Runtime / v1.0 Schema Target**

> "This is compiled context, not fuzzy memory."

This document defines the deterministic inputs, outputs, and execution boundaries required to invoke the Producer Agent's (Niles) judgment layer. The contract acts as the governor, rulebook, and schema authority. Runtime packets are instances emitted under this contract.

## Core Doctrine

### Context Payload Discipline
- **Compact & Potent**: Packets must be minimized for context efficiency.
- **Evidence over Authority**: Prior chat history is treated as evidence of intent, not as an overriding authority.
- **Staged Packets**: Staged, structured packets are preferred over bloated, raw context streams.

### Infrastructure & Routing (Shared)
- **Model Agnostic**: Packets must not hardcode specific LLM models.
- **Lane Ready**: Model, tool, and chat selection belongs to the shared routing infrastructure (e.g., Chief or an Execution Lane), not the individual packet.

---

## Runtime: The "Explain" Packet

When running with `--explain`, the `producer_intake.py` script emits an **Agent Intake / Action Intent Packet**. This bridges deterministic extraction and agentic intent.

### Explain Packet Fields (v0)
- **`original_text`**: The raw input string from the user.
- **`detected_intent`**: The primary creative goal (e.g., "vocal space", "groove focus").
- **`detected_environment`**: Targeted environments (e.g., `ableton`, `logic`, `x32`, `staged`).
- **`detected_taste_terms`**: Keywords indicating aesthetic preference or "vibe".
- **`detected_tools_or_platforms`**: Specific hardware/software detected in the input.
- **`evidence_level`**: Current state of proof (e.g., `text_only_no_audio`).
- **`suggested_move`**: The specific v0 identifier for the recommended action.
- **`allowed_actions`**: Explicitly permitted next steps (e.g., `["suggestion_only"]`).
- **`blocked_actions`**: Explicitly forbidden moves (e.g., `["audio_analysis_claims"]`).
- **`boundary_notes`**: Contextual reminders of system limits.
- **`response_template_key`**: Identifier for the deterministic response template used.

### Current v0 Suggested Move Identifiers
- `add_arrival_point_without_clutter`
- `widen_delay_return_preserve_vocal_clarity`
- `sketch_spacious_groove_suggestion_only`
- `production_optimization_suggestion` (Fallback only; specific identifiers preferred)

---

## Execution Boundaries

The following boundaries are enforced at the runtime and contract level:

1.  **no_side_effects**: Must always be `true`. The Producer layer provides judgment, not execution.
2.  **Suggestion Only**: Currently restricted to creative and technical advice.
3.  **BLOCKED: Audio Analysis Claims**: No agent may claim live audio analysis without a deterministic receipt.
4.  **BLOCKED: Hardware/DAW Execution**: Direct mutation of Ableton, Logic, X32, or DL16 state is forbidden without a separate execution lane.
5.  **BLOCKED: Hidden Authority**: Use of "hidden" logic or raw LLM inference outside of the compiled context is prohibited.

---

## ProducerInput Semantics

The `ProducerInput` payload must be a structured representation of the creative artifact to be reviewed.

### Expected Fields

- **`artifact_type`** (Required, String): Must be one of `lyric`, `song_brief`, `arrangement_map`, `mix_notes`, `ableton_clip_summary`, `logic_project_summary`, `daw_session_summary`, `plugin_chain_summary`, `hardware_routing_summary`, `demo_review`, `setlist`, or `production_question`.
- **`title`** (Required, String): The name of the track, project, or concept.
- **`user_intent`** (Required, String): What the user is trying to achieve with this artifact.
- **`emotional_target`** (Required, String): The desired emotional response from the listener.
- **`genre_or_reference_notes`** (Required, String): Stylistic guidelines or reference material.
- **`target_environment`** (Optional, String): The intended software/hardware environment (e.g., `ableton_live`).
- **`lyric_text`** (Optional, String): The raw lyric text, if applicable.
- **`arrangement_sections`** (Optional, Array): Structured list of song sections.
- **`bpm`** (Optional, Number/String): Tempo information.
- **`key`** (Optional, String): Musical key.
- **`time_feel`** (Optional, String): E.g., "straight", "swung", "pushing ahead".
- **`instrumentation`** (Optional, Array/String): Expected or current instruments.
- **`groove_description`** (Optional, String): Narrative description of the rhythm section.
- **`production_notes`** (Optional, String): Current production status or ideas.
- **`known_references`** (Optional, Array): Specific reference tracks or artists.
- **`available_tools`** (Optional, Array): Specific plugins, synths, or hardware available for this task.
- **`hardware_context`** (Optional, String): Current studio routing or physical gear state.
- **`constraints`** (Optional, Array/String): Hard limits on the production.
- **`do_not_change`** (Optional, Array/String): Elements that are locked and must remain untouched.
- **`open_questions`** (Optional, Array): Specific questions the user wants the Producer to answer.

## ProducerReview Semantics

The `ProducerReview` is the deterministic output from the Producer Agent, evaluating the `ProducerInput`.

### Required Fields

- **`producer_contract_version`** (String): Version of this schema (e.g., "v1.0").
- **`review_id`** (String): Unique identifier for this review instance.
- **`artifact_type`** (String): Echoed from input.
- **`target_environment`** (String): Echoed or inferred target.
- **`song_identity`** (String): A brief summary of what the song currently is vs. what it wants to be.
- **`primary_strength`** (String): The most compelling element of the current artifact.
- **`main_weakness`** (String): The critical flaw holding the artifact back.
- **`scores`** (Object): Numerical scores (1-10) aligned with the Six Pillars.
- **`hard_flags`** (Array): Immediate warnings regarding generic choices, loss of emotion, or pillar violations (e.g., `too_generic`, `groove_collapses`).
- **`arrangement_diagnosis`** (String): Assessment of the song's structure and flow.
- **`pillar_alignment`** (Object): Detailed notes on how the artifact aligns with each of the Six Pillars.
- **`tool_environment_notes`** (String): Suggestions specific to the `target_environment` (if known).
- **`producer_notes`** (String): Free-form, tough-love advice and creative direction.
- **`do_not_change`** (Array): Elements the Producer agrees should not be altered.
- **`next_best_move`** (String): The single most important action the user should take next.
- **`agentic_prompt_packet`** (String): A condensed string of instructions intended for Chief or another executing agent to follow.
- **`optional_tool_intent_packet`** (Object | Null): A structured `ToolIntentPacket` if the Producer suggests a specific technical intervention.
- **`confidence`** (Number): 1-10 rating of how sure the Producer is about this review given the input context.
- **`no_side_effects`** (Boolean): Must always be `true`, confirming the Producer merely reviewed and did not execute changes.

---

## FUTURE / ROADMAP (Not Yet Implemented)

### Hardware & Audio Receipts
- Implementation of deterministic receipts for hardware state (X32) and audio analysis results.
- No agent may claim live state without these receipts.

### Plugin Doctrine
- **Manifest-Backed**: Plugins are narrow, capability bundles containing scripts, hooks, MCP tools, prompts, schemas, tests, fixtures, permissions, and runtime adapters.
- **Chained Execution**: Complex jobs should chain narrow plugins in series or parallel.
- **Suggested vs. Executed**: Known plugin capability does not equal execution permission.

### Deep Pocket Records Direction
- **Readiness Packets**: Album, song, and release readiness will compile into structured packets.
- **Niles Oversight**: Niles provides creative and production readiness signals.
- **Authority Lanes**: Routing to publishing, legal, CPA, and final approval checks via Chief or specific authority lanes.

### Explainability: "Why did you say that?"
- Niles must eventually provide provenance for all claims, including:
  - Evidence/Context used.
  - Detected terms and intent.
  - Missing evidence warnings.
  - Provenance of rules and weights.
