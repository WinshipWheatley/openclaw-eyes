"""Compact Helm Calm Mode surface for Mission Control.

This read model projects existing local Helm, Hermes, and Chief read models
into one Mac-facing surface. It does not call providers, open apps, mutate
finance truth, execute repairs, or publish ledger/send state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from openclaw_substrate_utils import stable_json, utc_now


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "helm_calm_surface_v0"
READ_MODEL_ID = "helm_calm_surface"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"

SOURCE_READ_MODELS = {
    "helm": "helm_operator_attention_package.json",
    "hermes": "openclaw_hermes_sidecar.json",
    "chief": "chief_check_engine_diagnostic_package.json",
}

UNSAFE_TRUE_GRANT_KEYS = (
    "email_send_allowed",
    "ledger_posting_allowed",
    "browser_access_allowed",
    "gmail_allowed",
    "coupa_allowed",
    "chief_repair_allowed",
    "hermes_execution_allowed",
    "sent",
    "paid",
)

AUTHORITY_FLAGS = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "chief_repair_allowed": False,
    "hermes_execution_allowed": False,
    "sent": False,
    "paid": False,
    "artifact_delete_allowed": False,
    "external_provider_allowed": False,
    "production_state_mutation_allowed": False,
}


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _source_path(read_model_root: str | Path, filename: str) -> Path:
    return _rooted(read_model_root) / filename


def _source_payloads(read_model_root: str | Path) -> dict[str, dict[str, Any]]:
    return {
        source_key: _read_json(_source_path(read_model_root, filename))
        for source_key, filename in SOURCE_READ_MODELS.items()
    }


def _source_manifest(read_model_root: str | Path, payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_key, filename in SOURCE_READ_MODELS.items():
        path = _source_path(read_model_root, filename)
        payload = payloads.get(source_key, {})
        rows.append(
            {
                "source_key": source_key,
                "path": _source_ref(filename),
                "present": path.is_file(),
                "json_loaded": bool(payload),
                "schema_version": str(payload.get("schema_version") or ""),
                "read_model_id": str(payload.get("read_model_id") or payload.get("package_id") or ""),
            }
        )
    return rows


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    machine = clone.get("machine_proof")
    if isinstance(machine, dict):
        machine.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _string(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or "").strip()
    return text or default


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _check_engine_summary(helm: Mapping[str, Any], chief: Mapping[str, Any]) -> dict[str, Any]:
    check = _mapping(helm.get("check_engine"))
    status = _string(check.get("status") or chief.get("current_status"), "UNKNOWN")
    summary = _string(check.get("operator_summary"), "Check Engine status is available from local read models.")
    next_safe_move = _string(
        check.get("safe_next_move")
        or _mapping(chief.get("next_recommended_lane")).get("goal"),
        "Review the local Check Engine proof drawer if more detail is needed.",
    )
    return {
        "status": status,
        "summary": summary,
        "active_count": int(check.get("active_count") or 0),
        "operator_action_required": bool(check.get("operator_action_required", False)),
        "next_safe_move": next_safe_move,
        "source_ref": _source_ref(SOURCE_READ_MODELS["helm"]),
    }


def _hermes_execution_source_true(hermes: Mapping[str, Any]) -> bool:
    proof = _mapping(hermes.get("machine_proof"))
    posture = _mapping(hermes.get("current_posture"))
    return any(
        proof.get(key) is True
        for key in (
            "hermes_daemon_launched",
            "chief_launched",
            "lm_called",
            "services_started",
            "live_action_recommended",
        )
    ) or posture.get("executes") is True


def _hermes_summary(hermes: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = _mapping(hermes.get("recommended_next_package"))
    package_ref = _string(recommendation.get("package_ref"), "no_package_ref")
    lane = _string(recommendation.get("recommended_next_lane"), "no_recommended_lane")
    readiness = _string(hermes.get("readiness"), "UNKNOWN")
    confidence = _string(hermes.get("confidence"), "UNKNOWN")
    return {
        "readiness": readiness,
        "summary": f"Hermes recommends {lane} via {package_ref}; recommendation only.",
        "recommended_next_lane": lane,
        "package_ref": package_ref,
        "confidence": confidence,
        "execution_authority": False,
        "source_reported_execution": _hermes_execution_source_true(hermes),
        "source_ref": _source_ref(SOURCE_READ_MODELS["hermes"]),
    }


def _chief_repair_source_true(chief: Mapping[str, Any]) -> bool:
    future = _mapping(chief.get("future_gated_repair_cleanup_remount_posture"))
    no_authority = _mapping(chief.get("no_authority_flags"))
    return any(
        (
            future.get("this_package_may_execute_repair") is True,
            future.get("this_package_may_delete") is True,
            future.get("this_package_may_remount") is True,
            future.get("this_package_may_handle_credentials") is True,
            chief.get("backend_repair_authority_added") is True,
            no_authority.get("backend_repair_authority_added") is True,
        )
    )


def _chief_summary(chief: Mapping[str, Any]) -> dict[str, Any]:
    status = _string(chief.get("current_status"), "UNKNOWN")
    mission = _string(
        chief.get("diagnostic_mission"),
        "Chief diagnostic package is available as local read-model proof.",
    )
    signal_count = int(chief.get("signal_count") or len(_list(chief.get("degraded_signals"))))
    check_engine_on = bool(chief.get("check_engine_on", False))
    return {
        "status": status,
        "summary": f"Chief diagnostic package is {status}; {signal_count} diagnostic signals; repair authority is false.",
        "mission": mission,
        "check_engine_on": check_engine_on,
        "signal_count": signal_count,
        "repair_authority": False,
        "source_reported_repair_authority": _chief_repair_source_true(chief),
        "source_ref": _source_ref(SOURCE_READ_MODELS["chief"]),
    }


def _proof_drawer(source_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "collapsed_by_default": True,
        "default_visible_content": "summaries_only",
        "raw_proof_visible_by_default": False,
        "links": [
            {
                "proof_ref": row["path"],
                "label": row["source_key"],
                "source_status": "present" if row["present"] and row["json_loaded"] else "missing_or_unreadable",
                "schema_version": row["schema_version"],
                "collapsed_by_default": True,
                "body_included": False,
            }
            for row in source_manifest
        ],
    }


def _privacy_impact() -> dict[str, Any]:
    return {
        "provider_considered": "local_read_models",
        "data_exposure_class": "metadata_only_collapsed_proof_refs",
        "local_alternative": "existing_generated_read_models",
        "final_provider_decision": "local_only",
        "approval_required": False,
        "external_provider_called": False,
        "raw_proof_body_visible_by_default": False,
    }


def _unsafe_true_grants(value: Any, *, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in UNSAFE_TRUE_GRANT_KEYS and child is True:
                matches.append(child_path)
            matches.extend(_unsafe_true_grants(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_unsafe_true_grants(child, path=f"{path}[{index}]"))
    return matches


def build_helm_calm_surface(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payloads = _source_payloads(read_model_root)
    source_manifest = _source_manifest(read_model_root, payloads)
    check_engine = _check_engine_summary(payloads["helm"], payloads["chief"])
    hermes = _hermes_summary(payloads["hermes"])
    chief = _chief_summary(payloads["chief"])
    proof_drawer = _proof_drawer(source_manifest)
    privacy = _privacy_impact()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "surface_mode": "HELM_CALM",
        "source_manifest": source_manifest,
        "authority_flags": dict(AUTHORITY_FLAGS),
        "privacy_impact": privacy,
        "check_engine_summary": check_engine["summary"],
        "hermes_summary": hermes["summary"],
        "chief_summary": chief["summary"],
        "check_engine": check_engine,
        "hermes": hermes,
        "chief": chief,
        "proof_drawer": proof_drawer,
        "machine_proof": {
            "read_model_only": True,
            "source_payloads_embedded": False,
            "authority_flags_all_false": all(value is False for value in AUTHORITY_FLAGS.values()),
            "proof_drawer_collapsed": proof_drawer["collapsed_by_default"] is True,
            "hermes_execution_authority_false": hermes["execution_authority"] is False
            and hermes["source_reported_execution"] is False,
            "chief_repair_authority_false": chief["repair_authority"] is False
            and chief["source_reported_repair_authority"] is False,
            "privacy_impact_local_only": privacy["final_provider_decision"] == "local_only",
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": False,
            "content_hash": "",
        },
    }
    unsafe = _unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def export_helm_calm_surface(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    export_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    output_root = _rooted(export_root)
    output_root.mkdir(parents=True, exist_ok=True)
    payload = build_helm_calm_surface(
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    json_path = output_root / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "json_path": json_path.as_posix(),
        "proof_drawer_collapsed": payload["proof_drawer"]["collapsed_by_default"],
        "authority_flags_all_false": payload["machine_proof"]["authority_flags_all_false"],
        "privacy_impact_local_only": payload["machine_proof"]["privacy_impact_local_only"],
        "unsafe_true_grants_absent": payload["machine_proof"]["unsafe_true_grants_absent"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Helm Calm Mode surface read-model.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    summary = export_helm_calm_surface(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        payload = _read_json(Path(summary["json_path"]))
        print(stable_json(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
