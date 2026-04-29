# OpenClaw Service Management Freeze

_Created: 2026-04-29. Runtime-neutral documentation freeze only._

This document records the current service-management source of truth for Pass 3C Slice 1. It does not start, stop, restart, reload, enable, disable, install, remove, or otherwise change any service. It also does not authorize new runtime behavior. Until later cleanup slices land, treat this page as a freeze marker: it names the current owners, the safe control boundaries, and the controls that must not be expanded.

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
- `hermes-gateway.service` - systemd-owned, with a known repo-template vs installed-unit mismatch to reconcile in Slice 5.
- `openclaw-gateway.service` - systemd-owned as an installed unit, with no repo template currently recorded; add a template or documented external owner in Slice 6.
- `openclaw-drift-control-scan.timer` and `openclaw-drift-control-scan.service` - systemd-owned as installed units, with no repo templates currently recorded; add templates or documented external owners in Slice 6 and unify scheduling in Slice 7.

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

These controls are deprecated or frozen until the cleanup slices below explicitly replace, guard, or retire them:

- `scripts/start_all.sh`
- `start_chief.sh`
- `start_openclaw_brains.sh`
- `scripts/install_openclaw_stack.sh`
- `pkill` of systemd-owned brains
- `nohup` duplicate Telegram polling listeners
- blanket enabling all installed services
- running both drift-control cron and timer scheduling paths

Do not expand any of these controls in this slice. Existing references are historical and must remain visible until later slices replace them with guarded, tested behavior.

## Source-Of-Truth Table

| Service/process | current owner | allowed control path | forbidden control path | cleanup status |
|---|---|---|---|---|
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
| `hermes-gateway.service` | systemd user unit | systemd user-unit ownership; preserve current installed behavior until reconciled | Editing the unit/template mismatch opportunistically, blanket enablement, or alternate launch path | Frozen; reconcile mismatch in Slice 5 |
| `openclaw-gateway.service` | installed systemd user unit without repo template | Installed unit ownership only, pending a repo template or documented external owner | Blanket enablement, unreviewed template creation, or duplicate gateway launch path | Frozen; add template or owner in Slice 6 |
| `openclaw-drift-control-scan.timer` | installed systemd user timer without repo template | Installed timer ownership only, pending template/owner documentation and scheduler unification | Running both systemd timer and dashboard cron scheduling paths | Frozen; add template/owner in Slice 6, unify scheduler in Slice 7 |
| `openclaw-drift-control-scan.service` | installed systemd user service without repo template | Installed service ownership only, pending template/owner documentation and scheduler unification | Running both systemd timer and dashboard cron scheduling paths | Frozen; add template/owner in Slice 6, unify scheduler in Slice 7 |
| `chief_album_brain.py` | legacy/manual polling process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice, duplicate Telegram polling, unmanaged `nohup` expansion | Frozen; decide ownership in Slice 8 |
| `chief_billing_brain.py` | legacy/manual polling process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice, duplicate Telegram polling, unmanaged `nohup` expansion | Frozen; decide ownership in Slice 8 |
| `loop_supervisor.sh` | legacy/manual supervisor | Legacy/manual ownership only until guarded or retired | Supervising or killing systemd-owned services outside systemd | Frozen; deprecate or guard in Slice 4, decide ownership in Slice 8 |
| `orchestrator.py --loop` | legacy/manual loop process | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate loop supervision | Frozen; decide ownership in Slice 8 |
| `builder_watcher.sh` | legacy/manual watcher | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate watcher supervision | Frozen; decide ownership in Slice 8 |
| `dashboard_gen.py` | legacy/manual dashboard/cron participant | Legacy/manual ownership only until drift-control scheduler is unified | Running drift-control cron path alongside the systemd timer | Frozen; unify scheduler in Slice 7 |
| `loop_dashboard_watchdog.sh` | legacy/manual watchdog | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate dashboard supervision | Frozen; decide ownership in Slice 8 |
| `ceo_briefing_worker.py` | legacy/manual worker | Legacy/manual ownership only until ownership is decided | systemd promotion without a slice or duplicate worker supervision | Frozen; decide ownership in Slice 8 |

## Cleanup Slice Order

1. Slice 2: add read-only service inventory/audit check.
2. Slice 3: harden install script behavior behind dry-run/explicit flags.
3. Slice 4: deprecate or guard legacy launch scripts.
4. Slice 5: reconcile Hermes template vs installed unit.
5. Slice 6: add repo templates or documented external owners for `openclaw-gateway` and drift-control.
6. Slice 7: unify drift-control scheduler.
7. Slice 8: decide legacy polling/loop supervisor ownership.

## Runtime-Neutral Rule

This freeze is documentation only. It records ownership and forbidden control paths so future slices can make narrow, reviewable changes. Any future service operation, script guard, unit edit, template addition, scheduler change, or process ownership change must be performed in a later slice with explicit scope and verification.