## Context

The conversions dashboard queries `vw_gads_conversion_pipeline`, a view whose final WHERE clause gates rows on the existence of a `gads_conversion_uploads` row. This means estimates are invisible in the dashboard until the discovery cron fires (or the user manually triggers per-estimate discovery). In the current dataset, 258 of 498 recent estimates are invisible despite having jobs, customer records, and quote data that is operationally relevant.

The pipeline itself (discovery functions, cron, upload edge function) is not broken — it correctly discovers and uploads conversions. The problem is purely in the display layer: the view's gate couples "has been processed" with "should be visible."

## Goals / Non-Goals

**Goals:**
- All estimates are visible in the conversions dashboard immediately, with null stage columns for undiscovered ones
- Job context (`job_id`, `invoice_number`, `job_work_status`, `job_total`) is surfaced per estimate
- Time-window filtering is controlled by the frontend query, not baked into the view
- Zero disruption to the existing pipeline: no changes to `gads_conversion_uploads`, discovery functions, cron, or upload edge function

**Non-Goals:**
- Changes to discovery logic or upload criteria
- Per-user or configurable time windows (90 days is the intended window; it just lives at query time)
- Pagination or cursor-based loading (the ~500 row count at 90 days doesn't warrant it yet)
- Changes to how conversions are uploaded to Google Ads

## Decisions

### Decision 1: Drop the filter gate, keep the same view structure

**Chosen**: Replace `vw_gads_conversion_pipeline` with `vw_conversion_candidates` — identical LEFT JOINs to `gads_conversion_uploads` for each stage, but without the final `WHERE book.id IS NOT NULL OR qual.id IS NOT NULL OR conv.id IS NOT NULL`.

**Alternative considered**: Keep the pipeline view and add a separate pre-discovery view, then UNION or client-merge. Rejected: adds a second query and shape-normalization burden on the frontend for no benefit. The unified approach gives one query, one shape, no merge.

### Decision 2: Resolve job context via LATERAL through estimate_options

**Chosen**: `jobs.original_estimate_id` references `estimate_options.id`, not `estimates.id` directly. A LATERAL subquery resolves this:
```sql
LEFT JOIN LATERAL (
  SELECT j.id, j.invoice_number, j.work_status, j.total_amount
  FROM jobs j
  JOIN estimate_options eo ON eo.id = j.original_estimate_id
  WHERE eo.estimate_id = e.id
  ORDER BY j.created_at DESC LIMIT 1
) job_agg ON true
```
`LIMIT 1` picks the most recent job if multiple exist.

**Alternative considered**: Denormalize via a join through `estimate_options`. Same result but harder to read.

### Decision 3: 90-day filter at query time, not in view

**Chosen**: No time filter in the view. Frontend sends `.gte('estimate_created_at', ninetyDaysAgo)`.

**Rationale**: Baking a `NOW() - INTERVAL '90 days'` filter in the view makes it impossible to query historical data without a migration. The frontend already controls ordering; controlling the window is a natural extension.

### Decision 4: Keep `is_closed` in the view

**Chosen**: Retain the `is_closed` boolean computed in SQL:
```sql
(
    (book.status IS NULL OR book.status IN ('uploaded', 'skipped'))
    AND (qual.status IS NULL OR qual.status IN ('uploaded', 'skipped'))
    AND (conv.status IS NULL OR conv.status IN ('uploaded', 'skipped'))
    AND (book.status IS NOT NULL OR qual.status IS NOT NULL OR conv.status IS NOT NULL)
) AS is_closed
```
For pre-discovery rows (all stage statuses NULL), the last condition (`at least one IS NOT NULL`) makes `is_closed = false`. This is correct — an undiscovered estimate is not closed.

### Decision 5: `display_value` follows existing pipeline logic

**Chosen**: `display_value = SUM(approved estimate_options) / 100.0` — same as the current pipeline view. No change to value calculation semantics.

## Risks / Trade-offs

**[Risk] Pre-discovery estimates with no source signals now appear** → This is intentional per the change goal. Operationally, staff can see all recent estimates. If the signal-less estimates are noisy, a frontend filter (e.g., "hide rows with no stage and no signals") can be added as a follow-up without touching the view.

**[Risk] Performance: scanning all estimates vs. only pipeline-filtered ones** → At ~500 rows per 90 days the LATERAL subqueries (options agg, job, callrail) add negligible cost. Existing indexes on `estimate_options.estimate_id`, `callrail_leads.estimate_id`, and `jobs` via `estimate_options` cover the lookups. Monitor if estimate volume grows significantly.

**[Risk] `vw_gads_conversion_pipeline` is dropped** → Any code referencing that view name breaks. Search confirms only `ConversionsPage.tsx` references it in the frontend. Backend pipeline functions (`discover_pending_conversions`, upload functions) query `gads_conversion_uploads` directly — they do not use the view.

## Migration Plan

1. New migration: `DROP VIEW vw_gads_conversion_pipeline` → `CREATE VIEW vw_conversion_candidates` with the full new definition.
2. Update `ConversionsPage.tsx`: change `.from('vw_gads_conversion_pipeline')` to `.from('vw_conversion_candidates')`, add `.gte` filter, extend `PipelineRow` interface with job fields.
3. No rollback complexity — the pipeline table is untouched. Revert is: re-apply the previous view migration.

## Open Questions

- Should the view be granted to `anon` role as well, or only `authenticated` + `service_role`? (Current pipeline view grants both `authenticated` and `service_role`; same policy should apply here.)
- Future: if estimate volume grows past a few thousand per 90 days, an index on `estimates.created_at` may be warranted for the frontend time-filter. Currently `idx_estimates_updated_at_company` exists but not a plain `created_at` index.
