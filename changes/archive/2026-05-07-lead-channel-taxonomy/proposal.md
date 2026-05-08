## Why

The conversions pipeline groups estimates by a coarse medium (calls / form / thumbtack / other) that obscures which marketing channel actually generated the lead. The ONYX lead channel taxonomy defines seven semantic channels (Google Ads, GLS, GMB, Thumbtack, Organic, Direct, Others) that map directly to spend categories, but this taxonomy is not reflected anywhere in the database view or dashboard UI. Additionally, `estimates.lead_source` is incorrectly populated for booking-form estimates (it receives the HCP API's null value rather than the resolved channel), and `customers.lead_source` is overwritten on every repeat booking regardless of the attribution window — silently corrupting channel data for returning customers.

## What Changes

- Add a write-time channel resolver in the `hcp-booking` edge function that reads the existing customer's `lead_source` and `created_at` before writing; protects the original attribution for repeat customers within a 90-day window; and writes the resolved channel to `estimates.lead_source` (not just to the customer row).
- Expand the `booking_tags` lateral join in `vw_conversion_candidates` to surface `utm_source`, `utm_medium`, `hsa_src`, and `ref` as named columns alongside the existing `gclid`.
- Add a `channel` computed column to `vw_conversion_candidates` using a single SQL CASE resolver that evaluates signals in taxonomy priority order: Thumbtack → Google Ads → GLS → GMB → Organic → Direct → Others.
- Replace the TypeScript `classifySourceBucket()` function in `ConversionsPage.tsx` with a `classifyChannel()` function that reads the view's `channel` column directly.
- Update `buildHierarchy()` to group by channel (7 taxonomy values) instead of source bucket (4 medium values).
- Update `vw_gads_upload_reconciliation_daily` source-bucket columns to align with the taxonomy channel labels.

## Capabilities

### New Capabilities
- `lead-channel-resolver`: Write-time logic in `hcp-booking` that resolves and persists a taxonomy-aligned channel string to `estimates.lead_source`, with a 90-day repeat-customer attribution guard.
- `conversion-channel-grouping`: SQL view column and TypeScript grouping logic that classify each conversion candidate by taxonomy channel and group the weekly rollup accordingly.

### Modified Capabilities
- `conversion-candidates-view`: The view gains `channel`, `form_utm_source`, `form_utm_medium`, `form_hsa_src`, and `form_ref` columns; the existing `first_touch_medium` and `lead_source` columns are retained as supporting signals.
- `conversions-filter-bar`: The source filter dropdown options change from medium buckets (Calls / Form / Other) to taxonomy channels (Google Ads / GLS / GMB / Organic / Direct / Thumbtack / Other).

## Impact

- `supabase/functions/hcp-booking/supabase-writer.ts` — write-time resolver and attribution guard logic.
- `supabase/migrations/` — new migration recreating `vw_conversion_candidates` with expanded `booking_tags` lateral and `channel` CASE column.
- `supabase/migrations/` — new migration recreating `vw_gads_upload_reconciliation_daily` with taxonomy-aligned source columns.
- `horizon-dashboard/src/components/pages/ConversionsPage.tsx` — `classifyChannel()`, `buildHierarchy()` grouping key, filter dropdown options, and source group labels/colors.
- Existing rows (pre-fix) are handled by the SQL fallback chain in the `channel` CASE: `booking_tags[gclid/hsa_src/utm_source]` → `callrail_leads.source` → `other`. No backfill migration required.
