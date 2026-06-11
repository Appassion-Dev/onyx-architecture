## 1. Method classifier

- [x] 1.1 In `lib/classifyMethod.ts`, add `classifyRowMethod(row, stage): 'gclid_ecl' | 'gclid_only' | 'ecl_only' | 'none'`, reusing the existing `stageGclid` and `hasUserIdentifier` helpers. Leave the 3-bucket `classifyMethod` untouched.
- [x] 1.2 Add unit tests in `lib/classifyMethod.test.ts` covering all four cases (gclid+identifier, gclid-only, identifier-only, neither) across at least one stage.

## 2. Per-row Method cell

- [x] 2.1 In `PipelineRowItem.tsx`, replace the GCLID-count badge in the Method cell with one tag derived from `classifyRowMethod(row, stageKey)` (reuse the existing `stageKey` resolution). Render GCLID+ECL (light green), GCLID (purple), ECL (light blue), or a dash.
- [x] 2.2 Keep the `all_gclids` hover tooltip on the GCLID+ECL and GCLID tags only; show no GCLID tooltip on the ECL tag.

## 3. Per-row lead-source + call/booking tags

- [x] 3.1 In `PipelineRowItem.tsx`, after the customer name in the label cluster, render a light-colored `lead_source` tag when `lead_source` is non-empty.
- [x] 3.2 Render a light-colored call/booking tag: `first_touch_medium = 'call'` → Call, `'form'` → Booking, else fall back to `has_form` → Booking then `call_count > 0` → Call; render nothing when none resolve.
- [x] 3.3 Verify the tags wrap correctly alongside the existing missing-stage warning within the `flex-wrap` label cluster.

## 4. Rollup Method label

- [x] 4.1 In `RollupTriCell.tsx`, update the Method `SUBLABELS` entry and `METHOD_TOOLTIP` text to the GCLID+ECL / ECL / none terminology. Do not change the counts or their computation.

## 5. Verify

- [x] 5.1 Run the conversions test suite (`classifyMethod` tests, `PipelineRowItem`/`RollupTriCell` tests) and the typecheck; fix any failures. (30 tests pass; `vite build` succeeds — no standalone tsc in repo.)
- [x] 5.2 Manually confirm in the dashboard: per-row tags render across all-stages and single-stage modes, and the rollup Method sublabel/tooltip read with the new terminology.
