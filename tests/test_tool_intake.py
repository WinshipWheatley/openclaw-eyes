import json
import sqlite3
from pathlib import Path

import tool_intake
from scripts.query_tool_intake import main as query_main
from tool_intake import (
    DEFAULT_CANDIDATE_SEEDS,
    build_tool_intake_report,
    query_tool_intake_report_section,
    seed_tool_intake_registry,
    tool_intake_table_names,
)
from tool_inventory import DEFAULT_TOOL_SPECS, ProbeResult, ToolCommand, run_tool_inventory


def _specs(*tool_ids):
    wanted = set(tool_ids)
    return tuple(spec for spec in DEFAULT_TOOL_SPECS if spec.tool_id in wanted)


def _resolver(installed_names):
    installed = set(installed_names)

    def resolve(name: str):
        return f"/usr/bin/{name}" if name in installed else None

    return resolve


def _runner(command: ToolCommand):
    tool_name = Path(command.args[0]).name
    versions = {
        "docker": "Docker version fixture\n",
        "ollama": "ollama version is fixture\n",
    }
    return ProbeResult(True, True, False, 0, versions.get(tool_name, "version fixture\n"), "")


def _inventory_fixture(db_path: Path):
    run_tool_inventory(
        db_path=db_path,
        run_id="inventory_fixture",
        tool_specs=_specs(
            "docker",
            "ollama",
            "datasette",
            "sqlite_utils",
            "litestream",
            "sqlite3",
            "syncthing",
            "pocketbase",
            "llama_cpp",
        ),
        executable_resolver=_resolver({"docker", "ollama"}),
        command_runner=_runner,
    )


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


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "tool_intake_runs",
        "tool_candidates",
        "tool_candidate_labels",
        "tool_candidate_use_cases",
        "tool_candidate_risks",
        "tool_candidate_inventory_links",
        "tool_candidate_status_history",
    } <= set(tool_intake_table_names(db_path))


def test_seed_is_idempotent_and_candidate_count_is_deterministic(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)

    first = seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")
    second = seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    assert first.candidate_count == len(DEFAULT_CANDIDATE_SEEDS)
    assert second.candidate_count == len(DEFAULT_CANDIDATE_SEEDS)
    assert _row(db_path, "SELECT COUNT(*) FROM tool_candidates")[0] == len(DEFAULT_CANDIDATE_SEEDS)
    assert _row(db_path, "SELECT COUNT(*) FROM tool_candidates WHERE tool_id = 'ollama'")[0] == 1


def test_candidates_are_not_approved_or_integrated(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_candidates WHERE integration_status != 'not_integrated'",
    )[0] == 0
    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_candidates WHERE approval_status != 'not_approved'",
    )[0] == 0
    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM tool_candidates
WHERE install_status = 'observed_installed'
  AND (approval_status != 'not_approved' OR integration_status != 'not_integrated')
""",
    )[0] == 0


def test_high_risk_tools_require_operator_review(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    assert _row(
        db_path,
        "SELECT COUNT(*) FROM tool_candidates WHERE risk_level = 'high' AND requires_operator_review != 1",
    )[0] == 0
    installed_high_risk = {
        row[0]
        for row in _rows(
            db_path,
            """
SELECT tool_id
FROM tool_candidates
WHERE risk_level = 'high' AND install_status = 'observed_installed'
""",
        )
    }
    assert installed_high_risk == {"docker", "ollama"}


def test_unknown_url_license_and_install_command_are_not_guessed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM tool_candidates
WHERE official_url IS NOT NULL OR license IS NOT NULL OR install_command IS NOT NULL
""",
    )[0] == 0


def test_inventory_links_work_for_detected_and_not_detected_tools(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    linked = {
        row[0]: row[1]
        for row in _rows(
            db_path,
            """
SELECT c.tool_id, c.install_status
FROM tool_candidates c
JOIN tool_candidate_inventory_links l ON l.candidate_id = c.candidate_id
WHERE c.tool_id IN ('docker','ollama','datasette','sqlite_utils','litestream','sqlite3')
ORDER BY c.tool_id
""",
        )
    }
    assert linked == {
        "datasette": "not_detected",
        "docker": "observed_installed",
        "litestream": "not_detected",
        "ollama": "observed_installed",
        "sqlite3": "not_detected",
        "sqlite_utils": "not_detected",
    }


def test_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    _inventory_fixture(db_path)
    seed_tool_intake_registry(db_path=db_path, run_id="intake_fixture")

    summary = build_tool_intake_report(db_path=db_path, run_id="intake_fixture")
    sqlite_report = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="category",
        category="sqlite_exploration",
    )
    high_fit = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="high-fit",
    )
    high_risk = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="high-risk",
    )
    sandbox = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="sandbox-later",
    )
    client_capsule = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="client-capsule",
    )
    installed = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="installed-candidates",
    )
    not_detected = query_tool_intake_report_section(
        db_path=db_path,
        run_id="intake_fixture",
        section="not-detected-candidates",
    )

    assert summary["run"]["candidate_count"] == len(DEFAULT_CANDIDATE_SEEDS)
    assert {item["tool_id"] for item in sqlite_report["items"]} == {
        "datasette",
        "sqlite3",
        "sqlite_utils",
    }
    assert {"datasette", "sqlite_utils", "litestream", "copier", "devbox"} <= {
        item["tool_id"] for item in high_fit["items"]
    }
    assert {"docker", "ollama", "ansible", "sops", "wireguard"} <= {
        item["tool_id"] for item in high_risk["items"]
    }
    assert {"syncthing", "caddy", "netdata", "uptime_kuma", "llama_cpp"} <= {
        item["tool_id"] for item in sandbox["items"]
    }
    assert {"pocketbase", "copier"} <= {item["tool_id"] for item in client_capsule["items"]}
    assert {item["tool_id"] for item in installed["items"]} == {"docker", "ollama"}
    assert {"datasette", "sqlite_utils", "litestream", "sqlite3"} <= {
        item["tool_id"] for item in not_detected["items"]
    }

    exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "intake_fixture",
            "--report",
            "high-risk",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["section"] == "high-risk"

    summary_exit_code = query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "intake_fixture",
            "--report",
            "summary",
            "--format",
            "operator",
        ]
    )
    assert summary_exit_code == 0
    assert "Tool Intake Registry v0" in capsys.readouterr().out


def test_no_external_network_or_subprocess_behavior_in_lane_sources():
    source_files = [
        Path(tool_intake.__file__),
        Path("scripts/build_tool_intake.py"),
        Path("scripts/query_tool_intake.py"),
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
