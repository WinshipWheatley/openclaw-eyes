# Dependency and Execution Plan

## Context Relative to Opus's Current Batch
Opus is currently orchestrating the Gig-to-Cash (G2C) framework, focusing on isolated databases, strict JSON serialization (G2C-005), and robust domain models. The Evidence Pilot infrastructure is partially shared, but Legal Message Evidence introduces much higher security and privacy requirements (Tier 4 Legal Sealed Evidence).

## Recommended Plan: Partially Parallel, Partially Serial

### 1. Parallel (Can Proceed Safely Now)
- **Extraction-Tool Comparison & Selection:** Operator determines the source extraction method (manual).
- **Message Evidence Schema (Drafting):** Sonnet can draft the dataclasses and schemas (`ar_message_evidence.py`) based on the Audit design, using synthetic data ONLY.
- **Synthetic Test Corpus Generation:** Create the `synthetic_sms.db` with the two-phone scenarios.
- **Search Evaluation Plan:** Design the exact/semantic search wrappers.

### 2. Prerequisite / Series (Must Complete Before Raw Ingestion)
These items **MUST** be implemented by Opus/Security teams *before* any live evidence is ingested:
- **Dedicated Legal Sealed Storage:** OS-level directory separation.
- **Encrypted Token Vault:** Case-scoped, irreversible for LMs, detokenized only at the boundary.
- **Agent Permission Restricting:** Revoking raw SQLite/Bash access to Legal Sealed paths for builder agents.
- **Raw-Data Logging Prevention:** Ensuring logging interceptors scrub raw values globally.

### 3. Smallest Safe Next Engineering Unit
**Next Unit (Sonnet Task):** Draft the `MessageEvidenceRecord` and `TokenizedMessageRecord` immutable dataclasses (similar to G2C records), enforcing required fields (timestamps, sender/recipient endpoints, hashes) and rejecting missing critical evidence structures. **Strictly synthetic tests only.**
