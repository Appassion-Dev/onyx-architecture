## Requirements

### Requirement: Single page-level bulk upload entry point
The Conversions page SHALL expose exactly one bulk-upload affordance: a single Upload button rendered in `ConversionsHeroHeader` at the top of the page. There SHALL NOT be any bulk-upload button on Month rollup headers, Week rollup headers, SourceGroup headers, or per-estimate rows. Per-row upload affordance is reachable only through the expanded StageDetail panel (per `phase-cell-upload`); the rollup hierarchy is read-only.

#### Scenario: Top-of-page Upload button visible
- **WHEN** the Conversions page is rendered with at least one pending estimate visible
- **THEN** an Upload button SHALL be rendered in the page header (`ConversionsHeroHeader`) labeled with the count of pending estimates currently in scope

#### Scenario: No Upload button on Month rollups
- **WHEN** a MonthCard is rendered
- **THEN** the MonthCard SHALL NOT include any Upload button or other bulk-action control

#### Scenario: No Upload button on Week rollups
- **WHEN** a WeekBlock is rendered
- **THEN** the WeekBlock SHALL NOT include any Upload button or other bulk-action control

#### Scenario: No Upload button on SourceGroup rollups
- **WHEN** a SourceGroupBlock is rendered
- **THEN** the SourceGroupBlock SHALL NOT include any Upload button or other bulk-action control

#### Scenario: No Upload button on per-estimate rows
- **WHEN** a PipelineRowItem is rendered (collapsed)
- **THEN** the row SHALL NOT include any Upload button, PhaseCell, or other bulk-action control on its top-level grid

### Requirement: Page-level bulk upload uploads all visible pending estimates
The top-of-page Upload button SHALL bulk-upload pending estimate IDs across the currently visible (filtered) hierarchy. In single-stage modes (`booking`, `qualified`, `converted`) the batch SHALL include estimates pending for that mode's stage. In `all` mode the batch SHALL include estimates pending for ANY of booking / qualified / converted. The dialog confirm UI SHALL show the per-stage breakdown when more than one stage contributes.

#### Scenario: Single-stage scope
- **WHEN** the active mode is `qualified` and the user clicks the top-of-page Upload button
- **THEN** the batch SHALL include only estimates visible in the filtered set with `qualified_status = 'pending'`

#### Scenario: All-stages scope
- **WHEN** the active mode is `all` and the user clicks the top-of-page Upload button
- **THEN** the batch SHALL include estimates visible in the filtered set with any of `booking_status = 'pending'`, `qualified_status = 'pending'`, or `converted_status = 'pending'`
- **AND** the confirm dialog SHALL display per-stage counts (e.g. "5 booking, 3 qualified, 2 converted")

#### Scenario: Button hidden when no pending estimates
- **WHEN** the visible (filtered) hierarchy has zero pending estimates in scope
- **THEN** the top-of-page Upload button SHALL NOT be rendered (or SHALL be disabled with a "no pending uploads" tooltip)

### Requirement: Bulk upload confirm flow uses Dialog then countdown toast
Clicking the top-of-page Upload button SHALL open a `Dialog` confirm modal showing the count and (when in `all` mode) the per-stage breakdown. Confirming SHALL close the modal and start a cancellable 5-second Sonner countdown toast with a `Progress` bar; countdown expiry SHALL trigger the upload by calling `google-ads-conversion-upload` with the explicit list of `estimate_id` values and the relevant `conversion_types`. The dialog SHALL display a dry-run warning when any affected conversion type has `dry_run: true` in `gads_conversion_config`.

#### Scenario: Dialog opens
- **WHEN** the user clicks the top-of-page Upload button
- **THEN** a `Dialog` modal SHALL open showing the total count of pending estimates and (in `all` mode) the per-stage breakdown

#### Scenario: Dry-run warning
- **WHEN** the Dialog modal is open and at least one affected conversion type has `dry_run: true`
- **THEN** the modal SHALL display: "⚠ One or more conversion types are in dry-run mode — those uploads will be simulated, not sent to Google Ads"

#### Scenario: Cancel from dialog
- **WHEN** the user clicks Cancel in the Dialog modal
- **THEN** the modal SHALL close and no upload request SHALL be sent

#### Scenario: Confirm starts countdown toast
- **WHEN** the user clicks Confirm in the Dialog modal
- **THEN** the modal SHALL close immediately
- **THEN** a Sonner `toast.custom()` SHALL appear showing "Uploading N conversions in 5s…" with a `Progress` bar draining from 100% to 0% and a Cancel button

#### Scenario: Cancel from countdown toast
- **WHEN** the user clicks Cancel in the countdown toast
- **THEN** the toast SHALL be dismissed and no upload request SHALL be sent

#### Scenario: Countdown expiry triggers scoped upload
- **WHEN** 5 seconds elapse in the countdown toast without cancellation
- **THEN** the system SHALL call `google-ads-conversion-upload` with `{ estimate_ids: [list of all in-scope estimate IDs], conversion_types: [the stage(s) being uploaded] }`
- **THEN** the page SHALL refetch pipeline data after the response

### Requirement: Bulk upload scope is limited to the explicit estimate ID list
The bulk upload SHALL pass the explicit list of `estimate_id` values from the currently filtered, visible hierarchy to the edge function. It SHALL NOT use a date range filter.

#### Scenario: Only filtered estimates are uploaded
- **WHEN** filters narrow the visible hierarchy to a subset of pending estimates
- **THEN** the request body SHALL contain `estimate_ids` equal to exactly that filtered set
- **THEN** pending estimates outside the filter SHALL NOT be uploaded
