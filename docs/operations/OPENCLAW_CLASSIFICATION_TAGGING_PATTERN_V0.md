# OpenClaw Classification / Tagging Pattern v0

## Purpose

OpenClaw already has several local-first classification surfaces. This note
names the shared pattern so future ingest, source triage, module selection,
Markdown classification, Project Capsule planning, and agent work packets do
not grow incompatible vocabularies.

This is doctrine only. It does not create a new ontology framework, import
data, reclassify the repo, activate runtime behavior, or grant authority.

## Existing Classification Surfaces

| surface | main vocabulary role |
| --- | --- |
| `corpus_atlas.py` | Source role, freshness, canonicality, world binding, sensitivity, retrieval eligibility, ingestion eligibility, evidence category, reorg bucket. |
| `markdown_knowledge_atlas.py` | Markdown document role, freshness status, reorg status, sensitivity status, retrieval policy, world/module topic. |
| `generated/read_models/markdown_evidence.json` | Approved evidence excerpts, document role, freshness, retrieval policy, sensitivity, world binding, parsed-evidence-not-truth posture. |
| `module_registry.py` | Module id/status, world/category, capability scope, authority level, sensitivity policy, no-go data classes, client-safe/core-only posture. |
| `bundle_blueprint_planner.py` | Target context, selected/missing/blocked modules, sensitive-data policy, report-bridge policy, local-only requirements. |
| `project_capsule.py` | Project/client/capsule identity, world links, tools, data boundaries, approval status, deployment/runtime posture. |
| `context_selection.py` | Evidence labels, retrieval/ingestion allowlists, sensitivity exclusions, world binding, context-for-reasoning-only posture. |
| `tool_inventory.py` and `tool_intake.py` | Tool category, candidate/install/integration/approval status, fit/risk labels, operator-review requirement, no-authority posture. |
| `governed_intake_spine.py` | Source metadata, deterministic intent category, route status, agent/lane route, Work Board/packet projection, no-execution posture. |
| `estate_read_model.py` | Node/capsule/corpus/module/read-model posture with authority flags and redacted path handling. |
| `cassandra_chief_memory_authority.py` | Memory source category/type, sensitivity/trust/evidence status, recommended fate, retention/raw-content policies, allowed agent use, approval and no-authority flags. |

## Shared Axes

Use these axes before inventing new names:

| axis | preferred field names | purpose |
| --- | --- | --- |
| Stable identity | `source_id`, `module_id`, `project_id`, `capsule_id`, `tool_id`, `intent_id`, `packet_id` | Lets records link without treating labels as identity. |
| Location/reference | `source_ref`, `source_path`, `relative_path`, `path_hash`, `source_path_hash` | Points to evidence without exposing private raw paths when unsafe. |
| Domain/module | `world`, `world_binding`, `category`, `source_category`, `module_topic` | Places work in a reusable OpenClaw world/module lane. |
| Type/role | `source_type`, `source_role`, `document_role`, `tool_category`, `packet_kind` | Describes what the thing is. |
| Lifecycle/status | `status`, `candidate_status`, `import_status`, `freshness_status`, `freshness_label`, `canonicality` | Describes where the thing is in review/use. |
| Sensitivity | `sensitivity_label`, `sensitivity_status`, `sensitivity_level`, `sensitive_input_policy`, `no_go_data_classes` | Decides what may be read, summarized, exported, or blocked. |
| Evidence/trust | `evidence_status`, `evidence_label`, `evidence_category`, `trust_status`, `truth_status`, `parsed_evidence_not_truth` | Prevents evidence from becoming truth without confirmation. |
| Ingest/retrieval | `ingestion_eligibility`, `retrieval_eligibility`, `retrieval_policy`, `raw_content_policy` | Separates discovery, metadata, retrieval, and import authority. |
| Fate/disposition | `recommended_fate`, `reorg_bucket`, `suggested_bucket`, `blocked_reason`, `next_safe_move` | Makes the next action reviewable and non-magical. |
| Authority | `runtime_authority`, `send_allowed`, `network_authority`, `tool_execution_allowed`, `no_send_authority`, `no_runtime_authority` | Makes permissions explicit and false by default. |
| Review/approval | `approval_required`, `requires_operator_review`, `operator_confirmation_required`, `approval_status` | Routes ambiguous or risky records to humans instead of execution. |
| Read-model posture | `schema_version`, `read_model_version`, `source_basis`, `counts_by_*`, `operator_review_buckets` | Makes generated review packets deterministic and auditable. |

## Fate Vocabulary

`recommended_fate` is useful when the question is "what should happen to this
source next?" Use the Cassandra/Chief fate vocabulary for source-triage lanes:

- `import_structured_facts_to_sqlite`
- `register_as_evidence_source_only`
- `summarize_or_extract_only`
- `block_no_go`
- `delete_local_residue`
- `defer_operator_review`

This does not replace `ingestion_eligibility`, `retrieval_eligibility`,
`reorg_bucket`, or module `status`. It complements them:

- `ingestion_eligibility` says whether content may be ingested.
- `retrieval_eligibility` says whether content may be retrieved for context.
- `reorg_bucket` says where a file belongs structurally.
- `status` says lifecycle posture.
- `recommended_fate` says the next reviewed disposition.

## Operator Review Buckets

Human-facing packets should stay simple:

1. Safe to structure later
2. Keep as evidence source only
3. Block / do not trust
4. Delete local residue candidate
5. Needs operator decision

Every bucket should answer:

- what is this?
- why does it matter?
- what can safely happen next?
- what should not be trusted?
- what needs operator decision?

## Drift Risks To Avoid

- Do not create a new `classification_status` if an existing `status`,
  `freshness_status`, `evidence_status`, or `recommended_fate` answers the
  question.
- Do not treat `source_category`, `evidence_category`, `tool_category`, and
  module `category` as the same field. They are related, but scoped.
- Do not use `trusted`, `approved`, or `confirmed` unless the record has an
  explicit operator/receipt basis.
- Do not let a read-model field imply authority. Authority flags must stay
  explicit and false by default.
- Do not promote generated snapshots, legacy logs, or old HITL files into truth
  without a separate confirmation/import lane.

## Extraction Recommendation

Do not extract a shared Python framework yet.

The current surfaces are converging well enough with local constants and tests.
The next low-friction move is to keep this docs-only pattern and add small tests
when a lane introduces a new classification-heavy surface. Extract shared
constants or a dataclass later only if two or more active modules need the same
controlled vocabulary at runtime.
