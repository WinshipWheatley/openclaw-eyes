import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_clara_offline_worker_adapter as clara_adapter
from openclaw_lux_renderer import build_lux_renderer_prompt, render_packet, render_packet_result
from openclaw_terminology_adapter import translate_terms
from protected_generate import protected_generate_with_receipt
import repoa_worker_boundary_harness as harness


def test_terminology_adapter_is_json_backed_and_dual_labels_money(monkeypatch):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

    rendered = translate_terms(
        "SEND_HOLD BLOCKED_PENDING_APPROVAL amount $2,000.00",
        target_layer="maestro",
    )

    assert "Prepared for your review before dispatch" in rendered
    assert "Awaiting your approval before I move it" in rendered
    assert "Project investment: $2,000.00 / Total price: $2,000.00" in rendered


def test_renderer_fallback_keeps_severity_and_three_sections(monkeypatch):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

    rendered = render_packet(
        {
            "text": "FAILED_SEND for Capital Hilton on 2026-06-21. Recovery budget is $125.00.",
            "status": "FAILED_SEND",
        },
        target_agent="maestro",
    )

    assert rendered.startswith("Velvet:")
    assert "\nConcierge:" in rendered
    assert "\nSteel:" in rendered
    assert "FAILED_SEND" in rendered
    assert "2026-06-21" in rendered
    assert "Project investment: $125.00 / Total price: $125.00" in rendered


def test_renderer_passes_raw_packet_to_injected_llm(monkeypatch):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    calls = []

    def fake_llm(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return (
            "Velvet: SEND_HOLD is ready for review.\n"
            "Concierge: The client copy is restrained.\n"
            "Steel: $900.00 due on 2026-06-22."
        )

    result = render_packet_result(
        {"text": "Raw stage packet with SEND_HOLD and $900.00.", "packet_id": "fixture"},
        target_agent="clara",
        llm_fn=fake_llm,
    )

    assert result.llm_invoked is True
    assert result.fallback_used is False
    assert "Raw stage packet with SEND_HOLD and $900.00" in calls[0][0]
    assert calls[0][1]["task_class"] == "chief_user_reply"
    assert "Drafted and awaiting internal sign-off" in result.text
    assert "Project investment: $900.00 / Total price: $900.00" in result.text


def test_protected_generate_quiet_luxury_hook_is_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    packet = {
        "packet_id": "quiet-lux-fixture",
        "rendering": {"quiet_luxury": True},
        "facts": [
            {"label": "delivery", "value": "FAILED_SEND on 2026-06-21"},
            {"label": "budget", "value": "$125.00 recovery cap"},
        ],
    }

    outcome = protected_generate_with_receipt(
        "What is the delivery status?",
        context_packet=packet,
        allow_live_model=False,
        audit_log_path=tmp_path / "audit.jsonl",
    )

    assert outcome.status == "ANSWER_READY"
    assert outcome.text.startswith("Velvet:")
    assert "FAILED_SEND" in outcome.text
    assert outcome.receipt["quiet_luxury_render_applied"] is True
    assert outcome.receipt["quiet_luxury_llm_invoked"] is False


def test_clara_worker_can_use_central_renderer_when_requested(monkeypatch):
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    package_flow = harness.build_cassandra_clara_role_package(
        source_request_id="quiet_lux_clara_fixture",
        user_message="Draft a note to Hilton about the invoice package.",
        audience="external",
    )
    package = dict(package_flow["role_package"])
    package["quiet_luxury_render"] = True

    result = clara_adapter.run_cassandra_clara_offline_worker(package)

    assert result["selected_voice"] == "CLARA"
    assert result["draft_text"].startswith("Velvet:")
    assert "\nConcierge:" in result["draft_text"]
    assert "\nSteel:" in result["draft_text"]
    assert result["send_performed"] is False


def test_prompt_injects_doctrine_and_raw_packet():
    prompt = build_lux_renderer_prompt(
        {"text": "SECURITY_RISK and SEND_HOLD are both active."},
        target_agent="maestro",
    )

    assert "Velvet Over Steel" in prompt
    assert "Severity Integrity" in prompt
    assert "Raw packet:" in prompt
    assert "SECURITY_RISK and SEND_HOLD are both active" in prompt
