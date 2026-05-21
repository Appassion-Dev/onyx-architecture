## Context

`gads_conversion_upload_batches` already exists (added in [20260518000001_gads_error_dispositions_schema.sql](supabase/migrations/20260518000001_gads_error_dispositions_schema.sql)) and stores one row per upload batch with `http_status`, `request_error_code`, `request_error_message`, `row_count`, `accepted_count`, `rejected_count`, and `job_id`. The edge function builds the wire body in [ads-api.ts:25](supabase/functions/google-ads-conversion-upload/ads-api.ts#L25) (`JSON.stringify({ conversions, partialFailure: true })`) and parses the response in [ads-api.ts:27](supabase/functions/google-ads-conversion-upload/ads-api.ts#L27). Neither survives past the function invocation. Failed batches today only expose `request_error_code` / `request_error_message` (a 2 KB truncation of the parsed error) and per-row `error_detail` jsonb — sufficient for the lifecycle state machine but not for replay or Google support tickets.

## Goals / Non-Goals

**Goals:**
- Persist the exact JSON body POSTed to `uploadClickConversions` for every batch.
- Persist the parsed JSON response body Google returned, OR a structured envelope when the network call fails before a JSON body is available.
- Make the new columns visible to the same readers as the rest of the batch row (no new RLS scope).
- Cover both success and failure code paths so an investigator can pull any batch by id.

**Non-Goals:**
- Truncation, compression, or sampling. Current batch sizes are small; revisit if a single batch ever exceeds ~256 KB.
- Retention policy / TTL. Out of scope — orthogonal concern; can be added later as a scheduled cleanup.
- Capturing request/response *headers* (auth tokens, dev-token, login-customer-id). Headers carry secrets and add no investigative value the body lacks.
- Logging at the row level. The batch row is the right grain — per-row JSON would duplicate the request body N times.
- Capturing the raw response *text* when JSON parse fails. The HTTP status + network error envelope is enough; if Google returns non-JSON on 2xx, that's a separate bug.

## Decisions

### 1. Two `jsonb` columns on the existing batch table

Add `request_body jsonb` and `response_body jsonb` to `gads_conversion_upload_batches`. Both nullable.

- **Why not a separate `gads_conversion_upload_batch_payloads` side table?** No access pattern requires lazy loading. The batch row is already the unit investigators query, and a join just to read what was sent is friction. If retention later demands deleting bodies without losing the metadata row, the columns can be nulled in-place.
- **Why `jsonb` not `text`?** We always have JSON (we constructed the request as an object before stringifying; the response is parsed before we touch it). `jsonb` enables querying (`request_body -> 'conversions' -> 0 ->> 'gclid'`) and dedupes whitespace. The successful-response captured from `await res.json()` is already an object — storing it as `jsonb` is the natural shape.
- **Why not capture the literal stringified bytes?** The body POSTed is `JSON.stringify(obj)` — round-tripping the object through Postgres `jsonb` reproduces it byte-equivalent for our purposes (key order is preserved by stringify because we construct the object explicitly, and Postgres preserves jsonb key order on retrieval via `jsonb_pretty` is irrelevant since we don't depend on whitespace). Acceptable.

### 2. Structured envelope for network errors

When `fetch` throws (DNS, TCP, TLS, timeout), there is no response body. Store:

```json
{
  "network_error": "<String(err).slice(0, 4000)>",
  "captured_at": "<ISO timestamp>"
}
```

into `response_body`, distinguishable from a real Google response by the presence of the `network_error` key. `http_status` already records 599 in this case.

### 3. Capture the request body in `callGoogleAds`, return it alongside the response

[ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts) is the only place that holds both the input array (`toUpload`) and the final wire shape. Build the body object once, hand the same object to both `JSON.stringify` and the return value:

```ts
const requestBody = { conversions: toUpload.map((x) => x.conv), partialFailure: true };
// ... fetch with JSON.stringify(requestBody) ...
return { res, data, networkError, requestBody };
```

Extend `ApiResult` in [types.ts](supabase/functions/google-ads-conversion-upload/types.ts) with `requestBody: Record<string, unknown>`.

- **Alternative considered**: capture the body in the caller before invoking `callGoogleAds`. Rejected — `callGoogleAds` already owns the wire-shape responsibility; duplicating it in [index.ts](supabase/functions/google-ads-conversion-upload/index.ts) splits the source of truth.

### 4. Mock-response test path also returns a `requestBody`

When `mockResponse` is provided, the function never hits the wire. We still build and return the would-be request body so tests can assert on it and so the bookkeeping write is uniform with production behavior.

### 5. Write happens in `outcomes.ts` and `handleBatchFailure`, not `createBatch`

`createBatch` runs *before* the HTTP call, so it cannot know the request body in full (well — technically it could, since we've already built `toUpload`, but it does not currently take `cfg` or the partialFailure flag). Defer both writes to the terminal-write paths:

- `applyPerRowOutcomes` ([outcomes.ts:158-165](supabase/functions/google-ads-conversion-upload/outcomes.ts#L158-L165)) — the existing `gads_conversion_upload_batches` update extends to include `request_body` and `response_body`.
- `handleBatchFailure` ([outcomes.ts:45-51](supabase/functions/google-ads-conversion-upload/outcomes.ts#L45-L51)) — same update extension.

Both already write to the batch row exactly once at the end; one place to add columns each.

### 6. Storage shape for the response envelope

| Scenario | `http_status` | `response_body` |
|---|---|---|
| 2xx success (no partial failures) | 200 | parsed JSON from Google |
| 2xx with partialFailureError | 200 | parsed JSON from Google (includes the `partialFailureError` field) |
| Non-2xx HTTP response | 4xx/5xx | `null` (current `ads-api.ts` only calls `res.json()` on `res.ok`; preserve this — we don't know the error body is JSON) |
| Network/fetch error | 599 | `{ "network_error": "...", "captured_at": "..." }` |
| Mock test path | mock-controlled | the mock response value |

Capturing the non-2xx error body would require `await res.text()` and best-effort JSON parsing. Deferred — current operational signal (`request_error_code` from the parsed error path) is sufficient, and a non-2xx Google Ads response without a parseable JSON error is itself unusual enough to investigate via logs.

## Risks / Trade-offs

- **Storage growth** → Mitigation: monitor `pg_total_relation_size('gads_conversion_upload_batches')` after deploy; if it grows faster than expected, add a scheduled cleanup that nulls `request_body`/`response_body` on batches older than N days. Not done now to avoid scope creep.
- **PII in jsonb** → Mitigation: identifiers in the request are already SHA-256 hashed by [hashing.ts](supabase/functions/google-ads-conversion-upload/hashing.ts) before they reach `ads-api.ts`; GCLIDs are opaque click identifiers; `orderId` is the internal `estimate_id`. No additional categories of personal data leave the function. RLS on the table already restricts to `service_role` for write and `authenticated` for read — matches the existing surface.
- **Schema drift between captured request and Google's accepted shape** → Mitigation: we capture the body we sent, not what Google parsed. If Google changes the API and our body becomes invalid, that's exactly the case we want to investigate, so storing our intent is correct.
- **Successful-batch row count blow-up** → Currently batches run on a cadence and contain dozens of rows. If the function later moves to streaming or very large batches, a single `request_body` could exceed Postgres's practical jsonb working size (~256 MB hard limit, but realistically queries get slow well before that). Out of scope for this change; if batches grow, revisit.

## Migration Plan

1. **Schema migration** — additive, non-breaking, no backfill. Two `ADD COLUMN IF NOT EXISTS … jsonb` statements. Existing rows stay `NULL`.
2. **Code deploy** — the upload function starts writing both columns from the moment it ships. No coordination with readers needed (no consumer currently depends on these columns).
3. **Rollback** — if the new write causes errors, the Supabase update is in the same batch as the existing batch-finalization update; reverting the function deploy is sufficient. The columns can stay (harmless additions); a follow-up `DROP COLUMN` is only needed if storage growth proves unacceptable.

## Open Questions

- None blocking. Retention policy (when to null/delete old bodies) can be decided after observing storage growth in production.
