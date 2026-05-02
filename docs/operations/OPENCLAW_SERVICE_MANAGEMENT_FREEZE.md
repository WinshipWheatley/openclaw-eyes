# OpenClaw Service Management Freeze

_Created: 2026-04-29. Runtime-neutral documentation freeze only._

This document records the current service-management source of truth after service-freeze Slices 2-8. It does not start, stop, restart, reload, enable, disable, install, remove, or otherwise change any service. It also does not authorize new runtime behavior. Slices 2-8 are complete only as static, documented, tested service-freeze contracts: they do not prove live service state, select runtime owners, create missing templates, delete or revive legacy controls, or authorize service operations. Treat this page as a closure marker for current owners, safe control boundaries, and controls that must not be expanded without a separate planned lane.

## Systemd-Owned Services

The following units are currently treated as systemd-owned. Control should remain on the systemd user-unit path, and legacy/manual launchers must not be used to duplicate or replace these owners during the freeze.

- `openclaw-stack.target`
- `chief-listener.service`
- `chief-worker.service`
- `chief-memory-worker.service`
- `chief-state-worker.service`
- `chief-watcher-brain.service`
- `cassandra-listener.service`
- `cassandra-watcher.service`
- `cassandra-briefing-scheduler.service`
- `chief-guardian-listener.service`
- `hermes-gateway.service` - systemd-owned, with a narrow repo-supported reconciliation path in `scripts/install_hermes_gateway_service.sh`; do not use the broad stack installer for this unit.
- `openclaw-gateway.service` - systemd-owned as an installed unit, with no repo template in this source set. Slice 6 records this as frozen pending a documented external owner or future repo template decision; installed somewhere is not sufficient ownership evidence.
- `openclaw-drift-control-scan.timer` and `openclaw-drift-control-scan.service` - systemd-owned as installed units, with no repo templates in this source set. Slice 6 records these as frozen pending documented external owners or future repo template decisions; installed somewhere is not sufficient ownership evidence. Slice 7 records static scheduler-owner classification only; no canonical scheduler owner is selected here.

## Legacy/Manual-Owned Processes

The following processes remain legacy/manual-owned during the freeze. They must not be silently promoted into the systemd stack, and they must not be used to duplicate systemd-owned listeners or workers.

- `chief_album_brain.py`
- `chief_billing_brain.py`
- `loop_supervisor.sh`
- `orchestrator.py --loop`
- `builder_watcher.sh`
- `dashboard_gen.py`
- `loop_dashboard_watchdog.sh`
- `ceo_briefing_worker.py`

## Deprecated/Frozen Controls

These controls remain deprecated or frozen after the Slice 2-8 static closure unless a separate future lane explicitly replaces, guards, or retires them:

- `scripts/start_all.sh`
- `start_chief.sh`
- `start_openclaw_brains.sh`
- `scripts/install_openclaw_stack.sh`
- `pkill` of systemd-owned brains
- `nohup` duplicate Telegram polling listeners
- blanket enabling all installed services
- running both drift-control cron and timer scheduling paths

Do not expand any of these controls under this freeze. Existing references are historical and must remain visible until a later planned lane replaces them with guarded, tested behavior.

## Source-Of-Truth Table

| Service/process | current owner | allowed control path | forbidden control path | cleanup status |
| --- | --- | --- | --- | --- |
| `openclaw-stack.target` | systemd user unit | Existing systemd target ownership only; no behavior change implied by this document | Legacy launch wrappers, blanket enablement, or process kills as substitutes for systemd ownership | Frozen; inventory check in Slice 2 |
| `chief-listener.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | `start_chief.sh`, `scripts/start_all.sh`, `pkill`, duplicate `nohup` polling/listener launches | Frozen; guard legacy scripts in Slice 4 |
| `chief-worker.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | `start_chief.sh`, `scripts/start_all.sh`, `pkill`, manual duplicate worker launch | Frozen; guard legacy scripts in Slice 4 |
| `chief-memory-worker.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | `start_chief.sh`, `scripts/start_all.sh`, `pkill`, manual duplicate worker launch | Frozen; guard legacy scripts in Slice 4 |
| `chief-state-worker.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | `start_chief.sh`, `scripts/start_all.sh`, `pkill`, manual duplicate worker launch | Frozen; guard legacy scripts in Slice 4 |
| `chief-watcher-brain.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | Legacy launch wrappers, `pkill`, or duplicate watcher launch outside systemd | Frozen; guard legacy scripts in Slice 4 |
| `cassandra-listener.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | Manual duplicate listener launch, duplicate Telegram polling, `pkill` | Frozen; inventory check in Slice 2 |
| `cassandra-watcher.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | Manual duplicate watcher launch or `pkill` | Frozen; inventory check in Slice 2 |
| `cassandra-briefing-scheduler.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | Manual duplicate scheduler launch or `pkill` | Frozen; inventory check in Slice 2 |
| `chief-guardian-listener.service` | systemd user unit | systemd user-unit ownership through `openclaw-stack.target` or the explicit unit | Manual duplicate listener launch, duplicate Telegram polling, `pkill` | Frozen; inventory check in Slice 2 |
| `hermes-gateway.service` | systemd user unit | `scripts/install_hermes_gateway_service.sh` may render only `systemd/user/hermes-gateway.service.in`, reload the user daemon, verify gateway flags, and optionally restart only this unit when explicitly requested | Editing the unit/template mismatch opportunistically, blanket enablement, broad stack install, `openclaw-stack.target` restart, or alternate launch path | Narrow reconciliation path added; operator run/restart remains explicit |
| `openclaw-gateway.service` | installed systemd user unit without repo template | Installed unit ownership only; no repo template in this source set; installed somewhere is not sufficient ownership evidence; frozen pending documented external owner or future repo template decision | Blanket enablement, unreviewed template creation, or duplicate gateway launch path | Frozen pending documented external owner or future repo template decision |
| `openclaw-drift-control-scan.timer` | installed systemd user timer without repo template | Installed timer ownership only; no repo template in this source set; installed somewhere is not sufficient ownership evidence; frozen pending documented external owner or future repo template decision | Running both systemd timer and dashboard cron scheduling paths | Frozen pending documented external owner or future repo template decision; Slice 7 records static scheduler-owner classification only |
| `openclaw-drift-control-scan.service` | installed systemd user service without repo template | Installed service ownership only; no repo template in this source set; installed somewhere is not sufficient ownership evidence; frozen pending documented external owner or future repo template decision | Running both systemd timer and dashboard cron scheduling paths | Frozen pending documented external owner or future repo template decision; Slice 7 records static scheduler-owner classification only |
| `chief_album_brain.py` | legacy/manual polling process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice, duplicate Telegram polling, unmanaged `nohup` expansion | Frozen; Slice 8 records static legacy ownership disposition only |
| `chief_billing_brain.py` | legacy/manual polling process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice, duplicate Telegram polling, unmanaged `nohup` expansion | Frozen; Slice 8 records static legacy ownership disposition only |
| `loop_supervisor.sh` | legacy/manual supervisor | Legacy/manual ownership only until guarded or retired | Supervising or killing systemd-owned services outside systemd | Frozen; Slice 4 guard recorded; Slice 8 records static legacy ownership disposition only |
| `orchestrator.py --loop` | legacy/manual loop process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate loop supervision | Frozen; Slice 8 records static legacy ownership disposition only |
| `builder_watcher.sh` | legacy/manual watcher | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate watcher supervision | Frozen; Slice 8 records static legacy ownership disposition only |
| `dashboard_gen.py` | legacy/manual dashboard/cron participant | Legacy/manual ownership only until drift-control scheduler is unified | Running drift-control cron path alongside the systemd timer | Frozen; Slice 7 records static scheduler-owner classification only |
| `loop_dashboard_watchdog.sh` | legacy/manual watchdog | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate dashboard supervision | Frozen; Slice 8 records static legacy ownership disposition only |
| `ceo_briefing_worker.py` | legacy/manual worker | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate worker supervision | Frozen; Slice 8 records static legacy ownership disposition only |

## Legacy Ownership Disposition Contract

Slice 8 records definitive static disposition only. It does not delete files, select new runtime owners, run service audits, reconcile installed live state, start processes, stop processes, inspect live processes, or touch private/runtime data. A surface is either dispositioned below or must be reported as `unknown_unowned_finding` by the static audit contract.

Allowed disposition classes are:

- `retired_dead_entrypoint`
- `frozen_pending_owner_decision`
- `replaced_by_systemd_owned_path`
- `retained_manual_only_refusal_or_dry_run`
- `unknown_unowned_finding`

| Surface | disposition class | source evidence | allowed control path | forbidden control path | runtime mutation allowed | live inspection required | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scripts/start_all.sh` | retained_manual_only_refusal_or_dry_run | Slice 4 refusal-only launcher | Report-only dry-run/refusal text | Stack restart, delegated poller launch, live process inspection | false | false | Keep guarded until a later owner decision retires or replaces it |
| `start_chief.sh` | retained_manual_only_refusal_or_dry_run | Slice 4 refusal-only Chief launcher | Report-only dry-run/refusal text | Private env loading, log creation, process termination, duplicate listener or worker startup | false | false | Keep guarded until a later owner decision retires or replaces it |
| `start_openclaw_brains.sh` | retained_manual_only_refusal_or_dry_run | Slice 4 refusal-only poller launcher | Report-only dry-run/refusal text | `pkill`, detached poller launch, hidden Chief album or billing process mutation | false | false | Keep guarded until a later owner decision retires or replaces it |
| `scripts/install_openclaw_stack.sh` | retained_manual_only_refusal_or_dry_run | Slice 3 gated stack installer | Default dry-run report only in this slice | Broad enablement, hidden start, Hermes ownership claim, gateway or drift-control claim | false | false | Keep explicit apply/enable/start gates outside Slice 8 |
| `scripts/install_hermes_gateway_service.sh` | retained_manual_only_refusal_or_dry_run | Slice 5 Hermes-only gated installer | Default dry-run report only in this slice | Broad stack control, enable/start behavior, non-Hermes unit mutation | false | false | Keep narrow Hermes reconciliation separate from legacy disposition |
| `start_album_brain.sh` | frozen_pending_owner_decision | Static source directly activates venv and runs `chief_album_brain.py` | No run path in Slice 8 | Manual poller startup before owner decision | false | false | Later slice must guard, retire, or document manual-only ownership |
| `start_cassandra_core.sh` | replaced_by_systemd_owned_path | Static source restarts Cassandra listener, watcher, and scheduler via systemd or nohup fallback | Use repo-owned Cassandra systemd templates as the documented replacement path | `pkill`, nohup fallback, private env startup, duplicate Cassandra services | false | false | Retire or replace with refusal-only notice in a later cleanup slice |
| `orchestrator.py --loop` | frozen_pending_owner_decision | Freeze table and `polish_loop/orchestrator.py` continuous loop entrypoint | No run path in Slice 8 | Unreviewed loop promotion or duplicate orchestration | false | false | Later owner decision must retain manual-only, systemd-own, or retire |
| `polish_loop/start_orchestrator.sh` | frozen_pending_owner_decision | Static source launches `polish_loop/orchestrator.py` with `nohup` and PID file | No run path in Slice 8 | Background daemon launch before owner decision | false | false | Later slice must guard, retire, or document manual-only ownership |
| `builder_watcher.sh` | frozen_pending_owner_decision | Freeze table and static source launch coding runners from loop state | No run path in Slice 8 | Runner spawning, provider/model calls, duplicate watcher supervision | false | false | Later owner decision must define builder loop ownership and allowed runner path |
| `loop_supervisor.sh` | frozen_pending_owner_decision | Freeze table and static source restarts loop processes with `setsid` and `nohup` | No run path in Slice 8 | Supervising, restarting, SSH checking, killing, or duplicating loop processes | false | false | Later slice must retire or replace with explicit owner path |
| `dashboard_gen.py` | frozen_pending_owner_decision | Freeze table and static source dashboard cron participant | No run path in Slice 8 | Dashboard cron execution alongside drift-control timer path | false | false | Later scheduler decision must retain, replace, or disable cron participation |
| `loop_dashboard_watchdog.sh` | frozen_pending_owner_decision | Freeze table and static source watchdog restarts `dashboard_gen.py` | No run path in Slice 8 | `pkill`, `setsid`, `nohup`, stale-dashboard restart loop | false | false | Later slice must guard, retire, or document manual-only ownership |
| `ceo_briefing_worker.py` | frozen_pending_owner_decision | Freeze table and static source long-running briefing worker | No run path in Slice 8 | Unowned background worker or messaging side effect | false | false | Later owner decision must retain manual-only, systemd-own, or retire |
| `chief_album_brain.py` | frozen_pending_owner_decision | Freeze table and static source legacy polling shim | No run path in Slice 8 | Duplicate Telegram polling or unmanaged loop launch | false | false | Later owner decision must retain manual-only, systemd-own, or retire |
| `chief_billing_brain.py` | frozen_pending_owner_decision | Freeze table and static source polling loop | No run path in Slice 8 | Duplicate Telegram polling or unmanaged loop launch | false | false | Later owner decision must retain manual-only, systemd-own, or retire |
| `drift_control_scanner.py --scan` | frozen_pending_owner_decision | Static source registers `drift-control-scan` dashboard cron path | No run path in Slice 8 | Running scan, registering cron, updating drift state, or applying proposals | false | false | Later scheduler decision must choose canonical path or retire scheduling |
| `openclaw-gateway.service` | frozen_pending_owner_decision | Slice 6 installed-only unit record without repo template | Installed-only record in docs; no repo template claim | Template creation, blanket enablement, duplicate gateway launch | false | false | Future slice needs documented external owner or repo template decision |
| `openclaw-drift-control-scan.timer` | frozen_pending_owner_decision | Slice 6 and Slice 7 installed-only timer record without repo template | Installed-only record in docs; no canonical scheduler selected | Timer enablement, cron/timer dual scheduling, template creation | false | false | Future scheduler slice must choose systemd, dashboard cron, or retired path |
| `openclaw-drift-control-scan.service` | frozen_pending_owner_decision | Slice 6 and Slice 7 installed-only service record without repo template | Installed-only record in docs; no canonical scheduler selected | Service enablement, cron/timer dual scheduling, template creation | false | false | Future scheduler slice must choose systemd, dashboard cron, or retired path |
| `scripts/audit_openclaw_services.sh` | frozen_pending_owner_decision | Static source reads installed unit files and may query user unit-file status | No run path in Slice 8; use `service_inventory_audit.py` for static source audit | Service audit execution, installed-state reconciliation, `systemctl` query in this lane | false | false | Later service-audit slice must gate, retire, or replace this live-state audit path |

## Drift-Control Scheduler Classification

Slice 7 records scheduler-owner classification only. It does not choose a canonical scheduler owner, add a systemd timer/service template, enable or disable any scheduler, or change runtime behavior.

- Canonical scheduler owner: none selected in this source set.
- `installed_systemd_timer`: `openclaw-drift-control-scan.timer` is an installed-only timer reference with no repo template; classification `frozen_pending_owner_decision`.
- `installed_systemd_service`: `openclaw-drift-control-scan.service` is an installed-only service reference with no repo template; classification `frozen_pending_owner_decision`.
- `dashboard_cron_jobs_json`: repo source shows `dashboard_gen.py` can read `.openclaw/cron/jobs.json`, and `drift_control_scanner.py` can register `drift-control-scan`; classification `frozen_pending_owner_decision`.
- Dual scheduler risk remains advisory and forbidden: do not run both the drift-control dashboard cron path and the drift-control systemd timer path.

Installed somewhere is not sufficient scheduler ownership evidence. Future unification must explicitly decide whether the canonical scheduler is a repo-supported systemd timer, a repo-supported dashboard/cron jobs path, or a retired scheduler path.

## Cleanup Slice Order

1. Slice 2: add read-only service inventory/audit check.
2. Slice 3: harden install script behavior behind dry-run/explicit flags.
3. Slice 4: deprecate or guard legacy launch scripts.
4. Slice 5: reconcile Hermes template vs installed unit through the narrow Hermes-only installer.
5. Slice 6: record owner classification for `openclaw-gateway` and drift-control; no repo templates are added without enough source evidence.
6. Slice 7: record static drift-control scheduler-owner classification without selecting an owner.
7. Slice 8: record static legacy polling/loop supervisor ownership disposition.

## Runtime-Neutral Rule

This freeze is documentation only. It records ownership and forbidden control paths so future lanes can make narrow, reviewable changes. Any future service operation, script guard, unit edit, template addition, scheduler change, live-state verification, or process ownership change must be performed in a separate planned lane with explicit scope and verification.
