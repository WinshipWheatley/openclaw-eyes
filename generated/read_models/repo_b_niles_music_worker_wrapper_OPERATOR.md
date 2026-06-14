# Repo B Niles Music Worker Wrapper

## Summary
Repo B music logic is useful as a Niles creative planning/reference surface, but v0 keeps it fixture/source-ref based and blocks DAW, media, file-body, model, and publishing authority.

## Posture
- Wrapper posture: WRAP_AS_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET
- Repo B invocation: none in v0
- Source mode: metadata/source refs and safe summaries only

## Safe Capabilities
- SETLIST_PLANNING: Create a safe setlist arc from operator goals and source refs without touching files or apps.
- ALBUM_TASK_TRACKING: Summarize album task status from safe work-log/source-ref metadata.
- SONG_METADATA_ORGANIZATION: Organize song status labels, section refs, and album placement without copying raw song bodies.
- MIX_NOTE_SUMMARY: Summarize already-safe mix-note highlights and pass/gap status.
- ARRANGEMENT_IDEA: Suggest arrangement next moves from topic slices and safe song summaries.
- LIVE_SHOW_PLANNING: Plan rehearsal/show context and needed source refs for live music work.
- CREATIVE_PROJECT_STATUS: Produce a project status readback from safe album/song metadata refs.
- WORK_LOG_READBACK: Create a safe work-log readback when a metadata/source-ref rail exists.
- SOURCE_REF_NAVIGATION: Help the operator locate relevant music source refs without scanning folders or opening project files.

## Blocked Capabilities
- DAW_MUTATION_ATTEMPTED: DAW/project mutation is not allowed in the Niles wrapper.
- AUDIO_FILE_MUTATION_ATTEMPTED: Audio file mutation is outside this lane.
- VIDEO_FILE_MUTATION_ATTEMPTED: Video project mutation is outside this lane.
- EXPORT_OR_PUBLISH_ATTEMPTED: Publishing/exporting requires a separate gated adapter.
- BROAD_MUSIC_FOLDER_SCAN: Broad music folder scanning is blocked.
- RAW_LYRIC_OR_NOTE_BODY_EXPOSED: Raw creative bodies stay below deck.
- RAW_PROJECT_FILE_INGESTION: Project file ingestion is blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- CREDENTIAL_REQUIRED: Credentials are not handled here.
- UNKNOWN_FAIL_CLOSED: Unknown actions fail closed.

## Example Readback
- Status: FIXTURE_READBACK_READY
- Summary: Niles can draft a setlist arc from safe show goals and setlist source refs without touching files or apps.
- Next safe move: Ask the operator for set length and must-play refs, then return a second setlist card.

## Boundary
No DAW control, no audio/video/project mutation, no export/publish/upload, no external action, no credentials, no raw private body exposure.
