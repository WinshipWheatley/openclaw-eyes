# Conversation Topic Slicer Contract v0

ELIOPERATOR: Topic slices are non-destructive pointers. The original chat remains intact.

## What This Enables

One chat can point into several worlds/folders through safe topic slices and graph links.

## What This Does Not Do Yet

It does not run live slicing, ingest transcripts, write graph links, move folders, split threads, retrieve agents, or execute external actions.

## How Slices Work

A slice stores inferred topic, safe summary, source thread ref, message pointer range, and candidate graph/folder targets.

## Examples

- one_chat_three_topics: topic_slice_setlist_ideas, topic_slice_x32_routing_issue, topic_slice_new_song_arrangement, topic_slice_booking_followup
- misfiled_chat: topic_slice_capital_hilton_invoice_specific, topic_slice_invoice_automation_architecture
- x32_fader_replacement: topic_slice_x32_fader_replacement
- struna_drift: (none)
- raw_transcript_copy_blocker: (none)

## Reorganization Proposals

- proposal_multitopic_live_music_links: NON_DISRUPTIVE_SUGGESTION / review=True
- proposal_misfiled_invoice_architecture_link: NON_DISRUPTIVE_SUGGESTION / review=True
- proposal_x32_fader_resume_candidate: NON_DISRUPTIVE_SUGGESTION / review=True
- proposal_struna_cross_world_review: REVIEW_REQUIRED_MOVE / review=True

## Blockers

- RAW_TRANSCRIPT_COPIED: Block the copy and store pointer ranges plus safe summaries only.
- RAW_TRANSCRIPT_EXPOSED: Use safe summaries and source refs; keep raw bodies gated.
- SOURCE_PROVENANCE_MISSING: Fail closed until pointer refs exist.
- CROSS_CLIENT_LEAK: Block cross-client link unless explicit reviewed permission exists.
- CROSS_TENANT_LEAK: Block cross-tenant link.
- SILENT_DESTRUCTIVE_REORGANIZATION: Do not reorganize destructively; show a reviewable proposal.
- AUTO_MOVE_TOO_DISRUPTIVE: Move and split actions require operator approval.
- MESSAGE_POINTER_MISSING: Do not create the slice until pointer range is available.
- UNKNOWN_FOLDER: Ask for a folder choice or create a reviewable folder suggestion.
- AMBIGUOUS_TOPIC: Ask a clarifying question before linking.
- UNKNOWN_FAIL_CLOSED: Fail closed and preserve the original thread.

## Boundary

No live topic slicing, raw transcript ingestion/copy, graph link write, reorganization, folder move, thread split, delete, agent retrieval, cross-scope query, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.

Next safe move: Export non-destructive topic slice examples and wait for a future approved slicer/runtime before writing links.
