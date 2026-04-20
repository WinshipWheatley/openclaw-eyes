# Validation Policy

This document defines the "Definition of Done" for changes to the OpenClaw stack. It specifies the mandatory validation levels required before a change is considered stable and ready for commit.

## 1. Validation Levels

| Level | Name | Scope | Typical Command |
| :--- | :--- | :--- | :--- |
| **L1** | **Smoke** | Syntax and basic loading. | `python3 -m py_compile <file>` |
| **L2** | **Targeted** | Specific function/module logic. | `pytest tests/test_<module>.py` |
| **L3** | **Replay** | High-fidelity workflow validation. | `morning_brief_harness.py --fixture <name>` |
| **L4** | **Full Suite** | Global boundary and regression check. | `PYTHONPATH=. pytest tests/` |

## 2. Mandatory Requirements by Change Type

### Type A: Hygiene & Refactor (No behavior change)
*Example: Moving a helper to a utility module, updating imports.*
- **Required**: **L1** (all touched files), **L2** (direct callers), **L4** (if touching Utility Core).
- **Goal**: Ensure zero regressions in existing interfaces.

### Type B: Bug Fix (Logic correction)
*Example: Fixing a date parser, correcting a timeout value.*
- **Required**: **L2** (reproduce failure first, then verify fix). 
- **Optional but Recommended**: **L3** if the bug affected a staged workflow.

### Type C: Feature / New Capability
*Example: Adding a new briefing slot, wiring a new capability.*
- **Required**: **L2** (new tests must be added), **L3** (live capture + replay verify), **L1**.
- **Dashboard**: If the feature has a UI component, manual verification of `dashboard_gen.py` output is required.

### Type D: Prompt or Model Changes
*Example: Updating a persona brief, switching a default model lane.*
- **Required**: **L3** (**Recorded-Replay mode**). 
- **Comparison**: You MUST compare the new output against the previous recorded baseline to ensure quality did not degrade.

## 3. The "Harness-First" Rule
For any change affecting the **Morning Briefing** or **End of Day Review**, validation via the corresponding Python harness is MANDATORY. Unit tests alone are insufficient for these high-context synthesis paths.

## 4. Virtualenv Enforcement
Tests involving audio or heavy dependencies (`numpy`, `piper`) MUST be run within the `chief_env` virtualenv:
```bash
/home/openclaw/chief_env/bin/python -m pytest tests/test_cassandra_voice.py
```
