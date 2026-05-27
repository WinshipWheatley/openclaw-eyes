"""Safe preview provider feasibility v0.

Readiness-only provider selection for future backend-generated document
previews. This module does not render documents, parse workbooks, start
services, invoke containers, or mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-27T00:00:00+00:00"

READ_MODEL_ID = "safe_preview_provider"
SCHEMA_VERSION = "safe_preview_provider_feasibility_v0"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

PROVIDER_TYPES = (
    "NONE",
    "QUICKLOOK_MAC_CLIENT",
    "DANGERZONE_BACKEND",
    "LIBREOFFICE_SANDBOXED",
    "ONLYOFFICE_SERVER",
)

DANGERZONE_SPIKE_ID = "dangerzone_local_preview_spike_v0"
DANGERZONE_DOCUMENTED_VERSION = "0.10.0"
DANGERZONE_DOCUMENTED_SUPPORTED_OS = (
    "Ubuntu 24.04 noble",
    "Ubuntu 22.04 jammy",
    "Debian 12 bookworm",
    "Debian 13 trixie",
    "Fedora current supported releases",
)

AUTHORITY_BOUNDARY = {
    "document_conversion_performed": False,
    "pdf_generation_performed": False,
    "workbook_body_read": False,
    "container_started": False,
    "long_running_service_started": False,
    "network_server_started": False,
    "production_state_mutation_allowed": False,
    "email_send_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "ledger_posting_allowed": False,
}


@dataclass(frozen=True)
class ProviderReadinessResult:
    provider_type: str
    provider_available: bool
    install_required: bool
    detected_commands: tuple[str, ...]
    license_notes: str
    dependency_notes: str
    sandbox_required: bool
    safe_for_untrusted_docs: bool
    safe_for_invoice_candidate: bool
    production_ready: bool
    recommendation: str
    blocker: str | None = None


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def detect_local_tools() -> dict[str, bool]:
    commands = ("dangerzone", "dangerzone-cli", "libreoffice", "soffice", "docker", "podman")
    return {command: _command_available(command) for command in commands}


def build_provider_results(*, detected_tools: Mapping[str, bool] | None = None) -> tuple[ProviderReadinessResult, ...]:
    tools = dict(detected_tools or detect_local_tools())
    dangerzone_available = bool(tools.get("dangerzone") or tools.get("dangerzone-cli"))
    libreoffice_available = bool(tools.get("libreoffice") or tools.get("soffice"))
    docker_available = bool(tools.get("docker"))
    return (
        ProviderReadinessResult(
            provider_type="QUICKLOOK_MAC_CLIENT",
            provider_available=True,
            install_required=False,
            detected_commands=(),
            license_notes="Native Mac client capability; no backend dependency added.",
            dependency_notes="Best current path for candidate invoice inspection because the file is already bridged to Mac.",
            sandbox_required=False,
            safe_for_untrusted_docs=False,
            safe_for_invoice_candidate=True,
            production_ready=True,
            recommendation="Use for current invoice review side panel open/reveal behavior.",
        ),
        ProviderReadinessResult(
            provider_type="DANGERZONE_BACKEND",
            provider_available=dangerzone_available and docker_available,
            install_required=not dangerzone_available,
            detected_commands=tuple(
                command for command in ("dangerzone", "dangerzone-cli", "docker") if tools.get(command)
            ),
            license_notes="AGPLv3; commercial packaging and distribution need legal review before bundling.",
            dependency_notes="Promising future provider for untrusted PDF/Office/image conversion to safer PDFs; uses containerized conversion.",
            sandbox_required=True,
            safe_for_untrusted_docs=dangerzone_available and docker_available,
            safe_for_invoice_candidate=False,
            production_ready=False,
            recommendation="Evaluate in an isolated install lane before any backend preview production use.",
            blocker=None if dangerzone_available and docker_available else "Dangerzone command not installed locally.",
        ),
        ProviderReadinessResult(
            provider_type="LIBREOFFICE_SANDBOXED",
            provider_available=libreoffice_available,
            install_required=not libreoffice_available,
            detected_commands=tuple(command for command in ("libreoffice", "soffice") if tools.get(command)),
            license_notes="Open-source office suite; confirm distribution packaging terms before bundling.",
            dependency_notes="Useful for Office-to-PDF conversion only when sandboxed; not designed as a malware-safe document sanitizer.",
            sandbox_required=True,
            safe_for_untrusted_docs=False,
            safe_for_invoice_candidate=libreoffice_available,
            production_ready=False,
            recommendation="Use only behind an explicit sandbox and receipt gate; do not use for untrusted legal/discovery docs alone.",
            blocker=None if libreoffice_available else "LibreOffice/soffice not installed locally.",
        ),
        ProviderReadinessResult(
            provider_type="ONLYOFFICE_SERVER",
            provider_available=False,
            install_required=True,
            detected_commands=(),
            license_notes="Community edition is AGPLv3; commercial editions exist. Server packaging needs legal/security review.",
            dependency_notes="Heavy network-facing document server; not appropriate for v0 low-latency local review.",
            sandbox_required=True,
            safe_for_untrusted_docs=False,
            safe_for_invoice_candidate=False,
            production_ready=False,
            recommendation="Do not install for v0; revisit only if collaborative editing/viewing becomes a real backend module.",
            blocker="Would add a long-running document server and wider attack surface.",
        ),
        ProviderReadinessResult(
            provider_type="NONE",
            provider_available=True,
            install_required=False,
            detected_commands=(),
            license_notes="No third-party dependency.",
            dependency_notes="Fail-closed mode when no approved preview provider is available.",
            sandbox_required=False,
            safe_for_untrusted_docs=True,
            safe_for_invoice_candidate=True,
            production_ready=True,
            recommendation="Return metadata-only/candidate-only preview status.",
        ),
    )


def recommended_current_invoice_provider(results: tuple[ProviderReadinessResult, ...]) -> str:
    quicklook = next(result for result in results if result.provider_type == "QUICKLOOK_MAC_CLIENT")
    if quicklook.safe_for_invoice_candidate:
        return quicklook.provider_type
    return "NONE"


def recommended_future_untrusted_provider(results: tuple[ProviderReadinessResult, ...]) -> str:
    dangerzone = next(result for result in results if result.provider_type == "DANGERZONE_BACKEND")
    if dangerzone.safe_for_untrusted_docs:
        return dangerzone.provider_type
    return "DANGERZONE_BACKEND_PENDING_REVIEW"


def build_dangerzone_spike_receipt(
    *,
    detected_tools: Mapping[str, bool],
    os_release: str = "Ubuntu 24.04 noble on WSL2",
) -> dict[str, Any]:
    dangerzone_available = bool(detected_tools.get("dangerzone") or detected_tools.get("dangerzone-cli"))
    podman_available = bool(detected_tools.get("podman"))
    docker_available = bool(detected_tools.get("docker"))
    can_attempt_conversion = dangerzone_available and (podman_available or docker_available)
    blockers = []
    if not dangerzone_available:
        blockers.append("Dangerzone CLI/app is not installed locally.")
    if not podman_available:
        blockers.append("Dangerzone on Linux expects Podman; podman is not installed locally.")
    blockers.append("Installing a new external document sanitizer package needs explicit install and AGPL packaging review.")
    return {
        "spike_id": DANGERZONE_SPIKE_ID,
        "provider": "DANGERZONE_BACKEND",
        "status": "BLOCKED_INSTALL_REQUIRED" if not can_attempt_conversion else "READY_FOR_SYNTHETIC_CONVERSION_TEST",
        "os_release": os_release,
        "documented_supported_os_match": True,
        "documented_latest_version_seen": DANGERZONE_DOCUMENTED_VERSION,
        "documented_install_path": "Official Linux release package for supported Ubuntu/Debian/Fedora; Linux runtime uses Podman sandboxing.",
        "license_notes": "Dangerzone is AGPLv3; commercial packaging/distribution requires legal review before bundling.",
        "dependency_notes": "Dangerzone converts potentially dangerous documents through a sandbox; Linux install requires Podman/container support.",
        "local_detection": {
            "dangerzone": bool(detected_tools.get("dangerzone")),
            "dangerzone_cli": bool(detected_tools.get("dangerzone-cli")),
            "podman": podman_available,
            "docker": docker_available,
        },
        "synthetic_input_path": None,
        "synthetic_input_sha256": None,
        "safe_pdf_output_path": None,
        "safe_pdf_output_sha256": None,
        "conversion_attempted": False,
        "conversion_receipt_written": False,
        "blockers": tuple(dict.fromkeys(blockers)),
        "production_ready": False,
        "real_invoice_artifacts_touched": False,
        "capital_hilton_files_converted": False,
        "workbook_body_read": False,
        "long_running_service_started": False,
        "network_server_started": False,
    }


def build_payload(
    *,
    generated_at: str | None = None,
    detected_tools: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    local_detection = dict(detected_tools or detect_local_tools())
    results = build_provider_results(detected_tools=local_detection)
    dangerzone_spike = build_dangerzone_spike_receipt(detected_tools=local_detection)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "operator_summary": "Mac Quick Look is enough for the current invoice candidate. Backend safe preview remains not ready until a sandboxed provider is approved.",
        "provider_types": PROVIDER_TYPES,
        "local_tool_detection": local_detection,
        "provider_readiness": tuple(asdict(result) for result in results),
        "dangerzone_local_install_preview_spike": dangerzone_spike,
        "current_invoice_review_recommendation": {
            "provider_type": recommended_current_invoice_provider(results),
            "reason": "Lowest latency and no backend conversion for the already bridged candidate artifact.",
            "backend_preview_generation_needed_now": False,
        },
        "future_untrusted_docs_recommendation": {
            "provider_type": recommended_future_untrusted_provider(results),
            "reason": "Dangerzone is the best-fit candidate for future untrusted/legal/discovery preview sanitization, but it needs install, sandbox, and AGPL packaging review.",
            "backend_preview_production_ready": False,
        },
        "prototype": {
            "attempted": False,
            "reason": "No approved backend preview provider is installed locally; Dangerzone install requires an explicit package/dependency approval lane.",
            "synthetic_document_only": True,
            "real_invoice_artifacts_touched": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "provider_contract_present": True,
            "no_custom_renderer_built": True,
            "no_document_conversion_performed": True,
            "quicklook_recommended_for_current_invoice": recommended_current_invoice_provider(results)
            == "QUICKLOOK_MAC_CLIENT",
            "dangerzone_recommended_for_future_review": True,
            "dangerzone_spike_receipt_present": True,
            "dangerzone_conversion_blocked_by_install": dangerzone_spike["status"] == "BLOCKED_INSTALL_REQUIRED",
            "onlyoffice_not_recommended_for_v0": True,
            "production_ready_false_for_backend_preview": True,
            "all_action_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
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
        "# Safe Preview Provider Feasibility",
        "",
        payload["operator_summary"],
        "",
        "Current invoice review:",
        f"- Recommended provider: {payload['current_invoice_review_recommendation']['provider_type']}",
        "- Backend preview generation needed now: false",
        "",
        "Future untrusted documents:",
        f"- Recommended provider: {payload['future_untrusted_docs_recommendation']['provider_type']}",
        "- Backend preview production ready: false",
        "",
        "Dangerzone local spike:",
        f"- Status: {payload['dangerzone_local_install_preview_spike']['status']}",
        f"- Version checked: {payload['dangerzone_local_install_preview_spike']['documented_latest_version_seen']}",
        *[
            f"- Blocker: {blocker}"
            for blocker in payload["dangerzone_local_install_preview_spike"]["blockers"]
        ],
        "",
        "Local tools:",
        *[
            f"- {name}: {'found' if found else 'missing'}"
            for name, found in sorted(payload["local_tool_detection"].items())
        ],
        "",
        "Boundary:",
        "- No document conversion, PDF generation, workbook read, container start, service start, email, Coupa, browser, ledger, or production mutation.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export safe preview provider feasibility read-model.")
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
                    "current_invoice_provider": payload["current_invoice_review_recommendation"]["provider_type"],
                    "future_untrusted_provider": payload["future_untrusted_docs_recommendation"]["provider_type"],
                    "prototype_attempted": payload["prototype"]["attempted"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
