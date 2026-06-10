## 1. Scaffold the function

- [x] 1.1 Create `supabase/functions/hcp-webhook/index.ts` with the `Deno.serve` entry, CORS headers, and `json()` helper mirroring `callrail-webhook`
- [x] 1.2 Add `OPTIONS` preflight handling and a `405` guard for non-POST methods

## 2. Signature verification

- [x] 2.1 Read `HCP_WEBHOOK_SIGNING_KEY` from env; log an error and mark verification unconfirmed when it is unset
- [x] 2.2 Read the raw body once via `await req.text()` (do not parse-then-stringify before hashing)
- [x] 2.3 Read `Api-Timestamp` and `Api-Signature` headers; log their absence and mark verification failed when missing
- [x] 2.4 Compute `HMAC-SHA256` over `` `${apiTimestamp}.${rawBody}` `` using the signing key via `crypto.subtle`
- [x] 2.5 Produce both hex and base64 encodings of the digest
- [x] 2.6 Constant-time compare the **base64** digest (default encoding, matching callrail) against `Api-Signature` (compute the boolean result; phase 1 does not yet hard-reject)

## 3. Logging (phase 1 behavior)

- [x] 3.1 Log method, headers (without the secret value), raw body, and parsed JSON body; handle unparseable bodies without throwing
- [x] 3.2 Log the computed hex digest, computed base64 digest, and received `Api-Signature` together to resolve the encoding
- [x] 3.3 Log the verification result (match/encoding) for observability; ensure NO database writes and NO event-key routing occur
- [x] 3.4 Return a `2xx` JSON response

## 4. Configuration & docs

- [x] 4.1 Add `[functions.hcp-webhook]` to `supabase/config.toml` with `enabled = true` and `verify_jwt = false` (comment noting HMAC auth)
- [x] 4.2 Add `supabase/functions/hcp-webhook/README.md` documenting the endpoint, `HCP_WEBHOOK_SIGNING_KEY`, the timestamped-HMAC scheme, the open encoding question, and local testing
- [x] 4.3 Note in the README that signature enforcement (`401` on mismatch) and replay-window rejection are deferred to a later phase

## 5. Verify

- [x] 5.1 Run `supabase functions serve hcp-webhook --no-verify-jwt` and POST a sample payload; confirm it logs method/headers/body and both digest encodings without errors
- [x] 5.2 Confirm a non-POST method returns `405` and an `OPTIONS` request returns CORS headers
