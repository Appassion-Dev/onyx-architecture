## Context

The Google Ads offline conversion pipeline currently uses three SQL discovery functions, an upload edge function, and a pipeline view. The three discovery functions (`get_pending_booking_lead_conversions`, `get_pending_qualified_lead_conversions`, `get_pending_converted_lead_conversions`) were built with narrow criteria: booking = form-only, qualified = work_status complete, converted = job complete. The pipeline schema (`gads_conversion_uploads` with unique on `(estimate_id, conversion_type)`) and config table (`gads_conversion_config`) remain unchanged. Only the discovery logic, the pipeline view, and the value/datetime calculations change.

Key tables involved: `estimates`, `estimate_options`, `booking_tags`, `callrail_leads`, `customers`, `gads_conversion_uploads`, `gads_conversion_config`.

## Goals / Non-Goals

**Goals:**
- Rewrite the three discovery SQL functions to use the revised stage criteria
- Update `vw_gads_conversion_pipeline` to reflect new criteria and value calculations
- Keep the pipeline fully estimate-centric (no jobs table dependency)
- Maintain idempotent discovery via `ON CONFLICT (estimate_id, conversion_type) DO NOTHING`

**Non-Goals:**
- Changing the upload edge function logic (skip/retry/upload mechanics stay the same)
- Changing the `gads_conversion_uploads` or `gads_conversion_config` schema
- Adding new conversion types beyond booking_lead, qualified_lead, converted_lead
- Modifying the CallRail correlation trigger or booking form ingestion

## Decisions

### 1. Booking source detection via OR chain, not a single flag

**Decision**: Check four signals in a single query with LEFT JOINs and an OR-based WHERE clause rather than adding a new computed column.

**Rationale**: The four signals live in different tables (`estimates.is_booking_form`, `booking_tags`, `callrail_leads`, `estimates.lead_source`). A computed column would require a trigger to maintain. The OR chain in the WHERE clause is straightforward and the joins are already indexed.

**SQL shape**:
```sql
WHERE e.is_booking_form = true
   OR EXISTS (SELECT 1 FROM booking_tags bt WHERE bt.estimate_id = e.id)
   OR EXISTS (SELECT 1 FROM callrail_leads cl WHERE cl.estimate_id = e.id)
   OR e.lead_source IS NOT NULL
```

**Alternative considered**: Adding a materialized `has_source` boolean column on estimates. Rejected — adds trigger maintenance overhead for a query that runs on a cron schedule (not user-facing latency).

### 2. Qualified gate = total_amount IS NOT NULL on any option

**Decision**: Use `EXISTS (SELECT 1 FROM estimate_options eo WHERE eo.estimate_id = e.id AND eo.total_amount IS NOT NULL)` as the qualified gate. Value is computed separately as SUM of approved options only.

**Rationale**: The gate (has been quoted) and the value (approved amount) are intentionally decoupled. An estimate enters the qualified stage as soon as any option has a dollar figure, but the reported value only includes approved amounts. This may yield $0 values at the qualified stage, which is acceptable — it tells Google "this lead progressed" without overstating value.

### 3. Converted gate = approval_status check, not job completion

**Decision**: Move the converted stage entirely off the `jobs` table. Gate on `EXISTS (SELECT 1 FROM estimate_options eo WHERE eo.estimate_id = e.id AND eo.approval_status IN ('approved', 'pro approved'))`.

**Rationale**: Approval is the meaningful business event — the customer said yes. Job completion is an operational step that may lag significantly. Reporting approval as the conversion gives Google a faster signal for Smart Bidding optimization.

**Trade-off**: Google never learns actual job revenue, only approved estimate amounts. If actual revenue differs significantly from approved amounts, bidding optimization may be slightly less accurate.

### 4. Converted datetime = MAX(estimate_options.updated_at) where approved

**Decision**: Use the most recent `updated_at` from approved options rather than `estimates.updated_at`.

**Rationale**: The option's `updated_at` reflects when the approval actually happened. The estimate's `updated_at` may change for unrelated reasons (notes edited, etc.).

### 5. Single migration replacing all three functions + view

**Decision**: Ship one migration that `CREATE OR REPLACE`s all three discovery functions and recreates the pipeline view.

### 6. Qualified and converted discovery require a booking_lead row to exist

**Decision**: Add `EXISTS (SELECT 1 FROM gads_conversion_uploads WHERE estimate_id = e.id::text AND conversion_type = 'booking_lead')` as a required condition in both `get_pending_qualified_lead_conversions` and `get_pending_converted_lead_conversions`.

**Rationale**: Without this gate, estimates created directly in HousecallPro (no form, no CallRail, no lead_source) enter the pipeline at the qualified or converted stage with no ad-tracking context and no GCLID. These rows serve no purpose — they will always be skipped at upload time and pollute the conversions dashboard with non-ad traffic.

**How it works**: The wrapper `discover_pending_conversions()` already inserts booking leads *before* running qualified and converted discovery. So within a single cron run, freshly-discovered booking leads are immediately visible to the downstream passes.

**Trade-off**: If `booking_lead` discovery is disabled in `gads_conversion_config` (enabled=false), no qualified or converted leads will be discovered either — even for estimates that genuinely came from ads. This coupling is accepted; disabling booking lead discovery is not a normal operating state.

**Alternative considered**: Option A — duplicate the source signal OR-chain inside each downstream function. Rejected because it creates three diverging copies of the same logic. The booking_lead row IS the authoritative proof of source signal.

**Cleanup note**: Existing `pending` rows in `gads_conversion_uploads` for estimates without a booking_lead row are not automatically removed by this change. They will continue to appear in the view until they are uploaded or skipped. No cleanup migration is included; the natural upload cycle will drain them as skipped.

**Rationale**: The functions and view are tightly coupled to the same criteria definitions. Splitting across migrations risks an inconsistent intermediate state where the view shows different criteria than discovery.

## Risks / Trade-offs

- **Broader booking criteria increases pending volume** → Most additional records will lack GCLID and be skipped at upload. The `gads_conversion_uploads` table will have more `status='skipped'` rows. This is acceptable — it provides visibility into the full funnel even when upload isn't possible.
- **Qualified value may be $0** → When an estimate has been quoted but nothing approved yet, the conversion value sent to Google is $0. This is by design but may look odd in the dashboard. Consider displaying "—" for $0 values in the UI.
- **Converted and qualified have the same value formula** → Both compute `SUM(approved options / 100)`. The stages differ only in their gate condition. This is intentional — qualified fires earlier (any amount exists), converted fires later (amount is approved).
- **Backfill consideration** → Existing `gads_conversion_uploads` rows were created under old criteria. New discovery will find estimates that now qualify but were previously excluded. These will be inserted as new pending rows on the next cron cycle. Previously uploaded rows are unaffected due to `ON CONFLICT DO NOTHING`.
