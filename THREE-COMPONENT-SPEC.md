# OpenClaw: Three-Component Engineering Specification (ChatGPT 5.5 Pro, 2026-06-23)

AUTHORITATIVE BUILD CONTRACT. Build to this exactly. TRUTH FIRST throughout.

## Shared architectural contract
Each agent answers from a deterministic context packet of GROUNDED facts (each traces to a real
read-model/ledger source). Comedy, teaching, persona, and detector metadata are NOT facts and must
NEVER enter the grounded fact list.

context_packet: { packet_id: str, created_at: datetime, facts: list[GroundedFact], render_hints: RenderHints }
GroundedFact: { fact_id, subject_ref, predicate, value, value_type, source_ref, source_revision, observed_at }
facts are IMMUTABLE once assembly completes. Later components add directives to render_hints only;
they may not alter/reinterpret/replace grounded facts.

Reply pipeline: 1 assemble facts; 2 zero-error+comedy-admission gate; 3 select archetype+template;
4 plan term teaching; 5 render in persona; 6 insert approved defs+comedy deterministically;
7 operator_surface_guard; 8 claim detector on EXACT FINAL surface text; 9 audit accepted candidates;
10 deliver per policy; 11 update term-learning ONLY after confirmed delivery; 12 queue supervised
heal tasks ONLY for confirmed-incorrect claims. The detector inspects the exact operator-visible text
AFTER all rendering/insertion/guard rewriting.

---

## Component 1: Comedy Archetype Seeding
Purpose: the existing comedy GATE decides WHETHER comedy is permitted. This component decides WHICH
mechanism best exposes the situation and selects a grounded diagnostic realization. Occurrence
decision and archetype decision stay SEPARATE. Golden-ratio gate controls whether comedy may occur;
context signals select the archetype; random selection only as fallback among grounded-compatible
archetypes. A gate admission is NOT an obligation to joke — no diagnostic basis => no joke.

Field location: context_packet.render_hints.comedy = ComedyHint:
{ enabled: bool; archetype_hint: absurdist|logical_literalism|misplaced_confidence|bureaucratic_overthinker|null;
  selection_mode: none|context_rule|seeded_fallback; diagnostic_signal: str|null;
  evidence_fact_ids: list[fact_id]; template_id: str|null; slot_bindings: {slot: fact_id};
  agent_rank: int 1..6; intensity_cap: int 0..6 (copied from gate); max_sentences: int (v1: 0 or 1);
  gate_decision_ref; policy_version }
Comedian names are DOC ALIASES ONLY (absurdist=Harland Williams mech; logical_literalism=Mitch Hedberg;
misplaced_confidence=Jim Carrey/Jeff Daniels; bureaucratic_overthinker=Brian Regan). The production
prompt uses the abstract rhetorical MECHANISM, never "imitate performer X".

Seeder runs AFTER context assembly + AFTER the comedy gate, BEFORE persona rendering. Flow:
ContextAssembler -> ComedyGate -> ComedyArchetypeSeeder -> JargonTeachingPlanner -> PersonaRenderer
-> ComedyRealizer -> operator_surface_guard. Seeder consumes ComedyGateDecision {admitted,
zero_error_pass, agent_rank, intensity_cap, golden_ratio_roll_passed, gate_decision_ref} EXACTLY —
no re-admission, no reinterpreting a rejection.

Hard invariants: comedy disabled => enabled False, archetype_hint null, selection_mode none,
diagnostic_signal null, evidence empty, template null, slots empty, max_sentences 0. comedy enabled
=> zero_error_pass AND admitted AND golden_ratio_roll_passed all True. Every evidence_fact_id +
every slot fact_id must exist in the packet. A template may reframe a grounded relationship but may
NOT add an entity/number/date/cause/outcome/status/event absent from supporting facts. The literal
factual explanation PRECEDES the joke. v1: <=1 comedy sentence; on render/validation/guard failure,
REMOVE the comedy line — do NOT reroll/regenerate.

Situation signals (from structured facts / deterministic read-model comparisons; v1 does NOT ask an
LLM to infer signals from prose):
- logical_literalism: LITERAL_SCOPE_MISMATCH (requested vs selected scope both grounded, exact-token/
  label match, selected!=requested); BOUNDARY_LITERALISM (strict < / > rule, observed == threshold,
  equality excluded); WORDING_INTENT_MISMATCH (verified alias map exists, raw wording failed, a known
  alias would have resolved). Diagnostic: result came from exact rule semantics / missing normalization,
  not absent data.
- bureaucratic_overthinker: APPROVAL_DEPENDENCY_CYCLE (approval graph self-loop or SCC >1 node);
  REDUNDANT_GATE_CHAIN (>=3 sequential gates eval same normalized condition / same unresolved fact);
  PROCESS_EXCEEDS_TASK (mandatory approvals > threshold AND a grounded policy fact classifies the op
  low-risk/reversible). Diagnostic: structural process failure, not ordinary delay.
- misplaced_confidence: CONFIDENCE_EVIDENCE_GAP (reported conf >=0.80 AND verified evidence coverage
  <=0.50, OR conf-coverage >=0.40; coverage = verified_checks/required_checks); RETRY_WITHOUT_PROGRESS
  (>=3 attempts, same state revision, no new verified result, hang detector says NOT hung);
  PREMATURE_SUCCESS (task represented complete/success while >=1 grounded required-verification fact is
  false/absent). Diagnostic: distinguish estimated success / repeated activity / verified completion.
- absurdist: TYPE_CATEGORY_COLLISION (typed field got a value from a different registered category,
  safely handled, no unresolved error); MUTUALLY_EXCLUSIVE_CONSTRAINTS (constraint solver returns
  unsat core with >=2 operator constraints); ORDER_OF_MAGNITUDE_ANOMALY (actual/reference >=10 or
  <=0.1, compatible units). Diagnostic: category confusion / impossible requirements / magnitude gap.

Context rule vs fallback: context_rule when ONE high-specificity signal maps uniquely to one archetype.
seeded_fallback only when demonstrably diagnostic but no single archetype is causally superior — choose
from a CONTROLLED allowed list, not all four: GENERIC_REDUNDANCY -> {logical_literalism,
misplaced_confidence, bureaucratic_overthinker}; GENERIC_EXPECTATION_GAP -> {logical_literalism,
misplaced_confidence, absurdist}; UNUSUAL_VALID_SEQUENCE -> {absurdist, bureaucratic_overthinker}.
No grounded signal => comedy disabled even if gate passed. 10-15% is a MAX occurrence rate, not a quota.

SituationSignal: { code, priority(int causal specificity), salience(0..100 deterministic rule),
forced_archetype, allowed_archetypes, evidence_fact_ids, template_family, slot_bindings }.
Priorities: APPROVAL_DEPENDENCY_CYCLE 100; LITERAL_SCOPE_MISMATCH 95; BOUNDARY_LITERALISM 90;
CONFIDENCE_EVIDENCE_GAP 85; RETRY_WITHOUT_PROGRESS 80; MUTUALLY_EXCLUSIVE_CONSTRAINTS 75;
TYPE_CATEGORY_COLLISION 70; ORDER_OF_MAGNITUDE_ANOMALY 65; REDUNDANT_GATE_CHAIN 60;
GENERIC_REDUNDANCY 30; GENERIC_EXPECTATION_GAP 25; UNUSUAL_VALID_SEQUENCE 20.
Multi-signal: pick highest priority; tie-break higher salience; same-archetype ties merge evidence if
not confusing; different-but-compatible -> seeded fallback among them; materially different diagnoses
=> ABSTAIN (never compress two incompatible explanations).

Composition: seeder does NOT re-roll occurrence; consumes admitted + golden_ratio_roll_passed. Optional
prob schedule Guardian 10% Chief 11% Cassandra 12% Hermes 13% Maestro 14% Niles 15%. Rank controls
template INTENSITY not factual freedom (Guardian dry/minimal -> Niles most animated); all ranks same
grounded-evidence constraints, no rank invents facts.

Deterministic fallback randomness: keyed hash/HMAC over (reply_id, agent_id, domain "comedy-archetype",
policy_version); digest -> int -> mod (num sorted candidate archetypes). Secret key prevents operator
manipulating selection via crafted IDs. Separate domains: comedy-admission, comedy-archetype,
comedy-template-variant. Same reply_id+policy_version => same result.

Comedy realization (v1 = reviewed template registry, NOT free-form LLM jokes):
ComedyTemplate: { template_id, signal_code, archetype, minimum_rank, maximum_rank, required_slots,
rendered_pattern }. Template may use only grounded slot values; no number/date/proper-noun/status/causal
assertion unless its slot points to a grounded fact; no unknown technical terms. Comedy line inserted
AFTER the literal diagnosis. Future LLM mode strictly gated (only signal+grounded facts+1-sentence
limit, temp 0, no new proper nouns/numbers/dates/statuses/terms, detector+guard inspect it, any failure
removes line no retry).

Seeder procedure: 1 disabled if zero_error_pass False; 2 disabled if admitted False or
golden_ratio_roll_passed False; 3 extract deterministic signals; 4 select primary (priority,salience,
stable tie-break); 5 disabled if no primary; 6 forced archetype => context_rule; 7 else filter allowed
archetypes to those with reviewed templates for the rank; 8 disabled if none remain; 9 deterministically
pick one => seeded_fallback; 10 select reviewed template (signal, archetype, rank, intensity cap,
1-sentence); 11 disabled if none; 12 build ComedyHint w/ grounded evidence+slots; 13 validate every ref.

Worked: (1) approval cycle -> bureaucratic_overthinker, literal "release blocked by circular approval
dependency", joke "Each approval is waiting for the next approval to go first." (2) exact-label bug ->
logical_literalism, "It followed 'vocals' so literally that 'Lead Vox' and 'BGV' did not qualify."
(3) premature certainty (conf 96%, 2/5 checks) -> misplaced_confidence, "The confidence finished the
job before the checklist did."

Comedy acceptance tests: unresolved error => enabled False; hang => enabled False; rejected gate =>
no archetype; same reply/agent/secret/policy => same fallback; LITERAL_SCOPE_MISMATCH=>logical_literalism;
APPROVAL_DEPENDENCY_CYCLE=>bureaucratic_overthinker; CONFIDENCE_EVIDENCE_GAP=>misplaced_confidence;
TYPE_CATEGORY_COLLISION=>absurdist; admission+no grounded signal=>no joke; failed template removed no
reroll; comedy never adds unsupported number/date/entity/status/cause/term; factual explanation precedes
comedy.

---

## Component 2: Jargon-Teaching Store
Two read-models: read_models.verified_term_catalog (verified meaning/wording) and
read_models.operator_term_knowledge (per-operator learning state). Agents NEVER directly update either;
they append LEDGER EVENTS; PROJECTORS update the read-models.

VerifiedTermCatalogEntry: { term_id, canonical_surface, aliases[], domain, concept_version(int, ++ on
meaning/scope change), wording_version(int, ++ on wording-only change), precise_definition, eli5_full,
eli5_brief, plain_replacement?, definition_dependencies[term_id], usage_validator_id?, source_refs[],
verification_status: draft|verified|stale|rejected, verified_by, verified_at }. Only verified entries
reach the operator. wording-only edit ++wording_version, doesn't touch operator knowledge. meaning/scope
change ++concept_version; prior-version knowledge must NOT silently transfer.

operator_term_knowledge: PK (operator_id, term_id). { operator_id, term_id, concept_version, status:
unknown|learning|known, status_reason: unseen|first_taught|reinforcement|explicit_ack|
correct_use_threshold|definition_requested|confirmed_misuse|learning_expired|concept_version_changed,
exposure_count, full_teach_count, brief_teach_count, correct_use_count, unprompted_correct_use_count,
explicit_ack_at?, last_exposed_at?, last_taught_at?, last_taught_mode: full|brief|null, last_correct_use_at?,
known_at?, learning_expires_at?, updated_at, row_version, last_applied_event_seq }. Absent row = unknown.
Counters apply to current concept_version.

Status rules: UNKNOWN (never taught / learning expired / concept_version changed & revised concept not
taught). First required use of unknown => FULL eli5; after delivery -> learning, ++exposure, ++full_teach,
last_taught_mode full, learning_expires_at = delivery + 180d (configurable). LEARNING: subsequent use =>
BRIEF; if last_taught_at >= 90d old (configurable) use FULL as refresher; exposure alone never proves
knowledge; returns to unknown after 180d with no exposure/correct-use/ack/def-request. KNOWN via (a)
explicit ack naming/resolving the term, or (b) correct_use_count>=2 AND unprompted_correct_use_count>=1.
Known does NOT decay with time. Known -> learning only on def/refresher request, deterministic-validator
substantive misuse, or concept_version change.

Explicit acks: "Mark idempotency known", "I know what idempotency means", "Stop defining backpressure",
"Do not explain idempotency again" (must unambiguously identify ONE verified term). Bare "Got it/Okay/
Makes sense" does NOT. "Stop explaining <named term>" counts as ack.

Correct-use validation: catalog term may have deterministic usage_validator. Structured ops: validator
confirms use matches catalog concept+constraints. Unstructured prose: an LLM may NOMINATE a candidate +
span, but LLM-only judgment must NOT update the store. A correct-use event commits ONLY when a
deterministic term-specific validator confirms OR operator explicitly acks. (Intentionally undercounts.)

TermRequirement: { term_id, preferred_surface, necessity: required|optional, supporting_fact_ids,
plain_replacement, definition_requested }. required = needed for precision / exact concept / explicitly
requested. Generated from grounded fact types, action schemas, verified domain term maps, explicit
operator requests, reviewed comedy templates. Comedy normally introduces NO new terminology. Persona
renderer must NOT introduce an unplanned technical term.

TermTeachingHint at context_packet.render_hints.term_teaching: { term_id, surface_form, mode: full|brief|
plain|substitute|blocked, supporting_fact_ids, definition_fact_id, allowed_surface_forms, insertion_policy:
after_first_use|replace_with_plain|none }. full=exact full eli5 w/ first use; brief=exact short reminder;
plain=use w/o explanation (known); substitute=replace w/ approved plain language; blocked=no verified
explanation/safe substitute, term cannot appear.

Runtime decision: required unknown=>FULL; required learning & taught<90d=>BRIEF; required learning &
taught>=90d=>FULL refresher; known=>plain; operator asks for def=>FULL regardless; optional & unknown=>
approved plain replacement; catalog missing/stale/rejected/unverified=>substitute plain or block, NEVER
invent a definition.

Effective status: missing row=unknown; record concept_version != catalog version => learning + revised
teaching; learning & expired => unknown; else stored status.

Planner procedure: 1 collect+dedup TermRequirements by term_id; 2 load catalog entry; 3 blocked if no
entry or not verified; 4 load operator knowledge; 5 calc effective status; 6 select mode per runtime
rules; 7 substitute => requirement.plain_replacement then catalog.plain_replacement; 8 full/brief =>
create GROUNDED term-definition fact w/ EXACT approved catalog wording; 9 attach catalog source refs +
version; 10 create TermTeachingHint w/ permitted surface forms; 11 add definition fact via controlled
packet-extension (operational facts unchanged); 12 pass plan to renderer + guard.

Definition grounding: runtime LLM NEVER authors/paraphrases a definition; load exact verified catalog
text, insert deterministically. definition fact: { fact_id, subject_ref=term, predicate=definition,
value=approved wording, source_refs=verified catalog }. Internal terms cite versioned schema/code/source
contract/ADR; standard terms cite primary standard/spec; vendor terms cite official vendor docs. Catalog
build-time validator rejects entries w/ no source refs, circular def deps, alias collisions in same
domain, undeclared technical deps, brief explanations that materially change precise def. If a def depends
on a term the operator doesn't know, teach that dep too or revise to basic vocabulary.

Surface-guard integration: known term => canonical+aliases allowed; unknown/learning => allowed only when
exact required explanation is adjacent to first use; substituted => technical surface not allowed; blocked
=> no catalog surface allowed. Guard rejects internal term IDs, enum/class names, source pointers, schema
paths, machine-contract. On guard fail: remove comedy & re-guard; then replace optional terms w/ plain;
then deterministic plain fallback. Rejected/failed/retried/undelivered text => NO teaching-exposure events.

Ledger events: TERM_TAUGHT_FULL, TERM_TAUGHT_BRIEF, TERM_USED_PLAIN, TERM_ACKNOWLEDGED,
TERM_CORRECT_USE_CONFIRMED, TERM_DEFINITION_REQUESTED, TERM_MISUSE_CONFIRMED, TERM_LEARNING_EXPIRED,
TERM_CONCEPT_VERSION_CHANGED. One delivered reply = one exposure per term (even if it appears multiple
times). Uniqueness: (reply_id, term_id, event_type) for teaching; (operator_turn_id, term_id,
TERM_CORRECT_USE_CONFIRMED) for validated use. Projector ignores event seq <= last_applied_event_seq.

Knowledge update (per event): TAUGHT_FULL -> learning/first_taught, ++exposure,++full_teach, set
last_exposed/taught, mode full, expires=+180d. TAUGHT_BRIEF -> learning/reinforcement, ++exposure,
++brief_teach, mode brief, reset expires +180d. USED_PLAIN -> ++exposure, last_exposed. ACKNOWLEDGED ->
known/explicit_ack, set explicit_ack_at+known_at, clear expires. CORRECT_USE_CONFIRMED -> ++correct_use,
last_correct_use; if not prompted ++unprompted; if correct>=2 & unprompted>=1 -> known/correct_use_threshold,
known_at, clear expires. DEFINITION_REQUESTED -> learning/definition_requested, expires +180d.
MISUSE_CONFIRMED -> learning/confirmed_misuse, expires +180d. LEARNING_EXPIRED -> learning->unknown/
learning_expired, clear expires. CONCEPT_VERSION_CHANGED -> reset to learning for new version, clear prior
ack+correct-use counters, concept_version_changed, require revised teaching. Always update
last_applied_event_seq, updated_at, row_version.

Jargon acceptance tests: unknown required => full; second exposure within interval => brief; exposure
alone never marks known; named ack marks known; 2 validated correct uses (>=1 unprompted) marks known;
known doesn't decay with time; concept-version change returns known->learning; wording-version change
doesn't alter status; unverified/stale/missing/rejected term can't pass guard; optional unknown replaced
w/ plain; failed/rejected/retried/undelivered reply doesn't update counts; term x5 in one reply = 1 exposure.

---

## Component 3: Self-Healing Claim Detector
Receives operator question + the FINAL free-text answer. Identifies 0+ DIRECT factual claims that map to
known claim types, have extractable typed values, resolve to one entity + one time scope, and can be
checked vs a specific grounded read-model/ledger snapshot. It does NOT decide truth (check_agent_claim is
the authority: pass/fail/indeterminate). It does NOT rewrite/deploy/alter prompts. A confirmed FAIL may
only create a SUPERVISED heal task.

Precision-first: false negatives OK, false positives NOT. Ignore vague claims, predictions, opinions,
recommendations, approximate statements, unsupported comparisons, ambiguous entity refs, ambiguous time
scopes, unavailable historical snapshots, claims not mapping to a registered type. RULE: no candidate =>
no audit; no unambiguous truth source => no audit; audit pass => no heal; uncertainty at any stage => no
heal. Only a narrow explicitly-validated subset is heal-eligible; everything else abstains.

Claim-type registry (NO generic count/status/date; encode semantics): e.g. project.open_task_count.v1,
project.status.v1, finance.invoice_total.v1, finance.outstanding_balance.v1, schedule.event_start.v1,
schedule.due_date.v1, operations.queue_depth.v1, operations.agent_health_status.v1, artifact.file_count.v1,
deployment.release_version.v1. ClaimTypeSpec: { claim_type, description, value_kind: integer|money|
percentage|date|datetime|status|boolean|version|string_enum, entity_kind, allowed_status_values, aliases
(wording->canonical), deterministic_patterns, truth_source_adapter, comparison_policy: exact|currency_exact|
datetime_exact|tolerance, tolerance(null unless registered), max_truth_age_seconds, historical_snapshot_required,
registry_version }. LLM may choose only among allowed claim_type values; never a table/stream/class/adapter id.
Truth-source mapping is explicit/deterministic/reviewed/versioned; semantic/source change => new claim-type
version.

BoundTruthSource (before check_agent_claim): { claim_type, entity_ref, as_of, source_ref, source_revision,
observed_at, freshness_status, adapter, historical_snapshot_exists }. Then call check_agent_claim(agent_id,
candidate.claim_type, candidate.normalized_value, BoundTruthSource).

Time-of-check safety: fast-changing facts (queue depth, agent health, active jobs, deploy status, open
tasks) audited vs state WHEN ANSWER PRODUCED. Resolution order: 1 exact source revision from the original
packet; 2 historical read-model snapshot as of reply timestamp; 3 replay ledger as of reply timestamp.
Never audit an old response vs the latest value. No time-correct snapshot => unknown => no heal.

DetectedClaim: { detector_version, reply_id, agent_id, claim_type, normalized_value, value_surface,
entity_ref, entity_surface, temporal_scope, assertion_span{text,start,end}, assertion_kind: direct|quoted|
hypothetical|forecast|recommendation|ambiguous, polarity: positive|negative, extraction_route: deterministic|
llm_assisted, extraction_confidence, supporting_fact_ids, registry_version }. Only assertion_kind=direct is
heal-eligible in v1.

Deterministic prefilter: split answer into sentences w/ char offsets; low-cost cue scan (digits, number
words, currency symbols/codes, %, dates, times, registered status vocab, boolean vocab, version strings,
registered count nouns). No cue => no LLM. Cue scan broad (only decides whether to parse more).

Deterministic extraction: COUNT ("There are X registered items", "Entity has X registered items", etc;
noun must resolve to a registered semantic metric; number words ok if unambiguous). STATUS ("Entity is
<registered-status>"; resolve via alias map; unregistered adjectives not auditable). MONEY ("The invoice
total is <amount>"; normalize to currency code + integer minor units; NO binary float; unresolved currency
=> reject). DATE/DATETIME ("Entity is due on <date>"; ISO 8601; datetime needs explicit/unique tz; relative
dates via reply timestamp+operator tz; "soon/around Friday" => reject). PERCENTAGE (integer basis points /
fixed-decimal; "nearly complete" reject; no binary float). BOOLEAN ("Feature is enabled"; registered
entity+type; avoid negated/conditional/nested; "not necessarily disabled" reject).

Assertion filtering: reject hedging/modality (maybe, probably, possibly, approximately, roughly, about,
around, I think, it appears, it seems, should, could, might, likely); reject questions, quoted speech,
hypotheticals, recommendations, conditions, predictions, metaphors, example-only values. "Niles said there
were five jobs" = quoted => no claim. Distinguish a direct assertion from a sentence that merely contains a
factual-looking number.

Entity resolution order: 1 explicit name in assertion; 2 verified aliases in packet; 3 operator question
only if exactly one entity of the required kind in scope; 4 pronoun only if antecedent unambiguous. "Atlas
and Beacon... They have 12" => ambiguous => no audit/heal. Never ask LLM to guess between entities.

Deterministic vs LLM-assisted: deterministic covers canonical counts/statuses/currency/exact dates/
percentages/booleans/versions. LLM-assisted ONLY for varied phrasing w/ strong cues that missed deterministic
grammar (e.g. "Atlas is sitting on twelve unfinished tasks"). LLM receives ONLY: operator question, relevant
answer sentences, restricted applicable claim types, visible entity aliases. LLM must NOT receive truth
values/read-model contents/expected values/audit outcomes. Output constrained to { decision: auditable|
not_auditable|ambiguous, claim_type, exact_span, value_surface, entity_surface, time_scope_surface,
assertion_kind, hedged, confidence }. Span must be exact substring; value reparsed deterministically from
span (LLM value not in text => invalid); entity must pass deterministic resolution.

LLM cost gate: no cue => 0 LLM calls; cue sentence not handled deterministically => <=1 extraction call/reply;
suspicious LLM candidate after audit => <=1 verifier call; <=3 candidate sentences to extractor; <=5 detected
claims/reply; timeout/malformed/schema-violation/missing-span/failure => abstain.

LLM modes: config llm_claim_queue_mode = shadow|verified, DEFAULT shadow. shadow: LLM candidates recorded/
scored/compared for eval, may NOT queue heals; mine shadow data for repeated forms to add to deterministic
grammars. Promote (claim-type, prompt, model) bucket to verified only after >=1000 human-reviewed examples,
lower bound of 95% precision CI >= 99.5%, no systematic entity/temporal failure. Verified requires extractor
+ independent verifier agreement (claim type, value, entity, time scope, direct). Per-instance: extractor
conf >=0.98, verifier >=0.99. Self-reported LLM confidence never sufficient alone.

Candidate-validation gate (audit-eligible): claim type in registry; span exact substring; value parses
deterministically; value type matches; entity resolves uniquely; time scope resolves uniquely; direct; not
hedged; truth-source adapter resolves; snapshot fresh/historically-correct; comparison policy available.
Heal-eligible (additional): check_agent_claim returns FAIL (not unknown/error); diff exceeds registered
tolerance if any; truth-source revision recorded; route queue-enabled; LLM candidate passed independent
verification; no equivalent heal already queued.

Comparison: counts exact int eq; money matching currency + exact minor-units eq; status exact eq after alias
norm; dates exact normalized eq; datetimes exact instant eq unless registered tolerance; percentages exact
fixed-decimal/registered tolerance; versions exact normalized eq. Never invent/widen tolerances on demand.

Packet cross-check (fault domain): packet has correct value, answer differs => renderer_mutation; packet has
same wrong value => packet_value_error or source_mapping_error; packet has no corresponding fact =>
ungrounded_assertion; packet has answer value + audit passes => grounded+correct. A TRUE-but-unsupported
claim is NOT a factual heal (value not wrong) -> separate grounding-policy violation (OpenClaw prohibits
unsupported claims even when true). Do NOT mix grounding violations into the factual heal queue.

HealTask: { heal_task_id, idempotency_key, reply_id, agent_id, claim_type, entity_ref, temporal_scope,
assertion_span, claimed_value, truth_value, truth_source_ref, truth_source_revision, audited_at, detector_route,
detector_policy_version, fault_domain: renderer_mutation|ungrounded_assertion|packet_value_error|
source_mapping_error|unknown, status: awaiting_review|candidate_proposed|rejected|approved|stale }.
idempotency_key from (reply_id, claim_type, entity_ref, normalized claimed value, truth-source revision).
Worker REPEATS the audit before proposing; if source changed / audit not reproducible => stale. Worker may
propose renderer constraint / prompt correction / missing packet-field mapping / deterministic claim grammar
/ read-model adapter fix / surface-guard rule. Worker NEVER auto-deploys.

Detector procedure: 1 split into sentences w/ offsets; 2 cue prefilter; 3 deterministic parsers on cue
sentences; 4 validate spans/types/entity/assertion-kind/hedging/time-scope/registry membership; 5 dedup; 6
identify unmatched cue sentences; 7 if budget, <=3 unmatched to restricted LLM extractor; 8 validate each LLM
candidate (exact span, value in span, reparses, entity resolves, type allowed); 9 merge+dedup; 10 skip
non-eligible; 11 bind each eligible to truth source (type, entity, time scope, packet source revision); 12
skip if no historical snapshot; 13 call check_agent_claim; 14 pass => no action; 15 abstain on unknown/error/
stale/non-explicit-fail; 16 LLM-assisted fail => require llm_claim_queue_mode verified else shadow-only; 17
queue-eligible LLM candidate -> independent verifier; 18 abstain unless verifier agrees + meets gate; 19
packet cross-check fault domain; 20 create idempotent HealTask; 21 queue for SUPERVISED review.

Detector acceptance tests: correct claim never queues; ambiguous entity never queues; vague/hedged/
conditional/quoted/hypothetical/recommended/forecast never queues; stale/temporally-mismatched source never
queues; past current-state claim not audited vs latest unless as-of snapshot; LLM-only candidate can't queue
in shadow; LLM timeout/malformed/invalid-span/schema-fail => abstain; LLM value not in span => rejected;
deterministic count w/ unique entity + time-correct source queues only after check_agent_claim FAIL; duplicate
detections => one idempotent heal; every queued heal includes exact span/typed claimed value/typed truth
value/source revision/route/policy version/confirmed fail; every worker repeats audit before proposing; no
candidate fix auto-deployed.

---

## Combined Integration Flow
On operator turn: first detect term acks/def-requests/validated-uses in input, append+project learning events
BEFORE planning the reply. Build deterministic packet. Run comedy gate (owns zero-error/hang/rank/golden-ratio).
ComedyArchetypeSeeder (adds hint, not facts). Collect TermRequirements. JargonTeachingPlanner (loads knowledge,
adds verified def facts, surface allowances). PersonaRenderer (structure/voice; every assertion traces to a
fact). TermSurfaceRealizer (insert exact verified defs/reminders). ComedyRealizer (insert reviewed diagnostic
line if enabled). operator_surface_guard (reject raw JSON/hashes/paths/internal fields/class names/unknown
terminology/missing explanations/machine-contract). On reject: remove comedy & retry; then optional terms ->
plain; then deterministic fallback. Claim detector on EXACT guarded answer (bind time-correct sources, call
check_agent_claim). Confirmed wrong => supervised heal task; detector never rewrites/deploys. Delivery policy
may suppress a synchronously-confirmed-wrong answer (separate decision); detector never generates an ungrounded
replacement. After confirmed delivery, create term exposure events from the DELIVERED text only (not rejected
drafts/failed gens/removed text).
