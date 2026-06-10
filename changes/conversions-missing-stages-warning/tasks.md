<!-- This change documents features already implemented in the working tree; tasks are marked complete. -->

## 1. Shared helper

- [x] 1.1 Create `src/components/conversions/lib/missingStages.ts` exporting `getMissingStages(row)` that returns the undiscovered stages preceding the latest discovered stage (sequential gap rule — a trailing undiscovered stage is not reported)

## 2. Pipeline row warning

- [x] 2.1 Import `AlertTriangle` and `getMissingStages` in `PipelineRowItem.tsx`
- [x] 2.2 Add `MISSING_STAGE_COUNT_COLOR` map (1 → `#f5c518`, 2 → `#ff8a3d`, 3 → `#ee5d50`)
- [x] 2.3 Compute `missingStages` from the row and render the orange triangle + color-scaled count after the customer name when non-empty
- [x] 2.4 Add a tooltip listing the named missing stages

## 3. Channel rollup warning

- [x] 3.1 Import `AlertTriangle`, tooltip primitives, and `getMissingStages` in `SourceGroupBlock.tsx`
- [x] 3.2 Derive unique channel estimates (dedupe events by `estimate_id` in all-mode, use rows otherwise) and compute `missingConversions` and affected-estimate count
- [x] 3.3 Render the orange triangle + total missing-conversions count after the channel estimate count, with a tooltip stating the total and affected/total estimates

## 4. All-mode missing-stage display

- [x] 4.1 Add an `isMissing` prop to `StageDetail` that renders a collapsed summary with an orange `AlertTriangle` and orange label
- [x] 4.2 In `PipelineRowItem`'s `ExpandedPanel`, render missing (gap) stages in all-mode and pass `isMissing` only when in all-mode

## 5. HousecallPro detail-panel links

- [x] 5.1 In `EstimateOptionsTable.tsx`, move the `ExternalLink` icon inline after the option name and remove the standalone trailing column + its header
- [x] 5.2 In `JobDetailSection.tsx`, import `ExternalLink` and add a job deep-link icon next to the job ID pointing at `https://pro.housecallpro.com/app/jobs/{job.id}`

## 6. Verification

- [x] 6.1 Confirm the row warning appears only on a sequential gap (earlier stage missing while a later one exists) and not for trailing undiscovered stages
- [x] 6.2 Confirm the channel total counts each estimate once across view modes
- [x] 6.3 Confirm all-mode surfaces missing stages collapsed + orange, and single-stage filters are unchanged
