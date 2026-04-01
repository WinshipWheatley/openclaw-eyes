title: sys-004-architectural-cleanup
profile: architect
goal: Have Chief propose a v2.0 task hierarchy separating System Infrastructure work from Creative/Life execution lanes.
scope:
- Audit current task naming, grouping, and folder layout in /home/openclaw/polish_loop/tasks.
- Propose a v2.0 folder hierarchy with migration rules and naming standards.
- Define lane boundaries: System Infrastructure, Financial Ops, Creative/Music, Life/Performance, and Outreach.
- Provide backward-compatible transition plan so existing loop automation keeps working.
- Include a minimal rollout sequence and rollback guidance.
success:
- v2.0 hierarchy proposal is documented with migration mapping and rollout steps.
- Proposal cleanly separates infra tasks from creative/life tasks.
verification: |
  python3 -c "print('sys-004-architecture-v2-spec-ready')"
