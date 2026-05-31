# OpenClaw Service Supervision

- Startup readiness: READY
- Boot persistence: READY
- Linger: yes
- Risk count: 0

## Core Units
- openclaw-request-response.service: enabled=enabled active=active/running readiness=READY
- openclaw-change-sentinel.timer: enabled=enabled active=active/waiting readiness=READY
- openclaw-change-sentinel.service: enabled=static active=inactive/dead readiness=READY
- openclaw-service-keeper.timer: enabled=enabled active=active/waiting readiness=READY
- openclaw-service-keeper.service: enabled=static active=inactive/dead readiness=READY

## Keeper
- Last keeper action: NO_ACTION_REQUIRED

No unresolved supervision risks.
