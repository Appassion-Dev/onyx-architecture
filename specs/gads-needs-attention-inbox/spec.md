# gads-needs-attention-inbox

## Purpose

Provide a Workbench inbox that groups `needs-attention` upload rows by error code, surfaces the joined disposition and remediation copy, collapses muted groups, and offers group-level reset and disposition-creation actions.

## Requirements

### Requirement: Needs Attention inbox page

The system SHALL provide a Workbench page at `/conversions/needs-attention` that lists rows from `vw_gads_conversion_uploads` with `lifecycle = 'needs-attention'`, grouped by `error_code`. Each group SHALL display the `error_code`, the row count, the joined `disposition` and `human_action`, and group-level actions.

#### Scenario: Group ordering

- **WHEN** the inbox page loads
- **THEN** groups SHALL be ordered by row count descending
- **THEN** groups with the same row count SHALL be ordered by most recent `last_attempt_at` descending

#### Scenario: Group content

- **WHEN** a group is rendered
- **THEN** it SHALL show the full namespaced `error_code` (e.g., `conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS`)
- **THEN** it SHALL show the disposition (`fix-config`, `fix-data`, `fix-triage`) and the `human_action` text from the joined disposition row
- **THEN** it SHALL show the integer row count

#### Scenario: Show rows drill-down

- **WHEN** a user clicks "Show rows" on a group
- **THEN** the group SHALL expand to a table of the constituent rows with `estimate_id`, `conversion_type`, `last_attempt_at`, and `attempt_count`
- **THEN** each row in the drill-down SHALL offer a per-row "Reset to queued" menu action

### Requirement: Muted groups are collapsed by default

When a group's joined disposition has `no_alert = true`, the group SHALL NOT appear in the main list. Instead, all muted groups SHALL be collapsed into a single "Muted (N groups)" accordion at the bottom of the page that the user can expand to view.

#### Scenario: no_alert keeps group out of main list

- **WHEN** the inbox renders and a group's `no_alert` is true
- **THEN** that group SHALL NOT contribute to the main scrolling list
- **THEN** that group SHALL appear inside the "Muted" accordion footer instead

#### Scenario: Empty muted accordion absent

- **WHEN** zero groups have `no_alert = true`
- **THEN** the "Muted" accordion footer SHALL NOT render

### Requirement: Group-level reset to queued

The system SHALL provide a "Reset all N to queued" action on each non-muted group. Activating it SHALL UPDATE every row in the group setting `lifecycle = 'queued'`, `error_code = NULL`, `error_namespace = NULL`, `error_detail = NULL`, and `attempt_count = 0`. A confirm dialog SHALL precede the action, showing the row count.

#### Scenario: Confirm before reset

- **WHEN** a user clicks "Reset all N to queued" on a group
- **THEN** the system SHALL display a confirm dialog stating the action and the row count
- **THEN** the UPDATE SHALL execute only if the user confirms

#### Scenario: Reset clears error state

- **WHEN** the user confirms the group reset
- **THEN** every row in the group SHALL have its `lifecycle` set to `'queued'`, its `error_code` / `error_namespace` / `error_detail` set to NULL, and its `attempt_count` set to 0
- **THEN** the rows SHALL be eligible for selection by the next cron pickup query

### Requirement: Unknown codes link to disposition creation

When a group's `error_code` has no corresponding row in `gads_error_dispositions` (the joined `disposition` is NULL), the group SHALL display a "Configure disposition" action that navigates to the Dispositions admin page pre-filled with the unknown error code.

#### Scenario: Unknown disposition group rendering

- **WHEN** a group's joined `disposition` is NULL
- **THEN** the group SHALL label the disposition as "fix-triage (default)"
- **THEN** the "Reset all to queued" action SHALL be replaced by a "Configure disposition" action

#### Scenario: Configure jumps to admin

- **WHEN** a user clicks "Configure disposition" on an unknown-code group
- **THEN** the dashboard SHALL navigate to `/conversions/dispositions` with a query parameter or state that pre-fills the create form with that `error_code`
