import hashlib
import json
from pathlib import Path

import pytest

from report_bridge import (
    DEFAULT_REPORT_BRIDGE_INBOX,
    MANIFEST_NAME,
    NO_AUTHORITY_FLAGS,
    REPORT_BRIDGE_SCHEMA_VERSION,
    build_report_bridge_report,
    import_report_bridge_package,
    init_report_bridge_schema,
    report_bridge_table_names,
    resolve_report_bridge_package,
    stable_json,
)
from scripts.import_report_bridge_package import main as import_main
from scripts.query_report_bridge import main as query_main


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_package(root: Path, *, package_id: str = "rb_pkg_demo") -> Path:
    package = root / package_id
    read_model = package / "payload" / "read_models" / "context_selection.json"
    report = package / "payload" / "reports" / "node_status_OPERATOR.md"
    _write(read_model, '{"context": "selected evidence only"}\n')
    _write(report, "# Node Status\n\nNo authority granted.\n")
    _write(package / "README_NODE_UPLINK.md", "Synthetic package fixture.\n")
    files = [
        {
            "relative_path": "payload/read_models/context_selection.json",
            "size": read_model.stat().st_size,
            "sha256": _sha256(read_model),
            "role": "read_model",
            "sensitivity_label": "internal_project",
            "raw_content_eligibility": "metadata_only",
            "retrieval_eligibility": "retrievable",
            "ingestion_eligibility": "metadata_only",
            "evidence_category": "context_gate",
        },
        {
            "relative_path": "payload/reports/node_status_OPERATOR.md",
            "size": report.stat().st_size,
            "sha256": _sha256(report),
            "role": "operator_report",
            "sensitivity_label": "internal_project",
            "raw_content_eligibility": "metadata_only",
            "retrieval_eligibility": "retrievable",
            "ingestion_eligibility": "metadata_only",
            "evidence_category": "operator_status",
        },
    ]
    manifest = {
        "schema_version": REPORT_BRIDGE_SCHEMA_VERSION,
        "package_id": package_id,
        "generated_at": "2026-05-14T22:30:00+00:00",
        "node_id": "demo_node_wsl",
        "node_kind": "pc_wsl",
        "owner_scope": "internal_demo",
        "project_id": "demo_project_capsule_v0",
        "client_id": "demo_client",
        "package_kind": "node_report_package",
        "source_root_id": "pc_wsl_home_openclaw",
        "files": files,
        "sensitivity_summary": {"internal_project": 2, "no_go": 0},
        "allowed_data_classes": ["generated_read_model", "operator_report_metadata"],
        "forbidden_data_classes": ["raw_private_bodies", "real_client_data", "credentials"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        "raw_body_included": False,
        "client_data_included": False,
    }
    _write(package / MANIFEST_NAME, stable_json(manifest))
    return package


def test_schema_initializes(tmp_path):
    tables = set(report_bridge_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "report_bridge_runs",
        "report_bridge_packages",
        "report_bridge_files",
        "report_bridge_nodes",
        "report_bridge_projects",
        "report_bridge_import_receipts",
        "report_bridge_rejections",
    } <= tables


def test_valid_package_imports_metadata_and_reports(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    package = _valid_package(tmp_path / "inbox")

    result = import_report_bridge_package(
        package=package,
        db_path=db_path,
        run_id="report_bridge_fixture_run",
    )

    assert result.status == "imported"
    assert result.package_id == "rb_pkg_demo"
    assert result.imported_file_count == 2
    assert result.raw_body_included is False
    assert result.client_data_included is False
    assert result.truth_promotion_allowed is False

    report = build_report_bridge_report(db_path=db_path, report="summary")
    assert report["counts"]["packages"] == 1
    assert report["counts"]["files"] == 2
    assert report["counts"]["file_roles"] == {"operator_report": 1, "read_model": 1}

    query_main(["--db", str(db_path), "--report", "latest", "--format", "operator"])
    output = capsys.readouterr().out
    assert "Report Bridge v0 - latest" in output
    assert "rb_pkg_demo" in output

    import_main(
        [
            "--db",
            str(db_path),
            "--package",
            str(package),
            "--run-id",
            "report_bridge_cli_run",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_id"] == "rb_pkg_demo"
    assert payload["runtime_authority"] is False


def test_hashes_are_verified(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    package = _valid_package(tmp_path / "inbox")
    payload = package / "payload" / "read_models" / "context_selection.json"
    original_size = payload.stat().st_size
    payload.write_text("x" * original_size, encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        import_report_bridge_package(package=package, db_path=db_path, run_id="bad_hash")

    report = build_report_bridge_report(db_path=db_path, report="rejected")
    assert report["counts"]["rejections"] == 1
    assert report["items"][0]["rejection_type"] == "package_validation_failed"


def test_authority_flags_must_be_false(tmp_path):
    package = _valid_package(tmp_path / "inbox")
    manifest_path = package / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["no_authority_flags"]["network_authority"] = True
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="network_authority"):
        import_report_bridge_package(package=package, db_path=tmp_path / "ledger.sqlite")


def test_raw_bodies_and_client_data_rejected_by_default(tmp_path):
    package = _valid_package(tmp_path / "raw_inbox", package_id="raw_body_pkg")
    manifest_path = package / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["raw_body_included"] = True
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="raw bodies"):
        import_report_bridge_package(package=package, db_path=tmp_path / "raw.sqlite")

    client_package = _valid_package(tmp_path / "client_inbox", package_id="client_data_pkg")
    client_manifest_path = client_package / MANIFEST_NAME
    manifest = json.loads(client_manifest_path.read_text(encoding="utf-8"))
    manifest["client_data_included"] = True
    client_manifest_path.write_text(stable_json(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="client data"):
        import_report_bridge_package(package=client_package, db_path=tmp_path / "client.sqlite")


def test_no_truth_promotion_occurs(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    package = _valid_package(tmp_path / "inbox")

    import_report_bridge_package(package=package, db_path=db_path)

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        truth_count = conn.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
        promoted = conn.execute(
            "SELECT COUNT(*) FROM report_bridge_packages WHERE truth_promotion_allowed != 0"
        ).fetchone()[0]
    finally:
        conn.close()
    assert truth_count == 0
    assert promoted == 0


def test_default_inbox_uses_e_drive_and_resolves_latest_package(tmp_path):
    assert DEFAULT_REPORT_BRIDGE_INBOX.as_posix() == "/mnt/e/openclaw/node_uplink/inbox"
    assert not DEFAULT_REPORT_BRIDGE_INBOX.as_posix().startswith("/mnt/c/openclaw")

    inbox = tmp_path / "inbox"
    package = _valid_package(inbox, package_id="latest_pkg")
    resolved = resolve_report_bridge_package(inbox=inbox)
    assert resolved == package


def test_static_forbids_for_report_bridge_lane():
    paths = [
        Path("report_bridge.py"),
        Path("scripts/import_report_bridge_package.py"),
        Path("scripts/query_report_bridge.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    forbidden = [
        "import subprocess",
        "shell=true",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "import paramiko",
        "rsync",
        "scp ",
        '["ssh"',
        "git clone",
        "git push",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        "docker run",
        "ollama run",
        "ollama pull",
    ]
    for token in forbidden:
        assert token not in text
