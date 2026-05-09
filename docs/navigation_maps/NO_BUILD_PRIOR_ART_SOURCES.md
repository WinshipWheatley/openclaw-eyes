# No-Build / Prior-Art Sources Guide

**Artifact Type:** Discovery Guide
**Status:** This is a prior-art discovery artifact. It does **not** map full territory and does **not** grant approval to install, connect, download, or use any listed tool or platform.

**Purpose:** Prevent reinventing existing tools. Future workers must consult these sources to check for existing prior art before proposing custom builds.

## Rules

1. **Check Prior Art:** You must check prior art before proposing custom builds for common functions.
2. **Record Rejections:** If existing tools are rejected in favor of a custom build, you must record *why* they were rejected.
3. **Prefer Adopt/Adapt:** Prefer adopting or adapting an existing tool over a custom build, provided that privacy, authority, maintenance, license, data residency, and operator-control constraints are satisfied.
4. **Popularity is Not Fit:** Popularity alone is not proof of fit for OpenClaw's constraints.
5. **Quality Control:** If a recommended source becomes stale, spammy, abandoned, low-signal, or loses top quality, demote or replace it.

## Replaceable Source Families

These sources are current as of creation but are subject to replacement based on freshness and quality.

### 1. Awesome Ecosystem
- [Awesome Self-Hosted](https://github.com/awesome-selfhosted/awesome-selfhosted)
- [Awesome Open Source Alternatives](https://github.com/RunaCapital/awesome-oss-alternatives)
- [Free-for-Dev](https://github.com/ripienaar/free-for-dev)
- Relevant domain-specific Awesome lists

### 2. Aggregators / Directories
- [OpenAlternative.co](https://openalternative.co/)
- [Selfh.st](https://selfh.st/)
- [SaaSHub](https://www.saashub.com/)
- Open-Awesome / searchable Awesome-list indexers

### 3. GitHub Topics / No-Build Stack
- `low-code`
- `baas`
- `headless`
- `boilerplate`
- `starter-kit`
- `self-hosted`

## Required Prior-Art Checks

A prior-art check using the sources above is **mandatory** before proposing or building custom solutions. Use the following table to map categories to required constraints:

| Build Category | Sources to Check | Fit Constraints | Rejection Proof Required |
| :--- | :--- | :--- | :--- |
| Dashboards / Internal Tools | Awesome Self-Hosted, OpenAlternative | Privacy, self-hostable, low maintenance | Why existing low-code/dashboard builders fail requirements |
| Auth | OpenAlternative, GitHub Topics | License, data residency, integration ease | Why existing self-hosted auth (e.g. Authelia, Keycloak) is unfit |
| CRUD / Admin Apps | Awesome OSS Alternatives, Selfh.st | Operator-control, local database support | Why existing admin panels (e.g. Appsmith, ToolJet) cannot be adapted |
| Workflow Automation / Webhooks / Cron | Awesome Self-Hosted, GitHub Topics | Local execution, webhook security | Why existing tools (e.g. n8n, Node-RED) are rejected |
| CMS / Document Management | SaaSHub, Awesome Self-Hosted | File-based backing, markdown support | Why existing headless CMS or doc engines fail |
| Logging / Monitoring / Search | OpenAlternative, Free-for-Dev | Privacy, resource footprint | Why existing local observability stacks are rejected |
| File Sharing | Awesome Self-Hosted, Selfh.st | Local-only access, secure links | Why existing file-sharing tools fail OpenClaw constraints |

## Freshness and Replacement Protocol
Update this guide when a better directory, list, or source appears. This guide is not permanent authority and must remain a fresh reflection of the best discovery paths. Stale sources must be demoted or removed.
