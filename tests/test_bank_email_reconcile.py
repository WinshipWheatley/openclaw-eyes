"""Bank deposit email cross-references a check OCR — verified against the operator's REAL
Bank of America deposit email format (2026-07-02): the email carries the AMOUNT and a
Confirmation # (BoA's deposit tracking id), NOT the paper check number. So the email
confirms amount + deposit; the check number stays from the photo."""

import bank_email_reconcile as ber

# The operator's ACTUAL BoA email content (from the real snippet, 2026-07-02):
BOA_REAL = {
    "subject": "We received your mobile check deposit",
    "from": "onlinebanking@ealerts.bankofamerica.com",
    "body": ("We received your mobile check deposit Check amount $2000.00 To Adv Plus Banking 4529 "
             "Credit posts on 07/03/2026 Available now $0.00 Confirmation # 3813444679 View deposit details"),
}

# What the photo OCR produced — the check number IS on the photo (OCR read it), amount clean.
OCR_CHECK = {
    "amount": 2000.00, "payee": "Winship Live", "bank": "Wells Fargo Bank, N.A.",
    "check_number_guess": "3000014313", "date_guess": "06/25/2026",
    "needs_review": ["check_number (OCR-unreliable — confirm)"],
}


def test_parse_real_boa_email():
    f = ber.parse_bank_email(subject=BOA_REAL["subject"], body=BOA_REAL["body"], sender=BOA_REAL["from"])
    assert f["bank"] == "Bank of America"
    assert f["is_deposit_confirmation"] is True
    assert f["amount"] == 2000.00
    assert f["confirmation_number"] == "3813444679"
    assert f["check_number"] is None            # BoA does NOT include the check number
    assert f["account_last4"] == "4529"
    assert f["post_date"] == "07/03/2026"
    assert f["available_now"] == 0.00            # pending, not cleared


def test_reconcile_confirms_amount_and_deposit_keeps_photo_check_number():
    email = ber.parse_bank_email(subject=BOA_REAL["subject"], body=BOA_REAL["body"], sender=BOA_REAL["from"])
    r = ber.reconcile(OCR_CHECK, email)
    # amount agrees across both sources
    assert r["reconciled"]["amount"] == 2000.00
    assert "agree" in r["field_sources"]["amount"]
    # check number stays from the photo (the email doesn't have it)
    assert r["reconciled"]["check_number"] == "3000014313"
    assert r["field_sources"]["check_number"] == "photo (unconfirmed)"
    # the email's real contributions: deposit confirmed + confirmation number + pending status
    assert r["deposit_confirmed_by_bank"] is True
    assert r["reconciled"]["deposit_confirmation_number"] == "3813444679"
    assert r["reconciled"]["funds_available"] is False   # available now $0.00
    assert r["confidence"] == "high"                     # deposit confirmed + amount matches


def test_amount_conflict_surfaced():
    email = ber.parse_bank_email(subject="deposit", body="Check amount $500.00 Confirmation # 111111",
                                 sender="alerts@bankofamerica.com")
    r = ber.reconcile(OCR_CHECK, email)  # photo 2000 vs email 500
    assert r["conflicts"] and r["confidence"] == "review"


def test_find_matching_email_via_injected_search():
    def fake_search(query):
        return [{"id": "m1", "subject": BOA_REAL["subject"], "from": BOA_REAL["from"], "snippet": BOA_REAL["body"]}]
    facts = ber.find_bank_email_for_check(OCR_CHECK, gmail_search=fake_search)
    assert facts is not None and facts["confirmation_number"] == "3813444679" and facts["email_id"] == "m1"


def test_find_returns_none_when_no_match():
    assert ber.find_bank_email_for_check(OCR_CHECK, gmail_search=lambda q: []) is None
