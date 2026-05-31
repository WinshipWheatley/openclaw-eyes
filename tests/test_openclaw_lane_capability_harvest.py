import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_lane_capability_harvest as harvest
from scripts.export_openclaw_lane_capability_harvest import main as export_main


FIXED_NOW = "2026-05-31T21:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixtures(read_root: Path, wiki_root: Path) -> None:
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
                    "pdf_export_package": {
                        "request_payload_ready": True,
                        "invoice_id": "2026-1001",
                        "selected_sheet_label": "June 2026 Speaker Rental",
                    },
                },
                "payment_watch": {
                    "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
                    "ledger_posting_allowed": False,
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
                "invoice_selection": {"workbook_may_contain_multiple_invoice_records": True},
                "coupa_invoice_proof": {
                    "supplier_portal_provider": "COUPA",
                    "portal_submission_proof_required": True,
                    "portal_submission_action_allowed": False,
                },
                "guardian_approval_request": {"approval_required": True},
            },
        },
    )
    _write_json(
        read_root / "simple_invoice_event_bridge_rail_registry.json",
        {
            "schema_version": "simple_invoice_event_bridge_rail_registry_v0",
            "rail_status": "GENERIC_SIMPLE_INVOICE_EVENT_BRIDGE_RAIL_READY",
            "registered_simple_invoice_prepare_handlers": [
                "invoice_review_action_request.live_arts_md",
                "invoice_review_action_request.st_annes",
            ],
            "supported_action_kinds": [
                "prepare_selected_invoice_pdf_artifact",
                "selected_invoice_pdf_export_completed_candidate",
            ],
            "capital_hilton_separation": {
                "supplier_portal_extension_required": True,
                "purchase_order_extension_required": True,
                "do_not_apply_to_simple_clients": True,
            },
        },
    )
    _write_json(
        read_root / "openclaw_event_bridge_contract.json",
        {
            "schema_version": "openclaw_event_bridge_contract_v0",
            "contract_status": "DETERMINISTIC_HOT_PATH_EVENT_BRIDGE_CONTRACT_NO_EXECUTION",
            "registered_workflow_actions": [
                {"handler_id": "invoice_review_action_request.live_arts_md"},
                {"handler_id": "invoice_review_action_request.st_annes"},
            ],
        },
    )
    _write_json(
        read_root / "openclaw_authority_semantics_registry.json",
        {"schema_version": "openclaw_authority_semantics_registry_v0"},
    )
    _write_json(
        read_root / "openclaw_business_object_layer_audit.json",
        {"schema_version": "openclaw_business_object_layer_audit_read_model_v0", "freshness_status": "FRESH"},
    )
    _write_json(
        read_root / "openclaw_estate_topology_registry.json",
        {"schema_version": "openclaw_estate_topology_registry_read_model_v0"},
    )
    _write_json(
        read_root / "openclaw_context_wiki_index.json",
        {"schema_version": "openclaw_context_wiki_compiler_v0", "pages": []},
    )
    _write_json(
        read_root / "client_invoice_workflow_framework.json",
        {
            "schema_version": "client_invoice_workflow_framework_v0",
            "operator_summary": "St. Anne's and Live Arts MD do not inherit Coupa or PO rails by default.",
            "examples": {
                "st_annes_has_no_coupa_by_default": True,
                "st_annes_complete_without_coupa": {"workflow_complete": True},
            },
        },
    )
    _write_json(
        read_root / "capital_hilton_invoice_delivery_steel_thread.json",
        {"schema_version": "capital_hilton_invoice_delivery_steel_thread_v0"},
    )
    _write_json(
        read_root / "capital_hilton_review_packet_approval.json",
        {"schema_version": "capital_hilton_review_packet_approval_v0"},
    )
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "index.md").write_text("# OpenClaw\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs) -> dict:
    read_root = tmp_path / "read_models"
    wiki_root = tmp_path / "wiki"
    _fixtures(read_root, wiki_root)
    return harvest.build_lane_capability_harvest(
        read_model_root=read_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
        **kwargs,
    )


def test_registry_exports_json_operator_md_and_sqlite(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    system_root = tmp_path / "system_knowledge"
    wiki_root = tmp_path / "wiki"
    _fixtures(read_root, wiki_root)

    result = harvest.export_openclaw_lane_capability_harvest(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )

    assert Path(result.json_path).is_file()
    assert Path(result.operator_path).is_file()
    assert Path(result.sqlite_path).is_file()
    payload = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == harvest.READ_MODEL_VERSION


def test_required_sqlite_tables_exist(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    system_root = tmp_path / "system_knowledge"
    wiki_root = tmp_path / "wiki"
    _fixtures(read_root, wiki_root)
    result = harvest.export_openclaw_lane_capability_harvest(
        read_model_root=read_root,
        system_knowledge_root=system_root,
        wiki_root=wiki_root,
        generated_at=FIXED_NOW,
    )
    connection = sqlite3.connect(result.sqlite_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(harvest.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_live_arts_lane_harvests_simple_invoice_event_bridge_and_payment_watch(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    lane = {row["lane_ref"]: row for row in payload["lanes"]}["live_arts_md_invoice_lane"]
    assert lane["status"] == "ACTIVE_STEEL_THREAD"
    capability_refs = {
        row["capability_ref"]
        for row in payload["harvested_capabilities"]
        if row["produced_by_lane"] == "live_arts_md_invoice_lane"
    }
    assert "capability:simple_invoice_rail" in capability_refs
    assert "capability:event_bridge_prepare_pdf_action" in capability_refs
    assert "capability:payment_watch" in capability_refs


def test_capital_hilton_reuses_invoice_rails_but_keeps_coupa_extension_separate(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    plan = {
        row["reuse_plan_ref"]: row for row in payload["reuse_plans"]
    }["reuse:live_arts_to_capital_hilton"]
    assert "capability:simple_invoice_rail" in plan["reused_capabilities"]
    assert "capability:coupa_po_extension" in plan["new_capabilities_to_add"]
    coupa = {
        row["capability_ref"]: row for row in payload["harvested_capabilities"]
    }["capability:coupa_po_extension"]
    assert "st_annes_invoice_lane" in coupa["not_reusable_by"]
    assert "live_arts_md_invoice_lane" in coupa["not_reusable_by"]


def test_st_annes_placeholder_reuses_simple_invoice_without_coupa_po_or_portal(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    lane = {row["lane_ref"]: row for row in payload["lanes"]}["st_annes_invoice_lane"]
    assert lane["status"] == "PARTIAL"
    plan = {
        row["reuse_plan_ref"]: row for row in payload["reuse_plans"]
    }["reuse:live_arts_to_st_annes"]
    assert "capability:simple_invoice_rail" in plan["reused_capabilities"]
    assert "Coupa" in plan["blocked_capabilities"]
    assert "supplier portal" in plan["blocked_capabilities"]
    assert "purchase order blockers" in plan["blocked_capabilities"]


def test_hermes_recommends_finishing_invoice_sequence_until_all_three_proven(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    rec = payload["hermes_recommendation"]
    assert rec["recommended_next_lane"] == "finish_invoice_steel_thread_sequence"
    assert "not all proven" in rec["reason"]


def test_all_three_invoice_lanes_proven_moves_to_adjacent_payment_proof_lane(tmp_path: Path) -> None:
    payload = _build(
        tmp_path,
        lane_status_overrides={
            "live_arts_md_invoice_lane": "PROVEN",
            "capital_hilton_invoice_lane": "PROVEN",
            "st_annes_invoice_lane": "PROVEN",
        },
    )
    rec = payload["hermes_recommendation"]
    assert rec["recommended_next_lane"] == "payment_proof_intake_lane"
    assert rec["expected_new_capability"] == "payment proof receipt intake"
    assert "payment_watch" in rec["expected_reused_capabilities"]


def test_next_lane_recommendation_includes_reuse_and_one_new_capability(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    candidate = {
        row["candidate_ref"]: row for row in payload["next_lane_candidates"]
    }["payment_proof_intake_lane"]
    assert "payment_watch" in candidate["capabilities_reused"]
    added = json.loads(candidate["capabilities_added"])
    assert added == ["payment proof receipt intake"]


def test_do_not_work_now_blocks_generic_telegram_ledger_posting_and_remote_relay(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    text = " ".join(payload["do_not_work_now"])
    assert "generic Telegram polish" in text
    assert "ledger posting" in text
    assert "remote Mac or cloud relay" in text


def test_no_live_automation_authority_is_added(tmp_path: Path) -> None:
    payload = _build(tmp_path)
    flags = payload["no_authority_flags"]
    assert flags["lm_called"] is False
    assert flags["chief_launched"] is False
    assert flags["email_accessed"] is False
    assert flags["gmail_accessed"] is False
    assert flags["browser_accessed"] is False
    assert flags["coupa_accessed"] is False
    assert flags["workbook_cells_read"] is False
    assert flags["pdf_generated_or_exported"] is False
    assert flags["ledger_mutated"] is False


def test_cli_export_returns_ready(tmp_path: Path) -> None:
    read_root = tmp_path / "read_models"
    system_root = tmp_path / "system_knowledge"
    wiki_root = tmp_path / "wiki"
    _fixtures(read_root, wiki_root)
    rc = export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--wiki-root",
            str(wiki_root),
            "--generated-at",
            FIXED_NOW,
        ]
    )
    assert rc == 0
    json.loads((read_root / harvest.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
