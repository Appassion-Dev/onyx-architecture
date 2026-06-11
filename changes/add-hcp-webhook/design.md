## Context

HousecallPro signs every webhook it sends. Per HCP's webhook docs, two headers accompany each POST:

- `Api-Timestamp`: seconds since the epoch (e.g. `1677189615`).
- `Api-Signature`: an HMAC-SHA256 computed with the account's signing secret over the message `"${Api-Timestamp}.${json_payload}"`.

This project already has a near-identical pattern in [`callrail-webhook`](../../functions/callrail-webhook/index.ts): a public edge function (`verify_jwt = false`) that authenticates inbound requests by recomputing an HMAC over the raw body and comparing it constant-time. The HCP function reuses that shape and differs only in the signing scheme.

The function's first phase is observability only — verify the signature and log what arrives — so that production payload shapes and the exact signature encoding can be confirmed before any handling logic is written.

## Goals / Non-Goals

**Goals:**
- Stand up a public `hcp-webhook` endpoint that HCP can POST to.
- Authenticate requests using HCP's timestamped HMAC-SHA256 scheme and a `HCP_WEBHOOK_SIGNING_KEY` secret.
- Log each request richly enough to (a) inspect real HCP payloads and (b) resolve the undocumented digest encoding (hex vs base64) from the first genuine delivery.
- Follow the existing `callrail-webhook` conventions (CORS helper, `json()` helper, constant-time compare, structured `console.*`).

**Non-Goals:**
- Persisting events to the database.
- Routing or interpreting events by `event` key.
- Enforcing timestamp freshness (replay rejection) — deferred to a later phase.
- Backfilling or reconciling historical HCP data.

## Decisions

**1. Signed message is `"${Api-Timestamp}.${rawBody}"`, hashed with HMAC-SHA256.**
HCP's docs specify the signature body as `timestamp + "." + json_payload`. We use Web Crypto (`crypto.subtle`) with `{ name: "HMAC", hash: "SHA-256" }`, the same API callrail uses (callrail uses SHA-1). Rationale: matches HCP's spec exactly; no new dependencies.

**2. HMAC is computed over the raw request body string, never a re-serialized payload.**
The handler reads `await req.text()` once and hashes that exact string. We do *not* `JSON.parse` → `JSON.stringify` before hashing, because re-serialization can reorder keys / change whitespace and break the signature. HCP's phrase "JSON representation of the payload" is interpreted as the bytes as transmitted. Alternative (re-stringify) rejected as fragile and signature-breaking.

**3. Default the digest encoding to base64, but log both to confirm. — RESOLVED: HCP uses lowercase hex.**
HCP's docs say "a cryptographic hash" without specifying hex vs base64. Phase 1 defaulted the comparison to **base64** (matching `callrail-webhook`) while logging the locally computed HMAC in **both** encodings next to the received `Api-Signature`. Production deliveries (June 2026, e.g. `customer.updated`, `invoice.*`) resolved it: `computedHex` matched `Api-Signature` exactly on every request, while `matchesBase64` was always `false`. Example: received `6d0d6bdf…48649a94` == `computedHex` `6d0d6bdf…48649a94`. The base64 prior was wrong; **the confirmed encoding is lowercase hex.** This change flips the comparison to hex.

**4. ~~Verify against base64, but phase 1 still logs rather than hard-rejecting.~~ — Enforcement now enabled (hex).**
Phase 1 logged the payload regardless of match so traffic could be observed even if the encoding guess was wrong; that safety net (the dual-encoding log) did its job and revealed hex. With the encoding confirmed, the function now compares the **hex** digest in constant time and hard-rejects mismatches with `401`, logging the request body only for verified requests. A missing signing key or absent signature headers are treated as a failed match → `401`. The dual-encoding log line is retained so any future encoding change by HCP remains detectable.

**5. Public function, `verify_jwt = false`.**
External webhooks cannot present a Supabase JWT; authenticity comes from the HMAC. This matches `callrail-webhook` and the documented project convention for webhook endpoints.

**6. Secrets and config never logged.**
Logged headers redact `Api-Signature` value? No — the signature is not secret and is needed for debugging encoding, so it IS logged. The signing key (`HCP_WEBHOOK_SIGNING_KEY`) is never logged.

## Risks / Trade-offs

- **Base64 default turns out wrong (HCP uses hex)** → Mitigated by logging both hex and base64; no hard enforcement until a real delivery confirms base64, at which point the default is flipped if needed.
- **Re-serializing the body breaks verification** → Mitigated by hashing `req.text()` directly; documented as decision #2.
- **No replay protection in phase 1** → Accepted: log-only phase has no side effects to replay; freshness window deferred. The timestamp is already part of the signed message, so adding rejection later is non-breaking.
- **Phase-1 soft verification accepts unverified payloads into logs** → Accepted and temporary; logs are not a trust boundary and contain no acted-upon side effects. Enforcement is a fast follow.
- **Unset `HCP_WEBHOOK_SIGNING_KEY`** → Function logs an error and treats verification as failed/unconfirmed (mirrors callrail's "reject when key absent in prod, skip locally" stance).

## Migration Plan

1. Deploy the function (`supabase functions deploy hcp-webhook`) and set `HCP_WEBHOOK_SIGNING_KEY`.
2. Register the endpoint in HCP and trigger a test event.
3. Inspect logs: confirm which encoding (hex/base64) matches `Api-Signature`; confirm payload shapes.
4. (Later change) Lock the encoding, enable `401` enforcement, add replay window, add event routing.

Rollback: remove the HCP webhook subscription and/or disable the function in `config.toml`. No data is written, so rollback is side-effect-free.

## Open Questions

- ~~Digest encoding: defaulted to base64 (matches `callrail-webhook`); confirmed or flipped by the first real delivery's logs.~~ **Resolved: lowercase hex** (see decision #3).
- Does HCP retry on non-2xx? (Now relevant since enforcement returns `401` on mismatch — a misconfigured signing key would cause HCP to retry/disable. To confirm from HCP behavior, not blocking. The signing key is verified present in production.)
