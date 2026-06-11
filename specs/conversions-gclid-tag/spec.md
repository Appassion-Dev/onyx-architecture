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
Each estimate row in the Conversions roll-up SHALL render, in the Method cell of
the metric rail, exactly one upload-mechanism tag (or a dash) reflecting the
Google Ads payload that the row's current stage would send. GCLID presence is
read from the per-stage column `{stage}_gclid` (the stage resolved the same way
the row resolves its lifecycle: the event's stage in all-stages mode, otherwise
the active single-stage mode, defaulting to `booking`), falling back to
`all_gclids` only when no stage-specific column applies. Customer-identifier
presence is a non-empty `customer_email` OR `customer_mobile`. The tag is one of:
- **GCLID+ECL** (light green) — stage GCLID present AND a customer identifier
  present.
- **GCLID** (purple) — stage GCLID present, no customer identifier. (Defined for
  completeness; does not occur in practice.)
- **ECL** (light blue) — no stage GCLID, customer identifier present.
- a dash (`—`) — neither present.

The legacy single `GCLID ×N` count badge is replaced by these tags.

#### Scenario: GCLID and identifier both present
- **WHEN** the row's resolved stage GCLID is non-null AND `customer_email` or
  `customer_mobile` is non-empty
- **THEN** the Method cell SHALL show a light-green "GCLID+ECL" tag

#### Scenario: GCLID present, no identifier
- **WHEN** the row's resolved stage GCLID is non-null AND both `customer_email`
  and `customer_mobile` are empty
- **THEN** the Method cell SHALL show a purple "GCLID" tag

#### Scenario: Identifier only, no GCLID
- **WHEN** the row's resolved stage GCLID is null AND `customer_email` or
  `customer_mobile` is non-empty
- **THEN** the Method cell SHALL show a light-blue "ECL" tag

#### Scenario: Neither present
- **WHEN** the row's resolved stage GCLID is null AND both `customer_email` and
  `customer_mobile` are empty
- **THEN** the Method cell SHALL show a dash

### Requirement: Column headers match data columns
The `PipelineHeader` component SHALL include a "Source" header (w-16) and a separate "GCLID" header (w-20) aligned with their respective data columns.

### Requirement: GCLID tooltip on hover
The "GCLID+ECL" and "GCLID" tags SHALL show a tooltip on hover that lists all
GCLID values from `all_gclids`, one per line, in monospace font. The "ECL" tag
(no GCLID) SHALL NOT show a GCLID tooltip.

#### Scenario: Tooltip on a GCLID-bearing tag
- **WHEN** the user hovers over a "GCLID+ECL" or "GCLID" tag
- **THEN** a tooltip appears listing each `all_gclids` value on a separate line
  in monospace font

#### Scenario: No GCLID tooltip on ECL-only tag
- **WHEN** the row shows an "ECL" tag
- **THEN** no GCLID tooltip SHALL be shown

### Requirement: Combined GCLID source in view
The `vw_conversion_candidates` view SHALL expose an `all_gclids` column containing a deduplicated array of all GCLIDs from both `booking_tags` (where `key = 'gclid'`) and `callrail_leads.gclid` for the estimate. NULL values are excluded.

#### Scenario: GCLIDs from both sources combined
- **WHEN** an estimate has a GCLID in `booking_tags` and a different GCLID in `callrail_leads`
- **THEN** `all_gclids` contains both, deduplicated

#### Scenario: Duplicate GCLIDs across sources
- **WHEN** the same GCLID appears in both `booking_tags` and `callrail_leads`
- **THEN** `all_gclids` contains it only once