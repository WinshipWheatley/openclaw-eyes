# Orchestrator Handoff
**Gig-to-Cash Audit Complete.**

## Repository State
The full Gig-to-Cash loop does NOT exist. Currently, the system has a hardcoded set of scripts for Capital Hilton invoice generation, but it lacks openpyxl, bank integrations (Plaid/CashPro), and generalized work-session ledgers.

## Directive
Merge and reconcile your existing work, the Capital Hilton evidence-registry pilot, and the Gig-to-Cash audit. Preserve all three lines of work. Do not restart existing implementations, overwrite Sonnet’s uncommitted T005 changes, or assume an audit gap is missing until repository evidence confirms it. The evidence registry is shared infrastructure; the Gig-to-Cash workflow should extend it rather than create a competing ledger or provenance system.

## Immediate Next Actions for Orchestrator
**G2C-005 is scheduled elsewhere.**
“G2C-005 is assigned to a scheduled Sonnet 4.6 worker. Preserve and reconcile its branch, worktree, logs, handoff, and resulting commit. Do not independently restart G2C-005. After the run, inspect the committed diff and tests before merging. Do not begin G2C-006 until G2C-005 is verified.”

* Scheduled Task Name: `OpenClaw-Sonnet-G2C005-20260625`
* Exact Run Time: `2026-06-25 01:01:00 America/New_York`
* Branch: `agy-sonnet/g2c-005-scheduled-20260626`
* Worktree: `/home/openclaw/worktrees/g2c-005-sonnet`
* Base Commit: `96df352c`
* Spec Path: `/home/openclaw/Operator/G2C-005-SPEC.md`
* Spec ID: `20260625-G2C005-v1`
* Prompt Path: `/home/openclaw/Operator/scheduled/g2c005/SONNET_PROMPT.md`
* Launcher Path: `/home/openclaw/Operator/scheduled/g2c005/run_sonnet_g2c005.sh`
* Status File: `/home/openclaw/Operator/scheduled/g2c005/RUN_STATUS.json`
* Log Dir: `/home/openclaw/Operator/scheduled/g2c005/logs/`

Instructions: Do not duplicate or overwrite this task. Once G2C-005 is finished, review the resulting commit in `agy-sonnet/g2c-005-scheduled-20260626` and merge it. Only then, resume with G2C-006.

### Coordination Workflow Rule
Every future implementation task must begin by reading its durable task file and quoting its acceptance-criteria version or hash into the completion record.

A task may be marked DONE only when:
* The implementation matches the durable contract.
* The focused tests validate that contract.
* The final diff is reviewed for scope.
* The commit is isolated.
* The handoff records the exact commit and test result.

## Recommended Order (Corrected Roadmap)
Do not jump directly into writing Excel after completing the Capital Hilton evidence pilot. A generalized model must be established first to prevent hardcoding assumptions.

1. **Finish the Capital Hilton evidence pilot** (T005–T017).
2. **Define generalized records** (gig, work-session, invoice, expected-receivable).
3. **Define the workbook contract** (file, sheet, writable cells, formulas, protected regions, preservation requirements).
4. **Test read-only workbook inspection** and copy-based round trips.
5. **Implement deterministic workbook materialization.**
6. **Add invoice readiness and controlled sending.**
7. **Add bank transaction ingestion.**
8. **Add cautious payment matching and reconciliation.**

## Legal Message Evidence & PII Directive
Please refer to the complete verified audit in: `/home/openclaw/workspaces/legal_message_evidence_pii_audit/`

**CRITICAL DIRECTIVE:**
> Legal-message evidence is a Legal Sealed data class. Preserve original evidence immediately, but do not ingest raw message history into shared OpenClaw agent infrastructure until OS isolation, evidence provenance, encrypted token mapping, case-scoped access, logging controls, and authorized detokenization are proven. Reconcile this work with the Evidence Pilot, OS-boundary architecture, Write Authority Matrix, deterministic response work, and current Opus branches. Do not create competing provenance or authority systems.
>
> Opus owns the high-risk PII and evidence architecture. Sonnet builders may implement only narrow, durable-spec tasks. Gemini must audit each security boundary and evidence-preservation contract before merge.

**State of PII Infrastructure:**
- *Built:* In-memory tokenization interceptors (`cassandra_pii_hooks.py`, `pii_vault.py`), global Fernet storage, and a synthetic read-model (`token_vault.py`).
- *Missing:* There is NO secure Legal Sealed vault, no case-isolation, and no OS boundaries to protect raw identities from unrestricted shell/SQLite agent access.

**Action Plan:**
- *Manual Now:* Operator must manually acquire, hash, and safely preserve extraction databases (`sms.db`, backups) offline.
- *In Parallel:* Compare extraction tools, draft the immutable `MessageEvidenceRecord` data structures (using synthetic fixtures ONLY), and generate the `synthetic_sms.db` corpus.
- *Must Wait:* Raw message ingestion, LLM tokenized searching, and detokenization utility workflows MUST wait for Opus to establish the isolated Legal Sealed token vault.
- *Collision Risk:* Active Gig-to-Cash and Evidence Pilot branches. DO NOT overwrite `ar_gig_record.py` or its serialization files.
- *Smallest Next Engineering Unit:* Draft the `MessageEvidenceRecord` Python dataclasses with strict type validation (similar to the G2C records). Use synthetic fixtures exclusively.
