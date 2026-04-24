## Why

Conversion upload functionality is fragmented across three pages: `OnlineBookingsPage`, `CallsPage`, and `ConversionsPage`. The per-row upload buttons in bookings and calls use a legacy edge function (`gads-upload-booking`) that reads a single conversion action ID from an environment variable and bypasses the `gads_conversion_config` settings table entirely — meaning `enabled`, `dry_run`, and per-stage `conversion_action_id` settings have no effect on those uploads. Consolidating upload controls into the Conversions page removes the legacy path, unifies all uploads under the config-aware `google-ads-conversion-upload` function, and gives users richer per-stage control with countdowns and bulk upload scoping.

## What Changes

- **Remove** per-row "Conversion Upload" column and upload button from `OnlineBookingsPage` and `CallsPage` (includes removing `gads_upload_status` column from those tables).
- **Remove** `gads-upload-booking` edge function folder (`supabase/functions/gads-upload-booking/`). The `gads-upload-call` function never existed as a deployable function — only as a dead UI reference.
- **Extend** `google-ads-conversion-upload` edge function to accept an optional request body `{ estimate_ids?: string[], conversion_types?: string[] }` to support scoped single-cell and per-week/month uploads.
- **Add** `discover_pending_conversions_for_estimate(p_estimate_id text)` Postgres function scoped to a single estimate — called when a user clicks a null PhaseCell.
- **Add** interactive upload controls to `ConversionsPage`:
  - Per-cell hover-to-upload on `PhaseCell` (pending and error states): hover reveals upload icon, click starts a 5-second in-cell `Progress` bar countdown with Cancel; expiry triggers the scoped upload.
  - Null PhaseCell hover reveals Discover icon; click runs per-estimate discovery then refreshes.
  - Week and month header upload buttons that open a `Dialog` confirm modal showing count and dry-run warning, then a countdown toast with `Progress` bar and Cancel after confirmation.

## Capabilities

### New Capabilities
- `phase-cell-upload`: Interactive per-stage upload with hover state, in-cell countdown, and cancel support
- `bulk-upload-scoped`: Week/month header upload buttons with Dialog confirm modal and countdown toast
- `per-estimate-discovery`: On-demand conversion discovery scoped to a single estimate via null PhaseCell click

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **ConversionsPage.tsx**: `PhaseCell`, `PipelineStrip`, `PipelineRowItem`, month/week header buttons, new upload invocation logic
- **OnlineBookingsPage.tsx**: Remove `gads_upload_status` field, upload column header, upload button, `uploadingEstimate` state
- **CallsPage.tsx**: Remove `gads_upload_status` field, Conv. Upload column header, upload button, `uploadingCall` state
- **BookingManagerPage.tsx**: Same removals as OnlineBookingsPage (legacy file still present)
- **supabase/functions/gads-upload-booking/**: Delete folder
- **supabase/functions/google-ads-conversion-upload/index.ts**: Add optional `estimate_ids` / `conversion_types` body params to filter pending rows
- **supabase/migrations**: New migration for `discover_pending_conversions_for_estimate()`
