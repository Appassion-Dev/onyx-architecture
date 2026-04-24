## Why

The current `vw_gads_conversion_pipeline` view has a `LEFT JOIN callrail_leads` that produces duplicate rows when multiple calls correlate to the same estimate. The `estimate_options` join also risks 1:N duplication if multiple options are in approved state. Additionally, the conversions table UI lacks visual pipeline progression and has no way to see call history associated with an estimate.

## What Changes

- **Fix SQL view duplication**: Replace direct `LEFT JOIN callrail_leads` and `LEFT JOIN estimate_options` with aggregating subqueries (`COUNT` for calls, `SUM` for option amounts) to guarantee one row per estimate.
- **Add `call_count` column**: New integer column on the pipeline view showing how many callrail records are associated with each estimate.
- **Lazy-load call details**: When a row is expanded, fetch full callrail records for that estimate via a separate query.
- **Call history table**: Render a compact table of all calls (date, type, duration, source, lead status, GCLID) in the expanded detail panel.
- **Visual pipeline enhancement**: Redesign the Booking → Qualified → Converted columns to visually show phase progression with connectors, status baked into each phase cell, and relevant per-phase data visible in the table row.

## Capabilities

### New Capabilities
- `pipeline-view-fix`: Fix SQL view to eliminate row duplication from 1:N joins (callrail aggregation, estimate_options aggregation) and add call_count column.
- `call-detail-panel`: Lazy-loaded call history table in the expanded detail panel, showing all callrail records for an estimate.
- `pipeline-phase-visuals`: Enhanced visual representation of conversion phases as a connected pipeline with status and data baked into each phase cell.

### Modified Capabilities

_(none — the previous `conversions-pipeline-pivot` change is complete; this builds on top)_

## Impact

- **SQL**: Migration to `CREATE OR REPLACE VIEW vw_gads_conversion_pipeline` — replaces existing view definition.
- **Frontend**: `ConversionsPage.tsx` — updated `PipelineRow` interface, new call detail query, redesigned pipeline columns and expanded detail panel.
- **Supabase RLS**: `callrail_leads` table needs SELECT granted to `authenticated` role for the lazy-load query (verify existing grants).
