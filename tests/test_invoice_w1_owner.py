from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from test_invoice_workbook_finalizer import _lamd_fixture

import invoice_w1_owner


def test_owner_defaults_to_dry_run_without_creating_work_or_package(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    _lamd_fixture(source)
    package = tmp_path / "artifacts" / "live-arts-july"
    receipt = tmp_path / "receipt.json"

    result = invoice_w1_owner.run_lamd_july_finalization(
        source_path=source,
        package_dir=package,
        receipt_path=receipt,
        confirm=False,
    )

    assert result["status"] == "DRY_RUN_READY"
    assert result["source_selection"]["status"] == "FOUND"
    assert result["source_semantic_marker_count"] >= 3
    assert result["authority_boundary"] == {
        "provider_draft_created": False,
        "external_send_performed": False,
        "money_moved": False,
        "ledger_posted": False,
    }
    assert not package.exists()
    assert not receipt.exists()
    assert not (tmp_path / "artifacts" / ".w1_runs").exists()


def test_owner_rejects_ambiguous_source_before_any_write(tmp_path: Path) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    _lamd_fixture(first)
    _lamd_fixture(second)
    second.write_bytes(second.read_bytes() + b"distinct")
    package = tmp_path / "package"
    receipt = tmp_path / "receipt.json"

    result = invoice_w1_owner.run_lamd_july_finalization(
        source_path=[first, second],
        package_dir=package,
        receipt_path=receipt,
        confirm=True,
    )

    assert result["status"] == "SOURCE_BLOCKED"
    assert result["source_selection"]["status"] == "AMBIGUOUS"
    assert not package.exists()
    assert not receipt.exists()


def test_cli_dry_run_works_from_repo_root_without_pythonpath(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    _lamd_fixture(source)
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/finalize_lamd_july_invoice.py",
            "--source",
            str(source),
            "--package-dir",
            str(tmp_path / "package"),
            "--receipt",
            str(tmp_path / "receipt.json"),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "DRY_RUN_READY"
