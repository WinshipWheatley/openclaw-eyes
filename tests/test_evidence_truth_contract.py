import json
from pathlib import Path

import evidence_truth_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_evidence_truth_contract import main as export_main


FIXED_NOW = "2026-06-18T22:02:00+00:00"


def _write(path: Path, payload: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write(root / "OPENCLAW_RUNTIME.md", "# Runtime\n")
    _write(root / "operator_action_covenant.py", '"""fixture"""\n')
    _write(
        root / "generated/read_models/protected_evidence_reference_receipt.json",
        {"schema_version": "protected_evidence_reference_receipt_v0"},
    )
    _write(
        root / "generated/read_models/agent_package_preview_contract.json",
        {"schema_version": "agent_package_preview_contract_v0"},
    )


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_evidence_truth_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def test_contract_is_deterministic_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "evidence_truth_contract"
    assert first["contract_status"] == "deterministic_evidence_truth_metadata_only"
    assert first["contract_only"] is True
    assert first["truth_claim_authority_added"] is False
    assert first["approval_authority_added"] is False
    assert first["execution_authority_added"] is False
    assert first["raw_private_artifact_access_added"] is False


def test_green_gate_claim_requires_current_passing_receipt():
    supported = contract.evaluate_truth_claim(
        "green_gate_claim",
        [{"type": "gate_receipt", "result": "green", "exit_code": 0, "ref": "abc123"}],
    )
    missing = contract.evaluate_truth_claim(
        "green_gate_claim",
        [{"type": "orchestration_marker", "result": "claimed_green"}],
    )

    assert supported["truth_status"] == "SUPPORTED"
    assert supported["supported"] is True
    assert missing["truth_status"] == "GREEN_GATE_RECEIPT_REQUIRED"
    assert missing["supported"] is False
    assert "green_gate_claim_requires_passing_gate_receipt" in missing["blocking_reasons"]


def test_done_and_finding_claims_need_falsifiable_artifacts():
    done = contract.evaluate_truth_claim("done_claim", [{"type": "commit_ref", "ref": "abc123"}])
    unsupported_done = contract.evaluate_truth_claim("done_claim", [{"type": "narrative", "text": "done"}])
    finding = contract.evaluate_truth_claim(
        "finding_claim",
        [{"type": "file_line_ref", "path": "module.py", "line": 17}],
    )

    assert done["truth_status"] == "SUPPORTED"
    assert unsupported_done["truth_status"] == "EVIDENCE_MISSING"
    assert "required_evidence_type_missing" in unsupported_done["blocking_reasons"]
    assert finding["truth_status"] == "SUPPORTED"


def test_contradictions_force_diagnosis_before_fixes_or_done_claims():
    decision = contract.evaluate_truth_claim(
        "diagnosis_claim",
        [{"type": "test_log", "result": "green"}],
        contradiction_refs=[{"type": "test_log", "result": "red"}],
    )

    assert decision["truth_status"] == "CONTRADICTION_REQUIRES_DIAG"
    assert decision["supported"] is False
    assert decision["contradiction_count"] == 1
    assert "contradictory_evidence_requires_diagnosis" in decision["blocking_reasons"]


def test_stale_and_unknown_claims_fail_closed():
    stale = contract.evaluate_truth_claim("finding_claim", [{"type": "file_line_ref"}], stale=True)
    unknown = contract.evaluate_truth_claim("vibes_claim", [{"type": "orchestration_marker"}])

    assert stale["truth_status"] == "STALE_REQUIRES_RECHECK"
    assert unknown["truth_status"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["blocking_reasons"] == ["unknown_claim_type"]


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["truth_rule_count"] >= 4
    assert summary["execution_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert payload["read_model_id"] == "evidence_truth_contract"
    assert "Evidence + Truth Contract v0" in operator
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_live_execution_or_private_access():
    text = Path("evidence_truth_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "import requests",
        "httpx.",
        "urllib.request",
        "selenium",
        "playwright",
        "smtplib",
        "installedappflow",
        "google_access_broker",
        ".unlink(",
        "shutil.rmtree",
        "git push",
    ]:
        assert token not in text
