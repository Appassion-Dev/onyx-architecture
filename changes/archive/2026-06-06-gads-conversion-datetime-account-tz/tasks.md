## 1. Edge function: account-timezone formatter

- [x] 1.1 Change `formatConversionDateTime(iso)` in `hashing.ts` to `formatConversionDateTime(iso, timeZone)`, re-projecting the instant via `Intl.DateTimeFormat("en-CA", { timeZone, year/month/day/hour/minute/second: "2-digit", hour12: false, timeZoneName: "longOffset" })` and assembling `YYYY-MM-DD HH:MM:SS±HH:MM`
- [x] 1.2 Strip the `GMT` prefix from the `longOffset` part (`GMT-04:00` → `-04:00`); handle a `GMT`/`+00:00` (UTC) result
- [x] 1.3 Normalize the midnight `hour: "2-digit"` quirk (`24` → `00`) — handled at the source via `hourCycle: "h23"` (avoids the h24 day-rollover bug)
- [x] 1.4 Read `GOOGLE_ADS_ACCOUNT_TIMEZONE` (default `America/New_York`) in the upload handler and thread it into `buildPayloads`
- [x] 1.5 Pass the timezone through to the `formatConversionDateTime` call at `payload-builder.ts:59`

## 2. Edge function: tests

- [x] 2.1 Update the two pinned assertions in `hashing.test.ts:78-84` to the account-timezone output
- [x] 2.2 Add a summer/EDT case (`2026-05-15T12:00:00Z` → `2026-05-15 08:00:00-04:00`)
- [x] 2.3 Add a winter/EST case (`2026-01-02T03:04:05Z` → `2026-01-01 22:04:05-05:00`)
- [x] 2.4 Add a same-instant-equivalence assertion (parsed emitted string equals the stored instant)
- [x] 2.5 Add a configurable-timezone case (`UTC` → `+00:00`) and a midnight case (`00:00:00`, not `24`)
- [x] 2.6 Update `payload-builder.test.ts` expectations if any assert the `conversionDateTime` value — none assert it; made `buildPayloads` `timeZone` a **required** param (no hardcoded default) and passed it explicitly at all 7 call sites so the only `America/New_York` literals left are the `index.ts` env fallback and the SQL `gads_account_timezone()` default
- [x] 2.7 Run the function's Deno test suite and confirm green — 93 passed, 0 failed

## 3. SQL: single source for the reporting timezone

- [x] 3.1 Inspect the **live** `vw_gads_upload_reconciliation_daily` definition via `pg_get_functiondef`/deployed view (do not trust migration files) and confirm the current `timezone('America/New_York', u.uploaded_at)` expression — confirmed; live def drifted to a channel-based source-bucket classification, used as the migration base
- [x] 3.2 Author one migration: `CREATE FUNCTION public.gads_account_timezone() RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT 'America/New_York' $$;` with grants matching the view's roles
- [x] 3.3 In the same migration, recreate the live view changing only the timezone token to `timezone(public.gads_account_timezone(), u.uploaded_at)`
- [x] 3.4 Verify `reporting_date` output is identical to the pre-change view for a sample of rows (default timezone) — read-only parity check over 3031 uploaded rows: 0 mismatches

## 4. Config & rollout

- [x] 4.1 Document `GOOGLE_ADS_ACCOUNT_TIMEZONE` alongside the other `GOOGLE_ADS_*` secrets (supabase/README.md §8.3); note that the env var and the SQL `gads_account_timezone()` default must agree
- [ ] 4.2 Deploy the edge function (var unset → `America/New_York`; optionally set to `UTC` first to validate parity with current behavior) — **DEPLOY: requires user action** (also: apply migration `20260606000001` to the remote DB)
- [ ] 4.3 Confirm a real (or `_mock_response`) upload writes the expected local-offset `conversionDateTime` into `gads_conversion_upload_batches.request_body` — **VERIFY: requires deploy first**
- [x] 4.4 Note in the change that pre-existing `request_body` rows remain `+00:00` (no backfill) and that the browser/display timezone is a separate follow-up — covered in proposal.md Impact + design.md Non-Goals
