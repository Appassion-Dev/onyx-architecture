## 1. Schema Migration — Audit Table & Config Table

- [x] 1.1 Add `conversion_type text NOT NULL DEFAULT 'booking_lead'` column to `gads_conversion_uploads` with CHECK constraint (`'booking_lead'`, `'qualified_lead'`, `'converted_lead'`)
- [x] 1.2 Drop existing `UNIQUE(estimate_id)` constraint using idempotent DO block and create new `UNIQUE(estimate_id, conversion_type)` constraint
- [x] 1.3 Add `conversion_currency text DEFAULT 'USD'` column to `gads_conversion_uploads`
- [x] 1.4 Add `job_id text` nullable column to `gads_conversion_uploads` for converted lead job reference
- [x] 1.5 Verify `conversion_value` is already nullable (it is per existing schema — no ALTER needed; just confirm)
- [x] 1.6 Make `conversion_action` column nullable — it is NULL at discovery time and filled by the upload edge function after resolving the action ID from config (historical record of what was actually uploaded)
- [x] 1.7 Add `error_message text` nullable column to `gads_conversion_uploads` for capturing upload failure reasons
- [x] 1.8 Add `upload_attempts integer NOT NULL DEFAULT 0` column to `gads_conversion_uploads` — incremented on each upload attempt (success or failure)
- [x] 1.9 Update status CHECK constraint to allow: `'pending'`, `'uploaded'`, `'skipped'` (no `'failed'` status — failed rows stay `'pending'` with `error_message` set and `upload_attempts` incremented)
- [x] 1.10 Create `gads_conversion_config` table with columns: `conversion_type text PRIMARY KEY`, `conversion_action_id text` (nullable — NULL until configured via dashboard), `conversion_action_name text`, `enabled boolean NOT NULL DEFAULT false`, `dry_run boolean NOT NULL DEFAULT false`, `updated_at timestamptz DEFAULT now()`
- [x] 1.11 Grant appropriate permissions: `SELECT` for `authenticated`, `SELECT/INSERT/UPDATE` for `service_role` on both tables
- [x] 1.12 Seed `gads_conversion_config` with three rows for `booking_lead`, `qualified_lead`, `converted_lead` (`conversion_action_id = NULL`, `enabled = false`, `dry_run = false` — operator enables each type and sets action IDs through the dashboard)

## 2. SQL Functions — Estimate-Centric Pending Conversion Queries

- [x] 2.1 Create `get_pending_booking_lead_conversions()` — scans estimates with `is_booking_form = true` that have a GCLID (via `booking_tags` key-value lookup: `key = 'gclid'`, value in `value` column; or correlated `callrail_leads.gclid`), returns `estimate_id` (always HCP ID), resolved GCLID, `conversion_value = NULL`, `created_at` as datetime. Estimates without `is_booking_form = true` are excluded even if they have a GCLID. Also includes booking-form estimates without GCLID but with customer email/mobile_number (enhanced-conversion-only — requires JOIN to `customers` in WHERE clause only, not in SELECT).
- [x] 2.2 Create `get_pending_qualified_lead_conversions()` — scans estimates with `work_status IN ('complete rated', 'complete unrated')` (varchar comparison, not enum) + GCLID, returns estimate_id, resolved GCLID, `updated_at` as datetime, `estimate_options.total_amount / 100.0` as value (cents to dollars)
- [x] 2.3 Create `get_pending_converted_lead_conversions()` — scans jobs with `work_status IN ('complete rated', 'complete unrated')` where linked estimate has GCLID, returns `original_estimate_id` as estimate_id, `jobs.id` as job_id, resolved GCLID, `jobs.updated_at` as datetime, `jobs.total_amount / 100.0` as value (cents to dollars)
- [x] 2.4 All three functions return uniform columns: `estimate_id`, `conversion_type`, `gclid`, `conversion_datetime`, `conversion_value`, `job_id` (NULL for non-job types). No contact data columns — contact data is fetched at upload time.
- [x] 2.5 GCLID resolution in all functions uses scalar subquery for booking_tags (key-value table): `COALESCE((SELECT bt.value FROM booking_tags bt WHERE bt.estimate_id = e.id AND bt.key = 'gclid'), cl.gclid)` — booking form preferred when both exist
- [x] 2.6 Drop existing `get_pending_gclid_conversions()` function (replaced by the three dedicated functions above)

## 3. Discovery SQL Wrapper Function

- [x] 3.1 Create `discover_pending_conversions()` SQL function that reads `enabled` flag from `gads_conversion_config` and calls only the enabled pending conversion query functions
- [x] 3.2 For each returned row, INSERT into `gads_conversion_uploads` with `status = 'pending'`, `conversion_action = NULL`, `upload_attempts = 0`, `error_message = NULL`, and `job_id` for converted leads
- [x] 3.3 Use `INSERT ... ON CONFLICT (estimate_id, conversion_type) DO NOTHING` for idempotency
- [x] 3.4 No conversion_action_id lookup at discovery time — only the `enabled` boolean is read from config
- [x] 3.5 Return summary row counts: `booking_leads`, `qualified_leads`, `converted_leads`

## 4. Upload Edge Function — Refactor Existing

- [x] 4.1 Refactor `google-ads-conversion-upload` to read only `status = 'pending'` rows from `gads_conversion_uploads` (instead of calling `get_pending_gclid_conversions()`)
- [x] 4.2 For each pending row, look up `gads_conversion_config` by `conversion_type` — skip rows where `enabled = false` or `dry_run = true` (leave as pending, do not attempt)
- [x] 4.3 For enabled non-dry-run rows, resolve `conversion_action_id` from config and build the full resource name (`customers/{customerId}/conversionActions/{actionId}`). If `conversion_action_id` is NULL, increment `upload_attempts`, set `error_message` to indicate missing config, leave as pending.
- [x] 4.4 Fetch customer `email` and `mobile_number` for enhanced conversions by joining on `estimates.customer_id` → `customers`. Include as `userIdentifiers` when available (bonus, not required — GCLID alone is sufficient for upload).
- [x] 4.5 Keep existing hashing logic (`hashEmail`, `hashPhone`, `sha256hex`, `formatConversionDateTime`)
- [x] 4.6 On each upload attempt per row, increment `upload_attempts`. On success: set status to `'uploaded'`, clear `error_message`, write resolved `conversion_action` to row. On partial failure: leave status as `'pending'`, set `error_message` to API error, write resolved `conversion_action` to row.
- [x] 4.7 Update upsert calls to use `onConflict: "estimate_id,conversion_type"`
- [x] 4.8 On complete API failure (non-200), leave all rows as `'pending'`, increment `upload_attempts` for each, set `error_message`; log the error; next cron run will reattempt
- [x] 4.9 Update response to include per-type counts: `{ uploaded: N, skipped: N, errored: N }`

## 5. Update Existing Manual Upload Function

- [x] 5.1 Update `gads-upload-booking` to include `conversion_type: 'booking_lead'` in its audit row upsert and use new composite conflict key
- [x] 5.2 Update `gads-upload-booking` to read its conversion action ID from `gads_conversion_config` instead of the env var
- [x] 5.3 Delete `gads-upload-call` edge function directory and remove any `config.toml` entry (it stored `callrail_id` in `estimate_id`, violating the estimate-centric model; uncorrelated CallRail leads are handled by the correlation resync cron)

## 6. Config Edge Function & Dashboard

- [x] 6.1 Create `gads-conversion-config` edge function — GET returns all config rows, PUT upserts a single row (JWT-authenticated)
- [x] 6.2 Add `[functions.gads-conversion-config]` entry to `config.toml` with `verify_jwt = false` (JWT validated manually)
- [x] 6.3 Create dashboard page/component for viewing and editing conversion action ID mappings, enabled toggles, and dry_run toggles per type

## 7. Conversions Dashboard Page

- [x] 7.1 Create SQL view `vw_gads_conversions` joining `gads_conversion_uploads` with estimates, customers, jobs, booking_tags, and callrail_leads for denormalized dashboard query; include `gclid_source` indicator ('booking'/'call'/'both'), `booking_gclid`, `call_gclid`, `upload_attempts`, and `error_message` columns
- [x] 7.2 Create `ConversionsPage` dashboard component with date-grouped layout (reverse chronological)
- [x] 7.3 Display per-row details: conversion type badge, status indicator (color-coded: green=uploaded, amber=pending, red=pending+error, grey=skipped), GCLID + source indicator, value/currency (or "—" for booking leads), estimate number, customer name, upload timestamp, upload attempts count, error message (for retrying rows)
- [x] 7.4 Implement cross-phase lead correlation grouping: visually link rows sharing the same `estimate_id` to show booking → qualified → converted progression
- [x] 7.5 Display GCLID source attribution: show 'Booking'/'Call'/'Both' badge; when both, expose secondary GCLID on expansion/tooltip
- [x] 7.6 Add type filter (booking lead / qualified lead / converted lead) and status filter (pending / uploaded / skipped / errored) where "errored" = pending with upload_attempts > 0
- [x] 7.7 Show date section headers with summary counts and status breakdown
- [x] 7.8 Add route and navigation link for the conversions page

## 8. Cron Scheduling — Three Independent Jobs

- [x] 8.1 Enable `pg_cron` and `pg_net` extensions via migration
- [x] 8.2 Create `pg_cron` job #1: CallRail correlation resync — periodically call `resync_callrail_estimates(false)` as a direct SQL statement
- [x] 8.3 Create `pg_cron` job #2: Conversion discovery — periodically call `SELECT discover_pending_conversions()` as a direct SQL statement (no HTTP, no edge function)
- [x] 8.4 Create `pg_cron` job #3: Conversion upload — periodically invoke `google-ads-conversion-upload` edge function via `pg_net` HTTP call
- [x] 8.5 All three jobs are independent — no chaining, no ordering dependencies. Each runs on its own schedule.
- [x] 8.6 Store Supabase URL and service role key in `config.toml` `[db.settings]` as custom GUCs for `pg_net` to use (needed only for job #3)

## 9. Verification

- [x] 9.1 Test booking lead discovery: create estimate with `is_booking_form = true` and GCLID (via booking_tags `key='gclid'`) → run `discover_pending_conversions()` → verify pending row with `conversion_value = NULL`, `conversion_action = NULL`, `upload_attempts = 0`, and HCP estimate_id
- [x] 9.2 Test booking lead from CallRail: create estimate with `is_booking_form = true`, correlate CallRail lead with GCLID → verify pending row uses HCP estimate_id and CallRail GCLID
- [x] 9.3 Test non-booking-form estimate excluded: create estimate with `is_booking_form = false` and a GCLID via callrail_leads → verify booking lead function does NOT return it
- [x] 9.4 Test GCLID priority: create estimate with GCLID in both booking_tags and callrail_leads → verify booking_tags GCLID is used
- [x] 9.5 Test qualified lead discovery: update estimate to `'complete rated'` → run discovery → verify pending row with correct datetime and value in dollars (cents ÷ 100)
- [x] 9.6 Test converted lead discovery: complete a job linked to GCLID estimate → run discovery → verify pending row with job amount in dollars and job_id set
- [x] 9.7 Test idempotency: run `discover_pending_conversions()` twice → verify no duplicate rows
- [x] 9.8 Test upload function resolves conversion_action from config and writes it to the row after upload; verify `upload_attempts` incremented
- [x] 9.9 Test upload function fetches customer email and mobile_number as bonus enhanced conversion data; verify GCLID-only upload works without contact data
- [x] 9.10 Test missing config action ID: set `conversion_action_id = NULL` for a type → verify upload leaves row pending with error_message and incremented upload_attempts
- [x] 9.11 Test disabled type: set `enabled = false` for booking_lead → verify discovery creates no booking_lead rows, upload skips existing pending booking_lead rows
- [x] 9.12 Test dry_run mode: set `dry_run = true` for qualified_lead → verify discovery creates pending rows but upload leaves them pending (no API call)
- [x] 9.13 Test upload retry: simulate API partial failure → verify row stays pending with error_message set and upload_attempts incremented → re-run upload with success → verify row becomes uploaded, error_message cleared, upload_attempts incremented again
- [x] 9.14 Test manual `gads-upload-booking` function still works with new schema
- [x] 9.15 Test cross-phase correlation: verify same estimate_id links booking, qualified, and converted rows
- [x] 9.16 Test stage independence: create an estimate that goes directly to qualified lead (skipping booking lead) → verify qualified lead row is created without requiring booking lead row
- [x] 9.17 Test CallRail correlation resync cron: create uncorrelated CallRail lead, then create matching customer/estimate → run resync → verify estimate_id populated and lead enters pipeline on next discovery
- [x] 9.18 Test three independent cron jobs: verify each job runs independently on its own schedule
- [x] 9.19 Test conversions dashboard: verify date grouping, filters (including errored filter), gclid_source display, upload_attempts/error_message display, and lead correlation
