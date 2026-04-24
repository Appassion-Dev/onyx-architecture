## Context

The ConversionsPage expanded row currently uses a generic `StageDetail` component that renders flat metadata (status, GCLID, date, value). The underlying evidence data lives in three separate tables: `booking_tags` (form submission tracking), `estimate_options` (quote details), and `jobs` (job records). All tables are already available via Supabase client queries.

The existing `CallHistoryTable` component demonstrates the lazy-fetch-on-expand pattern — query data with `useQuery` when the expanded section renders.

## Goals / Non-Goals

**Goals:**
- Each pipeline stage's expanded detail includes the relevant evidence sub-section
- Data is lazy-fetched on expand (same pattern as existing `CallHistoryTable`)
- No new SQL views or migrations — query existing tables directly

**Non-Goals:**
- Editing or mutating data from the detail view (read-only)
- Adding new columns to the pipeline view
- Changing the collapsed row summary

## Decisions

### 1. Three new sub-components inside PipelineRowItem

- `BookingTagsTable` — fetches `booking_tags WHERE estimate_id = $id`, renders as key-value table with friendly label mapping
- `EstimateOptionsTable` — fetches `estimate_options WHERE estimate_id = $id ORDER BY total_amount DESC`, renders with approval status badges
- `JobDetailSection` — fetches jobs via two-hop: `jobs WHERE original_estimate_id IN (SELECT id FROM estimate_options WHERE estimate_id = $id)`, renders job status, total, outstanding balance

**Why sub-components vs. expanding StageDetail**: StageDetail is a generic metadata display. The evidence sections are table-structured with their own fetching logic. Keeping them as separate components maintains the existing pattern established by `CallHistoryTable`.

### 2. Job lookup uses Supabase nested select

`supabase.from('jobs').select('*').in('original_estimate_id', optionIds)` where optionIds come from the estimate_options query already in `EstimateOptionsTable`. This avoids needing a new SQL view or RPC.

**Alternative considered**: Single lateral join in the pipeline view. Rejected because it adds query cost to every pipeline load, not just when expanded.

### 3. Calls section moves inside Booking Lead

The `CallHistoryTable` component moves from the bottom of the expanded area into the Booking Lead stage section. When `call_count = 0`, show a muted "No calls recorded" message instead of hiding the section entirely — this confirms to the user that we checked rather than leaving them wondering.

### 4. Friendly label mapping for booking_tags

Map `hsa_*` keys to readable labels: `gclid` → "GCLID", `hsa_kw` → "Keyword", `hsa_mt` → "Match Type", `hsa_cam` → "Campaign", `hsa_src` → "Network", `hsa_grp` → "Ad Group", `hsa_ad` → "Ad", `hsa_tgt` → "Target". Skip `hsa_ver` and `ref` (internal/noisy).

## Risks / Trade-offs

- **[N+1 queries on expand]** → Each expanded row fires up to 3 queries. Acceptable because only one row is typically expanded, and `useQuery` caches results.
- **[Job may not exist yet]** → Graceful fallback "No job created yet" message. The Converted section always renders regardless of `converted_status`.
- **[Multiple jobs per estimate]** → Theoretically possible if multiple options were approved and each created a job. Render all found jobs. In practice, typically 0 or 1.
