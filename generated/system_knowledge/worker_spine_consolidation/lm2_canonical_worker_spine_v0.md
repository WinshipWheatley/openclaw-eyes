# LM2 Canonical Worker Spine

Status: OPENCLAW_LM2_CANONICAL_WORKER_SPINE_CONSOLIDATION_READY

LM2 is the spawned advisory/worker layer: a bounded model/worker instance receives a deterministic package with goal, sources, standard, permission boundary, proof requirement, expected output schema, and stop condition. It has no direct runtime authority.

## Canonical Runtime Spine
- File: `codex_work_package_lifecycle.py`
- SQLite registry: `generated/system_knowledge/codex_work_package_lifecycle.sqlite`
- CLI: `scripts/openclaw_run.py`
- Watch Desk projection: `watch_desk_feed.py` consumes canonical lifecycle read-model items.

## Adapter Functions
- `create_worker_package_from_assignment_loop`
- `create_worker_package_from_lm_consult_request`

## Module Roles
- `codex_work_package_lifecycle.py`: runtime_spine / canonical
- `scripts/openclaw_run.py`: cli_control_surface / canonical_cli
- `assignment_loop_contract.py`: task_container / canonical_contract
- `openclaw_lm_consult_spine.py`: consult_transport / canonical_transport
- `openclaw_agent_role_registry.py`: agent_role_context / canonical_contract
- `provider_access_catalog.py`: provider_access_metadata / support_metadata
- `provider_access_auth_status.py`: provider_auth_metadata / support_metadata
- `proof_to_response_verifier.py`: proof_verification / canonical_verifier
- `watch_desk_feed.py`: projection / canonical_projection
- `spawned_worker_package_lifecycle.py`: contract_only / deprecated_runtime_retained
- `cross_machine_worker_dispatch_package.py`: support_metadata / compatibility
- `openclaw_lm_child_package_gate.py`: contract_only / future_contract_not_runtime
- `model_work_package_router.py`: support_metadata / metadata_router_not_runtime_registry

## Agent Usability
- Cassandra: request=True, dispatch=False, ingest=False, verify=False, summarize=True
- Chief: request=True, dispatch=True, ingest=True, verify=True, summarize=True
- Niles: request=True, dispatch=False, ingest=False, verify=False, summarize=True
- Hermes: request=True, dispatch=False, ingest=False, verify=False, summarize=True
- Guardian: request=False, dispatch=False, ingest=False, verify=True, summarize=True
- Watch Desk: request=False, dispatch=False, ingest=False, verify=False, summarize=True

## Repo B Legacy Disposition
Repo B is reference-only and not runtime authority. Unsafe OAuth, broker, credential, and autonomous repair-loop patterns stay blocked.

## What Not To Build Next
- Do not create another worker registry or queue database.
- Do not resurrect Repo B google_access_broker/OAuth/credential bridge code.
- Do not create a new model router or approval system.
- Do not let LM2 output mutate runtime directly.
