## Why

The conversions page currently groups data by date → week → conversion type, then lists individual conversion rows under each type. This forces users to mentally correlate the same estimate across three separate collapsible sections (Booking, Qualified, Converted) to understand pipeline progress. The redesign pivots conversion types into columns so each estimate is a single row showing its full pipeline state at a glance.

## What Changes

- Replace the 3-level hierarchy (month → week → type → rows) with a 2-level hierarchy (month → week → estimate pipeline rows)
- Each row represents one estimate with columns for: estimate number, customer, source, job number, value, and sync status per pipeline stage (Booking, Qualified, Converted), plus a closed flag
- Add a "Source" column showing the booking origin (Form, Call, or future LSA)
- Value column uses the same logic as the sales page: respects `estimates_settings.total_amount_source` preference (job amount vs estimate amount)
- Closed flag indicates all existing pipeline stages for that estimate are synced (uploaded or skipped)
- Expandable rows reveal per-stage detail (GCLID, upload timestamps, error messages, per-stage value)
- Week/month rollups simplified to quantity + total value
- Remove type and status filters (may be re-added later)
- Create a new SQL view `vw_gads_conversion_pipeline` that pivots conversion rows by estimate

## Capabilities

### New Capabilities
- `conversion-pipeline-view`: SQL pivot view that groups conversion uploads by estimate, exposing per-stage status/value columns and the display value matching sales page logic
- `conversion-pipeline-ui`: Frontend pipeline table component with estimate-per-row layout, expandable detail rows, and Lucide status icons

### Modified Capabilities

## Impact

- **Database**: New view `vw_gads_conversion_pipeline` joining `gads_conversion_uploads`, `estimates`, `estimate_options`, `estimates_settings`, `customers`, `jobs`, `booking_tags`, `callrail_leads`
- **Frontend**: `ConversionsPage.tsx` rewritten to consume the new view and render the pivot table
- **Removed**: Type/status filter dropdowns, `buildHierarchy` with type grouping, `TypeGroup` interface
- **Preserved**: Scan Now, Upload Pending, Settings, Refresh buttons; month/week collapsible grouping; conversion config page unchanged
