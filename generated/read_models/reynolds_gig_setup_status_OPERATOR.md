# Reynolds Tavern Gig Setup Status

State: known_facts_ready_missing_operational_answers
Known gig: 2026-06-27 19:00-22:00 at Reynolds Tavern
Address: 7 Church Circle, Annapolis, MD
Fee: $250.00 USD
Contact: Sally <reservations@reynoldstavern.com>
Coupa: not required

Eight Lanes
- calendar: known_fact_needs_calendar_receipt
  missing: calendar event receipt or operator confirmation that the date/time is already on the calendar
- contact: primary_contact_known_day_of_details_missing
  missing: day-of phone number, preferred day-of contact channel
- logistics: venue_address_known_logistics_missing
  missing: arrival/load-in time, parking/load-in instructions, setup location at the venue, who provides PA/sound
- music: performance_window_known_music_brief_missing
  missing: music vibe/repertoire, break expectations, volume constraints, dress code or special requests
- payment: fee_known_payment_method_missing
  missing: payment method, who pays, payment timing, whether any tax/vendor form is needed
- invoice: invoice_artifacts_exist_defaults_need_confirmation
  missing: invoice_business_identity, payment_terms
- reply watch: target_known_live_watch_not_proven
  missing: scoped read-only reply-watch receipt, allowed query terms, watch cadence or manual-check preference
- recurrence: unknown_one_off_or_recurring
  missing: one-off vs recurring posture, if recurring: cadence/date source, if recurring: rate/payment rules, if recurring: who confirms future dates

Questions
- invoice: Use Winship Wheatley and due upon receipt, or use a different billing identity or terms?
- recurrence: Should Reynolds be set up as one-off for June 27, or as a recurring gig lane?
- calendar: Should I verify/create a calendar hold for June 27, 2026, 7-10 PM?
- contact: What day-of phone or preferred day-of contact channel should be stored for Sally/Reynolds?
- logistics: What are arrival/load-in time, parking/load-in instructions, setup location, and PA/sound responsibility?
- music: What music vibe/repertoire, break plan, volume constraints, dress code, or special requests should be captured?
- payment: How will Reynolds pay the $250, who pays, and when should payment be expected?
- reply_watch: Should I run or wire a scoped read-only reply watch for Sally/Reynolds updates?

Boundary
- No external send, calendar/contact mutation, business ledger write, invoice send, paid marking, or money movement.
