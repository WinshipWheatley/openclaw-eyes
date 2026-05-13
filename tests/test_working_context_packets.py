import json

from scripts.build_source_cards import build_source_cards
from scripts.build_source_inventory import build_inventory
from scripts.build_working_context_packets import (
    PACKETS_ARTIFACT_VERSION,
    build_working_context_packets,
    format_operator_packets,
    main,
)
from scripts.extract_accepted_sources import build_extraction_artifact
from scripts.promote_accepted_context import build_promotion_manifest, write_json_artifact


def _source_cards_artifact(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text(
        "# Packet Fixture\n\n- Bounded context fact\n",
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
        reason_for_promotion="compile accepted working packets",
    )
    extraction = build_extraction_artifact(promotion)
    return build_source_cards(extraction)


def test_packet_includes_only_accepted_cards(tmp_path):
    cards = _source_cards_artifact(tmp_path)
    rejected = dict(cards["cards"][0])
    rejected["path"] = "docs/rejected.md"
    rejected["usable_by_agents"] = False
    cards["cards"].append(rejected)

    artifact = build_working_context_packets(cards)

    assert artifact["artifact_version"] == PACKETS_ARTIFACT_VERSION
    assert artifact["summary"]["packets_total"] == 1
    assert artifact["summary"]["cards_included"] == 1
    assert artifact["summary"]["cards_excluded"] == 1
    assert artifact["packets"][0]["cards"][0]["path"] == "docs/allowed.md"


def test_blocked_or_unaccepted_cards_are_excluded(tmp_path):
    cards = _source_cards_artifact(tmp_path)
    blocked = dict(cards["cards"][0])
    blocked["path"] = ".chief.env"
    blocked["authority_label"] = "blocked"
    cards["cards"] = [blocked]

    artifact = build_working_context_packets(cards)

    assert artifact["summary"]["packets_total"] == 0
    assert artifact["summary"]["cards_excluded"] == 1
    assert artifact["excluded_records"][0]["path"] == ".chief.env"


def test_provenance_is_present(tmp_path):
    packet = build_working_context_packets(_source_cards_artifact(tmp_path))["packets"][0]

    assert packet["provenance"]
    assert packet["provenance"][0]["source_path"] == "docs/allowed.md"
    assert packet["provenance"][0]["source_card_ref"].startswith("source_cards_v0:")
    assert packet["cards"][0]["provenance"]["source_path"] == "docs/allowed.md"


def test_limits_and_authority_boundaries_are_present(tmp_path):
    packet = build_working_context_packets(_source_cards_artifact(tmp_path))["packets"][0]

    assert packet["limits"]
    assert "Accepted working context only; no raw full source bodies included." in packet["limits"]
    assert packet["authority_boundaries"]["context_for_reasoning_only"] is True
    assert packet["authority_boundaries"]["runtime_authority"] is False


def test_no_runtime_activation_or_raw_bodies(tmp_path):
    artifact = build_working_context_packets(_source_cards_artifact(tmp_path))

    assert artifact["summary"]["runtime_authority"] is False
    assert artifact["summary"]["raw_full_bodies_included"] is False
    packet = artifact["packets"][0]
    assert packet["runtime_authority"] is False
    assert packet["authority_boundaries"]["runtime_activation"] is False
    assert packet["authority_boundaries"]["agent_activation"] is False
    assert packet["full_body_included"] is False
    assert "extracted_text" not in json.dumps(packet, sort_keys=True)


def test_stable_json_shape(tmp_path):
    artifact = build_working_context_packets(_source_cards_artifact(tmp_path))

    assert set(artifact) == {
        "artifact_version",
        "source_cards_artifact_version",
        "packets",
        "excluded_records",
        "summary",
    }
    packet = artifact["packets"][0]
    assert set(packet) == {
        "packet_version",
        "packet_id",
        "context_state",
        "context_for_reasoning_only",
        "module",
        "lane",
        "source_class",
        "cards",
        "provenance",
        "limits",
        "authority_boundaries",
        "runtime_authority",
        "full_body_included",
    }


def test_operator_output_uses_cockpit_grammar(tmp_path):
    output = format_operator_packets(build_working_context_packets(_source_cards_artifact(tmp_path)))

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "reasoning only" in output
    assert "no raw full bodies" in output
    assert "`runtime_authority=false`" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output
    assert '"packets"' not in output


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    cards_path = tmp_path / "cards.json"
    write_json_artifact(_source_cards_artifact(tmp_path), cards_path)

    exit_code = main(["--source-cards", str(cards_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_version"] == PACKETS_ARTIFACT_VERSION
    assert payload["summary"]["packets_total"] == 1
    assert payload["packets"][0]["context_state"] == "accepted_working_context"
