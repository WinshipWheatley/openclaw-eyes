# Boundaries

Allowed data classes:
- generated_read_model_metadata: Generated read-model metadata may be referenced without treating it as truth.
- public_project_metadata: Public/internal project metadata may be referenced for planning.
- synthetic_demo_metadata: Synthetic project planning data is allowed inside this demo capsule.

Forbidden data classes:
- credentials_secrets_tokens: Credentials, secrets, tokens, and auth material remain no-go.
- private_legal_tax_finance: Private, legal, tax, CPA, and finance material is not in scope.
- real_client_data: No real client data is allowed in Project Capsule v0.
- runtime_logs_production_data: Runtime logs and production customer data are not in scope.

No real client data, credentials, private/legal/tax/finance material, runtime logs, or production customer data belongs in this synthetic capsule.
