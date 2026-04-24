## Requirements

### Requirement: Estimate-centric pipeline — all functions scan from estimates
All three pending conversion SQL functions SHALL scan the `estimates` table as their primary source, filtered by the presence of a GCLID. GCLID is resolved per estimate by checking `booking_tags` (key-value table: `key = 'gclid'`, GCLID is in `value` column) and `callrail_leads.gclid`, preferring the booking form value when both exist (see Decision 17). The `estimate_id` written to `gads_conversion_uploads` is always the real HCP estimate ID. Each lifecycle stage is independent — there is no required ordering between booking lead, qualified lead, and converted lead. A later stage may be discovered before or without an earlier one.

#### Scenario: Estimate with booking form GCLID
- **WHEN** an estimate has a `booking_tags` row with `key = 'gclid'`
- **THEN** the GCLID from `booking_tags` is used for all lifecycle stages

#### Scenario: Estimate with CallRail GCLID only
- **WHEN** an estimate has no `booking_tags` GCLID but a `callrail_leads` row with `estimate_id = e.id` and `gclid IS NOT NULL`
- **THEN** the CallRail GCLID is used for qualified lead and converted lead stages (but not booking lead — see booking lead requirement)

#### Scenario: Estimate with both booking form and CallRail GCLID
- **WHEN** an estimate has a GCLID in both `booking_tags` and `callrail_leads`
- **THEN** the booking form GCLID is used (COALESCE priority) and the CallRail GCLID is not uploaded

#### Scenario: Uncorrelated CallRail lead (no estimate_id)
- **WHEN** a `callrail_leads` row has `estimate_id IS NULL`
- **THEN** it does not appear in any SQL function results — it is not part of the pipeline

### Requirement: Booking lead pending conversion query
The system SHALL provide a SQL function `get_pending_booking_lead_conversions()` that returns estimates eligible for a "booking lead" conversion upload. A record is eligible when the estimate has `is_booking_form = true`, has a GCLID (from `booking_tags` or correlated `callrail_leads`), and no existing row in `gads_conversion_uploads` with `conversion_type = 'booking_lead'`. Booking leads have no conversion value. Only estimates originating from the booking form are eligible — estimates sourced only through CallRail (without `is_booking_form = true`) are not booking leads.

#### Scenario: Booking-form estimate with GCLID
- **WHEN** an estimate has `is_booking_form = true` and a GCLID in `booking_tags`, with no audit row for `conversion_type = 'booking_lead'`
- **THEN** the function returns the estimate with `gclid` populated, `conversion_type = 'booking_lead'`, `conversion_value = NULL`, and `created_at` as the conversion datetime

#### Scenario: Booking-form estimate with CallRail GCLID only
- **WHEN** an estimate has `is_booking_form = true` and no `booking_tags` GCLID but a correlated `callrail_leads` row with GCLID, with no audit row for `conversion_type = 'booking_lead'`
- **THEN** the function returns the estimate with the CallRail GCLID, `conversion_value = NULL`, and `created_at` as the conversion datetime

#### Scenario: Non-booking-form estimate with GCLID is excluded
- **WHEN** an estimate has `is_booking_form = false` (or NULL) but has a GCLID via correlated `callrail_leads`
- **THEN** the function SHALL NOT return that estimate for booking lead — it may still be eligible for qualified/converted lead stages

#### Scenario: Booking-form estimate without GCLID but with contact data
- **WHEN** an estimate has `is_booking_form = true` and no GCLID from either source but the customer has email or phone
- **THEN** the function returns the estimate with `gclid = NULL` and `conversion_type = 'booking_lead'` (for enhanced-conversion-only upload)

#### Scenario: Already-uploaded booking is excluded
- **WHEN** an estimate already has a row in `gads_conversion_uploads` with `conversion_type = 'booking_lead'`
- **THEN** the function SHALL NOT return that estimate

#### Scenario: Estimate with no GCLID and no contact data is excluded
- **WHEN** an estimate has `is_booking_form = true` but no GCLID and no customer email or phone
- **THEN** the function SHALL NOT return that estimate

### Requirement: Qualified lead pending conversion query
The system SHALL provide a SQL function `get_pending_qualified_lead_conversions()` that returns estimates with `work_status IN ('complete rated', 'complete unrated')` (varchar comparison — `estimates.work_status` is varchar(50), not the `work_status` enum used by `jobs`) that have a GCLID and no audit row with `conversion_type = 'qualified_lead'`. The conversion value is the estimate option total divided by 100.0 (converting from integer cents to dollars).

#### Scenario: Completed estimate with booking form GCLID
- **WHEN** an estimate has `work_status = 'complete rated'` and a GCLID in `booking_tags`
- **THEN** the function returns it with `conversion_type = 'qualified_lead'`, `updated_at` as conversion datetime, and `estimate_options.total_amount / 100.0` as conversion value

#### Scenario: Completed estimate with CallRail GCLID
- **WHEN** an estimate has `work_status = 'complete unrated'` and a correlated `callrail_leads` row with GCLID (no booking_tags GCLID)
- **THEN** the function returns it with the CallRail GCLID and `conversion_type = 'qualified_lead'`

#### Scenario: Completed estimate with both GCLIDs uses booking form
- **WHEN** an estimate has `work_status = 'complete rated'` and GCLIDs in both `booking_tags` and `callrail_leads`
- **THEN** the function returns it with the `booking_tags` GCLID (COALESCE priority)

#### Scenario: Completed estimate without GCLID is excluded
- **WHEN** an estimate has `work_status = 'complete rated'` but no GCLID from either source
- **THEN** the function SHALL NOT return it

#### Scenario: Non-completed estimate is excluded
- **WHEN** an estimate has `work_status = 'scheduled'` even with a GCLID
- **THEN** the function SHALL NOT return it

### Requirement: Converted lead pending conversion query
The system SHALL provide a SQL function `get_pending_converted_lead_conversions()` that returns jobs with `work_status IN ('complete rated', 'complete unrated')` whose linked estimate has a GCLID and no audit row with `conversion_type = 'converted_lead'` for that estimate. The function returns `original_estimate_id` as the estimate_id and `jobs.id` as the job_id. The conversion value is the job total divided by 100.0 (converting from integer cents to dollars).

#### Scenario: Completed job linked to GCLID estimate
- **WHEN** a job has `work_status = 'complete rated'`, `original_estimate_id` references an estimate with a GCLID, and no audit row exists with `estimate_id = original_estimate_id` and `conversion_type = 'converted_lead'`
- **THEN** the function returns it with `estimate_id = original_estimate_id`, `job_id = jobs.id`, `conversion_type = 'converted_lead'`, `jobs.updated_at` as conversion datetime, `jobs.total_amount / 100.0` as conversion value, and the estimate's resolved GCLID

#### Scenario: Completed job linked to CallRail GCLID estimate
- **WHEN** a job's `original_estimate_id` links to an estimate that has a `callrail_leads` GCLID (no booking_tags GCLID)
- **THEN** the function returns the job with that GCLID and `conversion_type = 'converted_lead'`

#### Scenario: Job with no original estimate is excluded
- **WHEN** a job has `original_estimate_id IS NULL`
- **THEN** the function SHALL NOT return it

#### Scenario: Job linked to non-GCLID estimate is excluded
- **WHEN** a job has `work_status = 'complete rated'` but the linked estimate has no GCLID from any source
- **THEN** the function SHALL NOT return it

### Requirement: Discovery SQL wrapper writes pending rows
The system SHALL provide a SQL function `discover_pending_conversions()` that invokes all three pending conversion query functions and writes their results as rows in `gads_conversion_uploads` with `status = 'pending'`. This function uses `INSERT ... ON CONFLICT (estimate_id, conversion_type) DO NOTHING` for idempotency. It does NOT look up `conversion_action_id` from `gads_conversion_config` — the `conversion_action` column is left NULL at discovery time (resolved at upload time). However, it DOES check the `enabled` flag in `gads_conversion_config` — conversion types with `enabled = false` are skipped entirely (no pending rows created). This function is called directly by `pg_cron` as a SQL statement — no edge function, no HTTP call.

#### Scenario: Discovery finds new booking lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_booking_lead_conversions()` returns an estimate
- **THEN** a row is inserted with `estimate_id` = HCP estimate ID, `conversion_type = 'booking_lead'`, `conversion_value = NULL`, `conversion_action = NULL`, `status = 'pending'`

#### Scenario: Discovery finds new qualified lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_qualified_lead_conversions()` returns an estimate
- **THEN** a row is inserted with `estimate_id` = HCP estimate ID, `conversion_type = 'qualified_lead'`, the estimate total ÷ 100 as `conversion_value`, `conversion_action = NULL`, and `status = 'pending'`

#### Scenario: Discovery finds new converted lead
- **WHEN** `discover_pending_conversions()` runs and `get_pending_converted_lead_conversions()` returns a job
- **THEN** a row is inserted with `estimate_id = original_estimate_id`, `job_id = jobs.id`, `conversion_type = 'converted_lead'`, the job total ÷ 100 as `conversion_value`, `conversion_action = NULL`, and `status = 'pending'`

#### Scenario: Discovery is idempotent
- **WHEN** `discover_pending_conversions()` runs twice with no status changes between runs
- **THEN** no duplicate rows are created (INSERT ON CONFLICT DO NOTHING)

### Requirement: Audit table supports multiple conversion types per estimate
The `gads_conversion_uploads` table SHALL have a `conversion_type` column, a nullable `job_id` column, and a UNIQUE constraint on `(estimate_id, conversion_type)` to allow up to three conversion rows per estimate (one per lifecycle stage). The `estimate_id` column always holds the real HCP estimate ID.

#### Scenario: Same estimate has booking, qualified, and converted lead rows
- **WHEN** an estimate progresses through all three lifecycle stages
- **THEN** three rows exist with the same `estimate_id` and different `conversion_type` values

#### Scenario: Duplicate insert for same type is rejected
- **WHEN** a row with `(estimate_id = 'est_123', conversion_type = 'qualified_lead')` already exists
- **THEN** a second insert with the same key is prevented by the UNIQUE constraint

### Requirement: Pending row metadata
Each pending conversion row SHALL include `conversion_value` (amount in dollars converted from integer cents by dividing by 100.0, or NULL for booking leads), `conversion_currency` (USD), and `conversion_datetime` appropriate to the conversion type. The `conversion_action` column is NULL at discovery time — it is populated by the upload edge function after resolving the action ID from `gads_conversion_config`.

#### Scenario: Booking lead has no value
- **WHEN** a booking lead row is written
- **THEN** `conversion_value` is NULL, `conversion_action` is NULL, and `conversion_datetime` is the estimate's `created_at`

#### Scenario: Qualified lead has estimate amount
- **WHEN** a qualified lead row is written for an estimate whose first `estimate_options.total_amount` is `8500` (integer cents)
- **THEN** `conversion_value` is `85.00` (8500 ÷ 100.0) and `conversion_datetime` is the estimate's `updated_at`

#### Scenario: Converted lead has job amount
- **WHEN** a converted lead row is written for a job with `total_amount = 15000` (integer cents)
- **THEN** `conversion_value` is `150.00` (15000 ÷ 100.0) and `conversion_datetime` is the job's `updated_at`