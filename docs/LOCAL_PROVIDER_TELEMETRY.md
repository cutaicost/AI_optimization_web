# Local provider telemetry

Provider credentials are controlled from **Administration → AI Providers**. Only administrators can connect, replace, test, refresh, or remove an OpenAI credential.

For local development, set `PROVIDER_CREDENTIAL_MASTER_KEY` to a URL-safe base64 encoding of exactly 32 random bytes before starting the API. Keep that value stable: changing it makes previously stored credentials undecryptable. The API key is encrypted in the database, never returned by the API, and never stored in browser storage.

Connection testing and model discovery use OpenAI's `GET /v1/models` endpoint. Public `/api/telemetry` output is deliberately sanitized and exposes only aggregate provider availability, measured latency, refresh time, and independently sourced pricing catalog entries. It does not expose credentials, credential masks, administrators, or non-catalog model identifiers.

Ordinary project API keys do not provide organization billing telemetry. Live usage remains unavailable unless a future, separately authorized organization Admin API integration is implemented.
