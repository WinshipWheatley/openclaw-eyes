title: std-chief-router-table-tests
profile: standard
goal: Build table-driven regression tests for chief_router intent precedence
scope:
- Create tests/test_chief_router_table.py with >=20 intent samples
- Cover overlaps: billing vs ops vs approval routing
- Verify fallback route stays deterministic
success:
- Routing precedence regressions are caught by table tests
generated_by: queue_balancer
generated_at: 2026-04-01T00:58:37.804907
