import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as adapter


FIXED_NOW = "2026-06-07T12:00:00+00:00"


def _bundle():
    return runtime.build_or_load_proof_bundle("finance_capital_hilton_payment_watch")


def _valid_draft(**overrides):
    payload = {
        "headline": "Payment evidence needed",
        "body": "Coupa is processing. I cannot mark this paid until payment evidence is attached. The ledger stays untouched.",
        "next_step": "Attach payment evidence.",
        "missing_input": ["payment_evidence"],
        "can_do_now": ["Hold payment watch", "Ask for proof"],
        "cannot_do_yet": ["paid marking", "ledger mutation", "Coupa/browser action"],
        "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
        "requested_controls": ["Attach payment evidence"],
        "uncertainty_notes": [],
    }
    payload.update(overrides)
    return payload


def _adapt(payload, **kwargs):
    return adapter.adapt_model_draft(
        json.dumps(payload),
        proof_bundle=_bundle(),
        generated_at=FIXED_NOW,
        **kwargs,
    )


def _unsafe_true_grants(value, path="$"):
    unsafe = set(adapter.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
    found = []
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


def test_valid_json_candidate_adapts_successfully():
    result = _adapt(_valid_draft())

    assert result["parse_status"] == adapter.PARSE_STATUS_PARSED
    assert result["adapter_errors"] == []
    assert result["verifier_ready"] is True
    candidate = result["adapted_candidate"]
    assert candidate["draft_headline"] == "Payment evidence needed"
    assert candidate["draft_next_step"] == "Attach payment evidence."
    assert candidate["claimed_facts"] == ["payment_evidence_missing", "coupa_processing", "ledger_untouched"]
    assert candidate["implied_actions"] == []
    assert candidate["can_do_now"] == ["Hold payment watch", "Ask for proof"]
    assert candidate["cannot_do_yet"] == ["paid marking", "ledger mutation", "Coupa/browser action"]
    assert result["verifier_result"]["publishable"] is True
    assert not _unsafe_true_grants(result)


def test_non_json_model_text_fails_with_parse_error():
    result = adapter.adapt_model_draft(
        "Payment evidence is missing. Attach proof.",
        proof_bundle=_bundle(),
        generated_at=FIXED_NOW,
    )

    assert result["parse_status"] == adapter.PARSE_STATUS_PARSE_ERROR
    assert result["adapted_candidate"] == {}
    assert result["verifier_ready"] is False
    assert any(error.startswith("json_parse_error") for error in result["adapter_errors"])


def test_markdown_code_fence_response_is_rejected():
    wrapped = "```json\n" + json.dumps(_valid_draft()) + "\n```"
    result = adapter.adapt_model_draft(wrapped, proof_bundle=_bundle(), generated_at=FIXED_NOW)

    assert result["parse_status"] == adapter.PARSE_STATUS_PARSE_ERROR
    assert "markdown_wrapped_json_rejected" in result["adapter_errors"]
    assert result["verifier_ready"] is False


def test_missing_required_fields_fail():
    payload = _valid_draft()
    payload.pop("next_step")
    result = _adapt(payload)

    assert result["parse_status"] == adapter.PARSE_STATUS_SCHEMA_ERROR
    assert "missing_field:next_step" in result["adapter_errors"]
    assert result["adapted_candidate"] == {}
    assert result["verifier_ready"] is False


def test_empty_list_fields_are_normalized():
    payload = _valid_draft(missing_input="", can_do_now=None, cannot_do_yet=[], uncertainty_notes=None)
    result = _adapt(payload)

    assert result["parse_status"] == adapter.PARSE_STATUS_PARSED
    assert result["adapted_candidate"]["missing_input"] == []
    assert result["adapted_candidate"]["can_do_now"] == []
    assert result["adapted_candidate"]["cannot_do_yet"] == []
    assert result["adapted_candidate"]["uncertainty_notes"] == []


def test_candidate_claiming_paid_fails_later_verifier_compatibility():
    payload = _valid_draft(
        body="Coupa is processing and the invoice is paid. The ledger stays untouched.",
        claimed_facts=["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
    )
    result = _adapt(payload)

    assert result["parse_status"] == adapter.PARSE_STATUS_PARSED
    assert result["adapted_candidate"]
    assert result["verifier_ready"] is False
    assert any("unsupported_completion_claim" in error for error in result["verifier_failure_reasons"])


def test_prompt_template_includes_json_only_and_proof_only_instructions():
    template = adapter.model_instruction_template()
    lowered = template.lower()

    assert "return json only" in lowered
    assert "no markdown" in lowered
    assert "no prose outside json" in lowered
    assert "no code fences" in lowered
    assert "use only the provided proof bundle" in lowered
    assert "do not claim paid/sent/submitted/executed unless proof says so" in lowered
    assert "do not promise protected actions" in lowered
    assert "do not ask for hidden context" in lowered
    assert "keep response concise" in lowered


def test_contract_contains_valid_capital_hilton_example_and_schema(tmp_path):
    contract = adapter.build_contract_read_model(generated_at=FIXED_NOW)

    assert contract["status"] == adapter.READY_STATUS
    assert contract["strict_json_draft_schema"]["required"] == list(adapter.STRICT_DRAFT_FIELDS)
    example = contract["valid_examples"][0]
    assert example["scenario_id"] == "finance_capital_hilton_payment_watch"
    assert example["draft"]["next_step"] == "Attach payment evidence."
    assert "Coupa is processing" in example["draft"]["body"]
    assert "ledger" in example["draft"]["body"].lower()
    assert example["adapted_result"]["verifier_ready"] is True
    assert not _unsafe_true_grants(contract)


def test_adapter_does_not_grant_authority():
    result = _adapt(_valid_draft())

    assert result["authority_boundary"]["email_send_allowed"] is False
    assert result["authority_boundary"]["ledger_mutation_allowed"] is False
    assert result["authority_boundary"]["coupa_allowed"] is False
    assert result["authority_boundary"]["paid_marking_allowed"] is False
    assert result["machine_proof"]["model_invocation_performed"] is False
    assert result["machine_proof"]["external_llm_invoked"] is False
    assert result["machine_proof"]["local_model_runtime_connected"] is False
    assert not _unsafe_true_grants(result)


def test_export_json_bridge_equality_and_unsafe_scan(tmp_path):
    result = adapter.export_schema_adapter(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Proof To Response Schema Adapter.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == adapter.READY_STATUS
    for local_key, bridge_key in [("contract_path", "bridge_contract_path"), ("status_path", "bridge_status_path")]:
        local = json.loads(Path(result[local_key]).read_text(encoding="utf-8"))
        bridge = json.loads(Path(result[bridge_key]).read_text(encoding="utf-8"))
        assert local == bridge
        assert not _unsafe_true_grants(local)
    assert Path(result["wiki_path"]).exists()
