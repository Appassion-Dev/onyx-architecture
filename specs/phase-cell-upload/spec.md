## Requirements

### Requirement: PhaseCell shows upload action on hover for pending and error states
A `PhaseCell` with `status === 'pending'` or `status === 'error'` SHALL display an upload icon when the user hovers over the cell, replacing the status icon.

#### Scenario: Hover reveals upload icon on pending cell
- **WHEN** a user hovers over a PhaseCell with `booking_status`, `qualified_status`, or `converted_status` equal to `'pending'`
- **THEN** the cell SHALL display an upload arrow icon in place of the clock icon

#### Scenario: Hover reveals upload icon on error state
- **WHEN** a user hovers over a PhaseCell where `status === 'pending'` and `upload_attempts > 0` (error state)
- **THEN** the cell SHALL display an upload arrow icon indicating retry

#### Scenario: Hover has no effect on uploaded, skipped, or null cells
- **WHEN** a user hovers over a PhaseCell with `status === 'uploaded'`, `status === 'skipped'`, or `status === null`
- **THEN** the cell SHALL NOT change its icon or appearance (except the null cell which has its own behavior)

### Requirement: Clicking an actionable PhaseCell starts a 5-second in-cell countdown
After clicking an upload-ready PhaseCell, the cell SHALL display an animated `Progress` bar draining from 100% to 0% over 5 seconds using the dashboard's `Progress` component. A Cancel button SHALL appear below the progress bar. When the countdown expires without cancellation, the upload SHALL be triggered.

#### Scenario: Countdown starts on click
- **WHEN** a user clicks a pending or error PhaseCell
- **THEN** the cell SHALL immediately show a `Progress` bar at 100% with `transition-all duration-[5000ms]` animating to 0%
- **THEN** a Cancel button SHALL appear in or below the cell

#### Scenario: Cancelling stops the countdown
- **WHEN** a user clicks Cancel during the 5-second countdown
- **THEN** the countdown SHALL be stopped
- **THEN** the cell SHALL revert to its normal status display
- **THEN** no upload request SHALL be sent

#### Scenario: Countdown expiry triggers upload
- **WHEN** 5 seconds elapse without cancellation
- **THEN** the system SHALL call `google-ads-conversion-upload` with `{ estimate_ids: [estimate_id], conversion_types: [stage_type] }` where `stage_type` is one of `'booking_lead'`, `'qualified_lead'`, `'converted_lead'`
- **THEN** the cell SHALL display a loading state while the request is in flight
- **THEN** the pipeline row SHALL be refetched after the response

### Requirement: Dry-run mode is surfaced before upload executes
When any upload is triggered and the relevant conversion type has `dry_run: true` in `gads_conversion_config`, the user SHALL be informed that the upload is simulated.

#### Scenario: Dry-run warning in single-cell countdown
- **WHEN** a countdown is active for a stage whose config has `dry_run: true`
- **THEN** the cell or an accompanying tooltip SHALL display a ⚠ indicator noting the upload is a dry run

#### Scenario: Dry-run warning in bulk upload modal
- **WHEN** the bulk upload Dialog confirm modal is shown and at least one affected conversion type has `dry_run: true`
- **THEN** the modal SHALL display a warning: "⚠ One or more conversion types are in dry-run mode — those uploads will be simulated, not sent to Google Ads"