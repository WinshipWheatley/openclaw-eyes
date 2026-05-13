#!/usr/bin/env python3
"""Record generic metadata-only artifact checkpoint receipts."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
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


MODULE_ATLAS_BOOTSTRAP_COMMAND = (
    "python3 scripts/record_artifact_checkpoint_receipts.py --module-atlas --ensure"
)

MODULE_ATLAS_SOURCE_BASIS = (
    "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
    "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md",
    "docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md",
    "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md",
    "docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md",
    "docs/operations/OPENCLAW_OPERATOR_STATUS_GRAMMAR_V0.md",
)

MODULE_ATLAS_ARTIFACT_CHECKPOINTS = (
    ArtifactCheckpoint(
        "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
        "module-atlas-v0",
        "module_atlas_doc",
        "docs_only",
    ),
    ArtifactCheckpoint(
        "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md",
        "manifest-schema-v0",
        "module_atlas_doc",
        "inert",
    ),
    ArtifactCheckpoint(
        "docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md",
        "synthetic-manifest-examples-v0",
        "module_atlas_doc",
        "inert",
    ),
    ArtifactCheckpoint(
        "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md",
        "manifest-validation-contract-v0",
        "module_atlas_doc",
        "validation_proven",
    ),
    ArtifactCheckpoint(
        "scripts/validate_module_manifests.py",
        "manifest-validator",
        "module_atlas_validation_code",
        "validation_proven",
    ),
    ArtifactCheckpoint(
        "tests/test_module_manifest_validation.py",
        "manifest-validator-tests",
        "module_atlas_validation_test",
        "validation_proven",
    ),
)

MODULE_ATLAS_ARTIFACT_PATHS = tuple(
    artifact.artifact_path for artifact in MODULE_ATLAS_ARTIFACT_CHECKPOINTS
)


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


def _default_db_path(db_path: str | None = None) -> str:
    return db_path or ".openclaw/business_ops/ledger.sqlite"


def find_existing_artifact_checkpoint(
    artifact_path: str,
    commit_hash: str,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """
    Return the newest matching checkpoint receipt envelope without reading the artifact body.
    """
    path = _default_db_path(db_path)
    if not os.path.exists(path):
        return None

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
                SELECT e.ts, p.packet_json_safe
                FROM events e
                JOIN packets p ON p.event_id = e.event_id
                WHERE e.event_type = 'artifact_checkpoint'
                ORDER BY e.ts DESC
                LIMIT 250
                """
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None

    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except json.JSONDecodeError:
            continue
        if packet.get("artifact_path") != artifact_path:
            continue
        if packet.get("commit_hash") != commit_hash:
            continue
        if packet.get("receipt_type") != "artifact_checkpoint":
            continue
        return {
            "receipt_id": packet.get("receipt_id") or packet.get("packet_id") or "",
            "artifact_path": artifact_path,
            "commit_hash": commit_hash,
            "artifact_status": packet.get("artifact_status"),
            "authority_status": packet.get("authority_status"),
            "runtime_activation": packet.get("runtime_activation"),
            "sqlite_meaning": packet.get("sqlite_meaning"),
            "ts": ts,
        }
    return None


def record_artifact_checkpoints(
    artifacts: Iterable[ArtifactCheckpoint],
    commit_hash: str,
    source_basis: list[str] | None = None,
    db_path: str | None = None,
    ensure: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for artifact in artifacts:
        existing = None
        if ensure:
            existing = find_existing_artifact_checkpoint(
                artifact.artifact_path,
                commit_hash=commit_hash,
                db_path=db_path,
            )
        if existing:
            results.append(
                {
                    "artifact_path": artifact.artifact_path,
                    "label": artifact.label,
                    "artifact_type": artifact.artifact_type,
                    "artifact_status": artifact.artifact_status,
                    "receipt_id": existing["receipt_id"],
                    "recorded": False,
                    "present": True,
                    "action": "present",
                }
            )
            continue

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
                "body_ingest_status": "not_ingested",
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
                "present": bool(receipt_id),
                "action": "recorded" if receipt_id else "failed",
            }
        )
    return results


def ensure_module_atlas_artifact_checkpoints(
    commit_hash: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    return record_artifact_checkpoints(
        MODULE_ATLAS_ARTIFACT_CHECKPOINTS,
        commit_hash=commit_hash,
        source_basis=list(MODULE_ATLAS_SOURCE_BASIS),
        db_path=db_path,
        ensure=True,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record generic metadata-only artifact checkpoint receipts."
    )
    parser.add_argument(
        "--module-atlas",
        action="store_true",
        help="Ensure receipts for the committed Module Atlas artifact checkpoint set.",
    )
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="Do not create a duplicate receipt when the same artifact/commit checkpoint exists.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        nargs=4,
        metavar=("PATH", "LABEL", "TYPE", "STATUS"),
        help="Explicit artifact path, label, artifact type, and artifact status.",
    )
    parser.add_argument("--commit-hash", help="Commit hash to bind to the receipts.")
    parser.add_argument("--source-basis", action="append", default=[], help="Source basis reference.")
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    args = parser.parse_args(argv)
    if not args.module_atlas and not args.artifact:
        parser.error("provide --module-atlas or at least one --artifact")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    commit_hash = args.commit_hash or current_commit_hash()
    init_business_ops_ledger(args.db)

    artifacts: list[ArtifactCheckpoint] = []
    source_basis = list(args.source_basis)
    ensure = args.ensure or args.module_atlas
    if args.module_atlas:
        artifacts.extend(MODULE_ATLAS_ARTIFACT_CHECKPOINTS)
        source_basis.extend(MODULE_ATLAS_SOURCE_BASIS)
    if args.artifact:
        artifacts.extend(
            ArtifactCheckpoint(
                artifact_path=item[0],
                label=item[1],
                artifact_type=item[2],
                artifact_status=item[3],
            )
            for item in args.artifact
        )

    results = record_artifact_checkpoints(
        artifacts,
        commit_hash=commit_hash,
        source_basis=source_basis,
        db_path=args.db,
        ensure=ensure,
    )

    failed = [result for result in results if result["action"] == "failed"]
    recorded = [result for result in results if result["action"] == "recorded"]
    present = [result for result in results if result["action"] == "present"]
    if args.module_atlas:
        print("Module Atlas receipt bootstrap")
        print("Evidence: committed docs/code artifacts are checked against metadata-only receipts.")
        print("Boundary: receipt-record-only; no runtime authority or full body ingest.")
        print("Blocked: no modules, agents, brokers, customer deployment, or runtime behavior are activated.")
        print("Next safe move: review generated status after this ensure command completes.")
        print("")

    for result in results:
        status = result["action"].upper()
        print(
            f"{status} {result['artifact_path']} "
            f"label={result['label']} status={result['artifact_status']} "
            f"receipt_id={result['receipt_id'] or 'none'}"
        )

    print(
        f"Summary: ensured={len(results) - len(failed)} "
        f"recorded={len(recorded)} present={len(present)} failed={len(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
