## 1. Catalog generation (gads-error-catalog-sync)

- [ ] 1.1 Add `horizon-dashboard/scripts/sync-gads-errors.mjs` with pinned URLs for the six v23 proto files (`conversion_upload_error.proto`, `user_data_error.proto`, `quota_error.proto`, `internal_error.proto`, `authentication_error.proto`, `field_error.proto`)
- [ ] 1.2 Implement the enum-block tokenizer that parses `ENUM_NAME = <int>; // <comment>` lines, asserts the strict regex from spec D1, and bails on malformed input
- [ ] 1.3 Implement description normalization (collapse newlines, strip `//` markers, trim) and JSON writer with sorted keys for deterministic output
- [ ] 1.4 Add `"sync:gads-errors": "node scripts/sync-gads-errors.mjs"` to `horizon-dashboard/package.json`
- [ ] 1.5 Run the script and commit the generated `supabase/generated/gads_error_catalog.json`
- [ ] 1.6 Verify byte-identical re-run (run twice, confirm `git diff` is empty)
- [ ] 1.7 Verify catalog covers every enum value across all six namespaces (manual spot check against proto sources)

## 2. Schema migration — tables and columns

- [ ] 2.1 Create migration file `supabase/migrations/<ts>_gads_error_dispositions_schema.sql`
- [ ] 2.2 In the migration, add `gads_error_dispositions` table with PK `error_code`, CHECK on `disposition`, defaults for `retry_after_seconds`, `no_alert`, `source`, `updated_at`
- [ ] 2.3 Add `gads_conversion_upload_batches` table with PK `id uuid DEFAULT gen_random_uuid()`, all columns from the spec
- [ ] 2.4 Add `gads_pipeline_state` singleton table with `id integer PRIMARY KEY CHECK (id = 1)` and the seed row `(1, false, ...)`
- [ ] 2.5 Add columns to `gads_conversion_uploads`: `error_code text`, `error_namespace text`, `error_detail jsonb`, `lifecycle text`, `last_attempt_at timestamptz`, `batch_id uuid REFERENCES gads_conversion_upload_batches(id) ON DELETE SET NULL`
- [ ] 2.6 Add CHECK constraint enforcing the `(lifecycle, status)` mapping from conversion-upload spec — must permit `lifecycle IS NULL` for legacy rows
- [ ] 2.7 Add index on `gads_conversion_uploads(lifecycle)` for the pickup query
- [ ] 2.8 Add index on `gads_conversion_uploads(error_code)` for the inbox grouping query
- [ ] 2.9 Add index on `gads_conversion_upload_batches(sent_at DESC)` for the batches panel pagination
- [ ] 2.10 Run migration locally; confirm all constraints accept valid inserts and reject invalid ones (test `gads_pipeline_state` rejects `id = 2`, test `disposition` CHECK rejects unknown values)

## 3. Schema migration — view and seed

- [ ] 3.1 Create migration file `supabase/migrations/<ts>_gads_dispositions_view.sql`
- [ ] 3.2 Add `vw_gads_conversion_uploads` view that left-joins `gads_conversion_uploads` to `gads_error_dispositions` on `error_code`, projecting all base columns plus computed `disposition`, `no_alert`, `human_action`
- [ ] 3.3 `GRANT SELECT` on the view to `authenticated` and `service_role`
- [ ] 3.4 Create migration file `supabase/migrations/<ts>_gads_dispositions_seed.sql` that reads from a SQL VALUES list derived from the catalog
- [ ] 3.5 Implement a one-shot Node script `horizon-dashboard/scripts/gen-dispositions-seed.mjs` that reads `gads_error_catalog.json` and emits the SQL VALUES list with default `disposition`, `no_alert`, and `human_action` per the rules in the `gads-error-dispositions` spec
- [ ] 3.6 Run the seed-gen script, paste its output into the seed migration, commit
- [ ] 3.7 Confirm the seed migration inserts one row per catalog entry with `source = 'proto-v23-seed'`
- [ ] 3.8 Manually verify the seed defaults for at least: `EXPIRED_EVENT` (drop, no_alert=true), `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS` (fix-config), `INVALID_HASHED_PHONE_NUMBER_FORMAT` (fix-data), `TOO_RECENT_EVENT` (retry, retry_after_seconds=21600), `CLICK_NOT_FOUND` (drop, no_alert=true), `TOO_MANY_CONVERSIONS_IN_REQUEST` (fix-config)

## 4. Schema migration — lifecycle backfill

- [ ] 4.1 Create migration file `supabase/migrations/<ts>_gads_lifecycle_backfill.sql`
- [ ] 4.2 UPDATE existing rows mapping `status` to `lifecycle` per the conversion-upload spec table (`pending`+attempts=0→`queued`, `pending`+attempts>0→`retrying`, `uploaded`→`sent`, `skipped`→`excluded`, `failed`→`failed`, `expired`→`expired`)
- [ ] 4.3 Verify no row has NULL `lifecycle` after backfill; verify every `(lifecycle, status)` pair satisfies the CHECK constraint

## 5. Edge function — pickup, pause check, batch tracking

- [ ] 5.1 In `supabase/functions/google-ads-conversion-upload/index.ts`, add the pause pre-flight check that reads `gads_pipeline_state.paused` first and returns early when true
- [ ] 5.2 Rewrite the pickup query to read from `gads_conversion_uploads` joined to `gads_error_dispositions`, selecting rows where `lifecycle = 'queued'` OR (`lifecycle = 'retrying'` AND retry timing OK)
- [ ] 5.3 Add helper to write a new `gads_conversion_upload_batches` row (`gen_random_uuid()` for the PK) at the start of an API call; capture the row's `id` for use as `batch_id` on the included rows
- [ ] 5.4 After successful API response, UPDATE the batch row with `job_id` (from response), `http_status`, `accepted_count`, `rejected_count`

## 6. Edge function — error parsing and disposition routing

- [ ] 6.1 Import `supabase/generated/gads_error_catalog.json` at the top of the edge function
- [ ] 6.2 Implement `parsePartialFailure(response)` that walks `partialFailureError.details[]`, extracts each `errorCode` discriminated-union, normalizes to `"<namespace>.<ENUM_NAME>"`, captures `location.fieldPathElements[0].index` to identify the row, and returns a per-row map of `{ error_code, error_namespace, error_detail }`
- [ ] 6.3 For each per-row error, look up the disposition (in-memory from a `Map` built from a single `SELECT * FROM gads_error_dispositions` at function start) and derive `lifecycle` per the spec mapping (`retry`→`retrying`, `fix-*`→`needs-attention`, `drop`→`failed`, `deliberate`→`excluded`)
- [ ] 6.4 Handle unknown `error_code` by defaulting to `lifecycle = 'needs-attention'` (the `fix-triage` default behavior)
- [ ] 6.5 Build the UPDATE that writes `error_code`, `error_namespace`, `error_detail`, `lifecycle`, `status` (per parallel-write mapping), `last_attempt_at = now()`, `batch_id`, increments `attempt_count` and `upload_attempts`
- [ ] 6.6 For successful rows in a partial-failure response, set `lifecycle = 'sent'`, `status = 'uploaded'`, `uploaded_at = now()`, clear `error_code`/`error_namespace`/`error_detail`
- [ ] 6.7 Manual test: send a synthetic partial-failure response through the parser locally; verify per-row routing for `retry`, `fix-config`, `drop` codes

## 7. Edge function — batch-level failures and pause trip

- [ ] 7.1 Detect batch-level failure: HTTP non-2xx OR `response.partialFailureError` with no per-row details AND a request-level error code
- [ ] 7.2 Write the batch row with `request_error_code`, `request_error_message`, `accepted_count = 0`, `rejected_count = 0`
- [ ] 7.3 For rows that were in the failed batch: increment `attempt_count`, set `last_attempt_at`, set `batch_id`, but leave `lifecycle = 'queued'` (do NOT mark needs-attention)
- [ ] 7.4 If the batch-level `error_code` has `disposition = 'fix-config'` in the disposition map, UPDATE `gads_pipeline_state` setting `paused = true`, `paused_reason`, `paused_error_code`, `paused_batch_id`, `paused_at`
- [ ] 7.5 Manual test: send a synthetic batch-level `fix-config` response; verify pause trips and constituent rows stay `queued`

## 8. FE — chip rendering (phase-cell-upload)

- [ ] 8.1 Update `horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx` signature to accept `(lifecycle, errorCode, disposition, noAlert, attemptCount, maxAttempts, uploadedAt)`
- [ ] 8.2 Implement the lifecycle→chip mapping from the phase-cell-upload spec (icons from `lucide-react`, colors from `tailwind.config.js`, sub-text per the table)
- [ ] 8.3 Implement the `no_alert = true` muted-render branch (gray icon/text overriding the lifecycle color)
- [ ] 8.4 Add hover tooltip rendering full `error_code` + `human_action` text on cells with `error_code` set
- [ ] 8.5 Update consumers of `getPhaseConfig` (search for callers, switch them to read `vw_gads_conversion_uploads` columns)
- [ ] 8.6 Update `vw_conversion_candidates` / pipeline view to expose the lifecycle/disposition/no_alert columns the FE needs (if not already covered by switching to `vw_gads_conversion_uploads`)
- [ ] 8.7 Update the hover-to-upload requirement: include `lifecycle` in `('queued', 'retrying', 'needs-attention')` as actionable
- [ ] 8.8 Manual test in browser: render rows for each lifecycle value, verify chip color/icon/sub-text matches spec

## 9. FE — Needs Attention inbox

- [ ] 9.1 Add route `/conversions/needs-attention` to the dashboard router
- [ ] 9.2 Create `horizon-dashboard/src/components/conversions/needs-attention/NeedsAttentionInbox.tsx`
- [ ] 9.3 Add TanStack hook `useNeedsAttentionGroups()` that queries `vw_gads_conversion_uploads` aggregated by `error_code`, `error_namespace`, `disposition`, `no_alert`, `human_action`, with 30s `staleTime`
- [ ] 9.4 Render the group cards in row-count-descending order, with disposition tag, human_action text, and row count
- [ ] 9.5 Implement "Show rows" drill-down listing constituent rows (estimate_id, conversion_type, last_attempt_at, attempt_count)
- [ ] 9.6 Implement group-level "Reset all N to queued" with confirm dialog and UPDATE that clears `error_code`/`error_namespace`/`error_detail`/`attempt_count` and sets `lifecycle = 'queued'`
- [ ] 9.7 Implement the "Muted (N groups)" accordion footer for `no_alert = true` groups
- [ ] 9.8 Implement the "Unknown codes" (NULL disposition) groups with "Configure disposition" action that navigates to `/conversions/dispositions?prefill=<error_code>`
- [ ] 9.9 Add the new tab to the Workbench header nav
- [ ] 9.10 Manual test: seed test rows with several `error_code` values, verify grouping, reset, and muted accordion behavior

## 10. FE — Batches panel

- [ ] 10.1 Add route `/conversions/batches` to the dashboard router
- [ ] 10.2 Create `horizon-dashboard/src/components/conversions/batches/BatchesPanel.tsx`
- [ ] 10.3 Add TanStack hook `useBatches({ page, pageSize: 50 })` querying `gads_conversion_upload_batches` ordered by `sent_at` descending
- [ ] 10.4 Render the table with columns: sent_at (NY tz), job_id (abbreviated), row_count, accepted_count, rejected_count, status indicator
- [ ] 10.5 Implement status indicator semantics: green check / amber dot / red triangle per the spec, with tooltip for `request_error_message` on failed batches
- [ ] 10.6 Implement batch drill-down (expanded row) querying `vw_gads_conversion_uploads WHERE batch_id = <id>`
- [ ] 10.7 Render "Paused pipeline" tag on the batch whose id equals `gads_pipeline_state.paused_batch_id`
- [ ] 10.8 Add the new tab to the Workbench header nav
- [ ] 10.9 Manual test: trigger a partial-failure batch and a batch-level failure; verify both render with correct status and drill-down

## 11. FE — Dispositions admin page

- [ ] 11.1 Add route `/conversions/dispositions` to the dashboard router
- [ ] 11.2 Create `horizon-dashboard/src/components/conversions/dispositions/DispositionsAdminPage.tsx`
- [ ] 11.3 Add TanStack hook `useDispositions()` and mutation `useUpdateDisposition()`
- [ ] 11.4 Render the editable table (Error Code, Namespace, Description tooltip, Disposition dropdown, Max attempts, Retry after, Mute checkbox, Human action input)
- [ ] 11.5 Implement filter bar: namespace dropdown, disposition dropdown, free-text search
- [ ] 11.6 On save, mutation sets `source = 'override'`, `updated_at = now()`, `updated_by = auth.uid()`
- [ ] 11.7 Implement "✎ Overridden" badge + row-level "Reset to seed default" action
- [ ] 11.8 Implement "Unknown codes" callout at top that lists `error_code`s appearing in `gads_conversion_uploads` but missing from `gads_error_dispositions`
- [ ] 11.9 Honor `?prefill=<error_code>` query param by scrolling to / opening the create form pre-filled
- [ ] 11.10 Add "Configure" link in the Workbench header (right-aligned, not a primary tab)
- [ ] 11.11 Manual test: edit a disposition, verify `source` updates; reset a row; create a disposition for an unknown code

## 12. FE — Pipeline pause banner

- [ ] 12.1 Add TanStack hook `usePipelineState()` polling `gads_pipeline_state` with 30s `staleTime` and `refetchOnWindowFocus: true`
- [ ] 12.2 Create `horizon-dashboard/src/components/conversions/PausedBanner.tsx`
- [ ] 12.3 Render banner only when `paused = true`; show paused_at (NY tz), paused_error_code, paused_reason
- [ ] 12.4 Implement "View batch" action → navigates to `/conversions/batches` scrolled to `paused_batch_id`
- [ ] 12.5 Implement "Resume uploads" action with confirm dialog → mutation that UPDATEs `paused = false`, `resumed_at = now()`, `resumed_by = auth.uid()`
- [ ] 12.6 Mount the banner inside the Workbench shell (above the tab nav, below the page header)
- [ ] 12.7 Manual test: trigger a `fix-config` batch-level failure, verify banner appears across all Conversions tabs; click Resume, verify next cron tick proceeds

## 13. End-to-end verification

- [ ] 13.1 With seeded test data covering every lifecycle value, render `/conversions` and verify each row's PUSH chip matches the spec
- [ ] 13.2 Seed rows that aggregate into at least 3 inbox groups (one fix-config, one fix-data, one muted drop); verify inbox grouping, reset, and muted accordion
- [ ] 13.3 Trigger a partial-failure batch and a batch-level fix-config failure; verify Batches panel and pause banner
- [ ] 13.4 Edit a disposition via the admin page; verify `source = 'override'`; re-run the seed migration; verify the override survives
- [ ] 13.5 Verify the legacy `status` column continues to match `lifecycle` per the parallel-write mapping for every row touched by the new edge function
- [ ] 13.6 Verify external consumers of `status` (the existing reconciliation view, any reports) still produce the same numbers as before for the time window covered by historical (NULL-lifecycle) rows
