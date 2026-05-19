## Requirements

### Requirement: Acceptance column sources from upload reconciliation view
The Acceptance column in the Conversions-page rollup rail SHALL be derived from `vw_gads_upload_reconciliation_daily` — the same view that powers the Upload Report page (`useUploadReport` / `useCombinedUploadReport`). The page SHALL fetch reconciliation rows scoped to the date range visible in the current hierarchy. The week-keying and time-zone logic SHALL be consistent with `src/lib/uploadReport.ts` (`getWeekInfo`, `America/New_York` time zone).

#### Scenario: Acceptance data source
- **WHEN** the Conversions page renders any Acceptance value
- **THEN** the underlying counts SHALL come from `vw_gads_upload_reconciliation_daily` (`google_successful_count`, `local_uploaded_count`) — NOT from `vw_conversion_candidates`

#### Scenario: Same totals as Upload Report page
- **WHEN** a user views the same month range on the Conversions page Month rollup and on the Upload Report page
- **THEN** the Acceptance count on the Conversions Month rollup SHALL equal the corresponding month total on the Upload Report page for that `event_key`

### Requirement: Acceptance is shown on Month and Week rollups only
The Acceptance column SHALL be rendered at the Month and Week levels of the hierarchy. It SHALL NOT be rendered at the SourceGroup level (reconciliation has no source attribution) and SHALL NOT be rendered on per-estimate rows.

#### Scenario: Month-level Acceptance
- **WHEN** a MonthCard is rendered
- **THEN** the Acceptance column SHALL be present in the metric rail

#### Scenario: Week-level Acceptance
- **WHEN** a WeekBlock is rendered
- **THEN** the Acceptance column SHALL be present in the metric rail

#### Scenario: SourceGroup omits Acceptance
- **WHEN** a SourceGroupBlock is rendered
- **THEN** the Acceptance column SHALL NOT be rendered

#### Scenario: Per-estimate row omits Acceptance
- **WHEN** a PipelineRowItem is rendered
- **THEN** Acceptance SHALL NOT appear anywhere on the row

### Requirement: Acceptance cell shows accepted-over-sent ratio with percent
The Acceptance cell SHALL display the count of rows Google Ads accepted over the count of rows we sent, plus the percentage. The numerator is `google_successful_count`, the denominator is `local_uploaded_count`. The percent SHALL be styled to match `SyncBadge`'s coloring: green ≥95%, amber 80–94%, red <80%. When the denominator is zero the cell SHALL display `—`.

#### Scenario: Healthy acceptance
- **WHEN** a Month has `local_uploaded_count = 50` and `google_successful_count = 48` for `event_key = 'qualified_lead'` in single-stage Qualified mode
- **THEN** the Acceptance cell SHALL display `48 / 50` with `96%` in green

#### Scenario: Degraded acceptance
- **WHEN** a Week has `local_uploaded_count = 20` and `google_successful_count = 15` for `event_key = 'converted_lead'` in single-stage Converted mode
- **THEN** the Acceptance cell SHALL display `15 / 20` with `75%` in red

#### Scenario: No uploads in window
- **WHEN** a Month has `local_uploaded_count = 0` for the active stage's event_key
- **THEN** the Acceptance cell SHALL display `—`

### Requirement: Acceptance aggregates across stages in all-stages mode
In `all` mode the Acceptance cell SHALL display a single aggregated `accepted / sent` ratio whose numerator is the sum of `google_successful_count` across `event_key IN ('booking_lead', 'qualified_lead', 'converted_lead')` and whose denominator is the sum of `local_uploaded_count` across the same keys, plus the corresponding percent badge.

#### Scenario: All-stages Acceptance aggregate
- **WHEN** the active mode is `all` and a Month has reconciliation counts for all three event_keys
- **THEN** the Acceptance cell SHALL display a single value formatted `Σaccepted / Σsent · pct%` summed across the three event_keys

#### Scenario: All-stages Acceptance with missing stage data
- **WHEN** the active mode is `all` and a Month has no reconciliation rows for `event_key = 'converted_lead'` but has rows for booking and qualified
- **THEN** the Acceptance cell SHALL display the booking + qualified counts summed (converted contributes zero to both numerator and denominator)

#### Scenario: All-stages Acceptance with no data anywhere
- **WHEN** the active mode is `all` and a Month has no reconciliation rows for any event_key
- **THEN** the Acceptance cell SHALL display `—`

### Requirement: Acceptance fetch is scoped to the visible date range
The hook that fetches reconciliation rows SHALL request only the date range covered by the currently visible hierarchy (the min and max `estimate_created_at` / stage datetimes across visible rows, rounded out to whole weeks in `America/New_York`). The query SHALL be cached using `@tanstack/react-query` with a key that includes the date range and the active mode (single-stage modes can request a single `event_key`; `all` mode requests all three).

#### Scenario: Single-stage fetch scope
- **WHEN** the active mode is `qualified`
- **THEN** the reconciliation fetch SHALL request rows with `event_key = 'qualified_lead'` only

#### Scenario: All-stages fetch scope
- **WHEN** the active mode is `all`
- **THEN** the reconciliation fetch SHALL request rows with `event_key IN ('booking_lead', 'qualified_lead', 'converted_lead')`

#### Scenario: Cache key changes with date range
- **WHEN** the visible hierarchy date range changes (e.g. a filter narrows the visible months)
- **THEN** the React Query cache key SHALL change and a new fetch SHALL be issued
