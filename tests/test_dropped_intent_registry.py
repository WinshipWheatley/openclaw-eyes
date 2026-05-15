import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from dropped_intent_registry import (
    NO_AUTHORITY_FLAGS,
    build_dropped_intent_registry,
    build_dropped_intent_report,
    build_dropped_intents_read_model,
    dropped_intent_table_names,
    export_dropped_intents_read_model,
    init_dropped_intent_schema,
)
from markdown_knowledge_atlas import build_markdown_knowledge_atlas
from scripts.build_dropped_intent_registry import main as build_main
from scripts.export_dropped_intents_read_model import main as export_main
from scripts.query_dropped_intents import main as query_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "OPENCLAW_RUNTIME.md", "# Runtime\n")
    _write(root / "USER.md", "# User\n")
    _write(root / "CORE_ARCHITECTURE_PRINCIPLES.md", "# Architecture\n")
    _write(root / "AGENTS.md", "# Adapter\n")
    _write(
        root / "docs" / "operations" / "OPENCLAW_SUBSTRATE_MISSION_CONTROL_CHECKPOINT_V1.md",
        "\n".join(
            [
                "# Checkpoint",
                "Mission Control remains read-only and has no action buttons.",
                "Mission Control System Layers now show substrate read models.",
                "Recommended next lane: Project Capsule v0.1 / Real Template Workflow.",
                "Alternate next lane: Legacy GitHub Repo Intake v0.1.",
                "We should build Mission Control action request writing later.",
            ]
        ),
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_OPERATOR_ACTION_INBOX_V0.md",
        "# Inbox\nMission Control drafts request JSON later.\nTelegram metadata future only; no Telegram API is wired.\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_FILE_EVENT_QUEUE_V0.md",
        "# File queue\nFile Event Queue is snapshot-based, not a daemon.\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_SAFE_IDEA.md",
        "# Safe idea\nWe should build a small operator status explainer later.\n",
    )
    _write(
        root / "docs" / "operations" / "SECRET_DO_NOT_FORGET.md",
        "# Secret\nDo not forget the private credential workflow.\n",
    )
    _write(root / ".ssh" / "private_directions.md", "# no-go\nI want this private thing.\n")
    _write(root / "file_event_queue.py", "# marker for built file queue\n")
    _write(
        root / "generated" / "read_models" / "agent_lanes.json",
        json.dumps(
            {
                "source_kind_posture": {
                    "telegram": "metadata only; no Telegram API, polling, or sending wired"
                },
                "agents": [
                    {
                        "agent_id": "niles",
                        "notes": "Producer and Creative File Resolver are aliases for Niles unless a future lane justifies a separate role.",
                    }
                ],
            }
        ),
    )
    _write(
        root / "generated" / "read_models" / "intent_router.json",
        json.dumps(
            {
                "routing_rules_summary": {
                    "logic_or_music_file_requests": "Niles resolves recent file metadata only."
                }
            }
        ),
    )
    _write(
        root / "generated" / "context_packets" / "context_packet_latest.md",
        "# Packet\nFuture lane: recent file context resolver for that new file.\n",
    )
    return root


def _build_fixture(tmp_path: Path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    hashed: list[str] = []

    def hash_reader(path: Path) -> str:
        relative = path.relative_to(root).as_posix()
        hashed.append(relative)
        assert ".ssh/" not in relative
        assert "SECRET_DO_NOT_FORGET" not in relative
        return "hash-" + relative.replace("/", "_")

    run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id="corpus_dropped_fixture",
        hash_reader=hash_reader,
    )
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_dropped_fixture")
    result = build_dropped_intent_registry(
        db_path=db_path,
        repo_root=root,
        run_id="dropped_fixture",
    )
    return root, db_path, result, hashed


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
    tables = set(dropped_intent_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "dropped_intent_runs",
        "dropped_intents",
        "dropped_intent_evidence_links",
        "dropped_intent_status_links",
        "dropped_intent_resolution_candidates",
        "dropped_intent_query_receipts",
    } <= tables


def test_build_is_idempotent_and_records_safe_candidates(tmp_path):
    root, db_path, first, _ = _build_fixture(tmp_path)
    second = build_dropped_intent_registry(
        db_path=db_path,
        repo_root=root,
        run_id="dropped_fixture",
    )

    assert first.run_id == second.run_id
    assert first.total_count == second.total_count
    assert _row(db_path, "SELECT COUNT(*) AS count FROM dropped_intent_runs")["count"] == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM dropped_intents")["count"] == first.total_count
    assert first.counts_by_status["unresolved"] >= 1
    assert first.counts_by_status["deferred"] >= 1


def test_detects_candidates_from_safe_fixture_markdown(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    rows = _rows(
        db_path,
        """
SELECT title, source_path, current_status
FROM dropped_intents
WHERE original_text_excerpt LIKE '%operator status explainer%'
""",
    )

    assert rows
    assert rows[0]["source_path"] == "docs/operations/OPENCLAW_SAFE_IDEA.md"
    assert rows[0]["current_status"] in {"deferred", "unresolved"}


def test_statuses_classify_built_deferred_and_unresolved(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    mission_refresh = _row(
        db_path,
        "SELECT current_status FROM dropped_intents WHERE title = ?",
        ("Mission Control read-model refresh",),
    )
    project_capsule = _row(
        db_path,
        "SELECT current_status FROM dropped_intents WHERE title = ?",
        ("Project Capsule v0.1 / Real Template Workflow",),
    )
    request_writer = _row(
        db_path,
        "SELECT current_status FROM dropped_intents WHERE title = ?",
        ("Mission Control action request writing",),
    )

    assert mission_refresh["current_status"] == "built"
    assert project_capsule["current_status"] == "deferred"
    assert request_writer["current_status"] == "unresolved"


def test_no_go_private_docs_are_excluded_and_raw_bodies_are_not_stored(tmp_path):
    _, db_path, _, hashed = _build_fixture(tmp_path)

    assert ".ssh/private_directions.md" not in hashed
    assert "docs/operations/SECRET_DO_NOT_FORGET.md" not in hashed
    assert _row(
        db_path,
        """
SELECT COUNT(*) AS count
FROM dropped_intents
WHERE COALESCE(source_path, '') LIKE '%SECRET%'
   OR COALESCE(source_path, '') LIKE '%.ssh/%'
""",
    )["count"] == 0
    assert _row(
        db_path,
        """
SELECT COUNT(*) AS count
FROM dropped_intents
WHERE raw_body_stored != 0 OR action_created != 0 OR notification_sent != 0
""",
    )["count"] == 0


def test_no_notifications_actions_or_execution_are_created(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    assert _row(db_path, "SELECT COUNT(*) FROM operator_action_requests")[0] == 0
    assert tuple(
        _row(
        db_path,
        """
SELECT action_created, notification_sent, execution_allowed,
       agent_activation_allowed, network_authority, model_call_allowed,
       raw_private_scan_allowed, file_move_allowed, file_delete_allowed
FROM dropped_intent_runs
WHERE run_id = 'dropped_fixture'
""",
        )
    ) == (0, 0, 0, 0, 0, 0, 0, 0, 0)


def test_read_model_export_and_reports_work(tmp_path, capsys):
    _, db_path, _, _ = _build_fixture(tmp_path)
    export_root = tmp_path / "read_models"

    summary = export_dropped_intents_read_model(db_path=db_path, export_root=export_root)
    read_model = build_dropped_intents_read_model(db_path=db_path)

    assert (export_root / "dropped_intents.json").is_file()
    assert (export_root / "dropped_intents_OPERATOR.md").is_file()
    assert summary["total_count"] == read_model["total_count"]
    assert read_model["unresolved_count"] >= 1
    assert read_model["deferred_count"] >= 1
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value

    assert query_main(["--db", str(db_path), "--report", "unresolved", "--format", "operator"]) == 0
    assert "Dropped Intent Registry v0 - unresolved" in capsys.readouterr().out
    assert query_main(["--db", str(db_path), "--agent", "chief", "--format", "operator"]) == 0
    assert "chief" in capsys.readouterr().out
    assert query_main(["--db", str(db_path), "--world", "build", "--format", "operator"]) == 0
    assert "Dropped Intent Registry v0" in capsys.readouterr().out
    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["json_path"].endswith("dropped_intents.json")


def test_build_script_exports_read_model(tmp_path, capsys):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    rc = build_main(
        [
            "--db",
            str(db_path),
            "--repo-root",
            str(root),
            "--run-id",
            "script_fixture",
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["total_count"] >= 9
    assert (export_root / "dropped_intents.json").is_file()


def test_recent_file_resolver_unresolved_while_file_event_queue_is_built(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    row = _row(
        db_path,
        """
SELECT current_status, evidence_basis
FROM dropped_intents
WHERE title = 'Recent File Context Resolver'
""",
    )

    assert row["current_status"] == "unresolved"
    assert "File Event Queue exists" in row["evidence_basis"]


def test_telegram_bridge_deferred_while_source_metadata_exists(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    row = _row(
        db_path,
        """
SELECT current_status, evidence_basis
FROM dropped_intents
WHERE title = 'Telegram Chief Bridge'
""",
    )

    assert row["current_status"] == "deferred"
    assert "source metadata only" in row["evidence_basis"]


def test_static_forbids_for_dropped_intent_lane():
    source_files = [
        Path("dropped_intent_registry.py"),
        Path("scripts/build_dropped_intent_registry.py"),
        Path("scripts/query_dropped_intents.py"),
        Path("scripts/export_dropped_intents_read_model.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_files)
    forbidden = [
        "subprocess",
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "docker run",
        "ollama run",
        "ollama pull",
        "ssh ",
        "scp ",
        "rsync",
        "apt install",
        "npm install",
        "pip install",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
    ]
    for token in forbidden:
        assert token not in text
