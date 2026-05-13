import json

from scripts.build_source_cards import build_source_cards
from scripts.build_source_inventory import build_inventory
from scripts.build_working_context_packets import build_working_context_packets
from scripts.check_runtime_activation_gate import (
    ACTIVATION_GATE_VERSION,
    REQUIRED_PREREQUISITES,
    build_activation_gate_report,
    format_operator_activation_gate,
    main,
)
from scripts.extract_accepted_sources import build_extraction_artifact
from scripts.promote_accepted_context import build_promotion_manifest, write_json_artifact


def _packets_artifact(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text(
        "# Activation Gate Fixture\n\n- Readiness fact\n",
        encoding="utf-8",
    )
    inventory = build_inventory(
        root=tmp_path,
        allowlist=("docs/allowed.md",),
        include_blocked_examples=False,
    )
    promotion = build_promotion_manifest(
        inventory,
        requested_paths=("docs/allowed.md",),
        reason_for_promotion="activation gate context",
    )
    extraction = build_extraction_artifact(promotion)
    cards = build_source_cards(extraction)
    return build_working_context_packets(cards)


def test_v0_always_blocks_activation(tmp_path):
    report = build_activation_gate_report(_packets_artifact(tmp_path))

    assert report["artifact_version"] == ACTIVATION_GATE_VERSION
    assert report["gate_state"] == "blocked_v0_contract"
    assert report["activation_allowed"] is False
    assert report["runtime_authority"] is False
    assert report["module_activation_authority"] is False


def test_required_prerequisites_are_listed():
    report = build_activation_gate_report()

    assert report["missing_prerequisites"] == REQUIRED_PREREQUISITES
    for prerequisite in [
        "explicit_operator_approval",
        "rollback_plan",
        "module_manifest_validation",
        "runtime_boundary_declaration",
        "logging_receipt_path",
        "dry_run_proof",
    ]:
        assert prerequisite in report["missing_prerequisites"]


def test_no_runtime_side_effects_or_sqlite_touch(tmp_path):
    report = build_activation_gate_report(_packets_artifact(tmp_path))

    assert report["scope"]["agent_activation"] is False
    assert report["scope"]["broker_wiring"] is False
    assert report["scope"]["module_activation"] is False
    assert report["scope"]["customer_deployment"] is False
    assert report["scope"]["external_tools"] is False
    assert report["scope"]["runtime_mutation"] is False
    assert report["scope"]["runtime_health_check"] is False
    assert report["scope"]["sqlite_touched"] is False


def test_no_live_health_claims(tmp_path):
    report = build_activation_gate_report(_packets_artifact(tmp_path))
    output = format_operator_activation_gate(report).lower()

    assert report["live_runtime_health_claimed"] is False
    for forbidden in [
        "runtime ready",
        "runtime-ready",
        "runtime healthy",
        "modules active",
        "agent wired",
        "broker connected",
        "customer deployment active",
    ]:
        assert forbidden not in output


def test_operator_output_uses_gate_grammar(tmp_path):
    output = format_operator_activation_gate(
        build_activation_gate_report(_packets_artifact(tmp_path))
    )

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "activation_allowed=false" in output
    assert "`runtime_authority=false`" in output
    assert "v0 always blocks runtime/module activation" in output
    assert "external tools" in output
    assert '"gate_state"' not in output


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    packets_path = tmp_path / "packets.json"
    write_json_artifact(_packets_artifact(tmp_path), packets_path)

    exit_code = main(["--packets", str(packets_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_version"] == ACTIVATION_GATE_VERSION
    assert payload["activation_allowed"] is False
    assert payload["evidence"]["accepted_packets"] == 1
