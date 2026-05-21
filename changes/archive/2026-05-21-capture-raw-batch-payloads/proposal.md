## Why

The `google-ads-conversion-upload` edge function discards both the JSON body it sends to `customers/{id}:uploadClickConversions` and the JSON body Google returns. When a batch fails, when a customer disputes attribution, or when we open a Google Ads support case, we currently have to *reconstruct* the request from `gads_conversion_uploads` rows joined by `batch_id` — an approximation that omits payload ordering, the exact wire shape, and any successful-result detail Google returned. We need an authoritative record per batch so failures are investigable without rerunning the pipeline.

## What Changes

- Add two `jsonb` columns to `gads_conversion_upload_batches`: `request_body` (the exact body POSTed to Google) and `response_body` (the parsed JSON Google returned, or a structured network-error envelope).
- Capture both in [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts) and persist them on the batch row in *every* terminal write path (success, partial failure, batch failure, network error, mock-response test path).
- Persist hashed identifiers as-sent — they are already SHA-256, so no additional PII risk beyond what we already write into `gads_conversion_uploads.estimates → customers`.
- Do **not** truncate or sample. Batches are bounded by the upstream payload-builder (one batch per cron invocation, currently dozens of rows), so a few KB of JSON per row is acceptable storage.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `conversion-upload`: the upload function MUST persist the raw request and response per batch onto `gads_conversion_upload_batches`.

## Impact

- **Schema**: new migration adding `request_body jsonb` and `response_body jsonb` to `gads_conversion_upload_batches` (both nullable; backfill not required — existing rows stay NULL).
- **Code**: [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts) returns the request body alongside the response; [outcomes.ts](supabase/functions/google-ads-conversion-upload/outcomes.ts) and [batches.ts](supabase/functions/google-ads-conversion-upload/batches.ts) write both columns. [index.ts](supabase/functions/google-ads-conversion-upload/index.ts) wiring threads them through.
- **Tests**: [ads-api.test.ts](supabase/functions/google-ads-conversion-upload/ads-api.test.ts), [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts), and [index.test.ts](supabase/functions/google-ads-conversion-upload/index.test.ts) gain assertions that both columns are populated on success and failure paths.
- **Storage**: jsonb growth scales with batch size; expected < 50 KB per batch at current volumes. No retention policy added in this change.
- **PII**: identifiers in `request_body` are already SHA-256 hashed; GCLIDs are opaque click IDs. RLS on `gads_conversion_upload_batches` is unchanged (service_role write, authenticated read).
