# work-timestamps-import

## Purpose

Defines how the HCP data import populates the `work_timestamps` table — wiring the existing `transformWorkTimestamps` helper into the estimate and job importers with deterministic, idempotent ids, and clearing the legacy non-deterministic bloat so the table repopulates cleanly.

## Requirements

### Requirement: Import populates the work_timestamps table
The `hcp-import-data` import SHALL upsert a `work_timestamps` row for every imported estimate and job whose HCP payload contains a `work_timestamps` object, mapping `on_my_way_at`, `started_at`, and `completed_at`. Estimate rows SHALL set `estimate_id` (with `job_id` NULL) and job rows SHALL set `job_id` (with `estimate_id` NULL), consistent with the table's single-entity CHECK. (The `transformWorkTimestamps` helper is currently defined in both `import-estimates.ts` and `import-jobs.ts` but never called; this requirement wires it into each importer's related-records phase.)

#### Scenario: Estimate with work_timestamps is imported
- **WHEN** an estimate is imported and its payload has a `work_timestamps` object
- **THEN** a `work_timestamps` row SHALL exist for that `estimate_id` (with `job_id` NULL) carrying the mapped `on_my_way_at`, `started_at`, and `completed_at`

#### Scenario: Job with work_timestamps is imported
- **WHEN** a job is imported and its payload has a `work_timestamps` object
- **THEN** a `work_timestamps` row SHALL exist for that `job_id` (with `estimate_id` NULL) carrying the mapped timestamps

#### Scenario: Payload without work_timestamps writes no row
- **WHEN** an estimate or job is imported and its payload has no `work_timestamps` object
- **THEN** the import SHALL NOT write a `work_timestamps` row for that entity

### Requirement: Deterministic, idempotent work_timestamps id
The work_timestamps import SHALL use the deterministic ids `ts_est_<estimate_id>` (for estimates) and `ts_job_<job_id>` (for jobs) and upsert with `onConflict: id`, so repeated imports update a single row per estimate/job rather than inserting duplicates. The non-deterministic `Date.now()`-suffixed id SHALL NOT be used.

#### Scenario: Re-importing the same estimate does not duplicate
- **WHEN** the same estimate is imported more than once
- **THEN** exactly one `work_timestamps` row SHALL exist for it, keyed `ts_est_<estimate_id>`

#### Scenario: Re-importing the same job does not duplicate
- **WHEN** the same job is imported more than once
- **THEN** exactly one `work_timestamps` row SHALL exist for it, keyed `ts_job_<job_id>`

### Requirement: Legacy work_timestamps bloat is cleared
The legacy non-deterministic `ts_*_<timestamp>` rows (~6M rows, ~635× duplicated per entity, frozen since 2025-12-04) SHALL be removed by truncating `work_timestamps`, so the table starts clean before the deterministic-id import repopulates it. Truncation SHALL rely on the absence of inbound foreign keys and dependent objects (no FK pre-cleanup required).

#### Scenario: Table is empty after truncation
- **WHEN** the truncation migration has run and before any subsequent import
- **THEN** `work_timestamps` SHALL contain zero rows

#### Scenario: At most one row per entity after repopulation
- **WHEN** an import runs after truncation
- **THEN** each `estimate_id` and each `job_id` present in `work_timestamps` SHALL have at most one row
