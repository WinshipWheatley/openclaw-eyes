title: life-001-the-ocean-city-surf-gate
profile: architect
goal: Implement a surf-condition gate for Ocean City, MD that pauses non-urgent business work and extends Flow State window when conditions are epic.
scope:
- Add logic to check Ocean City surf forecast from configured weather/surf source.
- Define threshold rules for 'Epic' conditions (wave height, wind, period, quality score).
- If Epic: auto-mute non-urgent business tasks and extend Flow State window to 8 hours (Annapolis drive + session).
- Preserve urgent/system-critical tasks and safety notifications.
- Log gate decisions with timestamp, input conditions, and resulting policy state.
success:
- Surf gate can switch between normal mode and Epic mode deterministically.
- Non-urgent tasks are deferred during Epic mode while critical operations continue.
verification: |
  python3 -c "print('life-001-surf-gate-spec-ready')"
