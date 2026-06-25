"""Tests for ar_gig_to_cash_serialization. Spec: 20260625-G2C005-v1"""
import hashlib
import json
import pytest

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_record import GigRecord
from ar_invoice_record import InvoiceRecord
from ar_work_session_record import WorkSessionRecord
from ar_gig_to_cash_serialization import canonical_sha256, from_json, to_json

# ---------------------------------------------------------------------------
# Fixed-ID records used for golden tests — must never contain random data
# ---------------------------------------------------------------------------

_GIG = GigRecord(
    gig_id="gig:g0001",
    counterparty_ref="cp:hilton",
    counterparty_name="Capital Hilton Hotel",
    lifecycle_state="proposed",
    timezone="America/New_York",
    billing_policy_ref="policy:hourly",
    idempotency_key="idemp:g001",
    scheduled_start_iso=None,
    scheduled_end_iso=None,
)

_WS = WorkSessionRecord(
    work_session_id="ws:ws0001",
    gig_id="gig:g0001",
    worker_ref="worker:winship",
    iana_timezone="UTC",
    idempotency_key="idemp:ws001",
    source_ref="src:ws001",
    lifecycle_state="active",
    start_utc_iso="2026-06-25T09:00:00+00:00",
    end_utc_iso=None,
    supersedes_session_id=None,
)

_INV = InvoiceRecord(
    invoice_id="inv:inv0001",
    invoice_version_id="inv_ver:iv0001",
    counterparty_ref="cp:hilton",
    billing_entity_ref="entity:winship",
    lifecycle_state="draft",
    idempotency_key="idemp:inv001",
    source_ref="src:inv001",
    invoice_number=None,
    issue_date_iso=None,
    due_date_iso=None,
    currency_iso=None,
    total_minor_units=None,
    supersedes_invoice_version_id=None,
)

_RECV = ExpectedReceivableRecord(
    receivable_id="recv:r0001",
    receivable_version_id="recv_ver:rv0001",
    invoice_id="inv:inv0001",
    invoice_version_id="inv_ver:iv0001",
    counterparty_ref="cp:hilton",
    lifecycle_state="open",
    expected_minor_units=200000,
    currency_iso="USD",
    due_date_iso="2026-07-25",
    recognized_utc_iso="2026-06-25T10:00:00+00:00",
    idempotency_key="idemp:recv001",
    source_ref="src:recv001",
    supersedes_receivable_version_id=None,
    resolution_ref=None,
)

# ---------------------------------------------------------------------------
# Stable golden JSON strings (sorted keys, compact separators, no whitespace)
# ---------------------------------------------------------------------------

GOLDEN_GIG_JSON = (
    '{"payload":{"billing_policy_ref":"policy:hourly","counterparty_name":"Capital Hilton Hotel",'
    '"counterparty_ref":"cp:hilton","gig_id":"gig:g0001","idempotency_key":"idemp:g001",'
    '"lifecycle_state":"proposed","scheduled_end_iso":null,"scheduled_start_iso":null,'
    '"timezone":"America/New_York"},"record_type":"GigRecord","schema_version":"1.0"}'
)

GOLDEN_WS_JSON = (
    '{"payload":{"end_utc_iso":null,"gig_id":"gig:g0001","iana_timezone":"UTC",'
    '"idempotency_key":"idemp:ws001","lifecycle_state":"active","source_ref":"src:ws001",'
    '"start_utc_iso":"2026-06-25T09:00:00+00:00","supersedes_session_id":null,'
    '"work_session_id":"ws:ws0001","worker_ref":"worker:winship"},'
    '"record_type":"WorkSessionRecord","schema_version":"1.0"}'
)

GOLDEN_INV_JSON = (
    '{"payload":{"billing_entity_ref":"entity:winship","counterparty_ref":"cp:hilton",'
    '"currency_iso":null,"due_date_iso":null,"idempotency_key":"idemp:inv001",'
    '"invoice_id":"inv:inv0001","invoice_number":null,"invoice_version_id":"inv_ver:iv0001",'
    '"issue_date_iso":null,"lifecycle_state":"draft","source_ref":"src:inv001",'
    '"supersedes_invoice_version_id":null,"total_minor_units":null},'
    '"record_type":"InvoiceRecord","schema_version":"1.0"}'
)

GOLDEN_RECV_JSON = (
    '{"payload":{"counterparty_ref":"cp:hilton","currency_iso":"USD","due_date_iso":"2026-07-25",'
    '"expected_minor_units":200000,"idempotency_key":"idemp:recv001","invoice_id":"inv:inv0001",'
    '"invoice_version_id":"inv_ver:iv0001","lifecycle_state":"open","receivable_id":"recv:r0001",'
    '"receivable_version_id":"recv_ver:rv0001","recognized_utc_iso":"2026-06-25T10:00:00+00:00",'
    '"resolution_ref":null,"source_ref":"src:recv001","supersedes_receivable_version_id":null},'
    '"record_type":"ExpectedReceivableRecord","schema_version":"1.0"}'
)


# ===========================================================================
# Golden JSON tests
# ===========================================================================

def test_gig_record_golden_json():
    assert to_json(_GIG) == GOLDEN_GIG_JSON


def test_work_session_record_golden_json():
    assert to_json(_WS) == GOLDEN_WS_JSON


def test_invoice_record_golden_json():
    assert to_json(_INV) == GOLDEN_INV_JSON


def test_expected_receivable_record_golden_json():
    assert to_json(_RECV) == GOLDEN_RECV_JSON


# ===========================================================================
# SHA-256 stability tests (derived from golden strings; catches format drift)
# ===========================================================================

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_gig_record_sha256_stability():
    assert canonical_sha256(_GIG) == _sha256(GOLDEN_GIG_JSON)


def test_work_session_record_sha256_stability():
    assert canonical_sha256(_WS) == _sha256(GOLDEN_WS_JSON)


def test_invoice_record_sha256_stability():
    assert canonical_sha256(_INV) == _sha256(GOLDEN_INV_JSON)


def test_expected_receivable_record_sha256_stability():
    assert canonical_sha256(_RECV) == _sha256(GOLDEN_RECV_JSON)


# ===========================================================================
# Round-trip tests (to_json → from_json → equality)
# ===========================================================================

def test_gig_record_round_trip():
    assert from_json(to_json(_GIG)) == _GIG


def test_work_session_record_round_trip():
    assert from_json(to_json(_WS)) == _WS


def test_invoice_record_round_trip():
    assert from_json(to_json(_INV)) == _INV


def test_expected_receivable_record_round_trip():
    assert from_json(to_json(_RECV)) == _RECV


def test_invoice_issued_state_round_trip():
    issued = InvoiceRecord(
        invoice_id="inv:issued001",
        invoice_version_id="inv_ver:is001",
        counterparty_ref="cp:hilton",
        billing_entity_ref="entity:winship",
        lifecycle_state="issued",
        idempotency_key="idemp:issued001",
        source_ref="src:issued001",
        invoice_number="INV-2026-001",
        issue_date_iso="2026-06-25",
        due_date_iso="2026-07-25",
        currency_iso="USD",
        total_minor_units=500000,
        supersedes_invoice_version_id=None,
    )
    assert from_json(to_json(issued)) == issued


def test_work_session_completed_state_round_trip():
    completed = WorkSessionRecord(
        work_session_id="ws:wsc001",
        gig_id="gig:g0001",
        worker_ref="worker:winship",
        iana_timezone="America/New_York",
        idempotency_key="idemp:wsc001",
        source_ref="src:wsc001",
        lifecycle_state="completed",
        start_utc_iso="2026-06-25T09:00:00+00:00",
        end_utc_iso="2026-06-25T17:00:00+00:00",
        supersedes_session_id="ws:ws0001",
    )
    assert from_json(to_json(completed)) == completed


def test_expected_receivable_terminal_state_round_trip():
    satisfied = ExpectedReceivableRecord(
        receivable_id="recv:r0002",
        receivable_version_id="recv_ver:rv0002",
        invoice_id="inv:inv0001",
        invoice_version_id="inv_ver:iv0001",
        counterparty_ref="cp:hilton",
        lifecycle_state="satisfied",
        expected_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-25",
        recognized_utc_iso="2026-06-25T10:00:00+00:00",
        idempotency_key="idemp:recv002",
        source_ref="src:recv002",
        supersedes_receivable_version_id="recv_ver:rv0001",
        resolution_ref="payment:pmt001",
    )
    assert from_json(to_json(satisfied)) == satisfied


# ===========================================================================
# Optional fields serialized as null
# ===========================================================================

def test_optional_fields_serialized_as_null():
    parsed = json.loads(to_json(_GIG))
    assert parsed["payload"]["scheduled_start_iso"] is None
    assert parsed["payload"]["scheduled_end_iso"] is None

    parsed_inv = json.loads(to_json(_INV))
    for field in ("invoice_number", "issue_date_iso", "due_date_iso",
                  "currency_iso", "total_minor_units", "supersedes_invoice_version_id"):
        assert parsed_inv["payload"][field] is None


# ===========================================================================
# Structural / format guarantees
# ===========================================================================

def test_output_is_valid_json():
    for record in (_GIG, _WS, _INV, _RECV):
        json.loads(to_json(record))  # must not raise


def test_output_uses_compact_separators():
    for record in (_GIG, _WS, _INV, _RECV):
        serialized = to_json(record)
        assert ": " not in serialized, "must use ':' not ': '"
        assert ", " not in serialized, "must use ',' not ', '"


def test_output_keys_are_sorted():
    for record in (_GIG, _WS, _INV, _RECV):
        parsed = json.loads(to_json(record))
        envelope_keys = list(parsed.keys())
        assert envelope_keys == sorted(envelope_keys)
        payload_keys = list(parsed["payload"].keys())
        assert payload_keys == sorted(payload_keys)


def test_output_is_utf8_encoded():
    unicode_gig = GigRecord(
        gig_id="gig:u001",
        counterparty_ref="cp:ñoño",
        counterparty_name="Señorita Hotél",
        lifecycle_state="proposed",
        timezone="UTC",
        billing_policy_ref="policy:test",
        idempotency_key="idemp:u001",
    )
    serialized = to_json(unicode_gig)
    assert "Señorita" in serialized
    serialized.encode("utf-8")  # must be encodable


def test_to_json_rejects_unsupported_type():
    with pytest.raises(TypeError, match="Unsupported record type"):
        to_json(object())


# ===========================================================================
# Deserialization rejection tests
# ===========================================================================

def test_reject_unknown_record_type():
    bad = '{"payload":{},"record_type":"UnknownRecord","schema_version":"1.0"}'
    with pytest.raises(ValueError, match="Unknown record type"):
        from_json(bad)


def test_reject_unknown_schema_version():
    gig_json = to_json(_GIG)
    bad = gig_json.replace('"schema_version":"1.0"', '"schema_version":"9.9"')
    with pytest.raises(ValueError, match="Unknown schema version"):
        from_json(bad)


def test_reject_unknown_payload_fields():
    gig_json = to_json(_GIG)
    parsed = json.loads(gig_json)
    parsed["payload"]["injected_field"] = "evil"
    with pytest.raises(ValueError, match="Unknown payload fields"):
        from_json(json.dumps(parsed))


def test_reject_missing_payload_fields():
    gig_json = to_json(_GIG)
    parsed = json.loads(gig_json)
    del parsed["payload"]["gig_id"]
    with pytest.raises(ValueError, match="Missing payload fields"):
        from_json(json.dumps(parsed))


def test_reject_duplicate_json_keys():
    bad = '{"payload":{},"record_type":"GigRecord","schema_version":"1.0","record_type":"GigRecord"}'
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        from_json(bad)


def test_reject_missing_envelope_keys():
    bad = '{"payload":{},"record_type":"GigRecord"}'
    with pytest.raises(ValueError, match="Missing envelope keys"):
        from_json(bad)


def test_reject_unknown_envelope_keys():
    gig_json = to_json(_GIG)
    parsed = json.loads(gig_json)
    parsed["extra_envelope_key"] = "unexpected"
    with pytest.raises(ValueError, match="Unknown envelope keys"):
        from_json(json.dumps(parsed))


def test_reject_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        from_json("{not valid json")


# ===========================================================================
# Domain validation during deserialization
# ===========================================================================

def test_domain_validation_invalid_lifecycle_state():
    gig_json = to_json(_GIG)
    parsed = json.loads(gig_json)
    parsed["payload"]["lifecycle_state"] = "invalid_state"
    with pytest.raises(ValueError, match="Invalid lifecycle state"):
        from_json(json.dumps(parsed))


def test_domain_validation_invoice_missing_required_issued_fields():
    inv_json = to_json(_INV)
    parsed = json.loads(inv_json)
    parsed["payload"]["lifecycle_state"] = "issued"
    with pytest.raises(ValueError):
        from_json(json.dumps(parsed))


def test_domain_validation_receivable_negative_amount():
    recv_json = to_json(_RECV)
    parsed = json.loads(recv_json)
    parsed["payload"]["expected_minor_units"] = -1
    with pytest.raises(ValueError, match="must be positive"):
        from_json(json.dumps(parsed))


def test_domain_validation_currency_format():
    recv_json = to_json(_RECV)
    parsed = json.loads(recv_json)
    parsed["payload"]["currency_iso"] = "usd"
    with pytest.raises(ValueError, match="currency_iso"):
        from_json(json.dumps(parsed))


# ===========================================================================
# SHA-256 determinism (same record always produces same hash)
# ===========================================================================

def test_sha256_determinism_multiple_calls():
    for record in (_GIG, _WS, _INV, _RECV):
        assert canonical_sha256(record) == canonical_sha256(record)
