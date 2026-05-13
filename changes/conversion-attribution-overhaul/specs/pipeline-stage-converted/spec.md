## MODIFIED Requirements

### Requirement: Converted lead discovery criteria
The system SHALL consider an estimate as a converted lead when at least one row exists in `jobs` with `jobs.original_estimate_id = e.id`. Option-level `approval_status` is NOT consulted by this gate. Job existence is the canonical signal that the lead converted into work.

#### Scenario: Estimate with a job qualifies as converted regardless of option approval_status
- **WHEN** an estimate has at least one row in `jobs` with `original_estimate_id` referencing it
- **THEN** the estimate SHALL be discovered as a pending `converted_lead` conversion

#### Scenario: Estimate with approved options but no job does not qualify as converted
- **WHEN** an estimate has options with `approval_status IN ('approved','pro approved')` but no row in `jobs` references it
- **THEN** the estimate SHALL NOT be discovered as a converted lead

#### Scenario: Estimate with multiple jobs uses the most recent
- **WHEN** an estimate has two or more rows in `jobs` referencing it
- **THEN** the resolver SHALL select the most recently created job (`ORDER BY jobs.created_at DESC LIMIT 1`) for `job_id`, `conversion_value`, and `conversion_datetime`

### Requirement: Converted lead conversion value
The system SHALL report the most-recent job's `total_amount / 100.0` as the conversion value. The converted gate is keyed on job existence, so the conversion value reflects the job total rather than option approval totals.

#### Scenario: Value is the job total
- **WHEN** the most-recent job for an estimate has `total_amount = 320000` (cents)
- **THEN** the conversion value SHALL be `3200.00`

#### Scenario: Value reflects most recent job when multiple exist
- **WHEN** an estimate has two jobs, an earlier one with `total_amount = 100000` and a later one with `total_amount = 250000`
- **THEN** the conversion value SHALL be `2500.00`

### Requirement: Converted lead conversion datetime
The system SHALL use the most-recent job's `updated_at` as the converted lead `conversion_datetime`.

#### Scenario: Datetime from most recent job
- **WHEN** an estimate has two jobs, the later one updated at `2026-04-30 16:13:44`
- **THEN** the `conversion_datetime` SHALL be `2026-04-30 16:13:44`

### Requirement: Converted lead GCLID resolution
The converted-lead row's `gclid` SHALL be supplied by the shared per-estimate GCLID resolver (see capability `customer-gclid-attribution`), invoked once per estimate per discovery run. The converted-stage detection function SHALL NOT independently query `customer_gclids` for the GCLID column. The resolver anchors the 90-day window on the latest available stage timestamp (`GREATEST(e.updated_at, MAX(jobs.updated_at))`), so the converted row's GCLID is the same canonical value used by the booking and qualified rows for the same estimate within that run.

#### Scenario: Converted row inherits the canonical per-estimate GCLID
- **WHEN** discovery resolves a GCLID `GCLID_X` for an estimate via the shared resolver
- **THEN** the converted-lead row inserted in the same run SHALL have `gclid = GCLID_X`, identical to the booking and qualified rows for that estimate

#### Scenario: Converted row has NULL gclid when the resolver returns NULL
- **WHEN** the shared resolver returns NULL (no in-window GCLID for the customer)
- **THEN** the converted-lead row is still discovered with `gclid = NULL`

#### Scenario: Converted-stage upload re-checks the stored GCLID against the converted-stage window
- **WHEN** the upload edge function processes the converted row
- **THEN** it SHALL apply the per-stage 90-day window check (see capability `customer-gclid-attribution`) anchored on the converted row's own `conversion_datetime` (the most-recent job's `updated_at`), and SHALL omit the GCLID from the API payload if out of window for this stage
