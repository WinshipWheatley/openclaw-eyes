import ast
import json
from pathlib import Path

import protected_evidence_reference_receipt as receipt
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_protected_evidence_reference_receipt import main as export_main


FIXED_NOW = "2026-05-19T03:00:00+00:00"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write(
        root / "generated/read_models/protected_access_broker_concept.json",
        {
            "schema_version": "protected_access_broker_concept_v0",
            "live_access_blocked": True,
            "agents_receive_direct_credentials": False,
        },
    )


def _build(tmp_path: Path, inputs: dict | None = None) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return receipt.build_protected_evidence_reference_receipt(
        repo_root=repo,
        receipt_inputs=inputs,
        generated_at=FIXED_NOW,
    )


def _record(payload: dict, receipt_type: str) -> dict:
    return next(item for item in payload["receipt_records"] if item["receipt_type"] == receipt_type)


def test_default_export_records_no_real_sensitive_proof(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == receipt.SCHEMA_VERSION
    assert payload["receipt_summary"]["real_sensitive_proof_recorded"] is False
    assert payload["real_sensitive_proof_recorded"] is False
    assert payload["raw_content_stored"] is False
    assert payload["authority_boundary"]["receipt_is_reference_only"] is True
    assert payload["authority_boundary"]["underlying_raw_artifact_truth_not_proven_by_receipt"] is True


def test_protected_reference_metadata_can_be_represented_without_raw_access(tmp_path):
    payload = _build(
        tmp_path,
        {
            "protected_evidence_references": {
                "coupa_payment_invoice_proof_reference": {
                    "protected_reference_id": "protected-capital-hilton-coupa-ref",
                    "artifact_identity_or_hash": "sha256:redacted-coupa-metadata-hash",
                    "po_reference": "DCASH00983536",
                    "amount": "800.00 USD",
                    "validation_status": "metadata_valid",
                    "redaction_status": "redacted_reference_only",
                    "protection_status": "protected_local_reference",
                    "operator_confirmation_status": "operator_supplied_metadata_only",
                }
            }
        },
    )
    record = _record(payload, "coupa_payment_invoice_proof_reference")

    assert record["receipt_status"] == "METADATA_VALID"
    assert record["protected_reference_id"] == "protected-capital-hilton-coupa-ref"
    assert record["safe_metadata"]["amount"] == "800.00 USD"
    assert record["receipt_grants_raw_access"] is False
    assert record["receipt_grants_execution_authority"] is False
    assert record["underlying_raw_artifact_truth_proven"] is False
    assert record["access_use_status"] == "PROTECTED_ACCESS_REQUIRED"


def test_raw_pdfs_excel_bodies_and_private_docs_are_rejected(tmp_path):
    payload = _build(
        tmp_path,
        {
            "protected_evidence_references": {
                "excel_companion_artifact_reference": {
                    "protected_reference_id": "protected-excel-ref",
                    "artifact_identity_or_hash": "sha256:redacted-excel-metadata-hash",
                    "invoice_number": "2026-1005",
                    "amount": "800.00 USD",
                    "raw_excel_body": "RAW EXCEL CONTENT THAT MUST NOT APPEAR",
                    "raw_pdf_body": "RAW PDF CONTENT THAT MUST NOT APPEAR",
                    "raw_private_document": "PRIVATE DOC BODY",
                }
            }
        },
    )
    record = _record(payload, "excel_companion_artifact_reference")
    text = json.dumps(payload).lower()

    assert record["receipt_status"] == "RAW_CONTENT_REJECTED"
    assert record["raw_content_rejected"] is True
    assert set(record["forbidden_input_keys_refused"]) == {"raw_excel_body", "raw_pdf_body", "raw_private_document"}
    assert "raw excel content" not in text
    assert "raw pdf content" not in text
    assert "private doc body" not in text


def test_credentials_tokens_oauth_bank_remit_and_check_images_are_rejected(tmp_path):
    payload = _build(
        tmp_path,
        {
            "protected_evidence_references": {
                "client_credential_reference": {
                    "protected_reference_id": "protected-client-credential-ref",
                    "source_system_label": "client_portal",
                    "protection_status": "protected_local_reference",
                    "password": "hunter2-secret",
                    "oauth_token": "oauth-token-value",
                    "api_key": "api-key-value",
                },
                "bank_remit_home_check_image_sensitive_reference": {
                    "protected_reference_id": "protected-bank-ref",
                    "redaction_status": "redacted",
                    "protection_status": "protected_local_reference",
                    "bank_account": "123456789",
                    "routing_number": "987654321",
                    "home_address": "123 Private Street",
                    "check_image": "raw-image-bytes",
                },
            }
        },
    )
    credential = _record(payload, "client_credential_reference")
    finance = _record(payload, "bank_remit_home_check_image_sensitive_reference")
    text = json.dumps(payload).lower()

    assert credential["receipt_status"] == "RAW_CONTENT_REJECTED"
    assert finance["receipt_status"] == "RAW_CONTENT_REJECTED"
    assert {"password", "oauth_token", "api_key"}.issubset(set(credential["forbidden_input_keys_refused"]))
    assert {"bank_account", "routing_number", "home_address", "check_image"}.issubset(
        set(finance["forbidden_input_keys_refused"])
    )
    assert "hunter2-secret" not in text
    assert "oauth-token-value" not in text
    assert "123 private street" not in text
    assert payload["credentials_or_tokens_stored"] is False
    assert payload["pii_bank_remit_check_image_stored"] is False


def test_metadata_incomplete_and_invalid_statuses_are_explicit(tmp_path):
    payload = _build(
        tmp_path,
        {
            "protected_evidence_references": {
                "pdf_invoice_artifact_reference": {
                    "protected_reference_id": "protected-pdf-ref",
                    "invoice_number": "2026-1005",
                },
                "gmail_email_evidence_reference": {
                    "protected_reference_id": "protected-email-ref",
                    "artifact_identity_or_hash": "sha256:redacted-email-metadata-hash",
                    "source_system_label": "gmail",
                    "validation_status": "invalid",
                    "mismatch_reasons": ["draft_identity_missing"],
                },
            }
        },
    )
    pdf = _record(payload, "pdf_invoice_artifact_reference")
    gmail = _record(payload, "gmail_email_evidence_reference")

    assert pdf["receipt_status"] == "METADATA_INCOMPLETE"
    assert "artifact_identity_or_hash" in pdf["missing_required_metadata"]
    assert gmail["receipt_status"] == "METADATA_INVALID"
    assert gmail["mismatch_error_reasons"] == ["draft_identity_missing"]


def test_unknown_sensitive_surface_fails_closed(tmp_path):
    payload = _build(
        tmp_path,
        {
            "protected_evidence_references": {
                "unknown_sensitive_surface_reference": {
                    "protected_reference_id": "unknown-ref",
                    "surface_label": "operator-mentioned private thing",
                }
            }
        },
    )
    unknown = _record(payload, "unknown_sensitive_surface_reference")

    assert unknown["receipt_status"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["future_access_or_use_requires_guardian_gate"] is True
    assert unknown["future_access_or_use_requires_security_threshold"] is True


def test_receipt_is_not_approval_execution_or_raw_access_authority(tmp_path):
    payload = _build(tmp_path)

    assert payload["authority_boundary"]["receipt_is_not_approval_authority"] is True
    assert payload["authority_boundary"]["receipt_is_not_execution_authority"] is True
    assert payload["authority_boundary"]["receipt_does_not_grant_raw_access"] is True
    for record in payload["receipt_records"]:
        assert record["receipt_grants_approval_authority"] is False
        assert record["receipt_grants_execution_authority"] is False
        assert record["receipt_grants_send_or_submit_authority"] is False
        assert record["agent_direct_access_allowed"] is False


def test_guardian_and_security_threshold_remain_required(tmp_path):
    payload = _build(tmp_path)

    assert payload["authority_boundary"]["future_guardian_gate_required_before_access_use"] is True
    assert payload["authority_boundary"]["future_security_threshold_required_before_live_access"] is True
    for record in payload["receipt_records"]:
        assert record["future_access_or_use_requires_guardian_gate"] is True
        assert record["future_access_or_use_requires_security_threshold"] is True


def test_eli5_summary_exists(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "protected proof exists" in eli5["openclaw_can_remember_protected_proof_exists"]
    assert "not passwords" in eli5["stores_only_safe_metadata_reference_not_secret_raw_file"]
    assert "not a key" in eli5["receipt_does_not_give_agents_access"]
    assert "does not approve sends" in eli5["receipt_does_not_authorize_execution"]
    assert "Future workflows can cite protected proof references" in eli5["what_this_unlocks_later"]


def test_no_live_execution_or_access_is_enabled(tmp_path):
    payload = _build(tmp_path)

    for key, expected in receipt.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["coupa_accessed"] is False
    assert payload["gmail_calendar_accessed"] is False
    assert payload["oauth_access_enabled"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False


def test_generated_read_model_is_deterministic_exportable_and_safe_mirror_candidate(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    first = receipt.build_protected_evidence_reference_receipt(repo_root=repo, generated_at=FIXED_NOW)
    second = receipt.build_protected_evidence_reference_receipt(repo_root=repo, generated_at=FIXED_NOW)
    assert receipt.stable_json(first) == receipt.stable_json(second)

    exit_code = export_main(["--repo-root", str(repo), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / receipt.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))

    assert exit_code == 0
    assert "Protected Evidence Reference Receipt" in operator_text
    assert payload["schema_version"] == receipt.SCHEMA_VERSION
    assert receipt.JSON_EXPORT_NAME in expected
    assert receipt.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_live_brokers_or_execute_network_browser_or_repo_b():
    source_files = [
        Path("protected_evidence_reference_receipt.py"),
        Path("scripts/export_protected_evidence_reference_receipt.py"),
    ]
    forbidden_text = [
        "/home/openclaw_external/openclaw-runtime",
        "subprocess.",
        "os.system",
        "asyncio.",
        "requests.",
        "httpx.",
        "urllib.request",
        "selenium",
        "playwright",
        "pyautogui",
        "smtplib",
        "InstalledAppFlow",
        "build(\"gmail\"",
        "build(\"calendar\"",
        "send_message(",
        "reply_text(",
        "send_email(",
        "import google_access_broker",
        "from google_access_broker",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_text:
            assert needle not in text
        tree = ast.parse(text)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert "subprocess" not in imported
        assert "requests" not in imported
        assert "httpx" not in imported
        assert "google_access_broker" not in imported
