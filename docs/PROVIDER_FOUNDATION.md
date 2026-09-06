# Provider Foundation

CutAIcost provider adapters declare capabilities rather than simulating unsupported operations. Phase 1 implements OpenAI credential validation and model discovery using `GET https://api.openai.com/v1/models`. Returned model identifiers, owner, and creation time are normalized; context windows, modalities, quality, pricing, and interchangeability remain unknown unless separately verified.

## OpenAI usage limitation

OpenAI provides organization usage endpoints such as `GET /v1/organization/usage/completions` and a cost endpoint at `GET /v1/organization/costs`. Official examples authenticate those organization endpoints with an **Admin API key**, not an ordinary project API key. CutAIcost does not ask a customer to elevate an ordinary connection silently, so Phase 1 advertises `usage_sync=false` and `billing_sync=false` for the OpenAI adapter.

Sources verified 2026-09-06:

- <https://developers.openai.com/api/reference/python/resources/models>
- <https://developers.openai.com/api/reference/python/resources/admin/subresources/organization/subresources/usage>
- <https://developers.openai.com/api/docs/models/compare>

No provider data is labeled LIVE merely because a credential validates. Live telemetry requires a later explicitly authorized Admin usage connector or the Observe Gateway.

## Credential encryption

Provider credentials are encrypted per owner/provider using AES-256-GCM. `PROVIDER_CREDENTIAL_MASTER_KEY` must be a URL-safe base64 encoding of exactly 32 random bytes. The key is deployment-injected and must be backed up independently; losing it makes stored provider credentials unrecoverable. Ciphertext records carry a key version to permit a future rotation operation.

Generate a value locally without printing it into source control, then store it in the deployment secret manager. Never reuse `SESSION_SECRET` as this key.

## Pricing and cost provenance

Pricing records are immutable effective-date versions. Phase 1 seeds only models and token prices verified from the official OpenAI model comparison on 2026-09-06. Unknown models return unknown cost rather than zero. Telemetry retains provider-recorded cost, independently calculated cost, the pricing version, and provenance separately.
