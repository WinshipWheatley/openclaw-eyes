# Recent File Context Read-Model v0

What this is:
- A generated read-model over `recent_file_*` SQLite rows.
- It resolves vague file references against File Event Queue metadata.

What this is not:
- It is not file ingestion, file editing, raw private content access, agent activation, or execution.

Summary:
- Latest run: `recent_file_context_6bf8721b210138c3662e`.
- Candidates: 100.
- Queries: 0.
- By kind: markdown_doc=7, source_code=7, unknown=86.
- By world: security=13, unknown=87.
- Metadata-only candidates: 88.
- Agent-readable candidates: 12.
- No-go boundary candidates: 13.

Next safe move:
- Use this metadata to route intent or ask a clarifying question; do not open raw private files or execute actions.

Authority boundary:
- raw_content_read=false; raw_body_stored=false; file_move_allowed=false; file_delete_allowed=false.
- runtime_authority=false; agent_activation_allowed=false; tool_execution_allowed=false; network_authority=false.
