## Why

When the `conversions-unified-view` change lands, pre-discovery estimates become visible in the conversions table. However, the expanded detail panel currently gates each stage section (`Booking Lead`, `Qualified Lead`) behind a `status != null` check — meaning a pre-discovery estimate expands to a nearly empty panel even when it has form submissions, CallRail calls, or estimate options worth reviewing. The panel should show all three stage sections unconditionally, displaying "No data detected" empty states where nothing exists, so operators can see attribution context and estimate state for every estimate regardless of discovery status.

## What Changes

- **Unconditional Booking Lead section**: Remove the `row.booking_status != null` gate. The Booking Lead section renders for all rows. When `booking_status` is null, the `StageDetail` header shows a neutral "Not discovered" state. `BookingTagsTable` and `CallHistoryTable` already handle their own empty states ("No tags identified", null render) — those are shown as-is. When both tables have no data, a single "No attribution data detected" message is shown instead.
- **Unconditional Qualified Lead section**: Remove the `row.qualified_status != null` gate. The Qualified Lead section renders for all rows. `EstimateOptionsTable` already renders "No estimate options found" when empty — that empty state is surfaced here.
- **Converted Lead section**: Already renders unconditionally (it has a null-status branch showing `— Converted Lead`). No change needed.
- **Job section**: Already renders unconditionally ("No job created yet" when empty). No change needed.
- **`StageDetail` null-status handling**: `StageDetail` currently requires a non-null `status` string — it must be updated to accept `null` and render a neutral "Not discovered" state (no icon, muted label) when status is null.

## Capabilities

### New Capabilities
- `pre-discovery-stage-sections`: Unconditional rendering of all three stage sections in the expanded detail panel, with appropriate empty states for pre-discovery estimates.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **`ConversionsPage.tsx`**: Two conditional gates removed (`booking_status != null`, `qualified_status != null`); `StageDetail` props type for `status` loosened from `string` to `string | null`; empty-state fallback added to Booking Lead section when both form and call data are absent.
- **No DB changes**: This is a pure frontend rendering change; depends on `conversions-unified-view` landing first so pre-discovery rows actually appear.
- **No pipeline changes**: Discovery functions, cron, and upload edge functions are untouched.
