## MODIFIED Requirements

### Requirement: Qualified lead discovery criteria
The system SHALL consider an estimate as a qualified lead when at least one `estimate_options` row exists for that estimate with `total_amount > 0`. The estimate's own `work_status` is NOT consulted by this gate. An estimate with no priced options has no measurable scope and SHALL NOT be discovered as qualified.

#### Scenario: Estimate with at least one priced option qualifies regardless of work_status
- **WHEN** an estimate has at least one `estimate_options` row with `total_amount > 0`
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion regardless of `estimates.work_status`

#### Scenario: Estimate with `created job from estimate` work_status qualifies
- **WHEN** an estimate has `work_status = 'created job from estimate'` and at least one priced option
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

#### Scenario: Estimate with no priced options does not qualify
- **WHEN** all `estimate_options` rows for an estimate have `total_amount IS NULL` or `total_amount = 0`, or no options exist
- **THEN** the estimate SHALL NOT be discovered as a qualified lead

#### Scenario: Estimate with non-complete work_status now qualifies if priced
- **WHEN** an estimate has `work_status` such as `'needs scheduling'`, `'scheduled'`, or `'in progress'` and has at least one priced option
- **THEN** the estimate SHALL be discovered as a pending `qualified_lead` conversion

### Requirement: Qualified lead GCLID resolution
The qualified-lead row's `gclid` SHALL be supplied by the shared per-estimate GCLID resolver (see capability `customer-gclid-attribution`), invoked once per estimate per discovery run. The qualified-stage detection function SHALL NOT independently query `customer_gclids` for the GCLID column. The resolver anchors the 90-day window on the latest available stage timestamp (`GREATEST(e.updated_at, MAX(jobs.updated_at))`), so the qualified row's GCLID is the same canonical value used by the booking and converted rows for the same estimate within that run.

#### Scenario: Qualified row inherits the canonical per-estimate GCLID
- **WHEN** discovery resolves a GCLID `GCLID_X` for an estimate via the shared resolver
- **THEN** the qualified-lead row inserted in the same run SHALL have `gclid = GCLID_X`, identical to the booking and converted rows for that estimate

#### Scenario: Qualified row has NULL gclid when the resolver returns NULL
- **WHEN** the shared resolver returns NULL (no in-window GCLID for the customer)
- **THEN** the qualified-lead row is still discovered with `gclid = NULL`

#### Scenario: Qualified-stage upload re-checks the stored GCLID against the qualified-stage window
- **WHEN** the upload edge function processes the qualified row
- **THEN** it SHALL apply the per-stage 90-day window check (see capability `customer-gclid-attribution`) anchored on the qualified row's own `conversion_datetime` (`e.updated_at`), and SHALL omit the GCLID from the API payload if out of window for this stage
