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

_TASTE_DNA_MARKERS = ("taste", "music dna", "our dna", "my dna", "pillars", "archetype",
                      "my sound", "what are we going for", "what am i going for")


def get_taste_dna_response():
    """Answer taste/DNA asks FROM the archetype doc (docs/producer/PRODUCER_ARCHETYPE.md)
    — the operator's music DNA is written truth, never LM freestyle."""
    from pathlib import Path as _Path
    doc = _Path(__file__).resolve().parents[1] / "docs" / "producer" / "PRODUCER_ARCHETYPE.md"
    try:
        text = doc.read_text(encoding="utf-8")
    except Exception:
        return None
    import re as _re
    pillars = _re.findall(r"^\d+\. \*\*(.+?)\*\*: (.+)$", text, _re.MULTILINE)
    if not pillars:
        return None
    lines = ["Niles: Our DNA, straight from the book — six pillars:"]
    for name, desc in pillars:
        lines.append(f"- {name}: {desc.split('. ')[0].rstrip('.')}.")
    lines.append("And the golden rule: references are for EXTRACTING the why (that kick EQ, "
                 "that vocal space) — we never mimic an artist. Synthesis, not imitation.")
    return "\n".join(lines)


def is_taste_dna_question(text):
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _TASTE_DNA_MARKERS)


def _money_route_response(text):
    """Task 140: money-class questions are not Niles's desk — route in one warm
    line and include the answer from the ONE money truth (money_truth.py)."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(__file__).resolve().parents[1])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from money_truth import classify_money_question, render_money_answer, route_line
    except Exception:
        return None
    if classify_money_question(text) != "money_read":
        return None
    line = route_line("niles")
    try:
        picture = render_money_answer("niles", question=text)
    except Exception:
        picture = ""
    if picture:
        return f"{line} {picture}"
    return f"{line} (Couldn't read the ledger just now — ask Maestro directly.)"


def _operator_refusal_reply(text):
    """Task 149: refusal-first tap, hoisted into the intake SUBPROCESS itself (not just
    the listener). This process is spawned fresh from disk per message, so a code fix
    here is immune to a stale/un-restarted long-running listener process -- root cause
    #3 of the live-path trace: niles-listener.service ran a Jun-30 binary through a
    deploy that omitted it from the restart list, so the listener-side task-141 tap was
    never actually loaded into memory."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(__file__).resolve().parents[1])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from operator_refusal_guard import refusal_reply_for_text
    except Exception:
        return None
    try:
        return refusal_reply_for_text(text, agent="niles", surface="niles_producer_intake")
    except Exception:
        return None


def _typed_contract_reply(text, *, first_touch_receipt=None):
    """Task 151 subprocess mirror for stale-listener resilience.

    The listener normally resolves this first.  A fresh subprocess still runs
    the same typed contract so an old in-memory listener cannot regress to the
    one-size catch-all after a code deploy.
    """
    try:
        import sys as _sys
        from pathlib import Path as _Path

        _root = str(_Path(__file__).resolve().parents[1])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from agent_contract_renderers import render_niles_status
        from typed_contract_decision import (
            ContractContext,
            decide_contract,
            semantic_vote_enabled_for_adapter,
        )

        decision = decide_contract(
            text,
            context=ContractContext(agent="niles", surface="niles_producer_intake"),
            status_renderer=render_niles_status,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter("niles_subprocess", default=True),
            first_touch_receipt=first_touch_receipt,
        )
    except Exception:
        return None
    return str(decision.reply or "") if decision.handled else None


def get_niles_response(text, producer_input):
    text_l = text.lower()

    # Money-class branch BEFORE anything else reaches the catch-all (task 140). Kept
    # here too (not just hoisted into main()'s top-level ordering, task 149) because
    # get_niles_response is itself a tested public entry point
    # (test_money_one_source_fleetwide.py calls it directly, bypassing main()) --
    # removing it broke that contract. Redundant-but-harmless when reached via main(),
    # which already checks money first.
    money_reply = _money_route_response(text)
    if money_reply is not None:
        return money_reply

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
    if is_taste_dna_question(text):
        dna = get_taste_dna_response()
        if dna:
            return dna
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
    parser.add_argument("--first-touch-receipt-json", default="")
    args = parser.parse_args()

    first_touch_receipt = None
    first_touch_valid = False
    if args.first_touch_receipt_json:
        try:
            candidate = json.loads(args.first_touch_receipt_json)
            root = str(Path(__file__).resolve().parents[1])
            if root not in sys.path:
                sys.path.insert(0, root)
            from first_touch_decision import valid_pass_through_marker

            first_touch_valid = valid_pass_through_marker(
                candidate,
                text=args.text,
                agent="niles",
            )
            if first_touch_valid:
                first_touch_receipt = candidate
        except Exception:
            first_touch_receipt = None
            first_touch_valid = False

    # Task 149: single-pipeline ordering, hoisted refusal-first + money-first. Previously
    # the X32 lane ran unconditionally before get_niles_response, so LANE ORDER decided
    # everything -- a bare "who owes me money right now?" could be shadowed by the X32
    # rig_knowledge classifier (root cause #1: bare "rig" substring-matched inside
    # "right") before money ever got a chance. Fails open at each tap: any non-matching
    # ask or internal error falls through to the next stage, ending at the legacy path.
    if args.human_only:
        typed_reply = (
            _typed_contract_reply(
                args.text,
                first_touch_receipt=first_touch_receipt,
            )
            if first_touch_valid
            else _typed_contract_reply(args.text)
        )
        if typed_reply is not None:
            print(typed_reply)
            return
        # Independent safety fallback: even if the typed-contract import/call
        # fails, destructive studio scope still reaches the proven refusal
        # guard before identity, money, X32, or the legacy catch-all.
        refusal = None if first_touch_valid else _operator_refusal_reply(args.text)
        if refusal is not None:
            print(refusal)
            return

        # ── Identity persona core (task 142 hook, task 145 wiring) — after the
        # refusal tap, before money/X32, so no marker addition can shadow it.
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _root = str(_Path(__file__).resolve().parents[1])
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from protected_generate import identity_persona_reply, is_identity_question

            if is_identity_question(args.text):
                print(identity_persona_reply("niles"))
                return
        except Exception:
            pass

        money_reply = _money_route_response(args.text)
        if money_reply is not None:
            print(money_reply)
            return

        try:
            import sys as _sys
            from pathlib import Path as _Path
            _root = str(_Path(__file__).resolve().parents[1])
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from niles_x32_capability import maybe_handle_x32

            x32 = maybe_handle_x32(args.text)
        except Exception:
            x32 = None
        if x32 is not None:
            print(x32["reply"])
            return

    producer_input = build_producer_input(args.text)
    review = run_review(producer_input)
    tool_packet = generate_tool_intent_packet(args.text, producer_input)

    if args.explain:
        text_l = args.text.lower()
        if "boring" in text_l and "spacious" in text_l:
            move = "add_arrival_point_without_clutter"
        elif "logic" in text_l and "vocal" in text_l and "delay" in text_l:
            move = "widen_delay_return_preserve_vocal_clarity"
        elif any(w in text_l for w in ["sketch", "create", "make"]) and "ableton" in text_l:
            move = "sketch_spacious_groove_suggestion_only"
        else:
            move = "production_optimization_suggestion"

        packet = {
            "original_text": args.text,
            "detected_intent": "production_inquiry",
            "detected_environment": producer_input["target_environment"],
            "detected_taste_terms": producer_input["emotional_target"],
            "detected_tools_or_platforms": producer_input["target_environment"],
            "evidence_level": "text_only_no_audio",
            "suggested_move": move,
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
