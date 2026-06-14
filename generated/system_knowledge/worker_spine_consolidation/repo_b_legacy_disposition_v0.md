# Repo B Legacy Disposition

Repo B is reference-only and not runtime authority. No Repo B code becomes live runtime code in this task.

## Unsafe Blocked
- google_access_broker.py OAuth/token/credential bridge patterns
- legacy OAuth refresh or credential storage paths
- automatic broker-based Gmail/Calendar/Contacts access
- autonomous repair loops that mutate runtime or restart services without current rails
- old bridge code that bypasses Guardian/HITL or package receipts

## Represented In Repo A
- chief_router.py routing/orchestration -> Operator Context Switchboard, agent_lane_registry.py, openclaw_lm_consult_spine.py
- chief_watcher_brain.py watch/status ideas -> watch_desk_feed.py and generated/read_models status projections
- chief_worker.py / ceo_briefing_worker.py worker concepts -> codex_work_package_lifecycle.py plus Assignment Loop

## Candidate Pattern Only
- watcher summaries -> Watch Desk item sourced from canonical read models and receipts only.
- queue balancing -> Worker Run Manager queue metadata, not a separate live queue.
- capability registry language -> Capability status read models and Assignment Loop proof requirements.
