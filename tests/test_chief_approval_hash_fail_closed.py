from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chief_approval_brain as approval  # noqa: E402


def test_hmac_verification_requires_stored_hash_when_secret_configured(monkeypatch):
    monkeypatch.setenv("APPROVAL_HMAC_SECRET", "test-secret")

    assert approval._verify_hash("send invoice", "ABC123", "2026-07-01 12:00:00", "") is False


def test_hmac_verification_denies_stored_hash_when_secret_missing(monkeypatch):
    monkeypatch.delenv("APPROVAL_HMAC_SECRET", raising=False)

    assert approval._verify_hash("send invoice", "ABC123", "2026-07-01 12:00:00", "DEADBEEF") is False


def test_hmac_verification_allows_only_matching_hash_when_secret_configured(monkeypatch):
    monkeypatch.setenv("APPROVAL_HMAC_SECRET", "test-secret")
    action = "send invoice"
    approval_id = "ABC123"
    requested_at = "2026-07-01 12:00:00"
    stored = approval._compute_hash(action, approval_id, requested_at)

    assert approval._verify_hash(action, approval_id, requested_at, stored) is True
    assert approval._verify_hash(action + " now", approval_id, requested_at, stored) is False


def test_hmac_verification_preserves_disabled_hash_legacy_path(monkeypatch):
    monkeypatch.delenv("APPROVAL_HMAC_SECRET", raising=False)

    assert approval._verify_hash("send invoice", "ABC123", "2026-07-01 12:00:00", "") is True
