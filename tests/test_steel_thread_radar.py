import ast
import json
import sqlite3
from pathlib import Path

from scripts.build_steel_thread_radar import main as build_main
from scripts.export_steel_thread_radar_read_model import main as export_main
from scripts.fetch_steel_thread_sources import main as fetch_main
from scripts.query_steel_thread_radar import main as query_main
from steel_thread_radar import (
    NO_AUTHORITY_FLAGS,
    RECOMMENDATIONS,
    build_steel_thread_radar,
    build_steel_thread_read_model,
    build_steel_thread_surface_read_model,
    build_steel_thread_report,
    export_steel_thread_radar_read_model,
    format_operator_steel_thread_read_model,
    fetch_steel_thread_sources,
    seed_steel_thread_source_registry,
    steel_thread_table_names,
)
from work_board import build_work_board


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    for relative in [
        "work_board.py",
        "external_ai_context_packager.py",
        "operator_action.py",
        "intent_router.py",
        "agent_lane_registry.py",
        "agent_work_packet.py",
        "docs/operations/OPENCLAW_EXTERNAL_AI_CONTEXT_PACKAGER_V0.md",
        "docs/operations/OPENCLAW_SUBSTRATE_MISSION_CONTROL_CHECKPOINT_V1.md",
    ]:
        _write(root / relative, "# fixture\n")
    _write(
        root / "generated" / "frontier_research_packets" / "agent_board.md",
        "\n".join(
            [
                "---",
                "source_kind: operator_supplied_summary",
                "verification_status: unverified_external_claim",
                "pattern_category: agent_orchestration",
                "---",
                "",
                "# Agent Work Board Pattern",
                "",
                "Operator summary mentions OpenAI Symphony, Hermes Kanban, and an agent work board orchestration board.",
                "Recommendation: adapt locally through Work Board v0 and Mission Control read-only cards.",
            ]
        ),
    )
    return root


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    tables = set(steel_thread_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "steel_thread_runs",
        "steel_thread_signals",
        "steel_thread_evidence_links",
        "steel_thread_patterns",
        "steel_thread_recommendations",
        "steel_thread_alignment_links",
        "steel_thread_watchlist_items",
        "steel_thread_source_registry",
        "steel_thread_feed_runs",
        "steel_thread_feed_items",
        "steel_thread_feed_item_classifications",
        "steel_thread_feed_fetch_receipts",
        "steel_thread_feed_rejections",
        "steel_thread_query_receipts",
    } <= tables


def test_source_registry_initializes_with_disabled_external_sources(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    counts = seed_steel_thread_source_registry(db_path)
    sources = _rows(
        db_path,
        """
SELECT source_id, source_kind, enabled, url, local_path,
       broad_web_crawl_allowed, recursive_crawl_allowed,
       browser_automation_allowed
FROM steel_thread_source_registry
ORDER BY source_id
""",
    )
    by_id = {row["source_id"]: row for row in sources}

    assert counts == {"source_count": 4, "enabled_source_count": 2}
    assert by_id["operator_manual_frontier_notes"]["enabled"] == 1
    assert by_id["local_frontier_research_packets"]["source_kind"] == "local_research_packet"
    assert by_id["local_frontier_research_packets"]["local_path"] == "generated/frontier_research_packets"
    assert by_id["official_ai_tooling_feeds"]["enabled"] == 0
    assert by_id["official_ai_tooling_feeds"]["url"] is None
    assert by_id["github_agent_framework_releases"]["enabled"] == 0
    assert all(row["broad_web_crawl_allowed"] == 0 for row in sources)
    assert all(row["recursive_crawl_allowed"] == 0 for row in sources)
    assert all(row["browser_automation_allowed"] == 0 for row in sources)


def test_build_is_idempotent_and_seeds_initial_signals(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)

    first = build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")
    second = build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    assert first == second
    assert first.signal_count == 3
    assert first.high_relevance_count == 3
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_runs")["count"] == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_signals")["count"] == 3
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_recommendations")["count"] == 3


def test_operator_supplied_tiktok_signal_is_source_claim_not_verified_truth(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    signal = _row(
        db_path,
        """
SELECT source_kind, source_ref, evidence_basis, confidence, recommendation, routed_agent
FROM steel_thread_signals
WHERE signal_id = ?
""",
        ("steel_signal_agent_work_board_orchestration",),
    )
    evidence = _row(
        db_path,
        """
SELECT verified_truth_claim, raw_body_stored
FROM steel_thread_evidence_links
WHERE signal_id = ?
""",
        ("steel_signal_agent_work_board_orchestration",),
    )

    assert signal["source_kind"] == "operator_note"
    assert "tiktok" in signal["source_ref"].lower()
    assert "source_claim/operator_note" in signal["evidence_basis"]
    assert signal["confidence"] == "medium"
    assert signal["recommendation"] == "adapt"
    assert signal["routed_agent"] == "chief"
    assert tuple(evidence) == (0, 0)


def test_local_research_packet_ingests_as_unverified_signal(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    result = fetch_steel_thread_sources(db_path=db_path, repo_root=root, run_id="feed_fixture")
    item = _row(db_path, "SELECT * FROM steel_thread_feed_items")
    classification = _row(db_path, "SELECT * FROM steel_thread_feed_item_classifications")
    signal = _row(db_path, "SELECT * FROM steel_thread_signals WHERE signal_id = ?", (classification["signal_id"],))

    assert result.fetched_item_count == 1
    assert result.local_packet_count == 1
    assert result.network_fetch_attempted is False
    assert item["verification_status"] == "unverified_external_claim"
    assert item["raw_body_stored"] == 0
    assert item["source_claim"] == 1
    assert classification["pattern_category"] == "agent_orchestration"
    assert classification["recommended_lane"] == "Mission Control Work Board Read-Only Surface v0"
    assert classification["routed_agent"] == "chief"
    assert classification["reviewer"] == "hermes"
    assert classification["safety_reviewer"] == "guardian"
    assert signal["source_kind"] == "local_research_packet"
    assert signal["recommendation"] == "adapt"
    assert "unverified_external_claim" in signal["evidence_basis"]


def test_disabled_url_sources_are_not_fetched(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    seed_steel_thread_source_registry(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE steel_thread_source_registry SET url = ? WHERE source_id = ?",
            ("https://example.com/feed.xml", "official_ai_tooling_feeds"),
        )
        conn.commit()
    finally:
        conn.close()

    called = {"urlopen": 0}

    def fail_urlopen(*args, **kwargs):
        called["urlopen"] += 1
        raise AssertionError("disabled URL source should not be fetched")

    monkeypatch.setattr("steel_thread_radar.urllib.request.urlopen", fail_urlopen)
    result = fetch_steel_thread_sources(db_path=db_path, repo_root=root, run_id="feed_disabled")

    assert result.network_fetch_attempted is False
    assert called["urlopen"] == 0
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_feed_rejections")["count"] == 0


def test_enabled_non_allowlisted_url_is_rejected_without_fetch(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    seed_steel_thread_source_registry(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
UPDATE steel_thread_source_registry
SET url = ?, enabled = 1
WHERE source_id = ?
""".strip(),
            ("file:///etc/passwd", "official_ai_tooling_feeds"),
        )
        conn.commit()
    finally:
        conn.close()

    called = {"urlopen": 0}

    def fail_urlopen(*args, **kwargs):
        called["urlopen"] += 1
        raise AssertionError("non-allowlisted URL should not be fetched")

    monkeypatch.setattr("steel_thread_radar.urllib.request.urlopen", fail_urlopen)
    result = fetch_steel_thread_sources(db_path=db_path, repo_root=root, run_id="feed_reject")
    rejection = _row(db_path, "SELECT rejection_reason, network_used FROM steel_thread_feed_rejections")

    assert result.rejected_count == 1
    assert result.network_fetch_attempted is False
    assert called["urlopen"] == 0
    assert "not explicitly enabled and allowlisted" in rejection["rejection_reason"]
    assert rejection["network_used"] == 0


def test_max_local_packet_item_limit_is_enforced(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    _write(
        root / "generated" / "frontier_research_packets" / "second.md",
        "# Second Signal\n\nAnother agent orchestration board packet.",
    )
    seed_steel_thread_source_registry(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
UPDATE steel_thread_source_registry
SET max_items_per_run = 1
WHERE source_id = 'local_frontier_research_packets'
""".strip()
        )
        conn.commit()
    finally:
        conn.close()

    result = fetch_steel_thread_sources(db_path=db_path, repo_root=root, run_id="feed_limit")

    assert result.fetched_item_count == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_feed_items")["count"] == 1


def test_agent_work_board_pattern_maps_to_chief_and_work_board_surface(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    pattern = _row(
        db_path,
        """
SELECT pattern_category, openclaw_mapping_json
FROM steel_thread_patterns
WHERE signal_id = ?
""",
        ("steel_signal_agent_work_board_orchestration",),
    )
    recommendation = _row(
        db_path,
        """
SELECT recommended_lane, next_safe_move, approval_required, action_created
FROM steel_thread_recommendations
WHERE signal_id = ?
""",
        ("steel_signal_agent_work_board_orchestration",),
    )
    alignment = _row(
        db_path,
        """
SELECT surface_status
FROM steel_thread_alignment_links
WHERE signal_id = ? AND related_surface = ?
""",
        ("steel_signal_agent_work_board_orchestration", "Work Board"),
    )

    mapping = json.loads(pattern["openclaw_mapping_json"])
    assert pattern["pattern_category"] == "agent_orchestration"
    assert "Work Board" in mapping
    assert "Mission Control" in mapping
    assert "Mission Control Work Board Read-Only Surface v0" in recommendation["recommended_lane"]
    assert "read-only" in recommendation["next_safe_move"].lower()
    assert tuple(recommendation)[2:] == (1, 0)
    assert alignment["surface_status"] == "present"


def test_recommendation_vocabulary_and_report_queries_work(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    seen = {
        row["recommendation"]
        for row in _rows(db_path, "SELECT recommendation FROM steel_thread_signals")
    }
    report = build_steel_thread_report(db_path=db_path, report="recommendations")
    category_report = build_steel_thread_report(
        db_path=db_path,
        report="category",
        category="agent_orchestration",
    )

    assert seen <= RECOMMENDATIONS
    assert {"adopt", "adapt", "watch"} <= seen
    assert report["counts"]["signal_count"] == 3
    assert len(report["rows"]) == 3
    assert len(category_report["rows"]) == 1
    assert category_report["rows"][0]["signal_id"] == "steel_signal_agent_work_board_orchestration"
    assert _row(db_path, "SELECT COUNT(*) AS count FROM steel_thread_query_receipts")["count"] == 2


def test_work_board_card_linkage_is_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")
    fetch_steel_thread_sources(db_path=db_path, repo_root=root, run_id="feed_fixture")

    result = build_work_board(db_path=db_path, run_id="board_steel_thread")
    card = _row(
        db_path,
        """
SELECT source_kind, board_column, agent_id, approval_required,
       execution_allowed, auto_approval_allowed, auto_execute_allowed
FROM work_board_cards
WHERE source_kind = 'steel_thread_signal'
ORDER BY title
LIMIT 1
""",
    )

    assert result.card_count >= 1
    assert card["source_kind"] == "steel_thread_signal"
    assert card["board_column"] in {"planned", "deferred", "completed_with_receipt"}
    assert card["agent_id"] == "chief"
    assert card["approval_required"] == 1
    assert card["execution_allowed"] == 0
    assert card["auto_approval_allowed"] == 0
    assert card["auto_execute_allowed"] == 0


def test_no_actions_notifications_or_authority_are_created(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
    assert _row(
        db_path,
        """
SELECT COUNT(*) AS count
FROM steel_thread_signals
WHERE action_created != 0
   OR notification_sent != 0
   OR autonomous_update_allowed != 0
   OR external_api_allowed != 0
   OR web_crawl_allowed != 0
   OR model_call_allowed != 0
""",
    )["count"] == 0
    assert _row(
        db_path,
        """
SELECT COUNT(*) AS count
FROM steel_thread_recommendations
WHERE action_created != 0 OR notification_sent != 0
""",
    )["count"] == 0


def test_read_model_export_exists_and_contains_no_authority_flags(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "exports"
    root = _fixture_root(tmp_path)
    build_steel_thread_radar(db_path=db_path, repo_root=root, run_id="steel_fixture")

    summary = export_steel_thread_radar_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "steel_thread_radar.json").read_text(encoding="utf-8"))
    operator_text = (export_root / "steel_thread_radar_OPERATOR.md").read_text(encoding="utf-8")

    assert summary["signal_count"] == 3
    assert payload["signal_count"] == 3
    assert payload["high_relevance_count"] == 3
    assert payload["source_registry_count"] == 4
    assert payload["enabled_source_count"] == 2
    assert payload["url_source_enabled_count"] == 0
    assert payload["feed_item_count"] == 0
    assert "Agent work board / orchestration board pattern" in operator_text
    assert all(value is False for value in payload["no_authority_flags"].values())
    assert "Mission Control Work Board Read-Only Surface v0" in payload["recommended_next_lanes"][0]


def test_surface_read_model_projects_seed_signals_without_ledger_mutation(tmp_path):
    db_path = tmp_path / "missing" / "ledger.sqlite"
    root = _fixture_root(tmp_path)

    payload = build_steel_thread_surface_read_model(
        db_path=db_path,
        repo_root=root,
        generated_at="test_generated_at",
    )
    operator_text = format_operator_steel_thread_read_model(payload)

    assert not db_path.exists()
    assert payload["surface_mode"] == "manual_seed_projection"
    assert payload["projection_basis"] == "steel_thread_seed_signals"
    assert payload["source_state_read_only"] is True
    assert payload["generated_at"] == "test_generated_at"
    assert payload["signal_count"] == 3
    assert payload["high_relevance_count"] == 3
    assert any(
        "Mission Control Work Board Read-Only Surface v0" in lane
        for lane in payload["recommended_next_lanes"]
    )
    assert {signal["signal_id"] for signal in payload["signals"]} == {
        "steel_signal_agent_work_board_orchestration",
        "steel_signal_external_ai_context_packs",
        "steel_signal_helm_control_path_maturity",
    }
    assert "Agent work board / orchestration board pattern" in operator_text
    assert all(value is False for value in payload["no_authority_flags"].values())


def test_scripts_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "exports"

    assert build_main(["--db", str(db_path), "--run-id", "steel_script", "--format", "operator"]) == 0
    assert "Steel Thread Frontier Radar v0" in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"]) == 0
    assert "Signals: 3" in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--category", "agent_orchestration", "--format", "operator"]) == 0
    assert "agent_orchestration" in capsys.readouterr().out

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    assert "Steel Thread Radar Read-Model Export v0" in capsys.readouterr().out
    assert (export_root / "steel_thread_radar.json").exists()
    assert (export_root / "steel_thread_radar_OPERATOR.md").exists()

    assert fetch_main(["--db", str(db_path), "--run-id", "feed_script", "--format", "operator"]) == 0
    assert "Steel Thread Frontier Source Intake v0" in capsys.readouterr().out


def test_static_boundaries_no_web_model_api_or_execution(tmp_path):
    paths = [
        "steel_thread_radar.py",
        "scripts/build_steel_thread_radar.py",
        "scripts/query_steel_thread_radar.py",
        "scripts/export_steel_thread_radar_read_model.py",
        "scripts/fetch_steel_thread_sources.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8").lower() for path in paths)
    tree = ast.parse(Path("steel_thread_radar.py").read_text(encoding="utf-8"))
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules.isdisjoint(
        {
            "requests",
            "httpx",
            "socket",
            "subprocess",
            "os",
            "paramiko",
        }
    )
    assert called_names.isdisjoint({"system", "run", "popen", "post"})
    forbidden = [
        "requests",
        "httpx",
        "import socket",
        "subprocess.",
        "shell=true",
        "os.system",
        "paramiko",
        "scp ",
        "rsync",
        "ssh ",
        "docker",
        "ollama",
        "pip install",
        "apt install",
        "npm install",
        "telegram api",
    ]
    assert not any(token in text for token in forbidden)
    db_path = tmp_path / "ledger.sqlite"
    build_steel_thread_radar(db_path=db_path, repo_root=_fixture_root(tmp_path), run_id="steel_static")
    read_model = build_steel_thread_read_model(db_path)
    assert "no_authority_flags" in read_model
