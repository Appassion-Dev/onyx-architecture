## ADDED Requirements

### Requirement: Upload cron runs at most once per day
The Google Ads conversion upload edge function SHALL be scheduled to run at most once per day (recommended: 09:00 America/New_York). The cadence SHALL be slow enough that late-arriving attribution data (CallRail webhooks, delayed booking_tag inserts) has time to populate `customer_gclids` and be picked up by the discovery re-attribution pass before pending rows are committed to Google Ads.

#### Scenario: Upload cron runs no more than once per 24 hours
- **WHEN** the cron schedule for `google-ads-conversion-upload` is inspected
- **THEN** the schedule SHALL fire at most once per 24-hour period

#### Scenario: Discovery cron runs before upload cron on the same day
- **WHEN** both the discovery and upload cron jobs are scheduled
- **THEN** the discovery cron (which performs the re-attribution pass) SHALL be scheduled to run before the upload cron on the same calendar day, so re-attribution has run against the freshest `customer_gclids` data before any commits

### Requirement: Manual upload via UI is not subject to the daily cadence
The bulk-upload UI action (triggered by a user clicking "Upload Pending" on the Conversions page) SHALL continue to invoke the upload edge function on demand, independently of the cron schedule. The cron-cadence requirement applies only to automated scheduled runs.

#### Scenario: User triggers a bulk upload between scheduled runs
- **WHEN** a user clicks "Upload Pending" on the Conversions page
- **THEN** the upload runs immediately without waiting for the next cron tick

### Requirement: Per-stage 90-day window check at upload time
For each row it sends, the upload edge function SHALL re-check the row's stored `gclid` against `customer_gclids.first_seen_at` and the row's own `conversion_datetime`. If the GCLID is not within the 90-day click-lookback window for that stage (`first_seen_at >= conversion_datetime - INTERVAL '90 days'`), the function SHALL omit the GCLID from the outbound API payload (sending the conversion as enhanced-conversion-only) WITHOUT modifying the stored row. This honours the per-estimate canonical GCLID at the storage layer while satisfying Google Ads' API-level constraint at the wire layer.

#### Scenario: Stored GCLID is in window — sent with GCLID
- **WHEN** a row's stored GCLID has `customer_gclids.first_seen_at` within 90 days of the row's `conversion_datetime`
- **THEN** the outbound API payload SHALL include the GCLID

#### Scenario: Stored GCLID is out of window for this stage — sent without GCLID, row preserved
- **WHEN** a row's stored GCLID has `customer_gclids.first_seen_at` outside the 90-day window relative to the row's `conversion_datetime`
- **THEN** the outbound API payload SHALL omit the GCLID and rely on enhanced conversions, AND `gads_conversion_uploads.gclid` for that row SHALL remain unchanged

#### Scenario: Lookup of first_seen_at fails — sent without GCLID
- **WHEN** the row's stored GCLID has no matching row in `customer_gclids` (e.g., manually inserted GCLID)
- **THEN** the outbound API payload SHALL omit the GCLID and rely on enhanced conversions; the stored row is preserved
