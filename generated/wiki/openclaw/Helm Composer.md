# Helm Composer

Status: HELM_COMPOSER_CONTRACT_READY

Helm Composer is a calm entry point for asking OpenClaw what is next or staging safe operator packages from Helm. It shows one current answer, keeps history short, and leaves proof collapsed by default.

## What It Can Route
- System questions through `system_question_answer`.
- Safe operator package requests through the package queue.
- St. Anne's work-log intake.
- Capital Hilton proposal follow-up staging.
- Capital Hilton invoice operator-assist staging.

## Suggested Prompts
- What is safe next?
- What is Chief watching?
- What does Hermes recommend?
- Why did Capital Hilton invoice block?
- Mark that I'm at church running sound.
- What is the difference between Chief and a spawned worker?

## Display Policy
- Show one current answer.
- Show at most three recent context items by default.
- Keep proof refs, machine details, and history drawers collapsed.
- Hide raw request bodies and full conversation history by default.

## Authority Boundary
Composer does not execute business actions directly. Email, Gmail, Coupa, browser access, ledger posting, workbook mutation, PDF export, submit, sent, and paid remain gated and false in this contract.

## Backend Sources
- `generated/read_models/workflow_package_queue_contract.json`
- `generated/read_models/workflow_package_request_consumer_status.json`
- `generated/read_models/system_question_answer_contract.json`
- `generated/read_models/package_event_index.json`
- `generated/read_models/operator_conversation_journal.json`
- `generated/read_models/overnight_workboard.json`
- `generated/read_models/agent_voice_profiles.json`
- `generated/read_models/operator_human_readability_surface.json`
