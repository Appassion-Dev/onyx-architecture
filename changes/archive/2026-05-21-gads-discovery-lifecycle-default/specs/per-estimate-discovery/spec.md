## MODIFIED Requirements

### Requirement: `discover_pending_conversions_for_estimate` is a Postgres function
A SQL function `public.discover_pending_conversions_for_estimate(p_estimate_id text)` SHALL exist in the database. It SHALL mirror the logic of `discover_pending_conversions()` but scope each sub-query to the given estimate ID. It SHALL return `(booking_leads int, qualified_leads int, converted_leads int)`. Every row it inserts into `gads_conversion_uploads` SHALL be written with `status = 'pending'` and `lifecycle = 'queued'` in the same INSERT, so on-demand discoveries are immediately visible to the upload edge function (which selects `lifecycle IN ('queued', 'retrying')`).

#### Scenario: Function returns counts per stage
- **WHEN** `discover_pending_conversions_for_estimate('some-estimate-id')` is called
- **THEN** it SHALL return a single row with the count of newly inserted rows per stage (0 if nothing was inserted)

#### Scenario: Inserted row has queued lifecycle
- **WHEN** the function inserts a new row for any of the three conversion types
- **THEN** the row SHALL have `status = 'pending'` and `lifecycle = 'queued'`

#### Scenario: On-demand discovery is visible to the uploader
- **WHEN** a user clicks a null PhaseCell, the function inserts a new row, and the upload edge function runs immediately after
- **THEN** the uploader's pickup query SHALL include the row in its candidate set (it is not stranded with `lifecycle = NULL`)
