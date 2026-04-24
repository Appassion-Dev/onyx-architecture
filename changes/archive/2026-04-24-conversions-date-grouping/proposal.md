## Why

The sales table and conversions page group estimates by date, but use different date fields — the sales table uses `jobs.created_at` (when an estimate was approved and booked) while the conversions page uses `estimates.created_at` (when the lead first came in). This means the same estimate lands in a different week on each page, making cross-page comparison unreliable. Before changing anything, the tradeoffs need to be evaluated and a deliberate decision made.

## What Changes

- **Decision needed**: Whether to keep `estimate_created_at` as the conversions page grouping date, or switch approved estimates to group by `job_created_at` (mirroring the sales table logic)
- If the job-date approach is chosen:
  - Add `j.created_at AS job_created_at` to the LATERAL job subquery in `vw_conversion_candidates`
  - Update `getRowDateKeys()` in `ConversionsPage.tsx` to use a CASE: approved → `job_created_at`, else → `estimate_created_at`
  - Revisit the 90-day cutoff filter (currently `.gte('estimate_created_at', cutoff)`) — mixing grouping and filter dates would be inconsistent
- Alternatively: keep `estimate_created_at` as the grouping date everywhere, and instead expose a secondary "booked date" column in the conversions table for reference

## Capabilities

### New Capabilities
- `conversions-date-grouping`: Defines which date field governs how estimates are bucketed into weeks and fiscal months on the conversions page, and under what conditions (approval status) that date field changes

### Modified Capabilities
<!-- none — no existing specs exist yet -->

## Impact

**Key tradeoffs identified during exploration:**

1. **"Moving estimate" problem** — If we group approved estimates by `job_created_at`, an estimate changes week buckets the moment it gets approved. An estimate you saw in Week 14 yesterday could appear in Week 16 today after a customer signs. This is potentially confusing.

2. **Cutoff filter mismatch** — The 90-day window currently filters by `estimate_created_at`. If grouping switches to `job_created_at` for approved rows, an estimate from 91 days ago whose job was booked 3 days ago would be invisible. The filter and grouping date would need to align.

3. **Conceptual purpose** — The conversions page serves a Google Ads attribution purpose: "for leads generated in this window, what percentage became jobs?" That question is naturally anchored to `estimate_created_at`. The sales table answers "when did revenue land?", which is naturally `job_created_at`. These may be intentionally different.

4. **`converted_datetime` alternative** — The `converted_datetime` field already captures the timestamp of the converted-lead upload event (tied to job booking). This could be used as a "booked date" display column without changing the grouping logic.

**Code affected:**
- `supabase/migrations/` — new migration for `vw_conversion_candidates` if `job_created_at` is added
- `horizon-dashboard/src/components/pages/ConversionsPage.tsx` — `getRowDateKeys()` function and the Supabase query cutoff filter
- `horizon-dashboard/src/lib/database.types.ts` — if new column added to view
