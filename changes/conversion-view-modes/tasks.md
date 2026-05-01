## 1. Mode Type and Config

- [x] 1.1 Replace `stepFilter: string` state with `conversionMode: ConversionMode` typed union (`'pre-discovery' | 'booking' | 'qualified' | 'converted'`), default `'qualified'`
- [x] 1.2 Define `MODE_CONFIG` lookup object with `dateField`, `valueField`, `stageType`, `label`, `showValue`, `showZeroToggle` per mode
- [x] 1.3 Update `STEP_TABS` array to remove "All" and "Closed" entries; update to 4 tabs matching `ConversionMode`
- [x] 1.4 Update `resetFilters` to set mode back to `'qualified'`

## 2. Date Field — Hierarchy Grouping

- [x] 2.1 Refactor `getRowDateKeys(row)` to `getRowDateKeys(iso: string | null)` — accepts a pre-resolved ISO string
- [x] 2.2 Update `buildHierarchy(rows, mode)` to resolve `MODE_CONFIG[mode].dateField(row)` and pass the result to `getRowDateKeys`

## 3. Value Field — Row and Rollup

- [x] 3.1 Update `computeStats(rows, mode)` to sum `MODE_CONFIG[mode].valueField(row)` instead of always `display_value`
- [x] 3.2 Update the Value cell in each table row to display `MODE_CONFIG[mode].valueField(row)` formatted as currency, or `—` when `showValue` is false
- [x] 3.3 Update the Value column header label if needed (no label change required; column hidden in pre-discovery)
- [x] 3.4 Hide the Value column and pipeline column entirely when mode is `pre-discovery` (simplified row layout)

## 4. Zero-Value Filter

- [x] 4.1 Update the zero-value filter predicate to check `MODE_CONFIG[mode].valueField(row) <= 0` instead of always `display_value`
- [x] 4.2 Conditionally hide the "Show zero values" toggle when `MODE_CONFIG[mode].showZeroToggle` is false (Pre-discovery and Booking modes)

## 5. Pipeline Column — Single PhaseCell

- [x] 5.1 Remove `PipelineStrip` component (or retain but no longer use it)
- [x] 5.2 In the table row, render a single `PhaseCell` for `MODE_CONFIG[mode].stageType` — passing the correct `status`, `uploadAttempts`, `uploadedAt`, `errorMessage`, `estimateId`, `isDryRun`, and (for qualified) `workStatus` props
- [x] 5.3 Hide the pipeline column when mode is `pre-discovery`

## 6. Bulk Upload — Stage-Scoped

- [x] 6.1 Update `getPendingEstimateIds(rows, mode)` to return only estimate IDs where the active mode's stage status is `'pending'`

## 7. Detail Panel — Primary + Collapsed Sections

- [x] 7.1 Add `isCollapsed?: boolean` prop to `StageDetail` component
- [x] 7.2 Implement collapsed rendering in `StageDetail`: when `isCollapsed` is true, render only a summary row (label + status badge + value if non-null); omit all sub-content
- [x] 7.3 Update the expanded detail panel in `PipelineRow` to pass `isCollapsed={true}` to all sections except the primary section for the active mode
- [x] 7.4 For `pre-discovery` mode, treat the Booking Lead section as primary (expanded by default)

## 8. GCLID Coverage Stat

- [x] 8.1 Update the GCLID coverage count and `missingGclidCount` to reference the active mode's stage GCLID field (`booking_gclid`, `qualified_gclid`, `converted_gclid`) rather than always `all_gclids`
- [x] 8.2 For Pre-discovery mode, use `all_gclids` (no stage-specific GCLID)

## 9. Retry Candidate Count

- [x] 9.1 Update `retryCandidateCount` to only count rows where the active mode's stage has `status = 'pending'` and `upload_attempts > 0`

## 10. Verification

- [x] 10.1 Verify Qualified mode: hierarchy groups by `qualified_datetime`, value shows `qualified_value`, single Qual cell, zero-value toggle present
- [x] 10.2 Verify Converted mode: hierarchy groups by `converted_datetime`, value shows `converted_value`, single Conv cell
- [x] 10.3 Verify Booking mode: hierarchy groups by `booking_datetime`, value shows `—`, single Book cell, zero-value toggle hidden
- [x] 10.4 Verify Pre-discovery mode: hierarchy groups by `estimate_created_at`, no pipeline or value column, simplified row
- [x] 10.5 Verify expanded row: primary section expanded, other two collapsed to summary rows
- [x] 10.6 Verify reset filters returns to Qualified mode
- [x] 10.7 Verify month/week rollup totals match active mode's value field
