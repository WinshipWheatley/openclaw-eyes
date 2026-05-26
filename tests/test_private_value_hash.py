import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_private_value_hash as private_hash
from scripts.export_private_value_hash_policy import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _set_test_key(monkeypatch) -> None:
    monkeypatch.delenv(private_hash.KEY_ENV_VAR, raising=False)
    monkeypatch.setenv(private_hash.TEST_KEY_ENV_VAR, "unit-test-only-private-value-hmac-key")
    monkeypatch.setenv(private_hash.ALLOW_TEST_KEY_ENV_VAR, "1")


def test_normalize_private_value_is_stable_without_emitting_value():
    assert private_hash.normalize_private_value("  Winship\tMusic  ") == "winship music"
    assert private_hash.normalize_private_value("ANNETTE@EXAMPLE.COM") == "annette@example.com"


def test_same_value_and_purpose_gives_same_hmac(monkeypatch):
    _set_test_key(monkeypatch)

    first = private_hash.private_value_hmac("Private Contact", purpose="client_label")
    second = private_hash.private_value_hmac(" private   contact ", purpose="client_label")

    assert first == second
    assert first.startswith("hmac:v1:client_label:")
    assert "Private Contact" not in first


def test_same_value_different_purpose_gives_different_hmac(monkeypatch):
    _set_test_key(monkeypatch)

    contact = private_hash.private_value_hmac("same-private-value", purpose="contact_email")
    client = private_hash.private_value_hmac("same-private-value", purpose="client_label")

    assert contact != client
    assert contact.startswith("hmac:v1:contact_email:")
    assert client.startswith("hmac:v1:client_label:")


def test_changed_value_gives_different_hmac(monkeypatch):
    _set_test_key(monkeypatch)

    first = private_hash.private_value_hmac("private-value-one", purpose="generic_private_value")
    second = private_hash.private_value_hmac("private-value-two", purpose="generic_private_value")

    assert first != second


def test_verify_private_value_hmac(monkeypatch):
    _set_test_key(monkeypatch)

    token = private_hash.private_value_hmac("PO private reference", purpose="po_reference")

    assert private_hash.verify_private_value_hmac("po private reference", token, purpose="po_reference") is True
    assert private_hash.verify_private_value_hmac("po private reference", token, purpose="client_label") is False
    assert private_hash.verify_private_value_hmac("different", token, purpose="po_reference") is False


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv(private_hash.KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.TEST_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.ALLOW_TEST_KEY_ENV_VAR, raising=False)

    try:
        private_hash.private_value_hmac("private-value", purpose="generic_private_value")
    except RuntimeError as exc:
        assert private_hash.KEY_ENV_VAR in str(exc)
        assert "private-value" not in str(exc)
    else:
        raise AssertionError("private_value_hmac did not fail closed without a key")

    assert private_hash.verify_private_value_hmac("private-value", "hmac:v1:generic_private_value:x", purpose="generic_private_value") is False


def test_unsupported_purpose_fails_closed(monkeypatch):
    _set_test_key(monkeypatch)

    try:
        private_hash.private_value_hmac("private-value", purpose="unsupported")
    except ValueError as exc:
        assert "unsupported" in str(exc)
        assert "private-value" not in str(exc)
    else:
        raise AssertionError("unsupported purpose was accepted")


def test_key_policy_status_does_not_expose_key(monkeypatch):
    _set_test_key(monkeypatch)

    status = private_hash.key_policy_status()
    text = private_hash.stable_json(status)

    assert status["test_key_enabled"] is True
    assert status["live_integration_ready"] is False
    assert status["test_key_treated_as_production"] is False
    assert "unit-test-only-private-value-hmac-key" not in text


def test_policy_payload_has_required_models_and_boundaries(monkeypatch):
    monkeypatch.delenv(private_hash.KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.TEST_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.ALLOW_TEST_KEY_ENV_VAR, raising=False)
    payload = private_hash.build_payload(generated_at=FIXED_NOW)

    assert payload["model_schemas"]["PrivateValueHashPolicy"]
    assert payload["output_format"] == "hmac:v1:<purpose>:<digest>"
    assert "contact_email" in payload["purposes"]
    assert "po_reference" in payload["purposes"]
    assert payload["machine_proof"]["plain_sha256_private_matching_allowed"] is False
    assert payload["machine_proof"]["plain_sha256_artifact_integrity_only"] is True
    assert payload["machine_proof"]["raw_values_in_read_model"] is False
    assert payload["machine_proof"]["key_material_exposed"] is False
    assert payload["key_policy_status"]["live_integration_ready"] is False
    assert payload["key_policy_status"]["test_key_treated_as_production"] is False
    for value in payload["authority_boundary"].values():
        assert value is False


def test_export_writes_json_and_operator_markdown_without_private_values(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(private_hash.KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.TEST_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(private_hash.ALLOW_TEST_KEY_ENV_VAR, raising=False)

    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / private_hash.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / private_hash.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    combined = private_hash.stable_json(payload) + operator

    assert summary["read_model_id"] == private_hash.READ_MODEL_ID
    assert summary["output_format"] == "hmac:v1:<purpose>:<digest>"
    assert summary["plain_sha256_private_matching_allowed"] is False
    assert summary["raw_values_in_read_model"] is False
    assert summary["key_material_exposed"] is False
    assert "Private Value Hash Policy" in operator
    for raw in (
        "Private Contact",
        "ANNETTE@EXAMPLE.COM",
        "PO private reference",
        "unit-test-only-private-value-hmac-key",
    ):
        assert raw not in combined
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", combined)
    assert "raw private body" not in combined.lower()
    assert "actual secret" not in combined.lower()


def test_module_uses_standard_library_only():
    module_path = Path(private_hash.__file__)
    text = module_path.read_text(encoding="utf-8")
    forbidden_imports = ("requests", "cryptography", "boto3", "google", "openai")

    for forbidden in forbidden_imports:
        assert f"import {forbidden}" not in text
        assert f"from {forbidden}" not in text


def test_no_credentials_secrets_or_private_bodies_in_generated_outputs(tmp_path):
    payload = private_hash.build_payload(generated_at=FIXED_NOW)
    private_hash.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "password value" not in text.lower()
    assert not re.search(r"AKIA[0-9A-Z]{16}", text)
    assert not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text)
    assert "private-value-one" not in text
