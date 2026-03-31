title: cas-005-client-urgency-mode
goal: Add a time-sensitive response mode for future client contacts where Cassandra still answers what she can, still queues the upgrade, but immediately notifies Winship to manually handle the urgent part instead of waiting for a build cycle.
scope:
- Add a contact classification system in /home/openclaw/contact_nicknames.json:
  - Each contact gets a "tier" field: "inner_circle" (parents, Draper) or "client"
  - Example: {"dad": {"name": "placeholder", "tier": "inner_circle"}, "clientname": {"name": "placeholder", "tier": "client"}}
  - Migrate existing flat nickname entries to this structure
- For tier=inner_circle (current behavior from cas-004):
  - Partial response + auto-upgrade task + follow-up when ready
  - No urgency notification to Winship
- For tier=client:
  - Partial response sent immediately (same as inner_circle)
  - Auto-upgrade task still queued (same as inner_circle)
  - ADDITIONALLY: Winship gets an urgent Telegram notification via Chief bot with:
    - Who messaged (client name)
    - What they asked
    - What Cassandra could answer
    - What she couldn't (the gap)
    - "Manual action needed — client is waiting"
  - The follow-up still happens when the upgrade completes, but Winship is expected to handle it manually in the meantime
- Add a response_sla field to client contacts (optional, default 30 minutes):
  - If set, Cassandra includes it in the Winship notification: "Client expects response within {sla} minutes"
- Use chief_sender.py (Chief's Telegram bot) for the Winship notification — NOT Cassandra's bot
  - This keeps the notification channel separate from client-facing messages
success:
- contact_nicknames.json supports tier classification (inner_circle vs client)
- Client messages trigger Winship notification via Chief bot
- Inner circle messages behave as cas-004 (no urgency ping)
- Upgrade tasks still queued for both tiers
- Response SLA field supported in contact config
verification: |
  python3 -c "import json; d=json.load(open('/home/openclaw/contact_nicknames.json')); assert any(v.get('tier') for v in d.values()); print('tier field present')"
depends_on: cas-004-partial-response-gap-detection
notes: |
  This is FUTURE infrastructure. No real clients are onboarded yet.
  The builder should implement the tier system and notification path but use placeholder contacts only.
  Do NOT send any real Telegram notifications during the build — use dry-run or test flags.
  Winship will onboard actual clients manually later.
