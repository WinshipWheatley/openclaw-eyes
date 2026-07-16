from __future__ import annotations

import hashlib
import json
from pathlib import Path

import invoice_artifact_locator as locator


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _package(
    root: Path,
    name: str,
    *,
    pdf_bytes: bytes = b"canonical june pdf",
    workbook_bytes: bytes = b"june workbook",
    client_slug: str = "st-annes",
    period: str = "2026-06",
    pdf_hash: str | None = None,
) -> Path:
    package_dir = root / name
    package_dir.mkdir(parents=True)
    (package_dir / "invoice.pdf").write_bytes(pdf_bytes)
    (package_dir / "invoice.xlsx").write_bytes(workbook_bytes)
    manifest = {
        "schema": "openclaw_invoice_manifest_v1",
        "invoice_key": f"{period}_{client_slug}",
        "client_slug": client_slug,
        "invoice_number": "3",
        "service_period_start": f"{period}-01",
        "service_period_end": f"{period}-30",
        "status": "draft",
        "amount": 875.0,
        "source_sheet": "June 2026",
        "package_workbook_sha256": _sha256(workbook_bytes),
        "current_pdf_sha256": pdf_hash or _sha256(pdf_bytes),
        "latest_send_receipt_path": None,
    }
    manifest_path = package_dir / "invoice_manifest.json"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return manifest_path


def test_locates_one_canonical_candidate_from_identical_pdf_copies(tmp_path: Path) -> None:
    root = tmp_path / "handoffs"
    first = _package(root, "st-annes-june-copy-a")
    second = _package(root, "st-annes-june-copy-b")

    result = locator.locate_invoice_artifacts(
        "st_annes",
        "2026-06",
        roots=[root],
    )

    assert result["status"] == "FOUND"
    candidate = result["canonical_candidate"]
    assert candidate["invoice_number"] == "3"
    assert candidate["source_sheet"] == "June 2026"
    assert candidate["amount"] == 875.0
    assert candidate["invoice_status"] == "draft"
    assert candidate["send_receipt_present"] is False
    assert candidate["pdf_sha256"] == _sha256(b"canonical june pdf")
    assert candidate["duplicate_pdf_paths"] == sorted(
        [
            (first.parent / "invoice.pdf").as_posix(),
            (second.parent / "invoice.pdf").as_posix(),
        ]
    )
    assert result["machine_proof"]["external_action_performed"] is False


def test_excludes_quarantined_candidate(tmp_path: Path) -> None:
    root = tmp_path / "handoffs"
    _package(root / ".openclaw_scope_quarantine", "st-annes-june")

    result = locator.locate_invoice_artifacts("st_annes", "2026-06", roots=[root])

    assert result["status"] == "NOT_FOUND"
    assert any(item["reason"] == "quarantined_path" for item in result["rejections"])


def test_rejects_declared_pdf_hash_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "handoffs"
    _package(root, "st-annes-june", pdf_hash="0" * 64)

    result = locator.locate_invoice_artifacts("st_annes", "2026-06", roots=[root])

    assert result["status"] == "NOT_FOUND"
    assert any(item["reason"] == "pdf_hash_mismatch" for item in result["rejections"])


def test_nonidentical_valid_candidates_are_ambiguous(tmp_path: Path) -> None:
    root = tmp_path / "handoffs"
    _package(root, "st-annes-june-a", pdf_bytes=b"version a")
    _package(root, "st-annes-june-b", pdf_bytes=b"version b")

    result = locator.locate_invoice_artifacts("st_annes", "2026-06", roots=[root])

    assert result["status"] == "AMBIGUOUS"
    assert result["canonical_candidate"] is None
    assert len(result["candidate_groups"]) == 2
