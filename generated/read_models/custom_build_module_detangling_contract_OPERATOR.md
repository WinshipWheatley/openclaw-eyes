# Custom Build Module Detangling Contract v0

What this is:
- A deterministic planning contract for future friend/client/company custom-build lanes.
- It forces each custom build to ask whether a needed OpenClaw capability should be split, paired, gated, client-only, or later used to replace a tangled Core section.

What this is not:
- It is not client repo generation, deployment, runtime activation, physical module extraction, send authority, or automatic OpenClaw Core replacement.

Summary:
- Synthetic assessments: 3.
- Variant shapes: client_only_extracted_module=1, gated_module=2, paired_module=2, standalone_smaller_module=1.

Synthetic cases:
- `moddetangle_e0724f010350c6612060`: Synthetic Cassandra-only helper
  - minimum module: `cassandra_clara_fact_intake` (standalone_smaller_module)
  - recommendation: `plan_standalone_receive_only_module_first`
  - client safe by default: `false`
  - core replacement automatic: `false`
- `moddetangle_ed70f2959542e0feb09d`: Synthetic Cassandra plus Chief planning helper
  - minimum module: `cassandra_chief_planning_pair` (paired_module)
  - recommendation: `define_paired_module_contract_then_synthetic_work_packet_proof`
  - client safe by default: `false`
  - core replacement automatic: `false`
- `moddetangle_2a520b74b8d47c3c26f6`: Synthetic Report Bridge client status helper
  - minimum module: `report_bridge_sanitized_summary` (client_only_extracted_module)
  - recommendation: `keep_as_reusable_sanitized_bridge_contract`
  - client safe by default: `false`
  - core replacement automatic: `false`

Boundary:
- `physical_module_extraction_added=false`.
- `client_repo_generation_added=false`.
- `runtime_authority=false`; `send_or_submit_authority=false`; `customer_deployment_authority=false`.
- All examples are synthetic; no real client data is used or copied.

Next safe lane: Custom Build Module Detangling Intake Gate
