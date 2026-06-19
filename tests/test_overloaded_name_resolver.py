from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entity_name_registry import build_entity_name_registry
from overloaded_name_resolver import AMBIGUOUS, AMBIGUOUS_SENSITIVE, RESOLVED, resolve_overloaded_name


def test_registry_has_required_ledger_referents_and_vault_has_no_path():
    registry = build_entity_name_registry(generated_at="2026-06-19T00:00:00+00:00")
    ledger = registry["names"]["ledger"]
    by_id = {row["referent_id"]: row for row in ledger}

    assert set(by_id) == {
        "business_ops",
        "control_plane",
        "gate_decision",
        "receipts",
        "gig_invoice",
        "bank_finance_vault",
    }
    assert by_id["business_ops"]["sensitivity"] == "operational"
    assert by_id["bank_finance_vault"]["sensitivity"] == "sensitive-vault"
    assert by_id["bank_finance_vault"]["default_surface"] == "NONE"
    assert by_id["bank_finance_vault"]["location"] == "VAULT_WALL_REFERENT_ONLY_NO_PATH"
    assert registry["machine_proof"]["vault_path_constructed"] is False
    assert "FinancePrivate" not in json.dumps(registry, sort_keys=True)


def test_check_the_ledger_no_context_is_ambiguous_sensitive_not_bank_resolution():
    result = resolve_overloaded_name("check the ledger", {"world_ref": "general"})

    assert result.status == AMBIGUOUS_SENSITIVE
    assert result.resolved_referent_id is None
    assert "bank_finance_vault" in {candidate["referent_id"] for candidate in result.candidates}


def test_polish_loop_surface_resolves_control_plane_ledger():
    result = resolve_overloaded_name("check the ledger", {"active_surface_ref": "polish_loop"})

    assert result.status == RESOLVED
    assert result.resolved_referent_id == "control_plane"


def test_finance_client_context_resolves_gig_invoice_ledger():
    result = resolve_overloaded_name(
        "check the ledger",
        {
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow_session",
        },
    )

    assert result.status == RESOLVED
    assert result.resolved_referent_id == "gig_invoice"


def test_general_inbox_is_ambiguous_without_sensitive_candidate():
    result = resolve_overloaded_name("check the inbox", {"world_ref": "general"})

    assert result.status == AMBIGUOUS
    assert {candidate["referent_id"] for candidate in result.candidates} == {
        "gmail_inbox",
        "bus_inbox",
        "operator_action_inbox",
    }


def test_business_ops_ledger_qualifier_resolves():
    result = resolve_overloaded_name("check the business-ops ledger", {"world_ref": "general"})

    assert result.status == RESOLVED
    assert result.resolved_referent_id == "business_ops"
