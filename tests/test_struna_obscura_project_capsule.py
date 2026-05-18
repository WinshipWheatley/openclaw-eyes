import ast
import json
from pathlib import Path
import struna_obscura_project_capsule as capsule
from scripts.export_struna_obscura_project_capsule import main as export_main
FIXED_NOW = "2026-05-18T12:00:00+00:00"

def test_struna_capsule_is_deterministic_project_metadata():
    first = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    second = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    assert capsule.stable_json(first) == capsule.stable_json(second)
    assert first["project_name"] == "Struna Obscura"
    assert first["project_type"] == ["external_collaboration", "creative_software", "synth_plugin_or_app"]
    assert first["tracking_status"] == "tracked_for_future_niles_resume"
    assert first["tracking_only"] is True and first["metadata_only"] is True

def test_struna_paths_and_paused_lane_are_tracked_without_execution():
    payload = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    assert payload["paths"]["working_repo_path"] == capsule.WORKING_REPO_PATH
    assert payload["paths"]["original_source_drop_path"] == capsule.ORIGINAL_SOURCE_DROP_PATH
    assert payload["technical_checkpoint"]["current_known_commit"] == "0345e7c"
    assert payload["paused_issue"]["issue_label"] == "tab_navigation_did_not_change_pages"
    assert payload["next_safe_lane"] == "Tabbed Navigation Reality Fix v0"
    assert payload["struna_build_or_test_run"] is False

def test_niles_can_discover_and_resume_struna_from_read_model():
    payload = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    assert payload["niles_relevance"]["resume_target_phrase"] == "Niles, let's work on Struna"
    assert payload["niles_relevance"]["resume_ready"] is True
    assert payload["niles_relevance"]["discoverable_from_read_model"] is True
    assert payload["resume_packet"]["route_to"] == "Tabbed Navigation Reality Fix v0"
    assert payload["resume_packet"]["struna_repo_modification_allowed_by_this_capsule"] is False

def test_business_terms_are_operator_reported_evidence_not_legal_truth():
    payload = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    terms = payload["business_legal_terms"]
    assert terms["evidence_posture"] == "operator_reported_evidence_not_final_legal_truth"
    assert terms["formal_proof_needed"] is True
    assert payload["formal_proof_needed_for_business_terms"] is True
    assert all(term["truth_status"] == "operator_reported_unverified" for term in terms["terms"])
    assert any("25% of sales" in term["operator_reported_term"] for term in terms["terms"])

def test_sensitive_data_and_authority_boundaries_are_closed():
    payload = capsule.build_struna_obscura_project_capsule(generated_at=FIXED_NOW)
    forbidden = payload["sensitive_data_boundary"]["forbidden"]
    flags = payload["authority_boundary"]
    assert "raw legal documents" in forbidden
    assert "contact details" in forbidden
    assert "raw source code bodies from Struna" in forbidden
    assert flags["struna_repo_modified"] is False
    assert flags["raw_source_body_ingested"] is False
    assert flags["raw_legal_or_contact_data_stored"] is False
    assert flags["runtime_authority_added"] is False
    assert flags["send_or_submit_authority_added"] is False
    assert flags["approval_authority_added"] is False

def test_export_writes_json_and_operator_outputs(tmp_path, capsys):
    result = capsule.export_struna_obscura_project_capsule(repo_root=tmp_path, export_root="generated/read_models", generated_at=FIXED_NOW)
    json_path = tmp_path / "generated/read_models" / capsule.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated/read_models" / capsule.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert result.project_id == "struna_obscura"
    assert result.niles_resume_ready is True
    assert payload["receipt_proof_status"]["niles_can_resume_from_read_model"] is True
    assert "Struna Obscura Project Capsule v0" in operator
    assert "Business/legal terms are operator-reported evidence" in operator
    assert export_main(["--repo-root", str(tmp_path), "--export-root", "generated/read_models", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["project_id"] == "struna_obscura"

def test_source_does_not_import_forbidden_execution_or_mutation_apis():
    source = "\n".join(Path(path).read_text(encoding="utf-8").lower() for path in ["struna_obscura_project_capsule.py", "scripts/export_struna_obscura_project_capsule.py"])
    for token in ["subprocess", "os.system", "shutil.", "copy2", "rename(", "unlink(", "remove(", "rmtree", "import requests", "import httpx", "urllib.request", "import socket", "smtplib", "send_message", "shell=true", "eval("]:
        assert token not in source

def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("struna_obscura_project_capsule.py").read_text(encoding="utf-8"))
    write_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"]
    assert len(write_calls) == 2

def test_struna_repo_and_mission_control_app_are_not_referenced_for_mutation():
    source = Path("struna_obscura_project_capsule.py").read_text(encoding="utf-8")
    assert "OpenClaw Mission Controle" not in source
    assert "git -C" not in source
    assert "cargo build" not in source
    assert "xcodebuild" not in source
    assert "swift build" not in source
    assert "struna_repo_modified\": true" not in source
