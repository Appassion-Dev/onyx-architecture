## Why

HousecallPro can push real-time events (jobs, leads, estimates, invoices, customers, appointments) to a webhook endpoint, but no such endpoint exists in this project today. Before designing any data flow off those events, we need a verified, observable landing point: a function that authenticates HCP's signature and logs exactly what HCP sends, so real payload shapes and signing details can be confirmed against production traffic rather than assumed.

## What Changes

- Add a new public Supabase edge function `hcp-webhook` that receives HCP webhook POSTs.
- Add a `HCP_WEBHOOK_SIGNING_KEY` environment secret used to verify request authenticity.
- Verify HCP's timestamped HMAC-SHA256 signature: read the `Api-Timestamp` and `Api-Signature` headers, compute `HMAC-SHA256(secret, "${Api-Timestamp}.${rawBody}")`, and compare against `Api-Signature` in constant time. Reject mismatches with `401`.
- Log each incoming request (method, headers with the signature/secret redacted, raw body, parsed body) plus the locally computed HMAC in **both hex and base64** alongside the received `Api-Signature`, so the first genuine HCP delivery resolves which digest encoding HCP uses.
- Register the function with `verify_jwt = false` in `config.toml` (authenticated by HMAC, not JWT), mirroring `callrail-webhook`.
- Add a README documenting the endpoint, the required secret, and local testing.

Explicitly **out of scope** for this change (deferred to a later phase):

- Any database writes or upserts.
- Routing/handling by `event` key (`job.*`, `lead.*`, `estimate.*`, `invoice.*`, etc.).
- Replay-attack enforcement via the `Api-Timestamp` freshness window (the timestamp is verified as part of the signed message, but stale-timestamp rejection is deferred).

## Capabilities

### New Capabilities

- `hcp-webhook-ingestion`: Receiving HousecallPro webhook events at a public endpoint, authenticating them via HCP's timestamped HMAC-SHA256 signature, and logging each request for observability.

### Modified Capabilities

<!-- None. This change introduces a new endpoint and does not alter requirements of any existing capability. -->

## Impact

- **New code**: `supabase/functions/hcp-webhook/` (`index.ts`, `README.md`).
- **Config**: new `[functions.hcp-webhook]` block in `supabase/config.toml` with `verify_jwt = false`.
- **Secrets**: new `HCP_WEBHOOK_SIGNING_KEY` (obtained from HCP account webhook settings).
- **External**: an HCP webhook subscription must be pointed at `POST /functions/v1/hcp-webhook`.
- **Pattern**: closely follows the existing `callrail-webhook` function; differs in header names (`Api-Timestamp` + `Api-Signature`), hash (SHA-256 vs SHA-1), and signed message (`timestamp.body` vs body).
