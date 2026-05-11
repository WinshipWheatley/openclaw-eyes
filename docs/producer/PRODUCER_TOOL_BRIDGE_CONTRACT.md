# Producer Tool Bridge Contract

This document defines the `ToolIntentPacket`, a structured payload proposed by the Producer Agent to suggest technical interventions across various creative environments.

## The Tool Intent Packet

The `ToolIntentPacket` is a software-agnostic proposal. It describes *what* should happen, leaving the *how* to the specific tool bridge execution lane.

### Required Fields

- **`intent_type`** (String): Must be one of `create_clip`, `modify_clip`, `suggest_groove`, `suggest_arrangement`, `audition_variant`, `suggest_plugin_chain`, `suggest_sound_design`, `suggest_mix_move`, `suggest_dj_transition`, `suggest_routing_plan`, or `suggest_recording_setup`.
- **`target_environment`** (String): Must be one of `ableton_live`, `logic_pro`, `th_u`, `moog_model_15`, `moog_model_d`, `struna_obscura`, `slate_digital`, `ozone_12`, `djay_pro`, `x32_rack`, `dl16`, `generic_daw`, `generic_audio_interface`, or `unknown`.
- **`title`** (String): A human-readable name for the intent.
- **`musical_goal`** (String): The functional and emotional reason for this intent (e.g., "Saturate the drum bus to add controlled chaos").
- **`emotional_target`** (String): The intended feeling this move should evoke.
- **`constraints`** (Array/String): Rules the executing lane must follow (e.g., "Do not exceed -3dB peak").
- **`human_confirmation_required`** (Boolean): Must always be `true`.
- **`generated_by`** (String): Must be `"producer_agent"`.
- **`source_review_id`** (String): The ID of the `ProducerReview` that spawned this intent.

### Optional Fields

- **`bpm`** (Number/String): Target tempo.
- **`time_signature`** (String): Target meter.
- **`key`** (String): Target key.
- **`track_type`** (String): E.g., "MIDI", "Audio", "Return", "Master".
- **`clip_length_bars`** (Number): For generated or modified clips.
- **`groove_description`** (String): Technical rhythm details (e.g., "swing 16ths 54%").
- **`note_density`** (String): E.g., "sparse", "dense", "syncopated".
- **`rhythmic_reference`** (String): Reference technique to extract rhythm from.
- **`suggested_tools`** (Array): Specific plugins or hardware (e.g., `["Ozone 12 Imager", "Moog Model D"]`).
- **`hardware_context`** (String): Required physical state for execution (e.g., "Ensure DL16 input 1 is patched to X32 channel 1").

---

## Target Environment Scopes

The Producer Agent recognizes a broad creative landscape. The following targets are known possibilities, though the Producer assumes none are active without explicit evidence.

### Ableton Live Bridge
*Implementation Note:* The existence of an Ableton bridge is a known non-authoritative proof. Past experiments successfully used an AbletonMCP Remote Script and a direct local Python socket wrapper to read session info, create MIDI tracks, and fire clips. **This proof lives outside the current OpenClaw repo lane and should not be treated as live runtime status.** Ableton execution remains isolated.

### Logic Pro & Plugin Ecosystem
Targets like Logic Pro, TH-U, Slate Digital, and Ozone 12 are valid `target_environment` values. The Producer will output standard mix/production terminology that a generic DAW controller or human operator could apply.

### Hardware & Studio Topology
Targets like Moog Model 15, Moog Model D, Struna Obscura, X32 Rack, and Midas DL16 represent physical routing and sound design targets. 
*Note:* Naming these in the contract does not claim live state. The physical topology (e.g., DL16 over AES50 to X32 Rack over USB to Mac) belongs to a future studio environment inventory/receipt lane, and must not be assumed live during a standard review.
