# Active Machinery High-Risk Quarantine Warnings v0

Status:
- Warning only: `true`.
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Services disabled: `false`.
- Destructive quarantine allowed: `false`.

## Summary
- High-risk live/script warnings: `14`.
- Test-only items kept out of runtime quarantine: `3`.
- Static references represented: `12`.
- Dispositions: `{'block_no_go': 5, 'keep_test_only': 3, 'replace_with_governed_path': 4, 'retire_later': 2, 'wrap_with_guardian': 3}`.

## High-Risk Warning Surfaces
| Surface | Disposition | Static refs | Why it matters |
| --- | --- | ---: | --- |
| `builder_watcher.sh` | `block_no_go` | 1 | Verified watcher/daemon signals on a builder surface; legacy watchdog-style build loops should not run outside a governed Operator Action packet. |
| `cassandra_listener.py` | `replace_with_governed_path` | 2 | Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener. |
| `cassandra_watcher.py` | `retire_later` | 2 | Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows. |
| `chief_brainstorm_watcher.py` | `retire_later` | 0 | Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path. |
| `chief_email_brain.py` | `wrap_with_guardian` | 0 | Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved. |
| `chief_guardian_listener.py` | `replace_with_governed_path` | 1 | Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract. |
| `chief_guardian_sender.py` | `wrap_with_guardian` | 1 | Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries. |
| `chief_listener.py` | `replace_with_governed_path` | 2 | Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority. |
| `chief_sender.py` | `wrap_with_guardian` | 1 | Verified send/API signals on a sender surface; external sends require Guardian/operator approval. |
| `chief_watcher_brain.py` | `block_no_go` | 1 | Verified watcher plus shell/process signals; this is too risky to run as active machinery without a replacement contract. |
| `producer_listener.py` | `replace_with_governed_path` | 1 | Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime. |
| `retry_send_demo_dashboard.sh` | `block_no_go` | 1 | Verified send-path signal on a shell demo/retry surface; demos must not become live send machinery. |
| `scripts/run_producer_listener.sh` | `block_no_go` | 1 | Verified launcher for listener machinery; shell launchers should not activate daemons outside governed runtime approval. |
| `send_demo_dashboard.py` | `block_no_go` | 1 | Verified send/API signal on a demo dashboard sender; demo send paths should remain blocked. |

## Test-Only Items
- `tests/test_cassandra_email_thread_analysis.py` stays `keep_test_only`; it is not treated as live runtime machinery.
- `tests/test_chief_listener_lifecycle.py` stays `keep_test_only`; it is not treated as live runtime machinery.
- `tests/test_send_truth.py` stays `keep_test_only`; it is not treated as live runtime machinery.

## Static References Already Captured
- systemd/user/chief-listener.service.in references chief_listener.py
- systemd/user/chief-watcher-brain.service.in references chief_watcher_brain.py
- systemd/user/cassandra-listener.service.in references cassandra_listener.py
- systemd/user/cassandra-watcher.service.in references cassandra_watcher.py
- systemd/user/chief-guardian-listener.service.in references chief_guardian_listener.py
- start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py
- start_chief_logged.sh starts chief_listener.py
- loop_supervisor.sh restarts builder_watcher.sh
- scripts/run_producer_listener.sh starts producer_listener.py
- retry_send_demo_dashboard.sh invokes send_demo_dashboard.py
- Chief brain files reference chief_sender.py
- Guardian/HITL surfaces reference chief_guardian_sender.py

## What Did Not Happen
- No services were disabled.
- No files were moved, deleted, renamed, or chmodded.
- No launchers or systemd templates were edited.
- No agents, sends, daemons, or runtime activation were enabled.
- Repo B was not executed.

## Next Safe Move
- Active Machinery Quarantine Operator Review v0
