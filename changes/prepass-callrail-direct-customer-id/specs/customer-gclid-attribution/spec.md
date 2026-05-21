## MODIFIED Requirements

### Requirement: Discovery pre-pass populates customer_gclids before stage detection
Both `discover_pending_conversions()` (batch cron) and `discover_pending_conversions_for_estimate(estimate_id)` (per-estimate RPC) SHALL run a GCLID resolution pre-pass that upserts into `customer_gclids` from `booking_tags` and `callrail_leads` before executing any of the three stage detection functions.

For the `callrail_leads` source, the pre-pass SHALL match rows by `callrail_leads.customer_id` (populated by the `correlate_callrail_estimate` BEFORE-trigger) and SHALL NOT route through `JOIN estimates ON estimates.id = callrail_leads.estimate_id`. A CallRail lead with `customer_id IS NOT NULL` and `gclid IS NOT NULL` is eligible regardless of whether `callrail_leads.estimate_id` is set. In the per-estimate variant, the additional predicate `callrail_leads.customer_id = <the estimate's customer_id>` SHALL be applied.

When inserting a row sourced from `callrail_leads`, the written `customer_gclids.estimate_id` value SHALL be `callrail_leads.estimate_id` as-stored (which may be NULL). The column is informational; no downstream resolver depends on its non-null value.

#### Scenario: Batch cron populates customer_gclids then discovers stages
- **WHEN** the `discover_pending_conversions()` cron function executes
- **THEN** it first runs the customer_gclids upsert pass, then runs booking, qualified, and converted detection in sequence

#### Scenario: Per-estimate RPC populates customer_gclids for that estimate
- **WHEN** `discover_pending_conversions_for_estimate(p_estimate_id)` is called
- **THEN** it upserts `customer_gclids` from `booking_tags` and `callrail_leads` for that estimate's customer before running stage detection

#### Scenario: Estimate with no customer_id is skipped in pre-pass
- **WHEN** an estimate has `customer_id IS NULL`
- **THEN** no row is inserted into `customer_gclids` for that estimate and processing continues without error

#### Scenario: CallRail lead with customer_id set but estimate_id NULL is included
- **WHEN** a `callrail_leads` row has `gclid IS NOT NULL`, `customer_id IS NOT NULL`, and `estimate_id IS NULL` (e.g. the trigger matched a customer but no estimate existed yet, or a resync was deferred)
- **THEN** the pre-pass inserts a row into `customer_gclids` with the lead's `customer_id` and `gclid`, `source = 'callrail'`, and `estimate_id = NULL`

#### Scenario: CallRail lead with NULL customer_id is excluded
- **WHEN** a `callrail_leads` row has `gclid IS NOT NULL` but `customer_id IS NULL` (no customer match)
- **THEN** the pre-pass does not insert a row into `customer_gclids` for that lead

#### Scenario: Per-estimate pre-pass scopes CallRail leads by customer_id, not by estimate_id
- **WHEN** `discover_pending_conversions_for_estimate(p_estimate_id)` runs and the resolved customer has multiple CallRail leads (some stapled to other estimates of the same customer, some with `estimate_id` NULL)
- **THEN** every eligible CallRail lead for that `customer_id` contributes its GCLID to `customer_gclids` via ON CONFLICT DO NOTHING, regardless of which estimate (if any) it was stapled to

### Requirement: Backfill function populates customer_gclids from historical data
The system SHALL provide a SQL function `backfill_customer_gclids()` that scans all existing `booking_tags` (where `key = 'gclid'`) and `callrail_leads` (where `gclid IS NOT NULL`) and upserts the associated customer attribution into `customer_gclids`. The function SHALL be idempotent.

For the `callrail_leads` source, the backfill SHALL match rows by `callrail_leads.customer_id` and SHALL NOT route through `JOIN estimates ON estimates.id = callrail_leads.estimate_id`. CallRail leads with `customer_id IS NOT NULL` and `gclid IS NOT NULL` are eligible regardless of whether `callrail_leads.estimate_id` is set. The inserted `customer_gclids.estimate_id` value SHALL be `callrail_leads.estimate_id` as-stored (which may be NULL).

#### Scenario: Backfill runs without errors on existing data
- **WHEN** `SELECT backfill_customer_gclids()` is executed on a database with existing booking_tags and callrail_leads
- **THEN** all customer-GCLID associations are populated in `customer_gclids` with no errors and no duplicate rows

#### Scenario: Backfill is idempotent
- **WHEN** `backfill_customer_gclids()` is run a second time
- **THEN** no existing rows are modified and no new duplicates are created (ON CONFLICT DO NOTHING)

#### Scenario: Backfill recovers CallRail GCLIDs previously dropped due to NULL estimate_id
- **WHEN** `backfill_customer_gclids()` runs against a database where some `callrail_leads` rows have `customer_id IS NOT NULL`, `gclid IS NOT NULL`, and `estimate_id IS NULL`
- **THEN** those rows are inserted into `customer_gclids` (subject to `(customer_id, gclid)` uniqueness) and counted in the function's `callrail_rows` return value
