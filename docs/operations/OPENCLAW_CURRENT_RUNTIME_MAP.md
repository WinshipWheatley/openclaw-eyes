# OpenClaw Current Runtime Map v0

**Last Updated:** Saturday, May 9, 2026
**Status:** Empirical Inventory (Docs-only)

## Core Runtime Components

| Component | Status | Entrypoint | Caller | Owns | Must Not Own | Current Proof | Next Test | Business Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cassandra Listener** | LIVE | `cassandra_listener.py` | `start_cassandra_core.sh` | Telegram incoming updates | Chief approval logic | `cassandra_listener.out` (May 9) | /brief command parsing | Primary operator interface |
| **Cassandra Watcher** | LIVE | `cassandra_watcher.py` | `start_cassandra_core.sh` | External state monitoring | User chat responses | `cassandra_watcher.out` (May 9) | Trigger event & check response | Proactive awareness |
| **Cassandra Briefing Scheduler** | LIVE | `cassandra_briefing_scheduler.py` | `start_cassandra_core.sh` | Briefing generation timing | Content generation | `cassandra_briefing_scheduler.out` (May 9) | Cron execution verification | Automated context delivery |
| **Chief Guardian Listener** | LIVE | `chief_guardian_listener.py` | `start_chief_logged.sh` | Approval workflow intake | Side effect implementation | `guardian_listener.out` (May 9) | Inject dummy approval request | Core safety/approval layer |
| **Hermes Gateway** | LIVE | `sidecars/hermes/run_agent.py` | Background process | Bounded advisory proposals | Canonical system state | `hermes_home/sessions/` (May 9) | Proposal schema compliance | Safe exploration/advisory |
| **Ollama Server** | LIVE | `ollama_serve.out` | Systemd `ollama.service` | LLM inference serving | Application logic | `ollama_serve.out` (May 9) | 8b vs 35b latency check | Local-first intelligence |
| **Gmail Broker** | LIVE | `google_access_broker.py` | `cassandra_brain.py` | API access control | Intent classification | `google_access_audit.jsonl` (May 9) | Access w/ denied intent | Privacy/Security gate |
| **Map Room / Architecture Gate** | EXPERIMENTAL | `architecture_map_gate.py` | `openclaw_receipts.py` | Request classification | Execution authority | `openclaw.architecture_map_gate_status` receipt | Integrate as build gate | Build safety/Prior-art check |
| **Telegram Transport** | LIVE | `gateway/platforms/telegram.py` | Hermes / Cassandra | Real-time messaging | Content decision-making | Active log connections (May 9) | Throughput burst test | Low-latency interaction |
| **Logs/Receipts** | LIVE | `/mnt/c/OpenClaw/logs` | System-wide | Durable activity record | Runtime state mutation | Log timestamps (May 9) | Log rotation efficiency | Auditability/Empirical truth |
| **Chief Worker (Hub/Spoke)** | UNKNOWN | `chief_worker.py` | `worker.out` | Generic task execution | Direct user interface | `worker.out` active (May 9) | Trace request through router | Redundant legacy (?) |
| **Billing Brain** | DISABLED | `billing_brain.py` | N/A | Financial processing | Gmail/Operator interface | Stale log: March 15 | Wake-up trigger attempt | Pending refactor |
| **Finance Watchdog** | DISABLED | `finance_watchdog.py` | N/A | Finance monitoring | Direct mutation | Stale log: April 1 | Wake-up trigger attempt | Pending refactor |
| **Stale Briefing Workers** | DISABLED | `ceo_briefing_worker.py` | N/A | CEO briefing content | Logic timing | 0-byte logs: March/April | N/A | Redundant |

## Ollama Inventory (May 9)

| Model | Size | Modified | Status |
| :--- | :--- | :--- | :--- |
| `qwen3.6:35b-a3b` | 23 GB | 2 days ago | LIVE (Heavy) |
| `qwen3.6:27b` | 17 GB | 2 days ago | LIVE |
| `qwen3:8b` | 5.2 GB | 2 days ago | LIVE (Fast) |
| `gemma4:31b` | 19 GB | 2 days ago | LIVE |
| `gemma4:26b` | 17 GB | 2 days ago | LIVE |
| `gemma4:e4b` | 9.6 GB | 2 days ago | LIVE |

## Business Ops Spine

The current intended operational flow is designed to be deterministic and safe:

1.  **Operator Prompt:** User provides input via Telegram (Cassandra/Hermes).
2.  **Deterministic Intent:** Intent is classified (e.g., via `decide_gmail_intent`) to bound capability access.
3.  **Context/Capability Packet:** A packet is formed containing only permitted tools and relevant context.
4.  **Permitted Retrieval:** Data is retrieved (e.g., via Gmail Broker) only if the intent matches the policy.
5.  **Cassandra Response/Draft:** A response or side-effect draft is generated.
6.  **Chief/Guardian Approval:** Any mutation or side effect requires explicit approval via the Guardian layer.
7.  **Logged Receipt:** The entire transaction is logged as a durable receipt for audit and validation.

## Unknowns & Risks

- **Chief Hub/Spoke vs. Cassandra:** The degree to which `chief_worker.py` and the legacy router are still active in "canonical" workflows is unproven.
- **Worker Bloat:** `worker.out` is large and active, but its internal role-switching logic is not fully mapped to the new intent gates.
- **Experimental Gates:** `architecture_map_gate.py` is implemented and verified as a substrate but not yet enforced as a mandatory blocking gate for all build agents.
