# Agent Roster + Model Backend Policy

## Roster
- Agents: CASSANDRA, CHIEF, NILES, GUARDIAN, HERMES
- System identities: OPENCLAW_SYSTEM

## Model Backends
- OPENAI_CODEX: Codex - Use as selected_model_backend or selected_worker_type, never as agent_role.
- OPENAI_GPT: GPT - Use only when privacy and credit gates allow.
- GEMINI_AGY: Gemini/Agy - Use as Hermes or Chief audit backend only after privacy/credit gates.
- CLAUDE: Claude - Use as fallback writing or critique backend when allowed.
- LOCAL_OLLAMA: Local Ollama - Prefer for sensitive/private explanation when adequate.
- FUTURE_PROVIDER: Future Provider - Fail closed until a provider profile, privacy gate, and authority policy exist.

## Worker Backends
- PC_CODEX_WORKER: Repo A backend implementation worker surface.
- MAC_CODEX_WORKER: Mac-side app/UI/build validation worker surface.
- GEMINI_AGY_ADVISORY_WORKER: Read-only advisory audit/scout surface.
- LOCAL_OLLAMA_INTERPRETER: Local model interpretation or explanation surface.
- REPO_B_WRAPPED_WORKER: Future wrapped worker surface from Repo B lanes.
- MANUAL_OPERATOR: Human operator decision/action surface.
- UNKNOWN_FAIL_CLOSED: Unknown worker backend.

## Legacy Findings
- openclaw_request_processor.py / CODEX_RESPONDER_FUTURE: FOUND_LEGACY_COMPATIBILITY_NAME
- openclaw_request_processor.py / GEMINI_RESPONDER_FUTURE: FOUND_LEGACY_COMPATIBILITY_NAME
- scoped_context_package_compiler_contract.py / TARGET_AGENT_ROLES: FOUND_LEGACY_COMPATIBILITY_NAME
- worker_routing_intelligence.py / GEMINI_PATTERNS: FOUND_LEGACY_COMPATIBILITY_NAME
- intent_router.py / AGENT_PHRASES: FOUND_LEGACY_COMPATIBILITY_NAME
- agent_voice_response_layer.py / "CODEX": MIGRATED_TO_MODEL_BACKEND

## Boundary
No live model call, no agent dispatch, no worker dispatch, no workflow run, no external action, no send/submit, no tool use, no credential handling, no raw-body ingestion.

Next safe move: Wire future intent validation to this ontology before allowing live LM interpretation.
