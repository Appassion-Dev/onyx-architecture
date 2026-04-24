## Why

The pipeline-stage-criteria-v3 change redefines the three conversion stages (booking, qualified, converted) with broadened criteria, removes the jobs table dependency, and unifies the value formula. The Conversions dashboard must be updated in parallel to reflect the new view contract: dropped columns, new source badge taxonomy, unified display value, and corrected weekly totals. Additionally, `BookingManagerPage` should be renamed to `OnlineBookingsPage` to avoid confusion with the broader "booking lead" conversion stage.

## What Changes

- **Drop job columns**: Remove `job_id` and `job_invoice_number` from `PipelineRow` interface and all rendering in `ConversionsPage.tsx`.
- **Source badges**: Replace the single `booking_source` string ('form'/'call') with multi-source badge rendering. Sources come from: `has_form` (booking form), `call_count` (CallRail leads), `lead_source` (estimates.lead_source), and individual CallRail lead sources. Each applicable source renders as a separate badge.
- **Unified display value**: `display_value` is now always `SUM(approved estimate options / 100.0)`. Per-stage value columns (`booking_value`, `qualified_value`, `converted_value`) are dropped; all stages share the single `display_value`.
- **Weekly totals**: Sum `display_value` once per estimate (not per stage). The current `computeStats` already does this correctly since it iterates rows (one per estimate).
- **Rename BookingManagerPage → OnlineBookingsPage**: Rename the file, component, route (`/bookings` → `/online-bookings`), and sidebar nav item ("Bookings" → "Online Bookings").

## Capabilities

### New Capabilities
- `source-badges`: Multi-source badge display system showing all lead attribution signals (form, call, Google Ads, Google Local Services, etc.)
- `conversions-page-v3`: Updated ConversionsPage layout with dropped job columns, unified value, and new source badges
- `online-bookings-rename`: Rename BookingManagerPage to OnlineBookingsPage across routes, sidebar, and imports

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **ConversionsPage.tsx**: PipelineRow interface, column rendering, source display, value columns
- **BookingManagerPage.tsx → OnlineBookingsPage.tsx**: File rename, component rename, export name
- **App.tsx**: Route path change (`/bookings` → `/online-bookings`), import update
- **Sidebar.tsx**: Nav item name and path update
- **vw_gads_conversion_pipeline**: View must expose `has_form`, `lead_source`, `call_count` and drop `booking_source`, `job_id`, `job_invoice_number`, per-stage value columns (covered by pipeline-stage-criteria-v3)
