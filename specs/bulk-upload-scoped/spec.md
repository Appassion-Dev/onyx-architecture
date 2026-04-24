## Requirements

### Requirement: Week and month headers show an Upload button
Each week header row and each month header row in `ConversionsPage` SHALL display an "Upload" button that triggers a bulk upload for all pending conversion rows within that time bucket.

#### Scenario: Week header upload button is visible
- **WHEN** a week section is expanded in the Conversions page hierarchy
- **THEN** the week header SHALL display an Upload button alongside the stats bar

#### Scenario: Month header upload button is visible
- **WHEN** a month section is shown in the Conversions page hierarchy
- **THEN** the month header SHALL display an Upload button alongside the stats bar

### Requirement: Bulk upload opens a Dialog confirm modal
Clicking an Upload button on a week or month header SHALL open a `Dialog` confirm modal before any upload is triggered.

#### Scenario: Modal shows count and scope
- **WHEN** the user clicks a week or month Upload button
- **THEN** a `Dialog` modal SHALL open displaying the count of pending conversions in that time bucket (e.g. "Upload 8 pending conversions in W17 Apr 21–27?")
- **THEN** the modal SHALL display Confirm and Cancel buttons

#### Scenario: Modal shows dry-run warning when applicable
- **WHEN** the Dialog modal is open and at least one conversion type in the bucket has `dry_run: true` in `gads_conversion_config`
- **THEN** the modal SHALL display: "⚠ One or more conversion types are in dry-run mode — those uploads will be simulated, not sent to Google Ads"

#### Scenario: Cancelling the modal takes no action
- **WHEN** the user clicks Cancel in the Dialog modal
- **THEN** the modal SHALL close
- **THEN** no upload request SHALL be sent

### Requirement: Confirming bulk upload shows a countdown toast
After the user confirms in the Dialog modal, the modal SHALL close and a Sonner `toast.custom()` SHALL appear with a `Progress` bar draining from 100% to 0% over 5 seconds and a Cancel button. When the countdown expires, the upload is triggered.

#### Scenario: Countdown toast appears after confirmation
- **WHEN** the user clicks Confirm in the Dialog modal
- **THEN** the modal SHALL close immediately
- **THEN** a toast SHALL appear showing "Uploading N conversions in 5s…" with a `Progress` bar and Cancel button

#### Scenario: Cancelling the toast stops the upload
- **WHEN** the user clicks Cancel in the countdown toast
- **THEN** the toast SHALL be dismissed
- **THEN** no upload request SHALL be sent

#### Scenario: Countdown expiry triggers scoped upload
- **WHEN** 5 seconds elapse in the countdown toast without cancellation
- **THEN** the system SHALL call `google-ads-conversion-upload` with `{ estimate_ids: [list of all estimate IDs in the time bucket] }`
- **THEN** the page SHALL refetch pipeline data after the response

### Requirement: Bulk upload scope is limited to the time bucket's estimate IDs
The bulk upload SHALL pass the explicit list of `estimate_id` values from the time bucket to the edge function. It SHALL NOT use a date range filter.

#### Scenario: Only bucket estimates are uploaded
- **WHEN** a week upload is triggered for W17
- **THEN** the request body SHALL contain `estimate_ids` equal to all estimate IDs in W17
- **THEN** estimates from other weeks SHALL NOT be uploaded