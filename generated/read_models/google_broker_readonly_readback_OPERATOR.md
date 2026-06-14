# Google Broker Read-Only Wrapper

Mode: GOOGLE_READ_ONLY_FIXTURE
Capability: google.gmail.read.metadata
Status: FIXTURE_READBACK_READY

1 tokenized Google metadata result(s) are ready from google.gmail.read.metadata.

Boundary:
- Repo B broker is wrapped as a bounded read-only worker.
- Fixture mode is safe by default; live bridge requires explicit invocation.
- Gmail body, send, draft, calendar/contact write, and attachment reads are blocked.
- Read-models and chat-visible outputs contain tokenized metadata only.

Next safe move: Use tokenized metadata refs only; request a governed adapter before any body/write/send action.
