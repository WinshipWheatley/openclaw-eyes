"""Live LM activation requirements v0.

Read-only blocker/receipt contract for future LM1/LM2 activation. It makes the
remaining live-model blockers explicit without enabling models, providers,
tools, or production actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import live_lm_shadow_trial
import token_vault


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "live_lm_activation_requirements_v0"
READ_MODEL_ID = "live_lm_activation_requirements"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LIVE_LM_ACTIVATION_BLOCKED_REQUIREMENTS_MISSING"
DEFAULT_ACTIVATION_RECEIPT_DB_PATH = Path(".openclaw/activation/activation_receipts.sqlite")
ACTIVATION_RECEIPT_TABLES = (
    "activation_receipt_metadata",
    "activation_receipt_contracts",
    "activation_receipt_fixture_validations",
    "activation_production_receipts",
)

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "provider_key_material_access_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
}

FORBIDDEN_RECEIPT_TRUE_CONTROLS = (
    "live_model_call_performed",
    "model_api_call_performed",
    "network_performed",
    "provider_key_material_access_performed",
    "credential_access_performed",
    "tool_execution_performed",
    "agent_dispatch_performed",
    "worker_dispatch_performed",
    "workflow_execution_performed",
    "external_action_performed",
    "send_submit_performed",
    "approval_execution_performed",
    "ledger_posting_performed",
    "production_state_mutation_performed",
)


@dataclass(frozen=True)
class ActivationReceiptRequirement:
    receipt_id: str
    receipt_type: str
    human_label: str
    required_for_lanes: tuple[str, ...]
    present: bool
    blocks_live_lm1: bool
    blocks_live_lm2: bool
    blocks_provider_activation: bool
    operator_copy: str
    next_safe_move: str


@dataclass(frozen=True)
class ActivationReceiptContract:
    receipt_type: str
    beam_id: str
    human_label: str
    receipt_contract_status: str
    can_be_collected_without_live_authority: bool
    required_true_controls: tuple[str, ...]
    required_false_controls: tuple[str, ...]
    production_receipt_required: bool
    operator_approval_required: bool
    governed_review_required: bool
    fixture_validation_allowed: bool
    blocks_live_lm1: bool
    blocks_live_lm2: bool
    authority_boundary: dict[str, bool]
    operator_copy: str
    next_safe_move: str


@dataclass(frozen=True)
class ActivationReceiptValidationResult:
    receipt_type: str
    validation_status: str
    valid_for_contract: bool
    valid_as_test_fixture: bool
    satisfies_production_activation: bool
    receipt_type_matches: bool
    missing_true_controls: tuple[str, ...]
    unsafe_true_controls: tuple[str, ...]
    unsafe_authority_controls: tuple[str, ...]
    production_receipt_present: bool
    operator_approved: bool
    governed_review_source: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ActivationProductionReceiptStatus:
    receipt_type: str
    beam_id: str
    human_label: str
    present: bool
    receipt_status: str
    operator_approved: bool
    governed_review_source: bool
    payload_hash: str
    recorded_at: str
    satisfies_production_activation: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ActivationProductionReceiptIntakeResult:
    receipt_type: str
    intake_status: str
    recorded: bool
    valid_for_contract: bool
    satisfies_production_activation: bool
    payload_hash: str
    db_path: str
    production_receipt_rows_present: int
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ActivationReceiptSubstrate:
    substrate_id: str
    db_path: str
    exists: bool
    required_tables: tuple[str, ...]
    present_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]
    contract_rows_persisted: int
    fixture_validation_rows_persisted: int
    production_receipt_rows_present: int
    valid_production_receipt_rows_present: int
    contracts_backed_by_sqlite: bool
    fixtures_backed_by_sqlite: bool
    production_receipt_intake_ready: bool
    production_receipt_writer_authority_free: bool
    satisfies_production_activation: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


PRODUCTION_ACTIVATION_BEAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "beam_id": "production_token_vault",
        "human_label": "Production token vault",
        "receipt_types": ("production_token_vault_ready_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs the production token vault to be ready before live model lanes can review sensitive work.",
    },
    {
        "beam_id": "provider_model_receipts",
        "human_label": "Provider/model receipts",
        "receipt_types": ("provider_policy_receipt", "model_selection_policy_receipt"),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs recorded provider and model-selection receipts for each live lane.",
    },
    {
        "beam_id": "live_enablement_receipt",
        "human_label": "Live enablement receipt",
        "receipt_types": ("live_model_enablement_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs an explicit live enablement receipt before LM1 or LM2 can leave shadow mode.",
    },
    {
        "beam_id": "privacy_receipt",
        "human_label": "Privacy receipt",
        "receipt_types": ("privacy_policy_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a production privacy receipt before live model-shaped packages can be used.",
    },
    {
        "beam_id": "rollback_disable_receipt",
        "human_label": "Rollback/disable receipt",
        "receipt_types": ("rollback_disable_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a proven way to disable live model lanes before activation review.",
    },
    {
        "beam_id": "device_trust_live_activation",
        "human_label": "Device trust / live activation",
        "receipt_types": ("device_trust_live_activation_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs trusted-device and live-activation proof for Mission Control traffic before it can feed live model lanes.",
    },
    {
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM1/LM2 production policy",
        "receipt_types": ("real_lm1_production_policy_receipt", "real_lm2_production_policy_receipt"),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a real LM1/LM2 production policy for routing, privacy, fallback, and rollback before live activation review.",
    },
)


REMAINING_RECEIPT_CONTRACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "receipt_type": "provider_policy_receipt",
        "beam_id": "provider_model_receipts",
        "human_label": "Provider policy receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "provider_policy_defined",
            "allowed_context_classes_declared",
            "forbidden_context_classes_declared",
            "provider_key_access_denied",
            "network_authority_denied",
        ),
        "required_false_controls": (
            "provider_key_material_included",
            "provider_api_call_enabled",
            "live_lm_call_enabled",
            "network_enabled",
        ),
        "operator_copy": "Provider policy can be reviewed without activating any provider or API key.",
    },
    {
        "receipt_type": "model_selection_policy_receipt",
        "beam_id": "provider_model_receipts",
        "human_label": "Model selection policy receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "lm1_model_class_policy_defined",
            "lm2_model_class_policy_defined",
            "fallback_model_class_defined",
            "model_self_selection_denied",
            "structured_output_requirement_defined",
        ),
        "required_false_controls": (
            "model_call_performed",
            "runtime_model_router_enabled",
            "provider_api_call_enabled",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Model-selection policy can be checked as metadata without calling a model.",
    },
    {
        "receipt_type": "live_model_enablement_receipt",
        "beam_id": "live_enablement_receipt",
        "human_label": "Live enablement receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "explicit_operator_enablement_required",
            "default_state_not_active",
            "all_other_receipts_required_first",
            "operator_visible_status_required",
        ),
        "required_false_controls": (
            "live_lm_enabled_by_receipt_shape",
            "provider_api_call_enabled",
            "tool_execution_enabled",
            "production_state_mutation_enabled",
        ),
        "operator_copy": "Live enablement has a receipt shape, but the shape itself cannot enable live models.",
    },
    {
        "receipt_type": "rollback_disable_receipt",
        "beam_id": "rollback_disable_receipt",
        "human_label": "Rollback/disable receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "disable_switch_defined",
            "rollback_path_defined",
            "operator_visible_disable_defined",
            "audit_log_required",
            "default_disable_available",
        ),
        "required_false_controls": (
            "rollback_requires_provider_access",
            "disable_depends_on_network",
            "production_state_mutation_enabled",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Rollback and disable controls can be reviewed before any live model activation.",
    },
    {
        "receipt_type": "device_trust_live_activation_receipt",
        "beam_id": "device_trust_live_activation",
        "human_label": "Device trust / live activation receipt",
        "blocks": ("Gate 1", "LM1", "LM2"),
        "required_true_controls": (
            "trusted_device_registry_required",
            "source_device_binding_required",
            "thread_scope_binding_required",
            "request_replay_protection_required",
            "scoped_response_route_required",
        ),
        "required_false_controls": (
            "untrusted_device_activation_allowed",
            "arbitrary_destination_allowed",
            "lm_inferred_routing_allowed",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Device trust can be shaped as a receipt without granting live activation.",
    },
    {
        "receipt_type": "real_lm1_production_policy_receipt",
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM1 production policy receipt",
        "blocks": ("LM1",),
        "required_true_controls": (
            "lm1_intent_only_policy_defined",
            "machine_intent_candidate_schema_required",
            "gate2_ingest_required",
            "privacy_minimization_required",
            "lm1_no_tool_authority_defined",
        ),
        "required_false_controls": (
            "lm1_can_execute_tools",
            "lm1_can_grant_authority",
            "lm1_can_dispatch_workers",
            "raw_sensitive_values_allowed",
        ),
        "operator_copy": "LM1 production policy can be reviewed as intent-proposal-only, with no tool or authority path.",
    },
    {
        "receipt_type": "real_lm2_production_policy_receipt",
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM2 production policy receipt",
        "blocks": ("LM2",),
        "required_true_controls": (
            "lm2_role_package_policy_defined",
            "gate3_package_required",
            "guardian_gate_required",
            "forbidden_tools_explicit",
            "no_send_submit_without_receipts",
        ),
        "required_false_controls": (
            "lm2_can_bypass_guardian",
            "lm2_can_send_submit_without_receipt",
            "lm2_can_post_ledger",
            "raw_sensitive_values_allowed",
        ),
        "operator_copy": "LM2 production policy can be reviewed as package-bound role response, with Guardian still behind it.",
    },
)


def production_activation_beams(
    *,
    token_vault_receipt_present: bool = False,
    privacy_policy_receipt_present: bool = False,
    receipt_contracts_ready: bool = False,
    production_receipts_present: Mapping[str, bool] | None = None,
) -> tuple[dict[str, Any], ...]:
    production_receipts_present = production_receipts_present or {}
    statuses = {
        "production_token_vault": "PRESENT" if token_vault_receipt_present else "MISSING",
        "privacy_receipt": "PRESENT" if privacy_policy_receipt_present else "MISSING",
    }
    if receipt_contracts_ready:
        for spec in PRODUCTION_ACTIVATION_BEAM_SPECS:
            beam_id = str(spec["beam_id"])
            if beam_id in statuses:
                continue
            receipt_types = tuple(spec["receipt_types"])
            statuses[beam_id] = (
                "PRESENT"
                if all(production_receipts_present.get(receipt_type, False) for receipt_type in receipt_types)
                else "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
            )
    return tuple({**item, "status": statuses.get(str(item["beam_id"]), item["status"])} for item in PRODUCTION_ACTIVATION_BEAM_SPECS)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _connect_activation_receipts(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def _create_activation_receipt_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
CREATE TABLE IF NOT EXISTS activation_receipt_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activation_receipt_contracts (
  receipt_type TEXT PRIMARY KEY,
  beam_id TEXT NOT NULL,
  human_label TEXT NOT NULL,
  receipt_contract_status TEXT NOT NULL,
  contract_hash TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activation_receipt_fixture_validations (
  receipt_type TEXT PRIMARY KEY,
  validation_status TEXT NOT NULL,
  valid_for_contract INTEGER NOT NULL,
  valid_as_test_fixture INTEGER NOT NULL,
  satisfies_production_activation INTEGER NOT NULL CHECK (satisfies_production_activation = 0),
  validation_hash TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activation_production_receipts (
  receipt_type TEXT PRIMARY KEY,
  receipt_status TEXT NOT NULL,
  operator_approved INTEGER NOT NULL,
  governed_review_source INTEGER NOT NULL,
  payload_hash TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
"""
    )


def ensure_activation_receipt_substrate(
    path: Path = DEFAULT_ACTIVATION_RECEIPT_DB_PATH,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contracts = activation_receipt_contracts()
    fixture_results = activation_receipt_contract_fixture_results()
    with _connect_activation_receipts(path) as conn:
        _create_activation_receipt_schema(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO activation_receipt_metadata (key, value, updated_at)
VALUES (?, ?, ?)
""",
            ("schema_version", SCHEMA_VERSION, generated_at),
        )
        for contract in contracts:
            contract_hash = "sha256:" + hashlib.sha256(stable_json(contract).encode("utf-8")).hexdigest()
            conn.execute(
                """
INSERT OR REPLACE INTO activation_receipt_contracts
  (receipt_type, beam_id, human_label, receipt_contract_status, contract_hash, recorded_at)
VALUES (?, ?, ?, ?, ?, ?)
""",
                (
                    contract["receipt_type"],
                    contract["beam_id"],
                    contract["human_label"],
                    contract["receipt_contract_status"],
                    contract_hash,
                    generated_at,
                ),
            )
        for result in fixture_results:
            validation_hash = "sha256:" + hashlib.sha256(stable_json(result).encode("utf-8")).hexdigest()
            conn.execute(
                """
INSERT OR REPLACE INTO activation_receipt_fixture_validations
  (receipt_type, validation_status, valid_for_contract, valid_as_test_fixture,
   satisfies_production_activation, validation_hash, recorded_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                (
                    result["receipt_type"],
                    result["validation_status"],
                    int(bool(result["valid_for_contract"])),
                    int(bool(result["valid_as_test_fixture"])),
                    0,
                    validation_hash,
                    generated_at,
                ),
            )
        conn.commit()
    return inspect_activation_receipt_substrate(path, create_if_missing=False)


def inspect_activation_receipt_substrate(
    path: Path = DEFAULT_ACTIVATION_RECEIPT_DB_PATH,
    *,
    create_if_missing: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if create_if_missing and not path.exists():
        return ensure_activation_receipt_substrate(path, generated_at=generated_at or DEFAULT_GENERATED_AT)
    if not path.exists():
        substrate = ActivationReceiptSubstrate(
            substrate_id=f"activation_receipt_substrate:{_short_hash(path)}",
            db_path=path.as_posix(),
            exists=False,
            required_tables=ACTIVATION_RECEIPT_TABLES,
            present_tables=(),
            missing_tables=ACTIVATION_RECEIPT_TABLES,
            contract_rows_persisted=0,
            fixture_validation_rows_persisted=0,
            production_receipt_rows_present=0,
            valid_production_receipt_rows_present=0,
            contracts_backed_by_sqlite=False,
            fixtures_backed_by_sqlite=False,
            production_receipt_intake_ready=False,
            production_receipt_writer_authority_free=True,
            satisfies_production_activation=False,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Create the local activation receipt substrate before production activation review.",
        )
        return asdict(substrate)

    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        present_tables = tuple(sorted(row[0] for row in table_rows))

        def count_rows(table_name: str) -> int:
            if table_name not in present_tables:
                return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

        contract_count = count_rows("activation_receipt_contracts")
        fixture_count = count_rows("activation_receipt_fixture_validations")
        production_count = count_rows("activation_production_receipts")
        valid_production_count = 0
        if "activation_production_receipts" in present_tables:
            valid_production_count = int(
                conn.execute(
                    """
SELECT COUNT(*) FROM activation_production_receipts
WHERE receipt_status = 'VALID_PRODUCTION_RECEIPT'
  AND operator_approved = 1
  AND governed_review_source = 1
"""
                ).fetchone()[0]
            )

    missing_tables = tuple(table for table in ACTIVATION_RECEIPT_TABLES if table not in present_tables)
    expected_count = len(REMAINING_RECEIPT_CONTRACT_SPECS)
    production_intake_ready = (
        "activation_production_receipts" in present_tables
        and contract_count == expected_count
        and fixture_count == expected_count
    )
    substrate = ActivationReceiptSubstrate(
        substrate_id=f"activation_receipt_substrate:{_short_hash(path, present_tables, contract_count, fixture_count, production_count)}",
        db_path=path.as_posix(),
        exists=True,
        required_tables=ACTIVATION_RECEIPT_TABLES,
        present_tables=present_tables,
        missing_tables=missing_tables,
        contract_rows_persisted=contract_count,
        fixture_validation_rows_persisted=fixture_count,
        production_receipt_rows_present=production_count,
        valid_production_receipt_rows_present=valid_production_count,
        contracts_backed_by_sqlite=contract_count == expected_count,
        fixtures_backed_by_sqlite=fixture_count == expected_count,
        production_receipt_intake_ready=production_intake_ready,
        production_receipt_writer_authority_free=True,
        satisfies_production_activation=production_intake_ready and valid_production_count == expected_count,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Activation receipt contracts and production receipt intake are backed by local SQLite proof; collect governed production receipts before activation."
            if production_intake_ready
            else "Repair the activation receipt substrate before production activation review."
        ),
    )
    return asdict(substrate)


def activation_receipt_contracts() -> tuple[dict[str, Any], ...]:
    contracts: list[dict[str, Any]] = []
    for spec in REMAINING_RECEIPT_CONTRACT_SPECS:
        blocks = tuple(spec["blocks"])
        contracts.append(
            asdict(
                ActivationReceiptContract(
                    receipt_type=str(spec["receipt_type"]),
                    beam_id=str(spec["beam_id"]),
                    human_label=str(spec["human_label"]),
                    receipt_contract_status="RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING",
                    can_be_collected_without_live_authority=True,
                    required_true_controls=tuple(spec["required_true_controls"]),
                    required_false_controls=tuple(spec["required_false_controls"]),
                    production_receipt_required=True,
                    operator_approval_required=True,
                    governed_review_required=True,
                    fixture_validation_allowed=True,
                    blocks_live_lm1="LM1" in blocks,
                    blocks_live_lm2="LM2" in blocks,
                    authority_boundary=dict(AUTHORITY_BOUNDARY),
                    operator_copy=str(spec["operator_copy"]),
                    next_safe_move="Use this contract for review/test receipts only; do not mark production-present without governed approval.",
                )
            )
        )
    return tuple(contracts)


def activation_receipt_contract_by_type(receipt_type: str) -> dict[str, Any]:
    for contract in activation_receipt_contracts():
        if contract["receipt_type"] == receipt_type:
            return contract
    raise ValueError(f"unknown activation receipt type: {receipt_type}")


def _fixture_candidate_for_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    candidate = {
        "receipt_type": contract["receipt_type"],
        "test_fixture": True,
        "production_receipt": False,
        "operator_approved": False,
        "receipt_source": "test_fixture",
    }
    candidate.update({name: True for name in contract["required_true_controls"]})
    candidate.update({name: False for name in contract["required_false_controls"]})
    return candidate


def validate_activation_receipt_candidate(receipt_type: str, candidate: Mapping[str, Any]) -> dict[str, Any]:
    contract = activation_receipt_contract_by_type(receipt_type)
    receipt_type_matches = str(candidate.get("receipt_type") or receipt_type) == receipt_type
    missing_true = tuple(name for name in contract["required_true_controls"] if bool(candidate.get(name, False)) is not True)
    unsafe_true = tuple(name for name in contract["required_false_controls"] if bool(candidate.get(name, False)) is not False)
    unsafe_authority = tuple(
        name
        for name in (*AUTHORITY_BOUNDARY.keys(), *FORBIDDEN_RECEIPT_TRUE_CONTROLS)
        if bool(candidate.get(name, False)) is True
    )
    valid_for_contract = receipt_type_matches and not missing_true and not unsafe_true and not unsafe_authority
    test_fixture = bool(candidate.get("test_fixture", False))
    production_receipt = bool(candidate.get("production_receipt", False))
    operator_approved = bool(candidate.get("operator_approved", False))
    governed_review_source = str(candidate.get("receipt_source") or "") == "governed_production_review"
    satisfies_production = valid_for_contract and production_receipt and operator_approved and governed_review_source
    result = ActivationReceiptValidationResult(
        receipt_type=receipt_type,
        validation_status=(
            "VALID_TEST_FIXTURE_ONLY"
            if valid_for_contract and test_fixture and not satisfies_production
            else "VALID_PRODUCTION_RECEIPT"
            if satisfies_production
            else "INVALID_RECEIPT_CANDIDATE"
        ),
        valid_for_contract=valid_for_contract,
        valid_as_test_fixture=valid_for_contract and test_fixture,
        satisfies_production_activation=satisfies_production,
        receipt_type_matches=receipt_type_matches,
        missing_true_controls=missing_true,
        unsafe_true_controls=unsafe_true,
        unsafe_authority_controls=unsafe_authority,
        production_receipt_present=production_receipt,
        operator_approved=operator_approved,
        governed_review_source=governed_review_source,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Treat this as fixture proof only; collect a governed production receipt before activation."
            if valid_for_contract and not satisfies_production
            else "Keep live models off until every activation receipt is present."
            if satisfies_production
            else "Repair missing or unsafe controls before this receipt can be considered."
        ),
    )
    return asdict(result)


def activation_receipt_contract_fixture_results() -> tuple[dict[str, Any], ...]:
    return tuple(
        validate_activation_receipt_candidate(contract["receipt_type"], _fixture_candidate_for_contract(contract))
        for contract in activation_receipt_contracts()
    )


def _activation_production_receipt_hash(receipt_type: str, candidate: Mapping[str, Any], validation: Mapping[str, Any]) -> str:
    metadata_only_payload = {
        "receipt_type": receipt_type,
        "candidate_hash": "sha256:" + hashlib.sha256(stable_json(dict(candidate)).encode("utf-8")).hexdigest(),
        "validation_status": validation["validation_status"],
        "recorded_as_metadata_only": True,
    }
    return "sha256:" + hashlib.sha256(stable_json(metadata_only_payload).encode("utf-8")).hexdigest()


def activation_production_receipt_statuses(
    path: Path = DEFAULT_ACTIVATION_RECEIPT_DB_PATH,
    *,
    create_if_missing: bool = True,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], ...]:
    if create_if_missing:
        ensure_activation_receipt_substrate(path, generated_at=generated_at or DEFAULT_GENERATED_AT)
    rows: dict[str, dict[str, Any]] = {}
    if path.exists():
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            table_exists = conn.execute(
                """
SELECT COUNT(*) FROM sqlite_master
WHERE type = 'table' AND name = 'activation_production_receipts'
"""
            ).fetchone()[0]
            if table_exists:
                for row in conn.execute(
                    """
SELECT receipt_type, receipt_status, operator_approved, governed_review_source,
       payload_hash, recorded_at
FROM activation_production_receipts
"""
                ).fetchall():
                    rows[str(row[0])] = {
                        "receipt_status": str(row[1]),
                        "operator_approved": bool(row[2]),
                        "governed_review_source": bool(row[3]),
                        "payload_hash": str(row[4]),
                        "recorded_at": str(row[5]),
                    }

    statuses: list[dict[str, Any]] = []
    for contract in activation_receipt_contracts():
        row = rows.get(contract["receipt_type"], {})
        present = (
            row.get("receipt_status") == "VALID_PRODUCTION_RECEIPT"
            and bool(row.get("operator_approved")) is True
            and bool(row.get("governed_review_source")) is True
            and str(row.get("payload_hash") or "").startswith("sha256:")
        )
        statuses.append(
            asdict(
                ActivationProductionReceiptStatus(
                    receipt_type=contract["receipt_type"],
                    beam_id=contract["beam_id"],
                    human_label=contract["human_label"],
                    present=present,
                    receipt_status=str(row.get("receipt_status") or "MISSING_PRODUCTION_RECEIPT"),
                    operator_approved=bool(row.get("operator_approved", False)),
                    governed_review_source=bool(row.get("governed_review_source", False)),
                    payload_hash=str(row.get("payload_hash") or ""),
                    recorded_at=str(row.get("recorded_at") or ""),
                    satisfies_production_activation=present,
                    authority_boundary=dict(AUTHORITY_BOUNDARY),
                    next_safe_move=(
                        "Keep this receipt as activation evidence; live models still require the full receipt set and explicit enablement."
                        if present
                        else "Collect this receipt through governed production review before live activation can be considered."
                    ),
                )
            )
        )
    return tuple(statuses)


def record_activation_production_receipt_candidate(
    receipt_type: str,
    candidate: Mapping[str, Any],
    path: Path = DEFAULT_ACTIVATION_RECEIPT_DB_PATH,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    ensure_activation_receipt_substrate(path, generated_at=generated_at)
    validation = validate_activation_receipt_candidate(receipt_type, candidate)
    payload_hash = _activation_production_receipt_hash(receipt_type, candidate, validation)
    if not validation["satisfies_production_activation"]:
        substrate = inspect_activation_receipt_substrate(path, create_if_missing=False)
        result = ActivationProductionReceiptIntakeResult(
            receipt_type=receipt_type,
            intake_status=validation["validation_status"],
            recorded=False,
            valid_for_contract=validation["valid_for_contract"],
            satisfies_production_activation=False,
            payload_hash=payload_hash,
            db_path=path.as_posix(),
            production_receipt_rows_present=substrate["production_receipt_rows_present"],
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Reject this receipt candidate until missing or unsafe controls are repaired.",
        )
        return asdict(result)

    with _connect_activation_receipts(path) as conn:
        _create_activation_receipt_schema(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO activation_production_receipts
  (receipt_type, receipt_status, operator_approved, governed_review_source, payload_hash, recorded_at)
VALUES (?, ?, ?, ?, ?, ?)
""",
            (
                receipt_type,
                validation["validation_status"],
                int(bool(validation["operator_approved"])),
                int(bool(validation["governed_review_source"])),
                payload_hash,
                generated_at,
            ),
        )
        conn.commit()
    substrate = inspect_activation_receipt_substrate(path, create_if_missing=False)
    result = ActivationProductionReceiptIntakeResult(
        receipt_type=receipt_type,
        intake_status=validation["validation_status"],
        recorded=True,
        valid_for_contract=True,
        satisfies_production_activation=True,
        payload_hash=payload_hash,
        db_path=path.as_posix(),
        production_receipt_rows_present=substrate["production_receipt_rows_present"],
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Receipt recorded as metadata-only evidence; live models remain off until the full receipt set and explicit enablement exist.",
    )
    return asdict(result)


def required_receipts(
    *,
    live_shadow_receipt_present: bool = False,
    production_token_vault_receipt_present: bool = False,
    privacy_policy_receipt_present: bool = False,
    production_receipts_present: Mapping[str, bool] | None = None,
) -> tuple[dict[str, Any], ...]:
    production_receipts_present = production_receipts_present or {}
    specs = (
        (
            "live_model_enablement_receipt",
            "Operator enablement",
            ("LM1", "LM2"),
            "OpenClaw needs an explicit operator enablement receipt before live models can turn on.",
        ),
        (
            "provider_policy_receipt",
            "Provider policy",
            ("LM1", "LM2"),
            "OpenClaw needs a recorded provider policy choice before any provider can be used.",
        ),
        (
            "model_selection_policy_receipt",
            "Model selection policy",
            ("LM1", "LM2"),
            "OpenClaw needs a model-selection receipt that matches the lane, privacy class, and risk.",
        ),
        (
            "privacy_policy_receipt",
            "Privacy policy",
            ("LM1", "LM2"),
            "OpenClaw needs the production privacy policy receipt before live model-shaped packages can leave shadow mode.",
        ),
        (
            "production_token_vault_ready_receipt",
            "Production token vault",
            ("LM1", "LM2"),
            "OpenClaw needs production token-vault readiness before sensitive live model packages are allowed.",
        ),
        (
            "shadow_comparison_live_run_receipt",
            "Live-shadow comparison",
            ("LM1", "LM2"),
            "OpenClaw needs successful real shadow comparison receipts beyond fixtures.",
        ),
        (
            "rollback_disable_receipt",
            "Rollback switch",
            ("LM1", "LM2"),
            "OpenClaw needs a rollback or disable receipt before any future live model lane can be reviewed.",
        ),
        (
            "device_trust_live_activation_receipt",
            "Device trust / live activation",
            ("Gate 1", "LM1", "LM2"),
            "OpenClaw needs a trusted-device and live-activation receipt before real Mission Control traffic can feed live model lanes.",
        ),
        (
            "real_lm1_production_policy_receipt",
            "Real LM1 production policy",
            ("LM1",),
            "OpenClaw needs a real LM1 production policy before the intent-proposal lane can be reviewed.",
        ),
        (
            "real_lm2_production_policy_receipt",
            "Real LM2 production policy",
            ("LM2",),
            "OpenClaw needs a real LM2 production policy before the role-response lane can be reviewed.",
        ),
    )
    return tuple(
        asdict(
            ActivationReceiptRequirement(
                receipt_id=f"activation_receipt:{_short_hash(receipt_type)}",
                receipt_type=receipt_type,
                human_label=human_label,
                required_for_lanes=lanes,
                present=(
                    (receipt_type == "shadow_comparison_live_run_receipt" and live_shadow_receipt_present)
                    or (receipt_type == "production_token_vault_ready_receipt" and production_token_vault_receipt_present)
                    or (receipt_type == "privacy_policy_receipt" and privacy_policy_receipt_present)
                    or bool(production_receipts_present.get(receipt_type, False))
                ),
                blocks_live_lm1="LM1" in lanes,
                blocks_live_lm2="LM2" in lanes,
                blocks_provider_activation=receipt_type in {"provider_policy_receipt", "model_selection_policy_receipt"},
                operator_copy=operator_copy,
                next_safe_move="Keep live models off; collect this receipt through a future governed review lane.",
            )
        )
        for receipt_type, human_label, lanes, operator_copy in specs
    )


def build_payload(*, generated_at: str | None = None, live_shadow_payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    live_shadow = dict(live_shadow_payload or live_lm_shadow_trial.latest_or_ready_payload(generated_at=generated_at))
    live_shadow_valid = bool((live_shadow.get("machine_proof") or {}).get("live_shadow_receipt_valid"))
    token_receipts = token_vault.production_activation_receipt_statuses()
    token_vault_receipt_present = bool(token_receipts["production_token_vault_ready_receipt"]["present"])
    privacy_policy_receipt_present = bool(token_receipts["privacy_policy_receipt"]["present"])
    receipt_contracts = activation_receipt_contracts()
    receipt_fixture_results = activation_receipt_contract_fixture_results()
    activation_substrate = ensure_activation_receipt_substrate(generated_at=generated_at)
    production_receipt_statuses = activation_production_receipt_statuses(create_if_missing=False)
    production_receipts_present = {item["receipt_type"]: bool(item["present"]) for item in production_receipt_statuses}
    receipts = required_receipts(
        live_shadow_receipt_present=live_shadow_valid,
        production_token_vault_receipt_present=token_vault_receipt_present,
        privacy_policy_receipt_present=privacy_policy_receipt_present,
        production_receipts_present=production_receipts_present,
    )
    missing = tuple(item["receipt_type"] for item in receipts if item["present"] is False)
    hard_blockers = []
    if not token_vault_receipt_present:
        hard_blockers.append("production_token_vault_inactive")
    if not (
        production_receipts_present.get("provider_policy_receipt", False)
        and production_receipts_present.get("model_selection_policy_receipt", False)
    ):
        hard_blockers.append("provider_activation_receipts_missing")
    if not production_receipts_present.get("live_model_enablement_receipt", False):
        hard_blockers.append("live_model_enablement_receipt_missing")
    if not privacy_policy_receipt_present:
        hard_blockers.append("production_privacy_policy_receipt_missing")
    for receipt_type, blocker in (
        ("rollback_disable_receipt", "rollback_disable_receipt_missing"),
        ("device_trust_live_activation_receipt", "device_trust_live_activation_receipt_missing"),
        ("real_lm1_production_policy_receipt", "real_lm1_production_policy_receipt_missing"),
        ("real_lm2_production_policy_receipt", "real_lm2_production_policy_receipt_missing"),
    ):
        if not production_receipts_present.get(receipt_type, False):
            hard_blockers.append(blocker)
    if not live_shadow_valid:
        hard_blockers.insert(4, "live_shadow_comparison_receipt_missing")
    beams = production_activation_beams(
        token_vault_receipt_present=token_vault_receipt_present,
        privacy_policy_receipt_present=privacy_policy_receipt_present,
        receipt_contracts_ready=all(
            contract["receipt_contract_status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
            for contract in receipt_contracts
        ),
        production_receipts_present=production_receipts_present,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "Live models are still off.",
            "OpenClaw now has an explicit checklist for what must exist before live LM1 or LM2 can be reviewed.",
            "No provider, model, tool, or action is activated by this checklist.",
        ),
        "live_lm1_activation_status": "NOT_READY",
        "live_lm2_activation_status": "NOT_READY",
        "provider_activation_status": "RECEIPTS_REQUIRED_NOT_PRESENT",
        "activation_receipt_requirements": receipts,
        "production_activation_beams": beams,
        "activation_receipt_substrate": activation_substrate,
        "activation_receipt_contracts": receipt_contracts,
        "activation_receipt_fixture_results": receipt_fixture_results,
        "activation_production_receipt_statuses": production_receipt_statuses,
        "activation_production_receipt_intake": {
            "intake_ready": activation_substrate["production_receipt_intake_ready"],
            "metadata_only": True,
            "writes_default_production_receipts": False,
            "writer_authority_free": activation_substrate["production_receipt_writer_authority_free"],
            "default_production_rows": activation_substrate["production_receipt_rows_present"],
            "next_safe_move": "Use record_activation_production_receipt_candidate only for governed production-review receipts.",
        },
        "missing_receipts": missing,
        "live_shadow_receipt": {
            "read_model_ref": "generated/read_models/live_lm_shadow_trial.json",
            "status": live_shadow.get("trial_status"),
            "present": live_shadow_valid,
            "provider_class": (live_shadow.get("machine_proof") or {}).get("provider_class"),
            "model_ref": (live_shadow.get("machine_proof") or {}).get("model_ref"),
        },
        "shadow_test_receipts": {
            "provider_policy_receipt": {
                "present": live_shadow_valid,
                "scope": "shadow_test_only",
                "satisfies_production_activation": False,
                "provider_class": (live_shadow.get("machine_proof") or {}).get("provider_class"),
            },
            "model_selection_policy_receipt": {
                "present": live_shadow_valid,
                "scope": "shadow_test_only",
                "satisfies_production_activation": False,
                "model_ref": (live_shadow.get("machine_proof") or {}).get("model_ref"),
            },
        },
        "production_privacy_receipts": token_receipts,
        "hard_blockers": tuple(hard_blockers),
        "next_safe_move": "Keep using fixture/shadow mode until these receipts exist.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "receipt_requirement_count": len(receipts),
            "missing_receipt_count": len(missing),
            "production_activation_beam_count": len(beams),
            "production_activation_beams_explicit": tuple(item["beam_id"] for item in beams)
            == (
                "production_token_vault",
                "provider_model_receipts",
                "live_enablement_receipt",
                "privacy_receipt",
                "rollback_disable_receipt",
                "device_trust_live_activation",
                "real_lm_production_policy",
            ),
            "provider_activation_receipts_required": True,
            "provider_activation_receipts_present": production_receipts_present.get("provider_policy_receipt", False)
            and production_receipts_present.get("model_selection_policy_receipt", False),
            "production_token_vault_ready_receipt_present": token_vault_receipt_present,
            "live_model_enablement_receipt_present": production_receipts_present.get("live_model_enablement_receipt", False),
            "privacy_policy_receipt_present": privacy_policy_receipt_present,
            "rollback_disable_receipt_present": production_receipts_present.get("rollback_disable_receipt", False),
            "device_trust_live_activation_receipt_present": production_receipts_present.get(
                "device_trust_live_activation_receipt", False
            ),
            "real_lm1_production_policy_receipt_present": production_receipts_present.get(
                "real_lm1_production_policy_receipt", False
            ),
            "real_lm2_production_policy_receipt_present": production_receipts_present.get(
                "real_lm2_production_policy_receipt", False
            ),
            "activation_receipt_contract_count": len(receipt_contracts),
            "activation_receipt_contracts_ready": all(
                contract["receipt_contract_status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
                for contract in receipt_contracts
            ),
            "activation_receipt_fixture_count": len(receipt_fixture_results),
            "activation_receipt_fixtures_valid": all(result["valid_as_test_fixture"] for result in receipt_fixture_results),
            "activation_receipt_fixtures_satisfy_production": any(
                result["satisfies_production_activation"] for result in receipt_fixture_results
            ),
            "activation_receipt_substrate_exists": activation_substrate["exists"],
            "activation_receipt_substrate_table_count": len(activation_substrate["present_tables"]),
            "activation_receipt_substrate_contract_rows": activation_substrate["contract_rows_persisted"],
            "activation_receipt_substrate_fixture_rows": activation_substrate["fixture_validation_rows_persisted"],
            "activation_receipt_substrate_production_rows": activation_substrate["production_receipt_rows_present"],
            "activation_receipt_substrate_valid_production_rows": activation_substrate[
                "valid_production_receipt_rows_present"
            ],
            "activation_receipt_substrate_contracts_backed": activation_substrate["contracts_backed_by_sqlite"],
            "activation_receipt_substrate_fixtures_backed": activation_substrate["fixtures_backed_by_sqlite"],
            "activation_production_receipt_intake_ready": activation_substrate["production_receipt_intake_ready"],
            "activation_production_receipt_writer_authority_free": activation_substrate[
                "production_receipt_writer_authority_free"
            ],
            "activation_production_receipt_status_count": len(production_receipt_statuses),
            "activation_production_receipts_present_count": sum(1 for item in production_receipt_statuses if item["present"]),
            "activation_receipt_substrate_satisfies_production": activation_substrate["satisfies_production_activation"],
            "live_shadow_comparison_receipt_present": live_shadow_valid,
            "live_shadow_model_call_recorded": bool((live_shadow.get("machine_proof") or {}).get("live_model_call_performed")),
            "shadow_provider_policy_receipt_present": live_shadow_valid,
            "shadow_model_selection_receipt_present": live_shadow_valid,
            "shadow_receipts_satisfy_production_activation": False,
            "live_lm1_ready": False,
            "live_lm2_ready": False,
            "live_lm_status": "NOT_ACTIVE",
            "live_model_call_performed": False,
            "model_api_call_performed": False,
            "network_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    lines = [
        "# Live LM Activation Requirements",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 live: {payload['live_lm1_activation_status']}",
        f"LM2 live: {payload['live_lm2_activation_status']}",
        f"Missing receipts: {payload['machine_proof']['missing_receipt_count']}",
        f"Receipt contracts ready: {payload['machine_proof']['activation_receipt_contract_count']}",
        f"SQLite-backed receipt contracts: {payload['machine_proof']['activation_receipt_substrate_contract_rows']}",
        f"Governed receipt intake ready: {payload['machine_proof']['activation_production_receipt_intake_ready']}",
        f"Production receipts recorded: {payload['machine_proof']['activation_production_receipts_present_count']}",
        "",
        "Still blocked:",
        *[f"- {item}" for item in payload["hard_blockers"]],
        "",
        "No production model, provider, tool, or action is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export live LM activation requirements read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "missing_receipt_count": payload["machine_proof"]["missing_receipt_count"],
                    "live_lm_status": payload["machine_proof"]["live_lm_status"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
