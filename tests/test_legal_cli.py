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


def test_create_matter_command_accepts_approved_vault_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"

    code, payload = _run_cli(
        [
            "create-matter",
            "--vault-root",
            str(vault),
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
    assert payload["root_path"] == str(root)
    assert (root / "manifest.json").is_file()


def test_create_matter_command_rejects_root_outside_vault(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = tmp_path / "outside" / "matter"

    code = main(
        [
            "create-matter",
            "--vault-root",
            str(vault),
            "--root",
            str(root),
            "--matter-id",
            "matter-001",
            "--display-name",
            "Example Matter",
        ]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out == ""
    assert "approved legal vault root" in captured.err
    assert not root.exists()


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


def test_import_staging_requires_lane(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "import-staging",
                "--vault-root",
                str(vault),
                "--root",
                str(root),
                "--staging-dir",
                str(staging),
            ]
        )
    captured = capsys.readouterr()

    assert exc.value.code == 2
    assert "--lane" in captured.err


def test_import_staging_rejects_invalid_lane(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "import-staging",
                "--vault-root",
                str(vault),
                "--root",
                str(root),
                "--staging-dir",
                str(staging),
                "--lane",
                "unknown",
            ]
        )
    captured = capsys.readouterr()

    assert exc.value.code == 2
    assert "invalid choice" in captured.err


def test_import_staging_requires_vault_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    create_matter_workspace(root, "matter", "Matter")

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "import-staging",
                "--root",
                str(root),
                "--staging-dir",
                str(staging),
                "--lane",
                "synthetic",
            ]
        )
    captured = capsys.readouterr()

    assert exc.value.code == 2
    assert "--vault-root" in captured.err


def test_import_staging_rejects_matter_root_outside_vault(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = tmp_path / "outside" / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()

    code = main(
        [
            "import-staging",
            "--vault-root",
            str(vault),
            "--root",
            str(root),
            "--staging-dir",
            str(staging),
            "--lane",
            "synthetic",
        ]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out == ""
    assert "approved legal vault root" in captured.err


def test_import_staging_synthetic_imports_and_records_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    first = staging / "alpha.txt"
    second = staging / "beta.md"
    first.write_text("alpha evidence", encoding="utf-8")
    second.write_text("# beta", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    code, payload = _run_cli(
        [
            "import-staging",
            "--vault-root",
            str(vault),
            "--root",
            str(root),
            "--staging-dir",
            str(staging),
            "--lane",
            "synthetic",
        ],
        capsys,
    )

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    audit = [
        json.loads(line)
        for line in (root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert code == 0
    assert payload["lane"] == "synthetic"
    assert payload["import_context"] == "synthetic"
    assert payload["source_count_imported"] == 2
    assert payload["staging_path_validated"] is True
    assert payload["staging_dir_present"] is True
    assert "staging_dir" not in payload
    assert first.read_text(encoding="utf-8") == "alpha evidence"
    assert second.read_text(encoding="utf-8") == "# beta"
    assert {source["original_filename"] for source in manifest["sources"]} == {
        "alpha.txt",
        "beta.md",
    }
    assert {source["staging_import_context"] for source in manifest["sources"]} == {
        "synthetic"
    }
    assert all(source["source_id"].startswith("src_") for source in manifest["sources"])
    assert all(len(source["sha256"]) == 64 for source in manifest["sources"])
    assert audit[-1]["event"] == "staging_import"
    assert audit[-1]["lane"] == "synthetic"
    assert audit[-1]["source_count_imported"] == 2
    assert audit[-1]["staging_path_validated"] is True
    assert audit[-1]["staging_dir_present"] is True
    assert "staging_dir" not in audit[-1]


def test_import_staging_real_matter_records_local_only_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "legal-vault"
    root = vault / "matter"
    staging = tmp_path / "staging"
    staging.mkdir()
    staged = staging / "client-note.txt"
    staged.write_text("local matter note", encoding="utf-8")
    create_matter_workspace(root, "matter", "Matter", allowed_vault_roots=[vault])

    code, payload = _run_cli(
        [
            "import-staging",
            "--vault-root",
            str(vault),
            "--root",
            str(root),
            "--staging-dir",
            str(staging),
            "--lane",
            "real-matter",
        ],
        capsys,
    )

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    audit = [
        json.loads(line)
        for line in (root / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert code == 0
    assert payload["lane"] == "real-matter"
    assert payload["import_context"] == "real_matter_local_only"
    assert payload["source_count_imported"] == 1
    assert payload["staging_dir_present"] is True
    assert "staging_dir" not in payload
    assert manifest["sources"][0]["staging_import_context"] == "real_matter_local_only"
    assert audit[-1]["import_context"] == "real_matter_local_only"
    assert audit[-1]["staging_dir_present"] is True
    assert "staging_dir" not in audit[-1]
    assert str(staging) not in json.dumps(payload, sort_keys=True)
    assert str(staging) not in json.dumps(audit[-1], sort_keys=True)
    assert staged.read_text(encoding="utf-8") == "local matter note"


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


def test_support_packet_command_creates_sanitized_packet(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "client-secret-facts.txt"
    source.write_text("privileged settlement content", encoding="utf-8")
    create_matter_workspace(root, "matter", "Private Client Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    code, payload = _run_cli(
        [
            "support-packet",
            "--root",
            str(root),
            "--packet-name",
            "diagnostics",
        ],
        capsys,
    )

    packet_path = Path(payload["packet_path"])
    packet_text = packet_path.read_text(encoding="utf-8")
    assert code == 0
    assert payload["artifact_type"] == "sanitized_support_packet"
    assert packet_path == root / "support" / "support-packet-diagnostics" / "support_packet.json"
    assert str(root) not in packet_text
    assert "client-secret-facts" not in packet_text
    assert "privileged settlement content" not in packet_text


def test_alternative_methods_command_reports_next_actions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "matter"
    source = tmp_path / "unsupported.secret"
    source.write_bytes(b"synthetic unsupported content")
    create_matter_workspace(root, "matter", "Matter")
    registered = register_source(root, source)
    extract_source_text(root, registered["source_id"])

    code, payload = _run_cli(["alternative-methods", "--root", str(root)], capsys)

    assert code == 0
    assert payload["artifact_type"] == "alternative_methods_v0"
    assert payload["needs_alternative_methods"] == 1
    assert payload["items"][0]["status"] == "unsupported"
    assert "request_feature" in payload["items"][0]["locked_actions"]


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
