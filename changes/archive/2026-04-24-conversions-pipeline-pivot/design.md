## Context

The conversions page (`ConversionsPage.tsx`) displays Google Ads offline conversion uploads in a 3-level collapsible hierarchy: month → week → conversion type → individual conversion rows. Each conversion row maps to one record in `gads_conversion_uploads` via the `vw_gads_conversions` view.

The problem: a single estimate can have up to 3 conversion types (booking_lead, qualified_lead, converted_lead), each appearing in a separate collapsible type group. Users must mentally join scattered rows to understand one estimate's pipeline status.

The current view (`vw_gads_conversions`) returns one row per conversion upload. The new design pivots this into one row per estimate with per-stage columns.

## Goals / Non-Goals

**Goals:**
- One row per estimate showing full pipeline state (Booking → Qualified → Converted)
- Sync status per pipeline stage using Lucide icons
- Dedicated "Source" column for booking origin (Form, Call)
- Value column matching the sales page logic (`estimates_settings.total_amount_source`)
- "Closed" flag when all existing stages are synced
- Expandable rows for per-stage detail
- Week/month rollups showing count + total value

**Non-Goals:**
- Per-type or per-status filters (removed; may return later)
- Changing the discovery or upload pipeline logic
- Modifying the conversion config page
- Supporting Google LSA source (future — but the Source column design accommodates it)

## Decisions

### 1. New SQL view `vw_gads_conversion_pipeline` instead of client-side pivot

**Decision**: Create a new Postgres view that pivots conversion data by estimate, rather than doing the pivot in JavaScript.

**Rationale**: The pivot requires joining `estimate_options` and `estimates_settings` (for value logic) which the existing view doesn't include. A SQL pivot with conditional aggregation (`MAX(CASE WHEN ...)`) is more maintainable and avoids shipping extra rows to the client. The existing `vw_gads_conversions` view remains untouched for other consumers.

**Alternative considered**: Client-side grouping from the existing view + a separate RPC call for estimate values. Rejected because it doubles the round trips and duplicates join logic.

### 2. Value column uses sales page CASE logic

**Decision**: The pipeline view computes `display_value` as:
```sql
CASE
    WHEN es.total_amount_source = 'JOB' THEN j.total_amount / 100.0
    ELSE eo.total_amount / 100.0
END
```

Where `eo` is the first approved `estimate_option` and `j` is the linked job (if one exists). This matches `fn_get_sales_table_data`.

**Rationale**: Consistency with the sales page. Users already understand this value.

### 3. Booking source derived from `is_booking_form` and `callrail_leads`

**Decision**: The view exposes a `booking_source` column:
- `'form'` when `estimates.is_booking_form = true`
- `'call'` when a `callrail_leads` record exists for the estimate
- `NULL` otherwise (shouldn't happen for rows that have a booking_lead conversion, but safe fallback)

**Rationale**: `is_booking_form` already flags website form submissions. CallRail correlation is handled by the existing trigger. A future LSA source can be added as a third case.

### 4. Closed flag is a SQL computed boolean

**Decision**: `is_closed` is computed in the view as: every existing stage has `status IN ('uploaded', 'skipped')`. This is expressed as:
```sql
(booking_status IS NULL OR booking_status IN ('uploaded', 'skipped'))
AND (qualified_status IS NULL OR qualified_status IN ('uploaded', 'skipped'))
AND (converted_status IS NULL OR converted_status IN ('uploaded', 'skipped'))
-- AND at least one stage exists
AND (booking_status IS NOT NULL OR qualified_status IS NOT NULL OR converted_status IS NOT NULL)
```

**Rationale**: Keeps the UI stateless — the view does the work.

### 5. Date anchor is `estimate_created_at`

**Decision**: Each pipeline row is grouped into a week/month based on `estimates.created_at`, not the individual conversion datetimes.

**Rationale**: An estimate's conversion stages can fire weeks apart. Using the estimate creation date means each estimate appears in exactly one week group, representing when the lead entered the funnel.

### 6. Icon set from Lucide (shadcn compatible)

**Decision**: Pipeline cell icons:

| State | Lucide Icon | Color |
|-------|-------------|-------|
| Uploaded | `CheckCircle2` | `#01b574` (green) |
| Pending | `Clock` | `#ffb547` (amber) |
| Error | `XCircle` | `#ee5d50` (red) |
| Skipped | `MinusCircle` | `#a3aed0` (gray) |
| No stage | `—` text dash | `#a3aed0` |
| Closed | `CheckSquare` | `#01b574` |
| Not closed | `Square` | `#a3aed0` |

**Rationale**: Consistent with the existing Horizon dashboard design tokens. No emoji.

### 7. Expandable detail rows

**Decision**: Clicking a pipeline row expands an inline detail panel showing each existing stage's full data: source, GCLID, value, upload timestamp, error message, upload attempts.

**Rationale**: The compact pipeline row can't show everything. The detail panel replaces what the old per-type expansion showed.

## Risks / Trade-offs

**[View performance with conditional aggregation]** → The pivot view uses `MAX(CASE WHEN conversion_type = ... ...)` across 3 types per column. With current data volume (hundreds of rows) this is negligible. If volume grows to tens of thousands, adding an index on `(estimate_id, conversion_type)` would help. The existing unique constraint already provides this index.

**[Estimate options join complexity]** → An estimate can have multiple options. The view needs to pick the right one (first approved, or the primary option). Mitigation: match the same logic used in `vw_approved_estimates_detailed` — join on `estimate_options` with `approval_status IN ('approved', 'pro approved')` and take the first by `option_number`.

**[Rows without estimate data]** → If an estimate is deleted from HousecallPro but conversion uploads remain, the row will have NULL estimate data. Mitigation: COALESCE fallbacks (show estimate_id prefix instead of estimate_number).

**[No filters initially]** → Removing filters simplifies the first version but may be missed for debugging. Mitigation: the browser's Cmd+F still works, and filters can be re-added in a follow-up.
