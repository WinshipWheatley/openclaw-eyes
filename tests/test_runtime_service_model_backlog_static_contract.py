from pathlib import Path

import pytest

import chief_llm


ROOT = Path(__file__).resolve().parents[1]
SERVICE_FREEZE = ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
MODEL_FALLBACK_POLICY = ROOT / "docs" / "operations" / "OPENCLAW_MODEL_FALLBACK_POLICY.md"
INTENT_CONTROL_MAP = ROOT / "docs" / "operations" / "OPENCLAW_INTENT_AND_CONTROL_MAP.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_service_management_freeze_is_runtime_neutral_and_ordered():
    text = _read(SERVICE_FREEZE)

    assert "Runtime-neutral documentation freeze only" in text
    assert "It does not start, stop, restart, reload, enable, disable, install, remove" in text
    assert "It also does not authorize new runtime behavior" in text
    assert "Do not expand any of these controls under this freeze" in text
    assert "Any future service operation" in text

    slice_markers = [
        "Slice 2: add read-only service inventory/audit check.",
        "Slice 3: harden install script behavior behind dry-run/explicit flags.",
        "Slice 4: deprecate or guard legacy launch scripts.",
        "Slice 5: reconcile Hermes template vs installed unit through the narrow Hermes-only installer.",
        "Slice 6: record owner classification for `openclaw-gateway` and drift-control; no repo templates are added without enough source evidence.",
        "Slice 7: record static drift-control scheduler-owner classification without selecting an owner.",
        "Slice 8: record static legacy polling/loop supervisor ownership disposition.",
    ]
    positions = [text.index(marker) for marker in slice_markers]

    assert positions == sorted(positions)


def test_model_fallback_policy_keeps_external_and_claude_paths_blocked_by_default():
    text = _read(MODEL_FALLBACK_POLICY)

    assert "No silent external fallback" in text
    assert "Claude CLI, Claude Code, and Claude models are human-only" in text
    assert "Automation paths fail closed instead of invoking Claude" in text
    assert "Sensitive/professional packets fail closed for external/cloud by default" in text
    assert "Future external model use for protected or professional packets requires a separate sanitizer/export gate" in text


def test_intent_map_does_not_authorize_runtime_or_delivery_expansion():
    text = _read(INTENT_CONTROL_MAP)

    forbidden_expansion_clause = (
        "This section does not authorize live provider execution, service/timer wiring, "
        "scheduler changes, Hermes runtime expansion, Gmail/Telegram actions, Legal matter access, or `.mcp.json` changes."
    )
    assert forbidden_expansion_clause in text
    assert "Runtime/provider/service/timer wiring remains stopped until separately approved." in text
    assert "Repo source, shared vaults, logs, Legal private paths, Hermes runtime state" in text
    assert "providers, messaging, terminal/process tools, write tools" in text


@pytest.mark.parametrize(
    ("packet", "metadata", "expected_reason"),
    [
        (
            "Summarize this synthetic public fixture.",
            {"data_classification": "synthetic_public"},
            "cloud_not_explicitly_allowed",
        ),
        (
            "Review this Gmail body excerpt.",
            {"data_classification": "synthetic_public", "cloud_allowed": "true"},
            "blocked_marker:gmail body",
        ),
        (
            "Review public fixture near /mnt/c/OpenClawLegalPrivate/demo.",
            {"data_classification": "synthetic_public", "cloud_allowed": "true"},
            "blocked_marker:/mnt/c/openclawlegalprivate",
        ),
        (
            "Summarize this synthetic public fixture.",
            {"data_classification": "private", "cloud_allowed": "true"},
            "blocked_classification:private",
        ),
    ],
)
def test_external_model_policy_fails_closed_for_unapproved_or_protected_packets(packet, metadata, expected_reason):
    policy = chief_llm.external_model_packet_policy(packet, metadata=metadata)

    assert policy["external_model_safe"] is False
    assert policy["blocked"] is True
    assert policy["reason"] == expected_reason


def test_external_model_policy_allows_only_explicit_synthetic_public_packet():
    policy = chief_llm.external_model_packet_policy(
        "Summarize this synthetic public fixture.",
        metadata={"data_classification": "synthetic_public", "cloud_allowed": "true"},
    )

    assert policy == {
        "external_model_safe": True,
        "blocked": False,
        "sensitive": False,
        "cloud_allowed": True,
        "classification": "synthetic_public",
        "reason": "explicit_cloud_allowed_public_or_synthetic",
    }


def test_claude_helpers_fail_closed_without_subprocess_or_network(monkeypatch):
    monkeypatch.setattr(chief_llm.subprocess, "run", lambda *args, **kwargs: pytest.fail("subprocess must not run"))
    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("network must not run"))

    assert chief_llm.claude_call("Synthetic public fixture prompt.") == ""
    assert chief_llm.claude_json("Synthetic public fixture prompt.") == {}
