import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_context_wiki_compiler import (
    AUTHORITY_BOUNDARY_FLAGS,
    FOOTER,
    INDEX_JSON_NAME,
    OPERATOR_INDEX_NAME,
    PAGE_OUTPUTS,
    SOURCE_OF_TRUTH_WARNING,
    compile_openclaw_context_wiki,
)


def _write_json(root: Path, relative_path: str, payload: dict) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _business_object_audit_payload(
    *,
    freshness_status: str = "FRESH",
    stale_reasons: list[str] | None = None,
    missing_inputs: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "openclaw_business_object_layer_audit_read_model_v0",
        "freshness_status": freshness_status,
        "generated_at": "2026-05-31T04:30:00+00:00",
        "fresh_for_minutes": 60,
        "input_manifest": [
            {"input_ref": "estate_topology", "status": "PRESENT"},
            {"input_ref": "reference_resolver", "status": "PRESENT"},
            {"input_ref": "change_sentinel", "status": "PRESENT"},
            {"input_ref": "live_arts_bundle", "status": "PRESENT"},
        ],
        "missing_inputs": missing_inputs or [],
        "stale_reasons": stale_reasons or [],
    }


def _base_sources(root: Path) -> None:
    _write_json(
        root,
        "generated/read_models/openclaw_estate_topology_registry.json",
        {
            "actual_repos": ["openclaw-eyes", "openclaw-runtime"],
            "bridge_paths": [
                {
                    "access_status": "PARTIAL",
                    "bridge_id": "pc_e_drive_bridge",
                    "local_path": "/mnt/e/openclaw",
                    "machine_id": "pc",
                }
            ],
            "codex_web_artifacts": [
                {
                    "canonical_status": "UNREACHABLE",
                    "commit_ref": "deadbeef",
                    "repo_name": "openclaw-eyes",
                    "source_truth": False,
                }
            ],
            "known_unknowns": [
                {
                    "question": "Where should the canonical system knowledge registry live?",
                    "status": "UNKNOWN",
                    "unknown_id": "canonical_registry_home",
                }
            ],
            "machines": [
                {
                    "display_name": "PC / WSL backend machine",
                    "evidence_status": "CONFIRMED",
                    "machine_id": "pc",
                    "machine_role": "backend_and_runtime_development",
                }
            ],
            "recommended_actions": [
                {
                    "action": "Install estate topology registry in /home/openclaw.",
                    "owner_hint": "PC_BACKEND",
                    "priority": 1,
                    "reason": "Agents need one local map before more cross-repo work.",
                    "status": "CONFIRMED",
                }
            ],
            "registry_presence": [
                {
                    "branch_name": "codex/system-knowledge-registry-v0-local",
                    "commit_ref": "abc123",
                    "display_name": "Evidence-Grounded Context Registry",
                    "registry_id": "evidence_grounded_context_registry",
                    "repo_name": "openclaw-eyes",
                    "status": "PRESENT_ON_REVIEW_BRANCH",
                }
            ],
            "repo_working_copies": [
                {
                    "classification": "PC_BACKEND",
                    "evidence_status": "CONFIRMED",
                    "machine_id": "pc",
                    "remote_status": "CONFIRMED",
                    "repo_key": "openclaw-eyes",
                    "repo_name": "openclaw-eyes",
                    "working_copy_id": "pc_openclaw_eyes_backend",
                    "worktree_status": "DIRTY",
                }
            ],
            "source_of_truth_areas": [
                {
                    "area_id": "mac_excel_edge_worker",
                    "display_name": "Mac Excel Edge Worker",
                    "notes": "PC emits packages; Mac owns Mac-local execution.",
                    "owner_classification": "MAC_APP",
                    "owner_repo_key": "openclaw-mission-control",
                    "ownership_rule": "Mac-local Excel/PDF helper code belongs with Mac architecture.",
                    "status": "CONFIRMED",
                }
            ],
            "topology_summary": {
                "actual_repos": ["openclaw-eyes", "openclaw-runtime"],
                "bridge_transport": "/mnt/e/openclaw <-> /Volumes/openclaw_e",
                "codex_web_artifacts_are_source_truth": False,
                "mac_app_working_copy": "mac_mission_control_app",
                "pc_backend_working_copy": "pc_openclaw_eyes_backend",
            },
        },
    )
    _write_json(
        root,
        "generated/read_models/openclaw_reference_resolver.json",
        {
            "drift_count": 0,
            "git_branch_refs": [
                {
                    "branch": "codex/system-knowledge-registry-v0-local",
                    "current_head_commit": "abc123",
                    "dirty_status": "DIRTY",
                    "local_status": "UNREACHABLE",
                    "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
                    "mac_mirror_path": "/Users/example/Eyes",
                    "mac_mirror_status": "LOCAL_PATH_UNREACHABLE",
                    "remote_status": "RESOLVED_REMOTE",
                    "target_ref": "openclaw_eyes_registry_review_branch",
                }
            ],
            "reference_resolutions": [
                {
                    "resolved_status": "RESOLVED_REMOTE",
                    "resolved_value": "abc123",
                    "target_ref": "openclaw_eyes_registry_review_branch",
                }
            ],
            "resolution_count": 1,
            "rules": ["Canonical sources store stable refs."],
            "target_count": 1,
        },
    )
    _write_json(
        root,
        "generated/read_models/openclaw_business_object_layer_audit.json",
        _business_object_audit_payload(),
    )
    _write_json(
        root,
        "generated/read_models/live_arts_md_invoice_review_bundle.json",
        {
            "live_arts_md_bundle": {
                "blockers": ["Prepare invoice PDF", "Confirm the Live Arts MD recipient/contact."],
                "developer_end_to_end_card": {
                    "artifact_storage_policy": {
                        "access_required": ["WORKBOOK_ACCESS", "OUTPUT_FOLDER_PERMISSION"],
                        "permission_repair_action": "Grant file/folder access via Access Broker",
                    }
                },
                "invoice_artifact": {
                    "artifact_review_status": "NOT_READY",
                    "attachment_ready": False,
                    "known_artifact_guardrails": {
                        "bridge_pdf_placeholder": {
                            "pc_reference_path": "/mnt/e/openclaw/artifacts/placeholder.pdf",
                            "status": "INVALID_PLACEHOLDER",
                            "trusted_as_selected_invoice_artifact": False,
                        },
                        "trusted_selected_invoice_artifact_present": False,
                    },
                    "pdf_export_package": {
                        "execution_venue": "MAC_LOCAL",
                        "invoice_id": "2026-1001",
                        "output_bridge_path": "/mnt/e/openclaw/artifacts/invoice.pdf",
                        "output_mac_path": "scoped_live_arts_md_export/2026-1001.pdf",
                        "output_pc_reference_path": "/mnt/e/openclaw/artifacts/invoice.pdf",
                        "request_payload_ready": True,
                        "required_capability": "MAC_EXCEL_PDF_EXPORT",
                        "selected_sheet_label": "June 2026 Speaker Rental",
                        "source_workbook_mac_path": "/Users/example/Invoice Live Arts MD.xlsx",
                        "status": "PDF_EXPORT_PACKAGE_READY_FOR_MAC",
                    },
                },
                "invoice_selection": {
                    "selected_invoice_candidate": {
                        "amount_display": "$900",
                        "invoice_id": "2026-1001",
                        "ledger_posted": False,
                        "paid": False,
                        "receipt_status": "UNPAID",
                        "selection_status": "OPERATOR_CONFIRMED",
                        "sent": False,
                        "sheet_label": "June 2026 Speaker Rental",
                        "submitted": False,
                        "work_type": "Speaker Rental",
                    }
                },
                "machine_proof": {
                    "live_arts_md_does_not_require_coupa": True,
                    "live_arts_md_does_not_require_po": True,
                },
                "manual_send_proof": {
                    "file_backed_proof": False,
                    "invoice_id": "2026-1001",
                    "missing_required_fields": ["proof screenshot/ref"],
                    "proof_status": "MANUAL_SEND_PROOF_PENDING",
                    "receipt_received": False,
                    "sent_timestamp": "2026-05-28T14:32:00-04:00",
                },
                "next_safe_move": "Prepare invoice PDF",
                "payment_watch": {
                    "bank_ledger_read_performed": False,
                    "ledger_match_status": "NOT_ATTEMPTED",
                    "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
                },
            }
        },
    )
    _write_json(
        root,
        "generated/read_models/invoice_review_bundle.json",
        {
            "capital_hilton_bundle": {
                "approval_footer": {
                    "approval_disabled_reasons": ["Coupa proof missing", "Invoice record/page not selected"],
                    "approval_ready": False,
                },
                "blockers": [
                    "Coupa submission proof is still required.",
                    "OpenClaw needs the current invoice page/period before it can attach the Excel invoice.",
                ],
                "bundle_id": "invoice_review_bundle:capital_hilton:v0",
                "client_ref": "capital_hilton",
                "coupa_invoice_proof": {
                    "required": True,
                    "status": "MISSING",
                    "supplier_portal_provider": "COUPA",
                    "supplier_portal_required": True,
                },
                "excel_invoice_artifact": {
                    "attachment_ready": False,
                    "display_name": "Capital Hilton Excel invoice candidate",
                    "linkage_status": "GENERATION_AUTHORITY_REQUIRED",
                    "mac_visible_ref": "/Volumes/openclaw_e/generated/invoice.xlsx",
                    "pc_bridge_ref": "/mnt/e/openclaw/generated/invoice.xlsx",
                    "proof_status": "GENERATION_AUTHORITY_REQUIRED",
                },
                "invoice_selection": {
                    "active_workbook_state": "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION",
                    "execution_boundary": {"operator_approval": "NOT_GRANTED"},
                    "workflow_progress": {"portal_submission_execution_status": "NOT_SUBMITTED"},
                },
            }
        },
    )
    _write_json(
        root,
        "generated/read_models/hermes_mission_sentinel.json",
        {
            "automation_ready_status": "NOT_SEND_READY",
            "contract_status": "READINESS_SENTINEL_NO_EXECUTION",
            "critical_path": [
                {
                    "required_receipt": "invoice_attachment_confirmed_receipt",
                    "status": "BLOCKING",
                    "title": "Get invoice artifact/attachment right",
                }
            ],
            "current_blockers": ["invoice artifact/attachment not ready"],
            "do_not_spend_time_on": ["Coupa/PO rails", "ledger automation"],
            "urgent_goal": "Send the Live Arts MD invoice today before the cutoff, or manually send it.",
        },
    )
    _write_json(
        root,
        "generated/read_models/hermes_chief_build_handoff.json",
        {
            "build_gaps": ["manual artifact attach/link rail"],
            "contract_status": "DEVELOPER_BUILD_HANDOFF_NO_PRODUCTION_AUTHORITY",
            "handoff_ref": "hermes_chief_build_handoff:test",
            "recommended_chief_tasks": [
                {
                    "priority": "CRITICAL",
                    "target_repo": "BOTH",
                    "title": "Build/verify manual artifact attach/link rail",
                    "why_it_matters": "The invoice attachment is the current blocker.",
                }
            ],
        },
    )
    _write_json(root, "generated/read_models/purpose_bound_automation_charter.json", {"charter_rows": [{"module_ref": "invoice_manager"}]})
    _write_json(
        root,
        "generated/read_models/hermes_gravity_controller.json",
        {
            "charter_lookup": {"charter_count": 1},
            "contract_status": "DETERMINISTIC_NON_EXECUTING_PURPOSE_BOUND_GRAVITY_CONTROLLER",
        },
    )
    _write_json(
        root,
        "generated/read_models/build_now_vs_hold_queue_posture.json",
        {
            "classified_items": [
                {
                    "next_safe_move": "Use this as a bounded work-packet prompt scaffold.",
                    "posture_category": "BUILD_NOW_READY",
                    "title": "Propose a Markdown organization/reorg plan without moving files.",
                }
            ]
        },
    )
    _write_json(
        root,
        "generated/read_models/work_terrain_build_cue_reconciliation_queue.json",
        {
            "default_candidates": [
                {
                    "next_safe_move": "Implement safe guided capture writer contract.",
                    "ready_to_build": True,
                    "title": "Capital Hilton Capture Rail Cue",
                }
            ]
        },
    )


def _compile(tmp_path: Path, generated_at: str = "2026-05-31T00:00:00+00:00") -> dict:
    _base_sources(tmp_path)
    return compile_openclaw_context_wiki(repo_root=tmp_path, generated_at=generated_at)


def test_wiki_pages_are_generated(tmp_path):
    summary = _compile(tmp_path)

    assert summary["page_count"] == len(PAGE_OUTPUTS)
    for filename in PAGE_OUTPUTS:
        assert (tmp_path / "generated/wiki/openclaw" / filename).is_file()


def test_readme_contains_source_of_truth_warning(tmp_path):
    _compile(tmp_path)

    readme = (tmp_path / "generated/wiki/openclaw/README.md").read_text(encoding="utf-8")
    assert SOURCE_OF_TRUTH_WARNING in readme
    assert FOOTER in readme


def test_wiki_index_includes_business_object_audit_freshness(tmp_path):
    summary = _compile(tmp_path)
    index = summary["index"]

    assert index["business_object_audit_freshness_status"] == "FRESH"
    assert index["business_object_audit_generated_at"] == "2026-05-31T04:30:00+00:00"
    assert index["business_object_audit_inputs_tracked"] == 4
    assert index["business_object_audit_missing_inputs"] == []
    assert index["business_object_audit_stale_reasons"] == []


def test_fresh_business_object_audit_renders_fresh_line(tmp_path):
    _compile(tmp_path)

    for filename in (
        "System Overview.md",
        "Evidence-Grounded Context Registry.md",
        "Hermes and Chief.md",
        "Build Order.md",
    ):
        text = (tmp_path / "generated/wiki/openclaw" / filename).read_text(encoding="utf-8")
        assert "Business-object audit freshness: FRESH." in text


def test_stale_business_object_audit_renders_warning(tmp_path):
    _base_sources(tmp_path)
    _write_json(
        tmp_path,
        "generated/read_models/openclaw_business_object_layer_audit.json",
        _business_object_audit_payload(
            freshness_status="STALE_INPUT_CHANGED",
            stale_reasons=["Audit input hashes changed: reference_resolver"],
            missing_inputs=["reference_resolver"],
        ),
    )
    summary = compile_openclaw_context_wiki(
        repo_root=tmp_path,
        generated_at="2026-05-31T00:00:00+00:00",
    )

    assert summary["index"]["business_object_audit_freshness_status"] == "STALE_INPUT_CHANGED"
    assert any(
        item["title"] == "Business-object audit stale"
        for item in summary["index"]["contradictions"]
    )
    for filename in (
        "System Overview.md",
        "Evidence-Grounded Context Registry.md",
        "Hermes and Chief.md",
        "Build Order.md",
    ):
        text = (tmp_path / "generated/wiki/openclaw" / filename).read_text(encoding="utf-8")
        assert (
            "This page is based on a stale business-object audit. Regenerate before using as planning source."
            in text
        )


def test_wiki_pages_include_source_refs(tmp_path):
    _compile(tmp_path)

    for filename in PAGE_OUTPUTS:
        text = (tmp_path / "generated/wiki/openclaw" / filename).read_text(encoding="utf-8")
        assert "## Source refs / input read-model refs" in text
        assert "generated/read_models/" in text or "generated/system_knowledge/" in text


def test_unknown_inputs_remain_marked_unknown(tmp_path):
    _compile(tmp_path)

    known_unknowns = (tmp_path / "generated/wiki/openclaw/Known Unknowns.md").read_text(encoding="utf-8")
    assert "Status: UNKNOWN" in known_unknowns
    assert "Where should the canonical system knowledge registry live?" in known_unknowns


def test_compiler_does_not_invent_missing_registries(tmp_path):
    summary = _compile(tmp_path)

    index = summary["index"]
    missing_paths = {item["path"] for item in index["missing_inputs"]}
    source_paths = {item["path"] for item in index["source_inputs"]}
    assert "generated/system_knowledge/openclaw_system_knowledge_registry.*" in missing_paths
    assert "generated/system_knowledge/openclaw_system_knowledge_registry.*" not in source_paths

    evidence_page = (tmp_path / "generated/wiki/openclaw/Evidence-Grounded Context Registry.md").read_text(encoding="utf-8")
    assert "openclaw_system_knowledge_registry_files, missing" in evidence_page


def test_contradiction_section_appears_when_seeded_test_data_conflicts(tmp_path):
    _base_sources(tmp_path)
    resolver_path = tmp_path / "generated/read_models/openclaw_reference_resolver.json"
    resolver = json.loads(resolver_path.read_text(encoding="utf-8"))
    resolver["drift_count"] = 1
    resolver["reference_resolutions"].append({"target_ref": "bridge", "resolved_status": "DRIFT"})
    resolver_path.write_text(json.dumps(resolver, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    live_path = tmp_path / "generated/read_models/live_arts_md_invoice_review_bundle.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    live["live_arts_md_bundle"]["send_readiness"] = "READY"
    live["live_arts_md_bundle"]["approval_ready"] = False
    live["live_arts_md_bundle"]["attachment_ready"] = False
    live_path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = compile_openclaw_context_wiki(repo_root=tmp_path, generated_at="2026-05-31T00:00:00+00:00")

    live_page = (tmp_path / "generated/wiki/openclaw/Live Arts MD Invoice Automation.md").read_text(encoding="utf-8")
    assert "Workflow readiness conflicts with attachment or approval" in live_page
    assert summary["index"]["contradiction_count"] > 0
    assert any(item["title"] == "Reference resolver drift reported" for item in summary["index"]["contradictions"])


def test_build_order_page_contains_top_tasks(tmp_path):
    _compile(tmp_path)

    build_order = (tmp_path / "generated/wiki/openclaw/Build Order.md").read_text(encoding="utf-8")
    assert "Install estate topology registry in /home/openclaw." in build_order
    assert "Build/verify manual artifact attach/link rail" in build_order
    assert "Capital Hilton Capture Rail Cue" in build_order


def test_live_arts_page_reflects_facts_without_overclaiming_send_pdf_or_ledger(tmp_path):
    _compile(tmp_path)

    live_page = (tmp_path / "generated/wiki/openclaw/Live Arts MD Invoice Automation.md").read_text(encoding="utf-8")
    assert "sent=false" in live_page
    assert "ledger_posted=false" in live_page
    assert "file_backed_proof=false" in live_page
    assert "PDF export package status: PDF_EXPORT_PACKAGE_READY_FOR_MAC" in live_page
    assert "Do not claim OpenClaw sent the invoice." in live_page
    assert "Do not claim PDF export completed just because a Mac package is ready." in live_page
    assert "Sent: true" not in live_page


def test_json_index_parses(tmp_path):
    _compile(tmp_path)

    index_path = tmp_path / "generated/read_models" / INDEX_JSON_NAME
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "openclaw_context_wiki_compiler_v0"
    assert payload["pages"]


def test_operator_summary_avoids_raw_backend_sludge(tmp_path):
    _compile(tmp_path)

    text = (tmp_path / "generated/read_models" / OPERATOR_INDEX_NAME).read_text(encoding="utf-8")
    assert "hidden_request_payload" not in text
    assert "body_template" not in text
    assert text.count("{") == 0
    assert "Pages generated:" in text


def test_no_live_automation_authority_is_added(tmp_path):
    summary = _compile(tmp_path)

    flags = summary["index"]["boundary_flags"]
    assert flags["compiler_generated_view_only"] is True
    for key, expected in AUTHORITY_BOUNDARY_FLAGS.items():
        assert flags[key] is expected
    for key, value in flags.items():
        if key == "compiler_generated_view_only":
            continue
        assert value is False
