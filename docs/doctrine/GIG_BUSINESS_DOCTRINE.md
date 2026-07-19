# Gig Business Doctrine — v1.2 (operator-verbatim-derived, 2026-07-18)

Status: ACTIVE-GROWING. Source: operator terminal, 2026-07-18. This document is the durable home
for booking/pricing/safety/team logistics. FRESHNESS RULE: this doc class must never be stale —
agents receive its content via dank packets when relevant; changes require operator words; the
system tracks its age and flags drift. NO agent acts on pricing/logistics from any other source.

## Artistic identity (governs all intake)
Deep-lane, scoped, world-class at exactly what he does — NOT a wide-shallow hire-and-change
musician. Happiest clients already like what he does and DEFER music decisions to him. He can
accommodate some requests done certain ways — but requests add cost, and requests outside the
deep lane are declined honestly: clients who want him to be something he is not will not be happy,
and that is a client-fit failure to detect at INTAKE, not after booking. His show energy is
precious; every factor that drains it is a real cost.

## Pricing & buckets
- **Band gig target: $20,000** (corporate gig or wedding class). Covers: 5-piece band (potentially
  all hired guns), 3–5 practices, travel, lodging, ~2 techs, extra lighting/stage/sound rentals.
- **Pay floor:** every musician AND tech ≥ $500.
- **Bonus system** (group-scoped: musicians pool / techs pool): all-practices attendance earns the
  group bonus; a missed practice never cuts the $500 floor — it only forfeits bonus. Bonus grows
  for: on-time + prepared at every practice/event; pulling own weight / executing responsibilities
  well; adapting to his requests. **Bonuses and expenses require operator approval.**
- **Hard economics:** max payout (band + techs + all costs) = $15,000 → operator minimum walk-away
  = **$5,000 after expenses and taxes.** At $20k+ with the $5k minimum guaranteed: he turns down
  almost nothing — the only absolute vetoes are UNSAFE or UNETHICAL.
- **Free / low-cost bucket:** big crowd at a cool event, or opening for a band he really likes.
  NOT in the bucket: bands he doesn't like or crowds that won't get his style (absent another real
  incentive). Solo-acoustic pricing scales by set length (1/2/3+ hour tiers) — tier points to be declared
  by operator. Observed numeric price history lives in the typed
  `config/price_truth_facts.v1.json` rows and is never treated as a declared current rate. Live Arts
  Maryland runs two streams — monthly speaker/PA rental + per-gig AV-tech labor.

## Label / identity facts (absorbed from DEEPPOCKET reference)
Deep Pocket Records (parent: Winship Live; owner H. Winship Wheatley IV). Genres: Yacht Rock, Pop
Rock, Soul, Electronica, World Rhythm — the named territory of the deep lane. DEEPPOCKET.md remains
the standing label/publishing reference; only the identity slice lives here.

## Client-fit & conflict sensing (class-level — NOT wedding-only)
Lesson (weddings round): the CONTRACT was with the bride; the groom hated the act and "terminated,"
but he was not the client. Multi-stakeholder events carry weird authority/satisfaction splits —
the system senses potential conflicts (who is the client, who feels like the client, who can blow
it up) and thinks them through at intake WITHOUT becoming over-cautious. Contract clarity on who
holds termination authority.

## Safety doctrine (non-negotiable, from lived events)
At his last wedding the operator was dosed (GHB, by a guest who dosed several people); he collapsed
at the DJ table; his ex-wife sipped his drink, was also affected, and drove him home.
- **NEVER accept drinks from anyone at gigs** — no exceptions for upscale/beautiful events.
- **Travel with a posse when possible.** Preferred structure: band with roadies, designated
  engineers, and a buffer person/tour-manager whose JOB is: keep stress off the operator, watch for
  crazy before it starts, and in any incident FIRST secure the talent (the operator), THEN handle
  gear/cleanup/whatever is appropriate.
- Safety factors price into gigs; unsafe = absolute veto regardless of money.

## Email/outreach conduct (applies to all client mail)
- Two watch modes on every outgoing thread: (1) POLL — no reply within 3 business days → follow-up
  on the 4th business day, repeating every cycle until a reply comes; business-week is PER-CLIENT
  (arts-scene businesses may exclude Mon/Tue — registry-driven calendars). Follow-ups are freshly
  written each time — never regurgitation — professional pestering that compels action while
  staying impeccably professional. (2) MONITOR — reply-triggered wake (provider push).
- **No auto-responses without Guardian approval. Responses NEVER send instantly — human-timing
  delays always.** Sole future exception: Clara's fast autonomous replies to POTENTIAL CLIENTS,
  only after she passes her trust phases (below).

## Clara's client-intake trust phases (FUTURE build — after email/scheduling/money/tone basics)
Before autonomous client response, Clara must demonstrably: read his calendar AND know it is fresh;
know pricing points and buckets; resolve gig location (venue/county/state/country), flights, gear
volume; recognize pain-in-the-ass factors and price them in; classify free-bucket vs minimum-met vs
above-minimum; apply the artistic-identity fit test; know accommodation-with-cost rules. Her rung
promotions ride the autonomy ladder with operator taps.

## The trust breaking point (governing rule for big fish)
When a big fish is on the line there is a CLEAN, BINARY handoff: either the system+agents pull it
in end-to-end, or the operator pulls it in himself with his human team. NO GRAY AREA. Music legal
and team coordination (agents, systems, humans, companies) integrate before the system ever holds
the rod. "This shit needs to work the day I let it loose." End-state: the crew runs the helm; the
operator is Picard — "engage."

<!-- BEGIN GIG_BUSINESS_DOCTRINE_CONTRACT -->
```json
{
  "schema_version": "gig_business_doctrine_contract_v1_2",
  "doctrine_ref": "gig_business_doctrine:v1.2",
  "pricing_logistics_source_policy": "ONLY",
  "freshness": {
    "class": "NEVER_STALE",
    "stale_on_age": false,
    "drift_on_hash_change": true,
    "missing_is_stale": true,
    "delivery_requires_current_hash": true
  },
  "sections": [
    {
      "section_id": "artistic_identity",
      "title": "Artistic identity (governs all intake)",
      "consumers": ["maestro", "cassandra", "clara", "niles"],
      "question_classes": ["gig_intake", "gig_booking"],
      "packet_summary": "The operator is a deep-lane, world-class artist, not a wide-shallow hire-and-change musician. Detect style fit at intake; accommodations add cost, and out-of-lane requests are declined honestly. Protect show energy as a real cost."
    },
    {
      "section_id": "pricing_buckets",
      "title": "Pricing & buckets",
      "consumers": ["maestro", "chief", "cassandra", "clara", "guardian", "hermes", "niles"],
      "question_classes": ["gig_pricing", "gig_intake", "gig_booking"],
      "packet_summary": "Band gig target: $20,000. Musician and tech pay floor: $500 each. Maximum band, tech, and cost payout: $15,000; operator minimum walk-away: $5,000 after expenses and taxes. Bonuses and expenses require operator approval. Historical observed prices are not declared rates; solo tier points remain operator-undeclared."
    },
    {
      "section_id": "label_identity",
      "title": "Label / identity facts (absorbed from DEEPPOCKET reference)",
      "consumers": ["maestro", "cassandra", "clara", "niles"],
      "question_classes": ["gig_marketing", "gig_intake"],
      "packet_summary": "Deep Pocket Records is the Winship Live label identity for Yacht Rock, Pop Rock, Soul, Electronica, and World Rhythm. DEEPPOCKET.md remains the detailed label and publishing reference."
    },
    {
      "section_id": "client_fit_conflict",
      "title": "Client-fit & conflict sensing (class-level — NOT wedding-only)",
      "consumers": ["maestro", "cassandra", "clara", "guardian", "hermes"],
      "question_classes": ["gig_intake", "gig_booking", "gig_logistics"],
      "packet_summary": "At intake, identify the contracting client, perceived decision-makers, and actual termination authority. Think through multi-stakeholder conflict without becoming over-cautious."
    },
    {
      "section_id": "safety",
      "title": "Safety doctrine (non-negotiable, from lived events)",
      "consumers": ["maestro", "chief", "cassandra", "clara", "guardian", "hermes"],
      "question_classes": ["gig_intake", "gig_booking", "gig_logistics"],
      "packet_summary": "Never accept drinks from anyone at gigs. Travel with a posse when possible, including roadies, engineers, and a buffer or tour manager who secures the operator before gear in an incident. Price safety factors into gigs; unsafe is an absolute veto."
    },
    {
      "section_id": "email_outreach",
      "title": "Email/outreach conduct (applies to all client mail)",
      "consumers": ["maestro", "cassandra", "clara", "guardian"],
      "question_classes": ["client_email", "email_watch"],
      "packet_summary": "Every outgoing client thread has POLL and MONITOR watches. POLL follows the per-client business calendar and freshly composes each cycle. MONITOR is provider-push reply wake. Guardian approval and randomized professional human timing are mandatory; no instant or unapproved auto-response."
    },
    {
      "section_id": "clara_intake_trust",
      "title": "Clara's client-intake trust phases (FUTURE build — after email/scheduling/money/tone basics)",
      "consumers": ["maestro", "cassandra", "clara", "guardian"],
      "question_classes": ["clara_intake", "gig_intake"],
      "packet_summary": "Clara autonomous client response is future and ladder-gated after email, scheduling, money, and tone basics. Her trust battery covers fresh calendar knowledge, pricing and buckets, venue and travel logistics, gear, cost factors, client fit, and accommodation-with-cost rules."
    },
    {
      "section_id": "trust_breaking_point",
      "title": "The trust breaking point (governing rule for big fish)",
      "consumers": ["maestro", "chief", "cassandra", "clara", "guardian", "hermes"],
      "question_classes": ["gig_intake", "gig_booking", "client_email", "email_watch"],
      "packet_summary": "Big-fish work requires a clean binary handoff: either the governed system and agents handle it end-to-end, or the operator and human team do. No gray area; legal and team coordination must work before autonomous release."
    }
  ]
}
```
<!-- END GIG_BUSINESS_DOCTRINE_CONTRACT -->


## Historical pricing evidence (Gmail-sourced, OBSERVED not declared — for tier calibration)
NOT current rates; his own past quotes, useful to anchor the solo/acoustic tiers:
- 2015: $400 for three 45-min sets; +$150 per learned/custom song.
- 2019: ~$727 for a 1-hour cocktail-hour solo (singing guitarist, single sound-system location).
- Corporate (GigSalad): a $727 full-fee corporate booking on record.
- 2016 wedding: a $2,000 barter-in-fees performance arrangement (client-fit: "laid-back, relaxed,
  effortless, professional, high-quality"; all-inclusive pricing to avoid line-item friction; no
  add-on discounts) — corroborates the artistic-fit doctrine.
- Boomerang tooling history (2015-2017): he already ran no-reply reminder cadence — prior art for the
  poll/follow-up watch modes (the day-4 cadence is NEW; Boomerang proves the pattern's in his DNA).
