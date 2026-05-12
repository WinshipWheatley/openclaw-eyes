import argparse
import json
import sys
import os

# Mapping intents to headings in canonical facts
INTENT_HEADING_MAP = {
    "WHERE_ARE_WE": "Status",
    "WHAT_IS_BUILT": "Mapping Table",
    "WHAT_IS_NOT_BUILT": "Do Not Build Yet",
    "WHAT_ARE_THE_BOUNDARIES": "Terrain vs Declaration",
}

# Mapping phrases to intents
PHRASE_INTENT_MAP = {
    "where are we?": "WHERE_ARE_WE",
    "what is built?": "WHAT_IS_BUILT",
    "what is not built?": "WHAT_IS_NOT_BUILT",
    "what are the boundaries?": "WHAT_ARE_THE_BOUNDARIES",
}

def answer_operator_question(db_path: str, question: str) -> dict:
    # Ensure gateway is available
    sys.path.append(os.getcwd())
    try:
        from scripts.truth_reconciliation_gateway import build_llm_truth_packet, MODEL_ALLOWED, MODEL_BLOCKED
    except ImportError:
        return {
            "intent_matched": None,
            "status": "ERROR",
            "answer": "Truth Reconciliation Gateway not found.",
            "provenance": []
        }

    from business_ops_ledger import get_canonical_facts_by_heading

    intent = PHRASE_INTENT_MAP.get(question.lower().strip())

    if not intent:
        return {
            "intent_matched": None,
            "status": "REFUSED",
            "answer": "Intent not recognized. Please use a supported question.",
            "provenance": []
        }

    heading = INTENT_HEADING_MAP.get(intent)
    candidate_facts = get_canonical_facts_by_heading(heading, db_path)

    if not candidate_facts:
        return {
            "intent_matched": intent,
            "status": "NOT_ENOUGH_CONTEXT",
            "answer": f"No facts found for intent: {intent}",
            "provenance": []
        }

    # Pass each candidate through the Truth Reconciliation Gateway
    allowed_packets = []
    blocked_reasons = []

    for fact in candidate_facts:
        packet = build_llm_truth_packet(db_path, fact["fact_id"], question)
        if packet["status"] == MODEL_ALLOWED:
            allowed_packets.append(packet)
        else:
            blocked_reasons.append({
                "fact_id": fact["fact_id"],
                "reason": packet.get("block_reason", "Unknown block")
            })

    if not allowed_packets:
        return {
            "intent_matched": intent,
            "status": MODEL_BLOCKED,
            "answer": f"All candidate facts were blocked by Truth Reconciliation Gateway. Reasons: {json.dumps(blocked_reasons)}",
            "provenance": [],
            "truth_summary": {
                "blocked": True,
                "candidate_count": len(candidate_facts),
                "blocked_reasons": blocked_reasons
            }
        }

    # Combine allowed facts
    all_verified_facts = []
    for packet in allowed_packets:
        all_verified_facts.extend(packet["verified_facts"])

    answer_text = "\n\n".join([f["text"] for f in all_verified_facts])

    provenance = []
    for f in all_verified_facts:
        prov = f["provenance"].copy()
        prov["labels"] = f["labels"]
        provenance.append(prov)

    # Use the last packet's boundary/authority info (they should be consistent)
    last_packet = allowed_packets[-1]

    truth_summary = {
        "truth_statuses_present": list(set(f["provenance"]["truth_status"] for f in all_verified_facts)),
        "verification_required_count": sum(1 for f in all_verified_facts if f["provenance"]["verification_required"]),
        "has_runtime_verified": any(f["provenance"]["truth_status"] == "runtime_verified" for f in all_verified_facts),
        "has_test_verified": any(f["provenance"]["truth_status"] == "test_verified" for f in all_verified_facts),
        "all_facts_require_verification": all(f["provenance"]["verification_required"] for f in all_verified_facts),
        "gateway_transitions": last_packet.get("transitions")
    }

    return {
        "intent_matched": intent,
        "status": "SUCCESS",
        "answer": answer_text,
        "provenance": provenance,
        "truth_summary": truth_summary,
        "answer_boundary": last_packet.get("answer_boundary"),
        "runtime_authority": last_packet.get("runtime_authority", False)
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministic operator question answer harness with Truth Gateway.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--question", required=True, help="Operator question.")

    args = parser.parse_args()

    result = answer_operator_question(args.db, args.question)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
