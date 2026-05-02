# Hermes Advisory Packet Contract

Status: static contract. This document does not authorize Hermes runtime execution, provider or model fallback, live service inspection, queue mutation, canonical writes, approval authority, Telegram or Gmail actions, installer runs, service or timer operations, `.mcp.json` edits, private-data access, or broad source discovery.

## Purpose

Hermes may act as an advisory consultant only when it receives a bounded packet that names its allowed source material and withheld surfaces. Hermes output is a non-canonical proposal memo for operator, Chief, or Guardian review. The memo may inform a future human-controlled promotion path, but it cannot promote itself and does not become canonical by presence.

## Packet Shape

A valid Hermes advisory packet must explicitly include these fields:

| Field | Required value or rule |
| --- | --- |
| `packet_id` | Stable local identifier. |
| `purpose` | Advisory purpose for this bounded packet. |
| `source_set_name` | Human-readable name for the explicit source set. |
| `allowed_read_surfaces` | Exact repo docs/tests/source references allowed for this packet. No broad repo roots, runtime state, logs, secrets, vaults, Legal/private matter data, Gmail bodies, live services, installed user units, queues, or `.mcp.json`. |
| `withheld_surfaces` | Must name withheld runtime state, logs, secrets, vaults, Legal/private matter data, Gmail bodies, queues, live services, installed user units, provider/model execution, and canonical write surfaces. |
| `sensitive_data_policy` | Must state that private data is not allowed. |
| `authority_level` | `advisory_only` |
| `execution_allowed` | `false` |
| `canonical_write_allowed` | `false` |
| `queue_mutation_allowed` | `false` |
| `approval_authority_allowed` | `false` |
| `provider_fallback_allowed` | `false` |
| `live_service_inspection_allowed` | `false` |
| `private_data_allowed` | `false` |
| `output_kind` | `non_canonical_advisory_memo` |
| `promotion_required` | `explicit_human_or_chief_controlled_promotion` |

## Output Memo Shape

A valid Hermes advisory output must explicitly include:

| Field | Required value or rule |
| --- | --- |
| `observations` | Evidence-grounded observations from the allowed packet only. |
| `risks` | Risks or uncertainties visible from the allowed packet only. |
| `suggested_next_slices` | Optional next slices phrased as suggestions, not decisions. |
| `evidence_refs` | References to allowed source material used by the memo. |
| `assumptions` | Assumptions and missing context. |
| `withheld_surfaces` | The packet's withheld surfaces, preserved in the memo. |
| `non_canonical_notice` | Must state that the memo is non-canonical, no decisions were made, no commands were executed, and no canonical writes were made. |
| `commands_executed` | `false` |
| `decisions_made` | `false` |
| `canonical_writes_made` | `false` |

## Fail-Closed Rules

Reject the packet or memo if any of these are true:

- Any permission field is missing or set to `true`.
- The packet omits required withheld surfaces.
- Allowed reads are broad roots or include runtime state, logs, secrets, vaults, Legal/private matter data, Gmail bodies, queues, live services, installed user units, provider/model execution, or `.mcp.json`.
- The memo omits the non-canonical notice.
- The memo claims Hermes made a decision, approved work, executed commands, mutated queues, inspected live services, used provider fallback, or wrote canonical state.
- The memo's withheld-surface list is narrower than the packet's withheld-surface list.

## Implementation Boundary

`hermes_advisory_packet.py` is a pure stdlib helper for building and checking local dictionaries. It must not import or call Hermes runtime modules, subprocess, shell execution, provider/model clients, Gmail, Telegram, Guardian send paths, live service inspection, logs, secrets, vaults, private data, or Hermes runtime state.

Passing this contract means only that a packet or memo is shaped safely enough for human review. It does not run Hermes, grant Hermes broader access, make Hermes canonical, or approve any action.
