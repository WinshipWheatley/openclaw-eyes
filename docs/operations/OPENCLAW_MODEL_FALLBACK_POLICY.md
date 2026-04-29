# OpenClaw Model Fallback Policy

Status: draft operational policy. Pending user approval.

## Executive Rule

- No silent external fallback.
- Sensitive/private data defaults to deterministic or local-only handling.
- External models may be used only for non-sensitive repo/code/docs or explicitly sanitized packets with user approval and logging.
- Real Legal/client/matter data must not go external.
- Gmail bodies/private correspondence must not go external by default.
- Model capability is not assumed until benchmarked.

## Installed Local Model Inventory — 2026-04-28

Confirmed `ollama list` output from 2026-04-28 shows these local model names installed:

- `mistral-nemo:12b-instruct-2407-q2_K`
- `qwen3:8b-q4_K_M`
- `qwen3:4b`
- `qwen3.6:latest`
- `magistral:latest`
- `mistral-small:latest`
- `nemotron-3-nano:4b`
- `nemotron-3-nano:30b`
- `gemma4:31b`
- `gemma4:26b`
- `gemma4:e4b`

Installed means present locally as of the inventory date. It does not mean trusted, benchmarked, policy-approved, or appropriate for sensitive drafting, summarization, planner-builder, or acceptance behavior.

The installed inventory strengthens local-first feasibility, but does not prove local model quality. Benchmarks are still required before trusting drafting, summarization, planner-builder, or acceptance behavior.

## Model Inventory

A model name appearing in code, docs, or tests is evidence of a reference. Only the local models listed in `Installed Local Model Inventory — 2026-04-28` are confirmed installed by this document. Installation is not evidence of capability or trust.

| Model/tool | local/external | referenced by | intended lane/task | current status | risk notes | evidence paths |
|---|---|---|---|---|---|---|
| Ollama API | local | Chief, Cassandra, Cassandra briefing, Chief acceptance, local builder | shared local model execution | local model inventory CONFIRMED by `ollama list` output dated 2026-04-28 | Local execution does not prove safety or quality. | `chief_llm.py:64`, `chief_llm.py:428`, `cassandra_briefing_brain.py:871`, `chief_acceptance_gate.py:66`, `polish_loop/local_builder.py:394` |
| `gemma4:e4b` | local | Cassandra task-class router | fast Cassandra replies, inbox/extract/classify, test brief lane | CONFIRMED INSTALLED on 2026-04-28 | Small/fast lane quality UNPROVEN. | `chief_llm.py:88`, `chief_llm.py:111`, `tests/test_chief_llm_router.py:185` |
| `gemma4:26b` | local | Cassandra task-class router | normal Cassandra replies, briefs, summaries | CONFIRMED INSTALLED on 2026-04-28 | Capability UNPROVEN until benchmarked. | `chief_llm.py:89`, `chief_llm.py:101`, `tests/test_chief_llm_router.py:185` |
| `gemma4:31b` | local | Cassandra strong/outbound lanes | outbound drafts, stronger Cassandra replies, generic strong/deep candidate | CONFIRMED INSTALLED on 2026-04-28 | May process sensitive local email context; must remain local-only unless sanitized/approved. | `chief_llm.py:70`, `chief_llm.py:96`, `chief_llm.py:101` |
| `nemotron-3-nano:4b` | local | Chief router, Hermes lane policy as retired | fast lane, Chief evidence scan; retired from Hermes routing | CONFIRMED INSTALLED on 2026-04-28 | Do not confuse this local name with NVIDIA cloud Nemotron. | `chief_llm.py:67`, `chief_llm.py:120`, `sidecars/hermes/LANE_POLICY.md:27` |
| `nemotron-3-nano:30b` | local | Chief router | deep lane, Chief evidence synthesis/debug | CONFIRMED INSTALLED on 2026-04-28 | Capability UNPROVEN. | `chief_llm.py:70`, `chief_llm.py:125`, `chief_llm.py:136` |
| `qwen2.5-coder:7b` | local | Chief old defaults | older/default code model | REFERENCED BUT NOT INSTALLED in 2026-04-28 `ollama list` inventory | Looks legacy beside newer task-class routing. | `chief_llm.py:241` |
| `qwen2.5-coder:14b` | local | Chief code challenger, runner fallback, registry | code challenger, local builder/review fallback | REFERENCED BUT NOT INSTALLED in 2026-04-28 `ollama list` inventory | Current fallback references may resolve to a model that is not installed. | `chief_llm.py:76`, `runner_registry.py:125`, `runner_profiles.py:883` |
| `qwen3.6:latest` | local | Chief agentic-code lane, Hermes Lane C, local proof scripts | heavy local reasoning/annex/agentic code lane | CONFIRMED INSTALLED on 2026-04-28 | Hermes docs only support limited proven use; not broad autonomous authority. | `chief_llm.py:142`, `sidecars/hermes/LANE_POLICY.md:19`, `sidecars/hermes/lane_selector.py:27` |
| `qwen3:4b` | local | Hermes Lane A | quick aide, advisory synthesis | CONFIRMED INSTALLED on 2026-04-28 | Hermes docs say not reliable for autonomous tool execution. | `sidecars/hermes/LANE_POLICY.md:14`, `sidecars/hermes/lane_selector.py:28` |
| `qwen3:8b-q4_K_M` | local | Hermes Lane B, Cassandra non-morning fallback | slower synthesis; non-morning briefing fallback | CONFIRMED INSTALLED on 2026-04-28 | Limited proof; local fallback only. | `sidecars/hermes/LANE_POLICY.md:16`, `sidecars/hermes/lane_selector.py:29`, `cassandra_briefing_brain.py:66` |
| `mistral-nemo:12b-instruct-2407-q2_K` | local | Hermes lane policy as retired | retired Hermes routing candidate | CONFIRMED INSTALLED on 2026-04-28 | Installed but not an approved active OpenClaw authority lane in this policy. | `sidecars/hermes/LANE_POLICY.md:27` |
| `mistral-small:latest` | local | Chief router | evidence synthesis, structured plans, debug | CONFIRMED INSTALLED on 2026-04-28 | Capability UNPROVEN. | `chief_llm.py:126`, `chief_llm.py:131`, `chief_llm.py:137` |
| `magistral:latest` | local | Chief router | structured planning, ambiguous debug | CONFIRMED INSTALLED on 2026-04-28 | Capability UNPROVEN. | `chief_llm.py:127`, `chief_llm.py:136` |
| NVIDIA Nemotron `nvidia/nemotron-3-super-120b-a12b` | external | `nemotron_call`, Cassandra, Chief brainstorm, Chief CPA parse | cloud reasoning/extraction after caller-side checks | active code path if external API is configured | `nemotron_call` depends on callers to decide whether prompt is safe. | `chief_llm.py:177`, `cassandra_brain.py:5144`, `chief_brainstorm_brain.py:99`, `chief_cpa_brain.py:477` |
| Claude CLI / `claude-sonnet-4-6` | external | Chief wrapper, Cassandra calendar fallback, runner registry | manual/env-gated JSON/text, runner option | wrapper blocks by default unless allowed by env | Latent external fallback if env permits; no broad approval granted here. | `chief_llm.py:245`, `chief_llm.py:516`, `cassandra_brain.py:1900`, `runner_registry.py:125` |
| Codex CLI | external/cloud | runner registry, runner profiles | cloud code runner/builder | active runner candidate if installed/selected | Repo prompt can leak sensitive files if selection/scrub is wrong. | `runner_registry.py:145`, `runner_profiles.py:914` |
| Gemini CLI | external/cloud | runner registry, runner profiles | cloud planner/cheap runner | active runner candidate if installed/selected; planner mode forced in profile code | Cloud prompt risk; sensitivity gate is heuristic. | `runner_registry.py:157`, `runner_profiles.py:66`, `runner_profiles.py:967` |
| Aider | hybrid | runner registry | possible code runner | registered; autonomously blocked for builder by profile policy | Hybrid behavior/config UNKNOWN. | `runner_registry.py:168`, `runner_profiles.py:71` |
| Hermes OpenAI/Anthropic provider fallback machinery | external-capable | Hermes deps and run-agent tests | provider fallback inside Hermes sidecar | capability exists; active Hermes config/secrets intentionally not inspected | Hermes is documented advisory-only, but provider fallback capability exists. | `sidecars/hermes/pyproject.toml:15`, `sidecars/hermes/tests/run_agent/test_provider_fallback.py:88`, `sidecars/hermes/tests/run_agent/test_primary_runtime_restore.py:126` |

## Task/Lane Policy

| Task/lane | default route | external allowed? | fallback allowed? | required guard | evidence paths | status |
|---|---|---|---|---|---|---|
| Cassandra user replies | local Cassandra task-class router | only if sanitized, context-clean, user-approved, and logged | local task escalation only by default; external pending approval | PII hook, context-clean check, topic/sensitivity gate, route log | `cassandra_brain.py:5058`, `cassandra_brain.py:5144`, `cassandra_brain.py:5576`, `cassandra_pii_hooks.py:112` | PENDING USER APPROVAL |
| Cassandra outbound drafts | local `cassandra_outbound_draft` | no by default | local only by default | Gmail/private correspondence must stay local unless sanitized and approved | `chief_llm.py:96`, `cassandra_brain.py:3832`, `cassandra_outreach.py:24` | PENDING USER APPROVAL |
| Gmail body analysis | local-only or deterministic handling | no by default | none unless sanitized and explicitly approved | no raw body to external model | `google_access_policy.py:64`, `google_access_broker.py:505`, `cassandra_outreach.py:590` | PENDING USER APPROVAL |
| Cassandra calendar extraction | deterministic/local extraction | no by default | Claude JSON fallback exists but should remain disabled unless approved | action-specific approval before external fallback | `cassandra_brain.py:1860`, `cassandra_brain.py:1900`, `chief_llm.py:516` | CONFLICT / NEEDS USER DECISION |
| Cassandra morning brief | local briefing stages | no by default | local qwen fallback, then deterministic fallback | local-only, deterministic fallback on failure | `cassandra_briefing_brain.py:871`, `cassandra_briefing_brain.py:1134`, `cassandra_briefing_brain.py:1166` | CONFIRMED BY CODE/DOCS |
| Chief evidence/plan/debug/code lanes | local task-class router | no by default for sensitive/private evidence | local candidate selection only | route through `resolve_local_model`; benchmark before trust | `chief_llm.py:120`, `chief_llm.py:150`, `tests/test_chief_llm_router.py:328` | INFERRED FROM CODE/DOCS |
| Chief acceptance gate | local fast Ollama, fail-closed | no | no external fallback | malformed/empty output must fail closed | `chief_acceptance_gate.py:1`, `chief_acceptance_gate.py:66`, `chief_acceptance_gate.py:88` | CONFIRMED BY CODE/DOCS |
| Planner-builder runner | local for sensitive; cloud only for repo-only non-sensitive tasks | yes, only after sensitivity/path check and logging | registry fallback may choose cloud; sensitive tasks force local | frontmatter/keyword sensitivity check is not enough for private data | `runner_profiles.py:506`, `runner_profiles.py:800`, `runner_registry.py:523` | PENDING USER APPROVAL |
| Local builder | local Ollama tool loop | no | no external fallback in local builder | tool/file-write bounds plus tests | `polish_loop/local_builder.py:394`, `polish_loop/local_builder.py:452`, `polish_loop/local_builder.py:314` | CONFIRMED BY CODE/DOCS |
| Hermes lanes | local deterministic lane selector for advisory use | provider fallback pending approval | no canonical fallback without approval | advisory-only, non-canonical, no authority-risk routing | `sidecars/hermes/LANE_POLICY.md:1`, `sidecars/hermes/lane_selector.py:91`, `sidecars/hermes_home/HERMES_ORIENTATION.md:3` | PENDING USER APPROVAL |
| Legal v0 | deterministic local workflow | no | no model fallback | real Legal/client/matter data must stay out of model contexts | `legal/README.md:34`, `legal/CHECKPOINT.md:30`, `docs/planning/openclaw_legal/law_program/LEGAL_V1_CONTRACT_INDEX.md:176` | CONFIRMED BY CODE/DOCS |
| Support packet generation | deterministic sanitized generation | external review only after approval | no default external fallback | sanitize before export/review | `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md:206`, `docs/planning/openclaw_legal/law_program/LEGAL_V1_CONTRACT_INDEX.md:337` | INFERRED FROM CODE/DOCS |
| Stale-folder cleanup recommendations | deterministic metadata manifest first | no by default | no model fallback on contents | metadata-only, no private content inspection | `docs/operations/OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md:11`, `docs/operations/OPENCLAW_STALE_FOLDER_MANIFEST_DRAFT.md:120` | CONFIRMED BY DOCS |
| Architecture review | local or external for repo-only non-sensitive inputs | yes after path/sensitivity check | external allowed only after approval/logging | exclude secrets, private data, runtime logs, vaults | `runner_profiles.py:506`, `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md:203` | PENDING USER APPROVAL |
| Code review | local/tests first; external only for repo-only non-sensitive inputs | yes after path/sensitivity check | external allowed only after approval/logging | exclude secrets, private data, Gmail, Legal matter data | `runner_registry.py:145`, `runner_profiles.py:914`, `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md:203` | PENDING USER APPROVAL |

## Local Model Suitability

| Task type | classification | notes |
|---|---|---|
| deterministic classification support | DETERMINISTIC VALIDATION REQUIRED | Local model may assist extraction/classification, but deterministic validation owns authority. |
| short summarization | FIRST-PASS/DRAFT ONLY | No benchmark in this document proves quality. |
| long-context summarization | UNPROVEN | Benchmark harness exists, but this document did not run it. |
| Cassandra user replies | DETERMINISTIC VALIDATION REQUIRED | Local-first route exists; safety depends on topic gates, PII hooks, and review. |
| email drafting | FIRST-PASS/DRAFT ONLY | Private correspondence risk requires review and local-only default. |
| Gmail body analysis | DETERMINISTIC VALIDATION REQUIRED | External is forbidden by default; local quality still UNPROVEN. |
| Legal/private matter analysis | NOT APPROPRIATE | Legal v0 doctrine is no LLM/no cloud for real matter data. |
| architecture review | FIRST-PASS/DRAFT ONLY | External may be useful only for sanitized repo-only context. |
| code review | DETERMINISTIC VALIDATION REQUIRED | Tests/harnesses must decide, not model confidence. |
| planner-builder implementation | UNPROVEN | Tool loop exists; autonomous implementation quality requires benchmark and bounded tests. |
| Chief acceptance/rejection | DETERMINISTIC VALIDATION REQUIRED | Local model is fail-closed evidence aid, not sole authority. |
| Hermes synthesis | FIRST-PASS/DRAFT ONLY | Advisory-only; no canonical authority. |
| stale-folder cleanup recommendations | FIRST-PASS/DRAFT ONLY | Metadata-only summaries are acceptable; no content-based cleanup authority. |
| support packet generation | NOT APPROPRIATE | Must be deterministic and sanitized before any model review. |

## External Model Policy Table

| Task type | external allowed? | default route | fallback route | sanitization required | approval required | logging required | forbidden inputs |
|---|---|---|---|---|---|---|---|
| Deterministic classification | no by default | deterministic code | none | n/a | no | normal audit | sensitive/private data to model |
| Non-sensitive architecture/code review | yes after path/sensitivity check | local/tests first or approved external | external large-context model allowed if sanitized | yes | yes | yes | secrets, private logs, Gmail, Legal, vaults, PII |
| Cassandra casual replies | only if sanitized and approved | local Cassandra route | external only after context-clean + approval | yes | yes | yes | PII, Gmail bodies, finance/private context, contacts |
| Email drafting | only if sanitized and explicitly approved | local draft model | external only after explicit approval | yes | yes | yes | raw Gmail bodies, private correspondence, attachments |
| Gmail body analysis | local-only by default | deterministic/local | none by default | yes if ever exported | yes if ever exported | yes | raw body text and private correspondence |
| Legal/private matter work | no | deterministic local workflow | none | n/a | n/a | yes | real Legal/client/matter data |
| Chief acceptance | no | local fail-closed model | none | n/a | no | yes | private evidence to external model |
| Planner-builder | only repo-only non-sensitive | local for sensitive; cloud for approved non-sensitive | runner registry after scrub/logging | yes | yes | yes | secrets, private data, Gmail, Legal, private vaults |
| Hermes synthesis | pending approval | advisory local lanes | provider fallback blocked until approved | yes | yes | yes | canonical state, private data, Legal/Gmail/vault data |
| Support packets | external review only after approval | deterministic sanitized generation | approved external review only | yes | yes | yes | raw secrets, Gmail, Legal/private matter data, PII vault data |

## Current Fallback Risks

- `nemotron_call` depends on caller-side privacy gates. Evidence: `chief_llm.py:177`, `chief_llm.py:200`.
- Cassandra `cloud_ok=True` can use external Nemotron; context-cleaning is heuristic. Evidence: `cassandra_brain.py:5058`, `cassandra_brain.py:5144`.
- Cassandra calendar extraction has latent Claude JSON fallback, env-blocked but not action-approval-gated. Evidence: `cassandra_brain.py:1900`, `chief_llm.py:516`.
- Planner-builder sensitivity routing is keyword/frontmatter based, not a full scrubber. Evidence: `runner_profiles.py:506`, `runner_profiles.py:800`.
- Runner docs/policy are stale or conflicting around Claude/Gemini/Aider/Ollama. Evidence: `runner_registry.py:14`, `runner_profiles.py:66`, `runner_profiles.py:71`.
- Gmail body read is Class A and could be misused by future model callers. Evidence: `google_access_policy.py:64`, `google_access_broker.py:505`.
- Hermes provider fallback machinery exists but active config was not inspected. Evidence: `sidecars/hermes/tests/run_agent/test_provider_fallback.py:88`, `sidecars/hermes/tests/run_agent/test_primary_runtime_restore.py:126`.
- Legal has stale LLM references beside current no-LLM Legal v0 doctrine. Evidence: `legal_llm.py:40`, `legal/README.md:37`.

## Required Benchmarks/Tests Before Trust

Do not treat these as authorization to run tests or live model calls. They are the verification set to run after user approval.

| Command | working directory | proves | live model? | private-data risk | expected safe inputs |
|---|---|---|---|---|---|
| `python3 -m pytest tests/test_chief_llm_router.py` | `/home/openclaw` | task-class routing and wrapper behavior with mocks | no | low | synthetic tests |
| `python3 -m pytest tests/test_send_truth.py::TestCassandraRouterPolicy tests/test_cassandra_briefing_context.py` | `/home/openclaw` | Cassandra routing and fallback invariants | no | low | synthetic/mocked tests |
| `python3 -m pytest tests/test_chief_claude_cleanup.py` | `/home/openclaw` | Chief modules avoid direct Claude calls outside wrapper expectations | no | low | code inspection tests |
| `python3 -m pytest tests/test_chief_acceptance_gate.py tests/test_pc_review_fallback.py` | `/home/openclaw` | local fail-closed acceptance/review behavior | no | low | synthetic/mocked tests |
| `python3 -m pytest tests/test_harness_task_runner.py tests/test_builder_fallback.py` | `/home/openclaw` | harness execution and runner fallback policy | no | low | synthetic/mocked tests |
| `python3 scripts/check_local_model_usage.py` | `/home/openclaw` | inventory of local model references | no | low | code/docs only |
| `ollama list` | `/home/openclaw` | installed local model inventory | no inference | low | local daemon metadata |
| `python3 openclaw_local_model_benchmark.py --reference-time 2026-04-28-model-audit` | `/home/openclaw` | actual local model format/latency on benchmark fixtures | yes, local only | low if fixtures remain synthetic | staged benchmark fixtures |
| `HERMES_HOME="$(mktemp -d)" python -m pytest -o addopts="" tests/test_lane_selector.py tests/run_agent/test_provider_fallback.py tests/run_agent/test_primary_runtime_restore.py` | `/home/openclaw/sidecars/hermes` | Hermes lane selector and provider fallback mechanics | no | low | mocked Hermes tests with temp home |

## Pending User Decisions

- Approve local-only rule for Gmail body analysis.
- Approve deterministic-only/no-LLM rule for real Legal matter data.
- Approve external architecture/code review only for sanitized repo-only inputs.
- Approve planner-builder cloud runner rules.
- Approve Hermes advisory-only/provider fallback restriction.
- Approve benchmark requirement before model-driven drafting, summarization, or builder trust.
- Approve no silent external fallback.

## Verification Limits

- This document confirms the listed local model names from the 2026-04-28 `ollama list` inventory, but does not prove they remain installed later or are usable for any task.
- This document does not prove model quality.
- This document does not authorize external fallback.
- This document does not approve sending private data to any model.
- This document does not update runtime enforcement code.
