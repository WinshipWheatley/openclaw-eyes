import json
import sqlite3
from pathlib import Path

from agent_lane_registry import seed_agent_lane_registry
from file_event_queue import build_file_event_snapshot
from recent_file_context import build_recent_file_context
from intent_router import (
    NO_AUTHORITY_FLAGS,
    build_intent_router_read_model,
    export_intent_router_read_model,
    format_intent_router_read_model,
    init_intent_router_schema,
    intent_router_table_names,
    route_operator_intent,
)
from scripts.export_intent_router_read_model import main as export_main
from scripts.query_intent_router import main as query_main
from scripts.route_operator_intent import main as route_main


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
    tables = set(intent_router_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "intent_router_runs",
        "intent_records",
        "intent_route_candidates",
        "intent_context_links",
        "intent_plan_proposals",
        "intent_router_rejections",
        "intent_router_receipts",
    } <= tables


def test_route_command_creates_intent_record_and_no_action(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    exit_code = route_main(
        [
            "--db",
            str(db_path),
            "--text",
            "Chief, refresh the read-model mirror.",
            "--source-kind",
            "cli",
            "--source-channel",
            "local_terminal",
            "--requested-by",
            "operator",
            "--intent-id",
            "intent_cli_refresh",
            "--run-id",
            "intent_run_fixture",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["intent_id"] == "intent_cli_refresh"
    assert payload["routed_agent_id"] == "chief"
    assert payload["intent_category"] == "read_model_refresh_request"
    assert payload["candidate_action_type"] == "prepare_mac_read_model_shuttle"
    assert payload["action_request_created"] is False
    assert payload["execution_allowed"] is False
    assert _row(db_path, "SELECT COUNT(*) FROM operator_action_requests")[0] == 0


def test_explicit_agent_routes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    cases = [
        ("Chief, organize my Markdown files.", "chief", "system_orchestration", "markdown_reorg_request", "operations"),
        ("Niles, do something with that new Logic file.", "niles", "music_art_production", "file_context_request", "music_art"),
        ("Producer, help with this Logic session.", "niles", "music_art_production", "file_context_request", "music_art"),
        ("Guardian, is this safe?", "guardian", "safety_security", "safety_review_request", "security"),
        ("Cassandra, summarize what changed.", "cassandra", "operator_comms", "communication_summary_request", "communications"),
        ("Report Bridge, import report package metadata.", "report_bridge", "node_report_intake", "report_bridge_request", "operations"),
    ]

    for index, (text, agent, lane, category, world) in enumerate(cases):
        result = route_operator_intent(
            text=text,
            source_kind="cli",
            source_channel="test",
            requested_by="operator",
            db_path=db_path,
            intent_id=f"intent_case_{index}",
            run_id=f"run_case_{index}",
        )
        assert result.routed_agent_id == agent
        assert result.routed_lane_id == lane
        assert result.intent_category == category
        assert result.world_hint == world
        assert result.action_request_created is False
        assert result.execution_allowed is False


def test_unknown_ambiguous_intent_needs_review(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = route_operator_intent(
        text="Handle that thing later.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_unknown",
        run_id="run_unknown",
    )

    assert result.status == "needs_operator_review"
    assert result.routed_agent_id is None
    assert result.intent_category == "unknown_review"
    assert result.confidence < 0.5


def test_that_new_file_without_recent_context_is_not_guessed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = route_operator_intent(
        text="Niles, do something with that new Logic file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_no_file_context",
        run_id="run_no_file_context",
    )
    row = _row(db_path, "SELECT routing_reason FROM intent_records WHERE intent_id = ?", (result.intent_id,))

    assert result.routed_agent_id == "niles"
    assert result.status == "needs_operator_review"
    assert "unresolved" in row["routing_reason"]
    assert _row(db_path, "SELECT COUNT(*) FROM intent_context_links WHERE intent_id = ?", (result.intent_id,))[0] == 0


def test_intent_intake_refines_dictation_before_operator_surfaces(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    raw_text = "Niles, do something with that new Logic file."

    result = route_operator_intent(
        text=raw_text,
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_anti_launder",
        run_id="run_anti_launder",
    )
    row = _row(
        db_path,
        """
SELECT refined_actor, refined_verb, refined_object, refined_status,
       refined_as_of, provenance_raw, provenance_raw_sha256,
       needs_operator_review, refinement_status, operator_display
FROM intent_records
WHERE intent_id = ?
""",
        (result.intent_id,),
    )
    read_model = build_intent_router_read_model(db_path=db_path)
    rendered = format_intent_router_read_model(read_model)

    assert row["refined_actor"] == "Niles"
    assert row["refined_verb"] == "review"
    assert row["refined_object"] == "new Logic file"
    assert row["refined_status"] == "needs_operator_review"
    assert row["refined_as_of"]
    assert row["provenance_raw"] == raw_text
    assert len(row["provenance_raw_sha256"]) == 64
    assert row["needs_operator_review"] == 1
    assert row["refinement_status"] == "needs_operator_review"
    assert row["operator_display"] == "Niles request about new Logic file needs operator review."
    assert read_model["latest_intent"]["operator_display"] == row["operator_display"]
    assert raw_text not in rendered
    assert "Intent: Niles, do something" not in rendered
    assert "Niles request about new Logic file needs operator review." in rendered


def test_file_context_links_recent_logic_metadata_without_raw_reads(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "song.logicx").mkdir()
    (root / "song.logicx" / "projectData").write_text("not read by router\n", encoding="utf-8")

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
    )
    build_recent_file_context(db_path=db_path, run_id="recent_file_run")

    result = route_operator_intent(
        text="Niles, do something with that new Logic file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_file_context",
        run_id="run_file_context",
    )
    links = _rows(
        db_path,
        """
SELECT link_kind, source_table, source_path, raw_content_read, raw_body_stored
FROM intent_context_links
WHERE intent_id = ?
""",
        (result.intent_id,),
    )

    assert result.routed_agent_id == "niles"
    assert result.status == "routed"
    assert links
    assert links[0]["link_kind"] == "recent_file_context_candidate"
    assert links[0]["source_table"] == "recent_file_candidates"
    assert links[0]["source_path"] == "song.logicx"
    assert links[0]["raw_content_read"] == 0
    assert links[0]["raw_body_stored"] == 0


def test_generic_new_file_can_route_to_niles_from_recent_logic_context(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "song.logicx").mkdir()
    (root / "song.logicx" / "projectData").write_text("not read by router\n", encoding="utf-8")

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
    )
    build_recent_file_context(db_path=db_path, run_id="recent_file_run")

    result = route_operator_intent(
        text="Do something with that new file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_generic_logic_context",
        run_id="run_generic_logic_context",
    )

    assert result.routed_agent_id == "niles"
    assert result.routed_lane_id == "music_art_production"
    assert result.status == "routed"
    assert result.context_link_count == 1


def test_ambiguous_recent_file_context_remains_needs_review(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "song.logicx").mkdir()
    (root / "other.logicx").mkdir()

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
    )
    build_recent_file_context(db_path=db_path, run_id="recent_file_run")

    result = route_operator_intent(
        text="Niles, do something with the new Logic file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_ambiguous_logic_context",
        run_id="run_ambiguous_logic_context",
    )

    assert result.routed_agent_id == "niles"
    assert result.status == "needs_operator_review"
    assert result.context_link_count == 0


def test_markdown_file_request_links_recent_context(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "new_doc.md").write_text("# New\n", encoding="utf-8")

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
    )
    build_recent_file_context(db_path=db_path, run_id="recent_file_run")

    result = route_operator_intent(
        text="Chief, organize that new Markdown file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_markdown_file_context",
        run_id="run_markdown_file_context",
    )
    link = _row(
        db_path,
        """
SELECT link_kind, source_table, source_path, raw_content_read, raw_body_stored
FROM intent_context_links
WHERE intent_id = ? AND link_kind = 'recent_file_context_candidate'
""",
        (result.intent_id,),
    )

    assert result.routed_agent_id == "chief"
    assert result.status == "routed"
    assert tuple(link) == ("recent_file_context_candidate", "recent_file_candidates", "new_doc.md", 0, 0)


def test_markdown_reorg_does_not_move_files_or_create_action(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_markdown",
        run_id="run_markdown",
    )
    row = _row(
        db_path,
        """
SELECT file_move_allowed, file_delete_allowed, action_request_created,
       execution_allowed, next_safe_move
FROM intent_records
WHERE intent_id = ?
""",
        (result.intent_id,),
    )

    assert result.routed_agent_id == "chief"
    assert result.intent_category == "markdown_reorg_request"
    assert tuple(row[:4]) == (0, 0, 0, 0)
    assert "do not move files" in row["next_safe_move"].lower()
    assert _row(db_path, "SELECT COUNT(*) FROM operator_action_requests")[0] == 0


def test_source_kinds_route_as_metadata_and_do_not_bypass_approval(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    for source_kind in ("mission_control", "telegram", "cli", "report_bridge", "future_client_node"):
        result = route_operator_intent(
            text="Guardian, is this safe?",
            source_kind=source_kind,
            source_channel=f"{source_kind}_channel",
            requested_by=source_kind,
            db_path=db_path,
            intent_id=f"intent_{source_kind}",
            run_id=f"run_{source_kind}",
        )
        assert result.routed_agent_id == "guardian"
        assert result.approval_required is True
        assert result.execution_allowed is False
        assert result.action_request_created is False

    rows = _rows(
        db_path,
        """
SELECT source_kind, approval_required, execution_allowed, action_request_created,
       raw_text_stored, agent_activation_allowed, approval_bypass_allowed
FROM intent_records
ORDER BY source_kind
""",
    )
    assert {row["source_kind"] for row in rows} == {
        "mission_control",
        "telegram",
        "cli",
        "report_bridge",
        "future_client_node",
    }
    assert all(tuple(row[1:]) == (1, 0, 0, 0, 0, 0) for row in rows)


def test_router_validates_agent_lane_registry_authority_flags(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE agent_lanes SET can_execute = 1 WHERE agent_id = 'chief'")
        conn.commit()
    finally:
        conn.close()

    result = route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_bad_agent",
        run_id="run_bad_agent",
    )

    assert result.status == "rejected"
    assert "unsafe authority" in result.rejection_reason


def test_read_model_export_and_queries_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    route_operator_intent(
        text="Chief, refresh report bridge read-model.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_export",
        run_id="run_export",
    )

    summary = export_intent_router_read_model(db_path=db_path, export_root=export_root)
    read_model = build_intent_router_read_model(db_path=db_path)
    json_path = export_root / "intent_router.json"
    operator_path = export_root / "intent_router_OPERATOR.md"

    assert summary["total_intents"] == 1
    assert json_path.is_file()
    assert operator_path.is_file()
    assert read_model["latest_intent"]["intent_id"] == "intent_export"
    assert read_model["latest_intent"]["candidate_action_type"] == "export_report_bridge_read_model"
    assert read_model["counts_by_agent"] == {"chief": 1}
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value
    assert "not agent activation" in operator_path.read_text(encoding="utf-8")

    assert query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"]) == 0
    assert "Intent Router v0 - summary" in capsys.readouterr().out
    assert query_main(["--db", str(db_path), "--report", "by-agent", "--agent", "chief", "--format", "operator"]) == 0
    assert "intent_export" in capsys.readouterr().out
    assert query_main(["--db", str(db_path), "--report", "needs-review", "--format", "operator"]) == 0
    assert "Intent Router v0 - needs-review" in capsys.readouterr().out

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["json_path"].endswith("intent_router.json")


def test_static_forbids_for_intent_router_lane():
    source_files = [
        Path("intent_router.py"),
        Path("scripts/route_operator_intent.py"),
        Path("scripts/query_intent_router.py"),
        Path("scripts/export_intent_router_read_model.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_files)
    forbidden = [
        "subprocess.",
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "rsync",
        "scp ",
        "ssh ",
        "docker run",
        "ollama run",
        "ollama pull",
        "apt install",
        "npm install",
        "pip install",
        "git clone",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
    ]
    for token in forbidden:
        assert token not in text
