import json
import argparse
import sys
import uuid

def check_missing_fields(data):
    required = ["artifact_type", "title", "user_intent", "emotional_target", "genre_or_reference_notes"]
    missing = [req for req in required if req not in data or not data[req]]
    return missing

def evaluate_hard_flags(data):
    flags = []
    
    # 1. Groove collapses
    groove = data.get("groove_description", "")
    if not groove:
        flags.append("groove_collapses")

    # 2. Too cluttered
    instruments = data.get("instrumentation", [])
    if isinstance(instruments, list) and len(instruments) > 8:
        flags.append("too_cluttered")
    elif isinstance(instruments, str) and len(instruments.split(",")) > 8:
        flags.append("too_cluttered")
        
    production_notes = data.get("production_notes", "")
    if "dense" in production_notes.lower() or "wall of sound" in production_notes.lower():
         if "too_cluttered" not in flags:
             flags.append("too_cluttered")

    # 3. Too much reference mimicry
    intent = data.get("user_intent", "").lower()
    if "copy" in intent or "just like" in intent or "clone" in intent:
        flags.append("too_much_reference_mimicry")

    # 4. Emotional target missing -> handled in confidence, but let's check if it's there
    if not data.get("emotional_target"):
        flags.append("emotion_overexplained") # Actually missing, but maybe no specific flag, let's just keep confidence low.

    # 5. Execution suggested without confirmation
    if "execute" in intent or "bounce" in intent or "render" in intent or "save" in intent:
        flags.append("execution_suggested_without_confirmation")

    # 6. Tool / Hardware without evidence
    # Since this is v0, any mention of hardware_context without a 'receipt' field triggers this
    if "hardware_context" in data:
        flags.append("hardware_routing_claim_without_receipt")
    
    available_tools = data.get("available_tools", [])
    if available_tools:
        flags.append("tool_specific_claim_without_evidence")

    return flags

def run_review(input_data):
    missing_fields = check_missing_fields(input_data)
    flags = evaluate_hard_flags(input_data)
    
    confidence = "medium"
    if missing_fields:
        confidence = "low"
    
    if not input_data.get("emotional_target"):
        confidence = "low"

    # Base review template
    review = {
      "producer_contract_version": "0.1",
      "review_id": str(uuid.uuid4()),
      "artifact_type": input_data.get("artifact_type", "unknown"),
      "target_environment": input_data.get("target_environment", "unknown"),
      "song_identity": "A track in development",
      "primary_strength": "Clear intent" if not missing_fields else "Incomplete concept",
      "main_weakness": f"Missing required fields: {', '.join(missing_fields)}" if missing_fields else "Lacks rich evidence",
      "scores": {
        "rhythmic_spine": 2 if "groove_collapses" in flags else 7,
        "spatial_architecture": 5,
        "emotional_truth": 3 if not input_data.get("emotional_target") else 7,
        "controlled_chaos": 5,
        "polished_indie_illusion": 5,
        "mythic_social_lyricism": 5,
        "healing_dance_transcendence": 5,
        "accessibility": 5,
        "restraint": 3 if "too_cluttered" in flags else 7,
        "identity_alignment": 5,
        "structure_motion": 5
      },
      "hard_flags": flags,
      "arrangement_diagnosis": {
        "intro": "",
        "verse": "",
        "pre_chorus": "",
        "chorus": "",
        "bridge": "",
        "outro": ""
      },
      "pillar_alignment": {
        "rhythmic_spine": "Weak groove metadata." if "groove_collapses" in flags else "Solid foundation.",
        "spatial_architecture": "Unverified.",
        "controlled_chaos": "Unverified.",
        "polished_indie_illusion": "Unverified.",
        "mythic_social_lyricism": "Unverified.",
        "healing_dance_transcendence": "Unverified."
      },
      "tool_environment_notes": "No execution permitted without receipt.",
      "producer_notes": [
          f"Please provide: {', '.join(missing_fields)}" if missing_fields else "Good start. We need to ground this in actual audio receipts next."
      ],
      "do_not_change": [],
      "next_best_move": "Fill missing fields" if missing_fields else "Gather actual evidence receipts",
      "agentic_prompt_packet": {
        "allowed_agentic_behavior": "critique_only",
        "summary_for_agent": "Awaiting audio evidence.",
        "questions_for_agent": []
      },
      "optional_tool_intent_packet": None,
      "confidence": confidence,
      "no_side_effects": True
    }
    return review

def main():
    parser = argparse.ArgumentParser(description="Producer Deterministic Reviewer v0")
    parser.add_argument("--input", required=True, help="Path to ProducerInput JSON")
    parser.add_argument("--pretty", action="store_true", help="Format JSON output")
    args = parser.parse_args()

    try:
        with open(args.input, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    review = run_review(data)
    
    if args.pretty:
        print(json.dumps(review, indent=2))
    else:
        print(json.dumps(review))

if __name__ == "__main__":
    main()
