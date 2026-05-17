# Operator Workflow Atlas

This is a grounded gap scan from current Repo A read-models and operations docs. Old files/docs are evidence, not truth.

At a glance:
- Workflows classified: 14.
- Confirmed built and wired: 4.
- Built but not fully steel-threaded: 5.
- Desired/planned/blocked but not built: 2.
- Should not build yet: 3.
- Manual rewrite required from Winship: no.
- MD/source ingestion required before next batch: no.

Built / Implemented:
- Capital Hilton invoice manual review
- Cassandra governed request to review packet
- Guardian HITL observational receipts
- Cassandra/Chief structured fact evidence

Built / Not Fully Integrated:
- Cassandra live receive into governed intake
- Work Board and Agent Work Packets
- Mission Control operator helm visibility
- Active machinery quarantine review
- Report Bridge client-safe status helper

Desired / Not Built:
- Niles album progress review
- Markdown and source classification for broad workflow discovery

Not Built / Should Not Build Yet:
- Remote builder bridge
- Send, reply, and portal submission automation
- Hard-drive/cloud/file ingest

Top Shared Bottlenecks:
- `governed_receive_to_work_packet_projection`: 2 workflows

Recommended First 3 Batch Lanes:
1. Capital Hilton Manual Confirmation Receipt v0
   - workflow: Capital Hilton invoice manual review
   - bottleneck: `manual_confirmation_receipt_binding`
   - gate: `pass`
   - output: Capital Hilton manual confirmation checklist/receipt read-model.
2. Niles Album Review Packet From Governed Evidence v0
   - workflow: Niles album progress review
   - bottleneck: `generic_review_packet_non_finance_reuse`
   - gate: `pass`
   - output: Niles album review packet or missing-facts packet.
3. Report Bridge Client Status Packet Proof v0
   - workflow: Client-safe project status review
   - bottleneck: `report_bridge_client_capsule_boundary`
   - gate: `pass`
   - output: Client-safe status packet proof with no raw client data.

Markdown / Source Classification:
- Sufficient for next batch: yes.
- Full-system restructure still needs ingestion/tagging: yes.
- Smallest later lane: Workflow Evidence Header Inventory v0.

Boundaries:
- No runtime authority added.
- No send/submit/customer deployment authority added.
- No Repo B execution.
- No broad private/source ingest.

Next recommended lane: Capital Hilton Manual Confirmation Receipt v0
