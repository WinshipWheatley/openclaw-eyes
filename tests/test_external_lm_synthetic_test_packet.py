import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_synthetic_test_packet as packet

FIXED_NOW = "2026-06-07T14:00:00+00:00"


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out = []
        for child in value.values():
            out.extend(_strings(child))
        return out
    if isinstance(value, list):
        out = []
        for child in value:
            out.extend(_strings(child))
        return out
    return []


def _unsafe_true_grants(value, path="$"):
    found = []
    unsafe = set(packet.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_packet_is_ready_and_uses_only_synthetic_proof_bundle():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)

    assert model["status"] == packet.READY_STATUS
    bundle = model["copy_paste_packet"]["synthetic_proof_bundle"]
    assert bundle["bundle_kind"] == "synthetic_redacted_test_only"
    assert bundle["scenario_id"] == "synthetic_finance_capital_hilton_shaped_payment_watch"
    assert bundle["privacy_class"] == "synthetic_only_no_private_proof"
    assert bundle["real_client_data_present"] is False
    assert bundle["private_proof_present"] is False
    assert bundle["raw_ocr_or_artifact_text_present"] is False
    assert bundle["paid"] is False
    assert bundle["ledger_untouched"] is True
    assert not _unsafe_true_grants(model)


def test_packet_contains_no_private_proof_paths_credentials_or_account_details():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    combined = "\n".join(_strings(model["copy_paste_packet"])).lower()

    forbidden_fragments = [
        "/home/",
        "/mnt/",
        "generated/read_models",
        "e:\\",
        "c:\\",
        "api_key",
        "secret:",
        "credential:",
        "password:",
        "account number",
        "routing number",
        "bank account",
        "raw ocr",
        "artifact text",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in combined
    assert "do not paste private proof" in combined


def test_json_only_response_schema_matches_adapter_contract():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    schema = model["copy_paste_packet"]["json_only_response_schema"]

    assert schema["required"] == list(packet.STRICT_RESPONSE_FIELDS)
    assert schema["additionalProperties"] is False
    for field in packet.STRICT_RESPONSE_FIELDS:
        assert field in schema["properties"]


def test_copy_paste_prompt_includes_required_external_lm_instructions():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    prompt = model["copy_paste_packet"]["copy_paste_prompt"]
    lowered = prompt.lower()

    assert "return json only" in lowered
    assert "no markdown" in lowered
    assert "no code fences" in lowered
    assert "use only the synthetic proof bundle" in lowered
    assert "do not paste private proof" in lowered
    assert "do not claim paid" in lowered
    assert "do not claim submitted" in lowered
    assert "do not promise send" in lowered
    assert "do not promise ledger" in lowered


def test_synthetic_scenario_and_expected_response_are_payment_watch_only():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    scenario = model["copy_paste_packet"]["synthetic_proof_bundle"]
    expected = model["expected_response"]

    assert scenario["world_ref"] == "finance"
    assert scenario["scenario_shape"] == "capital_hilton_payment_watch"
    assert scenario["payment_evidence_status"] == "missing"
    assert scenario["payment_processor_status"] == "processing"
    assert scenario["paid"] is False
    assert expected["headline"] == "Payment evidence needed"
    assert expected["next_step"] == "Attach payment evidence."
    assert "paid" in " ".join(expected["must_not_claim"]).lower()
    assert "ledger" in " ".join(expected["must_not_claim"]).lower()


def test_expected_verifier_checks_include_protected_claim_blocks():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    checks = model["expected_verifier_checks"]
    joined = "\n".join(checks).lower()

    assert "json only" in joined
    assert "claimed facts" in joined
    assert "paid" in joined
    assert "sent" in joined
    assert "submitted" in joined
    assert "ledger" in joined
    assert "protected action" in joined
    assert "concise" in joined


def test_manual_instructions_are_test_only_and_no_send():
    model = packet.build_packet_read_model(generated_at=FIXED_NOW)
    instructions = model["manual_test_instructions"]
    joined = "\n".join(instructions).lower()

    assert "copy/paste" in joined
    assert "do not paste private proof" in joined
    assert "do not call api" in joined
    assert "do not send" in joined
    assert "do not use secrets" in joined
    assert "paste the returned json back" in joined


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = packet.export_packet(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "External LM Synthetic Test Packet.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == packet.READY_STATUS
    local = json.loads(Path(result["packet_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_packet_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert not _unsafe_true_grants(local)
    assert Path(result["wiki_path"]).exists()
