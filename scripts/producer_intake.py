import argparse
import sys
import json
from pathlib import Path
import re

# We will import the reviewer directly
try:
    from scripts.producer_review import run_review, check_missing_fields
except ImportError:
    # Handle if run from within scripts dir or similar
    from producer_review import run_review, check_missing_fields

def detect_emotional_target(text):
    emotion_words = [
        "sad", "energetic", "nostalgic", "happy", "angry",
        "spacious", "hard", "driving", "dark", "bright", "cheesy", "boring"
    ]
    found = [word for word in emotion_words if word in text.lower()]
    return ", ".join(found) if found else ""

def detect_target_environment(text):
    text_lower = text.lower()
    if "ableton" in text_lower:
        return "ableton_live"
    if "logic" in text_lower:
        return "logic_pro"
    if "th-u" in text_lower:
        return "th_u"
    if "moog model 15" in text_lower:
        return "moog_model_15"
    if "model d" in text_lower:
        return "moog_model_d"
    if "struna obscura" in text_lower or "struna" in text_lower:
        return "struna_obscura"
    if "slate" in text_lower:
        return "slate_digital"
    if "ozone" in text_lower:
        return "ozone_12"
    if "djay" in text_lower:
        return "djay_pro"
    if "x32" in text_lower:
        return "x32_rack"
    if "dl16" in text_lower:
        return "dl16"
    return "unknown"

def detect_groove(text):
    groove_words = ["four-on-the-floor", "groove", "swing", "rhythm", "beat", "dub", "afro-dub"]
    found = [word for word in groove_words if word in text.lower()]
    return ", ".join(found) if found else ""

def extract_constraints(text):
    constraints = []
    text_lower = text.lower()

    # Split by common punctuation to find clauses
    clauses = re.split(r'[,.;?!]|\band\b|\bbut\b', text_lower)
    for clause in clauses:
        clause = clause.strip()
        if any(word in clause for word in ["don't", "do not", "avoid", "without", "not"]):
            constraints.append(clause)

    return constraints

def load_compiled_context():
    context_path = Path("generated/producer/producer_compiled_context.json")
    if not context_path.exists():
        return {"used": False, "error": "File not found"}
    try:
        with open(context_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "used": True,
                "version": data.get("compiled_context_version", "unknown"),
                "producer_identity_id": data.get("producer_identity", {}).get("id", "unknown")
            }
    except Exception as e:
        return {"used": False, "error": str(e)}

def build_producer_input(text):
    data = {
        "compiled_context": load_compiled_context(),
        "artifact_type": "production_question",
        "title": "Untitled Producer Intake",
        "user_intent": text,
        "emotional_target": detect_emotional_target(text),
        "genre_or_reference_notes": "unknown", # deterministic parser v0: we won't try too hard without an LLM
        "target_environment": detect_target_environment(text),
        "groove_description": detect_groove(text),
        "production_notes": text,
        "constraints": extract_constraints(text),
        "open_questions": []
    }

    if "x32" in text.lower() or "dl16" in text.lower():
        data["hardware_context"] = "mentioned"

    missing = check_missing_fields(data)
    if missing:
        data["open_questions"] = [f"What is the {m}?" for m in missing]

    return data

def generate_tool_intent_packet(text, producer_input):
    text_lower = text.lower()

    # We only trigger this if an action verb implies a tool change.
    action_verbs = ["sketch", "create", "make", "build", "try", "add", "suggest", "audition", "route", "record", "mix", "master", "transition"]

    if not any(verb in text_lower for verb in action_verbs):
        return None

    intent_type = "unknown"

    if any(w in text_lower for w in ["groove", "drums", "beat", "pulse"]):
        intent_type = "suggest_groove"
    elif any(w in text_lower for w in ["clip", "midi", "loop"]):
        intent_type = "create_clip"
    elif any(w in text_lower for w in ["arrangement", "section", "chorus", "bridge", "intro", "outro"]):
        intent_type = "suggest_arrangement"
    elif any(w in text_lower for w in ["plugin", "chain", "effects", "delay", "reverb", "saturation", "compressor"]):
        intent_type = "suggest_plugin_chain"
    elif any(w in text_lower for w in ["mix", "balance", "eq", "compression", "space"]):
        intent_type = "suggest_mix_move"
    elif any(w in text_lower for w in ["master", "ozone", "loudness"]):
        intent_type = "suggest_plugin_chain"
    elif any(w in text_lower for w in ["dj", "transition", "blend"]):
        intent_type = "suggest_dj_transition"
    elif any(w in text_lower for w in ["routing", "x32", "dl16", "input", "output", "record setup"]):
        if "record" in text_lower:
            intent_type = "suggest_recording_setup"
        else:
            intent_type = "suggest_routing_plan"

    packet = {
        "contract_version": "v0",
        "intent_type": intent_type,
        "target_environment": producer_input.get("target_environment", "unknown"),
        "title": f"Suggested {intent_type}",
        "musical_goal": "unknown",
        "bpm": "unknown",
        "time_signature": "unknown",
        "key": "unknown",
        "track_type": "unknown",
        "clip_length_bars": "unknown",
        "groove_description": producer_input.get("groove_description") or "unknown",
        "note_density": "unknown",
        "rhythmic_reference": "unknown",
        "emotional_target": producer_input.get("emotional_target") or "unknown",
        "suggested_tools": "unknown",
        "hardware_context": "mentioned" if producer_input.get("hardware_context") else "unknown",
        "constraints": producer_input.get("constraints") or [],
        "human_confirmation_required": True,
        "generated_by": "producer_agent",
        "source_review_id": "unknown",
        "no_execution_without_approval": True
    }

    return packet

def generate_human_response(producer_input, review, tool_packet=None):
    missing_info = review.get("producer_notes", [""])[0]
    next_move = review.get("next_best_move", "")

    hardware_claim = review.get("hard_flags", [])

    # Text output
    lines = []
    lines.append("=== Producer Intake ===")
    lines.append(f"Diagnosis: {review.get('primary_strength')} / {review.get('main_weakness')}")
    lines.append("")
    lines.append("--- What I can tell from your request ---")
    lines.append(f"Target Environment: {producer_input['target_environment']}")
    lines.append(f"Emotion detected: {producer_input['emotional_target'] or 'None'}")
    lines.append(f"Groove detected: {producer_input['groove_description'] or 'None'}")
    if producer_input["constraints"]:
        lines.append(f"Constraints: {', '.join(producer_input['constraints'])}")

    lines.append("")
    lines.append("--- What is still missing ---")
    if missing_info.startswith("Please provide:"):
        lines.append(missing_info)
    else:
        lines.append("Need to ground this in actual audio receipts next.")

    lines.append("")
    lines.append("--- Next best move ---")
    lines.append(next_move)
    lines.append("")

    if tool_packet:
        lines.append("--- Suggested tool intent ---")
        lines.append(f"Action: {tool_packet['intent_type']}")
        lines.append(f"Target: {tool_packet['target_environment']}")
        lines.append("Why: Based on explicit action verbs in your request.")
        lines.append("[!] This is a suggestion only. Confirmation is required before execution.")
        lines.append("")

    if "hardware_routing_claim_without_receipt" in hardware_claim or "hardware_context" in producer_input:
         lines.append("[!] Note: Hardware mentioned, but does not claim live state without explicit receipts.")
    elif review.get("confidence") == "low":
         lines.append("[!] Note: Missing evidence. Does not claim audio was heard.")

    if any(word in producer_input["user_intent"].lower() for word in ["execute", "bounce", "render", "save", "sketch"]):
        lines.append("[!] Tool action implied. Would require confirmation and a separate execution lane.")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Producer Natural Language Intake v0")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Plain text request")
    group.add_argument("--file", help="Path to text file containing request")
    parser.add_argument("--pretty", action="store_true", help="Format JSON output and print text")
    parser.add_argument("--json-only", action="store_true", help="Only output JSON")
    parser.add_argument("--human-only", action="store_true", help="Only output human readable text, no JSON")
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, "r") as f:
                text = f.read().strip()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = args.text

    producer_input = build_producer_input(text)
    review = run_review(producer_input)
    tool_packet = generate_tool_intent_packet(text, producer_input)

    output_payload = {
        "producer_input": producer_input,
        "producer_review": review
    }

    if tool_packet:
        output_payload["optional_tool_intent_packet"] = tool_packet

    if args.json_only:
        if args.pretty:
            print(json.dumps(output_payload, indent=2))
        else:
            print(json.dumps(output_payload))
    elif args.human_only:
        print(generate_human_response(producer_input, review, tool_packet))
    else:
        human_text = generate_human_response(producer_input, review, tool_packet)
        if args.pretty:
            print(human_text)
            print("\n--- JSON Payload ---")
            print(json.dumps(output_payload, indent=2))
        else:
            print(human_text)

if __name__ == "__main__":
    main()
