#!/usr/bin/env python3
"""Record generic metadata-only artifact checkpoint receipts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import init_business_ops_ledger, record_receipt


@dataclass(frozen=True)
class ArtifactCheckpoint:
    artifact_path: str
    label: str
    artifact_type: str
    artifact_status: str


def current_commit_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to determine current git commit hash")
    return result.stdout.strip()


def record_artifact_checkpoints(
    artifacts: Iterable[ArtifactCheckpoint],
    commit_hash: str,
    source_basis: list[str] | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for artifact in artifacts:
        receipt_id = record_receipt(
            receipt_type="artifact_checkpoint",
            artifact_path=artifact.artifact_path,
            commit_hash=commit_hash,
            artifact_type=artifact.artifact_type,
            artifact_status=artifact.artifact_status,
            authority_status="no_runtime_authority",
            runtime_activation=False,
            sqlite_meaning="receipt_record_only",
            source_basis=source_basis or [],
            payload={
                "artifact_label": artifact.label,
                "recorder": "record_artifact_checkpoint_receipts_v0",
                "metadata_only": True,
                "full_body_ingested": False,
                "runtime_activation": False,
                "authority_status": "no_runtime_authority",
            },
            db_path=db_path,
        )
        results.append(
            {
                "artifact_path": artifact.artifact_path,
                "label": artifact.label,
                "artifact_type": artifact.artifact_type,
                "artifact_status": artifact.artifact_status,
                "receipt_id": receipt_id,
                "recorded": bool(receipt_id),
            }
        )
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record generic metadata-only artifact checkpoint receipts."
    )
    parser.add_argument(
        "--artifact",
        action="append",
        nargs=4,
        metavar=("PATH", "LABEL", "TYPE", "STATUS"),
        required=True,
        help="Explicit artifact path, label, artifact type, and artifact status.",
    )
    parser.add_argument("--commit-hash", help="Commit hash to bind to the receipts.")
    parser.add_argument("--source-basis", action="append", default=[], help="Source basis reference.")
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    commit_hash = args.commit_hash or current_commit_hash()
    init_business_ops_ledger(args.db)

    artifacts = [
        ArtifactCheckpoint(
            artifact_path=item[0],
            label=item[1],
            artifact_type=item[2],
            artifact_status=item[3],
        )
        for item in args.artifact
    ]
    results = record_artifact_checkpoints(
        artifacts,
        commit_hash=commit_hash,
        source_basis=args.source_basis,
        db_path=args.db,
    )

    failed = [result for result in results if not result["recorded"]]
    for result in results:
        status = "RECORDED" if result["recorded"] else "FAILED"
        print(
            f"{status} {result['artifact_path']} "
            f"label={result['label']} status={result['artifact_status']} "
            f"receipt_id={result['receipt_id'] or 'none'}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
