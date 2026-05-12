import argparse
import json
import sys
from business_ops_ledger import get_canonical_facts_by_heading

# Mapping intents to headings in canonical facts
INTENT_HEADING_MAP = {
    "WHERE_ARE_WE": "WHERE_ARE_WE",
    "WHAT_IS_BUILT": "WHAT_IS_BUILT",
    "WHAT_IS_NOT_BUILT": "WHAT_IS_NOT_BUILT",
    "WHAT_ARE_THE_BOUNDARIES": "WHAT_ARE_THE_BOUNDARIES",
}

# Mapping phrases to intents
PHRASE_INTENT_MAP = {
    "where are we?": "WHERE_ARE_WE",
    "what is built?": "WHAT_IS_BUILT",
    "what is not built?": "WHAT_IS_NOT_BUILT",
    "what are the boundaries?": "WHAT_ARE_THE_BOUNDARIES",
}

def answer_operator_question(db_path: str, question: str) -> dict:
    intent = PHRASE_INTENT_MAP.get(question.lower().strip())
    
    if not intent:
        return {
            "intent_matched": None,
            "status": "REFUSED",
            "answer": "Intent not recognized. Please use a supported question.",
            "provenance": []
        }
    
    heading = INTENT_HEADING_MAP.get(intent)
    facts = get_canonical_facts_by_heading(heading, db_path)
    
    if not facts:
        return {
            "intent_matched": intent,
            "status": "NOT_ENOUGH_CONTEXT",
            "answer": f"No facts found for intent: {intent}",
            "provenance": []
        }
    
    answer_text = "\n\n".join([f["fact_text"] for f in facts])
    provenance = [
        {
            "fact_id": f["fact_id"],
            "source_file": f["source_file"],
            "section_heading": f["section_heading"],
            "source_commit": f["source_commit"],
            "content_hash": f["content_hash"]
        } for f in facts
    ]
    
    return {
        "intent_matched": intent,
        "status": "SUCCESS",
        "answer": answer_text,
        "provenance": provenance
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministic operator question answer harness.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--question", required=True, help="Operator question.")
    
    args = parser.parse_args()
    
    result = answer_operator_question(args.db, args.question)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
