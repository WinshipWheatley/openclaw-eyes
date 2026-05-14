import json
import sqlite3
from pathlib import Path

from context_selection import CONTEXT_SELECTION_VERSION, init_context_selection_schema, stable_json
from scripts.export_context_selection_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_context_selection_read_model,
    export_context_selection_read_model,
    main,
)


def _fixture(tmp_path: Path) -> Path:
    db_path = tmp_path / "ledger.sqlite"
    init_context_selection_schema(db_path)

    run_id = "ctx_fixture"
    packet_id = "ctxpacket_fixture"
    created_at = "2026-05-14T00:00:00+00:00"
    query = {
        "world": "build",
        "category": "runtime_gate",
        "task": "prepare Mission Control frontend prompt",
        "task_category_hints": ["runtime_gate", "helm_state"],
        "limit": 60,
    }
    packet_json = {
        "packet_version": CONTEXT_SELECTION_VERSION,
        "packet_id": packet_id,
        "run_id": run_id,
        "query": query,
        "source_tables_used": [
            "evidence_items",
            "read_model_snapshots",
            "corpus_paths",
            "generated/read_models/tool_inventory.json",
            "generated/read_models/tool_intake.json",
        ],
        "context_for_reasoning_only": True,
        "truth_claimed": False,
        "authority_posture": {
            "runtime_authority": False,
            "vector_search_used": False,
            "model_calls_used": False,
            "tool_execution_allowed": False,
            "network_authority": False,
        },
    }

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT INTO context_selection_runs (
  run_id, selector_version, created_at, completed_at, query_world, query_category,
  query_task, evidence_ingestion_run_id, source_basis_json, selected_item_count,
  excluded_item_count, no_go_exclusion_count, packet_count, generated_json_path,
  generated_operator_path, runtime_authority, vector_search_used, model_calls_used,
  network_access_attempted, tool_execution_attempted, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                run_id,
                CONTEXT_SELECTION_VERSION,
                created_at,
                created_at,
                "build",
                "runtime_gate",
                "prepare Mission Control frontend prompt",
                "ek_fixture",
                stable_json({"source_tables_used": packet_json["source_tables_used"]}),
                3,
                2,
                2,
                1,
                "generated/context_packets/context_packet_latest.json",
                "generated/context_packets/context_packet_latest.md",
                "fixture context selection packet",
            ),
        )
        conn.execute(
            """
INSERT INTO context_packets (
  packet_id, run_id, packet_kind, selector_version, created_at, query_json,
  packet_json, selected_item_count, excluded_item_count, no_go_exclusion_count,
  world_binding, evidence_categories_json, freshness_summary_json,
  canonicality_summary_json, sensitivity_summary_json, authority_posture_json,
  context_for_reasoning_only, truth_claimed, runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0)
""".strip(),
            (
                packet_id,
                run_id,
                "evidence_grounded_context_packet",
                CONTEXT_SELECTION_VERSION,
                created_at,
                stable_json(query),
                stable_json(packet_json),
                3,
                2,
                2,
                "build,cross_world",
                stable_json({"runtime_gate": 2, "tool_posture": 1}),
                stable_json({"generated_read_model_fact": 3}),
                stable_json({"generated_current": 3}),
                stable_json({"internal_project": 3}),
                stable_json(packet_json["authority_posture"]),
            ),
        )
        items = [
            (
                "ctxitem_1",
                0,
                "evidence_items",
                "ev_1",
                "generated/read_models/helm_state.json",
                "generated_read_model_snapshot",
                "future_gated_capability",
                "runtime_gate",
                "missing_prerequisite:explicit_operator_approval",
                {"missing": "explicit_operator_approval"},
                "Runtime gate requires explicit operator approval.",
                "generated_read_model_fact",
                "generated_current",
                "internal_project",
                "generated_read_model_only",
                "generated_snapshot_only",
                "build",
            ),
            (
                "ctxitem_2",
                1,
                "evidence_items",
                "ev_2",
                "generated/read_models/runtime_activation_gate.json",
                "generated_read_model_snapshot",
                "generated_read_model_fact",
                "runtime_gate",
                "runtime_authority",
                False,
                "Runtime authority remains false.",
                "generated_read_model_fact",
                "generated_current",
                "internal_project",
                "generated_read_model_only",
                "generated_snapshot_only",
                "cross_world",
            ),
            (
                "ctxitem_3",
                2,
                "generated_read_model_export",
                "rm_1",
                "generated/read_models/tool_intake.json",
                "tool_intake",
                "generated_read_model_fact",
                "tool_posture",
                "tool_intake:installed_candidates",
                ["docker", "ollama"],
                "Tool intake exposes installed candidates as observed metadata only.",
                "generated_read_model_fact",
                "generated_current",
                "internal_project",
                "generated_read_model_only",
                "generated_snapshot_only",
                "build",
            ),
        ]
        for item in items:
            (
                item_id,
                order,
                source_table,
                source_id,
                source_path,
                source_type,
                evidence_label,
                evidence_category,
                evidence_key,
                value,
                summary,
                freshness,
                canonicality,
                sensitivity,
                retrieval,
                ingestion,
                world,
            ) = item
            conn.execute(
                """
INSERT INTO context_packet_items (
  packet_item_id, packet_id, item_order, source_table, source_id, source_path,
  item_kind, evidence_label, evidence_category, evidence_key, evidence_value_json,
  summary, freshness_label, canonicality, sensitivity_label,
  retrieval_eligibility, ingestion_eligibility, world_binding, provenance_json,
  truth_claimed, runtime_authority
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
""".strip(),
                (
                    item_id,
                    packet_id,
                    order,
                    source_table,
                    source_id,
                    source_path,
                    "selected_evidence",
                    evidence_label,
                    evidence_category,
                    evidence_key,
                    stable_json(value),
                    summary,
                    freshness,
                    canonicality,
                    sensitivity,
                    retrieval,
                    ingestion,
                    world,
                    stable_json({"fixture": True}),
                ),
            )

        exclusions = [
            (
                "ctxexcl_1",
                "corpus_paths",
                "cpath_secret",
                ".ssh/id_rsa",
                "corpus_path_not_context_selectable",
                "credential_boundary",
                "blocked_no_go",
                "no_go",
                1,
            ),
            (
                "ctxexcl_2",
                "corpus_paths",
                "cpath_unknown",
                "loose.unknown",
                "corpus_path_not_context_selectable",
                "unknown",
                "blocked_unknown",
                "needs_review",
                1,
            ),
        ]
        for exclusion in exclusions:
            conn.execute(
                """
INSERT INTO context_packet_exclusions (
  exclusion_id, run_id, packet_id, source_table, source_id, source_path,
  exclusion_reason, sensitivity_label, retrieval_eligibility,
  ingestion_eligibility, no_go_boundary
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (exclusion[0], run_id, packet_id, *exclusion[1:]),
            )
        conn.commit()
    finally:
        conn.close()

    return db_path


def test_context_selection_json_and_operator_markdown_are_generated(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    summary = export_context_selection_read_model(db_path=db_path, export_root=export_root)

    assert summary["latest_context_packet_id"] == "ctxpacket_fixture"
    assert summary["selected_item_count"] == 3
    assert summary["excluded_item_count"] == 2
    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()


def test_read_model_represents_packet_counts_and_context_boundaries(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_context_selection_read_model(db_path=db_path)

    assert payload["latest_context_selection_run_id"] == "ctx_fixture"
    assert payload["latest_context_packet_id"] == "ctxpacket_fixture"
    assert payload["selected_item_count"] == 3
    assert payload["excluded_item_count"] == 2
    assert payload["no_go_blocked_sensitive_exclusion_count"] == 2
    assert payload["worlds_represented"] == {"build": 2, "cross_world": 1}
    assert payload["evidence_labels_represented"] == {
        "future_gated_capability": 1,
        "generated_read_model_fact": 2,
    }
    assert payload["evidence_categories_represented"] == {
        "runtime_gate": 2,
        "tool_posture": 1,
    }
    assert payload["selected_evidence_not_truth"] is True
    assert payload["context_packets_are_truth_promotion"] is False
    assert payload["truth_claimed"] is False
    assert payload["generic_rag"] is False


def test_no_authority_flags_are_true(tmp_path):
    db_path = _fixture(tmp_path)
    payload = build_context_selection_read_model(db_path=db_path)

    for key in [
        "runtime_authority",
        "agent_activation_allowed",
        "backend_execution_allowed",
        "model_call_allowed",
        "vector_search_allowed",
        "tool_execution_allowed",
        "docker_execution_allowed",
        "ollama_execution_allowed",
        "network_authority",
        "truth_promotion_allowed",
    ]:
        assert payload[key] is False
        assert payload["authority_flags"][key] is False
    assert payload["vector_search_used"] is False
    assert payload["model_calls_used"] is False
    assert "model_call" in payload["claims_not_made"]
    assert "vector_search" in payload["claims_not_made"]
    assert "tool_execution" in payload["claims_not_made"]


def test_operator_markdown_states_evidence_not_truth_and_next_safe_move(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    export_context_selection_read_model(db_path=db_path, export_root=export_root)

    text = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert "What this is:" in text
    assert "Latest packet summary:" in text
    assert "Context packets are selected evidence and bounded reasoning context, not truth promotion" in text
    assert "It is not generic RAG, vector search, model execution, tool execution" in text
    assert "runtime_authority=false" in text
    assert "model_call_allowed=false" in text
    assert "vector_search_allowed=false" in text
    assert "tool_execution_allowed=false" in text
    assert "Next safe move:" in text


def test_export_output_is_deterministic_for_same_context_packet(tmp_path):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    export_context_selection_read_model(db_path=db_path, export_root=export_root)
    first_json = (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8")
    first_operator = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    export_context_selection_read_model(db_path=db_path, export_root=export_root)

    assert (export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8") == first_json
    assert (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8") == first_operator


def test_cli_exports_json_and_operator_markdown(tmp_path, capsys):
    db_path = _fixture(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["latest_context_packet_id"] == "ctxpacket_fixture"
    assert (export_root / JSON_EXPORT_NAME).is_file()
    assert (export_root / OPERATOR_EXPORT_NAME).is_file()

    operator_exit_code = main(
        [
            "--db",
            str(db_path),
            "--export-root",
            str(export_root),
            "--format",
            "operator",
        ]
    )
    operator_output = capsys.readouterr().out
    assert operator_exit_code == 0
    assert "Context Selection Read-Model Export v0" in operator_output


def test_export_script_has_no_external_tool_or_network_behavior():
    text = Path("scripts/export_context_selection_read_model.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "pip install",
        "pipx install",
        "npm install",
        "apt install",
        "apt-get install",
        "uv pip install",
        "docker run",
        "ollama run",
        "ollama pull",
    ]
    for token in forbidden:
        assert token not in text
