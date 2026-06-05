"""Gate Decision Ledger V0.

Publishes a non-financial ledger of package gate decisions. This records why a
gate is allowed, blocked, or waiting for approval without executing or granting
business authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import dynamic_card_packet


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Gate Decision Ledger.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/gate_decision_ledger.sqlite")

SCHEMA_VERSION = "gate_decision_ledger_v0"
READ_MODEL_ID = "gate_decision_ledger"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "GATE_DECISION_LEDGER_READY"
STATUS_NOT_READY = "GATE_DECISION_LEDGER_NOT_READY"

PRECONDITIONS = {
    "workflow_package_queue": {
        "filename": "workflow_package_queue_contract.json",
        "accepted_statuses": ["WORKFLOW_PACKAGE_QUEUE_V0_READY"],
    },
    "agent_voice_routing": {
        "filename": "agent_voice_routing_contract.json",
        "accepted_statuses": ["AGENT_VOICE_ROUTING_V0_READY"],
    },
    "automation_permission_registry": {
        "filename": "automation_permission_registry.json",
        "accepted_statuses": ["AUTOMATION_PERMISSION_REGISTRY_READY"],
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "external_provider_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

GATE_TEMPLATES = [
    {
        "gate_ref": "send_email",
        "decision": "approval_required",
        "speaker_ref": "guardian",
        "reason": "Email sending is a protected business action and requires explicit operator approval plus a separate executor gate.",
        "authority_requested": "email_send",
    },
    {
        "gate_ref": "coupa_submit",
        "decision": "approval_required",
        "speaker_ref": "guardian",
        "reason": "Coupa submit is a protected portal action and cannot be authorized by a read model.",
        "authority_requested": "portal_submit",
    },
    {
        "gate_ref": "ledger_post",
        "decision": "blocked",
        "speaker_ref": "guardian",
        "reason": "Business ledger posting requires separate ledger/payment evidence and is outside this governance ledger.",
        "authority_requested": "ledger_post",
    },
    {
        "gate_ref": "mark_paid",
        "decision": "blocked",
        "speaker_ref": "guardian",
        "reason": "Paid truth requires payment evidence; package or operator-display state cannot mark paid.",
        "authority_requested": "mark_paid",
    },
    {
        "gate_ref": "workbook_mutation",
        "decision": "approval_required",
        "speaker_ref": "guardian",
        "reason": "Workbook changes are source-data mutations and must stay behind operator approval.",
        "authority_requested": "workbook_mutation",
    },
    {
        "gate_ref": "pdf_export",
        "decision": "approval_required",
        "speaker_ref": "guardian",
        "reason": "PDF export can create client-facing artifacts and needs operator approval.",
        "authority_requested": "pdf_export",
    },
    {
        "gate_ref": "git_push",
        "decision": "blocked",
        "speaker_ref": "chief",
        "reason": "Build packets may commit after validation, but push remains outside local package authority.",
        "authority_requested": "git_push",
    },
    {
        "gate_ref": "worker_spawn",
        "decision": "blocked",
        "speaker_ref": "chief",
        "reason": "Worker packages can be staged, but workers are not spawned by governance surfaces.",
        "authority_requested": "worker_spawn",
    },
    {
        "gate_ref": "external_provider",
        "decision": "blocked",
        "speaker_ref": "guardian",
        "reason": "External providers and model runtimes are not used by local governance read models.",
        "authority_requested": "external_provider",
    },
    {
        "gate_ref": "local_only_read",
        "decision": "allowed",
        "speaker_ref": "openclaw",
        "reason": "Local read-model, wiki, and generated SQLite metadata reads are allowed for safe status work.",
        "authority_requested": "local_read",
    },
]


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


def _decision_id(gate_ref: str, decision: str) -> str:
    digest = hashlib.sha256(f"{gate_ref}:{decision}".encode("utf-8")).hexdigest()[:16]
    return f"gate_decision:{digest}"


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


def _decisions(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in GATE_TEMPLATES:
        gate_ref = str(template["gate_ref"])
        decision = str(template["decision"])
        rows.append(
            {
                "decision_id": _decision_id(gate_ref, decision),
                "source_request_ref": "governance_seed:track_b_gate_decision_ledger_v0",
                "package_id": "",
                "gate_ref": gate_ref,
                "decision": decision,
                "speaker_ref": str(template["speaker_ref"]),
                "reason": str(template["reason"]),
                "authority_requested": str(template["authority_requested"]),
                "authority_granted": False,
                "proof_refs": [
                    "generated/read_models/workflow_package_queue_contract.json",
                    "generated/read_models/automation_permission_registry.json",
                    "generated/read_models/agent_voice_routing_contract.json",
                ],
                "created_at": generated_at,
            }
        )
    return rows


def _write_sqlite(sqlite_path: Path, decisions: list[Mapping[str, Any]]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS gate_decisions")
        conn.execute(
            """
            CREATE TABLE gate_decisions (
              decision_id TEXT PRIMARY KEY,
              source_request_ref TEXT NOT NULL,
              package_id TEXT NOT NULL,
              gate_ref TEXT NOT NULL,
              decision TEXT NOT NULL,
              speaker_ref TEXT NOT NULL,
              reason TEXT NOT NULL,
              authority_requested TEXT NOT NULL,
              authority_granted INTEGER NOT NULL,
              proof_refs_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO gate_decisions (
              decision_id, source_request_ref, package_id, gate_ref, decision,
              speaker_ref, reason, authority_requested, authority_granted,
              proof_refs_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["decision_id"],
                    row["source_request_ref"],
                    row["package_id"],
                    row["gate_ref"],
                    row["decision"],
                    row["speaker_ref"],
                    row["reason"],
                    row["authority_requested"],
                    1 if row["authority_granted"] else 0,
                    json.dumps(row["proof_refs"], sort_keys=True),
                    row["created_at"],
                )
                for row in decisions
            ],
        )
        conn.commit()
    finally:
        conn.close()


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    decisions = _decisions(generated_at)
    _write_sqlite(sqlite_path, decisions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "decision_count": len(decisions),
        "decisions": decisions,
        "required_gates": [row["gate_ref"] for row in decisions],
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "This ledger records gate decisions only.",
            "It never grants authority.",
            "Guardian owns protected business/provider gates.",
            "Chief owns diagnostic/build gates.",
            "No business action was performed.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "authority_granted": False,
            "business_action_performed": False,
            "business_ledger_mutated": False,
            "email_sent": False,
            "gmail_opened": False,
            "browser_or_coupa_opened": False,
            "workbook_mutated": False,
            "pdf_exported": False,
            "paid_marked": False,
            "submitted": False,
            "pushed": False,
        },
    }
    return dynamic_card_packet.add_rail_card_packet(
        payload,
        "gate_decision_ledger",
        read_model_root=read_model_root,
        generated_at=generated_at,
    )


def _wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Gate Decision Ledger",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This is a non-financial governance ledger. It records why OpenClaw allows, blocks, or requires approval for package gates without touching the business ledger.",
        "",
        "## Gates",
    ]
    for row in read_model["decisions"]:
        lines.append(
            f"- {row['gate_ref']}: {row['decision']} ({row['speaker_ref']}) - authority granted: false"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "No email, Coupa submit, ledger post, workbook mutation, PDF export, paid marking, worker spawn, external provider call, or git push authority is granted here.",
            "",
        ]
    )
    return "\n".join(lines)


def export_gate_decision_ledger(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        read_model_root=read_model_root,
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
        "decision_count": str(read_model["decision_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Gate Decision Ledger V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_gate_decision_ledger(
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
