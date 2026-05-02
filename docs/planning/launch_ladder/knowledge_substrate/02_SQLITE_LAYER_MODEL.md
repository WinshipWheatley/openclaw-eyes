# SQLite Layer Model

Status: conceptual planning model only. This file does not define a production schema, migration, API, ingestion job, or database file.

## First Principle

SQLite is the canonical local memory substrate. Markdown is an export/handoff surface. HTML/rich fragments preserve source shape where structure matters. FTS5/search finds relevant records quickly. Compiled notes make recurring knowledge useful.

This is not vanilla RAG. It is a compile-first knowledge substrate inspired by Karpathy-style LLM Wiki thinking.

## Conceptual Layers

| Layer/table | Intended role | Required fields conceptually | Must not imply |
| --- | --- | --- | --- |
| `source_files` | Records discovered source artifacts without interpreting them. | `source_id`, `source_uri_or_local_ref`, `source_kind`, `source_hash`, `size`, `modified_at`, `discovered_at`, `sensitivity_level`, `withheld_reason`, `operator_scope`. | Discovery does not mean permission to read, summarize, export, or call a model. |
| `extracted_text` | Stores parsed text derived from a source file. | `extraction_id`, `source_id`, `extractor_name`, `extracted_at`, `text_hash`, `plain_text_ref`, `warnings`, `quality`, `evidence_ref`. | Extraction does not mean correctness, completeness, or safe export. |
| `rendered_fragments` | Preserves shape for pages, tables, images, emails, contracts, invoices, and structured artifacts. | `fragment_id`, `source_id`, `extraction_id`, `fragment_kind`, `html_ref`, `plaintext_ref`, `page_or_region`, `rendered_at`, `shape_warning`. | A rendered fragment is not a claim and not an approval to display private content outside local scope. |
| `artifact_classifications` | Labels artifacts by type, sensitivity, and likely workflow relevance. | `classification_id`, `source_id`, `artifact_type`, `sensitivity_level`, `confidence`, `basis`, `classified_at`, `review_state`. | Classification does not make a sensitive artifact safe and does not make a claim true. |
| `entities` | Stores people, companies, projects, works, contracts, dates, accounts, and other named objects. | `entity_id`, `entity_type`, `canonical_label`, `aliases`, `source_basis`, `confidence`, `sensitivity_level`. | Entity extraction does not prove identity or relationship. |
| `entity_links` | Connects entities to sources, fragments, claims, and compiled notes. | `link_id`, `entity_id`, `target_kind`, `target_id`, `relationship_type`, `evidence_ref`, `confidence`, `review_state`. | A link is an evidence-backed hypothesis unless promoted. |
| `claims` | Stores bounded statements with evidence and confidence. | `claim_id`, `claim_text`, `claim_type`, `source_basis`, `evidence_refs`, `confidence`, `created_at`, `contradiction_state`, `review_state`. | Claims are not truth by default and must not become status copy without evidence/freshness proof. |
| `compiled_notes` | Durable operator-readable interpretation made from evidence and claims. | `note_id`, `title`, `markdown_body`, `source_basis`, `claim_refs`, `evidence_refs`, `confidence`, `created_at`, `updated_at`, `limitations`. | Compiled notes are interpretation, not truth, and not operator acceptance. |
| `freshness` | Tracks stale conditions, refresh triggers, timestamps, hashes, and source commits. | `freshness_id`, `target_kind`, `target_id`, `source_basis`, `timestamp_or_commit`, `stale_conditions`, `refresh_trigger`, `state`. | Freshness is scoped to one target and must not imply system health or current runtime state. |
| `operator_promotions` | Records explicit operator decisions about what to accept, reject, mark historical, mark sensitive, or exclude. | `promotion_id`, `target_kind`, `target_id`, `decision`, `operator`, `decided_at`, `scope`, `reason`, `expiry_or_review_date`. | Promotion does not broaden authority beyond its named scope. |
| `conversation_packets` | Creates safe handoff/context packets for chat or app review. | `packet_id`, `purpose`, `included_note_refs`, `included_claim_refs`, `withheld_surfaces`, `sensitivity_summary`, `freshness_snapshot`, `operator_scope`. | A packet is not approval for execution or external model use. |
| `audit_events` or `substrate_events` | Records substrate-side planning and review events. | `event_id`, `event_type`, `target_kind`, `target_id`, `created_at`, `actor`, `reason`, `evidence_ref`. | Events do not prove success unless paired with validation evidence. |

## Search And Compilation

FTS5/search should find candidate source files, extracted text, rendered fragments, claims, and compiled notes. Search ranking is not authority. A high-ranked result is still only a candidate.

Compilation should create durable notes that cite evidence, state confidence, name contradictions, and expose limitations. Recurring knowledge becomes useful only after it is compiled and reviewed.

## Export Surfaces

Markdown exports should be optimized for human review, ChatGPT Project handoff, and source-set refresh. They must not become the database authority.

HTML/rich exports should preserve source shape when layout matters. They must not hide sensitivity, confidence, evidence, or stale warnings.

## Implementation Guardrail

This file deliberately stops at conceptual layers. Do not create migrations, SQL DDL, ingestion scripts, fixture loaders, API routes, or app storage code from this slice.
