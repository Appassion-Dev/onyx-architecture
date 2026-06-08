## Why

The conversion `dateTime` we send to Google Ads is rendered in UTC with a hardcoded `+00:00` offset ([`hashing.ts:1-8`](../../../supabase/functions/google-ads-conversion-upload/hashing.ts)). Google parses that offset to an absolute instant, so attribution and click↔conversion matching are already correct — but every timestamp we send (and persist in `gads_conversion_upload_batches.request_body`) reads several hours off from what the Google Ads UI shows, because the UI renders all times in the account's timezone. Google's own guidance is to send the account timezone "so that the conversion counts match." Aligning the sent timestamp to the account timezone makes our audit trail and any manual UI reconciliation read the same wall-clock as Google, with zero change to which instant or report day Google records.

This is a readability/reconciliation-parity change, **not** an attribution fix. The same motivation applies to the one other place the account timezone is hardcoded on the upload path — the `reporting_date` key in `vw_gads_upload_reconciliation_daily` — which we unify to a single configurable source in the same change.

## What Changes

- **Edge function — send conversion times in the account timezone.** `formatConversionDateTime` gains a `timeZone` parameter and renders the same instant in that zone, DST-aware (e.g. `2026-05-15 12:00:00+00:00` → `2026-05-15 08:00:00-04:00` in summer, `-05:00` in winter). The transform MUST be instant-preserving (re-project via `Intl.DateTimeFormat`, never re-label the offset on the same wall-clock numbers).
- **New config — `GOOGLE_ADS_ACCOUNT_TIMEZONE`.** An IANA timezone env var (Supabase function secret), defaulting to `America/New_York`, threaded into the payload builder at [`payload-builder.ts:59`](../../../supabase/functions/google-ads-conversion-upload/payload-builder.ts).
- **SQL — single source for the reporting timezone.** Introduce a `gads_account_timezone()` SQL function (default `America/New_York`) and replace the hardcoded `timezone('America/New_York', uploaded_at)` literal in `vw_gads_upload_reconciliation_daily` so the SQL plane reads one source instead of a scattered literal.
- **Tests.** Update the two pinned assertions in [`hashing.test.ts:78-84`](../../../supabase/functions/google-ads-conversion-upload/hashing.test.ts) and add summer/winter (DST) and same-instant-equivalence cases.
- **Non-goal (documented):** the browser-side display timezone (`src/lib/uploadReport.ts` `getWeekInfo`, `phase-cell-upload`) is out of scope — it is a separate runtime that cannot read the edge env var, it is display-only and not on the upload path, and the default keeps it consistent with the rest of the system. See design.md for the cross-runtime rationale.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `conversion-upload`: the conversion `dateTime` sent to Google Ads SHALL be formatted in the configured account timezone (instant-preserving, DST-aware) sourced from `GOOGLE_ADS_ACCOUNT_TIMEZONE`, rather than always UTC.
- `upload-reconciliation-reporting`: the daily reconciliation day key SHALL be computed in the configured account timezone via `gads_account_timezone()` rather than a hardcoded `America/New_York` literal; the default keeps current output byte-identical.

## Impact

- **Code:** `hashing.ts` (signature + impl of `formatConversionDateTime`), `payload-builder.ts` (pass the configured zone), `hashing.test.ts` (revised + new DST cases).
- **Config:** new Supabase function secret `GOOGLE_ADS_ACCOUNT_TIMEZONE` (default `America/New_York`); no value change required for the current single-account deployment.
- **Database:** new `gads_account_timezone()` function; one new migration recreating the live `vw_gads_upload_reconciliation_daily` (and any sibling views recreated alongside it) to call that function. ⚠️ The view is recreated across ~9 migrations — verify the **live** definition with `pg_get_functiondef` before authoring the migration; do not trust the migration files alone.
- **Audit trail:** newly persisted `gads_conversion_upload_batches.request_body` rows will show local-offset datetimes; pre-existing rows remain in `+00:00`. No backfill.
- **Behavior:** no change to Google attribution, conversion counts, or report-day bucketing (Google normalizes to the same instant and renders in the account timezone regardless). With the default timezone, the SQL reconciliation output is unchanged.
- **Out of scope:** frontend/display timezone literals (separate browser runtime) — flagged as a follow-up.
