import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import canonical_state_map as state_map


FIXED_NOW = "2026-06-03T13:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_read_model_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    statuses = {
        "sqlite_governance_registry": "SQLITE_GOVERNANCE_REGISTRY_READY",
        "package_event_index": "PACKAGE_EVENT_INDEX_READY",
        "operator_conversation_journal": "OPERATOR_CONVERSATION_JOURNAL_READY",
        "workflow_package_queue_contract": "WORKFLOW_PACKAGE_QUEUE_V0_READY",
        "st_annes_work_log_events": "ST_ANNES_WORK_LOG_INTAKE_V0_READY",
        "st_annes_invoice_status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
        "capital_hilton_invoice_operator_run_status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
        "capital_hilton_business_development_proposal": "DRAFT_READY_FOR_OPERATOR_REVIEW",
        "agent_voice_profiles": "AGENT_VOICE_PROFILES_V0_READY",
        "automation_permission_registry": "AUTOMATION_PERMISSION_REGISTRY_READY",
        "overnight_workboard": "READY_FOR_OPERATOR_REVIEW",
    }
    for source_id, filename in state_map.SOURCE_FILES.items():
        payload = {
            "read_model_id": source_id,
            "schema_version": f"{source_id}_v0",
            "generated_at": FIXED_NOW,
        }
        if source_id == "st_annes_invoice_status":
            payload["invoice_status"] = statuses[source_id]
        elif source_id == "capital_hilton_business_development_proposal":
            payload["proposal_status"] = statuses[source_id]
        else:
            payload["status"] = statuses[source_id]
        _write_json(root / filename, payload)
    return root


def _domain(read_model: dict, domain_ref: str) -> dict:
    matches = [domain for domain in read_model["domains"] if domain["domain_ref"] == domain_ref]
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


def test_builds_all_required_domains_with_ready_preconditions(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = state_map.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == state_map.MAP_STATUS
    assert read_model["domain_count"] == len(state_map.REQUIRED_DOMAIN_REFS)
    assert {domain["domain_ref"] for domain in read_model["domains"]} == set(state_map.REQUIRED_DOMAIN_REFS)
    assert all(item["ready"] for item in read_model["preconditions"])
    assert read_model["missing_required_inputs"] == []


def test_package_and_conversation_truth_sources_are_explicit(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = state_map.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    package = _domain(read_model, "package_queue")
    assert package["canonical_source"]["source_ref"] == "generated/read_models/workflow_package_queue_contract.json"
    assert any(
        source["source_ref"] == "generated/read_models/package_event_index.json"
        for source in package["supporting_sources"]
    )
    assert "Package status truth comes from package queue / package event index." in read_model["truth_rules"]

    conversation = _domain(read_model, "conversation_journal")
    assert conversation["canonical_source"]["source_ref"] == "generated/read_models/operator_conversation_journal.json"
    assert "Operator-facing history comes from conversation journal." in read_model["truth_rules"]


def test_invoice_proposal_paid_and_ledger_rules_are_guarded(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = state_map.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    capital_invoice = _domain(read_model, "capital_hilton_invoice_status")
    assert capital_invoice["canonical_source"]["source_ref"] == (
        "generated/read_models/capital_hilton_invoice_operator_run_status.json"
    )
    assert any("Do not mark paid from Coupa submission alone." == item for item in capital_invoice["forbidden_mutations"])

    proposal = _domain(read_model, "capital_hilton_proposal_status")
    assert proposal["canonical_source"]["source_ref"] == (
        "generated/read_models/capital_hilton_business_development_proposal.json"
    )
    assert any("Do not infer proposal acceptance from send recording." == item for item in proposal["forbidden_mutations"])

    ledger = _domain(read_model, "business_ledger")
    assert ledger["canonical_source"]["source_ref"] == "generated/read_models/sqlite_governance_registry.json"
    assert any("proposal" in source["reason"].lower() for source in ledger["not_truth_sources"])
    assert "Paid truth never comes from proposal, send, or Coupa submit alone." in read_model["truth_rules"]
    assert "Ledger truth stays isolated until explicit payment evidence." in read_model["truth_rules"]


def test_missing_precondition_marks_not_ready(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    _write_json(root / state_map.SOURCE_FILES["package_event_index"], {"status": "NOT_READY"})

    read_model = state_map.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == state_map.MAP_NOT_READY_STATUS
    assert read_model["machine_proof"]["preconditions_ready"] is False


def test_export_writes_local_bridge_and_wiki(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    result = state_map.export_canonical_state_map(
        read_model_root=root,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Canonical State Map.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == state_map.MAP_STATUS
    assert Path(result["wiki_path"]).exists()
    assert result["domain_count"] == str(len(state_map.REQUIRED_DOMAIN_REFS))


def test_no_mutation_or_unsafe_authority_grants(tmp_path):
    root = _fixture_read_model_root(tmp_path)
    read_model = state_map.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

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
        "sqlite_consolidation_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["database_consolidation_performed"] is False
    assert read_model["machine_proof"]["database_delete_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
    assert all(domain["write_authority"]["mode"] == "no_write_grant_from_this_map" for domain in read_model["domains"])
