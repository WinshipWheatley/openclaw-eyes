import json
from pathlib import Path

from project_capsule import create_demo_project_capsule
from scripts.export_project_capsule_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_project_capsule_read_model,
    export_project_capsule_read_model,
    main,
)


def test_project_capsule_read_model_is_generated(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")

    summary = export_project_capsule_read_model(
        db_path=db_path,
        export_root=export_root,
        run_id="pcap_fixture",
    )

    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["capsule_count"] == 1
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["demo_capsule"]["project_id"] == "demo_project_capsule_v0"
    assert payload["demo_capsule"]["project_name"] == "Demo Client Operations Helper"
    assert payload["real_client_data_present"] is False
    assert payload["approval_status"] == "not_approved"
    assert all(value is False for value in payload["authority_flags"].values())
    assert "not deployment" in operator_path.read_text(encoding="utf-8")

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "pcap_fixture",
            "--export-root",
            str(export_root),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    cli_summary = json.loads(capsys.readouterr().out)
    assert cli_summary["json_path"].endswith(JSON_EXPORT_NAME)


def test_read_model_empty_state_is_non_authorizing(tmp_path):
    payload = build_project_capsule_read_model(db_path=tmp_path / "ledger.sqlite")

    assert payload["capsule_count"] == 0
    assert payload["demo_capsule"] is None
    assert payload["real_client_data_present"] is False
    assert all(value is False for value in payload["authority_flags"].values())


def test_read_model_sources_do_not_claim_forbidden_behavior():
    source_files = [Path("scripts/export_project_capsule_read_model.py")]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "docker run",
        "ollama run",
        "git clone",
        "pip install",
        "npm install",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text
