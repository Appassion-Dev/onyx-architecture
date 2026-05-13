## ADDED Requirements

### Requirement: GCLID is resolved once per estimate per discovery run and shared across stages
The system SHALL provide a single per-estimate GCLID resolver function (e.g., `resolve_estimate_gclid(p_estimate_id text)`) that returns one canonical GCLID for the estimate. The discovery pipeline SHALL invoke this resolver once per estimate per discovery run, and the returned value SHALL be written to all stage rows (`booking_lead`, `qualified_lead`, `converted_lead`) inserted for that estimate within that run. The per-stage detection functions SHALL NOT re-query `customer_gclids` independently for the GCLID column.

The resolver SHALL anchor the 90-day click-lookback window on the latest available stage `conversion_datetime` for the estimate, computed as:

```
GREATEST(
  e.updated_at,                                                                       -- qualified anchor
  (SELECT MAX(j.updated_at) FROM jobs j WHERE j.original_estimate_id = e.id)          -- converted anchor
)
```

When the estimate has no jobs, the anchor is `e.updated_at`. The resolver SHALL select the newest in-window GCLID from `customer_gclids` (`ORDER BY first_seen_at DESC LIMIT 1`).

#### Scenario: All three stage rows for an estimate share the same GCLID within a discovery run
- **WHEN** `discover_pending_conversions_for_estimate(eid)` runs for an estimate that newly qualifies for booking, qualified, and converted in the same run
- **THEN** all three resulting rows in `gads_conversion_uploads` SHALL have the same value in `gclid`

#### Scenario: Resolver anchor uses the latest available stage timestamp
- **WHEN** an estimate has `e.updated_at = 2026-04-01` and `MAX(j.updated_at) = 2026-05-01`
- **THEN** the resolver's window cutoff is `2026-02-01` (`2026-05-01 - 90 days`), not `2026-01-01`

#### Scenario: Resolver returns NULL when no in-window GCLID exists
- **WHEN** the customer has no `customer_gclids` row within 90 days of the latest stage anchor
- **THEN** the resolver returns NULL, and all three stage rows SHALL be inserted with `gclid = NULL`

#### Scenario: Per-stage detection functions do not re-query customer_gclids
- **WHEN** `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()` are inspected
- **THEN** neither function SHALL contain a `SELECT ... FROM customer_gclids ...` subquery in its `gclid` column expression; the column SHALL be supplied by the discovery wrapper via the shared resolver

### Requirement: Per-stage 90-day window check is enforced at upload time, not at storage time
The Google Ads conversion upload edge function SHALL, for each row it sends, re-check the row's stored `gclid` against `customer_gclids.first_seen_at` and the row's own `conversion_datetime`. If the stored GCLID is outside the 90-day window for that stage, the function SHALL omit the GCLID from the outbound API payload (sending the conversion as enhanced-conversion-only) WITHOUT modifying the stored row. The stored `gclid` value SHALL be preserved so analytics, badges, and future re-attribution still see the canonical per-estimate value.

#### Scenario: Stored GCLID is in window for the stage — sent with GCLID
- **WHEN** an upload row has `conversion_datetime = 2026-05-01` and stored `gclid` whose `customer_gclids.first_seen_at = 2026-03-15` (47 days before)
- **THEN** the outbound API payload SHALL include the GCLID

#### Scenario: Stored GCLID is out of window for the stage — sent without GCLID, row unchanged
- **WHEN** a booking-stage upload row has `conversion_datetime = 2026-01-15` and stored `gclid` whose `customer_gclids.first_seen_at = 2026-05-01` (out of window: too new for booking, but valid for the canonical-per-estimate pick)
- **THEN** the outbound API payload SHALL omit the GCLID and rely on enhanced conversions, AND the stored `gads_conversion_uploads.gclid` SHALL remain unchanged

#### Scenario: Stored GCLID is NULL — sent without GCLID
- **WHEN** an upload row has `gclid IS NULL`
- **THEN** the outbound API payload SHALL omit the GCLID and rely on enhanced conversions

## MODIFIED Requirements

### Requirement: GCLID resolution for upload uses customer_gclids with newest-in-window ordering within the click lookback window
When the per-estimate GCLID resolver runs, the system SHALL query `customer_gclids` for the estimate's `customer_id`, filtered to rows where `first_seen_at >= anchor_datetime - INTERVAL '90 days'` (where `anchor_datetime = GREATEST(e.updated_at, MAX(jobs.updated_at))` for the estimate), ordered by `first_seen_at DESC`, and take the first result (newest in-window). The reference point for the 90-day window is the conversion event timestamp anchored on the latest available stage, not the upload time. If no row exists within the window, the GCLID SHALL be NULL.

The 90-day constant mirrors the maximum allowed `click_through_lookback_window_days` in Google Ads. GCLIDs older than 90 days relative to the conversion event are rejected by the Ads API and must not be selected. Within the eligible set, newest-in-window is preferred over oldest because (a) the most recent click is the most likely to still be valid in Google's click cache at upload time, and (b) selecting the oldest creates a known failure mode where the only-eligible-stale-click suppresses fresher in-window clicks.

#### Scenario: Customer has a single in-window GCLID
- **WHEN** a customer has exactly one `customer_gclids` row within 90 days of the latest-stage anchor
- **THEN** that GCLID is selected

#### Scenario: Customer has multiple in-window GCLIDs — newest wins
- **WHEN** a customer has two `customer_gclids` rows both within 90 days of the latest-stage anchor, with `first_seen_at` of `2026-03-01` and `2026-04-15`
- **THEN** the `2026-04-15` row is selected (`ORDER BY first_seen_at DESC LIMIT 1`)

#### Scenario: Customer has both stale and in-window GCLIDs
- **WHEN** a customer has one row at 120 days before the latest-stage anchor and one row at 30 days before the anchor
- **THEN** the 30-day-before row is selected; the stale row is filtered out by the WHERE clause

#### Scenario: Customer has only an out-of-window GCLID
- **WHEN** a customer's only `customer_gclids` row has `first_seen_at` more than 90 days before the latest-stage anchor
- **THEN** the GCLID resolves to `NULL` and rows proceed via enhanced conversions

#### Scenario: Customer has no GCLID in customer_gclids
- **WHEN** no row exists in `customer_gclids` for the estimate's customer
- **THEN** all stage rows are discovered with `gclid = NULL` and rely on enhanced conversions for attribution

### Requirement: Stale pending rows with out-of-window GCLIDs are remediated
Existing `pending` rows in `gads_conversion_uploads` that were discovered with a GCLID whose `first_seen_at` in `customer_gclids` exceeds 90 days before `conversion_datetime` SHALL have their `gclid` re-resolved by the discovery re-attribution pass (see capability `conversion-populate`). If the re-attribution pass yields a usable in-window GCLID, that value replaces the stale one; if not, the `gclid` is set to NULL. The `status` SHALL remain `pending` in either case, allowing the upload phase to proceed via the GCLID path or fall back to enhanced conversions.

#### Scenario: Stale GCLID replaced by an in-window GCLID
- **WHEN** a `pending` row's stored `gclid` corresponds to a `customer_gclids.first_seen_at` older than 90 days, AND the customer has another `customer_gclids` row within 90 days of `conversion_datetime`
- **THEN** the re-attribution pass SHALL replace the stored `gclid` with the in-window value

#### Scenario: Stale GCLID NULLed when no in-window GCLID exists
- **WHEN** a `pending` row's stored `gclid` is stale and no in-window GCLID exists for the customer
- **THEN** the re-attribution pass SHALL set `gclid = NULL` and the row remains `pending`
