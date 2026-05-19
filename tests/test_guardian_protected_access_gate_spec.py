import ast
import json
from pathlib import Path

import guardian_protected_access_gate_spec as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_guardian_protected_access_gate_spec import main as export_main


FIXED_NOW = "2026-05-19T04:00:00+00:00"


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
    _write(
        root / "generated/read_models/protected_evidence_reference_receipt.json",
        {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "receipt_records": [
                {
                    "receipt_id": "protected_ref_receipt_missing",
                    "receipt_type": "coupa_payment_invoice_proof_reference",
                    "workflow_id": "capital_hilton_coupa_supplier_portal_invoice",
                    "workflow_name": "Capital Hilton Coupa supplier-portal invoice",
                    "protected_evidence_type": "coupa_payment_invoice_proof",
                    "receipt_status": "REFERENCE_MISSING",
                    "missing_required_metadata": ["protected_reference_id"],
                    "forbidden_input_keys_refused": [],
                    "receipt_grants_raw_access": False,
                    "receipt_grants_approval_authority": False,
                    "receipt_grants_execution_authority": False,
                    "receipt_grants_send_or_submit_authority": False,
                    "agent_direct_access_allowed": False,
                }
            ],
        },
    )
    _write(
        root / "generated/read_models/operator_sovereignty_power_stage_gate.json",
        {
            "schema_version": "operator_sovereignty_power_stage_gate_read_model_v0",
            "stage_3_blocked_without_protected_pii_broker_controls": True,
            "stage_4_blocked_without_hard_stop_and_tamper_controls": True,
        },
    )
    _write(
        root / "generated/read_models/guardian_responsibility_dna_audit.json",
        {
            "schema_version": "guardian_responsibility_dna_audit_v0",
            "guardian_modeled_as_executor": False,
        },
    )


def _build(tmp_path: Path, receipt_inputs: dict | None = None, gate_requests: dict | None = None) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return gate.build_guardian_protected_access_gate_spec(
        repo_root=repo,
        receipt_inputs=receipt_inputs,
        gate_requests=gate_requests,
        generated_at=FIXED_NOW,
    )


def _record(payload: dict, gate_key: str) -> dict:
    return next(item for item in payload["gate_records"] if item["gate_key"] == gate_key)


def _valid_coupa_receipt_inputs() -> dict:
    return {
        "protected_evidence_references": {
            "coupa_payment_invoice_proof_reference": {
                "protected_reference_id": "protected-coupa-ref",
                "artifact_identity_or_hash": "sha256:redacted-coupa-metadata-hash",
                "po_reference": "DCASH00983536",
                "amount": "800.00 USD",
                "validation_status": "metadata_valid",
                "redaction_status": "redacted_reference_only",
                "protection_status": "protected_local_reference",
            }
        }
    }


def test_default_gate_blocks_protected_access_now(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == gate.SCHEMA_VERSION
    assert payload["protected_access_allowed_now"] is False
    assert payload["current_availability_status"] == "protected_access_blocked_now"
    assert payload["gate_summary"]["protected_access_allowed_now"] is False
    assert payload["raw_content_boundary"]["raw_content_access_allowed_now"] is False


def test_receipt_does_not_grant_access_even_when_valid_metadata_exists(tmp_path):
    payload = _build(
        tmp_path,
        receipt_inputs=_valid_coupa_receipt_inputs(),
        gate_requests={
            "protected_access_requests": {
                "coupa_payment_invoice_proof_reference": {
                    "access_requested": True,
                    "requested_action": "future_use_coupa_payment_invoice_proof_reference",
                }
            }
        },
    )
    record = _record(payload, "capital_hilton_coupa_payment_invoice_proof_access")

    assert record["protected_evidence_reference_receipt_requirement"]["receipt_status"] == "METADATA_VALID"
    assert record["protected_evidence_reference_receipt_requirement"]["receipt_does_not_grant_access"] is True
    assert record["current_access_state"] == "SECURITY_THRESHOLD_REQUIRED"
    assert record["protected_access_allowed_now"] is False
    assert record["proof_receipt_metadata_exists"] is True


def test_reference_missing_and_metadata_incomplete_are_explicit(tmp_path):
    missing_payload = _build(
        tmp_path,
        gate_requests={
            "protected_access_requests": {
                "coupa_payment_invoice_proof_reference": {"access_requested": True}
            }
        },
    )
    missing = _record(missing_payload, "capital_hilton_coupa_payment_invoice_proof_access")

    incomplete_payload = _build(
        tmp_path,
        receipt_inputs={
            "protected_evidence_references": {
                "pdf_invoice_artifact_reference": {
                    "protected_reference_id": "protected-pdf-ref",
                    "invoice_number": "2026-1005",
                }
            }
        },
        gate_requests={
            "protected_access_requests": {
                "pdf_invoice_artifact_reference": {"access_requested": True}
            }
        },
    )
    incomplete = _record(incomplete_payload, "capital_hilton_pdf_invoice_attachment_access")

    assert missing["current_access_state"] == "REFERENCE_MISSING"
    assert incomplete["current_access_state"] == "METADATA_INCOMPLETE"
    assert any(blocker["blocker_id"] == "metadata_incomplete" for blocker in incomplete["blockers"])


def test_guardian_review_and_security_threshold_are_required_before_future_review(tmp_path):
    security_payload = _build(
        tmp_path,
        receipt_inputs=_valid_coupa_receipt_inputs(),
        gate_requests={"coupa_payment_invoice_proof_reference": {"access_requested": True}},
    )
    security = _record(security_payload, "capital_hilton_coupa_payment_invoice_proof_access")

    guardian_payload = _build(
        tmp_path,
        receipt_inputs=_valid_coupa_receipt_inputs(),
        gate_requests={
            "coupa_payment_invoice_proof_reference": {
                "access_requested": True,
                "security_threshold_controls_ready": True,
            }
        },
    )
    guardian = _record(guardian_payload, "capital_hilton_coupa_payment_invoice_proof_access")

    future_payload = _build(
        tmp_path,
        receipt_inputs=_valid_coupa_receipt_inputs(),
        gate_requests={
            "coupa_payment_invoice_proof_reference": {
                "access_requested": True,
                "security_threshold_controls_ready": True,
                "guardian_review_ready": True,
            }
        },
    )
    future = _record(future_payload, "capital_hilton_coupa_payment_invoice_proof_access")

    assert security["current_access_state"] == "SECURITY_THRESHOLD_REQUIRED"
    assert guardian["current_access_state"] == "GUARDIAN_REVIEW_REQUIRED"
    assert future["current_access_state"] == "ACCESS_READY_FOR_FUTURE_GATED_REVIEW"
    assert future["protected_access_allowed_now"] is False
    assert future["available_for_future_gated_review"] is True


def test_reference_recorded_without_validation_is_still_access_blocked(tmp_path):
    payload = _build(
        tmp_path,
        receipt_inputs={
            "protected_evidence_references": {
                "coupa_payment_invoice_proof_reference": {
                    "protected_reference_id": "protected-coupa-ref",
                    "artifact_identity_or_hash": "sha256:redacted-coupa-metadata-hash",
                    "po_reference": "DCASH00983536",
                    "amount": "800.00 USD",
                    "redaction_status": "redacted_reference_only",
                    "protection_status": "protected_local_reference",
                }
            }
        },
        gate_requests={"coupa_payment_invoice_proof_reference": {"access_requested": True}},
    )
    record = _record(payload, "capital_hilton_coupa_payment_invoice_proof_access")

    assert record["current_access_state"] == "REFERENCE_RECORDED_ACCESS_BLOCKED"
    assert record["protected_access_allowed_now"] is False
    assert any(blocker["blocker_id"] == "reference_recorded_but_access_blocked" for blocker in record["blockers"])


def test_raw_content_remains_forbidden_and_rejected_receipt_denies_access(tmp_path):
    payload = _build(
        tmp_path,
        receipt_inputs={
            "protected_evidence_references": {
                "excel_companion_artifact_reference": {
                    "protected_reference_id": "protected-excel-ref",
                    "artifact_identity_or_hash": "sha256:redacted-excel-metadata-hash",
                    "invoice_number": "2026-1005",
                    "amount": "800.00 USD",
                    "raw_excel_body": "RAW EXCEL BODY MUST NOT APPEAR",
                }
            }
        },
        gate_requests={"excel_companion_artifact_reference": {"access_requested": True}},
    )
    record = _record(payload, "capital_hilton_excel_companion_artifact_access")
    text = json.dumps(payload).lower()

    assert record["current_access_state"] == "ACCESS_DENIED"
    assert "raw_excel_body" in record["forbidden_raw_content_fields"]
    assert payload["raw_content_boundary"]["raw_content_inspected"] is False
    assert "raw excel body must not appear" not in text


def test_credentials_oauth_browser_and_tool_bridges_remain_blocked(tmp_path):
    credential_payload = _build(
        tmp_path,
        receipt_inputs={
            "protected_evidence_references": {
                "client_credential_reference": {
                    "protected_reference_id": "protected-credential-ref",
                    "source_system_label": "client_portal",
                    "protection_status": "protected_local_reference",
                    "password": "secret-value",
                }
            }
        },
        gate_requests={"client_credential_reference": {"access_requested": True}},
    )
    credential = _record(credential_payload, "client_credential_reference_access")
    bridge = _record(credential_payload, "browser_oauth_tool_bridge_reference_access")
    text = json.dumps(credential_payload).lower()

    assert credential["current_access_state"] == "ACCESS_DENIED"
    assert bridge["current_access_state"] == "UNKNOWN_FAIL_CLOSED"
    assert any(blocker["blocker_id"] == "receipt_contract_missing_for_surface" for blocker in bridge["blockers"])
    assert "secret-value" not in text
    assert credential_payload["credentials_accessed"] is False
    assert credential_payload["oauth_flow_started"] is False
    assert credential_payload["browser_automation_added"] is False


def test_unknown_protected_access_fails_closed(tmp_path):
    payload = _build(
        tmp_path,
        gate_requests={"unknown_sensitive_surface_reference": {"access_requested": True}},
    )
    unknown = _record(payload, "unknown_sensitive_surface_access")

    assert unknown["current_access_state"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["protected_access_allowed_now"] is False
    assert any(blocker["blocker_id"] == "unknown_or_unsupported_protected_access" for blocker in unknown["blockers"])


def test_no_approval_receipt_execution_send_or_upload_authority_is_created(tmp_path):
    payload = _build(tmp_path)

    for key, expected in gate.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["approval_receipt_created"] is False
    assert payload["execution_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["protected_artifact_access_granted"] is False


def test_eli5_summary_exists(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "protected proof exists" in eli5["openclaw_can_know_protected_proof_exists"]
    assert "not the key" in eli5["receipt_is_not_the_key"]
    assert "eligible for later gated review" in eli5["guardian_decides_if_future_use_is_reviewable"]
    assert "Nothing opens" in eli5["nothing_opens_sends_uploads_or_executes_yet"]


def test_generated_read_model_is_deterministic_exportable_and_safe_mirror_candidate(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    first = gate.build_guardian_protected_access_gate_spec(repo_root=repo, generated_at=FIXED_NOW)
    second = gate.build_guardian_protected_access_gate_spec(repo_root=repo, generated_at=FIXED_NOW)
    assert gate.stable_json(first) == gate.stable_json(second)

    exit_code = export_main(["--repo-root", str(repo), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / gate.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))

    assert exit_code == 0
    assert "Guardian Protected Access Gate Spec" in operator_text
    assert payload["schema_version"] == gate.SCHEMA_VERSION
    assert gate.JSON_EXPORT_NAME in expected
    assert gate.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_live_brokers_or_execute_network_browser_or_repo_b():
    source_files = [
        Path("guardian_protected_access_gate_spec.py"),
        Path("scripts/export_guardian_protected_access_gate_spec.py"),
    ]
    forbidden_text = [
        "/home/openclaw_external/openclaw-runtime",
        "subprocess.",
        "os.system",
        "asyncio.",
        "import requests",
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
