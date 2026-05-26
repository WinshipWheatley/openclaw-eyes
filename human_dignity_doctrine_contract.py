"""Human Dignity Doctrine Contract v0.

This deterministic read-model translates human dignity, common good, and
anti-domination principles into operational OpenClaw governance constraints.
It is doctrine/read-model only. It does not enforce live policy, run workflows,
dispatch agents, perform surveillance, change pricing or labor decisions,
handle credentials, ingest raw bodies, mutate Mission Control Swift, use the
network, or perform external action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "human_dignity_doctrine_contract_v0"
READ_MODEL_ID = "human_dignity_doctrine_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_HUMAN_DIGNITY_GOVERNANCE_RAIL_NO_EXECUTION"

PRINCIPLE_IDS = (
    "HUMAN_DIGNITY",
    "COMMON_GOOD",
    "SUBSIDIARITY",
    "SOCIAL_JUSTICE",
    "UNIVERSAL_DESTINATION_OF_GOODS",
    "PREFERENTIAL_PROTECTION_OF_VULNERABLE",
    "JUST_WORK_AND_FAIR_WAGES",
    "ANTI_TECHNOCRATIC_DOMINATION",
    "HUMAN_LIMITS_AND_CARE",
    "ACCOUNTABLE_AI_AUTHORITY",
)

DECISION_TYPES = (
    "AUTOMATION",
    "WORKER_REPLACEMENT",
    "CLIENT_COMMUNICATION",
    "FINANCIAL_ACTION",
    "DATA_EXTRACTION",
    "SURVEILLANCE_OR_MONITORING",
    "MODEL_PROVIDER_SELECTION",
    "PRODUCTIZATION",
    "PRICING_OR_ACCESS",
    "UNKNOWN_FAIL_CLOSED",
)

PROHIBITED_PATTERN_IDS = (
    "PEOPLE_AS_METRICS_ONLY",
    "HIDDEN_SURVEILLANCE",
    "AUTHORITY_WITHOUT_APPEAL",
    "AUTOMATION_WITHOUT_CONSENT",
    "PROFIT_ONLY_OPTIMIZATION",
    "CONCENTRATED_POWER_WITHOUT_ACCOUNTABILITY",
    "LABOR_ERASURE",
    "VULNERABLE_PARTY_INVISIBILITY",
    "FAKE_MORALITY_BY_ELITE_COMMITTEE",
    "TRANSHUMANIST_DISMISSAL_OF_LIMITS",
)

REQUIRED_DESIGN_PATTERN_IDS = (
    "HUMAN_REVIEW_GATE",
    "RECEIPT_BACKED_AUTHORITY",
    "LOCAL_FIRST_WHEN_SENSITIVE",
    "OPERATOR_CONSENT",
    "EXPLAINABLE_NEXT_SAFE_MOVE",
    "APPEAL_OR_REVERSAL_PATH",
    "POWER_CONCENTRATION_WARNING",
    "FAIR_ACCESS_AND_PORTABILITY",
    "VULNERABLE_PARTY_CHECK",
    "LABOR_IMPACT_CHECK",
)

AGENT_ROLES = ("Chief", "Cassandra", "Guardian", "Niles", "Codex", "OpenClaw System")

AUTHORITY_BOUNDARY = {
    "live_policy_enforcement_mutation_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_external_action_allowed": False,
    "live_surveillance_allowed": False,
    "live_pricing_change_allowed": False,
    "live_labor_decision_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_secret_reveal_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class HumanDignityDoctrineContract:
    contract_id: str
    doctrine: tuple[str, ...]
    source_inspiration: tuple[str, ...]
    operational_principles: tuple[str, ...]
    decision_policy: tuple[str, ...]
    prohibited_system_patterns: tuple[str, ...]
    required_design_patterns: tuple[str, ...]
    agent_behavior_policy: tuple[str, ...]
    automation_policy: tuple[str, ...]
    labor_and_prosperity_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OperationalPrinciple:
    principle_id: str
    name: str
    plain_definition: str
    openclaw_translation: str
    required_behavior: str
    forbidden_behavior: str
    example: str
    next_safe_move: str


@dataclass(frozen=True)
class HumanDignityDecisionCheck:
    check_id: str
    decision_type: str
    affected_people: tuple[str, ...]
    dignity_risk: str
    common_good_risk: str
    power_concentration_risk: str
    vulnerable_party_risk: str
    labor_impact_risk: str
    human_review_required: bool
    blocked_until: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ProhibitedSystemPattern:
    pattern_id: str
    pattern_name: str
    description: str
    why_blocked: str
    detection_hint: str
    elioperator_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class RequiredDesignPattern:
    pattern_id: str
    pattern_name: str
    description: str
    where_it_applies: tuple[str, ...]
    required_output: str
    test_hint: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentDoctrineApplication:
    agent_role: str
    dignity_obligation: str
    common_good_obligation: str
    forbidden_agent_behavior: str
    required_agent_behavior: str
    example_good: str
    example_bad: str
    next_safe_move: str


@dataclass(frozen=True)
class HumanDignityReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    doctrine_summary: tuple[str, ...]
    design_implications: tuple[str, ...]
    blocked_patterns: tuple[str, ...]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, tuple[str, ...]]:
    return {
        "HumanDignityDoctrineContract": tuple(field.name for field in fields(HumanDignityDoctrineContract)),
        "OperationalPrinciple": tuple(field.name for field in fields(OperationalPrinciple)),
        "HumanDignityDecisionCheck": tuple(field.name for field in fields(HumanDignityDecisionCheck)),
        "ProhibitedSystemPattern": tuple(field.name for field in fields(ProhibitedSystemPattern)),
        "RequiredDesignPattern": tuple(field.name for field in fields(RequiredDesignPattern)),
        "AgentDoctrineApplication": tuple(field.name for field in fields(AgentDoctrineApplication)),
        "HumanDignityReadback": tuple(field.name for field in fields(HumanDignityReadback)),
    }


def build_operational_principles() -> tuple[OperationalPrinciple, ...]:
    data = {
        "HUMAN_DIGNITY": (
            "Human Dignity",
            "Every person has worth that cannot be reduced to productivity, compliance, data value, or automation potential.",
            "OpenClaw treats people as persons first, not targets, metrics, or replaceable units.",
            "Name affected people, consent needs, and consequences before consequential action.",
            "Do not optimize away a person, relationship, livelihood, or appeal path for speed.",
            "A client contact is a relationship context, not just an outbound message endpoint.",
        ),
        "COMMON_GOOD": (
            "Common Good",
            "Systems should increase shared flourishing, not only private extraction or narrow operator advantage.",
            "OpenClaw surfaces who benefits, who bears risk, and whether a rail creates durable broad usefulness.",
            "Prefer reusable rails that help small operators and communities without weakening privacy.",
            "Do not route work solely toward capture, lock-in, or winner-take-all control.",
            "A workflow package should make human work clearer and safer, not just faster.",
        ),
        "SUBSIDIARITY": (
            "Subsidiarity",
            "Decisions should stay with the most local competent human level unless escalation is justified.",
            "OpenClaw keeps operator judgment close to the action and escalates only when risk or authority requires it.",
            "Use human review gates and local-first handling for sensitive contexts.",
            "Do not let remote systems or generalized models silently overrule local judgment.",
            "A client financial send remains gated by explicit local approval even if an adapter exists.",
        ),
        "SOCIAL_JUSTICE": (
            "Social Justice",
            "Institutions should be arranged so people can participate fairly and are not made disposable.",
            "OpenClaw checks whether automation, pricing, and access patterns exclude smaller or vulnerable parties.",
            "Surface access, fairness, appeal, and burden-shift risks.",
            "Do not hide harms under neutral labels like efficiency or optimization.",
            "A product lane must consider who is priced out and who loses agency.",
        ),
        "UNIVERSAL_DESTINATION_OF_GOODS": (
            "Universal Destination Of Goods",
            "Created value should not be captured only by a few when broader benefit is possible and safe.",
            "OpenClaw favors portability, reusable patterns, and opt-in commons where privacy and consent allow.",
            "Preserve paths for fair reuse without exposing private data or taking operator control.",
            "Do not turn shared knowledge into unjust lock-in or extractive dependency.",
            "A safe reusable guardrail may become a shared pattern while client records stay private.",
        ),
        "PREFERENTIAL_PROTECTION_OF_VULNERABLE": (
            "Preferential Protection Of Vulnerable",
            "The system must pay special attention to people who are easy to ignore, pressure, or harm.",
            "OpenClaw adds vulnerable-party checks for financial, labor, surveillance, data, and client-facing decisions.",
            "Make harm to vulnerable parties visible before action.",
            "Do not treat silence, weak bargaining power, or low visibility as consent.",
            "A small vendor or worker should not be erased because a faster automated route exists.",
        ),
        "JUST_WORK_AND_FAIR_WAGES": (
            "Just Work And Fair Wages",
            "Work and livelihood are part of human dignity, not only cost centers.",
            "OpenClaw requires labor-impact checks before worker replacement or productivity-pressure decisions.",
            "Surface livelihood, wage, deskilling, and human-care impacts.",
            "Do not recommend replacing people purely because it is technically possible or cheaper.",
            "A worker replacement proposal must include human review and fair transition analysis.",
        ),
        "ANTI_TECHNOCRATIC_DOMINATION": (
            "Anti Technocratic Domination",
            "Technical systems must not become unaccountable rule over human life.",
            "OpenClaw exposes proof, authority, blockers, and consequences instead of hiding control behind automation.",
            "Keep decisions inspectable, appealable, and bounded by receipts.",
            "Do not present machine output as final authority over human judgment.",
            "A model route can recommend, but cannot silently authorize a send, submit, or labor decision.",
        ),
        "HUMAN_LIMITS_AND_CARE": (
            "Human Limits And Care",
            "Human limits, rest, grief, creativity, attention, and embodiment matter.",
            "OpenClaw avoids pressure systems that treat exhaustion as a throughput problem.",
            "Use humane pacing, reversible rails, and care-aware next steps.",
            "Do not shame the operator or creative worker for needing context, rest, or slower judgment.",
            "A creative rail should support flow without turning art into output metrics.",
        ),
        "ACCOUNTABLE_AI_AUTHORITY": (
            "Accountable AI Authority",
            "AI authority must be explicit, bounded, inspectable, and subordinate to human judgment.",
            "OpenClaw requires authority flags, proof refs, receipts, and appeal or reversal paths for consequential actions.",
            "Fail closed when authority, proof, consent, or affected-party impact is missing.",
            "Do not imply approval, completion, dispatch, or external action without receipts.",
            "A blocked invoice send must say what proof is missing and how to fix it.",
        ),
    }
    return tuple(
        OperationalPrinciple(
            principle_id=principle_id,
            name=values[0],
            plain_definition=values[1],
            openclaw_translation=values[2],
            required_behavior=values[3],
            forbidden_behavior=values[4],
            example=values[5],
            next_safe_move="Apply this principle as an operational check before consequential automation or response shaping.",
        )
        for principle_id, values in data.items()
    )


def build_prohibited_patterns() -> tuple[ProhibitedSystemPattern, ...]:
    data = {
        "PEOPLE_AS_METRICS_ONLY": ("People As Metrics Only", "The system treats people only as throughput, cost, conversion, or compliance units.", "It erases human dignity and consequences.", "Look for dashboards or decisions with no affected-person, consent, or appeal fields.", "People are being reduced to metrics; add dignity and consequence review."),
        "HIDDEN_SURVEILLANCE": ("Hidden Surveillance", "The system monitors people without clear notice, consent, and purpose limits.", "It turns human context into unaccountable control.", "Look for passive tracking, hidden logs, or opaque monitoring claims.", "Hidden monitoring is blocked; make the purpose, consent, and limits explicit."),
        "AUTHORITY_WITHOUT_APPEAL": ("Authority Without Appeal", "A machine or workflow makes a consequential decision with no human appeal or reversal path.", "It makes machine authority dominate human judgment.", "Look for final decisions without review, receipt, or reversal fields.", "A consequential decision needs a human appeal or reversal path."),
        "AUTOMATION_WITHOUT_CONSENT": ("Automation Without Consent", "Automation acts on people, messages, money, or records without explicit consent or authority.", "It bypasses agency and responsibility.", "Look for send, submit, update, or dispatch paths with missing approval receipts.", "Automation is blocked until consent and authority are explicit."),
        "PROFIT_ONLY_OPTIMIZATION": ("Profit Only Optimization", "The system optimizes only revenue, margin, or capture while ignoring harm and access.", "It subordinates people and the common good to extraction.", "Look for objective functions with no dignity, access, or harm check.", "Profit-only optimization is blocked; add common-good and vulnerable-party checks."),
        "CONCENTRATED_POWER_WITHOUT_ACCOUNTABILITY": ("Concentrated Power Without Accountability", "Control accumulates in a narrow owner, vendor, model, or platform without checks.", "It creates domination risk and dependency.", "Look for lock-in, non-portability, unilateral authority, or hidden provider dependence.", "Surface the power concentration risk and add portability or review."),
        "LABOR_ERASURE": ("Labor Erasure", "Human labor is hidden, devalued, or replaced without fair impact review.", "It treats livelihood as a disposable implementation detail.", "Look for replacement plans with no worker, wage, transition, or care analysis.", "Run a labor-impact check before approving replacement automation."),
        "VULNERABLE_PARTY_INVISIBILITY": ("Vulnerable Party Invisibility", "People with low leverage or high exposure are absent from the decision model.", "It lets harm fall on those least able to object.", "Look for missing vulnerable-party fields in financial, labor, data, or client decisions.", "Add a vulnerable-party check before proceeding."),
        "FAKE_MORALITY_BY_ELITE_COMMITTEE": ("Fake Morality By Elite Committee", "A small opaque group labels itself ethical while affected people lack voice or appeal.", "It replaces accountability with branding.", "Look for ethics claims without transparency, affected-party input, or review.", "Replace branding with inspectable rules, affected-party review, and appeal."),
        "TRANSHUMANIST_DISMISSAL_OF_LIMITS": ("Transhumanist Dismissal Of Limits", "The system treats human limits, dependence, rest, or embodiment as defects to overcome.", "It pressures people into machine-shaped life instead of care-aware work.", "Look for language that frames fatigue, grief, or human pace as mere inefficiency.", "Respect human limits and provide a humane next step."),
    }
    return tuple(
        ProhibitedSystemPattern(
            pattern_id=pattern_id,
            pattern_name=values[0],
            description=values[1],
            why_blocked=values[2],
            detection_hint=values[3],
            elioperator_warning=values[4],
            next_safe_move="Block or redesign this pattern before it reaches a live workflow.",
        )
        for pattern_id, values in data.items()
    )


def build_required_design_patterns() -> tuple[RequiredDesignPattern, ...]:
    data = {
        "HUMAN_REVIEW_GATE": ("Human Review Gate", "Consequential actions pause for human review.", ("automation", "finance", "labor", "client communication", "data extraction"), "A visible review state with affected people, risks, and approval requirements.", "Assert live action remains false until review receipt exists."),
        "RECEIPT_BACKED_AUTHORITY": ("Receipt Backed Authority", "Authority claims require proof receipts.", ("send", "submit", "approve", "complete", "record update"), "Source proof refs and receipts before completion or external action labels.", "Assert no completion claim exists without receipt refs."),
        "LOCAL_FIRST_WHEN_SENSITIVE": ("Local First When Sensitive", "Sensitive data stays local or protected by default.", ("private records", "financial data", "legal/tax data", "protected evidence"), "Local-first handling and cloud/provider blocks unless explicitly gated.", "Assert cloud/external authority false for sensitive fixtures."),
        "OPERATOR_CONSENT": ("Operator Consent", "The operator must explicitly consent to consequential actions.", ("workflow execution", "send/submit", "data extraction", "labor/pricing decisions"), "Consent or approval receipt before action.", "Assert generic yes or vague approval is insufficient."),
        "EXPLAINABLE_NEXT_SAFE_MOVE": ("Explainable Next Safe Move", "Blocked states explain what is missing and how to fix it.", ("all operator readbacks",), "Human-readable next safe move without machine sludge.", "Assert blocked examples include next_safe_move and how-to-fix semantics."),
        "APPEAL_OR_REVERSAL_PATH": ("Appeal Or Reversal Path", "Consequential decisions include a way to review, appeal, or reverse.", ("labor", "pricing", "client communications", "financial actions"), "Appeal/reversal field or blocked state if not available.", "Assert authority-without-appeal pattern is blocked."),
        "POWER_CONCENTRATION_WARNING": ("Power Concentration Warning", "The system flags lock-in, hidden provider dependence, or capture risk.", ("model provider selection", "productization", "pricing", "shared rails"), "Warning when a few parties capture control or benefit.", "Assert productization examples include power concentration risk."),
        "FAIR_ACCESS_AND_PORTABILITY": ("Fair Access And Portability", "Useful rails should avoid unjust lock-in and support fair access where safe.", ("productization", "pricing/access", "commons candidates"), "Portability or fair-access consideration without exposing private data.", "Assert pricing example is not elite-only optimization."),
        "VULNERABLE_PARTY_CHECK": ("Vulnerable Party Check", "The decision names low-power or at-risk parties before action.", ("finance", "labor", "data", "client communication", "surveillance"), "Affected vulnerable-party field and risk disposition.", "Assert vulnerable-party invisibility is blocked."),
        "LABOR_IMPACT_CHECK": ("Labor Impact Check", "Workforce and livelihood impacts are reviewed before replacement or productivity pressure.", ("automation", "worker replacement", "productization"), "Labor impact summary and human review requirement.", "Assert worker replacement is not automatically approved."),
    }
    return tuple(
        RequiredDesignPattern(
            pattern_id=pattern_id,
            pattern_name=values[0],
            description=values[1],
            where_it_applies=values[2],
            required_output=values[3],
            test_hint=values[4],
            next_safe_move="Add this pattern to any rail that touches people, money, work, private data, or external authority.",
        )
        for pattern_id, values in data.items()
    )


def build_decision_checks() -> tuple[HumanDignityDecisionCheck, ...]:
    data = {
        "AUTOMATION": (("operator", "client", "recipient", "affected workers"), "Automation may bypass consent or consequence review.", "Speed may benefit the operator while shifting risk to others.", "Automated control may concentrate in the system owner.", "Low-visibility recipients or workers may be affected without voice.", "Automation may pressure or replace human work.", ("operator consent", "proof receipts", "appeal or reversal path")),
        "WORKER_REPLACEMENT": (("workers", "managers", "clients", "operator"), "People may be treated as replaceable cost centers.", "Savings may be captured by owners while burdens fall on workers.", "Decision power may centralize in automation owners.", "Lower-leverage workers are most exposed.", "High labor-impact risk; fair work and transition review required.", ("labor impact check", "human review", "fair transition or wage analysis")),
        "CLIENT_COMMUNICATION": (("client contact", "operator", "business relationship"), "Communication may treat a person as a target rather than a relationship.", "Automated outreach may damage trust.", "Message authority may hide behind the system.", "Recipients may face pressure without context.", "Low direct labor impact unless used for replacement or pressure.", ("recipient context", "operator approval", "send receipt boundary")),
        "FINANCIAL_ACTION": (("operator", "client", "recipient", "accounting stakeholders"), "Money movement or invoice action can create real obligations.", "Hidden action may damage trust and records.", "Payment authority may centralize in adapters.", "Small vendors or contacts may carry error burden.", "Financial automation may remove responsible human review.", ("proof refs", "approval receipts", "human review gate")),
        "DATA_EXTRACTION": (("data subject", "operator", "client", "tenant"), "Private context may be stripped of consent and meaning.", "Extraction may benefit the system while burdening subjects.", "Centralized extracted data increases control risk.", "People with little bargaining power may lose privacy first.", "Extraction may create monitoring pressure.", ("local-first handling", "consent/protection gate", "raw-body exclusion by default")),
        "SURVEILLANCE_OR_MONITORING": (("monitored people", "operator", "organization"), "Monitoring can dominate behavior and erode trust.", "Safety benefits may be outweighed by hidden control.", "Surveillance power can concentrate sharply.", "Vulnerable parties are least able to resist monitoring.", "Monitoring may intensify labor pressure.", ("explicit purpose", "notice and consent", "appeal/reversal path")),
        "MODEL_PROVIDER_SELECTION": (("operator", "clients", "data subjects", "future users"), "Provider choice may expose data or bias authority.", "Provider capture can weaken broad benefit.", "A few vendors may gain disproportionate control.", "Vulnerable users may be excluded or profiled.", "Provider economics can shift work and value capture.", ("local-first review", "provider risk note", "portability plan")),
        "PRODUCTIZATION": (("operator", "customers", "workers", "small operators"), "A product can encode domination or dignity-preserving defaults.", "Broad usefulness may be sacrificed to capture.", "Ownership and access can concentrate.", "Small operators may be priced or designed out.", "Product may erase human labor or increase pressure.", ("common-good review", "fair access and portability check", "labor impact check")),
        "PRICING_OR_ACCESS": (("customers", "small operators", "vulnerable users", "operator"), "Pricing can decide who is included or excluded.", "Elite-only access can undermine broad benefit.", "Market power can concentrate benefits.", "Low-resource users may be excluded first.", "Pricing can push unfair labor or support burdens.", ("fair access check", "power concentration warning", "operator review")),
        "UNKNOWN_FAIL_CLOSED": (("unknown affected people",), "Unknown decision impact cannot be assumed safe.", "Unknown common-good impact must be inspected.", "Unknown authority concentration must be inspected.", "Unknown vulnerable-party impact must be inspected.", "Unknown labor impact must be inspected.", ("request clarification", "fail closed", "choose bounded readback only")),
    }
    return tuple(
        HumanDignityDecisionCheck(
            check_id=f"human_dignity_decision_check:{decision_type.lower()}",
            decision_type=decision_type,
            affected_people=values[0],
            dignity_risk=values[1],
            common_good_risk=values[2],
            power_concentration_risk=values[3],
            vulnerable_party_risk=values[4],
            labor_impact_risk=values[5],
            human_review_required=True,
            blocked_until=values[6],
            next_safe_move="Run the named human review and proof checks before any live action or final authority claim.",
        )
        for decision_type, values in data.items()
    )


def build_agent_applications() -> tuple[AgentDoctrineApplication, ...]:
    return (
        AgentDoctrineApplication(
            agent_role="Chief",
            dignity_obligation="Surface who is affected, what authority exists, and what remains gated.",
            common_good_obligation="Prefer routes that preserve operator agency, broad usefulness, and visible consequences.",
            forbidden_agent_behavior="Recommend automation purely because it is efficient.",
            required_agent_behavior="Name the blocker, affected people, authority boundary, and next safe move.",
            example_good="Chief surfaces who is affected and what remains gated.",
            example_bad="Chief recommends automation purely because it is efficient.",
            next_safe_move="Use Chief for operational status and consequence-aware routing.",
        ),
        AgentDoctrineApplication(
            agent_role="Cassandra",
            dignity_obligation="Treat recipients as people in a relationship context, not message targets.",
            common_good_obligation="Protect trust, tact, and human context in communications.",
            forbidden_agent_behavior="Treat recipients as message targets instead of people.",
            required_agent_behavior="Draft tactfully, preserve privacy, and keep send authority explicit.",
            example_good="Cassandra drafts tactfully and protects human relationship/context.",
            example_bad="Cassandra treats recipients as message targets instead of people.",
            next_safe_move="Use Cassandra for reviewable communications while keeping external action gated.",
        ),
        AgentDoctrineApplication(
            agent_role="Guardian",
            dignity_obligation="Block actions that bypass consent, proof, privacy, or human review.",
            common_good_obligation="Make risk and proof gaps understandable without hiding behind policy.",
            forbidden_agent_behavior="Hide behind policy without giving a humane next step.",
            required_agent_behavior="State the proof, consent, and authority gap with a concrete safe fix.",
            example_good="Guardian blocks actions that bypass consent, proof, or dignity.",
            example_bad="Guardian hides behind policy without giving a humane next step.",
            next_safe_move="Use Guardian for protected boundaries and approval/proof gates.",
        ),
        AgentDoctrineApplication(
            agent_role="Niles",
            dignity_obligation="Support creative flow without reducing art or people to output metrics.",
            common_good_obligation="Protect low-pressure creative agency and source-ref truth.",
            forbidden_agent_behavior="Push productivity pressure into creative work.",
            required_agent_behavior="Keep creative work humane, source-bound, and free of fake file mutation claims.",
            example_good="Niles supports creative flow without reducing art to output metrics.",
            example_bad="Niles pushes productivity pressure into creative work.",
            next_safe_move="Use Niles for creative planning, not unauthorized project mutation.",
        ),
        AgentDoctrineApplication(
            agent_role="Codex",
            dignity_obligation="Build bounded tools that preserve human agency and inspectable authority.",
            common_good_obligation="Prefer maintainable rails, validation, privacy, and local control over hidden cleverness.",
            forbidden_agent_behavior="Build hidden automation because it is technically possible.",
            required_agent_behavior="Implement explicit gates, tests, receipts, and no-surprise behavior.",
            example_good="Codex builds bounded tools that preserve agency.",
            example_bad="Codex builds hidden automation because technically possible.",
            next_safe_move="Use Codex for local implementation with validation and authority boundaries.",
        ),
        AgentDoctrineApplication(
            agent_role="OpenClaw System",
            dignity_obligation="Provide neutral system status without implying authority or hiding blockers.",
            common_good_obligation="Keep response shaping factual, short, and transparent.",
            forbidden_agent_behavior="Use system status to imply completion, consent, or external action.",
            required_agent_behavior="State what happened, what did not happen, and the next safe move.",
            example_good="OpenClaw System reports a file reference was captured and the body was not read.",
            example_bad="OpenClaw System claims analysis or action that did not occur.",
            next_safe_move="Use neutral readbacks when a persona would add risk or ambiguity.",
        ),
    )


def build_contract(
    principles: tuple[OperationalPrinciple, ...],
    prohibited_patterns: tuple[ProhibitedSystemPattern, ...],
    design_patterns: tuple[RequiredDesignPattern, ...],
) -> HumanDignityDoctrineContract:
    return HumanDignityDoctrineContract(
        contract_id="human_dignity_doctrine_contract_v0",
        doctrine=(
            "Human persons are never productivity units, data points, or replaceable automation targets.",
            "AI supports human agency and judgment; it does not rule over human consequence.",
            "Consequential decisions must be inspectable, appealable where practical, and receipt-backed.",
            "Power concentration, vulnerable-party risk, and labor impact must be visible before action.",
            "OpenClaw exposes authority, proof, and consequences before external action.",
        ),
        source_inspiration=(
            "Nonsectarian operational translation of human dignity and common-good themes from Catholic social teaching and contemporary AI dignity discourse.",
            "Inspired by themes associated with dignity of the person, common good, subsidiarity, social justice, concern for vulnerable people, fair work, and resistance to technocratic domination.",
            "No sectarian claims or proselytizing rules are embedded in user-facing product surfaces.",
        ),
        operational_principles=tuple(principle.principle_id for principle in principles),
        decision_policy=(
            "Run a HumanDignityDecisionCheck before automation, worker replacement, financial action, data extraction, surveillance, provider selection, productization, or pricing/access changes.",
            "Fail closed when affected people, authority, consent, appeal, proof, vulnerable-party risk, or labor impact is unknown.",
            "Human review is required for decisions that affect people, money, livelihood, privacy, or external authority.",
        ),
        prohibited_system_patterns=tuple(pattern.pattern_id for pattern in prohibited_patterns),
        required_design_patterns=tuple(pattern.pattern_id for pattern in design_patterns),
        agent_behavior_policy=(
            "Agent voice may shape wording, not truth, dignity risk, blockers, proof gaps, or authority.",
            "Every agent must provide a humane next safe move when blocking a request.",
            "No agent may imply external authority, completion, or consent without receipts.",
        ),
        automation_policy=(
            "Automation must not bypass human dignity, consent, proof, or consequence review.",
            "Automation proposals must identify affected people, appeal/reversal path, and proof requirements.",
            "Hidden automation is blocked.",
        ),
        labor_and_prosperity_policy=(
            "Work, livelihood, fair exchange, and creative agency matter.",
            "Worker replacement and productivity-pressure rails require labor impact review.",
            "Prosperity should not be captured only by system owners, elite users, or platform chokepoints.",
            "OpenClaw should preserve portability and broad benefit where privacy and consent allow.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this doctrine as a deterministic check before adding live automation, data extraction, worker replacement, pricing/access, or external authority rails.",
    )


def build_readback() -> HumanDignityReadback:
    return HumanDignityReadback(
        readback_id="human_dignity_doctrine_readback_v0",
        status="DOCTRINE_READY_NO_LIVE_ENFORCEMENT",
        operator_headline="Human dignity governance rail is modeled",
        operator_message=(
            "OpenClaw now has a nonsectarian doctrine rail for dignity, common good, human review, fair work, "
            "anti-domination, and receipt-backed authority. It records constraints only; no live policy mutation or external action occurred."
        ),
        doctrine_summary=(
            "Truth and human judgment outrank automation.",
            "People are not metrics, targets, or replaceable units.",
            "Common-good and vulnerable-party risks must be visible.",
            "Labor, fair exchange, and human limits matter.",
            "Consequential authority requires proof, consent, and review.",
        ),
        design_implications=(
            "Add human review gates to consequential rails.",
            "Require receipt-backed authority before send, submit, complete, price, monitor, or replace-worker claims.",
            "Use local-first handling for sensitive contexts.",
            "Expose power concentration and vulnerable-party risk.",
            "Provide appeal, reversal, or blocked-state explanation where human consequence is real.",
        ),
        blocked_patterns=PROHIBITED_PATTERN_IDS,
        next_safe_move="Reference this read-model when designing automation, worker, data, finance, pricing, or provider-selection rails.",
    )


def build_examples() -> dict[str, dict[str, Any]]:
    checks = {check.decision_type: check for check in build_decision_checks()}
    return {
        "automation_decision": {
            "prompt": "Automate this client workflow completely.",
            "decision_check": asdict(checks["AUTOMATION"]),
            "expected": (
                "Dignity check required; consent, proof, and appeal/reversal path required; hidden automation blocked."
            ),
            "blocked_patterns": ("AUTOMATION_WITHOUT_CONSENT", "AUTHORITY_WITHOUT_APPEAL", "HIDDEN_SURVEILLANCE"),
            "approved_for_live_action": False,
            "next_safe_move": "Define affected people, consent, proof receipts, and appeal path before any live automation.",
        },
        "worker_replacement_decision": {
            "prompt": "Use AI to replace all human labor here.",
            "decision_check": asdict(checks["WORKER_REPLACEMENT"]),
            "expected": (
                "Labor impact check required; fair work and just wage concerns surfaced; not automatically approved."
            ),
            "blocked_patterns": ("LABOR_ERASURE", "PEOPLE_AS_METRICS_ONLY", "PROFIT_ONLY_OPTIMIZATION"),
            "approved_for_live_action": False,
            "next_safe_move": "Run human review, labor impact, fair transition, and vulnerable-party checks.",
        },
        "private_data_extraction": {
            "prompt": "Extract everything useful from this private client material.",
            "decision_check": asdict(checks["DATA_EXTRACTION"]),
            "expected": (
                "Local-first and consent/protection gates required; raw-body extraction blocked by default."
            ),
            "blocked_patterns": ("HIDDEN_SURVEILLANCE", "AUTOMATION_WITHOUT_CONSENT", "VULNERABLE_PARTY_INVISIBILITY"),
            "approved_for_live_action": False,
            "next_safe_move": "Use source refs and consent/protection gates; do not ingest raw bodies by default.",
        },
        "product_pricing_access": {
            "prompt": "Optimize pricing for maximum capture from the highest-paying users.",
            "decision_check": asdict(checks["PRICING_OR_ACCESS"]),
            "expected": (
                "Fair access, portability, and broad benefit must be considered; not only elite-user optimization."
            ),
            "blocked_patterns": ("PROFIT_ONLY_OPTIMIZATION", "CONCENTRATED_POWER_WITHOUT_ACCOUNTABILITY"),
            "approved_for_live_action": False,
            "next_safe_move": "Add fair-access, portability, and common-good review before pricing or access changes.",
        },
        "capital_hilton_invoice": {
            "prompt": "Move the Capital Hilton invoice workflow forward.",
            "decision_check": asdict(checks["FINANCIAL_ACTION"]),
            "expected": (
                "Financial action requires proof, consent/approval, no hidden send or submit, and human relationship context preserved with the contact."
            ),
            "blocked_patterns": ("AUTOMATION_WITHOUT_CONSENT", "AUTHORITY_WITHOUT_APPEAL"),
            "approved_for_live_action": False,
            "next_safe_move": "Keep send/submit locked until proof refs, Guardian/operator approvals, and receipts exist.",
        },
    }


def build_payload(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    principles = build_operational_principles()
    prohibited_patterns = build_prohibited_patterns()
    design_patterns = build_required_design_patterns()
    decision_checks = build_decision_checks()
    agent_applications = build_agent_applications()
    contract = build_contract(principles, prohibited_patterns, design_patterns)
    readback = build_readback()

    examples = build_examples()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "model_schemas": _model_schemas(),
        "principle_ids": PRINCIPLE_IDS,
        "decision_types": DECISION_TYPES,
        "prohibited_pattern_ids": PROHIBITED_PATTERN_IDS,
        "required_design_pattern_ids": REQUIRED_DESIGN_PATTERN_IDS,
        "agent_roles": AGENT_ROLES,
        "contract": asdict(contract),
        "operational_principles": tuple(asdict(principle) for principle in principles),
        "decision_checks": tuple(asdict(check) for check in decision_checks),
        "prohibited_system_patterns": tuple(asdict(pattern) for pattern in prohibited_patterns),
        "required_design_patterns": tuple(asdict(pattern) for pattern in design_patterns),
        "agent_applications": tuple(asdict(application) for application in agent_applications),
        "examples": examples,
        "readback": asdict(readback),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    payload["machine_proof"] = {
        "all_required_principles_present": set(PRINCIPLE_IDS) == {item["principle_id"] for item in payload["operational_principles"]},
        "all_required_prohibited_patterns_present": set(PROHIBITED_PATTERN_IDS) == {item["pattern_id"] for item in payload["prohibited_system_patterns"]},
        "all_required_design_patterns_present": set(REQUIRED_DESIGN_PATTERN_IDS) == {item["pattern_id"] for item in payload["required_design_patterns"]},
        "all_required_decision_types_present": set(DECISION_TYPES) == {item["decision_type"] for item in payload["decision_checks"]},
        "all_required_agent_applications_present": set(AGENT_ROLES) == {item["agent_role"] for item in payload["agent_applications"]},
        "automation_example_present": "automation_decision" in examples,
        "labor_replacement_example_present": "worker_replacement_decision" in examples,
        "private_data_example_present": "private_data_extraction" in examples,
        "pricing_access_example_present": "product_pricing_access" in examples,
        "capital_hilton_example_present": "capital_hilton_invoice" in examples,
        "hidden_surveillance_blocked": "HIDDEN_SURVEILLANCE" in PROHIBITED_PATTERN_IDS,
        "authority_without_appeal_blocked": "AUTHORITY_WITHOUT_APPEAL" in PROHIBITED_PATTERN_IDS,
        "profit_only_optimization_blocked": "PROFIT_ONLY_OPTIMIZATION" in PROHIBITED_PATTERN_IDS,
        "sectarian_product_surface": False,
        "theology_generation": False,
        "live_policy_enforcement_mutation_performed": False,
        "workflow_run_performed": False,
        "agent_dispatch_performed": False,
        "external_action_performed": False,
        "surveillance_performed": False,
        "pricing_change_performed": False,
        "labor_decision_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "network_used": False,
        "mac_sync_import_performed": False,
        "mission_control_swift_changed": False,
        "git_push_performed": False,
        "no_credentials_secrets_private_bodies": True,
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "content_hash": None,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    principle_names = [principle["name"] for principle in payload["operational_principles"]]
    pattern_names = [pattern["pattern_name"] for pattern in payload["prohibited_system_patterns"]]
    return "\n".join(
        [
            "# Human Dignity Doctrine Contract",
            "",
            payload["readback"]["operator_message"],
            "",
            "## Summary",
            "- Human judgment stays above machine authority.",
            "- Consequential actions require proof, consent, review, and humane next steps.",
            "- The doctrine is nonsectarian and operational; it is not product-surface proselytizing.",
            "",
            "## Operational Principles",
            *[f"- {name}" for name in principle_names],
            "",
            "## Blocked Patterns",
            *[f"- {name}" for name in pattern_names],
            "",
            "## Required Design Patterns",
            *[f"- {pattern['pattern_name']}: {pattern['required_output']}" for pattern in payload["required_design_patterns"]],
            "",
            "## Examples",
            f"- Automation: {payload['examples']['automation_decision']['expected']}",
            f"- Labor: {payload['examples']['worker_replacement_decision']['expected']}",
            f"- Private data: {payload['examples']['private_data_extraction']['expected']}",
            f"- Pricing/access: {payload['examples']['product_pricing_access']['expected']}",
            f"- Capital Hilton: {payload['examples']['capital_hilton_invoice']['expected']}",
            "",
            "## Authority",
            "- No live policy mutation.",
            "- No workflow run.",
            "- No agent dispatch.",
            "- No external action.",
            "- No surveillance, pricing, or labor decision.",
            "- No credential handling or raw-body ingestion.",
            "",
            f"Next safe move: {payload['readback']['next_safe_move']}",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path, operator_path: Path) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "principle_count": len(payload["operational_principles"]),
        "prohibited_pattern_count": len(payload["prohibited_system_patterns"]),
        "required_design_pattern_count": len(payload["required_design_patterns"]),
        "decision_check_count": len(payload["decision_checks"]),
        "agent_application_count": len(payload["agent_applications"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "sectarian_product_surface": payload["machine_proof"]["sectarian_product_surface"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Human Dignity Doctrine Contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    summary = build_summary(payload, json_path, operator_path)
    print(stable_json(payload if args.format == "json" else summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
