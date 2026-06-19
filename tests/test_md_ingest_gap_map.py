import json
from pathlib import Path

import md_ingest_gap_map
from scripts.md_ingest_gap_map import main as gap_map_main


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    inventory = _write_json(
        tmp_path / "root_inventory.json",
        {
            "roots": [
                {"root_path": "/drive", "allowed_markdown_count": 10},
                {"root_path": "/drive/exact", "allowed_markdown_count": 3},
                {"root_path": "/other", "allowed_markdown_count": 5},
            ]
        },
    )
    corpus = _write_json(
        tmp_path / "corpus.json",
        {
            "root_path": "/drive/exact",
            "ingested_document_count": 3,
        },
    )
    return inventory, corpus


def test_gap_map_classifies_exact_partial_and_unmapped_roots(tmp_path):
    inventory, corpus = _fixtures(tmp_path)

    result = md_ingest_gap_map.build_ingest_gap_map(
        root_inventory_receipt=inventory,
        corpus_receipts=[corpus],
        map_id="gap_fixture",
    )
    by_path = {item["root_path"]: item for item in result.roots}

    assert by_path["/drive"]["coverage_status"] == "partially_mapped_subroot"
    assert by_path["/drive"]["remaining_markdown_count_lower_bound"] == 7
    assert by_path["/drive/exact"]["coverage_status"] == "mapped_exact"
    assert by_path["/other"]["coverage_status"] == "unmapped"
    assert result.partial_root_count == 1
    assert result.mapped_root_count == 1
    assert result.unmapped_root_count == 1
    assert result.remaining_markdown_count_lower_bound == 12


def test_gap_map_reports_no_body_or_truth_authority(tmp_path):
    inventory, corpus = _fixtures(tmp_path)

    result = md_ingest_gap_map.build_ingest_gap_map(
        root_inventory_receipt=inventory,
        corpus_receipts=[corpus],
        map_id="authority_fixture",
    )
    payload = md_ingest_gap_map.result_as_dict(result)

    assert payload["no_authority_flags"]["markdown_body_read_allowed"] is False
    assert payload["no_authority_flags"]["source_markdown_writeback_allowed"] is False
    assert payload["no_authority_flags"]["truth_claimed"] is False
    assert all(item["body_read"] is False for item in payload["roots"])


def test_cli_json_and_operator_output(tmp_path, capsys):
    inventory, corpus = _fixtures(tmp_path)

    assert gap_map_main(
        [
            "--root-inventory-receipt",
            str(inventory),
            "--corpus-receipt",
            str(corpus),
            "--map-id",
            "cli_json",
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unmapped_root_count"] == 1
    assert payload["remaining_markdown_count_lower_bound"] == 12

    assert gap_map_main(
        [
            "--root-inventory-receipt",
            str(inventory),
            "--corpus-receipt",
            str(corpus),
            "--map-id",
            "cli_operator",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Markdown Ingest Gap Map" in capsys.readouterr().out


def test_source_has_no_scan_network_send_delete_move_or_writeback_authority():
    source = Path("md_ingest_gap_map.py").read_text(encoding="utf-8").lower()

    for token in [
        "os.walk",
        "sqlite3",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "send_message",
        "reply_text",
        "os.system",
        "shell=true",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
        "write_text",
    ]:
        assert token not in source
    assert md_ingest_gap_map.NO_AUTHORITY_FLAGS["markdown_body_read_allowed"] is False
    assert md_ingest_gap_map.NO_AUTHORITY_FLAGS["truth_claimed"] is False
