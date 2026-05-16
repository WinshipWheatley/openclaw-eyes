# Cassandra/Chief Memory Authority Read-Model v0

What this is:
- Metadata-only SQLite schema and source-catalog visibility for Cassandra/Chief memory authority.

What this is not:
- It is not data import, runtime authority, send authority, Repo B execution, or approval authority.

Summary:
- Sources cataloged: 15.
- Structured-fact candidates: 5.
- Blocked sources: 1.
- Deferred sources: 2.
- Delete-residue candidates: 1.
- Fates: block_no_go=1, defer_operator_review=2, delete_local_residue=1, import_structured_facts_to_sqlite=5, register_as_evidence_source_only=2, summarize_or_extract_only=4.

Boundary:
- Old files are import candidates or evidence references, not truth.
- Old HITL JSON/JSONL is blocked as active approval authority.
- No raw private contents were imported.
- `send_allowed=false`; `runtime_authority=false`; `repo_b_execution_allowed=false`.

Next Safe Move:
- Operator-reviewed Cassandra/Chief structured import plan.
