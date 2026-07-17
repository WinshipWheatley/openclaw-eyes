from __future__ import annotations

import activation_gate_register
import invoice_cockpit_client_registry as registry
import temporal_recurrence_registry as recurrence


def test_live_arts_registry_is_guardian_gated_with_monthly_july_due_model() -> None:
    live_arts = registry.DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["live_arts_md"]
    assert live_arts["send_state"] == "SEND_REQUIRES_GUARDIAN"
    assert live_arts["send_block"] is False
    assert live_arts["canonical_recipient"] == "Accountant@liveartsmd.org"
    assert live_arts["within_days"] == 30
    assert live_arts["paid_through_period"] == "2026-06"
    assert live_arts["numbering_collision_requires_reconciliation"] is True
    assert live_arts["send_authority"] is False
    assert live_arts["payment_authority"] is False
    assert live_arts["workbook_mutation_authority"] is False

    model = recurrence.ClientRecurrenceRegistry().get("live_arts_md")
    assert model is not None
    assert model.cadence == "monthly"
    assert model.day_of_month == 16
    assert recurrence.next_expected_invoice("live_arts_md", after="2026-06-30").isoformat() == "2026-07-16"


def test_capital_hilton_email_scope_is_separate_from_coupa() -> None:
    capital = registry.DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["capital_hilton"]
    assert capital["delivery_channel"] == "email"
    assert capital["supplier_portal_required"] is False
    assert capital["coupa_transaction_class_in_scope"] is False


def test_w0_capabilities_are_in_activation_gate_register() -> None:
    payload = activation_gate_register.build_activation_gate_register()
    rows = {row["capability_id"]: row for row in payload["capabilities"]}
    assert rows["invoice_send_class_waist"]["gate_stage"] == "operator_approved_live"
    assert rows["invoice_send_class_waist"]["activation_allowed_now"] is False
    assert rows["autonomous_invoice_prepare_scheduler"]["gate_stage"] == "operator_approved_live"
    assert rows["autonomous_invoice_prepare_scheduler"]["activation_allowed_now"] is False
