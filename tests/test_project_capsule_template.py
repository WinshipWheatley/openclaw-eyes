import json
from pathlib import Path

from project_capsule import DEMO_PROJECT_ID, create_demo_project_capsule
from scripts.export_project_capsule_template import TEMPLATE_FILES, export_project_capsule_template, main


def test_template_files_are_generated_for_synthetic_demo(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    output_root = tmp_path / "project_capsules"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")

    summary = export_project_capsule_template(db_path=db_path, output_root=output_root)

    capsule_root = output_root / DEMO_PROJECT_ID
    assert capsule_root.is_dir()
    assert {path.name for path in capsule_root.iterdir()} == set(TEMPLATE_FILES)
    assert summary["synthetic_demo_only"] is True
    assert summary["deployment_authority"] is False

    payload = json.loads((capsule_root / "capsule.json").read_text(encoding="utf-8"))
    assert payload["project_id"] == DEMO_PROJECT_ID
    assert payload["authority_flags"]["runtime_authority"] is False
    assert payload["authority_flags"]["deployment_authority"] is False
    assert payload["authority_flags"]["client_data_access"] is False
    assert payload["approval_status"] == "not_approved"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--output-root",
            str(output_root),
            "--format",
            "operator",
        ]
    )
    assert exit_code == 0
    assert "Synthetic/demo only" in capsys.readouterr().out


def test_template_text_does_not_imply_deployment_or_client_data_authority(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    output_root = tmp_path / "project_capsules"
    create_demo_project_capsule(db_path=db_path, run_id="pcap_fixture")
    export_project_capsule_template(db_path=db_path, output_root=output_root)

    capsule_root = output_root / DEMO_PROJECT_ID
    deployment_text = (capsule_root / "DEPLOYMENT_NOT_AUTHORIZED.md").read_text(encoding="utf-8")
    readme_text = (capsule_root / "README.md").read_text(encoding="utf-8")
    assert "Deployment authority is false" in deployment_text
    assert "must not be used to deploy" in deployment_text
    assert "client_data_access=false" in readme_text
    assert "run containers" in deployment_text
    assert "Future deployment requires" in deployment_text


def test_template_source_has_no_external_or_runtime_behavior():
    source = Path("scripts/export_project_capsule_template.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "docker run",
        "ollama run",
        "pip install",
        "npm install",
    ]
    for token in forbidden:
        assert token not in source
