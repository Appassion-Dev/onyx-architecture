## Why

The conversions dashboard only shows estimates that have already been processed by the discovery cron — roughly 240 of 498 recent estimates are invisible until the cron fires. By removing the filter gate from `vw_gads_conversion_pipeline` and replacing it with a unified view that LEFT JOINs upload state, all estimates appear immediately with null stage columns for undiscovered ones, while the existing pipeline functions and cron job require zero changes.

## What Changes

- **Replace `vw_gads_conversion_pipeline`** with `vw_conversion_candidates` — same column contract, same LEFT JOIN pivots for each stage, but the final `WHERE book.id IS NOT NULL OR qual.id IS NOT NULL OR conv.id IS NOT NULL` gate is dropped. All estimates are returned; stage columns are NULL when no upload row exists.
- **Add job fields** — a LATERAL subquery resolves the estimate → estimate_options → jobs path and surfaces `job_id`, `invoice_number`, `job_work_status`, and `job_total` on every row.
- **Remove 90-day filter from view** — time-window filtering is applied at query time from the frontend (`.gte('estimate_created_at', cutoff)`), keeping the view general-purpose.
- **Update `ConversionsPage.tsx`** — query target changes from `vw_gads_conversion_pipeline` to `vw_conversion_candidates`; add `.gte` time filter; `PipelineRow` interface gains job fields. No rendering logic changes — null stage columns already render as the dashed `—` PhaseCell today.
- **`is_closed` flag** — remains in the view, computed from stage states as today. For pre-discovery rows all stages are NULL, so `is_closed` will be `false` (no stages to close).

## Capabilities

### New Capabilities
- `conversion-candidates-view`: A unified DB view (`vw_conversion_candidates`) that surfaces all estimates with LEFT-joined upload stage state and resolved job context, with no discovery gate.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **`supabase/migrations/`**: One new migration replacing the pipeline view.
- **`horizon-dashboard/src/components/pages/ConversionsPage.tsx`**: Query target and `PipelineRow` interface updated; `.gte` time filter added.
- **`gads_conversion_uploads` table, all pipeline functions, cron job, edge functions**: No changes — the pipeline continues writing to `gads_conversion_uploads` exactly as today; the new view just reads from it without filtering.
- **`vw_gads_conversion_pipeline`**: Dropped and replaced by `vw_conversion_candidates`.
