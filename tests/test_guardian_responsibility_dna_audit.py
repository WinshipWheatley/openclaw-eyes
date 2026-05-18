import json
from pathlib import Path

import guardian_responsibility_dna_audit as audit
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_guardian_responsibility_dna_audit import main as export_main


FIXED_NOW = "2026-05-18T12:00:00+00:00"


def _payload():
    return audit.build_guardian_responsibility_dna_audit(generated_at=FIXED_NOW)


def _by_id(payload):
    return {item["responsibility_id"]: item for item in payload["responsibilities"]}


def test_audit_is_deterministic_and_classifies_guardian_responsibilities():
    first = _payload()
    second = _payload()

    assert audit.stable_json(first) == audit.stable_json(second)
    assert first["schema_version"] == audit.SCHEMA_VERSION
    assert first["audit_status"] == "ready_for_specific_approval_request_contract_not_execution"
    assert first["responsibility_classifications"]["CANONICAL_DETERMINISTIC"] >= 4
    assert first["responsibility_classifications"]["UNSAFE_OR_BLOCKED"] >= 1
    assert first["responsibility_classifications"]["UNKNOWN_NEEDS_REVIEW"] >= 1


def test_guardian_is_not_modeled_as_executor_or_generic_authority():
    payload = _payload()

    assert payload["guardian_modeled_as_executor"] is False
    assert payload["generic_approval_authority_added"] is False
    assert payload["execution_authority_added"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert "generic approval authority" in payload["blocked_authority_surfaces"]


def test_start_approval_and_final_send_approval_remain_distinct():
    distinction = _payload()["start_vs_final_send_approval_distinction"]

    assert distinction["start_approval"]["send_authority"] is False
    assert distinction["final_send_approval"]["send_authority_now"] is False
    assert distinction["start_approval"]["defining_file"] == "capital_hilton_coupa_start_approval_packet.py"
    assert distinction["final_send_approval"]["defining_file"] == "capital_hilton_send_approval_gate.py"


def test_unknown_or_ambiguous_authority_fails_closed_and_sensitive_scope_preserved():
    payload = _payload()
    by_id = _by_id(payload)

    assert payload["operator_sovereignty_security_relevance"]["unknown_or_ambiguous_authority_fails_closed"] is True
    assert payload["operator_sovereignty_security_relevance"]["guardian_monitors_authority_surfaces_not_private_life"] is True
    assert by_id["unknown_future_guardian_capability"]["classification"] == "UNKNOWN_NEEDS_REVIEW"
    assert by_id["sensitive_no_go_policy"]["classification"] == "TESTED_SUPPORTING_CONTRACT"
    assert "raw private content surveillance" in payload["blocked_authority_surfaces"]


def test_review_approval_request_receipt_and_execution_are_distinct_concepts():
    taxonomy = _payload()["approval_request_receipt_execution_taxonomy"]

    assert "never approval or execution" in taxonomy["review_packet"]
    assert "immutable scope" in taxonomy["approval_request"]
    assert "not generic authority" in taxonomy["approval_receipt"]
    assert "not performed or enabled" in taxonomy["execution"]


def test_cassandra_capital_hilton_guardian_relevance_is_blocked_until_proof_and_specific_scope():
    payload = _payload()
    relevance = payload["cassandra_capital_hilton_relevance"]
    by_id = _by_id(payload)

    assert relevance["cassandra_current_role"] == "review-only draft packet producer, not executor"
    assert "blocked_until_coupa_excel" in relevance["capital_hilton_final_send_state"]
    assert "specific draft" in relevance["approval_request_safe_only_when"]
    assert by_id["cassandra_capital_hilton_review_integration"]["classification"] == "TESTED_SUPPORTING_CONTRACT"


def test_next_lane_does_not_enable_runtime_send_browser_or_credential_authority():
    payload = _payload()

    assert payload["next_safe_lane"] == "Guardian Draft Approval Request Contract v0"
    for forbidden_key in [
        "runtime_authority_added",
        "send_or_submit_authority_added",
        "browser_or_coupa_authority_added",
        "credential_or_oauth_access_added",
        "telegram_send_added",
        "gmail_draft_or_send_added",
        "calendar_access_added",
        "spreadsheet_mutation_added",
    ]:
        assert payload[forbidden_key] is False
        assert payload["no_authority_flags"][forbidden_key] is False


def test_export_writes_json_operator_and_cli(tmp_path, capsys):
    export_root = tmp_path / "generated/read_models"
    result = audit.export_guardian_responsibility_dna_audit(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    json_path = export_root / audit.JSON_EXPORT_NAME
    operator_path = export_root / audit.OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert result["guardian_modeled_as_executor"] is False

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = operator_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == audit.SCHEMA_VERSION
    assert "Guardian Responsibility + Deterministic DNA Audit v0" in rendered
    assert "Guardian is not modeled as executor: `false`" in rendered

    assert export_main(["--export-root", str(export_root), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["runtime_authority_added"] is False


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated/read_models"
    audit.export_guardian_responsibility_dna_audit(export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert audit.JSON_EXPORT_NAME in expected
    assert audit.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_forbidden_live_authority():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in ["guardian_responsibility_dna_audit.py", "scripts/export_guardian_responsibility_dna_audit.py"]
    )
    forbidden = [
        "google_access_broker(",
        "smtplib",
        "imaplib",
        "selenium",
        "playwright",
        "subprocess.run",
        "requests.post",
        "send_approval(",
        "create_draft",
        "send_email",
        "from oauth",
        "import oauth",
    ]
    for token in forbidden:
        assert token not in source
