# Tool Inventory Read-Model v0

Evidence:
- Latest inventory run `toolrun_e495bbed1f000fac8585` observed 63 candidates: detected=15, not_detected=48.
- Detected tools: `docker` (Docker version 28.2.2, build 28.2.2-0ubuntu1~24.04.1), `aider` (aider 0.86.2), `claude` (2.1.108 (Claude Code)), `code` (1.120.0), `codex` (codex-cli 0.130.0), `gh` (gh version 2.88.1 (2026-03-12)), `git` (git version 2.43.0), `ollama` (ollama version is 0.20.2), `node` (v24.14.0), `npm` (11.9.0), `pip` (pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.12)), `uv` (uv 0.11.8 (x86_64-unknown-linux-gnu)), `python3` (Python 3.12.3), `make` (GNU Make 4.3), `rg` (ripgrep 15.1.0 (rev af60c2de9d)).
- Not detected sample: `appsmith`, `appwrite`, `directus`, `pocketbase`, `docker_compose`, `podman`, `ansible`, `caddy`, `coolify`, `dokku`, `helm`, `kubectl`, `cursor`, `syncthing`, `llama_cli`, `llama_cpp` plus 32 more.
- High-risk detected tools: `docker` (Docker version 28.2.2, build 28.2.2-0ubuntu1~24.04.1), `ollama` (ollama version is 0.20.2).
- Local LLM findings: `llama_cli`, `llama_cpp`, `llm`, `ollama` (ollama version is 0.20.2).
- SQLite findings: `datasette`, `litestream`, `sqlite3`, `sqlite_utils`.

Boundary:
- Installed does not mean approved.
- Detected does not mean integrated.
- Available does not mean authorized.
- Ollama installed does not mean models may be listed, pulled, run, or used by agents.
- Docker installed does not mean containers may be built, pulled, run, or composed.
- This export reads existing SQLite inventory rows only; it does not probe tools.

Blocked:
- tool_activation_allowed=false; integration_authority=false; runtime_authority=false.
- model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false; network_authority=false.
- No installs, upgrades, removals, git clones, remote access, server starts, daemon starts, model pulls, model runs, or container runs are authorized.

Next safe move:
- Use this read-model for inspection only; any future tool integration, sandbox, local model, deployment, sync, or client-capsule lane needs separate operator-scoped approval and tests.
