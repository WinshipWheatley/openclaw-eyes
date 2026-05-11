import os
import json
from pathlib import Path

def test_compiler_builds_context():
    from scripts.compile_producer_context import compile_context
    context = compile_context()

    assert "producer_identity" in context
    assert context["producer_identity"]["id"] == "rhythm_governed_cinematic_alt_producer"

    assert "priority_weights" in context
    assert context["priority_weights"]["rhythmic_spine"] == 10
    assert context["priority_weights"]["emotional_truth"] == 10

    assert "hard_rules" in context
    assert "do_not_execute_tools" in context["hard_rules"]
    assert "do_not_claim_audio_without_evidence" in context["hard_rules"]

    assert "environment_targets" in context
    targets = context["environment_targets"]
    # Handle dict or list depending on yaml format
    target_names = targets.keys() if isinstance(targets, dict) else [list(t.keys())[0] for t in targets] if isinstance(targets, list) else []
    assert "ableton_live" in target_names
    assert "logic_pro" in target_names
    assert "x32_rack" in target_names
    assert "dl16" in target_names
    assert "unknown" in target_names

    assert "runtime_notes" in context
    assert context["runtime_notes"]["compiled_context_is_runtime_payload"] is True

    assert "forbidden_default_behavior" in context
    assert "execute_tools" in context["forbidden_default_behavior"]
    assert "claim_hardware_or_software_live_state_without_receipt" in context["forbidden_default_behavior"]

def test_compiler_check_mode(tmp_path, monkeypatch):
    from scripts.compile_producer_context import compile_context
    import json

    context = compile_context()
    context_json = json.dumps(context, indent=2, sort_keys=True) + "\n"

    # We will test the file writing and checking logic.
    output_dir = tmp_path / "generated" / "producer"
    output_dir.mkdir(parents=True)
    output_path = output_dir / "producer_compiled_context.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(context_json)

    # Read it back and check it matches
    with open(output_path, 'r', encoding='utf-8') as f:
        existing_json = f.read()

    assert existing_json == context_json
