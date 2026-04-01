title: std-chief-session-persistence
profile: standard
goal: Harden session lifecycle with persistence edge-case tests
scope:
- Test stale session eviction and restore behavior
- Test concurrent update ordering on same session id
- Add explicit serialization roundtrip checks
success:
- Session lifecycle is deterministic under edge conditions
generated_by: queue_balancer
generated_at: 2026-04-01T00:58:37.812664
