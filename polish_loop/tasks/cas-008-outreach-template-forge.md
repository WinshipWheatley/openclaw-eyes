title: cas-008-outreach-template-forge
profile: standard
goal: Have Cassandra generate three high-priority outreach templates for overdue invoices or session follow-ups and store them in Drafts.
scope:
- Use contacts and invoice history context to identify top-priority outreach scenarios.
- Draft 3 templates: overdue payment follow-up, session booking renewal, and warm reactivation.
- Keep language professional, concise, and action-oriented with placeholders for client-specific details.
- Save templates to a Drafts location in vault/runtime docs for quick reuse.
- Do not send messages automatically; drafting only.
success:
- Three reusable templates are saved in Drafts with clear usage notes.
- Each template includes subject line and body variants.
verification: |
  python3 -c "print('cas-008-template-forge-spec-ready')"
