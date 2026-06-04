## Requirements

### Requirement: Estimate import populates the schedules table
The `hcp-import-data` estimate import SHALL upsert a `schedules` row for every imported estimate whose HCP `/estimates` payload contains a `schedule` object with a non-null `scheduled_start`, mapping `scheduled_start`, `scheduled_end`, and `arrival_window` and setting `estimate_id`. (The `transformSchedule` helper is currently defined but never called; this requirement wires it into the import's related-records phase.)

#### Scenario: Estimate with a schedule is imported
- **WHEN** an estimate is imported and its payload has `schedule.scheduled_start`
- **THEN** a `schedules` row SHALL exist for that `estimate_id` with the mapped `scheduled_start`, `scheduled_end`, and `arrival_window`

#### Scenario: Estimate without a schedule writes no row
- **WHEN** an estimate is imported and its payload has no `schedule` object (or a null `scheduled_start`)
- **THEN** the import SHALL NOT write a `schedules` row for that estimate

### Requirement: Deterministic, idempotent schedule id
The estimate schedule import SHALL use the deterministic id `sch_<estimate_id>` and upsert with `onConflict: id`, so repeated imports update a single row per estimate rather than inserting duplicates. This id convention SHALL match the `hcp-booking` writer so both paths converge on the same row.

#### Scenario: Re-importing the same estimate does not duplicate
- **WHEN** the same estimate is imported more than once
- **THEN** exactly one `schedules` row SHALL exist for it, keyed `sch_<estimate_id>`

#### Scenario: Import and hcp-booking converge on one row
- **WHEN** both the estimate import and the `hcp-booking` webhook write a schedule for the same estimate
- **THEN** they SHALL target the same `sch_<estimate_id>` row (no parallel rows for the estimate)

### Requirement: One-time backfill of existing estimates
A one-time backfill SHALL populate `schedules` for estimates already present in the database by re-importing their schedule data from HCP, so historical estimates gain a `scheduled_start` where one exists in HCP.

#### Scenario: Backfill populates historical schedules
- **WHEN** the backfill runs for estimates that have a `schedule` in HCP but no deterministic `schedules` row
- **THEN** each such estimate SHALL gain a `sch_<estimate_id>` row with its `scheduled_start`

### Requirement: Remove legacy duplicated schedule rows
The legacy non-deterministic `sched_est_<id>_<timestamp>` rows (from the one-time Dec 2025 backfill) SHALL be de-duplicated so that at most one schedule row per estimate remains — the deterministic `sch_<estimate_id>` row.

#### Scenario: Legacy duplicates are removed after backfill
- **WHEN** the cleanup runs for an estimate that has a deterministic `sch_<estimate_id>` row
- **THEN** no `sched_est_%` duplicate rows SHALL remain for that estimate

#### Scenario: At most one schedule row per estimate
- **WHEN** the cleanup completes
- **THEN** each `estimate_id` in `schedules` SHALL have at most one row
