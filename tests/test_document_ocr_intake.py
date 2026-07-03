"""OCR intake reads a check honestly — reliable fields extracted, garbled ones flagged."""

from pathlib import Path

import document_ocr_intake as ocr

FIXTURE = (Path(__file__).parent / "fixtures" / "check_ocr.txt").read_text(encoding="utf-8")


def test_classifies_as_check():
    assert ocr.classify_document(FIXTURE) == "check"


def test_extracts_amount_with_cross_validation():
    facts = ocr.extract_check_facts(FIXTURE)
    assert facts["amount"] == 2000.00
    # digits "2,000.00" and words "Two Thousand" agree -> high confidence
    assert facts["amount_confidence"] == "high"
    assert facts["amount_numeric"] == 2000.00
    assert facts["amount_words"] == 2000.0


def test_extracts_payee_and_bank():
    facts = ocr.extract_check_facts(FIXTURE)
    assert facts["payee"] and "WINSHIP" in facts["payee"].upper()
    assert facts["bank"] == "Wells Fargo Bank, N.A."


def test_void_days_read():
    facts = ocr.extract_check_facts(FIXTURE)
    assert facts["void_after_days"] == 120


def test_garbled_fields_flagged_not_fabricated():
    facts = ocr.extract_check_facts(FIXTURE)
    review = " ".join(facts["needs_review"])
    # the noisy check number / date must be flagged for confirmation, never presented as fact
    assert "check_number" in review
    assert "date" in review


def test_summary_is_true_and_flags_uncertainty():
    result = ocr.read_document.__wrapped__ if hasattr(ocr.read_document, "__wrapped__") else None
    # build a result dict directly from the fixture facts (no image needed)
    res = {"status": "read", "doc_type": "check", "check": ocr.extract_check_facts(FIXTURE)}
    line = ocr.summarize_for_operator(res)
    assert "$2,000.00" in line
    assert "WINSHIP" in line.upper()
    assert "Wells Fargo" in line
    assert "confirm" in line.lower()  # honest about the garbled fields


def test_read_document_never_raises_on_bad_path():
    res = ocr.read_document("/nonexistent/nope.jpg")
    assert res["status"] == "ocr_empty"


def test_non_check_text_classified_unknown():
    assert ocr.classify_document("just some random note about groceries") == "unknown"
