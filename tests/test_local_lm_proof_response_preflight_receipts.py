import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_preflight_receipts as preflight
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T06:10:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_lm_runtime_discovery.json",
        {
            "status": "LOCAL_LM_RUNTIME_DISCOVERY_READY",
            "recommended_candidate_ref": "local_llm_shadow_mode",
            "ready_for_pilot": False,
        },
    )
    _write_json(root / "local_lm_proof_to_response_pilot_plan.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY"})
    _write_json(
        root / "local_lm_pilot_harness_selection_packet.json",
        {
            "status": "LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY",
            "selection_packet": {
                "selected_harness_ref": "local_llm_shadow_mode",
                "selected_runtime_ref": "none_connected_review_only",
                "selected_model_ref": "not_selected_pending_operator_review",
                "invocation_allowed": False,
                "tool_access": False,
                "memory_write_access": False,
                "business_action_authority": False,
            },
        },
    )
    _write_json(root / "local_lm_harness_inventory_receipts.json", {"status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        },
    )
    return root


def _read_model(tmp_path: Path) -> dict:
    return preflight.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "preflight.sqlite",
        generated_at=FIXED_NOW,
    )


def _receipt_refs(rows: list[dict]) -> set[str]:
    return {row["receipt_ref"] for row in rows}


def test_ready_for_live_invocation_is_false(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == preflight.READY_STATUS
    assert read_model["ready_for_operator_decision"] is True
    assert read_model["ready_for_live_invocation"] is False
    assert read_model["authority_boundary"]["ready_for_live_invocation"] is False


def test_operator_approval_receipt_remains_missing(tmp_path):
    read_model = _read_model(tmp_path)

    assert "operator_approval_receipt" in _receipt_refs(read_model["receipts_missing"])
    assert read_model["machine_proof"]["operator_approval_present"] is False


def test_no_external_provider_receipt_present(tmp_path):
    read_model = _read_model(tmp_path)

    assert "no_external_provider_receipt" in _receipt_refs(read_model["receipts_present"])
    assert read_model["machine_proof"]["external_provider_used"] is False
    assert read_model["authority_boundary"]["external_provider_connect_allowed"] is False


def test_no_tool_authority_receipt_present(tmp_path):
    read_model = _read_model(tmp_path)

    assert "no_tool_authority_receipt" in _receipt_refs(read_model["receipts_present"])
    assert read_model["machine_proof"]["tool_authority"] is False
    assert read_model["authority_boundary"]["tool_authority_allowed"] is False


def test_redaction_policy_receipt_present(tmp_path):
    read_model = _read_model(tmp_path)

    assert "redacted_proof_bundle_policy_receipt" in _receipt_refs(read_model["receipts_present"])


def test_verifier_required_receipt_present(tmp_path):
    read_model = _read_model(tmp_path)

    assert "verifier_required_receipt" in _receipt_refs(read_model["receipts_present"])


def test_selected_model_ref_null_unless_proven_without_runtime_connection(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["selected_harness_ref"] == "local_llm_shadow_mode"
    assert read_model["selected_runtime_ref"] == "none_connected_review_only"
    assert read_model["selected_model_ref"] is None


def test_required_missing_receipts_remain_missing(tmp_path):
    read_model = _read_model(tmp_path)
    missing = _receipt_refs(read_model["receipts_missing"])

    assert "model_invocation_boundary_receipt" in missing
    assert "verifier_pass_fail_receipt" in missing
    assert "published_response_hash_receipt" in missing


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert preflight.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_wiki_and_sqlite(tmp_path):
    sqlite_path = tmp_path / "system_knowledge" / "preflight.sqlite"
    result = preflight.export_local_lm_proof_response_preflight_receipts(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response Preflight Receipts.md",
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")
    with sqlite3.connect(sqlite_path) as conn:
        sqlite_count = conn.execute("SELECT COUNT(*) FROM preflight_receipts").fetchone()[0]

    assert result["status"] == preflight.READY_STATUS
    assert result["ready_for_live_invocation"] == "false"
    assert local == bridge
    assert sqlite_count == len(local["receipts_present"]) + len(local["receipts_missing"])
    assert sqlite_count == local["sqlite_row_count"]
    assert preflight.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof Response Preflight Receipts")
