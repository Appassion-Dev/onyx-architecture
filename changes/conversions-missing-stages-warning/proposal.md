## Why

When reviewing the conversions rollup, there was no way to tell at a glance which estimates still had conversion stages that hadn't been discovered (booking / qualified / converted). Operators had to expand each row to find the "Not discovered" stages, and there was no channel-level signal of how much discovery work remained. At the same time, the expanded detail tables linked to HousecallPro inconsistently — the estimate-option link sat in a trailing column away from the option it referenced, and jobs had no deep link at all.

## What Changes

- Add a warning indicator (orange `AlertTriangle`) on each `PipelineRowItem` header, immediately after the customer name, shown when the estimate has a *sequential gap* — an undiscovered stage that precedes a discovered one (e.g. Qualified or Converted exists but Booking does not). Trailing undiscovered stages (normal in-progress flow) do NOT warn.
- Next to the row indicator, show a count of how many earlier stages are missing (1 or 2), color-coded yellow / orange by severity, with a tooltip naming the specific missing stages.
- Propagate the warning to the channel (source-group) rollup header, after the channel's estimate count, showing the **total missing conversions** summed across all estimates in that channel, with a tooltip giving the conversion total and the number of affected estimates.
- In all-mode, surface the missing (sequential-gap) stages in the expanded panel as collapsed stage summaries marked orange, so the gap is visible without switching to a single-stage filter.
- Relocate the estimate-option HousecallPro deep-link icon in `EstimateOptionsTable` so it sits inline directly after the option name (removing the standalone trailing column).
- Add a HousecallPro deep-link icon next to the job ID in `JobDetailSection`, following the existing `https://pro.housecallpro.com/app/jobs/{job_id}` convention.

## Capabilities

### New Capabilities
- `conversions-stage-discovery-warning`: Surfaces undiscovered conversion stages in the rollup — a per-estimate warning with a missing-stage count on each pipeline row, and an aggregate missing-conversions count on each channel rollup header.

### Modified Capabilities
- `conversions-qualified-enrichment`: Relocates the estimate-option HousecallPro deep-link icon so it sits inline directly after the option name (previously a standalone trailing column).
- `converted-evidence`: Adds a HousecallPro deep-link icon next to the job ID in the Converted Lead detail.

## Impact

- `src/components/conversions/lib/missingStages.ts` (new shared helper `getMissingStages`)
- `src/components/conversions/components/pipeline-row/PipelineRowItem.tsx` (row warning + count badge)
- `src/components/conversions/components/hierarchy/SourceGroupBlock.tsx` (channel rollup warning + aggregate count)
- `src/components/conversions/components/row-details/EstimateOptionsTable.tsx` (inline HCP link)
- `src/components/conversions/components/row-details/JobDetailSection.tsx` (job HCP link)
- No database, API, or dependency changes. Relies on existing `vw_conversion_candidates` columns (`booking_status`, `qualified_status`, `converted_status`).
