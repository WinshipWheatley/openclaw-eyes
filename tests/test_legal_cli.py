from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.cli import main
from legal.local_ingestion import extract_source_text
from legal.matter_workspace import create_matter_workspace, register_source
from legal.search_report import export_search_report


def _run_cli(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    code = main(args)
    captured = capsys.readouterr()
    assert captured.err == ""
    return code, json.loads(captured.out)


def test_create_matter_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "matter"

    code, payload = _run_cli(
        [
            "create-matter",
            "--root",
            str(root),
            "--matter-id",
            "matter-001",
            "--display-name",
            "Example Matter",
        ],
        capsys,
    )

    assert code == 0
    assert payload["matter_id"] == "matter-001"
    assert payload["display_name"] == "Example Matter"
    assert payload["root_path"] == str(root)
    assert (root / "manifest.json").is_file()


def test_add_source_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")

    code, payload = _run_cli(
        ["add-source", "--root", str(root), "--source", str(source)],
        capsys,
    )

    assert code == 0
    assert payload["original_filename"] == "source.txt"
    assert payload["source_id"].startswith("src_")
    assert Path(payload["stored_path"]).is_file()


def test_extract_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.md"
    source.write_text("# Settlement\n", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)

    code, payload = _run_cli(
        ["extract", "--root", str(root), "--source-id", registered["source_id"]],
        capsys,
    )

    assert code == 0
    assert payload["status"] == "extracted"
    assert Path(payload["extracted_path"]).read_text(encoding="utf-8") == "# Settlement\n"


def test_extract_all_command_extracts_registered_supported_sources(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    txt = tmp_path / "source.txt"
    md = tmp_path / "notes.md"
    pdf = tmp_path / "record.pdf"
    unsupported = tmp_path / "scan.bin"
    txt.write_text("plain evidence", encoding="utf-8")
    md.write_text("# Notes\n", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    unsupported.write_bytes(b"unsupported")
    create_matter_workspace(root, "matter", "Matter")
    registered = [
        register_source(root, txt),
        register_source(root, md),
        register_source(root, pdf),
        register_source(root, unsupported),
    ]

    with patch(
        "legal.local_ingestion._pdf_to_text",
        return_value={
            "ok": True,
            "text": "PDF text layer",
            "pages": 1,
            "chars": len("PDF text layer"),
        },
    ):
        code = main(["extract-all", "--root", str(root)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert captured.err == ""
    assert payload["root"] == str(root)
    assert payload["result_count"] == 4
    assert payload["status_counts"] == {
        "extracted": 3,
        "unsupported": 1,
    }
    assert [result["source_id"] for result in payload["results"]] == [
        source["source_id"] for source in registered
    ]
    assert [result["status"] for result in payload["results"]] == [
        "extracted",
        "extracted",
        "extracted",
        "unsupported",
    ]


def test_search_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("Settlement demand", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    code, payload = _run_cli(
        ["search", "--root", str(root), "--query", "settlement"],
        capsys,
    )

    assert code == 0
    assert payload["query"] == "settlement"
    assert payload["result_count"] == 1
    assert payload["results"][0]["source_id"] == registered["source_id"]


def test_report_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("Settlement report", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    code, payload = _run_cli(
        [
            "report",
            "--root",
            str(root),
            "--query",
            "settlement",
            "--report-name",
            "settlement-report",
        ],
        capsys,
    )

    assert code == 0
    assert payload["result_count"] == 1
    assert Path(payload["report_path"]).parent == root / "exports"
    assert Path(payload["report_path"]).is_file()


def test_default_profile_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "legal-profile.json"

    code, payload = _run_cli(
        [
            "default-profile",
            "--firm-name",
            "Example Law",
            "--output",
            str(output),
            "--profile-name",
            "example-local",
        ],
        capsys,
    )

    assert code == 0
    assert payload == {
        "firm_name": "Example Law",
        "profile_name": "example-local",
        "profile_path": str(output),
    }
    profile = json.loads(output.read_text(encoding="utf-8"))
    assert profile["firm_name"] == "Example Law"
    assert profile["mode"] == "local_first"


def test_review_packet_command_creates_packet_with_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("Settlement packet", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])
    export_search_report(root, "settlement", report_name="settlement-report")

    code, payload = _run_cli(
        [
            "review-packet",
            "--root",
            str(root),
            "--packet-name",
            "first-review",
        ],
        capsys,
    )

    packet_path = Path(payload["packet_path"])
    assert code == 0
    assert packet_path == root / "exports" / "review-packet-first-review"
    assert packet_path.is_dir()
    assert payload["matter_id"] == "matter"
    assert payload["source_count"] == 1
    assert payload["extracted_count"] == 2
    assert payload["report_count"] == 1
    assert payload["included_file_count"] >= 5


def test_review_packet_no_reports_excludes_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "source.txt"
    source.write_text("Settlement packet", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])
    export_search_report(root, "settlement", report_name="settlement-report")

    code, payload = _run_cli(
        ["review-packet", "--root", str(root), "--no-reports"],
        capsys,
    )

    packet_path = Path(payload["packet_path"])
    assert code == 0
    assert payload["report_count"] == 0
    assert not (packet_path / "reports").exists()


def test_user_error_returns_one_and_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"

    code = main(
        [
            "create-matter",
            "--root",
            str(root),
            "--matter-id",
            "",
            "--display-name",
            "Matter",
        ]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out == ""
    assert "error: matter_id is required" in captured.err
