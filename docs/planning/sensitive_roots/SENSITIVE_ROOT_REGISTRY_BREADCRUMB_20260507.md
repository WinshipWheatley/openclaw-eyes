# Sensitive Root Registry / Quarantine Intake Breadcrumb

## 1. Purpose
This document captures a new sensitive-root boundary discovered from operator file organization. It should guide a future implementation lane for a Sensitive Root Registry and Quarantine Intake Policy, ensuring that sensitive financial, legal, and private materials are properly protected from unauthorized access or processing by outside LLMs.

## 2. Operator-Provided Sensitive Root Metadata
**Root path:** `/Users/hwinshipwheatley/Sensitive Folder For Review`

**Visible subfolders (from operator-provided screenshot/description):**
- `Legal_Local`
- `OpenClawFinancePrivate`
- `OpenClawLegalDev`
- `OpenClawLegalPrivate`
- `OpenClawMusicLawPrivate`
- `Sensitive Discovery (no unauthorized approval)`

*Note: This is metadata supplied by the operator, not the result of filesystem crawling. Do not inspect or crawl these folders.*

## 3. Core Policy Doctrine
- **Border Checkpoint:** The sensitive root acts as a border checkpoint / customs gate.
- **Default Posture:** Deny content access.
- **Metadata-Only Awareness:** Allowed only when explicitly scoped.
- **Content Access Requirements:** Requires a local-only actor and an approval receipt.
- **No Cloud/Outside LLMs:** Cloud or external LLMs cannot read contents under any circumstances.
- **Strict Quarantine:** `Sensitive Discovery (no unauthorized approval)` is strict quarantine.
- **No Automatic Processing:** No automatic ingestion, OCR, summarization, or classification from body text.
- **Presence ≠ Permission:** The presence of a file is not permission to read it.
- **Path ≠ Content:** Path access is not content authorization.
- **Local-Only ≠ Approved:** "Local-only" status does not mean automatic approval to process the data.

## 4. Proposed Subfolder Policy Classes
These are initial policy suggestions, not a final legal/security classification:
- `Legal_Local`: Local-only legal/private work; content access requires an approved local actor.
- `OpenClawFinancePrivate`: Finance/CPA/tax/payment-sensitive; local-only by default.
- `OpenClawLegalDev`: Development/testing legal-product work; may contain non-sensitive dev material but remains under the sensitive root; metadata-first posture.
- `OpenClawLegalPrivate`: Private legal/matter material; strict local-only.
- `OpenClawMusicLawPrivate`: Music law, publishing, rights, contract-sensitive material; local-only protected boundary.
- `Sensitive Discovery (no unauthorized approval)`: Strict quarantine; outside LLMs may know only existence/path metadata if explicitly approved; no content read allowed.

## 5. Future Sensitive Root Registry Fields
Concept for a static/data schema for a future implementation lane (not for implementation yet):
- `sensitive_root_id`
- `tenant_id`
- `root_path`
- `root_label`
- `sensitivity_level`
- `root_class`
- `metadata_policy`
- `content_policy`
- `allowed_actor_classes`
- `allowed_actor_lanes`
- `requires_approval_receipt`
- `external_export_allowed`
- `cloud_access_policy`
- `local_only`
- `staleness_review_cadence`
- `last_reviewed_at`
- `status`
- `operator_approval_ref`
- `notes`

## 6. Relationship to Actor Registry / Context Export
- **Actor Registry:** Answers *who* is asking.
- **Sensitive Root Registry:** Answers *what zone/root* is being requested.
- **Context Export:** Decides whether the response is denied, metadata-only, local-only, or sanitized-with-receipt based on the interaction of the two registries.
- **Cloud Sidecars:** Remain deny-by-default.
- **No Fake Sanitization:** Sanitization must be real and receipt-backed.
- **No Automatic Accepted-Truth Promotion:** Content must be explicitly approved before promotion to accepted truth.

## 7. Staleness / Review Concept
The operator requires visibility into the state of the quarantine zone without live scanning. The system should track:
- What is stale.
- What needs review.
- What has not been classified.
- What is in quarantine.
- What has approval receipts.
- What should never be externally processed.

*(Note: Live scanning is strictly prohibited at this stage. This defines the future need only.)*

## 8. Future Lane: Sensitive Root Registry / Quarantine Intake Policy
A possible future implementation lane may include:
- Static data contract only.
- SQLite table concept only.
- Repository helpers only.
- Pure read-model/risk helpers only.
- **No filesystem traversal.**
- **No private content reads.**
- **No live ingestion.**
- **No OCR.**
- **No cloud calls.**
- **No UI yet.**

## 9. Hard Boundaries
- **No filesystem crawl.**
- **No content read.**
- **No private root traversal.**
- **No external LLM access.**
- **No OCR.**
- **No summarization.**
- **No automatic classification from content.**
- **No legal/finance/client data exposure.**
- **No moving/copying/deleting files.**
- **No changing permissions.**
- **No sync.**
- **No ingestion.**
- **No action execution.**

## 10. Next Safe Action
- Keep this document as a breadcrumb for now.
- After current docs/source-set work is clean, consider a bounded implementation prompt for Sensitive Root Registry / Quarantine Intake Policy.
- Implementation should start with the static schema and tests only.

---

**Prompt Rule for Future Chats:**
> "Do not inspect `/Users/hwinshipwheatley/Sensitive Folder For Review` or any subfolders. You may reference the folder path and subfolder names as operator-provided metadata only. Do not read contents unless a future local-only approved lane explicitly scopes it."
