# Estate Read-Model v0

What this is:
- Metadata-only topology visibility over existing OpenClaw Core primitives.

What this is not:
- It is not a new Estate Registry schema, runtime authority, deployment authority, repo split, send path, private-data export, or Mission Control UI change.

Core / Node Schema:
- Static node schema available: `true`.
- Live node records proven: `false`.
- Schema tables summarized: 5.

Corpus Roots:
- Status: `ok`.
- Roots: 7.

Project Capsules:
- Status: `ok`.
- Capsules: 1.

Modules:
- Modules: 8.
- Status counts: approved=2, available_planning=8, blocked=1, draft=5, future_gated=1.

Generated Read-Models:
- Safe files: 69.
- Self export files are excluded from generated read-model inventory to avoid self-invalidating output.

Mac Mirror:
- Mac roots: 3.
- Missing expected generated read-model files: 7.
- Hash mismatches: 2.

Gaps:
- openclaw_nodes live row helper is not proven; estate view uses static schema metadata only
- Mac generated read-model mirror is missing expected generated read-model files

Authority Boundary:
- `estate_registry_schema_created=false`; `runtime_authority=false`; `repo_split_allowed=false`.
- `raw_data_visibility=false`; `client_private_contents_exported=false`; `send_allowed=false`.
- This is read-model visibility only, not authority.

Next Safe Move:
- Mission Control module/bundle visibility.
