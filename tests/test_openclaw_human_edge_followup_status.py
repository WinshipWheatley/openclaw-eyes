import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_human_edge_followup_status as followup


FIXED_NOW = "2026-06-13T23:00:00+00:00"


def test_followup_labels_remaining_work_without_live_authority():
    payload = followup.build_payload(generated_at=FIXED_NOW)
    gaps = {item["gap_id"]: item for item in payload["remaining_work"]}

    assert payload["status"] == followup.READY_STATUS
    assert payload["graphiffy_status"]["latest_result"] == "connector_timeout"
    assert gaps["live_email_transport_not_proven"]["status"] == "blocked_pending_explicit_transport_test"
    assert gaps["live_calendar_transport_not_proven"]["status"] == "blocked_pending_explicit_transport_test"
    assert gaps["post_fix_live_cassandra_smoke_needed"]["status"] == "waiting_for_operator_telegram_message"
    assert payload["authority_boundary"]["email_sent"] is False
    assert payload["authority_boundary"]["calendar_api_called"] is False
    assert payload["authority_boundary"]["hermes_started"] is False
    assert payload["safety_confirmation"]["live_transport_not_claimed"] is True
    assert payload["unsafe_true_paths"] == []


def test_coverage_graph_contains_systems_and_dry_run_boundaries():
    graph = followup.build_coverage_graph()
    node_ids = {node["id"] for node in graph["nodes"]}
    edge_pairs = {(edge["source"], edge["target"]) for edge in graph["edges"]}

    assert "human-edge-lab" in node_ids
    assert "test-effect-adapters" in node_ids
    assert "live-email-transport" in node_ids
    assert "live-calendar-transport" in node_ids
    assert ("dry-run-email", "live-email-transport") in edge_pairs
    assert ("dry-run-calendar", "live-calendar-transport") in edge_pairs


def test_write_outputs_parse_and_bridge_match(tmp_path):
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"
    wiki_path = tmp_path / "wiki" / "OpenClaw Human Edge Followup Status.md"

    payload = followup.write_outputs(
        export_root=export_root,
        bridge_root=bridge_root,
        wiki_path=wiki_path,
        generated_at=FIXED_NOW,
    )
    paths = payload["artifact_paths"]
    read_model = Path(paths["read_model_path"])
    bridge = Path(paths["bridge_path"])
    graph = Path(paths["graph_path"])
    bridge_graph = Path(paths["bridge_graph_path"])

    assert json.loads(read_model.read_text(encoding="utf-8")) == json.loads(bridge.read_text(encoding="utf-8"))
    assert json.loads(graph.read_text(encoding="utf-8")) == json.loads(bridge_graph.read_text(encoding="utf-8"))
    assert "Dry-run receipts are test evidence only" in wiki_path.read_text(encoding="utf-8")
    assert json.loads(read_model.read_text(encoding="utf-8"))["unsafe_true_paths"] == []
