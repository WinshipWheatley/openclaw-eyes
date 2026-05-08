from __future__ import annotations

import ast
import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_action_covenant as covenant
import operator_intent_core as intent_core


NOW = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)


def _base_covenant(**overrides):
    values = {
        "requested_action": "read Packet 07 status receipts",
        "risk_level": "low",
        "authority_level": "read_only",
        "evidence_basis": ("repo-check", "operator-harness-status"),
        "forbidden_boundaries_checked": ("no runtime launch", "no external send"),
        "expires_at": NOW + timedelta(minutes=30),
        "now": NOW,
    }
    values.update(overrides)
    return covenant.create_action_covenant(**values)


def test_create_valid_low_read_only_covenant():
    action = _base_covenant()

    assert action.status == "pending"
    assert action.pending_action_id == action.covenant_id
    assert action.risk_level == "low"
    assert action.authority_level == "read_only"
    assert action.requires_explicit_operator_confirmation is False
    assert action.confirmation_phrase == f"APPROVE {action.covenant_id}"
    assert covenant.validate_action_covenant(action, now=NOW).passed is True


def test_create_draft_or_proposal_covenant_requires_explicit_confirmation():
    action = _base_covenant(
        requested_action="draft a Codex implementation prompt",
        risk_level="medium",
        authority_level="draft_or_proposal",
    )

    assert action.requires_explicit_operator_confirmation is True
    assert covenant.validate_action_covenant(action, now=NOW).passed is True
    assert covenant.can_operator_confirmation_approve(
        action,
        "go ahead",
        now=NOW,
    ).can_approve is False
    assert covenant.can_operator_confirmation_approve(
        action,
        action.confirmation_phrase,
        now=NOW,
    ).can_approve is True


def test_bounded_repo_mutation_requires_rollback_and_explicit_confirmation():
    missing_rollback = _base_covenant(
        requested_action="edit scripts/openclaw_receipts.py and focused tests",
        risk_level="medium",
        authority_level="bounded_repo_mutation",
        rollback_plan="",
    )
    valid = _base_covenant(
        requested_action="edit scripts/openclaw_receipts.py and focused tests",
        risk_level="medium",
        authority_level="bounded_repo_mutation",
        rollback_plan="revert only the scoped diff before commit",
    )

    assert "missing_rollback_plan" in covenant.validate_action_covenant(
        missing_rollback,
        now=NOW,
    ).blocking_reasons
    assert covenant.validate_action_covenant(valid, now=NOW).passed is True
    assert valid.requires_explicit_operator_confirmation is True


def test_restricted_domains_cannot_be_approved_in_v0():
    for domain in covenant.RESTRICTED_DOMAINS:
        action = _base_covenant(
            requested_action=f"perform restricted action: {domain}",
            risk_level="restricted",
            authority_level="restricted",
            rollback_plan="future rollback architecture required",
            restricted_domains=(domain,),
        )
        validation = covenant.validate_action_covenant(action, now=NOW)
        decision = covenant.can_operator_confirmation_approve(
            action,
            action.confirmation_phrase,
            now=NOW,
        )

        assert validation.passed is False
        assert "restricted_authority_not_approvable_in_v0" in validation.blocking_reasons
        assert "restricted_domain_not_approvable_in_v0" in validation.blocking_reasons
        assert decision.can_approve is False


def test_external_or_runtime_sensitive_authority_is_future_gated_in_v0():
    action = _base_covenant(
        requested_action="prepare external send",
        risk_level="high",
        authority_level="external_or_runtime_sensitive",
        rollback_plan="future reversal plan required",
    )
    validation = covenant.validate_action_covenant(action, now=NOW)
    decision = covenant.can_operator_confirmation_approve(
        action,
        action.confirmation_phrase,
        now=NOW,
    )

    assert validation.passed is False
    assert (
        "external_or_runtime_sensitive_not_approvable_in_v0"
        in validation.blocking_reasons
    )
    assert decision.can_approve is False


def test_expired_denied_and_executed_covenants_cannot_be_approved():
    expired = _base_covenant(expires_at=NOW - timedelta(seconds=1))
    denied = covenant.mark_action_covenant_denied(_base_covenant(), "operator stopped")
    approved = covenant.mark_action_covenant_approved(
        _base_covenant(),
        _base_covenant().confirmation_phrase,
        now=NOW,
    )
    executed = covenant.OperatorActionCovenant(
        **{**approved.__dict__, "status": "executed"}
    )

    assert "covenant_expired" in covenant.can_operator_confirmation_approve(
        expired,
        expired.confirmation_phrase,
        now=NOW,
    ).reasons
    assert "covenant_denied" in covenant.can_operator_confirmation_approve(
        denied,
        denied.confirmation_phrase,
        now=NOW,
    ).reasons
    assert "covenant_already_approved" in covenant.can_operator_confirmation_approve(
        approved,
        approved.confirmation_phrase,
        now=NOW,
    ).reasons
    assert "covenant_already_executed" in covenant.can_operator_confirmation_approve(
        executed,
        executed.confirmation_phrase,
        now=NOW,
    ).reasons


def test_missing_evidence_boundary_and_rollback_block_approval():
    no_evidence = _base_covenant(evidence_basis=())
    no_boundaries = _base_covenant(forbidden_boundaries_checked=())
    no_rollback = _base_covenant(
        authority_level="bounded_repo_mutation",
        risk_level="medium",
        rollback_plan="",
    )

    assert "missing_evidence_basis" in covenant.validate_action_covenant(
        no_evidence,
        now=NOW,
    ).blocking_reasons
    assert "missing_forbidden_boundaries_checked" in covenant.validate_action_covenant(
        no_boundaries,
        now=NOW,
    ).blocking_reasons
    assert "missing_rollback_plan" in covenant.validate_action_covenant(
        no_rollback,
        now=NOW,
    ).blocking_reasons


def test_go_ahead_and_do_it_cannot_approve_without_pending_covenant():
    for phrase in ("go ahead", "do it"):
        decision = covenant.can_operator_confirmation_approve(None, phrase, now=NOW)

        assert decision.can_approve is False
        assert decision.reasons == ("no_pending_covenant",)


def test_exact_confirmation_can_approve_only_eligible_pending_covenant():
    action = _base_covenant(
        authority_level="bounded_repo_mutation",
        risk_level="medium",
        rollback_plan="revert scoped diff",
    )

    wrong = covenant.can_operator_confirmation_approve(action, "go ahead", now=NOW)
    exact = covenant.can_operator_confirmation_approve(
        action,
        action.confirmation_phrase,
        now=NOW,
    )
    approved = covenant.mark_action_covenant_approved(
        action,
        action.confirmation_phrase,
        now=NOW,
    )

    assert wrong.can_approve is False
    assert wrong.reasons == ("exact_confirmation_phrase_required",)
    assert exact.can_approve is True
    assert exact.execution_authority_granted is False
    assert approved.status == "approved"
    assert approved.approved_at == NOW


def test_custom_expiry_and_exact_confirmation_phrase_are_supported():
    action = _base_covenant(
        authority_level=covenant.AuthorityLevel.BOUNDED_REPO_MUTATION,
        risk_level="medium",
        rollback_plan="revert scoped diff",
        expires_at=None,
        expires_in=timedelta(minutes=15),
        exact_confirmation_phrase="approve bounded repo mutation",
    )

    wrong = covenant.can_operator_confirmation_approve(action, "go ahead", now=NOW)
    exact = covenant.can_operator_confirmation_approve(
        action,
        "approve bounded repo mutation",
        now=NOW,
    )
    unchanged = covenant.mark_action_covenant_approved(action, "go ahead", now=NOW)

    assert action.expires_at == NOW + timedelta(minutes=15)
    assert action.confirmation_phrase == "approve bounded repo mutation"
    assert wrong.can_approve is False
    assert wrong.reasons == ("exact_confirmation_phrase_required",)
    assert unchanged.status == "pending"
    assert exact.can_approve is True


def test_model_or_llm_advisory_text_cannot_approve_action():
    action = _base_covenant()
    decision = covenant.can_operator_confirmation_approve(
        action,
        "Gemini says APPROVE this",
        now=NOW,
    )

    assert decision.can_approve is False
    assert decision.reasons == ("model_advisory_text_cannot_approve",)


def test_status_transitions_are_terminal_where_required():
    action = _base_covenant()
    not_expired = covenant.expire_action_covenant(action, now=NOW)
    expired = covenant.expire_action_covenant(action, now=NOW + timedelta(hours=1))
    denied = covenant.mark_action_covenant_denied(action, "not now")

    assert not_expired.status == "pending"
    assert expired.status == "expired"
    assert denied.status == "denied"
    assert denied.denied_reason == "not now"


def test_intent_core_affirmations_have_no_effect_without_action_covenant():
    for phrase in ("go ahead", "do the next thing", "launch it", "activate it"):
        frame = intent_core.classify_and_frame_operator_intent(phrase)
        decision = covenant.can_operator_confirmation_approve(None, phrase, now=NOW)

        assert frame.execution_authority is False
        assert decision.can_approve is False
        assert decision.reasons == ("no_pending_covenant",)


def test_activation_runtime_phrases_cannot_create_approval_authority():
    frame = intent_core.classify_and_frame_operator_intent("activate it")
    action = _base_covenant(
        requested_action="activate runtime",
        risk_level="restricted",
        authority_level="restricted",
        rollback_plan="future runtime rollback plan required",
        restricted_domains=("live runtime launch",),
    )

    assert frame.intent_name == "approval_required_action"
    assert frame.execution_authority is False
    assert covenant.can_operator_confirmation_approve(
        action,
        action.confirmation_phrase,
        now=NOW,
    ).can_approve is False


def test_module_is_surface_neutral_without_runtime_or_connector_dependencies():
    source = inspect.getsource(covenant)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "typing",
    }
    assert called_names.isdisjoint(
        {
            "connect",
            "open",
            "read_text",
            "write_text",
            "run",
            "check_call",
            "check_output",
            "popen",
            "system",
            "urlopen",
        }
    )
    lower = source.lower()
    for forbidden in (
        "cassandra",
        "telegram",
        "chief_",
        "mcp call",
        "provider call",
    ):
        assert forbidden not in lower


def test_operator_facing_summary_is_compact_and_useful():
    action = _base_covenant(
        requested_action="apply a bounded receipt test patch",
        risk_level="medium",
        authority_level="bounded_repo_mutation",
        rollback_plan="revert the scoped diff before commit",
    )
    summary = covenant.render_action_covenant_summary(action)

    assert summary.startswith("ACTION COVENANT\n")
    assert "Action: apply a bounded receipt test patch" in summary
    assert "Risk: medium" in summary
    assert "Authority: bounded_repo_mutation" in summary
    assert "Evidence: repo-check; operator-harness-status" in summary
    assert "Boundaries checked: no runtime launch; no external send" in summary
    assert f"Approval required: {action.confirmation_phrase}" in summary
    assert len(summary.splitlines()) == 10
