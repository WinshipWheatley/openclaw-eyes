"""Artifact Lineage Registry V0.

Builds a read-only lineage registry for PDFs, proposals, receipts, reports,
screenshots, and review packet artifacts. It records provenance and trust status
without deleting, replacing, sending, or treating artifacts as payment truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Artifact Lineage Registry.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/artifact_lineage_registry.sqlite")
DEFAULT_ARTIFACT_SEARCH_ROOTS = [
    Path("/mnt/e/openclaw/artifacts"),
    Path("generated"),
]

SCHEMA_VERSION = "artifact_lineage_registry_v0"
READ_MODEL_ID = "artifact_lineage_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "ARTIFACT_LINEAGE_REGISTRY_READY"
STATUS_NOT_READY = "ARTIFACT_LINEAGE_REGISTRY_NOT_READY"

PRECONDITIONS = {
    "package_event_index": {
        "filename": "package_event_index.json",
        "accepted_statuses": ["PACKAGE_EVENT_INDEX_READY"],
    },
    "canonical_state_map": {
        "filename": "canonical_state_map.json",
        "accepted_statuses": ["CANONICAL_STATE_MAP_READY"],
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_from_payload(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("sha256") or "")
    if not value:
        return ""
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _sanitize(value: str) -> str:
    keep = []
    for char in value.lower():
        if char.isalnum():
            keep.append(char)
        elif char in {":", "_", "-", "."}:
            keep.append("_")
    rendered = "".join(keep).strip("_")
    while "__" in rendered:
        rendered = rendered.replace("__", "_")
    return rendered or "artifact"


def _artifact_kind(path: str, source_kind: str = "") -> str:
    kind = source_kind.lower()
    suffix = Path(path).suffix.lower()
    if "proposal" in kind and suffix == ".pdf":
        return "proposal"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "screenshot"
    if suffix == ".md":
        return "report"
    if suffix == ".json" or "receipt" in kind:
        return "receipt"
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return "workbook_copy"
    return "report"


def _bridge_path(path: str) -> str:
    return path if path.startswith("/mnt/e/openclaw/") else ""


def _path_exists(path: str) -> bool:
    if not path:
        return False
    return Path(path).exists() or (ROOT / path).exists()


def _resolved(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _artifact(
    *,
    artifact_ref: str,
    artifact_kind: str,
    path: str,
    source_workflow_ref: str,
    source_package_id: str = "",
    source_receipt_ref: str = "",
    lineage_status: str = "active",
    proof_refs: Sequence[str] = (),
    created_at: str,
    source_sha256: str = "",
) -> dict[str, Any]:
    exists = _path_exists(path)
    resolved = _resolved(path)
    sha256 = _sha256_file(resolved) if exists else source_sha256
    return {
        "artifact_ref": artifact_ref,
        "artifact_kind": artifact_kind,
        "path": path,
        "bridge_path": _bridge_path(path),
        "path_exists": exists,
        "sha256": sha256,
        "source_workflow_ref": source_workflow_ref,
        "source_package_id": source_package_id,
        "source_receipt_ref": source_receipt_ref,
        "lineage_status": lineage_status,
        "trusted_for_action": False,
        "proof_refs": list(dict.fromkeys(proof_refs)),
        "created_at": created_at,
    }


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        payload = _load_json(root / str(contract["filename"]))
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
                "source_ref": f"generated/read_models/{contract['filename']}",
            }
        )
    return rows


def _artifact_refs_from_read_model(
    payload: Mapping[str, Any],
    *,
    source_read_model_ref: str,
    source_workflow_ref: str,
    artifact_prefix: str,
    lineage_status_by_key: Mapping[str, str] | None = None,
    source_receipt_ref: str = "",
    created_at: str,
) -> list[dict[str, Any]]:
    refs = payload.get("artifact_refs")
    if not isinstance(refs, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for key, value in refs.items():
        if not isinstance(value, Mapping):
            continue
        path = str(value.get("path") or "")
        if not path:
            continue
        source_kind = str(value.get("kind") or key)
        artifact_kind = _artifact_kind(path, source_kind)
        status_map = lineage_status_by_key or {}
        lineage_status = status_map.get(str(key), "active")
        receipt_ref = path if artifact_kind == "receipt" else source_receipt_ref
        rows.append(
            _artifact(
                artifact_ref=f"artifact:{artifact_prefix}_{_sanitize(str(key))}",
                artifact_kind=artifact_kind,
                path=path,
                source_workflow_ref=source_workflow_ref,
                source_receipt_ref=receipt_ref,
                lineage_status=lineage_status,
                proof_refs=[source_read_model_ref, receipt_ref] if receipt_ref else [source_read_model_ref],
                created_at=created_at,
                source_sha256=_sha256_from_payload(value),
            )
        )
    return rows


def _st_annes_artifacts(read_model_root: Path, generated_at: str) -> list[dict[str, Any]]:
    payload = _load_json(read_model_root / "st_annes_invoice_status.json")
    pdf = str(payload.get("source_pdf_path") or "")
    receipt = str(payload.get("source_receipt_path") or "")
    rows: list[dict[str, Any]] = []
    if pdf:
        rows.append(
            _artifact(
                artifact_ref="artifact:st_annes_operator_sent_invoice_pdf",
                artifact_kind="pdf",
                path=pdf,
                source_workflow_ref=str(payload.get("workflow_ref") or "st_annes_invoice_workflow"),
                source_receipt_ref=receipt,
                lineage_status="operator_sent",
                proof_refs=[
                    "generated/read_models/st_annes_invoice_status.json",
                    receipt,
                ],
                created_at=generated_at,
                source_sha256=str(payload.get("source_pdf_sha256") or ""),
            )
        )
    if receipt:
        rows.append(
            _artifact(
                artifact_ref="artifact:st_annes_manual_send_receipt",
                artifact_kind="receipt",
                path=receipt,
                source_workflow_ref=str(payload.get("workflow_ref") or "st_annes_invoice_workflow"),
                source_receipt_ref=receipt,
                lineage_status="operator_sent",
                proof_refs=["generated/read_models/st_annes_invoice_status.json"],
                created_at=generated_at,
                source_sha256=str(payload.get("source_receipt_sha256") or ""),
            )
        )
    return rows


def _capital_invoice_artifacts(read_model_root: Path, generated_at: str) -> list[dict[str, Any]]:
    payload = _load_json(read_model_root / "capital_hilton_invoice_operator_run_status.json")
    proof_refs = payload.get("proof_refs") if isinstance(payload.get("proof_refs"), Mapping) else {}
    receipt = str(proof_refs.get("receipt_ref") or "")
    rows = _artifact_refs_from_read_model(
        payload,
        source_read_model_ref="generated/read_models/capital_hilton_invoice_operator_run_status.json",
        source_workflow_ref=str(payload.get("workflow_ref") or "capital_hilton_invoice_operator_run"),
        artifact_prefix="capital_hilton_invoice",
        source_receipt_ref=receipt,
        created_at=generated_at,
    )
    for row in rows:
        if row["artifact_ref"] == "artifact:capital_hilton_invoice_pdf":
            row["lineage_status"] = "active"
    return rows


def _capital_proposal_artifacts(read_model_root: Path, generated_at: str) -> list[dict[str, Any]]:
    payload = _load_json(read_model_root / "capital_hilton_business_development_proposal.json")
    proof_refs = payload.get("proof_refs") if isinstance(payload.get("proof_refs"), Mapping) else {}
    send_receipt = str(proof_refs.get("proposal_send_receipt_ref") or "")
    return _artifact_refs_from_read_model(
        payload,
        source_read_model_ref="generated/read_models/capital_hilton_business_development_proposal.json",
        source_workflow_ref="capital_hilton_business_development_proposal",
        artifact_prefix="capital_hilton_proposal",
        lineage_status_by_key={"proposal_send_receipt": "operator_sent"},
        source_receipt_ref=send_receipt,
        created_at=generated_at,
    )


def _live_arts_artifacts(artifact_search_roots: Sequence[Path], generated_at: str) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for root in artifact_search_roots:
        root = _rooted(root)
        if not root.exists():
            continue
        candidates.extend(root.rglob("*Live_Arts*scope_corrected*.pdf"))
    if not candidates:
        return []
    candidates = sorted(
        candidates,
        key=lambda path: (".openclaw_scope_quarantine" in str(path), "_2.pdf" not in str(path), str(path)),
    )
    path = candidates[0]
    return [
        _artifact(
            artifact_ref="artifact:live_arts_corrected_invoice_pdf",
            artifact_kind="pdf",
            path=str(path),
            source_workflow_ref="live_arts_invoice_pdf_approval",
            lineage_status="active",
            proof_refs=["generated/wiki/openclaw/Live Arts MD Invoice Automation.md"],
            created_at=generated_at,
        )
    ]


def _workroom_review_artifacts(read_model_root: Path, generated_at: str) -> list[dict[str, Any]]:
    payload = _load_json(read_model_root / "workroom_review_packet_index.json")
    packets = payload.get("packets")
    if not isinstance(packets, list):
        return []
    rows: list[dict[str, Any]] = []
    for packet in packets:
        if not isinstance(packet, Mapping):
            continue
        packet_id = str(packet.get("review_packet_id") or "")
        package_id = str(packet.get("package_id") or "")
        refs = packet.get("proof_refs")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            path = str(ref)
            suffix = Path(path).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".md"}:
                continue
            kind = _artifact_kind(path)
            label = "screenshot" if kind == "screenshot" else "report"
            rows.append(
                _artifact(
                    artifact_ref=f"artifact:workroom_review_packet_{_sanitize(packet_id.split(':')[-1])}_{label}",
                    artifact_kind=kind,
                    path=path,
                    source_workflow_ref="workroom_review_packet_index",
                    source_package_id=package_id,
                    lineage_status="test_only" if not _path_exists(path) else "active",
                    proof_refs=["generated/read_models/workroom_review_packet_index.json", packet_id],
                    created_at=generated_at,
                )
            )
    wiki = ROOT / "generated/wiki/openclaw/Workroom Review Packet Index.md"
    if wiki.exists():
        rows.append(
            _artifact(
                artifact_ref="artifact:workroom_review_packet_index_report",
                artifact_kind="report",
                path="generated/wiki/openclaw/Workroom Review Packet Index.md",
                source_workflow_ref="workroom_review_packet_index",
                lineage_status="active",
                proof_refs=["generated/read_models/workroom_review_packet_index.json"],
                created_at=generated_at,
            )
        )
    return rows


def _dedupe(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ref: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_ref[str(row["artifact_ref"])] = row
    return sorted(by_ref.values(), key=lambda item: str(item["artifact_ref"]))


def _write_sqlite(sqlite_path: Path, artifacts: list[Mapping[str, Any]]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS artifact_lineage")
        conn.execute(
            """
            CREATE TABLE artifact_lineage (
              artifact_ref TEXT PRIMARY KEY,
              artifact_kind TEXT NOT NULL,
              path TEXT NOT NULL,
              bridge_path TEXT NOT NULL,
              path_exists INTEGER NOT NULL,
              sha256 TEXT NOT NULL,
              source_workflow_ref TEXT NOT NULL,
              source_package_id TEXT NOT NULL,
              source_receipt_ref TEXT NOT NULL,
              lineage_status TEXT NOT NULL,
              trusted_for_action INTEGER NOT NULL,
              proof_refs_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO artifact_lineage (
              artifact_ref, artifact_kind, path, bridge_path, path_exists,
              sha256, source_workflow_ref, source_package_id,
              source_receipt_ref, lineage_status, trusted_for_action,
              proof_refs_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["artifact_ref"],
                    row["artifact_kind"],
                    row["path"],
                    row["bridge_path"],
                    1 if row["path_exists"] else 0,
                    row["sha256"],
                    row["source_workflow_ref"],
                    row["source_package_id"],
                    row["source_receipt_ref"],
                    row["lineage_status"],
                    1 if row["trusted_for_action"] else 0,
                    json.dumps(row["proof_refs"], sort_keys=True),
                    row["created_at"],
                )
                for row in artifacts
            ],
        )
        conn.commit()
    finally:
        conn.close()


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    artifact_search_roots: Sequence[Path] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    read_model_root = _rooted(read_model_root)
    search_roots = list(artifact_search_roots or DEFAULT_ARTIFACT_SEARCH_ROOTS)
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    artifacts = _dedupe(
        [
            *_st_annes_artifacts(read_model_root, generated_at),
            *_capital_invoice_artifacts(read_model_root, generated_at),
            *_capital_proposal_artifacts(read_model_root, generated_at),
            *_live_arts_artifacts(search_roots, generated_at),
            *_workroom_review_artifacts(read_model_root, generated_at),
        ]
    )
    _write_sqlite(sqlite_path, artifacts)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Registry records artifact truth only.",
            "It does not delete or overwrite artifacts.",
            "It does not mark paid or create send truth.",
            "Test/smoke artifacts are clearly marked test_only.",
            "trusted_for_action remains false by default.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "artifact_files_mutated": False,
            "artifact_files_deleted": False,
            "trusted_for_action_default": False,
            "business_action_performed": False,
            "email_sent": False,
            "gmail_opened": False,
            "browser_or_coupa_opened": False,
            "ledger_mutated": False,
            "workbook_mutated": False,
            "pdf_exported": False,
            "paid_marked": False,
            "submitted": False,
            "pushed": False,
        },
    }


def _wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Artifact Lineage Registry",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This registry records where artifacts came from and does not delete or overwrite artifacts.",
        "",
        "## Artifacts",
    ]
    for row in read_model["artifacts"]:
        lines.append(
            f"- {row['artifact_ref']} ({row['artifact_kind']}): {row['lineage_status']} - trusted for action: false"
        )
    lines.extend(
        [
            "",
            "Artifact lineage is evidence metadata only. It does not grant send, submit, ledger, paid, workbook, or PDF export authority.",
            "",
        ]
    )
    return "\n".join(lines)


def export_artifact_lineage_registry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    artifact_search_roots: Sequence[Path] | None = None,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        read_model_root=read_model_root,
        artifact_search_roots=artifact_search_roots,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    export_path = _rooted(export_root) / JSON_EXPORT_NAME
    bridge_path = _rooted(bridge_export_root) / JSON_EXPORT_NAME
    wiki_path = _rooted(wiki_path)
    _write_json(export_path, read_model)
    _write_json(bridge_path, read_model)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": str(export_path),
        "bridge_read_model_path": str(bridge_path),
        "sqlite_path": str(_rooted(sqlite_path)),
        "wiki_path": str(wiki_path),
        "artifact_count": str(read_model["artifact_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Artifact Lineage Registry V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_artifact_lineage_registry(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        sqlite_path=args.sqlite_path,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
