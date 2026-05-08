"""Surface-neutral Operator Action Covenant v0.

The covenant is a local, deterministic approval object. It describes an action,
the evidence behind it, the checked boundaries, the rollback posture, expiry,
and the exact operator confirmation needed before an eligible action can move.

It executes nothing and grants no restricted-domain authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Sequence


class _CovenantValue(str, Enum):
    def __str__(self) -> str:
        return self.value


class AuthorityLevel(_CovenantValue):
    READ_ONLY = "read_only"
    DRAFT_OR_PROPOSAL = "draft_or_proposal"
    BOUNDED_REPO_MUTATION = "bounded_repo_mutation"
    EXTERNAL_OR_RUNTIME_SENSITIVE = "external_or_runtime_sensitive"
    RESTRICTED = "restricted"


STATUSES = ("pending", "approved", "denied", "expired", "executed")
RISK_LEVELS = ("low", "medium", "high", "restricted")
AUTHORITY_LEVELS = (
    AuthorityLevel.READ_ONLY.value,
    AuthorityLevel.DRAFT_OR_PROPOSAL.value,
    AuthorityLevel.BOUNDED_REPO_MUTATION.value,
    AuthorityLevel.EXTERNAL_OR_RUNTIME_SENSITIVE.value,
    AuthorityLevel.RESTRICTED.value,
)

RESTRICTED_DOMAINS = (
    "live runtime launch",
    "MCP writes/shared memory",
    "provider/model/API calls",
    "invoice generation/reconciliation/sending",
    "legal/private-root/sensitive-data access",
    "external sends",
    "destructive filesystem operations",
    "hidden memory writes",
    "Packet 08 creation",
)

MUTATION_OR_EXECUTION_AUTHORITY_LEVELS = (
    "bounded_repo_mutation",
    "external_or_runtime_sensitive",
    "restricted",
)

EXACT_CONFIRMATION_POLICY = "exact_phrase"
PLAIN_AFFIRMATION_FOR_LOW_READ_ONLY_POLICY = "plain_affirmation_for_low_read_only"
CONFIRMATION_POLICIES = (
    EXACT_CONFIRMATION_POLICY,
    PLAIN_AFFIRMATION_FOR_LOW_READ_ONLY_POLICY,
)

PLAIN_AFFIRMATIONS = ("go ahead", "do it", "yes", "approved", "approve")
MODEL_ADVISORY_MARKERS = (
    "model says",
    "llm says",
    "gemini says",
    "codex says",
    "chatgpt says",
    "assistant says",
    "ai says",
)


@dataclass(frozen=True)
class OperatorActionCovenant:
    covenant_id: str
    pending_action_id: str
    requested_action: str
    risk_level: str
    authority_level: str
    evidence_basis: tuple[str, ...]
    forbidden_boundaries_checked: tuple[str, ...]
    rollback_plan: str
    expires_at: datetime
    requires_explicit_operator_confirmation: bool
    status: str
    confirmation_phrase: str
    restricted_domains: tuple[str, ...] = ()
    confirmation_policy: str = EXACT_CONFIRMATION_POLICY
    created_at: datetime | None = None
    approved_at: datetime | None = None
    denied_reason: str = ""


@dataclass(frozen=True)
class CovenantValidation:
    passed: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CovenantApprovalDecision:
    can_approve: bool
    reasons: tuple[str, ...]
    required_confirmation: str
    execution_authority_granted: bool = False


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _as_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value).strip()
    return str(value).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_expired(covenant: OperatorActionCovenant, now: datetime | None = None) -> bool:
    current = (now or _utc_now()).astimezone(timezone.utc)
    return current >= covenant.expires_at


def _stable_covenant_id(
    *,
    requested_action: str,
    risk_level: str,
    authority_level: str,
    evidence_basis: tuple[str, ...],
    forbidden_boundaries_checked: tuple[str, ...],
    expires_at: datetime,
) -> str:
    seed = "\n".join(
        (
            requested_action.strip(),
            risk_level,
            authority_level,
            "|".join(evidence_basis),
            "|".join(forbidden_boundaries_checked),
            expires_at.isoformat(),
        )
    )
    return "cov_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _confirmation_phrase(covenant_id: str) -> str:
    return f"APPROVE {covenant_id}"


def create_action_covenant(
    *,
    requested_action: str,
    risk_level: str,
    authority_level: str,
    evidence_basis: Sequence[str],
    forbidden_boundaries_checked: Sequence[str],
    rollback_plan: str = "",
    expires_at: datetime | str | None = None,
    expires_in: timedelta | None = None,
    requires_explicit_operator_confirmation: bool | None = None,
    restricted_domains: Sequence[str] | None = None,
    covenant_id: str | None = None,
    pending_action_id: str | None = None,
    exact_confirmation_phrase: str | None = None,
    confirmation_policy: str = EXACT_CONFIRMATION_POLICY,
    now: datetime | None = None,
) -> OperatorActionCovenant:
    """Create a local covenant object without persisting or executing anything."""
    current = (now or _utc_now()).astimezone(timezone.utc)
    risk = _as_value(risk_level)
    authority = _as_value(authority_level)
    if expires_at is not None:
        expiry = _coerce_datetime(expires_at)
    elif expires_in is not None:
        expiry = current + expires_in
    else:
        expiry = current + timedelta(hours=1)
    evidence = _as_tuple(evidence_basis)
    boundaries = _as_tuple(forbidden_boundaries_checked)
    restricted = _as_tuple(restricted_domains)
    action_id = covenant_id or _stable_covenant_id(
        requested_action=requested_action,
        risk_level=risk,
        authority_level=authority,
        evidence_basis=evidence,
        forbidden_boundaries_checked=boundaries,
        expires_at=expiry,
    )
    explicit_confirmation = (
        requires_explicit_operator_confirmation
        if requires_explicit_operator_confirmation is not None
        else authority != AuthorityLevel.READ_ONLY.value
    )

    return OperatorActionCovenant(
        covenant_id=action_id,
        pending_action_id=pending_action_id or action_id,
        requested_action=requested_action.strip(),
        risk_level=risk,
        authority_level=authority,
        evidence_basis=evidence,
        forbidden_boundaries_checked=boundaries,
        rollback_plan=rollback_plan.strip(),
        expires_at=expiry,
        requires_explicit_operator_confirmation=bool(explicit_confirmation),
        status="pending",
        confirmation_phrase=(exact_confirmation_phrase or _confirmation_phrase(action_id)).strip(),
        restricted_domains=restricted,
        confirmation_policy=confirmation_policy,
        created_at=current,
    )


def validate_action_covenant(
    covenant: OperatorActionCovenant,
    *,
    now: datetime | None = None,
) -> CovenantValidation:
    """Validate the covenant shape and v0 approval eligibility."""
    reasons: list[str] = []
    warnings: list[str] = []

    if covenant.status not in STATUSES:
        reasons.append("unknown_status")
    if covenant.risk_level not in RISK_LEVELS:
        reasons.append("unknown_risk_level")
    if covenant.authority_level not in AUTHORITY_LEVELS:
        reasons.append("unknown_authority_level")
    if covenant.confirmation_policy not in CONFIRMATION_POLICIES:
        reasons.append("unknown_confirmation_policy")
    if not covenant.requested_action:
        reasons.append("missing_requested_action")
    if not covenant.evidence_basis:
        reasons.append("missing_evidence_basis")
    if not covenant.forbidden_boundaries_checked:
        reasons.append("missing_forbidden_boundaries_checked")
    if covenant.authority_level in MUTATION_OR_EXECUTION_AUTHORITY_LEVELS and not covenant.rollback_plan:
        reasons.append("missing_rollback_plan")
    if (
        covenant.authority_level != "read_only"
        and covenant.requires_explicit_operator_confirmation is not True
    ):
        reasons.append("explicit_operator_confirmation_required_above_read_only")
    if covenant.risk_level == "restricted" or covenant.authority_level == "restricted":
        reasons.append("restricted_authority_not_approvable_in_v0")
    if covenant.authority_level == "external_or_runtime_sensitive":
        reasons.append("external_or_runtime_sensitive_not_approvable_in_v0")
    if covenant.restricted_domains:
        reasons.append("restricted_domain_not_approvable_in_v0")
    if any(domain not in RESTRICTED_DOMAINS for domain in covenant.restricted_domains):
        reasons.append("unknown_restricted_domain")
    if covenant.status == "expired" or _is_expired(covenant, now=now):
        reasons.append("covenant_expired")
    if covenant.status == "approved":
        reasons.append("covenant_already_approved")
    if covenant.status == "denied":
        reasons.append("covenant_denied")
    if covenant.status == "executed":
        reasons.append("covenant_already_executed")
    if not covenant.confirmation_phrase:
        reasons.append("missing_exact_confirmation_phrase")

    return CovenantValidation(
        passed=not reasons,
        blocking_reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(warnings),
    )


def can_operator_confirmation_approve(
    covenant: OperatorActionCovenant | None = None,
    confirmation_text: str | None = None,
    *,
    now: datetime | None = None,
) -> CovenantApprovalDecision:
    """Return whether operator text can approve this pending covenant."""
    if covenant is None:
        return CovenantApprovalDecision(
            can_approve=False,
            reasons=("no_pending_covenant",),
            required_confirmation="",
        )

    validation = validate_action_covenant(covenant, now=now)
    if not validation.passed:
        return CovenantApprovalDecision(
            can_approve=False,
            reasons=validation.blocking_reasons,
            required_confirmation=covenant.confirmation_phrase,
        )

    normalized = " ".join(str(confirmation_text or "").strip().split())
    lowered = normalized.lower()
    if any(marker in lowered for marker in MODEL_ADVISORY_MARKERS):
        return CovenantApprovalDecision(
            can_approve=False,
            reasons=("model_advisory_text_cannot_approve",),
            required_confirmation=covenant.confirmation_phrase,
        )

    if covenant.requires_explicit_operator_confirmation:
        if normalized != covenant.confirmation_phrase:
            return CovenantApprovalDecision(
                can_approve=False,
                reasons=("exact_confirmation_phrase_required",),
                required_confirmation=covenant.confirmation_phrase,
            )
        return CovenantApprovalDecision(
            can_approve=True,
            reasons=(),
            required_confirmation=covenant.confirmation_phrase,
        )

    if covenant.confirmation_policy == PLAIN_AFFIRMATION_FOR_LOW_READ_ONLY_POLICY:
        if (
            covenant.risk_level == "low"
            and covenant.authority_level == "read_only"
            and lowered in PLAIN_AFFIRMATIONS
        ):
            return CovenantApprovalDecision(
                can_approve=True,
                reasons=(),
                required_confirmation=covenant.confirmation_phrase,
            )

    if normalized == covenant.confirmation_phrase:
        return CovenantApprovalDecision(
            can_approve=True,
            reasons=(),
            required_confirmation=covenant.confirmation_phrase,
        )

    return CovenantApprovalDecision(
        can_approve=False,
        reasons=("confirmation_not_accepted",),
        required_confirmation=covenant.confirmation_phrase,
    )


def expire_action_covenant(
    covenant: OperatorActionCovenant,
    *,
    now: datetime | None = None,
) -> OperatorActionCovenant:
    """Return an expired covenant when its expiry has elapsed."""
    if covenant.status != "pending":
        return covenant
    if _is_expired(covenant, now=now):
        return replace(covenant, status="expired")
    return covenant


def mark_action_covenant_denied(
    covenant: OperatorActionCovenant,
    reason: str,
) -> OperatorActionCovenant:
    """Return a denied covenant. Denial is terminal for v0."""
    return replace(covenant, status="denied", denied_reason=reason.strip())


def mark_action_covenant_approved(
    covenant: OperatorActionCovenant,
    confirmation_text: str,
    *,
    now: datetime | None = None,
) -> OperatorActionCovenant:
    """Return an approved covenant only when validation and confirmation pass."""
    decision = can_operator_confirmation_approve(
        covenant,
        confirmation_text,
        now=now,
    )
    if not decision.can_approve:
        return covenant
    return replace(
        covenant,
        status="approved",
        approved_at=(now or _utc_now()).astimezone(timezone.utc),
    )


def render_action_covenant_summary(covenant: OperatorActionCovenant) -> str:
    """Render a compact operator-facing covenant summary."""
    evidence = "; ".join(covenant.evidence_basis) or "missing"
    boundaries = "; ".join(covenant.forbidden_boundaries_checked) or "missing"
    rollback = covenant.rollback_plan or "not required for read-only action"
    restricted = "; ".join(covenant.restricted_domains) or "none"
    return "\n".join(
        (
            "ACTION COVENANT",
            f"Action: {covenant.requested_action}",
            f"Risk: {covenant.risk_level}",
            f"Authority: {covenant.authority_level}",
            f"Evidence: {evidence}",
            f"Boundaries checked: {boundaries}",
            f"Rollback: {rollback}",
            f"Restricted domains: {restricted}",
            f"Expires: {covenant.expires_at.isoformat()}",
            f"Approval required: {covenant.confirmation_phrase}",
        )
    )
