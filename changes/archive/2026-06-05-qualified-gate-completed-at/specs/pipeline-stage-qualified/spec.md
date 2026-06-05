## MODIFIED Requirements

### Requirement: Qualified lead conversion datetime
The system SHALL use the estimate's `work_timestamps.completed_at` as the `conversion_datetime` for qualified lead conversions when a non-NULL value is present, and SHALL fall back to `estimates.updated_at` otherwise. `completed_at` is stored as `timestamp without time zone` holding HCP's UTC value, so it SHALL be interpreted as UTC (`completed_at AT TIME ZONE 'UTC'`) to yield a `timestamptz` compatible with the fallback and the return type. Because `completed_at` is the literal visit-completion signal, it is preferred over `updated_at` (a lagging proxy) wherever it exists; `updated_at` guarantees 100% coverage so a value is always produced.

#### Scenario: Datetime uses completed_at when present
- **WHEN** a qualified lead is discovered for an estimate that has a `work_timestamps` row with a non-NULL `completed_at`
- **THEN** `conversion_datetime` SHALL equal that `completed_at` interpreted as UTC

#### Scenario: Datetime falls back to updated_at when no completed_at
- **WHEN** a qualified lead is discovered for an estimate that has no `work_timestamps` row, or whose `work_timestamps` row has a NULL `completed_at`
- **THEN** `conversion_datetime` SHALL equal `estimates.updated_at`

#### Scenario: Pending rows order by the conversion datetime
- **WHEN** pending qualified conversions are returned
- **THEN** they SHALL be ordered ascending by the same coalesced expression used for `conversion_datetime` (`completed_at` interpreted as UTC, else `updated_at`)
