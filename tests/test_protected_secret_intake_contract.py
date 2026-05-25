import json
import re
from pathlib import Path

import protected_secret_intake_contract as protected
from scripts.export_protected_secret_intake_contract import main as export_main


FIXED_NOW = "2026-05-25T12:00:00+00:00"


def _build() -> dict:
    return protected.build_protected_secret_intake_contract(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert protected.stable_json(first) == protected.stable_json(second)
    assert first["schema_version"] == protected.SCHEMA_VERSION
    assert first["read_model_id"] == protected.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["protected_secret_intake_contract_model_present"] is True
    assert proof["protected_secret_intake_request_model_present"] is True
    assert proof["protected_secret_token_model_present"] is True
    assert proof["secret_use_policy_model_present"] is True
    assert proof["protected_secret_receipt_model_present"] is True
    assert proof["protected_secret_blocker_model_present"] is True
    assert proof["protected_secret_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["protected_secret_intake_contract"]["required_fields"] == list(protected.REQUIRED_CONTRACT_FIELDS)
    assert schemas["protected_secret_intake_request"]["required_fields"] == list(protected.REQUIRED_REQUEST_FIELDS)
    assert schemas["protected_secret_token"]["required_fields"] == list(protected.REQUIRED_TOKEN_FIELDS)
    assert schemas["secret_use_policy"]["required_fields"] == list(protected.REQUIRED_USE_POLICY_FIELDS)
    assert schemas["protected_secret_receipt"]["required_fields"] == list(protected.REQUIRED_RECEIPT_FIELDS)
    assert schemas["protected_secret_blocker"]["required_fields"] == list(protected.REQUIRED_BLOCKER_FIELDS)
    assert schemas["protected_secret_elioperator_report"]["required_fields"] == list(protected.REQUIRED_REPORT_FIELDS)


def test_secret_modes_and_kinds_exist():
    payload = _build()

    assert payload["machine_proof"]["all_secret_modes_exist"] is True
    assert payload["machine_proof"]["secret_kinds_exist"] is True
    for mode in ["USE_ONCE", "STORE_PROTECTED", "SESSION_TTL", "TASK_SCOPED", "NEVER_STORE"]:
        assert mode in payload["supported_secret_modes"]
    for kind in [
        "PASSWORD",
        "API_KEY",
        "OAUTH_TOKEN",
        "SESSION_COOKIE",
        "SSH_KEY",
        "BANKING_OR_PAYMENT_SECRET",
        "COUPA_CREDENTIAL",
        "EMAIL_ACCOUNT_SECRET",
        "APP_SPECIFIC_PASSWORD",
        "UNKNOWN_SECRET_FAIL_CLOSED",
    ]:
        assert kind in payload["secret_kinds"]


def test_contract_privacy_boundary_forbids_raw_secret_surfaces():
    payload = _build()
    contract = payload["protected_secret_intake_contract"]
    boundary = "\n".join(contract["privacy_boundary"])

    assert "Raw secret never appears in normal read-models." in boundary
    assert "Raw secret never appears in chat transcript." in boundary
    assert "Raw secret never appears in LLM/model context." in boundary
    assert "Raw secret never appears in generated operator markdown." in boundary
    assert "Raw secret never appears in logs/tests/fixtures." in boundary
    assert "Agents see refs, not values." in boundary


def test_use_once_coupa_example_tokenizes_ref_and_does_not_login():
    payload = _build()
    example = payload["examples"]["use_once_coupa_login_later"]
    request = example["intake_request"]
    token = example["protected_secret_token"]
    policy = example["secret_use_policy"]
    receipt = example["protected_secret_receipt"]

    assert request["secret_mode"] == "USE_ONCE"
    assert request["secret_kind"] == "COUPA_CREDENTIAL"
    assert request["raw_secret_allowed_in_request"] is False
    assert request["raw_secret_allowed_in_read_model"] is False
    assert request["raw_secret_allowed_in_llm_context"] is False
    assert token["token_ref"].startswith("secret_ref:")
    assert token["reveal_allowed"] is False
    assert token["adapter_use_required"] is True
    assert token["guardian_review_required"] is True
    assert policy["one_time_use"] is True
    assert policy["raw_value_reveal_forbidden"] is True
    assert receipt["raw_secret_logged"] is False
    assert receipt["raw_secret_sent_to_llm"] is False
    assert example["agent_visible_context"]["raw_value_visible"] is False
    assert example["login_performed"] is False


def test_store_protected_api_key_example_requires_future_adapter():
    payload = _build()
    example = payload["examples"]["store_protected_api_key"]

    assert example["intake_request"]["secret_mode"] == "STORE_PROTECTED"
    assert example["protected_secret_token"]["secret_kind"] == "API_KEY"
    assert example["raw_key_visible"] is False
    assert example["future_adapter_required"] is True
    assert example["protected_secret_receipt"]["raw_secret_stored"] is False
    assert tuple(example["secret_use_policy"]["allowed_adapter_refs"]) == ("future_named_adapter",)


def test_session_ttl_example_requires_expiry_and_blocks_after_expiry():
    payload = _build()
    example = payload["examples"]["session_ttl_secret"]
    token = example["protected_secret_token"]

    assert example["intake_request"]["secret_mode"] == "SESSION_TTL"
    assert token["ttl_seconds"] == 900
    assert example["secret_use_policy"]["ttl_required"] is True
    assert example["protected_secret_receipt"]["action"] == "TOKEN_EXPIRED"
    assert example["use_after_expiry_allowed"] is False
    assert payload["machine_proof"]["ttl_requirement_exists"] is True


def test_raw_chat_and_llm_exposure_examples_are_blocked():
    payload = _build()
    chat = payload["examples"]["block_raw_secret_in_chat"]
    llm = payload["examples"]["block_raw_secret_in_llm_context"]

    assert chat["blocker_type"] == "RAW_SECRET_IN_CHAT"
    assert chat["raw_value_recorded"] is False
    assert chat["fail_closed"] is True
    assert llm["blocker_type"] == "RAW_SECRET_IN_LLM_CONTEXT"
    assert llm["raw_value_included"] is False
    assert llm["fail_closed"] is True
    assert payload["machine_proof"]["llm_exposure_blocker_exists"] is True


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["protected_secret_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["raw_secret_blockers_exist"] is True
    for blocker_type in protected.BLOCKER_TYPES:
        assert blocker_type in blocker_types
    assert blockers["protected_secret_blocker_raw_secret_in_chat"]["fail_closed"] is True
    assert blockers["protected_secret_blocker_unknown_secret_fail_closed"]["severity"] == "CRITICAL"


def test_agents_see_refs_only_and_scope_requirements_exist():
    payload = _build()

    assert payload["machine_proof"]["agents_see_token_refs_only"] is True
    assert payload["machine_proof"]["scope_requirement_exists"] is True
    for example in payload["examples"].values():
        if "protected_secret_token" not in example:
            continue
        token = example["protected_secret_token"]
        assert token["token_ref"].startswith("secret_ref:")
        assert token["allowed_scope"]
        assert token["reveal_allowed"] is False


def test_receipts_never_log_send_or_expose_raw_secret():
    payload = _build()
    for example in payload["examples"].values():
        receipt = example.get("protected_secret_receipt")
        if not receipt:
            continue
        assert receipt["raw_secret_logged"] is False
        assert receipt["raw_secret_sent_to_llm"] is False
        assert receipt["raw_secret_sent_external"] is False
        assert receipt["external_authority"] is False


def test_all_live_authority_false():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["live_secret_capture_performed"] is False
    assert payload["machine_proof"]["live_secret_store_performed"] is False
    assert payload["machine_proof"]["live_adapter_use_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["all_secret_modes_exist"] is True
    assert summary["secret_kinds_exist"] is True
    assert summary["agents_see_token_refs_only"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_generated_outputs_have_no_real_secret_like_values(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_real_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", combined)
    assert not re.search(r"(?i)\b(api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", combined)
    assert "BEGIN " not in combined
    assert "raw value:" not in combined.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "protected_secret_intake_contract.py",
            "scripts/export_protected_secret_intake_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
