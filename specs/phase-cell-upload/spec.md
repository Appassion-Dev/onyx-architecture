# phase-cell-upload

## Purpose

Define the PhaseCell upload affordance in the conversion pipeline: hover-to-upload behavior, the in-cell countdown that triggers an upload, dry-run surfacing, and lifecycle-driven chip rendering including muted (no_alert) styling.

## Requirements

### Requirement: PhaseCell shows upload action on hover for queued and needs-attention states

A `PhaseCell` with `lifecycle === 'queued'`, `lifecycle === 'retrying'`, or `lifecycle === 'needs-attention'` SHALL display an upload icon when the user hovers over the cell, replacing the status icon. Cells with any other `lifecycle` value SHALL NOT change appearance on hover.

#### Scenario: Hover reveals upload icon on queued cell

- **WHEN** a user hovers over a PhaseCell whose joined view row has `lifecycle === 'queued'` or `lifecycle === 'retrying'`
- **THEN** the cell SHALL display an upload arrow icon in place of the lifecycle icon

#### Scenario: Hover reveals upload icon on needs-attention cell

- **WHEN** a user hovers over a PhaseCell with `lifecycle === 'needs-attention'`
- **THEN** the cell SHALL display an upload arrow icon indicating retry

#### Scenario: Hover has no effect on sent, excluded, expired, failed, or null cells

- **WHEN** a user hovers over a PhaseCell with `lifecycle` in `('sent', 'excluded', 'expired', 'failed')` or with no row
- **THEN** the cell SHALL NOT change its icon or appearance

### Requirement: Clicking an actionable PhaseCell starts a 5-second in-cell countdown

After clicking an upload-ready PhaseCell (`lifecycle` in `('queued', 'retrying', 'needs-attention')`), the cell SHALL display an animated `Progress` bar draining from 100% to 0% over 5 seconds using the dashboard's `Progress` component. A Cancel button SHALL appear below the progress bar. When the countdown expires without cancellation, the upload SHALL be triggered.

#### Scenario: Countdown starts on click

- **WHEN** a user clicks a PhaseCell with `lifecycle` in `('queued', 'retrying', 'needs-attention')`
- **THEN** the cell SHALL immediately show a `Progress` bar at 100% with `transition-all duration-[5000ms]` animating to 0%
- **THEN** a Cancel button SHALL appear in or below the cell

#### Scenario: Cancelling stops the countdown

- **WHEN** a user clicks Cancel during the 5-second countdown
- **THEN** the countdown SHALL be stopped
- **THEN** the cell SHALL revert to its normal lifecycle display
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

### Requirement: PhaseCell chip renders per lifecycle value

The PhaseCell SHALL render its chip (icon, color, sub-text) based on the joined `vw_gads_conversion_uploads.lifecycle` value, not the legacy `status` column. The mapping SHALL be:

| `lifecycle`        | Icon                   | Color                | Sub-text                                            |
|--------------------|------------------------|----------------------|-----------------------------------------------------|
| `queued`           | Clock                  | amber `#ffb547`      | "Queued"                                            |
| `sending`          | Animated spinner       | amber `#ffb547`      | "Sending…"                                          |
| `sent`             | CheckCircle2           | green `#01b574`      | localized `uploaded_at` date (`MMM D` in NY tz)     |
| `retrying`         | Clock with retry glyph | amber `#ffb547`      | `Attempt ${attempt_count}/${max_attempts ?? '∞'}`   |
| `needs-attention`  | AlertTriangle          | red `#ee5d50`        | abbreviated `error_code` (segment after the dot)    |
| `failed`           | XCircle                | red `#ee5d50`        | abbreviated `error_code`, or "Failed" if `no_alert` |
| `excluded`         | MinusCircle            | gray `#a3aed0`       | "Excluded"                                          |
| `expired`          | Clock-strikethrough    | gray `#a3aed0`       | "Expired"                                           |
| (no row)           | em dash                | dashed gray border   | empty                                               |

#### Scenario: Sent cell renders green check with date

- **WHEN** a row has `lifecycle = 'sent'` and `uploaded_at = 2026-05-18T18:02:00Z`
- **THEN** the cell SHALL render a green CheckCircle2 icon
- **THEN** the sub-text SHALL be "May 18" (or the equivalent in America/New_York)

#### Scenario: Needs-attention cell renders red triangle

- **WHEN** a row has `lifecycle = 'needs-attention'` and `error_code = 'conversionUploadError.CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS'`
- **THEN** the cell SHALL render a red AlertTriangle icon
- **THEN** the sub-text SHALL be the abbreviated last segment (e.g., `"CUSTOMER_NOT_AC…"` truncated to fit)

#### Scenario: Retrying cell shows attempt count

- **WHEN** a row has `lifecycle = 'retrying'`, `attempt_count = 2`, and joined `max_attempts = 5`
- **THEN** the cell sub-text SHALL be `"Attempt 2/5"`

- **WHEN** a row has `lifecycle = 'retrying'`, `attempt_count = 2`, and joined `max_attempts = NULL`
- **THEN** the cell sub-text SHALL be `"Attempt 2/∞"`

### Requirement: no_alert mutes the chip rendering

When the joined `no_alert = true` for the row's `error_code`, the PhaseCell SHALL render in a subdued style: gray icon and text, no badge weight, no animation — regardless of the underlying `lifecycle`. A hover tooltip SHALL surface the full `error_code` and the `human_action` text.

#### Scenario: Muted cell renders subdued

- **WHEN** a row has `lifecycle = 'failed'` and joined `no_alert = true` (e.g., a `drop`+`no_alert` disposition like `EXPIRED_EVENT`)
- **THEN** the cell SHALL render with gray icon and gray text, not red

#### Scenario: Muted cell tooltip shows context

- **WHEN** a user hovers a muted cell
- **THEN** the tooltip SHALL show the full namespaced `error_code` and the joined `human_action` text

### Requirement: PhaseCell is not rendered in the per-row pipeline column
The PhaseCell SHALL NOT be rendered inside the per-estimate row layout of `PipelineRowItem`. The row layout SHALL show the estimate label and inline value only — no framed upload card on the right side. The PhaseCell continues to render inside the expanded StageDetail panel, where it provides the row-level upload affordance.

#### Scenario: Collapsed row has no PhaseCell
- **WHEN** a PipelineRowItem is rendered in any conversion mode and is NOT expanded
- **THEN** no PhaseCell SHALL appear on the row

#### Scenario: Expanded row exposes per-stage PhaseCell
- **WHEN** a PipelineRowItem is expanded and the StageDetail panel is rendered for a stage with an actionable status (`pending` or error)
- **THEN** the StageDetail panel SHALL include a PhaseCell for that stage, retaining all PhaseCell hover / countdown / dry-run behavior described in the other requirements of this capability

#### Scenario: PhaseCell is removed from `pre-discovery` and other layouts
- **WHEN** the active mode is `pre-discovery`, `booking`, `qualified`, `converted`, or `all`
- **THEN** no PhaseCell SHALL appear in the row's top-level grid (regardless of mode)
