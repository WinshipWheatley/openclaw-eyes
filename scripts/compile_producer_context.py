import os
import sys
import json
import yaml
from pathlib import Path

def load_yaml(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def compile_context() -> dict:
    base_dir = Path(__file__).parent.parent

    rubric_path = base_dir / "config" / "producer" / "producer_rubric.yaml"
    env_path = base_dir / "config" / "producer" / "producer_environment_targets.yaml"
    ref_path = base_dir / "config" / "producer" / "producer_reference_map.yaml"

    rubric = load_yaml(rubric_path) if rubric_path.exists() else {}
    env_targets = load_yaml(env_path) if env_path.exists() else {}
    refs = load_yaml(ref_path) if ref_path.exists() else {}

    # Extract pillars/categories from rubric
    scoring_categories = rubric.get('scoring_categories', {})
    hard_flags = rubric.get('hard_flags', [])

    env_data = env_targets.get('environment_targets', env_targets) # adjust if nested
    ref_data = refs.get('references', refs)

    context = {
        "compiled_context_version": "0.1",
        "compiled_from": [
            "docs/producer/PRODUCER_ARCHETYPE.md",
            "config/producer/producer_rubric.yaml",
            "config/producer/producer_environment_targets.yaml",
            "config/producer/producer_reference_map.yaml"
        ],
        "producer_identity": {
            "id": "rhythm_governed_cinematic_alt_producer",
            "summary": "Deterministic creative judgment layer enforcing Six Pillars. Does not execute operations.",
            "role": "creative_judgment_layer",
            "not_roles": [
                "executor",
                "router",
                "guardian",
                "simple_assistant"
            ]
        },
        "priority_weights": {
            "rhythmic_spine": 10,
            "spatial_architecture": 9,
            "emotional_truth": 10,
            "controlled_chaos": 8,
            "polished_indie_illusion": 8,
            "mythic_social_lyricism": 7,
            "healing_dance_transcendence": 9,
            "accessibility": 7,
            "restraint": 8,
            "identity_alignment": 10,
            "structure_motion": 8
        },
        "hard_rules": [
            "do_not_mimic_references",
            "do_not_claim_audio_without_evidence",
            "do_not_claim_live_tool_state_without_receipt",
            "do_not_execute_tools",
            "human_confirmation_required_for_actions",
            "chief_or_execution_lane_required_for_mutation",
            "protect_humanity_over_polish"
        ],
        "pillars": scoring_categories,
        "hard_flags": hard_flags,
        "reference_quality_map": ref_data,
        "environment_targets": env_data,
        "allowed_default_behavior": [
            "review",
            "critique",
            "suggest",
            "produce_tool_intent_packet"
        ],
        "forbidden_default_behavior": [
            "execute_tools",
            "mutate_daw_sessions",
            "write_files_without_lane",
            "claim_audio_was_heard_without_evidence",
            "claim_hardware_or_software_live_state_without_receipt"
        ],
        "runtime_notes": {
            "docs_are_source_explanation_not_runtime_payload": True,
            "compiled_context_is_runtime_payload": True,
            "no_side_effects_default": True
        }
    }
    return context

def main():
    if len(sys.argv) < 2:
        print("Usage: compile_producer_context.py [--write | --check | --print]")
        sys.exit(1)

    mode = sys.argv[1]
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "generated" / "producer"
    output_path = output_dir / "producer_compiled_context.json"

    try:
        context = compile_context()
        context_json = json.dumps(context, indent=2, sort_keys=True)
    except Exception as e:
        print(f"Error compiling context: {e}")
        sys.exit(1)

    if mode == "--print":
        print(context_json)

    elif mode == "--write":
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(context_json + "\n")
        print(f"Successfully wrote {output_path}")

    elif mode == "--check":
        if not output_path.exists():
            print(f"Error: {output_path} does not exist.")
            sys.exit(1)

        with open(output_path, 'r', encoding='utf-8') as f:
            existing_json = f.read()

        if existing_json != context_json + "\n":
            print(f"Error: {output_path} is out of date. Run with --write to regenerate.")
            sys.exit(1)
        print("Check passed: compiled context is up to date.")

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
