# Validation Map

This map provides a deterministic lookup for selecting the correct tests and harnesses based on the files or systems modified. Use this as a mandatory pre-completion checklist.

## 1. Core Logic & Routing

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `chief_llm.py` | `tests/test_chief_llm_router.py` | — |
| `chief_router.py` | `test_cassandra_routing.py` (root) | — |
| `chief_approval_brain.py` | `tests/test_chief_approval_brain.py` | `guardian_schema_harness.py` |
| `agent_task_proposals.py` | `tests/test_agent_task_proposals.py` | — |
| `chief_session_manager.py`| `tests/test_chief_session_manager.py` | — |

## 2. Cassandra Briefings

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `cassandra_briefing_brain.py`| `tests/test_cassandra_briefing_brain.py` | `morning_brief_harness.py` |
| `chief_ops_reporter.py` | `tests/test_cassandra_briefing_context.py` | `morning_brief_harness.py` |
| `cassandra_mode.py` | `tests/test_cassandra_morning_policy.py`| — |

## 3. Outreach & Identity

| Area / File | Primary Test(s) | Harness / Replay |
| :--- | :--- | :--- |
| `cassandra_identity.py` | `tests/test_cassandra_identity.py` | — |
| `cassandra_outreach.py` | `tests/test_cassandra_outreach.py` | — |
| `inbox_parser.py` | `tests/test_inbox_parser.py` | — |
| `chief_guardian_sender.py`| `tests/test_chief_acceptance_gate.py` | — |

## 4. Subsystem Components

| Area / File | Primary Test(s) | Notes |
| :--- | :--- | :--- |
| `cassandra_voice.py` | `tests/test_cassandra_voice.py` | Requires `chief_env` virtualenv |
| `dashboard_gen.py` | `tests/test_agent_task_proposals.py` | Verifies advisory lane rendering |
| `finance_state.py` | `tests/test_cassandra_payment_verify.py`| — |

## 5. Global Readiness (Full Suite)
If multiple core boundaries are touched (e.g., refactoring `chief_env` or `cassandra_mode`), run the full suite:
```bash
PYTHONPATH=. pytest tests/
```
