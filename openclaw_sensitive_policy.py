"""Static sensitive-root and source-set path policy for OpenClaw.

This module intentionally works from path strings only. It does not resolve,
open, list, crawl, or inspect filesystem contents.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path("/home/openclaw")

ACTIVE_PACKET_RELATIVE_PATH = Path(
    "docs/planning/project_packets/"
    "06_OPERATOR_HARNESS_ACTOR_EFFICIENCY_AND_SENSITIVE_WORKFLOWS"
)
ACTIVE_RAILS_RELATIVE_PATH = ACTIVE_PACKET_RELATIVE_PATH / "24_files"

APPROVED_SENSITIVE_POLICY_DOC_PREFIXES = (
    "docs/planning/sensitive_roots/",
    str(ACTIVE_RAILS_RELATIVE_PATH).replace("\\", "/") + "/15_",
)

APPROVED_STATIC_POLICY_PATHS = {
    "openclaw_sensitive_policy.py",
}

BROAD_SOURCE_SET_PREFIXES = {
    ".",
    "docs",
    "docs/planning",
    "docs/planning/project_packets",
    "docs/planning/project_packets_archive",
}

SENSITIVE_COMPONENTS = {
    ".chief.env",
    ".env",
    ".google-secrets",
    "api_keys",
    "apikeys",
    "client",
    "clients",
    "credential",
    "credentials",
    "key",
    "keys",
    "legal",
    "private",
    "secrets",
    "sensitive",
    "token",
    "tokens",
    "vault",
    "vaults",
}

SENSITIVE_NAME_MARKERS = (
    "api_key",
    "apikey",
    "credential",
    "private",
    "secret",
    "sensitive folder for review",
    "token",
)

PATH_HINT_KEYS = (
    "path",
    "path_hint",
    "source_path",
    "folder",
    "folder_path",
    "file",
    "file_path",
    "root",
    "root_path",
    "uri",
)


@dataclass(frozen=True)
class PathPolicyFinding:
    path: str
    finding: str
    matched: str


def _collapse_slashes(value: str) -> str:
    while "//" in value:
        value = value.replace("//", "/")
    return value


def normalize_repo_path(raw_path: str, root: Path = ROOT) -> tuple[str, bool]:
    """Normalize a path string without resolving or inspecting the filesystem."""

    raw = str(raw_path).strip().replace("\\", "/")
    raw = _collapse_slashes(raw)
    root_text = str(root).replace("\\", "/").rstrip("/")

    if raw == root_text:
        raw = "."
    elif raw.startswith(root_text + "/"):
        raw = raw[len(root_text) + 1 :]
    elif raw.startswith("/") or (len(raw) > 2 and raw[1] == ":" and raw[2] == "/"):
        return raw, False

    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append(part)
            continue
        parts.append(part)

    if not parts:
        return ".", True
    if parts[0] == "..":
        return "/".join(parts), False
    return "/".join(parts), True


def is_under(path: str, prefix: str) -> bool:
    normalized = prefix.strip().replace("\\", "/").rstrip("/")
    if normalized in ("", "."):
        return True
    return path == normalized or path.startswith(normalized + "/")


def is_approved_sensitive_policy_doc(path: str) -> bool:
    return path in APPROVED_STATIC_POLICY_PATHS or any(
        path.startswith(prefix) for prefix in APPROVED_SENSITIVE_POLICY_DOC_PREFIXES
    )


def path_policy_findings(
    paths: Iterable[str],
    *,
    root: Path = ROOT,
) -> tuple[PathPolicyFinding, ...]:
    findings: list[PathPolicyFinding] = []
    for raw_path in paths:
        path, inside_repo = normalize_repo_path(raw_path, root)
        lowered = path.lower()
        if not inside_repo:
            findings.append(
                PathPolicyFinding(
                    path=path,
                    finding="outside_repo_or_parent_escape",
                    matched=str(raw_path),
                )
            )
            continue
        if is_approved_sensitive_policy_doc(path):
            continue

        components = [part.lower() for part in path.split("/") if part]
        for component in components:
            if component in SENSITIVE_COMPONENTS or component.startswith(".env"):
                findings.append(
                    PathPolicyFinding(
                        path=path,
                        finding="sensitive_path_component",
                        matched=component,
                    )
                )
                break
        else:
            for marker in SENSITIVE_NAME_MARKERS:
                if marker in lowered:
                    findings.append(
                        PathPolicyFinding(
                            path=path,
                            finding="sensitive_path_marker",
                            matched=marker,
                        )
                    )
                    break
    return tuple(findings)


def broad_source_set_prefix_findings(
    allowed_prefixes: Iterable[str],
    *,
    root: Path = ROOT,
) -> tuple[str, ...]:
    broad: list[str] = []
    for raw_prefix in allowed_prefixes:
        prefix, inside_repo = normalize_repo_path(raw_prefix, root)
        normalized = prefix.rstrip("/")
        if not inside_repo or normalized in BROAD_SOURCE_SET_PREFIXES:
            broad.append(normalized)
    return tuple(broad)


def sensitive_path_hint_values(seed_params: Mapping[str, object]) -> tuple[str, ...]:
    """Return seed values that are explicitly path-like; non-path IDs are ignored."""

    values: list[str] = []
    for key, value in seed_params.items():
        lowered_key = str(key).lower()
        key_tokens = tuple(
            token
            for token in lowered_key.replace("-", "_").replace(".", "_").split("_")
            if token
        )
        if lowered_key not in PATH_HINT_KEYS and not any(
            token in PATH_HINT_KEYS for token in key_tokens
        ):
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (tuple, list)):
            values.extend(item for item in value if isinstance(item, str))
    return tuple(values)


def sensitive_root_contract() -> dict[str, object]:
    return {
        "receipt_type": "openclaw.sensitive_root_static_contract",
        "mode": "metadata-only/no-content-access/no-traversal",
        "registry_fields": (
            "root_id",
            "display_name",
            "path_hint",
            "sensitivity_class",
            "quarantine_state",
            "allowed_access_mode",
            "content_access_authority",
            "approved_actor_class",
            "approval_receipt_ref",
            "review_status",
        ),
        "quarantine_states": (
            "blocked_unknown",
            "metadata_only",
            "quarantined_no_unauthorized_approval",
            "approved_local_only_future_lane",
        ),
        "quarantine_intake_contract": {
            "input_mode": "operator-provided-metadata-only",
            "default_state": "blocked_unknown",
            "filesystem_inventory_allowed": False,
            "content_read_allowed": False,
            "path_string_policy_only": True,
            "required_review_before_content": True,
        },
        "forbidden_actions": (
            "crawl",
            "open",
            "summarize",
            "classify_content",
            "ocr",
            "sync",
            "move",
            "permission_change",
            "external_model_access",
        ),
        "content_access_allowed": False,
        "path_policy_only": True,
        "filesystem_inspected": False,
        "passed": True,
    }


def packet06_final_static_boundary_contract() -> dict[str, object]:
    """Final Packet 06 static boundaries before any Packet 07 renewal work."""

    return {
        "receipt_type": "openclaw.packet06_final_static_boundary_contract",
        "mode": "static-policy/no-content/no-runtime/no-provider/no-billing-execution",
        "invoice_artifact": {
            "draft_only": True,
            "approval_before_send_required": True,
            "invoice_generation_allowed": False,
            "invoice_send_allowed": False,
            "invoice_reconciliation_authority": False,
            "private_finance_access_allowed": False,
            "future_authority_required": True,
        },
        "legal_context_export": {
            "metadata_only": True,
            "blocked_source_refs_only": True,
            "content_access_allowed": False,
            "private_legal_root_inspection_allowed": False,
            "outside_model_access_allowed": False,
            "client_private_summary_allowed": False,
            "no_echo_required": True,
            "future_authority_required": True,
        },
        "mcp_shared_memory": {
            "external_mcp_calls_allowed": False,
            "hidden_canonical_memory_writes_allowed": False,
            "receipts_are_execution_authority": False,
            "shared_memory_is_roadmap_authority": False,
            "future_architecture_review_required": True,
        },
        "runtime_and_legacy_gating": {
            "static_review_only": True,
            "live_service_launch_allowed": False,
            "runtime_mutation_allowed": False,
            "process_scan_allowed": False,
            "legacy_bypass_allowed": False,
            "self_healing_allowed": False,
            "future_explicit_authority_required": True,
        },
        "source_set_exclusion": {
            "broad_preload_allowed": False,
            "broad_source_set_authority": False,
            "path_metadata_is_authority": False,
            "private_root_inspection_allowed": False,
            "runtime_provider_billing_laundering_allowed": False,
            "packet07_carry_forward_constraint": True,
        },
        "packet07_carry_forward": (
            "draft-only invoice artifacts until explicit billing authority exists",
            "legal exports stay metadata-only until explicit local legal authority exists",
            "MCP/shared memory cannot become hidden authority or memory writes",
            "runtime and legacy launch surfaces stay static-reviewed until authorized",
            "broad preload and path-metadata-as-authority stay blocked",
            "model/tool prompts must be specific to the review or implementation role",
        ),
        "passed": True,
    }
