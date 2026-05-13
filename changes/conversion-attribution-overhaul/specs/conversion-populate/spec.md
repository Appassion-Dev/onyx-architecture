## ADDED Requirements

### Requirement: Discovery resolves the per-estimate GCLID once and shares it across stages
Within a single discovery run for an estimate, `discover_pending_conversions()` and `discover_pending_conversions_for_estimate(p_estimate_id)` SHALL invoke the per-estimate GCLID resolver (see capability `customer-gclid-attribution`) exactly once per estimate, AFTER the `customer_gclids` pre-pass (booking_tags + callrail_leads) and BEFORE the per-stage detection inserts. The resolved value SHALL be passed to all three stage inserts (`booking_lead`, `qualified_lead`, `converted_lead`) for that estimate, so the three rows carry the same `gclid`.

The per-stage detection functions (`get_pending_qualified_lead_conversions`, `get_pending_converted_lead_conversions`) SHALL NOT contain a `customer_gclids` subquery in their `gclid` column expression; the column SHALL be supplied by the discovery wrapper.

#### Scenario: Three stages discovered in one run share the same GCLID
- **WHEN** `discover_pending_conversions_for_estimate(eid)` runs and inserts a booking, qualified, and converted row for the same estimate in the same run
- **THEN** all three inserted rows SHALL have identical `gclid` values

#### Scenario: Resolver runs once per estimate per run, not three times
- **WHEN** `discover_pending_conversions_for_estimate(eid)` runs
- **THEN** the per-estimate GCLID resolver SHALL be invoked at most once for that estimate during the run

### Requirement: Discovery includes a re-attribution pass for NULL-gclid pending rows
Both `discover_pending_conversions()` (batch cron) and `discover_pending_conversions_for_estimate(p_estimate_id)` (per-estimate RPC) SHALL include a re-attribution pass that runs AFTER the `customer_gclids` pre-pass and BEFORE per-stage discovery. The pass SHALL update existing rows in `gads_conversion_uploads` where `status = 'pending'`, `gclid IS NULL`, and `conversion_type IN ('qualified_lead','converted_lead')`, setting `gclid` to the result of the per-estimate GCLID resolver (newest in-window from `customer_gclids` within 90 days of the latest stage anchor). Rows where the resolver returns NULL are left unchanged (still NULL). Rows with `status` other than `'pending'` SHALL NOT be touched.

#### Scenario: Re-attribution pass populates a NULL pending qualified row
- **WHEN** a `qualified_lead` row exists with `status = 'pending'` and `gclid IS NULL`, and `customer_gclids` now contains an in-window entry for the customer
- **THEN** the re-attribution pass SHALL set the row's `gclid` to that in-window value

#### Scenario: Re-attribution pass leaves uploaded rows untouched
- **WHEN** a `qualified_lead` row has `status = 'uploaded'` even with `gclid IS NULL`
- **THEN** the re-attribution pass SHALL NOT modify that row

#### Scenario: Re-attribution pass leaves expired and skipped rows untouched
- **WHEN** a row has `status IN ('expired','skipped','failed')`
- **THEN** the re-attribution pass SHALL NOT modify it regardless of `gclid` value

#### Scenario: Per-estimate RPC re-attribution scoped to the estimate's customer
- **WHEN** `discover_pending_conversions_for_estimate(p_estimate_id)` runs
- **THEN** the re-attribution pass SHALL only update `pending` rows for estimates belonging to the same `customer_id` as `p_estimate_id`

#### Scenario: Re-attribution pass does not touch booking_lead rows
- **WHEN** a `booking_lead` row has `status = 'pending'` and `gclid IS NULL`
- **THEN** the re-attribution pass SHALL NOT modify it (booking uses per-estimate resolution, not customer_gclids)

### Requirement: One-time backfill recovers historical NULL-gclid pending rows
A migration SHALL execute the re-attribution UPDATE once at deploy time against all existing `pending` rows in `gads_conversion_uploads` where `gclid IS NULL` and `conversion_type IN ('qualified_lead','converted_lead')`. The backfill SHALL be idempotent (safe to re-run) and SHALL produce the same result as the discovery re-attribution pass would on the same rows.

#### Scenario: Backfill recovers a historical NULL-gclid qualified row
- **WHEN** a `pending` qualified row has `gclid IS NULL` and the customer has an in-window `customer_gclids` entry
- **THEN** the backfill SHALL set the row's `gclid` to the resolver's value

#### Scenario: Backfill is idempotent
- **WHEN** the backfill UPDATE is run twice in sequence with no intervening data changes
- **THEN** the second run SHALL produce zero additional row changes
