# Local Model Benchmark Plan: Qwen3.6-35B-A3B

Status: docs-only benchmark planning artifact. This file does not install models, compile runtimes, start services, expose endpoints, edit routers, inspect private data, touch secrets, mutate storage, or authorize production routing.

Generated/reviewed: 2026-05-05

Source basis:

- Operator-provided hardware note for the PC WSL Ubuntu-E node.
- Operator-provided caveat note about Qwen3.6-35B-A3B as a MoE-class local-model experiment.
- `20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`, especially the Hardware Fit Analyzer / Deployment Advisor doctrine.

Freshness:

- Stale when PC hardware, GPU driver/runtime availability, model card claims, GGUF/TurboQuant artifacts, upstream llama.cpp support, fork support, Ollama/LM Studio support, or OpenClaw model-routing policy changes.
- Refresh before any install, download, fork build, runtime configuration, router change, or PI/Chief/Cassandra production-use decision.

## 1. Purpose

Define a bounded local benchmark lane for testing whether the PC can run Qwen3.6-35B-A3B or a nearby quantized MoE artifact.

The goal is to decide whether this candidate belongs in an experimental PI/local-private reasoning lane. It is not a plan to make OpenClaw depend on the model for production PI, Chief, Cassandra, routing, approvals, or autonomous execution.

## 2. Initial Fit Verdict

Hardware Fit Analyzer verdict: likely too large, but installation/test run is reasonable only as a bounded benchmark with prepared validation tests.

Interpretation:

- the PC can probably run a carefully chosen quantized MoE build as an experiment;
- default convenience-wrapper behavior is unlikely to be stable or comfortable without tuning;
- the main limits remain 6 GB VRAM, PCIe traffic, system RAM bandwidth, runtime/fork support, and context/KV cache behavior;
- success would justify an experimental local lane, not production OpenClaw routing.

## 3. PC Hardware Baseline

Known target node:

- PC WSL Ubuntu-E canonical workspace at `/home/openclaw`.
- Hostname: `DESKTOP-HP`.
- CPU: Intel i7-6700.
- RAM: about 27 GiB visible to WSL.
- GPU: NVIDIA GTX 1660 Ti with 6 GB VRAM.
- Runtime baseline from readiness audit: Python `3.12.3`, Node `v24.14.0`.
- Active WSL VHDX: `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`.

Hardware read:

- GTX 1660 Ti 6 GB is likely better than a GTX 1060 6 GB reference case, but not a different class of machine.
- The shared VRAM class matters more than the generational improvement.
- Any workable setup will likely rely on CPU RAM for many MoE experts and use the GPU selectively.

## 4. Candidate Model Posture

Candidate: Qwen3.6-35B-A3B or a closely matching quantized MoE artifact.

Planning assumptions to verify before install:

- public model material describes the candidate as a MoE-class model with about 35B total parameters and a much smaller active slice per token;
- the active-parameter shape is what makes a 6 GB GPU experiment plausible;
- long-context claims must be tested against actual KV cache behavior and memory pressure;
- GGUF, TurboQuant, and fork-specific artifacts may not behave the same across runtimes.

Do not treat model-card claims as operational proof. They are benchmark inputs.

## 5. Runtime And Fork Caveat

The first benchmark should target llama.cpp directly, not Ollama, LM Studio, or another convenience wrapper.

Reasoning:

- MoE placement flags may be required to fit the workload into this PC's VRAM/RAM reality;
- TurboQuant-specific KV cache types may require a specific llama.cpp fork and may not exist in upstream llama.cpp;
- standard runtimes are more likely to support conventional KV cache types such as `q8_0` or `q4_0`;
- wrappers may hide the exact placement, context, cache, and memory decisions needed for a meaningful fit verdict.

The benchmark plan should record the exact runtime source, commit, fork, build flags, model artifact, quant type, and cache type before any test result is accepted.

## 6. Flags And Concepts To Test

These are planning concepts, not approved commands.

- `--n-cpu-moe`: key MoE placement concept. Keep non-expert or fast layers on GPU where useful, while placing many experts in CPU RAM.
- `--no-mmap`: load the model into RAM instead of relying on lazy OS paging. This may reduce stutter when RAM is sufficient.
- `--mlock`: pin model memory so the OS does not page it out during long runs. This may require OS/container permissions and must be tested carefully.
- KV cache quantization: test conventional cache options first, such as `q8_0` or `q4_0`, unless a verified fork-specific TurboQuant lane is intentionally selected.
- Context size: start smaller than headline context claims and expand only after memory, latency, and stability are understood.
- Speculative decoding: do not start here. MoE routing and hybrid recurrent/attention behavior may make speculative verification less clean than with dense models.

Exact flag names and valid values are runtime-specific and must be confirmed against the selected llama.cpp build or fork before execution.

## 7. Benchmark Matrix

Future benchmark rows should vary one major axis at a time.

Minimum axes:

- model artifact and quantization;
- runtime source: upstream llama.cpp versus specific fork;
- MoE CPU/GPU placement;
- KV cache type;
- context size;
- batch and prompt-processing settings;
- `--no-mmap` on/off;
- `--mlock` on/off where permitted;
- GPU offload strategy;
- workload prompt class.

Each row should record tokens per second, time to first token, prompt-processing speed, peak RAM, peak VRAM, CPU load, GPU load, context length, errors, thermal or stability symptoms, and whether output quality is usable for the intended private workflow lane.

## 8. Validation Workloads

Use synthetic and non-sensitive prompts only until the local privacy boundary and runtime stability are proven.

Suggested workload classes:

- short instruction following;
- multi-step reasoning with no private data;
- coding explanation on public toy snippets;
- long-context retrieval from synthetic text;
- structured JSON output with a small schema;
- refusal/boundary behavior for secrets or private-data requests;
- extended run stability with repeated prompts;
- restart/reload behavior.

Do not benchmark against private files, secrets, logs, Gmail, Telegram, LegalPrivate, cloud drives, client data, financial data, or production OpenClaw state.

## 9. Success Criteria

The benchmark is successful only if it produces a specific fit verdict with evidence.

Minimum evidence:

- exact model artifact and checksum or equivalent identity;
- exact runtime/fork and commit;
- exact quant and KV cache settings;
- exact placement settings;
- stable launch and clean shutdown behavior in the benchmark lane;
- measured RAM and VRAM envelope;
- measured tokens per second and first-token latency;
- tested context size;
- reproducible workload results;
- known failure states;
- rollback notes.

Fit outcomes:

- not able to run this workload;
- not able unless the model, quant, runtime, memory plan, or hardware changes;
- likely too large, but bounded install/test run is reasonable;
- able to run, but smoother with specific modifications;
- able to run normally;
- running with all required tests passed.

## 10. OpenClaw Routing Boundary

This candidate must not become production PI, Chief, Cassandra, routing, approval, or execution infrastructure from benchmark enthusiasm alone.

Allowed future role if validated:

- experimental local-private reasoning lane;
- PI Local helper candidate;
- benchmark evidence for the future Hardware Fit Analyzer;
- model-policy input for later routing discussions.

Denied current role:

- default OpenClaw brain;
- Chief/Cassandra production router;
- approval authority;
- autonomous execution worker;
- source of truth for private workflow claims;
- replacement for evidence/freshness receipts.

## 11. Rollback And Cleanup Plan

A future approved benchmark should define rollback before installation.

Rollback planning should cover:

- where model artifacts are stored;
- how build products or forks are isolated;
- how environment variables or config files are avoided or reverted;
- how benchmark logs are separated from private data;
- how running processes are stopped in the approved lane;
- how disk usage is measured before and after;
- how to remove only benchmark-created files without touching unrelated OpenClaw storage.

No cleanup, deletion, service stop, or runtime mutation is authorized by this document.

## 12. Recommended Next Move

Create a future bounded benchmark packet before any install.

That packet should include:

- exact target hardware snapshot;
- exact candidate model and artifact source;
- runtime/fork selection;
- flags to test;
- benchmark matrix;
- synthetic validation prompts;
- success criteria;
- failure states;
- rollback plan;
- decision gate for whether PI Local can use the model experimentally.

The next concrete action is planning the benchmark lane, not downloading or running the model.

## 13. What This Does Not Authorize

This document does not authorize:

- model download;
- llama.cpp build or fork checkout;
- Ollama or LM Studio runtime changes;
- package installation;
- GPU driver changes;
- service start/stop;
- router changes;
- OpenClaw production model use;
- provider/model calls against private data;
- inspection of secrets, private files, logs, Gmail, Telegram, LegalPrivate, client data, financial data, cloud drives, or runtime state;
- storage cleanup, migration, deletion, or movement;
- committing changes.

This is only the planning lane for a future bounded local model benchmark.