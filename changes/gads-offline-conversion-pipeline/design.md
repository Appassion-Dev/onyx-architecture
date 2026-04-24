## Context

The ONYX system currently uploads one type of Google Ads offline conversion — "booking lead" — via a batch edge function (`google-ads-conversion-upload`) that polls a SQL function (`get_pending_gclid_conversions()`). The audit table `gads_conversion_uploads` tracks uploads with a `UNIQUE(estimate_id)` constraint, allowing only one conversion per entity.

The system needs to report three funnel stages back to Google Ads, all anchored to the HCP estimate as the unit of work:
1. **Booking lead** — the estimate was created (booking made)
2. **Qualified lead** — the estimate was approved (work_status → complete)
3. **Converted lead** — the associated job was finished

Each stage uses a different Google Ads conversion action ID. GCLID is resolved per estimate from `booking_tags` (key-value table, `key = 'gclid'`) and `callrail_leads.gclid`, preferring the booking form value — the same GCLID is used for all three stages of that estimate.

Key existing components:
- `gads_conversion_uploads` table — audit log, `UNIQUE(estimate_id)`
- `get_pending_gclid_conversions()` — SQL function returning pending bookings + CallRail leads
- `google-ads-conversion-upload` edge function — batch upload with enhanced conversions
- `gads-upload-booking` — manual single-record upload function for booking estimates
- `booking_tags` table — stores GCLID captured at booking time
- `callrail_leads` table — stores GCLID from CallRail webhooks, correlated to estimates via trigger
- `estimates.is_booking_form` flag — marks booking-sourced estimates
- `estimates.work_status` — varchar(50) column (note: NOT the `work_status` enum used by `jobs`); string values like `'complete rated'`, `'complete unrated'` etc.
- `jobs.original_estimate_id` — links jobs to their parent estimate
- `correlate_callrail_estimate()` trigger + `resync_callrail_estimates()` — matches CallRail leads to HCP estimates

## Goals / Non-Goals

**Goals:**
- Report three estimate lifecycle stages to Google Ads: booking lead, qualified lead, converted lead
- Anchor the entire pipeline on the HCP estimate — `estimate_id` is always the real HCP ID in the audit table
- Resolve GCLID per estimate via `COALESCE(booking_tags.gclid, callrail_leads.gclid)`
- Separate data discovery (pure SQL, called by `pg_cron`) from API interaction (edge function, called via `pg_net`)
- Use per-type conversion action IDs stored in a dashboard-configurable table, resolved at upload time
- Run via cron — no database triggers; three independent `pg_cron` jobs
- No conversion value for booking leads; estimate total (cents ÷ 100) for qualified leads; job total (cents ÷ 100) for converted leads
- Schedule periodic CallRail correlation resync so late-matched calls enter the pipeline
- Maintain backward compatibility with the existing `gads-upload-booking` manual upload function
- Remove `gads-upload-call` — it stored `callrail_id` in the `estimate_id` column, violating the estimate-centric constraint; uncorrelated CallRail leads are handled by the correlation resync cron instead

**Non-Goals:**
- Real-time conversion uploads (cron polling is sufficient; Google processes offline conversions in daily batches)
- Uploading conversions for non-GCLID records in the qualified/converted stages (enhanced-conversion-only is kept for booking leads only)
- Building a retry queue — rows that fail to upload stay in `'pending'` status with the error captured in `error_message` and `upload_attempts` incremented; the next cron run re-attempts them automatically
- Replacing the manual `gads-upload-booking` dashboard function (it continues to work alongside the batch system)

## Decisions

### 1. Three separate SQL functions vs. one with a type parameter

**Decision**: Three dedicated SQL functions — `get_pending_booking_lead_conversions()`, `get_pending_qualified_lead_conversions()`, `get_pending_converted_lead_conversions()`. All three scan from the `estimates` table (with a join to `jobs` for converted leads).

**Rationale**: Each function has distinct WHERE conditions and value sources, but all share the same anchor: the HCP estimate. A single parameterized function would require complex branching. Separate functions are independently testable and their query plans are optimized by Postgres without needing runtime branching.

**Alternative considered**: One function with a `conversion_type` parameter and internal `IF/CASE` logic. Rejected because it conflates unrelated queries and makes the SQL harder to read and optimize.

### 2. Two-phase cron: discover (SQL) then upload (edge function)

**Decision**: Phase 1 is pure SQL — a wrapper function `discover_pending_conversions()` calls the three discovery sub-functions and INSERTs pending rows into `gads_conversion_uploads`. It is called directly by `pg_cron` (no edge function, no HTTP). Phase 2 is the only edge function — it reads pending rows, resolves conversion action IDs from `gads_conversion_config`, fetches customer contact data for enhanced conversions, and uploads to the Google Ads API.

**Rationale**: Discovery is pure data work — scanning tables and writing rows. It doesn't need HTTP, OAuth, cold starts, or auth tokens. `pg_cron` can call a SQL function directly: `SELECT discover_pending_conversions()`. The edge function is reserved for the only thing that genuinely needs it: calling the external Google Ads API with OAuth credentials and hashing logic.

**Alternative considered**: A populate edge function that calls the SQL functions and writes rows. Rejected because it adds unnecessary HTTP overhead, requires auth token management for a purely internal operation, and creates a pg_cron chaining problem (can't easily call two edge functions sequentially).

### 3. Conversion action IDs from config table, not env vars

**Decision**: Store the mapping of `conversion_type → conversion_action_id` in a new `gads_conversion_config` table, manageable via a dashboard page. The edge function reads this table at runtime.

**Rationale**: Three separate env vars (`GOOGLE_ADS_BOOKING_LEAD_ACTION_ID`, `GOOGLE_ADS_QUALIFIED_LEAD_ACTION_ID`, `GOOGLE_ADS_CONVERTED_LEAD_ACTION_ID`) require redeployment to change. A config table lets the business owner update action IDs without developer intervention. It also naturally extends if more conversion types are added later.

**Alternative considered**: Keep env vars. Simpler for initial setup, but doesn't scale and requires CLI access to update.

### 4. Extend existing audit table vs. new table

**Decision**: Add `conversion_type` column to existing `gads_conversion_uploads` and change the UNIQUE constraint to `(estimate_id, conversion_type)`.

**Rationale**: The audit data shape is identical across conversion types (estimate_id, gclid, conversion_action, datetime, value, status). A single table with a type discriminator is simpler than three tables with the same schema.

### 5. Cron scheduling: three independent `pg_cron` jobs

**Decision**: Three independent `pg_cron` jobs:
1. **CallRail resync** — direct SQL: `SELECT resync_callrail_estimates(false)` (e.g., every 30 minutes)
2. **Conversion discovery** — direct SQL: `SELECT discover_pending_conversions()` (e.g., every 15 minutes)
3. **Conversion upload** — via `pg_net`: HTTP POST to the upload edge function (e.g., every 15 minutes, offset by ~5 min from discovery)

Jobs 2 and 3 are independent — upload processes whatever is pending, regardless of when discovery last ran. If discovery hasn't produced new rows, upload finds nothing and returns immediately.

**Rationale**: No chaining dependency between jobs. `pg_cron` can call SQL functions directly (no `pg_net` needed for jobs 1 and 2). Only the upload job needs `pg_net` because it calls an edge function. The offset between discovery and upload is a convenience, not a requirement.

### 6. GCLID resolution for jobs

**Decision**: For qualified leads, GCLID is resolved directly from the estimate (via `booking_tags` or `callrail_leads`). For converted leads, GCLID is resolved via `jobs.original_estimate_id → estimate → booking_tags/callrail_leads`.

**Rationale**: Jobs don't store GCLIDs directly. The `original_estimate_id` FK (already indexed) provides the link. The SQL function handles this join.

### 7. Estimate-centric pipeline — estimate_id is always the HCP ID

**Decision**: The pipeline is anchored entirely on HCP estimates. The `estimate_id` column in `gads_conversion_uploads` always holds the real HCP estimate ID — never a CallRail ID or synthetic prefix. All three SQL functions scan from the `estimates` table, filtered by the presence of a GCLID (via `booking_tags` or a correlated `callrail_leads` row). CallRail leads only enter the pipeline after the `correlate_callrail_estimate()` trigger (or `resync_callrail_estimates()` cron) has set their `estimate_id`. Uncorrelated CallRail leads are not part of this pipeline.

A `job_id` column (nullable) on `gads_conversion_uploads` stores the HCP job ID for converted lead rows, preserving the specific job reference.

**Rationale**: Using the real estimate_id consistently means a simple `WHERE estimate_id = 'est_123'` retrieves all funnel stages for a lead. No mixed ID types, no bridging joins through `callrail_leads`. The three lifecycle stages (booking → qualified → converted) map naturally to the estimate's progression. Uncorrelated CallRail leads are handled by the correlation resync cron; once correlated, they enter the pipeline on the next populate run.

**Alternative considered**: Using `callrail_id` as a stand-in for uncorrelated booking leads (previous spec). Rejected because it pollutes `estimate_id` with mixed ID types and makes cross-phase correlation require type-aware joins. The `gads-upload-call` manual function is removed for the same reason.

### 8. CallRail correlation resync via cron

**Decision**: A `pg_cron` job periodically calls `resync_callrail_estimates(false)` to re-attempt matching uncorrelated CallRail leads (`estimate_id IS NULL`) to HCP estimates. This ensures that leads which arrive before their estimate exists in HCP are eventually correlated and enter the conversion pipeline.

**Rationale**: CallRail webhooks often fire before the corresponding HCP estimate is created (new prospect calls, then gets booked). The correlation trigger runs on INSERT but may fail if the customer/estimate doesn't exist yet. Periodic resync bridges this timing gap without requiring real-time event hooks.

### 9. Conversions dashboard view with GCLID source attribution

**Decision**: Create a SQL view `vw_gads_conversions` that joins `gads_conversion_uploads` with estimate, customer, and job data, providing a single denormalized source for the dashboard page. The view includes a `gclid_source` indicator (`'booking'`, `'call'`, `'both'`) resolved by checking which source tables have a GCLID for the estimate. When both exist, the view exposes both the uploaded (primary) GCLID and the secondary (non-uploaded) GCLID.

**Rationale**: A view keeps the dashboard query simple and avoids complex joins in TypeScript. The `gclid_source` field provides attribution insight — knowing a lead both submitted a form and called signals high intent. Grouping by date matches the natural way to review conversion upload history.

### 10. GCLID priority: booking form over CallRail

**Decision**: When an estimate has a GCLID from both `booking_tags` (key-value: `key = 'gclid'`, value is the GCLID) and `callrail_leads` (phone call), the pipeline uses the booking form GCLID. Resolution is: `COALESCE((SELECT bt.value FROM booking_tags bt WHERE bt.estimate_id = e.id AND bt.key = 'gclid'), cl.gclid)`. Only one GCLID per estimate is uploaded to Google Ads across all three lifecycle stages.

**Rationale**: A single customer journey may involve both a form submission and a phone call, each from a separate ad click (or the same click). Uploading both would double-count the conversion. The booking form GCLID is preferred because it's captured at the exact moment of conversion (form submission), while the CallRail GCLID may come from a different session or day. The non-uploaded GCLID remains in its source table (`booking_tags` or `callrail_leads`) and is visible in the dashboard for attribution context.

**Alternative considered**: Upload both GCLIDs as separate conversion records. Rejected because it overcounts conversions and breaks the `UNIQUE(estimate_id, conversion_type)` constraint (would need a third key component). Google Ads bidding algorithms optimize on conversion counts, so overcounting degrades bid quality.

### 11. Tracking multi-source leads (booking + call) independently of GCLID upload

**Decision**: The `vw_gads_conversions` dashboard view includes a `gclid_source` indicator (`'booking'`, `'call'`, `'both'`) resolved by checking which source tables have a GCLID for the estimate. When both exist, the view also exposes the secondary (non-uploaded) GCLID. This gives full attribution visibility without affecting what gets uploaded.

**Rationale**: Knowing that a lead both submitted a form *and* called is valuable business intelligence — it signals high intent. This information should be visible in the dashboard even though only one GCLID is used for the Google Ads upload. The source tables (`booking_tags`, `callrail_leads`) are the system of record; the audit table (`gads_conversion_uploads`) only tracks what was uploaded.

### 12. Booking lead scope: booking form only

**Decision**: The booking lead discovery function (`get_pending_booking_lead_conversions()`) only returns estimates with `is_booking_form = true`. Estimates that have a GCLID solely through a correlated CallRail lead (but were not created via the booking form) are NOT booking leads — they enter the pipeline at stage 2 (qualified lead) or stage 3 (converted lead) when the estimate reaches those milestones.

**Rationale**: A "booking lead" means the customer submitted the online booking form. An estimate created by a tech in the field that happens to have a correlated CallRail call is not a booking — it's a different acquisition channel. Mixing them would inflate the booking lead count and misattribute conversions.

### 13. Conversion value: cents to dollars

**Decision**: The discovery SQL functions SHALL divide `total_amount` (stored as integer cents) by 100.0 when writing `conversion_value` to the audit table. Google Ads expects dollar values, not cents.

**Rationale**: `estimate_options.total_amount` and `jobs.total_amount` are both stored as integer cents in the database. The conversion must happen at discovery time so the audit table contains the final dollar value ready for upload.

### 14. Contact data: not in discovery, fetched at upload

**Decision**: The three discovery SQL functions do NOT return customer contact data (`email`, `mobile_number`). They return only: `estimate_id`, `conversion_type`, `gclid`, `conversion_datetime`, `conversion_value`, `job_id`. The upload edge function fetches `email` and `mobile_number` from the `customers` table (via `estimates.customer_id`) at upload time, just before hashing.

**Rationale**: Contact data is only needed for enhanced conversions (hashing for the Google Ads API). The audit table has no email/phone columns. Fetching it in the SQL functions would be wasted work — the discovery phase writes to the audit table, which doesn't store it. The upload edge function is the right place to fetch and hash contact data in a single step.

### 15. Conversion action resolved at upload, not discovery

**Decision**: The `conversion_action` column on `gads_conversion_uploads` is nullable. Discovery writes NULL. The upload edge function reads `conversion_type` from the pending row, looks up `conversion_action_id` from `gads_conversion_config`, builds the full resource name (`customers/{id}/conversionActions/{actionId}`), and writes it back to the row after upload as a historical record. Discovery reads only the `enabled` flag from `gads_conversion_config` to skip disabled types — it does not read or resolve `conversion_action_id`.

**Rationale**: The conversion action ID is a Google Ads API concern, not a data discovery concern. Deferring it to upload keeps the SQL functions free of API-specific config. Checking the `enabled` boolean at discovery time is a pipeline control concern, not an API concern, so it's appropriate for the SQL layer. If the config is missing or wrong, the pending row is visible in the dashboard (stuck as pending with incremented upload_attempts), making misconfiguration obvious.

### 16. Lifecycle stages are independent — no ordering enforced

**Decision**: The three discovery functions operate independently. There is no requirement that a `booking_lead` row exists before a `qualified_lead` row can be created for the same estimate. If a populate run discovers a new estimate that's already completed, both a `booking_lead` and `qualified_lead` row may be created in the same run.

**Rationale**: This makes the system self-healing — if a cron run is missed or delayed, the next run catches up for all stages simultaneously. The `conversion_datetime` values are correct regardless (estimate `created_at` for booking, `updated_at` for qualified), so Google Ads receives the right timestamps even if the rows are discovered late.

### 17. booking_tags is a key-value table — GCLID resolved via subquery

**Decision**: `booking_tags` is a generic key-value store with columns `key` and `value`, constrained by `UNIQUE(estimate_id, key)`. The GCLID is stored as `key = 'gclid'`, `value = <gclid_string>`. In SQL, the booking form GCLID is resolved as a scalar subquery: `(SELECT bt.value FROM booking_tags bt WHERE bt.estimate_id = e.id AND bt.key = 'gclid')`. The shorthand "booking_tags GCLID" or `COALESCE(booking_tags.gclid, ...)` throughout these specs refers to this subquery pattern, not a literal `gclid` column.

**Rationale**: `booking_tags` stores all URL attribution tags captured at booking time (utm_source, utm_medium, gclid, etc.), not just GCLIDs. A key-value schema is more flexible than dedicated columns. The subquery is efficient because `UNIQUE(estimate_id, key)` provides an index-backed lookup.

### 18. No 'failed' status — upload retries via cron

**Decision**: Rows that fail to upload stay in `'pending'` status. The `error_message` column captures the last failure reason and `upload_attempts` is incremented. On the next cron run, the upload function re-attempts all pending rows. On successful upload, `error_message` is cleared, `upload_attempts` is incremented, and status changes to `'uploaded'`. The only terminal statuses are `'uploaded'` and `'skipped'`.

**Rationale**: No retry queue or separate 'failed' state needed. The cron-based system naturally retries pending rows. A separate 'failed' status would require a mechanism to re-queue rows. Keeping them 'pending' with diagnostic columns (`error_message`, `upload_attempts`) is simpler and self-healing. The dashboard can distinguish "never tried" (attempts=0) from "retrying" (attempts>0, error set) from "succeeded after retries" (attempts>1, uploaded) without needing a separate status.

### 19. Per-type enabled and dry_run config flags

**Decision**: Each row in `gads_conversion_config` has `enabled boolean NOT NULL DEFAULT false` and `dry_run boolean NOT NULL DEFAULT false` flags. When `enabled = false`, the discovery function skips that conversion type entirely — no pending rows are created. When `dry_run = true`, the upload function skips pending rows of that type, leaving them in 'pending' status so they accumulate visibly in the dashboard without being sent to Google Ads.

**Rationale**: This gives the operator three modes per conversion type:
- **Disabled** (`enabled = false`): discovery and upload both skip — no rows created, no API calls
- **Dry run** (`enabled = true, dry_run = true`): discovery creates pending rows, upload skips them — preview what would be uploaded
- **Live** (`enabled = true, dry_run = false`): full pipeline — discover and upload

This supports phased rollout: enable `booking_lead` first in dry_run, verify the pending rows look correct in the dashboard, then switch off dry_run to go live.

### 20. Upload attempts tracking

**Decision**: `gads_conversion_uploads` has an `upload_attempts integer NOT NULL DEFAULT 0` column. The upload function increments this on every upload attempt (whether the attempt succeeds, partially fails, or the API rejects the row). On successful upload, `error_message` is cleared. On failure, `error_message` is set to the latest error.

**Rationale**: Combined with `error_message`, this gives full diagnostic visibility: `upload_attempts = 0` means never tried, `upload_attempts > 0` with `status = 'pending'` means retrying, `upload_attempts > 0` with `status = 'uploaded'` means succeeded (possibly after retries). The dashboard can surface rows that are stuck retrying (high attempt count, still pending) without needing a separate status.

## Risks / Trade-offs

**[Stale conversion action IDs in config table]** → Config table could have invalid IDs if changed incorrectly in the dashboard. Mitigation: The upload function logs partial failure errors from Google Ads API per row, making invalid action IDs immediately visible in audit rows.

**[pg_cron interval vs. freshness]** → A 15-minute cron interval means conversions can be up to 15 minutes stale. Mitigation: This is irrelevant; Google processes offline conversions in daily batches. Even hourly would be fine.

**[GCLID expiration]** → Google rejects GCLIDs older than 90 days. A job might complete months after the original ad click. Mitigation: In practice the discovery functions scan a limited time frame (not the full table), so most expired GCLIDs are naturally excluded. If an expired GCLID is uploaded, the Google Ads API returns a partial failure — the row stays `'pending'` with the error captured in `error_message` and `upload_attempts` incremented, visible in the dashboard.

**[Uncorrelated CallRail leads never enter pipeline]** → If `resync_callrail_estimates()` never matches a CallRail lead to an estimate (e.g., the caller never becomes a customer), that lead's conversion is never uploaded. Mitigation: The correlation resync cron reduces the window of unmatched leads. Truly uncorrelatable leads (caller never becomes a customer) are acceptable losses — there is no estimate to anchor the conversion to.

**[One-estimate-many-jobs]** → The `UNIQUE(estimate_id, conversion_type)` constraint allows only one converted_lead row per estimate. If an estimate spawns multiple jobs, only the first completed job is captured. Mitigation: In practice most estimates produce one job. If this proves insufficient, the constraint can be expanded to include `job_id`.

**[Existing batch function upsert breaks]** → The existing `google-ads-conversion-upload` uses `onConflict: "estimate_id"`. Once the UNIQUE constraint changes to `(estimate_id, conversion_type)`, this breaks. Mitigation: Update the existing function's upsert calls to include `conversion_type` as part of the migration.

**[Manual upload function compatibility]** → `gads-upload-booking` writes to `gads_conversion_uploads` without a `conversion_type`. Mitigation: Must be updated to include `conversion_type: 'booking_lead'` in its upsert payload. `gads-upload-call` is removed entirely.
