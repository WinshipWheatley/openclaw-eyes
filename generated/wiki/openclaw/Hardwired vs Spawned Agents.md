# Hardwired vs Spawned Agents

OpenClaw has two different ideas that can sound similar: named agents and spawned package workers.

Named agents are stable roles. Spawned workers are bounded execution threads.

## Hardwired Named Agents

Hardwired agents include Cassandra, Chief, Hermes, Guardian, Niles, Clara, and OpenClaw.

They give OpenClaw stable identity, voice, routing, and authority boundaries. Some have sidecar or read-model functions, but they are not automatically broad executors.

In plain terms:

- Cassandra captures intake, work logs, and human follow-up.
- Chief diagnoses blockers and packages bounded work.
- Hermes recommends architecture and lane sequence.
- Guardian names protected gates and blocks unsafe action.
- Niles handles music, art, and creative direction.
- Clara prepares polished external-facing copy for review.
- OpenClaw reports neutral system status.

These names usually mean "who should speak or gate this," not "who can take any action."

## Spawned Package Workers

A spawned package worker exists for one task package.

It should have:

- a package id
- bounded inputs
- allowed actions
- blocked actions
- provider gates
- result receipts
- operator review when required
- a business action gate before protected actions

The worker can be PC_CODEX, MAC_CODEX, or a future LM2 child worker. It may carry a speaker or character context so the result sounds right, but that context does not grant more authority.

The package defines authority. The persona does not.

## LM2 Child Cage

The LM2 child-worker path is contract-only or dry-run unless a future gated package explicitly changes that.

Current default posture:

- no hidden children
- no swarms
- no recursive spawning
- no live business action children
- max children defaults to zero
- Guardian involvement is required for protected or scope-expanding child packages
- receipts are required

Child workers are not a swarm. They are bounded package workers or they do not run.

## Common Questions

### What is Chief versus a spawned worker?

Chief is a stable diagnostic role. Chief explains gates and shapes bounded task packets.

A spawned worker is a task-specific execution thread. It only acts inside one package and returns a receipt.

### Can Cassandra execute this?

Cassandra can capture intake, prepare calm operator copy, and stage follow-up for review.

Execution still needs the right package, provider gate, and operator approval.

### Can a child agent use tools?

Only if the package grants the tool scope.

Current LM2 child-worker behavior is contract-only or dry-run, and live business tools remain blocked.

### Does speaker_ref change authority?

No. speaker_ref chooses the voice and routing identity for the response.

It does not allow sending, submitting, ledger changes, workbook edits, paid marking, or child spawning.

### What can run while I sleep?

Planning, local read-model generation, safe validation, and dry-run package staging can be acceptable when already scoped.

Email, Coupa, ledger changes, workbook mutation, PDF export, paid marking, and child-agent execution need explicit gates.

## Operator Rule

Use named agents for explanation, routing, voice, and gates. Use spawned workers only for explicit package-bound work.

Never treat a character voice as permission to act.

## Proof Refs

Proof is collapsed by default in operator surfaces.

- generated/read_models/agent_voice_routing_contract.json
- generated/read_models/agent_voice_profiles.json
- generated/read_models/workflow_package_queue_contract.json
- generated/read_models/system_question_answer_contract.json
- generated/read_models/openclaw_lm_child_package_gate.json
- generated/read_models/agentic_chain_inspector.json
