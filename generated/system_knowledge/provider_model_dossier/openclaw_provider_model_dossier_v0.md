# OpenClaw Provider Model Dossier V0

Status: `OPENCLAW_PROVIDER_MODEL_DOSSIER_READY`

This is a knowledge artifact for future model capability routing. It does not implement a router, call model APIs, inspect credentials, mutate runtime services, create approvals, or start Hermes.

## Executive Summary

- OpenClaw must separate provider capability from access mode, subscription entitlement, provider/API health, and local runtime availability. [repo-derived: `repo_provider_access_catalog`, `repo_model_work_package_router`]
- Winship's current policy preference is subscription-backed CLI/app use before API-key billing or credit pools. [operator-provided, repo-derived: `repo_provider_access_catalog`]
- The Gemini API route currently has config present but is blocked by a 429 `RESOURCE_EXHAUSTED` credit condition, so provider health must not be treated as model capability. [repo-derived: `repo_lm_consult_spine_status`]
- Codex is a code-worker/access mode for OpenClaw, not Cassandra's chat brain. [source: `openai_codex_cli`, `openai_codex_app`, `openai_codex_web`; repo-derived: `repo_provider_access_catalog`]

## Provider vs Access Mode vs Capability

- OpenAI capability layer: GPT-5.5/GPT-5.4 families, Responses API, structured outputs, GPT Image, Realtime/audio, transcription, Sora/video, Agents SDK, and Codex surfaces. [source: `openai_models`, `openai_latest_model`, `openai_structured_outputs`, `openai_realtime_audio`, `openai_images`, `openai_video`, `openai_agents`]
- OpenAI access layer: Codex CLI/app/web are coding-agent surfaces included with ChatGPT plans; ChatGPT app/web remains manual-only in OpenClaw until a supported bridge is proven. [source: `openai_codex_cli`, `openai_codex_app`, `openai_codex_web`, `openai_codex_pricing`; repo-derived: `repo_provider_access_catalog`]
- Google capability layer: Gemini 3.x text/multimodal models, Gemini 3.5 Flash, Gemini 3.1 Live/TTS, Nano Banana, Imagen, Veo, Lyria, Deep Research, Computer Use, Antigravity Agent, and embeddings. [source: `google_models`, `google_gemini35_flash`, `google_gemini31_live`, `google_gemini31_tts`, `google_image_generation`, `google_imagen`, `google_veo`, `google_lyria_music`, `google_deep_research`, `google_computer_use`, `google_antigravity`, `google_embeddings`]
- Google access layer: Gemini CLI and Antigravity CLI are installed locally, but auth/subscription/billing mode is not proven. [repo-derived: `repo_provider_access_catalog`]
- Anthropic capability layer: Claude Opus 4.8, Sonnet 4.6, Haiku 4.5, pricing/context controls, effort controls, and Claude Code surfaces. [source: `anthropic_models`, `anthropic_pricing`, `anthropic_context_windows`, `anthropic_choose_model`, `anthropic_claude_code_overview`]
- Anthropic access layer: Claude CLI is installed locally, but auth/subscription/billing mode is not proven. [repo-derived: `repo_provider_access_catalog`]
- Local/Ollama layer: Ollama is a local runtime inventory and redaction/classification candidate, not subscription-backed access. [repo-derived: `repo_provider_access_catalog`]

## OpenAI Section

- GPT-5.5 is documented as OpenAI's newest frontier model for complex reasoning and coding/professional work. [source: `openai_models`, `openai_latest_model`]
- GPT-5.4, GPT-5.4 Pro, GPT-5.4 mini, and GPT-5.4 nano are documented GPT-5.4-family options for professional work and lower-cost/lower-latency workloads. [source: `openai_models`, `openai_changelog`]
- Structured Outputs constrain model text to a supplied JSON Schema. [source: `openai_structured_outputs`]
- The Responses API and Agents SDK are the relevant OpenAI surfaces for model calls with tools, state, guardrails, human review, and structured output. [source: `openai_agents`]
- Realtime/audio docs separate voice agents, live translation, transcription, and text-to-speech paths. [source: `openai_realtime_audio`, `openai_speech_to_text`]
- Image generation/editing and Sora video generation are specialized creative media surfaces. [source: `openai_images`, `openai_video`]
- Prompt caching, Batch API, cost optimization, and evals are documented cost/latency/quality controls. [source: `openai_prompt_caching`, `openai_batch`, `openai_cost_optimization`, `openai_evals`]
- Codex CLI, Codex app, and Codex web/cloud are coding-agent surfaces included with ChatGPT plans. [source: `openai_codex_cli`, `openai_codex_app`, `openai_codex_web`, `openai_codex_pricing`]
- Codex app computer use is documented, but OpenClaw should keep desktop-control/computer-use disabled by default behind Guardian and explicit operator approval. [source: `openai_codex_computer_use`; repo-derived: `repo_provider_access_catalog`]

## Google/Gemini Section

- Gemini 3.5 Flash is documented as a faster/lower-cost frontier-level model for real-world and agentic tasks, with multimodal input, structured outputs, function calling, code execution, grounding, caching, and large context. [source: `google_gemini35_flash`]
- Gemini 3.1 Flash Live Preview is documented for low-latency audio-to-audio dialogue. [source: `google_gemini31_live`]
- Gemini 3.1 Flash TTS Preview is documented for low-latency speech generation. [source: `google_gemini31_tts`]
- Lyria 3 Clip/Pro and Lyria RealTime are documented music-generation capabilities; Lyria belongs in a Niles/creative branch only after explicit creative-media approval. [source: `google_lyria_music`, `google_lyria_realtime`; repo-derived policy label]
- Nano Banana, Nano Banana 2, Nano Banana Pro, Imagen 4, and Veo 3.1 are documented image/video creative media capabilities. [source: `google_image_generation`, `google_imagen`, `google_veo`]
- Deep Research, Computer Use, and Antigravity Agent are documented agent/tool surfaces. [source: `google_deep_research`, `google_computer_use`, `google_antigravity`]
- Antigravity Agent is documented as a managed Gemini API agent powered by Gemini 3.5 Flash that can run code, manage files, and browse in a hosted sandbox. [source: `google_antigravity`]
- Gemini embeddings are documented for semantic search, classification, clustering, and RAG. [source: `google_embeddings`]
- Google publishes a deprecation/lifecycle page for model shutdown schedules. [source: `google_model_lifecycle`]
- No new Gemini 2.x route candidates should be added; Gemini 2.x belongs only as an excluded or legacy reference. [operator-provided; source: `google_model_lifecycle`]

## Anthropic/Claude Section

- Anthropic documents Claude Opus 4.8, Sonnet 4.6, and Haiku 4.5, with Opus for advanced reasoning/coding/creative work, Sonnet as balanced, and Haiku as fastest/lowest-cost tier. [source: `anthropic_models`, `anthropic_pricing`]
- Anthropic documents 1M context windows for Claude Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 4.6, Fable 5, and Mythos 5 on specified surfaces; other Claude models can remain at 200k depending on platform. [source: `anthropic_context_windows`]
- Anthropic documents effort tuning for recent Opus/Sonnet models as a cost/latency/intelligence lever. [source: `anthropic_choose_model`, `anthropic_models`]
- Claude Code docs list Terminal CLI, VS Code, desktop, web, JetBrains, and related surfaces; most surfaces require a Claude subscription, Console account, or supported cloud provider. [source: `anthropic_claude_code_overview`, `anthropic_claude_code_quickstart`, `anthropic_claude_code_auth`]
- Claude CLI reference documents noninteractive print, piped input, model selection, JSON output, JSON Schema, and tools controls. [source: `anthropic_claude_cli_reference`]
- Local Claude CLI help exposed fable/opus/sonnet aliases; Haiku was not observed locally and should not be claimed locally selectable without a future probe. [repo-derived: `repo_provider_access_catalog`; source: `anthropic_claude_model_config`]

## Local/Ollama Section

- The local audit found Ollama installed with local models including `qwen3:8b-q4_K_M`; no model invocation was performed by that audit. [repo-derived: `repo_provider_access_catalog`]
- Local models are the preferred class for private redaction/classification when an invocation boundary, redaction policy, verifier, and receipts exist. [repo-derived: `repo_provider_access_catalog`, `repo_model_work_package_router`]
- Local runtime presence does not approve proof-bundle exposure or model invocation. [repo-derived: `repo_provider_access_catalog`]

## OpenClaw Current Substrate

- Provider Access Catalog found Codex CLI, Gemini CLI, Antigravity CLI, Claude CLI, and Ollama installed, but did not prove subscription/auth backing for cloud CLIs. [repo-derived: `repo_provider_access_catalog`]
- Worker Run Manager/Codex package lifecycle supports bounded package states, allowed worker kinds, result ingestion, and authority boundaries. [repo-derived: `repo_worker_run_manager`]
- Assignment Loop frames worker/model jobs as bounded assignments with goals, sources, standards, permission boundaries, proof requirements, receipts, Watch Desk refs, and stop conditions. [repo-derived: `repo_assignment_loop`]
- Model Work Package Router builds advisory-only packages and deterministic model-class decisions without calling models or granting execution authority. [repo-derived: `repo_model_work_package_router`]
- Watch Desk aggregates read models into proof-backed display items and remains display-only. [repo-derived: `repo_watch_desk`]

## Router Implications

- Router inputs must include task class, data sensitivity, source freshness, required proof, access mode, provider health, subscription/auth proof, budget posture, tool/desktop risk, and required receipts. [repo-derived: `repo_model_work_package_router`, `repo_assignment_loop`]
- Model capability can recommend a lane but cannot grant tool, desktop, browser, email, Coupa, ledger, workbook, PDF, paid, or push authority. [repo-derived: `repo_provider_access_catalog`, `repo_worker_run_manager`]
- Codex should route as a code-worker/access mode, not Cassandra's live chat brain. [source: `openai_codex_cli`; repo-derived: `repo_provider_access_catalog`]
- Google Deep Research, Antigravity Agent, Computer Use, Lyria, Imagen/Nano Banana, Veo, OpenAI media, and Codex/desktop computer-use remain disabled by default. [source: `google_deep_research`, `google_antigravity`, `google_computer_use`, `google_lyria_music`, `google_image_generation`, `google_veo`, `openai_images`, `openai_video`, `openai_codex_computer_use`; repo-derived policy label]
- Chief should adjudicate router changes, and Guardian gates risky capability enablement. [operator-provided; repo-derived: `repo_assignment_loop`]

## Subscription-Backed Access Implications

- Installation does not prove subscription-backed access. [repo-derived: `repo_provider_access_catalog`]
- Codex CLI is the strongest first candidate for subscription-backed implementation work once auth/subscription proof exists. [source: `openai_codex_cli`, `openai_codex_pricing`; repo-derived: `repo_provider_access_catalog`]
- Gemini CLI, Antigravity CLI, and Claude CLI remain candidate worker lanes until safe auth/billing and no-tools/no-file boundaries are proven. [repo-derived: `repo_provider_access_catalog`]
- API routes are fallback-only unless explicitly configured and approved. [repo-derived: `repo_provider_access_catalog`, `repo_lm_consult_spine_status`]
- ChatGPT app/web remains manual-only without a supported bridge. [source: `openai_codex_app`; repo-derived: `repo_provider_access_catalog`]

## Cost/Latency/Accuracy Doctrine

- Use deterministic local logic when proof can answer without a model. [repo-derived: `repo_model_work_package_router`]
- Use local/Ollama for private redaction/classification when verifier coverage exists. [repo-derived: `repo_provider_access_catalog`]
- Use subscription-backed CLI workers before API billing when a bounded assignment can be dispatched and ingested safely. [operator-provided; repo-derived: `repo_worker_run_manager`]
- Use API models only for capability gaps that subscription/local access cannot satisfy and only after provider health, cost, and approval receipts exist. [repo-derived: `repo_lm_consult_spine_status`, `repo_assignment_loop`]
- Prefer smaller/faster model tiers only after eval fixtures prove accuracy and safety. [source: `openai_evals`, `openai_cost_optimization`, `anthropic_choose_model`]

## Evals/Accuracy Target Doctrine

- Every provider lane needs fixtures for schema compliance, unsupported-claim refusal, protected-action refusal, citation/source behavior, stale-context handling, and fallback behavior. [source: `openai_evals`; repo-derived: `repo_model_work_package_router`]
- Provider/model upgrades require regression checks across proof-to-response, code review, form-fill, stale-context, protected-action, and unsupported-claim tasks. [repo-derived: `repo_provider_access_catalog`, `repo_assignment_loop`]
- Do not lower verifier or Guardian thresholds to make a model pass. [repo-derived: `repo_assignment_loop`]
- Track cost/latency separately from accuracy and safety. [source: `openai_cost_optimization`, `anthropic_choose_model`]

## Known Unknowns

- Whether Codex CLI here is authenticated through Winship's ChatGPT subscription rather than API billing. [repo-derived: `repo_provider_access_catalog`; source: `openai_codex_cli`]
- Whether Gemini CLI and Antigravity CLI can run through subscription-backed access rather than API credit pools. [repo-derived: `repo_provider_access_catalog`]
- Whether Claude CLI is authenticated through Claude subscription, Anthropic Console, or another provider route. [repo-derived: `repo_provider_access_catalog`; source: `anthropic_claude_code_auth`]
- Which CLI lanes expose enough JSON/no-tools/sandbox controls for automatic Worker Run Manager ingestion. [repo-derived: `repo_provider_access_catalog`, `repo_worker_run_manager`]
- Whether any ChatGPT workspace-agent bridge is suitable for OpenClaw without GUI/browser scraping. [unknown; source: `openai_agents`]

## What Not To Build

- Do not build a new approval system; use Guardian/HITL. [repo-derived: `repo_assignment_loop`]
- Do not build a new dashboard; feed Watch Desk/read models. [repo-derived: `repo_watch_desk`]
- Do not start Hermes to watch catalogs in this task. [operator-provided]
- Do not route private finance proof to external providers by default. [repo-derived: `repo_provider_access_catalog`]
- Do not make Gemini API credits the main route while provider health is blocked. [repo-derived: `repo_lm_consult_spine_status`]
- Do not automate ChatGPT app/web without a supported bridge. [repo-derived: `repo_provider_access_catalog`]
- Do not enable computer-use, managed agents, creative media, browser tools, or file tools by default. [source: `openai_codex_computer_use`, `google_computer_use`, `google_antigravity`, `google_lyria_music`, `google_image_generation`, `google_veo`; repo-derived policy label]

## Next Build Tasks

1. `OPENCLAW_SUBSCRIPTION_CLI_AUTH_STATUS_PROBE_V0`: prove auth/subscription/billing mode for Codex, Gemini, Antigravity, and Claude CLIs without printing credentials or invoking generation.
2. `OPENCLAW_MODEL_CAPABILITY_ROUTER_CONTRACT_V0`: define router inputs/outputs using this dossier, provider access catalog, assignment loop, Guardian gates, and Worker Run Manager.
3. `OPENCLAW_WORKER_PROVIDER_NO_TOOLS_SMOKE_PACKETS_V0`: create bounded, non-business smoke packages for CLI worker candidates after auth mode is proven.
4. `OPENCLAW_PROVIDER_EVAL_FIXTURE_SET_V0`: build offline eval fixtures for proof-to-response, code review, form-fill, stale-context, protected-action, and unsupported-claim behavior.
