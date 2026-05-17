# Custom Build Module Detangling Contract v0

## Purpose

Future custom builds must reduce OpenClaw modular debt instead of copying
tangles forward.

When a friend, client, company, or internal custom build needs an OpenClaw
capability, the first step is a module-detangling assessment. The assessment
decides whether the needed capability should become a standalone smaller
module, a paired module, a gated module, a client-only extracted module, or a
candidate replacement for part of OpenClaw Core.

This contract is planning substrate only. It does not generate a client repo,
extract physical modules, deploy anything, run Repo B, read private files, or
grant runtime/send/customer authority.

## Required Assessment Fields

Every future custom-build lane that reuses OpenClaw capability must produce a
machine-readable assessment with:

| field | meaning |
| --- | --- |
| `requested_custom_build` | Synthetic or operator-provided use case summary; no raw client/private body text. |
| `capability_needed` | Bounded capability required by the custom build. |
| `current_source_module_locations` | Current Repo A files/modules where the capability exists or is tangled. |
| `current_tangle_dependencies` | Chief, Cassandra, Guardian, memory, loops, senders, or other dependencies that make extraction risky. |
| `minimum_viable_extracted_module` | Smallest useful module shape that avoids copying unnecessary tangle. |
| `possible_module_variants` | Standalone, paired, gated, client-only, or Core-replacement candidate variants. |
| `private_data_risk` | Private/client/no-go data risk. |
| `authority_risk` | Runtime, send, approval, deployment, or external-action risk. |
| `runtime_dependency_risk` | Listener, scheduler, watcher, model, service, credential, or Repo B dependency risk. |
| `client_suitability` | Explicit suitability posture; never granted by default. |
| `openclaw_core_replacement_potential` | Whether the cleaner module might later replace tangled Core behavior; never automatic. |
| `migration_recommendation` | Next planning or implementation lane. |
| `validation_required_before_adoption` | Tests/proofs required before selection, extraction, or Core adoption. |

## Variant Shapes

- `standalone_smaller_module`: the cleanest useful slice can stand alone.
- `paired_module`: two capabilities are legitimately intertwined and should be
  packaged together, such as Cassandra + Chief planning.
- `gated_module`: the capability can exist only behind Guardian/HITL approval.
- `client_only_extracted_module`: useful for a client/local deployment but not
  necessarily a Core replacement.
- `openclaw_core_replacement_candidate`: a cleaner module may later replace a
  tangled Core section, after equivalence and authority proofs.

## Authority Defaults

Every detangling assessment defaults to:

- `physical_module_extraction_added=false`
- `client_repo_generation_added=false`
- `repo_b_execution_allowed=false`
- `private_data_copy_allowed=false`
- `customer_deployment_authority=false`
- `runtime_authority=false`
- `tool_execution_authority=false`
- `model_execution_authority=false`
- `send_or_submit_authority=false`
- `openclaw_core_replacement_automatic=false`

## Future Lane Rules

Custom-build lanes must not copy a tangled OpenClaw file tree directly into a
client or friend project. They must first identify the smallest safe module
shape and prove its boundaries with synthetic fixtures.

Client suitability is not inherited from local usefulness. It requires explicit
proof that private/client data stays out of OpenClaw Core, credentials are not
copied, sends are not authorized, and tenant configuration is separated from
Winship's personal system.

OpenClaw Core replacement is never automatic. A new module can become a Core
replacement candidate only after behavior equivalence, authority-boundary,
receipt, rollback, and operator-review proofs.

## Current Read-Model Surface

The deterministic contract lives in:

- `custom_build_module_detangling_contract.py`
- `generated/read_models/custom_build_module_detangling_contract.json`
- `generated/read_models/custom_build_module_detangling_contract_OPERATOR.md`

The initial read-model contains only synthetic examples:

- Cassandra-only helper
- Cassandra + Chief planning helper
- Report Bridge client status helper

## Next Safe Lane

`Custom Build Module Detangling Intake Gate`

That lane should add an intake/check command that requires this assessment
before any custom-build scaffold, repo generation, module extraction, or Core
replacement proposal proceeds.
