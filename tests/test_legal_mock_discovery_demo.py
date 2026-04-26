from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.demo_legal_mock_discovery import QUERY, run_mock_discovery_demo


PRODUCT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mock_discovery_demo_runs_end_to_end_outside_repo(tmp_path: Path) -> None:
    result = run_mock_discovery_demo(tmp_path / "mock-discovery")

    vault_root = Path(result["vault_root"])
    matter_root = Path(result["matter_root"])
    manifest_path = Path(result["manifest_path"])
    audit_path = Path(result["audit_path"])
    report_path = Path(result["report_path"])
    review_packet_path = Path(result["review_packet_path"])
    support_packet_path = Path(result["support_packet_path"])

    assert not matter_root.resolve().is_relative_to(PRODUCT_REPO_ROOT)
    assert vault_root == tmp_path / "mock-discovery" / "legal_vault"
    assert matter_root == vault_root / "matter_alpha"
    assert manifest_path.is_file()
    assert audit_path.is_file()
    assert report_path.is_file()
    assert review_packet_path.is_dir()
    assert support_packet_path.is_file()
    assert result["product_repo_data_written"] is False

    manifest = _read_json(manifest_path)
    support_packet = _read_json(support_packet_path)
    report = report_path.read_text(encoding="utf-8")
    support_packet_text = support_packet_path.read_text(encoding="utf-8")

    assert result["source_count"] == 5
    assert len(manifest["sources"]) == 5
    assert result["extracted_count"] == 3
    assert result["unsupported_count"] == 1
    assert result["no_text_count"] == 1
    assert result["failed_count"] == 0
    assert result["source_status_counts"] == support_packet["diagnostics"]["source_status_counts"]
    assert result["alternative_methods_count"] == (
        result["unsupported_count"] + result["no_text_count"] + result["failed_count"]
    )
    assert result["search_result_count"] >= 3
    assert f"- Query: `{QUERY}`" in report
    assert "allocation" in report.casefold()
    assert "Witness observed" not in support_packet_text
    assert "Synthetic allocation clause" not in support_packet_text
