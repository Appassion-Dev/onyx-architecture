## ADDED Requirements

### Requirement: customer_gclids table stores customer-scoped GCLID attribution
The system SHALL maintain a `customer_gclids` table with columns `(id, customer_id, gclid, source, first_seen_at, estimate_id)`. The table SHALL enforce `UNIQUE(customer_id, gclid)` to prevent duplicate entries per customer per click.

#### Scenario: New GCLID recorded for customer
- **WHEN** a GCLID is observed for an estimate belonging to a customer who has no prior entry for that GCLID
- **THEN** a row is inserted into `customer_gclids` with the `customer_id`, `gclid`, `source` (either `'booking_form'` or `'callrail'`), `first_seen_at`, and the originating `estimate_id`

#### Scenario: Duplicate GCLID for same customer is ignored
- **WHEN** a GCLID that already exists for a given `customer_id` is encountered during discovery
- **THEN** the existing row is NOT overwritten (ON CONFLICT DO NOTHING)

#### Scenario: Customer with multiple ad clicks accumulates multiple rows
- **WHEN** a customer has clicked two separate ads over time, producing two distinct GCLIDs
- **THEN** `customer_gclids` contains two rows for that `customer_id`

### Requirement: Discovery pre-pass populates customer_gclids before stage detection
Both `discover_pending_conversions()` (batch cron) and `discover_pending_conversions_for_estimate(estimate_id)` (per-estimate RPC) SHALL run a GCLID resolution pre-pass that upserts into `customer_gclids` from `booking_tags` and `callrail_leads` before executing any of the three stage detection functions.

#### Scenario: Batch cron populates customer_gclids then discovers stages
- **WHEN** the `discover_pending_conversions()` cron function executes
- **THEN** it first runs the customer_gclids upsert pass, then runs booking, qualified, and converted detection in sequence

#### Scenario: Per-estimate RPC populates customer_gclids for that estimate
- **WHEN** `discover_pending_conversions_for_estimate(p_estimate_id)` is called
- **THEN** it upserts `customer_gclids` from `booking_tags` and `callrail_leads` for that estimate's customer before running stage detection

#### Scenario: Estimate with no customer_id is skipped in pre-pass
- **WHEN** an estimate has `customer_id IS NULL`
- **THEN** no row is inserted into `customer_gclids` for that estimate and processing continues without error

### Requirement: GCLID resolution for upload uses customer_gclids with first-touch ordering
When qualified_lead or converted_lead detection functions resolve a GCLID, the system SHALL query `customer_gclids` for the estimate's `customer_id`, ordered by `first_seen_at ASC`, and take the first result (first-touch attribution). If no row exists in `customer_gclids` for the customer, the GCLID SHALL be NULL.

#### Scenario: Customer has a prior GCLID from a different estimate
- **WHEN** a customer's first estimate came via an ad (GCLID recorded) and a second estimate is being discovered
- **THEN** the second estimate's qualified or converted conversion row receives the GCLID from the first estimate via `customer_gclids`

#### Scenario: Customer has no GCLID in customer_gclids
- **WHEN** no row exists in `customer_gclids` for the estimate's customer
- **THEN** the discovered conversion row has `gclid = NULL`; the row is still discovered as pending and relies on enhanced conversions for attribution

### Requirement: Backfill function populates customer_gclids from historical data
The system SHALL provide a SQL function `backfill_customer_gclids()` that scans all existing `booking_tags` (where `key = 'gclid'`) and `callrail_leads` (where `gclid IS NOT NULL`) and upserts the associated customer attribution into `customer_gclids`. The function SHALL be idempotent.

#### Scenario: Backfill runs without errors on existing data
- **WHEN** `SELECT backfill_customer_gclids()` is executed on a database with existing booking_tags and callrail_leads
- **THEN** all customer-GCLID associations are populated in `customer_gclids` with no errors and no duplicate rows

#### Scenario: Backfill is idempotent
- **WHEN** `backfill_customer_gclids()` is run a second time
- **THEN** no existing rows are modified and no new duplicates are created (ON CONFLICT DO NOTHING)
