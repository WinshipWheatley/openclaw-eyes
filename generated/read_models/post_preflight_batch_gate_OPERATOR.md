# Briar Patch Batch Gate

Machine contract: `post_preflight_batch_gate_v0`.

What this does:
- Checks proposed post-preflight lanes before they drift into abstract prep or vague modularity work.
- Requires one reusable substrate improvement plus one named real operator workflow proof.
- Records module split pressure as future work when extraction is not needed now.

What this does not do:
- No module extraction, client repo generation, runtime activation, sends, submits, deployment, or approval authority.

Summary:
- Examples: 4.
- Status counts: fail=2, pass=2.
- Failure counts: detangling_became_mandatory_prep_detour=1, missing_expected_artifacts=1, missing_named_operator_workflow=1, missing_steel_thread_contract_link=1, missing_validation_required=1, missing_workflow_proof_output=1, shared_bottleneck_is_vague_theme=1, ungated_authority_expansion_requested=1.

Examples:
- `Generic Review Packet Reuse for Capital Hilton Followup` -> `pass`
  - workflow: `Capital Hilton manual invoice review`
  - bottleneck: `review_packet_schema_reuse`
  - recommendation: `proceed_with_bounded_post_preflight_lane`
- `Abstract Module Prep Sprint` -> `fail`
  - workflow: `missing`
  - bottleneck: `modularity`
  - recommendation: `stop_until_lane_names_real_operator_workflow`
  - failures: missing_named_operator_workflow, shared_bottleneck_is_vague_theme, missing_steel_thread_contract_link, missing_workflow_proof_output, missing_expected_artifacts, missing_validation_required, detangling_became_mandatory_prep_detour
- `Cassandra Intake to Niles Album Review Packet` -> `pass`
  - workflow: `Niles album progress review`
  - bottleneck: `governed_receive_to_review_packet_projection`
  - recommendation: `proceed_with_lane_and_record_module_split_for_future_work`
- `Ungated Send and Deployment Shortcut` -> `fail`
  - workflow: `Capital Hilton invoice review`
  - bottleneck: `review_packet_to_external_action`
  - recommendation: `stop_and_create_explicit_authority_gate_lane`
  - failures: ungated_authority_expansion_requested

Boundary:
- `abstract_prep_allowed_without_workflow=false`.
- `module_extraction_added=false`; `client_repo_generation_added=false`.
- `runtime_authority_added=false`; `send_or_submit_authority_added=false`; `customer_deployment_authority_added=false`.

Next safe lane: Run Post-Preflight Gate On Next Lane
