import json

from scripts.build_source_cards import build_source_cards
from scripts.build_source_inventory import build_inventory
from scripts.build_working_context_packets import build_working_context_packets
from scripts.extract_accepted_sources import build_extraction_artifact
from scripts.promote_accepted_context import build_promotion_manifest, write_json_artifact
from scripts.query_context_packets import (
    RETRIEVAL_ARTIFACT_VERSION,
    format_operator_retrieval,
    main,
    query_context_packets,
)


def _packets_artifact(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text(
        "# Retrieval Fixture\n\n- Exact context fact\n",
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
        reason_for_promotion="retrieve accepted context packets",
    )
    extraction = build_extraction_artifact(promotion)
    cards = build_source_cards(extraction)
    return build_working_context_packets(cards)


def test_can_retrieve_by_module_source_class_and_lane(tmp_path):
    packets = _packets_artifact(tmp_path)

    by_module = query_context_packets(packets, module="openclaw_context")
    by_source_class = query_context_packets(packets, source_class="explicit_allowlist_source")
    by_lane = query_context_packets(packets, lane="context_substrate")

    for result in (by_module, by_source_class, by_lane):
        assert result["artifact_version"] == RETRIEVAL_ARTIFACT_VERSION
        assert result["query_allowed"] is True
        assert result["summary"]["packets_returned"] == 1
        assert result["packets"][0]["context_state"] == "accepted_working_context"


def test_refuses_unknown_and_broad_query(tmp_path):
    packets = _packets_artifact(tmp_path)

    broad = query_context_packets(packets)
    unknown = query_context_packets(packets, module="unknown_module")

    assert broad["query_allowed"] is False
    assert broad["query_state"] == "refused_broad_query"
    assert unknown["query_allowed"] is False
    assert unknown["query_state"] == "refused_unknown_module"
    assert broad["packets"] == []
    assert unknown["packets"] == []


def test_returns_packets_not_raw_files(tmp_path):
    result = query_context_packets(_packets_artifact(tmp_path), lane="context_substrate")
    payload = json.dumps(result, sort_keys=True)

    assert result["summary"]["raw_files_read"] is False
    assert result["summary"]["raw_full_bodies_returned"] is False
    assert "extracted_text" not in payload
    assert "Exact context fact\n" not in payload


def test_no_blocked_records_returned(tmp_path):
    packets = _packets_artifact(tmp_path)
    unsafe_packet = dict(packets["packets"][0])
    unsafe_packet["packet_id"] = "unsafe"
    unsafe_card = dict(unsafe_packet["cards"][0])
    unsafe_card["path"] = ".chief.env"
    unsafe_card["authority_label"] = "blocked"
    unsafe_packet["cards"] = [unsafe_card]
    packets["packets"] = [unsafe_packet]

    result = query_context_packets(packets, lane="context_substrate")

    assert result["query_allowed"] is False
    assert result["query_state"] == "refused_no_safe_packets"
    assert result["packets"] == []


def test_no_runtime_authority_implied(tmp_path):
    result = query_context_packets(_packets_artifact(tmp_path), source_class="explicit_allowlist_source")

    assert result["context_for_reasoning_only"] is True
    assert result["runtime_authority"] is False
    assert result["summary"]["runtime_authority"] is False
    packet = result["packets"][0]
    assert packet["authority_boundaries"]["runtime_authority"] is False
    assert packet["authority_boundaries"]["runtime_activation"] is False


def test_operator_output_uses_gate_grammar(tmp_path):
    output = format_operator_retrieval(
        query_context_packets(_packets_artifact(tmp_path), module="openclaw_context")
    )

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "exact filters" in output
    assert "not raw source files" in output
    assert "`runtime_authority=false`" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output
    assert '"packets"' not in output


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    packets_path = tmp_path / "packets.json"
    write_json_artifact(_packets_artifact(tmp_path), packets_path)

    exit_code = main(
        [
            "--packets",
            str(packets_path),
            "--lane",
            "context_substrate",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_version"] == RETRIEVAL_ARTIFACT_VERSION
    assert payload["query_allowed"] is True
    assert payload["summary"]["packets_returned"] == 1
