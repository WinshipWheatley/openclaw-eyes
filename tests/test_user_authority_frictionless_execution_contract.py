import json
from pathlib import Path

import user_authority_frictionless_execution_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_user_authority_frictionless_execution_contract import main as export_main


FIXED_NOW = "2026-06-18T22:02:00+00:00"


def _write(path: Path, payload: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write(root / "OPENCLAW_RUNTIME.md", "# Runtime\n")
    _write(root / "USER.md", "# Winship\n")
    _write(root / "operator_action_covenant.py", '"""fixture"""\n')
    _write(
        root / "generated/read_models/agent_identity_actor_router_contract.json",
        {"schema_version": "agent_identity_actor_router_contract_v0"},
    )
    _write(
        root / "generated/read_models/protected_evidence_reference_receipt.json",
        {"schema_version": "protected_evidence_reference_receipt_v0"},
    )


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_user_authority_frictionless_execution_contract(
        repo_root=tmp_path,
        generated_at=FIXED_NOW,
    )


def test_contract_is_deterministic_metadata_only_and_preserves_operator_authority(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "user_authority_frictionless_execution_contract"
    assert first["contract_status"] == "deterministic_user_authority_and_frictionless_execution_metadata_only"
    assert first["contract_only"] is True
    assert first["execution_authority_added"] is False
    assert first["approval_authority_added"] is False
    assert first["operator_authority_transferred"] is False
    assert first["operator_final_authority_preserved"] is True


def test_safe_local_work_can_be_frictionless_but_still_needs_proof():
    decision = contract.decide_frictionless_execution("bounded_branch_edit")
    no_branch = contract.decide_frictionless_execution("bounded_branch_edit", branch_scoped=False)

    assert decision["decision"] == "ALLOW_FRICTIONLESS_LOCAL"
    assert decision["may_proceed_without_extra_operator_prompt"] is True
    assert decision["execution_authority_granted_by_contract"] is False
    assert "claim_marker" in next(
        rail for rail in contract.build_user_authority_frictionless_execution_contract()["authority_rails"]
        if rail["rail_id"] == "frictionless_repo_local_work"
    )["required_proof"]
    assert no_branch["decision"] == "BLOCKED_UNTIL_BOUNDARY_FIXED"
    assert "branch_or_worktree_scope_required" in no_branch["blocking_reasons"]


def test_full_go_does_not_override_hard_stop_rails(tmp_path):
    payload = _build(tmp_path)
    rails = payload["hard_stop_rails_preserved"]

    assert rails["SEND_HOLD_absolute"] is True
    assert rails["no_real_external_send"] is True
    assert rails["no_money"] is True
    assert rails["no_prod_restart_or_deploy"] is True
    assert rails["legal_discovery_off_limits"] is True
    assert rails["no_secret_values_printed"] is True
    assert rails["no_merge_to_master"] is True
    assert rails["no_force_push"] is True

    send = contract.decide_frictionless_execution("real_external_send", send_hold_present=True)
    money = contract.decide_frictionless_execution("money_movement", operator_final_approval_present=True)
    legal = contract.decide_frictionless_execution("legal_discovery")
    secret = contract.decide_frictionless_execution("secret_value_print_or_edit", secret_values_requested=True)

    assert send["decision"] == "BLOCKED"
    assert "SEND_HOLD_blocks_real_external_send" in send["blocking_reasons"]
    assert money["decision"] == "BLOCKED"
    assert money["execution_authority_granted_by_contract"] is False
    assert legal["blocking_reasons"] == ["operator_final_authority_required", "legal_discovery_off_limits"]
    assert "secret_values_must_not_be_printed" in secret["blocking_reasons"]


def test_unknown_action_fails_closed():
    decision = contract.decide_frictionless_execution("launch_unscoped_tool_swarm")

    assert decision["decision"] == "UNKNOWN_FAIL_CLOSED"
    assert decision["may_proceed_without_extra_operator_prompt"] is False
    assert decision["blocking_reasons"] == ["unknown_action_kind"]


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
    assert summary["authority_rail_count"] >= 7
    assert summary["execution_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert payload["read_model_id"] == "user_authority_frictionless_execution_contract"
    assert "User Authority + Frictionless Execution Contract v0" in operator
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_live_execution_or_account_access():
    text = Path("user_authority_frictionless_execution_contract.py").read_text(encoding="utf-8").lower()
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
        "import google_access_broker",
        "from google_access_broker",
        ".unlink(",
        "shutil.rmtree",
        "git push",
    ]:
        assert token not in text
