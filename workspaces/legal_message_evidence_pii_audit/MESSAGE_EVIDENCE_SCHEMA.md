# Message Evidence Schema

## Raw Evidence Schema (Sealed)
- `matter_id`: UUID
- `evidence_id`: UUID
- `source_artifact_id`: UUID (points to the extraction archive)
- `source_artifact_hash`: SHA-256
- `source_device_id` / `source_account_id`
- `source_export_method`: String (e.g., "iTunes Backup", "Google Takeout")
- `source_export_timestamp`: UTC ISO8601
- `conversation_id`: String (native identifier from the app)
- `thread_id`: String (logical thread)
- `message_id`: String
- `message_sequence`: Integer (for robust ordering)
- `sender_entity_id` / `sender_endpoint_id`: Raw phone number, email, or UUID
- `recipient_entity_ids` / `recipient_endpoint_ids`: List of raw identifiers
- `message_direction`: "incoming" | "outgoing"
- `message_body_exact`: String (untouched)
- `message_body_hash`: SHA-256
- `message_timestamp_raw`: String/Integer (as extracted)
- `message_timestamp_utc`: UTC ISO8601
- `timezone_offset`: String
- `timestamp_source`: String (e.g., "device_clock", "server_receipt")
- `delivery_status` / `read_status` / `edit_status` / `deletion_or_unsent_status`
- `reaction_data`: JSON
- `attachment_references`: List of UUIDs
- `reply_to_message_reference`: message_id
- `group_membership`: JSON
- `source_record_location`: String (e.g., SQLite rowid)
- `ingestion_timestamp`: UTC ISO8601
- `parser_identity_and_version`: String
- `schema_version`: String
- `validation_status`: String
- `provenance_receipt`: JSON

## Tokenized Working Schema
Identical to Raw, EXCEPT:
- `sender_entity_id`, `recipient_entity_ids`, etc. are replaced by stable `[PHONE_A1]` or `[PERSON_A]` tokens.
- `message_body_exact` is scanned, and direct PII mentions (phone numbers, addresses) are substituted with tokens.
- Stable references back to the raw `evidence_id` and `message_id` remain intact to support verified detokenized views.

## Two-Phone Identity Mapping Model
A single opposing person may use two phones. The system models Endpoints and Persons separately.
- `person_entity_id`: `[PERSON_A]`
- `endpoint_id`: `[PHONE_A1]` (Number 1), `[PHONE_A2]` (Number 2)
- `endpoint_type`: "sms", "imessage", "whatsapp"
- `valid_from` / `valid_to`: UTC Date bounds for when the person owned this endpoint.
- `association_confidence`: "operator_confirmed", "inferred", "disputed"
- `association_source_evidence`: References to message_ids where they self-identified.
- `notes`: Rationale for the link.

This structure allows searching both numbers under `[PERSON_A]` while retaining the exact `[PHONE_A1]` or `[PHONE_A2]` origin for every single message.
