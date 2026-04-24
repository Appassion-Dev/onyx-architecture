## Requirements

### Requirement: Source column shows computed first-touch medium
Each estimate row in the Conversions pipeline table SHALL show a single "Source" column displaying the computed `first_touch_medium` value. The column renders a single badge reading "form" or "call" (capitalized), or a dash when `first_touch_medium` is NULL. Legacy multi-badge rendering (callrail_sources, lead_source, has_form, call_count) is removed.

#### Scenario: Form first-touch
- **WHEN** `first_touch_medium = 'form'`
- **THEN** the Source column shows a single "Form" badge

#### Scenario: Call first-touch
- **WHEN** `first_touch_medium = 'call'`
- **THEN** the Source column shows a single "Call" badge

#### Scenario: No medium computed
- **WHEN** `first_touch_medium` is NULL
- **THEN** the Source column shows a dash

### Requirement: GCLID count badge in its own column
Each estimate row in the Conversions page SHALL include a dedicated "GCLID" column (separate from the Source column) displaying a `GCLID ×N` badge when one or more unique GCLIDs are present in `all_gclids`. When no GCLIDs exist, the column is empty.

#### Scenario: No GCLIDs present
- **WHEN** `all_gclids` is NULL or empty
- **THEN** the GCLID column is empty

#### Scenario: Single GCLID present
- **WHEN** `all_gclids` contains one entry
- **THEN** the GCLID column shows a badge reading "GCLID ×1"

#### Scenario: Multiple GCLIDs present
- **WHEN** `all_gclids` contains N entries (N > 1)
- **THEN** the GCLID column shows a badge reading "GCLID ×N"

### Requirement: Column headers match data columns
The `PipelineHeader` component SHALL include a "Source" header (w-16) and a separate "GCLID" header (w-20) aligned with their respective data columns.

### Requirement: GCLID tooltip on hover
The GCLID badge SHALL show a tooltip on hover that lists all GCLID values from `all_gclids`, one per line, in monospace font.

#### Scenario: Tooltip on hover
- **WHEN** user hovers over the GCLID badge
- **THEN** a tooltip appears listing each GCLID value on a separate line in monospace font

### Requirement: Combined GCLID source in view
The `vw_conversion_candidates` view SHALL expose an `all_gclids` column containing a deduplicated array of all GCLIDs from both `booking_tags` (where `key = 'gclid'`) and `callrail_leads.gclid` for the estimate. NULL values are excluded.

#### Scenario: GCLIDs from both sources combined
- **WHEN** an estimate has a GCLID in `booking_tags` and a different GCLID in `callrail_leads`
- **THEN** `all_gclids` contains both, deduplicated

#### Scenario: Duplicate GCLIDs across sources
- **WHEN** the same GCLID appears in both `booking_tags` and `callrail_leads`
- **THEN** `all_gclids` contains it only once