import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlite_consolidation_plan as plan


FIXED_NOW = "2026-06-03T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _db(path: str, classification: str, owner_lane: str, risk: str, candidate: bool = False) -> dict:
    return {
        "db_ref": f"sqlite_db:{path}",
        "path": path,
        "classification": classification,
        "owner_lane": owner_lane,
        "purpose": "fixture",
        "tables": [],
        "row_counts": {},
        "last_modified": FIXED_NOW,
        "canonical_truth_allowed": classification == "canonical_workflow_state",
        "writable_by_automation": False,
        "safe_to_delete": False,
        "consolidation_candidate": candidate,
        "consolidation_risk": risk,
        "notes": [],
    }


def _fixture_read_model_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    databases = [
        _db("/home/openclaw/.openclaw/business_ops/ledger.sqlite", "protected_business_ledger", "business_ops", "forbidden"),
        _db("/home/openclaw/.openclaw/business_ops/backups/old.sqlite", "legacy_archive", "business_ops", "low"),
        _db("/home/openclaw/.openclaw/flows/registry.sqlite", "unknown_needs_review", "unknown_review", "medium"),
        _db("/home/openclaw/.openclaw/privacy/token_vault.sqlite", "canonical_workflow_state", "privacy", "forbidden"),
        _db("/home/openclaw/.openclaw/test_harness/gate_chain_harness.sqlite", "test_harness", "test_harness", "medium"),
        _db("/home/openclaw/generated/system_knowledge/openclaw_change_sentinel.sqlite", "generated_status", "system_health", "medium", True),
        _db("/home/openclaw/generated/system_knowledge/package_event_index.sqlite", "generated_evidence", "package_event_index", "high", True),
        _db("/home/openclaw/generated/system_knowledge/st_annes_monthly_work_log.sqlite", "generated_evidence", "invoice_operations", "medium", True),
        _db("/home/openclaw/generated/system_knowledge/workflow_package_queue.sqlite", "canonical_workflow_state", "workflow_package_queue", "low"),
        _db("/home/openclaw/generated/system_knowledge/operator_conversation_journal.sqlite", "canonical_workflow_state", "operator_conversation", "medium"),
    ]
    _write_json(
        root / "sqlite_governance_registry.json",
        {
            "status": "SQLITE_GOVERNANCE_REGISTRY_READY",
            "read_model_id": "sqlite_governance_registry",
            "schema_version": "sqlite_governance_registry_v0",
            "generated_at": FIXED_NOW,
            "database_count": len(databases),
            "classification_counts": {
                "protected_business_ledger": 1,
                "legacy_archive": 1,
                "unknown_needs_review": 1,
                "canonical_workflow_state": 3,
                "test_harness": 1,
                "generated_status": 1,
                "generated_evidence": 2,
            },
            "consolidation_candidate_count": 3,
            "unknown_review_count": 1,
            "databases": databases,
        },
    )
    domains = [
        ("package_queue", "generated/read_models/workflow_package_queue_contract.json"),
        ("request_response", "generated/read_models/package_event_index.json"),
        ("conversation_journal", "generated/read_models/operator_conversation_journal.json"),
        ("st_annes_work_log", "generated/read_models/st_annes_work_log_events.json"),
    ]
    _write_json(
        root / "canonical_state_map.json",
        {
            "status": "CANONICAL_STATE_MAP_READY",
            "read_model_id": "canonical_state_map",
            "schema_version": "canonical_state_map_v0",
            "generated_at": FIXED_NOW,
            "domains": [
                {
                    "domain_ref": domain_ref,
                    "canonical_source": {
                        "source_ref": source_ref,
                        "truth_scope": "fixture",
                    },
                }
                for domain_ref, source_ref in domains
            ],
        },
    )
    _write_json(
        root / "agentic_chain_inspector.json",
        {
            "status": "AGENTIC_CHAIN_INSPECTOR_READY",
            "read_model_id": "agentic_chain_inspector",
            "schema_version": "agentic_chain_inspector_v0",
            "fragmentation_risks": [
                {"risk_id": "business_ledger_exclusion", "severity": "critical", "affected_path_count": 1},
                {"risk_id": "duplicate_package_concepts", "severity": "high", "affected_path_count": 3},
            ],
        },
    )
    _write_json(
        root / "package_event_index.json",
        {
            "status": "PACKAGE_EVENT_INDEX_READY",
            "read_model_id": "package_event_index",
            "schema_version": "package_event_index_v0",
            "source_systems": {
                "workflow_package_queue_sqlite": {
                    "path": "generated/system_knowledge/workflow_package_queue.sqlite",
                },
                "operator_conversation_journal_sqlite": {
                    "path": "generated/system_knowledge/operator_conversation_journal.sqlite",
                },
            },
        },
    )
    return root


def _bucket(read_model: dict, section: str, category: str) -> dict:
    matches = [item for item in read_model[section] if item["category"] == category]
    assert len(matches) == 1
    return matches[0]


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_plan_builds_ready_no_touch_and_keep_isolated_sections(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = plan.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == plan.PLAN_STATUS
    assert _bucket(read_model, "do_not_touch_databases", "business_ledger")["count"] == 1
    assert _bucket(read_model, "do_not_touch_databases", "legacy_archives")["count"] == 1
    assert _bucket(read_model, "do_not_touch_databases", "unknown_needs_review")["count"] == 1
    assert _bucket(read_model, "do_not_touch_databases", "protected_evidence")["count"] == 1
    assert _bucket(read_model, "keep_isolated_databases", "test_harness")["count"] == 1
    assert _bucket(read_model, "keep_isolated_databases", "generated_proof_status_dbs")["count"] == 3


def test_candidates_first_move_and_never_rules_are_present(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = plan.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    candidate_refs = {item["candidate_ref"] for item in read_model["consolidation_candidates"]}
    assert {
        "package_queue_event_concepts",
        "request_response_index_concepts",
        "operator_conversation_index_concepts",
        "work_log_staging_if_safe",
    } == candidate_refs
    assert read_model["recommended_first_low_risk_move"]["move_ref"] == "read_only_views_and_indexes_overlay"
    assert read_model["recommended_first_low_risk_move"]["write_allowed_now"] is False
    assert "Never consolidate ledger into package DB." in read_model["never_consolidate"]
    assert "Never consolidate secrets/tokens into read models." in read_model["never_consolidate"]
    assert "Never consolidate raw prompt bodies into operator journal." in read_model["never_consolidate"]


def test_migration_requirements_include_all_required_gates(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = plan.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    requirement_refs = {
        item["requirement_ref"]
        for item in read_model["migration_requirements_before_any_consolidation"]
    }
    assert set(plan.MIGRATION_REQUIREMENTS) == requirement_refs
    assert all(
        item["required_before_consolidation"] == "yes"
        for item in read_model["migration_requirements_before_any_consolidation"]
    )


def test_missing_precondition_marks_not_ready(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    _write_json(root / "canonical_state_map.json", {"status": "NOT_READY"})

    read_model = plan.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == plan.PLAN_NOT_READY_STATUS
    assert read_model["machine_proof"]["preconditions_ready"] is False


def test_export_writes_local_bridge_and_wiki(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    result = plan.export_sqlite_consolidation_plan(
        read_model_root=root,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "SQLite Consolidation Plan.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == plan.PLAN_STATUS
    assert Path(result["wiki_path"]).exists()
    assert result["candidate_count"] == "4"


def test_no_mutation_or_unsafe_authority_grants(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = plan.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    unsafe_keys = {
        "email_send_allowed",
        "gmail_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "database_delete_allowed",
        "database_move_allowed",
        "database_migration_allowed",
        "sqlite_consolidation_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["existing_database_mutation_performed"] is False
    assert read_model["machine_proof"]["database_consolidation_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
    assert all(item["migration_allowed_now"] is False for item in read_model["consolidation_candidates"])
