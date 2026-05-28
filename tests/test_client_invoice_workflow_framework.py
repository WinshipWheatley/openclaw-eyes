import json
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import client_invoice_workflow_framework as framework
from scripts.export_client_invoice_workflow_framework import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _receipt_set(client_ref: str, *extra: str, omit=()) -> tuple[str, ...]:
    receipts = list(framework._receipt_set_for_recipe(client_ref, omit=tuple(omit)))
    receipts.extend(extra)
    return tuple(dict.fromkeys(receipts))


def test_framework_defines_reusable_rails_with_required_fields():
    assert tuple(field.name for field in fields(framework.InvoiceWorkflowRail)) == (
        "rail_ref",
        "purpose",
        "required_inputs",
        "optional_inputs",
        "required_receipts",
        "output_receipts",
        "allowed_actions",
        "forbidden_actions",
        "readiness_states",
        "blockers",
        "operator_confirmation_points",
        "default_optional",
        "next_safe_move",
    )
    rails = framework.rails_by_ref()

    assert len(rails) >= 12
    for rail_ref in (
        framework.SOURCE_WORKBOOK_RAIL,
        framework.SUPPLIER_PORTAL_RAIL,
        framework.EXCEL_INVOICE_GENERATION_RAIL,
        framework.CLARA_EMAIL_DRAFT_RAIL,
        framework.EXTERNAL_SEND_RAIL,
        framework.PAYMENT_WATCH_RAIL,
        framework.LEDGER_HANDOFF_RAIL,
        framework.TAX_EVIDENCE_RAIL,
    ):
        assert rail_ref in rails
        assert rails[rail_ref]["required_inputs"]
        assert rails[rail_ref]["required_receipts"]
        assert rails[rail_ref]["output_receipts"]


def test_capital_hilton_recipe_composes_coupa_excel_email_payment_and_ledger_tax_rails():
    recipe = framework.recipes_by_client_ref()["capital_hilton"]

    for rail_ref in (
        framework.SOURCE_WORKBOOK_RAIL,
        framework.INVOICE_PERIOD_SHEET_RAIL,
        framework.PERFORMANCE_DATE_CONFIRMATION_RAIL,
        framework.PURCHASE_ORDER_RAIL,
        framework.SUPPLIER_PORTAL_RAIL,
        framework.EXCEL_INVOICE_GENERATION_RAIL,
        framework.CLARA_EMAIL_DRAFT_RAIL,
        framework.GUARDIAN_APPROVAL_RAIL,
        framework.EXTERNAL_SEND_RAIL,
        framework.PAYMENT_WATCH_RAIL,
        framework.LEDGER_HANDOFF_RAIL,
        framework.TAX_EVIDENCE_RAIL,
    ):
        assert framework.recipe_requires_rail(recipe, rail_ref)

    assert recipe["client_specific_portal_requirements"]["portal_ref"] == "coupa_supplier_portal"
    assert recipe["client_specific_portal_requirements"]["supplier_portal_provider"] == "COUPA"
    assert recipe["client_specific_portal_requirements"]["provider_display_name"] == "Coupa supplier portal"
    assert recipe["client_specific_portal_requirements"]["portal_submission_action_allowed"] is False
    assert recipe["client_specific_portal_requirements"]["portal_submission_is_payment_trigger"] is True
    assert recipe["client_specific_invoice_artifact_requirements"]["excel_invoice_required_for_annette_records"] is True
    assert recipe["client_specific_invoice_artifact_requirements"]["cc_candidates"] == ("Chyna", "Will")


def test_st_annes_placeholder_does_not_inherit_coupa_or_po_by_default():
    recipe = framework.recipes_by_client_ref()["st_annes"]

    assert not framework.recipe_selects_rail(recipe, framework.SUPPLIER_PORTAL_RAIL)
    assert not framework.recipe_selects_rail(recipe, framework.PURCHASE_ORDER_RAIL)
    assert recipe["client_specific_portal_requirements"]["supplier_portal_required"] is False
    assert recipe["client_specific_portal_requirements"]["supplier_portal_provider"] is None
    assert recipe["client_specific_portal_requirements"]["purchase_order_required"] is False


def test_live_arts_md_placeholder_does_not_inherit_coupa_or_po_by_default():
    recipe = framework.recipes_by_client_ref()["live_arts_md"]

    assert not framework.recipe_selects_rail(recipe, framework.SUPPLIER_PORTAL_RAIL)
    assert not framework.recipe_selects_rail(recipe, framework.PURCHASE_ORDER_RAIL)
    assert recipe["client_specific_portal_requirements"]["supplier_portal_required"] is False
    assert recipe["client_specific_portal_requirements"]["supplier_portal_provider"] is None


def test_recipe_can_require_po_only_when_selected():
    recipes = framework.recipes_by_client_ref()

    assert framework.recipe_requires_rail(recipes["capital_hilton"], framework.PURCHASE_ORDER_RAIL)
    assert not framework.recipe_selects_rail(recipes["st_annes"], framework.PURCHASE_ORDER_RAIL)
    assert not framework.recipe_selects_rail(recipes["live_arts_md"], framework.PURCHASE_ORDER_RAIL)


def test_recipe_can_require_portal_submission_only_when_selected():
    capital = framework.evaluate_recipe(
        "capital_hilton",
        _receipt_set("capital_hilton", omit=("portal_invoice_submission_receipt",)),
    )
    st_annes = framework.evaluate_recipe("st_annes", _receipt_set("st_annes"))

    assert capital["success_layers"]["portal_submitted"]["required_for_recipe"] is True
    assert capital["success_layers"]["portal_submitted"]["complete"] is False
    assert st_annes["success_layers"]["portal_submitted"]["required_for_recipe"] is False
    assert st_annes["success_layers"]["portal_submitted"]["complete"] is False
    assert st_annes["workflow_complete"] is True


def test_recipe_dependencies_are_acyclic():
    def visit(recipe, rail_ref, visiting, visited):
        assert rail_ref not in visiting, f"cycle detected at {rail_ref}"
        if rail_ref in visited:
            return
        visiting.add(rail_ref)
        for dep in recipe["rail_dependencies"].get(rail_ref, ()):
            visit(recipe, dep, visiting, visited)
        visiting.remove(rail_ref)
        visited.add(rail_ref)

    for recipe in framework.build_client_invoice_recipes():
        visited = set()
        for rail_ref in recipe["rail_order"]:
            visit(recipe, rail_ref, set(), visited)


def test_clara_email_rail_cannot_mark_sent_without_send_receipt():
    receipts = _receipt_set("capital_hilton", omit=("email_send_receipt",))
    result = framework.evaluate_recipe("capital_hilton", receipts)
    clara = next(item for item in result["rail_evaluations"] if item["rail_ref"] == framework.CLARA_EMAIL_DRAFT_RAIL)
    send = next(item for item in result["rail_evaluations"] if item["rail_ref"] == framework.EXTERNAL_SEND_RAIL)

    assert clara["complete"] is True
    assert send["complete"] is False
    assert result["success_layers"]["client_email_sent"]["complete"] is False
    assert result["workflow_complete"] is False


def test_coupa_rail_cannot_mark_submitted_without_portal_submission_receipt():
    result = framework.evaluate_recipe(
        "capital_hilton",
        _receipt_set("capital_hilton", omit=("portal_invoice_submission_receipt",)),
    )
    coupa = next(item for item in result["rail_evaluations"] if item["rail_ref"] == framework.SUPPLIER_PORTAL_RAIL)

    assert coupa["complete"] is False
    assert "portal_invoice_submission_receipt" in coupa["missing_receipts"]
    assert result["success_layers"]["portal_submitted"]["complete"] is False


def test_guardian_approval_receipt_does_not_equal_execution_receipt():
    result = framework.evaluate_recipe(
        "capital_hilton",
        {
            "guardian_approval_receipt",
            "operator_approval_receipt",
            "clara_email_draft_receipt",
            "invoice_attachment_proof_receipt",
        },
    )

    assert result["success_layers"]["client_email_sent"]["complete"] is False
    assert framework.EXTERNAL_SEND_RAIL in result["missing_required_rails"]
    assert "Guardian approval is not execution." in framework.RECEIPT_RULES


def test_payment_detection_does_not_equal_ledger_posting():
    result = framework.evaluate_recipe(
        "capital_hilton",
        _receipt_set("capital_hilton", omit=("ledger_handoff_ready_receipt", "tax_evidence_ready_receipt")),
    )

    assert result["success_layers"]["payment_detected"]["complete"] is True
    assert result["success_layers"]["ledger_ready"]["complete"] is False
    assert result["success_layers"]["tax_evidence_ready"]["complete"] is False
    assert "Payment detected is not ledger-posted." in framework.RECEIPT_RULES


def test_capital_hilton_workflow_is_not_complete_until_all_required_selected_rails_complete():
    incomplete = framework.evaluate_recipe(
        "capital_hilton",
        _receipt_set("capital_hilton", omit=("purchase_order_confirmed_receipt",)),
    )
    complete = framework.evaluate_recipe("capital_hilton", _receipt_set("capital_hilton"))

    assert incomplete["workflow_complete"] is False
    assert framework.PURCHASE_ORDER_RAIL in incomplete["missing_required_rails"]
    assert complete["workflow_complete"] is True
    assert complete["success_layers"]["portal_submitted"]["complete"] is True
    assert complete["success_layers"]["client_email_sent"]["complete"] is True


def test_non_coupa_client_workflow_can_complete_without_coupa_rails():
    for client_ref in ("st_annes", "live_arts_md"):
        result = framework.evaluate_recipe(client_ref, _receipt_set(client_ref))

        assert result["workflow_complete"] is True
        assert result["success_layers"]["portal_submitted"]["required_for_recipe"] is False
        assert all(item["rail_ref"] != framework.SUPPLIER_PORTAL_RAIL for item in result["rail_evaluations"])


def test_no_action_authority_is_enabled():
    payload = framework.build_payload(generated_at=FIXED_NOW)

    assert payload["machine_proof"]["all_action_authority_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())
    for rail in payload["rails"]:
        assert "send_without_send_receipt" in rail["forbidden_actions"]
        assert "submit_without_submission_receipt" in rail["forbidden_actions"]


def test_export_writes_parseable_readmodel_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / framework.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / framework.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == framework.READ_MODEL_ID
    assert summary["rail_count"] >= 12
    assert payload["machine_proof"]["capital_hilton_has_coupa_recipe"] is True
    assert "Capital Hilton: complex Coupa" in operator
    assert "A draft is not sent." in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = framework.build_payload(generated_at=FIXED_NOW)
    framework.write_exports(payload, tmp_path)
    combined = (tmp_path / framework.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / framework.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    for forbidden in ("password", "api_key", "secret", "raw email body", "spreadsheet cell"):
        assert forbidden not in lowered
