## MODIFIED Requirements

### Requirement: GCLID resolution for upload uses customer_gclids with first-touch ordering
When qualified_lead or converted_lead detection functions resolve a GCLID, the system SHALL query `customer_gclids` for the estimate's `customer_id`, ordered by `first_seen_at ASC`, **filtered to rows where `first_seen_at >= conversion_datetime - INTERVAL '90 days'`**, and take the first result (first-touch attribution). If no row exists in `customer_gclids` for the customer **within the lookback window**, the GCLID SHALL be NULL.

The 90-day constant mirrors the maximum allowed value of Google Ads `click_through_lookback_window_days`. The reference point is the conversion event timestamp (`conversion_datetime`, i.e. `e.updated_at` for qualified leads and the approved option timestamp for converted leads), not the upload time.

#### Scenario: Customer has a prior GCLID from a different estimate — within window
- **WHEN** a customer's first estimate came via an ad (GCLID recorded, `first_seen_at` within 90 days of the conversion event) and a second estimate is being discovered
- **THEN** the second estimate's qualified or converted conversion row receives the GCLID from the first estimate via `customer_gclids`

#### Scenario: Customer has a prior GCLID from a different estimate — outside window
- **WHEN** a customer's GCLID in `customer_gclids` has `first_seen_at` more than 90 days before the conversion event
- **THEN** that GCLID is excluded from the subquery and the conversion row is discovered with `gclid = NULL`; the row proceeds via enhanced conversions

#### Scenario: Customer has a recent GCLID and a stale GCLID — recent is selected
- **WHEN** a customer has two rows in `customer_gclids` — one with `first_seen_at` older than 90 days and one within 90 days of the conversion event
- **THEN** only the row within the window is eligible; the oldest eligible result (`ORDER BY first_seen_at ASC LIMIT 1` within the window) is selected

#### Scenario: Customer has no GCLID in customer_gclids
- **WHEN** no row exists in `customer_gclids` for the estimate's customer
- **THEN** the discovered conversion row has `gclid = NULL`; the row is still discovered as pending and relies on enhanced conversions for attribution

## ADDED Requirements

### Requirement: Stale pending rows with out-of-window GCLIDs are remediated
Existing `pending` rows in `gads_conversion_uploads` that were discovered with a GCLID whose `first_seen_at` exceeds 90 days before `conversion_datetime` SHALL be identified and updated: their `gclid` SHALL be set to NULL and their `status` SHALL remain `pending`, allowing them to be retried via the enhanced conversion path.

#### Scenario: Cleanup migration identifies affected rows
- **WHEN** the cleanup migration runs
- **THEN** all `pending` rows where the linked `customer_gclids.first_seen_at < conversion_datetime - INTERVAL '90 days'` are identified

#### Scenario: Cleanup migration NULLs the stale GCLID
- **WHEN** a `pending` row is identified with a stale GCLID
- **THEN** its `gclid` is set to NULL and `status` stays `pending` so the upload phase retries it via enhanced conversions
