## Why

The existing Google Ads conversion upload system tracks only one event — the initial booking lead. There is no way to report downstream funnel milestones (estimate completed, job completed) back to Google Ads. Without these signals, Google's Smart Bidding optimizes for lead volume rather than lead quality, wasting ad spend on clicks that generate bookings but never convert to paid work.

## What Changes

- **Estimate-centric lifecycle tracking**: The pipeline treats each HCP estimate as the unit of work and tracks it through three lifecycle stages: booking made, estimate approved, job finished. Booking leads come from the booking form only (`is_booking_form = true`). Qualified and converted leads scan estimates/jobs with a resolved GCLID from either `booking_tags` or `callrail_leads`.
- **Separate pending-conversion queries per funnel stage**: Three dedicated SQL functions replace the single `get_pending_gclid_conversions()`. Each scans for estimates that qualify as a pending conversion for its stage: booking lead (booking-form estimate with GCLID or contact data), qualified lead (estimate completed with GCLID), or converted lead (job completed with GCLID).
- **New `conversion_type` column on `gads_conversion_uploads`**: Allows the same estimate to have multiple audit rows — one per funnel stage. The UNIQUE constraint changes from `(estimate_id)` to `(estimate_id, conversion_type)`. The `estimate_id` column always holds the real HCP estimate ID.
- **Conversion action ID per type via dashboard config**: Instead of a single `GOOGLE_ADS_CONVERSION_ACTION_ID` env var, each conversion type maps to its own Google Ads conversion action ID, stored in a dashboard-managed configuration table.
- **Separate "discover" and "upload" phases**: A SQL wrapper function `discover_pending_conversions()` is called directly by `pg_cron` to scan estimates across all three stages and write pending rows to the audit table. A separate cron-triggered edge function reads pending rows, resolves the conversion action ID from the config table, and uploads them to the Google Ads API. This separates data discovery (pure SQL) from API interaction (edge function).
- **GCLID resolution via COALESCE**: Each estimate's GCLID is resolved from `booking_tags` (key-value table: `key = 'gclid'`, value column holds the GCLID) and `callrail_leads.gclid`, preferring the booking form value when both exist. Only one GCLID per estimate is uploaded across all three stages.
- **No conversion value for booking leads**: The booking lead stage records no dollar value (the estimate hasn't been quoted yet). Qualified leads use the estimate option total; converted leads use the job total.
- **Correct conversion timestamps**: Booking leads use estimate `created_at`; qualified leads use estimate `updated_at` (status change time); converted leads use job `updated_at`.
- **CallRail correlation cron**: A periodic cron job runs `resync_callrail_estimates()` to re-attempt matching uncorrelated CallRail leads to HCP estimates. Once correlated, these estimates enter the main pipeline on the next discovery run.
- **Conversions dashboard page**: A new dashboard page displays all pending and uploaded conversions, grouped by date, with per-row detail including conversion type, status, value, GCLID source indicator (booking/call/both), and cross-phase lead correlation via shared `estimate_id`.

## Capabilities

### New Capabilities
- `conversion-populate`: SQL wrapper function `discover_pending_conversions()` called directly by `pg_cron` (no edge function). Internally calls three discovery sub-functions for booking lead, qualified lead, and converted lead stages, and writes pending rows to the audit table. All functions are estimate-centric — `estimate_id` is always the real HCP ID.
- `conversion-upload`: Cron-triggered edge function (via `pg_net`) that reads pending audit rows, checks enabled/dry_run flags, resolves conversion action IDs from the config table, fetches customer contact data (`email`, `mobile_number`) for enhanced conversions, and uploads to the Google Ads API. Tracks `upload_attempts` and `error_message` per row — failed rows stay pending for automatic retry on the next cron run.
- `conversion-config`: Dashboard-managed configuration for Google Ads conversion action IDs per conversion type, with `enabled` and `dry_run` toggles per type for phased rollout. Replaces the single env-var approach.
- `conversion-dashboard`: Dashboard page displaying all conversion uploads grouped by date, with status indicators, value totals, GCLID source attribution (booking/call/both), and cross-phase lead correlation via shared `estimate_id`.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **Database**: `gads_conversion_uploads` table altered (new columns including `conversion_type`, `job_id`, `error_message`, `upload_attempts`; `conversion_action` made nullable; changed UNIQUE constraint). Three new discovery SQL functions plus `discover_pending_conversions()` wrapper. Existing `get_pending_gclid_conversions()` dropped. New SQL view `vw_gads_conversions` for dashboard.
- **Edge functions**: `google-ads-conversion-upload` refactored to read pending rows and resolve action IDs from config (no more populate edge function — discovery is pure SQL). Existing `gads-upload-booking` manual upload function needs updating to include `conversion_type`. `gads-upload-call` is removed.
- **Dashboard**: New conversion config UI for mapping conversion types to Google Ads action IDs. New conversions dashboard page showing upload history grouped by date with GCLID source attribution and lead correlation.
- **Config**: `GOOGLE_ADS_CONVERSION_ACTION_ID` env var deprecated in favor of the config table.
- **Scheduling**: Requires `pg_cron` for three independent periodic jobs: (1) CallRail correlation resync (direct SQL), (2) conversion discovery via `discover_pending_conversions()` (direct SQL), (3) conversion upload via edge function (pg_net HTTP).
