"""Struna Obscura project capsule/read-model v0.

Records operator-supplied metadata for the Struna Obscura collaboration so
Niles can later resume the project deterministically. This is tracking metadata
only: it does not inspect or modify the Struna repository, ingest source bodies,
run builds, store raw legal/contact material, or grant runtime/send/approval
authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "struna_obscura_project_capsule_v0"
JSON_EXPORT_NAME = "struna_obscura_project_capsule.json"
OPERATOR_EXPORT_NAME = "struna_obscura_project_capsule_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
PROJECT_ID = "struna_obscura"
PROJECT_NAME = "Struna Obscura"
NEXT_SAFE_LANE = "Tabbed Navigation Reality Fix v0"
CURRENT_KNOWN_COMMIT = "0345e7c"
WORKING_REPO_PATH = "/Users/hwinshipwheatley/Developer/Struna Obscura/Struna Obscura"
ORIGINAL_SOURCE_DROP_PATH = "/Users/hwinshipwheatley/Downloads/struna_obscura-2026-05-01-organ-recovery-2"
RECOMMENDED_ARCHIVE_TARGET_PATH = "operator_provided_archive_path_needed/read_only_struna_obscura_source_drop"
NO_AUTHORITY_FLAGS = {
    "tracking_only": True,
    "metadata_only": True,
    "read_model_only": True,
    "struna_repo_modified": False,
    "struna_build_or_test_run": False,
    "raw_source_body_ingested": False,
    "broad_private_folder_scan": False,
    "raw_legal_or_contact_data_stored": False,
    "credential_or_secret_stored": False,
    "repo_b_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "mission_control_app_changed": False,
}

@dataclass(frozen=True)
class StrunaObscuraProjectCapsuleResult:
    schema_version: str
    project_id: str
    project_name: str
    json_path: str
    operator_path: str
    next_safe_lane: str
    niles_resume_ready: bool
    struna_repo_modified: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"

def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()

def build_struna_obscura_project_capsule(*, generated_at: str | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "capsule_id": PROJECT_ID,
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "project_type": ["external_collaboration", "creative_software", "synth_plugin_or_app"],
        "tracking_status": "tracked_for_future_niles_resume",
        "capsule_status": "paused_waiting_for_next_build_lane",
        "owner_originator": {"name_label": "Draper", "source_basis": "operator_reported", "truth_status": "operator_reported_evidence", "role": "original Struna Obscura synth builder"},
        "winship_role": {"role_label": "Mac port collaborator / builder", "source_basis": "operator_reported", "truth_status": "operator_reported_evidence"},
        "niles_relevance": {"resume_target_phrase": "Niles, let's work on Struna", "resume_ready": True, "world_domain": "music_art", "reason": "music/software creative project with deterministic paused issue and next lane", "discoverable_from_read_model": True},
        "paths": {
            "working_repo_path": WORKING_REPO_PATH,
            "working_repo_path_policy": "metadata_label_only_do_not_modify_or_scan",
            "original_source_drop_path": ORIGINAL_SOURCE_DROP_PATH,
            "original_source_drop_path_policy": "temporary_intake_not_canonical_storage_metadata_label_only",
            "recommended_archive_target_path": RECOMMENDED_ARCHIVE_TARGET_PATH,
            "recommended_archive_target_path_status": "placeholder_operator_path_needed",
        },
        "technical_checkpoint": {
            "current_known_commit": CURRENT_KNOWN_COMMIT,
            "previous_known_commits": ["1feaae0", "55ca88e", "0ffe4bb", "ca6af64", "83096e6", "7994d97"],
            "app_builds_and_launches": True,
            "rust_dsp_engine_preserved": True,
            "dylib_loads": True,
            "symbols_resolve": True,
            "engine_initializes": True,
            "audio_operator_confirmed_audible_earlier": True,
            "presets_bundled": True,
            "initial_json_loads": True,
            "swiftui_pages_follow_egui_order": True,
            "visible_parameter_readback_synced": "19/19",
        },
        "current_status": "paused_after_bounded_preset_parameter_readback",
        "architecture_summary": ["native SwiftUI macOS shell", "full existing Rust DSP crate preserved", "Rust dylib", "C ABI bridge", "Swift dynamic bridge", "EGUI parity over time"],
        "source_of_truth_files_or_docs": [
            {"label": "Current working Struna repo", "path_label": WORKING_REPO_PATH, "role": "canonical working Mac-port repo path, operator-provided", "read_policy": "metadata_reference_only_no_source_body_ingest"},
            {"label": "Original Draper source drop", "path_label": ORIGINAL_SOURCE_DROP_PATH, "role": "temporary intake source drop, operator-provided", "read_policy": "metadata_reference_only_downloads_is_not_canonical_storage"},
            {"label": "Recommended archive target", "path_label": RECOMMENDED_ARCHIVE_TARGET_PATH, "role": "placeholder for future read-only archive outside Downloads", "read_policy": "placeholder_only_operator_path_needed"},
        ],
        "paused_issue": {"issue_label": "tab_navigation_did_not_change_pages", "operator_observation": "After commit 0345e7c, operator clicked tabs/pages in the visible app and tab navigation did not change pages. No other app versions were open.", "truth_status": "operator_reported_runtime_observation", "next_debug_scope": "navigation UI reality, not DSP/build architecture"},
        "next_safe_lane": NEXT_SAFE_LANE,
        "do_not_run_now": ["Struna builds", "Struna tests", "tabbed navigation fix lane", "repo mutation", "source body ingest"],
        "business_legal_terms": {
            "evidence_posture": "operator_reported_evidence_not_final_legal_truth",
            "formal_proof_needed": True,
            "terms": [
                {"label": "Mac version sales share", "operator_reported_term": "Winship gets 25% of sales of the Mac version.", "truth_status": "operator_reported_unverified"},
                {"label": "Use/license permission", "operator_reported_term": "Winship can license/use Struna Obscura with any software he builds.", "truth_status": "operator_reported_unverified"},
            ],
            "sensitive_data_boundary": "Do not store raw legal documents, contact details, payment terms documents, credentials, private messages, or signatures in normal read-models.",
        },
        "formal_proof_needed_for_business_terms": True,
        "sensitive_data_boundary": {
            "allowed": ["operator-supplied project metadata", "safe path labels", "commit labels", "architecture summary labels", "operator-reported business/legal term summaries marked unverified"],
            "forbidden": ["raw legal documents", "contact details", "payment documents", "credentials or secrets", "private messages", "raw source code bodies from Struna", "broad private folder scans"],
        },
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "resume_packet": {"when_operator_says": "Niles, let's work on Struna", "route_to": NEXT_SAFE_LANE, "initial_operator_context": "Struna Obscura Mac port is paused at tab navigation reality after commit 0345e7c; preserve Rust DSP, inspect UI navigation only in a future scoped Struna lane.", "requires_formal_proof_before_legal_claims": True, "struna_repo_modification_allowed_by_this_capsule": False},
        "receipt_proof_status": {"project_tracked_as_external_collab": True, "niles_can_resume_from_read_model": True, "business_terms_operator_reported_evidence": True, "formal_proof_needed_flagged": True, "raw_sensitive_legal_contact_data_stored": False, "struna_repo_modified": False, "runtime_authority_added": False, "send_or_submit_authority_added": False, "approval_authority_added": False},
        "next_recommended_lane": "Mission Control Struna Capsule Surface v0",
        **NO_AUTHORITY_FLAGS,
    }
    return payload

def format_struna_obscura_project_capsule(payload: dict[str, Any]) -> str:
    checkpoint = payload["technical_checkpoint"]
    lines = [
        "# Struna Obscura Project Capsule v0", "", "Status:",
        f"- Project: `{payload['project_name']}`.",
        f"- Capsule status: `{payload['capsule_status']}`.",
        f"- Current known commit: `{checkpoint['current_known_commit']}`.",
        f"- Next safe lane: `{payload['next_safe_lane']}`.",
        "- Struna repo modified by this lane: `false`.",
        "- Runtime/send/approval authority added: `false`.", "",
        "## Operator Meaning",
        "- Struna Obscura is now tracked as an external collaboration creative-software project capsule.",
        "- Niles can later resume from this read-model when Winship says: `Niles, let's work on Struna`.",
        "- This capsule is tracking metadata only; it is not a Struna build lane.", "",
        "## Paths",
        f"- Working repo path: `{payload['paths']['working_repo_path']}`.",
        f"- Original source drop path: `{payload['paths']['original_source_drop_path']}`.",
        f"- Recommended archive target placeholder: `{payload['paths']['recommended_archive_target_path']}`.",
        "- Downloads is temporary intake, not canonical storage.", "",
        "## Current Technical Checkpoint",
        f"- App builds/launches: `{str(checkpoint['app_builds_and_launches']).lower()}`.",
        f"- Rust DSP preserved: `{str(checkpoint['rust_dsp_engine_preserved']).lower()}`.",
        f"- Dylib loads / symbols resolve / engine initializes: `{str(checkpoint['dylib_loads']).lower()}` / `{str(checkpoint['symbols_resolve']).lower()}` / `{str(checkpoint['engine_initializes']).lower()}`.",
        f"- Presets bundled and initial.json loads: `{str(checkpoint['presets_bundled']).lower()}` / `{str(checkpoint['initial_json_loads']).lower()}`.",
        f"- Visible parameter readback synced: `{checkpoint['visible_parameter_readback_synced']}`.", "",
        "## Paused Issue", f"- {payload['paused_issue']['operator_observation']}", "",
        "## Business / Legal Evidence Posture",
        "- Business/legal terms are operator-reported evidence, not final legal truth.",
        "- Formal proof needed: `true`.",
    ]
    for term in payload["business_legal_terms"]["terms"]:
        lines.append(f"- {term['label']}: {term['operator_reported_term']} (`{term['truth_status']}`).")
    lines.extend(["", "## Sensitive Data Boundary", "- Do not store raw legal documents, contact details, payment documents, credentials, private messages, or raw source bodies in normal read-models.", "- Do not scan broad private folders or modify the Struna repository in this lane.", "", "## Next Safe Move", f"- Resume with `{payload['next_safe_lane']}` only when a future Struna build lane is explicitly requested."])
    return "\n".join(lines) + "\n"

def export_struna_obscura_project_capsule(*, repo_root: str | Path = ROOT, export_root: str | Path = DEFAULT_EXPORT_ROOT, generated_at: str | None = None) -> StrunaObscuraProjectCapsuleResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_struna_obscura_project_capsule(generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_struna_obscura_project_capsule(payload), encoding="utf-8")
    return StrunaObscuraProjectCapsuleResult(SCHEMA_VERSION, PROJECT_ID, PROJECT_NAME, _display_path(json_path), _display_path(operator_path), payload["next_safe_lane"], payload["niles_relevance"]["resume_ready"], payload["struna_repo_modified"], payload["runtime_authority_added"], payload["send_or_submit_authority_added"], payload["approval_authority_added"])

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Struna Obscura project capsule read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_struna_obscura_project_capsule(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(f"Struna Obscura project capsule exported: {result.json_path} and {result.operator_path} (next_safe_lane={result.next_safe_lane}; niles_resume_ready={result.niles_resume_ready}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
