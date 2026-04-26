#!/usr/bin/env python3
"""Synthetic mock discovery run-through for OpenClaw Legal."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.cli import main as legal_cli_main


DEFAULT_OUTPUT_ROOT = Path("/tmp/openclaw_legal_mock_discovery")
QUERY = "allocation"


def run_mock_discovery_demo(output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Run the current Legal CLI spine against a synthetic discovery batch."""

    output = Path(output_root).expanduser().resolve(strict=False)
    _require_outside_repo(output)
    if output.exists():
        shutil.rmtree(output)
    source_dir = output / "synthetic_sources"
    vault_root = output / "legal_vault"
    matter_root = vault_root / "matter_alpha"
    source_dir.mkdir(parents=True)

    sources = _write_synthetic_sources(source_dir)
    _run_cli(
        [
            "create-matter",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--matter-id",
            "mock-discovery-001",
            "--display-name",
            "Synthetic Mock Discovery",
        ]
    )

    registered = [
        _run_cli(
            [
                "add-source",
                "--vault-root",
                str(vault_root),
                "--root",
                str(matter_root),
                "--source",
                str(source),
            ]
        )
        for source in sources
    ]
    extraction = _run_cli(
        [
            "extract-all",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
        ]
    )
    search = _run_cli(
        [
            "search",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--query",
            QUERY,
        ]
    )
    report = _run_cli(
        [
            "report",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--query",
            QUERY,
            "--report-name",
            "mock-discovery-allocation-report",
        ]
    )
    review_packet = _run_cli(
        [
            "review-packet",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--packet-name",
            "mock-discovery-review",
        ]
    )
    support_packet = _run_cli(
        [
            "support-packet",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--packet-name",
            "mock-discovery-diagnostics",
        ]
    )

    _require_outside_repo(matter_root)
    status_counts = _normalized_status_counts(extraction["status_counts"])
    summary = {
        "vault_root": str(vault_root),
        "matter_root": str(matter_root),
        "manifest_path": str(matter_root / "manifest.json"),
        "audit_path": str(matter_root / "audit.jsonl"),
        "source_count": len(registered),
        "extracted_count": status_counts.get("extracted", 0),
        "unsupported_count": status_counts.get("unsupported", 0),
        "no_text_count": status_counts.get("no_text", 0),
        "failed_count": status_counts.get("failed", 0),
        "search_result_count": search["result_count"],
        "report_path": report["report_path"],
        "review_packet_path": review_packet["packet_path"],
        "support_packet_path": support_packet["packet_path"],
        "product_repo_data_written": False,
        "source_status_counts": status_counts,
    }
    return summary


def _write_synthetic_sources(source_dir: Path) -> list[Path]:
    witness = source_dir / "mock_witness_statement.txt"
    witness.write_text(
        "Witness observed shipment allocation discussion during a mock hearing prep.\n",
        encoding="utf-8",
    )
    case_note = source_dir / "mock_case_note.md"
    case_note.write_text(
        "# Mock Case Note\n\n- Counsel flagged allocation timeline questions.\n",
        encoding="utf-8",
    )
    text_pdf = source_dir / "mock_contract_excerpt.pdf"
    _write_text_layer_pdf(text_pdf, "Synthetic allocation clause for mock discovery")
    scanned_placeholder = source_dir / "mock_scanned_placeholder.pdf"
    scanned_placeholder.write_bytes(b"%PDF-1.4\n%%EOF\n")
    unsupported = source_dir / "mock_export.abcxyz"
    unsupported.write_bytes(b"synthetic unsupported payload")
    return [witness, case_note, text_pdf, scanned_placeholder, unsupported]


def _normalized_status_counts(status_counts: dict[str, int]) -> dict[str, int]:
    normalized = {
        "extracted": 0,
        "unsupported": 0,
        "no_text": 0,
        "failed": 0,
        "pending": 0,
    }
    normalized.update(status_counts)
    return normalized


def _write_text_layer_pdf(path: Path, text: str) -> None:
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
            "endobj\n"
        ),
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj\n",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj
    xref_offset = len(pdf.encode("latin-1"))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        "trailer\n<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes(pdf.encode("latin-1"))


def _run_cli(args: list[str]) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = legal_cli_main(args)
    if code != 0:
        raise RuntimeError(f"legal CLI failed ({code}): {' '.join(args)}\n{stderr.getvalue()}")
    return json.loads(stdout.getvalue())


def _require_outside_repo(path: Path) -> None:
    resolved = path.expanduser().resolve(strict=False)
    repo_root = ROOT.resolve(strict=False)
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return
    raise ValueError(f"demo output must be outside product repo: {resolved}")


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("Usage: demo_legal_mock_discovery.py [OUTPUT_ROOT]", file=sys.stderr)
        return 2
    output_root = Path(argv[1]) if len(argv) == 2 else DEFAULT_OUTPUT_ROOT
    summary = run_mock_discovery_demo(output_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
