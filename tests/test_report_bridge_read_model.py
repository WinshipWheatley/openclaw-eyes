import hashlib
import json
from pathlib import Path

import pytest

from report_bridge import MANIFEST_NAME, NO_AUTHORITY_FLAGS, REPORT_BRIDGE_SCHEMA_VERSION
from report_bridge import import_report_bridge_package, stable_json
from scripts.export_report_bridge_read_model import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_report_bridge_read_model,
    export_report_bridge_read_model,
    main,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _package(root: Path, *, package_id: str = "report_bridge_read_model_pkg") -> Path:
    package = root / package_id
    read_model = package / "payload" / "read_models" / "project_capsules.json"
    report = package / "payload" / "reports" / "capsule_status_OPERATOR.md"
    _write(read_model, '{"capsule_count": 1}\\n')
    _write(report, "# Capsule Status\\n\\nMetadata only.\\n")
    _write(package / "README_NODE_UPLINK.md", "Fixture package.\\n")
    manifest = {
        "schema_version": REPORT_BRIDGE_SCHEMA_VERSION,
        "package_id": package_id,
        "generated_at": "2026-05-14T23:00:00+00:00",
        "node_id": "fixture_client_node",
        "node_kind": "client_runtime_stub",
        "owner_scope": "internal_demo",
        "project_id": "demo_project_capsule_v0",
        "client_id": "demo_client",
        "package_kind": "node_report_package",
        "source_root_id": "client_runtime_root",
        "files": [
            {
                "relative_path": "payload/read_models/project_capsules.json",
                "size": read_model.stat().st_size,
                "sha256": _sha256(read_model),
                "role": "read_model",
                "sensitivity_label": "internal_project",
                "raw_content_eligibility": "metadata_only",
                "retrieval_eligibility": "retrievable",
                "ingestion_eligibility": "metadata_only",
                "evidence_category": "project_capsule",
            },
            {
                "relative_path": "payload/reports/capsule_status_OPERATOR.md",
                "size": report.stat().st_size,
                "sha256": _sha256(report),
                "role": "operator_report",
                "sensitivity_label": "internal_project",
                "raw_content_eligibility": "metadata_only",
                "retrieval_eligibility": "retrievable",
                "ingestion_eligibility": "metadata_only",
                "evidence_category": "operator_status",
            },
        ],
        "sensitivity_summary": {"internal_project": 2, "no_go": 0},
        "allowed_data_classes": ["generated_read_model", "operator_report_metadata"],
        "forbidden_data_classes": ["raw_private_bodies", "real_client_data", "credentials"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        "raw_body_included": False,
        "client_data_included": False,
    }
    _write(package / MANIFEST_NAME, stable_json(manifest))
    return package


def test_report_bridge_read_model_is_generated(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    package = _package(tmp_path / "inbox")
    import_report_bridge_package(package=package, db_path=db_path, run_id="rb_read_model_fixture")

    summary = export_report_bridge_read_model(db_path=db_path, export_root=export_root)

    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    assert summary["package_count"] == 1
    assert summary["accepted_package_count"] == 1
    assert summary["rejected_package_count"] == 0
    assert summary["node_count"] == 1
    assert summary["project_count"] == 1

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "report_bridge_read_model_v0"
    assert payload["package_count"] == 1
    assert payload["accepted_package_count"] == 1
    assert payload["node_count"] == 1
    assert payload["project_count"] == 1
    assert payload["latest_package_summary"]["package_id"] == "report_bridge_read_model_pkg"
    assert payload["package_kinds_represented"] == {"node_report_package": 1}
    assert payload["node_kinds_represented"] == {"client_runtime_stub": 1}
    assert payload["projects_represented"] == ["demo_project_capsule_v0"]
    assert payload["clients_represented"] == ["demo_client"]
    assert payload["report_bridge_inbox_path"] == "/mnt/e/openclaw/node_uplink/inbox"
    assert payload["accepted_packages_have_raw_bodies"] is False
    assert payload["accepted_packages_have_client_data"] is False
    assert payload["packages_with_raw_bodies_or_client_data_are_not_accepted_authority"] is True
    assert all(value is False for value in payload["authority_flags"].values())
    assert "sanitized package intake, not remote control or deployment" in operator_path.read_text(
        encoding="utf-8"
    )

    exit_code = main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"])
    assert exit_code == 0
    cli_summary = json.loads(capsys.readouterr().out)
    assert cli_summary["json_path"].endswith(JSON_EXPORT_NAME)


def test_rejected_raw_body_package_is_not_accepted_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    accepted = _package(tmp_path / "inbox", package_id="accepted_pkg")
    import_report_bridge_package(package=accepted, db_path=db_path, run_id="accepted_run")

    rejected = _package(tmp_path / "bad_inbox", package_id="raw_body_pkg")
    manifest_path = rejected / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["raw_body_included"] = True
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="raw bodies"):
        import_report_bridge_package(package=rejected, db_path=db_path, run_id="rejected_run")

    payload = build_report_bridge_read_model(db_path=db_path)

    assert payload["accepted_package_count"] == 1
    assert payload["rejected_package_count"] == 1
    assert payload["latest_rejection_summary"]["rejection_type"] == "package_validation_failed"
    assert payload["accepted_packages_have_raw_bodies"] is False
    assert payload["accepted_packages_have_client_data"] is False
    assert payload["accepted_packages_are_authority"] is False
    assert payload["client_data_access"] is False


def test_empty_state_is_non_authorizing(tmp_path):
    payload = build_report_bridge_read_model(db_path=tmp_path / "missing.sqlite")

    assert payload["package_count"] == 0
    assert payload["latest_report_bridge_run_id"] is None
    assert payload["report_bridge_inbox_path"] == "/mnt/e/openclaw/node_uplink/inbox"
    assert payload["client_data_access"] is False
    assert all(value is False for value in payload["authority_flags"].values())


def test_export_source_does_not_claim_forbidden_behavior():
    text = Path("scripts/export_report_bridge_read_model.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "rsync",
        "scp ",
        "git clone",
        "docker run",
        "ollama run",
        "pip install",
        "npm install",
    ]
    for token in forbidden:
        assert token not in text
