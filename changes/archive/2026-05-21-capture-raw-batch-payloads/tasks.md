## 1. Schema migration

- [x] 1.1 Add a new migration `supabase/migrations/<timestamp>_gads_batches_raw_payload_columns.sql` that runs `ALTER TABLE public.gads_conversion_upload_batches ADD COLUMN IF NOT EXISTS request_body jsonb, ADD COLUMN IF NOT EXISTS response_body jsonb;`
- [x] 1.2 Confirm RLS / grants on `gads_conversion_upload_batches` already cover the new columns (table-level grants apply; no per-column grant needed)

## 2. Edge function — capture in `ads-api.ts`

- [x] 2.1 In [ads-api.ts](supabase/functions/google-ads-conversion-upload/ads-api.ts), build the request body object once (`const requestBody = { conversions: toUpload.map((x) => x.conv), partialFailure: true }`) and pass it to both `JSON.stringify` and the return value
- [x] 2.2 Extend the `ApiResult` interface in [types.ts](supabase/functions/google-ads-conversion-upload/types.ts) with `requestBody: Record<string, unknown>`
- [x] 2.3 In the network-error branch, set `data = { network_error: String(err).slice(0, 4000), captured_at: new Date().toISOString() }` so the downstream writer has a single field shape to persist
- [x] 2.4 In the mock-response branch, still return `requestBody` so test paths exercise the same wiring

## 3. Edge function — persist on the batch row

- [x] 3.1 Update [outcomes.ts:158-165](supabase/functions/google-ads-conversion-upload/outcomes.ts#L158-L165) (`applyPerRowOutcomes` batch finalize) to write `request_body` and `response_body` alongside the existing `http_status` / `accepted_count` / `rejected_count` / `job_id`
- [x] 3.2 Update [outcomes.ts:45-51](supabase/functions/google-ads-conversion-upload/outcomes.ts#L45-L51) (`handleBatchFailure`) to write `request_body` and `response_body` alongside the existing failure fields; when `http_status` indicates non-2xx and `data` is `null`, write `response_body = null`
- [x] 3.3 Update the call sites in [index.ts](supabase/functions/google-ads-conversion-upload/index.ts) so the new `requestBody` from `callGoogleAds` reaches both `handleBatchFailure` and `applyPerRowOutcomes`; update their function signatures accordingly

## 4. Tests

- [x] 4.1 In [ads-api.test.ts](supabase/functions/google-ads-conversion-upload/ads-api.test.ts), assert that `callGoogleAds` returns `requestBody` matching the expected `{ conversions, partialFailure: true }` shape for: success path, mock-response path, and network-error path (where `data` is the structured envelope)
- [x] 4.2 In [outcomes.test.ts](supabase/functions/google-ads-conversion-upload/outcomes.test.ts), assert that the batch row update payload contains `request_body` and `response_body` for both `applyPerRowOutcomes` (success and partial-failure cases) and `handleBatchFailure` (HTTP error and network-error cases)
- [x] 4.3 In [index.test.ts](supabase/functions/google-ads-conversion-upload/index.test.ts), add an end-to-end test (using the existing `_mock_response` test hook) that verifies the persisted batch row has both `request_body` and `response_body` populated and that `request_body.conversions[0].gclid` matches the input row's gclid
- [x] 4.4 Add a network-error end-to-end test asserting `response_body.network_error` is populated and the batch's lifecycle fallout (rows back to `queued`, `attempt_count` incremented) is unchanged

## 5. Verification

- [x] 5.1 Run `deno test` against `supabase/functions/google-ads-conversion-upload/` and confirm all tests pass
- [ ] 5.2 Run the migration against a local Supabase instance and confirm the two columns exist with `jsonb` type and `NULL` for existing rows
- [ ] 5.3 Invoke the edge function locally with `_dry_run` or `_mock_response` and confirm the new batch row has both columns populated by querying `select id, http_status, jsonb_typeof(request_body), jsonb_typeof(response_body) from gads_conversion_upload_batches order by sent_at desc limit 1;`
- [x] 5.4 Run `openspec validate capture-raw-batch-payloads --strict` and resolve any findings
