import json

from scripts.build_source_cards import (
    SOURCE_CARDS_VERSION,
    build_source_cards,
    format_operator_source_cards,
    main,
)
from scripts.build_source_inventory import build_inventory
from scripts.extract_accepted_sources import build_extraction_artifact
from scripts.promote_accepted_context import build_promotion_manifest, write_json_artifact


def _extraction_artifact(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text(
        "# Source Card Fixture\n\n## Purpose\n\n- Fact one\n- Fact two\n",
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
        reason_for_promotion="build source cards",
    )
    return build_extraction_artifact(promotion)


def test_cards_generated_from_extracted_sources(tmp_path):
    artifact = build_source_cards(_extraction_artifact(tmp_path))

    assert artifact["artifact_version"] == SOURCE_CARDS_VERSION
    assert artifact["summary"]["cards_total"] == 1
    card = artifact["cards"][0]
    assert card["path"] == "docs/allowed.md"
    assert card["purpose"] == "Source Card Fixture"
    assert "Purpose" in card["known_facts"]
    assert card["ingestion_state"] == "summarized"
    assert card["usable_by_agents"] is True


def test_authority_freshness_and_limits_are_present(tmp_path):
    card = build_source_cards(_extraction_artifact(tmp_path))["cards"][0]

    assert card["authority_label"] == "documentation_only"
    assert card["freshness"]["source_sha256"]
    assert card["freshness"]["source_size_bytes"] > 0
    assert card["freshness"]["extraction_time_policy"] == "omitted_for_deterministic_read_model"
    assert card["limits"]
    assert "Parsed evidence is not truth." in card["limits"]
    assert card["provenance"]["source_path"] == "docs/allowed.md"


def test_cards_do_not_create_runtime_authority(tmp_path):
    artifact = build_source_cards(_extraction_artifact(tmp_path))

    assert artifact["summary"]["runtime_authority"] is False
    for card in artifact["cards"]:
        assert card["runtime_authority"] is False
        assert card["not_runtime_authority"] is True
        assert card["context_for_reasoning_only"] is True


def test_blocked_or_refused_sources_are_not_included(tmp_path):
    extraction = _extraction_artifact(tmp_path)
    extraction["refusals"].append(
        {
            "path": ".chief.env",
            "reason_refused": "source_inventory_record_not_allowed_for_agent_context",
            "runtime_authority": False,
        }
    )

    artifact = build_source_cards(extraction)

    paths = {card["path"] for card in artifact["cards"]}
    assert ".chief.env" not in paths
    assert artifact["summary"]["excluded_records"] == 1
    assert artifact["excluded_records"][0]["path"] == ".chief.env"


def test_cards_do_not_include_full_extracted_bodies(tmp_path):
    artifact = build_source_cards(_extraction_artifact(tmp_path))
    card_json = json.dumps(artifact["cards"][0], sort_keys=True)

    assert artifact["summary"]["full_bodies_in_cards"] is False
    assert '"extracted_text"' not in card_json
    assert "Fact one\n- Fact two" not in card_json


def test_operator_grammar_present(tmp_path):
    output = format_operator_source_cards(build_source_cards(_extraction_artifact(tmp_path)))

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "deterministic/extractive only" in output
    assert "no LLM calls" in output
    assert "do not contain full source bodies" in output
    assert "`runtime_authority=false`" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output
    assert '"cards"' not in output


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    extraction_path = tmp_path / "extraction.json"
    write_json_artifact(_extraction_artifact(tmp_path), extraction_path)

    exit_code = main(
        [
            "--extraction-artifact",
            str(extraction_path),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_version"] == SOURCE_CARDS_VERSION
    assert payload["summary"]["cards_total"] == 1
    assert payload["cards"][0]["usable_by_agents"] is True
