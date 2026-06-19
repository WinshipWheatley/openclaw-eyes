"""Build the overloaded entity-name registry from metadata.

The registry is declarative. It records what an overloaded noun can refer to,
but it never opens those backing stores and never constructs vault paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_GOVERNANCE_REGISTRY = ROOT / "generated/read_models/sqlite_governance_registry.json"
DEFAULT_OUTPUT = ROOT / "generated/system_knowledge/entity_name_registry.json"
SCHEMA_VERSION = "entity_name_registry_v0"
READ_MODEL_ID = "entity_name_registry"


LEDGER_REFERENTS: tuple[dict[str, Any], ...] = (
    {
        "referent_id": "business_ops",
        "display_name": "Business Ops ledger",
        "namespace": "business_ops",
        "location": ".openclaw/business_ops/ledger.sqlite",
        "default_surface": "business_ops",
        "aliases": (
            "business ops ledger",
            "business-ops ledger",
            "business_ops ledger",
            "ops ledger",
        ),
        "source_refs": ("business_ops_ledger.py:16",),
        "governance_path_contains": ".openclaw/business_ops/ledger.sqlite",
        "fallback_sensitivity": "operational",
        "read_authority": "metadata_or_approved_read_only",
    },
    {
        "referent_id": "control_plane",
        "display_name": "Polish loop control-plane ledger",
        "namespace": "control_plane",
        "location": "polish_loop/control_plane.sqlite3",
        "default_surface": "polish_loop",
        "aliases": (
            "control plane ledger",
            "control-plane ledger",
            "polish loop ledger",
            "polish-loop ledger",
        ),
        "source_refs": ("polish_loop/control_plane.sqlite3",),
        "governance_path_contains": "polish_loop/control_plane.sqlite3",
        "fallback_sensitivity": "operational",
        "read_authority": "metadata_or_approved_read_only",
    },
    {
        "referent_id": "gate_decision",
        "display_name": "Gate decision ledger",
        "namespace": "gate_decision",
        "location": "generated/system_knowledge/gate_decision_ledger.sqlite",
        "default_surface": "governance",
        "aliases": (
            "gate decision ledger",
            "gate-decision ledger",
            "governance ledger",
            "gate ledger",
        ),
        "source_refs": ("gate_decision_ledger.py:26",),
        "governance_path_contains": "gate_decision_ledger.sqlite",
        "fallback_sensitivity": "operational",
        "read_authority": "metadata_or_approved_read_only",
    },
    {
        "referent_id": "receipts",
        "display_name": "Proof and receipts ledger",
        "namespace": "receipts",
        "location": "generated/system_knowledge/proof_to_response_runtime.sqlite; generated/system_knowledge/universal_receipts.sqlite",
        "default_surface": "proof",
        "aliases": (
            "receipt ledger",
            "receipts ledger",
            "proof ledger",
            "proof receipts ledger",
        ),
        "source_refs": (
            "proof_to_response_runtime.py:29",
            "universal_receipt_envelope.py:26",
        ),
        "governance_path_contains": "proof_to_response_runtime.sqlite",
        "fallback_sensitivity": "operational",
        "read_authority": "metadata_or_approved_read_only",
    },
    {
        "referent_id": "gig_invoice",
        "display_name": "Gig invoice and work-log ledger",
        "namespace": "invoice_operations",
        "location": "generated/system_knowledge/capital_hilton_invoice_operator_run_status.sqlite; generated/system_knowledge/st_annes_invoice_status.sqlite; generated/system_knowledge/st_annes_monthly_work_log.sqlite",
        "default_surface": "finance",
        "aliases": (
            "gig ledger",
            "invoice ledger",
            "work log ledger",
            "work-log ledger",
            "capital hilton ledger",
            "st anne ledger",
            "st anne's ledger",
            "st annes ledger",
        ),
        "source_refs": (
            "capital_hilton_invoice_operator_run_status.py",
            "st_annes_invoice_status.py",
            "finance_state.py:8",
        ),
        "governance_path_contains": "capital_hilton_invoice_operator_run_status.sqlite",
        "fallback_sensitivity": "operational",
        "read_authority": "metadata_or_approved_read_only",
    },
    {
        "referent_id": "bank_finance_vault",
        "display_name": "Bank and finance vault ledger",
        "namespace": "bank_finance_vault",
        "location": "VAULT_WALL_REFERENT_ONLY_NO_PATH",
        "default_surface": "NONE",
        "aliases": (
            "bank ledger",
            "finance ledger",
            "financial ledger",
            "bank finance ledger",
            "vault ledger",
        ),
        "source_refs": (
            "OPENCLAW_RUNTIME.md:52",
            "maestro_cassandra_responder.py:41",
            "fabric_peer.py:134",
        ),
        "governance_path_contains": "token_vault.sqlite",
        "fallback_sensitivity": "sensitive-vault",
        "read_authority": "requires_operator_proof",
    },
)


INBOX_REFERENTS: tuple[dict[str, Any], ...] = (
    {
        "referent_id": "gmail_inbox",
        "display_name": "Gmail inbox",
        "namespace": "gmail",
        "location": "GMAIL_CONNECTOR_METADATA_ONLY",
        "default_surface": "gmail",
        "aliases": ("gmail inbox", "email inbox", "mail inbox"),
        "source_refs": ("business_ops_intent.py",),
        "fallback_sensitivity": "operational",
        "read_authority": "existing_gmail_metadata_staging_only",
    },
    {
        "referent_id": "bus_inbox",
        "display_name": "Mission-control bus inbox",
        "namespace": "mission_control_bus",
        "location": "mission_control_capture_requests/inbox",
        "default_surface": "mission_control",
        "aliases": ("bus inbox", "mission control inbox", "mission-control inbox"),
        "source_refs": ("openclaw_request_processor.py:53",),
        "fallback_sensitivity": "operational",
        "read_authority": "local_metadata_only",
    },
    {
        "referent_id": "operator_action_inbox",
        "display_name": "Operator action inbox",
        "namespace": "operator_action",
        "location": "operator_action_inbox",
        "default_surface": "operator_action",
        "aliases": ("operator action inbox", "operator-action inbox", "action inbox"),
        "source_refs": ("operator_action_inbox.py",),
        "fallback_sensitivity": "operational",
        "read_authority": "local_metadata_only",
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_governance(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def _governance_rows(payload: Mapping[str, Any], path_contains: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path_contains:
        return rows
    needle = path_contains.lower()
    for row in payload.get("databases", ()):
        if not isinstance(row, Mapping):
            continue
        path = str(row.get("path") or "")
        if needle in path.lower():
            rows.append(
                {
                    "path": path,
                    "classification": row.get("classification"),
                    "owner_lane": row.get("owner_lane"),
                    "purpose": row.get("purpose"),
                    "consolidation_risk": row.get("consolidation_risk"),
                    "canonical_truth_allowed": row.get("canonical_truth_allowed"),
                    "writable_by_automation": row.get("writable_by_automation"),
                    "db_ref": row.get("db_ref"),
                }
            )
    return rows


def _sensitivity_from_governance(spec: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    if spec.get("fallback_sensitivity") == "sensitive-vault":
        return "sensitive-vault"
    for row in rows:
        text = " ".join(
            str(row.get(key) or "").lower()
            for key in ("path", "classification", "owner_lane", "purpose", "consolidation_risk")
        )
        if "vault" in text or "privacy" in text:
            return "sensitive-vault"
        if "private" in text:
            return "sensitive-vault"
    return str(spec.get("fallback_sensitivity") or "operational")


def _referent(spec: Mapping[str, Any], governance: Mapping[str, Any]) -> dict[str, Any]:
    rows = _governance_rows(governance, str(spec.get("governance_path_contains") or ""))
    sensitivity = _sensitivity_from_governance(spec, rows)
    return {
        "referent_id": spec["referent_id"],
        "display_name": spec["display_name"],
        "namespace": spec["namespace"],
        "location": spec["location"],
        "default_surface": spec["default_surface"],
        "aliases": list(spec.get("aliases") or ()),
        "sensitivity": sensitivity,
        "read_authority": spec["read_authority"],
        "source_refs": list(spec.get("source_refs") or ()),
        "sqlite_governance_registry_rows": rows,
        "sensitivity_source": (
            "sqlite_governance_registry"
            if rows
            else "verified_source_ref_operational_default"
        ),
    }


def build_entity_name_registry(
    *,
    governance_registry_path: Path = DEFAULT_GOVERNANCE_REGISTRY,
    generated_at: str | None = None,
) -> dict[str, Any]:
    governance = _load_governance(governance_registry_path)
    ledger = [_referent(spec, governance) for spec in LEDGER_REFERENTS]
    inbox = [_referent(spec, governance) for spec in INBOX_REFERENTS]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or _now(),
        "source_refs": [
            str(governance_registry_path.relative_to(ROOT) if governance_registry_path.is_relative_to(ROOT) else governance_registry_path),
            "/mnt/e/openclaw/orchestration/_LAUNCH-NAME-DISAMBIGUATION-ledger.md",
            "OPENCLAW_RUNTIME.md:52",
        ],
        "names": {
            "ledger": ledger,
            "inbox": inbox,
        },
        "machine_proof": {
            "sqlite_database_opened": False,
            "vault_path_constructed": False,
            "bank_ledger_read_performed": False,
            "metadata_only": True,
            "ledger_referent_count": len(ledger),
            "bank_finance_vault_default_surface": "NONE",
        },
    }


def export_entity_name_registry(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    governance_registry_path: Path = DEFAULT_GOVERNANCE_REGISTRY,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_entity_name_registry(
        governance_registry_path=governance_registry_path,
        generated_at=generated_at,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--governance-registry", type=Path, default=DEFAULT_GOVERNANCE_REGISTRY)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    args = parser.parse_args()

    payload = export_entity_name_registry(
        args.output,
        governance_registry_path=args.governance_registry,
        generated_at=args.generated_at,
    )
    if args.format == "summary":
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "ledger_referent_count": payload["machine_proof"]["ledger_referent_count"],
                    "bank_finance_vault_default_surface": payload["machine_proof"]["bank_finance_vault_default_surface"],
                    "vault_path_constructed": payload["machine_proof"]["vault_path_constructed"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
