"""Shared generated read-model file selection helpers.

The canonical generated read-model set is the safe top-level file set under
``generated/read_models``. This helper keeps shuttle packaging and Mac mirror
expectations aligned without manually maintaining expected filename lists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_substrate_utils import sha256_file


ROOT = Path(__file__).resolve().parent
DEFAULT_GENERATED_READ_MODEL_ROOT = Path("generated/read_models")
SAFE_READ_MODEL_SUFFIXES = {".json", ".md", ".txt"}

NO_GO_PARTS = {
    ".ssh",
    ".gnupg",
    ".google-secrets",
    ".private",
    "private",
    "secrets",
    "vaults",
    "finance",
    "legal",
    "tax",
    "cpa",
    "runtime_logs",
}

NO_GO_FILE_HINTS = (
    "credential",
    "credentials",
    "secret",
    "token",
    ".env",
    "sqlite",
    "ledger",
    "manifest",
    "private",
    "temp",
    "tmp",
)

MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES = (
    "capital_hilton_actionable_review_packet.json",
    "capital_hilton_actionable_review_packet_OPERATOR.md",
    "cassandra_governed_review_packet_request_proof.json",
    "cassandra_governed_review_packet_request_proof_OPERATOR.md",
    "purpose_bound_automation_charter.json",
    "hermes_gravity_controller.json",
    "invoice_review_bundle.json",
    "invoice_review_bundle_OPERATOR.md",
)

MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES = (
    "mission_control_capture_request_intake.json",
    "mission_control_capture_request_intake_OPERATOR.md",
)

EVENT_BRIDGE_DESCRIPTOR_READ_MODEL_FILES = (
    "openclaw_event_bridge_contract.json",
    "openclaw_event_bridge_contract_OPERATOR.md",
    "openclaw_authority_semantics_registry.json",
    "openclaw_authority_semantics_registry_OPERATOR.md",
    "simple_invoice_event_bridge_rail_registry.json",
    "simple_invoice_event_bridge_rail_registry_OPERATOR.md",
)

VOLATILE_SELF_REPORT_READ_MODEL_FILES = (
    "operator_threshold_map_contract.json",
    "operator_threshold_map_contract_OPERATOR.md",
    "sync_health.json",
    "sync_health_OPERATOR.md",
    "system_health_lights_taxonomy.json",
    "system_health_lights_taxonomy_OPERATOR.md",
)

HELM_DECLUTTER_BRIDGE_READ_MODEL_FILES = (
    "helm_operator_attention_package.json",
    "operator_mission_priority_helm_declutter.json",
    "system_health_lights_taxonomy.json",
)

SAFE_GENERATED_READ_MODEL_MANIFEST_FILES = frozenset(
    {
        "capital_hilton_proof_resolution_batch_manifest.json",
        "capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
        "make_winship_life_easier_batch_manifest.json",
        "make_winship_life_easier_batch_manifest_OPERATOR.md",
        "openclaw_map_manifest.json",
        "openclaw_work_terrain_reconciliation_batch_manifest.json",
        "openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
    }
)

CRITICAL_GENERATED_READ_MODEL_FILES = (
    "artifact_registry.json",
    "evidence_freshness.json",
    "generated_current_state.md",
    "generated_next_actions.md",
    "helm_state.json",
    "runtime_activation_gate.json",
    "source_inventory.json",
    "world_domain_registry.json",
    "world_status.json",
    *MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
    *MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    *EVENT_BRIDGE_DESCRIPTOR_READ_MODEL_FILES,
)


def resolve_repo_path(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def is_no_go_generated_read_model_relative_path(relative_path: str) -> bool:
    if relative_path in SAFE_GENERATED_READ_MODEL_MANIFEST_FILES:
        return False
    parts = {part.lower() for part in Path(relative_path).parts}
    lowered = Path(relative_path).name.lower()
    if parts & NO_GO_PARTS:
        return True
    for hint in NO_GO_FILE_HINTS:
        if hint == "temp":
            if (
                lowered.startswith(("temp_", "tmp_", "temporary_"))
                or "_temp_" in lowered
                or "-temp-" in lowered
                or lowered.startswith("temp.")
                or lowered.startswith("tmp.")
            ):
                return True
            continue
        if hint in lowered:
            return True
    return False


def is_safe_generated_read_model_file(path: Path, source_root: Path) -> bool:
    try:
        relative_path = path.relative_to(source_root).as_posix()
    except ValueError:
        return False
    if "/" in relative_path:
        return False
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    if path.suffix.lower() not in SAFE_READ_MODEL_SUFFIXES:
        return False
    if is_no_go_generated_read_model_relative_path(relative_path):
        return False
    return True


def iter_safe_generated_read_models(
    source_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    *,
    repo_root: str | Path = ROOT,
) -> list[Path]:
    root = resolve_repo_path(source_root, repo_root=repo_root)
    if not root.is_dir():
        raise ValueError(f"generated read-model source root does not exist: {root}")
    return [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if is_safe_generated_read_model_file(path, root)
    ]


def canonical_generated_read_model_records(
    source_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    *,
    repo_root: str | Path = ROOT,
    include_hash: bool = True,
) -> tuple[dict[str, Any], ...]:
    root = resolve_repo_path(source_root, repo_root=repo_root)
    records: list[dict[str, Any]] = []
    for path in iter_safe_generated_read_models(root, repo_root=repo_root):
        stat_result = path.stat()
        digest = sha256_file(path) if include_hash else None
        records.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "absolute_path": path.as_posix(),
                "size_bytes": stat_result.st_size,
                "sha256": digest,
                "hash_algorithm": "sha256" if digest else None,
            }
        )
    return tuple(records)


def canonical_generated_read_model_expected_files(
    source_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    *,
    repo_root: str | Path = ROOT,
) -> tuple[str, ...]:
    return tuple(
        record["relative_path"]
        for record in canonical_generated_read_model_records(
            source_root=source_root,
            repo_root=repo_root,
            include_hash=False,
        )
    )


__all__ = [
    "CRITICAL_GENERATED_READ_MODEL_FILES",
    "EVENT_BRIDGE_DESCRIPTOR_READ_MODEL_FILES",
    "DEFAULT_GENERATED_READ_MODEL_ROOT",
    "MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES",
    "MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES",
    "NO_GO_FILE_HINTS",
    "NO_GO_PARTS",
    "SAFE_READ_MODEL_SUFFIXES",
    "SAFE_GENERATED_READ_MODEL_MANIFEST_FILES",
    "HELM_DECLUTTER_BRIDGE_READ_MODEL_FILES",
    "VOLATILE_SELF_REPORT_READ_MODEL_FILES",
    "canonical_generated_read_model_expected_files",
    "canonical_generated_read_model_records",
    "is_no_go_generated_read_model_relative_path",
    "is_safe_generated_read_model_file",
    "iter_safe_generated_read_models",
    "resolve_repo_path",
    "sha256_file",
]
