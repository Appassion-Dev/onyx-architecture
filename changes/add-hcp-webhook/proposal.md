## Why

HousecallPro can push real-time events (jobs, leads, estimates, invoices, customers, appointments) to a webhook endpoint, but no such endpoint exists in this project today. Before designing any data flow off those events, we need a verified, observable landing point: a function that authenticates HCP's signature and logs exactly what HCP sends, so real payload shapes and signing details can be confirmed against production traffic rather than assumed.

## What Changes

- Add a new public Supabase edge function `hcp-webhook` that receives HCP webhook POSTs.
- Add a `HCP_WEBHOOK_SIGNING_KEY` environment secret used to verify request authenticity.
- Verify HCP's timestamped HMAC-SHA256 signature: read the `Api-Timestamp` and `Api-Signature` headers, compute `HMAC-SHA256(secret, "${Api-Timestamp}.${rawBody}")`, and compare the **hex**-encoded digest against `Api-Signature` in constant time. Reject mismatches with `401`.
- Log each verified request (method, headers with the secret excluded, raw body, parsed body) plus the locally computed HMAC in **both hex and base64** alongside the received `Api-Signature` and the match result, keeping verification observable and any future encoding change detectable.
- Register the function with `verify_jwt = false` in `config.toml` (authenticated by HMAC, not JWT), mirroring `callrail-webhook`.
- Add a README documenting the endpoint, the required secret, and local testing.

**Finding (resolved):** Phase 1 ran log-only with the digest comparison defaulted to base64 (matching `callrail-webhook`) while logging both encodings. Production HCP deliveries (June 2026) showed `computedHex` matching `Api-Signature` on 100% of requests and base64 never matching. The encoding is therefore confirmed as **lowercase hex**; this change flips the comparison to hex and enables `401` enforcement (the fast follow the Phase 1 design named).

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
