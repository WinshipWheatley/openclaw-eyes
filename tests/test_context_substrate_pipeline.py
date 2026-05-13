import json

from scripts.build_source_cards import build_source_cards
from scripts.build_source_inventory import BlockedExample, build_inventory
from scripts.build_working_context_packets import build_working_context_packets
from scripts.check_runtime_activation_gate import build_activation_gate_report
from scripts.extract_accepted_sources import EVIDENCE_LABEL, build_extraction_artifact
from scripts.generate_operator_status import get_context_gates_operator_status
from scripts.promote_accepted_context import (
    build_promotion_manifest,
    load_json_artifact,
    write_json_artifact,
)
from scripts.query_context_packets import query_context_packets


RAW_BODY_SENTINEL = "RAW_BODY_SENTINEL_SHOULD_NOT_LEAVE_EXTRACTION"
BLOCKED_PATH = ".chief.env"

FORBIDDEN_TRUE_KEYS = {
    "activation_allowed",
    "agent_activation",
    "broker_connection",
    "broker_wiring",
    "customer_deployment",
    "external_tools",
    "live_runtime_health_claimed",
    "module_activation",
    "module_activation_authority",
    "runtime_activation",
    "runtime_authority",
    "runtime_health_check",
    "runtime_mutation",
    "sqlite_touched",
}


def _round_trip(tmp_path, name, payload):
    path = tmp_path / f"{name}.json"
    write_json_artifact(payload, path)
    return load_json_artifact(path)


def _assert_forbidden_flags_false(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_TRUE_KEYS:
                assert value is False
            _assert_forbidden_flags_false(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_forbidden_flags_false(item)


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True)


def test_deterministic_context_substrate_pipeline_preserves_boundaries(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "context.md").write_text(
        "# Pipeline Context Fixture\n\n"
        "- Compact card fact\n\n"
        f"{RAW_BODY_SENTINEL}\n",
        encoding="utf-8",
    )

    inventory = _round_trip(
        tmp_path,
        "inventory",
        build_inventory(
            root=tmp_path,
            allowlist=("docs/context.md",),
            blocked_examples=(
                BlockedExample(
                    BLOCKED_PATH,
                    "secret_or_credential",
                    "credential file is outside source inventory scope",
                ),
            ),
        ),
    )
    assert inventory["summary"]["body_ingested"] is False
    assert inventory["scope"]["sqlite_touched"] is False

    promotion = _round_trip(
        tmp_path,
        "promotion",
        build_promotion_manifest(
            inventory,
            requested_paths=("docs/context.md", BLOCKED_PATH),
            reason_for_promotion="verify deterministic context substrate handoff",
        ),
    )
    assert promotion["summary"]["promoted_records"] == 1
    assert promotion["summary"]["refused_records"] == 1
    assert promotion["records"][0]["path"] == "docs/context.md"
    assert promotion["refusals"][0]["path"] == BLOCKED_PATH
    assert promotion["scope"]["body_ingested"] is False
    assert promotion["scope"]["source_body_read"] is False

    extraction = _round_trip(
        tmp_path,
        "extraction",
        build_extraction_artifact(promotion),
    )
    extracted_record = extraction["records"][0]
    assert extraction["summary"]["extracted_records"] == 1
    assert extracted_record["evidence_label"] == EVIDENCE_LABEL
    assert extracted_record["truth_status"] == "not_truth"
    assert extracted_record["body_ingested"] is True
    assert RAW_BODY_SENTINEL in extracted_record["extracted_text"]
    assert BLOCKED_PATH not in {record["path"] for record in extraction["records"]}

    source_cards = _round_trip(
        tmp_path,
        "source_cards",
        build_source_cards(extraction),
    )
    card = source_cards["cards"][0]
    source_cards_text = _payload_text(source_cards)
    assert card["path"] == "docs/context.md"
    assert card["limits"]
    assert card["authority_label"] == "documentation_only"
    assert card["provenance"]["source_path"] == "docs/context.md"
    assert card["runtime_authority"] is False
    assert card["full_body_included"] is False
    assert "Compact card fact" in source_cards_text
    assert RAW_BODY_SENTINEL not in source_cards_text
    assert "extracted_text" not in source_cards_text
    assert BLOCKED_PATH not in {item["path"] for item in source_cards["cards"]}

    packets = _round_trip(
        tmp_path,
        "packets",
        build_working_context_packets(source_cards),
    )
    packet = packets["packets"][0]
    packets_text = _payload_text(packets)
    assert packet["context_state"] == "accepted_working_context"
    assert packet["limits"]
    assert packet["authority_boundaries"]["runtime_authority"] is False
    assert packet["provenance"][0]["source_path"] == "docs/context.md"
    assert packet["cards"][0]["provenance"]["source_path"] == "docs/context.md"
    assert packets["summary"]["raw_full_bodies_included"] is False
    assert RAW_BODY_SENTINEL not in packets_text
    assert "extracted_text" not in packets_text
    assert BLOCKED_PATH not in packets_text

    retrieval = query_context_packets(packets, module=packet["module"])
    retrieval_text = _payload_text(retrieval)
    assert retrieval["query_allowed"] is True
    assert retrieval["context_for_reasoning_only"] is True
    assert retrieval["summary"]["raw_files_read"] is False
    assert retrieval["summary"]["raw_full_bodies_returned"] is False
    assert retrieval["packets"][0]["provenance"][0]["source_path"] == "docs/context.md"
    assert RAW_BODY_SENTINEL not in retrieval_text
    assert "extracted_text" not in retrieval_text
    assert BLOCKED_PATH not in retrieval_text

    activation_gate = build_activation_gate_report(packets)
    assert activation_gate["gate_state"] == "blocked_v0_contract"
    assert activation_gate["activation_allowed"] is False
    assert activation_gate["runtime_authority"] is False
    assert activation_gate["live_runtime_health_claimed"] is False
    assert activation_gate["scope"]["sqlite_touched"] is False

    generated_status = get_context_gates_operator_status()
    assert "reports gate availability only" in generated_status
    assert "`body_ingested=false`" in generated_status
    assert "does not read extraction artifacts or raw source bodies" in generated_status
    assert "No agents, modules, brokers, customer deployment, external tools" in generated_status

    for payload in (
        inventory,
        promotion,
        extraction,
        source_cards,
        packets,
        retrieval,
        activation_gate,
    ):
        _assert_forbidden_flags_false(payload)
