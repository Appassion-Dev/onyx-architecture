## Why

The Conversions page currently shows all three pipeline stages as a unified strip regardless of which funnel step you're viewing, and groups/aggregates rows by `estimate_created_at` for every tab. This is incoherent: an estimate *created* in January that was *qualified* in April appears under January in the Qualified tab, monetary values use a single `display_value` column regardless of context, and all three upload cells are always visible even when you're triaging a single stage. The page needs to become context-aware — each conversion type tab should drive what date, value, and action are shown.

## What Changes

- **BREAKING**: Remove the "All" and "Closed" step tabs. The step selector becomes a required mode selector with four tabs: Pre-discovery, Booking, Qualified, Converted.
- The active tab determines the **hierarchy date field** used for month/week grouping: `estimate_created_at` for Pre-discovery, `booking_datetime` for Booking, `qualified_datetime` for Qualified, `converted_datetime` for Converted.
- The **Value column** becomes tab-aware: Booking and Pre-discovery show `—`; Qualified shows `qualified_value` (AVG of all options); Converted shows `converted_value` (SUM of approved).
- The **Pipeline column** is replaced by a single upload cell (`PhaseCell`) for the active stage. Pre-discovery shows no cell.
- The **zero-value filter** checks the tab-relevant value field (not always `display_value`). The toggle is hidden on Booking and Pre-discovery tabs.
- The **rollup totals** (month/week headers) sum the tab-relevant value field.
- The **expanded detail panel** shows the active stage's section expanded and the other two collapsed (status badge + value only). Collapsed sections remain visible for cross-reference.
- The **GCLID coverage stat** and **bulk upload** scope to the active stage.
- The default tab on page load is **Qualified**.
- Pre-discovery tab shows a simplified row layout (no Pipeline or Value columns).

## Capabilities

### New Capabilities
- `conversion-view-mode`: The step tabs become a required mode selector that drives date grouping, value display, upload action, and detail panel layout for the entire Conversions page.

### Modified Capabilities
- `conversions-filter-bar`: Step selector changes from optional row filter (with "All" default) to required mode selector (no "All" or "Closed" options; defaults to "Qualified").
- `conversions-fiscal-grouping`: Date field used for grouping is no longer always `estimate_created_at`; it is selected per active mode.
- `conversions-filtered-totals`: Value column and rollup sums use the mode-appropriate value field (`qualified_value` or `converted_value`) rather than always `display_value`. Zero-value toggle scopes to the mode-relevant field.
- `conversion-pipeline-ui`: Pipeline column replaced by single-stage upload cell; detail panel shows primary section expanded and secondary sections collapsed.

## Impact

- `horizon-dashboard/src/components/pages/ConversionsPage.tsx`: Major refactor — `stepFilter` state becomes `conversionMode`, `getRowDateKeys` becomes mode-aware, `computeStats` becomes mode-aware, `PipelineStrip` replaced by mode-gated single `PhaseCell`, detail panel gets collapse/expand per section, zero-value filter updated.
- `openspec/specs/conversions-filter-bar/spec.md`: Delta spec required.
- `openspec/specs/conversions-fiscal-grouping/spec.md`: Delta spec required.
- `openspec/specs/conversions-filtered-totals/spec.md`: Delta spec required.
- `openspec/specs/conversion-pipeline-ui/spec.md`: Delta spec required.
