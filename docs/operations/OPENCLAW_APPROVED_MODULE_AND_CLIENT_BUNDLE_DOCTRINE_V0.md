# OpenClaw Approved Module and Client Bundle Doctrine v0

## Purpose

OpenClaw is moving from Winship's personal governed system toward a reusable local-first operating substrate. The reusable unit is an approved module. The delivery unit for a friend, company, client, or internal test is a local bundle manifest or generated deployment plan.

OpenClaw Core remains canonical. Client/project bundles are not new authority over Core.

## Approved Module Registry

The approved module registry records reusable capability posture. It is planning metadata by default. A module record does not activate code, grant runtime authority, approve integrations, create repos, deploy systems, call APIs, or authorize sends.

Required module metadata fields:

| field | meaning |
| --- | --- |
| `module_id` | Stable module identifier. |
| `version` | Version of the module contract. |
| `display_name` | Operator-readable name. |
| `category/world` | Product category or OpenClaw world. |
| `capabilities` | Bounded capabilities provided or planned. |
| `required_inputs` | Required non-secret inputs or metadata. |
| `optional_inputs` | Optional non-secret inputs. |
| `sensitive_input_policy` | How sensitive inputs are blocked, redacted, vaulted, tokenized, or summarized. |
| `no_go_data_classes` | Data classes the module must not ingest or return to Core. |
| `allowed_authority_level` | Maximum authority in v0, normally `planning_only` or `metadata_only`. |
| `dependencies` | Other modules or read-models used as metadata dependencies. |
| `tests_required` | Tests needed before a module can be selected or advanced. |
| `client_safe` | Whether the module is safe to select for client/friend/company bundles by default. |
| `core_only` | Whether the module must stay inside OpenClaw Core. |
| `report_bridge_summary_allowed` | Whether sanitized status/proof may return through Report Bridge. |

## Bundle Manifest

A bundle manifest is a local planning artifact. It turns a structured pain point into a conservative list of selected modules, missing inputs, blocked modules, sensitivity posture, and report bridge rules.

The manifest must include:

- bundle identity and target context.
- selected modules and blocked modules.
- missing inputs.
- sensitive data policy.
- report bridge policy.
- local-only requirements.
- explicit `github_packaging_allowed=false`.
- explicit `deployment_allowed=false`.
- explicit `runtime_authority=false`.
- notes for the operator.

## Client and Private Data Rule

Client systems may process their sensitive data locally, but OpenClaw Core must receive only sanitized Report Bridge summaries unless the operator explicitly approves a specific data transfer.

Core should see status, proof, version, health, blockers, and receipt summaries. Core should not see raw client/customer records, bank data, privileged material, private files, inbox bodies, spreadsheet cells, credentials, tokens, or client-specific private content.

## PII Rule

PII is either:

- not collected,
- redacted,
- tokenized,
- locally vaulted, or
- summarized into non-identifying status before returning to Core.

Any module that needs PII must be marked `local_only_required` or `needs_operator_review` until a later lane defines storage, vaulting, redaction, receipts, and approval policy.

## GitHub Packaging Rule

No automatic GitHub repo creation, remote push, deployment, or network integration is allowed until a later explicit lane. Stage 2 may only build local manifest/scaffold logic if the implementation spec approves it and tests prove `github_packaging_allowed=false`, `deployment_allowed=false`, and `runtime_authority=false`.

## Mission Control Rule

Mission Control shows module and bundle posture, proof, readiness, blockers, and sanitized Report Bridge status. It must not show raw client data, private body text, spreadsheet cells, credentials, Telegram content, bank data, legal/tax/private roots, or runtime logs with sensitive content.

## Authority Defaults

Default posture for every module and bundle is:

- `runtime_authority=false`
- `deployment_allowed=false`
- `github_packaging_allowed=false`
- `external_api_allowed=false`
- `model_call_allowed=false`
- `send_allowed=false`
- `approval_bypass_allowed=false`
- `client_private_data_export_allowed=false`

Any future exception must be explicit, receipt-backed, test-backed, capability-scoped, and approved through the existing OpenClaw authority path.
