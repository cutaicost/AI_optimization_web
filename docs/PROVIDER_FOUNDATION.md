# Provider Foundation

CutAIcost provider adapters declare capabilities rather than simulating unsupported operations. Phase 1 implements OpenAI credential validation and model discovery using `GET https://api.openai.com/v1/models`. Returned model identifiers, owner, and creation time are normalized; context windows, modalities, quality, pricing, and interchangeability remain unknown unless separately verified.

## OpenAI usage limitation

OpenAI provides organization usage endpoints such as `GET /v1/organization/usage/completions` and a cost endpoint at `GET /v1/organization/costs`. Official examples authenticate those organization endpoints with an **Admin API key**, not an ordinary project API key. CutAIcost does not ask a customer to elevate an ordinary connection silently, so Phase 1 advertises `usage_sync=false` and `billing_sync=false` for the OpenAI adapter.

Sources verified 2026-09-06:

- <https://developers.openai.com/api/reference/python/resources/models>
- <https://developers.openai.com/api/reference/python/resources/admin/subresources/organization/subresources/usage>
- <https://developers.openai.com/api/docs/models/compare>

No provider data is labeled LIVE merely because a credential validates. The user-facing live session is explicitly `GATEWAY` mode: only requests submitted to the authenticated telemetry ingestion endpoint are observed per request. Calls made directly to OpenAI remain invisible. The SSE feed sends owner-scoped database observations and heartbeats; it is not a provider billing snapshot.

## Credential encryption

Provider credentials are encrypted per owner/provider using AES-256-GCM. `PROVIDER_CREDENTIAL_MASTER_KEY` must be a URL-safe base64 encoding of exactly 32 random bytes. The key is deployment-injected and must be backed up independently; losing it makes stored provider credentials unrecoverable. Ciphertext records carry a key version to permit a future rotation operation.

Generate a value locally without printing it into source control, then store it in the deployment secret manager. Never reuse `SESSION_SECRET` as this key.

## Pricing and cost provenance

Pricing records are immutable effective-date versions. Phase 1 seeds only models and token prices verified from the official OpenAI model comparison on 2026-09-06. Unknown models return unknown cost rather than zero. Telemetry retains provider-recorded cost, independently calculated cost, the pricing version, and provenance separately.

The admin refresh first resolves the encrypted OpenAI credential owned by the authenticated admin who triggered the operation. It decrypts the credential only server-side and calls the authenticated OpenAI models API. Credentials owned by non-admin users are never searched or reused. Discovered availability is stored independently in `pricing_catalog_models`.

OpenAI's models API does not return token prices. Actual prices therefore use a validated maintained adapter sourced from the official model comparison page and are matched to model identifiers returned by the authenticated catalog call. The refresh UI and audit distinguish `AUTHENTICATED_PROVIDER_API` model discovery from `MANUAL_MAINTAINED_CATALOG` pricing. A preview is required before apply, changed values create new effective-dated catalog versions, and provider failure leaves prior active prices intact.

The maintained OpenAI rate snapshot was reviewed on 2026-09-08. A catalog price is marked `STALE` after 180 days without review. This deliberately conservative threshold is long enough to avoid implying daily automatic price retrieval while forcing a twice-yearly review at minimum; a review should also happen immediately after any provider pricing announcement. The admin action is named **Sync Models & Pricing Catalog**, not “live prices,” because only model discovery is retrieved live.

Previews classify new and unavailable models, unknown and disappeared pricing, increases, decreases, unchanged prices, stale prices, and models whose effective price is protected by a manual override. Per-dimension changes over 10× or under 0.1× are anomaly-flagged and require explicit confirmation. Successful discovery marks models no longer returned by the authenticated provider API as unavailable, without assigning substitute prices.

The signed-in `GET /api/v1/pricing` catalog normalizes primary values to USD per one million tokens. It merges provider availability, active catalog prices, and only the caller's manual overrides. Precedence is owner manual override, active imported catalog, explicitly marked built-in fallback, then unknown. Missing values remain null and render as an em dash rather than `$0.00`.

## Production proxy behavior

`GET /api/v1/live/stream` uses same-origin cookie authentication, `text/event-stream`, five-second heartbeat comments, `Cache-Control: no-cache, no-transform`, and `X-Accel-Buffering: no`. Cloudflare and Railway must leave streaming responses unbuffered and the route timeout must exceed the intended session duration. Browser `EventSource` reconnect supplies `Last-Event-ID`; the server replays only later events belonging to the same owner. No new environment variable is required beyond `PROVIDER_CREDENTIAL_MASTER_KEY`.
