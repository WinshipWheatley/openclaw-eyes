# Storage and Source Registry Readiness Plan

Status: docs/test-only planning.

## 1. Purpose

Define the storage architecture, hardware capacity constraints, and source registry policies before attempting to move, restructure, index, or ingest business archives and sensitive files. Establish clear boundaries for hardware roles, sensitive zones, and cleanup priorities.

## 2. Non-goals

This slice is strictly planning. Do not move, delete, rename, install, update, sync, ingest, scan contents, or restructure files. Do not modify the local OpenClaw 2026.4.24 runtime. Do not execute cloud provider or local model calls against private data.

## 3. Current Storage Findings

Based on recent environmental audits:
- **PC C:** 246G total, 244G used, 2.5G available, 99% full.
- **PC D:** 229G total, 103G used, 127G available.
- **PC E:** 932G total, 521G used, 412G available.
- **WSL root:** 1007G total, 190G used, 767G available. (C: pressure is driven primarily by WSL VHD stored under Windows AppData, roughly 190GB).
- **Mac internal:** ~116GiB available.
- **8TB BU external:** ~80GiB available and is nearly full.
- **Orange external:** ~1.0TiB available.
- **Green external:** ~245GiB available.

Candidate business-memory source found: `/Volumes/8TB BU/Winship/Other/Old Buisness plans`.
No contents were inspected during the audit.

## 4. Sensitive Boundary Policy

- **Zones:** Areas such as Mac taxes/CPA paths and PC `C:/OpenClawLegalPrivate` are explicitly designated as Sensitive/local-only zones.
- **Rule:** Sensitive/local-only status must be respected prior to any model access.
- **No cloud model access to sensitive data by default.** These areas must remain restricted and isolated from broad indexing unless explicitly sanitized and promoted.

## 5. Proposed Drive Roles

Given the capacities and existing structures, we propose specific hardware roles to manage future data ingestion and cleanup cleanly:
- **Primary Work/Ingestion Layer:** (WSL/PC E or Mac internal, pending space) - Fast access for current active development and recent memory extraction.
- **Archival/Deep Storage Layer:** (Orange external, Green external) - Large capacity for historical business data, raw source files, and heavy media.
- **Read-Only Evidence/Staging Layer:** Segregated areas for staging data before it enters the SQLite-backed knowledge substrate.

## 6. OpenClaw Runtime/Repo Storage Policy

OpenClaw repo, runtime states, cache, and compiled databases must reside on fast, local storage.
Given the critical space pressure on PC C: (99% full), OpenClaw operational footprints on WSL must be tightly managed. The WSL VHD growth should be monitored and mitigated to prevent system lockups.

## 7. Future Source Registry Fields

Before SQLite ingestion can occur, a Source Registry must catalog available files. The registry should include:
- `source_id`
- `original_uri`
- `hardware_volume`
- `discovery_timestamp`
- `file_size`
- `hash`
- `sensitivity_classification` (e.g., restricted, unknown)
- `processing_status` (e.g., discovered, ignored, staged)

Rule: Inventory before extraction. Source registry must exist before SQLite ingestion begins.

## 8. Backup Before Restructure Rule

Rule: Backup before movement. Before any file or folder is moved, renamed, or restructured as part of the Operator Harness integration or OpenClaw management, it must be successfully backed up to a designated archival drive.

## 9. Safe Cleanup Candidate Classes

To alleviate the C: drive pressure safely, the following have been identified as candidates for operator-approved cleanup:
- pip cache (~7.2GB)
- npm cache (~2.7GB)
- Gemini tmp (~1.8GB)
- OpenClaw backup (~582MB)
- Windows Downloads (~5.5GB)
- Chrome cache (~6.6GB)

Rule: Operator approval before cleanup. No files are deleted automatically.

## 10. Move/Relocation Candidate Classes

Large static archives currently residing on fast, space-constrained drives (e.g., heavy media, outdated VM images, old backups) should be mapped for relocation to the Orange or Green external drives to reclaim space.

## 11. Music/Media Version Retention Policy Questions

Before scanning large music or media directories, we need to answer:
- Do we index all project versions or only masters?
- Do audio assets require separate metadata extraction vs text?
- How long are intermediate stem bounces retained locally?

## 12. Cloud/Local Model Access Rules

- Files in sensitive boundaries (`C:/OpenClawLegalPrivate`, taxes/CPA paths) are strictly blocked from cloud model access.
- Only non-sensitive or explicitly sanitized data may be transmitted to external models like Claude or GPT.
- Local models (via OpenClaw) may be utilized for sensitivity classification or summarization of restricted files if the local environment is confirmed secure.

## 13. Windows 10/11 Compatibility Investigation Lane

The storage pressure on the PC (especially the WSL VHD on C:) necessitates a brief investigation lane regarding Windows 10/11 host limitations, WSL2 dynamic disk compaction, and proper allocation limits to prevent the VHD from constantly exhausting the C: drive.

## 14. Operator Harness Mission Control Implications

The Mission Control dashboard must be able to display storage health. It should present:
- Current drive capacities.
- Warnings for space constraints (e.g., C: at 99%).
- Pending operator approval cards for Safe Cleanup Candidates.
- Evidence-backed read-only status for known sensitive zones.

## 15. Hard Rules

- Inventory before extraction.
- Backup before movement.
- Sensitive/local-only before model access.
- Source registry before SQLite ingestion.
- Operator approval before cleanup.
- No cloud model access to sensitive data by default.

## 16. Recommended Next Move

The recommended next move is to proceed with the static validation and formalization of the Source Registry data structures or to prepare an operator-approved cleanup packet to resolve the immediate PC C: storage crisis. No implementation, movement, or ingestion should begin yet.
