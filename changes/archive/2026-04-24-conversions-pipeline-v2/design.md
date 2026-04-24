## Context

The `vw_gads_conversion_pipeline` view (created in `conversions-pipeline-pivot`) joins `estimates` → `gads_conversion_uploads` (3 pivoted LEFT JOINs), `customers`, `jobs`, `estimate_options`, `estimates_settings`, and `callrail_leads`. The callrail and estimate_options joins are 1:N, causing row duplication. The frontend currently renders flat pipeline status icons (CheckCircle2/Clock/XCircle/MinusCircle) with no visual connection between phases and no call history.

Tech stack: Supabase Postgres (local Docker), React + TypeScript + TanStack Query + shadcn/ui + Tailwind v4 + Lucide icons. No animation library installed (CSS transitions only).

## Goals / Non-Goals

**Goals:**
- Guarantee exactly one row per estimate in the pipeline view (fix 1:N joins)
- Surface call count per estimate in the main table
- Show full call history in the expanded detail panel via lazy-loaded query
- Visually represent Booking → Qualified → Converted as a connected pipeline with status and data baked in

**Non-Goals:**
- Changing the `gads_conversion_uploads` schema or how conversions are discovered/uploaded
- Adding filters or search to the conversions page
- Real-time updates or WebSocket subscriptions
- Modifying callrail webhook ingestion or estimate correlation logic

## Decisions

### D1: Aggregate callrail via LATERAL subquery

Replace `LEFT JOIN callrail_leads cl ON cl.estimate_id = e.id::varchar` with:
```sql
LEFT JOIN LATERAL (
    SELECT COUNT(*)::int AS call_count
    FROM callrail_leads cl
    WHERE cl.estimate_id = e.id::varchar
) call_agg ON true
```
**Rationale**: A LATERAL subquery guarantees one row regardless of how many calls exist. We only need the count in the main view; full call records are fetched on demand.
**Alternative**: `DISTINCT ON` or `GROUP BY` at the outer level — messier and harder to reason about with the existing pivot joins.

### D2: Aggregate estimate_options via LATERAL subquery

Replace `LEFT JOIN estimate_options eo ON eo.estimate_id = e.id AND eo.approval_status IN (...)` with:
```sql
LEFT JOIN LATERAL (
    SELECT COALESCE(SUM(eo.total_amount), 0) AS total_amount
    FROM estimate_options eo
    WHERE eo.estimate_id = e.id
      AND eo.approval_status IN ('approved', 'pro approved')
) eo_agg ON true
```
**Rationale**: Multiple approved options can exist per estimate. SUM gives the total estimate value, matching the intent of "what is this conversion worth?". When `total_amount_source = 'JOB'`, the job amount is used instead (1:1 via `conv.job_id`).
**Alternative**: Pick MAX or first option — loses information and doesn't match business intent.

### D3: Booking source priority: form > call > null

```sql
CASE
    WHEN e.is_booking_form = true THEN 'form'
    WHEN call_agg.call_count > 0 THEN 'call'
    ELSE NULL
END
```
**Rationale**: `is_booking_form` indicates the original booking channel. Calls are follow-up activity. Form takes priority because it's the conversion trigger.

### D4: Lazy-load call records on row expand

When user expands a row and `call_count > 0`, fire:
```ts
supabase.from('callrail_leads')
  .select('callrail_id, event_type, call_type, duration, call_started_at, direction, source, gclid, lead_status, answered')
  .eq('estimate_id', row.estimate_id)
  .order('call_started_at', { ascending: false })
```
**Rationale**: Fetching all call records upfront for every estimate would be wasteful. Most rows won't be expanded. TanStack Query caches results per estimate_id, so repeated expands don't re-fetch.
**Alternative**: Include call data in the view as a JSONB array — would work but makes the main query heavier and the view harder to maintain.

### D5: Pipeline phase visual design

Replace flat icon columns with a connected 3-phase pipeline strip. Each phase cell shows:
- Status icon + colored background (green/amber/red/gray)
- Connector line between phases showing progression
- Key data point beneath: uploaded date or error message

Uses CSS-only transitions and the existing Horizon theme tokens. No animation library needed.

## Risks / Trade-offs

- **[LATERAL subquery performance]** → The WHERE clause already filters to estimates with at least one `gads_conversion_uploads` row, limiting the result set. LATERAL subqueries on this filtered set should be fast. Monitor if the estimates table grows large.
- **[Callrail RLS grants]** → The lazy-load query requires `authenticated` to SELECT from `callrail_leads`. Need to verify existing grants or add them. → Check and add grant in migration if missing.
- **[SUM vs single option]** → If the business later wants per-option breakdown, the SUM approach loses that granularity in the main view. → Acceptable trade-off; per-option detail could be added to the expanded panel if needed.
