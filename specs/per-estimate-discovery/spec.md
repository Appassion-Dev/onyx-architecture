## Requirements

### Requirement: Null PhaseCell shows a Discover action on hover
A `PhaseCell` with `status === null` (no pipeline row exists yet for that stage) SHALL display a Discover icon (🔍 or magnifier) when hovered, indicating the user can trigger on-demand discovery for that estimate.

#### Scenario: Hover reveals Discover icon on null cell
- **WHEN** a user hovers over a PhaseCell where the stage status is `null`
- **THEN** the cell SHALL display a search/discover icon in place of the dashed placeholder

#### Scenario: No action on hover for non-null cells
- **WHEN** a user hovers over a PhaseCell with any non-null status
- **THEN** the null-discover hover behavior SHALL NOT apply (each status has its own hover behavior)

### Requirement: Clicking a null PhaseCell runs per-estimate conversion discovery
Clicking a null PhaseCell SHALL invoke `discover_pending_conversions_for_estimate(estimate_id)` via `supabase.rpc()`. This function checks all three conversion stages for the given estimate and inserts any eligible pending rows into `gads_conversion_uploads`.

#### Scenario: Discovery inserts a pending row
- **WHEN** the user clicks a null PhaseCell for an estimate that qualifies for that stage
- **THEN** the system SHALL call `discover_pending_conversions_for_estimate()` with the estimate's ID
- **THEN** if the estimate qualifies, a new `pending` row SHALL be inserted into `gads_conversion_uploads` for the applicable stage(s)
- **THEN** the pipeline row SHALL be refetched and the cell SHALL transition from null/dashed to pending/yellow

#### Scenario: Discovery finds nothing
- **WHEN** the user clicks a null PhaseCell and the estimate does not qualify for any stage
- **THEN** the system SHALL call `discover_pending_conversions_for_estimate()`
- **THEN** no rows are inserted
- **THEN** the cell SHALL remain in the null/dashed state
- **THEN** a brief informational toast SHALL appear: "No new conversions discovered for this estimate"

#### Scenario: Discovery is gated by config enabled flag
- **WHEN** `discover_pending_conversions_for_estimate()` is called for a stage whose `gads_conversion_config.enabled = false`
- **THEN** no pending row SHALL be inserted for that stage (consistent with global discovery behavior)

### Requirement: `discover_pending_conversions_for_estimate` is a Postgres function
A new SQL function `public.discover_pending_conversions_for_estimate(p_estimate_id text)` SHALL be created in a Supabase migration. It SHALL mirror the logic of `discover_pending_conversions()` but add `AND e.id = p_estimate_id::uuid` to each sub-query. It SHALL return `(booking_leads int, qualified_leads int, converted_leads int)`.

#### Scenario: Function returns counts per stage
- **WHEN** `discover_pending_conversions_for_estimate('some-uuid')` is called
- **THEN** it SHALL return a single row with the count of newly inserted rows per stage (0 if nothing was inserted)

#### Scenario: Function is callable by service_role
- **WHEN** the function is created via migration
- **THEN** `GRANT EXECUTE ON FUNCTION public.discover_pending_conversions_for_estimate(text) TO "service_role"` SHALL be applied
- **THEN** the function SHALL be invokable via `supabase.rpc('discover_pending_conversions_for_estimate', { p_estimate_id: '...' })`