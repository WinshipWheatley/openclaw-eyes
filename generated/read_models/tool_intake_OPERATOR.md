# Tool Intake Read-Model v0

What this is:
- A generated policy read-model over `tool_intake_*` SQLite candidate rows.
- It is safe metadata for inspection by operators, future agents, and Mission Control.

What this is not:
- It is not approval, integration authority, runtime authority, install authority, or execution authority.
- It does not include install commands, official URL guesses, license guesses, latest-version guesses, secrets, or private data.

Evidence:
- Latest intake run `toolintake_2026_05_14_v0` contains 39 candidates, 33 inventory-linked candidates, and 2 installed candidates.
- Installed candidates: `docker` (observed_only, observed_installed, risk=high), `ollama` (observed_only, observed_installed, risk=high).
- High-fit candidates: `pocketbase` (candidate, not_detected, risk=medium), `devbox` (candidate, not_detected, risk=medium), `grype` (candidate, not_detected, risk=medium), `syft` (candidate, not_detected, risk=medium), `trivy` (candidate, not_detected, risk=medium), `litestream` (candidate, not_detected, risk=medium), `datasette` (candidate, not_detected, risk=medium), `copier` (candidate, not_detected, risk=low), `sqlite3` (candidate, not_detected, risk=low), `sqlite_utils` (candidate, not_detected, risk=low).
- High-risk candidates: `ansible` (deferred, not_detected, risk=high), `coolify` (deferred, not_detected, risk=high), `docker` (observed_only, observed_installed, risk=high), `ollama` (observed_only, observed_installed, risk=high), `wireguard` (deferred, not_detected, risk=high), `sops` (deferred, not_detected, risk=high), `headscale` (deferred, not_detected, risk=high), `meshcentral` (deferred, not_detected, risk=high), `openbao` (deferred, not_detected, risk=high).
- Sandbox-later candidates: `caddy` (sandbox_later, not_detected, risk=medium), `syncthing` (sandbox_later, not_detected, risk=medium), `llama_cpp` (sandbox_later, not_detected, risk=medium), `netdata` (sandbox_later, not_detected, risk=medium), `uptime_kuma` (sandbox_later, not_detected, risk=medium).
- Client-capsule candidates: `pocketbase` (candidate, not_detected, risk=medium), `devbox` (candidate, not_detected, risk=medium), `grype` (candidate, not_detected, risk=medium), `syft` (candidate, not_detected, risk=medium), `trivy` (candidate, not_detected, risk=medium), `copier` (candidate, not_detected, risk=low), `coolify` (deferred, not_detected, risk=high), `docker` (observed_only, observed_installed, risk=high), `appwrite` (deferred, not_detected, risk=medium), `directus` (deferred, not_detected, risk=medium), `caddy` (sandbox_later, not_detected, risk=medium), `dokku` (deferred, not_detected, risk=medium), `syncthing` (sandbox_later, not_detected, risk=medium), `appsmith` (deferred, not_detected, risk=medium), `grafana` (deferred, not_detected, risk=medium), `loki` (deferred, not_detected, risk=medium), `opentelemetry` (deferred, unknown, risk=medium), `prometheus` (deferred, not_detected, risk=medium), `uptime_kuma` (sandbox_later, not_detected, risk=medium), `cookiecutter` (candidate, not_detected, risk=low).

Boundary:
- No candidate is approved.
- No candidate is integrated.
- Docker remains high-risk observed-only metadata; containers are not authorized.
- Ollama remains high-risk observed-only metadata; model execution is not authorized.

Blocked:
- tool_install_allowed=false; tool_execution_allowed=false.
- approval_authority=false; integration_authority=false; runtime_authority=false.
- network_authority=false; model_execution_allowed=false; container_execution_allowed=false; remote_access_allowed=false.

Next safe move:
- Use this read-model for policy inspection only; any future sandbox, install, integration, deployment, model, remote-access, or client-capsule action needs a separate scoped lane and operator approval.
