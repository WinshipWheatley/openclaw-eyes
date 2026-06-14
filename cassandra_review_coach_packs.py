"""Static Cassandra guided-review coach packs.

The packs are deterministic copy and option templates for local review
sessions. They do not call models, promote data, or provide professional
advice.
"""

from __future__ import annotations

from typing import Any


COACH_PACK_SCHEMA_VERSION = "REVIEW_COACH_PACK_V0"

REQUIRED_COACH_CATEGORIES = (
    "payment privacy",
    "identity/persona policy",
    "Clara Reid use",
    "Niles public technical-director use",
    "Log Rhythm exclusion",
    "rates",
    "clients/payers",
    "invoice numbering/payee policy",
    "expense categories",
    "venues",
    "do-not-import rules",
    "data room review",
)


def _pack(
    *,
    plain_context: str,
    why_it_matters: str,
    recommended_default: str,
    option_templates: list[dict[str, str]],
    example_answers: list[str],
    best_practice_notes: list[str],
    caution_flags: list[str],
    cpa_review_recommended: bool = False,
    legal_review_recommended: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": COACH_PACK_SCHEMA_VERSION,
        "plain_context": plain_context,
        "why_it_matters": why_it_matters,
        "recommended_default": recommended_default,
        "option_templates": option_templates,
        "example_answers": example_answers,
        "best_practice_notes": best_practice_notes,
        "caution_flags": caution_flags,
        "cpa_review_recommended": cpa_review_recommended,
        "legal_review_recommended": legal_review_recommended,
    }


COACH_PACKS_BY_CATEGORY: dict[str, dict[str, Any]] = {
    "payment privacy": _pack(
        plain_context="This decides which payment details are safe to reuse in routine business workflows.",
        why_it_matters=(
            "Invoices and follow-ups can be forwarded, so private payment details should stay out of default text."
        ),
        recommended_default="Keep direct deposit and raw private payment details manual-only; use Zelle/check wording as the safer default when appropriate.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Use safe default",
                "answer_text": "Use the safer payment privacy default and keep sensitive details manual-only.",
                "tradeoff": "Safer for forwarding; may require manual handling for some clients.",
            },
            {
                "option_id": "trusted_clients_only",
                "label": "Trusted clients only",
                "answer_text": "Allow more payment detail only for explicitly trusted clients.",
                "tradeoff": "More convenient, but requires maintaining trust tiers.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep this unresolved until Winship reviews exact wording.",
                "tradeoff": "Avoids premature defaults; slows automation.",
            },
        ],
        example_answers=[
            "Keep direct deposit manual-only. Zelle/check wording is fine for normal invoices.",
            "Only show extra payment instructions after I confirm the client is trusted.",
        ],
        best_practice_notes=[
            "Store policy choices, not raw payment details.",
            "Treat forwarding risk as the default assumption.",
        ],
        caution_flags=["Do not store raw payment details in guided-review answers."],
    ),
    "identity/persona policy": _pack(
        plain_context="This decides which identity or persona OpenClaw may use for business communication context.",
        why_it_matters="Sender identity mistakes can confuse clients and make later review harder.",
        recommended_default="Keep Winship as the default business identity unless a narrower persona rule is explicitly confirmed.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Winship default",
                "answer_text": "Use Winship as the default identity and keep persona use narrow and explicit.",
                "tradeoff": "Clear and conservative; less automation for specialized contexts.",
            },
            {
                "option_id": "context_specific",
                "label": "Context-specific",
                "answer_text": "Allow persona use only in named contexts after review.",
                "tradeoff": "More flexible; requires careful routing rules.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep identity/persona rules provisional pending professional review.",
                "tradeoff": "Safer for public-facing use; delays promotion.",
            },
        ],
        example_answers=[
            "Use Winship by default; keep persona use off unless I name the context.",
            "Persona wording can be drafted as context, but not treated as confirmed public identity.",
        ],
        best_practice_notes=[
            "Keep sender identity, signature, and public-facing persona rules separate.",
            "Record the boundary, not just the display name.",
        ],
        caution_flags=["Public-facing identity rules should not be promoted from provisional notes alone."],
        legal_review_recommended=True,
    ),
    "Clara Reid use": _pack(
        plain_context="This decides whether Clara Reid is a private helper context or a public-facing business identity.",
        why_it_matters="Using Clara Reid too broadly could create confusing authorship or sender expectations.",
        recommended_default="Keep Clara Reid non-default and require explicit confirmation before any public-facing use.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Private helper only",
                "answer_text": "Keep Clara Reid as private helper context only unless I explicitly approve a use case.",
                "tradeoff": "Conservative and clear; limits automation.",
            },
            {
                "option_id": "followups_only",
                "label": "Follow-ups only",
                "answer_text": "Allow Clara Reid only for reviewed follow-up contexts, not original invoices.",
                "tradeoff": "Useful for operations; requires precise boundaries.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep Clara Reid rules provisional pending professional review.",
                "tradeoff": "Avoids public identity mistakes; slows rollout.",
            },
        ],
        example_answers=[
            "Clara Reid is private helper context only for now.",
            "Clara can help prepare follow-up language, but not be the default sender.",
        ],
        best_practice_notes=["Separate drafting context from sender identity."],
        caution_flags=["Do not treat a provisional persona note as confirmed authority."],
        legal_review_recommended=True,
    ),
    "Niles public technical-director use": _pack(
        plain_context="This decides how Niles may be used around technical-director or music-production contexts.",
        why_it_matters="Niles may be helpful internally, but public-facing use needs a clear boundary.",
        recommended_default="Keep Niles internal by default and require explicit context before public-facing use.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Internal by default",
                "answer_text": "Keep Niles internal by default and require explicit approval for public-facing use.",
                "tradeoff": "Clear boundary; fewer automatic public references.",
            },
            {
                "option_id": "project_context",
                "label": "Project context",
                "answer_text": "Allow Niles references only inside named creative or technical projects.",
                "tradeoff": "Useful for organization; needs project scoping.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep Niles public-use rules provisional pending professional review.",
                "tradeoff": "Safer for external use; slower to promote.",
            },
        ],
        example_answers=[
            "Niles is internal unless I name the project and say it can be public-facing.",
            "Use Niles for organizing creative notes, not for default client identity.",
        ],
        best_practice_notes=["Keep creative context separate from business sender identity."],
        caution_flags=["Do not infer public-facing authority from internal project notes."],
        legal_review_recommended=True,
    ),
    "Log Rhythm exclusion": _pack(
        plain_context="This decides whether historical Log Rhythm Records material stays excluded from active business logic.",
        why_it_matters="Old identities can accidentally come back if exclusion rules are not explicit.",
        recommended_default="Keep Log Rhythm Records blocked from active identity, client, sender, and routing logic.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Keep blocked",
                "answer_text": "Keep Log Rhythm Records blocked from active business logic.",
                "tradeoff": "Prevents revival of old context; may require manual archive lookup.",
            },
            {
                "option_id": "archive_only",
                "label": "Archive only",
                "answer_text": "Allow Log Rhythm Records only as archived historical context.",
                "tradeoff": "Keeps history available; requires clear archive labeling.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep this exclusion provisional pending professional review.",
                "tradeoff": "Conservative; delays any active use.",
            },
        ],
        example_answers=[
            "Keep Log Rhythm Records blocked from active routing and sender logic.",
            "Archive only. Do not use it as a current business identity.",
        ],
        best_practice_notes=["Use explicit exclusion rules for historical identities."],
        caution_flags=["Do not import historical identity labels into active routing."],
        legal_review_recommended=True,
    ),
    "rates": _pack(
        plain_context="This decides how rate or service-price facts should be treated before they drive invoices.",
        why_it_matters="Wrong rates can create wrong expectations and wrong billing drafts.",
        recommended_default="Keep rates provisional until Winship confirms source, client, service, and effective context.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Keep provisional",
                "answer_text": "Keep this rate provisional until source, client, service, and context are confirmed.",
                "tradeoff": "Avoids bad billing assumptions; needs one more review step.",
            },
            {
                "option_id": "service_split",
                "label": "Split services",
                "answer_text": "Split the rate by service type before any later promotion.",
                "tradeoff": "Cleaner records; more setup work.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Hold this rate for CPA/professional review before promotion.",
                "tradeoff": "More conservative; slower to use.",
            },
        ],
        example_answers=[
            "Keep this rate provisional until I confirm the service and client.",
            "Split speaker rental from A/V support before promotion.",
        ],
        best_practice_notes=["Tie rates to client, service, date/rhythm, and source."],
        caution_flags=["Do not let provisional rates create invoice-ready facts."],
        cpa_review_recommended=True,
    ),
    "clients/payers": _pack(
        plain_context="This decides how OpenClaw should distinguish client, payer, contact, and venue names.",
        why_it_matters="Client/payer confusion can route follow-ups to the wrong person or context.",
        recommended_default="Keep client, payer, billing contact, and venue as separate fields until Winship confirms them.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Separate roles",
                "answer_text": "Keep client, payer, billing contact, and venue separate until confirmed.",
                "tradeoff": "Cleaner records; asks for more specificity.",
            },
            {
                "option_id": "single_context",
                "label": "Single context",
                "answer_text": "Treat this as one client context for now, without promoting payer/contact details.",
                "tradeoff": "Faster setup; less precise.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Hold this client/payer item until Winship provides the exact role split.",
                "tradeoff": "Avoids mistaken routing; delays automation.",
            },
        ],
        example_answers=[
            "Capital Hilton is the client context; keep payer/contact details unconfirmed for now.",
            "Separate venue from billing contact before promotion.",
        ],
        best_practice_notes=["Do not collapse client, payer, contact, and venue unless confirmed."],
        caution_flags=["Do not infer billing contact authority from a venue mention."],
    ),
    "invoice numbering/payee policy": _pack(
        plain_context="This decides how invoice identifiers, payee wording, and billing terms should be handled.",
        why_it_matters="Invoice policy choices affect consistency across future business records.",
        recommended_default="Keep numbering/payee policy provisional until Winship confirms one future-facing convention.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Future convention",
                "answer_text": "Keep old invoices as history and choose one future-facing numbering/payee convention later.",
                "tradeoff": "Avoids rewriting history; requires a clean future rule.",
            },
            {
                "option_id": "map_old_new",
                "label": "Map old/new",
                "answer_text": "Create a later mapping between historical invoice names and the future convention.",
                "tradeoff": "Better traceability; more review work.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Hold invoice policy until Winship confirms exact wording and numbering.",
                "tradeoff": "Conservative; slower setup.",
            },
        ],
        example_answers=[
            "Do not rename old invoices; use one future convention after I confirm it.",
            "Keep payee wording provisional until I approve exact invoice text.",
        ],
        best_practice_notes=["Separate historical mapping from future policy."],
        caution_flags=["Do not mark invoice policy as confirmed from provisional notes."],
    ),
    "expense categories": _pack(
        plain_context="This decides whether expense labels are business organization labels or professional classifications.",
        why_it_matters="Business labels are useful, but they should not be mistaken for professional classification advice.",
        recommended_default="Use expense categories only as provisional business labels pending CPA review.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Business labels",
                "answer_text": "Use these as provisional business labels only, pending CPA review.",
                "tradeoff": "Useful for sorting; not treated as professional classification.",
            },
            {
                "option_id": "rename_labels",
                "label": "Rename labels",
                "answer_text": "Revise the expense labels before any later promotion.",
                "tradeoff": "Clearer language; requires another pass.",
            },
            {
                "option_id": "manual_review",
                "label": "CPA review",
                "answer_text": "Hold expense categories for CPA review before promotion.",
                "tradeoff": "Most conservative; delays use.",
            },
        ],
        example_answers=[
            "Use these only as business labels until CPA review.",
            "Rename this category before using it in reports.",
        ],
        best_practice_notes=["Keep business labels separate from professional classification decisions."],
        caution_flags=["Do not present category labels as tax advice."],
        cpa_review_recommended=True,
    ),
    "venues": _pack(
        plain_context="This decides whether a place is a venue, mileage destination, client context, or contact context.",
        why_it_matters="Venue mistakes can distort event history, travel context, and billing context.",
        recommended_default="Keep venue records separate from mileage destinations and client/payer records.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Separate places",
                "answer_text": "Keep venues separate from mileage destinations and client/payer records.",
                "tradeoff": "Cleaner records; requires role confirmation.",
            },
            {
                "option_id": "review_list",
                "label": "Review list",
                "answer_text": "Review this place list before any venue promotion.",
                "tradeoff": "Avoids mixed records; takes another pass.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep this venue item provisional until Winship confirms its role.",
                "tradeoff": "Conservative; slower setup.",
            },
        ],
        example_answers=[
            "This is a venue, not a payer.",
            "Keep mileage destinations separate from venues.",
        ],
        best_practice_notes=["Use separate fields for place role, business role, and contact role."],
        caution_flags=["Do not infer client/payer status from a place name."],
    ),
    "do-not-import rules": _pack(
        plain_context="This decides whether a provisional item should stay blocked from active import.",
        why_it_matters="Explicit blocks prevent unsafe or stale information from becoming active behavior.",
        recommended_default="Keep blocked items blocked unless Winship later gives a narrow, explicit exception.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Keep blocked",
                "answer_text": "Keep this item blocked from active import.",
                "tradeoff": "Safest default; may require manual handling if needed later.",
            },
            {
                "option_id": "archive_only",
                "label": "Archive only",
                "answer_text": "Keep this as archive context only, not active reference data.",
                "tradeoff": "Preserves history; prevents automation.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Keep blocked pending professional review.",
                "tradeoff": "Conservative; no active use until reviewed.",
            },
        ],
        example_answers=[
            "Keep this blocked from active import.",
            "Archive-only. Do not use it for active routing or business defaults.",
        ],
        best_practice_notes=["Make exclusion rules explicit and durable."],
        caution_flags=["Do not override a block from a provisional review answer."],
        legal_review_recommended=True,
    ),
    "data room review": _pack(
        plain_context="This is a general Data Room setup question for business defaults and missing specifics.",
        why_it_matters="Clear defaults make later automation safer, but provisional answers still need promotion review.",
        recommended_default="Choose the conservative default and keep ambiguous details provisional.",
        option_templates=[
            {
                "option_id": "recommended_default",
                "label": "Conservative default",
                "answer_text": "Use the conservative default and keep ambiguous details provisional.",
                "tradeoff": "Safer setup; may ask more follow-up questions.",
            },
            {
                "option_id": "revise",
                "label": "Revise wording",
                "answer_text": "Revise this item before later promotion.",
                "tradeoff": "More accurate; takes another pass.",
            },
            {
                "option_id": "manual_review",
                "label": "Manual review",
                "answer_text": "Hold this item for later review.",
                "tradeoff": "Avoids premature assumptions; delays automation.",
            },
        ],
        example_answers=[
            "Use the conservative default for now.",
            "Hold this until I can give a more exact answer.",
        ],
        best_practice_notes=["Prefer explicit defaults over inferred behavior."],
        caution_flags=["Do not treat a coach answer as confirmed reference data."],
    ),
}


def coach_pack_for_category(category: str) -> dict[str, Any]:
    """Return the static coach pack for a question category."""

    return COACH_PACKS_BY_CATEGORY.get(str(category or ""), COACH_PACKS_BY_CATEGORY["data room review"])
