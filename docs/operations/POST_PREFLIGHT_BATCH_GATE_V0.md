# Post-Preflight Batch Gate v0

## Purpose

After preflight, OpenClaw lanes should move real operator work while improving
shared substrate. The gate prevents drift into abstract preparation, vague
modularity work, or ungated authority expansion.

Operator-facing language may call this the Briar Patch Batch Gate. The machine
contract is `post_preflight_batch_gate_v0`.

## Rule

One batch must pair:

- one named real operator workflow, and
- one reusable substrate improvement, and
- one workflow proof output.

The batch must be grouped by a shared bottleneck, not a vague theme.

## Structured Gate Object

A proposed post-preflight lane must be represented with:

| field | meaning |
| --- | --- |
| `lane_name` | Proposed lane name. |
| `lane_summary` | Bounded one-lane summary. |
| `named_operator_workflow` | The real workflow improved within one prompt. |
| `shared_bottleneck` | The concrete bottleneck the batch addresses. |
| `steel_thread_contract_link` | Existing steel-thread contract/read-model/proof reused or strengthened. |
| `reusable_substrate_improvement` | The reusable improvement made while serving the workflow. |
| `workflow_proof_output` | Review packet, read-model, proof, Mission Control surface, or other workflow output. |
| `detangling_scope` | Whether detangling serves this lane directly and stays opportunistic. |
| `module_split_disposition` | Whether a split is unnecessary now or recorded as future work. |
| `authority_change_requested` | Any requested send, submit, runtime, approval, deployment, model, or tool authority. |
| `authority_gate_required` | Whether a separate explicit authority gate is required. |
| `expected_artifacts` | Expected read-models, packets, tests, proofs, receipts, or surfaces. |
| `validation_required` | Focused tests and validation commands. |
| `gate_status` | `pass` or `fail`. |
| `failure_reasons` | Deterministic blockers. |
| `recommendation` | Next safe action. |

## Gate Questions

1. Does this lane unlock or improve a named real operator workflow within one prompt?
2. Does it reuse or strengthen the steel-thread contract?
3. Is the batch grouped by a shared bottleneck, not a vague theme?
4. Does any modular detangling serve the lane directly?
5. If a module split is discovered but not needed now, is it recorded as structured future work?
6. Does the lane avoid new send/submit/runtime/approval authority unless explicitly gated?
7. Is the expected output a read-model, packet, Mission Control surface, test/proof, or real workflow improvement?

## Defaults

- `abstract_prep_allowed_without_workflow=false`
- `batch_by_shared_bottleneck=true`
- `one_batch_reusable_substrate_plus_workflow_proof=true`
- `module_extraction_added=false`
- `client_repo_generation_added=false`
- `runtime_authority_added=false`
- `send_or_submit_authority_added=false`
- `customer_deployment_authority_added=false`

## Detangling Rule

Detangle opportunistically inside real lanes. If a module split is discovered
but not needed to complete the named workflow proof, record it as structured
future work. Do not turn it into a blocking extraction detour.

## Current Read-Model Surface

- `post_preflight_batch_gate.py`
- `generated/read_models/post_preflight_batch_gate.json`
- `generated/read_models/post_preflight_batch_gate_OPERATOR.md`

## Next Safe Lane

Run this gate against the next proposed post-preflight lane before coding.
