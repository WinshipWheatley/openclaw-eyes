# OpenClaw Module Manifest Validation Contract v0

## 1. Source Basis

This contract is based only on:

- `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md`
  - commit: `dcbc5188bfd2ae3556184865fb69c89c6a992043`
- `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md`
  - commit: `d5eda97795bcf70480914f4253479d82f2b8cc9d`
- `docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md`
  - commit: `d1873cc7f5388570eb32a11ce6dfe9583a1d7aac`

This contract introduces deterministic validation for inert module manifest
example documents. It does not create runtime authority, runtime memory, SQLite
writes, broker connections, agent wiring, private data reads, customer
deployment, autonomous action, or live system readiness.

## 2. Purpose And Authority Boundary

The purpose of this contract is to define what a small static validator may
prove about synthetic module manifest examples.

The validator may prove:

- required draft schema fields are present
- authority labels stay within a documented non-runtime set
- NOT_READY boundaries are explicit
- examples do not permit blocked activation paths
- examples remain synthetic, inert, and non-authoritative

The validator may not prove:

- a module is active
- a module is deployable
- a service is healthy
- a broker is connected
- an agent is wired
- a customer workflow is ready
- sensitive data may be processed
- SQLite or generated runtime status may be written

Validation output is evidence for review only. It is not activation authority.

## 3. Validator Scope

The validator is intentionally narrow:

- default input: `docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md`
- optional input: explicit file paths passed on the command line
- parsed content: fenced `yaml` or `yml` manifest blocks in Markdown files
- parser class: deterministic, standard-library-only structural text parser
- output: process exit code plus human-readable validation findings

The validator must not:

- scan broad source sets
- read no-go categories
- ingest SQLite
- write SQLite
- create runtime memory
- connect brokers
- wire agents
- call external services
- read private data
- deploy customer workflows
- claim live readiness

## 4. Required Manifest Fields

Every manifest example must include these top-level fields:

- `module_id`
- `module_family`
- `purpose`
- `authority_level`
- `allowed_inputs`
- `forbidden_inputs`
- `outputs_artifacts`
- `approval_gates`
- `sensitivity_gates`
- `dependencies`
- `tests_required`
- `receipts_required`
- `disable_path`
- `rollback_path`
- `NOT_READY_boundaries`

Missing fields are validation failures.

## 5. Allowed Authority Levels

The validator accepts only this documented authority set:

- `docs_only`
- `proposal_only`
- `read_only_after_approval`
- `dry_run_after_approval`
- `runtime_blocked`

No accepted authority level grants write, send, mutate, deploy, broker,
autonomous, sensitive-data, customer, or runtime activation authority.

## 6. Required NOT_READY Boundaries

Every manifest example must list baseline blocked uses in
`NOT_READY_boundaries`:

- runtime activation
- customer deployment
- autonomous action
- sensitive-data processing
- broker connection
- agent wiring
- SQLite write
- live system health claim

Additional NOT_READY boundaries are allowed when they further restrict the
manifest.

## 7. Forbidden Permission Claims

Manifest examples fail validation if they permit or positively claim any of the
following:

- runtime activation
- SQLite writes
- broker connections
- agent wiring
- private data reads
- customer deployment
- autonomous action
- live system state or live system health readiness

The validator distinguishes blocked-use notices from permission claims. Listing
a term inside `forbidden_inputs`, `sensitivity_gates`, `approval_gates`, or
`NOT_READY_boundaries` is allowed when the surrounding text denies, blocks, or
gates the capability.

## 8. Synthetic And Inert Requirement

Each example must be explicitly synthetic and non-active.

The section around each manifest block must include:

- a synthetic/example marker
- an inert or non-active marker such as `does not describe an active`, `inert`,
  or `not activation authority`

This prevents a valid-looking field set from being mistaken for an active
module declaration.

## 9. Test Contract

Focused tests must prove:

- the committed synthetic examples pass validation
- a manifest missing a required field fails validation
- a manifest with a forbidden activation claim fails validation

Tests must use temporary synthetic files for negative cases. They must not read
private data, write SQLite, connect brokers, wire agents, deploy customer flows,
or mutate runtime state.

## 10. Operational Boundary

This contract is READY for inert deterministic validation of synthetic manifest
example documents.

This contract is NOT_READY for:

- runtime activation
- runtime registry creation
- SQLite writes
- broker connections
- agent wiring
- private data reads
- customer deployment
- autonomous action
- sensitive-data processing
- generated-status mutation
- live system readiness claims

Future movement beyond this contract requires separate approval, tests,
receipts, and a committed activation-specific lane.
