import json
import sqlite3
from pathlib import Path

from context_selection import (
    CONTEXT_SELECTION_VERSION,
    compile_context_packet,
    context_selection_table_names,
    query_context_selection_report_section,
)
from corpus_atlas import run_corpus_atlas
from evidence_kettle import run_evidence_kettle
from scripts.build_context_packet import main as build_main
from scripts.query_context_selection import main as query_main


WORLD_IDS = (
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    for name in (
        "AGENTS.md",
        "CORE_ARCHITECTURE_PRINCIPLES.md",
        "OPENCLAW_RUNTIME.md",
        "USER.md",
    ):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")

    (root / ".ssh").mkdir()
    (root / ".ssh" / "id_rsa").write_text("secret fixture should not appear\n", encoding="utf-8")
    (root / "loose.unknown").write_text("unknown fixture should not be selected\n", encoding="utf-8")
    (root / "execution_receipts").mkdir()
    (root / "execution_receipts" / "receipt.json").write_text(
        '{"full_body":"receipt body should not appear"}\n',
        encoding="utf-8",
    )
    (root / "compliance_verdicts").mkdir()
    (root / "compliance_verdicts" / "verdict.json").write_text(
        '{"full_body":"verification body should not appear"}\n',
        encoding="utf-8",
    )

    read_models = root / "generated" / "read_models"
    read_models.mkdir(parents=True)
    _write_json(
        read_models / "helm_state.json",
        {
            "read_model_version": "helm_state_v0",
            "helm_state": {"state": "inspect_only"},
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "strategic_gravity": {"supported": False},
            "agent_presence_model": {"supported": False, "live_agents_claimed": False},
            "activation_gate": {
                "gate_state": "blocked_v0_contract",
                "missing_prerequisites": ["explicit_operator_approval", "rollback_plan"],
            },
            "next_safe_move": "keep inspect-only",
        },
    )
    _write_json(
        read_models / "runtime_activation_gate.json",
        {
            "artifact_version": "runtime_module_activation_gate_v0",
            "gate_state": "blocked_v0_contract",
            "runtime_authority": False,
            "activation_allowed": False,
            "module_activation_authority": False,
            "missing_prerequisites": ["explicit_operator_approval", "rollback_plan"],
            "next_safe_move": "keep packets as reasoning context",
        },
    )
    _write_json(
        read_models / "world_domain_registry.json",
        {
            "read_model_version": "world_domain_registry_v0",
            "world_count": len(WORLD_IDS),
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "dynamic_world_state": False,
            "strategic_gravity_supported": False,
            "agent_presence_supported": False,
            "worlds": [{"world_id": world_id} for world_id in WORLD_IDS],
        },
    )
    _write_json(
        read_models / "world_status.json",
        {
            "read_model_version": "world_status_v0",
            "world_count": len(WORLD_IDS),
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "dynamic_world_state": False,
            "strategic_gravity_supported": False,
            "agent_presence_supported": False,
            "worlds": [{"world_id": world_id, "status": "inspect_only"} for world_id in WORLD_IDS],
        },
    )
    _write_json(
        read_models / "artifact_registry.json",
        {
            "read_model_version": "artifact_registry_v0",
            "artifact_count": 9,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution_authorized": False,
            "body_ingested": False,
            "metadata_only": True,
        },
    )
    _write_json(
        read_models / "source_inventory.json",
        {
            "inventory_version": "bounded_source_inventory_v0",
            "summary": {
                "records_total": 21,
                "allowlisted_records": 13,
                "blocked_no_go_examples": 8,
                "blocked_records": 8,
                "body_ingested": False,
                "metadata_only_records": 13,
            },
            "scope": {
                "runtime_activation": False,
                "agent_activation": False,
                "broker_connection": False,
                "customer_deployment": False,
                "hard_drive_scan": False,
                "sqlite_touched": False,
                "whole_repo_scan": False,
            },
            "records": [],
        },
    )
    _write_json(
        read_models / "evidence_freshness.json",
        {
            "read_model_version": "evidence_freshness_v0",
            "artifact_count": 7,
            "freshness_counts": {"current": 7, "stale": 0, "missing": 0, "unknown": 0},
            "generated_status_current": True,
            "read_model_exports_current": True,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution_authorized": False,
            "body_ingested": False,
        },
    )
    (read_models / "generated_current_state.md").write_text("# Generated current state\n", encoding="utf-8")
    (read_models / "generated_next_actions.md").write_text("# Generated next actions\n", encoding="utf-8")
    _write_json(
        read_models / "tool_inventory.json",
        {
            "read_model_version": "tool_inventory_read_model_v0",
            "observed_candidate_count": 63,
            "detected_count": 15,
            "not_detected_count": 48,
            "high_risk_detected_tools": [{"tool_id": "docker"}, {"tool_id": "ollama"}],
            "local_llm_findings": {
                "detected_count": 1,
                "tools": [{"tool_id": "ollama"}, {"tool_id": "llama_cpp"}],
            },
            "sqlite_findings": {
                "detected_count": 0,
                "tools": [{"tool_id": "sqlite3"}, {"tool_id": "datasette"}],
            },
            "tool_activation_allowed": False,
            "runtime_authority": False,
            "integration_authority": False,
            "model_execution_allowed": False,
            "container_execution_allowed": False,
            "remote_access_allowed": False,
            "network_authority": False,
        },
    )
    _write_json(
        read_models / "tool_intake.json",
        {
            "read_model_version": "tool_intake_read_model_v0",
            "candidate_count": 39,
            "inventory_linked_candidate_count": 33,
            "installed_candidate_count": 2,
            "installed_candidates": [{"tool_id": "docker"}, {"tool_id": "ollama"}],
            "high_fit_candidates": [{"tool_id": "pocketbase"}, {"tool_id": "datasette"}],
            "high_risk_candidates": [{"tool_id": "docker"}, {"tool_id": "ollama"}],
            "sandbox_later_candidates": [{"tool_id": "caddy"}, {"tool_id": "syncthing"}],
            "client_capsule_candidates": [{"tool_id": "pocketbase"}, {"tool_id": "copier"}],
            "tool_install_allowed": False,
            "tool_execution_allowed": False,
            "integration_authority": False,
            "approval_authority": False,
            "runtime_authority": False,
            "network_authority": False,
            "model_execution_allowed": False,
            "container_execution_allowed": False,
            "remote_access_allowed": False,
        },
    )
    return root


def _substrate(tmp_path: Path):
    root = _sample_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"

    def hash_reader(path: Path) -> str:
        rel = path.relative_to(root).as_posix()
        assert not rel.startswith(".ssh")
        return "hash-" + rel.replace("/", "_")

    atlas = run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id="atlas_fixture",
        hash_reader=hash_reader,
    )

    read_paths = []

    def file_reader(path: Path) -> bytes:
        rel = path.relative_to(root).as_posix()
        read_paths.append(rel)
        assert rel.startswith("generated/read_models/")
        assert not rel.startswith(".ssh")
        return path.read_bytes()

    evidence = run_evidence_kettle(
        db_path=db_path,
        root=root,
        atlas_run_id=atlas.run_id,
        ingestion_run_id="ek_fixture",
        file_reader=file_reader,
    )
    return root, db_path, evidence


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_context_selection_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "context_selection_runs",
        "context_packets",
        "context_packet_items",
        "context_packet_sources",
        "context_packet_world_bindings",
        "context_packet_exclusions",
        "context_packet_receipts",
    } <= set(context_selection_table_names(db_path))


def test_runtime_gate_packet_records_provenance_and_receipt(tmp_path):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    result = compile_context_packet(
        db_path=db_path,
        category="runtime_gate",
        run_id="ctx_runtime_gate",
        output_root=output_root,
        read_model_root=root / "generated" / "read_models",
    )
    packet = json.loads((output_root / "context_packet_latest.json").read_text(encoding="utf-8"))

    assert result.selected_item_count > 0
    assert packet["packet_version"] == CONTEXT_SELECTION_VERSION
    assert packet["context_for_reasoning_only"] is True
    assert packet["authority_posture"]["runtime_authority"] is False
    assert packet["authority_posture"]["vector_search_used"] is False
    assert packet["selected_items"][0]["provenance"]
    assert _row(db_path, "SELECT COUNT(*) FROM context_packet_receipts WHERE run_id = ?", (result.run_id,))[0] == 1


def test_no_go_unknown_and_private_content_are_excluded(tmp_path):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    result = compile_context_packet(
        db_path=db_path,
        category="runtime_gate",
        run_id="ctx_exclusions",
        output_root=output_root,
        read_model_root=root / "generated" / "read_models",
    )
    packet_text = (output_root / "context_packet_latest.json").read_text(encoding="utf-8")
    selected_paths = {
        row[0]
        for row in _rows(
            db_path,
            "SELECT source_path FROM context_packet_items WHERE packet_id = ?",
            (result.packet_id,),
        )
    }
    excluded_paths = {
        row[0]
        for row in _rows(
            db_path,
            "SELECT source_path FROM context_packet_exclusions WHERE run_id = ?",
            (result.run_id,),
        )
    }

    assert not any(path.startswith(".ssh") for path in selected_paths)
    assert "loose.unknown" not in selected_paths
    assert any(path.startswith(".ssh") for path in excluded_paths)
    assert "loose.unknown" in excluded_paths
    assert "secret fixture should not appear" not in packet_text
    assert "receipt body should not appear" not in packet_text
    assert "verification body should not appear" not in packet_text
    assert result.no_go_exclusion_count >= 1


def test_world_packet_selects_world_bound_and_cross_world_evidence(tmp_path):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    result = compile_context_packet(
        db_path=db_path,
        world="build",
        run_id="ctx_build_world",
        output_root=output_root,
        read_model_root=root / "generated" / "read_models",
    )
    world_bindings = {
        row[0]
        for row in _rows(
            db_path,
            "SELECT DISTINCT world_binding FROM context_packet_items WHERE packet_id = ?",
            (result.packet_id,),
        )
    }

    assert result.selected_item_count > 0
    assert "build" in world_bindings or "cross_world" in world_bindings
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM context_packet_items WHERE packet_id = ? AND evidence_category = 'runtime_gate'",
        (result.packet_id,),
    )[0] >= 1


def test_tool_posture_packet_reads_generated_read_models_without_authority(tmp_path):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    result = compile_context_packet(
        db_path=db_path,
        category="tool_posture",
        run_id="ctx_tool_posture",
        output_root=output_root,
        read_model_root=root / "generated" / "read_models",
    )
    packet = json.loads((output_root / "context_packet_latest.json").read_text(encoding="utf-8"))
    keys = {item["evidence_key"] for item in packet["selected_items"]}
    values = json.dumps(packet, sort_keys=True)

    assert "tool_intake:installed_candidates" in keys
    assert "tool_intake:high_risk_candidates" in keys
    assert "tool_inventory:high_risk_detected_tools" in keys
    assert "docker" in values
    assert "ollama" in values
    assert packet["authority_posture"]["model_execution_allowed"] is False
    assert packet["authority_posture"]["container_execution_allowed"] is False
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM context_packet_items WHERE packet_id = ? AND sensitivity_label != 'internal_project'",
        (result.packet_id,),
    )[0] == 0


def test_task_client_capsule_maps_to_tool_posture(tmp_path):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    result = compile_context_packet(
        db_path=db_path,
        task="inspect client capsule candidates",
        run_id="ctx_client_capsule",
        output_root=output_root,
        read_model_root=root / "generated" / "read_models",
    )

    assert _row(
        db_path,
        "SELECT COUNT(*) FROM context_packet_items WHERE packet_id = ? AND evidence_key = 'tool_intake:client_capsule_candidates'",
        (result.packet_id,),
    )[0] == 1


def test_reports_and_clis_work(tmp_path, capsys):
    root, db_path, _ = _substrate(tmp_path)
    output_root = tmp_path / "generated" / "context_packets"

    build_exit = build_main(
        [
            "--db",
            str(db_path),
            "--category",
            "future_gated_capability",
            "--run-id",
            "ctx_cli",
            "--output-root",
            str(output_root),
            "--format",
            "json",
        ]
    )
    build_payload = json.loads(capsys.readouterr().out)
    assert build_exit == 0
    assert build_payload["selected_item_count"] >= 1

    summary_exit = query_main(
        ["--db", str(db_path), "--run-id", "ctx_cli", "--report", "summary", "--format", "operator"]
    )
    assert summary_exit == 0
    assert "Context Selection Knowledge Packet v0" in capsys.readouterr().out

    items = query_context_selection_report_section(db_path=db_path, run_id="ctx_cli", section="items")
    exclusions = query_context_selection_report_section(db_path=db_path, run_id="ctx_cli", section="exclusions")
    receipts = query_context_selection_report_section(db_path=db_path, run_id="ctx_cli", section="receipts")
    assert items["items"]
    assert exclusions["items"]
    assert receipts["items"]


def test_context_selection_sources_have_no_external_tool_or_network_behavior():
    source_files = [
        Path("context_selection.py"),
        Path("scripts/build_context_packet.py"),
        Path("scripts/query_context_selection.py"),
    ]
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
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text
