import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import safe_preview_provider as provider
from scripts.export_safe_preview_provider import main as export_main


FIXED_NOW = "2026-05-27T12:00:00+00:00"


def _payload(tools=None):
    return provider.build_payload(generated_at=FIXED_NOW, detected_tools=tools or {})


def test_provider_types_are_declared():
    payload = _payload()

    assert payload["provider_types"] == provider.PROVIDER_TYPES
    assert {"NONE", "QUICKLOOK_MAC_CLIENT", "DANGERZONE_BACKEND", "LIBREOFFICE_SANDBOXED", "ONLYOFFICE_SERVER"} <= set(
        payload["provider_types"]
    )


def test_quicklook_is_recommended_for_current_invoice_review():
    payload = _payload({"docker": True})

    assert payload["current_invoice_review_recommendation"]["provider_type"] == "QUICKLOOK_MAC_CLIENT"
    assert payload["current_invoice_review_recommendation"]["backend_preview_generation_needed_now"] is False
    assert payload["machine_proof"]["quicklook_recommended_for_current_invoice"] is True


def test_dangerzone_future_provider_is_pending_when_not_installed():
    payload = _payload({"docker": True, "dangerzone": False, "dangerzone-cli": False})

    dangerzone = next(item for item in payload["provider_readiness"] if item["provider_type"] == "DANGERZONE_BACKEND")
    assert dangerzone["provider_available"] is False
    assert dangerzone["install_required"] is True
    assert dangerzone["production_ready"] is False
    assert payload["future_untrusted_docs_recommendation"]["provider_type"] == "DANGERZONE_BACKEND_PENDING_REVIEW"


def test_dangerzone_can_be_shadow_ready_when_command_and_docker_exist():
    payload = _payload({"docker": True, "dangerzone": True, "dangerzone-cli": False})

    dangerzone = next(item for item in payload["provider_readiness"] if item["provider_type"] == "DANGERZONE_BACKEND")
    assert dangerzone["provider_available"] is True
    assert dangerzone["safe_for_untrusted_docs"] is True
    assert dangerzone["production_ready"] is False
    assert payload["future_untrusted_docs_recommendation"]["provider_type"] == "DANGERZONE_BACKEND"


def test_libreoffice_is_not_marked_safe_for_untrusted_docs():
    payload = _payload({"libreoffice": True, "soffice": False})

    libreoffice = next(item for item in payload["provider_readiness"] if item["provider_type"] == "LIBREOFFICE_SANDBOXED")
    assert libreoffice["provider_available"] is True
    assert libreoffice["sandbox_required"] is True
    assert libreoffice["safe_for_untrusted_docs"] is False
    assert libreoffice["production_ready"] is False


def test_onlyoffice_is_too_heavy_for_v0():
    payload = _payload()

    onlyoffice = next(item for item in payload["provider_readiness"] if item["provider_type"] == "ONLYOFFICE_SERVER")
    assert onlyoffice["provider_available"] is False
    assert onlyoffice["install_required"] is True
    assert onlyoffice["production_ready"] is False
    assert payload["machine_proof"]["onlyoffice_not_recommended_for_v0"] is True


def test_no_conversion_or_service_authority_is_enabled():
    payload = _payload()

    assert payload["prototype"]["attempted"] is False
    assert payload["prototype"]["real_invoice_artifacts_touched"] is False
    assert payload["machine_proof"]["no_document_conversion_performed"] is True
    assert payload["machine_proof"]["all_action_authority_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())


def test_export_writes_parseable_json_and_operator_summary(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / provider.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / provider.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == provider.READ_MODEL_ID
    assert summary["current_invoice_provider"] == "QUICKLOOK_MAC_CLIENT"
    assert payload["machine_proof"]["provider_contract_present"] is True
    assert "No document conversion" in operator


def test_export_contains_no_secret_or_action_enablement(tmp_path):
    payload = _payload()
    provider.write_exports(payload, tmp_path)
    combined = (tmp_path / provider.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / provider.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert "api_key" not in lowered
    assert "password" not in lowered
    assert "secret" not in lowered
    assert '"document_conversion_performed": true' not in lowered
    assert '"network_server_started": true' not in lowered
