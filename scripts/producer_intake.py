import argparse
import sys
import json
from pathlib import Path
import re

try:
    from scripts.producer_review import run_review, check_missing_fields
except ImportError:
    from producer_review import run_review, check_missing_fields

def detect_emotional_target(text):
    emotion_words = ["sad", "energetic", "nostalgic", "happy", "angry", "spacious", "hard", "driving", "dark", "bright", "cheesy", "boring"]
    found = [word for word in emotion_words if word in text.lower()]
    return ", ".join(found) if found else ""

def detect_target_environment(text):
    text_lower = text.lower()
    if "ableton" in text_lower: return "ableton_live"
    if "logic" in text_lower: return "logic_pro"
    return "unknown"

def detect_groove(text):
    groove_words = ["groove", "dub", "afro-dub", "beat"]
    found = [word for word in groove_words if word in text.lower()]
    return ", ".join(found) if found else ""

def extract_constraints(text):
    constraints = []
    text_lower = text.lower()
    clauses = re.split(r'[,.;?!]|\band\b|\bbut\b', text_lower)
    for clause in clauses:
        clause = clause.strip()
        if any(word in clause for word in ["don't", "do not", "avoid", "without", "not"]):
            constraints.append(clause)
    return constraints

def load_compiled_context():
    context_path = Path("generated/producer/producer_compiled_context.json")
    if not context_path.exists(): return {"used": False}
    try:
        with open(context_path, "r", encoding="utf-8") as f:
            return {"used": True}
    except: return {"used": False}

def build_producer_input(text):
    return {
        "compiled_context": load_compiled_context(),
        "artifact_type": "production_question",
        "title": "Untitled Producer Intake",
        "user_intent": text,
        "emotional_target": detect_emotional_target(text),
        "genre_or_reference_notes": "unknown",
        "target_environment": detect_target_environment(text),
        "groove_description": detect_groove(text),
        "production_notes": text,
        "constraints": extract_constraints(text),
        "open_questions": []
    }

def generate_tool_intent_packet(text, producer_input):
    text_lower = text.lower()
    action_verbs = ["sketch", "create", "make", "build", "try", "add", "suggest"]
    if not any(verb in text_lower for verb in action_verbs): return None
    intent_type = "suggest_move"
    return {
        "contract_version": "v0",
        "intent_type": intent_type,
        "target_environment": producer_input.get("target_environment", "unknown"),
        "title": f"Suggested {intent_type}",
        "human_confirmation_required": True,
        "no_execution_without_approval": True
    }

def get_niles_response(text, producer_input):
    text_l = text.lower()

    # Boring + Spacious Template
    if "boring" in text_l and "spacious" in text_l:
        return "Alright — sounds like the chorus needs an arrival point, not more clutter. Keep the space. Try one clear lift: stronger drum/bass pocket, one upper melody, or a single widened texture. Don't solve boring by stacking parts. Next move: decide whether the boredom is coming from groove, melody, or arrangement change."

    # Hit harder + spacious
    if "hit" in text_l and "hard" in text_l and "spacious" in text_l:
        return "You want impact without filling the room? Focus on transient shaping and side-chain compression, not adding more elements. Keep the space, tighten the envelope. Next move: check your low-end phase and transient attack."

    # Groove / Dub
    if any(w in text_l for w in ["groove", "dub", "afro-dub"]):
        return "Dub's all about what you take away. Keep it locked, keep it sparse, and let the delays do the heavy lifting. Don't add complexity just because it's quiet. Next move: refine your rhythm pocket."

    # Logic Vocal Delay
    if "logic" in text_l and any(w in text_l for w in ["vocal", "word"]) and any(w in text_l for w in ["delay", "reverb"]) and any(w in text_l for w in ["wide", "width"]) and any(w in text_l for w in ["clear", "clarity"]):
        return "For vocal delay width in Logic, keep the dry vocal dead center. Put your delay on a return track, apply a high-pass and low-pass filter to the return to keep the core vocal words clear, and use a stereo widener or slight pitch-shift offset on the return only. Keep it out of the dry vocal's way."

    # General
    return "Let's keep it practical. What's the main goal: groove, melody, or arrangement? Don't stack more layers until you've stripped back the ones that aren't working."

def generate_human_response(producer_input, review, tool_packet=None):
    text = producer_input["user_intent"]
    lines = []
    lines.append("Niles: " + get_niles_response(text, producer_input))
    if tool_packet:
        lines.append("")
        lines.append("[!] Suggestion: " + tool_packet['title'] + ". Confirmation required before execution.")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--human-only", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args()

    producer_input = build_producer_input(args.text)
    review = run_review(producer_input)
    tool_packet = generate_tool_intent_packet(args.text, producer_input)

    if args.explain:
        packet = {
            "original_text": args.text,
            "detected_intent": "production_inquiry",
            "detected_environment": producer_input["target_environment"],
            "detected_taste_terms": producer_input["emotional_target"],
            "detected_tools_or_platforms": producer_input["target_environment"],
            "evidence_level": "text_only_no_audio",
            "suggested_move": "production_optimization_suggestion",
            "allowed_actions": ["suggestion_only"],
            "blocked_actions": ["audio_analysis_claims", "ableton_logic_hardware_execution"],
            "boundary_notes": "no_side_effects",
            "response_template_key": "niles_v0"
        }
        print(json.dumps(packet, indent=2))
    elif args.human_only:
        print(generate_human_response(producer_input, review, tool_packet))
    elif args.pretty:
        print(json.dumps(review, indent=2))
    else:
        print(json.dumps(review))

if __name__ == "__main__":
    main()
