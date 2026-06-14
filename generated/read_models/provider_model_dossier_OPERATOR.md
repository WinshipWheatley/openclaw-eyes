# Provider Model Dossier Operator Summary

Status: `OPENCLAW_PROVIDER_MODEL_DOSSIER_READY`

Files:
- `generated/system_knowledge/provider_model_dossier/openclaw_provider_model_dossier_v0.md`
- `generated/system_knowledge/provider_model_dossier/openclaw_provider_model_dossier_v0.json`
- `generated/system_knowledge/provider_model_dossier/source_index.json`

## What This Says

- Model capability, access mode, subscription entitlement, API billing health, and runtime authority are separate things. [repo-derived: `repo_provider_access_catalog`]
- Codex CLI/app/web are worker/access modes for code work, not Cassandra's chat brain. [source: `openai_codex_cli`, `openai_codex_app`, `openai_codex_web`]
- ChatGPT app/web remains manual-only until a supported bridge exists. [repo-derived: `repo_provider_access_catalog`]
- Gemini API capability is separate from the current Gemini provider-health blocker: `RESOURCE_EXHAUSTED` / prepayment credits depleted. [repo-derived: `repo_lm_consult_spine_status`]
- Claude CLI, Gemini CLI, Antigravity CLI, and Codex CLI are installed, but subscription/auth backing is not proven yet. [repo-derived: `repo_provider_access_catalog`]
- Ollama is local runtime access, not subscription-backed access. [repo-derived: `repo_provider_access_catalog`]

## Provider Findings

- OpenAI: GPT-5.5/GPT-5.4 families, Responses API, structured outputs, Realtime/audio, image/video/transcription, Codex, caching, Batch, cost optimization, and evals are documented official capabilities. [source: `openai_models`, `openai_latest_model`, `openai_structured_outputs`, `openai_realtime_audio`, `openai_images`, `openai_video`, `openai_speech_to_text`, `openai_codex_cli`, `openai_batch`, `openai_prompt_caching`, `openai_cost_optimization`, `openai_evals`]
- Google/Gemini: Gemini 3.5 Flash, Gemini 3.1 Flash Live, Gemini 3.1 Flash TTS, Lyria, Nano Banana, Imagen, Veo, Deep Research, Computer Use, Antigravity Agent, embeddings, and model lifecycle/deprecation docs are indexed. [source: `google_gemini35_flash`, `google_gemini31_live`, `google_gemini31_tts`, `google_lyria_music`, `google_lyria_realtime`, `google_image_generation`, `google_imagen`, `google_veo`, `google_deep_research`, `google_computer_use`, `google_antigravity`, `google_embeddings`, `google_model_lifecycle`]
- Anthropic/Claude: Opus 4.8, Sonnet 4.6, Haiku 4.5, context/pricing, effort tuning, and Claude Code/CLI access docs are indexed. [source: `anthropic_models`, `anthropic_pricing`, `anthropic_context_windows`, `anthropic_choose_model`, `anthropic_claude_code_overview`, `anthropic_claude_cli_reference`]

## Router Implications

- First build should be a router contract, not a live router.
- Chief adjudicates router changes.
- Guardian gates risky capability enablement.
- Creative media, computer use, browser/file tools, managed agents, and external API routes stay disabled by default.
- Subscription-backed CLI lanes should be proven before API-key billing lanes are preferred.

## Known Unknowns

- Whether Codex CLI is using ChatGPT subscription entitlement.
- Whether Gemini CLI or Antigravity CLI avoid Gemini API credit pools.
- Whether Claude CLI is subscription-backed, Console-backed, or provider-backed.
- Whether any ChatGPT workspace-agent bridge is suitable without GUI/browser scraping.

## Next Prompt

`OPENCLAW_SUBSCRIPTION_CLI_AUTH_STATUS_PROBE_V0`

Goal: prove auth/subscription/billing mode for Codex, Gemini, Antigravity, and Claude CLIs without printing credentials, reading token stores, or invoking generation.

Safety: no model APIs were called, no credentials were inspected, no runtime services were mutated, no approvals were created, and Hermes was not started.
