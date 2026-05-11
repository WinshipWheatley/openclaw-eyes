# Producer Machine Contract

This document defines the deterministic inputs and outputs required to invoke the Producer Agent's judgment layer.

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
- **`hard_flags`** (Array): Immediate warnings regarding generic choices, loss of emotion, or pillar violations.
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
