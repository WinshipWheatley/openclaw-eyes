import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shadow_lm_mode as shadow


def test_shadow_lm_uses_fixtures_only_and_persists_isolated_proof(tmp_path):
    payload = shadow.build_payload(
        db_path=tmp_path / "shadow_lm_mode.sqlite",
        gate_chain_db_path=tmp_path / "gate_chain_harness.sqlite",
        persist=True,
    )

    assert payload["machine_proof"]["fixtures_only"] is True
    assert payload["machine_proof"]["lm1_live_call_performed"] is False
    assert payload["machine_proof"]["lm2_live_call_performed"] is False
    assert payload["machine_proof"]["harness_failed_count"] == 0
    assert payload["machine_proof"]["lm1_shadow_ready"] is True
    assert payload["machine_proof"]["lm2_shadow_ready"] is True

    db_path = Path(payload["isolated_sqlite"]["db_path"])
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"shadow_lm_runs"}


def test_shadow_slots_document_future_lm_interfaces_without_live_calls(tmp_path):
    payload = shadow.build_payload(
        db_path=tmp_path / "shadow_lm_mode.sqlite",
        gate_chain_db_path=tmp_path / "gate_chain_harness.sqlite",
        persist=True,
    )
    run = payload["shadow_run"]

    assert run["lm1_slot"]["accepts_fixture_type"] == "MachineIntentCandidate"
    assert run["lm2_slot"]["accepts_fixture_type"] == "RoleResponseCandidate-compatible response payload"
    assert run["lm1_slot"]["live_call_allowed"] is False
    assert run["lm2_slot"]["live_call_allowed"] is False


def test_exported_readmodel_parses(tmp_path):
    payload = shadow.build_payload(
        db_path=tmp_path / "shadow_lm_mode.sqlite",
        gate_chain_db_path=tmp_path / "gate_chain_harness.sqlite",
        persist=True,
    )
    json_path, operator_path = shadow.write_exports(payload, tmp_path / "read_models")

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == shadow.READ_MODEL_ID
    assert parsed["machine_proof"]["model_api_call_performed"] is False
    assert "fixtures only" in operator_path.read_text(encoding="utf-8").lower()
