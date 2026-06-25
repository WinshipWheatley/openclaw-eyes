import sqlite3
import pytest
from pathlib import Path
from ar_counterparty_contact_operations import seed_capital_hilton_annette_fixture
from capital_hilton_payload_builder import build_capital_hilton_read_model

def _metadata_receipt(tmp_path: Path) -> Path:
    import json
    path = tmp_path / "lookup_receipt.json"
    path.write_text(
        json.dumps({
            "schema_version": "ANNETTE_CAPITAL_HILTON_GMAIL_METADATA_LOOKUP_RECEIPT_V0",
            "receipt_id": "receipt:gmail_metadata_lookup:annette_capital_hilton_fixture",
            "objective_id": "cassandra_operator_objective:5c8cfd7f7d50f40e",
            "result": "metadata_match_found",
            "matching_message_count": 1,
            "raw_body_read": False,
            "metadata_only": True,
            "metadata_evidence": [
                {
                    "date": "2026-05-06T14:27:21+00:00",
                    "sender": "Annette Sunga <Annette.Sunga@hilton.com>",
                    "subject": "FW: Winship invoice",
                    "message_id_hash": "6e19b4fa49374cd1c1f7116f",
                    "thread_id_hash": "6e19b4fa49374cd1c1f7116f",
                }
            ],
        }),
        encoding="utf-8",
    )
    return path

def test_build_capital_hilton_read_model(tmp_path):
    db = tmp_path / "ar.sqlite"
    receipt_path = _metadata_receipt(tmp_path)
    
    seed_capital_hilton_annette_fixture(
        sqlite_path=db,
        metadata_receipt_path=receipt_path,
        generated_at="2026-06-25T00:00:00+00:00"
    )
    
    with sqlite3.connect(db) as conn:
        model = build_capital_hilton_read_model(conn)
        
    assert model["schema_version"] == "AR_CAPITAL_HILTON_READ_MODEL_V0"
    assert model["account"]["account_id"] == "capital_hilton"
    assert len(model["contacts"]) == 1
    assert model["contacts"][0]["display_name"] == "Annette Sunga"
    assert len(model["communication_policies"]) >= 1
    assert model["status"] == "available"
    assert "generation_timestamp" in model
