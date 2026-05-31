import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_business_object_layer_audit as audit
import openclaw_authority_semantics_registry as authority_registry
from scripts.export_openclaw_business_object_layer_audit import main as export_main


FIXED_NOW = "2026-05-31T05:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixtures(read_root: Path, wiki_root: Path) -> None:
    _write_json(
        read_root / "openclaw_estate_topology_registry.json",
        {
            "schema_version": "openclaw_estate_topology_registry_read_model_v0",
            "machine_count": 2,
            "repo_working_copy_count": 5,
            "external_registry_materialization": [
                {
                    "registry_ref": "openclaw_eyes_system_knowledge_registry_external_input",
                    "source_repo": "openclaw-eyes",
                    "source_branch": "main",
                    "source_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "canonical_owner": "openclaw-eyes",
                    "local_role": "READ_ONLY_EXTERNAL_INPUT",
                    "local_status": "EXTERNAL_REGISTRY_MATERIALIZED",
                    "artifact_count": 5,
                    "notes": "openclaw-eyes system knowledge registry imported as read-only external input.",
                }
            ],
            "registry_presence": [
                {
                    "registry_id": "evidence_grounded_context_registry",
                    "current_state": "CANONICAL_ON_MAIN",
                    "canonical_status": "CANONICAL",
                    "commit_ref": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                }
            ],
            "source_of_truth_areas": [
                {
                    "area_id": "mac_excel_edge_worker",
                    "status": "CONFIRMED",
                    "ownership_rule": "Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.",
                },
                {
                    "area_id": "access_broker",
                    "status": "PARTIAL",
                    "ownership_rule": "Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.",
                },
                {
                    "area_id": "evidence_grounded_context_registry",
                    "current_state": "CANONICAL_ON_MAIN",
                    "status": "CANONICAL_ON_MAIN",
                    "canonical_status": "CANONICAL",
                    "review_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                },
            ],
        },
    )
    _write_json(
        read_root / "openclaw_reference_resolver.json",
        {
            "schema_version": "openclaw_reference_resolver_read_model_v0",
            "drift_count": 0,
            "git_branch_refs": [
                {
                    "target_ref": "openclaw_eyes_main_branch",
                    "branch": "main",
                    "current_head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "remote_status": "RESOLVED_REMOTE",
                    "resolution_status": "RESOLVED_REMOTE",
                },
                {
                    "target_ref": "openclaw_eyes_registry_review_branch",
                    "branch": "codex/system-knowledge-registry-v0-local",
                    "current_head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "remote_status": "RESOLVED_REMOTE",
                    "resolution_status": "RESOLVED_REMOTE",
                    "local_status": "UNREACHABLE",
                    "mac_mirror_status": "LOCAL_PATH_UNREACHABLE",
                }
            ],
            "reference_resolutions": [
                {
                    "target_ref": "estate_topology_registry_read_model_mirror",
                    "resolved_status": "MISSING",
                }
            ],
        },
    )
    _write_json(
        read_root / "openclaw_change_sentinel.json",
        {
            "schema_version": "openclaw_change_sentinel_read_model_v0",
            "run_status": "NO_MATERIAL_CHANGE",
            "material_change_count": 0,
        },
    )
    _write_json(
        read_root / "openclaw_authority_semantics_registry.json",
        authority_registry.build_registry_payload(generated_at=FIXED_NOW),
    )
    _write_json(
        read_root / "openclaw_context_wiki_index.json",
        {
            "schema_version": "openclaw_context_wiki_compiler_v0",
            "pages": [{"page_ref": "live_arts"}],
            "contradiction_count": 2,
            "missing_inputs": [],
            "top_next_actions": ["Live Arts MD: Prepare invoice PDF"],
        },
    )
    _write_json(
        read_root / "external_system_knowledge_registry_index.json",
        {
            "schema_version": "external_system_knowledge_registry_index_v0",
            "source_repo": "openclaw-eyes",
            "source_branch": "main",
            "source_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "canonical_owner": "openclaw-eyes",
            "local_role": "READ_ONLY_EXTERNAL_INPUT",
            "import_status": "IMPORTED",
            "artifact_count": 5,
        },
    )
    _write_json(
        read_root / "live_arts_md_invoice_review_bundle.json",
        {
            "schema_version": "live_arts_md_invoice_review_bundle_v0",
            "live_arts_md_bundle": {
                "status": "SIMPLE_EMAIL_INVOICE_REVIEW",
                "candidate_selection_rail": {
                    "selected_invoice_summary": "2026-1001 - June 2026 Speaker Rental - $900",
                    "selected_invoice_ids": ["2026-1001"],
                },
                "invoice_artifact": {
                    "attachment_ready": False,
                    "known_artifact_guardrails": {
                        "trusted_selected_invoice_artifact_present": False
                    },
                    "pdf_export_package": {
                        "status": "PDF_EXPORT_PACKAGE_READY_FOR_MAC",
                        "invoice_id": "2026-1001",
                        "selected_sheet_label": "June 2026 Speaker Rental",
                        "output_bridge_path": "/mnt/e/openclaw/artifacts/invoice.pdf",
                        "execution_venue": "MAC_LOCAL",
                        "required_capability": "MAC_EXCEL_PDF_EXPORT",
                        "no_workbook_cell_read": True,
                        "no_email_send": True,
                        "no_ledger_post": True,
                    },
                },
                "payment_watch": {
                    "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
                    "ledger_match_status": "NOT_ATTEMPTED",
                    "bank_ledger_read_performed": False,
                },
                "clara_invoice_email_draft_package": {
                    "draft_status": "DRAFT_PREVIEW_NOT_SEND_READY",
                    "missing_prerequisites": ["attachment_readiness"],
                },
                "client_comms_thread": {
                    "thread_ref": "client_comms_thread:live_arts_md:test",
                    "thread_watch_status": "BLOCKED_UNTIL_SENT_RECEIPT",
                    "guardian_approval_request_status": "NOT_CREATED",
                },
            },
        },
    )
    _write_json(
        read_root / "invoice_review_bundle.json",
        {
            "schema_version": "invoice_review_bundle_v0",
            "capital_hilton_bundle": {
                "status": "READY_FOR_REVIEW_BLOCKED_FOR_SELECTION",
                "invoice_selection": {
                    "operator_question": "Which invoice page/period should OpenClaw prepare for Capital Hilton?"
                },
                "missing_receipts": ["invoice_record_selected_receipt"],
                "guardian_approval_request": {"status": "BLOCKED_PREREQUISITES_MISSING"},
            },
        },
    )
    _write_json(
        read_root / "purpose_bound_automation_charter.json",
        {"schema_version": "purpose_bound_automation_charter_v0", "charter_rows": []},
    )
    _write_json(
        read_root / "openclaw_service_supervision.json",
        {
            "schema_version": "openclaw_service_supervision_read_model_v0",
            "startup_readiness": "READY",
            "core_monitor_status": {
                "request_response_active": True,
                "sentinel_timer_active": True,
                "service_keeper_timer_active": True,
                "unresolved_supervision_risks": [],
            },
            "supervised_units": [
                {
                    "unit_name": "openclaw-request-response.service",
                    "active_state": "active",
                    "sub_state": "running",
                    "timer_settings": {
                        "ExecStart": "/usr/bin/env python3 run.py --watch-seconds 21600"
                    },
                }
            ],
        },
    )
    _write_json(
        read_root / "hermes_mission_sentinel.json",
        {
            "schema_version": "hermes_mission_sentinel_v0",
            "current_blockers": ["invoice candidate not selected"],
        },
    )
    _write_json(
        read_root / "hermes_chief_build_handoff.json",
        {
            "schema_version": "hermes_chief_build_handoff_v0",
            "handoff_status": "PRESENT",
        },
    )
    _write_json(
        read_root / "hermes_gravity_controller.json",
        {
            "schema_version": "hermes_gravity_controller_v0",
            "controller_status": "PRESENT",
        },
    )
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "README.md").write_text("# Wiki\n", encoding="utf-8")


def test_audit_has_required_scorecard_and_inventory(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)

    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )

    assert {row["category"] for row in payload["scorecard"]} == set(audit.SCORE_CATEGORIES)
    assert {row["object_name"] for row in payload["business_objects"]} == set(audit.BUSINESS_OBJECT_NAMES)
    assert payload["freshness_status"] == "FRESH"
    assert payload["fresh_for_minutes"] == audit.DEFAULT_FRESH_FOR_MINUTES
    assert set(payload["input_hashes"]) == {row[0] for row in audit.AUDIT_INPUT_SPECS}
    assert payload["readiness"] == "READY_FOR_BUILD_PLANNING_NOT_EXECUTION"
    for row in payload["scorecard"]:
        assert row["confidence"]
        assert row["strongest_evidence"]
        assert row["biggest_gap"]
        assert row["fastest_improvement"]
        assert row["source_refs"]
        assert row["freshness_notes"]


def test_audit_reflects_live_arts_and_external_registry_claims(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)

    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    corrections = {row["claim_ref"]: row for row in payload["stale_claims_corrected"]}
    branch_object = {
        row["object_name"]: row for row in payload["business_objects"]
    }["openclaw-eyes registry branch"]

    assert "2026-1001" in corrections["live_arts_candidate_unselected"]["corrected_current_claim"]
    assert corrections["openclaw_eyes_registry_external_input"]["correction_status"] == "CORRECTED"
    assert branch_object["implementation_status"] == "EXTERNAL_REGISTRY_MATERIALIZED"
    assert branch_object["blockers"] == []
    assert payload["external_registry_materialization"]["local_role"] == "READ_ONLY_EXTERNAL_INPUT"
    assert payload["missing_inputs"] == []


def test_missing_required_input_marks_audit_stale(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)
    (read_root / "openclaw_context_wiki_index.json").unlink()

    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )

    manifest = {row["input_ref"]: row for row in payload["input_manifest"]}
    assert payload["freshness_status"] == "STALE_MISSING_INPUT"
    assert payload["readiness"] == "STALE_INPUTS_REGENERATION_REQUIRED"
    assert manifest["context_wiki_index"]["status"] == "MISSING"
    assert "context_wiki_index" in payload["missing_inputs"]
    assert {row["confidence"] for row in payload["scorecard"]} == {"LOW"}


def test_changed_input_hash_marks_prior_audit_stale(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)
    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    live_path = read_root / "live_arts_md_invoice_review_bundle.json"
    live_payload = json.loads(live_path.read_text(encoding="utf-8"))
    live_payload["live_arts_md_bundle"]["candidate_selection_rail"][
        "selected_invoice_summary"
    ] = "2026-1001 - updated summary"
    _write_json(live_path, live_payload)

    freshness = audit.assess_audit_freshness(
        payload,
        read_model_root=read_root,
        now=FIXED_NOW,
    )

    assert freshness["freshness_status"] == "STALE_INPUT_CHANGED"
    assert "live_arts_bundle" in freshness["changed_inputs"]


def test_present_registry_objects_are_not_marked_missing(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)

    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    objects = {row["object_name"]: row for row in payload["business_objects"]}
    for object_name in (
        "reference resolver",
        "change sentinel",
        "estate topology registry",
        "context wiki",
    ):
        assert objects[object_name]["implementation_status"] not in {"MISSING", "UNKNOWN"}


def test_authority_score_cites_registry_and_missing_registry_reduces_confidence(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    _fixtures(read_root, wiki_root)

    payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    authority_score = {row["category"]: row for row in payload["scorecard"]}["Authority"]

    assert authority_score["status"] == "STRONG_DEFAULT_DENY_WITH_REGISTRY"
    assert any(
        ref["path"] == "generated/read_models/openclaw_authority_semantics_registry.json"
        for ref in authority_score["source_refs"]
    )

    (read_root / "openclaw_authority_semantics_registry.json").unlink()
    stale_payload = audit.build_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    stale_authority = {row["category"]: row for row in stale_payload["scorecard"]}["Authority"]

    assert stale_payload["freshness_status"] == "STALE_MISSING_INPUT"
    assert stale_authority["confidence"] == "LOW"
    assert stale_authority["status"] == "REGISTRY_MISSING"


def test_export_writes_json_operator_and_sqlite(tmp_path, capsys):
    read_root = tmp_path / "generated" / "read_models"
    wiki_root = tmp_path / "generated" / "wiki" / "openclaw"
    system_root = tmp_path / "generated" / "system_knowledge"
    _fixtures(read_root, wiki_root)

    result = audit.export_openclaw_business_object_layer_audit(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )

    json_path = read_root / audit.JSON_EXPORT_NAME
    sqlite_path = system_root / audit.SQLITE_EXPORT_NAME
    assert result.business_object_count == len(audit.BUSINESS_OBJECT_NAMES)
    assert result.freshness_status == "FRESH"
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == audit.READ_MODEL_VERSION
    assert (read_root / audit.OPERATOR_EXPORT_NAME).exists()
    assert (system_root / audit.SCHEMA_EXPORT_NAME).exists()
    assert (system_root / audit.SEED_EXPORT_NAME).exists()

    connection = sqlite3.connect(sqlite_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert set(audit.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute(
            "SELECT COUNT(*) FROM business_object_inventory"
        ).fetchone()[0] == len(audit.BUSINESS_OBJECT_NAMES)
    finally:
        connection.close()

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--wiki-root",
            str(wiki_root),
            "--format",
            "json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == audit.READ_MODEL_VERSION


def test_source_does_not_call_forbidden_live_surfaces():
    source_files = [
        Path("openclaw_business_object_layer_audit.py"),
        Path("scripts/export_openclaw_business_object_layer_audit.py"),
    ]
    forbidden = [
        "systemctl --user " + "start",
        "systemctl --user " + "restart",
        "git " + "push",
        "open" + "ai",
        "anthro" + "pic",
        "import " + "requests",
        "import " + "httpx",
        "urllib" + ".request",
        "smtp" + "lib",
        "selen" + "ium",
        "play" + "wright",
        "pya" + "utogui",
        "open" + "pyxl",
        "shell" + "=True",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_text in forbidden:
            assert forbidden_text not in text
