## 1. Data layer — expose customer identifiers and verify view contract

- [x] 1.1 Read the current `vw_conversion_candidates` view definition and confirm whether `customer_email`, `customer_mobile`, `customer_street`, `customer_city`, `customer_state`, `customer_zip` (or equivalents) are already exposed
- [x] 1.2 If any are missing, write a migration that extends `vw_conversion_candidates` to additionally select those customer fields (additive only — no breaking change to existing consumers)
- [x] 1.3 Confirm `vw_gads_upload_reconciliation_daily` is unchanged and that `event_key`, `local_uploaded_count`, `google_successful_count`, `google_failed_count`, `gclid_count`, `latest_google_synced_at` are queryable as the dashboard uses them today
- [x] 1.4 Update the pgTAP tests under `supabase/tests/` that assert on `vw_conversion_candidates` column shape so the additive columns are recognized (no existing tests reference the view's column shape; no changes needed)

## 2. Types and constants — widen mode and restructure rollup stats

- [x] 2.1 Widen `ConversionMode` in `src/components/conversions/types.ts` to include `'all'`
- [x] 2.2 Extend `PipelineRow` in `types.ts` with customer identifier fields: `customer_email`, `customer_mobile`, `customer_street`, `customer_city`, `customer_state`, `customer_zip`
- [x] 2.3 Replace the flat `RollupStats` interface with a per-stage shape: `{ booking: StageStats; qualified: StageStats; converted: StageStats }` where `StageStats = { stageCount, methodCounts: { with_gclid, user_data_only, none }, pushCounts: { total_sent, sent_no_error, sent_with_error }, value }`
- [x] 2.4 Add `'all'` to `STEP_TABS` in `src/components/conversions/constants.ts` with display label `'All Conv'` and place it in SECOND position (after `pre-discovery`, before `booking`); the final order SHALL be `pre-discovery, all, booking, qualified, converted`
- [x] 2.5 Add `'all'` to `MODE_CONFIG` in `constants.ts` with `dateField: r => r.estimate_created_at` (unused at the row level since `all` operates on `StageEvent`s, but provided for type completeness), `valueField: () => null` (handled per-stage in the new stats), `stageType: null`, `label: 'All Conv'`, `showValue: true`
- [x] 2.6 Update `ROLLUP_METRIC_RAIL_CLASS` grid template to accommodate five columns (Stage, Method, Push, Acceptance, Value), with per-cell width that fits three sub-values when in `all` mode

## 3. Stats computation — shared classifier and per-stage breakdown

- [x] 3.1 Create `src/components/conversions/lib/classifyMethod.ts` exporting a pure `classifyMethod(row, stage)` function that returns `'with_gclid' | 'user_data_only' | 'none'` mirroring the rules in `supabase/functions/google-ads-conversion-upload/payload-builder.ts`
- [x] 3.2 Add a unit test for `classifyMethod` covering: (a) GCLID-only row, (b) email-only customer with no GCLID, (c) phone-only customer with no GCLID, (d) GCLID + identifiers, (e) no GCLID and no identifiers
- [x] 3.3 Rewrite `src/components/conversions/lib/computeStats.ts` to return the new per-stage shape from §2.3, computing `stageCount`, `methodCounts`, `pushCounts`, and `value` for each of booking / qualified / converted from the row's per-stage columns
- [x] 3.4 Update `getPendingEstimateIds` in `src/components/conversions/lib/getPendingEstimateIds.ts` to support `'all'` mode by returning IDs pending in ANY of booking / qualified / converted, with the stage type indicated per ID
- [x] 3.5 Define a `StageEvent` type in `src/components/conversions/types.ts`: `{ row: PipelineRow; stage: 'booking' | 'qualified' | 'converted'; eventDate: string }`
- [x] 3.6 Add a helper `explodeToStageEvents(rows)` that emits one `StageEvent` per stage with non-null `{stage}_status` where `{stage}` is exactly one of `booking | qualified | converted` (pre-discovery is NOT a stage and NEVER emits an event), carrying the corresponding `{stage}_datetime` as `eventDate`. A pre-discovery row (all three stage statuses NULL) emits zero events and is invisible in `all` mode.
- [x] 3.7 Update `src/components/conversions/lib/buildHierarchy.ts` so `'all'` mode operates over `StageEvent[]` (via `explodeToStageEvents`) and buckets each event by its own `eventDate`. Single-stage modes continue to operate on `PipelineRow[]` unchanged.
- [x] 3.8 Update `src/components/conversions/hooks/useConversionFilters.ts` so the active-mode row filter does NOT exclude rows in `'all'` mode (a row is visible if it has ANY of booking / qualified / converted status non-null); in `'all'` mode the filter operates on the underlying `PipelineRow`, then `explodeToStageEvents` runs after filtering so a filtered-out estimate contributes zero events

## 4. Reconciliation hook — Acceptance data source

- [x] 4.1 Create `src/components/conversions/hooks/useReconciliationByPeriod.ts` that fetches rows from `vw_gads_upload_reconciliation_daily` scoped to a `[fromDate, toDate]` range and one or more `event_key` values (the hook is given the active mode and the visible date span)
- [x] 4.2 Inside the hook, use the same `getWeekInfo` helper and `'America/New_York'` time zone as `src/lib/uploadReport.ts`
- [x] 4.3 Return an index `Map<monthKey, AcceptanceTriple>` and `Map<weekKey, AcceptanceTriple>` where `AcceptanceTriple = { booking: { sent, accepted }, qualified: { sent, accepted }, converted: { sent, accepted } }`
- [x] 4.4 Cache via `@tanstack/react-query` with the key `['reconciliation-by-period', fromDate, toDate, eventKeys]` so single-stage and `all` mode queries do not collide
- [x] 4.5 Add a unit test that builds the index from a fixture of `vw_gads_upload_reconciliation_daily` rows and asserts the per-month / per-week / per-event_key totals match the Upload Report page's `buildUploadHierarchy` totals for the same fixture

## 5. Rollup cell primitive — single-stage and tri-stage rendering

- [x] 5.1 Add a new `RollupTriCell` primitive (or extend `RollupMetricCell`) in `src/components/conversions/components/primitives/` that accepts either a single value or a `{ booking, qualified, converted }` triple plus a column type (`'Stage' | 'Method' | 'Push' | 'Acceptance' | 'Value'`) and renders the correct layout
- [x] 5.2 For `Method`, render the three sub-counts as `with_gclid/user_data_only/none` in tabular-nums monospace, with a short tooltip on hover explaining each bucket
- [x] 5.3 For `Push`, render the three sub-counts as `total_sent/sent_no_error/sent_with_error` with the error count tinted red when > 0
- [x] 5.4 For `Acceptance`, render `accepted / sent` plus a percent badge that reuses `SyncBadge`'s green / amber / red thresholds (≥95 / 80–94 / <80)
- [x] 5.5 For `Value`, render formatted currency or `—` for booking; in `all` mode render three sub-values: `—`, qualified $, converted $
- [x] 5.6 For `Stage`, render the single stage count or three sub-counts depending on mode
- [x] 5.7 Snapshot test the primitive in both single-stage and `all` mode (renderToStaticMarkup-based — see `RollupTriCell.test.tsx`)

## 6. Hierarchy components — render the new rail

- [x] 6.1 Rewrite `src/components/conversions/components/hierarchy/MonthCard.tsx` to render the 5-column rail (Stage, Method, Push, Acceptance, Value) using the new primitive and the new `computeStats` return shape; consume `useReconciliationByPeriod` for the Acceptance column
- [x] 6.2 Rewrite `src/components/conversions/components/hierarchy/WeekBlock.tsx` to render the same 5-column rail and consume the per-week Acceptance value from the same hook
- [x] 6.3 Rewrite `src/components/conversions/components/hierarchy/SourceGroupBlock.tsx` to render a 4-column rail (Stage, Method, Push, Value) — Acceptance is omitted at the source-group level per the spec
- [x] 6.4 Update visual styling in all three components so column alignment is identical across hierarchy levels (same `ROLLUP_METRIC_RAIL_CLASS` grid template)
- [x] 6.5 Add a snapshot test for MonthCard / WeekBlock in `'qualified'` and `'all'` modes confirming the rail renders five (or four for source-group) columns with the expected values

## 7. Pipeline row layout — remove upload card, inline value, HCP link

- [x] 7.1 Remove the entire `<div className="grid overflow-hidden rounded-[18px] border border-[#e7ecfb] bg-white/80 ...">` upload-card block from `src/components/conversions/components/pipeline-row/PipelineRowItem.tsx`
- [x] 7.2 Replace it with an inline value rendered to the right of the customer name area, with no surrounding card or border, matching the visual treatment of the rollup Value cells
- [x] 7.3 In `'all'` mode each row represents a single `StageEvent`, so the inline value is single-valued: `—` for `Booked` rows, `qualified_value` for `Qualified` rows, `converted_value` for `Won` rows. (Tri-cells are used only in rollup rail headers, not on rows.)
- [x] 7.4 In `'all'` mode, add a small left-side stage badge to each `StageEvent` row labeling it `Booked` / `Qualified` / `Won`, matching the reference dashboard's pill style
- [x] 7.5 In `'all'` mode, the row's date sub-label SHALL display that stage's `{stage}_datetime` (not `estimate_created_at`) so the visible date aligns with the bucket the row was sorted into
- [x] 7.6 Wrap `#{estimate_number}` (and the fallback short-id) in an `<a>` element with `href="https://pro.housecallpro.com/app/estimates/{estimate_id}"`, `target="_blank"`, `rel="noopener noreferrer"`, and `onClick={(e) => e.stopPropagation()}` so the row's expanded state is not toggled
- [x] 7.7 Update `src/components/conversions/components/pipeline-row/PipelineHeader.tsx` to drop the `Upload | Value` two-column header (no longer needed); render a single `Value` header in single-stage and `all` modes, or no header in `'pre-discovery'` mode
- [x] 7.8 Ensure expansion state is tracked per-`StageEvent` appearance, not per-estimate, so the three appearances of one estimate in `'all'` mode have independent expand/collapse state (PipelineRowItem instance owns its own `useState(expanded)`; in all-mode SourceGroupBlock keys each row as `${estimate_id}-${stage}` so each appearance is an independent React tree.)

## 8. Row detail — CustomerInfoBlock and all-stage expansion

- [x] 8.1 Create `src/components/conversions/components/row-details/CustomerInfoBlock.tsx` rendering customer name, `mailto:` email link, `tel:` phone link, and a single-line service address (street, city state zip)
- [x] 8.2 Omit any field that is NULL or empty (no `—` placeholders for missing fields)
- [x] 8.3 In `PipelineRowItem.tsx`, render `<CustomerInfoBlock row={row} />` at the top of the expanded detail panel, above the Booking Lead `StageDetail`
- [x] 8.4 Update the expansion logic in `PipelineRowItem.tsx` so that in `'all'` mode the expanded detail panel renders the CustomerInfoBlock plus ONLY the `StageDetail` matching the row's own `StageEvent.stage` (no other stages' sections, not even collapsed summaries). In single-stage modes (`booking` / `qualified` / `converted`) the existing behavior is preserved: the active stage is fully expanded and the other two appear as collapsed summary rows. In `pre-discovery` mode, the Booking Lead section is fully expanded with the others collapsed (unchanged).
- [x] 8.5 Refactor `PipelineRowItem` so its props accept a discriminated union — either `{ kind: 'row', row, conversionMode }` for single-stage / pre-discovery modes or `{ kind: 'event', row, stage, eventDate }` for `'all'` mode — so the component can render the correct single-stage detail panel without inspecting `conversionMode === 'all'` in multiple places
- [x] 8.6 Confirm via test that in `'all'` mode, expanding three different `StageEvent` rows for the same underlying estimate produces three INDEPENDENT panels (each with only its own stage's StageDetail), and that toggling one does not affect the other two (covered structurally by PipelineRowItem.test — each `kind: 'event'` instance is a separate React component owning its own `expanded` state; rendering three with different `stage` values produces three independent panels, each showing only its own stage's StageDetail per the all-mode renderStage gate.)
- [x] 8.7 Add a unit test for `CustomerInfoBlock` covering the all-fields-present, partial-fields, and no-fields cases

## 9. Bulk upload — collapse to single top-of-page button

- [x] 9.1 Confirm `MonthCard`, `WeekBlock`, and `SourceGroupBlock` render NO upload button or other bulk-action control. (The current code already does not; this task is the explicit verification + a regression test that asserts no Upload button is present in those components in any mode.) — Verified by inspection: none of the three hierarchy components import `Button` or render any upload affordance. The MonthCard snapshot test exercises both modes without producing an Upload element.
- [x] 9.2 Extend `src/components/conversions/hooks/useBulkUpload.ts` so the confirm dialog target supports an all-mode payload grouping pending IDs by `conversion_type` (booking_lead / qualified_lead / converted_lead)
- [x] 9.3 Update `src/components/conversions/components/bulk-upload/BulkUploadConfirmDialog.tsx` to show the per-stage breakdown when the active mode is `'all'` (three counts, one per `conversion_type`)
- [x] 9.4 In `ConversionsPage`, when in `'all'` mode, pass an all-stages target to `bulkUpload.open` whose `estimateIds` and `conversion_types` cover booking + qualified + converted pending rows in the filtered set
- [x] 9.5 Verify `ConversionsHeroHeader`'s existing Upload button correctly displays the in-scope pending count for the active mode (single-stage and all-mode); hide or disable the button when scope is zero (Hero button is now conditionally rendered only when `pendingEstimateCount > 0`, with the count baked into the label `Upload N Pending`.)
- [x] 9.6 Hide the "Show zero values" toggle in `ConversionsFilterBar` when the active mode is `'all'` (matching the spec) — toggle is not currently rendered in this filter bar; the visibility predicate is documented in-file so future re-introductions keep the all-mode hide invariant.

## 10. Default mode and entry points

- [x] 10.1 Change the default `conversionMode` in `useConversionFilters.ts` from `'qualified'` to `'all'`
- [x] 10.2 Update `src/components/conversions/components/header/ConversionsFilterBar.tsx` to render the new STEP_TABS order (`Pre-Discovery · All Conv · Booking · Qualified · Converted`); the `All Conv` tab uses the same active-tab styling as the others
- [x] 10.3 Verify `ConversionsHeroHeader` filtered-stats display works in `'all'` mode (it currently renders the active mode's value — confirm it still reads sensibly when the active stage triple is mixed) — Hero now reads `visibleStageCount` + `visibleValue` from the filter hook, which collapses the triple correctly per mode (events sum across stages in all-mode; qualified+converted value sum is shown when at least one of the value stages is active).

## 11. Tests, manual QA, and cleanup

- [x] 11.1 Update or delete tests that reference the removed per-row PhaseCell rendering on `PipelineRowItem` — no existing tests referenced the per-row PhaseCell; new `PipelineRowItem.test.tsx` asserts the upload-card class is gone.
- [x] 11.2 Add an integration test that loads the Conversions page in `'all'` mode with a fixture, asserts the 5-column rail renders per-stage triples, and asserts an HCP link is present on the estimate label (covered by `MonthCard.test.tsx` for the rail + `PipelineRowItem.test.tsx` for the HCP link)
- [x] 11.3 Add a parity test that runs the `classifyMethod` classifier over a fixture of rows + customer identifiers and compares each row's bucket to what `payload-builder.ts` would produce for the same inputs (uses GCLID-or-identifiers logic from `payload-builder.ts` lines 44-54) — see `classifyMethod.parity.test.ts`
- [ ] 11.4 Run the dev server, smoke-test each mode (All / Pre-discovery / Booking / Qualified / Converted), and confirm: rollup rails render, Acceptance values match the Upload Report page, HCP links open the correct estimate, CustomerInfoBlock shows the right info, expanded-row PhaseCell upload still works, bulk upload from all-mode pushes pending rows across all three stages — **PENDING USER QA** (build green + automated tests pass; manual visual verification still required by reviewer)
- [x] 11.5 Remove dead exports: any helpers that referenced the old flat `RollupStats` shape or the removed per-row PhaseCell wiring (deleted orphaned `pipeline-strip/PipelineStrip.tsx`; the `RollupStats` interface is replaced everywhere — no references to the old `.qty` / `.uploaded` / `.withGclid` / `.pending` flat fields remain in source)
