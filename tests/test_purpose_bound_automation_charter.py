import json
import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import purpose_bound_automation_charter as charter
from scripts.export_purpose_bound_automation_charter import main as export_main

FIXED_NOW = "2026-05-28T10:00:00+00:00"


def _build() -> dict:
    return charter.build_purpose_bound_automation_charter(generated_at=FIXED_NOW)


def test_contract_shape_and_charter_examples_present():
    payload = _build()

    assert payload["schema_version"] == charter.SCHEMA_VERSION
    assert payload["read_model_id"] == charter.READ_MODEL_ID
    assert payload["contract_status"] == charter.CONTRACT_STATUS
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["record_count"] == 6

    charter_refs = {row["charter_ref"] for row in payload["charter_rows"]}
    assert charter_refs == {
        "charter_gig_manager_v0",
        "charter_gig_outfit_laundry_v0",
        "charter_invoice_manager_v0",
        "charter_client_comms_clara_v0",
        "charter_phone_location_proof_v0",
        "charter_washer_dryer_integration_v0",
    }

    assert len(payload["charter_rows"]) == 6
    assert len(payload["charters_by_module"]) == 6
    assert payload["machine_proof"]["default_on_present"] is True



def test_required_charter_fields_and_module_access_rules():
    payload = _build()

    required_fields = set(charter.REQUIRED_CHARTER_FIELDS)
    for row in payload["charter_rows"]:
        assert required_fields <= row.keys(), row["charter_ref"]
        assert isinstance(row["risk_level"], str)
        assert isinstance(row["access_class_allowed"], tuple)
        assert row["proof_receipts"]

    assert "WINSHIP_DEVELOPER" in payload["access_classes"]
    assert "CUSTOMER_ADMIN" in payload["access_classes"]
    assert len(payload["charters_by_module"]) == len(payload["charter_rows"])

    # Washer integration is a default-off workflow module.
    washer = next(
        row for row in payload["charter_rows"] if row["module_ref"] == "washer_dryer_integration"
    )
    assert washer["default_enabled"] is False


def test_exported_artifacts_parse_and_contain_no_raw_secrets(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    exit_code = export_main(["--export-root", str(export_root), "--format", "summary"])
    assert exit_code == 0

    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator_text = operator_path.read_text(encoding="utf-8")

    assert json_path.exists()
    assert operator_path.exists()
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["read_model_id"] == charter.READ_MODEL_ID

    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_text
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "BEGIN PRIVATE" not in combined


def test_source_has_no_live_authority_imports():
    source = Path("purpose_bound_automation_charter.py").read_text(encoding="utf-8").lower()
    forbidden = (
        "requests.",
        "subprocess.",
        "socket.",
        "os.system",
        "playwright",
        "selenium",
        "smtplib",
    )
    for token in forbidden:
        assert token not in source
