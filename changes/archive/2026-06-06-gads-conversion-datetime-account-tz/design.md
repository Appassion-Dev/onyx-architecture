## Context

`formatConversionDateTime(iso)` ([`hashing.ts:1-8`](../../../supabase/functions/google-ads-conversion-upload/hashing.ts)) renders a stored UTC `timestamptz` instant as `YYYY-MM-DD HH:MM:SS+00:00` using `getUTC*` accessors and a literal `+00:00`. It is called once, at [`payload-builder.ts:59`](../../../supabase/functions/google-ads-conversion-upload/payload-builder.ts), and pinned by two assertions in [`hashing.test.ts:78-84`](../../../supabase/functions/google-ads-conversion-upload/hashing.test.ts).

Google Ads accepts `yyyy-mm-dd HH:mm:ss+|-HH:mm` and uses the offset only to compute the absolute instant; the offset does **not** have to match the account timezone. Per Google's docs, matching the account timezone matters only so "the conversion counts match" when comparing against the Google Ads UI. So this change alters how an already-correct instant is *rendered*, not which moment is recorded.

The account timezone is currently a hardcoded `America/New_York` literal in two planes on the upload path: the edge function (implicitly, via UTC) and the SQL reconciliation view (`vw_gads_upload_reconciliation_daily.reporting_date`). A third plane — the browser (`src/lib/uploadReport.ts`) — also hardcodes it but is display-only and off the upload path.

## Goals / Non-Goals

**Goals:**
- Render the conversion `dateTime` sent to Google in a configurable account timezone, instant-preserving and DST-aware.
- Source that timezone from one place per runtime, defaulting to `America/New_York` so current behavior is unchanged.
- Replace the hardcoded `America/New_York` literal in the SQL reconciliation view with a single `gads_account_timezone()` source.

**Non-Goals:**
- Changing Google attribution, conversion counts, or report-day bucketing (impossible via the offset; Google normalizes to the instant and renders in the account timezone).
- Per-end-customer timezones (no data source exists; Google's UI-match benefit is about the *account* zone, not the contact's).
- The browser/display timezone in `src/lib/uploadReport.ts` and `phase-cell-upload` — separate runtime, deferred to a follow-up.
- Backfilling existing `request_body` rows (they remain `+00:00`).

## Decisions

### 1. Instant-preserving, DST-aware rendering via `Intl.DateTimeFormat`

The transform must re-project the instant into the target zone, never re-label the offset on the same wall-clock numbers.

```
WRONG: "12:00:00" + swap +00:00 → -04:00  ⇒ 12:00:00-04:00  (shifted 4h, corrupt)
RIGHT: re-project instant to zone          ⇒ 08:00:00-04:00  (same moment)
```

Use `Intl.DateTimeFormat("en-CA", { timeZone, year/month/day/hour/minute/second: 2-digit, hour12:false, timeZoneName:"longOffset" })` and assemble the parts into `YYYY-MM-DD HH:MM:SS±HH:MM`. `en-CA` yields ISO-ordered date parts; `longOffset` yields `GMT-04:00` / `GMT-05:00`, from which we strip the `GMT` prefix to get the `±HH:MM` Google expects. This is DST-correct automatically because `Intl` resolves the offset for the specific instant. Deno's runtime ships full ICU, so IANA zones and `longOffset` are available.

- **Alternative — fixed offset constant (`-05:00`):** rejected; wrong for half the year (EDT vs EST).
- **Alternative — a date library (Luxon/date-fns-tz):** rejected; `Intl` covers this with no new dependency in an edge function.
- **Edge cases to pin in tests:** `hour: "2-digit"` can emit `24` for midnight in some ICU versions → normalize to `00`; and verify a UTC instant near a US DST boundary lands on the correct offset.

### 2. Config source: env var for the edge function, SQL function for the view (one value, two readers)

A Supabase edge-function env var is invisible to Postgres, and both are invisible to the browser bundle. "One env var everywhere" is therefore not literally achievable across runtimes. We give each plane on the upload path a single source defaulting to the same value:

| Plane | Source | Default |
|---|---|---|
| Edge function (what we send) | `GOOGLE_ADS_ACCOUNT_TIMEZONE` env (Supabase secret) | `America/New_York` |
| Postgres (reconciliation view) | `gads_account_timezone()` SQL function | `America/New_York` |
| Browser (display) | unchanged — **out of scope** | `America/New_York` |

- **Alternative — DB config row as the single cross-runtime source** (edge function queries it, SQL reads it via the function, browser fetches it): this is the only design that yields *one* authoritative value. Rejected for this change because the user asked for an env var and the default keeps all planes aligned anyway; noted as the path to adopt if the account timezone ever needs to differ from `America/New_York` or vary per deployment. If chosen later, `GOOGLE_ADS_ACCOUNT_TIMEZONE` becomes a fallback only.
- The edge function already reads several `GOOGLE_ADS_*` env vars in `_shared/google-ads-auth.ts`; the new var fits that pattern. It is read in the upload handler (not inside `getAdsConfig`, which is auth-only) and threaded to `buildPayloads`.

### 3. Default to `America/New_York`, validate, fall back

`GOOGLE_ADS_ACCOUNT_TIMEZONE` defaults to `America/New_York` when unset. If set to a value `Intl` rejects, the formatter throws on first use — preferable to silently emitting a wrong offset. Tests cover the unset (default) path; the proposal does not require runtime validation beyond letting an invalid zone fail loudly.

### 4. SQL: `gads_account_timezone()` + one migration recreating the live view

Add `CREATE FUNCTION public.gads_account_timezone() RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT 'America/New_York' $$;` and replace `timezone('America/New_York', u.uploaded_at)` with `timezone(public.gads_account_timezone(), u.uploaded_at)` in `vw_gads_upload_reconciliation_daily`. Because the view is recreated across ~9 migrations, the migration must reproduce the **live** definition (verified via `pg_get_functiondef` / inspecting the deployed view), changing only the timezone expression — not an older copy from the migration files.

## Risks / Trade-offs

- **Re-labeling instead of re-projecting corrupts the instant (4–5h shift) → `EXPIRED_EVENT` / `CONVERSION_PRECEDES_GCLID` rejections.** → The instant-preserving `Intl` approach is the core requirement; pin same-instant-equivalence and DST cases in tests so a future refactor can't regress to string surgery.
- **`Intl` midnight `hour: "2-digit"` → `24` quirk.** → Normalize `24` to `00` and add a midnight test.
- **Mixed offsets in the audit trail** (old rows `+00:00`, new rows `-04:00`/`-05:00`). → Documented; same instant, no backfill. Anyone reading `request_body` history should expect the representation change at the cutover.
- **Live view definition drift** when authoring the migration. → Inspect the deployed view first; change only the timezone token.
- **Two config points can diverge** (env var vs SQL function default). → Both default to `America/New_York`; for the single-account deployment they need not be touched. Divergence only becomes possible if someone sets one without the other — called out in tasks.
- **Low payoff, real surface area.** → Cosmetic/reconciliation benefit only. Default-unchanged behavior and tight scope (no frontend) keep the risk proportionate.

## Migration Plan

1. Ship the edge-function change with `GOOGLE_ADS_ACCOUNT_TIMEZONE` unset → behaves as `America/New_York`. (To keep `+00:00` during validation, the var could temporarily be set to `UTC`.)
2. Apply the SQL migration (`gads_account_timezone()` + view) — output identical at the default.
3. Rollback: revert the edge function (restore the UTC formatter) and drop/restore the view migration. No data migration to undo; stored instants are unchanged.
