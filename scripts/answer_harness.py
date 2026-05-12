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

def answer_operator_question(
    db_path: str,
    question: str,
    allow_reconciliation: bool = False,
    record_receipt: bool = False,
    receipt_db_path: str | None = None
) -> dict:
    # Ensure gateway is available
    sys.path.append(os.getcwd())
    try:
        from scripts.truth_reconciliation_gateway import (
            build_llm_truth_packet,
            MODEL_ALLOWED_VERIFIED,
            MODEL_ALLOWED_UNCERTAIN,
            MODEL_BLOCKED,
            MODEL_ALLOWED # for backward compatibility if needed
        )
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
    all_processed_facts = []
    blocked_reasons = []
    has_uncertain = False
    last_packet = None

    for fact in candidate_facts:
        packet = build_llm_truth_packet(
            db_path,
            fact["fact_id"],
            question,
            allow_reconciliation=allow_reconciliation,
            record_receipt=record_receipt,
            receipt_db_path=receipt_db_path
        )
        last_packet = packet

        if packet["status"] == MODEL_ALLOWED_VERIFIED:
            for f in packet["verified_facts"]:
                all_processed_facts.append({
                    "text": f["text"],
                    "labels": f["labels"],
                    "provenance": f["provenance"],
                    "uncertain": False,
                    "packet": packet
                })
        elif packet["status"] == MODEL_ALLOWED_UNCERTAIN:
            has_uncertain = True
            # Construct provenance and labels for uncertain fact
            prov = {
                "fact_id": fact["fact_id"],
                "source_file": packet["source_file"],
                "source_commit": packet.get("source_commit"),
                "content_hash": packet["content_hash"],
                "truth_source_id": packet["truth_source_id"],
                "truth_status": packet["truth_status"],
                "verification_required": packet["verification_required"],
                "verification_evidence_id": packet.get("verification_evidence_id")
            }
            hash_status = packet.get("source_content_hash_status", "unknown").upper()
            truth_status = packet.get("truth_status", "unknown").upper()
            labels = f"[UNCERTAIN] [REPO-SOURCE] [HASH-{hash_status}] [{truth_status}] [VERIFY_REQUIRED]"

            all_processed_facts.append({
                "text": packet["fact_text"],
                "labels": labels,
                "provenance": prov,
                "uncertain": True,
                "uncertainty_status": packet["uncertainty_status"],
                "confidence_band": packet["confidence_band"],
                "uncertainty_reason": packet["uncertainty_reason"],
                "packet": packet
            })
        else:
            blocked_reasons.append({
                "fact_id": fact["fact_id"],
                "reason": packet.get("block_reason", "Unknown block")
            })

    if not all_processed_facts:
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

    # Combine allowed facts with qualification for uncertain ones
    formatted_answers = []
    for f in all_processed_facts:
        if f["uncertain"]:
            qualification = f"Based on currently available evidence, this appears to be provisional (status: {f['uncertainty_status']}, confidence: {f['confidence_band']}): "
            formatted_answers.append(f"{qualification}{f['text']}")
        else:
            formatted_answers.append(f["text"])

    answer_text = "\n\n".join(formatted_answers)

    provenance = []
    for f in all_processed_facts:
        prov = f["provenance"].copy()
        prov["labels"] = f["labels"]
        if f["uncertain"]:
            prov["uncertainty_status"] = f["uncertainty_status"]
            prov["confidence_band"] = f["confidence_band"]
            prov["uncertainty_reason"] = f["uncertainty_reason"]
        provenance.append(prov)

    # Use the last packet's boundary/authority info (they should be consistent)
    # If we have a mix, the uncertain one's boundary is likely more restrictive
    # For now, we take the last one processed that was allowed
    # (Or just use the last_packet if it was allowed)

    # Let's find an uncertain packet if it exists, to be safe with boundaries
    effective_packet = last_packet
    for f in all_processed_facts:
        if f["uncertain"]:
            effective_packet = f["packet"]
            break

    truth_summary = {
        "truth_statuses_present": list(set(f["provenance"]["truth_status"] for f in all_processed_facts)),
        "verification_required_count": sum(1 for f in all_processed_facts if f["provenance"]["verification_required"]),
        "has_runtime_verified": any(f["provenance"]["truth_status"] == "runtime_verified" for f in all_processed_facts),
        "has_test_verified": any(f["provenance"]["truth_status"] == "test_verified" for f in all_processed_facts),
        "all_facts_require_verification": all(f["provenance"]["verification_required"] for f in all_processed_facts),
        "has_uncertain_facts": has_uncertain,
        "gateway_transitions": effective_packet.get("transitions")
    }

    return {
        "intent_matched": intent,
        "status": "SUCCESS",
        "answer": answer_text,
        "provenance": provenance,
        "truth_summary": truth_summary,
        "answer_boundary": effective_packet.get("answer_boundary"),
        "runtime_authority": effective_packet.get("runtime_authority", False)
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministic operator question answer harness with Truth Gateway.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--question", required=True, help="Operator question.")
    parser.add_argument("--allow-reconciliation", action="store_true", help="Allow mechanical metadata repairs")
    parser.add_argument("--record-receipt", action="store_true", help="Record truth decision receipt to ledger")
    parser.add_argument("--receipt-db", help="Target DB for receipt logging (defaults to --db)")

    args = parser.parse_args()

    result = answer_operator_question(
        args.db,
        args.question,
        allow_reconciliation=args.allow_reconciliation,
        record_receipt=args.record_receipt,
        receipt_db_path=args.receipt_db
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
