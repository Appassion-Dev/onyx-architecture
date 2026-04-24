## Requirements

### Requirement: Drop job columns from pipeline table
The ConversionsPage SHALL NOT render `job_id` or `job_invoice_number` columns. The `PipelineRow` interface SHALL NOT include these fields.

#### Scenario: Pipeline table has no job columns
- **WHEN** the ConversionsPage renders the pipeline table
- **THEN** no column header or cell for job ID or job invoice number SHALL be present

### Requirement: Unified display value
The ConversionsPage SHALL display a single `display_value` per estimate, representing the SUM of approved/pro-approved estimate option amounts in dollars. Per-stage value columns (`booking_value`, `qualified_value`, `converted_value`) SHALL NOT be rendered.

#### Scenario: Display value shown for estimate with approved options
- **WHEN** an estimate has approved options totaling $2,500
- **THEN** the display_value column SHALL show "$2,500.00"

#### Scenario: Display value zero when no options approved
- **WHEN** an estimate has been quoted but no options are approved
- **THEN** the display_value column SHALL show "—"

#### Scenario: Display value null for booking-only estimate
- **WHEN** an estimate has only reached the booking stage (no options exist)
- **THEN** the display_value column SHALL show "—"

### Requirement: Weekly totals sum display_value once per estimate
The weekly rollup stats SHALL sum `display_value` across all estimates in the week, counting each estimate exactly once.

#### Scenario: Weekly total for three estimates
- **WHEN** a week contains estimates with display_values $1,000, $2,000, and $500
- **THEN** the weekly total SHALL be $3,500

### Requirement: Source badges column replaces booking_source
The ConversionsPage SHALL replace the single `booking_source` text column with a multi-badge source column as defined in the source-badges spec.

#### Scenario: Source column renders badges not text
- **WHEN** an estimate row is rendered
- **THEN** the source column SHALL render Badge components, not a plain text string

### Requirement: Pipeline view contract
The `PipelineRow` TypeScript interface SHALL include these new fields from the updated view: `has_form` (boolean), `call_count` (number), `lead_source` (string | null), `callrail_sources` (string[] | null). It SHALL NOT include: `job_id`, `job_invoice_number`, `booking_source`, `booking_value`, `qualified_value`, `converted_value`.

#### Scenario: PipelineRow interface matches view contract
- **WHEN** the ConversionsPage queries `vw_gads_conversion_pipeline`
- **THEN** the PipelineRow interface SHALL type-check against the view's columns without extra or missing fields