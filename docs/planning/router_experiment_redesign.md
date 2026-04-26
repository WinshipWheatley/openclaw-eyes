# Router Experiment Redesign Note

**WARNING: Do not apply the `router_experiment_review.patch` wholesale.**
The original experiment introduced highly experimental, architecture-breaking workflow concepts into the synchronous routing layer. This note preserves the useful intent of the experiment while defining a safe, architecturally compliant redesign.

## Useful Features to Preserve
The core goal of using LLMs to normalize complex system artifacts into readable inventories is valuable. We should preserve the ability to:
- **Transform Artifacts:** Convert raw system inspection snapshots into normalized operational findings.
- **Summarize Inventories:** Generate high-level, readable summaries of the normalized inventory.
- **Filter Findings:** Keep the helper logic (e.g., `_filter_transform_findings`) that aggressively shrinks and cleans up raw inspection data before sending it to the LLM.
- **Background Generation:** Run the heavy, long-running (up to 10 minutes) LLM artifact transformation asynchronously so it does not block the user.

## Rejected Implementation Patterns
The following patterns from the original patch violate OpenClaw boundaries and are explicitly rejected:
- **LLM Contract Routing on Global Ingress:** Adding a synchronous 15-second LLM dependency (`infer_intent_contract`) to the critical path of *every* message is too slow and risky.
- **Unmanaged Threads in `chief_router.py`:** Spawning unmanaged `threading.Thread` instances inside the synchronous, pure-function routing layer risks memory leaks, untracked crashes, and orphaned processes.
- **Direct Telegram Sends from Router:** The routing layer importing `send_message` to push alerts breaks the strict `Listener -> Router -> Brain -> Listener` event boundary.
- **Hardcoded Model Calls:** Explicitly calling `gemma4:e4b` bypasses `chief_llm.py`'s centralized contention control, fallback logic, and dynamic lane routing.
- **Polling Crash/Sleep Wrappers:** Catching all exceptions around `app.run_polling()` and sleeping masks fatal startup/auth errors, creating zombie processes. We rely on systemd's `Restart=on-failure` for process resilience.

## Correct Redesign Architecture
To safely implement the artifact transformation and inventory summary features:
1. **Deterministic Intent Only:** The router must use fast, deterministic logic (e.g., regex or a highly optimized classifier) to detect the `artifact_transform` or `inventory_summary` intents.
2. **Immediate Router Response:** The router must remain a pure function that returns a payload immediately (e.g., "I'm building the inventory in the background."). It must not block on long LLM calls or spawn unmanaged threads.
3. **Dedicated Workers/Brains:** Long-running work must be delegated to a dedicated worker script (e.g., `scripts/generate_runtime_inventory.py`) or queued to a specific background brain. The router can trigger this via a non-blocking `subprocess.Popen` call (similar to how the Hermes annex is triggered).
4. **Centralized Model Routing:** All LLM calls must go through `chief_llm` routing functions (like `resolve_local_model`) to ensure proper lane selection and fallback behavior, rather than hardcoding model names.
5. **Standardized Completion Notification:** The background worker should notify the user of completion via the standard `chief_notify.py` mechanism, or by writing a marker file that the listener or dashboard picks up. It should not import Telegram sending libraries directly.

## Proposed Implementation Slices (Smallest-Safe-First)
Implement the redesign in the following isolated steps:

1. **Extract Helpers:** Move the data preparation and filtering logic (`_filter_transform_findings`) into `chief_output_utils.py` or a new `chief_inventory_brain.py`.
2. **Create Standalone Worker:** Create a decoupled script (e.g., `scripts/generate_runtime_inventory.py`) that performs the heavy 600s LLM artifact transformation. Ensure it uses dynamic model routing and standard notification methods.
3. **Add Router Hooks:** In `chief_router.py`, add simple regex intent matching for the new commands. The handler should use `subprocess.Popen` to fire the standalone script and return a synchronous confirmation message to the listener.
4. **Implement Summary Brain:** Build the `inventory_summary` logic into the daily morning synthesis pipeline, or delegate it to a dedicated brain that runs asynchronously when requested.

## Open Questions
- Should the normalized inventory generation become a standard part of the automated `chief_morning_synthesis.py` pipeline instead of (or in addition to) being an on-demand chat command?
- Is `subprocess.Popen` from the router the most robust way to trigger the background worker, or should we introduce a lightweight local task queue (e.g., a simple spool directory) that a separate watcher process consumes?