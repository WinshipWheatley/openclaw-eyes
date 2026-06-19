import ast
import json
from pathlib import Path

import niles_album_evidence_intake_boundary as evidence_boundary
import niles_album_matrix_review as matrix_review
import niles_album_metadata_intake_packet as metadata_packet
import niles_album_review_packet as review_packet
import niles_stage1_contract as contract
from scripts.export_niles_stage1_contract import main as export_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_source_contracts(tmp_path: Path, *, omit: str | None = None) -> Path:
    read_models = tmp_path / "generated" / "read_models"
    read_models.mkdir(parents=True, exist_ok=True)
    specs = {
        "niles_album_evidence_intake_boundary": evidence_boundary.SCHEMA_VERSION,
        "niles_album_metadata_intake_packet": metadata_packet.SCHEMA_VERSION,
        "niles_album_review_packet": review_packet.SCHEMA_VERSION,
        "niles_album_matrix_review": matrix_review.SCHEMA_VERSION,
    }
    for source_id, schema_version in specs.items():
        if source_id == omit:
            continue
        (read_models / f"{source_id}.json").write_text(
            json.dumps(
                {
                    "schema_version": schema_version,
                    "source_id": source_id,
                    "truth_status": "contract_evidence_not_album_truth",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    for module_path in [
        "niles_album_evidence_intake_boundary.py",
        "niles_album_metadata_intake_packet.py",
        "niles_album_review_packet.py",
        "niles_album_matrix_review.py",
    ]:
        (tmp_path / module_path).write_text("# test source placeholder\n", encoding="utf-8")
    return tmp_path


def test_stage1_contract_is_deterministic():
    first = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)
    second = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["contract_status"] == "stage_1_schema_contracts_ready_metadata_only"


def test_stage1_composes_existing_niles_contracts_without_parallel_rebuild(tmp_path):
    repo_root = _write_source_contracts(tmp_path)
    payload = contract.build_niles_stage1_contract(repo_root=repo_root, generated_at=FIXED_NOW)
    sources = {source["source_id"]: source for source in payload["existing_contracts"]}

    assert set(sources) == {
        "niles_album_evidence_intake_boundary",
        "niles_album_metadata_intake_packet",
        "niles_album_review_packet",
        "niles_album_matrix_review",
    }
    assert sources["niles_album_evidence_intake_boundary"]["schema_version"] == evidence_boundary.SCHEMA_VERSION
    assert sources["niles_album_metadata_intake_packet"]["schema_version"] == metadata_packet.SCHEMA_VERSION
    assert sources["niles_album_review_packet"]["schema_version"] == review_packet.SCHEMA_VERSION
    assert sources["niles_album_matrix_review"]["schema_version"] == matrix_review.SCHEMA_VERSION
    assert all(source["module_present"] for source in sources.values())
    assert all(source["read_model_present"] for source in sources.values())
    assert payload["machine_proof"]["source_contract_count"] == 4
    assert payload["machine_proof"]["missing_source_contract_count"] == 0


def test_missing_source_contract_blocks_stage1_readiness(tmp_path):
    repo_root = _write_source_contracts(tmp_path, omit="niles_album_matrix_review")

    payload = contract.build_niles_stage1_contract(repo_root=repo_root, generated_at=FIXED_NOW)

    assert payload["stage_1_ready"] is False
    assert payload["contract_status"] == "blocked_missing_stage_1_source_contracts"
    assert payload["machine_proof"]["missing_source_contract_count"] == 1
    decision = payload["stage_decisions"]["stage_1_schema_contracts"]
    assert decision["decision"] == "blocked_missing_source_contracts"
    assert decision["allowed"] is False


def test_stage_gates_keep_taste_calibration_for_master_later():
    payload = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)
    gates = {gate["stage_id"]: gate for gate in payload["stage_gates"]}

    assert gates["stage_1_schema_contracts"]["status"] == "ready"
    assert gates["stage_1_schema_contracts"]["allowed_now"] is True
    assert gates["stage_4_taste_calibration_master_only"]["status"] == "blocked_until_master_calibration"
    assert gates["stage_4_taste_calibration_master_only"]["owner"] == "master"
    assert gates["stage_4_taste_calibration_master_only"]["allowed_now"] is False
    assert payload["master_taste_calibration"]["included_now"] is False
    assert payload["master_taste_calibration"]["required_later"] is True
    assert payload["stage_decisions"]["stage_4_taste_calibration_master_only"]["allowed"] is False


def test_release_publish_runtime_and_external_send_requests_fail_closed():
    release = contract.evaluate_niles_stage1_transition(
        "stage_5_release_publish_future_gate",
        release_authority_requested=True,
    )
    runtime = contract.evaluate_niles_stage1_transition(
        "stage_1_schema_contracts",
        runtime_authority_requested=True,
    )
    external_send = contract.evaluate_niles_stage1_transition(
        "stage_1_schema_contracts",
        external_send_requested=True,
    )

    assert release.decision == "blocked_release_or_publish_request"
    assert release.allowed is False
    assert runtime.decision == "blocked_runtime_authority_request"
    assert runtime.allowed is False
    assert external_send.decision == "blocked_external_send_request"
    assert external_send.allowed is False
    assert release.authority_added is False
    assert runtime.authority_added is False
    assert external_send.authority_added is False


def test_raw_audio_daw_scan_mutation_repo_b_money_and_send_boundaries_are_blocked():
    payload = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)
    flags = payload["authority_boundary"]
    forbidden = payload["forbidden_boundaries"]

    assert "raw_audio" in payload["blocked_boundaries"]
    assert "daw_session_contents" in payload["blocked_boundaries"]
    assert "private_drive_crawl" in payload["blocked_boundaries"]
    assert "audio_or_session_file_mutation" in payload["blocked_boundaries"]
    assert "release_or_publish_action" in payload["blocked_boundaries"]
    assert forbidden["raw_audio_ingest"] == "forbidden"
    assert forbidden["daw_session_content_ingest"] == "forbidden"
    assert forbidden["broad_private_drive_scan"] == "forbidden"
    assert forbidden["external_send_or_submit"] == "forbidden"
    assert forbidden["money_or_payment_action"] == "forbidden"
    assert flags["raw_audio_ingest_allowed"] is False
    assert flags["daw_session_content_ingest_allowed"] is False
    assert flags["broad_private_drive_scan_allowed"] is False
    assert flags["audio_file_mutation_allowed"] is False
    assert flags["repo_b_authority_allowed"] is False
    assert flags["money_or_payment_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False


def test_no_runtime_tool_model_approval_or_mission_control_authority_added():
    payload = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)
    flags = payload["authority_boundary"]

    assert payload["read_model_only"] is True
    assert flags["runtime_authority_added"] is False
    assert flags["tool_execution_authority_added"] is False
    assert flags["model_execution_authority_added"] is False
    assert flags["approval_authority_added"] is False
    assert flags["release_or_publish_authority_added"] is False
    assert flags["mission_control_app_changed"] is False
    assert payload["receipt_proof_status"]["external_action_taken"] is False
    assert payload["receipt_proof_status"]["mission_control_app_changed"] is False


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    repo_root = _write_source_contracts(tmp_path)
    export_root = "generated/read_models"

    result = contract.export_niles_stage1_contract(
        repo_root=repo_root,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((repo_root / export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (repo_root / export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.contract_status == "stage_1_schema_contracts_ready_metadata_only"
    assert result.stage_1_ready is True
    assert result.taste_calibration_included is False
    assert result.runtime_authority_added is False
    assert result.send_or_submit_authority_added is False
    assert result.release_or_publish_authority_added is False
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert "Niles Stage 1 Contract v0" in operator
    assert "Taste calibration included: `false`" in operator
    assert "Release/publish authority added: `false`" in operator
    assert export_main(["--repo-root", str(repo_root), "--export-root", export_root, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["contract_status"] == "stage_1_schema_contracts_ready_metadata_only"


def test_canonical_generated_read_model_expected_files_are_declared():
    payload = contract.build_niles_stage1_contract(generated_at=FIXED_NOW)

    assert payload["canonical_generated_read_model_expected_files"] == [
        "generated/read_models/niles_stage1_contract.json",
        "generated/read_models/niles_stage1_contract_OPERATOR.md",
    ]


def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "niles_stage1_contract.py",
            "scripts/export_niles_stage1_contract.py",
        ]
    )
    forbidden = [
        "subprocess",
        "os.system",
        "shutil.",
        "copy2",
        "rename(",
        "unlink(",
        "remove(",
        "rmtree",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "send_message",
        "reply_text",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source


def test_source_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("niles_stage1_contract.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2


def test_mission_control_app_code_is_not_referenced_or_changed():
    source = Path("niles_stage1_contract.py").read_text(encoding="utf-8").lower()

    assert "openclaw mission controle" not in source
    assert "mission_control_app_changed\": true" not in source
