## 1. Update StageDetail Component

- [x] 1.1 Change the `status` prop type on `StageDetail` from `string` to `string | null`. Guard the `statusLabel` derivation (currently `status.charAt(0).toUpperCase() + status.slice(1)`) so it does not throw when `status` is `null` — render "Not discovered" in muted text (`text-[#a3aed0]`) instead.
- [x] 1.2 When `status` is `null`, suppress all detail fields (GCLID, value, date, upload attempts, error message) — render only the stage label and the "Not discovered" status line.

## 2. Remove Stage Section Gates in PipelineRowItem

- [x] 2.1 Remove the `{row.booking_status != null && (...)}` conditional wrapper from the Booking Lead section. The section should always render.
- [x] 2.2 Remove the `{row.qualified_status != null && (...)}` conditional wrapper from the Qualified Lead section. The section should always render, passing `EstimateOptionsTable` unconditionally.

## 3. Add Consolidated Empty State for Booking Lead

- [x] 3.1 In the Booking Lead section's attribution subtable area, replace the two independent checks (`has_form ? <BookingTagsTable> : "No form submission recorded"` and `call_count > 0 ? <CallHistoryTable> : "No calls recorded"`) with a three-branch pattern: if neither form nor calls exist, render a single "No attribution data detected" message; otherwise render whichever subtables have data with their existing individual empty states.

## 4. Validate

- [x] 4.1 With `conversions-unified-view` applied locally, expand a pre-discovery estimate and confirm all three stage sections render, `StageDetail` shows "Not discovered" for null stages without errors, and the Booking Lead section shows "No attribution data detected" when the estimate has no form or calls.
- [x] 4.2 Expand a fully-discovered estimate and confirm the expanded panel is visually identical to its current state — no regression in stage detail, form tags, call history, options, or job sections.
